from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.graph.models import FunctionNode
from apps.repos.utils import user_has_repo_access

from .models import RepoFile


class FileTreeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, repo_id):
        if not user_has_repo_access(request.user, repo_id):
            return Response({"error": "not found"}, status=404)
        files = RepoFile.objects.filter(repository_id=repo_id).values("id", "path", "language")
        tree = {}
        for f in files:
            parts = f["path"].split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = {"id": f["id"], "path": f["path"], "language": f["language"], "type": "file"}
        return Response({"tree": tree, "files": list(files)})


class FileFunctionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, repo_id, file_id):
        if not user_has_repo_access(request.user, repo_id):
            return Response({"error": "not found"}, status=404)
        functions = FunctionNode.objects.filter(
            repository_id=repo_id, file_id=file_id
        ).values("id", "name", "start_line", "end_line", "summary")
        return Response(list(functions))
