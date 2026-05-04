"""Merger hooków CC: global + project → efektywny widok merge.

Semantyka CC: hooki na wszystkich poziomach są ADDYTYWNE (nie nadpisują się).
CC uruchamia wszystkie pasujące hooki z obu poziomów.
Merger produkuje widok merged z oznaczeniem source/level dla UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.hooker.core.model import Hook, HookLevel, HookType


@dataclass
class MergedHook:
    """Hook w widoku merge — z oznaczeniem źródła i czy jest nadpisany."""

    hook: Hook
    shadowed_by: list[Hook]  # hooki z wyższego poziomu które mają ten sam type+matcher

    @property
    def is_shadowed(self) -> bool:
        return bool(self.shadowed_by)

    @property
    def source_label(self) -> str:
        return "global" if self.hook.level == HookLevel.GLOBAL else "project"


@dataclass
class MergeResult:
    """Wynik merge hooków z 2 poziomów."""

    global_hooks: list[Hook]
    project_hooks: list[Hook]
    merged: list[MergedHook]  # pełny widok: global + project, z oznaczeniem shadowing

    @property
    def all_hooks(self) -> list[Hook]:
        return self.global_hooks + self.project_hooks

    def by_type(self, hook_type: HookType) -> list[MergedHook]:
        return [m for m in self.merged if m.hook.hook_type == hook_type]

    def only_global(self) -> list[MergedHook]:
        return [m for m in self.merged if m.hook.level == HookLevel.GLOBAL]

    def only_project(self) -> list[MergedHook]:
        return [m for m in self.merged if m.hook.level == HookLevel.PROJECT]


def merge(global_hooks: list[Hook], project_hooks: list[Hook]) -> MergeResult:
    """Łączy hooki z 2 poziomów w widok merge.

    CC uruchamia hooki addytywnie — project hooki NIE nadpisują global.
    Shadowing oznacza wyłącznie: project hook ma taki sam type+matcher co global
    (informacja wizualna dla usera, nie zmiana zachowania CC).
    """
    merged: list[MergedHook] = []

    # Zbuduj indeks project hooks po (type, matcher)
    project_index: dict[tuple[HookType, str], list[Hook]] = {}
    for ph in project_hooks:
        key = (ph.hook_type, ph.matcher)
        project_index.setdefault(key, []).append(ph)

    # Global hooki — oznacz które są "powtórzone" na poziomie project
    for gh in global_hooks:
        key = (gh.hook_type, gh.matcher)
        shadowed_by = project_index.get(key, [])
        merged.append(MergedHook(hook=gh, shadowed_by=shadowed_by))

    # Project hooki — oznacz które "powtarzają" global
    global_index: dict[tuple[HookType, str], list[Hook]] = {}
    for gh in global_hooks:
        key = (gh.hook_type, gh.matcher)
        global_index.setdefault(key, []).append(gh)

    for ph in project_hooks:
        key = (ph.hook_type, ph.matcher)
        shadowed_by = global_index.get(key, [])
        merged.append(MergedHook(hook=ph, shadowed_by=shadowed_by))

    return MergeResult(
        global_hooks=global_hooks,
        project_hooks=project_hooks,
        merged=merged,
    )
