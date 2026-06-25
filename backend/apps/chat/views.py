import json

import google.generativeai as genai
from django.conf import settings
from django.http import StreamingHttpResponse
from pgvector.django import L2Distance
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.embeddings.client import embed_texts
from apps.embeddings.models import FunctionEmbedding
from apps.graph.models import FunctionEdge, FunctionNode
from apps.repos.utils import user_has_repo_access

TOP_K = 8


def _sse(event, data):
    """Serialize a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _chunk_text(chunk):
    """Safely pull text from a Gemini stream chunk.

    Accessing ``chunk.text`` raises when a chunk carries no text parts (e.g. a
    safety-only chunk), so guard it rather than let it kill the stream.
    """
    try:
        return chunk.text or ""
    except (ValueError, AttributeError):
        return ""


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, repo_id):
        # Gate + validation run synchronously *before* the stream opens so these
        # stay normal JSON 4xx responses rather than mid-stream errors.
        if not user_has_repo_access(request.user, repo_id):
            return Response({"error": "not found"}, status=404)
        query = request.data.get("query", "").strip()
        if not query:
            return Response({"error": "query required"}, status=400)

        query_vec = embed_texts([query])[0]

        hits = (
            FunctionEmbedding.objects
            .filter(function__repository_id=repo_id)
            .order_by(L2Distance("vector", query_vec))[:TOP_K]
            .select_related("function__file")
        )
        seed_ids = [h.function_id for h in hits]

        expanded_ids = set(seed_ids)
        # Defense-in-depth: seed_ids are already repo-scoped via the embedding
        # filter above, but constrain the edge fan-out to this repo as well so
        # any stray cross-repo edge cannot pull a foreign target into context.
        for edge in FunctionEdge.objects.filter(
            source_id__in=seed_ids, repository_id=repo_id
        ):
            expanded_ids.add(edge.target_id)

        # Materialize eagerly: the generator below must not lazily evaluate the
        # ORM once the streaming response has started.
        functions = list(
            FunctionNode.objects.filter(
                id__in=expanded_ids, repository_id=repo_id
            ).select_related("file")
        )

        context_parts = [
            f"# {fn.file.path} :: {fn.name} (line {fn.start_line})\n{fn.source}"
            for fn in functions
        ]
        context = "\n\n".join(context_parts[:12])

        citations = [
            {
                "id": fn.id,
                # node_id is the graph node id the frontend uses to focus/center
                # a function in GraphPanel — the load-bearing link field.
                "node_id": str(fn.id),
                "name": fn.name,
                "file": fn.file.path,
                "start_line": fn.start_line,
                "summary": fn.summary,
            }
            for fn in functions
        ]

        genai.configure(api_key=settings.GOOGLE_API_KEY, transport="rest")
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = (
            "You are a code assistant. Answer questions about the codebase using the provided function context. "
            "Be concise and reference function names and file paths. Use Markdown formatting.\n\n"
            f"Context:\n{context}\n\nQuestion: {query}"
        )

        def event_stream():
            yield _sse("meta", {"functions": citations})
            try:
                for chunk in model.generate_content(prompt, stream=True):
                    text = _chunk_text(chunk)
                    if text:
                        yield _sse("token", {"text": text})
            except Exception:
                yield _sse("error", {"error": "generation failed"})
            yield _sse("done", {})

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # disable nginx buffering
        return response
