from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

_TITLE_PROP_TYPES = {"title"}
_STATUS_PROP_TYPES = {"status", "select"}
_DATE_PROP_TYPES = {"date"}
_TEXT_PROP_TYPES = {"rich_text"}


@dataclass
class NotionProject:
    """DTO projektu pobranego z Notion."""

    notion_page_id: str
    name: str
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    raw_properties: dict = field(default_factory=dict)

    def display_label(self) -> str:
        parts = [self.name]
        if self.status:
            parts.append(f"[{self.status}]")
        if self.due_date:
            parts.append(f"do: {self.due_date}")
        return "  ".join(parts)


class NotionProjectsFetcher:
    """Pobiera projekty z bazy Notion i zwraca jako listę NotionProject."""

    def __init__(
        self,
        token: str | None = None,
        db_id: str | None = None,
    ) -> None:
        self._token = token or os.environ.get("RAZD_NOTION_TOKEN", "")
        self._db_id = db_id or os.environ.get("RAZD_NOTION_PROJECTS_DB_ID", "")
        self._client = Client(auth=self._token)
        self._schema: dict[str, str] | None = None  # prop_name -> prop_type

    def is_configured(self) -> bool:
        return bool(self._token and self._db_id)

    def fetch_projects(self, active_only: bool = True) -> list[NotionProject]:
        """Pobiera projekty z Notion. Zwraca pustą listę przy błędzie."""
        if not self.is_configured():
            logger.warning("NotionProjectsFetcher: brak tokena lub DB ID")
            return []
        try:
            schema = self._get_schema()
            pages = self._query_all_pages()
            projects = [self._parse_page(p, schema) for p in pages]
            if active_only:
                projects = [p for p in projects if _is_active(p)]
            projects.sort(key=lambda p: p.name.lower())
            return projects
        except APIResponseError as exc:
            logger.error("NotionProjectsFetcher: błąd API: %s", exc)
            return []
        except Exception as exc:
            logger.error("NotionProjectsFetcher: nieoczekiwany błąd: %s", exc)
            return []

    def _get_schema(self) -> dict[str, str]:
        """Pobiera schemat bazy (nazwa pola → typ). Cache'uje w sesji."""
        if self._schema is not None:
            return self._schema
        # notion-client 3.x używa data_sources zamiast databases
        db = self._client.data_sources.retrieve(data_source_id=self._db_id)
        props = db.get("properties") or db.get("schema") or {}
        self._schema = {
            name: prop.get("type", "")
            for name, prop in props.items()
        }
        logger.debug("Notion schema: %s", self._schema)
        return self._schema

    def _query_all_pages(self) -> list[dict]:
        pages: list[dict] = []
        cursor: str | None = None
        while True:
            kwargs: dict = {"data_source_id": self._db_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self._client.data_sources.query(**kwargs)
            pages.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return pages

    def _parse_page(self, page: dict, schema: dict[str, str]) -> NotionProject:
        page_id = _normalize_uuid(page["id"])
        props = page.get("properties", {})

        name = _extract_title(props, schema)
        status = _extract_status(props, schema)
        priority = _extract_priority(props, schema)
        due_date = _extract_date(props, schema)
        raw = {k: _prop_plain_value(v) for k, v in props.items()}

        return NotionProject(
            notion_page_id=page_id,
            name=name or page_id,
            status=status,
            priority=priority,
            due_date=due_date,
            raw_properties=raw,
        )


# --- parsowanie pól ---

def _extract_title(props: dict, schema: dict[str, str]) -> str:
    for name, ptype in schema.items():
        if ptype == "title" and name in props:
            return _plain_text(props[name].get("title", []))
    # fallback — pierwsza dostępna wartość tytułu
    for prop in props.values():
        if prop.get("type") == "title":
            return _plain_text(prop.get("title", []))
    return ""


def _extract_status(props: dict, schema: dict[str, str]) -> str | None:
    # Twoja baza używa pola "Live" typu status
    candidates = ["Live", "Status", "status", "Stan", "Etap", "Stage", "Phase"]
    for name in candidates:
        if name in props and schema.get(name) in _STATUS_PROP_TYPES:
            p = props[name]
            ptype = p.get("type")
            if ptype == "status":
                s = p.get("status") or {}
                return s.get("name")
            if ptype == "select":
                s = p.get("select") or {}
                return s.get("name")
    # fallback — pierwszy prop typu status/select
    for name, ptype in schema.items():
        if ptype in _STATUS_PROP_TYPES and name in props:
            p = props[name]
            inner = p.get(ptype) or {}
            return inner.get("name")
    return None


def _extract_priority(props: dict, schema: dict[str, str]) -> str | None:
    # Twoja baza używa pola "Prio" typu select
    candidates = ["Prio", "Priority", "Priorytet", "Ważność", "P"]
    for name in candidates:
        if name in props and schema.get(name) == "select":
            s = (props[name].get("select") or {})
            return s.get("name")
    return None


def _extract_date(props: dict, schema: dict[str, str]) -> str | None:
    # Twoja baza używa pola "Deadline" typu date
    date_names = ["Deadline", "Due date", "Due", "Termin", "Data", "End date", "Date"]
    for name in date_names:
        if name in props and schema.get(name) == "date":
            d = props[name].get("date") or {}
            return d.get("start")
    for name, ptype in schema.items():
        if ptype == "date" and name in props:
            d = props[name].get("date") or {}
            return d.get("start")
    return None


def _plain_text(rich_text: list) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text)


