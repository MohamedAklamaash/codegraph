import google.generativeai as genai
from django.conf import settings
from pgvector.django import L2Distance
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.embeddings.client import embed_texts
from apps.embeddings.models import FunctionEmbedding
from apps.graph.models import FunctionEdge, FunctionNode

TOP_K = 8

class ChatView(APIView):
    def post(self, request, repo_id):
        query = request.data.get("query", "").strip()
        if not query:
            return Response({"error": "query required"}, status=400)

        # 1. Embed query
        query_vec = embed_texts([query])[0]

        # 2. Semantic search
        hits = (
            FunctionEmbedding.objects
            .filter(function__repository_id=repo_id)
            .order_by(L2Distance("vector", query_vec))[:TOP_K]
            .select_related("function__file")
        )
        seed_ids = [h.function_id for h in hits]

        # 3. Graph expansion (1 hop)
        expanded_ids = set(seed_ids)
        for edge in FunctionEdge.objects.filter(source_id__in=seed_ids):
            expanded_ids.add(edge.target_id)

        functions = FunctionNode.objects.filter(id__in=expanded_ids).select_related("file")

        # 4. Build context
        context_parts = []
        for fn in functions:
            context_parts.append(f"# {fn.file.path} :: {fn.name} (line {fn.start_line})\n{fn.source}")
        context = "\n\n".join(context_parts[:12])

        # 5. Gemini answer
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            "You are a code assistant. Answer questions about the codebase using the provided function context. "
            "Be concise and reference function names and file paths.\n\n"
            f"Context:\n{context}\n\nQuestion: {query}"
        )
        response = model.generate_content(prompt)
        answer = response.text

        return Response({
            "answer": answer,
            "functions": [
                {
                    "id": fn.id,
                    "name": fn.name,
                    "file": fn.file.path,
                    "start_line": fn.start_line,
                    "summary": fn.summary,
                }
                for fn in functions
            ],
        })
