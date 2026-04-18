import google.generativeai as genai
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FunctionEdge, FunctionNode


def serialize_node(n):
    return {
        "id": str(n.id),
        "name": n.name,
        "file": n.file.path,
        "file_id": n.file_id,
        "start_line": n.start_line,
        "summary": n.summary,
    }


def serialize_edge(e):
    return {
        "id": str(e.id),
        "source": str(e.source_id),
        "target": str(e.target_id),
        "type": e.edge_type,
    }


class GraphView(APIView):
    def get(self, request, repo_id):
        file_id = request.query_params.get("file_id")
        dir_prefix = request.query_params.get("dir")
        node_id = request.query_params.get("node_id")

        if node_id:
            center_ids = {int(node_id)}
            out_edges = list(FunctionEdge.objects.filter(source_id=node_id))
            in_edges = list(FunctionEdge.objects.filter(target_id=node_id))
            for e in out_edges + in_edges:
                center_ids.add(e.source_id)
                center_ids.add(e.target_id)
            nodes_qs = list(FunctionNode.objects.filter(id__in=center_ids).select_related("file"))
            all_edges = out_edges + in_edges

        elif file_id:
            file_nodes = list(
                FunctionNode.objects.filter(repository_id=repo_id, file_id=file_id).select_related("file")
            )
            file_node_ids = {n.id for n in file_nodes}
            out_edges = list(FunctionEdge.objects.filter(source_id__in=file_node_ids))
            in_edges = list(FunctionEdge.objects.filter(target_id__in=file_node_ids))
            all_edges = out_edges + in_edges
            neighbor_ids = set()
            for e in all_edges:
                if e.source_id not in file_node_ids:
                    neighbor_ids.add(e.source_id)
                if e.target_id not in file_node_ids:
                    neighbor_ids.add(e.target_id)
            neighbor_nodes = list(
                FunctionNode.objects.filter(id__in=neighbor_ids).select_related("file")
            ) if neighbor_ids else []
            nodes_qs = file_nodes + neighbor_nodes

        elif dir_prefix:
            from apps.files.models import RepoFile
            dir_files = RepoFile.objects.filter(
                repository_id=repo_id, path__startswith=dir_prefix + "/"
            )
            dir_file_ids = set(dir_files.values_list("id", flat=True))
            dir_nodes = list(
                FunctionNode.objects.filter(repository_id=repo_id, file_id__in=dir_file_ids).select_related("file")
            )
            dir_node_ids = {n.id for n in dir_nodes}
            out_edges = list(FunctionEdge.objects.filter(source_id__in=dir_node_ids))
            in_edges = list(FunctionEdge.objects.filter(target_id__in=dir_node_ids))
            all_edges = out_edges + in_edges
            neighbor_ids = set()
            for e in all_edges:
                if e.source_id not in dir_node_ids:
                    neighbor_ids.add(e.source_id)
                if e.target_id not in dir_node_ids:
                    neighbor_ids.add(e.target_id)
            neighbor_nodes = list(
                FunctionNode.objects.filter(id__in=neighbor_ids).select_related("file")
            ) if neighbor_ids else []
            nodes_qs = dir_nodes + neighbor_nodes

        else:
            nodes_qs = list(
                FunctionNode.objects.filter(repository_id=repo_id).select_related("file")
            )
            node_ids = {n.id for n in nodes_qs}
            all_edges = list(
                FunctionEdge.objects.filter(
                    repository_id=repo_id, source_id__in=node_ids, target_id__in=node_ids
                )
            )

        # Deduplicate edges
        seen = set()
        unique_edges = []
        for e in all_edges:
            if e.id not in seen:
                seen.add(e.id)
                unique_edges.append(e)

        return Response({
            "nodes": [serialize_node(n) for n in nodes_qs],
            "edges": [serialize_edge(e) for e in unique_edges],
        })


class TraceView(APIView):
    def get(self, request, repo_id, node_id):
        try:
            fn = FunctionNode.objects.select_related("file").get(id=node_id, repository_id=repo_id)
        except FunctionNode.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        MAX_DEPTH = int(request.query_params.get("depth", 4))

        # Pre-fetch all outgoing CALLS edges for this repo
        all_edges = FunctionEdge.objects.filter(
            repository_id=repo_id, edge_type="CALLS"
        ).select_related("target__file")
        edges_by_source: dict[int, list] = {}
        for e in all_edges:
            targets = edges_by_source.setdefault(e.source_id, [])
            # deduplicate targets by id
            if not any(t.id == e.target_id for t in targets):
                targets.append(e.target)

        # BFS — mark visited on enqueue to prevent duplicates
        visited: set[int] = {fn.id}
        flow = []
        queue = [(fn.id, 0, None)]

        while queue:
            cur_id, depth, parent_id = queue.pop(0)
            if depth > MAX_DEPTH:
                continue

            if depth > 0:
                try:
                    node = FunctionNode.objects.select_related("file").get(id=cur_id)
                    flow.append({
                        "id": str(node.id),
                        "name": node.name,
                        "file": node.file.path,
                        "depth": depth,
                        "parent_id": str(parent_id) if parent_id else None,
                    })
                except FunctionNode.DoesNotExist:
                    continue

            for child in edges_by_source.get(cur_id, []):
                if child.id not in visited:
                    visited.add(child.id)
                    queue.append((child.id, depth + 1, cur_id))

        callee_names = [s["name"] for s in flow]
        prompt = (
            f"Function: {fn.name}\nFile: {fn.file.path}\n"
        )
        if callee_names:
            prompt += "Full call chain:\n" + "".join(f"- {n}\n" for n in callee_names[:20]) + "\n"
        prompt += (
            f"Source:\n```\n{fn.source[:800]}\n```\n\n"
            "Explain in 3-5 lines what this function does and how it orchestrates its call chain. "
            "No markdown, no headers, plain text only."
        )

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        response = genai.GenerativeModel("gemini-2.0-flash").generate_content(prompt)

        return Response({
            "name": fn.name,
            "file": fn.file.path,
            "start_line": fn.start_line,
            "flow": flow,
            "explanation": response.text,
        })
