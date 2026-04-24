"""Konfiguracja slotów CC Launcher — persystencja do launcher_config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".claude" / "cc-panel" / "launcher_config.json"
_USTAWIENIA_PATH = Path.home() / ".claude" / "cc-panel" / "ustawienia.json"

CC_MODELS = [
    "claude-sonnet-4-5",
    "claude-opus-4",
    "claude-haiku-4-5",
]
CC_EFFORTS = ["high", "medium", "low"]

# Tryby uprawnień CC (wartość = flaga CLI lub "")
CC_PERMISSION_MODES: dict[str, str] = {
    "bypass (--dangerously-skip-permissions)": "--dangerously-skip-permissions",
    "standardowy (bez flagi)": "",
}

DEFAULT_VIBE_PROMPT = "Odczytaj CLAUDE.md -> PLAN.md kontynuuj zgodnie z planem"


@dataclass
class SlotConfig:
    """Konfiguracja jednego slotu projektu CC.

    Args:
        project_path: Ścieżka do katalogu projektu.
        model: Identyfikator modelu CC.
        effort: Poziom wysiłku (high/medium/low).
        permission_mode: Klucz trybu uprawnień z CC_PERMISSION_MODES.
        terminal_count: Liczba terminali CC do uruchomienia (1–4).
        vibe_prompt: Prompt startowy wklejany do terminala CC.
    """

    project_path: str = ""
    model: str = "claude-sonnet-4-5"
    effort: str = "high"
    permission_mode: str = "bypass (--dangerously-skip-permissions)"
    terminal_count: int = 1
    vibe_prompt: str = DEFAULT_VIBE_PROMPT


@dataclass
class LauncherConfig:
    """Konfiguracja całego CC Launcher — 4 sloty.

    Args:
        slots: Lista konfiguracji 4 slotów projektów.
    """

    slots: list[SlotConfig] = field(
        default_factory=lambda: [SlotConfig() for _ in range(4)]
    )


def load_launcher_config() -> LauncherConfig:
    """Wczytuje konfigurację z launcher_config.json.

    Przy braku pliku próbuje zainicjować ścieżki z ustawienia.json cc-panel.

    Returns:
        Załadowana lub domyślna konfiguracja.
    """
    if _CONFIG_PATH.exists():
        try:
            raw: Any = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            slots = []
            for slot_raw in raw.get("slots", [])[:4]:
                slots.append(SlotConfig(
                    project_path=slot_raw.get("project_path", ""),
                    model=slot_raw.get("model", "claude-sonnet-4-5"),
                    effort=slot_raw.get("effort", "high"),
                    permission_mode=slot_raw.get(
                        "permission_mode",
                        "bypass (--dangerously-skip-permissions)",
                    ),
                    terminal_count=int(slot_raw.get("terminal_count", 1)),
                    vibe_prompt=slot_raw.get("vibe_prompt", DEFAULT_VIBE_PROMPT),
                ))
            while len(slots) < 4:
                slots.append(SlotConfig())
            return LauncherConfig(slots=slots)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    # Pierwsze uruchomienie — pobierz ścieżki z ustawienia.json cc-panel
    config = LauncherConfig()
    try:
        ustawienia: Any = json.loads(_USTAWIENIA_PATH.read_text(encoding="utf-8"))
        paths: list[str] = ustawienia.get("projectPaths", ["", "", "", ""])
        for i, path in enumerate(paths[:4]):
            config.slots[i].project_path = path or ""
    except (OSError, json.JSONDecodeError):
        pass
    return config


def save_launcher_config(config: LauncherConfig) -> None:
    """Zapisuje konfigurację do launcher_config.json.

    Args:
        config: Konfiguracja do zapisania.
    """
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"slots": [asdict(slot) for slot in config.slots]}
    _CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
