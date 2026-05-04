"""Model danych hooka Claude Code."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class HookType(str, Enum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    NOTIFICATION = "Notification"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"


class HookLevel(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"


# Opisy typów hooków wyświetlane w UI Hook Setup (podpowiedzi).
HOOK_TYPE_INFO: dict[HookType, dict[str, str]] = {
    HookType.PRE_TOOL_USE: {
        "label": "PreToolUse",
        "color": "#3b82f6",
        "when": "Przed każdym wywołaniem narzędzia przez CC",
        "input": "tool_name, tool_input (JSON)",
        "output": "Możesz zwrócić exit code 1 + komunikat żeby zablokować wywołanie narzędzia",
        "example": "Blokowanie niebezpiecznych komend bash, logowanie wywołań",
    },
    HookType.POST_TOOL_USE: {
        "label": "PostToolUse",
        "color": "#10b981",
        "when": "Po każdym wywołaniu narzędzia przez CC (niezależnie od wyniku)",
        "input": "tool_name, tool_input, tool_response (JSON)",
        "output": "Brak — hook informacyjny, exit code ignorowany",
        "example": "Logowanie wyników, powiadomienia po zakończeniu operacji",
    },
    HookType.USER_PROMPT_SUBMIT: {
        "label": "UserPromptSubmit",
        "color": "#8b5cf6",
        "when": "Gdy user wysyła wiadomość do CC, przed jej przetworzeniem",
        "input": "prompt (tekst wiadomości użytkownika)",
        "output": "Możesz modyfikować prompt lub blokować (exit code 2 + JSON z nowym promptem)",
        "example": "Wstrzykiwanie kontekstu, sprawdzanie długości promptu",
    },
    HookType.NOTIFICATION: {
        "label": "Notification",
        "color": "#f59e0b",
        "when": "Gdy CC emituje powiadomienie (np. wymaga uwagi użytkownika)",
        "input": "message (tekst powiadomienia)",
        "output": "Brak — hook informacyjny",
        "example": "Dźwięki, desktop notifications, Slack",
    },
    HookType.STOP: {
        "label": "Stop",
        "color": "#ef4444",
        "when": "Gdy główny agent CC kończy pracę (normalnie lub po błędzie)",
        "input": "stop_reason, session_id",
        "output": "Brak — hook informacyjny",
        "example": "Dźwięk zakończenia sesji, zapis raportu, powiadomienie",
    },
    HookType.SUBAGENT_STOP: {
        "label": "SubagentStop",
        "color": "#f97316",
        "when": "Gdy sub-agent CC kończy pracę",
        "input": "stop_reason, session_id, subagent_id",
        "output": "Brak — hook informacyjny",
        "example": "Monitorowanie wielu równoległych agentów (np. 4 terminale)",
    },
    HookType.PRE_COMPACT: {
        "label": "PreCompact",
        "color": "#06b6d4",
        "when": "Przed kompaktowaniem kontekstu (gdy zbliża się limit tokenów)",
        "input": "context_stats (tokeny, % zapełnienia)",
        "output": "Brak — hook informacyjny",
        "example": "Logowanie, zapis bufora, ostrzeżenie",
    },
    HookType.SESSION_START: {
        "label": "SessionStart",
        "color": "#84cc16",
        "when": "Na początku nowej sesji CC",
        "input": "session_id, project_path",
        "output": "Brak — hook informacyjny",
        "example": "Inicjalizacja logów, powiadomienie o starcie, wczytanie kontekstu",
    },
    HookType.SESSION_END: {
        "label": "SessionEnd",
        "color": "#ec4899",
        "when": "Na końcu sesji CC (normalne zamknięcie)",
        "input": "session_id, duration_ms",
        "output": "Brak — hook informacyjny",
        "example": "Finalizacja logów, raport sesji, archiwizacja",
    },
}


@dataclass
class Hook:
    """Pojedynczy hook Claude Code."""

    hook_type: HookType
    command: str
    matcher: str = ""
    source_file: Path = field(default_factory=Path)
    level: HookLevel = HookLevel.GLOBAL

    @property
    def info(self) -> dict[str, str]:
        return HOOK_TYPE_INFO.get(self.hook_type, {})

    @classmethod
    def from_dict(
        cls,
        hook_type: str,
        entry: dict,
        source_file: Path,
        level: HookLevel,
    ) -> "Hook":
        """Tworzy Hook z surowego wpisu JSON settings.json."""
        try:
            ht = HookType(hook_type)
        except ValueError:
            ht = HookType.PRE_TOOL_USE  # fallback przy nieznanym typie

        return cls(
            hook_type=ht,
            command=entry.get("command", ""),
            matcher=entry.get("matcher", ""),
            source_file=source_file,
            level=level,
        )

    def to_dict(self) -> dict:
        """Serializacja do formatu settings.json."""
        d: dict = {"command": self.command}
        if self.matcher:
            d["matcher"] = self.matcher
        return d
