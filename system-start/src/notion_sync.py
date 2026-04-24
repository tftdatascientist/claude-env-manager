"""
notion_sync.py — push 4 plików MD + pcc.log jako podstrony rekordu w PCC_Projects.

Struktura w Notion:
  PCC_Projects (baza danych)
    └── system-start (rekord)
          ├── CLAUDE.md
          ├── ARCHITECTURE.md
          ├── PLAN.md
          ├── CONVENTIONS.md
          └── pcc.log

Podstrony są dziećmi rekordu — nie zaśmiecają strony głównej LAB_CC_System.
Stan (record_id, child_ids) trzymany w logs/notion_state.json.

notion-client 3.0.0:
  - databases.query nie istnieje — stan lokalny zamiast query
  - databases.retrieve/update — działa, ale properties w odpowiedzi zawsze {}
    (ograniczenie integracji); przyjmujemy że kolumny istnieją po notion_setup
  - pages.create z parent database_id tworzy rekord w bazie
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from notion_client import Client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from src.logger import get_logger as _get_logger
_log = _get_logger("notion_sync")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PCC_DS = os.environ.get("NOTION_PCC_DB", "b278a890-e4a5-4d61-b3f6-1d2058dba11c")

STATE_FILE = BASE_DIR / "logs" / "notion_state.json"
LOG_FILE   = BASE_DIR / "logs" / "pcc.log"

SUBPAGES = ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md", "pcc.log"]
BLOCK_LIMIT = 1990


# ---------------------------------------------------------------------------
# Stan lokalny
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------

def _client() -> Client:
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN nie ustawiony — uzupelnij plik .env")
    return Client(auth=NOTION_TOKEN)


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else "(brak pliku)"


def _extract_meta(plan_text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    in_meta = False
    for line in plan_text.splitlines():
        if "SECTION:meta" in line and "/SECTION" not in line:
            in_meta = True
            continue
        if "/SECTION:meta" in line:
            break
        if in_meta and line.strip().startswith("- "):
            key, _, val = line.strip()[2:].partition(": ")
            meta[key.strip()] = val.strip()
    return meta


def _page_id_from_url(url: str) -> str:
    segment = url.rstrip("/").split("/")[-1]
    raw = segment.replace("-", "")
    if len(raw) >= 32:
        hex_part = raw[-32:]
        return f"{hex_part[:8]}-{hex_part[8:12]}-{hex_part[12:16]}-{hex_part[16:20]}-{hex_part[20:]}"
    return segment


def _md_to_blocks(content: str) -> list[dict]:
    chunks = [content[i:i + BLOCK_LIMIT] for i in range(0, len(content), BLOCK_LIMIT)]
    return [
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}],
                "language": "markdown",
            },
        }
        for chunk in chunks
    ] or [{"object": "block", "type": "code", "code": {
        "rich_text": [{"type": "text", "text": {"content": ""}}],
        "language": "markdown",
    }}]


def _create_child_page(client: Client, parent_id: str, title: str, content: str) -> str:
    """Tworzy podstronę jako dziecko parent_id, zwraca URL."""
    page = client.pages.create(
        parent={"type": "page_id", "page_id": parent_id},
        properties={"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        children=_md_to_blocks(content),
    )
    _log.debug("create_child_page: '%s' -> %s", title, page["url"])
    return page["url"]


def _update_child_page(client: Client, page_url: str, content: str) -> None:
    """Zastępuje treść istniejącej podstrony."""
    page_id = _page_id_from_url(page_url)
    children = client.blocks.children.list(block_id=page_id).get("results", [])
    for block in children:
        client.blocks.delete(block_id=block["id"])
    client.blocks.children.append(block_id=page_id, children=_md_to_blocks(content))
    _log.debug("update_child_page: page_id=%s", page_id)


def _build_props(project_name: str, meta: dict, now_iso: str,
                 child_urls: dict, sync_log: str) -> dict:
    props: dict = {
        "Name":         {"title": [{"type": "text", "text": {"content": project_name}}]},
        "Status":       {"select": {"name": meta.get("status", "idle")}},
        "Goal":         {"rich_text": [{"type": "text", "text": {"content": meta.get("goal", "")[:2000]}}]},
        "Session":      {"number": int(meta.get("session", "1"))},
        "Sync_Log":     {"rich_text": [{"type": "text", "text": {"content": sync_log[:2000]}}]},
        "Last Updated": {"date": {"start": now_iso}},
    }
    url_prop_map = {
        "CLAUDE.md":        "CLAUDE_md",
        "ARCHITECTURE.md":  "ARCHITECTURE_md",
        "PLAN.md":          "PLAN_md",
        "CONVENTIONS.md":   "CONVENTIONS_md",
    }
    for fname, prop in url_prop_map.items():
        if fname in child_urls:
            props[prop] = {"url": child_urls[fname]}
    # pcc.log jest dzieckiem rekordu — brak osobnej kolumny URL (ograniczenie integracji)
    return props


# ---------------------------------------------------------------------------
# Główna funkcja
# ---------------------------------------------------------------------------

def sync(project_dir: Path | None = None, project_name: str | None = None) -> dict:
    """
    Push 4 plików MD + pcc.log do Notion jako dzieci rekordu projektu.

    Returns:
        {nazwa_pliku: url_podstrony}
    """
    if project_dir is None:
        project_dir = BASE_DIR
    if project_name is None:
        project_name = project_dir.name

    _log.info("sync: start | projekt=%s", project_name)
    client = _client()
    now_iso = datetime.now(timezone.utc).date().isoformat()

    plan_text = _read_file(project_dir / "PLAN.md")
    meta = _extract_meta(plan_text)

    state = _load_state()
    project_state: dict = state.get(project_name, {})
    existing_record_id: str | None = project_state.get("record_id")
    existing_child_urls: dict[str, str] = project_state.get("child_urls", {})

    # Weryfikuj czy istniejący rekord nadal żyje
    if existing_record_id:
        try:
            client.pages.retrieve(page_id=existing_record_id)
        except Exception:
            _log.warning("sync: rekord %s niedostepny, tworze nowy", existing_record_id)
            existing_record_id = None
            existing_child_urls = {}

    # Utwórz rekord jeśli nie istnieje (z samą nazwą — URL-e dodamy po stworzeniu podstron)
    if not existing_record_id:
        new_record = client.pages.create(
            parent={"type": "database_id", "database_id": NOTION_PCC_DS},
            properties={"Name": {"title": [{"type": "text", "text": {"content": project_name}}]}},
        )
        existing_record_id = new_record["id"]
        _log.info("sync: nowy rekord | record_id=%s", existing_record_id)

    # Push każdego pliku jako podstronę rekordu
    child_urls: dict[str, str] = {}
    sources: dict[str, Path] = {
        "CLAUDE.md":        project_dir / "CLAUDE.md",
        "ARCHITECTURE.md":  project_dir / "ARCHITECTURE.md",
        "PLAN.md":          project_dir / "PLAN.md",
        "CONVENTIONS.md":   project_dir / "CONVENTIONS.md",
        "pcc.log":          LOG_FILE,
    }
    for fname, fpath in sources.items():
        content = _read_file(fpath)
        if fname in existing_child_urls:
            _update_child_page(client, existing_child_urls[fname], content)
            child_urls[fname] = existing_child_urls[fname]
        else:
            child_urls[fname] = _create_child_page(client, existing_record_id, fname, content)

    # Ostatni wpis session_log → Sync_Log
    log_lines = [l.strip() for l in plan_text.splitlines()
                 if l.strip().startswith("- ") and "|" in l]
    sync_log = log_lines[-1] if log_lines else f"sync {now_iso}"

    # Zaktualizuj rekord z pełnymi properties
    props = _build_props(project_name, meta, now_iso, child_urls, sync_log)
    client.pages.update(page_id=existing_record_id, properties=props)
    _log.info("sync: rekord zaktualizowany | record_id=%s", existing_record_id)

    # Zapisz stan
    state[project_name] = {"record_id": existing_record_id, "child_urls": child_urls}
    _save_state(state)

    _log.info("sync: OK | projekt=%s | podstrony=%d", project_name, len(child_urls))
    return child_urls


def sync_cli() -> None:
    """CLI: python src/notion_sync.py [katalog] [nazwa]"""
    import sys
    args = sys.argv[1:]
    project_dir = Path(args[0]) if args else None
    project_name = args[1] if len(args) > 1 else None
    result = sync(project_dir, project_name)
    for f, url in result.items():
        print(f"  {f} -> {url}")
    print("OK: sync OK.")


if __name__ == "__main__":
    sync_cli()
