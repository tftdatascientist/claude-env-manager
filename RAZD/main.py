from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from razd.ui.main_window import RazdMainWindow


def _load_dotenv() -> None:
    """Wczytuje zmienne z .env jeśli plik istnieje (bez zewnętrznych zależności)."""
    import os
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    _load_dotenv()
    minimized = "--minimized" in sys.argv

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RAZD")
    app.setStyle("Fusion")
    # nie zamykaj aplikacji gdy okno jest ukryte — tray ma trzymać ją przy życiu
    app.setQuitOnLastWindowClosed(False)

    window = RazdMainWindow()
    if minimized:
        window.start_minimized()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