def _prop_plain_value(prop: dict) -> str | None:
    """Ekstrakt prostej wartości z dowolnego pola Notion (do raw_properties)."""
    ptype = prop.get("type", "")
    try:
        if ptype == "title":
            return _plain_text(prop.get("title", []))
        if ptype == "rich_text":
            return _plain_text(prop.get("rich_text", []))
        if ptype in ("select", "status"):
            inner = prop.get(ptype) or {}
            return inner.get("name")
        if ptype == "multi_select":
            return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
        if ptype == "date":
            d = prop.get("date") or {}
            return d.get("start")
        if ptype == "number":
            return str(prop.get("number"))
        if ptype == "checkbox":
            return str(prop.get("checkbox", False))
        if ptype == "url":
            return prop.get("url")
        if ptype == "email":
            return prop.get("email")
        if ptype == "phone_number":
            return prop.get("phone_number")
    except Exception:
        pass
    return None


def _normalize_uuid(uid: str) -> str:
    """Zapewnia format UUID z myślnikami: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx."""
    clean = uid.replace("-", "")
    if len(clean) != 32:
        return uid
    return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"


def _is_active(project: NotionProject) -> bool:
    if not project.status:
        return True
    done_statuses = {
        "done", "cancel", "archiwum", "zakończony", "completed",
        "archived", "cancelled", "anulowany", "zarchiwizowany", "finished",
    }
    return project.status.lower() not in done_statuses


def write_session_time_to_notion(
    project: NotionProject,
    duration_mins: int,
    token: str | None = None,
) -> bool:
    """Dodaje czas sesji do projektu w Notion (pole liczbowe 'Spent time' lub podobne)."""
    token = token or os.environ.get("RAZD_NOTION_TOKEN", "")
    if not token:
        return False
    client = Client(auth=token)
    try:
        page = client.pages.retrieve(page_id=project.notion_page_id)
        props = page.get("properties", {})
        time_field = _find_time_field(props)
        if not time_field:
            logger.warning(
                "Notion: brak pola 'Spent time (min)' w projekcie '%s' — pomijam zapis czasu",
                project.name,
            )
            return False
        current = (props[time_field].get("number") or 0)
        client.pages.update(
            page_id=project.notion_page_id,
            properties={time_field: {"number": current + duration_mins}},
        )
        logger.info(
            "Notion: zaktualizowano '%s' w projekcie '%s' — +%d min (łącznie %d min)",
            time_field, project.name, duration_mins, current + duration_mins,
        )
        return True
    except APIResponseError as exc:
        logger.error("Notion: błąd zapisu czasu dla '%s': %s", project.name, exc)
        return False


def _find_time_field(props: dict) -> str | None:
    # dokładna nazwa pola dodanego do bazy Notion
    if "Spent time (min)" in props and props["Spent time (min)"].get("type") == "number":
        return "Spent time (min)"
    # fallback — inne możliwe nazwy
    candidates = [
        "Spent time", "Czas", "Czas pracy", "Time spent", "Hours",
        "Minutes", "Godziny", "Łączny czas", "Total time",
    ]
    for name in candidates:
        if name in props and props[name].get("type") == "number":
            return name
    for name, prop in props.items():
        if prop.get("type") == "number":
            return name
    return None
