"""Cluster — cross-repo IDOR through graph/chat queries.

The view-level access gate (`user_has_repo_access`) only proves the user can
see ``repo_id``. It does NOT validate that ``node_id`` / ``file_id`` query
params belong to that same repo. Without per-query repository_id filtering,
an authed user with access to repo A can pass a node_id from repo B and
receive node + edge data for repo B.

These tests exercise the inner-query repo scoping in
`apps/graph/views.py:GraphView` and `apps/chat/views.py:ChatView`. The
`FunctionNode` rows are created directly in the test DB; under SQLite the
ArrayField/VectorField columns are stubbed (see `core/test_settings.py`)
so we can write to these models without postgres-only features.
"""
import pytest

from apps.files.models import RepoFile
from apps.graph.models import FunctionEdge, FunctionNode
from apps.repos.models import Repository, RepositoryAccess


@pytest.fixture
def two_repos_with_nodes(user_factory, authed_client, db):
    """Alice has access to repo A. Repo B exists but Alice has no access.

    Each repo has one file and one FunctionNode. Returns the IDs the tests
    need to attempt cross-repo access through ``node_id`` / ``file_id``.
    """
    alice = user_factory(username="alice")

    repo_a = Repository.objects.create(
        url="https://github.com/alice/proj-a",
        name="proj-a",
        is_private=False,
        status="ready",
    )
    RepositoryAccess.objects.create(
        user=alice, repository=repo_a, role="owner", source="public_url"
    )

    repo_b = Repository.objects.create(
        url="https://github.com/bob/proj-b",
        name="proj-b",
        is_private=False,
        status="ready",
    )
    # No access for Alice to repo B.

    file_a = RepoFile.objects.create(repository=repo_a, path="a.py", language="python")
    file_b = RepoFile.objects.create(repository=repo_b, path="b.py", language="python")

    node_a = FunctionNode.objects.create(
        repository=repo_a,
        file=file_a,
        name="fn_a",
        start_line=1,
        end_line=10,
        source="def fn_a(): pass",
        summary="",
        calls=[],
    )
    node_b = FunctionNode.objects.create(
        repository=repo_b,
        file=file_b,
        name="fn_b",
        start_line=1,
        end_line=10,
        source="def fn_b(): pass",
        summary="",
        calls=[],
    )

    return {
        "alice": alice,
        "client": authed_client(alice),
        "repo_a": repo_a,
        "repo_b": repo_b,
        "file_a": file_a,
        "file_b": file_b,
        "node_a": node_a,
        "node_b": node_b,
    }


@pytest.mark.django_db
class TestGraphViewNodeIdCrossRepo:
    def test_graph_view_node_id_from_other_repo_returns_404(self, two_repos_with_nodes):
        """Alice has access to repo A. She passes node_b.id (in repo B) as
        ?node_id= to the repo A endpoint. Must 404, NOT leak node B data."""
        ctx = two_repos_with_nodes
        resp = ctx["client"].get(
            f"/api/graph/{ctx['repo_a'].id}/?node_id={ctx['node_b'].id}"
        )
        assert resp.status_code == 404
        assert resp.json() == {"error": "node_not_found"}

    def test_graph_view_node_id_from_own_repo_returns_200(self, two_repos_with_nodes):
        """Sanity check: in-repo node_id must still work (proves the new
        repo-scoped fetch isn't over-rejecting legitimate requests)."""
        ctx = two_repos_with_nodes
        resp = ctx["client"].get(
            f"/api/graph/{ctx['repo_a'].id}/?node_id={ctx['node_a'].id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        node_ids = {n["id"] for n in body["nodes"]}
        assert str(ctx["node_a"].id) in node_ids
        assert str(ctx["node_b"].id) not in node_ids

    def test_graph_view_non_numeric_node_id_returns_400(self, two_repos_with_nodes):
        """Non-numeric node_id must 400, not 500."""
        ctx = two_repos_with_nodes
        resp = ctx["client"].get(f"/api/graph/{ctx['repo_a'].id}/?node_id=abc")
        assert resp.status_code == 400
        assert resp.json() == {"error": "invalid_param", "detail": "node_id"}


@pytest.mark.django_db
class TestGraphViewFileIdCrossRepo:
    def test_graph_view_file_id_from_other_repo_returns_empty(self, two_repos_with_nodes):
        """Alice queries repo A with ?file_id pointing to a file in repo B.
        The view-level repo gate passes (Alice owns repo A), but the inner
        FunctionNode/FunctionEdge queries must filter by repository_id, so
        no data from repo B leaks. Result: empty nodes/edges."""
        ctx = two_repos_with_nodes
        resp = ctx["client"].get(
            f"/api/graph/{ctx['repo_a'].id}/?file_id={ctx['file_b'].id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []


@pytest.mark.django_db
class TestChatViewEdgeFanoutRepoScoped:
    """The chat view's `expanded_ids` set is built by following outgoing
    edges from ``seed_ids``. ``seed_ids`` come from FunctionEmbedding rows
    pre-filtered by `function__repository_id=repo_id`, so a stored
    cross-repo edge is the only practical exfiltration path. We can't
    easily provoke that under SQLite (FunctionEmbedding uses VectorField
    + L2Distance ordering — both stubs are no-ops), so we settle for a
    structural assertion: the queryset's SQL contains a `repository_id`
    filter."""

    def test_chat_view_edge_fanout_filters_by_repository(self, monkeypatch, two_repos_with_nodes):
        """Spy on `FunctionEdge.objects.filter` to confirm the chat view
        passes `repository_id=<repo_id>` when expanding seed_ids."""
        from apps.chat import views as chat_views

        ctx = two_repos_with_nodes
        captured = {}

        real_filter = FunctionEdge.objects.filter

        def _spy(*args, **kwargs):
            # Record the kwargs used by the chat view's edge fan-out call.
            # The standalone `objects.all().order_by(...)` queries don't pass
            # `source_id__in`, so we filter for the expansion call only.
            if "source_id__in" in kwargs:
                captured.update(kwargs)
            return real_filter(*args, **kwargs)

        monkeypatch.setattr(FunctionEdge.objects, "filter", _spy)

        # Stub the embedding lookup so we don't need a real vector DB. Returns
        # a list with one hit pointing at node_a, so seed_ids = [node_a.id].
        class _FakeHit:
            def __init__(self, fn_id):
                self.function_id = fn_id

        class _FakeQS:
            def __init__(self, hits):
                self._hits = hits

            def filter(self, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def __getitem__(self, key):
                return self

            def select_related(self, *args, **kwargs):
                return self._hits

        monkeypatch.setattr(
            chat_views.FunctionEmbedding,
            "objects",
            _FakeQS([_FakeHit(ctx["node_a"].id)]),
        )
        monkeypatch.setattr(chat_views, "embed_texts", lambda texts: [[0.0]])

        resp = ctx["client"].post(
            f"/api/chat/{ctx['repo_a'].id}/",
            data={"query": "tell me about fn_a"},
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.content
        # Confirm the edge fan-out queryset was built with the repo_id filter.
        assert "repository_id" in captured, (
            "FunctionEdge edge fan-out did not include repository_id filter; "
            "this is the IDOR defense-in-depth check"
        )
        assert str(captured["repository_id"]) == str(ctx["repo_a"].id)
