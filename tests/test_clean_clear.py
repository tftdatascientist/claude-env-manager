"""Testy dla modułu CleanClearPanel — skaner, klasyfikator, generator CLEANING.md."""

from pathlib import Path

import pytest

from src.ui.clean_clear_panel import (
    CAT_DEPENDS,
    CAT_IMPORTANT,
    CAT_JUNK,
    LineInfo,
    build_cleaned,
    build_cleaning_md,
    classify_line,
    parse_files,
    scan_project,
    stats_per_file,
)


# ── classify_line ─────────────────────────────────────────────────────────────

class TestClassifyLine:
    def test_empty_line_is_junk(self):
        assert classify_line("") == CAT_JUNK

    def test_whitespace_only_is_junk(self):
        assert classify_line("   ") == CAT_JUNK

    def test_separator_is_junk(self):
        assert classify_line("# ------") == CAT_JUNK
        assert classify_line("# ======") == CAT_JUNK

    def test_html_comment_is_junk(self):
        assert classify_line("<!-- SECTION:foo -->") == CAT_JUNK

    def test_header_is_important(self):
        assert classify_line("## Zasady kodowania") == CAT_IMPORTANT

    def test_must_keyword_is_important(self):
        assert classify_line("You MUST always use pathlib.") == CAT_IMPORTANT

    def test_important_keyword_important(self):
        assert classify_line("IMPORTANT: nie używaj hardkodowanych ścieżek.") == CAT_IMPORTANT

    def test_python_stack_is_important(self):
        assert classify_line("Stack: Python 3.13, PySide6") == CAT_IMPORTANT

    def test_regular_line_is_depends(self):
        assert classify_line("Oto zwykła linia tekstu opisująca coś.") == CAT_DEPENDS

    def test_short_line_is_junk(self):
        assert classify_line("ok") == CAT_JUNK

    def test_table_separator_is_junk(self):
        assert classify_line("| --- | --- | --- |") == CAT_JUNK


# ── scan_project ──────────────────────────────────────────────────────────────

