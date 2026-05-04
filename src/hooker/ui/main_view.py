"""Hooker — główny widok modułu (QTabWidget z zakładkami Finder/Setup/Wiki/Sound)."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget

from src.hooker.ui.finder_tab import FinderTab
from src.hooker.ui.setup_tab import SetupTab
from src.hooker.ui.sound_tab import SoundTab
from src.hooker.ui.wiki_tab import WikiTab


class HookerView(QTabWidget):
    """Główny widok modułu Hooks — QTabWidget z czterema zakładkami."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._finder = FinderTab()
        self._setup = SetupTab()
        self._wiki = WikiTab()
        self._sound = SoundTab()
        self.addTab(self._finder, "🔍 Finder")
        self.addTab(self._setup, "⚙️ Setup")
        self.addTab(self._wiki, "📖 Wiki")
        self.addTab(self._sound, "🔊 Sound")
