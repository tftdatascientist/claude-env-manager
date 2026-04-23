"""Projektant CC panel — browse and manage project files (CLAUDE, STATUS, ARCHITECTURE, PLAN, CHANGELOG)."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QSplitter, QPlainTextEdit, QMessageBox,
    QLineEdit, QFrame, QDialog, QFormLayout, QComboBox, QDialogButtonBox,
    QStackedWidget,
)

from src.projektant.template_parser import create_from_template, read_file
from src.ui.projektant_wizard import ProjectWizardDialog, build_overrides
from src.models.history import load_history
from src.utils.paths import user_history_path
from src.utils.aliases import load_aliases
from src.utils.relocations import resolve_path

PROJECT_FILES = ["CLAUDE.md", "STATUS.md", "ARCHITECTURE.md", "PLAN.md", "CHANGELOG.md"]

_LABEL_STYLE = "color: #abb2bf; font-size: 11px; padding: 2px 0;"
_BUTTON_STYLE = (
    "QPushButton { background: #3e4451; color: #abb2bf; border: 1px solid #4b5263;"
    " border-radius: 3px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background: #4b5263; color: #e5c07b; }"
    "QPushButton:disabled { color: #5c6370; }"
)
_CREATE_STYLE = (
    "QPushButton { background: #2d4a2d; color: #98c379; border: 1px solid #3a5c3a;"
    " border-radius: 3px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background: #3a5c3a; }"
    "QPushButton:disabled { color: #5c6370; background: #1e2127; border-color: #2c313a; }"
)
_NEW_STYLE = (
    "QPushButton { background: #2d3a4a; color: #61afef; border: 1px solid #3a4a5c;"
    " border-radius: 3px; padding: 4px 10px; font-size: 11px; font-weight: bold; }"
    "QPushButton:hover { background: #3a4a5c; color: #56b6c2; }"
)
_SAVE_STYLE = (
    "QPushButton { background: #2d4a2d; color: #98c379; border: 1px solid #3a5c3a;"
    " border-radius: 3px; padding: 3px 12px; font-size: 11px; font-weight: bold; }"
    "QPushButton:hover { background: #3a5c3a; }"
)
_DISCARD_STYLE = (
    "QPushButton { background: #4a2d2d; color: #e06c75; border: 1px solid #5c3a3a;"
    " border-radius: 3px; padding: 3px 12px; font-size: 11px; }"
    "QPushButton:hover { background: #5c3a3a; }"
)


def _collect_known_projects() -> list[tuple[str, str]]:
    """Return list of (display_name, resolved_path) from CC history, deduplicated."""
    aliases = load_aliases()
    seen: dict[str, str] = {}  # path -> display name

    entries = load_history(user_history_path())
    for entry in entries:
        raw = entry.project
        if not raw:
            continue
        resolved, _ = resolve_path(raw)
        if not resolved or not Path(resolved).exists():
            continue
        if resolved not in seen:
            display = aliases.get(resolved) or aliases.get(raw) or Path(resolved).name
            seen[resolved] = display

    return [(name, path) for path, name in seen.items()]


# ---------------------------------------------------------------------------
# New Project Dialog
# ---------------------------------------------------------------------------

class NewProjectDialog(QDialog):
    """Dialog for creating a new project folder with Projektant CC structure."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nowy projekt — Projektant CC")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._result_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("np. moj-projekt")
        self._name_edit.setStyleSheet(
            "QLineEdit { background: #21252b; color: #e5c07b; border: 1px solid #3e4451;"
            " border-radius: 3px; padding: 4px 8px; font-size: 12px; }"
        )
        form.addRow("Nazwa projektu:", self._name_edit)

        self._type_edit = QLineEdit()
        self._type_edit.setPlaceholderText("np. moduł aplikacji CEM, web app, API, biblioteka...")
        self._type_edit.setStyleSheet(
            "QLineEdit { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
            " border-radius: 3px; padding: 4px 8px; font-size: 12px; }"
        )
        form.addRow("Typ projektu:", self._type_edit)

        layout.addLayout(form)

        # Parent directory selector
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(6)

        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Katalog nadrzędny (gdzie zostanie utworzony folder)...")
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setStyleSheet(
            "QLineEdit { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
            " border-radius: 3px; padding: 4px 8px; font-size: 11px; }"
        )
        dir_layout.addWidget(self._dir_edit, 1)

        btn_dir = QPushButton("Wybierz...")
        btn_dir.setStyleSheet(_BUTTON_STYLE)
        btn_dir.clicked.connect(self._browse_parent)
        dir_layout.addWidget(btn_dir)

        layout.addLayout(dir_layout)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet("color: #5c6370; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._preview_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3e4451;")
        layout.addWidget(sep)

        files_lbl = QLabel("Zostaną utworzone pliki: " + ", ".join(PROJECT_FILES))
        files_lbl.setStyleSheet("color: #5c6370; font-size: 10px;")
        files_lbl.setWordWrap(True)
        layout.addWidget(files_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Utwórz projekt")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(_NEW_STYLE)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(_BUTTON_STYLE)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_edit.textChanged.connect(self._update_preview)
        self._dir_edit.textChanged.connect(self._update_preview)

    def _browse_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wybierz katalog nadrzędny")
        if path:
            self._dir_edit.setText(path)

    def _update_preview(self) -> None:
        name = self._name_edit.text().strip()
        parent = self._dir_edit.text().strip()
        if name and parent:
            self._preview_label.setText(f"Zostanie utworzony: {parent}/{name}/")
        elif name:
            self._preview_label.setText("Wskaż katalog nadrzędny")
        else:
            self._preview_label.setText("")

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        parent = self._dir_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Błąd", "Podaj nazwę projektu.")
            return
        if not parent:
            QMessageBox.warning(self, "Błąd", "Wskaż katalog nadrzędny.")
            return

        # Sanitize folder name
        safe_name = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in name)
        dest = Path(parent) / safe_name

        if dest.exists():
            QMessageBox.warning(self, "Błąd", f"Folder już istnieje:\n{dest}")
            return

        self._result_path = dest
        self._project_name = name
        self._project_type = self._type_edit.text().strip()
        self.accept()

    @property
    def result_path(self) -> Path | None:
        return self._result_path

    @property
    def project_name(self) -> str:
        return getattr(self, "_project_name", "")

    @property
    def project_type(self) -> str:
        return getattr(self, "_project_type", "")


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class ProjectantPanel(QWidget):
    """Tab panel for Projektant CC — manage structured project files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._known_projects: list[tuple[str, str]] = []  # (display, path)
        self._current_file: Path | None = None
        self._dirty: bool = False
        self._loading: bool = False  # suppress textChanged during load
        self._setup_ui()
        self._load_known_projects()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Top bar: project selector ---
        top = QHBoxLayout()
        top.setSpacing(6)

        lbl = QLabel("Projekt:")
        lbl.setStyleSheet(_LABEL_STYLE)
        top.addWidget(lbl)

        self._project_combo = QComboBox()
        self._project_combo.setEditable(False)
        self._project_combo.setMinimumWidth(300)
        self._project_combo.setStyleSheet(
            "QComboBox { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
            " border-radius: 3px; padding: 3px 6px; font-size: 11px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background: #21252b; color: #abb2bf;"
            " selection-background-color: #3e4451; selection-color: #e5c07b; }"
        )
        self._project_combo.currentIndexChanged.connect(self._on_combo_changed)
        top.addWidget(self._project_combo, 1)

        btn_browse = QPushButton("Wskaż...")
        btn_browse.setToolTip("Wskaż dowolny katalog projektu")
        btn_browse.setStyleSheet(_BUTTON_STYLE)
        btn_browse.clicked.connect(self._browse_project)
        top.addWidget(btn_browse)

        btn_new = QPushButton("+ Nowy projekt")
        btn_new.setToolTip("Utwórz nowy folder projektu ze strukturą Projektant CC")
        btn_new.setStyleSheet(_NEW_STYLE)
        btn_new.clicked.connect(self._new_project)
        top.addWidget(btn_new)

        btn_wizard = QPushButton("Kreator...")
        btn_wizard.setToolTip("Wypełnij pliki projektu przez kreator z listami opcji")
        btn_wizard.setStyleSheet(_BUTTON_STYLE)
        btn_wizard.clicked.connect(self._open_wizard)
        top.addWidget(btn_wizard)
        self._btn_wizard = btn_wizard

        root.addLayout(top)

        # Path display
        self._path_label = QLabel()
        self._path_label.setStyleSheet("color: #5c6370; font-size: 10px; padding: 0 2px;")
        root.addWidget(self._path_label)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3e4451;")
        root.addWidget(sep)

        # --- Main splitter: file list (left) + content viewer (right) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: file list + create buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        files_lbl = QLabel("Pliki projektowe")
        files_lbl.setStyleSheet("color: #e5c07b; font-size: 11px; font-weight: bold; padding: 2px 0;")
        left_layout.addWidget(files_lbl)

        self._file_list = QListWidget()
        self._file_list.setStyleSheet(
            "QListWidget { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
            " font-size: 12px; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background: #3e4451; color: #e5c07b; }"
            "QListWidget::item:hover { background: #2c313a; }"
        )
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list, 1)

        # Create missing file buttons
        create_lbl = QLabel("Utwórz z szablonu:")
        create_lbl.setStyleSheet(_LABEL_STYLE)
        left_layout.addWidget(create_lbl)

        self._create_buttons: dict[str, QPushButton] = {}
        for fname in PROJECT_FILES:
            template = fname.replace(".md", "")
            btn = QPushButton(f"+ {fname}")
            btn.setStyleSheet(_CREATE_STYLE)
            btn.setToolTip(f"Utwórz {fname} z szablonu Projektant CC")
            btn.clicked.connect(lambda checked=False, t=template, f=fname: self._create_file(t, f))
            left_layout.addWidget(btn)
            self._create_buttons[fname] = btn

        self._btn_open_editor = QPushButton("Otwórz w edytorze")
        self._btn_open_editor.setStyleSheet(_BUTTON_STYLE)
        self._btn_open_editor.setToolTip("Otwórz wybrany plik w domyślnym edytorze systemu")
        self._btn_open_editor.clicked.connect(self._open_in_editor)
        left_layout.addWidget(self._btn_open_editor)

        splitter.addWidget(left)

        # Right: content editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Header row: filename label + dirty indicator
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        self._content_label = QLabel("Zawartość")
        self._content_label.setStyleSheet("color: #e5c07b; font-size: 11px; font-weight: bold; padding: 2px 0;")
        header_row.addWidget(self._content_label, 1)
        self._dirty_label = QLabel("● niezapisane zmiany")
        self._dirty_label.setStyleSheet("color: #e5c07b; font-size: 10px;")
        self._dirty_label.setVisible(False)
        header_row.addWidget(self._dirty_label)
        right_layout.addLayout(header_row)

        self._content_view = QPlainTextEdit()
        self._content_view.setFont(QFont("Consolas", 10))
        self._content_view.setStyleSheet(
            "QPlainTextEdit { background: #1e2127; color: #abb2bf; border: 1px solid #3e4451; }"
        )
        self._content_view.textChanged.connect(self._on_text_changed)
        right_layout.addWidget(self._content_view)

        # Save/discard bar (hidden by default)
        self._save_bar = QWidget()
        save_bar_layout = QHBoxLayout(self._save_bar)
        save_bar_layout.setContentsMargins(0, 2, 0, 0)
        save_bar_layout.setSpacing(6)
        save_bar_layout.addStretch()
        self._btn_discard = QPushButton("Odrzuć zmiany")
        self._btn_discard.setStyleSheet(_DISCARD_STYLE)
        self._btn_discard.clicked.connect(self._discard_changes)
        save_bar_layout.addWidget(self._btn_discard)
        self._btn_save = QPushButton("Zapisz")
        self._btn_save.setStyleSheet(_SAVE_STYLE)
        self._btn_save.clicked.connect(self._save_current_file)
        save_bar_layout.addWidget(self._btn_save)
        self._save_bar.setVisible(False)
        right_layout.addWidget(self._save_bar)

        splitter.addWidget(right)
        splitter.setSizes([220, 780])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(splitter, 1)

        self._refresh_ui()

    # ------------------------------------------------------------------
    # Known projects
    # ------------------------------------------------------------------

    def _load_known_projects(self) -> None:
        self._known_projects = _collect_known_projects()
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("— wybierz projekt —", None)
        for display, path in self._known_projects:
            self._project_combo.addItem(display, path)
        self._project_combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        path = self._project_combo.currentData()
        if path:
            self._set_project(Path(path))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wskaż katalog projektu")
        if path:
            self._set_project(Path(path))

    def _new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        dest = dlg.result_path
        name = dlg.project_name
        project_type = dlg.project_type

        try:
            dest.mkdir(parents=True, exist_ok=False)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się utworzyć folderu:\n{e}")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        errors = []
        for fname in PROJECT_FILES:
            template = fname.replace(".md", "")
            overrides: dict = {}

            if fname == "CLAUDE.md":
                overrides = {
                    "project": {"name": name, "type": project_type, "client": "", "repo": ""},
                }
            elif fname == "STATUS.md":
                overrides = {
                    "meta": {"project": name, "session": "1", "updated": now, "plan": "none"},
                }
            elif fname == "PLAN.md":
                overrides = {
                    "meta": {"status": "active", "goal": "", "session": "1", "updated": now},
                }

            try:
                create_from_template(template, dest / fname, overrides or None)
            except Exception as e:
                errors.append(f"{fname}: {e}")

        if errors:
            QMessageBox.warning(self, "Ostrzeżenie", "Niektóre pliki nie zostały utworzone:\n" + "\n".join(errors))

        # Add to combo and select
        display = name or dest.name
        self._project_combo.blockSignals(True)
        self._project_combo.addItem(display, str(dest))
        self._project_combo.blockSignals(False)

        self._set_project(dest)
        QMessageBox.information(self, "Projektant CC", f"Projekt '{name}' utworzony w:\n{dest}")

    def _set_project(self, path: Path) -> None:
        self._project_path = path
        self._path_label.setText(str(path))
        # Sync combo if path matches a known entry
        for i in range(self._project_combo.count()):
            if self._project_combo.itemData(i) == str(path):
                self._project_combo.blockSignals(True)
                self._project_combo.setCurrentIndex(i)
                self._project_combo.blockSignals(False)
                break
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self._file_list.clear()
        self._loading = True
        self._content_view.setPlainText("")
        self._loading = False
        self._content_label.setText("Zawartość")
        self._set_dirty(False)
        self._current_file = None

        if self._project_path is None:
            for btn in self._create_buttons.values():
                btn.setEnabled(False)
            self._btn_open_editor.setEnabled(False)
            return

        self._btn_open_editor.setEnabled(False)

        for fname in PROJECT_FILES:
            fpath = self._project_path / fname
            item = QListWidgetItem(fname)
            if fpath.exists():
                item.setForeground(Qt.GlobalColor.white)
                item.setToolTip(str(fpath))
                self._create_buttons[fname].setEnabled(False)
            else:
                item.setForeground(Qt.GlobalColor.darkGray)
                item.setToolTip(f"Plik nie istnieje — kliknij '+ {fname}' aby utworzyć")
                self._create_buttons[fname].setEnabled(True)
            self._file_list.addItem(item)

    def _on_file_selected(self, current: QListWidgetItem | None, _prev) -> None:
        # Ask about unsaved changes before switching
        if self._dirty and self._current_file is not None:
            answer = QMessageBox.question(
                self, "Niezapisane zmiany",
                f"Plik {self._current_file.name} ma niezapisane zmiany.\nZapisać przed przejściem?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                # Restore selection to previous file — block signals to avoid recursion
                self._file_list.blockSignals(True)
                for i in range(self._file_list.count()):
                    if self._file_list.item(i).text() == self._current_file.name:
                        self._file_list.setCurrentRow(i)
                        break
                self._file_list.blockSignals(False)
                return
            if answer == QMessageBox.StandardButton.Save:
                self._save_current_file()

        if current is None or self._project_path is None:
            self._loading = True
            self._content_view.setPlainText("")
            self._loading = False
            self._btn_open_editor.setEnabled(False)
            self._current_file = None
            self._set_dirty(False)
            return

        fname = current.text()
        fpath = self._project_path / fname

        if fpath.exists():
            try:
                self._loading = True
                self._content_view.setPlainText(read_file(fpath))
                self._loading = False
                self._content_label.setText(fname)
                self._current_file = fpath
                self._set_dirty(False)
                self._btn_open_editor.setEnabled(True)
                self._content_view.setReadOnly(False)
            except Exception as e:
                self._loading = True
                self._content_view.setPlainText(f"Błąd odczytu: {e}")
                self._loading = False
                self._content_view.setReadOnly(True)
                self._btn_open_editor.setEnabled(False)
                self._current_file = None
        else:
            self._loading = True
            self._content_view.setPlainText(f"Plik nie istnieje:\n{fpath}")
            self._loading = False
            self._content_view.setReadOnly(True)
            self._btn_open_editor.setEnabled(False)
            self._current_file = None
            self._set_dirty(False)

    def _on_text_changed(self) -> None:
        if not self._loading and self._current_file is not None:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._dirty_label.setVisible(dirty)
        self._save_bar.setVisible(dirty)

    def _save_current_file(self) -> None:
        if self._current_file is None:
            return
        try:
            self._current_file.write_text(self._content_view.toPlainText(), encoding="utf-8")
            self._set_dirty(False)
        except Exception as e:
            QMessageBox.critical(self, "Błąd zapisu", f"Nie udało się zapisać:\n{e}")

    def _discard_changes(self) -> None:
        if self._current_file is None:
            return
        try:
            self._loading = True
            self._content_view.setPlainText(read_file(self._current_file))
            self._loading = False
            self._set_dirty(False)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się odczytać pliku:\n{e}")

    def _create_file(self, template: str, fname: str) -> None:
        if self._project_path is None:
            return
        dest = self._project_path / fname
        if dest.exists():
            QMessageBox.information(self, "Projektant CC", f"{fname} już istnieje.")
            return
        try:
            create_from_template(template, dest)
            self._refresh_ui()
            for i in range(self._file_list.count()):
                if self._file_list.item(i).text() == fname:
                    self._file_list.setCurrentRow(i)
                    break
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się utworzyć {fname}:\n{e}")

    def _open_in_editor(self) -> None:
        current = self._file_list.currentItem()
        if current is None or self._project_path is None:
            return
        fpath = self._project_path / current.text()
        if fpath.exists():
            subprocess.Popen(["start", "", str(fpath)], shell=True)

    def _open_wizard(self) -> None:
        if self._project_path is None:
            QMessageBox.information(self, "Projektant CC", "Najpierw wskaż lub utwórz projekt.")
            return

        # Warn if any files already exist
        existing = [f for f in PROJECT_FILES if (self._project_path / f).exists()]
        if existing:
            answer = QMessageBox.question(
                self, "Kreator",
                f"Pliki już istnieją:\n{', '.join(existing)}\n\nKreator nadpisze ich zawartość. Kontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        project_name = self._project_path.name
        dlg = ProjectWizardDialog(project_name=project_name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.result_data
        if not data:
            return

        errors = []
        for fname, file_data in data.items():
            template = fname.replace(".md", "")
            dest = self._project_path / fname
            try:
                overrides = build_overrides(file_data, fname)
                create_from_template(template, dest, overrides or None)
            except Exception as e:
                errors.append(f"{fname}: {e}")

        if errors:
            QMessageBox.warning(self, "Kreator", "Błędy:\n" + "\n".join(errors))

        self._refresh_ui()
        # Select CLAUDE.md after wizard
        for i in range(self._file_list.count()):
            if self._file_list.item(i).text() == "CLAUDE.md":
                self._file_list.setCurrentRow(i)
                break

    def set_project_path(self, path: Path) -> None:
        """Programmatically set the project directory (called from other panels)."""
        self._set_project(path)
