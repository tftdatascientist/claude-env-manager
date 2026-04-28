from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

_MD_FILES = ["CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md", "CHANGELOG.md"]


class RoundWatcher(QObject):
    qt_md_read = Signal(str, str)    # filename, content
    qt_phase_changed = Signal(str)   # nowa faza

    def __init__(self, project_dir: Path | str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project_dir = Path(project_dir)
        self._last_phase: str | None = None

    def on_plan_changed(self, sections: dict[str, str]) -> None:
        meta = sections.get("meta", "")
        phase = self._extract_phase(meta)
        if phase and phase != self._last_phase:
            self._last_phase = phase
            logger.debug("Faza zmieniona: %s", phase)
            self.qt_phase_changed.emit(phase)
            self._read_md_files()

    def _extract_phase(self, meta_text: str) -> str | None:
        for line in meta_text.splitlines():
            if line.strip().startswith("- phase:"):
                return line.split(":", 1)[1].strip()
        return None

    def _read_md_files(self) -> None:
        for filename in _MD_FILES:
            path = self._project_dir / filename
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    self.qt_md_read.emit(filename, content)
                    logger.debug("Przeczytano %s (%d znaków)", filename, len(content))
                except OSError as exc:
                    logger.warning("Nie można przeczytać %s: %s", filename, exc)
