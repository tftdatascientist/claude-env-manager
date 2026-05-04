"""ssm_service.py — SSM background service, uruchamiany przy starcie CM.

Singleton QObject. Trzyma watchers i snapshoty dla wszystkich projektów SSS
niezależnie od tego, czy panel SSM jest aktualnie widoczny.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .jsonl_watcher import JsonlWatcher
from .logger import get_logger
from .project_registry import ProjectEntry, ProjectRegistry
from .project_state import ProjectSnapshot, load_snapshot

MAX_PROJECTS = 4
_REGISTRY_POLL_MS = 5_000  # co ile ms sprawdzamy ~/.ssm/projects.json pod kątem nowych projektów

_log = get_logger()


def _pid(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).lower().encode()).hexdigest()[:12]


class SSMService(QObject):
    """Singleton — trzyma watchers i snapshoty dla wszystkich projektów SSS.

    Uruchamiany przy starcie CM niezależnie od widoczności panelu SSM.
    - project_updated(pid): snapshot projektu się zmienił
    - project_added(pid):   nowy projekt auto-wykryty z registry (dodany przez hook SessionStart)
    """

    project_updated = Signal(str)
    project_added = Signal(str)

    _instance: SSMService | None = None

    @classmethod
    def instance(cls) -> SSMService:
        if cls._instance is None:
            cls._instance = SSMService()
        return cls._instance

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._registry = ProjectRegistry()
        self._watchers: dict[str, JsonlWatcher] = {}
        self._snapshots: dict[str, ProjectSnapshot] = {}
        self._start_all()
        self._registry_poll = QTimer(self)
        self._registry_poll.setInterval(_REGISTRY_POLL_MS)
        self._registry_poll.timeout.connect(self._check_new_projects)
        self._registry_poll.start()
        _log.info('SSMService uruchomiony, %d projektów w rejestrze', len(self._registry.all()))

    # --- Inicjalizacja ---

    def _start_all(self) -> None:
        for entry in self._registry.all():
            self._attach(entry)

    def _attach(self, entry: ProjectEntry) -> None:
        pid = entry.project_id
        if pid in self._watchers:
            return
        path = Path(entry.path)
        jsonl_path = path.resolve() / '.claude' / 'SSS.jsonl'
        watcher = JsonlWatcher(jsonl_path)
        watcher.file_changed.connect(lambda p=pid: self._refresh_snapshot(p))
        watcher.start()
        self._watchers[pid] = watcher
        self._snapshots[pid] = load_snapshot(path)
        _log.debug('Watcher uruchomiony: %s → %s', entry.name or pid, jsonl_path)

    def _detach(self, pid: str) -> None:
        if pid in self._watchers:
            self._watchers.pop(pid).stop()
        self._snapshots.pop(pid, None)

    # --- Aktualizacja snapshotu ---

    def _refresh_snapshot(self, pid: str) -> None:
        entry = self._registry.get(pid)
        if not entry:
            return
        try:
            self._snapshots[pid] = load_snapshot(Path(entry.path))
            _log.debug('Snapshot odświeżony: %s', pid)
        except Exception as exc:
            _log.warning('Błąd odświeżania snapshotu %s: %s', pid, exc)
            return
        self.project_updated.emit(pid)

    # --- Auto-wykrywanie projektów z registry (hook SessionStart) ---

    def _check_new_projects(self) -> None:
        """Sprawdza czy hook SessionStart dodał nowe projekty do ~/.ssm/projects.json."""
        if len(self._watchers) >= MAX_PROJECTS:
            return
        try:
            fresh = ProjectRegistry()
        except Exception:
            return
        known_pids = set(self._watchers.keys())
        for entry in fresh.all():
            if entry.project_id in known_pids:
                continue
            if len(self._watchers) >= MAX_PROJECTS:
                break
            self._registry.add(entry)
            self._attach(entry)
            _log.info('Auto-wykryto projekt SSS (hook): %s', entry.name or entry.project_id)
            self.project_added.emit(entry.project_id)

    # --- Public API ---

    def projects(self) -> list[ProjectEntry]:
        return self._registry.all()

    def snapshot(self, pid: str) -> ProjectSnapshot | None:
        return self._snapshots.get(pid)

    def can_add(self) -> bool:
        return len(self._registry.all()) < MAX_PROJECTS

    def add_project(self, path: Path) -> tuple[bool, str]:
        """Dodaje projekt SSS do monitorowania. Zwraca (success, message)."""
        if not self.can_add():
            return False, f'Limit {MAX_PROJECTS} projektów osiągnięty'
        plan = path / 'PLAN.md'
        try:
            has_marker = plan.exists() and '<!-- SECTION:next -->' in plan.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            has_marker = False
        if not has_marker:
            return False, 'Nie jest projektem SSS (brak PLAN.md z markerem <!-- SECTION:next -->)'
        if self._registry.find_by_path(str(path)):
            return False, 'Projekt już monitorowany'
        pid = _pid(path)
        entry = ProjectEntry(project_id=pid, path=str(path), added_via='manual', name=path.name)
        self._registry.add(entry)
        self._attach(entry)
        _log.info('Dodano projekt: %s (%s)', path.name, pid)
        return True, 'OK'

    def remove_project(self, pid: str) -> None:
        self._detach(pid)
        self._registry.remove(pid)
        _log.info('Usunięto projekt: %s', pid)
