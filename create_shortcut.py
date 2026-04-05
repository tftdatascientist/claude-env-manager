"""Create a Windows desktop shortcut for Claude Environment Manager."""

import subprocess
from pathlib import Path

app_dir = Path(__file__).parent
desktop = Path.home() / "Desktop"
shortcut_path = desktop / "Claude Env Manager.lnk"
target = app_dir / ".venv" / "Scripts" / "pythonw.exe"
arguments = str(app_dir / "main.py")
working_dir = str(app_dir)

ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{shortcut_path}")
$s.TargetPath = "{target}"
$s.Arguments = '"{arguments}"'
$s.WorkingDirectory = "{working_dir}"
$s.Description = "Claude Environment Manager"
$s.Save()
'''

subprocess.run(["powershell", "-Command", ps_script], check=True)
print(f"Shortcut created: {shortcut_path}")
