"""Sound manager — config dźwięków per typ zdarzenia CC."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_CONFIG_PATH = Path.home() / ".claude" / "hooker" / "sound_config.json"
_HOOK_SCRIPT_PATH = Path.home() / ".claude" / "hooks" / "sound_hook.py"

# Typy eventów obsługiwane przez Sound Hook
SOUND_EVENT_TYPES = [
    "Stop",
    "Notification",
    "SessionEnd",
    "SessionStart",
    "SubagentStop",
    "PreCompact",
    "PostCompact",
]

_HOOK_SCRIPT_TEMPLATE = '''\
#!/usr/bin/env python3
"""Sound Hook — odtwarza dźwięk dla zdarzenia CC."""
import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "hooker" / "sound_config.json"

def main() -> None:
    event_type = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    sound_file = config.get("sounds", {}).get(event_type, "")
    if not sound_file or not Path(sound_file).exists():
        return

    play_sound(sound_file)


def play_sound(path: str) -> None:
    import sys as _sys
    if _sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass
        # Fallback: PowerShell
        import subprocess
        subprocess.Popen(
            ["powershell", "-c", f"(New-Object Media.SoundPlayer '{path}').Play()"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        import subprocess
        subprocess.Popen(["aplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
'''


# ------------------------------------------------------------------ config I/O

def load_config() -> dict:
    """Zwraca config dźwięków: {sounds: {EventType: filepath}, enabled: [EventType]}."""
    if not _CONFIG_PATH.exists():
        return {"sounds": {}, "enabled": []}
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sounds": {}, "enabled": []}


def save_config(config: dict) -> None:
    """Zapisuje config atomowo (UTF-8)."""
    import os, tempfile
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(_CONFIG_PATH.parent), prefix=".sound_cfg_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, str(_CONFIG_PATH))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------ hook script

def install_hook_script() -> Path:
    """Zapisuje sound_hook.py do ~/.claude/hooks/. Zwraca ścieżkę."""
    _HOOK_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _HOOK_SCRIPT_PATH.write_text(_HOOK_SCRIPT_TEMPLATE, encoding="utf-8")
    return _HOOK_SCRIPT_PATH


def hook_command(event_type: str) -> str:
    """Zwraca komendę hooka dla danego typu zdarzenia."""
    script = str(_HOOK_SCRIPT_PATH).replace("\\", "/")
    return f'python "{script}" {event_type}'


# ------------------------------------------------------------------ preview

def preview_sound(file_path: str) -> None:
    """Odtwarza dźwięk w tle (preview w UI)."""
    if not Path(file_path).exists():
        return
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-c",
             f"(New-Object Media.SoundPlayer '{file_path}').Play()"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        subprocess.Popen(["aplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ settings.json integration

def build_sound_hooks(config: dict) -> dict[str, list[dict]]:
    """Zwraca fragment hooks do wstawienia do settings.json."""
    hooks: dict[str, list[dict]] = {}
    enabled = set(config.get("enabled", []))
    sounds = config.get("sounds", {})

    for evt in SOUND_EVENT_TYPES:
        if evt in enabled and sounds.get(evt):
            hooks[evt] = [{"hooks": [{"type": "command", "command": hook_command(evt)}]}]

    return hooks
