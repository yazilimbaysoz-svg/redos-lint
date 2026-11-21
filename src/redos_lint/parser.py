"""Small, dependency-free parser for the regex subset relevant to ReDoS analysis."""

from __future__ import annotations

import string
from dataclasses import dataclass

__all__ = [
    "Alternate",
    "Anchor",
    "Assertion",
    "Atomic",
    "Backref",
    "Concat",
    "Empty",
    "Literal",
    "Node",
    "RegexSyntaxError",
    "Repeat",
    "children",
    "parse",
]

_ESCAPE_SETS: dict[str, frozenset[str]] = {
    "d": frozenset("0123456789"),
    "w": frozenset(string.ascii_letters + string.digits + "_"),
    "s": frozenset(" \t\n\r\f\v"),
}
_BROAD_ESCAPES = frozenset("DWS")
_ANCHOR_ESCAPES = frozenset("bBAZ")
_DOT_EXCLUDES = frozenset("\n")
_FLAG_CHARS = frozenset("aimsuxL")


class RegexSyntaxError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (offset {position})")
        self.message = message
        self.position = position


@dataclass(frozen=True, slots=True)
class Literal:
    chars: frozenset[str] = frozenset()
    broad: bool = False
    excludes: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Empty:
    pass


@dataclass(frozen=True, slots=True)
class Anchor:
    pass


@dataclass(frozen=True, slots=True)
class Backref:
    pass


@dataclass(frozen=True, slots=True)
class Concat:
    items: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Alternate:
    branches: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Repeat:
    child: Node
    minimum: int
    maximum: int | None
    greedy: bool = True


@dataclass(frozen=True, slots=True)
class Assertion:
    child: Node


@dataclass(frozen=True, slots=True)
class Atomic:
    child: Node


Node = Literal | Empty | Anchor | Backref | Concat | Alternate | Repeat | Assertion | Atomic


def children(node: Node) -> tuple[Node, ...]:
    if isinstance(node, Concat):
        return node.items
    if isinstance(node, Alternate):
        return node.branches
    if isinstance(node, (Repeat, Assertion, Atomic)):
        return (node.child,)
    return ()


