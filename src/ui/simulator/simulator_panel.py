"""Glowny panel Token Simulator v2 — zakładka w MainWindow."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.simulator.engine import simulate, simulate_dual
from src.simulator.preset_scenes import PRESET_SCENES, PresetScene
from src.simulator.preset_data import PRESET_PROFILES, PRESET_SCENARIOS
from src.simulator.models import (
    DualSimResult,
    ModelTier,
    Profile,
    Scenario,
    Scene,
    SimResult,
)
from src.simulator.storage import SimulatorStorage
from src.ui.simulator.context_widget import ContextWidget
from src.ui.simulator.profile_editor import ProfileEditor
from src.ui.simulator.results_view import ResultsView

_BTN_STYLE = (
    "QPushButton { background-color: #2d2d2d; color: #cccccc; "
    "border: 1px solid #454545; border-radius: 3px; padding: 3px 10px; }"
    "QPushButton:hover { background-color: #3c3c3c; }"
)
_BTN_ACCENT = (
    "QPushButton { background-color: #007acc; color: white; "
    "border: none; border-radius: 3px; padding: 3px 12px; }"
    "QPushButton:hover { background-color: #1a8dd9; }"
)
_FONT_MONO9 = QFont("Consolas", 9)


def _btn(label: str, accent: bool = False) -> QPushButton:
    b = QPushButton(label)
    b.setFont(_FONT_MONO9)
    b.setStyleSheet(_BTN_ACCENT if accent else _BTN_STYLE)
    return b


class _StatusBar(QLabel):
    """Pasek stanu w stylu CC status bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet(
            "background-color: #007acc; color: white; padding: 3px 8px;"
        )
        self.set_idle()

    def set_idle(self) -> None:
        self.setText("Model: —  |  Ctx: —  |  Session: —  |  Cost: $0.00  |  Msgs: 0")

    def update_from(self, result: SimResult, scene_idx: int = -1) -> None:
        sr_list = result.scene_results
        if not sr_list:
            self.set_idle()
            return
        idx = scene_idx if 0 <= scene_idx < len(sr_list) else len(sr_list) - 1
        sr = sr_list[idx]
        raw = result.profile.model.value
        parts = raw.replace("claude-", "").split("-")
        model = " ".join(p.capitalize() for p in parts)
        ctx_pct = sr.ctx_pct
        cum_cost = sr.cumulative_cost_usd
        self.setText(
            f"{result.profile.name}  |  "
            f"Model: {model}  |  "
            f"Ctx: {ctx_pct:.1f}%  |  "
            f"Cost: ${cum_cost:.4f}  |  "
            f"Msg: {idx + 1}/{len(sr_list)}"
        )


