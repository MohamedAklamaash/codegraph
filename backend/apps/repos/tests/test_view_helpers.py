"""Unit tests for `apps.repos._view_helpers` and the `RepoStatus` enum.

Covers:
- `normalize_or_400(raw_url, normalize_fn)` — wraps a normalize function and
  converts `ValueError` into a DRF 400 `Response` with `{"error": "invalid_url",
  "detail": <ValueError args>}`.
- `get_user_repo_or_404_response(user, repo_id)` — returns `(repo, None)` for
  a user with a `RepositoryAccess` row, else `(None, Response(..., status=404))`.
- `RepoStatus` TextChoices — sanity check on the value-strings since the
  frontend mirrors them (`frontend/src/constants/repoStatus.ts`).
"""
import uuid

import pytest
from django.contrib.auth.models import User

from apps.repos._view_helpers import (
    get_user_repo_or_404_response,
    normalize_or_400,
)
from apps.repos.models import RepoStatus, Repository, RepositoryAccess
from apps.repos.views import _normalize_url


# ---------------------------------------------------------------------------
# normalize_or_400
# ---------------------------------------------------------------------------


class TestNormalizeOr400:
    """No DB needed — pure-function wrapper around the normalize callable."""

    def test_valid_github_url_returns_normalized_string(self):
        normalized, err = normalize_or_400("https://github.com/X/Y", _normalize_url)
        assert err is None
        assert normalized == "https://github.com/x/y"

    def test_valid_gitlab_url_returns_normalized_string(self):
        normalized, err = normalize_or_400("https://gitlab.com/team/proj", _normalize_url)
        assert err is None
        # Non-github hosts keep case in the path; only host is lowercased.
        assert normalized.startswith("https://gitlab.com/")

    def test_unsupported_scheme_returns_400(self):
        normalized, err = normalize_or_400("file:///etc/passwd", _normalize_url)
        assert normalized is None
        assert err is not None
        assert err.status_code == 400
        assert err.data["error"] == "invalid_url"
        assert err.data["detail"] == "unsupported_scheme"

    def test_unsupported_host_returns_400(self):
        normalized, err = normalize_or_400("https://example.com/x/y", _normalize_url)
        assert normalized is None
        assert err is not None
        assert err.status_code == 400
        assert err.data["error"] == "invalid_url"
        assert err.data["detail"] == "unsupported_host"

    def test_missing_host_returns_400(self):
        # `https:///foo` parses to scheme=https, netloc='' -> missing_host.
        normalized, err = normalize_or_400("https:///foo", _normalize_url)
        assert normalized is None
        assert err is not None
        assert err.status_code == 400
        assert err.data["error"] == "invalid_url"
        assert err.data["detail"] == "missing_host"

    def test_response_shape_matches_existing_views_contract(self):
        """The repos view-level tests assert `resp.json()["error"] == "invalid_url"`;
        this helper must produce a Response whose body is JSON-serializable to
        the same shape."""
        _, err = normalize_or_400("git+ssh://github.com/x/y", _normalize_url)
        assert err is not None
        assert set(err.data.keys()) == {"error", "detail"}


# ---------------------------------------------------------------------------
# get_user_repo_or_404_response
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetUserRepoOr404Response:
    def test_returns_repo_when_user_has_access(self):
        user = User.objects.create_user(username="owner", password="pw")
        repo = Repository.objects.create(
            url="https://github.com/o/r",
            name="r",
            status=RepoStatus.READY,
        )
        RepositoryAccess.objects.create(user=user, repository=repo, role="owner")

        result_repo, err = get_user_repo_or_404_response(user, repo.id)

        assert err is None
        assert result_repo is not None
        assert result_repo.pk == repo.pk

    def test_returns_404_when_user_has_no_access_row(self):
        owner = User.objects.create_user(username="owner", password="pw")
        intruder = User.objects.create_user(username="intruder", password="pw")
        repo = Repository.objects.create(
            url="https://github.com/o/r",
            name="r",
            status=RepoStatus.READY,
        )
        RepositoryAccess.objects.create(user=owner, repository=repo, role="owner")

        result_repo, err = get_user_repo_or_404_response(intruder, repo.id)

        assert result_repo is None
        assert err is not None
        assert err.status_code == 404
        assert err.data == {"error": "not found"}

    def test_returns_404_for_nonexistent_repo_id(self):
        user = User.objects.create_user(username="ghost", password="pw")

        result_repo, err = get_user_repo_or_404_response(user, uuid.uuid4())

        assert result_repo is None
        assert err is not None
        assert err.status_code == 404
        assert err.data == {"error": "not found"}


# ---------------------------------------------------------------------------
# RepoStatus enum
# ---------------------------------------------------------------------------


class TestRepoStatusEnum:
    """The frontend mirrors these string values in
    `frontend/src/constants/repoStatus.ts`; a value drift here is a
    cross-stack bug. Lock the wire-strings down."""

    def test_status_values_match_frontend_mirror(self):
        assert RepoStatus.PENDING == "pending"
        assert RepoStatus.CLONING == "cloning"
        assert RepoStatus.PARSING == "parsing"
        assert RepoStatus.EMBEDDING == "embedding"
        assert RepoStatus.READY == "ready"
        assert RepoStatus.FAILED == "failed"

    def test_labels_are_human_readable(self):
        assert RepoStatus.PENDING.label == "Pending"
        assert RepoStatus.CLONING.label == "Cloning"
        assert RepoStatus.PARSING.label == "Parsing"
        assert RepoStatus.EMBEDDING.label == "Embedding"
        assert RepoStatus.READY.label == "Ready"
        assert RepoStatus.FAILED.label == "Failed"

    def test_choices_count_matches_expected(self):
        # Six states: pending / cloning / parsing / embedding / ready / failed.
        assert len(RepoStatus.choices) == 6
