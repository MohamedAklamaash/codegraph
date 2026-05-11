"""Shared helpers for the repos app.

Single source of truth for repo-access checks and GitHub URL parsing,
imported by `apps.repos.views`, `apps.repos.tasks`, and the cross-app
view modules under `apps.files`, `apps.graph`, `apps.chat`.
"""
import re

from .models import Repository


def user_has_repo_access(user, repo_id) -> bool:
    """Return True if ``user`` has any access row for ``repo_id``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return Repository.objects.filter(id=repo_id, accesses__user=user).exists()


def parse_github_owner_repo(url: str):
    """Extract (owner, name) from a github.com URL or return (None, None).

    Permissive variant: tolerates a trailing ``.git`` and a trailing slash.
    Used by both views (URL submission) and tasks (clone).
    """
    if not url:
        return None, None
    m = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        url,
        re.IGNORECASE,
    )
    if not m:
        return None, None
    return m.group(1), m.group(2)
