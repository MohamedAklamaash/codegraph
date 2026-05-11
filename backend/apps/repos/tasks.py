import logging
import os
import re
import shutil

import git
from celery import shared_task
from django.conf import settings

from .models import RepoStatus, Repository
from .utils import parse_github_owner_repo as _parse_github_owner_repo

logger = logging.getLogger(__name__)

# Set once on import — disabling the git terminal prompt globally for the
# worker process keeps GIT_ASKPASS / interactive credential helpers from
# popping up on a clone failure (which would leave the worker hung). Setting
# this in the task body is too late on the very first invocation in a fresh
# worker, since GitPython spawns the git process before reading os.environ
# changes done in the same request.
os.environ["GIT_TERMINAL_PROMPT"] = "0"


def _set_status(repo, status, msg=""):
    repo.status = status
    repo.status_message = msg
    repo.save(update_fields=["status", "status_message"])


def _redact(msg, token: str | None) -> str:
    """Redact a token (and any URL userinfo block) from a string OR from
    the message-bearing attributes of a `git.GitCommandError`-like object.

    Accepts either a string or any object with `command`, `stdout`, `stderr`
    attributes — those three are also redacted in place AND folded into the
    returned string. This matters because Celery serializes both the
    exception args AND the attributes when propagating a failure.
    """
    if msg is None:
        return ""
    extras: list[str] = []
    if not isinstance(msg, str):
        # Treat as a GitCommandError-like exception; redact its message-bearing
        # attributes IN PLACE so any later serialization is also clean, and
        # also fold them into the returned text for logging.
        for attr in ("command", "stdout", "stderr"):
            val = getattr(msg, attr, None)
            if val is None:
                continue
            try:
                # Some attrs (`command`) may be a list — coerce to string.
                text = val.decode() if isinstance(val, (bytes, bytearray)) else str(val)
            except Exception:
                text = ""
            cleaned = _redact_text(text, token)
            try:
                setattr(msg, attr, cleaned)
            except Exception:
                # If the attr is read-only, swallow — the returned string
                # below will still be clean.
                pass
            if cleaned:
                extras.append(cleaned)
        msg = str(msg)
    base = _redact_text(msg, token)
    if extras:
        return base + " | " + " | ".join(extras)
    return base


def _redact_text(msg: str, token: str | None) -> str:
    if not msg:
        return ""
    if token:
        msg = msg.replace(token, "***")
    return re.sub(r"https://[^@\s]+@", "https://***@", msg)


def _load_identity(user_id):
    if not user_id:
        return None
    try:
        from apps.auth_github.models import GitHubIdentity
        return GitHubIdentity.objects.select_related("user").get(user_id=user_id)
    except Exception:
        return None


def _decrypt_token(identity):
    if not identity:
        return None
    try:
        from apps.auth_github.crypto import decrypt
        return decrypt(identity.access_token_enc)
    except Exception:
        return None


@shared_task
def ingest_repository(repo_id, user_id=None):
    from apps.embeddings.tasks import generate_embeddings
    from apps.parser.tasks import parse_repository

    repo = Repository.objects.get(id=repo_id)
    repo_path = os.path.join(settings.REPOS_DIR, str(repo_id))

    owner, name = _parse_github_owner_repo(repo.url)
    identity = _load_identity(user_id) if owner else None
    token = _decrypt_token(identity)

    if owner and name and token and repo.is_private is None:
        from apps.auth_github.github_api import github_get

        probe = github_get(
            token,
            f"https://api.github.com/repos/{owner}/{name}",
            timeout=15,
        )
        if not isinstance(probe, tuple):
            if probe.status_code == 200:
                try:
                    data = probe.json()
                    repo.is_private = bool(data.get("private"))
                    repo.save(update_fields=["is_private", "updated_at"])
                except ValueError:
                    pass
            elif probe.status_code == 401 and identity:
                identity.needs_reauth = True
                identity.save(update_fields=["needs_reauth", "updated_at"])
                token = None

    if repo.is_private and token and owner and name:
        clone_url = f"https://x-access-token:{token}@github.com/{owner}/{name}.git"
    else:
        clone_url = repo.url

    try:
        _set_status(repo, RepoStatus.CLONING, "Cloning repo...")
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        try:
            git.Repo.clone_from(clone_url, repo_path, depth=1)
        except git.GitCommandError as e:
            stderr = str(getattr(e, "stderr", "") or "")
            if identity and (
                e.status == 128
                and ("401" in stderr or "Authentication failed" in stderr or "could not read Username" in stderr)
            ):
                identity.needs_reauth = True
                identity.save(update_fields=["needs_reauth", "updated_at"])
            msg = _redact(e, token)
            _set_status(repo, RepoStatus.FAILED, msg)
            logger.warning("Clone failed for repo %s: %s", repo_id, msg)
            return

        _set_status(repo, RepoStatus.PARSING, "Parsing and building graph...")
        parse_repository(repo_id, repo_path)

        _set_status(repo, RepoStatus.EMBEDDING, "Generating embeddings...")
        generate_embeddings(repo_id)

        _set_status(repo, RepoStatus.READY, "Done")

    except Exception as e:
        # Outer guard: catch broader-than-GitCommandError failures and
        # re-raise as a plain RuntimeError carrying ONLY the redacted text.
        # Without this, Celery may serialize locals (including `clone_url`
        # and the original exception's stderr) into the task result.
        redacted = _redact(e, token)
        _set_status(repo, RepoStatus.FAILED, redacted)
        raise RuntimeError(redacted) from None
    finally:
        # Best-effort drop of in-scope tokenized URL.
        clone_url = None  # noqa: F841
        token = None  # noqa: F841
