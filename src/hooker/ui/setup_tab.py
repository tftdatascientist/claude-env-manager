"""Hook Setup — zakładka do dodawania/edycji/usuwania hooków CC (wszystkie 9 typów)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.hooker.core import logger as audit_log
from src.hooker.core.editor import apply_hooks, load_hooks_for_type, read_settings
from src.hooker.core.model import Hook, HookLevel, HookType, HOOK_TYPE_INFO
from src.hooker.core.persister import write_settings
from src.hooker.core.validator import validate_dict
from src.hooker.ui.restore_dialog import RestoreDialog
from src.hooker.ui.snippet_dialog import SnippetDialog

_GLOBAL_SETTINGS = Path.home() / ".claude" / "settings.json"


class SetupTab(QWidget):
    """Hook Setup — CRUD dla wszystkich 9 typów hooków (global lub project)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._hooks: list[Hook] = []
        self._editing_index: int | None = None
        self._setup_ui()
        self._refresh_hooks()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Toolbar wiersz 1: poziom
        toolbar1 = QHBoxLayout()
        toolbar1.addWidget(QLabel("<b>Poziom:</b>"))
        self._level_combo = QComboBox()
        self._level_combo.addItem("🌐 Globalny  (~/.claude/settings.json)", HookLevel.GLOBAL)
        self._level_combo.addItem("📁 Projekt  (.claude/settings.json)", HookLevel.PROJECT)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar1.addWidget(self._level_combo)

        self._btn_folder = QPushButton("📁 Wybierz folder…")
        self._btn_folder.setVisible(False)
        self._btn_folder.clicked.connect(self._pick_folder)
        toolbar1.addWidget(self._btn_folder)

        self._lbl_path = QLabel()
        self._lbl_path.setStyleSheet("color:#94a3b8; font-size:11px;")
        toolbar1.addWidget(self._lbl_path, 1)
        root.addLayout(toolbar1)

        # Toolbar wiersz 2: typ hooka
        toolbar2 = QHBoxLayout()
        toolbar2.addWidget(QLabel("<b>Typ hooka:</b>"))
        self._type_combo = QComboBox()
        for hook_type in HookType:
            info = HOOK_TYPE_INFO[hook_type]
            self._type_combo.addItem(f"{hook_type.value}", hook_type)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        toolbar2.addWidget(self._type_combo)
        btn_snippet = QPushButton("📋 Wstaw snippet…")
        btn_snippet.setToolTip("Wybierz gotowy snippet hooka z biblioteki")
        btn_snippet.clicked.connect(self._open_snippet_picker)
        toolbar2.addWidget(btn_snippet)
        toolbar2.addStretch()
        root.addLayout(toolbar2)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#334155;")
        root.addWidget(sep)

        # Splitter: lista | formularz
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ---- Lewa: lista hooków ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(4)

        self._list_header = QLabel()
        self._list_header.setTextFormat(Qt.TextFormat.RichText)
        left_layout.addWidget(self._list_header)

        self._hook_list = QListWidget()
        self._hook_list.currentRowChanged.connect(self._on_hook_selected)
        left_layout.addWidget(self._hook_list, 1)

        list_btns = QHBoxLayout()
        self._btn_new = QPushButton("＋ Nowy")
        self._btn_new.clicked.connect(self._new_hook)
        self._btn_delete = QPushButton("🗑 Usuń")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_hook)
        list_btns.addWidget(self._btn_new)
        list_btns.addWidget(self._btn_delete)
        left_layout.addLayout(list_btns)

        splitter.addWidget(left)

        # ---- Prawa: formularz ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        self._form_box = QGroupBox()
        self._form_layout = QVBoxLayout(self._form_box)
        self._form_layout.setSpacing(6)

        # Matcher
        self._form_layout.addWidget(
            QLabel("Matcher <span style='color:#64748b'>(opcjonalny — nazwa narzędzia lub regex)</span>:")
        )
        self._matcher_edit = QLineEdit()
        self._matcher_edit.setPlaceholderText(
            "np. Bash  lub  ^(Bash|Read)$  lub  puste = wszystkie"
        )
        self._form_layout.addWidget(self._matcher_edit)

        # Command
        self._form_layout.addWidget(
            QLabel(
                "Command <span style='color:#ef4444'>*</span>"
                " <span style='color:#64748b'>(wymagane — ścieżka do skryptu lub komenda shell)</span>:"
            )
        )
        cmd_row = QHBoxLayout()
        self._command_edit = QLineEdit()
        self._command_edit.setPlaceholderText("np. python ~/.claude/hooks/my_hook.py")
        cmd_row.addWidget(self._command_edit, 1)
        btn_browse = QPushButton("📂")
        btn_browse.setToolTip("Wybierz plik skryptu…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse_command)
        cmd_row.addWidget(btn_browse)
        self._form_layout.addLayout(cmd_row)

        # Info box (dynamiczny)
        self._info_lbl = QLabel()
        self._info_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._info_lbl.setWordWrap(True)
        self._info_lbl.setStyleSheet("background:#1e293b; padding:6px; border-radius:4px;")
        self._form_layout.addWidget(self._info_lbl)

        self._form_layout.addStretch()

        self._btn_save = QPushButton("💾 Zapisz")
        self._btn_save.setStyleSheet(
            "QPushButton { background:#3b82f6; color:white; font-weight:bold;"
            " padding:6px 16px; border-radius:4px; }"
            "QPushButton:hover { background:#2563eb; }"
            "QPushButton:disabled { background:#334155; color:#64748b; }"
        )
        self._btn_save.clicked.connect(self._save_hook)
        self._form_layout.addWidget(self._btn_save)

        right_layout.addWidget(self._form_box, 1)

        restore_bar = QHBoxLayout()
        self._btn_restore = QPushButton("🔄 Restore z backupu…")
        self._btn_restore.setStyleSheet("color:#94a3b8;")
        self._btn_restore.clicked.connect(self._open_restore)
        restore_bar.addStretch()
        restore_bar.addWidget(self._btn_restore)
        right_layout.addLayout(restore_bar)

        splitter.addWidget(right)
        splitter.setSizes([300, 500])
        root.addWidget(splitter, 1)

        self._update_path_label()
        self._update_type_ui()

    # ------------------------------------------------------------------ Helpers UI

    def _update_type_ui(self) -> None:
        ht = self._current_hook_type()
        info = HOOK_TYPE_INFO[ht]
        color = info.get("color", "#94a3b8")

        self._form_box.setTitle(f"Edytuj hook {ht.value}")
        self._form_box.setStyleSheet(
            f"QGroupBox {{ font-weight:bold; color:{color}; "
            f"border:1px solid {color}44; border-radius:4px; "
            f"margin-top:8px; padding-top:4px; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left:8px; }}"
        )
        self._list_header.setText(
            f"<b style='color:{color}'>{ht.value}</b>"
            f"<span style='color:#64748b'> — hooki w wybranym pliku</span>"
        )
        self._info_lbl.setText(
            f"<small style='color:#64748b'>"
            f"<b>Kiedy:</b> {info['when']}<br>"
            f"<b>Input:</b> {info['input']}<br>"
            f"<b>Output:</b> {info['output']}<br>"
            f"<b>Przykład:</b> {info['example']}"
            f"</small>"
        )

    # ------------------------------------------------------------------ Level / path

    def _on_level_changed(self, _index: int) -> None:
        is_project = self._current_level() == HookLevel.PROJECT
        self._btn_folder.setVisible(is_project)
        self._update_path_label()
        self._refresh_hooks()

    def _on_type_changed(self, _index: int) -> None:
        self._update_type_ui()
        self._refresh_hooks()

    def _pick_folder(self) -> None:
        start = str(self._project_path) if self._project_path else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder projektu CC", start)
        if folder:
            self._project_path = Path(folder)
            self._update_path_label()
            self._refresh_hooks()

    def _current_level(self) -> HookLevel:
        data = self._level_combo.currentData()
        if isinstance(data, HookLevel):
            return data
        try:
            return HookLevel(data)
        except (ValueError, TypeError):
            return HookLevel.GLOBAL

    def _current_hook_type(self) -> HookType:
        data = self._type_combo.currentData()
        if isinstance(data, HookType):
            return data
        try:
            return HookType(data)
        except (ValueError, TypeError):
            return HookType.PRE_TOOL_USE

    def _current_settings_path(self) -> Path | None:
        if self._current_level() == HookLevel.GLOBAL:
            return _GLOBAL_SETTINGS
        if self._project_path is None:
            return None
        return self._project_path / ".claude" / "settings.json"

    def _update_path_label(self) -> None:
        path = self._current_settings_path()
        if path is None:
            self._lbl_path.setText("<i style='color:#f59e0b'>Wybierz folder projektu →</i>")
        else:
            exists = "✓" if path.exists() else "○ nowy plik"
            self._lbl_path.setText(
                f"<code style='color:#94a3b8'>{path}</code>"
                f" <span style='color:#64748b'>{exists}</span>"
            )

    # ------------------------------------------------------------------ Hook list

    def _refresh_hooks(self) -> None:
        path = self._current_settings_path()
        self._hook_list.clear()
        self._editing_index = None
        self._btn_delete.setEnabled(False)
        self._clear_form()

        if path is None:
            self._hooks = []
            return

        self._hooks = load_hooks_for_type(path, self._current_hook_type(), self._current_level())
        for h in self._hooks:
            matcher_label = h.matcher if h.matcher else "* (wszystkie)"
            self._hook_list.addItem(QListWidgetItem(f"{matcher_label}  →  {h.command}"))

    def _on_hook_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._hooks):
            self._editing_index = None
            self._btn_delete.setEnabled(False)
            return
        self._editing_index = row
        self._btn_delete.setEnabled(True)
        h = self._hooks[row]
        self._matcher_edit.setText(h.matcher)
        self._command_edit.setText(h.command)

    def _new_hook(self) -> None:
        self._hook_list.clearSelection()
        self._editing_index = None
        self._btn_delete.setEnabled(False)
        self._clear_form()
        self._command_edit.setFocus()

    def _clear_form(self) -> None:
        self._matcher_edit.clear()
        self._command_edit.clear()

    def _open_snippet_picker(self) -> None:
        ht = self._current_hook_type()
        dlg = SnippetDialog(ht.value, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            snippet = dlg.get_snippet()
            if snippet:
                self._new_hook()
                self._matcher_edit.setText(snippet.matcher)
                self._command_edit.setText(snippet.command)

    def _browse_command(self) -> None:
        start = str(Path.home() / ".claude" / "hooks")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik skryptu hooka",
            start,
            "Skrypty (*.py *.sh *.bat *.ps1 *.js);;Wszystkie pliki (*)",
        )
        if not path:
            return
        current = self._command_edit.text().strip()
        if not current:
            self._command_edit.setText(path)
        else:
            self._command_edit.setText(f"{current} {path}")

    # ------------------------------------------------------------------ Save / Delete

    def _save_hook(self) -> None:
        path = self._current_settings_path()
        if path is None:
            QMessageBox.warning(self, "Brak pliku", "Najpierw wybierz folder projektu.")
            return

        command = self._command_edit.text().strip()
        if not command:
            QMessageBox.warning(self, "Brak command", "Pole 'Command' jest wymagane.")
            self._command_edit.setFocus()
            return

        hook_type = self._current_hook_type()
        matcher = self._matcher_edit.text().strip()
        level = self._current_level()

        new_hook = Hook(
            hook_type=hook_type,
            command=command,
            matcher=matcher,
            source_file=path,
            level=level,
        )

        hooks = list(self._hooks)
        if self._editing_index is not None:
            hooks[self._editing_index] = new_hook
        else:
            hooks.append(new_hook)

        settings = read_settings(path)
        updated = apply_hooks(settings, hook_type, hooks)

        result = validate_dict(updated)
        if result.has_schema_warnings:
            warn_text = "\n".join(result.schema_errors[:5])
            reply = QMessageBox.warning(
                self,
                "Ostrzeżenie schema",
                f"Walidacja schema zgłosiła uwagi:\n\n{warn_text}\n\nZapisać mimo to?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            bak, hash_before, hash_after = write_settings(path, updated)
            audit_log.log_write(path, hash_before, hash_after, bak)
        except Exception as e:
            audit_log.log_error(path, str(e))
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return

        self._refresh_hooks()
        target_idx = self._editing_index if self._editing_index is not None else len(self._hooks) - 1
        if 0 <= target_idx < self._hook_list.count():
            self._hook_list.setCurrentRow(target_idx)

        QMessageBox.information(
            self,
            "Zapisano",
            f"Hook {hook_type.value} zapisany.\nBackup: {bak.name if bak else 'brak (nowy plik)'}",
        )

    def _delete_hook(self) -> None:
        if self._editing_index is None:
            return
        path = self._current_settings_path()
        if path is None:
            return

        h = self._hooks[self._editing_index]
        hook_type = self._current_hook_type()
        matcher_label = h.matcher if h.matcher else "* (wszystkie)"
        reply = QMessageBox.question(
            self,
            "Usuń hook",
            f"Usunąć hook:\n  typ: {hook_type.value}\n  matcher: {matcher_label}\n  command: {h.command}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        hooks = list(self._hooks)
        hooks.pop(self._editing_index)

        settings = read_settings(path)
        updated = apply_hooks(settings, hook_type, hooks)

        try:
            bak, hash_before, hash_after = write_settings(path, updated)
            audit_log.log_write(path, hash_before, hash_after, bak)
        except Exception as e:
            audit_log.log_error(path, str(e))
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return

        self._refresh_hooks()

    # ------------------------------------------------------------------ Restore

    def _open_restore(self) -> None:
        path = self._current_settings_path()
        if path is None:
            QMessageBox.warning(self, "Brak pliku", "Najpierw wybierz poziom i folder projektu.")
            return
        dlg = RestoreDialog(path, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_hooks()
