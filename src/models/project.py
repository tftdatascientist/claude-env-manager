"""Project model representing a git repository with Claude resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.models.resource import Resource


@dataclass
class Project:
    name: str
    root_path: Path
    resources: list[Resource] = field(default_factory=list)
    session_count: int = 0

    @property
    def has_claude_config(self) -> bool:
        return len(self.resources) > 0
