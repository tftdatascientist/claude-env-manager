"""Testy walidatora JSON syntax + JSON Schema hooków."""

import json
import tempfile
from pathlib import Path

import pytest

from src.hooker.core.validator import (
    validate_file, validate_dict, validate_json_syntax, ValidationResult
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_syntax_valid():
    assert validate_json_syntax('{"hooks": {}}') is True


def test_syntax_invalid():
    assert validate_json_syntax('{ INVALID }') is False


def test_syntax_empty_object():
    assert validate_json_syntax('{}') is True


def test_validate_file_global_real():
    result = validate_file(FIXTURES / "global_real.json")
    assert result.is_valid_json
    assert result.ok


def test_validate_file_project_local_sss():
    result = validate_file(FIXTURES / "project_local_sss.json")
    assert result.is_valid_json
    assert result.ok


def test_validate_file_edge_empty():
    result = validate_file(FIXTURES / "edge_empty.json")
    assert result.is_valid_json
    assert result.ok


def test_validate_file_malformed():
    result = validate_file(FIXTURES / "edge_malformed.json")
    assert not result.is_valid_json
    assert not result.ok
    assert result.schema_errors


def test_validate_file_nonexistent():
    result = validate_file(Path("/nonexistent/settings.json"))
    assert not result.is_valid_json
    assert not result.ok


def test_validate_dict_valid_hooks():
    data = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo test"}]}
            ]
        }
    }
    result = validate_dict(data)
    assert result.is_valid_json
    assert not result.has_schema_warnings


def test_validate_dict_no_hooks_section():
    """Plik bez sekcji hooks jest poprawny (inne ustawienia CM)."""
    data = {"permissions": {"allow": []}, "model": "sonnet"}
    result = validate_dict(data)
    assert result.is_valid_json


def test_validate_file_returns_validation_result_type():
    result = validate_file(FIXTURES / "global_real.json")
    assert isinstance(result, ValidationResult)
    assert isinstance(result.schema_errors, list)
    assert isinstance(result.schema_checked, bool)
