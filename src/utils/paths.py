"""Resolving Windows paths for Claude Code resources."""

import os
from pathlib import Path


def home_dir() -> Path:
    return Path.home()


def claude_dir() -> Path:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return home_dir() / ".claude"


def claude_global_state_path() -> Path:
    return home_dir() / ".claude.json"


def managed_dir() -> Path:
    return Path("C:/Program Files/ClaudeCode")


# --- Managed (read-only) ---

def managed_settings_path() -> Path:
    return managed_dir() / "managed-settings.json"


def managed_claude_md_path() -> Path:
    return managed_dir() / "CLAUDE.md"


# --- User-level ---

def user_settings_path() -> Path:
    return claude_dir() / "settings.json"


def user_settings_local_path() -> Path:
    return claude_dir() / "settings.local.json"


def user_credentials_path() -> Path:
    return claude_dir() / ".credentials.json"


def user_claude_md_path() -> Path:
    return claude_dir() / "CLAUDE.md"


def user_mcp_path() -> Path:
    return claude_dir() / ".mcp.json"


def user_history_path() -> Path:
    return claude_dir() / "history.jsonl"


def user_rules_dir() -> Path:
    return claude_dir() / "rules"


def user_skills_dir() -> Path:
    return claude_dir() / "skills"


# --- Projects memory ---

def projects_dir() -> Path:
    return claude_dir() / "projects"


# --- External ---

def gitconfig_path() -> Path:
    return home_dir() / ".gitconfig"


def ssh_dir() -> Path:
    return home_dir() / ".ssh"


def vscode_settings_path() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "Code" / "User" / "settings.json"
    return home_dir() / "AppData" / "Roaming" / "Code" / "User" / "settings.json"


# Environment variables relevant to Claude Code
CLAUDE_ENV_VARS: list[str] = [
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
    "CLAUDE_CODE_GIT_BASH_PATH",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_ENV_FILE",
    "CLAUDE_CODE_REMOTE",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
]

SENSITIVE_ENV_VARS: set[str] = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
