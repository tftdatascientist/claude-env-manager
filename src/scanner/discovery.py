"""Discover all Claude Code resources on the filesystem."""

from __future__ import annotations

import os
from pathlib import Path

from src.models.project import Project
from src.models.resource import Resource, ResourceScope, ResourceType
from src.utils import paths


def _resource(
    path: Path,
    rtype: ResourceType,
    scope: ResourceScope,
    display_name: str,
    *,
    read_only: bool = False,
    masked: bool = False,
) -> Resource | None:
    """Create a Resource if the path exists."""
    if not path.exists():
        return None
    return Resource(
        path=path,
        resource_type=rtype,
        scope=scope,
        display_name=display_name,
        read_only=read_only,
        masked=masked,
    )


def discover_managed() -> list[Resource]:
    """Discover managed (read-only) resources."""
    results: list[Resource] = []
    r = _resource(
        paths.managed_settings_path(),
        ResourceType.SETTINGS, ResourceScope.MANAGED,
        "managed-settings.json", read_only=True,
    )
    if r:
        results.append(r)
    r = _resource(
        paths.managed_claude_md_path(),
        ResourceType.CLAUDE_MD, ResourceScope.MANAGED,
        "CLAUDE.md", read_only=True,
    )
    if r:
        results.append(r)
    return results


def discover_user() -> list[Resource]:
    """Discover user-level resources."""
    results: list[Resource] = []

    candidates = [
        (paths.user_settings_path(), ResourceType.SETTINGS, "settings.json", False, False),
        (paths.user_settings_local_path(), ResourceType.SETTINGS, "settings.local.json", False, False),
        (paths.user_claude_md_path(), ResourceType.CLAUDE_MD, "CLAUDE.md", False, False),
        (paths.user_credentials_path(), ResourceType.CREDENTIALS, ".credentials.json", False, True),
        (paths.user_mcp_path(), ResourceType.MCP, ".mcp.json", False, False),
        (paths.claude_global_state_path(), ResourceType.SETTINGS, ".claude.json", False, False),
    ]

    for path, rtype, name, ro, masked in candidates:
        r = _resource(path, rtype, ResourceScope.USER, name, read_only=ro, masked=masked)
        if r:
            results.append(r)

    # Rules
    rules_dir = paths.user_rules_dir()
    if rules_dir.is_dir():
        for md_file in sorted(rules_dir.glob("*.md")):
            results.append(Resource(
                path=md_file,
                resource_type=ResourceType.RULES,
                scope=ResourceScope.USER,
                display_name=md_file.name,
            ))

    # Skills
    skills_dir = paths.user_skills_dir()
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            results.append(Resource(
                path=skill_md,
                resource_type=ResourceType.SKILLS,
                scope=ResourceScope.USER,
                display_name=skill_md.parent.name,
            ))

    return results


def _discover_project_resources(project_root: Path) -> list[Resource]:
    """Discover Claude resources within a single project directory."""
    results: list[Resource] = []
    claude_dir = project_root / ".claude"

    candidates = [
        (project_root / "CLAUDE.md", ResourceType.CLAUDE_MD, ResourceScope.PROJECT, "CLAUDE.md"),
        (claude_dir / "CLAUDE.md", ResourceType.CLAUDE_MD, ResourceScope.PROJECT, ".claude/CLAUDE.md"),
        (project_root / "CLAUDE.local.md", ResourceType.CLAUDE_MD, ResourceScope.LOCAL, "CLAUDE.local.md"),
        (claude_dir / "settings.json", ResourceType.SETTINGS, ResourceScope.PROJECT, "settings.json"),
        (claude_dir / "settings.local.json", ResourceType.SETTINGS, ResourceScope.LOCAL, "settings.local.json"),
        (project_root / ".mcp.json", ResourceType.MCP, ResourceScope.PROJECT, ".mcp.json"),
    ]

    for path, rtype, scope, name in candidates:
        r = _resource(path, rtype, scope, name)
        if r:
            results.append(r)

    # Project rules
    rules_dir = claude_dir / "rules"
    if rules_dir.is_dir():
        for md_file in sorted(rules_dir.glob("*.md")):
            results.append(Resource(
                path=md_file,
                resource_type=ResourceType.RULES,
                scope=ResourceScope.PROJECT,
                display_name=md_file.name,
            ))

    # Project agents
    agents_dir = claude_dir / "agents"
    if agents_dir.is_dir():
        for md_file in sorted(agents_dir.glob("*.md")):
            results.append(Resource(
                path=md_file,
                resource_type=ResourceType.AGENTS,
                scope=ResourceScope.PROJECT,
                display_name=md_file.name,
            ))

    return results


