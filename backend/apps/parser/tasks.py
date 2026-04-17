import os

from apps.files.models import RepoFile
from apps.graph.models import FunctionEdge, FunctionNode
from apps.repos.models import Repository

from .extractor import SUPPORTED_EXTENSIONS, extract_functions


def parse_repository(repo_id, repo_path):
    repo = Repository.objects.get(id=repo_id)

    # Clear old data
    RepoFile.objects.filter(repository=repo).delete()
    FunctionNode.objects.filter(repository=repo).delete()

    # name → FunctionNode (for edge building)
    func_map = {}  # (file_path, func_name) → FunctionNode

    for root, dirs, files in os.walk(repo_path):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1]
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, repo_path)
            language = SUPPORTED_EXTENSIONS[ext]

            repo_file = RepoFile.objects.create(
                repository=repo, path=rel_path, language=language
            )

            functions = extract_functions(abs_path, language)
            for fn in functions:
                node = FunctionNode.objects.create(
                    repository=repo,
                    file=repo_file,
                    name=fn["name"],
                    start_line=fn["start_line"],
                    end_line=fn["end_line"],
                    source=fn["source"],
                    calls=fn["calls"],
                )
                func_map[(rel_path, fn["name"])] = node

    # Build CALLS edges
    for (rel_path, func_name), node in func_map.items():
        for called_name in node.calls:
            # Find any function with that name in the repo
            targets = FunctionNode.objects.filter(repository=repo, name=called_name).exclude(id=node.id)
            for target in targets:
                FunctionEdge.objects.get_or_create(
                    repository=repo,
                    source=node,
                    target=target,
                    defaults={"edge_type": "CALLS"},
                )
