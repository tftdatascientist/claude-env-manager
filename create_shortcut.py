"""Tworzy lub aktualizuje skrót Claude Manager na pulpicie Windows."""

import os
import subprocess
import sys
import winreg
from pathlib import Path


def _find_desktop() -> Path:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            0,
            winreg.KEY_READ,
        ) as key:
            raw, _ = winreg.QueryValueEx(key, "Desktop")
            return Path(os.path.expandvars(raw))
    except OSError:
        return Path.home() / "Desktop"


def main() -> None:
    app_dir = Path(__file__).parent
    ico_path = app_dir / "assets" / "cm.ico"
    desktop = _find_desktop()
    shortcut_path = desktop / "Claude Manager.lnk"

    target = app_dir / ".venv" / "Scripts" / "pythonw.exe"
    if not target.exists():
        target = Path(sys.executable)

    main_py = app_dir / "main.py"
    ico_str = str(ico_path) if ico_path.exists() else ""

    ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut_path}')
$s.TargetPath = '{target}'
$s.Arguments = '"{main_py}"'
$s.WorkingDirectory = '{app_dir}'
$s.Description = 'Claude Manager - CC Tools Hub'
{f"$s.IconLocation = '{ico_str},0'" if ico_str else ""}
$s.Save()
"""
    subprocess.run(["powershell", "-Command", ps_script], check=True)
    action = "zaktualizowany" if shortcut_path.exists() else "utworzony"
    print(f"Skrót {action}: {shortcut_path}")


if __name__ == "__main__":
    main()
