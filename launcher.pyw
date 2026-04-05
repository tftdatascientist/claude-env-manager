"""Silent launcher (no console window) for Claude Environment Manager."""

import sys
import subprocess
from pathlib import Path

app_dir = Path(__file__).parent
venv_python = app_dir / ".venv" / "Scripts" / "pythonw.exe"
main_script = app_dir / "main.py"

subprocess.Popen([str(venv_python), str(main_script)], cwd=str(app_dir))
