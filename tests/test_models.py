"""Tests for models."""

from pathlib import Path
from datetime import datetime

from src.models.resource import Resource, ResourceType, ResourceScope
from src.models.project import Project


class TestResource:
    def test_create_resource(self):
        r = Resource(
            path=Path("test.json"),
            resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER,
            display_name="test.json",
        )
        assert r.resource_type == ResourceType.SETTINGS
        assert r.scope == ResourceScope.USER
        assert r.content is None
        assert r.read_only is False

    def test_load_content(self, tmp_path: Path):
        f = tmp_path / "data.json"
        f.write_text('{"x": 1}', encoding="utf-8")
        r = Resource(
            path=f,
            resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER,
            display_name="data.json",
        )
        content = r.load_content()
        assert content == '{"x": 1}'
        assert r.last_modified is not None

    def test_load_missing_file(self):
        r = Resource(
            path=Path("nonexistent.json"),
            resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER,
            display_name="nonexistent.json",
        )
        assert r.load_content() is None

    def test_file_format(self):
        r = Resource(
            path=Path("settings.json"),
            resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER,
            display_name="settings.json",
        )
        assert r.file_format == "json"


class TestProject:
    def test_empty_project(self):
        p = Project(name="test", root_path=Path("/tmp/test"))
        assert p.has_claude_config is False

    def test_project_with_resources(self):
        r = Resource(
            path=Path("CLAUDE.md"),
            resource_type=ResourceType.CLAUDE_MD,
            scope=ResourceScope.PROJECT,
            display_name="CLAUDE.md",
        )
        p = Project(name="test", root_path=Path("/tmp/test"), resources=[r])
        assert p.has_claude_config is True
