"""test_registry.py — testy ProjectRegistry save/load round-trip."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ssm_module.core.project_registry import ProjectEntry, ProjectRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ProjectRegistry:
    return ProjectRegistry(registry_path=tmp_path / 'projects.json')


def test_registry_add_and_load(registry: ProjectRegistry, tmp_path: Path) -> None:
    entry = ProjectEntry(project_id='abc123', path='/some/project', added_via='manual', name='TestProj')
    registry.add(entry)

    reg2 = ProjectRegistry(registry_path=tmp_path / 'projects.json')
    loaded = reg2.get('abc123')
    assert loaded is not None
    assert loaded.path == '/some/project'
    assert loaded.name == 'TestProj'
    assert loaded.added_via == 'manual'


def test_registry_remove(registry: ProjectRegistry) -> None:
    registry.add(ProjectEntry(project_id='x1', path='/p1', added_via='hook'))
    registry.add(ProjectEntry(project_id='x2', path='/p2', added_via='manual'))
    registry.remove('x1')
    assert registry.get('x1') is None
    assert registry.get('x2') is not None


def test_registry_find_by_path(registry: ProjectRegistry, tmp_path: Path) -> None:
    proj_path = tmp_path / 'myproject'
    registry.add(ProjectEntry(project_id='pid1', path=str(proj_path), added_via='hook'))
    found = registry.find_by_path(str(proj_path))
    assert found is not None
    assert found.project_id == 'pid1'


def test_registry_all(registry: ProjectRegistry) -> None:
    registry.add(ProjectEntry(project_id='a', path='/a', added_via='hook'))
    registry.add(ProjectEntry(project_id='b', path='/b', added_via='manual'))
    assert len(registry.all()) == 2
