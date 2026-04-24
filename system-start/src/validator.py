"""
Walidator formatów plików MD systemu PCC.
Sprawdza:
  - ARCHITECTURE.md / decisions: każda pozycja ma 3 pola rozdzielone |
  - ARCHITECTURE.md / components: każda linia to "- nazwa: opis"
  - PLAN.md: integralność sekcji (via controller.validate_plan)
"""
from __future__ import annotations

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_block(text: str, header: str) -> list[str]:
    """Zwraca linie z sekcji markdown zaczynającej się od '## Header', bez tagów HTML."""
    lines = text.splitlines()
    result: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == f"## {header}":
            inside = True
            continue
        if inside:
            if line.startswith("## "):
                break
            stripped = line.strip()
            if stripped and not stripped.startswith("<!--"):
                result.append(stripped)
    return result


DECISION_RE = re.compile(r"^-\s+\[.\]\s+.+\|.+\|.+$")
COMPONENT_RE = re.compile(r"^-\s+\S+.*:\s+\S+")


def validate_architecture(path: Path | None = None) -> list[str]:
    if path is None:
        path = BASE_DIR / "ARCHITECTURE.md"
    if not path.exists():
        return [f"Plik nie istnieje: {path}"]

    text = _read(path)
    errors: list[str] = []

    decisions = _extract_block(text, "Decisions")
    for i, line in enumerate(decisions, 1):
        if not DECISION_RE.match(line):
            errors.append(
                f"ARCHITECTURE/Decisions linia {i}: nieprawidłowy format "
                f"(oczekiwano '- [x] opis | data | powód'): {line!r}"
            )

    components = _extract_block(text, "Components")
    for i, line in enumerate(components, 1):
        if not COMPONENT_RE.match(line):
            errors.append(
                f"ARCHITECTURE/Components linia {i}: nieprawidłowy format "
                f"(oczekiwano '- nazwa: opis'): {line!r}"
            )

    return errors


def validate_all(base_dir: Path | None = None) -> dict[str, list[str]]:
    """Waliduje wszystkie pliki MD. Zwraca słownik {plik: [błędy]}."""
    if base_dir is None:
        base_dir = BASE_DIR

    report: dict[str, list[str]] = {}

    arch_errors = validate_architecture(base_dir / "ARCHITECTURE.md")
    if arch_errors:
        report["ARCHITECTURE.md"] = arch_errors

    from src.controller import validate_plan, PLAN_FILE
    import src.controller as ctrl
    original = ctrl.PLAN_FILE
    ctrl.PLAN_FILE = base_dir / "PLAN.md"
    plan_errors = validate_plan()
    ctrl.PLAN_FILE = original
    if plan_errors:
        report["PLAN.md"] = plan_errors

    return report


def print_report(report: dict[str, list[str]]) -> None:
    if not report:
        print("OK: wszystkie pliki MD przeszły walidację.")
        return
    for file, errors in report.items():
        print(f"\n[{file}]")
        for e in errors:
            print(f"  ERR: {e}")


if __name__ == "__main__":
    report = validate_all()
    print_report(report)
    raise SystemExit(0 if not report else 1)
