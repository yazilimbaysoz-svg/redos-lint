import json
from pathlib import Path

from redos_lint import __version__
from redos_lint.cli import main


def test_check_safe_pattern(capsys: object) -> None:
    assert main(["check", r"\d+", "--color", "never"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "No risky patterns found" in output


def test_check_risky_pattern(capsys: object) -> None:
    assert main(["check", "(a+)+", "--color", "never"]) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "CRITICAL" in output
    assert "nested-quantifier" in output


def test_check_invalid_pattern(capsys: object) -> None:
    assert main(["check", "(a", "--color", "never"]) == 2
    assert "invalid pattern" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_json_output(capsys: object) -> None:
    assert main(["check", "(a+)+", "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert payload["version"] == 1
    assert payload["patterns_checked"] == 1
    assert payload["counts"]["critical"] == 1
    assert payload["findings"][0]["code"] == "nested-quantifier"


def test_markdown_output(capsys: object) -> None:
    assert main(["check", "a+a+", "--format", "markdown"]) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "| Severity | Location | Pattern | Rule |" in output
    assert "overlapping-quantifiers" in output


def test_fail_on_none(capsys: object) -> None:
    assert main(["check", "(a+)+", "--fail-on", "none", "--color", "never"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "0 finding(s)" in output


def test_fail_on_critical_allows_high(capsys: object) -> None:
    assert main(["check", "a+a+", "--fail-on", "critical", "--color", "never"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "HIGH" not in output


def test_version(capsys: object) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__  # type: ignore[attr-defined]


def test_scan_command(tmp_path: Path, capsys: object) -> None:
    source = tmp_path / "app.py"
    source.write_text("import re\nre.compile('(a+)+')\n", encoding="utf-8")
    assert main(["scan", str(tmp_path), "--color", "never"]) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert str(source) in output
    assert "CRITICAL" in output


def test_scan_json_with_exclusion(tmp_path: Path, capsys: object) -> None:
    (tmp_path / "bad.py").write_text("import re\nre.compile('(a+)+')\n", encoding="utf-8")
    (tmp_path / "good.py").write_text("import re\nre.compile('a+')\n", encoding="utf-8")
    assert main(["scan", str(tmp_path), "--exclude", "bad.py", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert payload["patterns_checked"] == 1
    assert payload["counts"]["critical"] == 0


def test_max_findings(tmp_path: Path, capsys: object) -> None:
    source = tmp_path / "many.py"
    source.write_text("import re\nre.compile('(a+)+')\nre.compile('(b+)+')\n", encoding="utf-8")
    assert main(["scan", str(tmp_path), "--max-findings", "1", "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert len(payload["findings"]) == 1
    assert payload["patterns_checked"] == 2


def test_color_always_emits_ansi(capsys: object) -> None:
    assert main(["check", "(a+)+", "--color", "always"]) == 1
    assert "\033[" in capsys.readouterr().out  # type: ignore[attr-defined]