class TestScanProject:
    def test_finds_standard_files(self, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("# test")
        (tmp_path / "PLAN.md").write_text("# plan")
        standard, extra = scan_project(tmp_path)
        assert "CLAUDE.md" in standard
        assert "PLAN.md" in standard

    def test_finds_extra_files(self, tmp_path: Path):
        (tmp_path / "NOTES.md").write_text("notes")
        standard, extra = scan_project(tmp_path)
        assert "NOTES.md" in extra

    def test_standard_not_in_extra(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("readme")
        standard, extra = scan_project(tmp_path)
        assert "README.md" not in extra

    def test_empty_dir(self, tmp_path: Path):
        standard, extra = scan_project(tmp_path)
        assert standard == []
        assert extra == []


# ── parse_files ───────────────────────────────────────────────────────────────

class TestParseFiles:
    def test_basic_parse(self, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("## Stack\nPython 3.13\n")
        lines = parse_files(tmp_path, ["CLAUDE.md"])
        assert len(lines) == 2
        assert lines[0].file == "CLAUDE.md"
        assert lines[0].lineno == 1
        assert lines[0].text == "## Stack"
        assert lines[0].category == CAT_IMPORTANT

    def test_missing_file_ignored(self, tmp_path: Path):
        lines = parse_files(tmp_path, ["NONEXISTENT.md"])
        assert lines == []

    def test_multiple_files(self, tmp_path: Path):
        (tmp_path / "A.md").write_text("lineA\n")
        (tmp_path / "B.md").write_text("lineB\n")
        lines = parse_files(tmp_path, ["A.md", "B.md"])
        files = {l.file for l in lines}
        assert "A.md" in files
        assert "B.md" in files


# ── stats_per_file ────────────────────────────────────────────────────────────

class TestStatsPerFile:
    def test_counts_categories(self):
        lines = [
            LineInfo("A.md", 1, "## Header", CAT_IMPORTANT),
            LineInfo("A.md", 2, "some text", CAT_DEPENDS),
            LineInfo("A.md", 3, "", CAT_JUNK),
            LineInfo("A.md", 4, "", CAT_JUNK),
        ]
        stats = stats_per_file(lines)
        assert stats["A.md"][CAT_IMPORTANT] == 1
        assert stats["A.md"][CAT_DEPENDS] == 1
        assert stats["A.md"][CAT_JUNK] == 2

    def test_multiple_files(self):
        lines = [
            LineInfo("A.md", 1, "x", CAT_IMPORTANT),
            LineInfo("B.md", 1, "y", CAT_JUNK),
        ]
        stats = stats_per_file(lines)
        assert "A.md" in stats
        assert "B.md" in stats


# ── build_cleaned ─────────────────────────────────────────────────────────────

class TestBuildCleaned:
    def test_removes_junk(self, tmp_path: Path):
        (tmp_path / "A.md").write_text("## Header\n\nsome text\n")
        lines = parse_files(tmp_path, ["A.md"])
        cleaned = build_cleaned(tmp_path, lines, {CAT_JUNK})
        assert "## Header" in cleaned["A.md"]
        assert "some text" in cleaned["A.md"]

    def test_removes_all_categories(self, tmp_path: Path):
        (tmp_path / "A.md").write_text("## Header\nsome text\n")
        lines = parse_files(tmp_path, ["A.md"])
        cleaned = build_cleaned(tmp_path, lines, {CAT_IMPORTANT, CAT_DEPENDS, CAT_JUNK})
        assert cleaned["A.md"].strip() == ""

    def test_empty_remove_keeps_all(self, tmp_path: Path):
        content = "## Header\nsome text\n"
        (tmp_path / "A.md").write_text(content)
        lines = parse_files(tmp_path, ["A.md"])
        cleaned = build_cleaned(tmp_path, lines, set())
        assert "## Header" in cleaned["A.md"]
        assert "some text" in cleaned["A.md"]


# ── build_cleaning_md ─────────────────────────────────────────────────────────

class TestBuildCleaningMd:
    def test_contains_removed_lines(self):
        lines = [
            LineInfo("CLAUDE.md", 3, "junk line", CAT_JUNK),
            LineInfo("CLAUDE.md", 5, "more junk", CAT_JUNK),
        ]
        result = build_cleaning_md(lines, {CAT_JUNK})
        assert "## CLAUDE.md" in result
        assert "junk line" in result
        assert "more junk" in result

    def test_does_not_contain_kept_lines(self):
        lines = [
            LineInfo("CLAUDE.md", 1, "## Important", CAT_IMPORTANT),
            LineInfo("CLAUDE.md", 2, "junk", CAT_JUNK),
        ]
        result = build_cleaning_md(lines, {CAT_JUNK})
        assert "## Important" not in result
        assert "junk" in result

    def test_empty_result_when_nothing_removed(self):
        lines = [LineInfo("CLAUDE.md", 1, "## Header", CAT_IMPORTANT)]
        result = build_cleaning_md(lines, {CAT_JUNK})
        assert "brak usuniętych" in result

    def test_section_header_per_file(self):
        lines = [
            LineInfo("CLAUDE.md", 1, "x", CAT_JUNK),
            LineInfo("PLAN.md",   1, "y", CAT_JUNK),
        ]
        result = build_cleaning_md(lines, {CAT_JUNK})
        assert "## CLAUDE.md" in result
        assert "## PLAN.md" in result

    def test_lines_in_order(self):
        lines = [
            LineInfo("CLAUDE.md", 10, "z", CAT_JUNK),
            LineInfo("CLAUDE.md", 2,  "a", CAT_JUNK),
        ]
        result = build_cleaning_md(lines, {CAT_JUNK})
        idx_a = result.index("2:")
        idx_z = result.index("10:")
        assert idx_a < idx_z
