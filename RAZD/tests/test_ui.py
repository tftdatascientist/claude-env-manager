from __future__ import annotations

from unittest.mock import MagicMock, patch

from razd.ui.main_window import RazdMainWindow


def test_main_window_opens(qtbot):
    with patch("razd.ui.main_window.RazdAgentThread") as mock_agent_cls:
        mock_agent = MagicMock()
        mock_agent.isRunning.return_value = False
        mock_agent_cls.return_value = mock_agent

        window = RazdMainWindow()
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()


def test_tabs_count(qtbot):
    with patch("razd.ui.main_window.RazdAgentThread") as mock_agent_cls:
        mock_agent = MagicMock()
        mock_agent.isRunning.return_value = False
        mock_agent_cls.return_value = mock_agent

        window = RazdMainWindow()
        qtbot.addWidget(window)
        tabs = window.centralWidget()
        assert tabs.count() == 2
        assert tabs.tabText(0) == "Time Tracking"
        assert tabs.tabText(1) == "Focus Timer"
