"""parser.py — shared regex lib dla markerów <!-- SECTION:name -->.

Dwa typy operacji:
  read_section(text, name)     -> str    (treść między markerami)
  write_section(text, name, content) -> str    (zwraca nowy tekst pliku)
  list_sections(text)          -> list   (nazwy wszystkich sekcji w pliku)
  append_to_section(text, name, line) -> str  (dopisuje linię na końcu sekcji)
"""
from __future__ import annotations
import re
from pathlib import Path

# Marker para: <!-- SECTION:name --> ... <!-- /SECTION:name -->
# Group 1: nazwa, Group 2: treść (bez wiodących/kończących whitespace newlines)
SECTION_RE = re.compile(
    r'<!-- SECTION:(\w+) -->\n?(.*?)\n?<!-- /SECTION:\1 -->',
    re.DOTALL,
)


def read_section(text: str, name: str) -> str:
    """Zwraca treść sekcji. Pusty string jeśli sekcji nie ma lub jest pusta."""
    pattern = re.compile(
        rf'<!-- SECTION:{re.escape(name)} -->\n?(.*?)\n?<!-- /SECTION:{re.escape(name)} -->',
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ''


def write_section(text: str, name: str, content: str) -> str:
    """Zastępuje treść sekcji. Jeśli sekcji nie ma — rzuca ValueError."""
    pattern = re.compile(
        rf'(<!-- SECTION:{re.escape(name)} -->)\n?(.*?)\n?(<!-- /SECTION:{re.escape(name)} -->)',
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f'Sekcja "{name}" nie istnieje w pliku')
    content = (content or '').strip()
    if content:
        replacement = rf'\1\n{content}\n\3'
    else:
        replacement = r'\1\n\3'
    # re.sub z lambda żeby uniknąć problemów z backreferences w content
    def repl(m):
        return f'{m.group(1)}\n{content}\n{m.group(3)}' if content else f'{m.group(1)}\n{m.group(3)}'
    return pattern.sub(repl, text, count=1)


def append_to_section(text: str, name: str, line: str) -> str:
    """Dopisuje linię na końcu istniejącej treści sekcji."""
    current = read_section(text, name)
    line = line.rstrip('\n')
    new_content = f'{current}\n{line}' if current else line
    return write_section(text, name, new_content)


def list_sections(text: str) -> list[str]:
    """Zwraca listę nazw wszystkich sekcji w pliku."""
    return [m.group(1) for m in SECTION_RE.finditer(text)]


def read_file(path: str | Path) -> str:
    return Path(path).read_text(encoding='utf-8')


def write_file(path: str | Path, text: str) -> None:
    Path(path).write_text(text, encoding='utf-8')


# === Helpery dla typowych operacji DPS ===

def list_checkbox_items(section_content: str, checked: bool | None = None) -> list[str]:
    """Wyciąga elementy listy checkbox z sekcji.

    checked=True   -> tylko ukończone "- [x]"
    checked=False  -> tylko nieukończone "- [ ]"
    checked=None   -> wszystkie
    """
    items = []
    for raw in section_content.splitlines():
        line = raw.strip()
        if not line.startswith('- ['):
            continue
        is_done = line.startswith('- [x]') or line.startswith('- [X]')
        if checked is True and not is_done:
            continue
        if checked is False and is_done:
            continue
        items.append(line)
    return items


def remove_lines_from_section(text: str, name: str, lines_to_remove: list[str]) -> str:
    """Usuwa konkretne linie z sekcji (porównanie po strip)."""
    current = read_section(text, name)
    targets = {l.strip() for l in lines_to_remove}
    kept = [raw for raw in current.splitlines() if raw.strip() not in targets]
    return write_section(text, name, '\n'.join(kept))
