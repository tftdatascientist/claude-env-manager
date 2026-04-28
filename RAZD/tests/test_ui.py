from __future__ import annotations

import pytest

from razd.ui.main_window import RazdMainWindow


def test_main_window_opens(qtbot):
    window = RazdMainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()


def test_tabs_count(qtbot):
    window = RazdMainWindow()
    qtbot.addWidget(window)
    tabs = window.centralWidget()
    assert tabs.count() == 2
    assert tabs.tabText(0) == "Time Tracking"
    assert tabs.tabText(1) == "Focus Timer"
