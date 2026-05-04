"""Snippet manager — ładuje snippety z builtin.yaml + user override."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml  # ruamel.yaml lub PyYAML
    _HAS_YAML = True
except ImportError:
    try:
        from ruamel.yaml import YAML as _RUAMEL
        _HAS_YAML = True
        yaml = None  # obsłużone niżej
    except ImportError:
        _HAS_YAML = False

_BUILTIN_PATH = Path(__file__).resolve().parent.parent / "snippets" / "builtin.yaml"
_USER_PATH = Path.home() / ".claude" / "hooker_snippets_user.yaml"


@dataclass
class Snippet:
    name: str
    hook_type: str
    command: str
    description: str = ""
    matcher: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Snippet":
        return cls(
            name=d.get("name", ""),
            hook_type=d.get("hook_type", "PreToolUse"),
            command=d.get("command", ""),
            description=d.get("description", ""),
            matcher=d.get("matcher", ""),
            tags=d.get("tags", []),
        )


def _load_yaml(path: Path) -> list[dict]:
    if not path.exists() or not _HAS_YAML:
        return []
    try:
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(text)
        else:
            from ruamel.yaml import YAML
            _yaml = YAML()
            import io
            data = _yaml.load(io.StringIO(text))
        return data.get("snippets", []) if isinstance(data, dict) else []
    except Exception:
        return []


def load_snippets() -> list[Snippet]:
    """Ładuje snippety: builtin + user override (user nadpisuje po nazwie)."""
    builtin = {s["name"]: s for s in _load_yaml(_BUILTIN_PATH) if "name" in s}
    user = {s["name"]: s for s in _load_yaml(_USER_PATH) if "name" in s}
    merged = {**builtin, **user}
    return [Snippet.from_dict(d) for d in merged.values()]


def snippets_for_type(hook_type: str) -> list[Snippet]:
    """Zwraca snippety pasujące do podanego typu hooka."""
    return [s for s in load_snippets() if s.hook_type == hook_type]
