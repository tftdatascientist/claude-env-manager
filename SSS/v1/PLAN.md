<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: MVP: spawner CC z plan mode + polling PLAN.md + LogsView pod Develop → Sesje CC → Logi
- session: 1
- updated: 2026-04-28 21:28
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: Stworzyć schemat bazy events w log_store
- file: src/cm/sss_module/db/schema.sql
- started: 2026-04-28 21:28
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] schema SQLite events (session_id, ts, round, kind, payload, file_path)
- [ ] LogStore: insert_event, query_by_session, query_by_round, query_by_kind
- [ ] IntakeView: pola prompt + nazwa + lokalizacja, walidacja, sygnał qt_start_clicked
- [ ] ProjectSpawner: utworzenie katalogu, zapis intake.json, prompt → CC, VS Code subprocess
- [ ] integracja z skill /sss: wywołanie init_project.py przez SSSBridge i log eventu
- [ ] PlanWatcher: QTimer 60s, parsuje PLAN.md przez parser.py ze skilla, emituje sygnały zmian + log eventów
- [ ] RoundWatcher: detekcja zmiany fazy przez state.py, czytanie pozostałych plików .md przy zmianie
- [ ] LogsView: drzewo sesji, filtry round/kind, podgląd payload
- [ ] migracja istniejącego przycisku Start CC na nowy flow (prompt + spawn)
- [ ] testy pytest core modułów
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Buffer
<!-- SECTION:buffer -->
<!-- /SECTION:buffer -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- session:1 | 2026-04-28 | projekt zainicjalizowany przez sss
<!-- /SECTION:session_log -->
