<!-- CHANGELOG v1.0 -->

# Changelog

## Entries
<!-- SECTION:entries -->
- session:1 | 2026-04-30 | szkielet pakietu razd/ + pyproject.toml + ruff config
- session:1 | 2026-04-30 | entry point: razd/__init__.py rejestracja w CEM (top menu hook)
- session:1 | 2026-04-30 | RazdMainWindow z QTabWidget (dwie zakładki: TimeTracking, FocusTimer) — pusty szkielet
- session:1 | 2026-04-30 | schema SQLite: events, processes, categories, url_mappings, user_decisions + repository.py
- session:1 | 2026-04-30 | Tracker.active_window: pywin32 GetForegroundWindow + GetWindowText
- session:1 | 2026-04-30 | Tracker.idle: GetLastInputInfo, threshold 60s = idle
- session:1 | 2026-04-30 | Tracker.browser_url: uiautomation extract URL z Chrome/Edge + privacy filter
- session:1 | 2026-04-30 | Tracker.poller: agreguje sygnały, emituje EventDTO co 2s (QObject + QTimer)
- session:1 | 2026-04-30 | format strumienia eventów JSON do agenta (EventDTO.to_json())
- session:1 | 2026-04-30 | integracja claude-code-sdk: RazdAgentThread (QThread) + RazdAgentWorker + asyncio queue
- session:1 | 2026-04-30 | custom tools MCP: save_category, ask_user, query_knowledge (in-process MCP server)
- session:1 | 2026-04-30 | privacy filter: regex sanitize_url w browser_url.py
- session:1 | 2026-04-30 | dialog Qt RazdAskUserDialog + ask_user_blocking (marshal UI thread przez _DialogBridge)
- session:1 | 2026-04-30 | RazdMainWindow spina Tracker → Agent → UI (poller, agent thread, repo)
- session:1 | 2026-04-30 | TimeTrackingTab: akumulacja sekund per kategoria, oś czasu QGraphicsView z blokami, QListWidget kategorii z czasem, wybór dnia przez QCalendarWidget, ładowanie historii z DB
- session:1 | 2026-04-30 | FocusTimerTab: whitelist QListWidget + Add/Remove, QSpinBox + presety 30/60/90/120min, _FocusState machine, QTimer countdown, start/pause/resume/reset, QSystemTrayIcon ping, _EscapeDialog gdy app spoza whitelisty
- session:1 | 2026-04-30 | config TOML: defaults.toml + RazdSettings (load/save, deep merge user override, ścieżki posix)
- session:1 | 2026-04-30 | testy pytest-qt: 54 testów (focus timer state machine, TimeTrackingTab, RazdSettings, UI smoke) — 54/54 pass
- session:1 | 2026-04-30 | dokumentacja install: INSTALL.md — wymagania, wpięcie w CEM, konfiguracja CC SDK, config TOML, przepływ agenta, ograniczenia MVP
- session:2 | 2026-05-01 | Notion integration: razd/notion/ — schema.py (NotionActivityRecord), exporter.py (RazdNotionExporter upsert), sync_worker.py (RazdNotionSyncThread cykliczny sync)
- session:2 | 2026-05-01 | RazdSettings: sekcja [notion] — enabled, sync_interval_mins, export_urls
- session:2 | 2026-05-01 | RazdMainWindow: wpięcie RazdNotionSyncThread gdy notion.enabled=true
- session:2 | 2026-05-01 | testy notion: 12 testów (normalize, map_category, record properties, export session upsert/update/no-events/missing-token, url privacy) — 12/12 pass
- session:2 | 2026-05-01 | fix: test_export_session_updates_existing_page — mock search zamiast databases.query
<!-- /SECTION:entries -->

## Session Log (przeniesiony z PLAN.md)
<!-- SECTION:session_log -->
- 2026-04-29 01:41 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:43 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-29 01:47 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 | session:2 | zakończono TimeTrackingTab (oś czasu, kategorie, historia DB, wybór dnia) + FocusTimerTab (whitelist, countdown, tray ping, escape dialog)
- 2026-04-30 11:40 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 13:28 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 13:32 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 13:37 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 13:42 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
- 2026-04-30 13:45 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
<!-- /SECTION:session_log -->
