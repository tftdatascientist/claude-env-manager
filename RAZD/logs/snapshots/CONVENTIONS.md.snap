<!-- CONVENTIONS v1.0 -->

## Naming
<!-- SECTION:naming -->
snake_case dla plików .py i funkcji; PascalCase dla klas Qt z prefiksem Razd (RazdMainWindow, RazdTimeTrackingTab, RazdFocusTimerTab, RazdTracker, RazdAgent); UPPER_CASE dla stałych; nazwy sygnałów Qt w stylu on_<event> dla slotów, <subject>_<changed|emitted> dla sygnałów
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
- razd/: główny pakiet modułu
- razd/__init__.py: rejestracja w CEM (entry point dla menu)
- razd/tracker/: active_window.py, idle.py, browser_url.py, poller.py
- razd/agent/: client.py (claude-agent-sdk wrapper), prompts.py, tools.py
- razd/db/: schema.sql, repository.py, migrations.py
- razd/ui/: main_window.py, time_tracking_tab.py, focus_timer_tab.py, dialogs.py
- razd/config/: defaults.toml, settings.py
- tests/: test_tracker.py, test_agent.py, test_ui.py (pytest-qt)
- pyproject.toml: deps + ruff config + pytest config
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
- type hints wszędzie (Python 3.13, from __future__ import annotations)
- ruff format + ruff check przed każdym commitem
- line-length = 100
- docstringi tylko dla publicznych funkcji/klas (Google style)
- preferuj dataclasses/NamedTuple dla DTO, Pydantic tylko dla I/O JSON
- async tylko gdzie naprawdę potrzeba (claude-agent-sdk jest async); reszta sync z QThread
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
imperatyw, angielski, max 72 znaki w subject; scope z listy: tracker, agent, ui, db, config, build, docs; przykłady: feat(tracker): add idle detection via GetLastInputInfo, fix(agent): handle SDK timeout gracefully, refactor(ui): extract focus timer state machine
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
- pytest + pytest-qt dla wszystkich warstw
- unit testy dla tracker (mock pywin32) i db (in-memory SQLite)
- integration testy dla agenta przez claude-agent-sdk z mock SDK responses
- pytest-qt dla UI: smoke test każdej zakładki (otwiera się, klika się start/stop)
- bez gonienia coverage % — priorytet happy paths publicznych API
<!-- /SECTION:testing -->

## Anti Patterns
<!-- SECTION:anti_patterns -->
- nie wywołuj subprocess Claude Code synchronicznie z UI thread → freeze
- nie hardkoduj ścieżek Chrome/Edge — używaj registry / shutil.which
- nie zapisuj URLi w plain text bez filtrowania (regex na tokens, passwords w query string)
- nie używaj time.sleep w UI — QTimer
- nie trzymaj otwartych connection do SQLite na cross-thread — używaj per-thread connection lub QSqlDatabase
- nie wrzucaj logiki biznesowej do slotów Qt — slot deleguje do service layer
<!-- /SECTION:anti_patterns -->
