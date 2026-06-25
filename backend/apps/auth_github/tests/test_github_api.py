"""Unit tests for `apps.auth_github.github_api` helpers.

Covers the three new helpers added in the cleanup branch:

- `get_identity_or_reauth(user)`
- `decrypt_token_or_reauth(identity)`
- `github_get(token, url, params=None)`

The identity helpers require real DB-backed `User` and `GitHubIdentity`
rows, so they go through `@pytest.mark.django_db`. The `github_get`
helper is a pure wrapper around `requests.get` and is exercised by
patching `requests.get` directly.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.auth.models import User

from apps.auth_github.crypto import encrypt
from apps.auth_github.github_api import (
    decrypt_token_or_reauth,
    get_identity_or_reauth,
    github_get,
)
from apps.auth_github.models import GitHubIdentity


# ---------------------------------------------------------------------------
# get_identity_or_reauth
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetIdentityOrReauth:
    def test_returns_identity_when_present_and_not_needs_reauth(self):
        user = User.objects.create_user(username="ok", password="pw")
        identity = GitHubIdentity.objects.create(
            user=user,
            github_user_id=12345,
            login="ok",
            access_token_enc=encrypt("gho_tok"),
            scopes="repo",
            needs_reauth=False,
        )

        result_identity, err = get_identity_or_reauth(user)

        assert err is None
        assert result_identity is not None
        assert result_identity.pk == identity.pk

    def test_returns_401_when_user_has_no_github_identity(self):
        user = User.objects.create_user(username="no-gh", password="pw")

        identity, err = get_identity_or_reauth(user)

        assert identity is None
        assert err is not None
        assert err.status_code == 401
        assert err.data == {"needs_reauth": True}

    def test_returns_401_when_identity_needs_reauth(self):
        user = User.objects.create_user(username="stale", password="pw")
        GitHubIdentity.objects.create(
            user=user,
            github_user_id=54321,
            login="stale",
            access_token_enc=encrypt("gho_tok"),
            scopes="repo",
            needs_reauth=True,
        )

        identity, err = get_identity_or_reauth(user)

        assert identity is None
        assert err is not None
        assert err.status_code == 401
        assert err.data == {"needs_reauth": True}


# ---------------------------------------------------------------------------
# decrypt_token_or_reauth
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDecryptTokenOrReauth:
    def test_returns_plaintext_token_on_success(self):
        user = User.objects.create_user(username="happy", password="pw")
        identity = GitHubIdentity.objects.create(
            user=user,
            github_user_id=11111,
            login="happy",
            access_token_enc=encrypt("gho_plaintext"),
            scopes="repo",
        )

        token, err = decrypt_token_or_reauth(identity)

        assert err is None
        assert token == "gho_plaintext"

    def test_flips_needs_reauth_and_returns_401_on_decrypt_failure(self):
        user = User.objects.create_user(username="corrupt", password="pw")
        identity = GitHubIdentity.objects.create(
            user=user,
            github_user_id=22222,
            login="corrupt",
            # Not a valid Fernet ciphertext -> decrypt() raises InvalidToken.
            access_token_enc="not-a-fernet-token",
            scopes="repo",
            needs_reauth=False,
        )

        token, err = decrypt_token_or_reauth(identity)

        assert token is None
        assert err is not None
        assert err.status_code == 401
        assert err.data == {"needs_reauth": True}

        # Verify the flag was persisted (not just mutated in-memory).
        identity.refresh_from_db()
        assert identity.needs_reauth is True


# ---------------------------------------------------------------------------
# github_get
# ---------------------------------------------------------------------------


def _mock_resp(status_code=200, headers=None):
    r = MagicMock()
    r.status_code = status_code
    r.headers = headers or {}
    return r


class TestGithubGet:
    """Pure wrapper — no DB needed. We patch `requests.get` directly."""

    def test_200_returns_raw_response(self):
        resp = _mock_resp(200)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp) as mock_get:
            result = github_get("tok", "https://api.github.com/user")
        assert result is resp
        # Bearer auth header is set; Accept header is GitHub JSON.
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert kwargs["headers"]["Accept"] == "application/vnd.github+json"

    def test_401_bubbles_response_up(self):
        """401 is semantically caller-handled (needs_reauth)."""
        resp = _mock_resp(401)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result is resp

    def test_404_bubbles_response_up(self):
        """404 is semantically caller-handled (no access / not found)."""
        resp = _mock_resp(404)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/repos/x/y")
        assert result is resp

    def test_request_exception_maps_to_unreachable_503(self):
        with patch(
            "apps.auth_github.github_api.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("github_unreachable", 503, None)

    def test_timeout_maps_to_unreachable_503(self):
        with patch(
            "apps.auth_github.github_api.requests.get",
            side_effect=requests.Timeout("slow"),
        ):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("github_unreachable", 503, None)

    def test_403_returns_rate_limited_with_retry_after(self):
        resp = _mock_resp(403, headers={"Retry-After": "60"})
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("rate_limited", 503, "60")

    def test_429_returns_rate_limited_with_retry_after(self):
        resp = _mock_resp(429, headers={"Retry-After": "30"})
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("rate_limited", 503, "30")

    def test_429_returns_rate_limited_with_none_retry_after_when_header_absent(self):
        resp = _mock_resp(429, headers={})
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("rate_limited", 503, None)

    def test_500_maps_to_github_error_502(self):
        resp = _mock_resp(500)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("github_error", 502, None)

    def test_502_maps_to_github_error_502(self):
        resp = _mock_resp(502)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("github_error", 502, None)

    def test_400_other_4xx_maps_to_github_error_502(self):
        """4xx that isn't 401, 403, 404, or 429 is folded to a generic upstream error."""
        resp = _mock_resp(400)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp):
            result = github_get("tok", "https://api.github.com/user")
        assert result == ("github_error", 502, None)

    def test_params_are_forwarded(self):
        resp = _mock_resp(200)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp) as mock_get:
            github_get("tok", "https://api.github.com/user/repos", params={"per_page": 5})
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"per_page": 5}

    def test_default_timeout_is_set(self):
        """Defensive: every github_get call must set a timeout to avoid hangs."""
        resp = _mock_resp(200)
        with patch("apps.auth_github.github_api.requests.get", return_value=resp) as mock_get:
            github_get("tok", "https://api.github.com/user")
        _, kwargs = mock_get.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] is not None
