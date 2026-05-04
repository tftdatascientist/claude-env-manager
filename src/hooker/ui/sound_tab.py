"""Sound Hook — zakładka konfiguracji dźwięków per typ zdarzenia CC."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.hooker.core import logger as audit_log
from src.hooker.core.editor import apply_hooks, read_settings
from src.hooker.core.model import HookType
from src.hooker.core.persister import write_settings
from src.hooker.core.sound_manager import (
    SOUND_EVENT_TYPES,
    build_sound_hooks,
    install_hook_script,
    load_config,
    preview_sound,
    save_config,
)

_GLOBAL_SETTINGS = Path.home() / ".claude" / "settings.json"

_EVENT_COLORS = {
    "Stop":         "#ef4444",
    "Notification": "#f59e0b",
    "SessionEnd":   "#ec4899",
    "SessionStart": "#84cc16",
    "SubagentStop": "#f97316",
    "PreCompact":   "#06b6d4",
    "PostCompact":  "#8b5cf6",
}
_EVENT_DESC = {
    "Stop":         "Główny agent kończy pracę",
    "Notification": "CC potrzebuje uwagi",
    "SessionEnd":   "Sesja CC się kończy",
    "SessionStart": "Sesja CC startuje",
    "SubagentStop": "Sub-agent kończy pracę",
    "PreCompact":   "Przed kompresją kontekstu",
    "PostCompact":  "Po kompresji kontekstu",
}


class _SoundRow(QWidget):
    """Jeden wiersz tabeli — event type + plik + preview + enable."""

    def __init__(self, event_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.event_type = event_type
        self._file_path = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        color = _EVENT_COLORS.get(self.event_type, "#94a3b8")
        desc = _EVENT_DESC.get(self.event_type, "")

        # Enable checkbox
        self._chk = QCheckBox()
        self._chk.setToolTip("Włącz hook dźwiękowy dla tego zdarzenia")
        row.addWidget(self._chk)

        # Event type label
        lbl_type = QLabel(f"<b style='color:{color}'>{self.event_type}</b>")
        lbl_type.setTextFormat(Qt.TextFormat.RichText)
        lbl_type.setFixedWidth(120)
        row.addWidget(lbl_type)

        # Desc
        lbl_desc = QLabel(f"<span style='color:#64748b; font-size:11px'>{desc}</span>")
        lbl_desc.setTextFormat(Qt.TextFormat.RichText)
        lbl_desc.setFixedWidth(180)
        row.addWidget(lbl_desc)

        # File label
        self._lbl_file = QLabel("<i style='color:#475569'>brak pliku</i>")
        self._lbl_file.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_file.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._lbl_file.setToolTip("")
        row.addWidget(self._lbl_file, 1)

        # Browse button
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(32)
        btn_browse.setToolTip("Wybierz plik dźwiękowy…")
        btn_browse.clicked.connect(self._browse)
        row.addWidget(btn_browse)

        # Clear button
        btn_clear = QPushButton("✕")
        btn_clear.setFixedWidth(28)
        btn_clear.setToolTip("Usuń plik")
        btn_clear.setStyleSheet("color:#64748b;")
        btn_clear.clicked.connect(self._clear)
        row.addWidget(btn_clear)

        # Preview button
        self._btn_play = QPushButton("▶")
        self._btn_play.setFixedWidth(32)
        self._btn_play.setToolTip("Odtwórz podgląd")
        self._btn_play.setEnabled(False)
        self._btn_play.clicked.connect(self._preview)
        row.addWidget(self._btn_play)

    def _browse(self) -> None:
        start = str(Path.home() / "Desktop")
        path, _ = QFileDialog.getOpenFileName(
            self, f"Dźwięk dla {self.event_type}",
            start, "Dźwięk (*.wav *.mp3 *.ogg);;Wszystkie (*)",
        )
        if path:
            self.set_file(path)

    def _clear(self) -> None:
        self.set_file("")

    def _preview(self) -> None:
        if self._file_path:
            preview_sound(self._file_path)

    def set_file(self, path: str) -> None:
        self._file_path = path
        if path:
            name = Path(path).name
            self._lbl_file.setText(f"<code style='color:#94a3b8'>{name}</code>")
            self._lbl_file.setToolTip(path)
            self._btn_play.setEnabled(True)
        else:
            self._lbl_file.setText("<i style='color:#475569'>brak pliku</i>")
            self._lbl_file.setToolTip("")
            self._btn_play.setEnabled(False)

    def get_file(self) -> str:
        return self._file_path

    def is_enabled(self) -> bool:
        return self._chk.isChecked()

    def set_enabled(self, val: bool) -> None:
        self._chk.setChecked(val)


class SoundTab(QWidget):
    """Sound Hook — konfiguracja dźwięków per typ zdarzenia CC."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, _SoundRow] = {}
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        header = QLabel(
            "<b style='color:#f8fafc; font-size:14px'>Sound Hook</b>"
            "<span style='color:#64748b'> — dźwięki per zdarzenie CC</span>"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(header)

        info = QLabel(
            "<small style='color:#64748b'>"
            "Każdy włączony event uruchamia skrypt <code>~/.claude/hooks/sound_hook.py</code> "
            "który odtwarza wybrany plik dźwiękowy. "
            "Obsługiwane formaty: WAV (natywny), MP3/OGG (przez PowerShell)."
            "</small>"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        root.addWidget(info)

        # Nagłówek kolumn
        col_header = QHBoxLayout()
        col_header.setContentsMargins(0, 0, 0, 0)
        col_header.addWidget(QLabel(""), 0)   # checkbox
        lbl_ev = QLabel("<b style='color:#94a3b8; font-size:11px'>ZDARZENIE</b>")
        lbl_ev.setTextFormat(Qt.TextFormat.RichText)
        lbl_ev.setFixedWidth(120)
        col_header.addWidget(lbl_ev)
        lbl_de = QLabel("<b style='color:#94a3b8; font-size:11px'>OPIS</b>")
        lbl_de.setTextFormat(Qt.TextFormat.RichText)
        lbl_de.setFixedWidth(180)
        col_header.addWidget(lbl_de)
        lbl_fi = QLabel("<b style='color:#94a3b8; font-size:11px'>PLIK DŹWIĘKOWY</b>")
        lbl_fi.setTextFormat(Qt.TextFormat.RichText)
        col_header.addWidget(lbl_fi, 1)
        col_header.addWidget(QLabel(""), 0)
        col_header.addWidget(QLabel(""), 0)
        col_header.addWidget(QLabel(""), 0)
        root.addLayout(col_header)

        # Scroll area z wierszami
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 4px; }")
        container = QWidget()
        container.setStyleSheet("background: #0f172a;")
        rows_layout = QVBoxLayout(container)
        rows_layout.setContentsMargins(8, 4, 8, 4)
        rows_layout.setSpacing(2)

        for evt in SOUND_EVENT_TYPES:
            row_widget = _SoundRow(evt)
            rows_layout.addWidget(row_widget)
            self._rows[evt] = row_widget

        rows_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Przyciski akcji
        btns = QHBoxLayout()
        btn_install = QPushButton("📥 Zainstaluj skrypt hooka")
        btn_install.setToolTip("Generuje ~/.claude/hooks/sound_hook.py")
        btn_install.clicked.connect(self._install_script)

        btn_save = QPushButton("💾 Zapisz i wstaw hooki do settings.json")
        btn_save.setStyleSheet(
            "QPushButton { background:#3b82f6; color:white; font-weight:bold;"
            " padding:6px 16px; border-radius:4px; }"
            "QPushButton:hover { background:#2563eb; }"
        )
        btn_save.clicked.connect(self._save)

        btns.addWidget(btn_install)
        btns.addStretch()
        btns.addWidget(btn_save)
        root.addLayout(btns)

    def _load(self) -> None:
        config = load_config()
        sounds = config.get("sounds", {})
        enabled = set(config.get("enabled", []))
        for evt, row in self._rows.items():
            row.set_file(sounds.get(evt, ""))
            row.set_enabled(evt in enabled)

    def _install_script(self) -> None:
        try:
            path = install_hook_script()
            QMessageBox.information(
                self, "Skrypt zainstalowany",
                f"Skrypt sound_hook.py zapisany:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Błąd", str(e))

    def _save(self) -> None:
        config: dict = {"sounds": {}, "enabled": []}
        for evt, row in self._rows.items():
            f = row.get_file()
            if f:
                config["sounds"][evt] = f
            if row.is_enabled():
                config["enabled"].append(evt)

        try:
            save_config(config)
        except Exception as e:
            QMessageBox.critical(self, "Błąd zapisu config", str(e))
            return

        # Wstaw/usuń hooki w global settings.json
        try:
            sound_hooks = build_sound_hooks(config)
            settings = read_settings(_GLOBAL_SETTINGS)

            for evt in SOUND_EVENT_TYPES:
                try:
                    ht = HookType(evt)
                except ValueError:
                    continue
                hooks_for_type = []
                if evt in sound_hooks:
                    from src.hooker.core.model import Hook, HookLevel
                    hooks_for_type = [
                        Hook(hook_type=ht, command=sound_hooks[evt][0]["hooks"][0]["command"],
                             source_file=_GLOBAL_SETTINGS, level=HookLevel.GLOBAL)
                    ]
                settings = apply_hooks(settings, ht, hooks_for_type)

            bak, hb, ha = write_settings(_GLOBAL_SETTINGS, settings)
            audit_log.log_write(_GLOBAL_SETTINGS, hb, ha, bak)
        except Exception as e:
            audit_log.log_error(_GLOBAL_SETTINGS, str(e))
            QMessageBox.warning(self, "Config OK, błąd settings.json", str(e))
            return

        enabled_count = len(config["enabled"])
        QMessageBox.information(
            self, "Zapisano",
            f"Config dźwięków zapisany.\n"
            f"Włączonych hooków: {enabled_count}\n"
            f"Backup settings.json: {bak.name if bak else 'brak'}"
        )