class SimulatorPanel(QWidget):
    """Zakładka Token Simulator v2."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._storage = SimulatorStorage()
        self._profiles: list[Profile] = []
        self._scenarios: list[Scenario] = []
        self._current_scenario: Scenario = Scenario(name="Nowy scenariusz")
        self._profile_a: Profile = Profile(name="Profil A", color="#569cd6")
        self._profile_b: Profile = Profile(name="Profil B", color="#98c379",
                                            model=ModelTier.SONNET_4)
        self._last_dual: DualSimResult | None = None
        self._auto_sim = True

        self._sim_running = False
        self._sim_step = 0
        self._sim_result_a: SimResult | None = None
        self._sim_result_b: SimResult | None = None

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save)

        self._step_timer = QTimer()
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._sim_next_step)

        self._build_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Główny splitter pionowy: góra (profile+wyniki) | dół (scenariusze)
        main_split = QSplitter(Qt.Orientation.Vertical)

        main_split.addWidget(self._build_top_section())
        main_split.addWidget(self._build_scenario_section())
        main_split.setSizes([420, 300])

        root.addWidget(main_split, stretch=1)

    def _build_top_section(self) -> QWidget:
        """Górna połowa: profile+context (lewo) | wyniki (prawo)."""
        top = QSplitter(Qt.Orientation.Horizontal)

        top.addWidget(self._build_profiles_and_context())
        top.addWidget(self._build_results_section())
        top.setSizes([480, 520])

        return top

    def _build_profiles_and_context(self) -> QWidget:
        """Lewa strona góry: wybór profili, context widgety, status bary."""
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 4, 0)
        vbox.setSpacing(4)

        vbox.addWidget(self._build_profile_row())
        vbox.addWidget(self._build_context_row())
        vbox.addWidget(self._build_status_bar_row())

        return w

    def _build_profile_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._combo_a = QComboBox()
        self._combo_a.setFont(_FONT_MONO9)
        self._combo_a.setMinimumWidth(160)
        self._combo_a.currentIndexChanged.connect(lambda i: self._on_profile_selected("a", i))

        edit_a = _btn("Edytuj")
        edit_a.clicked.connect(lambda: self._edit_profile("a"))
        new_a = _btn("+ Nowy")
        new_a.clicked.connect(lambda: self._new_profile("a"))

        row.addWidget(QLabel("A:"))
        row.addWidget(self._combo_a)
        row.addWidget(edit_a)
        row.addWidget(new_a)

        sep = QLabel("vs")
        sep.setStyleSheet("color: #569cd6; font-weight: bold; font-size: 13px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(sep)

        self._combo_b = QComboBox()
        self._combo_b.setFont(_FONT_MONO9)
        self._combo_b.setMinimumWidth(160)
        self._combo_b.currentIndexChanged.connect(lambda i: self._on_profile_selected("b", i))

        edit_b = _btn("Edytuj")
        edit_b.clicked.connect(lambda: self._edit_profile("b"))
        new_b = _btn("+ Nowy")
        new_b.clicked.connect(lambda: self._new_profile("b"))

        row.addWidget(QLabel("B:"))
        row.addWidget(self._combo_b)
        row.addWidget(edit_b)
        row.addWidget(new_b)
        row.addStretch()

        return w

    def _build_context_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._ctx_a = ContextWidget("A")
        self._ctx_b = ContextWidget("B")

        row.addWidget(self._ctx_a)
        row.addWidget(self._ctx_b)
        return w

    def _build_status_bar_row(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._status_a = _StatusBar()
        self._status_b = _StatusBar()
        row.addWidget(self._status_a, stretch=1)
        vs = QLabel("vs")
        vs.setStyleSheet("color: #569cd6; font-weight: bold;")
        vs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(vs)
        row.addWidget(self._status_b, stretch=1)
        return w

    def _build_results_section(self) -> QWidget:
        """Prawa strona góry: panel wyników."""
        box = QGroupBox("Wyniki")
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(4, 4, 4, 4)
        self._results_view = ResultsView()
        vbox.addWidget(self._results_view)
        return box

    def _build_scenario_section(self) -> QWidget:
        """Dolna połowa: lista scenariuszy (lewo) | sceny bieżącego scenariusza (prawo)."""
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(4)

        # Pasek scenariuszy: wybór + przyciski + auto-sim + Run
        vbox.addLayout(self._build_scenario_toolbar())

        # Splitter: lista scenariuszy | sceny scenariusza
        sc_split = QSplitter(Qt.Orientation.Horizontal)
        sc_split.addWidget(self._build_scenarios_list())
        sc_split.addWidget(self._build_scene_queue())
        sc_split.setSizes([260, 500])

        vbox.addWidget(sc_split, stretch=1)
        return w

    def _build_scenario_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        row.addWidget(QLabel("Scenariusz:"))

        self._scenario_combo = QComboBox()
        self._scenario_combo.setFont(_FONT_MONO9)
        self._scenario_combo.setMinimumWidth(220)
        self._scenario_combo.currentIndexChanged.connect(self._on_scenario_selected)
        row.addWidget(self._scenario_combo)

        btn_new_sc  = _btn("Nowy")
        btn_rename  = _btn("Zmień nazwę")
        btn_del_sc  = _btn("Usuń")
        btn_new_sc.clicked.connect(self._new_scenario)
        btn_rename.clicked.connect(self._rename_scenario)
        btn_del_sc.clicked.connect(self._delete_scenario)
        row.addWidget(btn_new_sc)
        row.addWidget(btn_rename)
        row.addWidget(btn_del_sc)

        row.addSpacing(16)

        self._auto_cb = QCheckBox("Auto-simulate")
        self._auto_cb.setFont(_FONT_MONO9)
        self._auto_cb.setChecked(True)
        self._auto_cb.toggled.connect(lambda v: setattr(self, "_auto_sim", v))
        row.addWidget(self._auto_cb)

        row.addSpacing(8)
        self._run_btn = _btn("▶ Symuluj", accent=True)
        self._run_btn.clicked.connect(self._run_simulation)
        row.addWidget(self._run_btn)

        self._sim_progress_label = QLabel("  —")
        self._sim_progress_label.setFont(_FONT_MONO9)
        self._sim_progress_label.setStyleSheet("color: #569cd6;")
        row.addWidget(self._sim_progress_label)

        row.addStretch()
        return row

    def _build_scenarios_list(self) -> QWidget:
        """Lista wszystkich scenariuszy — kliknięcie przełącza bieżący."""
        box = QGroupBox("Scenariusze")
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        self._scenarios_list = QListWidget()
        self._scenarios_list.setFont(_FONT_MONO9)
        self._scenarios_list.setStyleSheet(
            "QListWidget { background-color: #1e1e1e; color: #cccccc; border: none; }"
            "QListWidget::item:selected { background-color: #094771; }"
            "QListWidget::item:hover { background-color: #2a2d2e; }"
        )
        self._scenarios_list.currentRowChanged.connect(self._on_scenario_list_changed)
        vbox.addWidget(self._scenarios_list)

        # Opis scenariusza
        self._scenario_desc_label = QLabel("")
        self._scenario_desc_label.setFont(QFont("Consolas", 8))
        self._scenario_desc_label.setWordWrap(True)
        self._scenario_desc_label.setStyleSheet("color: #808080; padding: 2px;")
        self._scenario_desc_label.setMaximumHeight(48)
        vbox.addWidget(self._scenario_desc_label)

        return box

    def _build_scene_queue(self) -> QWidget:
        """Prawa część dolna: lista scen bieżącego scenariusza + biblioteka presetów."""
        split = QSplitter(Qt.Orientation.Horizontal)

        # Kolejka scen bieżącego scenariusza
        queue_box = QGroupBox("Sceny scenariusza")
        ql = QVBoxLayout(queue_box)
        ql.setContentsMargins(4, 4, 4, 4)
        ql.setSpacing(4)

        self._queue_list = QListWidget()
        self._queue_list.setFont(_FONT_MONO9)
        self._queue_list.setStyleSheet(
            "QListWidget { background-color: #1e1e1e; color: #cccccc; border: none; }"
            "QListWidget::item:selected { background-color: #094771; }"
        )
        ql.addWidget(self._queue_list)

        queue_btns = QHBoxLayout()
        up_btn   = _btn("▲")
        down_btn = _btn("▼")
        del_btn  = _btn("✕ Usuń")
        clear_q  = _btn("Wyczyść")

        up_btn.clicked.connect(self._queue_move_up)
        down_btn.clicked.connect(self._queue_move_down)
        del_btn.clicked.connect(self._queue_delete)
        clear_q.clicked.connect(self._clear_queue)

        up_btn.setFixedWidth(32)
        down_btn.setFixedWidth(32)
        queue_btns.addWidget(up_btn)
        queue_btns.addWidget(down_btn)
        queue_btns.addWidget(del_btn)
        queue_btns.addStretch()
        queue_btns.addWidget(clear_q)
        ql.addLayout(queue_btns)

        split.addWidget(queue_box)

        # Biblioteka presetów scen — do dodawania do scenariusza
        lib_box = QGroupBox("Biblioteka scen (dodaj do scenariusza)")
        ll = QVBoxLayout(lib_box)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.setSpacing(4)

        self._library_list = QListWidget()
        self._library_list.setFont(_FONT_MONO9)
        self._library_list.setStyleSheet(
            "QListWidget { background-color: #1e1e1e; color: #cccccc; border: none; }"
            "QListWidget::item:selected { background-color: #094771; }"
            "QListWidget::item:hover { background-color: #2a2d2e; }"
        )
        self._library_list.setToolTip("Dwuklik = dodaj scenę do kolejki")
        self._library_list.itemDoubleClicked.connect(self._library_add_to_queue)
        self._library_list.currentRowChanged.connect(self._on_library_selection_changed)
        ll.addWidget(self._library_list)

        self._lib_desc_label = QLabel("")
        self._lib_desc_label.setFont(QFont("Consolas", 8))
        self._lib_desc_label.setWordWrap(True)
        self._lib_desc_label.setStyleSheet("color: #808080; padding: 2px;")
        self._lib_desc_label.setMaximumHeight(48)
        ll.addWidget(self._lib_desc_label)

        add_btn = _btn("+ Dodaj do scenariusza", accent=True)
        add_btn.clicked.connect(self._library_add_to_queue)
        ll.addWidget(add_btn)

        split.addWidget(lib_box)
        split.setSizes([340, 300])

        return split

    # ------------------------------------------------------------------
    # Ladowanie / zapis danych
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        state = self._storage.load()
        loaded_profiles  = state.get("profiles", [])
        loaded_scenarios = state.get("scenarios", [])

        if loaded_profiles:
            self._profiles = loaded_profiles
        else:
            self._profiles = [copy.deepcopy(p) for p in PRESET_PROFILES]

        self._profile_a = copy.deepcopy(self._profiles[0])
        self._profile_b = copy.deepcopy(self._profiles[min(2, len(self._profiles) - 1)])

        preset_ids = {sc.id for sc in PRESET_SCENARIOS}
        preset_map = {sc.id: copy.deepcopy(sc) for sc in PRESET_SCENARIOS}

        for sc in loaded_scenarios:
            if sc.id in preset_map:
                preset_map[sc.id] = sc

        merged = [preset_map[sc.id] for sc in PRESET_SCENARIOS]
        user_custom = [sc for sc in loaded_scenarios if sc.id not in preset_ids]
        self._scenarios = merged + user_custom

        self._current_scenario = copy.deepcopy(self._scenarios[0])

        self._refresh_profile_combos()
        self._refresh_scenario_combo()
        self._refresh_scenarios_list()
        self._refresh_queue()
        self._refresh_library()
        self._ctx_a.update_state(self._profile_a, None)
        self._ctx_b.update_state(self._profile_b, None)

    def _schedule_save(self) -> None:
        self._save_timer.start(500)

    def _save(self) -> None:
        self._sync_current_scenario()
        self._storage.save(
            profiles=self._profiles,
            scenes=[],
            scenarios=self._scenarios,
        )

    def _sync_current_scenario(self) -> None:
        for i, sc in enumerate(self._scenarios):
            if sc.id == self._current_scenario.id:
                self._scenarios[i] = copy.deepcopy(self._current_scenario)
                return
        self._scenarios.append(copy.deepcopy(self._current_scenario))

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def _refresh_profile_combos(self) -> None:
        for combo in (self._combo_a, self._combo_b):
            combo.blockSignals(True)
            combo.clear()
            for p in self._profiles:
                combo.addItem(p.name, p.id)
            combo.blockSignals(False)

        idx_a = next((i for i, p in enumerate(self._profiles) if p.id == self._profile_a.id), 0)
        idx_b = next((i for i, p in enumerate(self._profiles) if p.id == self._profile_b.id),
                     min(1, len(self._profiles) - 1))
        self._combo_a.setCurrentIndex(idx_a)
        self._combo_b.setCurrentIndex(idx_b)

    def _on_profile_selected(self, which: str, index: int) -> None:
        if index < 0 or index >= len(self._profiles):
            return
        profile_copy = copy.deepcopy(self._profiles[index])
        if which == "a":
            self._profile_a = profile_copy
            self._ctx_a.update_state(self._profile_a, None)
            self._status_a.set_idle()
        else:
            self._profile_b = profile_copy
            self._ctx_b.update_state(self._profile_b, None)
            self._status_b.set_idle()
        if self._auto_sim and self._current_scenario.scenes:
            self._run_simulation()

    def _edit_profile(self, which: str) -> None:
        profile = self._profile_a if which == "a" else self._profile_b
        dlg = ProfileEditor(profile=copy.deepcopy(profile), parent=self)
        if dlg.exec():
            updated = dlg.get_profile()
            if which == "a":
                self._profile_a = updated
            else:
                self._profile_b = updated
            for i, p in enumerate(self._profiles):
                if p.id == updated.id:
                    self._profiles[i] = copy.deepcopy(updated)
                    break
            self._refresh_profile_combos()
            self._ctx_a.update_state(self._profile_a, None)
            self._ctx_b.update_state(self._profile_b, None)
            self._schedule_save()
            if self._auto_sim and self._current_scenario.scenes:
                self._run_simulation()

    def _new_profile(self, which: str) -> None:
        base = Profile(name=f"Profil {len(self._profiles) + 1}")
        dlg = ProfileEditor(profile=base, parent=self)
        if dlg.exec():
            new_p = dlg.get_profile()
            self._profiles.append(new_p)
            self._refresh_profile_combos()
            new_idx = len(self._profiles) - 1
            if which == "a":
                self._combo_a.setCurrentIndex(new_idx)
            else:
                self._combo_b.setCurrentIndex(new_idx)
            self._schedule_save()

    # ------------------------------------------------------------------
    # Scenariusze
    # ------------------------------------------------------------------

    def _refresh_scenario_combo(self) -> None:
        self._scenario_combo.blockSignals(True)
        self._scenario_combo.clear()
        for sc in self._scenarios:
            self._scenario_combo.addItem(sc.name, sc.id)
        idx = next((i for i, sc in enumerate(self._scenarios)
                    if sc.id == self._current_scenario.id), 0)
        self._scenario_combo.setCurrentIndex(idx)
        self._scenario_combo.blockSignals(False)

    def _refresh_scenarios_list(self) -> None:
        """Odświeża lewą listę scenariuszy."""
        self._scenarios_list.blockSignals(True)
        self._scenarios_list.clear()
        for sc in self._scenarios:
            n = len(sc.scenes)
            item = QListWidgetItem(f"{sc.name}  [{n} scen]")
            item.setData(Qt.ItemDataRole.UserRole, sc.id)
            self._scenarios_list.addItem(item)
        # Zaznacz bieżący
        idx = next((i for i, sc in enumerate(self._scenarios)
                    if sc.id == self._current_scenario.id), 0)
        self._scenarios_list.setCurrentRow(idx)
        self._scenarios_list.blockSignals(False)

    def _on_scenario_list_changed(self, row: int) -> None:
        """Kliknięcie na listę scenariuszy przełącza bieżący scenariusz."""
        if row < 0 or row >= len(self._scenarios):
            return
        if self._scenarios[row].id == self._current_scenario.id:
            return
        self._sync_current_scenario()
        self._current_scenario = copy.deepcopy(self._scenarios[row])
        # Synchronizuj combo
        self._scenario_combo.blockSignals(True)
        self._scenario_combo.setCurrentIndex(row)
        self._scenario_combo.blockSignals(False)
        self._refresh_queue()
        self._update_scenario_desc(row)
        if self._auto_sim and self._current_scenario.scenes:
            self._run_simulation()

    def _on_scenario_selected(self, index: int) -> None:
        """Combo scenariuszy — synchronizuje listę."""
        if index < 0 or index >= len(self._scenarios):
            return
        self._sync_current_scenario()
        self._current_scenario = copy.deepcopy(self._scenarios[index])
        self._scenarios_list.blockSignals(True)
        self._scenarios_list.setCurrentRow(index)
        self._scenarios_list.blockSignals(False)
        self._refresh_queue()
        self._update_scenario_desc(index)
        if self._auto_sim and self._current_scenario.scenes:
            self._run_simulation()

    def _update_scenario_desc(self, index: int) -> None:
        if index < 0 or index >= len(self._scenarios):
            self._scenario_desc_label.setText("")
            return
        sc = self._scenarios[index]
        n = len(sc.scenes)
        names = ", ".join(s.name for s in sc.scenes[:4])
        if n > 4:
            names += f" +{n - 4}"
        self._scenario_desc_label.setText(f"{n} scen: {names}" if names else "Brak scen")

    def _new_scenario(self) -> None:
        name, ok = QInputDialog.getText(self, "Nowy scenariusz", "Nazwa:")
        if not ok or not name.strip():
            return
        sc = Scenario(name=name.strip())
        self._sync_current_scenario()
        self._scenarios.append(sc)
        self._current_scenario = copy.deepcopy(sc)
        self._refresh_scenario_combo()
        self._refresh_scenarios_list()
        self._refresh_queue()
        self._schedule_save()

    def _rename_scenario(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Zmień nazwę scenariusza", "Nowa nazwa:", text=self._current_scenario.name
        )
        if not ok or not name.strip():
            return
        self._current_scenario.name = name.strip()
        self._sync_current_scenario()
        self._refresh_scenario_combo()
        self._refresh_scenarios_list()
        self._schedule_save()

    def _delete_scenario(self) -> None:
        if len(self._scenarios) <= 1:
            QMessageBox.information(self, "Simulator", "Nie można usunąć ostatniego scenariusza.")
            return
        idx = self._scenario_combo.currentIndex()
        if idx < 0:
            return
        self._scenarios.pop(idx)
        self._current_scenario = copy.deepcopy(self._scenarios[max(0, idx - 1)])
        self._refresh_scenario_combo()
        self._refresh_scenarios_list()
        self._refresh_queue()
        self._schedule_save()

    # ------------------------------------------------------------------
    # Kolejka scen
    # ------------------------------------------------------------------

    def _refresh_queue(self) -> None:
        self._queue_list.clear()
        for i, scene in enumerate(self._current_scenario.scenes):
            n_act = len(scene.activities)
            act_summary = ", ".join(
                f"{a.activity_id}×{a.count}" for a in scene.activities[:3]
            )
            if n_act > 3:
                act_summary += f" +{n_act - 3}"
            text = (
                f"#{i + 1}  {scene.name}  "
                f"[u:{scene.user_message_tokens} r:{scene.assistant_response_tokens}]"
            )
            if act_summary:
                text += f"  {act_summary}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._queue_list.addItem(item)

    def _queue_move_up(self) -> None:
        row = self._queue_list.currentRow()
        if row <= 0:
            return
        scenes = self._current_scenario.scenes
        scenes[row - 1], scenes[row] = scenes[row], scenes[row - 1]
        self._refresh_queue()
        self._queue_list.setCurrentRow(row - 1)
        self._schedule_save()

    def _queue_move_down(self) -> None:
        row = self._queue_list.currentRow()
        scenes = self._current_scenario.scenes
        if row < 0 or row >= len(scenes) - 1:
            return
        scenes[row], scenes[row + 1] = scenes[row + 1], scenes[row]
        self._refresh_queue()
        self._queue_list.setCurrentRow(row + 1)
        self._schedule_save()

    def _queue_delete(self) -> None:
        row = self._queue_list.currentRow()
        if row < 0:
            return
        self._current_scenario.scenes.pop(row)
        self._refresh_queue()
        self._refresh_scenarios_list()
        self._schedule_save()
        if self._auto_sim and self._current_scenario.scenes:
            self._run_simulation()

    def _clear_queue(self) -> None:
        self._current_scenario.scenes.clear()
        self._refresh_queue()
        self._refresh_scenarios_list()
        self._results_view.clear()
        self._ctx_a.update_state(self._profile_a, None)
        self._ctx_b.update_state(self._profile_b, None)
        self._status_a.set_idle()
        self._status_b.set_idle()
        self._schedule_save()

    # ------------------------------------------------------------------
    # Biblioteka scen (presety)
    # ------------------------------------------------------------------

    def _refresh_library(self) -> None:
        self._library_list.clear()
        for preset in PRESET_SCENES:
            item = QListWidgetItem(preset.label)
            item.setForeground(QColor("#b5cea8"))
            item.setData(Qt.ItemDataRole.UserRole, preset.key)
            item.setToolTip(preset.description)
            self._library_list.addItem(item)

    def _on_library_selection_changed(self, row: int) -> None:
        item = self._library_list.item(row)
        if item is None:
            self._lib_desc_label.setText("")
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        preset = next((p for p in PRESET_SCENES if p.key == key), None)
        if preset:
            s = preset.scene_template
            acts = ", ".join(f"{a.activity_id}×{a.count}" for a in s.activities) or "—"
            self._lib_desc_label.setText(
                f"{preset.description}\n"
                f"[u:{s.user_message_tokens} r:{s.assistant_response_tokens}  {acts}]"
            )
        else:
            self._lib_desc_label.setText("")

    def _library_add_to_queue(self) -> None:
        item = self._library_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        preset = next((p for p in PRESET_SCENES if p.key == key), None)
        if preset is None:
            return
        scene = preset.instantiate()
        self._current_scenario.scenes.append(scene)
        self._refresh_queue()
        self._refresh_scenarios_list()
        self._schedule_save()
        if self._auto_sim:
            self._run_simulation()

    # ------------------------------------------------------------------
    # Symulacja — animacja krokowa
    # ------------------------------------------------------------------

    def _run_simulation(self) -> None:
        if not self._current_scenario.scenes:
            return
        if self._sim_running:
            self._step_timer.stop()
            self._sim_finish()
            return

        result_a = simulate(self._profile_a, self._current_scenario)
        result_b = simulate(self._profile_b, self._current_scenario)
        self._sim_result_a = result_a
        self._sim_result_b = result_b
        self._last_dual = DualSimResult(result_a=result_a, result_b=result_b)

        self._sim_running = True
        self._sim_step = 0
        self._results_view.clear()
        self._run_btn.setText("⏹ Stop")

        self._sim_next_step()

    def _sim_next_step(self) -> None:
        if not self._sim_running:
            return

        n = len(self._current_scenario.scenes)
        step = self._sim_step

        if step >= n:
            self._sim_finish()
            return

        result_a = self._sim_result_a
        result_b = self._sim_result_b

        self._results_view.show_step(self._last_dual, step)
        self._queue_list.setCurrentRow(step)

        self._ctx_a.update_state(self._profile_a, result_a, step)
        self._ctx_b.update_state(self._profile_b, result_b, step)
        self._status_a.update_from(result_a, step)
        self._status_b.update_from(result_b, step)

        dots = "." * ((step % 3) + 1) + "   "[:3 - (step % 3)]
        self._sim_progress_label.setText(f"  Symulacja{dots}  scena {step + 1}/{n}")

        self._sim_step += 1
        if self._sim_step < n:
            self._step_timer.start(1000)
        else:
            self._step_timer.start(400)

    def _sim_finish(self) -> None:
        self._sim_running = False
        self._step_timer.stop()
        self._run_btn.setText("▶ Symuluj")
        self._queue_list.setCurrentRow(-1)

        if self._last_dual is None:
            return

        self._results_view.show_dual(self._last_dual)
        self._ctx_a.update_state(self._profile_a, self._last_dual.result_a)
        self._ctx_b.update_state(self._profile_b, self._last_dual.result_b)
        self._status_a.update_from(self._last_dual.result_a)
        self._status_b.update_from(self._last_dual.result_b)

        n = len(self._current_scenario.scenes)
        winner = self._last_dual.winner
        savings = self._last_dual.savings_usd
        self._sim_progress_label.setText(
            f"  Gotowe — {n} scen  |  Winner: {winner}  |  "
            f"Oszczednosc: ${savings:.4f}"
        )
