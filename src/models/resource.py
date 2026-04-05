"""Resource model representing a single Claude Code configuration file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ResourceType(Enum):
    SETTINGS = "settings"
    MEMORY = "memory"
    RULES = "rules"
    SKILLS = "skills"
    HOOKS = "hooks"
    MCP = "mcp"
    AGENTS = "agents"
    CLAUDE_MD = "claude_md"
    CREDENTIALS = "credentials"
    EXTERNAL = "external"
    ENV_VAR = "env_var"
    PROJECT_INFO = "project_info"
    HISTORY = "history"


class ResourceScope(Enum):
    MANAGED = "managed"
    USER = "user"
    PROJECT = "project"
    LOCAL = "local"
    AUTO_MEMORY = "auto_memory"
    EXTERNAL = "external"


@dataclass
class Resource:
    path: Path
    resource_type: ResourceType
    scope: ResourceScope
    display_name: str
    content: str | None = None
    last_modified: datetime | None = None
    read_only: bool = False
    masked: bool = False
    children: list[Resource] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def file_format(self) -> str:
        from src.utils.parsers import detect_file_format
        return detect_file_format(self.path)

    def load_content(self) -> str | None:
        """Load file content from disk."""
        if not self.path.exists():
            self.content = None
            return None
        try:
            self.content = self.path.read_text(encoding="utf-8")
            self.last_modified = datetime.fromtimestamp(self.path.stat().st_mtime)
        except (OSError, UnicodeDecodeError):
            self.content = None
        return self.content
