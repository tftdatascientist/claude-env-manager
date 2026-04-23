"""
Wbudowane profile i scenariusze — dostepne od razu po instalacji.

5 profili reprezentujacych rozne konfiguracje srodowiska CC.
10 scenariuszy reprezentujacych typowe zadania wykonywane przez CC.
"""
from __future__ import annotations

import copy
import uuid

from .models import Activity, ModelTier, Profile, Scene, Scenario
from .preset_scenes import PRESET_SCENES, PRESET_BY_KEY


# ---------------------------------------------------------------------------
# 5 gotowych profili
# ---------------------------------------------------------------------------

PRESET_PROFILES: list[Profile] = [

    Profile(
        id="profile_bare",
        name="Bare minimum",
        color="#808080",
        model=ModelTier.HAIKU_4,
        system_prompt_tokens=6600,
        system_tools_tokens=8400,
        skills_tokens=0,
        mcp_tokens=0,
        plugins_tokens=0,
        memory_tokens=0,
        global_claude_md_lines=0,
        project_claude_md_lines=0,
        line_token_ratio=10.0,
        cache_hit_rate=0.50,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    ),

    Profile(
        id="profile_light",
        name="Light setup",
        color="#98c379",
        model=ModelTier.SONNET_4,
        system_prompt_tokens=6600,
        system_tools_tokens=8400,
        skills_tokens=0,
        mcp_tokens=0,
        plugins_tokens=0,
        memory_tokens=3500,
        global_claude_md_lines=40,
        project_claude_md_lines=30,
        line_token_ratio=10.0,
        cache_hit_rate=0.65,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    ),

    Profile(
        id="profile_standard",
        name="Standard",
        color="#569cd6",
        model=ModelTier.SONNET_4,
        system_prompt_tokens=6600,
        system_tools_tokens=8400,
        skills_tokens=785,
        mcp_tokens=1200,
        plugins_tokens=0,
        memory_tokens=6800,
        global_claude_md_lines=73,
        project_claude_md_lines=45,
        line_token_ratio=10.0,
        cache_hit_rate=0.70,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    ),

    Profile(
        id="profile_power",
        name="Power setup",
        color="#ce9178",
        model=ModelTier.OPUS_4,
        system_prompt_tokens=6600,
        system_tools_tokens=8400,
        skills_tokens=3200,
        mcp_tokens=4800,
        plugins_tokens=1500,
        memory_tokens=12000,
        global_claude_md_lines=120,
        project_claude_md_lines=80,
        line_token_ratio=10.0,
        cache_hit_rate=0.75,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    ),

    Profile(
        id="profile_heavy",
        name="Heavy Opus",
        color="#f44747",
        model=ModelTier.OPUS_4,
        system_prompt_tokens=6600,
        system_tools_tokens=8400,
        skills_tokens=6000,
        mcp_tokens=8000,
        plugins_tokens=3000,
        memory_tokens=20000,
        global_claude_md_lines=200,
        project_claude_md_lines=150,
        line_token_ratio=10.0,
        cache_hit_rate=0.80,
        ctx_limit=200_000,
        autocompact_threshold=0.85,
    ),
]

PRESET_PROFILES_BY_ID: dict[str, Profile] = {p.id: p for p in PRESET_PROFILES}


# ---------------------------------------------------------------------------
# Pomocnik: tworzy Scene z presetu ze swiezym ID
# ---------------------------------------------------------------------------

def _ps(key: str, name_override: str | None = None) -> Scene:
    preset = PRESET_BY_KEY[key]
    s = copy.deepcopy(preset.scene_template)
    s.id = str(uuid.uuid4())[:8]
    if name_override:
        s.name = name_override
    return s


def _custom(
    name: str,
    user: int,
    resp: int,
    acts: list[tuple[str, int]],
) -> Scene:
    return Scene(
        id=str(uuid.uuid4())[:8],
        name=name,
        user_message_tokens=user,
        assistant_response_tokens=resp,
        activities=[Activity(activity_id=aid, count=cnt) for aid, cnt in acts],
    )


# ---------------------------------------------------------------------------
# 10 gotowych scenariuszy
# ---------------------------------------------------------------------------

