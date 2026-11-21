"""Source-file regex extraction for Python and JavaScript/TypeScript."""

from __future__ import annotations

import ast
import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

from .analyzer import analyze_pattern
from .model import Finding, Report

_PY_EXTENSIONS = frozenset({".py", ".pyi"})
_JS_EXTENSIONS = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})
_RE_CALLS = frozenset(
    {"compile", "match", "search", "fullmatch", "findall", "finditer", "sub", "subn", "split"}
)
_MODULES = frozenset({"re", "regex"})
_SUPPRESSORS = ("redos-lint: ignore", "redos-lint: disable")
_DEFAULT_SKIP_DIRS = frozenset(
    {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}
)
_JS_LITERAL = re.compile(
    r"(?<![A-Za-z0-9_$/])/(?P<body>(?:\\.|\[(?:\\.|[^\]])*\]|[^/\n])*)/(?P<flags>[a-z]*)"
)
_JS_CONSTRUCTOR = re.compile(
    r"\b(?:new\s+)?RegExp\(\s*(?P<quote>['\"])(?P<body>(?:\\.|(?!\1)[^\\])*)(?P=quote)"
)


@dataclass(frozen=True, slots=True)
class Match:
    pattern: str
    line: int


def _python_matches(text: str, path: Path) -> list[Match]:
    tree = ast.parse(text, filename=str(path))
    modules: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _MODULES:
                    modules.add(alias.asname or root)
        elif isinstance(node, ast.ImportFrom) and node.module in _MODULES:
            for alias in node.names:
                if alias.name in _RE_CALLS:
                    functions.add(alias.asname or alias.name)
    results: list[Match] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        direct_module = (
            isinstance(func, ast.Attribute)
            and func.attr in _RE_CALLS
            and isinstance(func.value, ast.Name)
            and func.value.id in modules
        )
        direct_function = isinstance(func, ast.Name) and func.id in functions
        if not (direct_module or direct_function):
            continue
        argument = node.args[0] if node.args else None
        if argument is None:
            argument = next((kw.value for kw in node.keywords if kw.arg == "pattern"), None)
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            results.append(Match(argument.value, node.lineno))
    return results


def _unescape_js_string(value: str) -> str:
    output: list[str] = []
    index = 0
    replacements = {"n": "\n", "t": "\t", "r": "\r", "v": "\v", "f": "\f", "0": "\x00"}
    while index < len(value):
        ch = value[index]
        if ch != "\\" or index + 1 >= len(value):
            output.append(ch)
            index += 1
            continue
        following = value[index + 1]
        if following in replacements:
            output.append(replacements[following])
        elif following == "u" and index + 5 < len(value):
            digits = value[index + 2 : index + 6]
            try:
                output.append(chr(int(digits, 16)))
            except ValueError:
                output.append(following)
            index += 4
        else:
            output.append(following)
        index += 2
    return "".join(output)


def _javascript_matches(text: str) -> list[Match]:
    results: list[Match] = []
    for match in _JS_LITERAL.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        results.append(Match(match.group("body"), line))
    for match in _JS_CONSTRUCTOR.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        results.append(Match(_unescape_js_string(match.group("body")), line))
    return sorted(results, key=lambda item: item.line)


def _matches_for(path: Path) -> list[Match]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in _PY_EXTENSIONS:
        return _python_matches(text, path)
    if path.suffix.lower() in _JS_EXTENSIONS:
        return _javascript_matches(text)
    return []


def _excluded(path: Path, root: Path, excludes: tuple[str, ...]) -> bool:
    relative = path.relative_to(root).as_posix()
    parts = set(relative.split("/")[:-1])
    if parts & _DEFAULT_SKIP_DIRS:
        return True
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern)
        for pattern in excludes
    )


def _collect(paths: tuple[Path, ...], excludes: tuple[str, ...]) -> list[Path]:
    collected: dict[Path, None] = {}
    for path in paths:
        if path.is_file():
            collected[path.resolve()] = None
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if (
                    not candidate.is_file()
                    or candidate.suffix.lower() not in _PY_EXTENSIONS | _JS_EXTENSIONS
                ):
                    continue
                if not _excluded(candidate, path, excludes):
                    collected[candidate.resolve()] = None
    return list(collected)


def scan_sources(paths: tuple[Path, ...], excludes: tuple[str, ...] = ()) -> Report:
    findings: list[Finding] = []
    checked = 0
    for path in _collect(paths, excludes):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            matches = _matches_for(path)
        except SyntaxError:
            continue
        source = str(path)
        for match in matches:
            checked += 1
            line_text = lines[match.line - 1] if 0 < match.line <= len(lines) else ""
            if any(marker in line_text for marker in _SUPPRESSORS):
                continue
            for finding in analyze_pattern(match.pattern):
                findings.append(
                    Finding(
                        finding.pattern,
                        finding.severity,
                        finding.code,
                        finding.message,
                        finding.suggestion,
                        source,
                        match.line,
                    )
                )
    return Report(findings, checked)