def discover_projects() -> list[Project]:
    """Discover projects by scanning ~/.claude/projects/ for all project directories."""
    projects: list[Project] = []

    proj_dir = paths.projects_dir()
    if not proj_dir.is_dir():
        return projects

    for hash_dir in sorted(proj_dir.iterdir()):
        if not hash_dir.is_dir():
            continue

        dir_name = hash_dir.name
        project_path = _resolve_project_path(dir_name)
        display_name = _make_display_name(dir_name)

        # Collect memory resources
        memory_resources: list[Resource] = []
        memory_dir = hash_dir / "memory"
        if memory_dir.is_dir():
            for md_file in sorted(memory_dir.glob("*.md")):
                memory_resources.append(Resource(
                    path=md_file,
                    resource_type=ResourceType.MEMORY,
                    scope=ResourceScope.AUTO_MEMORY,
                    display_name=md_file.name,
                ))

        # Agent memory
        agents_mem_dir = hash_dir / "agents"
        if agents_mem_dir.is_dir():
            for agent_dir in sorted(agents_mem_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue
                agent_memory = agent_dir / "memory"
                if agent_memory.is_dir():
                    for md_file in sorted(agent_memory.glob("*.md")):
                        memory_resources.append(Resource(
                            path=md_file,
                            resource_type=ResourceType.MEMORY,
                            scope=ResourceScope.AUTO_MEMORY,
                            display_name=f"{agent_dir.name}/{md_file.name}",
                        ))

        # Session count as info
        session_count = len(list(hash_dir.glob("*.jsonl")))

        # Discover project-level resources from actual project directory
        project_resources: list[Resource] = []
        if project_path and project_path.is_dir():
            project_resources = _discover_project_resources(project_path)

        all_resources = project_resources + memory_resources
        root = project_path if project_path else hash_dir
        name = project_path.name if project_path else display_name

        # Always include the project, even with no resources (show session count)
        projects.append(Project(
            name=name,
            root_path=root,
            resources=all_resources,
            session_count=session_count,
        ))

    return projects


def _make_display_name(hash_dir_name: str) -> str:
    """Extract a human-readable project name from the hash directory name.

    E.g. 'C--Users-S-awek-Documents--MD-PARA-SER-10-PROJEKTY-SIDE-LEWY'
    -> 'SIDE-LEWY' (last meaningful segment)
    """
    # Remove drive prefix like "C--Users-S-awek-" or "c--Users-S-awek-"
    name = hash_dir_name
    # Strip the common user prefix pattern
    import re
    name = re.sub(r'^[Cc]--Users-[^-]+-[^-]+-', '', name)
    if not name:
        return hash_dir_name

    # Take the last segment(s) after the last -- (which was a path separator)
    if '--' in name:
        parts = name.split('--')
        name = parts[-1]

    # If still long, take last 2 dash-segments for context
    segments = name.split('-')
    if len(segments) > 4:
        name = '-'.join(segments[-3:])

    return name or hash_dir_name


def _encode_path(path: Path) -> str:
    """Encode a filesystem path the same way Claude Code does.

    Every non-alphanumeric, non-dash character becomes a dash.
    This includes path separators, dots, underscores, exclamation marks, spaces, non-ASCII.
    """
    raw = str(path)
    result = ""
    for ch in raw:
        if ch.isascii() and (ch.isalnum() or ch == "-"):
            result += ch
        else:
            result += "-"
    return result


def _resolve_project_path(hash_dir_name: str) -> Path | None:
    """Resolve a project path from the hashed directory name.

    Strategy: walk the filesystem starting from home, encoding each candidate
    path and comparing with the hash to find the right one.
    """
    home = Path.home()
    home_encoded = _encode_path(home)

    # Check if hash starts with the home prefix (case-insensitive for drive letter)
    hash_lower = hash_dir_name.lower()
    home_lower = home_encoded.lower()
    if not hash_lower.startswith(home_lower + "-"):
        return None

    after_home = hash_dir_name[len(home_encoded) + 1:]
    return _walk_resolve(home, after_home)


def _encode_name(name: str) -> str:
    """Encode a single directory/file name the way Claude Code does."""
    result = ""
    for ch in name:
        if ch.isascii() and (ch.isalnum() or ch == "-"):
            result += ch
        else:
            result += "-"
    return result


def _walk_resolve(base: Path, remaining_hash: str) -> Path | None:
    """Walk filesystem, encoding real dirs and matching against the hash."""
    if not remaining_hash:
        return base

    if not base.is_dir():
        return None

    try:
        entries = list(base.iterdir())
    except OSError:
        return None

    # Build candidates: (encoded_name, actual_path)
    candidates: list[tuple[str, Path]] = []
    for entry in entries:
        if not entry.is_dir():
            continue
        candidates.append((_encode_name(entry.name), entry))

    # Sort by longest encoded name first (greedy match avoids wrong splits)
    candidates.sort(key=lambda x: -len(x[0]))

    for encoded_name, actual_path in candidates:
        if remaining_hash == encoded_name:
            return actual_path
        if remaining_hash.startswith(encoded_name + "-"):
            rest = remaining_hash[len(encoded_name) + 1:]
            result = _walk_resolve(actual_path, rest)
            if result is not None:
                return result

    return None


def discover_external() -> list[Resource]:
    """Discover external resources (gitconfig, VS Code, SSH, env vars)."""
    results: list[Resource] = []

    r = _resource(
        paths.gitconfig_path(), ResourceType.EXTERNAL,
        ResourceScope.EXTERNAL, ".gitconfig",
    )
    if r:
        results.append(r)

    r = _resource(
        paths.vscode_settings_path(), ResourceType.EXTERNAL,
        ResourceScope.EXTERNAL, "VS Code settings.json",
    )
    if r:
        results.append(r)

    # SSH keys - list filenames only, not content
    ssh_dir = paths.ssh_dir()
    if ssh_dir.is_dir():
        for f in sorted(ssh_dir.iterdir()):
            if f.is_file() and f.suffix in (".pub", ""):
                is_private = f.suffix == "" and not f.name.startswith("known_hosts") and not f.name == "config"
                results.append(Resource(
                    path=f,
                    resource_type=ResourceType.EXTERNAL,
                    scope=ResourceScope.EXTERNAL,
                    display_name=f"SSH: {f.name}",
                    read_only=True,
                    masked=is_private,
                ))

    # Environment variables
    for var_name in paths.CLAUDE_ENV_VARS:
        value = os.environ.get(var_name)
        if value:
            results.append(Resource(
                path=Path(f"ENV:{var_name}"),
                resource_type=ResourceType.ENV_VAR,
                scope=ResourceScope.EXTERNAL,
                display_name=var_name,
                content=value,
                masked=var_name in paths.SENSITIVE_ENV_VARS,
            ))

    return results


def discover_all() -> tuple[list[Resource], list[Resource], list[Project], list[Resource]]:
    """Discover all resources. Returns (managed, user, projects, external)."""
    return (
        discover_managed(),
        discover_user(),
        discover_projects(),
        discover_external(),
    )
