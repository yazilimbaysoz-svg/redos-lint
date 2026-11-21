"""Data models shared by the analyzer, scanner and CLI."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

_SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> Severity | None:
        if value == "none":
            return None
        return cls(_SEVERITY_RANK[value.lower()])

    def label(self) -> str:
        return self.name.lower()


class Finding:
    __slots__ = ("code", "line", "message", "pattern", "severity", "source", "suggestion")

    def __init__(
        self,
        pattern: str,
        severity: Severity,
        code: str,
        message: str,
        suggestion: str,
        source: str | None = None,
        line: int | None = None,
    ) -> None:
        self.pattern = pattern
        self.severity = severity
        self.code = code
        self.message = message
        self.suggestion = suggestion
        self.source = source
        self.line = line

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "pattern": self.pattern,
            "severity": self.severity.label(),
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }
        if self.source is not None:
            result["source"] = self.source
        if self.line is not None:
            result["line"] = self.line
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Finding):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        location = f"{self.source}:{self.line}" if self.source else "<pattern>"
        return f"Finding({self.severity.label()}, {location}, {self.code})"


class Report:
    __slots__ = ("findings", "patterns_checked")

    def __init__(
        self, findings: list[Finding] | tuple[Finding, ...] = (), patterns_checked: int = 0
    ) -> None:
        self.findings = tuple(findings)
        self.patterns_checked = patterns_checked

    def filtered(self, threshold: Severity | None) -> list[Finding]:
        if threshold is None:
            return []
        return [finding for finding in self.findings if finding.severity >= threshold]

    def counts(self) -> dict[str, int]:
        return {level: 0 for level in _SEVERITY_RANK} | {
            level: sum(1 for item in self.findings if item.severity.label() == level)
            for level in _SEVERITY_RANK
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "patterns_checked": self.patterns_checked,
            "counts": self.counts(),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def __bool__(self) -> bool:
        return bool(self.findings)
