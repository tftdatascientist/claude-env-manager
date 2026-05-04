"""Historia sesji CC z pliku aa-sessions.jsonl i transkryptów projektów."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_AA_SESSIONS_PATH = Path.home() / ".claude" / "cc-panel" / "aa-sessions.jsonl"
_PROJECTS_PATH = Path.home() / ".claude" / "projects"


def _encode_project_path(project_path: str) -> str:
    """Konwertuje ścieżkę projektu na format nazwy katalogu używany przez Claude Code.

    Claude Code zamienia każdy znak poza [A-Za-z0-9-] na '-', co daje:
      C:\\Users\\Sławek\\.MD\\10_PROJEKTY  →  C--Users-S-awek--MD-10-PROJEKTY
    (dwukropek, ukośniki, kropki, podkreślenia, znaki spoza ASCII → '-')
    """
    s = str(Path(project_path).resolve())
    return re.sub(r"[^A-Za-z0-9\-]", "-", s)


def _find_project_dir(project_path: str) -> "Path | None":
    """Zwraca katalog transkryptów dla projektu lub None."""
    if not _PROJECTS_PATH.is_dir() or not project_path:
        return None
    encoded = _encode_project_path(project_path)
    candidate = _PROJECTS_PATH / encoded
    if candidate.is_dir():
        return candidate
    # Fallback: porównanie case-insensitive (Windows)
    encoded_lower = encoded.lower()
    try:
        for d in _PROJECTS_PATH.iterdir():
            if d.is_dir() and d.name.lower() == encoded_lower:
                return d
    except OSError:
        pass
    return None


@dataclass
class SessionRecord:
    """Jeden rekord sesji Auto-Accept.

    Args:
        session_id: Unikalny ID sesji.
        terminal_id: Numer terminala (1–4).
        started_at: Czas rozpoczęcia sesji.
        stopped_at: Czas zakończenia sesji lub None jeśli brak rekordu stop.
        duration_s: Czas trwania w sekundach lub None.
        total_cost_usd: Łączny koszt sesji w USD.
        stop_reason: Powód zakończenia ('user-stop', 'budget', 'circuit-break', itp.).
        iterations: Liczba iteracji Haiku.
    """

    session_id: str = ""
    terminal_id: int = 0
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    duration_s: Optional[int] = None
    total_cost_usd: float = 0.0
    stop_reason: str = ""
    iterations: int = 0


@dataclass
class SessionHistorySummary:
    """Podsumowanie historii sesji dla slotu.

    Args:
        aa_session_count: Liczba sesji Auto-Accept.
        aa_total_cost_usd: Łączny koszt sesji AA.
        aa_total_duration_s: Łączny czas sesji AA w sekundach.
        aa_last_session_at: Data ostatniej sesji AA.
        aa_sessions: Lista ostatnich sesji AA (max 20).
        transcript_count: Liczba plików transkryptów projektu (regularne sesje CC).
        transcript_last_at: Data ostatniego transkryptu lub None.
    """

    aa_session_count: int = 0
    aa_total_cost_usd: float = 0.0
    aa_total_duration_s: int = 0
    aa_last_session_at: Optional[datetime] = None
    aa_sessions: list[SessionRecord] = field(default_factory=list)
    transcript_count: int = 0
    transcript_last_at: Optional[datetime] = None


def get_session_history(
    terminal_id: int | None = None,
    project_path: str = "",
) -> SessionHistorySummary:
    """Zbiera historię sesji CC dla danego slotu lub projektu.

    Odczytuje aa-sessions.jsonl (sesje Auto-Accept) i katalog transkryptów
    projektu z ~/.claude/projects/.

    Args:
        terminal_id: Filtruj AA sesje po terminal_id lub None = wszystkie.
        project_path: Ścieżka projektu do znalezienia transkryptów.

    Returns:
        Podsumowanie historii sesji.
    """
    summary = SessionHistorySummary()
    summary.aa_sessions = _read_aa_sessions(terminal_id)
    summary.aa_session_count = len(summary.aa_sessions)

    for rec in summary.aa_sessions:
        summary.aa_total_cost_usd += rec.total_cost_usd
        if rec.duration_s is not None:
            summary.aa_total_duration_s += rec.duration_s
        if rec.started_at and (
            summary.aa_last_session_at is None
            or rec.started_at > summary.aa_last_session_at
        ):
            summary.aa_last_session_at = rec.started_at

    if project_path:
        count, last_at = _count_transcripts(project_path)
        summary.transcript_count = count
        summary.transcript_last_at = last_at

    return summary


def _read_aa_sessions(terminal_id: int | None) -> list[SessionRecord]:
    """Parsuje aa-sessions.jsonl i zwraca listę zakończonych sesji (max 20)."""
    if not _AA_SESSIONS_PATH.exists():
        return []

    # Grupuj rekordy po session_id
    starts: dict[str, dict] = {}
    stops: dict[str, dict] = {}
    iterations: dict[str, int] = {}

    try:
        lines = _AA_SESSIONS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = rec.get("sessionId", "")
        rtype = rec.get("type", "")
        tid = rec.get("terminalId", 0)
        if terminal_id is not None and tid != terminal_id:
            if rtype == "session-start":
                pass  # może pasuje inny terminal — pomijamy
            continue
        if rtype == "session-start":
            starts[sid] = rec
        elif rtype == "session-stop":
            stops[sid] = rec
        elif rtype == "haiku-response":
            iterations[sid] = iterations.get(sid, 0) + 1

    # Zbuduj rekordy
    records: list[SessionRecord] = []
    for sid, start in starts.items():
        stop = stops.get(sid)
        started_at = _parse_iso(start.get("t") or start.get("timestamp"))
        stopped_at = _parse_iso(stop.get("t") or stop.get("timestamp")) if stop else None
        duration_s = None
        if started_at and stopped_at:
            duration_s = max(0, int((stopped_at - started_at).total_seconds()))
        cost = 0.0
        if stop:
            cost = float(stop.get("finalCostUsd", 0) or 0)
        records.append(SessionRecord(
            session_id=sid,
            terminal_id=start.get("terminalId", 0),
            started_at=started_at,
            stopped_at=stopped_at,
            duration_s=duration_s,
            total_cost_usd=cost,
            stop_reason=stop.get("stopReason", "") if stop else "w toku",
            iterations=iterations.get(sid, 0),
        ))

    # Sortuj od najnowszych, ogranicz do 20
    records.sort(key=lambda r: r.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return records[:20]


def _count_transcripts(project_path: str) -> tuple[int, Optional[datetime]]:
    """Liczy pliki transkryptów w ~/.claude/projects/ dla danego projektu."""
    target_dir = _find_project_dir(project_path)
    if target_dir is None:
        return 0, None
    count = 0
    last_mtime: Optional[float] = None
    try:
        for f in target_dir.iterdir():
            if f.suffix == ".jsonl" and f.is_file():
                count += 1
                mtime = f.stat().st_mtime
                if last_mtime is None or mtime > last_mtime:
                    last_mtime = mtime
    except OSError:
        return count, None
    last_at = datetime.fromtimestamp(last_mtime, tz=timezone.utc) if last_mtime else None
    return count, last_at


def list_project_transcripts(project_path: str) -> list[tuple[Path, float, int]]:
    """Zwraca listę (path, mtime, rozmiar_bajtów) wszystkich transkryptów projektu.

    Sortuje od najnowszego do najstarszego.
    """
    target_dir = _find_project_dir(project_path)
    if target_dir is None:
        return []
    results: list[tuple[Path, float, int]] = []
    try:
        for f in target_dir.iterdir():
            if f.suffix == ".jsonl" and f.is_file():
                st = f.stat()
                results.append((f, st.st_mtime, st.st_size))
    except OSError:
        pass
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def find_latest_transcript(project_path: str) -> Path | None:
    """Zwraca ścieżkę najnowszego transkryptu JSONL dla projektu lub None."""
    entries = list_project_transcripts(project_path)
    return entries[0][0] if entries else None


def fmt_duration(seconds: int) -> str:
    """Formatuje czas trwania sesji.

    Args:
        seconds: Czas w sekundach.

    Returns:
        Czytelny string, np. "12m 30s", "2h 5m".
    """
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"


def _parse_iso(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
