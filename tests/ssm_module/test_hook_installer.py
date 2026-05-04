"""test_hook_installer.py — testy install_hook idempotencja i backup."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.ssm_module.core.hook_installer import install_hook, is_hook_installed, is_sss_project

_PLAN_CONTENT = '<!-- SECTION:next -->\n- [ ] task\n<!-- /SECTION:next -->'


@pytest.fixture
def sss_project(tmp_path: Path) -> Path:
    (tmp_path / '.claude' / 'hooks').mkdir(parents=True)
    (tmp_path / 'PLAN.md').write_text(_PLAN_CONTENT, encoding='utf-8')
    return tmp_path


def test_is_sss_project_true(sss_project: Path) -> None:
    assert is_sss_project(sss_project)


def test_is_sss_project_false_no_marker(tmp_path: Path) -> None:
    (tmp_path / 'PLAN.md').write_text('# Plan\n', encoding='utf-8')
    assert not is_sss_project(tmp_path)


def test_install_hook_success(sss_project: Path) -> None:
    result = install_hook(sss_project)
    assert result.success
    assert not result.already_installed
    assert is_hook_installed(sss_project)


def test_install_hook_idempotent(sss_project: Path) -> None:
    install_hook(sss_project)
    settings_before = (sss_project / '.claude' / 'settings.local.json').read_text()
    result2 = install_hook(sss_project)
    settings_after = (sss_project / '.claude' / 'settings.local.json').read_text()
    assert result2.already_installed
    assert settings_before == settings_after


def test_install_hook_creates_backup(sss_project: Path) -> None:
    settings_path = sss_project / '.claude' / 'settings.local.json'
    settings_path.write_text('{"existing": true}', encoding='utf-8')
    install_hook(sss_project)
    bak = sss_project / '.claude' / 'settings.local.json.bak'
    assert bak.exists()
    assert json.loads(bak.read_text())['existing'] is True


def test_install_hook_dry_run(sss_project: Path) -> None:
    result = install_hook(sss_project, dry_run=True)
    assert result.success
    assert result.dry_run
    assert not is_hook_installed(sss_project)
