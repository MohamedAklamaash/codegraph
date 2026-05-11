import logging
from urllib.parse import urlparse

import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth_github.crypto import decrypt
from apps.auth_github.models import GitHubIdentity

from ._view_helpers import get_user_repo_or_404, normalize_or_400
from .models import RepoStatus, Repository, RepositoryAccess
from .serializers import RepositorySerializer
from .tasks import ingest_repository
from .utils import parse_github_owner_repo as _parse_github_owner_repo

logger = logging.getLogger(__name__)

# Hosts the gateway accepts for repo submission. We deliberately do NOT
# accept raw.githubusercontent.com or any other subdomain — `_can_grant_access`
# only knows how to talk to api.github.com/repos/{owner}/{name} and the cloner
# only knows the canonical github.com/{owner}/{name}.git form.
ALLOWED_HOSTS_GITHUB = ("github.com",)
# Non-github hosts that we treat as "public URL"; access is granted on
# submission without a probe (caller cannot privately authenticate to them).
ALLOWED_PUBLIC_HOSTS_NON_GITHUB = ("gitlab.com", "bitbucket.org")


def _normalize_url(raw: str) -> str:
    """Normalize a user-supplied repo URL.

    Raises ValueError("unsupported_scheme"|"unsupported_host"|"missing_host")
    on invalid input. Forces https for github.com and lowercases the host
    and (for github URLs) the path so that case-only variants collapse to
    a single Repository row. Strips default ports and a trailing ``.git`` /
    trailing slash.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)

    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        raise ValueError("unsupported_scheme")

    netloc = (parsed.netloc or "").strip()
    if not netloc:
        raise ValueError("missing_host")

    # Strip default ports — e.g. github.com:443 == github.com.
    host_only = netloc.split(":", 1)[0].lower()
    if ":" in netloc:
        _, port = netloc.split(":", 1)
        if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
            netloc = host_only
        else:
            netloc = f"{host_only}:{port}"
    else:
        netloc = host_only

    # GitHub paths are case-insensitive; lowercase for stable equality.
    is_github = host_only in ALLOWED_HOSTS_GITHUB
    is_other_known = host_only in ALLOWED_PUBLIC_HOSTS_NON_GITHUB
    if not (is_github or is_other_known):
        raise ValueError("unsupported_host")

    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if is_github:
        path = path.lower()
        # github URLs always normalize to https.
        scheme = "https"
        # Default port already stripped above; this also drops the port for
        # the http→https rewrite case (http://github.com:80/x/y → https://github.com/x/y).
        netloc = host_only

    # All allowed hosts (github/gitlab/bitbucket) follow the
    # `/{owner}/{name}` shape. A single-segment path like
    # `https://github.com/onlyone` would create a dead Repository row that
    # `_can_grant_access` and the cloner can't act on. Reject it up front.
    segments = [s for s in path.split("/") if s]
    if len(segments) != 2:
        raise ValueError("invalid_repo_path")

    return f"{scheme}://{netloc}{path}"


def _get_github_token(user):
    try:
        identity = user.github_identity
    except GitHubIdentity.DoesNotExist:
        return None, None
    if identity.needs_reauth:
        return None, identity
    try:
        return decrypt(identity.access_token_enc), identity
    except Exception:
        identity.needs_reauth = True
        identity.save(update_fields=["needs_reauth", "updated_at"])
        return None, identity


def _probe_github(owner: str, name: str, token: str | None = None) -> dict:
    """Hit api.github.com/repos/{owner}/{name} and summarize the result.

    Returns ``{"status": int, "is_private": bool|None, "needs_reauth": bool}``.
    ``status == 0`` means the network call itself failed (treat as unknown).
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as e:
        logger.warning("GitHub probe network error for %s/%s: %s", owner, name, type(e).__name__)
        return {"status": 0, "is_private": None, "needs_reauth": False}

    is_private = None
    if resp.status_code == 200:
        try:
            is_private = bool(resp.json().get("private"))
        except ValueError:
            is_private = None
    return {
        "status": resp.status_code,
        "is_private": is_private,
        "needs_reauth": resp.status_code == 401 and bool(token),
    }


