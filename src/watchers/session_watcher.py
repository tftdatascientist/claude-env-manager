"""Polling stanu sesji CC z plików state.{id}.json co-panel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass
class TerminalSnapshot:
    """Snapshot stanu jednej sesji CC.

    Args:
        slot_id: Numer slotu (1–4).
        phase: Faza sesji ('working', 'waiting') lub None.
        last_message: Ostatnia wiadomość asystenta (max 500 znaków).
        last_message_at: Czas ostatniej wiadomości lub None.
        phase_changed_at: Czas ostatniej zmiany fazy lub None.
        transcript_path: Ścieżka do transkryptu JSONL lub None.
        model: Model CC (opcjonalne).
        cost_usd: Koszt sesji w USD (opcjonalne).
        ctx_pct: Procent wykorzystania kontekstu (opcjonalne).
        session_id: ID sesji (opcjonalne).
        seconds_since_change: Sekundy od ostatniej zmiany fazy.
        is_file_missing: True jeśli plik state.json nie istnieje.
    """

    slot_id: int
    phase: Optional[str] = None
    last_message: str = ""
    last_message_at: Optional[datetime] = None
    phase_changed_at: Optional[datetime] = None
    transcript_path: Optional[str] = None
    model: Optional[str] = None
    cost_usd: Optional[float] = None
    ctx_pct: Optional[float] = None
    session_id: Optional[str] = None
    seconds_since_change: int = 0
    is_file_missing: bool = True


class SessionWatcher(QObject):
    """Obserwuje stan 4 sesji CC przez polling plików state.{id}.json.

    Args:
        parent: Rodzic Qt.
        interval_ms: Interwał pollingu w milisekundach (domyślnie 15 000).
    """

    snapshot_updated = Signal(object)    # TerminalSnapshot
    all_snapshots_updated = Signal(object)  # list[TerminalSnapshot]

    _CC_PANEL_DIR = Path.home() / ".claude" / "cc-panel"

    def __init__(
        self,
        parent: QObject | None = None,
        interval_ms: int = 15_000,
    ) -> None:
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._snapshots: list[TerminalSnapshot] = [
            TerminalSnapshot(slot_id=i) for i in range(1, 5)
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_all)

    def start(self) -> None:
        """Uruchamia polling — natychmiastowy odczyt i start timera."""
        self._poll_all()
        self._timer.start(self._interval_ms)

    def stop(self) -> None:
        """Zatrzymuje polling."""
        self._timer.stop()

    def force_refresh(self) -> None:
        """Wymusza natychmiastowy odczyt wszystkich slotów."""
        self._poll_all()

    def get_snapshot(self, slot_id: int) -> TerminalSnapshot:
        """Zwraca ostatni snapshot dla danego slotu.

        Args:
            slot_id: Numer slotu (1–4).

        Returns:
            Ostatni znany snapshot.
        """
        return self._snapshots[slot_id - 1]

    def _poll_all(self) -> None:
        updated: list[TerminalSnapshot] = []
        for slot_id in range(1, 5):
            snap = self._read_state(slot_id)
            self._snapshots[slot_id - 1] = snap
            self.snapshot_updated.emit(snap)
            updated.append(snap)
        self.all_snapshots_updated.emit(updated)

    def _read_state(self, slot_id: int) -> TerminalSnapshot:
        path = self._CC_PANEL_DIR / f"state.{slot_id}.json"
        if not path.exists():
            return TerminalSnapshot(slot_id=slot_id, is_file_missing=True)
        try:
            data: dict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return TerminalSnapshot(slot_id=slot_id, is_file_missing=True)

        phase_changed_at = _parse_iso(data.get("phase_changed_at"))
        seconds_since = 0
        if phase_changed_at:
            delta = datetime.now(timezone.utc) - phase_changed_at
            seconds_since = max(0, int(delta.total_seconds()))

        cost_usd = data.get("cost_usd")
        transcript_path = data.get("transcript_path")

        # Transkrypt jest źródłem prawdy dla model i ctx_pct.
        # state.json używamy tylko jako fallback gdy brak transkryptu.
        model: Optional[str] = None
        ctx_pct: Optional[float] = None
        if transcript_path:
            model, ctx_pct = _read_metrics_from_transcript(transcript_path)
        if model is None:
            model = data.get("model")
        if ctx_pct is None:
            ctx_pct = data.get("ctx_pct")

        return TerminalSnapshot(
            slot_id=slot_id,
            phase=data.get("phase"),
            last_message=str(data.get("last_message", ""))[:500],
            last_message_at=_parse_iso(data.get("last_message_at")),
            phase_changed_at=phase_changed_at,
            transcript_path=transcript_path,
            model=model,
            cost_usd=cost_usd,
            ctx_pct=ctx_pct,
            session_id=data.get("session_id"),
            seconds_since_change=seconds_since,
            is_file_missing=False,
        )


def _read_metrics_from_transcript(
    transcript_path: str,
) -> tuple[Optional[str], Optional[float]]:
    """Czyta model i ctx_pct z ostatniego wpisu assistant w transkrypcie.

    Fallback używany gdy state.json nie zawiera tych pól (statusline hook
    nie zdążył jeszcze zapisać — np. zaraz po starcie sesji).

    Returns:
        (model, ctx_pct) — wartości lub None gdy niedostępne.
    """
    try:
        p = Path(transcript_path)
        if not p.exists():
            return None, None
        size = p.stat().st_size
        buf_size = min(65536, size)  # ostatnie 64 KB wystarczą
        with p.open("rb") as f:
            f.seek(max(0, size - buf_size))
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            msg = entry.get("message", {})
            model: Optional[str] = msg.get("model") or None
            usage = msg.get("usage", {})
            ctx_pct: Optional[float] = None
            if usage:
                total = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
                if total > 0:
                    ctx_pct = round(total / 200_000 * 100, 1)
            return model, ctx_pct
    except Exception:
        return None, None
    return None, None


def read_transcript_tail(path: str, n_messages: int = 5) -> list[dict]:
    """Odczytuje ostatnie n_messages wpisów user/assistant z transkryptu JSONL.

    Czyta bufor 8192 B od końca pliku — nie ładuje całego pliku do pamięci.

    Args:
        path: Ścieżka do pliku JSONL.
        n_messages: Liczba ostatnich wpisów do zwrócenia.

    Returns:
        Lista słowników (type, text) posortowana chronologicznie.
    """
    try:
        p = Path(path)
        if not p.exists():
            return []
        size = p.stat().st_size
        buf_size = min(8192, size)
        with p.open("rb") as f:
            f.seek(max(0, size - buf_size))
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        results: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry_type = entry.get("type")
            if entry_type not in ("user", "assistant"):
                continue
            text = ""
            msg = entry.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        break
            elif isinstance(content, str):
                text = content
            results.append({"type": entry_type, "text": text[:300]})
            if len(results) >= n_messages:
                break
        return list(reversed(results))
    except OSError:
        return []


def read_transcript_messages(
    path: str | Path,
    n: int = 60,
    max_bytes: int = 400_000,
) -> list[dict]:
    """Odczytuje ostatnie n wiadomości user/assistant z transkryptu JSONL.

    Zwraca listę słowników {type, text, ts} posortowaną chronologicznie.
    Pole ts to datetime lub None. Tekst asystenta jest pełny (nie skracany).
    """
    try:
        p = Path(path)
        if not p.exists():
            return []
        size = p.stat().st_size
        buf_size = min(max_bytes, size)
        with p.open("rb") as f:
            f.seek(max(0, size - buf_size))
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        results: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry_type = entry.get("type")
            if entry_type not in ("user", "assistant"):
                continue
            msg = entry.get("message", {})
            content = msg.get("content", [])
            text = ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        break
            elif isinstance(content, str):
                text = content
            if not text.strip():
                continue
            ts: datetime | None = None
            raw_ts = entry.get("timestamp") or msg.get("timestamp")
            if raw_ts:
                ts = _parse_iso(str(raw_ts))
            results.append({"type": entry_type, "text": text, "ts": ts})
            if len(results) >= n:
                break
        return list(reversed(results))
    except OSError:
        return []


def read_last_activity_ts(path: str) -> "datetime | None":
    """Zwraca timestamp ostatniej wiadomości user/assistant w transkrypcie.

    Czyta ostatnie 8 KB pliku — nie ładuje całego transkryptu.
    Zwraca None gdy plik nie istnieje lub brak timestampów.
    """
    try:
        p = Path(path)
        if not p.exists():
            return None
        size = p.stat().st_size
        buf_size = min(8192, size)
        with p.open("rb") as f:
            f.seek(max(0, size - buf_size))
            raw = f.read()
        for line in reversed(raw.decode("utf-8", errors="replace").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            raw_ts = entry.get("timestamp") or entry.get("message", {}).get("timestamp")
            ts = _parse_iso(str(raw_ts)) if raw_ts else None
            if ts:
                return ts
    except OSError:
        pass
    return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
