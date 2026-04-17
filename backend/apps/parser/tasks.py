import os

from apps.files.models import RepoFile
from apps.graph.models import FunctionEdge, FunctionNode
from apps.repos.models import Repository

from .extractor import SUPPORTED_EXTENSIONS, extract_functions

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "__pycache__",
    ".venv", "venv", "env", "target", ".idea", ".vscode",
}

# Common stdlib/framework method names — skip cross-file edge creation for these
_NOISE_CALLS = {
    "add", "remove", "get", "set", "put", "delete", "update", "init",
    "start", "stop", "run", "close", "open", "read", "write", "print",
    "append", "extend", "insert", "pop", "push", "clear", "reset",
    "toString", "equals", "hashCode", "compareTo", "clone",
    "paintComponent", "paint", "repaint", "revalidate",
    "windowClosing", "windowOpened", "windowClosed", "actionPerformed",
    "mouseClicked", "keyPressed", "keyReleased",
    "setUp", "tearDown", "beforeEach", "afterEach",
}


def parse_repository(repo_id, repo_path):
    repo = Repository.objects.get(id=repo_id)

    RepoFile.objects.filter(repository=repo).delete()
    FunctionNode.objects.filter(repository=repo).delete()

    func_map = {}  # (rel_path, func_name) -> FunctionNode

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
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

    # Build CALLS edges — prefer same-directory matches, skip noise names
    for (rel_path, _func_name), node in func_map.items():
        src_dir = os.path.dirname(rel_path)
        for called_name in node.calls:
            if called_name in _NOISE_CALLS:
                continue
            targets = FunctionNode.objects.filter(
                repository=repo, name=called_name
            ).exclude(id=node.id).select_related("file")

            if not targets:
                continue

            # Prefer targets in the same directory; fall back to all if none found there
            same_dir = [t for t in targets if os.path.dirname(t.file.path) == src_dir]
            chosen = same_dir if same_dir else list(targets)

            for target in chosen:
                FunctionEdge.objects.get_or_create(
                    repository=repo,
                    source=node,
                    target=target,
                    defaults={"edge_type": "CALLS"},
                )
