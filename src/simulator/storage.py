from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    ACTIVITY_REGISTRY,
    Activity,
    ActivityDef,
    ModelTier,
    Profile,
    Scene,
    Scenario,
)

_DEFAULT_PATH = Path(__file__).parent.parent.parent / "simulator_data.json"
DATA_VERSION = 2


def _profile_to_dict(p: Profile) -> dict:
    return {
        "id":                      p.id,
        "name":                    p.name,
        "color":                   p.color,
        "model":                   p.model.value,
        "system_prompt_tokens":    p.system_prompt_tokens,
        "system_tools_tokens":     p.system_tools_tokens,
        "skills_tokens":           p.skills_tokens,
        "mcp_tokens":              p.mcp_tokens,
        "plugins_tokens":          p.plugins_tokens,
        "memory_tokens":           p.memory_tokens,
        "global_claude_md_lines":  p.global_claude_md_lines,
        "project_claude_md_lines": p.project_claude_md_lines,
        "line_token_ratio":        p.line_token_ratio,
        "cache_hit_rate":          p.cache_hit_rate,
        "ctx_limit":               p.ctx_limit,
        "autocompact_threshold":   p.autocompact_threshold,
    }


def _profile_from_dict(d: dict) -> Profile:
    return Profile(
        id=d["id"],
        name=d["name"],
        color=d.get("color", "#569cd6"),
        model=ModelTier(d["model"]),
        system_prompt_tokens=d.get("system_prompt_tokens", 6600),
        system_tools_tokens=d.get("system_tools_tokens", 8400),
        skills_tokens=d.get("skills_tokens", 0),
        mcp_tokens=d.get("mcp_tokens", 0),
        plugins_tokens=d.get("plugins_tokens", 0),
        memory_tokens=d.get("memory_tokens", 0),
        global_claude_md_lines=d.get("global_claude_md_lines", 0),
        project_claude_md_lines=d.get("project_claude_md_lines", 0),
        line_token_ratio=d.get("line_token_ratio", 10.0),
        cache_hit_rate=d.get("cache_hit_rate", 0.70),
        ctx_limit=d.get("ctx_limit", 200_000),
        autocompact_threshold=d.get("autocompact_threshold", 0.90),
    )


def _scene_to_dict(s: Scene) -> dict:
    return {
        "id":                       s.id,
        "name":                     s.name,
        "user_message_tokens":      s.user_message_tokens,
        "assistant_response_tokens": s.assistant_response_tokens,
        "activities": [
            {"activity_id": a.activity_id, "count": a.count}
            for a in s.activities
        ],
    }


def _scene_from_dict(d: dict) -> Scene:
    return Scene(
        id=d["id"],
        name=d.get("name", "Scena"),
        user_message_tokens=d.get("user_message_tokens", 200),
        assistant_response_tokens=d.get("assistant_response_tokens", 800),
        activities=[
            Activity(activity_id=a["activity_id"], count=a.get("count", 1))
            for a in d.get("activities", [])
            if a["activity_id"] in ACTIVITY_REGISTRY
        ],
    )


def _scenario_to_dict(sc: Scenario, scene_index: dict[str, int]) -> dict:
    return {
        "id":        sc.id,
        "name":      sc.name,
        "scene_ids": [s.id for s in sc.scenes],
    }


def _scenario_from_dict(d: dict, scenes_by_id: dict[str, Scene]) -> Scenario:
    scenes = [scenes_by_id[sid] for sid in d.get("scene_ids", []) if sid in scenes_by_id]
    return Scenario(id=d["id"], name=d.get("name", "Scenariusz"), scenes=scenes)


class SimulatorStorage:
    """Ladowanie i zapis stanu symulatora z/do simulator_data.json."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_PATH

    def load(self) -> dict[str, Any]:
        """
        Zwraca slownik z kluczami: profiles, scenes, scenarios,
        activity_tokens_overrides, calibration.
        Jesli pliku nie ma, zwraca puste struktury.
        """
        if not self.path.exists():
            return self._empty_state()

        raw = json.loads(self.path.read_text(encoding="utf-8"))

        # Zaaplikuj nadpisania tokenow aktywnosci
        overrides: dict = raw.get("activity_tokens_overrides", {})
        for act_id, vals in overrides.items():
            if act_id in ACTIVITY_REGISTRY:
                entry = ACTIVITY_REGISTRY[act_id]
                entry.input_tokens  = vals.get("input_tokens",  entry.input_tokens)
                entry.output_tokens = vals.get("output_tokens", entry.output_tokens)
                entry.calibrated    = vals.get("calibrated",    entry.calibrated)

        profiles  = [_profile_from_dict(d) for d in raw.get("profiles", [])]
        scenes    = [_scene_from_dict(d)   for d in raw.get("scenes",   [])]
        scenes_by_id = {s.id: s for s in scenes}
        scenarios = [
            _scenario_from_dict(d, scenes_by_id)
            for d in raw.get("scenarios", [])
        ]

        return {
            "profiles":   profiles,
            "scenes":     scenes,
            "scenarios":  scenarios,
            "calibration": raw.get("calibration", {"sessions": [], "corrections": {}}),
        }

    def save(
        self,
        profiles: list[Profile],
        scenes: list[Scene],
        scenarios: list[Scenario],
        calibration: dict | None = None,
    ) -> None:
        # Zbierz wszystkie unikalne sceny: biblioteka + sceny ze scenariuszy
        all_scenes: dict[str, Scene] = {s.id: s for s in scenes}
        for sc in scenarios:
            for s in sc.scenes:
                all_scenes.setdefault(s.id, s)

        scene_list = list(all_scenes.values())
        scene_index = {s.id: i for i, s in enumerate(scene_list)}
        data = {
            "version":   DATA_VERSION,
            "profiles":  [_profile_to_dict(p) for p in profiles],
            "scenes":    [_scene_to_dict(s)    for s in scene_list],
            "scenarios": [_scenario_to_dict(sc, scene_index) for sc in scenarios],
            "activity_tokens_overrides": self._build_overrides(),
            "calibration": calibration or {"sessions": [], "corrections": {}},
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _build_overrides(self) -> dict:
        """Zbiera aktywnosci, ktore maja calibrated=True (odchylenia od defaults)."""
        from .models import ACTIVITY_REGISTRY as _REG
        overrides = {}
        _defaults = {
            "file_read":       (800,  50),
            "file_read_large": (2400, 50),
            "file_edit":       (300,  100),
            "file_write":      (200,  500),
            "file_multi_read": (1600, 50),
            "bash_cmd":        (150,  300),
            "bash_long":       (150,  1200),
            "grep_glob":       (100,  200),
            "skill_invoke":    (1500, 300),
            "mcp_call":        (400,  600),
            "web_search":      (200,  1500),
            "web_fetch":       (200,  3000),
            "subagent_launch": (500,  2000),
            "todo_read":       (50,   50),
            "todo_write":      (50,   100),
            "memory_read":     (300,  50),
            "memory_write":    (100,  50),
            "context_view":    (50,   400),
            "git_status":      (200,  50),
            "lint_run":        (150,  800),
        }
        for act_id, act in _REG.items():
            def_in, def_out = _defaults.get(act_id, (act.input_tokens, act.output_tokens))
            if act.calibrated or act.input_tokens != def_in or act.output_tokens != def_out:
                overrides[act_id] = {
                    "input_tokens":  act.input_tokens,
                    "output_tokens": act.output_tokens,
                    "calibrated":    act.calibrated,
                }
        return overrides

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "profiles":   [],
            "scenes":     [],
            "scenarios":  [],
            "calibration": {"sessions": [], "corrections": {}},
        }
