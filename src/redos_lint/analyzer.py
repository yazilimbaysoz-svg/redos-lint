"""Heuristic ReDoS detection over the lightweight regex AST."""

from __future__ import annotations

from itertools import combinations, pairwise

from .model import Finding, Severity
from .parser import (
    Alternate,
    Anchor,
    Assertion,
    Atomic,
    Backref,
    Concat,
    Empty,
    Literal,
    Node,
    RegexSyntaxError,
    Repeat,
    children,
    parse,
)

_FIX_BOUND = "Bound the quantifier (for example {1,64}) or validate the maximum input length first."
_FIX_ATOMIC = "Use an atomic group or possessive quantifier when the regex engine supports it."
_FIX_MERGE = (
    "Combine adjacent quantifiers into one bounded expression, or use a single character class."
)
_FIX_ALT = (
    "Replace overlapping branches with one bounded class/expression, or make the group atomic."
)


def is_nullable(node: Node) -> bool:
    if isinstance(node, (Empty, Anchor, Backref, Assertion)):
        return True
    if isinstance(node, Repeat):
        return node.minimum == 0 or is_nullable(node.child)
    if isinstance(node, Concat):
        return all(is_nullable(item) for item in node.items)
    if isinstance(node, Alternate):
        return any(is_nullable(branch) for branch in node.branches)
    if isinstance(node, Atomic):
        return is_nullable(node.child)
    return False


def first_chars(node: Node) -> tuple[frozenset[str], bool, frozenset[str]]:
    if isinstance(node, Literal):
        return node.chars, node.broad, node.excludes
    if isinstance(node, Concat):
        result: set[str] = set()
        excluded: set[str] = set()
        broad = False
        for item in node.items:
            chars, item_broad, item_excludes = first_chars(item)
            result.update(chars)
            excluded.update(item_excludes)
            broad = broad or item_broad
            if not is_nullable(item):
                break
        return frozenset(result), broad, frozenset(excluded)
    if isinstance(node, Alternate):
        result: set[str] = set()
        excluded: set[str] = set()
        broad = False
        for branch in node.branches:
            chars, branch_broad, branch_excludes = first_chars(branch)
            result.update(chars)
            excluded.update(branch_excludes)
            broad = broad or branch_broad
        return frozenset(result), broad, frozenset(excluded)
    if isinstance(node, (Repeat, Atomic)):
        return first_chars(node.child)
    return frozenset(), False, frozenset()


def _overlaps(left: Node, right: Node) -> bool:
    left_chars, left_broad, left_excludes = first_chars(left)
    right_chars, right_broad, right_excludes = first_chars(right)
    if left_broad and right_broad:
        return True
    if left_broad:
        return any(char not in left_excludes for char in right_chars)
    if right_broad:
        return any(char not in right_excludes for char in left_chars)
    return bool(left_chars & right_chars)


def _contains(node: Node, kind: type[Node]) -> bool:
    return isinstance(node, kind) or any(_contains(child, kind) for child in children(node))


def _branches_overlap(node: Alternate) -> bool:
    for left, right in combinations(node.branches, 2):
        if _overlaps(left, right) or (is_nullable(left) and is_nullable(right)):
            return True
    return False


def _finding(
    pattern: str,
    severity: Severity,
    code: str,
    message: str,
    suggestion: str,
) -> Finding:
    return Finding(pattern, severity, code, message, suggestion)


def _check_repeat(node: Repeat, pattern: str, output: list[Finding]) -> None:
    if node.maximum is not None and node.maximum <= 1:
        return
    child = node.child
    if isinstance(child, Atomic):
        return
    reasons: list[str] = []
    unbounded = node.maximum is None
    code = "ambiguous-quantifier"
    if _contains(child, Repeat):
        reasons.append("the repeated expression contains another quantifier")
        code = "nested-quantifier"
    if isinstance(child, Alternate) and _branches_overlap(child):
        reasons.append("alternation branches can match the same input")
        code = "overlapping-alternation"
    if is_nullable(child) and not isinstance(child, Alternate):
        reasons.append("the repeated expression can match an empty string")
    if _contains(child, Backref):
        reasons.append("the repeated expression contains a backreference")
    if not reasons:
        return
    severity = (
        Severity.CRITICAL
        if unbounded and code in {"nested-quantifier", "overlapping-alternation"}
        else Severity.HIGH
    )
    suggestion = _FIX_ATOMIC if code == "overlapping-alternation" else _FIX_BOUND
    output.append(
        _finding(
            pattern,
            severity,
            code,
            f"Unbounded repetition is ambiguous: {'; '.join(reasons)}.",
            suggestion,
        )
    )


def _check_adjacent(items: tuple[Node, ...], pattern: str, output: list[Finding]) -> None:
    for left, right in pairwise(items):
        if not isinstance(left, Repeat) or not isinstance(right, Repeat):
            continue
        if left.maximum == 0 or right.maximum == 0:
            continue
        if not _overlaps(left, right):
            continue
        unbounded = left.maximum is None or right.maximum is None
        output.append(
            _finding(
                pattern,
                Severity.HIGH if unbounded else Severity.MEDIUM,
                "overlapping-quantifiers",
                "Adjacent quantifiers can consume the same characters, "
                "creating ambiguous backtracking paths.",
                _FIX_MERGE,
            )
        )


def _walk(node: Node, pattern: str, output: list[Finding]) -> None:
    if isinstance(node, Repeat):
        _check_repeat(node, pattern, output)
    elif isinstance(node, Concat):
        _check_adjacent(node.items, pattern, output)
    elif isinstance(node, Alternate) and _branches_overlap(node) and _contains(node, Repeat):
        output.append(
            _finding(
                pattern,
                Severity.MEDIUM,
                "overlapping-alternation",
                "Alternation branches overlap and contain quantifiers; "
                "the engine may retry the same input.",
                _FIX_ALT,
            )
        )
    for child in children(node):
        _walk(child, pattern, output)


def analyze_pattern(pattern: str) -> tuple[Finding, ...]:
    try:
        tree = parse(pattern)
    except RegexSyntaxError as exc:
        return (
            _finding(
                pattern,
                Severity.LOW,
                "parse-error",
                f"The analyzer could not fully parse this pattern: {exc}",
                "Review the pattern manually or simplify the unsupported construct.",
            ),
        )
    output: list[Finding] = []
    _walk(tree, pattern, output)
    unique: dict[tuple[str, str], Finding] = {}
    for finding in output:
        unique.setdefault((finding.code, finding.message), finding)
    return tuple(sorted(unique.values(), key=lambda item: (-item.severity, item.code))[:5])
