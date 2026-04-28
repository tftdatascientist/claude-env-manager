from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILL_SCRIPTS = {
    "init_project": "init_project.py",
    "plan_buffer": "plan_buffer.py",
    "service_round": "service_round.py",
    "finalize": "finalize.py",
    "state": "state.py",
}


class SSSBridge:
    def __init__(self, skills_dir: Path | str, python_executable: str | None = None) -> None:
        self._skills_dir = Path(skills_dir)
        self._python = python_executable or shutil.which("python") or "python"

    def run_script(
        self,
        script_name: str,
        project_dir: Path | str,
        extra_args: list[str] | None = None,
    ) -> tuple[int, str, str]:
        """Uruchamia skrypt SSS i zwraca (returncode, stdout, stderr)."""
        filename = _SKILL_SCRIPTS.get(script_name, f"{script_name}.py")
        script_path = self._skills_dir / filename
        if not script_path.exists():
            raise FileNotFoundError(f"Skrypt SSS nie istnieje: {script_path}")

        cmd = [self._python, str(script_path)] + (extra_args or [])
        logger.debug("SSSBridge: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            logger.warning("Skrypt %s zakończony kodem %d: %s", script_name, result.returncode, result.stderr)
        return result.returncode, result.stdout, result.stderr
