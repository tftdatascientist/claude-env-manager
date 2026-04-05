"""Tests for scanner/discovery.py and scanner/indexer.py."""

from pathlib import Path

from src.models.resource import Resource, ResourceType, ResourceScope
from src.models.project import Project
from src.scanner.indexer import build_tree, TreeNode


class TestBuildTree:
    def test_empty_tree(self):
        root = build_tree([], [], [], [])
        assert root.label == "Root"
        assert len(root.children) == 0

    def test_managed_section(self):
        managed = [
            Resource(
                path=Path("managed-settings.json"),
                resource_type=ResourceType.SETTINGS,
                scope=ResourceScope.MANAGED,
                display_name="managed-settings.json",
                read_only=True,
            )
        ]
        root = build_tree(managed, [], [], [])
        assert len(root.children) == 1
        assert root.children[0].label == "Managed (read-only)"
        assert len(root.children[0].children) == 1

    def test_user_with_rules(self):
        user = [
            Resource(
                path=Path("settings.json"),
                resource_type=ResourceType.SETTINGS,
                scope=ResourceScope.USER,
                display_name="settings.json",
            ),
            Resource(
                path=Path("rule1.md"),
                resource_type=ResourceType.RULES,
                scope=ResourceScope.USER,
                display_name="rule1.md",
            ),
        ]
        root = build_tree([], user, [], [])
        user_node = root.children[0]
        assert user_node.label == "User"
        # Should have settings.json at top and Rules/ subfolder
        labels = [c.label for c in user_node.children]
        assert "settings.json" in labels
        assert "Rules/" in labels

    def test_project_section(self):
        project = Project(
            name="my-project",
            root_path=Path("/tmp/my-project"),
            resources=[
                Resource(
                    path=Path("CLAUDE.md"),
                    resource_type=ResourceType.CLAUDE_MD,
                    scope=ResourceScope.PROJECT,
                    display_name="CLAUDE.md",
                )
            ],
        )
        root = build_tree([], [], [project], [])
        projects_node = root.children[0]
        assert projects_node.label == "Projects (1)"
        assert projects_node.children[0].label == "my-project"

    def test_external_env_vars(self):
        external = [
            Resource(
                path=Path("ENV:ANTHROPIC_API_KEY"),
                resource_type=ResourceType.ENV_VAR,
                scope=ResourceScope.EXTERNAL,
                display_name="ANTHROPIC_API_KEY",
                content="sk-ant-test",
                masked=True,
            ),
        ]
        root = build_tree([], [], [], external)
        ext_node = root.children[0]
        assert ext_node.label == "External"


class TestTreeNode:
    def test_is_category(self):
        parent = TreeNode(label="Category")
        parent.add_child(TreeNode(label="child", resource=Resource(
            path=Path("x"), resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER, display_name="x",
        )))
        assert parent.is_category is True

    def test_leaf_not_category(self):
        leaf = TreeNode(label="leaf", resource=Resource(
            path=Path("x"), resource_type=ResourceType.SETTINGS,
            scope=ResourceScope.USER, display_name="x",
        ))
        assert leaf.is_category is False
