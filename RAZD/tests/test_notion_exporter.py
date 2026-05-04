from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from razd.db.repository import RazdRepository
from razd.notion.exporter import RazdNotionExporter, _normalize_process, _map_category_name
from razd.notion.schema import NotionActivityRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path: Path) -> RazdRepository:
    r = RazdRepository(tmp_path / "test.db")
    cat_id = r.upsert_category("Praca")
    r.insert_event(
        ts="2026-04-30T10:00:00",
        event_type="active",
        raw_json="{}",
        process_name="chrome.exe",
        window_title="GitHub",
        url=None,
        idle_seconds=0,
        category_id=cat_id,
    )
    r.insert_event(
        ts="2026-04-30T10:00:02",
        event_type="active",
        raw_json="{}",
        process_name="chrome.exe",
        window_title="GitHub",
        url=None,
        idle_seconds=0,
        category_id=cat_id,
    )
    return r


@pytest.fixture
def exporter(repo: RazdRepository) -> RazdNotionExporter:
    return RazdNotionExporter(
        repo=repo,
        token="secret_test",
        db_id="abc123",
        export_urls=False,
    )


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------

def test_normalize_process_strips_exe():
    assert _normalize_process("chrome.exe") == "chrome"


def test_normalize_process_strips_path():
    assert _normalize_process(r"C:\Program Files\code.exe") == "code"


def test_normalize_process_empty():
    assert _normalize_process("") == "unknown"


def test_map_category_known():
    assert _map_category_name("praca") == "Praca"
    assert _map_category_name("Nauka") == "Nauka"


def test_map_category_unknown():
    assert _map_category_name("cokolwiek") == "Inne"


# ---------------------------------------------------------------------------
# NotionActivityRecord.to_notion_properties
# ---------------------------------------------------------------------------

def test_record_properties_no_url():
    rec = NotionActivityRecord(
        name="chrome — 2026-04-30",
        category="Praca",
        duration_mins=5,
        date="2026-04-30",
        processes=["chrome"],
        url="https://example.com",
    )
    props = rec.to_notion_properties(export_urls=False)
    assert "URL" not in props
    assert props["Kategoria"]["select"]["name"] == "Praca"


def test_record_properties_with_url():
    rec = NotionActivityRecord(
        name="chrome — 2026-04-30",
        category="Praca",
        duration_mins=5,
        date="2026-04-30",
        url="https://example.com",
    )
    props = rec.to_notion_properties(export_urls=True)
    assert props["URL"]["url"] == "https://example.com"


def test_record_agent_note_truncated():
    rec = NotionActivityRecord(
        name="x",
        category="Inne",
        duration_mins=1,
        date="2026-04-30",
        agent_note="A" * 3000,
    )
    props = rec.to_notion_properties()
    note = props["Notatka agenta"]["rich_text"][0]["text"]["content"]
    assert len(note) == 2000


# ---------------------------------------------------------------------------
# RazdNotionExporter — insert happy path
# ---------------------------------------------------------------------------

def test_export_session_inserts_new_page(exporter: RazdNotionExporter):
    mock_client = MagicMock()
    mock_client.databases.query.return_value = {"results": []}
    mock_client.pages.create.return_value = {"id": "page-111"}
    exporter._client = mock_client

    page_id = exporter.export_session(date(2026, 4, 30))

    assert page_id == "page-111"
    mock_client.pages.create.assert_called_once()


def test_export_session_updates_existing_page(exporter: RazdNotionExporter):
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "id": "existing-page-999",
                "parent": {"database_id": "abc123"},
                "properties": {
                    "Nazwa": {"title": [{"plain_text": "chrome — 2026-04-30"}]}
                },
            }
        ]
    }
    exporter._client = mock_client

    exporter.export_session(date(2026, 4, 30))

    mock_client.pages.update.assert_called_once()
    mock_client.pages.create.assert_not_called()


def test_export_session_no_events_returns_none(exporter: RazdNotionExporter):
    result = exporter.export_session(date(2099, 1, 1))
    assert result is None


def test_export_session_missing_token(repo):
    exp = RazdNotionExporter(repo=repo, token="", db_id="abc")
    result = exp.export_session(date(2026, 4, 30))
    assert result is None


# ---------------------------------------------------------------------------
# Privacy — URL nie trafia do Notion domyślnie
# ---------------------------------------------------------------------------

def test_url_not_exported_by_default(exporter: RazdNotionExporter):
    mock_client = MagicMock()
    mock_client.databases.query.return_value = {"results": []}
    mock_client.pages.create.return_value = {"id": "p1"}
    exporter._client = mock_client

    exporter.export_session(date(2026, 4, 30))

    call_kwargs = mock_client.pages.create.call_args
    props = call_kwargs.kwargs.get("properties") or call_kwargs[1].get("properties", {})
    assert "URL" not in props
