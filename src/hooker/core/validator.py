"""Walidator hooków CC — JSON syntax + JSON Schema (soft warning)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "hooker" / "schemas" / "hooks_schema.json"
_SCHEMA: dict | None = None


def _load_schema() -> dict | None:
    global _SCHEMA
    if _SCHEMA is not None:
        return _SCHEMA
    if not _SCHEMA_PATH.exists():
        return None
    try:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return _SCHEMA
    except (json.JSONDecodeError, OSError):
        return None


@dataclass
class ValidationResult:
    is_valid_json: bool
    schema_errors: list[str] = field(default_factory=list)
    schema_checked: bool = False

    @property
    def has_schema_warnings(self) -> bool:
        return bool(self.schema_errors)

    @property
    def ok(self) -> bool:
        return self.is_valid_json


def validate_json_syntax(raw: str) -> bool:
    """Sprawdza czy string jest poprawnym JSON."""
    try:
        json.loads(raw)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def validate_file(path: Path) -> ValidationResult:
    """Waliduje plik settings.json — składnia + schema (soft)."""
    if not path.exists():
        return ValidationResult(is_valid_json=False, schema_errors=["Plik nie istnieje"])

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return ValidationResult(is_valid_json=False, schema_errors=[str(e)])

    if not validate_json_syntax(raw):
        return ValidationResult(is_valid_json=False, schema_errors=["Niepoprawna składnia JSON"])

    data = json.loads(raw)
    schema_errors = _validate_schema(data)

    return ValidationResult(
        is_valid_json=True,
        schema_errors=schema_errors,
        schema_checked=_HAS_JSONSCHEMA and _load_schema() is not None,
    )


def validate_dict(data: dict) -> ValidationResult:
    """Waliduje słownik (już zparsowany JSON) — tylko schema."""
    schema_errors = _validate_schema(data)
    return ValidationResult(
        is_valid_json=True,
        schema_errors=schema_errors,
        schema_checked=_HAS_JSONSCHEMA and _load_schema() is not None,
    )


def _validate_schema(data: dict) -> list[str]:
    """Zwraca listę błędów schema (pusta = ok). Soft — nie rzuca wyjątku."""
    if not _HAS_JSONSCHEMA:
        return []

    schema = _load_schema()
    if schema is None:
        return []

    errors: list[str] = []
    try:
        validator = jsonschema.Draft7Validator(schema)
        for err in validator.iter_errors(data):
            path = " → ".join(str(p) for p in err.absolute_path) or "(root)"
            errors.append(f"{path}: {err.message}")
    except Exception as e:
        errors.append(f"Błąd walidatora: {e}")

    return errors
