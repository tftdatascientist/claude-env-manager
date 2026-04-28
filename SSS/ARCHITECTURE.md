<!-- ARCHITECTURE v1.0 -->

## Overview
<!-- SECTION:overview -->
Moduł CM spawnuje projekt Claude Code w plan mode i monitoruje jego stan. UI (PySide6) pozwala wpisać prompt + nazwę + lokalizację. Po kliknięciu CM zapisuje strukturę projektu, wkleja prompt do CC i odpala VS Code z wtyczką VS_CLAUDE. W tle pollinguje PLAN.md co minutę, pozostałe pliki .md raz na rundę. Wszystkie zdarzenia (rundy, skrypty, bufor, zadania, milestone'y) lądują w log store dostępnym z menu Develop → Sesje CC → Logi.
<!-- /SECTION:overview -->

## Components
<!-- SECTION:components -->
- IntakeView: PySide6 widget z polami prompt + nazwa + lokalizacja + przycisk Start
- ProjectSpawner: tworzy katalog projektu, wkleja prompt do CC, odpala VS Code
- PlanWatcher: QFileSystemWatcher + QTimer 60s, parsuje PLAN.md, emituje sygnały zmian
- RoundWatcher: czyta CLAUDE/ARCHITECTURE/CONVENTIONS/CHANGELOG raz na rundę (trigger: zmiana fazy z state.py)
- LogStore: SQLite + tabela events, kolumny session_id, timestamp, round, kind, payload
- LogsView: PySide6 widget pod Develop → Sesje CC → Logi z filtrami session/round/kind
- SSSBridge: wrapper na skill /sss, woła skrypty Pythona (init_project, plan_buffer, service_round, finalize, state)
<!-- /SECTION:components -->

## Data Flow
<!-- SECTION:data_flow -->
user wpisuje prompt → IntakeView → ProjectSpawner (mkdir, prompt → schowek/stdin CC, VS Code subprocess) → PlanWatcher poll PLAN.md → state.py wykrywa fazę → LogStore zapis events → LogsView render
<!-- /SECTION:data_flow -->

## External Deps
<!-- SECTION:external_deps -->
<!-- /SECTION:external_deps -->

## Decisions
<!-- SECTION:decisions -->
- [x] SQLite zamiast pliku JSONL na logi | 2026-04-28 | filtry po session/round/kind wymagają indeksów; jeden plik DB w katalogu CM
- [x] PLAN.md polling co 60s zamiast tylko QFileSystemWatcher | 2026-04-28 | watcher nie łapie zmian zapisanych przez WSL/edytory zewnętrzne; timer 60s jest deterministyczny
- [x] inne pliki .md tylko raz na rundę | 2026-04-28 | user wymaganie + redukcja I/O
- [x] CHANGELOG.md powstaje dopiero przy pierwszym service round | 2026-04-28 | tak działa skill /sss — moduł nie tworzy go z góry
- [x] event-sourced log (jeden rekord = jedno zdarzenie) | 2026-04-28 | umożliwia rekonstrukcję historii projektu i audyt rund
<!-- /SECTION:decisions -->

## Constraints
<!-- SECTION:constraints -->
- Windows-first (ścieżki C:\Users\Sławek), ale kod ma pathlib bez hardkodu
- nie wstawiamy promptu przez clipboard jeśli da się przez stdin — clipboard jest ostateczny fallback
- VS_CLAUDE wtyczka jest stałym artefaktem, CM tylko wskazuje na nią
<!-- /SECTION:constraints -->
