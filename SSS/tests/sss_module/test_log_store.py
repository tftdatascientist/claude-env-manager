import pytest
from src.cm.sss_module.core.log_store import LogStore


@pytest.fixture
def store():
    s = LogStore(":memory:")
    yield s
    s.close()


def test_insert_and_query_by_session(store):
    store.insert_event("20260428_210000_proj", "spawn", payload={"msg": "start"})
    store.insert_event("20260428_210000_proj", "plan_change", round=1)
    rows = store.query_by_session("20260428_210000_proj")
    assert len(rows) == 2
    assert rows[0]["kind"] == "spawn"


def test_query_by_round(store):
    sid = "20260428_210000_proj"
    store.insert_event(sid, "round_start", round=1)
    store.insert_event(sid, "script", round=1, payload={"script": "init_project.py"})
    store.insert_event(sid, "round_start", round=2)
    rows = store.query_by_round(sid, 1)
    assert len(rows) == 2
    assert all(r["round"] == 1 for r in rows)


def test_query_by_kind(store):
    sid = "20260428_210000_proj"
    store.insert_event(sid, "spawn")
    store.insert_event(sid, "milestone", payload={"name": "MVP done"})
    store.insert_event("other_session", "milestone", payload={"name": "other"})
    rows = store.query_by_kind("milestone", session_id=sid)
    assert len(rows) == 1
    rows_all = store.query_by_kind("milestone")
    assert len(rows_all) == 2


def test_payload_roundtrip(store):
    sid = "sess"
    data = {"script": "init_project.py", "status": "ok", "lines": 42}
    store.insert_event(sid, "script", payload=data, round=1)
    import json
    row = store.query_by_session(sid)[0]
    assert json.loads(row["payload"]) == data


def test_file_path_stored(store):
    store.insert_event("s", "md_read", file_path="PLAN.md")
    row = store.query_by_session("s")[0]
    assert row["file_path"] == "PLAN.md"