def _can_grant_access(user, repo: Repository):
    """Return ``(allowed, source)`` where source is one of:

    - ``"public_url"`` — non-github, or github confirmed public.
    - ``"github"`` — private github repo, user authed and has access.
    - ``"no_access"`` — user not allowed.
    - ``"needs_reauth"`` — user's GitHub token is invalid; UI should re-auth.
    - ``"github_unreachable"`` — network failure talking to GitHub; fail closed.
    """
    owner, name = _parse_github_owner_repo(repo.url)

    # Non-github URL — no probe path. Defensive: `_normalize_url` already
    # rejects unsupported hosts before this is called.
    if not owner or not name:
        return True, "public_url"

    token, identity = _get_github_token(user)

    # If we don't yet know whether the repo is private, probe to find out.
    if repo.is_private is None:
        probe = _probe_github(owner, name, token=token if token else None)
        if probe["status"] == 0:
            return False, "github_unreachable"

        if probe["needs_reauth"]:
            if identity:
                identity.needs_reauth = True
                identity.save(update_fields=["needs_reauth", "updated_at"])
            return False, "needs_reauth"

        if probe["status"] == 200:
            repo.is_private = bool(probe["is_private"])
            repo.save(update_fields=["is_private", "updated_at"])
        elif probe["status"] == 404:
            if not token:
                # Anonymous probe got 404 — could be private (we can't tell)
                # or could be deleted. Treat as private and fall through to
                # the auth path, which will reject (no_access).
                repo.is_private = True
                # Don't persist this guess to the DB — a future authed user
                # may flip it. Keep `is_private` cached only for this request.
            else:
                # Authed probe got 404 → user has no access to this repo.
                return False, "no_access"
        else:
            # 403, 5xx, etc — fail closed.
            return False, "github_unreachable"

    # Now `repo.is_private` is known (True/False) for this request.
    if repo.is_private is False:
        return True, "public_url"

    # Private github repo. Require an authed probe returning 200.
    if not token:
        return False, "no_access"
    authed = _probe_github(owner, name, token=token)
    if authed["status"] == 0:
        return False, "github_unreachable"
    if authed["needs_reauth"]:
        if identity:
            identity.needs_reauth = True
            identity.save(update_fields=["needs_reauth", "updated_at"])
        return False, "needs_reauth"
    if authed["status"] == 200:
        return True, "github"
    return False, "no_access"


_NEGATIVE_REASON_TO_RESPONSE = {
    "needs_reauth": (401, {"error": "needs_reauth"}),
    "github_unreachable": (503, {"error": "github_unreachable"}),
    "no_access": (403, {"error": "no_access"}),
}


def _negative_response(reason: str) -> Response:
    status, body = _NEGATIVE_REASON_TO_RESPONSE.get(reason, (403, {"error": "no_access"}))
    return Response(body, status=status)


class RepositoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        normalized, err = normalize_or_400(request.data.get("url", ""), _normalize_url)
        if err is not None:
            return err
        if not normalized:
            return Response({"error": "url required"}, status=400)

        name = normalized.split("/")[-1]
        repo, created = Repository.objects.get_or_create(
            url=normalized,
            defaults={"name": name, "first_ingested_by": request.user},
        )

        allowed, source = _can_grant_access(request.user, repo)
        if not allowed:
            # Don't leak a freshly-created Repository row for a user who
            # turned out to have no access (or whose probe failed).
            if created:
                repo.delete()
            return _negative_response(source)

        RepositoryAccess.objects.get_or_create(
            user=request.user,
            repository=repo,
            defaults={"role": "owner", "source": source},
        )

        should_ingest = created or repo.status == RepoStatus.FAILED
        if should_ingest:
            if not created:
                repo.status = RepoStatus.PENDING
                repo.status_message = ""
                repo.save(update_fields=["status", "status_message", "updated_at"])
            ingest_repository.delay(str(repo.id), str(request.user.id))

        return Response(RepositorySerializer(repo).data, status=201 if created else 200)

    def get(self, request, repo_id=None):
        if repo_id:
            repo, err = get_user_repo_or_404(request.user, repo_id)
            if err is not None:
                return err
            return Response(RepositorySerializer(repo).data)
        repos = (
            Repository.objects.filter(accesses__user=request.user)
            .distinct()
            .order_by("-created_at")
        )
        return Response(RepositorySerializer(repos, many=True).data)


class RepositoryAttachView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        repo_id = request.data.get("repo_id")
        url = request.data.get("url")

        repo = None
        if repo_id:
            repo = Repository.objects.filter(id=repo_id).first()
        elif url:
            normalized, err = normalize_or_400(url, _normalize_url)
            if err is not None:
                return err
            if normalized:
                repo = Repository.objects.filter(url=normalized).first()

        if not repo:
            return Response({"error": "not found"}, status=404)

        allowed, source = _can_grant_access(request.user, repo)
        if not allowed:
            return _negative_response(source)

        RepositoryAccess.objects.get_or_create(
            user=request.user,
            repository=repo,
            defaults={"role": "member", "source": source},
        )
        return Response(RepositorySerializer(repo).data, status=200)
