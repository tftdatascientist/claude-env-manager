<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: MVP RAZD: moduł CEM z dwiema zakładkami — Time Tracking (auto-detekcja procesów/URLs/idle + AI kategoryzacja przez Claude Code z dialogiem nauki) i Focus Timer (whitelist appek 30-120min + ping gdy odlatujesz)
- session: 1
- updated: 2026-04-28 23:06
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami
- file: razd/__init__.py
- started: 2026-04-28 23:06
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] dialog Qt 'co to za proces/URL?' wywołany przez tool ask_user
- [ ] TimeTrackingTab: agregacja godzin per kategoria (dzień/tydzień), QListWidget kategorii
- [ ] TimeTrackingTab: oś czasu (custom QGraphicsView lub QChart) z kolorami per kategoria
- [ ] FocusTimerTab: QListWidget whitelist + QSpinBox czasu + przyciski start/stop/reset
- [ ] FocusTimerTab: QTimer countdown + QSystemTrayIcon ping + modal dialog gdy app spoza whitelisty
- [ ] config TOML: tracking interval, idle threshold, AI prompts, paths
- [ ] testy pytest-qt: tracker poller, focus timer state machine, dialogi nauki
- [ ] dokumentacja install: jak wpiąć w CEM, jak skonfigurować claude-agent-sdk
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
- [x] szkielet pakietu razd/ + pyproject.toml + ruff config
- [x] entry point: razd/__init__.py rejestracja w CEM (top menu hook)
- [x] RazdMainWindow z QTabWidget (dwie zakładki: TimeTracking, FocusTimer) — pusty szkielet
- [x] schema SQLite: events, processes, categories, url_mappings, user_decisions + repository.py
- [x] Tracker.active_window: pywin32 GetForegroundWindow + GetWindowText
- [x] Tracker.idle: GetLastInputInfo, threshold 60s = idle
- [x] Tracker.browser_url: uiautomation extract URL z Chrome/Edge + privacy filter
- [x] Tracker.poller: agreguje sygnały, emituje EventDTO co 2s (QObject + QTimer)
- [x] format strumienia eventów JSON do agenta (EventDTO.to_json())
- [x] integracja claude-code-sdk: RazdAgentThread (QThread) + RazdAgentWorker + asyncio queue
- [x] custom tools MCP: save_category, ask_user, query_knowledge (in-process MCP server)
- [x] privacy filter: regex sanitize_url w browser_url.py
<!-- /SECTION:done -->

## Buffer
<!-- SECTION:buffer -->
<!-- /SECTION:buffer -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- 2026-04-29 01:41 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:25 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:21 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:14 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:11 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- session:1 | 2026-04-28 | projekt zainicjalizowany przez sss
<!-- /SECTION:session_log -->
