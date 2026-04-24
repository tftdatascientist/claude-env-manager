"""Odczyt i zapis sekcji PLAN.md z zachowaniem oryginalnego formatowania."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.utils.parsers import read_text

PLAN_SECTIONS = ["Stan", "Cel", "Kroki", "Aktywne zadanie", "Decyzje", "Blokery"]

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


@dataclass
class PlanData:
    """Dane wyekstrahowane z pliku PLAN.md.

    Args:
        raw_text: Pełny tekst pliku.
        sections: Słownik {nazwa_sekcji: treść} dla znanych sekcji.
        is_missing: True jeśli plik nie istnieje lub nie można go odczytać.
        parse_error: Komunikat błędu lub None.
    """

    raw_text: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    is_missing: bool = False
    parse_error: Optional[str] = None


def read_plan(project_path: str | Path) -> PlanData:
    """Wczytuje i parsuje PLAN.md z katalogu projektu.

    Args:
        project_path: Ścieżka do katalogu projektu.

    Returns:
        PlanData z wyekstrahowanymi sekcjami lub is_missing=True.
    """
    path = Path(project_path) / "PLAN.md"
    text = read_text(path)
    if text is None:
        return PlanData(is_missing=True)
    return PlanData(raw_text=text, sections=_parse_sections(text))


def write_plan(project_path: str | Path, data: PlanData) -> bool:
    """Zapisuje zaktualizowany PLAN.md (pełny raw_text).

    Args:
        project_path: Ścieżka do katalogu projektu.
        data: PlanData z zaktualizowanym raw_text.

    Returns:
        True jeśli zapis się powiódł, False przy błędzie.
    """
    path = Path(project_path) / "PLAN.md"
    try:
        path.write_text(data.raw_text, encoding="utf-8")
        return True
    except OSError:
        return False


def get_section(data: PlanData, section_name: str) -> str:
    """Zwraca treść sekcji lub pusty string jeśli nie istnieje.

    Args:
        data: Dane PLAN.md.
        section_name: Nazwa sekcji (np. "Stan", "Cel").

    Returns:
        Treść sekcji (bez nagłówka) lub "".
    """
    return data.sections.get(section_name, "")


def update_section(data: PlanData, section_name: str, new_content: str) -> PlanData:
    """Aktualizuje treść jednej sekcji w raw_text i w sections.

    Jeśli sekcja nie istnieje, dopisuje ją na końcu pliku.

    Args:
        data: Obecne dane PLAN.md.
        section_name: Nazwa sekcji do aktualizacji.
        new_content: Nowa treść sekcji (bez nagłówka).

    Returns:
        Nowy PlanData z zaktualizowaną zawartością.
    """
    text = data.raw_text
    pattern = re.compile(
        r"(^#{2,3}\s+" + re.escape(section_name) + r"\s*$)(.*?)(?=^#{2,3}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    replacement = f"## {section_name}\n{new_content.rstrip()}\n"
    if pattern.search(text):
        new_text = pattern.sub(lambda m: replacement, text, count=1)
    else:
        new_text = text.rstrip() + f"\n\n## {section_name}\n{new_content.rstrip()}\n"

    new_sections = dict(data.sections)
    new_sections[section_name] = new_content.strip()
    return PlanData(raw_text=new_text, sections=new_sections)


def _parse_sections(text: str) -> dict[str, str]:
    """Parsuje sekcje H2/H3 z tekstu Markdown.

    Args:
        text: Pełny tekst PLAN.md.

    Returns:
        Słownik {nazwa_sekcji: treść_bez_nagłówka}.
    """
    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections
