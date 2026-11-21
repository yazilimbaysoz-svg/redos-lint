"""Command line interface for redos-lint."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analyzer import analyze_pattern
from .model import Finding, Report, Severity
from .parser import RegexSyntaxError, parse
from .scan import scan_sources
from .version import __version__

_LEVELS = ("low", "medium", "high", "critical", "none")
_FORMATS = ("text", "json", "markdown")
_COLORS = {
    "low": "\033[36m",
    "medium": "\033[33m",
    "high": "\033[31m",
    "critical": "\033[1;31m",
}
_RESET = "\033[0m"
_DIM = "\033[2m"


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=_FORMATS, default="text", help="output format")
    common.add_argument(
        "--fail-on", choices=_LEVELS, default="high", help="minimum severity that fails the run"
    )
    common.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto", help="ANSI color mode"
    )
    parser = argparse.ArgumentParser(
        prog="redos-lint",
        description="Detect catastrophic regex backtracking before it reaches production.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check", parents=[common], help="analyze a single regular expression"
    )
    check.add_argument("pattern", help="regular expression pattern to analyze")
    scan = subparsers.add_parser(
        "scan", parents=[common], help="analyze regexes found in source files"
    )
    scan.add_argument("paths", nargs="+", type=Path, help="files or directories to scan")
    scan.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB", help="exclude matching paths"
    )
    scan.add_argument(
        "--max-findings", type=int, default=100, help="maximum number of reported findings"
    )
    subparsers.add_parser("version", help="print the installed version")
    return parser


def _use_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty()


def _location(finding: Finding) -> str:
    if finding.source and finding.line:
        return f"{finding.source}:{finding.line}"
    return finding.source or "<literal>"


def _render_text(report: Report, threshold: Severity | None, color: bool) -> str:
    selected = report.filtered(threshold)
    lines = [f"redos-lint: {len(selected)} finding(s) across {report.patterns_checked} pattern(s)"]
    for finding in sorted(selected, key=lambda item: (-item.severity, _location(item))):
        level = finding.severity.label()
        label = f"[{level.upper()}]"
        if color:
            label = f"{_COLORS[level]}{label}{_RESET}"
        lines.append(f"  {label} {_location(finding)}  {finding.code}")
        lines.append(f"      pattern: {finding.pattern}")
        lines.append(f"      {finding.message}")
        if color:
            lines.append(f"      {_DIM}fix: {finding.suggestion}{_RESET}")
        else:
            lines.append(f"      fix: {finding.suggestion}")
    if not selected:
        lines.append("  No risky patterns found.")
    return "\n".join(lines)


def _render_markdown(report: Report, threshold: Severity | None) -> str:
    selected = report.filtered(threshold)
    lines = [
        "# redos-lint report",
        "",
        f"Patterns checked: {report.patterns_checked}",
        "",
        "| Severity | Location | Pattern | Rule |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for finding in sorted(selected, key=lambda item: (-item.severity, _location(item))):
        pattern = finding.pattern.replace("|", "\\|").replace("`", "'")
        lines.append(
            f"| {finding.severity.label()} | `{_location(finding)}` | `{pattern}` | "
            f"{finding.code} |"
        )
    if not selected:
        lines.append("| - | - | - | no findings |")
    return "\n".join(lines)


def _render(report: Report, threshold: Severity | None, fmt: str, color: bool) -> str:
    if fmt == "json":
        return json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if fmt == "markdown":
        return _render_markdown(report, threshold)
    return _render_text(report, threshold, color)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    threshold = Severity.parse(args.fail_on)
    if args.command == "check":
        try:
            parse(args.pattern)
        except RegexSyntaxError as exc:
            print(f"redos-lint: invalid pattern: {exc}", file=sys.stderr)
            return 2
        report = Report(analyze_pattern(args.pattern), 1)
    else:
        report = scan_sources(tuple(args.paths), tuple(args.exclude))
        if len(report.findings) > args.max_findings:
            report = Report(report.findings[: args.max_findings], report.patterns_checked)
    print(_render(report, threshold, args.format, _use_color(args.color)))
    return 1 if report.filtered(threshold) else 0
