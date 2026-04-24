"""
notion_setup.py — jednorazowy setup schematu bazy PCC_Projects.

Dodaje brakujące właściwości do istniejącej bazy.
Uruchom raz przed pierwszym pcc_round_end.

Użycie:
  python src/notion_setup.py
  python src/notion_setup.py --check   # tylko weryfikacja, bez zmian
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from notion_client import Client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PCC_DB = os.environ.get("NOTION_PCC_DB", "")

REQUIRED_PROPERTIES: dict[str, dict] = {
    "Status": {"select": {"options": [
        {"name": "active", "color": "green"},
        {"name": "idle",   "color": "gray"},
    ]}},
    "Goal":         {"rich_text": {}},
    "Session":      {"number": {"format": "number"}},
    "Sync_Log":     {"rich_text": {}},
    "Last Updated": {"date": {}},
    "CLAUDE_md":    {"url": {}},
    "ARCHITECTURE_md": {"url": {}},
    "PLAN_md":      {"url": {}},
    "CONVENTIONS_md": {"url": {}},
    "Log_md":       {"url": {}},
}

app = typer.Typer(add_completion=False)


def _client() -> Client:
    if not NOTION_TOKEN:
        typer.echo("ERROR: NOTION_TOKEN nie ustawiony w .env", err=True)
        raise typer.Exit(1)
    return Client(auth=NOTION_TOKEN)


def _get_existing_props(client: Client) -> set[str]:
    if not NOTION_PCC_DB:
        typer.echo("ERROR: NOTION_PCC_DB nie ustawiony w .env", err=True)
        raise typer.Exit(1)
    db = client.databases.retrieve(database_id=NOTION_PCC_DB)
    return set(db.get("properties", {}).keys())


@app.command()
def setup(
    check: bool = typer.Option(False, "--check", help="Tylko sprawdź, nie modyfikuj"),
) -> None:
    """Dodaj brakujące właściwości do bazy PCC_Projects."""
    from src.logger import get_logger
    log = get_logger("notion_setup")

    client = _client()
    existing = _get_existing_props(client)

    missing = {k: v for k, v in REQUIRED_PROPERTIES.items() if k not in existing}

    if not missing:
        typer.echo("OK: wszystkie wymagane właściwości już istnieją.")
        log.info("notion_setup: schemat kompletny, brak zmian")
        return

    typer.echo(f"Brakujące właściwości ({len(missing)}): {', '.join(missing)}")
    log.info("notion_setup: brakujace wlasciwosci: %s", list(missing))

    if check:
        typer.echo("Tryb --check: bez zmian.")
        raise typer.Exit(1)

    client.databases.update(
        database_id=NOTION_PCC_DB,
        properties=missing,
    )
    typer.echo(f"OK: dodano {len(missing)} właściwości do PCC_Projects.")
    log.info("notion_setup: dodano %d wlasciwosci: %s", len(missing), list(missing))


if __name__ == "__main__":
    app()
