# Token Simulator v2 — Architektura techniczna

## Struktura modulow

```
src/
  simulator/
    models.py       # dataclassy: Profile, Scene, Activity, Scenario, SimResult, SceneResult
    engine.py       # logika symulacji, obliczenia kosztow
    calibrator.py   # porownanie sim vs real, MAE
    storage.py      # ladowanie / zapis simulator_data.json

  ui/simulator/
    simulator_panel.py   # glowny QWidget panelu, layout, orkiestracja
    profile_editor.py    # dialog edycji profilu (QDialog)
    scene_builder.py     # widget budowania sceny (przyciski aktywnosci)
    results_view.py      # tabela wynikow (QTableWidget)
    context_widget.py    # widget /context (canvas lub QLabel z monospace)
    status_bar.py        # status bar w stylu CC
```

---

## Klasy danych (models.py)

```python
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
    ModelTier.OPUS_4:   {"input": 15.0, "output": 75.0, "cache_read": 1.5,  "cache_creation": 18.75},
    ModelTier.SONNET_4: {"input": 3.0,  "output": 15.0, "cache_read": 0.30, "cache_creation": 3.75},
    ModelTier.HAIKU_4:  {"input": 0.80, "output": 4.0,  "cache_read": 0.08, "cache_creation": 1.0},
}


@dataclass
class ActivityDef:
    """Definicja jednego typu aktywnosci CC z domyslnymi kosztami tokenow."""
    id: str
    label: str
    input_tokens: int
    output_tokens: int
    description: str
    # flaga: wartosci sa skalibrowane (True) lub domyslne szacunki (False)
    calibrated: bool = False


# Rejestr wszystkich aktywnosci — zrodlo prawdy
ACTIVITY_REGISTRY: dict[str, ActivityDef] = {
    "file_read":        ActivityDef("file_read",        "Read file",         800,  50,   "Odczyt pliku ~200 linii"),
    "file_read_large":  ActivityDef("file_read_large",  "Read file (large)", 2400, 50,   "Odczyt pliku ~600 linii"),
    "file_edit":        ActivityDef("file_edit",        "Edit file",         300,  100,  "Edycja istniejacego pliku"),
    "file_write":       ActivityDef("file_write",       "Write file",        200,  500,  "Zapis nowego pliku"),
    "file_multi_read":  ActivityDef("file_multi_read",  "Multi-file read",   1600, 50,   "Odczyt 2+ plikow naraz"),
    "bash_cmd":         ActivityDef("bash_cmd",         "Bash command",      150,  300,  "Komenda shell"),
    "bash_long":        ActivityDef("bash_long",        "Bash (long out)",   150,  1200, "Komenda z dlugim outputem"),
    "grep_glob":        ActivityDef("grep_glob",        "Grep/Glob",         100,  200,  "Szukanie po plikach"),
    "skill_invoke":     ActivityDef("skill_invoke",     "Skill invocation",  1500, 300,  "Zaladowanie i uzycie skilla"),
    "mcp_call":         ActivityDef("mcp_call",         "MCP tool call",     400,  600,  "Wywolanie narzedzia MCP"),
    "web_search":       ActivityDef("web_search",       "Web search",        200,  1500, "Wyszukiwanie w sieci"),
    "web_fetch":        ActivityDef("web_fetch",        "Web fetch",         200,  3000, "Pobranie strony"),
    "subagent_launch":  ActivityDef("subagent_launch",  "Sub-agent",         500,  2000, "Uruchomienie subagenta"),
    "todo_read":        ActivityDef("todo_read",        "TodoRead",          50,   50,   "Odczyt listy todo"),
    "todo_write":       ActivityDef("todo_write",       "TodoWrite",         50,   100,  "Zapis listy todo"),
    "memory_read":      ActivityDef("memory_read",      "Memory read",       300,  50,   "Odczyt pliku pamieci"),
    "memory_write":     ActivityDef("memory_write",     "Memory write",      100,  50,   "Zapis do pamieci"),
    "context_view":     ActivityDef("context_view",     "/context",          50,   400,  "Podglad okna kontekstu"),
    "git_status":       ActivityDef("git_status",       "Git status",        200,  50,   "Odswiezenie git status"),
    "lint_run":         ActivityDef("lint_run",         "Linter/tests",      150,  800,  "Wynik lintowania/testow"),
}


@dataclass
class Activity:
    """Instancja aktywnosci w scenie."""
    activity_id: str   # klucz do ACTIVITY_REGISTRY
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
    color: str = "#569cd6"           # kolor w UI
    model: ModelTier = ModelTier.OPUS_4

    # Tokeny wpisywane recznie (MVP)
    system_prompt_tokens: int = 6600
    system_tools_tokens: int = 8400
    skills_tokens: int = 785         # TODO: docelowo per-skill breakdown
    mcp_tokens: int = 0              # TODO: docelowo per-server breakdown
    plugins_tokens: int = 0          # TODO: docelowo per-plugin breakdown
    memory_tokens: int = 6800

    # CLAUDE.md — linie → tokeny
    global_claude_md_lines: int = 50
    project_claude_md_lines: int = 0
    line_token_ratio: float = 10.0   # kalibrowalny

    # Parametry symulacji
    cache_hit_rate: float = 0.70
    ctx_limit: int = 200_000
    autocompact_threshold: float = 0.90  # 90% okna = compact

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
    total_ctx_tokens: int          # calkowity kontekst po tej turze
    history_tokens: int            # historia na wejscie nastepnej sceny
    cost_usd: float
    cumulative_cost_usd: float
    autocompact_fired: bool
    ctx_pct: float                 # % uzytego okna kontekstu


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
```

