"""Tests for /api/github/repos/, /api/me/, /api/auth/logout/, /api/auth/csrf/
(items 8, 9, 12, 13)."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from apps.auth_github.crypto import encrypt
from apps.auth_github.models import GitHubIdentity


@pytest.fixture(autouse=True)
def _clear_cache_each_test():
    """Prevent the GithubReposView's response cache from leaking across tests.
    Cache keys are `gh_repos:{user_id}:...` and SQLite IDs can repeat after
    a per-test rollback."""
    cache.clear()
    yield
    cache.clear()


def _gh_response(status_code, json_payload=None, headers=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_payload or []
    r.headers = headers or {}
    return r


@pytest.fixture
def make_authed_user(db):
    counter = {"i": 0}

    def make(with_identity=True, needs_reauth=False, token="gho_test_token"):
        counter["i"] += 1
        u = User.objects.create_user(username=f"u{counter['i']}", password="pw")
        if with_identity:
            GitHubIdentity.objects.create(
                user=u,
                github_user_id=42_000 + counter["i"],
                login=u.username,
                access_token_enc=encrypt(token),
                scopes="repo",
                needs_reauth=needs_reauth,
            )
        c = Client()
        c.force_login(u)
        return u, c

    return make


@pytest.mark.django_db
class TestGithubReposView:
    def test_anonymous_returns_401_or_403(self):
        resp = Client().get("/api/github/repos/")
        assert resp.status_code in (401, 403)

    def test_authed_without_identity_returns_401(self, make_authed_user):
        _, c = make_authed_user(with_identity=False)
        resp = c.get("/api/github/repos/")
        assert resp.status_code == 401
        assert resp.json() == {"needs_reauth": True}

    def test_authed_with_identity_returns_trimmed_repo_list(self, make_authed_user):
        _, c = make_authed_user()
        github_payload = [
            {
                "id": 1,
                "name": "alpha",
                "full_name": "user/alpha",
                "html_url": "https://github.com/user/alpha",
                "private": False,
                "pushed_at": "2026-01-01T00:00:00Z",
                "default_branch": "main",
                "extraneous": "should-be-dropped",
            },
            {
                "id": 2,
                "name": "beta",
                "full_name": "user/beta",
                "html_url": "https://github.com/user/beta",
                "private": True,
                "pushed_at": None,
                "default_branch": "dev",
            },
        ]
        with patch("apps.auth_github.views.requests.get", return_value=_gh_response(200, github_payload)):
            resp = c.get("/api/github/repos/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert set(data[0].keys()) == {
            "id", "name", "full_name", "html_url", "private", "pushed_at", "default_branch",
        }
        assert data[0]["id"] == 1
        assert data[1]["private"] is True
        assert data[1]["default_branch"] == "dev"

    def test_github_401_flips_needs_reauth_and_returns_401(self, make_authed_user):
        u, c = make_authed_user()
        with patch("apps.auth_github.views.requests.get", return_value=_gh_response(401)):
            resp = c.get("/api/github/repos/")
        assert resp.status_code == 401
        assert resp.json() == {"needs_reauth": True}
        u.refresh_from_db()
        assert u.github_identity.needs_reauth is True

    def test_user_with_needs_reauth_flag_short_circuits_401(self, make_authed_user):
        _, c = make_authed_user(needs_reauth=True)
        # No HTTP mock needed; should not even call requests.get
        with patch("apps.auth_github.views.requests.get") as mock_get:
            resp = c.get("/api/github/repos/")
        assert resp.status_code == 401
        assert resp.json() == {"needs_reauth": True}
        mock_get.assert_not_called()

    def test_rate_limit_429_returns_503_with_retry_after(self, make_authed_user):
        _, c = make_authed_user()
        with patch(
            "apps.auth_github.views.requests.get",
            return_value=_gh_response(429, headers={"Retry-After": "60"}),
        ):
            resp = c.get("/api/github/repos/")
        assert resp.status_code == 503
        assert resp["Retry-After"] == "60"

    def test_rate_limit_403_returns_503(self, make_authed_user):
        _, c = make_authed_user()
        with patch(
            "apps.auth_github.views.requests.get",
            return_value=_gh_response(403, headers={"Retry-After": "30"}),
        ):
            resp = c.get("/api/github/repos/")
        assert resp.status_code == 503
        assert resp["Retry-After"] == "30"


@pytest.mark.django_db
class TestMeView:
    def test_anonymous_me_returns_401_or_403(self):
        resp = Client().get("/api/me/")
        assert resp.status_code in (401, 403)

    def test_authed_with_identity_returns_identity_payload(self, make_authed_user):
        u, c = make_authed_user()
        resp = c.get("/api/me/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == u.id
        assert body["login"] == u.username
        assert "avatar_url" in body
        assert body["needs_reauth"] is False

    def test_authed_without_identity_returns_user_payload(self, make_authed_user):
        u, c = make_authed_user(with_identity=False)
        resp = c.get("/api/me/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == u.id
        assert body["login"] == u.username


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_clears_session(self, make_authed_user):
        _, c = make_authed_user()
        assert "_auth_user_id" in c.session
        resp = c.post("/api/auth/logout/")
        assert resp.status_code == 204
        assert "_auth_user_id" not in c.session

    def test_logout_succeeds_without_csrf_token(self, db):
        """Verify the csrf_exempt + custom-auth setup: logout MUST work even
        when CSRF is enforced and no token is sent. A stale csrftoken cookie
        should never wedge a user out of the ability to sign out."""
        u = User.objects.create_user(username="logout-csrf", password="pw")
        c = Client(enforce_csrf_checks=True)
        c.force_login(u)
        # No CSRF token sent — would normally 403 with enforce_csrf_checks.
        resp = c.post("/api/auth/logout/")
        assert resp.status_code == 204
        assert "_auth_user_id" not in c.session


class TestCsrfView:
    def test_csrf_endpoint_returns_204_and_sets_csrftoken_cookie(self):
        resp = Client().get("/api/auth/csrf/")
        assert resp.status_code == 204
        assert "csrftoken" in resp.cookies
        assert resp.cookies["csrftoken"].value  # non-empty value
