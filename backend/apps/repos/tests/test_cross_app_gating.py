"""Cluster 6 — cross-app permission gating.

`apps.files`, `apps.graph`, `apps.chat` views must call the shared
`apps.repos.utils.user_has_repo_access` helper (the single source of
truth for "can this user see this repo?"). For an unrelated user the
endpoints must return 404 — never 200, never 403 — so that we don't
leak the existence of the repo.

The model layers for these apps depend on postgres-only fields
(ArrayField, pgvector.VectorField); we stub those at module load (see
`core/test_settings.py`) so the views can be imported under SQLite.
We mock the inner queryset-returning calls so the tests never reach
the `db_type=text` columns — only the access gate is exercised here.
"""
import pytest

from apps.repos.models import Repository, RepositoryAccess


@pytest.fixture
def two_users_one_repo(user_factory, authed_client):
    ua = user_factory(username="alice")
    ub = user_factory(username="bob")
    repo = Repository.objects.create(
        url="https://github.com/alice/proj",
        name="proj",
        is_private=False,
        status="ready",
    )
    RepositoryAccess.objects.create(
        user=ua, repository=repo, role="owner", source="public_url"
    )
    return ua, ub, repo, authed_client(ub)


@pytest.mark.django_db
class TestCrossAppGating404:
    def test_chat_view_404_for_unrelated_user(self, two_users_one_repo):
        _, _, repo, client_b = two_users_one_repo
        # No mocks needed: gate runs before any model query reaches the body.
        resp = client_b.post(
            f"/api/chat/{repo.id}/",
            data={"query": "anything"},
            content_type="application/json",
        )
        assert resp.status_code == 404
        assert resp.json() == {"error": "not found"}

    def test_graph_view_404_for_unrelated_user(self, two_users_one_repo):
        _, _, repo, client_b = two_users_one_repo
        resp = client_b.get(f"/api/graph/{repo.id}/")
        assert resp.status_code == 404

    def test_files_view_404_for_unrelated_user(self, two_users_one_repo):
        _, _, repo, client_b = two_users_one_repo
        resp = client_b.get(f"/api/files/{repo.id}/tree/")
        assert resp.status_code == 404

    def test_trace_view_404_for_unrelated_user(self, two_users_one_repo):
        _, _, repo, client_b = two_users_one_repo
        resp = client_b.get(f"/api/graph/{repo.id}/trace/1/")
        assert resp.status_code == 404

    def test_file_functions_view_404_for_unrelated_user(self, two_users_one_repo):
        _, _, repo, client_b = two_users_one_repo
        resp = client_b.get(f"/api/files/{repo.id}/files/1/functions/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestUserHasRepoAccessHelper:
    """Direct unit tests for the helper used by all cross-app views — the
    single source of truth for repo-scoped authorization."""

    def test_returns_true_for_owner(self, user_factory):
        from apps.repos.utils import user_has_repo_access

        u = user_factory(username="owner")
        repo = Repository.objects.create(url="https://github.com/x/y", name="y")
        RepositoryAccess.objects.create(user=u, repository=repo, role="owner")
        assert user_has_repo_access(u, repo.id) is True

    def test_returns_false_for_unrelated_user(self, user_factory):
        from apps.repos.utils import user_has_repo_access

        owner = user_factory(username="o")
        other = user_factory(username="other")
        repo = Repository.objects.create(url="https://github.com/x/y", name="y")
        RepositoryAccess.objects.create(user=owner, repository=repo, role="owner")
        assert user_has_repo_access(other, repo.id) is False

    def test_returns_false_for_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser

        from apps.repos.utils import user_has_repo_access

        repo = Repository.objects.create(url="https://github.com/x/y", name="y")
        assert user_has_repo_access(AnonymousUser(), repo.id) is False
        assert user_has_repo_access(None, repo.id) is False

    def test_views_dispatch_through_shared_helper(self, two_users_one_repo, monkeypatch):
        """Belt-and-suspenders: confirm the views actually call
        `apps.repos.utils.user_has_repo_access`. If a future refactor swaps
        in an inline check, this test will break loudly."""
        ua, ub, repo, client_b = two_users_one_repo

        calls = []

        def _spy(user, repo_id):
            calls.append((user.id, str(repo_id)))
            return False

        # Patch the binding inside each view module — the views import the
        # helper by name at module load.
        monkeypatch.setattr("apps.files.views.user_has_repo_access", _spy)
        monkeypatch.setattr("apps.graph.views.user_has_repo_access", _spy)
        monkeypatch.setattr("apps.chat.views.user_has_repo_access", _spy)

        client_b.get(f"/api/files/{repo.id}/tree/")
        client_b.get(f"/api/graph/{repo.id}/")
        client_b.post(
            f"/api/chat/{repo.id}/",
            data={"query": "x"},
            content_type="application/json",
        )

        assert len(calls) == 3
        for user_id, repo_id in calls:
            assert user_id == ub.id
            assert repo_id == str(repo.id)
