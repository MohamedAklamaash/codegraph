"""Tests for the GitHub OAuth callback view (item 3)."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.auth_github.crypto import decrypt
from apps.auth_github.models import GitHubIdentity


def _mock_token_response(payload):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = payload
    return r


def _mock_user_response(payload):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = payload
    return r


@pytest.mark.django_db
class TestOAuthCallbackState:
    def test_callback_with_missing_state_redirects_to_login_error(self):
        client = Client()
        # No prior /start/, so no gh_oauth_state in session.
        resp = client.get("/api/auth/github/callback/?code=somecode")
        assert resp.status_code == 302
        assert "login_error=1" in resp["Location"]

    def test_callback_with_mismatched_state_redirects_to_login_error(self):
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "expected_state_value"
        session.save()
        resp = client.get("/api/auth/github/callback/?code=somecode&state=WRONG")
        assert resp.status_code == 302
        assert "login_error=1" in resp["Location"]

    def test_callback_with_missing_code_redirects_to_login_error(self):
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "abc"
        session.save()
        resp = client.get("/api/auth/github/callback/?state=abc")
        assert resp.status_code == 302
        assert "login_error=1" in resp["Location"]


@pytest.mark.django_db
class TestOAuthCallbackSuccess:
    def test_valid_callback_creates_user_identity_and_redirects_to_frontend(self):
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "good_state"
        session.save()

        token_payload = {"access_token": "gho_synthetic_oauth_token", "scope": "read:user,repo"}
        user_payload = {"id": 4242, "login": "octopus", "avatar_url": "https://avatar.example/o.png"}

        with patch("apps.auth_github.views.requests.post", return_value=_mock_token_response(token_payload)) as mock_post, \
             patch("apps.auth_github.views.requests.get", return_value=_mock_user_response(user_payload)) as mock_get:
            resp = client.get("/api/auth/github/callback/?code=valid_code&state=good_state")

        # Redirect to FRONTEND_BASE_URL (not login_error)
        assert resp.status_code == 302
        assert resp["Location"] == "http://localhost:5173"
        assert "login_error" not in resp["Location"]

        # User + identity created
        user = User.objects.get(username="gh__4242")
        ident = GitHubIdentity.objects.get(user=user)
        assert ident.github_user_id == 4242
        assert ident.login == "octopus"
        assert ident.avatar_url == "https://avatar.example/o.png"
        assert ident.needs_reauth is False
        assert ident.scopes == "read:user,repo"
        # Token stored encrypted; round-trip recovers original
        assert ident.access_token_enc != "gho_synthetic_oauth_token"
        assert decrypt(ident.access_token_enc) == "gho_synthetic_oauth_token"

        # Session is logged in (auth_login was called)
        assert "_auth_user_id" in client.session

        # GitHub HTTP calls were made
        assert mock_post.called
        assert mock_get.called

    def test_token_endpoint_returning_no_access_token_redirects_to_error(self):
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "good_state"
        session.save()

        with patch("apps.auth_github.views.requests.post",
                   return_value=_mock_token_response({"error": "bad_verification_code"})):
            resp = client.get("/api/auth/github/callback/?code=bad&state=good_state")

        assert resp.status_code == 302
        assert "login_error=1" in resp["Location"]
        assert not User.objects.filter(username__startswith="gh_").exists()

    def test_state_is_consumed_on_use(self):
        """After a callback (success or scope-failure) the state is wiped from session."""
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "good_state"
        session.save()

        # Use a valid `repo` scope so we don't short-circuit before User creation;
        # the assertion is that state is consumed regardless.
        with patch("apps.auth_github.views.requests.post",
                   return_value=_mock_token_response(
                       {"access_token": "tok", "scope": "repo"})), \
             patch("apps.auth_github.views.requests.get",
                   return_value=_mock_user_response({"id": 1, "login": "x"})):
            client.get("/api/auth/github/callback/?code=c&state=good_state")
        assert "gh_oauth_state" not in client.session


@pytest.mark.django_db
class TestOAuthCallbackHardening:
    """Cluster 4 — timing-safe state, IntegrityError handling, scope validation."""

    def test_callback_user_collision_does_not_500(self):
        """If a User row with the same gh__<id> username already exists,
        the callback should match it instead of crashing with IntegrityError."""
        existing = User.objects.create_user(username="gh__999", password="pw")

        client = Client()
        session = client.session
        session["gh_oauth_state"] = "good_state"
        session.save()

        token_payload = {"access_token": "gho_collide_token", "scope": "read:user,repo"}
        user_payload = {"id": 999, "login": "collider"}

        with patch("apps.auth_github.views.requests.post",
                   return_value=_mock_token_response(token_payload)), \
             patch("apps.auth_github.views.requests.get",
                   return_value=_mock_user_response(user_payload)):
            resp = client.get("/api/auth/github/callback/?code=c&state=good_state")

        assert resp.status_code == 302
        # Logged in as the existing user (no duplicate row created).
        assert User.objects.filter(username="gh__999").count() == 1
        ident = GitHubIdentity.objects.get(user=existing)
        assert ident.github_user_id == 999

    def test_callback_missing_repo_scope_redirects_with_error(self):
        client = Client()
        session = client.session
        session["gh_oauth_state"] = "good_state"
        session.save()

        token_payload = {"access_token": "tok", "scope": "read:user"}

        with patch("apps.auth_github.views.requests.post",
                   return_value=_mock_token_response(token_payload)), \
             patch("apps.auth_github.views.requests.get") as mock_get:
            resp = client.get("/api/auth/github/callback/?code=c&state=good_state")

        assert resp.status_code == 302
        assert "login_error=missing_scope" in resp["Location"]
        # No User or Identity created; the user-info GET wasn't called.
        assert not User.objects.exists()
        mock_get.assert_not_called()
