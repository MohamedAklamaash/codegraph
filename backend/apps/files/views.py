from rest_framework.response import Response
from rest_framework.views import APIView

from apps.graph.models import FunctionNode

from .models import RepoFile


class FileTreeView(APIView):
    def get(self, request, repo_id):
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
    def get(self, request, repo_id, file_id):
        functions = FunctionNode.objects.filter(
            repository_id=repo_id, file_id=file_id
        ).values("id", "name", "start_line", "end_line", "summary")
        return Response(list(functions))
