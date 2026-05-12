from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

_TASKS_DB_ID = os.environ.get("RAZD_NOTION_TASKS_DB_ID", "")

# Statusy Notion → grupy kanban
KANBAN_TODO       = "Not started"
KANBAN_IN_PROGRESS = "In progress"
KANBAN_DONE       = "Done"
KANBAN_CANCEL     = "Cancel"

KANBAN_COLUMNS = [KANBAN_TODO, KANBAN_IN_PROGRESS, KANBAN_DONE]
# Cancel traktujemy jak Done na kanban


@dataclass
class NotionTask:
    page_id: str
    title: str
    status: str                          # "Not started" | "In progress" | "Done" | "Cancel"
    deadline: str | None                 # ISO date lub None
    details: str | None
    project_page_ids: list[str] = field(default_factory=list)   # URL-e stron projektów

    @property
    def kanban_column(self) -> str:
        if self.status in (KANBAN_DONE, KANBAN_CANCEL):
            return KANBAN_DONE
        return self.status or KANBAN_TODO


class NotionTasksFetcher:
    """Pobiera i tworzy zadania w bazie Notion 'Zadania'."""

    def __init__(self, token: str | None = None, db_id: str | None = None) -> None:
        self._token = token or os.environ.get("RAZD_NOTION_TOKEN", "")
        raw_db = db_id or os.environ.get("RAZD_NOTION_TASKS_DB_ID", "")
        self._db_id = _normalize_uuid(raw_db) if raw_db else ""
        self._client = Client(auth=self._token)

    def is_configured(self) -> bool:
        return bool(self._token and self._db_id)

    # ── pobieranie ───────────────────────────────────────────────────────────

    def fetch_tasks(self, project_page_ids: list[str] | None = None) -> list[NotionTask]:
        """Pobiera zadania, opcjonalnie filtrując do podanych page_id projektów."""
        if not self.is_configured():
            logger.warning("TasksFetcher: brak tokena lub DB ID")
            return []
        try:
            # Notion wymaga UUID z myślnikami w filtrze relacji
            if project_page_ids:
                project_page_ids = [_normalize_uuid(pid) for pid in project_page_ids]
            pages = self._query_all(project_page_ids)
            return [self._parse(p) for p in pages]
        except APIResponseError as exc:
            logger.error("TasksFetcher API error: %s", exc)
            return []
        except Exception as exc:
            logger.error("TasksFetcher error: %s", exc)
            return []

    def _query_all(self, project_page_ids: list[str] | None) -> list[dict]:
        pages: list[dict] = []
        cursor: str | None = None
        filt: dict | None = None
        if project_page_ids:
            conditions = [
                {"property": "Projekt", "relation": {"contains": pid}}
                for pid in project_page_ids
            ]
            filt = {"or": conditions} if len(conditions) > 1 else conditions[0]

        while True:
            kwargs: dict = {"data_source_id": self._db_id, "page_size": 100}
            if filt:
                kwargs["filter"] = filt
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self._client.data_sources.query(**kwargs)
            pages.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return pages

    def _parse(self, page: dict) -> NotionTask:
        page_id = _normalize_uuid(page["id"])
        props = page.get("properties", {})

        title = _plain_text(props.get("Task title", {}).get("title", []))
        status_obj = props.get("Status", {}).get("status") or {}
        status = status_obj.get("name", KANBAN_TODO)
        deadline_obj = props.get("Deadline", {}).get("date") or {}
        deadline = deadline_obj.get("start")
        details_rich = props.get("Task details", {}).get("rich_text", [])
        details = _plain_text(details_rich) or None
        rel_list = props.get("Projekt", {}).get("relation", [])
        project_ids = [_normalize_uuid(r["id"]) for r in rel_list if "id" in r]

        return NotionTask(
            page_id=page_id,
            title=title or "(bez tytułu)",
            status=status,
            deadline=deadline,
            details=details,
            project_page_ids=project_ids,
        )

    # ── tworzenie zadania ────────────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        project_page_id: str,
        status: str = KANBAN_TODO,
        deadline: str | None = None,
        details: str | None = None,
    ) -> NotionTask | None:
        """Tworzy nowe zadanie w Notion i zwraca je jako NotionTask."""
        if not self.is_configured():
            return None
        try:
            props: dict = {
                "Task title": {"title": [{"text": {"content": title}}]},
                "Status": {"status": {"name": status}},
                "Projekt": {"relation": [{"id": project_page_id}]},
            }
            if deadline:
                props["Deadline"] = {"date": {"start": deadline}}
            if details:
                props["Task details"] = {"rich_text": [{"text": {"content": details}}]}

            page = self._client.pages.create(
                parent={"data_source_id": self._db_id},
                properties=props,
            )
            return self._parse(page)
        except APIResponseError as exc:
            logger.error("TasksFetcher create_task error: %s", exc)
            return None

    # ── aktualizacja statusu ─────────────────────────────────────────────────

    def update_status(self, page_id: str, new_status: str) -> bool:
        """Aktualizuje status zadania w Notion."""
        if not self.is_configured():
            return False
        try:
            self._client.pages.update(
                page_id=page_id,
                properties={"Status": {"status": {"name": new_status}}},
            )
            return True
        except APIResponseError as exc:
            logger.error("TasksFetcher update_status error: %s", exc)
            return False

    def update_task(self, page_id: str, title: str | None = None,
                    deadline: str | None = None, details: str | None = None) -> bool:
        """Aktualizuje pola zadania (poza statusem)."""
        if not self.is_configured():
            return False
        try:
            props: dict = {}
            if title is not None:
                props["Task title"] = {"title": [{"text": {"content": title}}]}
            if deadline is not None:
                props["Deadline"] = {"date": {"start": deadline}} if deadline else {"date": None}
            if details is not None:
                props["Task details"] = {"rich_text": [{"text": {"content": details}}] if details else []}
            if props:
                self._client.pages.update(page_id=page_id, properties=props)
            return True
        except APIResponseError as exc:
            logger.error("TasksFetcher update_task error: %s", exc)
            return False

    def archive_task(self, page_id: str) -> bool:
        """Archiwizuje (usuwa) zadanie w Notion."""
        if not self.is_configured():
            return False
        try:
            self._client.pages.update(page_id=page_id, archived=True)
            return True
        except APIResponseError as exc:
            logger.error("TasksFetcher archive_task error: %s", exc)
            return False


def _plain_text(rich_text: list) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text)


def _normalize_uuid(uid: str) -> str:
    """Zapewnia format UUID z myślnikami: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx."""
    clean = uid.replace("-", "")
    if len(clean) != 32:
        return uid
    return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
