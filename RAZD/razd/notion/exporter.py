from __future__ import annotations

import logging
import os
import re
from datetime import date
from dataclasses import dataclass, field

from notion_client import Client
from notion_client.errors import APIResponseError

from razd.db.repository import RazdRepository
from razd.notion.schema import NotionActivityRecord

logger = logging.getLogger(__name__)


@dataclass
class _Bucket:
    secs: int = 0
    category: str = "Inne"
    processes: set[str] = field(default_factory=set)


class RazdNotionExporter:
    """Eksportuje dzienne podsumowanie łącznego czasu per aplikacja do Notion DB."""

    def __init__(
        self,
        repo: RazdRepository,
        token: str | None = None,
        db_id: str | None = None,
        export_urls: bool = False,
    ) -> None:
        self._repo = repo
        self._token = token or os.environ.get("RAZD_NOTION_TOKEN", "")
        self._db_id = db_id or os.environ.get("RAZD_NOTION_DB_ID", "")
        self._export_urls = export_urls
        self._client = Client(auth=self._token)

    # --- public API ---

    def export_session(self, target_date: date) -> str | None:
        """Eksportuje lub aktualizuje podsumowanie dnia. Zwraca page_id lub None."""
        if not self._token or not self._db_id:
            logger.warning("RAZD Notion: brak tokena lub DB ID — pomijam eksport")
            return None

        records = self._build_records(target_date)
        if not records:
            logger.debug("RAZD Notion: brak aktywności dla %s", target_date)
            return None

        results = []
        for rec in records:
            page_id = self._upsert_record(rec)
            if page_id:
                results.append(page_id)

        logger.info("RAZD Notion: zsynchronizowano %d rekordów dla %s", len(results), target_date)
        return results[0] if results else None

    # --- private helpers ---

    def _build_records(self, target_date: date) -> list[NotionActivityRecord]:
        """Agreguje eventy z SQLite — łączny czas per aplikacja per dzień."""
        events = self._repo.get_events_for_day(target_date.isoformat())
        if not events:
            return []

        # Buduj cache kategorii raz na cały export
        cat_cache: dict[int, str] = {
            c.id: _map_category_name(c.name)
            for c in self._repo.list_categories()
        }

        # Klucz = znormalizowana nazwa procesu (bez .exe, bez ścieżki)
        buckets: dict[str, _Bucket] = {}
        for ev in events:
            if ev.event_type == "idle":
                continue
            proc = _normalize_process(ev.process_name or "")
            if proc not in buckets:
                buckets[proc] = _Bucket()
            b = buckets[proc]
            b.secs += 2  # każdy poll = 2 sekundy aktywności
            b.processes.add(proc)
            # nadpisz kategorię jeśli event ma przypisaną (bardziej wiarygodna)
            if ev.category_id is not None:
                b.category = cat_cache.get(ev.category_id, "Inne")

        records: list[NotionActivityRecord] = []
        for proc, b in buckets.items():
            mins = max(1, round(b.secs / 60))
            records.append(
                NotionActivityRecord(
                    name=f"{proc} — {target_date.isoformat()}",
                    category=b.category,
                    duration_mins=mins,
                    date=target_date.isoformat(),
                    processes=sorted(b.processes),
                )
            )
        return records

    def _upsert_record(self, rec: NotionActivityRecord) -> str | None:
        """Wstaw lub zaktualizuj stronę w Notion."""
        existing_id = self._find_existing_page(rec.name)
        props = rec.to_notion_properties(export_urls=self._export_urls)
        try:
            if existing_id:
                self._client.pages.update(page_id=existing_id, properties=props)
                return existing_id
            else:
                page = self._client.pages.create(
                    parent={"database_id": self._db_id},
                    properties=props,
                )
                return page["id"]
        except APIResponseError as exc:
            logger.error("RAZD Notion: błąd API przy upsert '%s': %s", rec.name, exc)
            return None

    def _find_existing_page(self, title: str) -> str | None:
        """Szuka strony po tytule przez search (notion-client 3.x)."""
        try:
            results = self._client.search(
                query=title,
                filter={"property": "object", "value": "page"},
                page_size=5,
            )
            for page in results.get("results", []):
                # weryfikuj że to strona z naszej bazy i tytuł się zgadza
                if page.get("parent", {}).get("database_id", "").replace("-", "") != self._db_id.replace("-", ""):
                    continue
                title_prop = page.get("properties", {}).get("Nazwa", {})
                page_title = "".join(
                    t.get("plain_text", "") for t in title_prop.get("title", [])
                )
                if page_title == title:
                    return page["id"]
            return None
        except APIResponseError as exc:
            logger.warning("RAZD Notion: błąd szukania '%s': %s", title, exc)
            return None


def _normalize_process(name: str) -> str:
    """Zwraca czystą nazwę procesu bez ścieżki i rozszerzenia."""
    stem = re.sub(r"\.(exe|app)$", "", name.lower(), flags=re.IGNORECASE)
    stem = stem.split("\\")[-1].split("/")[-1]
    return stem or "unknown"


_CATEGORY_MAP = {
    "work": "Praca",
    "praca": "Praca",
    "learn": "Nauka",
    "nauka": "Nauka",
    "entertainment": "Rozrywka",
    "rozrywka": "Rozrywka",
    "communication": "Komunikacja",
    "komunikacja": "Komunikacja",
    "system": "System",
}


def _map_category_name(name: str) -> str:
    return _CATEGORY_MAP.get(name.lower(), "Inne")