def _make_scenarios() -> list[Scenario]:
    """Tworzy scenariusze ze swiezymi ID scen (kazde wywolanie = nowe UUID)."""

    scenarios = [

        # 1 ----------------------------------------------------------------
        Scenario(
            id="scenario_01",
            name="1. Typowy dzien pracy",
            scenes=[
                _ps("session_start"),
                _ps("explore_codebase"),
                _ps("read_and_plan"),
                _ps("small_edit"),
                _ps("small_edit", "Mala edycja #2"),
                _ps("feature_implementation"),
                _ps("debug_session"),
                _custom("Commit i push", 100, 300,
                        [("git_status", 1), ("bash_cmd", 2)]),
            ],
        ),

        # 2 ----------------------------------------------------------------
        Scenario(
            id="scenario_02",
            name="2. Bugfix od zera",
            scenes=[
                _ps("session_start"),
                _custom("Reprodukcja bledu", 300, 500,
                        [("bash_long", 1), ("git_status", 1)]),
                _ps("explore_codebase"),
                _custom("Izolacja przyczyny", 400, 800,
                        [("file_read", 4), ("grep_glob", 2), ("bash_cmd", 1)]),
                _ps("small_edit", "Fix"),
                _custom("Testy po fFixie", 200, 600,
                        [("lint_run", 1), ("bash_cmd", 2)]),
                _custom("PR description", 300, 900,
                        [("git_status", 1), ("bash_cmd", 1)]),
            ],
        ),

        # 3 ----------------------------------------------------------------
        Scenario(
            id="scenario_03",
            name="3. Nowy feature end-to-end",
            scenes=[
                _ps("session_start"),
                _ps("read_and_plan", "Analiza wymagan"),
                _ps("explore_codebase", "Eksploracja struktury"),
                _custom("Szkielet modulu", 300, 1000,
                        [("file_write", 2), ("file_read", 2)]),
                _ps("feature_implementation", "Implementacja logiki"),
                _custom("Testy jednostkowe", 400, 1200,
                        [("file_write", 1), ("file_read", 3), ("lint_run", 1)]),
                _custom("Integracja z UI", 400, 900,
                        [("file_read", 3), ("file_edit", 3), ("file_write", 1)]),
                _ps("debug_session", "Debug edge cases"),
                _custom("Dokumentacja", 200, 800,
                        [("file_read", 2), ("file_edit", 2)]),
                _custom("Final review + commit", 200, 400,
                        [("git_status", 1), ("bash_cmd", 2), ("lint_run", 1)]),
            ],
        ),

        # 4 ----------------------------------------------------------------
        Scenario(
            id="scenario_04",
            name="4. Research i raport",
            scenes=[
                _ps("session_start"),
                _ps("mcp_research", "Research temat #1"),
                _ps("mcp_research", "Research temat #2"),
                _ps("web_heavy", "Pobranie dokumentacji"),
                _custom("Synteza wynikow", 500, 2000,
                        [("file_read", 2), ("memory_write", 1)]),
                _custom("Pisanie raportu", 300, 1500,
                        [("file_write", 1), ("file_edit", 2)]),
                _custom("Eksport do Notion", 200, 400,
                        [("mcp_call", 2)]),
            ],
        ),

        # 5 ----------------------------------------------------------------
        Scenario(
            id="scenario_05",
            name="5. Refaktor duzego modulu",
            scenes=[
                _ps("session_start"),
                _custom("Audit kodu", 300, 1200,
                        [("file_read", 6), ("grep_glob", 3)]),
                _ps("read_and_plan", "Plan refaktoru"),
                _custom("Rename + move", 300, 600,
                        [("file_read", 4), ("file_edit", 4)]),
                _custom("Przepisanie logiki A", 400, 1000,
                        [("file_read", 3), ("file_edit", 3), ("file_write", 1)]),
                _custom("Przepisanie logiki B", 400, 1000,
                        [("file_read", 3), ("file_edit", 3)]),
                _custom("Aktualizacja testow", 400, 1000,
                        [("file_read", 4), ("file_edit", 4), ("lint_run", 1)]),
                _ps("debug_session", "Debug po refaktorze"),
                _custom("Cleanup imports", 200, 400,
                        [("grep_glob", 2), ("file_edit", 3)]),
            ],
        ),

        # 6 ----------------------------------------------------------------
        Scenario(
            id="scenario_06",
            name="6. Praca z MCP i AI tools",
            scenes=[
                _ps("session_start"),
                _ps("skill_heavy", "Skill: commit"),
                _ps("mcp_research"),
                _ps("subagent_task", "Subagent: generowanie"),
                _ps("mcp_research", "MCP: zapis wyniku"),
                _custom("Weryfikacja output", 300, 700,
                        [("file_read", 3), ("bash_cmd", 1)]),
                _ps("skill_heavy", "Skill: review-pr"),
            ],
        ),

        # 7 ----------------------------------------------------------------
        Scenario(
            id="scenario_07",
            name="7. Szybkie sesje (micro-tasks)",
            scenes=[
                _custom("Pytanie o API", 150, 400,
                        [("web_search", 1)]),
                _ps("small_edit", "Poprawka literowki"),
                _custom("Snippet generation", 200, 600,
                        [("file_read", 1), ("file_edit", 1)]),
                _custom("Explain code", 300, 800,
                        [("file_read", 2)]),
                _custom("Rename variable", 150, 300,
                        [("grep_glob", 1), ("file_edit", 2)]),
            ],
        ),

        # 8 ----------------------------------------------------------------
        Scenario(
            id="scenario_08",
            name="8. Dlugie sesje z autocompact",
            scenes=[
                _ps("session_start"),
                _ps("explore_codebase"),
                _ps("read_and_plan"),
                _ps("feature_implementation"),
                _ps("debug_session"),
                _custom("Kolejny feature", 400, 1200,
                        [("file_read", 4), ("file_write", 2), ("file_edit", 3)]),
                _ps("subagent_task"),
                _ps("mcp_research"),
                _ps("feature_implementation", "Feature #3"),
                _custom("Zamkniecie sesji", 200, 500,
                        [("git_status", 1), ("todo_write", 1), ("memory_write", 1)]),
            ],
        ),

        # 9 ----------------------------------------------------------------
        Scenario(
            id="scenario_09",
            name="9. Code review + poprawki",
            scenes=[
                _ps("session_start"),
                _custom("Checkout PR branch", 150, 300,
                        [("bash_cmd", 2), ("git_status", 1)]),
                _custom("Review plikow", 400, 1500,
                        [("file_read", 6), ("grep_glob", 2)]),
                _custom("Komentarze review", 300, 1200,
                        [("file_read", 3)]),
                _ps("small_edit", "Poprawka #1"),
                _ps("small_edit", "Poprawka #2"),
                _ps("small_edit", "Poprawka #3"),
                _custom("Testy po poprawkach", 200, 600,
                        [("lint_run", 1), ("bash_cmd", 2)]),
                _custom("Approve i merge", 150, 300,
                        [("bash_cmd", 2), ("git_status", 1)]),
            ],
        ),

        # 10 ---------------------------------------------------------------
        Scenario(
            id="scenario_10",
            name="10. Setup nowego projektu",
            scenes=[
                _custom("Inicjalizacja repo", 200, 600,
                        [("bash_cmd", 4), ("file_write", 2)]),
                _ps("read_and_plan", "Architektura projektu"),
                _custom("Scaffold struktury", 300, 800,
                        [("file_write", 5), ("bash_cmd", 2)]),
                _custom("Konfiguracja CI/CD", 300, 700,
                        [("file_write", 3), ("file_read", 2)]),
                _custom("CLAUDE.md + README", 300, 900,
                        [("file_write", 2), ("file_read", 1)]),
                _custom("Zaleznosci i venv", 200, 500,
                        [("bash_cmd", 3), ("file_write", 1)]),
                _custom("Pierwszy feature stub", 400, 1000,
                        [("file_write", 3), ("file_edit", 2)]),
                _custom("Testy bazowe", 300, 800,
                        [("file_write", 2), ("lint_run", 1)]),
            ],
        ),
    ]

    return scenarios


PRESET_SCENARIOS: list[Scenario] = _make_scenarios()
