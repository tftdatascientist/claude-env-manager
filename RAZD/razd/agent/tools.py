from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol

from claude_code_sdk import create_sdk_mcp_server, tool


class AskUserCallback(Protocol):
    """Qt-side callback: przyjmuje pytanie, zwraca odpowiedź usera (sync przez Event)."""
    def __call__(self, subject: str, question: str) -> str: ...


class RepositoryProtocol(Protocol):
    def upsert_category(self, name: str, color: str, is_productive: bool) -> int: ...
    def get_category_by_name(self, name: str): ...
    def upsert_process(self, name: str, category_id: int | None) -> None: ...
    def upsert_url_mapping(self, pattern: str, category_id: int) -> None: ...
    def save_decision(self, subject: str, subject_type: str, question: str, answer: str, category_id: int | None) -> int: ...
    def list_categories(self) -> list: ...


def build_mcp_server(repo: RepositoryProtocol, ask_user_cb: AskUserCallback):
    """Buduje in-process MCP server z trzema narzędziami dla agenta RAZD."""

    @tool(
        "save_category",
        "Zapisuje kategorię dla procesu lub domeny URL w bazie wiedzy RAZD.",
        {
            "subject": str,
            "subject_type": str,
            "category_name": str,
            "is_productive": bool,
            "color": str,
        },
    )
    async def save_category(args: dict[str, Any]) -> dict[str, Any]:
        subject: str = args["subject"]
        subject_type: str = args["subject_type"]   # "process" | "url"
        name: str = args["category_name"]
        productive: bool = args.get("is_productive", True)
        color: str = args.get("color", "#888888")

        cid = repo.upsert_category(name, color, productive)

        if subject_type == "process":
            repo.upsert_process(subject, cid)
        elif subject_type == "url":
            repo.upsert_url_mapping(subject, cid)

        return {"content": [{"type": "text", "text": f"Zapisano: {subject} → {name} (id={cid})"}]}

    @tool(
        "ask_user",
        "Wyświetla dialog Qt z pytaniem do użytkownika o nieznany proces lub URL. Zwraca odpowiedź.",
        {"subject": str, "subject_type": str, "question": str},
    )
    async def ask_user(args: dict[str, Any]) -> dict[str, Any]:
        subject: str = args["subject"]
        subject_type: str = args["subject_type"]
        question: str = args["question"]

        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, ask_user_cb, subject, question)

        repo.save_decision(
            subject=subject,
            subject_type=subject_type,
            question=question,
            answer=answer,
        )
        return {"content": [{"type": "text", "text": answer}]}

    @tool(
        "query_knowledge",
        "Sprawdza bazę wiedzy RAZD — czy znamy już kategorię dla procesu lub URL.",
        {"subject": str, "subject_type": str},
    )
    async def query_knowledge(args: dict[str, Any]) -> dict[str, Any]:
        subject: str = args["subject"]
        subject_type: str = args["subject_type"]

        if subject_type == "process":
            cid = repo.get_category_by_name(subject)
            result = str(cid) if cid else "nieznany"
        else:
            cats = [c.name for c in repo.list_categories()]
            result = ", ".join(cats) if cats else "brak kategorii"

        return {"content": [{"type": "text", "text": result}]}

    return create_sdk_mcp_server([save_category, ask_user, query_knowledge])
