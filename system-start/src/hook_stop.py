"""
Hook Stop — uruchamiany przez Claude Code po zakończeniu sesji.
Zapisuje 1-linijkowy handoff do PLAN/session_log.
Wywołanie: python src/hook_stop.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.controller import read_current, append_rotating
from src.logger import get_logger
from datetime import datetime

_log = get_logger("hook_stop")


def main() -> None:
    current = read_current()
    task = current.get("task", "brak aktywnego zadania")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- {ts} | HANDOFF: sesja zamknieta, ostatnie current='{task}'"
    append_rotating("session_log", entry, max=10)
    _log.info("hook_stop: sesja zamknieta | current='%s'", task)
    print(entry)


if __name__ == "__main__":
    main()