---

## Silnik symulacji (engine.py)

```python
from tost.cost import calculate_cost   # lub lokalny odpowiednik
from .models import Profile, Scenario, SimResult, SceneResult, DualSimResult

AUTOCOMPACT_BUFFER = 33_000   # ze screena: bufor po compakcie = ~33k tok


def simulate(profile: Profile, scenario: Scenario) -> SimResult:
    history_tokens = 0
    cumulative_cost = 0.0
    scene_results: list[SceneResult] = []
    autocompact_count = 0
    total_in = total_out = total_cached = 0

    for i, scene in enumerate(scenario.scenes, 1):
        tool_in  = scene.tool_input_tokens
        tool_out = scene.tool_output_tokens

        cached_history   = int(history_tokens * profile.cache_hit_rate)
        uncached_history = history_tokens - cached_history

        input_tokens  = (profile.static_overhead
                         + scene.user_message_tokens
                         + uncached_history
                         + tool_in)
        cached_tokens = cached_history
        output_tokens = scene.assistant_response_tokens + tool_out

        total_ctx = (profile.static_overhead + history_tokens
                     + input_tokens + output_tokens)

        autocompact_fired = False
        if total_ctx > profile.autocompact_token_threshold:
            history_tokens = AUTOCOMPACT_BUFFER
            autocompact_fired = True
            autocompact_count += 1
        else:
            history_tokens += (scene.user_message_tokens + output_tokens
                               + tool_in + tool_out)

        rates = PRICING[profile.model]
        cost = (
            input_tokens  * rates["input"]  / 1_000_000
            + cached_tokens * rates["cache_read"] / 1_000_000
            + output_tokens * rates["output"] / 1_000_000
        )
        cumulative_cost += cost
        total_in     += input_tokens
        total_out    += output_tokens
        total_cached += cached_tokens

        scene_results.append(SceneResult(
            scene=scene,
            scene_number=i,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_ctx_tokens=total_ctx,
            history_tokens=history_tokens,
            cost_usd=cost,
            cumulative_cost_usd=cumulative_cost,
            autocompact_fired=autocompact_fired,
            ctx_pct=total_ctx / profile.ctx_limit * 100,
        ))

    return SimResult(
        profile=profile,
        scenario=scenario,
        scene_results=scene_results,
        total_cost_usd=cumulative_cost,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cached_tokens=total_cached,
        autocompact_count=autocompact_count,
    )


def simulate_dual(profile_a: Profile, profile_b: Profile, scenario: Scenario) -> DualSimResult:
    return DualSimResult(
        result_a=simulate(profile_a, scenario),
        result_b=simulate(profile_b, scenario),
    )
```

