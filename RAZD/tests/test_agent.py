from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from razd.agent.prompts import SYSTEM_PROMPT
from razd.tracker.poller import EventDTO


# --- prompts ---

def test_system_prompt_not_empty() -> None:
    assert len(SYSTEM_PROMPT) > 50
    assert "kategoryzuj" in SYSTEM_PROMPT.lower() or "kategori" in SYSTEM_PROMPT.lower()


# --- tools ---

def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo.upsert_category.return_value = 1
    repo.get_category_by_name.return_value = None
    repo.list_categories.return_value = []
    return repo


@pytest.mark.asyncio
async def test_save_category_process(tmp_path) -> None:
    from pathlib import Path
    import sqlite3
    from razd.db.repository import RazdRepository

    repo = RazdRepository(tmp_path / "test.db")
    ask_cb = MagicMock(return_value="notatnik")

    with patch("claude_code_sdk.create_sdk_mcp_server", return_value=MagicMock()):
        from razd.agent.tools import build_mcp_server
        # Testujemy logikę save_category bezpośrednio przez repo
        cid = repo.upsert_category("IDE", "#aabb00", True)
        repo.upsert_process("code.exe", cid)
        assert repo.get_category_for_process("code.exe") == cid

    repo.close()


@pytest.mark.asyncio
async def test_query_knowledge_unknown(tmp_path) -> None:
    from razd.db.repository import RazdRepository

    repo = RazdRepository(tmp_path / "test.db")
    result = repo.get_category_for_process("chrome.exe")
    assert result is None
    repo.close()


# --- EventDTO kolejkowanie ---

def test_event_dto_idle_has_idle_type() -> None:
    dto = EventDTO(
        ts="2026-04-29T10:00:00+00:00",
        event_type="idle",
        process_name=None,
        window_title=None,
        url=None,
        idle_seconds=120.0,
    )
    assert dto.event_type == "idle"
    assert dto.idle_seconds == 120.0


def test_event_dto_browser_has_url() -> None:
    dto = EventDTO(
        ts="2026-04-29T10:01:00+00:00",
        event_type="browser",
        process_name="chrome.exe",
        window_title="GitHub",
        url="https://github.com/user/repo",
        idle_seconds=0.0,
    )
    assert dto.url is not None
    assert "github" in dto.url
