"""Tests for RepositoryAttachView's private-repo permission boundary (item 6)."""
from unittest.mock import patch

import pytest

from apps.repos.models import Repository, RepositoryAccess
from apps.repos.tests.conftest import mock_gh_response


@pytest.fixture
def private_repo(db):
    return Repository.objects.create(
        url="https://github.com/acme/secret",
        name="secret",
        is_private=True,
        status="ready",
    )


@pytest.mark.django_db
class TestAttachPrivateRepo:
    def test_user_with_no_github_identity_gets_403(self, user_factory, authed_client, private_repo):
        u = user_factory(username="no-gh", with_github=False)
        resp = authed_client(u).post(
            "/api/repos/attach/",
            data={"repo_id": str(private_repo.id)},
            content_type="application/json",
        )
        assert resp.status_code == 403
        assert RepositoryAccess.objects.filter(user=u, repository=private_repo).count() == 0

    def test_user_whose_github_probe_returns_404_gets_403(
        self, user_factory, authed_client, private_repo
    ):
        u = user_factory(username="cant-see", with_github=True)
        with patch("apps.repos.views.requests.get", return_value=mock_gh_response(404)):
            resp = authed_client(u).post(
                "/api/repos/attach/",
                data={"repo_id": str(private_repo.id)},
                content_type="application/json",
            )
        assert resp.status_code == 403
        assert RepositoryAccess.objects.filter(user=u, repository=private_repo).count() == 0

    def test_user_whose_github_probe_returns_200_gets_access(
        self, user_factory, authed_client, private_repo
    ):
        u = user_factory(username="can-see", with_github=True)
        with patch(
            "apps.repos.views.requests.get",
            return_value=mock_gh_response(200, {"private": True}),
        ):
            resp = authed_client(u).post(
                "/api/repos/attach/",
                data={"repo_id": str(private_repo.id)},
                content_type="application/json",
            )
        assert resp.status_code == 200
        access = RepositoryAccess.objects.get(user=u, repository=private_repo)
        assert access.source == "github"

    def test_attach_unknown_repo_id_returns_404(self, user_factory, authed_client):
        import uuid
        u = user_factory(username="x")
        resp = authed_client(u).post(
            "/api/repos/attach/",
            data={"repo_id": str(uuid.uuid4())},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_anonymous_attach_blocked(self):
        from django.test import Client
        resp = Client().post(
            "/api/repos/attach/", data={"repo_id": "anything"}, content_type="application/json"
        )
        assert resp.status_code in (401, 403)


@pytest.fixture
def unprobed_repo(db):
    """A github repo whose privacy hasn't been determined yet (`is_private=None`)."""
    return Repository.objects.create(
        url="https://github.com/acme/maybepublic",
        name="maybepublic",
        is_private=None,
        status="ready",
    )


@pytest.mark.django_db
class TestAttachAnonymousProbeFallback:
    """Cluster 2 — when a user with no token tries to attach to an unprobed
    repo, fall back to an anonymous probe rather than auto-deny."""

    def test_attach_user_with_no_token_for_unprobed_repo_falls_back_to_anonymous_probe(
        self, user_factory, authed_client, unprobed_repo
    ):
        u = user_factory(username="anon-attacher", with_github=False)
        # Anonymous probe returns 200 with private=False — repo is public.
        with patch(
            "apps.repos.views.requests.get",
            return_value=mock_gh_response(200, {"private": False}),
        ):
            resp = authed_client(u).post(
                "/api/repos/attach/",
                data={"repo_id": str(unprobed_repo.id)},
                content_type="application/json",
            )
        assert resp.status_code == 200
        access = RepositoryAccess.objects.get(user=u, repository=unprobed_repo)
        assert access.source == "public_url"
        unprobed_repo.refresh_from_db()
        assert unprobed_repo.is_private is False

    def test_attach_user_with_no_token_for_unprobed_private_repo_returns_403(
        self, user_factory, authed_client, unprobed_repo
    ):
        u = user_factory(username="anon-locked-out", with_github=False)
        # Anonymous probe returns 404 — repo is either private or doesn't
        # exist; treat as private and reject (we can't authenticate anonymously).
        with patch(
            "apps.repos.views.requests.get",
            return_value=mock_gh_response(404),
        ):
            resp = authed_client(u).post(
                "/api/repos/attach/",
                data={"repo_id": str(unprobed_repo.id)},
                content_type="application/json",
            )
        assert resp.status_code == 403
        assert RepositoryAccess.objects.filter(user=u, repository=unprobed_repo).count() == 0
