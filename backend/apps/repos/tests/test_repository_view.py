"""Tests for RepositoryView gating, public-URL sharing, normalization and task args
(items 4, 5, 7, 10)."""
from unittest.mock import patch

import pytest
import requests
from django.test import Client

from apps.repos.models import Repository, RepositoryAccess
from apps.repos.tests.conftest import mock_gh_response


@pytest.mark.django_db
class TestPermissionGating:
    def test_anonymous_get_returns_401_or_403(self):
        # DRF SessionAuthentication returns 403 for anonymous when login is
        # required; either 401 or 403 indicates "unauthenticated -> blocked".
        resp = Client().get("/api/repos/")
        assert resp.status_code in (401, 403)

    def test_user_b_does_not_see_user_a_repo_in_list(self, user_factory, authed_client):
        ua = user_factory(username="alice")
        ub = user_factory(username="bob")
        # Alice creates a repo.
        with patch("apps.repos.views.requests.get", return_value=mock_gh_response(404)), \
             patch("apps.repos.views.ingest_repository.delay"):
            authed_client(ua).post(
                "/api/repos/",
                data={"url": "https://github.com/some/private-thing"},
                content_type="application/json",
            )
        # Alice should still get a repo created via the public-URL fallback
        # (probe 404 with no github identity -> falls back to public_url=True).
        # But we want her to have a successful row; the test uses the simpler
        # public path with no github account, so use a non-github URL instead.
        # Re-do this test with a non-github URL to be unambiguous.
        Repository.objects.all().delete()
        RepositoryAccess.objects.all().delete()
        with patch("apps.repos.views.ingest_repository.delay"):
            resp = authed_client(ua).post(
                "/api/repos/",
                data={"url": "https://gitlab.com/alice/proj"},
                content_type="application/json",
            )
        assert resp.status_code == 201, resp.content

        # Bob's list should be empty.
        resp = authed_client(ub).get("/api/repos/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_user_b_retrieve_user_a_repo_returns_404(self, user_factory, authed_client):
        ua = user_factory(username="alice")
        ub = user_factory(username="bob")
        with patch("apps.repos.views.ingest_repository.delay"):
            r = authed_client(ua).post(
                "/api/repos/",
                data={"url": "https://gitlab.com/alice/proj"},
                content_type="application/json",
            )
        assert r.status_code == 201
        repo_id = r.json()["id"]

        resp = authed_client(ub).get(f"/api/repos/{repo_id}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPublicUrlSharing:
    def test_two_users_submit_same_public_url_results_in_one_repo_two_accesses(
        self, user_factory, authed_client
    ):
        ua = user_factory(username="alice")
        ub = user_factory(username="bob")

        with patch("apps.repos.views.ingest_repository.delay"):
            ra = authed_client(ua).post(
                "/api/repos/",
                data={"url": "https://gitlab.com/team/proj"},
                content_type="application/json",
            )
        assert ra.status_code == 201

        with patch("apps.repos.views.ingest_repository.delay") as delay_mock_b:
            rb = authed_client(ub).post(
                "/api/repos/",
                data={"url": "https://gitlab.com/team/proj"},
                content_type="application/json",
            )
        # 2nd time: existing repo -> 200, not 201
        assert rb.status_code == 200

        # only one Repository row, two RepositoryAccess rows
        assert Repository.objects.count() == 1
        repo = Repository.objects.get()
        assert RepositoryAccess.objects.filter(repository=repo).count() == 2
        assert {a.user_id for a in repo.accesses.all()} == {ua.id, ub.id}

        # Second submission should NOT re-enqueue ingest (repo wasn't re-created
        # and status isn't 'failed').
        delay_mock_b.assert_not_called()


@pytest.mark.django_db
class TestUrlNormalization:
    def test_different_url_forms_resolve_to_same_repository(
        self, user_factory, authed_client
    ):
        ua = user_factory(username="alice", with_github=True)
        ub = user_factory(username="bob", with_github=True)
        uc = user_factory(username="carol", with_github=True)
        ud = user_factory(username="dave", with_github=True)
        ue = user_factory(username="eve", with_github=True)

        # alice submits the ".git/" suffix form; bob the bare form; carol the
        # http://...  /  d the explicit-https-port-443 form / e the trailing-slash
        # form. Each pair lowercases owner+name and collapses to one row.
        public_resp = mock_gh_response(200, {"private": False, "default_branch": "main"})

        submissions = [
            (ua, "https://GitHub.com/x/y.git/", 201),
            (ub, "https://github.com/x/y", 200),
            (uc, "http://github.com/X/Y/", 200),
            (ud, "https://github.com:443/x/y/", 200),
            (ue, "http://github.com:80/x/y", 200),
        ]
        for user, url, expected_status in submissions:
            with patch("apps.repos.views.requests.get", return_value=public_resp), \
                 patch("apps.repos.views.ingest_repository.delay"):
                resp = authed_client(user).post(
                    "/api/repos/",
                    data={"url": url},
                    content_type="application/json",
                )
            assert resp.status_code == expected_status, (url, resp.content)

        # Single Repository row with the normalized URL.
        assert Repository.objects.count() == 1
        repo = Repository.objects.get()
        assert repo.url == "https://github.com/x/y"
        assert RepositoryAccess.objects.filter(repository=repo).count() == len(submissions)


@pytest.mark.django_db
class TestUrlValidation:
    """Cluster 1 — SSRF + host validation. Reject schemes/hosts that
    `_can_grant_access` and the cloner can't safely talk to."""

    def _post(self, user_factory, authed_client, url):
        u = user_factory(username=None)
        return authed_client(u).post(
            "/api/repos/",
            data={"url": url},
            content_type="application/json",
        )

    def test_file_scheme_rejected(self, user_factory, authed_client):
        resp = self._post(user_factory, authed_client, "file:///etc/passwd")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_ssh_scheme_rejected(self, user_factory, authed_client):
        resp = self._post(user_factory, authed_client, "git+ssh://github.com/x/y")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_non_github_host_rejected(self, user_factory, authed_client):
        resp = self._post(user_factory, authed_client, "https://example.com/x/y")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_subdomain_host_rejected(self, user_factory, authed_client):
        resp = self._post(
            user_factory, authed_client, "https://raw.githubusercontent.com/x/y"
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_lookalike_host_rejected(self, user_factory, authed_client):
        resp = self._post(user_factory, authed_client, "https://github.com.evil.tld/x/y")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_single_path_segment_rejected(self, user_factory, authed_client):
        # `https://github.com/onlyone` lacks a repo name; previously created a
        # dead Repository row that `_can_grant_access`/the cloner couldn't act on.
        resp = self._post(user_factory, authed_client, "https://github.com/onlyone")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0

    def test_three_path_segments_rejected(self, user_factory, authed_client):
        resp = self._post(user_factory, authed_client, "https://github.com/x/y/z")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_url"
        assert Repository.objects.count() == 0


@pytest.mark.django_db
class TestCanGrantAccessFailureModes:
    """Cluster 2 — error/edge-case handling in `_can_grant_access`."""

    def test_can_grant_access_flips_needs_reauth_on_401(self, user_factory, authed_client):
        u = user_factory(username="reauth-user", with_github=True)
        with patch("apps.repos.views.requests.get", return_value=mock_gh_response(401)), \
             patch("apps.repos.views.ingest_repository.delay"):
            resp = authed_client(u).post(
                "/api/repos/",
                data={"url": "https://github.com/x/y"},
                content_type="application/json",
            )
        assert resp.status_code == 401
        assert resp.json() == {"error": "needs_reauth"}
        u.refresh_from_db()
        assert u.github_identity.needs_reauth is True
        # No row created on failure.
        assert Repository.objects.count() == 0

    def test_can_grant_access_returns_503_on_github_unreachable(self, user_factory, authed_client):
        u = user_factory(username="net-fail", with_github=True)
        with patch(
            "apps.repos.views.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ), patch("apps.repos.views.ingest_repository.delay"):
            resp = authed_client(u).post(
                "/api/repos/",
                data={"url": "https://github.com/x/y"},
                content_type="application/json",
            )
        assert resp.status_code == 503
        assert resp.json() == {"error": "github_unreachable"}
        assert Repository.objects.count() == 0


@pytest.mark.django_db
class TestIngestTaskDelayArgs:
    def test_delay_called_with_repo_id_and_user_id_only_no_token(
        self, user_factory, authed_client
    ):
        ua = user_factory(username="alice")
        with patch("apps.repos.views.ingest_repository.delay") as delay_mock:
            r = authed_client(ua).post(
                "/api/repos/",
                data={"url": "https://gitlab.com/alice/proj"},
                content_type="application/json",
            )
        assert r.status_code == 201
        assert delay_mock.call_count == 1
        args, kwargs = delay_mock.call_args
        # Exactly two positional args: repo_id (str), user_id (str). No token.
        assert len(args) == 2, f"expected 2 args, got {args}"
        assert kwargs == {}, f"expected no kwargs, got {kwargs}"
        repo_id, user_id = args
        assert isinstance(repo_id, str) and isinstance(user_id, str)
        # Verify neither arg looks like a token (sanity: no 'ghp_' / 'gho_' prefixes,
        # no x-access-token URL).
        for a in args:
            assert "ghp_" not in a and "gho_" not in a
            assert "x-access-token" not in a
        # And neither contains any encrypted-token chunk -- effectively, args are
        # the repo's UUID and the user's primary key.
        assert user_id == str(ua.id)
