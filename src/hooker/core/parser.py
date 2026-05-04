"""Parser settings.json → List[Hook]."""

from __future__ import annotations

import json
from pathlib import Path

from src.hooker.core.model import Hook, HookLevel, HookType


class ParseError(Exception):
    pass


def parse_settings(path: Path, level: HookLevel) -> list[Hook]:
    """Parsuje settings.json i zwraca listę hooków.

    Obsługuje malformed JSON (zwraca []) i brak klucza 'hooks'.
    Format wejścia CC:
      { "hooks": { "PreToolUse": [ { "matcher": "...", "hooks": [ {"type":"command","command":"..."} ] } ] } }
    """
    if not path.exists():
        return []

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    if not isinstance(data, dict):
        return []

    hooks_section = data.get("hooks")
    if not isinstance(hooks_section, dict):
        return []

    result: list[Hook] = []

    for type_str, matchers in hooks_section.items():
        if not isinstance(matchers, list):
            continue

        for matcher_block in matchers:
            if not isinstance(matcher_block, dict):
                continue

            matcher = matcher_block.get("matcher", "")
            inner_hooks = matcher_block.get("hooks", [])

            if not isinstance(inner_hooks, list):
                continue

            for entry in inner_hooks:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command", "")
                if not command:
                    continue

                hook = Hook.from_dict(
                    hook_type=type_str,
                    entry={"command": command, "matcher": matcher},
                    source_file=path,
                    level=level,
                )
                result.append(hook)

    return result


def parse_settings_raw(path: Path) -> dict | None:
    """Zwraca surowy dict z pliku (lub None przy błędzie). Używane przez walidator i persister."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def known_hook_types() -> set[str]:
    return {t.value for t in HookType}
