from __future__ import annotations

from dataclasses import dataclass

import psutil

# Nazwy exe Claude Code CLI (Windows)
_CC_EXE_NAMES = frozenset({"cc", "cc.exe", "claude", "claude.exe"})
# Słowa kluczowe w cmdline dla procesów Node.js będących CC
_CC_NODE_KEYWORDS = ("@anthropic", "claude-code", "claude/cli", "claude\\cli")


@dataclass(frozen=True)
class CcProcessDTO:
    pid: int
    exe: str
    project_path: str


def scan_cc_processes() -> set[CcProcessDTO]:
    """Skanuje wszystkie procesy i zwraca aktywne sesje Claude Code."""
    result: set[CcProcessDTO] = set()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            if name in _CC_EXE_NAMES:
                cwd = proc.cwd()
                result.add(CcProcessDTO(pid=info["pid"], exe=name, project_path=cwd))
                continue
            if name in ("node", "node.exe"):
                cmdline = info.get("cmdline") or []
                cmd_str = " ".join(cmdline).lower()
                if any(kw in cmd_str for kw in _CC_NODE_KEYWORDS):
                    cwd = proc.cwd()
                    result.add(CcProcessDTO(pid=info["pid"], exe=name, project_path=cwd))
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
    return result
