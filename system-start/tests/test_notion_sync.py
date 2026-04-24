"""
Testy notion_sync.py z mockiem klienta Notion — nie uderzają w live API.
Podstrony tworzone jako dzieci rekordu w PCC_Projects (nie w NOTION_PARENT_PAGE).
Stan trzymany w logs/notion_state.json.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notion_sync import _extract_meta, _page_id_from_url, sync


SAMPLE_PLAN = """\
<!-- PLAN v2.0 -->
## Meta
<!-- SECTION:meta -->
- status: active
- goal: Test goal notion
- session: 3
- updated: 2026-04-24 10:00
<!-- /SECTION:meta -->
## Session Log
<!-- SECTION:session_log -->
- 2026-04-24 10:00 | init
- 2026-04-24 11:00 | step done
<!-- /SECTION:session_log -->
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_extract_meta_parses_fields():
    meta = _extract_meta(SAMPLE_PLAN)
    assert meta["status"] == "active"
    assert meta["goal"] == "Test goal notion"
    assert meta["session"] == "3"


def test_extract_meta_empty():
    meta = _extract_meta("bez sekcji meta")
    assert meta == {}


def test_page_id_from_url_standard():
    url = "https://www.notion.so/SomeTitle-b278a890e4a54d61b3f61d2058dba11c"
    pid = _page_id_from_url(url)
    assert "b278a890" in pid
    assert len(pid) == 36


def test_page_id_from_url_plain():
    url = "https://www.notion.so/b278a890e4a54d61b3f61d2058dba11c"
    pid = _page_id_from_url(url)
    assert "b278a890" in pid


# ---------------------------------------------------------------------------
# Mock factory
# ---------------------------------------------------------------------------

EXISTING_CHILD_URLS = {
    "CLAUDE.md":        "https://www.notion.so/CLAUDE-b278a890e4a54d61b3f61d2058dba111",
    "ARCHITECTURE.md":  "https://www.notion.so/ARCH-b278a890e4a54d61b3f61d2058dba112",
    "PLAN.md":          "https://www.notion.so/PLAN-b278a890e4a54d61b3f61d2058dba113",
    "CONVENTIONS.md":   "https://www.notion.so/CONV-b278a890e4a54d61b3f61d2058dba114",
    "pcc.log":          "https://www.notion.so/LOG-b278a890e4a54d61b3f61d2058dba115",
}


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.pages.create.return_value = {
        "url": "https://www.notion.so/New-b278a890e4a54d61b3f61d2058dba11c",
        "id": "new-record-id-1234",
    }
    client.pages.retrieve.return_value = {"id": "existing-record-id"}
    client.blocks.children.list.return_value = {"results": []}
    return client


def _write_state(state_path: Path, project_name: str,
                 record_id: str, child_urls: dict) -> None:
    state_path.parent.mkdir(exist_ok=True)
    state_path.write_text(
        json.dumps({project_name: {"record_id": record_id, "child_urls": child_urls}}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# sync() — nowy rekord
# ---------------------------------------------------------------------------

def test_sync_creates_new_record(tmp_path):
    for fname in ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]:
        (tmp_path / fname).write_text(f"# {fname}\ncontent", encoding="utf-8")
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")

    mock_client = _make_mock_client()
    state_file = tmp_path / "logs" / "notion_state.json"

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        result = sync(project_dir=tmp_path, project_name="TestProject")

    # 1 rekord DB + 5 podstron (4 MD + pcc.log) = 6 wywołań pages.create
    assert mock_client.pages.create.call_count == 6
    assert len(result) == 5
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert "TestProject" in state
    assert state["TestProject"]["record_id"] == "new-record-id-1234"


def test_sync_record_created_with_database_id_parent(tmp_path):
    """Rekord w DB tworzony z parent database_id."""
    for fname in ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]:
        (tmp_path / fname).write_text("x", encoding="utf-8")
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")

    mock_client = _make_mock_client()
    state_file = tmp_path / "logs" / "notion_state.json"

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        sync(project_dir=tmp_path, project_name="TestProject")

    # Pierwsze pages.create to rekord DB
    first_call_kwargs = mock_client.pages.create.call_args_list[0][1]
    assert first_call_kwargs["parent"]["type"] == "database_id"


def test_sync_subpages_created_as_children_of_record(tmp_path):
    """Podstrony MD tworzone jako dzieci rekordu, nie NOTION_PARENT_PAGE."""
    for fname in ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]:
        (tmp_path / fname).write_text("x", encoding="utf-8")
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")

    mock_client = _make_mock_client()
    state_file = tmp_path / "logs" / "notion_state.json"

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        sync(project_dir=tmp_path, project_name="TestProject")

    # Wywołania pages.create po rekordzie (indeksy 1-5) mają parent page_id = record_id
    for call in mock_client.pages.create.call_args_list[1:]:
        parent = call[1].get("parent", {})
        assert parent.get("type") == "page_id"
        assert parent.get("page_id") == "new-record-id-1234"


# ---------------------------------------------------------------------------
# sync() — istniejący rekord (stan z pliku)
# ---------------------------------------------------------------------------

def test_sync_updates_existing_record(tmp_path):
    for fname in ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]:
        (tmp_path / fname).write_text(f"# {fname}\nupdated", encoding="utf-8")
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")

    state_file = tmp_path / "logs" / "notion_state.json"
    _write_state(state_file, "TestProject", "existing-record-id", EXISTING_CHILD_URLS)

    mock_client = _make_mock_client()

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        result = sync(project_dir=tmp_path, project_name="TestProject")

    # Brak pages.create — rekord i podstrony już istnieją
    mock_client.pages.create.assert_not_called()
    mock_client.pages.update.assert_called_once()
    assert len(result) == 5


def test_sync_no_query_called(tmp_path):
    """Sync nie wywołuje żadnego query — stan pochodzi z pliku."""
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")
    for f in ["CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md"]:
        (tmp_path / f).write_text("x", encoding="utf-8")

    mock_client = _make_mock_client()
    state_file = tmp_path / "logs" / "notion_state.json"

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        sync(project_dir=tmp_path, project_name="TestProject")

    mock_client.data_sources.query.assert_not_called()
    mock_client.databases.query.assert_not_called()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_sync_missing_md_files(tmp_path):
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")
    mock_client = _make_mock_client()
    state_file = tmp_path / "logs" / "notion_state.json"

    with patch("src.notion_sync._client", return_value=mock_client), \
         patch("src.notion_sync.STATE_FILE", state_file), \
         patch("src.notion_sync.LOG_FILE", tmp_path / "pcc.log"):
        result = sync(project_dir=tmp_path, project_name="MinimalProject")

    assert "PLAN.md" in result


def test_sync_raises_without_token(tmp_path, monkeypatch):
    import src.notion_sync as ns
    import pytest
    monkeypatch.setattr(ns, "NOTION_TOKEN", "")
    (tmp_path / "PLAN.md").write_text(SAMPLE_PLAN, encoding="utf-8")

    with pytest.raises(RuntimeError, match="NOTION_TOKEN"):
        sync(project_dir=tmp_path, project_name="X")
