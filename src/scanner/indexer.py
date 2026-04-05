"""Build a tree model from discovered resources for the UI TreeView."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.project import Project
from src.models.resource import Resource, ResourceScope, ResourceType


@dataclass
class TreeNode:
    """A node in the resource tree. Can be a category or a leaf resource."""
    label: str
    resource: Resource | None = None
    children: list[TreeNode] = field(default_factory=list)
    expanded: bool = True

    @property
    def is_category(self) -> bool:
        return self.resource is None and len(self.children) > 0

    def add_child(self, node: TreeNode) -> TreeNode:
        self.children.append(node)
        return node


def _group_by_type(resources: list[Resource]) -> dict[str, list[Resource]]:
    """Group resources by their type into named sub-categories."""
    groups: dict[str, list[Resource]] = {}
    for r in resources:
        if r.resource_type == ResourceType.RULES:
            groups.setdefault("Rules", []).append(r)
        elif r.resource_type == ResourceType.SKILLS:
            groups.setdefault("Skills", []).append(r)
        elif r.resource_type == ResourceType.AGENTS:
            groups.setdefault("Agents", []).append(r)
        elif r.resource_type == ResourceType.MEMORY:
            groups.setdefault("Memory", []).append(r)
        else:
            groups.setdefault("_top", []).append(r)
    return groups


def _build_grouped_children(resources: list[Resource]) -> list[TreeNode]:
    """Build child nodes, grouping rules/skills/agents/memory into sub-folders."""
    children: list[TreeNode] = []
    groups = _group_by_type(resources)

    # Top-level items first
    for r in groups.get("_top", []):
        children.append(TreeNode(label=r.display_name, resource=r))

    # Sub-categories
    for category in ("Rules", "Skills", "Agents", "Memory"):
        items = groups.get(category, [])
        if items:
            cat_node = TreeNode(label=f"{category}/")
            for r in items:
                cat_node.add_child(TreeNode(label=r.display_name, resource=r))
            children.append(cat_node)

    return children


def build_tree(
    managed: list[Resource],
    user: list[Resource],
    projects: list[Project],
    external: list[Resource],
) -> TreeNode:
    """Build the full resource tree from discovered data."""
    root = TreeNode(label="Root")

    # Managed
    if managed:
        managed_node = TreeNode(label="Managed (read-only)")
        for r in managed:
            managed_node.add_child(TreeNode(label=r.display_name, resource=r))
        root.add_child(managed_node)

    # User
    if user:
        user_node = TreeNode(label="User")
        user_node.children = _build_grouped_children(user)
        root.add_child(user_node)

    # Projects
    if projects:
        projects_node = TreeNode(label=f"Projects ({len(projects)})")
        for project in projects:
            session_info = f" [{project.session_count}s]" if project.session_count else ""

            # Build project info content
            lines = [f"Project: {project.name}"]
            lines.append(f"Path: {project.root_path}")
            lines.append(f"Sessions: {project.session_count}")
            lines.append(f"Resources: {len(project.resources)}")
            if project.resources:
                lines.append("")
                for r in project.resources:
                    lines.append(f"  [{r.resource_type.value}] {r.display_name}")

            info_resource = Resource(
                path=project.root_path,
                resource_type=ResourceType.PROJECT_INFO,
                scope=ResourceScope.PROJECT,
                display_name=project.name,
                content="\n".join(lines),
                read_only=True,
            )

            proj_node = TreeNode(
                label=f"{project.name}{session_info}",
                resource=info_resource,
            )
            if project.resources:
                proj_node.children = _build_grouped_children(project.resources)
            projects_node.add_child(proj_node)
        root.add_child(projects_node)

    # External
    if external:
        ext_node = TreeNode(label="External")
        env_vars = [r for r in external if r.resource_type == ResourceType.ENV_VAR]
        ssh_keys = [r for r in external if r.display_name.startswith("SSH:")]
        other = [r for r in external if r not in env_vars and r not in ssh_keys]

        for r in other:
            ext_node.add_child(TreeNode(label=r.display_name, resource=r))

        if ssh_keys:
            ssh_node = TreeNode(label="SSH keys/")
            for r in ssh_keys:
                ssh_node.add_child(TreeNode(label=r.display_name, resource=r))
            ext_node.add_child(ssh_node)

        if env_vars:
            env_node = TreeNode(label="Environment variables")
            for r in env_vars:
                env_node.add_child(TreeNode(label=r.display_name, resource=r))
            ext_node.add_child(env_node)

        root.add_child(ext_node)

    return root
