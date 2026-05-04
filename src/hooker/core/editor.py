"""Editor — CRUD na sekcji hooks w settings.json CC."""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path

from src.hooker.core.model import Hook, HookLevel, HookType
from src.hooker.core.parser import parse_settings_raw


def read_settings(path: Path) -> dict:
    """Zwraca dict z settings.json lub {} jeśli plik nie istnieje / malformed."""
    data = parse_settings_raw(path)
    return data if isinstance(data, dict) else {}


def hooks_to_section(hooks: list[Hook]) -> list[dict]:
    """Konwertuje listę Hook do formatu CC (lista matcher_block-ów)."""
    groups: dict[str, list[Hook]] = defaultdict(list)
    for h in hooks:
        groups[h.matcher].append(h)

    result = []
    for matcher, group in groups.items():
        block: dict = {}
        if matcher:
            block["matcher"] = matcher
        block["hooks"] = [{"type": "command", "command": h.command} for h in group]
        result.append(block)
    return result


def apply_hooks(settings: dict, hook_type: HookType, hooks: list[Hook]) -> dict:
    """Zwraca nowy settings dict z zaktualizowaną sekcją hook_type."""
    result = copy.deepcopy(settings)
    if "hooks" not in result:
        result["hooks"] = {}

    section = hooks_to_section(hooks)
    if section:
        result["hooks"][hook_type.value] = section
    else:
        result["hooks"].pop(hook_type.value, None)

    if not result["hooks"]:
        del result["hooks"]

    return result


def load_hooks_for_type(path: Path, hook_type: HookType, level: HookLevel) -> list[Hook]:
    """Ładuje hooki konkretnego typu z pliku."""
    from src.hooker.core.parser import parse_settings
    all_hooks = parse_settings(path, level)
    return [h for h in all_hooks if h.hook_type == hook_type]
