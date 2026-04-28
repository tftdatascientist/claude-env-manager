from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_VSCODE_SETTINGS = {
    "claude.plansDirectory": ".",
}


def _session_id(slug: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
    return f"{ts}_{safe}"


class ProjectSpawner:
    def __init__(
        self,
        cc_executable: str | None = None,
        vscode_executable: str | None = None,
    ) -> None:
        self._cc = cc_executable or shutil.which("cc") or "cc"
        self._code = vscode_executable or shutil.which("code") or "code"

    def spawn(
        self,
        prompt: str,
        project_name: str,
        parent_location: Path | str,
    ) -> tuple[str, Path]:
        """Tworzy katalog projektu, zapisuje intake.json, odpala CC w plan mode i VS Code.

        Returns:
            (session_id, project_dir)
        """
        parent_location = Path(parent_location)
        project_dir = parent_location / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        session_id = _session_id(project_name)
        intake = {
            "session_id": session_id,
            "project_name": project_name,
            "prompt": prompt,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        intake_path = project_dir / "intake.json"
        intake_path.write_text(json.dumps(intake, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("intake.json zapisany: %s", intake_path)

        vscode_dir = project_dir / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        settings_path = vscode_dir / "settings.json"
        if not settings_path.exists():
            settings_path.write_text(
                json.dumps(_VSCODE_SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        self._launch_cc(prompt, project_dir)
        self._launch_vscode(project_dir)
        return session_id, project_dir

    def _launch_cc(self, prompt: str, project_dir: Path) -> None:
        try:
            subprocess.Popen(
                [self._cc, "--plan", "--print", prompt],
                cwd=str(project_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            logger.info("CC uruchomiony w plan mode: %s", project_dir)
        except FileNotFoundError:
            logger.error("Nie znaleziono cc CLI: %s", self._cc)
            raise

    def _launch_vscode(self, project_dir: Path) -> None:
        try:
            subprocess.Popen(
                [self._code, str(project_dir)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            logger.info("VS Code otwarty: %s", project_dir)
        except FileNotFoundError:
            logger.error("Nie znaleziono code: %s", self._code)
            raise
