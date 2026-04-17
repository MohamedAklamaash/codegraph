import ast

SUPPORTED_EXTENSIONS = {".py": "python"}

def extract_functions(file_path, language):
    """Returns list of dicts: {name, start_line, end_line, source, calls, imports}"""
    if language != "python":
        return []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines()
    functions = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        start = node.lineno
        end = node.end_lineno
        func_source = "\n".join(lines[start - 1:end])

        # Collect function calls within this function
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        functions.append({
            "name": node.name,
            "start_line": start,
            "end_line": end,
            "source": func_source,
            "calls": list(set(calls)),
        })

    return functions

def get_imports(file_path):
    """Returns list of imported module names."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, Exception):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports
