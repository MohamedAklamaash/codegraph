"""Shared fixtures for repos tests."""
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.auth_github.crypto import encrypt
from apps.auth_github.models import GitHubIdentity


@pytest.fixture
def user_factory(db):
    counter = {"i": 0}

    def make(username=None, with_github=False, github_user_id=None, token="gho_synthetic"):
        counter["i"] += 1
        if username is None:
            username = f"u{counter['i']}"
        u = User.objects.create_user(username=username, password="pw")
        if with_github:
            GitHubIdentity.objects.create(
                user=u,
                github_user_id=github_user_id or (10_000 + counter["i"]),
                login=username,
                access_token_enc=encrypt(token),
                scopes="repo",
            )
        return u

    return make


@pytest.fixture
def authed_client(db):
    def make(user):
        c = Client()
        c.force_login(user)
        return c

    return make


def mock_gh_response(status_code=200, json_payload=None, headers=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_payload or {}
    r.headers = headers or {}
    return r
