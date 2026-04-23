from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class ModelTier(str, Enum):
    OPUS_4   = "claude-opus-4"
    SONNET_4 = "claude-sonnet-4"
    HAIKU_4  = "claude-haiku-4"


PRICING: dict[ModelTier, dict[str, float]] = {
    ModelTier.OPUS_4:   {"input": 15.0,  "output": 75.0,  "cache_read": 1.5,  "cache_creation": 18.75},
    ModelTier.SONNET_4: {"input": 3.0,   "output": 15.0,  "cache_read": 0.30, "cache_creation": 3.75},
    ModelTier.HAIKU_4:  {"input": 0.80,  "output": 4.0,   "cache_read": 0.08, "cache_creation": 1.0},
}


@dataclass
class ActivityDef:
    """Definicja jednego typu aktywnosci CC z domyslnymi kosztami tokenow."""
    id: str
    label: str
    input_tokens: int
    output_tokens: int
    description: str
    calibrated: bool = False


ACTIVITY_REGISTRY: dict[str, ActivityDef] = {
    "file_read":       ActivityDef("file_read",       "Read file",         800,  50,   "Odczyt pliku ~200 linii"),
    "file_read_large": ActivityDef("file_read_large", "Read file (large)", 2400, 50,   "Odczyt pliku ~600 linii"),
    "file_edit":       ActivityDef("file_edit",       "Edit file",         300,  100,  "Edycja istniejacego pliku"),
    "file_write":      ActivityDef("file_write",      "Write file",        200,  500,  "Zapis nowego pliku"),
    "file_multi_read": ActivityDef("file_multi_read", "Multi-file read",   1600, 50,   "Odczyt 2+ plikow naraz"),
    "bash_cmd":        ActivityDef("bash_cmd",        "Bash command",      150,  300,  "Komenda shell"),
    "bash_long":       ActivityDef("bash_long",       "Bash (long out)",   150,  1200, "Komenda z dlugim outputem"),
    "grep_glob":       ActivityDef("grep_glob",       "Grep/Glob",         100,  200,  "Szukanie po plikach"),
    "skill_invoke":    ActivityDef("skill_invoke",    "Skill invocation",  1500, 300,  "Zaladowanie i uzycie skilla"),
    "mcp_call":        ActivityDef("mcp_call",        "MCP tool call",     400,  600,  "Wywolanie narzedzia MCP"),
    "web_search":      ActivityDef("web_search",      "Web search",        200,  1500, "Wyszukiwanie w sieci"),
    "web_fetch":       ActivityDef("web_fetch",       "Web fetch",         200,  3000, "Pobranie strony"),
    "subagent_launch": ActivityDef("subagent_launch", "Sub-agent",         500,  2000, "Uruchomienie subagenta"),
    "todo_read":       ActivityDef("todo_read",       "TodoRead",          50,   50,   "Odczyt listy todo"),
    "todo_write":      ActivityDef("todo_write",      "TodoWrite",         50,   100,  "Zapis listy todo"),
    "memory_read":     ActivityDef("memory_read",     "Memory read",       300,  50,   "Odczyt pliku pamieci"),
    "memory_write":    ActivityDef("memory_write",    "Memory write",      100,  50,   "Zapis do pamieci"),
    "context_view":    ActivityDef("context_view",    "/context",          50,   400,  "Podglad okna kontekstu"),
    "git_status":      ActivityDef("git_status",      "Git status",        200,  50,   "Odswiezenie git status"),
    "lint_run":        ActivityDef("lint_run",        "Linter/tests",      150,  800,  "Wynik lintowania/testow"),
}


@dataclass
class Activity:
    """Instancja aktywnosci w scenie."""
    activity_id: str
    count: int = 1

    @property
    def definition(self) -> ActivityDef:
        return ACTIVITY_REGISTRY[self.activity_id]

    @property
    def total_input(self) -> int:
        return self.definition.input_tokens * self.count

    @property
    def total_output(self) -> int:
        return self.definition.output_tokens * self.count


@dataclass
class Profile:
    """Profil konfiguracji srodowiska CC."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Nowy profil"
    color: str = "#569cd6"
    model: ModelTier = ModelTier.OPUS_4

    system_prompt_tokens: int = 6600
    system_tools_tokens: int = 8400
    skills_tokens: int = 785       # TODO: docelowo per-skill breakdown
    mcp_tokens: int = 0            # TODO: docelowo per-server breakdown
    plugins_tokens: int = 0        # TODO: docelowo per-plugin breakdown
    memory_tokens: int = 6800

    global_claude_md_lines: int = 50
    project_claude_md_lines: int = 0
    line_token_ratio: float = 10.0

    cache_hit_rate: float = 0.70
    ctx_limit: int = 200_000
    autocompact_threshold: float = 0.90

    @property
    def claude_md_tokens(self) -> int:
        return int(
            (self.global_claude_md_lines + self.project_claude_md_lines)
            * self.line_token_ratio
        )

    @property
    def static_overhead(self) -> int:
        """Tokeny dodawane do kazdej wiadomosci jako overhead konfiguracji."""
        return (
            self.system_prompt_tokens
            + self.system_tools_tokens
            + self.skills_tokens
            + self.mcp_tokens
            + self.plugins_tokens
            + self.memory_tokens
            + self.claude_md_tokens
        )

    @property
    def autocompact_token_threshold(self) -> int:
        return int(self.ctx_limit * self.autocompact_threshold)


@dataclass
class Scene:
    """Jeden krok scenariusza — para wiadomosc/odpowiedz + aktywnosci CC."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Scena"
    user_message_tokens: int = 200
    assistant_response_tokens: int = 800
    activities: list[Activity] = field(default_factory=list)

    @property
    def tool_input_tokens(self) -> int:
        return sum(a.total_input for a in self.activities)

    @property
    def tool_output_tokens(self) -> int:
        return sum(a.total_output for a in self.activities)


@dataclass
class Scenario:
    """Nazwana sekwencja scen."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Nowy scenariusz"
    scenes: list[Scene] = field(default_factory=list)


@dataclass
class SceneResult:
    """Wynik symulacji jednej sceny dla jednego profilu."""
    scene: Scene
    scene_number: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    total_ctx_tokens: int
    history_tokens: int
    cost_usd: float
    cumulative_cost_usd: float
    autocompact_fired: bool
    ctx_pct: float


@dataclass
class SimResult:
    """Kompletny wynik symulacji jednego profilu dla scenariusza."""
    profile: Profile
    scenario: Scenario
    scene_results: list[SceneResult]
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    autocompact_count: int


@dataclass
class DualSimResult:
    """Wynik porownania dwoch profili."""
    result_a: SimResult
    result_b: SimResult

    @property
    def winner(self) -> str:
        if self.result_a.total_cost_usd <= self.result_b.total_cost_usd:
            return self.result_a.profile.name
        return self.result_b.profile.name

    @property
    def savings_usd(self) -> float:
        return abs(self.result_a.total_cost_usd - self.result_b.total_cost_usd)

    @property
    def savings_pct(self) -> float:
        bigger = max(self.result_a.total_cost_usd, self.result_b.total_cost_usd)
        return (self.savings_usd / bigger * 100) if bigger > 0 else 0.0
