"""Testy wiki_renderer — parse_jsx i render_html."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.hooker.core.wiki_renderer import (
    _esc,
    _extract_array_block,
    _split_top_objects,
    _str_field,
    parse_jsx,
    render_html,
)


# ------------------------------------------------------------------ unit helpers

def test_esc_encodes_special_chars():
    assert _esc("<b>Test & 'x'</b>") == "&lt;b&gt;Test &amp; 'x'&lt;/b&gt;"


def test_extract_array_block_simple():
    text = "const FOO = [{a:1},{b:2}];"
    result = _extract_array_block(text, "FOO")
    assert result == "[{a:1},{b:2}]"


def test_extract_array_block_missing():
    assert _extract_array_block("const X = 1;", "FOO") == "[]"


def test_split_top_objects_two():
    block = "[{a:1},{b:2}]"
    parts = _split_top_objects(block)
    assert len(parts) == 2
    assert "{a:1}" in parts[0]


def test_str_field_single_quotes():
    assert _str_field("{id: 'hello'}", "id") == "hello"


def test_str_field_double_quotes():
    assert _str_field('{id: "world"}', "id") == "world"


def test_str_field_missing():
    assert _str_field("{other: 'x'}", "id") == ""


# ------------------------------------------------------------------ parse_jsx fallback

def test_parse_jsx_missing_file_returns_empty(tmp_path: Path):
    result = parse_jsx(tmp_path / "nonexistent.jsx")
    assert result == {}


def test_render_html_missing_file_returns_error_page(tmp_path: Path):
    html = render_html(tmp_path / "nonexistent.jsx")
    assert "Nie znaleziono" in html


# ------------------------------------------------------------------ parse_jsx with minimal JSX

_MINIMAL_JSX = """\
const SECTIONS = [{id: 'events', name: 'Events', hint: 'lifecycle'}];
const EVENTS = [{id: 'Stop', cat: 'session', cadence: 'once', fires: 'CC stops'}];
const HANDLERS = [{id: 'command', name: 'Command', color: '#a3e635', tagline: 'Shell'}];
const CONTROL_MECHANISMS = [{id: 'block', name: 'Block', color: '#f43f5e', short: 'exit 2'}];
const PATTERNS = [{id: 'pat1', name: 'Pattern A', color: '#22d3ee', problem: 'Prob', solution: 'Sol'}];
"""


@pytest.fixture
def minimal_jsx(tmp_path: Path) -> Path:
    p = tmp_path / "hooks-guide.jsx"
    p.write_text(_MINIMAL_JSX, encoding="utf-8")
    return p


def test_parse_jsx_sections(minimal_jsx: Path):
    data = parse_jsx(minimal_jsx)
    assert len(data["sections"]) == 1
    assert data["sections"][0]["id"] == "events"


def test_parse_jsx_events(minimal_jsx: Path):
    data = parse_jsx(minimal_jsx)
    assert len(data["events"]) == 1
    assert data["events"][0]["id"] == "Stop"
    assert data["events"][0]["fires"] == "CC stops"


def test_parse_jsx_handlers(minimal_jsx: Path):
    data = parse_jsx(minimal_jsx)
    assert len(data["handlers"]) == 1
    assert data["handlers"][0]["name"] == "Command"


def test_parse_jsx_mechanisms(minimal_jsx: Path):
    data = parse_jsx(minimal_jsx)
    assert len(data["mechanisms"]) == 1
    assert data["mechanisms"][0]["short"] == "exit 2"


def test_parse_jsx_patterns(minimal_jsx: Path):
    data = parse_jsx(minimal_jsx)
    assert len(data["patterns"]) == 1
    assert data["patterns"][0]["name"] == "Pattern A"


def test_render_html_contains_sections(minimal_jsx: Path):
    html = render_html(minimal_jsx)
    assert "<html>" in html
    assert "Lifecycle Events" in html
    assert "Handler Types" in html
    assert "Mechanizmy kontroli" in html
    assert "Zaawansowane wzorce" in html


def test_render_html_contains_css(minimal_jsx: Path):
    html = render_html(minimal_jsx)
    assert "<style>" in html
    assert "background:#0f172a" in html


def test_render_html_has_section_anchors(minimal_jsx: Path):
    html = render_html(minimal_jsx)
    assert 'name="events"' in html
    assert 'name="handlers"' in html