---

## Format JSON (simulator_data.json)

```json
{
  "version": 2,
  "profiles": [
    {
      "id": "abc12345",
      "name": "Power Setup",
      "color": "#569cd6",
      "model": "claude-opus-4",
      "system_prompt_tokens": 6600,
      "system_tools_tokens": 8400,
      "skills_tokens": 785,
      "mcp_tokens": 1200,
      "plugins_tokens": 3800,
      "memory_tokens": 6800,
      "global_claude_md_lines": 73,
      "project_claude_md_lines": 45,
      "line_token_ratio": 10.0,
      "cache_hit_rate": 0.70,
      "ctx_limit": 200000,
      "autocompact_threshold": 0.90
    }
  ],
  "scenes": [
    {
      "id": "sc001",
      "name": "Init session",
      "user_message_tokens": 200,
      "assistant_response_tokens": 800,
      "activities": [
        {"activity_id": "todo_read", "count": 1},
        {"activity_id": "git_status", "count": 1}
      ]
    }
  ],
  "scenarios": [
    {
      "id": "sn001",
      "name": "Typowy dzien roboty",
      "scene_ids": ["sc001", "sc002", "sc001"]
    }
  ],
  "activity_tokens_overrides": {
    "file_read": {"input_tokens": 850, "output_tokens": 50, "calibrated": true}
  },
  "calibration": {
    "sessions": [],
    "corrections": {}
  }
}
```

---

## Kalibracja (calibrator.py)

```python
from dataclasses import dataclass

@dataclass
class CalibrationReport:
    session_id: str
    scene_count: int
    mae_input: float       # sredni bezwzgledny blad tokenow wejscia
    mae_output: float
    total_sim_cost: float
    total_real_cost: float
    cost_error_pct: float  # (sim - real) / real * 100
    per_scene: list[dict]  # scene_number, sim_input, real_input, delta_pct


def compare_with_tost(
    sim_result: SimResult,
    tost_db_path: str,
    session_id: str,
) -> CalibrationReport:
    """
    Porownuje wynik symulacji z prawdziwymi deltami z bazy TOST.
    
    Wymaga: tost.db z tabelą metric_snapshots (delta_input, delta_output, delta_cost).
    Mapowanie: scena N → delta N (po kolei, zakladamy ze sceny = wiadomosci w sesji).
    """
    import sqlite3
    conn = sqlite3.connect(tost_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT delta_input, delta_output, delta_cost FROM metric_snapshots "
        "WHERE session_id = ? AND (delta_input > 0 OR delta_output > 0) "
        "ORDER BY id ASC",
        (session_id,)
    ).fetchall()
    conn.close()

    n = min(len(sim_result.scene_results), len(rows))
    if n == 0:
        raise ValueError("Brak danych do kalibracji")

    per_scene = []
    total_sim_in = total_real_in = 0.0

    for i in range(n):
        sr = sim_result.scene_results[i]
        real = rows[i]
        delta_pct = ((sr.input_tokens - real["delta_input"]) / real["delta_input"] * 100
                     if real["delta_input"] > 0 else 0.0)
        per_scene.append({
            "scene_number": i + 1,
            "sim_input":    sr.input_tokens,
            "real_input":   real["delta_input"],
            "delta_pct":    delta_pct,
        })
        total_sim_in  += sr.input_tokens
        total_real_in += real["delta_input"]

    mae = sum(abs(s["sim_input"] - s["real_input"]) for s in per_scene) / n
    total_sim_cost  = sim_result.total_cost_usd
    total_real_cost = sum(r["delta_cost"] for r in rows[:n])
    cost_err = ((total_sim_cost - total_real_cost) / total_real_cost * 100
                if total_real_cost > 0 else 0.0)

    return CalibrationReport(
        session_id=session_id,
        scene_count=n,
        mae_input=mae,
        mae_output=0.0,  # TODO
        total_sim_cost=total_sim_cost,
        total_real_cost=total_real_cost,
        cost_error_pct=cost_err,
        per_scene=per_scene,
    )
```

