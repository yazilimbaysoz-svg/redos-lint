"""redos-lint: zero-dependency catastrophic backtracking detection."""

from .analyzer import analyze_pattern
from .cli import main
from .model import Finding, Report, Severity
from .scan import scan_sources
from .version import __version__

__all__ = [
    "Finding",
    "Report",
    "Severity",
    "__version__",
    "analyze_pattern",
    "main",
    "scan_sources",
]
