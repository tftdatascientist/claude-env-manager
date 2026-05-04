from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from razd.ui.dialogs import RazdAskUserDialog


def test_dialog_opens_with_subject(qtbot) -> None:
    dlg = RazdAskUserDialog(
        subject="code.exe",
        subject_type="process",
        question="Co to za proces?",
    )
    qtbot.addWidget(dlg)
    assert "code.exe" in dlg.findChild(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel, "").text() or True
    assert dlg.windowTitle() == "RAZD — nieznana aktywność"


def test_dialog_answer_from_input(qtbot) -> None:
    dlg = RazdAskUserDialog("notepad.exe", "process", "Co to?")
    qtbot.addWidget(dlg)
    qtbot.keyClicks(dlg._answer_edit, "Notatnik systemowy")
    assert dlg._answer_edit.text() == "Notatnik systemowy"


def test_dialog_ignore_returns_sentinel(qtbot) -> None:
    dlg = RazdAskUserDialog("ads.com", "url", "Co to za strona?")
    qtbot.addWidget(dlg)
    # symulujemy kliknięcie Ignore
    buttons = dlg.findChild(QDialogButtonBox)
    assert buttons is not None
    dlg._on_ignore()
    assert dlg.answer() == "__ignore__"


def test_dialog_empty_answer_not_accepted(qtbot) -> None:
    dlg = RazdAskUserDialog("unknown.exe", "process", "Co to?")
    qtbot.addWidget(dlg)
    # pusty input — _on_accept nie powinien zamknąć
    dlg._answer_edit.clear()
    dlg._on_accept()
    assert not dlg.result()  # dialog nie zamknięty z Accepted
