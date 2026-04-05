"""Parsers for JSON, Markdown, and YAML frontmatter."""

import json
from pathlib import Path


def read_text(path: Path) -> str | None:
    """Read file as UTF-8 text. Returns None if file doesn't exist or can't be read."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def parse_json(path: Path) -> dict | list | None:
    """Parse a JSON file. Returns None on failure."""
    text = read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_frontmatter(text: str) -> dict[str, str] | None:
    """Extract YAML-like frontmatter from Markdown text.

    Parses simple key: value pairs (no nested YAML).
    Returns None if no frontmatter found.
    """
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None
    frontmatter: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def detect_file_format(path: Path) -> str:
    """Detect display format based on file extension."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in (".md", ".markdown"):
        return "markdown"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if suffix in (".ini", ".cfg") or name in (".gitconfig", ".gitconfig.local"):
        return "ini"
    return "text"
