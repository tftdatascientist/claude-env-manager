"""
Gotowe sceny do ukladania scenariuszy.

10 presetow reprezentujacych typowe etapy pracy z Claude Code.
Sa wbudowane w aplikacje — zawsze dostepne niezaleznie od simulator_data.json.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from .models import Activity, Scene


@dataclass
class PresetScene:
    """Gotowa scena z opisem — szablon do wstawiania do scenariusza."""
    key: str
    label: str
    description: str
    scene_template: Scene

    def instantiate(self) -> Scene:
        """Zwraca nowy egzemplarz sceny z unikalnym ID."""
        s = copy.deepcopy(self.scene_template)
        import uuid
        s.id = str(uuid.uuid4())[:8]
        return s


# ---------------------------------------------------------------------------
# 10 presetow
# ---------------------------------------------------------------------------

PRESET_SCENES: list[PresetScene] = [

    PresetScene(
        key="session_start",
        label="1. Start sesji",
        description=(
            "Pierwsze wiadomosci po otwarciu CC: odczyt todo, git status, "
            "przegladanie CLAUDE.md. Typowy overhead na poczatku kazdej sesji."
        ),
        scene_template=Scene(
            id="preset_01",
            name="Start sesji",
            user_message_tokens=150,
            assistant_response_tokens=400,
            activities=[
                Activity("todo_read",  count=1),
                Activity("git_status", count=1),
                Activity("memory_read", count=1),
            ],
        ),
    ),

    PresetScene(
        key="explore_codebase",
        label="2. Eksploracja kodu",
        description=(
            "Faza orientacji: grep po strukturze, odczyt kilku plikow, "
            "glob zeby znalezc wlasciwe pliki. Duzo read, malo write."
        ),
        scene_template=Scene(
            id="preset_02",
            name="Eksploracja kodu",
            user_message_tokens=200,
            assistant_response_tokens=600,
            activities=[
                Activity("grep_glob",       count=3),
                Activity("file_read",       count=4),
                Activity("bash_cmd",        count=1),
            ],
        ),
    ),

    PresetScene(
        key="read_and_plan",
        label="3. Analiza + plan",
        description=(
            "CC czyta wiele plikow naraz i odpowiada szczegolowym planem. "
            "Duza odpowiedz (architektura, lista krokow)."
        ),
        scene_template=Scene(
            id="preset_03",
            name="Analiza i plan",
            user_message_tokens=300,
            assistant_response_tokens=1500,
            activities=[
                Activity("file_multi_read", count=2),
                Activity("file_read",       count=2),
            ],
        ),
    ),

    PresetScene(
        key="small_edit",
        label="4. Mala edycja",
        description=(
            "Szybka, chirurgiczna zmiana: jedno read + edit jednego pliku. "
            "Typowe bugfixy i drobne poprawki."
        ),
        scene_template=Scene(
            id="preset_04",
            name="Mala edycja",
            user_message_tokens=200,
            assistant_response_tokens=500,
            activities=[
                Activity("file_read", count=1),
                Activity("file_edit", count=1),
            ],
        ),
    ),

    PresetScene(
        key="feature_implementation",
        label="5. Implementacja feature",
        description=(
            "Sredni feature: czyta kontekst, pisze nowy plik, edytuje istniejace, "
            "uruchamia testy/linter."
        ),
        scene_template=Scene(
            id="preset_05",
            name="Implementacja feature",
            user_message_tokens=400,
            assistant_response_tokens=1200,
            activities=[
                Activity("file_read",  count=3),
                Activity("file_write", count=1),
                Activity("file_edit",  count=2),
                Activity("lint_run",   count=1),
            ],
        ),
    ),

    PresetScene(
        key="mcp_research",
        label="6. Research przez MCP",
        description=(
            "CC uzywa narzedzi MCP do pobrania danych zewnetrznych "
            "(np. Notion, web search), przetwarza wyniki."
        ),
        scene_template=Scene(
            id="preset_06",
            name="Research przez MCP",
            user_message_tokens=200,
            assistant_response_tokens=800,
            activities=[
                Activity("mcp_call",   count=3),
                Activity("web_search", count=1),
            ],
        ),
    ),

    PresetScene(
        key="skill_heavy",
        label="7. Praca ze skillem",
        description=(
            "CC laduje skilla (np. /commit, /review-pr) + przetwarza rezultaty. "
            "Skill invocation to duzy koszt jednorazowy."
        ),
        scene_template=Scene(
            id="preset_07",
            name="Skill invocation",
            user_message_tokens=100,
            assistant_response_tokens=600,
            activities=[
                Activity("skill_invoke", count=1),
                Activity("file_read",    count=2),
                Activity("git_status",   count=1),
            ],
        ),
    ),

    PresetScene(
        key="debug_session",
        label="8. Debugowanie",
        description=(
            "Iteracyjne debugowanie: komendy bash z dlugim outputem, "
            "odczyt logow, poprawki kodu. Charakterystyczne dla sesji naprawiania bledow."
        ),
        scene_template=Scene(
            id="preset_08",
            name="Debugowanie",
            user_message_tokens=300,
            assistant_response_tokens=700,
            activities=[
                Activity("bash_long",  count=2),
                Activity("file_read",  count=2),
                Activity("file_edit",  count=1),
                Activity("lint_run",   count=1),
            ],
        ),
    ),

    PresetScene(
        key="subagent_task",
        label="9. Delegacja do subagenta",
        description=(
            "CC uruchamia subagenta do zrownoleglenia pracy. "
            "Bardzo wysoki koszt tokenow — jeden subagent = duzo toksenow."
        ),
        scene_template=Scene(
            id="preset_09",
            name="Subagent",
            user_message_tokens=300,
            assistant_response_tokens=500,
            activities=[
                Activity("subagent_launch", count=2),
                Activity("todo_write",      count=1),
            ],
        ),
    ),

    PresetScene(
        key="web_heavy",
        label="10. Web fetch + analiza",
        description=(
            "CC pobiera pelne strony (web_fetch) — najdrozsze narzedzie output-wise. "
            "Typowe przy researchu dokumentacji lub scrapingu."
        ),
        scene_template=Scene(
            id="preset_10",
            name="Web fetch + analiza",
            user_message_tokens=200,
            assistant_response_tokens=1000,
            activities=[
                Activity("web_fetch",  count=2),
                Activity("web_search", count=1),
                Activity("file_write", count=1),
            ],
        ),
    ),
]

# Szybki dostep po kluczu
PRESET_BY_KEY: dict[str, PresetScene] = {p.key: p for p in PRESET_SCENES}
