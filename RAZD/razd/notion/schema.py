from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NotionActivityRecord:
    """DTO reprezentujący jeden wpis aktywności w bazie Notion."""

    name: str                        # Nazwa (title) — np. "chrome — 2026-04-30"
    category: str                    # Kategoria (select)
    duration_mins: int               # Czas (min)
    date: str                        # Data ISO-8601 YYYY-MM-DD
    processes: list[str] = field(default_factory=list)  # Procesy (multi_select)
    url: str | None = None           # URL (opcjonalne, zależnie od RAZD_NOTION_EXPORT_URLS)
    agent_note: str | None = None    # Notatka agenta (rich_text)

    def to_notion_properties(self, export_urls: bool = False) -> dict:
        """Buduje słownik properties zgodny z notion-client pages.create."""
        props: dict = {
            "Nazwa": {"title": [{"text": {"content": self.name}}]},
            "Kategoria": {"select": {"name": self.category}},
            "Czas (min)": {"number": self.duration_mins},
            "Data": {"date": {"start": self.date}},
        }
        if self.processes:
            props["Procesy"] = {"multi_select": [{"name": p} for p in self.processes]}
        if export_urls and self.url:
            props["URL"] = {"url": self.url}
        if self.agent_note:
            props["Notatka agenta"] = {
                "rich_text": [{"text": {"content": self.agent_note[:2000]}}]
            }
        return props