---

## Testy (test_simulator_engine.py)

```python
import pytest
from src.simulator.models import Profile, Scene, Activity, Scenario, ModelTier, ACTIVITY_REGISTRY
from src.simulator.engine import simulate, simulate_dual, AUTOCOMPACT_BUFFER


def make_profile(**kwargs) -> Profile:
    defaults = dict(
        name="Test",
        model=ModelTier.SONNET_4,
        system_prompt_tokens=1000,
        system_tools_tokens=500,
        skills_tokens=0, mcp_tokens=0, plugins_tokens=0,
        memory_tokens=0,
        global_claude_md_lines=0, project_claude_md_lines=0,
        cache_hit_rate=0.0,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    )
    defaults.update(kwargs)
    return Profile(**defaults)


def make_scene(user=200, resp=800, activities=None) -> Scene:
    return Scene(user_message_tokens=user, assistant_response_tokens=resp,
                 activities=activities or [])


def test_static_overhead_calculation():
    p = make_profile(system_prompt_tokens=1000, system_tools_tokens=500,
                     global_claude_md_lines=10, line_token_ratio=10.0)
    assert p.static_overhead == 1000 + 500 + 100


def test_scene_cost_no_history():
    p = make_profile(system_prompt_tokens=5000)
    scenario = Scenario(scenes=[make_scene(user=200, resp=800)])
    result = simulate(p, scenario)
    sr = result.scene_results[0]
    assert sr.input_tokens == 5000 + 200   # overhead + user, brak historii
    assert sr.cached_tokens == 0
    assert sr.output_tokens == 800


def test_history_accumulation():
    p = make_profile(system_prompt_tokens=1000, cache_hit_rate=0.0)
    scene = make_scene(user=100, resp=200)
    scenario = Scenario(scenes=[scene, scene])
    result = simulate(p, scenario)
    # Scena 2: history = user(100) + output(200) z sceny 1 = 300
    assert result.scene_results[1].input_tokens == 1000 + 100 + 300


def test_cache_hit_reduces_cost():
    p_no_cache  = make_profile(cache_hit_rate=0.0, model=ModelTier.OPUS_4)
    p_with_cache = make_profile(cache_hit_rate=0.70, model=ModelTier.OPUS_4)
    scene = make_scene(user=100, resp=200)
    scenario = Scenario(scenes=[scene, scene, scene])
    r_no  = simulate(p_no_cache,  scenario)
    r_yes = simulate(p_with_cache, scenario)
    # Od sceny 2 historia trafia w cache → tanszej stawce
    assert r_yes.total_cost_usd < r_no.total_cost_usd


def test_autocompact_fires():
    p = make_profile(
        system_prompt_tokens=1000,
        cache_hit_rate=0.0,
        ctx_limit=10_000,
        autocompact_threshold=0.50,  # compact przy 5k
    )
    big_scene = make_scene(user=2000, resp=2000)
    scenario = Scenario(scenes=[big_scene, big_scene, big_scene])
    result = simulate(p, scenario)
    assert result.autocompact_count >= 1
    # Po compakcie historia = AUTOCOMPACT_BUFFER
    fired = [sr for sr in result.scene_results if sr.autocompact_fired]
    assert fired[0].history_tokens == AUTOCOMPACT_BUFFER


def test_two_profiles_delta():
    heavy = make_profile(system_prompt_tokens=10_000, model=ModelTier.OPUS_4)
    light = make_profile(system_prompt_tokens=2_000,  model=ModelTier.SONNET_4)
    scenario = Scenario(scenes=[make_scene() for _ in range(5)])
    dual = simulate_dual(heavy, light, scenario)
    assert dual.result_a.total_cost_usd > dual.result_b.total_cost_usd
    assert dual.savings_usd > 0


def test_activity_tokens_added():
    activity = Activity(activity_id="file_read", count=2)
    scene = make_scene(activities=[activity])
    assert scene.tool_input_tokens  == ACTIVITY_REGISTRY["file_read"].input_tokens  * 2
    assert scene.tool_output_tokens == ACTIVITY_REGISTRY["file_read"].output_tokens * 2
```
