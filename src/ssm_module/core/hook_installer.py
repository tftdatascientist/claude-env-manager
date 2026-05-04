"""hook_installer.py — retroaktywna instalacja hooka SSM w istniejących projektach SSS."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

_SSS_HOOK_SRC = (
    Path(__file__).parent.parent.parent.parent
    / '.claude' / 'skills' / 'sss' / 'assets' / 'hooks' / 'ssm_session_start.py'
)
_HOOK_CMD = 'python .claude/hooks/ssm_session_start.py'
_PLAN_MARKER = '<!-- SECTION:next -->'


@dataclass
class InstallResult:
    project_path: str
    success: bool
    message: str
    already_installed: bool = False
    dry_run: bool = False


def is_sss_project(project_path: Path) -> bool:
    plan = project_path / 'PLAN.md'
    if not plan.exists():
        return False
    try:
        return _PLAN_MARKER in plan.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False


def is_hook_installed(project_path: Path) -> bool:
    settings = project_path / '.claude' / 'settings.local.json'
    if not settings.exists():
        return False
    try:
        cfg = json.loads(settings.read_text(encoding='utf-8'))
        session_hooks = cfg.get('hooks', {}).get('SessionStart', [])
        return any(
            any(h.get('command') == _HOOK_CMD for h in entry.get('hooks', []))
            for entry in session_hooks
        )
    except Exception:
        return False


def install_hook(project_path: Path, dry_run: bool = False) -> InstallResult:
    """Instaluje ssm_session_start.py i wpis w settings.local.json.

    Tworzy backup settings.local.json.bak przed modyfikacją.
    Idempotentne — drugie wywołanie nie zmienia nic.
    """
    if not is_sss_project(project_path):
        return InstallResult(str(project_path), False, 'Nie jest projektem SSS (brak PLAN.md z markerem)')

    if is_hook_installed(project_path):
        return InstallResult(str(project_path), True, 'Hook już zainstalowany', already_installed=True)

    claude_dir = project_path / '.claude'
    hooks_dir = claude_dir / 'hooks'
    settings_path = claude_dir / 'settings.local.json'

    if dry_run:
        return InstallResult(str(project_path), True, 'dry-run: hook byłby zainstalowany', dry_run=True)

    # 1. Skopiuj hook script
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_dst = hooks_dir / 'ssm_session_start.py'
    if _SSS_HOOK_SRC.exists():
        shutil.copy2(_SSS_HOOK_SRC, hook_dst)
        hook_dst.chmod(0o755)

    # 2. Zaktualizuj settings.local.json z backupem
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.parent / (settings_path.name + '.bak'))
        try:
            cfg = json.loads(settings_path.read_text(encoding='utf-8'))
        except Exception:
            cfg = {}
    else:
        cfg = {}

    session_hooks = cfg.setdefault('hooks', {}).setdefault('SessionStart', [])
    session_hooks.append({'hooks': [{'type': 'command', 'command': _HOOK_CMD}]})
    settings_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')

    return InstallResult(str(project_path), True, 'Hook zainstalowany pomyślnie')
