"""Persister — atomowy zapis settings.json z backup .bak i UTF-8 bez BOM."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def _json_bytes(data: dict) -> bytes:
    """Serializuje dict do JSON — UTF-8 bez BOM, LF, ensure_ascii=False."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    text += "\n"
    return text.encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def backup_path(target: Path) -> Path:
    """Zwraca ścieżkę backupu z timestampem (do mikrosekundy) obok docelowego pliku."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return target.with_suffix(f".{ts}.bak")


def list_backups(target: Path) -> list[Path]:
    """Zwraca listę backupów dla danego pliku, posortowana od najnowszego."""
    pattern = target.stem + ".*.bak"
    baks = sorted(target.parent.glob(pattern), key=lambda p: p.name, reverse=True)
    return baks


def write_settings(target: Path, data: dict) -> tuple[Path | None, str, str]:
    """Atomowy zapis settings.json z backup .bak.

    Returns:
        (backup_file_path, hash_before, hash_after)
        backup_file_path = None jeśli oryginalny plik nie istniał (nowy plik)
    """
    target = Path(target)
    new_bytes = _json_bytes(data)
    hash_after = _sha256(new_bytes)

    # Backup istniejącego pliku
    bak_path: Path | None = None
    hash_before = ""
    if target.exists():
        old_bytes = target.read_bytes()
        hash_before = _sha256(old_bytes)
        bak_path = backup_path(target)
        bak_path.write_bytes(old_bytes)

    # Atomowy zapis przez tempfile w tym samym katalogu
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=".hooker_tmp_",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_bytes)
        os.replace(tmp_name, str(target))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return bak_path, hash_before, hash_after


def restore_from_backup(bak_path: Path, target: Path) -> None:
    """Przywraca plik z backupu (atomowo)."""
    bak_path = Path(bak_path)
    target = Path(target)
    if not bak_path.exists():
        raise FileNotFoundError(f"Backup nie istnieje: {bak_path}")
    old_bytes = bak_path.read_bytes()
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=".hooker_restore_",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(old_bytes)
        os.replace(tmp_name, str(target))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
