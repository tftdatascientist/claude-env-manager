"""Dialog edycji profilu konfiguracji CC."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from src.simulator.models import ModelTier, Profile


class ProfileEditor(QDialog):
    """Dialog pozwalajacy edytowac wszystkie pola profilu."""

    def __init__(self, profile: Profile | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edytuj profil")
        self.setMinimumWidth(440)
        self.setModal(True)

        self._profile = profile or Profile()
        self._color = self._profile.color
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        form_layout = QVBoxLayout(inner)
        form_layout.setSpacing(10)
        scroll_area.setWidget(inner)
        root.addWidget(scroll_area)

        font_mono = QFont("Consolas", 9)

        # --- Podstawowe ---
        grp_basic = QGroupBox("Podstawowe")
        fl = QFormLayout(grp_basic)
        self._name_edit = QLineEdit()
        fl.addRow("Nazwa:", self._name_edit)

        self._model_combo = QComboBox()
        for tier in ModelTier:
            self._model_combo.addItem(tier.value, tier)
        fl.addRow("Model:", self._model_combo)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(32, 20)
        self._color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        fl.addRow("Kolor:", color_row)
        form_layout.addWidget(grp_basic)

        # --- Tokeny ---
        grp_tokens = QGroupBox("Tokeny (MVP — wpisywane recznie)")
        tl = QFormLayout(grp_tokens)
        self._sys_prompt  = self._spinbox(0, 200_000)
        self._sys_tools   = self._spinbox(0, 200_000)
        self._skills      = self._spinbox(0, 200_000)
        self._mcp         = self._spinbox(0, 200_000)
        self._plugins     = self._spinbox(0, 200_000)
        self._memory      = self._spinbox(0, 200_000)
        tl.addRow("System prompt:", self._sys_prompt)
        tl.addRow("System tools:", self._sys_tools)
        tl.addRow("Skills (suma) ℹ:", self._skills)
        tl.addRow("MCP (suma) ℹ:", self._mcp)
        tl.addRow("Plugins (suma) ℹ:", self._plugins)
        tl.addRow("Memory files:", self._memory)
        todo_note = QLabel("ℹ Breakdown per-komponent — wkrótce")
        todo_note.setStyleSheet("color: #ce9178; font-size: 10px;")
        tl.addRow("", todo_note)
        form_layout.addWidget(grp_tokens)

        # --- CLAUDE.md ---
        grp_md = QGroupBox("CLAUDE.md")
        ml = QFormLayout(grp_md)
        self._global_md   = self._spinbox(0, 5000)
        self._project_md  = self._spinbox(0, 5000)
        self._line_ratio  = self._dspinbox(1.0, 50.0, 0.5, 1)
        ml.addRow("Global linie:", self._global_md)
        ml.addRow("Project linie:", self._project_md)
        ml.addRow("Linia → tokeny:", self._line_ratio)
        form_layout.addWidget(grp_md)

        # --- Parametry symulacji ---
        grp_sim = QGroupBox("Parametry symulacji")
        sl = QFormLayout(grp_sim)
        self._cache_rate      = self._dspinbox(0.0, 1.0, 0.05, 2)
        self._ctx_limit       = self._spinbox(10_000, 2_000_000, step=10_000)
        self._autocompact_thr = self._dspinbox(0.50, 1.0, 0.01, 2)
        sl.addRow("Cache hit rate:", self._cache_rate)
        sl.addRow("Ctx limit:", self._ctx_limit)
        sl.addRow("Autocompact threshold:", self._autocompact_thr)
        form_layout.addWidget(grp_sim)

        form_layout.addStretch()

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._update_color_btn()

    @staticmethod
    def _spinbox(min_v: int, max_v: int, step: int = 100) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(min_v, max_v)
        sb.setSingleStep(step)
        sb.setFont(QFont("Consolas", 9))
        return sb

    @staticmethod
    def _dspinbox(min_v: float, max_v: float, step: float, decimals: int) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        sb.setFont(QFont("Consolas", 9))
        return sb

    def _populate(self) -> None:
        p = self._profile
        self._name_edit.setText(p.name)
        idx = self._model_combo.findData(p.model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._sys_prompt.setValue(p.system_prompt_tokens)
        self._sys_tools.setValue(p.system_tools_tokens)
        self._skills.setValue(p.skills_tokens)
        self._mcp.setValue(p.mcp_tokens)
        self._plugins.setValue(p.plugins_tokens)
        self._memory.setValue(p.memory_tokens)
        self._global_md.setValue(p.global_claude_md_lines)
        self._project_md.setValue(p.project_claude_md_lines)
        self._line_ratio.setValue(p.line_token_ratio)
        self._cache_rate.setValue(p.cache_hit_rate)
        self._ctx_limit.setValue(p.ctx_limit)
        self._autocompact_thr.setValue(p.autocompact_threshold)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Wybierz kolor profilu")
        if color.isValid():
            self._color = color.name()
            self._update_color_btn()

    def _update_color_btn(self) -> None:
        self._color_btn.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #555;"
        )

    def _accept(self) -> None:
        p = self._profile
        p.name                    = self._name_edit.text().strip() or "Profil"
        p.model                   = self._model_combo.currentData()
        p.color                   = self._color
        p.system_prompt_tokens    = self._sys_prompt.value()
        p.system_tools_tokens     = self._sys_tools.value()
        p.skills_tokens           = self._skills.value()
        p.mcp_tokens              = self._mcp.value()
        p.plugins_tokens          = self._plugins.value()
        p.memory_tokens           = self._memory.value()
        p.global_claude_md_lines  = self._global_md.value()
        p.project_claude_md_lines = self._project_md.value()
        p.line_token_ratio        = self._line_ratio.value()
        p.cache_hit_rate          = self._cache_rate.value()
        p.ctx_limit               = self._ctx_limit.value()
        p.autocompact_threshold   = self._autocompact_thr.value()
        self.accept()

    def get_profile(self) -> Profile:
        return self._profile
