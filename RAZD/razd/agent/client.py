from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal

from claude_code_sdk import ClaudeCodeOptions, query
from claude_code_sdk.types import ResultMessage, TextBlock

from razd.agent.prompts import SYSTEM_PROMPT
from razd.agent.tools import AskUserCallback, RepositoryProtocol, build_mcp_server

if TYPE_CHECKING:
    from razd.tracker.poller import EventDTO

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5"


class RazdAgentWorker(QObject):
    """Żyje w QThread — przyjmuje eventy z pollera i wysyła do CC agenta."""

    question_ready = Signal(str, str)   # (subject, question) — do dialogu Qt

    def __init__(
        self,
        repo: RepositoryProtocol,
        ask_user_cb: AskUserCallback,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._ask_user_cb = ask_user_cb
        self._mcp_server = build_mcp_server(repo, ask_user_cb)
        self._queue: asyncio.Queue[EventDTO] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

    def enqueue_event(self, dto: "EventDTO") -> None:
        """Wołane ze słotu Qt w wątku UI — bezpieczne przez queue."""
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, dto)

    def run(self) -> None:
        """Główna pętla — uruchamiana przez QThread.started."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._agent_loop())
        finally:
            self._loop.close()

    async def _agent_loop(self) -> None:
        log.info("RAZD agent loop start")
        while True:
            dto = await self._queue.get()
            if dto.event_type == "idle":
                continue
            await self._process_event(dto)

    async def _process_event(self, dto: "EventDTO") -> None:
        prompt = dto.to_json()
        options = ClaudeCodeOptions(
            system_prompt=SYSTEM_PROMPT,
            mcp_servers={"razd": self._mcp_server},
            allowed_tools=["mcp__razd__save_category", "mcp__razd__ask_user", "mcp__razd__query_knowledge"],
            permission_mode="acceptEdits",
            max_turns=5,
        )
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    log.debug("agent result: %s", message)
        except Exception as exc:
            log.warning("agent error: %s", exc)


class RazdAgentThread(QThread):
    """QThread opakowujący RazdAgentWorker."""

    def __init__(
        self,
        repo: RepositoryProtocol,
        ask_user_cb: AskUserCallback,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker = RazdAgentWorker(repo, ask_user_cb)
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)

    def enqueue_event(self, dto: "EventDTO") -> None:
        self.worker.enqueue_event(dto)
