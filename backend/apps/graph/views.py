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
        node_id = request.query_params.get("node_id")

        if node_id:
            # Subgraph: node + direct neighbors (cross-file included)
            center_ids = {int(node_id)}
            out_edges = list(FunctionEdge.objects.filter(source_id=node_id))
            in_edges = list(FunctionEdge.objects.filter(target_id=node_id))
            for e in out_edges + in_edges:
                center_ids.add(e.source_id)
                center_ids.add(e.target_id)
            nodes_qs = FunctionNode.objects.filter(id__in=center_ids).select_related("file")
            all_edges = out_edges + in_edges

        elif file_id:
            # File view: all functions in file + cross-file neighbors reachable via edges
            file_nodes = list(
                FunctionNode.objects.filter(repository_id=repo_id, file_id=file_id).select_related("file")
            )
            file_node_ids = {n.id for n in file_nodes}

            # All edges where source OR target is in this file
            out_edges = list(FunctionEdge.objects.filter(source_id__in=file_node_ids))
            in_edges = list(FunctionEdge.objects.filter(target_id__in=file_node_ids))
            all_edges = out_edges + in_edges

            # Collect neighbor ids from other files
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

        else:
            # Full graph
            nodes_qs = list(
                FunctionNode.objects.filter(repository_id=repo_id).select_related("file")
            )
            node_ids = {n.id for n in nodes_qs}
            all_edges = list(
                FunctionEdge.objects.filter(repository_id=repo_id, source_id__in=node_ids, target_id__in=node_ids)
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
