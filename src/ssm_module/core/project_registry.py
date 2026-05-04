"""project_registry.py — globalny indeks projektów SSS monitorowanych przez SSM."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_REGISTRY_PATH = Path(os.environ.get('USERPROFILE', Path.home())) / '.ssm' / 'projects.json'

AddedVia = Literal['hook', 'manual']


@dataclass
class ProjectEntry:
    project_id: str
    path: str
    added_via: AddedVia
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat())
    name: str = ''


class ProjectRegistry:
    def __init__(self, registry_path: Path = _REGISTRY_PATH) -> None:
        self._path = registry_path
        self._entries: dict[str, ProjectEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding='utf-8'))
            for item in data.get('projects', []):
                e = ProjectEntry(**item)
                self._entries[e.project_id] = e
        except Exception:
            pass

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {'projects': [asdict(e) for e in self._entries.values()]}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def add(self, entry: ProjectEntry) -> None:
        self._entries[entry.project_id] = entry
        self.save()

    def remove(self, project_id: str) -> None:
        self._entries.pop(project_id, None)
        self.save()

    def get(self, project_id: str) -> ProjectEntry | None:
        return self._entries.get(project_id)

    def all(self) -> list[ProjectEntry]:
        return list(self._entries.values())

    def find_by_path(self, path: str) -> ProjectEntry | None:
        resolved = str(Path(path).resolve())
        return next(
            (e for e in self._entries.values() if str(Path(e.path).resolve()) == resolved),
            None,
        )
