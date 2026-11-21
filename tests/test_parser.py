import pytest

from redos_lint.parser import (
    Alternate,
    Anchor,
    Assertion,
    Atomic,
    Backref,
    Concat,
    Empty,
    Literal,
    RegexSyntaxError,
    Repeat,
    children,
    parse,
)


def test_literal_and_concat() -> None:
    assert parse("abc") == Concat(
        (Literal(frozenset("a")), Literal(frozenset("b")), Literal(frozenset("c")))
    )


def test_single_literal_is_not_wrapped() -> None:
    assert parse("a") == Literal(frozenset("a"))


def test_empty_alternative_branch() -> None:
    assert parse("a|") == Alternate((Literal(frozenset("a")), Empty()))


def test_alternation_precedence() -> None:
    tree = parse("ab|cd")
    assert isinstance(tree, Alternate)
    assert all(isinstance(branch, Concat) for branch in tree.branches)


@pytest.mark.parametrize(
    ("pattern", "minimum", "maximum"),
    [
        ("a*", 0, None),
        ("a+", 1, None),
        ("a?", 0, 1),
        ("a{3}", 3, 3),
        ("a{2,}", 2, None),
        ("a{1,5}", 1, 5),
    ],
)
def test_quantifiers(pattern: str, minimum: int, maximum: int | None) -> None:
    tree = parse(pattern)
    assert isinstance(tree, Repeat)
    assert (tree.minimum, tree.maximum) == (minimum, maximum)


def test_lazy_quantifier() -> None:
    tree = parse("a+?")
    assert isinstance(tree, Repeat)
    assert tree.greedy is False


def test_possessive_quantifier() -> None:
    tree = parse("a++")
    assert isinstance(tree, Repeat)
    assert tree.maximum is None


def test_bad_bounds_raise() -> None:
    with pytest.raises(RegexSyntaxError):
        parse("a{2,1}")


def test_capturing_and_non_capturing_groups() -> None:
    assert parse("(?:ab)") == parse("ab")
    assert parse("(ab)") == parse("ab")


def test_named_groups_python_and_javascript() -> None:
    assert parse("(?P<word>a)") == Literal(frozenset("a"))
    assert parse("(?<word>a)") == Literal(frozenset("a"))
    assert parse("(?P=word)") == Backref()


def test_assertions_and_atomic_groups() -> None:
    assert isinstance(parse("(?=a)"), Assertion)
    assert isinstance(parse("(?!a)"), Assertion)
    assert isinstance(parse("(?<=a)"), Assertion)
    assert isinstance(parse("(?<!a)"), Assertion)
    assert isinstance(parse("(?>a+)"), Atomic)


def test_inline_flags_and_comments() -> None:
    assert parse("(?i)") == Anchor()
    assert parse("(?i:a)") == Literal(frozenset("a"))
    assert parse("(?#note)a") == parse("a")


def test_character_class_ranges_and_negation() -> None:
    tree = parse("[a-c]")
    assert isinstance(tree, Literal)
    assert {"a", "b", "c"} <= tree.chars
    assert tree.broad is False
    negated = parse("[^a]")
    assert isinstance(negated, Literal)
    assert negated.broad is True


def test_character_class_with_leading_bracket_and_range() -> None:
    tree = parse("[]-a]")
    assert isinstance(tree, Literal)
    assert "]" in tree.chars


@pytest.mark.parametrize("pattern", [r"\d", r"\w", r"\s"])
def test_common_escape_sets(pattern: str) -> None:
    tree = parse(pattern)
    assert isinstance(tree, Literal)
    assert tree.chars and not tree.broad


@pytest.mark.parametrize("pattern", [r"\D", r"\W", r"\S", "."])
def test_broad_escapes(pattern: str) -> None:
    tree = parse(pattern)
    assert isinstance(tree, Literal)
    assert tree.broad is True


@pytest.mark.parametrize("pattern", [r"\b", r"\A", r"\Z", "^", "$"])
def test_anchors(pattern: str) -> None:
    assert parse(pattern) == Anchor()


def test_hex_and_backreference_escapes() -> None:
    assert parse(r"\x41") == Literal(frozenset("A"))
    assert parse(r"\u0042") == Literal(frozenset("B"))
    assert parse(r"\U00000043") == Literal(frozenset("C"))
    assert parse(r"\1") == Backref()


def test_escaped_digits_in_class() -> None:
    tree = parse(r"[\d-]")
    assert isinstance(tree, Literal)
    assert "0" in tree.chars
    assert "-" in tree.chars


@pytest.mark.parametrize("pattern", ["(", ")", "[a", "a{2,1}", "a\\", "*a", "(?Q)a"])
def test_invalid_patterns_raise(pattern: str) -> None:
    with pytest.raises(RegexSyntaxError):
        parse(pattern)


def test_children_helper() -> None:
    tree = parse("(a|b)+c")
    assert len(children(tree)) == 2
    repeat = children(tree)[0]
    assert isinstance(repeat, Repeat)
    assert len(children(repeat)) == 1
    assert isinstance(children(repeat)[0], Alternate)
    assert children(Literal(frozenset("x"))) == ()
