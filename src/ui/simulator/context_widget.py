"""Widget /context — pasek procentowy + breakdown kategorii tokenow."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.simulator.models import Profile, SimResult


class _ProgressBar(QWidget):
    """Prosty pasek procentowy w stylu terminal."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(14)
        self._pct = 0.0

    def set_pct(self, pct: float) -> None:
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        filled = int(w * self._pct / 100)

        # tlo
        p.fillRect(0, 0, w, h, QColor("#3c3c3c"))
        # wypelnienie
        color = "#569cd6" if self._pct < 80 else ("#ce9178" if self._pct < 95 else "#f44747")
        p.fillRect(0, 0, filled, h, QColor(color))


class ContextWidget(QWidget):
    """
    Wyswietla breakdown tokenow profilu w stylu /context z CC.
    Aktualizuje sie po kazdej scenie symulacji.
    """

    _CATEGORIES = [
        ("system_prompt_tokens", "System prompt", "#569cd6"),
        ("system_tools_tokens",  "System tools",  "#569cd6"),
        ("memory_tokens",        "Memory files",  "#c678dd"),
        ("skills_tokens",        "Skills",        "#56b6c2"),
        ("mcp_tokens",           "MCP",           "#98c379"),
    ]

    def __init__(self, label: str = "Profile", parent=None) -> None:
        super().__init__(parent)
        self._label = label
        self._profile: Profile | None = None
        self._result: SimResult | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        font_mono = QFont("Consolas", 9)

        title = QLabel(f" Context Usage — {self._label}")
        title.setFont(QFont("Consolas", 9))
        title.setStyleSheet("color: #569cd6;")
        layout.addWidget(title)

        self._bar = _ProgressBar()
        layout.addWidget(self._bar)

        self._pct_label = QLabel(" 0.0%  of 200k ctx window")
        self._pct_label.setFont(font_mono)
        self._pct_label.setStyleSheet("color: #b5cea8;")
        layout.addWidget(self._pct_label)

        sep = QLabel("  Estimated usage by category")
        sep.setFont(font_mono)
        sep.setStyleSheet("color: #569cd6;")
        layout.addWidget(sep)

        self._cat_labels: dict[str, QLabel] = {}
        for key, name, color in self._CATEGORIES:
            lbl = QLabel()
            lbl.setFont(font_mono)
            layout.addWidget(lbl)
            self._cat_labels[key] = lbl

        self._msg_label = QLabel()
        self._msg_label.setFont(font_mono)
        layout.addWidget(self._msg_label)

        self._free_label = QLabel()
        self._free_label.setFont(font_mono)
        layout.addWidget(self._free_label)

        self._compact_label = QLabel()
        self._compact_label.setFont(font_mono)
        layout.addWidget(self._compact_label)

        layout.addStretch()
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333333;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._render_profile(None, None)

    def update_state(self, profile: Profile, result: SimResult | None, scene_idx: int = -1) -> None:
        """Odswierza widget po zasymulowaniu sceny scene_idx (domyslnie ostatnia)."""
        self._profile = profile
        self._result = result
        self._render_profile(profile, result, scene_idx)

    def _render_profile(self, profile: Profile | None, result: SimResult | None, scene_idx: int = -1) -> None:
        if profile is None:
            self._bar.set_pct(0)
            self._pct_label.setText("  —")
            for lbl in self._cat_labels.values():
                lbl.setText("")
            self._msg_label.setText("")
            self._free_label.setText("")
            self._compact_label.setText("")
            return

        ctx_limit = profile.ctx_limit
        sr = None
        if result and result.scene_results:
            idx = scene_idx if (0 <= scene_idx < len(result.scene_results)) else len(result.scene_results) - 1
            sr = result.scene_results[idx]

        history_tok = sr.history_tokens if sr else 0
        total_ctx   = sr.total_ctx_tokens if sr else profile.static_overhead
        ctx_pct     = total_ctx / ctx_limit * 100

        self._bar.set_pct(ctx_pct)
        self._pct_label.setText(f"  {ctx_pct:.1f}%  of {ctx_limit // 1000}k ctx window")
        color = "#b5cea8" if ctx_pct < 80 else ("#ce9178" if ctx_pct < 95 else "#f44747")
        self._pct_label.setStyleSheet(f"color: {color};")

        def fmt(tok: int, limit: int) -> tuple[str, str]:
            k = tok / 1000
            pct = tok / limit * 100
            k_str = f"{k:.1f}k" if k >= 1 else str(tok)
            return k_str, f"{pct:.1f}%"

        for key, name, cat_color in self._CATEGORIES:
            tok = getattr(profile, key, 0)
            k_str, p_str = fmt(tok, ctx_limit)
            lbl = self._cat_labels[key]
            lbl.setText(f"  ● {name:<18} {k_str:>6}  ({p_str})")
            lbl.setStyleSheet(f"color: {cat_color};")

        # claude.md + historia = messages
        msg_tok = history_tok + profile.claude_md_tokens
        k_str, p_str = fmt(msg_tok, ctx_limit)
        self._msg_label.setText(f"  ● {'Messages':<18} {k_str:>6}  ({p_str})")
        self._msg_label.setStyleSheet("color: #cccccc;")

        free = max(0, ctx_limit - total_ctx)
        k_str, p_str = fmt(free, ctx_limit)
        self._free_label.setText(f"  □ {'Free space':<18} {k_str:>6}  ({p_str})")
        self._free_label.setStyleSheet("color: #808080;")

        compact_tok = 33_000
        k_str2, p_str2 = fmt(compact_tok, ctx_limit)
        ac_label = "Autocompact" + (" ⚡" if (sr and sr.autocompact_fired) else "")
        self._compact_label.setText(f"  ⊠ {ac_label:<18} {k_str2:>6}  ({p_str2})")
        style = "color: #ce9178;" if (sr and sr.autocompact_fired) else "color: #555555;"
        self._compact_label.setStyleSheet(style)
