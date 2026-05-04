from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULTS_TOML = Path(__file__).parent / "defaults.toml"
_USER_CONFIG_PATH = Path.home() / ".razd" / "config.toml"


@dataclass
class TrackingSettings:
    poll_interval_ms: int = 2000
    idle_threshold_secs: int = 60
    browser_url_enabled: bool = True


@dataclass
class AgentSettings:
    unknown_process_cooldown_secs: int = 300
    max_pending_questions: int = 5


@dataclass
class FocusSettings:
    default_duration_mins: int = 25
    alert_sound: bool = False
    whitelist: list[str] = field(default_factory=list)


@dataclass
class NotionSettings:
    enabled: bool = False
    sync_interval_mins: int = 15
    export_urls: bool = False


@dataclass
class RazdSettings:
    tracking: TrackingSettings = field(default_factory=TrackingSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    focus: FocusSettings = field(default_factory=FocusSettings)
    notion: NotionSettings = field(default_factory=NotionSettings)
    db_path: Path = field(default_factory=lambda: Path.home() / ".razd" / "razd.db")
    break_interval_min: int = 50

    @classmethod
    def load(cls) -> RazdSettings:
        """Wczytuje defaults + opcjonalny user config (merge)."""
        data = tomllib.loads(_DEFAULTS_TOML.read_text(encoding="utf-8"))
        if _USER_CONFIG_PATH.exists():
            user = tomllib.loads(_USER_CONFIG_PATH.read_text(encoding="utf-8"))
            _deep_merge(data, user)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, d: dict) -> RazdSettings:
        t = d.get("tracking", {})
        a = d.get("agent", {})
        f = d.get("focus", {})
        p = d.get("paths", {})

        db_path = Path(p["db"]).expanduser() if "db" in p else Path.home() / ".razd" / "razd.db"

        n = d.get("notion", {})

        return cls(
            tracking=TrackingSettings(
                poll_interval_ms=t.get("poll_interval_ms", 2000),
                idle_threshold_secs=t.get("idle_threshold_secs", 60),
                browser_url_enabled=t.get("browser_url_enabled", True),
            ),
            agent=AgentSettings(
                unknown_process_cooldown_secs=a.get("unknown_process_cooldown_secs", 300),
                max_pending_questions=a.get("max_pending_questions", 5),
            ),
            focus=FocusSettings(
                default_duration_mins=f.get("default_duration_mins", 25),
                alert_sound=f.get("alert_sound", False),
                whitelist=f.get("whitelist", []),
            ),
            notion=NotionSettings(
                enabled=n.get("enabled", False),
                sync_interval_mins=n.get("sync_interval_mins", 15),
                export_urls=n.get("export_urls", False),
            ),
            db_path=db_path,
            break_interval_min=d.get("break", {}).get("work_interval_min", 50),
        )

    def save_user(self) -> None:
        """Zapisuje bieżące ustawienia do ~/.razd/config.toml (tylko sekcje zmodyfikowane)."""
        _USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        db_posix = self.db_path.as_posix()
        lines = [
            "[tracking]",
            f"poll_interval_ms = {self.tracking.poll_interval_ms}",
            f"idle_threshold_secs = {self.tracking.idle_threshold_secs}",
            f"browser_url_enabled = {str(self.tracking.browser_url_enabled).lower()}",
            "",
            "[agent]",
            f"unknown_process_cooldown_secs = {self.agent.unknown_process_cooldown_secs}",
            f"max_pending_questions = {self.agent.max_pending_questions}",
            "",
            "[focus]",
            f"default_duration_mins = {self.focus.default_duration_mins}",
            f"alert_sound = {str(self.focus.alert_sound).lower()}",
            f"whitelist = {_toml_list(self.focus.whitelist)}",
            "",
            "[paths]",
            f'db = "{db_posix}"',
        ]
        _USER_CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base in-place (shallow per section)."""
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def _toml_list(lst: list[str]) -> str:
    items = ", ".join(f'"{x}"' for x in lst)
    return f"[{items}]"
