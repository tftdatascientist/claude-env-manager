"""Tests for utils/parsers.py."""

import json
import pytest
from pathlib import Path

from src.utils.parsers import parse_json, extract_frontmatter, detect_file_format, read_text


class TestReadText:
    def test_reads_existing_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        assert read_text(f) == "hello"

    def test_returns_none_for_missing(self, tmp_path: Path):
        assert read_text(tmp_path / "nope.txt") is None


class TestParseJson:
    def test_valid_json(self, tmp_path: Path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        assert parse_json(f) == {"key": "value"}

    def test_invalid_json(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{not json}", encoding="utf-8")
        assert parse_json(f) is None

    def test_missing_file(self, tmp_path: Path):
        assert parse_json(tmp_path / "missing.json") is None


class TestExtractFrontmatter:
    def test_simple_frontmatter(self):
        text = "---\ntitle: Test\ndescription: A test\n---\n# Content"
        result = extract_frontmatter(text)
        assert result == {"title": "Test", "description": "A test"}

    def test_no_frontmatter(self):
        assert extract_frontmatter("# Just markdown") is None

    def test_unclosed_frontmatter(self):
        assert extract_frontmatter("---\ntitle: Test\nno closing") is None


class TestDetectFileFormat:
    @pytest.mark.parametrize("name,expected", [
        ("settings.json", "json"),
        ("CLAUDE.md", "markdown"),
        ("config.yaml", "yaml"),
        (".gitconfig", "ini"),
        ("unknown.txt", "text"),
    ])
    def test_formats(self, name: str, expected: str):
        assert detect_file_format(Path(name)) == expected