class _Parser:
    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.pos = 0

    def parse(self) -> Node:
        node = self._alternation()
        if self.pos != len(self.pattern):
            raise RegexSyntaxError("unexpected closing parenthesis", self.pos)
        return node

    def _peek(self) -> str | None:
        return self.pattern[self.pos] if self.pos < len(self.pattern) else None

    def _take(self) -> str:
        ch = self.pattern[self.pos]
        self.pos += 1
        return ch

    def _expect(self, expected: str) -> None:
        if self._peek() != expected:
            raise RegexSyntaxError(f"expected {expected!r}", self.pos)
        self._take()

    def _alternation(self) -> Node:
        branches = [self._sequence()]
        while self._peek() == "|":
            self._take()
            branches.append(self._sequence())
        if len(branches) == 1:
            return branches[0]
        return Alternate(tuple(branches))

    def _sequence(self) -> Node:
        items: list[Node] = []
        while (ch := self._peek()) is not None and ch not in "|)":
            items.append(self._quantified())
        items = [item for item in items if not isinstance(item, Empty)]
        if not items:
            return Empty()
        if len(items) == 1:
            return items[0]
        return Concat(tuple(items))

    def _quantified(self) -> Node:
        atom = self._atom()
        ch = self._peek()
        if ch in ("*", "+", "?"):
            self._take()
            minimum, maximum = (0, None) if ch == "*" else (1, None) if ch == "+" else (0, 1)
        elif ch == "{":
            bounds = self._bounds()
            if bounds is None:
                return atom
            minimum, maximum = bounds
        else:
            return atom
        greedy = True
        if self._peek() == "?":
            self._take()
            greedy = False
        elif self._peek() == "+":
            self._take()
        return Repeat(atom, minimum, maximum, greedy)

    def _bounds(self) -> tuple[int, int | None] | None:
        start = self.pos
        self._take()
        low = ""
        while (ch := self._peek()) is not None and ch.isdigit():
            low += self._take()
        if not low:
            self.pos = start
            return None
        minimum = int(low)
        if self._peek() == "}":
            self._take()
            return minimum, minimum
        if self._peek() != ",":
            self.pos = start
            return None
        self._take()
        high = ""
        while (ch := self._peek()) is not None and ch.isdigit():
            high += self._take()
        if self._peek() != "}":
            self.pos = start
            return None
        self._take()
        maximum = int(high) if high else None
        if maximum is not None and maximum < minimum:
            raise RegexSyntaxError("repetition minimum exceeds maximum", start)
        return minimum, maximum

    def _atom(self) -> Node:
        ch = self._peek()
        if ch is None:
            raise RegexSyntaxError("unexpected end of pattern", self.pos)
        if ch in "*+?":
            raise RegexSyntaxError("nothing to repeat", self.pos)
        if ch == "(":
            return self._group()
        if ch == "[":
            return self._char_class()
        if ch == "\\":
            return self._escape()
        if ch == ".":
            self._take()
            return Literal(broad=True, excludes=_DOT_EXCLUDES)
        if ch in "^$":
            self._take()
            return Anchor()
        self._take()
        return Literal(frozenset(ch))

    def _group(self) -> Node:
        start = self.pos
        self._take()
        if self._peek() != "?":
            child = self._alternation()
            self._expect(")")
            return child
        self._take()
        ch = self._peek()
        if ch == ":":
            self._take()
            child = self._alternation()
            self._expect(")")
            return child
        if ch == ">":
            self._take()
            child = self._alternation()
            self._expect(")")
            return Atomic(child)
        if ch == "#":
            while self._peek() not in (")", None):
                self._take()
            self._expect(")")
            return Empty()
        if ch in ("=", "!"):
            self._take()
            child = self._alternation()
            self._expect(")")
            return Assertion(child)
        if ch == "<":
            self._take()
            kind = self._peek()
            if kind in ("=", "!"):
                self._take()
                child = self._alternation()
                self._expect(")")
                return Assertion(child)
            while self._peek() not in (">", None):
                self._take()
            self._expect(">")
            child = self._alternation()
            self._expect(")")
            return child
        if ch == "P":
            self._take()
            if self._peek() == "=":
                self._take()
                while self._peek() not in (")", None):
                    self._take()
                self._expect(")")
                return Backref()
            if self._peek() == "<":
                self._take()
                while self._peek() not in (">", None):
                    self._take()
                self._expect(">")
                child = self._alternation()
                self._expect(")")
                return child
            raise RegexSyntaxError("invalid named group", start)
        if ch in _FLAG_CHARS:
            while (flag := self._peek()) is not None and flag in _FLAG_CHARS:
                self._take()
            if self._peek() == ")":
                self._take()
                return Anchor()
            if self._peek() == ":":
                self._take()
                child = self._alternation()
                self._expect(")")
                return child
        raise RegexSyntaxError("unsupported group construct", start)

    def _escape(self, *, in_class: bool = False) -> Node:
        start = self.pos
        self._take()
        ch = self._peek()
        if ch is None:
            raise RegexSyntaxError("trailing backslash", start)
        self._take()
        if ch in _ESCAPE_SETS:
            return Literal(_ESCAPE_SETS[ch])
        if ch in _BROAD_ESCAPES:
            return Literal(broad=True, excludes=_ESCAPE_SETS[ch.lower()])
        if ch in _ANCHOR_ESCAPES:
            return Anchor() if not in_class else Literal(frozenset(ch))
        if ch.isdigit():
            if ch == "0":
                return Literal(frozenset("\x00"))
            return Backref()
        if ch in ("x", "u", "U"):
            width = {"x": 2, "u": 4, "U": 8}[ch]
            digits = "".join(self._take() for _ in range(width) if self._peek() is not None)
            if len(digits) != width:
                raise RegexSyntaxError("incomplete hex escape", start)
            try:
                value = int(digits, 16)
                return Literal(frozenset(chr(value)))
            except (ValueError, OverflowError) as exc:
                raise RegexSyntaxError("invalid hex escape", start) from exc
        return Literal(frozenset(ch))

    def _class_char(self) -> str:
        ch = self._take()
        if ch != "\\":
            return ch
        node = self._escape(in_class=True)
        if isinstance(node, Literal) and len(node.chars) == 1:
            return next(iter(node.chars))
        return "\x00"

    def _char_class(self) -> Node:
        start = self.pos
        self._take()
        negated = self._peek() == "^"
        if negated:
            self._take()
        chars: set[str] = set()
        excluded: set[str] = set()
        broad = negated
        previous: str | None = None
        first = True
        while True:
            ch = self._peek()
            if ch is None:
                raise RegexSyntaxError("unterminated character class", start)
            if ch == "]" and not first:
                self._take()
                break
            first = False
            if (
                ch == "-"
                and previous is not None
                and self.pos + 1 < len(self.pattern)
                and self.pattern[self.pos + 1] != "]"
            ):
                self._take()
                end = self._class_char()
                if ord(end) >= ord(previous):
                    for code in range(ord(previous), min(ord(end), ord(previous) + 64) + 1):
                        chars.add(chr(code))
                previous = None
                continue
            if ch == "\\":
                node = self._escape(in_class=True)
                if isinstance(node, Literal):
                    chars.update(node.chars)
                    excluded.update(node.excludes)
                    broad = broad or node.broad
                previous = None
                continue
            self._take()
            chars.add(ch)
            previous = ch
        if negated:
            excluded.update(chars)
        return Literal(frozenset(chars), broad=broad, excludes=frozenset(excluded))


def parse(pattern: str) -> Node:
    return _Parser(pattern).parse()
