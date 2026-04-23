"""Persistence for project groups in History tab."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "project_groups.json"


@dataclass
class ProjectGroup:
    """A group of projects with one designated as main."""
    main: str  # path of the main (top) project
    members: list[str] = field(default_factory=list)  # all member paths including main
    name: str = ""  # optional custom display name for the group

    @property
    def all_paths(self) -> set[str]:
        return set(self.members)


def load_groups() -> list[ProjectGroup]:
    """Load project groups from disk."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [
                    ProjectGroup(main=g["main"], members=g["members"], name=g.get("name", ""))
                    for g in data
                    if isinstance(g, dict) and "main" in g and "members" in g
                ]
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return []


def save_groups(groups: list[ProjectGroup]) -> None:
    """Save project groups to disk."""
    data = [{"main": g.main, "members": g.members, "name": g.name} for g in groups]
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_group(main_path: str, member_paths: list[str]) -> None:
    """Create a new group. Removes members from any existing groups first."""
    groups = load_groups()
    new_members = set(member_paths)

    # Remove these paths from any existing groups
    for group in groups[:]:
        group.members = [m for m in group.members if m not in new_members]
        if len(group.members) < 2:
            groups.remove(group)
        elif group.main not in group.members:
            group.main = group.members[0]

    # Ensure main is in members and first
    all_members = [main_path] + [p for p in member_paths if p != main_path]
    groups.append(ProjectGroup(main=main_path, members=all_members))
    save_groups(groups)


def ungroup(main_path: str) -> None:
    """Remove a group entirely."""
    groups = load_groups()
    groups = [g for g in groups if g.main != main_path]
    save_groups(groups)


def remove_from_group(project_path: str) -> None:
    """Remove a single project from its group."""
    groups = load_groups()
    for group in groups[:]:
        if project_path in group.members:
            group.members.remove(project_path)
            if len(group.members) < 2:
                groups.remove(group)
            elif group.main == project_path:
                group.main = group.members[0]
            break
    save_groups(groups)


def rename_group(main_path: str, name: str) -> None:
    """Set or clear a custom name for a group."""
    groups = load_groups()
    for group in groups:
        if group.main == main_path:
            group.name = name
            break
    save_groups(groups)


def find_group_for(project_path: str) -> ProjectGroup | None:
    """Find which group a project belongs to, if any."""
    for group in load_groups():
        if project_path in group.members:
            return group
    return None


def get_grouped_paths() -> set[str]:
    """Return all paths that are part of any group (non-main members)."""
    result: set[str] = set()
    for group in load_groups():
        for m in group.members:
            if m != group.main:
                result.add(m)
    return result
