"""Workflow backend — clean_plan, git_push, round_end.

Obsługuje dwa formaty PLAN.md:
- PCC v2.0 (<!-- SECTION:name -->) — projekty z Projektanta, obsługa przez template_parser
- legacy (## Nagłówek) — starsze projekty, obsługa przez fallback regex
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from src.projektant.template_parser import (
    plan_append_session_log,
    plan_flush,
)


class WorkflowResult:
    def __init__(self, ok: bool, message: str = "") -> None:
        self.ok = ok
        self.message = message


def clean_plan(project_path: str | Path) -> WorkflowResult:
    """Czyści sekcje Done i Current w PLAN.md (PCC v2.0 lub legacy ## format)."""
    path = Path(project_path) / "PLAN.md"
    if not path.exists():
        return WorkflowResult(False, "PLAN.md nie istnieje")

    try:
        plan_flush(path)
        return WorkflowResult(True, "PLAN.md wyczyszczony (Done + Current)")
    except ValueError:
        pass

    # fallback: legacy format z ## nagłówkami
    text = path.read_text(encoding="utf-8")
    original = text
    for section in ("Done", "Current"):
        text = re.sub(
            r"(^## " + section + r"\s*$)(.*?)(?=^## |\Z)",
            r"\1\n",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
    if text == original:
        return WorkflowResult(True, "PLAN.md — brak sekcji do wyczyszczenia")
    path.write_text(text, encoding="utf-8")
    return WorkflowResult(True, "PLAN.md wyczyszczony (Done + Current)")


def _git_current_branch(p: Path) -> str:
    """Zwraca nazwę bieżącej gałęzi lub 'master' jako fallback."""
    r = subprocess.run(
        ["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "master"


def git_push(project_path: str | Path, message: str = "") -> WorkflowResult:
    """git add -A + commit + push w katalogu projektu.

    Jeśli push nie powiedzie się z powodu braku upstream, automatycznie
    ponawia z --set-upstream origin <bieżąca_gałąź>.
    """
    p = Path(project_path)
    if not (p / ".git").exists():
        return WorkflowResult(False, "Brak repozytorium git w katalogu projektu")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = message or f"chore: round-end {ts}"

    try:
        # add + commit
        for cmd in (
            ["git", "-C", str(p), "add", "-A"],
            ["git", "-C", str(p), "commit", "-m", msg],
        ):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                combined = (r.stdout + r.stderr).lower()
                if "nothing to commit" in combined or "nothing added" in combined:
                    continue
                return WorkflowResult(False, (r.stderr or r.stdout).strip())

        # push — z obsługą braku upstream i braku remote
        r = subprocess.run(
            ["git", "-C", str(p), "push"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            combined = (r.stdout + r.stderr).lower()

            _no_upstream = ("no upstream branch" in combined or "has no upstream" in combined)
            _no_remote = ("no configured push destination" in combined or
                          "does not appear to be a git repository" in combined)
            _repo_not_found = ("repository not found" in combined or
                               "not found" in combined and "fatal: repository" in combined)

            if _repo_not_found:
                raw_url = (r.stderr or r.stdout).strip()
                url_match = re.search(r"'(https?://[^']+)'", raw_url)
                url_hint = url_match.group(1) if url_match else ""
                return WorkflowResult(
                    False,
                    "Repozytorium nie istnieje na serwerze.\n\n"
                    "Utwórz je najpierw na GitHub (lub innym hostingu),\n"
                    "a następnie kliknij Push ponownie.\n\n"
                    + (f"Brakujące repo: {url_hint}" if url_hint else raw_url),
                )
            if _no_remote:
                return WorkflowResult(
                    False,
                    "Brak skonfigurowanego remote.\n\n"
                    "Dodaj remote i kliknij Push ponownie:\n"
                    "  git remote add origin https://github.com/uzytkownik/repo.git",
                )
            if _no_upstream:
                # Sprawdź czy remote origin istnieje
                remote_r = subprocess.run(
                    ["git", "-C", str(p), "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=10,
                )
                if remote_r.returncode != 0:
                    return WorkflowResult(
                        False,
                        "Gałąź nie ma skonfigurowanego upstream i brak remote 'origin'.\n\n"
                        "Skonfiguruj remote:\n"
                        "  git remote add origin https://github.com/uzytkownik/repo.git\n"
                        "a następnie kliknij Push ponownie.",
                    )
                branch = _git_current_branch(p)
                r = subprocess.run(
                    ["git", "-C", str(p), "push", "--set-upstream", "origin", branch],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    return WorkflowResult(False, (r.stderr or r.stdout).strip())
            else:
                return WorkflowResult(False, (r.stderr or r.stdout).strip())

        return WorkflowResult(True, f"Push OK: {msg}")
    except subprocess.TimeoutExpired:
        return WorkflowResult(False, "Timeout — git push trwal zbyt dlugo (>30s)")
    except FileNotFoundError:
        return WorkflowResult(False, "git nie znaleziony w PATH")
    except Exception as exc:
        return WorkflowResult(False, str(exc))


def git_init_and_push(
    project_path: str | Path,
    remote_url: str = "",
    branch: str = "master",
    commit_message: str = "",
) -> WorkflowResult:
    """Inicjalizuje repo git, robi initial commit i opcjonalnie pushuje do remote.

    Kroki: git init → git add -A → git commit → (git remote add origin) → (git push -u)
    """
    p = Path(project_path)
    if not p.is_dir():
        return WorkflowResult(False, f"Katalog nie istnieje: {p}")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = commit_message.strip() or f"feat: initial commit {ts}"
    remote = remote_url.strip()

    try:
        # git init z nazwą gałęzi (git >= 2.28); fallback bez -b dla starszych wersji
        r = subprocess.run(
            ["git", "-C", str(p), "init", "-b", branch],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            r = subprocess.run(
                ["git", "-C", str(p), "init"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                return WorkflowResult(False, f"git init: {r.stderr.strip()}")

        # git add -A
        r = subprocess.run(
            ["git", "-C", str(p), "add", "-A"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return WorkflowResult(False, f"git add: {r.stderr.strip()}")

        # git commit
        r = subprocess.run(
            ["git", "-C", str(p), "commit", "-m", msg],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            combined = (r.stdout + r.stderr).lower()
            if "nothing to commit" not in combined and "nothing added" not in combined:
                return WorkflowResult(False, f"git commit: {r.stderr.strip()}")

        if not remote:
            return WorkflowResult(True, f"Repozytorium zainicjalizowane lokalnie w:\n{p}")

        # git remote add origin <url>
        r = subprocess.run(
            ["git", "-C", str(p), "remote", "add", "origin", remote],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 and "already exists" not in r.stderr.lower():
            return WorkflowResult(False, f"git remote add: {r.stderr.strip()}")

        # git push -u origin <branch>
        r = subprocess.run(
            ["git", "-C", str(p), "push", "-u", "origin", branch],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return WorkflowResult(False, f"git push: {r.stderr.strip()}")

        return WorkflowResult(True, f"Repo zainicjalizowane i wypchnięte do:\n{remote}")

    except subprocess.TimeoutExpired:
        return WorkflowResult(False, "Timeout — operacja git trwała zbyt długo")
    except FileNotFoundError:
        return WorkflowResult(False, "git nie znaleziony w PATH")
    except Exception as exc:
        return WorkflowResult(False, str(exc))


def round_end(project_path: str | Path) -> WorkflowResult:
    """Konczy runde: czysci PLAN.md, loguje handoff, pushuje do git."""
    p = Path(project_path)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    r = clean_plan(p)
    if not r.ok:
        return r

    plan_path = p / "PLAN.md"
    if plan_path.exists():
        try:
            plan_append_session_log(plan_path, "round-end: PLAN wyczyszczony")
        except ValueError:
            # legacy format — szukaj ## Session Log
            text = plan_path.read_text(encoding="utf-8")
            m = re.search(r"^## Session Log\s*$", text, re.MULTILINE)
            if m:
                entry = f"\n- {ts} | round-end: PLAN wyczyszczony"
                text = text[: m.end()] + entry + text[m.end() :]
                plan_path.write_text(text, encoding="utf-8")

    return git_push(p, f"chore: round-end {ts}")


# ---------------------------------------------------------------------------
# Qt async wrapper
# ---------------------------------------------------------------------------

class _Worker(QThread):
    finished = Signal(bool, str)

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self._fn = fn
        self._args = args

    def run(self) -> None:
        result = self._fn(*self._args)
        self.finished.emit(result.ok, result.message)


class WorkflowRunner(QObject):
    """Uruchamia operacje workflow w tle i emituje wynik."""

    operation_done = Signal(str, bool, str)  # (name, ok, message)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workers: list[_Worker] = []

    def run_clean_plan(self, project_path: str) -> None:
        self._start("clean_plan", clean_plan, project_path)

    def run_git_push(self, project_path: str) -> None:
        self._start("git_push", git_push, project_path)

    def run_git_init(
        self,
        project_path: str,
        remote_url: str = "",
        branch: str = "master",
        commit_message: str = "",
    ) -> None:
        self._start("git_init", git_init_and_push, project_path, remote_url, branch, commit_message)

    def run_round_end(self, project_path: str) -> None:
        self._start("round_end", round_end, project_path)

    def _start(self, name: str, fn, *args) -> None:
        worker = _Worker(fn, *args)
        worker.finished.connect(lambda ok, msg: self.operation_done.emit(name, ok, msg))
        worker.finished.connect(lambda: self._cleanup(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup(self, worker: _Worker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
