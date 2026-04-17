import ast
import re

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _find_block_end(lines, start_idx, open_ch="{", close_ch="}"):
    """Walk lines from start_idx until the opening brace's matching close brace.
    Returns the 0-based line index of the closing brace line."""
    depth = 0
    for i in range(start_idx, len(lines)):
        depth += lines[i].count(open_ch) - lines[i].count(close_ch)
        if depth <= 0 and i >= start_idx:
            return i
    return len(lines) - 1


def _call_names(source, pattern):
    """Extract called function names from source using a regex pattern."""
    return list(set(re.findall(pattern, source)))


# ---------------------------------------------------------------------------
# Python (AST — precise)
# ---------------------------------------------------------------------------

def _extract_python(file_path):
    source = _read(file_path)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start, end = node.lineno, node.end_lineno
        func_source = "\n".join(lines[start - 1 : end])
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        results.append({
            "name": node.name,
            "start_line": start,
            "end_line": end,
            "source": func_source,
            "calls": list(set(calls)),
        })
    return results


# ---------------------------------------------------------------------------
# Brace-delimited languages: JS/TS, Go, Rust, Java, C/C++, Kotlin
# ---------------------------------------------------------------------------

_FUNC_PATTERNS = {
    "javascript": [
        # function foo(  /  async function foo(
        re.compile(r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\("),
        # const foo = (...) =>  /  const foo = function(
        re.compile(r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s+)?(?:function\s*)?\("),
        # foo(...) {   (method shorthand)
        re.compile(r"^[ \t]*(?:async\s+)?(?P<name>\w+)\s*\([^)]*\)\s*\{"),
    ],
    "typescript": [
        re.compile(r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*[<(]"),
        re.compile(r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s+)?(?:function\s*)?\("),
        re.compile(r"^[ \t]*(?:(?:public|private|protected|static|async|override)\s+)*(?P<name>\w+)\s*\([^)]*\)(?:\s*:\s*\S+)?\s*\{"),
    ],
    "go": [
        re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(?P<name>\w+)\s*\("),
    ],
    "rust": [
        re.compile(r"^[ \t]*(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*[<(]"),
    ],
    "java": [
        # access modifier(s) + optional static/final + return type + name(
        re.compile(
            r"^[ \t]*(?:(?:public|private|protected|static|final|synchronized|abstract|native|default)\s+)*"
            r"(?:[\w<>\[\]]+\s+)+(?P<name>\w+)\s*\("
        ),
    ],
    "cpp": [
        # Matches: [qualifiers] return_type [ClassName::]funcName(params) [const] {
        # Handles: void Foo::bar(...) {  /  std::string baz(...) {  /  Foo::Foo(...) {
        re.compile(
            r"^[ \t]*"
            r"(?:(?:inline|static|virtual|explicit|constexpr|override|friend)\s+)*"  # optional qualifiers
            r"(?:[\w:*&<>, \t]+?\s+)?"          # optional return type (greedy-lazy)
            r"(?:[\w]+::)*"                      # optional ClassName:: prefix(es)
            r"(?P<name>~?[\w]+)\s*"              # function name (with optional ~)
            r"\([^;{]*\)\s*"                     # params — no semicolons or braces inside
            r"(?:const\s*)?(?:noexcept\s*)?"     # optional const/noexcept
            r"(?:override\s*)?(?:->\s*[\w:*& ]+\s*)?"  # optional trailing return
            r"\{"                                # opening brace on same line
        ),
        # Same but brace on next line (two-line match not possible with single regex,
        # so match the signature line alone and let _find_block_end handle it)
        re.compile(
            r"^[ \t]*"
            r"(?:(?:inline|static|virtual|explicit|constexpr|override|friend)\s+)*"
            r"(?:[\w:*&<>, \t]+?\s+)?"
            r"(?:[\w]+::)*"
            r"(?P<name>~?[\w]+)\s*"
            r"\([^;{]*\)\s*"
            r"(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?$"
        ),
    ],
    "c": [
        re.compile(r"^(?:[\w*]+\s+)+(?P<name>\w+)\s*\([^;]*\)\s*\{"),
        re.compile(r"^(?:[\w*]+\s+)+(?P<name>\w+)\s*\([^;]*\)\s*$"),
    ],
    "kotlin": [
        re.compile(r"^[ \t]*(?:(?:public|private|protected|internal|open|override|suspend|inline|operator)\s+)*fun\s+(?P<name>\w+)\s*[<(]"),
    ],
}

_CALL_RE = re.compile(r"\b(\w+)\s*\(")
_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "typeof",
    "instanceof", "void", "delete", "throw", "case", "else", "do",
    "class", "interface", "enum", "struct", "fn", "func", "fun",
    "function", "async", "await", "yield", "import", "export",
    "public", "private", "protected", "static", "final", "override",
    "super", "this", "self", "true", "false", "null", "nil", "None",
    "True", "False", "let", "const", "var", "val",
}


def _extract_brace(file_path, language):
    source = _read(file_path)
    lines = source.splitlines()
    patterns = _FUNC_PATTERNS.get(language, [])
    results = []
    seen = set()

    for i, line in enumerate(lines):
        for pat in patterns:
            m = pat.match(line)
            if not m:
                continue
            name = m.group("name")
            if name in _KEYWORDS or not name:
                continue
            key = (name, i)
            if key in seen:
                continue
            seen.add(key)

            end_i = _find_block_end(lines, i)
            func_source = "\n".join(lines[i : end_i + 1])
            calls = [c for c in _CALL_RE.findall(func_source) if c not in _KEYWORDS and c != name]

            results.append({
                "name": name,
                "start_line": i + 1,
                "end_line": end_i + 1,
                "source": func_source,
                "calls": list(set(calls)),
            })
            break  # matched, don't try other patterns for this line

    return results


def extract_functions(file_path, language):
    if language == "python":
        return _extract_python(file_path)
    if language in _FUNC_PATTERNS:
        return _extract_brace(file_path, language)
    return []


def get_imports(file_path):
    """Best-effort import extraction (Python only, kept for compatibility)."""
    try:
        source = _read(file_path)
        tree = ast.parse(source)
    except Exception:
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
