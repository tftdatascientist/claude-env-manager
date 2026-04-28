from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from razd.ui.main_window import RazdMainWindow


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RAZD")
    app.setStyle("Fusion")

    window = RazdMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
