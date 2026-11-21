import pytest

from redos_lint.analyzer import analyze_pattern, first_chars, is_nullable
from redos_lint.model import Finding, Severity
from redos_lint.parser import Literal, parse


@pytest.mark.parametrize(
    "pattern",
    [
        "a+",
        r"\d+",
        r"\w+@\w+\.\w+",
        "(a|b)+",
        "^[a-z]{1,32}$",
        "colou?r",
        "(?:foo|bar)*x",
        r"\s*key\s*=\s*\S+",
        "[a-z0-9_-]{3,20}",
        "https?://[^/]+",
    ],
)
def test_safe_patterns_have_no_findings(pattern: str) -> None:
    assert analyze_pattern(pattern) == ()


def test_nested_quantifier_is_critical() -> None:
    findings = analyze_pattern("(a+)+")
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].code == "nested-quantifier"


@pytest.mark.parametrize("pattern", ["(a|aa)+", "(a|a)*", "(.|.cl)+"])
def test_overlapping_alternation_is_critical(pattern: str) -> None:
    findings = analyze_pattern(pattern)
    assert findings
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].code == "overlapping-alternation"


@pytest.mark.parametrize("pattern", ["(a*)*", "(a?)+", "((ab)*)*"])
def test_nullable_nested_repeat_is_critical(pattern: str) -> None:
    findings = analyze_pattern(pattern)
    assert findings[0].severity is Severity.CRITICAL


def test_adjacent_overlapping_quantifiers_are_high() -> None:
    findings = analyze_pattern(r"\s+\s+")
    assert findings
    assert findings[0].severity is Severity.HIGH
    assert findings[0].code == "overlapping-quantifiers"


def test_bounded_adjacent_overlap_is_medium() -> None:
    findings = analyze_pattern("a{2,4}a{2,4}")
    assert findings[0].severity is Severity.MEDIUM


def test_bounded_nested_quantifier_is_high() -> None:
    findings = analyze_pattern("(a+){1,4}")
    assert findings[0].severity is Severity.HIGH
    assert findings[0].code == "nested-quantifier"


def test_atomic_group_suppresses_finding() -> None:
    assert analyze_pattern("(?>a+)+") == ()


def test_backreference_inside_repeat_is_flagged() -> None:
    findings = analyze_pattern(r"(a+)\1+")
    assert findings[0].severity is Severity.HIGH
    assert "backreference" in findings[0].message


def test_parse_error_is_low_severity() -> None:
    findings = analyze_pattern("(a")
    assert len(findings) == 1
    assert findings[0].severity is Severity.LOW
    assert findings[0].code == "parse-error"


def test_findings_are_sorted_and_limited() -> None:
    findings = analyze_pattern("(a+)+(a|aa)+a+a+")
    assert [item.severity for item in findings] == sorted(
        (item.severity for item in findings), reverse=True
    )
    assert len(findings) <= 5


def test_findings_are_deduplicated() -> None:
    findings = analyze_pattern("a+a+a+a+")
    assert len(findings) == 1


def test_finding_is_hashable_value() -> None:
    first = analyze_pattern("(a+)+")[0]
    second = analyze_pattern("(a+)+")[0]
    assert first == second
    assert isinstance(first, Finding)
    assert first.to_dict()["severity"] == "critical"


@pytest.mark.parametrize(
    ("pattern", "nullable"),
    [
        ("a", False),
        ("a*", True),
        ("a?", True),
        ("ab", False),
        ("a|", True),
        ("^a$", False),
        ("(?>a)", False),
    ],
)
def test_is_nullable(pattern: str, nullable: bool) -> None:
    assert is_nullable(parse(pattern)) is nullable


def test_first_chars_returns_set_broad_flag_and_exclusions() -> None:
    chars, broad, excludes = first_chars(parse("abc"))
    assert chars == frozenset("a")
    assert broad is False
    assert excludes == frozenset()
    chars, broad, excludes = first_chars(parse(r"\s+"))
    assert " " in chars
    assert broad is False
    chars, broad, excludes = first_chars(parse(".*"))
    assert broad is True
    assert "\n" in excludes


def test_broad_literal_model() -> None:
    node = Literal(broad=True)
    assert node.chars == frozenset()
    assert node.broad is True
