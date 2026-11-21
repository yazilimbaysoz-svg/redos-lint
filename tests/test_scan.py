from pathlib import Path

import pytest

from redos_lint.model import Severity
from redos_lint.scan import (
    Match,
    _javascript_matches,
    _python_matches,
    _unescape_js_string,
    scan_sources,
)


def test_python_direct_call_and_keyword(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "import re\n"
        "pattern = re.compile(r'(a+)+')\n"
        "ok = re.match(r'\\d+', '42')\n"
        "other = re.compile(pattern='a+a+')\n",
        encoding="utf-8",
    )
    text = source.read_text(encoding="utf-8")
    matches = _python_matches(text, source)
    assert [match.pattern for match in matches] == [r"(a+)+", r"\d+", "a+a+"]
    assert [match.line for match in matches] == [2, 3, 4]


def test_python_ignores_unrelated_calls(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("import json\nvalue = json.loads('(a+)+')\n", encoding="utf-8")
    assert _python_matches(source.read_text(encoding="utf-8"), source) == []


def test_python_import_alias_and_from_import(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "import re as regexp\nfrom re import compile as make\n"
        "a = regexp.search(r'(a|aa)+')\nb = make('a+a+')\n",
        encoding="utf-8",
    )
    matches = _python_matches(source.read_text(encoding="utf-8"), source)
    assert len(matches) == 2


def test_javascript_literal_and_constructor() -> None:
    text = "const a = /(a+)+/g;\nconst b = new RegExp('a+a+');\nconst c = /ok/;\n"
    matches = _javascript_matches(text)
    assert [match.pattern for match in matches] == ["(a+)+", "a+a+", "ok"]
    assert [match.line for match in matches] == [1, 2, 3]


def test_unescape_js_string() -> None:
    assert _unescape_js_string(r"a\/b\\c\n") == "a/b\\c\n"


def test_javascript_literal_with_character_class() -> None:
    matches = _javascript_matches(r"const re = /[/]a+/;")
    assert matches == [Match(r"[/]a+", 1)]


def test_scan_directory_returns_locations(tmp_path: Path) -> None:
    source = tmp_path / "vulnerable.py"
    source.write_text("import re\nre.compile('(a+)+')\n", encoding="utf-8")
    report = scan_sources((tmp_path,))
    assert report.patterns_checked == 1
    assert report.findings[0].source == str(source)
    assert report.findings[0].line == 2
    assert report.findings[0].severity is Severity.CRITICAL


def test_suppression_marker(tmp_path: Path) -> None:
    source = tmp_path / "ignored.py"
    source.write_text("import re\nre.compile('(a+)+')  # redos-lint: ignore\n", encoding="utf-8")
    report = scan_sources((tmp_path,))
    assert report.patterns_checked == 1
    assert report.findings == ()


def test_exclude_glob(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("import re\nre.compile('(a+)+')\n", encoding="utf-8")
    (tmp_path / "skip.py").write_text("import re\nre.compile('(a+)+')\n", encoding="utf-8")
    report = scan_sources((tmp_path,), ("skip.py",))
    assert report.patterns_checked == 1
    assert report.findings[0].source.endswith("keep.py")


def test_default_skip_directories(tmp_path: Path) -> None:
    hidden = tmp_path / "__pycache__"
    hidden.mkdir()
    (hidden / "cached.js").write_text("const r = /(a+)+/;\n", encoding="utf-8")
    report = scan_sources((tmp_path,))
    assert report.patterns_checked == 0


def test_syntax_error_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n", encoding="utf-8")
    assert scan_sources((tmp_path,)).findings == ()


def test_duplicate_paths_are_scanned_once(tmp_path: Path) -> None:
    source = tmp_path / "one.py"
    source.write_text("import re\nre.compile('a+')\n", encoding="utf-8")
    report = scan_sources((tmp_path, source))
    assert report.patterns_checked == 1


def test_non_source_files_are_ignored(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("(a+)+\n", encoding="utf-8")
    assert scan_sources((source,)).patterns_checked == 0


def test_empty_directory(tmp_path: Path) -> None:
    assert scan_sources((tmp_path,)).findings == ()
    with pytest.raises(TypeError):
        scan_sources(None)  # type: ignore[arg-type]
