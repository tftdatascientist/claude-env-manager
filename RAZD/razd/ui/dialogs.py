from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QMetaObject, Q_ARG, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class RazdAskUserDialog(QDialog):
    """Modal z pytaniem agenta o nieznany proces lub URL."""

    def __init__(self, subject: str, subject_type: str, question: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — nieznana aktywność")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # nagłówek
        icon_label = QLabel("🤖 Agent RAZD pyta:")
        icon_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(icon_label)

        # co wykryto
        subject_row = QHBoxLayout()
        type_label = QLabel(f"{'Proces' if subject_type == 'process' else 'URL'}:")
        type_label.setFixedWidth(60)
        subject_label = QLabel(f"<code>{subject}</code>")
        subject_label.setTextFormat(Qt.RichText)
        subject_row.addWidget(type_label)
        subject_row.addWidget(subject_label, 1)
        layout.addLayout(subject_row)

        # pytanie agenta
        q_label = QLabel(question)
        q_label.setWordWrap(True)
        q_label.setStyleSheet("color: #ccc;")
        layout.addWidget(q_label)

        # pole odpowiedzi
        self._answer_edit = QLineEdit()
        self._answer_edit.setPlaceholderText("np. Praca / Rozrywka / IDE do kodowania …")
        self._answer_edit.returnPressed.connect(self._on_accept)
        layout.addWidget(self._answer_edit)

        # przyciski
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Ignore)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self._on_ignore)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        text = self._answer_edit.text().strip()
        if text:
            self.done(QDialog.Accepted)

    def _on_ignore(self) -> None:
        self._answer_edit.setText("__ignore__")
        self.done(QDialog.Rejected)

    def answer(self) -> str:
        return self._answer_edit.text().strip() or "__ignore__"


def ask_user_blocking(subject: str, subject_type: str, question: str) -> str:
    """
    Wywoływane z wątku agenta (nie UI). Marshaluje dialog do UI thread,
    blokuje wątek agenta na threading.Event aż user odpowie (max 5 min).
    """
    app = QApplication.instance()
    if app is None:
        return "__ignore__"

    result: list[str] = []
    event = threading.Event()

    def _show_dialog() -> None:
        parent = app.activeWindow()
        dlg = RazdAskUserDialog(subject, subject_type, question, parent)
        dlg.exec()
        result.append(dlg.answer())
        event.set()

    _DialogBridge.instance().request(_show_dialog)
    event.wait(timeout=300)
    return result[0] if result else "__ignore__"


class _DialogBridge(QWidget):
    """Singleton Qt widget żyjący w UI thread — odbiera requesty z innych wątków."""

    _inst: _DialogBridge | None = None

    def __init__(self) -> None:
        super().__init__()
        self._queue: list = []

    @classmethod
    def instance(cls) -> _DialogBridge:
        if cls._inst is None:
            cls._inst = _DialogBridge()
        return cls._inst

    def request(self, fn) -> None:
        """Wołane z dowolnego wątku — fn zostanie wykonane w UI thread."""
        self._queue.append(fn)
        QMetaObject.invokeMethod(self, "_run", Qt.QueuedConnection)

    @Slot()
    def _run(self) -> None:
        if self._queue:
            fn = self._queue.pop(0)
            fn()
