# CLEANING.md


## CLAUDE.md

   2: Moduł CEM do auto-trackingu czasu i fokusu, sterowany agentem Claude Code który uczy się znaczenia procesów/URLs przez dialog z userem.
   4: @ARCHITECTURE.md
   5: @PLAN.md
   6: @CONVENTIONS.md
   8: - name: RAZD
   9: - type: moduł desktop (PySide6) w Claude Env Manager
  10: - client: własny (Radek)
  13: - PySide6
  14: - psutil
  15: - pywin32
  16: - uiautomation
  17: - claude-agent-sdk
  18: - SQLite
  20: - nie używaj zewnętrznych API trackingu (Toggl, RescueTime, Clockify) — wszystko lokalnie
  21: - nie blokuj Qt UI threada — każdy I/O i polling w QThread/QTimer
  22: - nie modyfikuj struktury CEM poza punktem wpięcia (top menu)
  23: - nie wysyłaj danych aktywności poza maszynę bez zgody usera (privacy first)
  24: - nie hardkoduj ścieżek do Chrome/Edge — discover przez registry/where
  26: - moduł wpina się w CEM przez QMenuBar (top menu CEM → RAZD)
  28: - agent CC działa persistent w tle gdy komputer włączony, czyta strumień zdarzeń trackera
  29: - nieznany proces/URL → agent generuje pytanie → dialog Qt do usera → odpowiedź → zapis w SQLite
  31: - platforma MVP: Windows-only (pywin32, uiautomation API), cross-platform na fazę 2
  32: - rozróżniamy dwie role: Tracker (zbiera surowe sygnały) vs Agent (interpretuje, kategoryzuje, pyta)

## ARCHITECTURE.md

   2: RAZD to trójwarstwowy moduł PySide6 wpięty w Claude Env Manager. Warstwa Tracker zbiera niskopoziomowe sygnały aktywności (aktywne okno, URL z przeglądarki, idle/active) przez polling co 2s. Strumień zdarzeń JSON trafia do Claude Code Agenta (claude-agent-sdk, persistent session), który kategoryzuje aktywność, buduje bazę wiedzy o procesach i URLach, a gdy napotka coś nieznanego — wystawia pytanie do usera przez dialog Qt. Warstwa UI to dwie zakładki: Time Tracking (oś czasu, kategorie, statystyki dzień/tydzień) i Focus Timer (timer 30-120min, whitelist appek, ping przy ucieczce z fokusu).
   4: - Tracker: psutil (lista procesów), pywin32 (GetForegroundWindow + GetLastInputInfo dla idle), uiautomation (extract URL z address bar Chrome/Edge)
   5: - Event stream: JSON lines do agenta, schema {ts, event_type, process, window_title, url?, idle_seconds}
   7: - Knowledge base: lokalny SQLite (events, processes, categories, url_mappings, user_decisions)
   8: - UI: PySide6 widget RazdMainWindow z QTabWidget, wpięty do CEM przez plugin pattern
   9: - TimeTrackingTab: oś czasu (QGraphicsView lub custom), agregacja godzin per kategoria, eksport CSV
  10: - FocusTimerTab: QListWidget whitelist + QSpinBox czas (30/60/90/120) + QTimer + QSystemTrayIcon do alertów
  11: - Question dialog: Qt modal pytający o nieznany proces/URL, odpowiedź zasila bazę wiedzy
  13: [Tracker poll 2s] → [event JSON] → [Claude Code Agent persistent session]
  14:                                            [Knowledge SQLite ← zapis kategoryzacji]
  15:                                            [PySide6 TimeTrackingTab — update osi czasu]
  16: [Agent napotyka nieznany proces] → [QDialog pytanie do usera] → [odpowiedź] → [agent → SQLite]
  17: [FocusTimer start] → [whitelist appek] → [QTimer countdown 30-120min]
  18:                           [Tracker wykrywa app spoza whitelisty]
  19:                           [QSystemTrayIcon ping + modal dialog: wracaj lub zatrzymaj]
  22: - [x] AI engine = Claude Code przez claude-agent-sdk, nie bezpośredni Claude API | 2026-04-29 | spójność z preferencjami usera (CC robi maks roboty), pełne agentic capabilities, tool use bez własnego harnessa
  23: - [x] knowledge base lokalny SQLite, nie Notion | 2026-04-29 | zero latencji sieci, działa offline; eksport do Notion można dorobić w fazie 2
  24: - [x] tracking polling co 2s, nie event-driven (SetWinEventHook) | 2026-04-29 | prostsze, deterministyczne, niskie zużycie CPU; event hooks na fazę 2 jeśli potrzeba
  25: - [x] PySide6 moduł CEM, nie oddzielna app | 2026-04-29 | jeden install, jedno menu, spójność stacku z CEM
  26: - [x] Windows-only na MVP | 2026-04-29 | pywin32 + uiautomation są Windows-specific; Linux/Mac na fazę 2 z innymi API
  27: - 2026-05-02 00:11 | Decyzja: focus scoring — podczas sesji focus zbierane próbki procesu co 2s do focus_process_samples, po zakończeniu score=round(whitelist_count/total*10) min 1; blok focus renderowany jako fioletowa nakładka na osi czasu TimeTrackingTab | 2026-05-02
  29: - Windows 10/11 only (pywin32, uiautomation API)
  30: - Wymaga zainstalowanego Claude Code SDK + aktywnej subskrypcji/API key
  31: - Claude Code Agent musi być uruchamiany w QThread (nie blokować UI)
  32: - URL extraction tylko z Chrome/Edge na MVP (Firefox UI Automation jest mniej stabilne)
  33: - Privacy: URLs filtrujemy z tokenów/haseł przed zapisem do bazy
  34: - Wszystkie operacje SQLite przez QThreadPool (Qt + SQLite + threading wymaga ostrożności)

## CONVENTIONS.md

   2: snake_case dla plików .py i funkcji; PascalCase dla klas Qt z prefiksem Razd (RazdMainWindow, RazdTimeTrackingTab, RazdFocusTimerTab, RazdTracker, RazdAgent); UPPER_CASE dla stałych; nazwy sygnałów Qt w stylu on_<event> dla slotów, <subject>_<changed|emitted> dla sygnałów
   4: - razd/: główny pakiet modułu
   5: - razd/__init__.py: rejestracja w CEM (entry point dla menu)
   6: - razd/tracker/: active_window.py, idle.py, browser_url.py, poller.py
   7: - razd/agent/: client.py (claude-agent-sdk wrapper), prompts.py, tools.py
   8: - razd/db/: schema.sql, repository.py, migrations.py
   9: - razd/ui/: main_window.py, time_tracking_tab.py, focus_timer_tab.py, dialogs.py
  10: - razd/config/: defaults.toml, settings.py
  15: - ruff format + ruff check przed każdym commitem
  16: - line-length = 100
  17: - docstringi tylko dla publicznych funkcji/klas (Google style)
  18: - preferuj dataclasses/NamedTuple dla DTO, Pydantic tylko dla I/O JSON
  19: - async tylko gdzie naprawdę potrzeba (claude-agent-sdk jest async); reszta sync z QThread
  21: imperatyw, angielski, max 72 znaki w subject; scope z listy: tracker, agent, ui, db, config, build, docs; przykłady: feat(tracker): add idle detection via GetLastInputInfo, fix(agent): handle SDK timeout gracefully, refactor(ui): extract focus timer state machine
  24: - unit testy dla tracker (mock pywin32) i db (in-memory SQLite)
  25: - integration testy dla agenta przez claude-agent-sdk z mock SDK responses
  27: - bez gonienia coverage % — priorytet happy paths publicznych API
  29: - nie wywołuj subprocess Claude Code synchronicznie z UI thread → freeze
  30: - nie hardkoduj ścieżek Chrome/Edge — używaj registry / shutil.which
  31: - nie zapisuj URLi w plain text bez filtrowania (regex na tokens, passwords w query string)
  32: - nie używaj time.sleep w UI — QTimer
  33: - nie trzymaj otwartych connection do SQLite na cross-thread — używaj per-thread connection lub QSqlDatabase
  34: - nie wrzucaj logiki biznesowej do slotów Qt — slot deleguje do service layer

## PLAN.md

   2: - status: notion-complete
   3: - goal: MVP RAZD: moduł CEM z dwiema zakładkami — Time Tracking (auto-detekcja procesów/URLs/idle + AI kategoryzacja przez Claude Code z dialogiem nauki) i Focus Timer (whitelist appek 30-120min + ping gdy odlatujesz) + eksport do Notion
   4: - session: 3
   5: - updated: 2026-05-02 00:52
   7: - task: brak — F1+F2+F3 ukończone, 133/133 testów zielonych
   9: - [x] F1-DB + F1-Engine + F1-UI + F1-Tests: RazdBreakEngine, break_events DB, BreakBar UI, tray, 11 testów
  10: - [x] F2-DB + F2-Detector + F2-UI + F2-Tests: RazdDistractionDetector, distraction_events DB, score panel, 10 testów
  11: - [x] F3-Repo + F3-Dialog + F3-Tests: get_daily_report, RazdDailyReportDialog, 12 testów
  13: - Bootstrap projektu: szkielet razd/, integracja z top menu CEM, RazdMainWindow z dwiema zakładkami
  14: - Tracker: active_window, idle, browser_url, poller (EventDTO co 2s)
  15: - Agent: RazdAgentThread, tools (save_category, ask_user, query_knowledge), prompts
  16: - DB: schema SQLite, RazdRepository (events, processes, categories, url_mappings, user_decisions)
  17: - UI: TimeTrackingTab (oś czasu, kategorie, historia DB), FocusTimerTab (whitelist, countdown, tray ping)
  18: - Config: defaults.toml + RazdSettings (load/save/merge)
  19: - Notion integration: RazdNotionExporter, NotionActivityRecord, RazdNotionSyncThread
  20: - Testy: 67/67 pass (tracker, db, agent, dialogs, focus timer, time tracking, settings, notion, UI smoke)
  21: - Focus scoring: focus_sessions + focus_process_samples w SQLite, scoring 1-10, blok focus na osi czasu, dialog podsumowania; 82/82 testów
  22: - CC monitoring: cc_scanner (psutil, cc/claude/node+@anthropic), cc_sessions + cc_snapshots w SQLite, _CcSessionTracker w pollerze, bloki CC na osi czasu, panel aktywnych sesji; 100/100 testów (18 nowych)
  26: - 2026-05-02 17:56 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  27: - 2026-05-02 17:30 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  28: - 2026-05-02 16:53 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  29: - 2026-05-02 16:27 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  30: - 2026-05-02 12:35 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  31: - 2026-05-02 11:46 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  32: - 2026-05-02 11:41 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  33: - 2026-05-02 01:45 | HANDOFF: sesja zamknięta, ostatnie current='brak — F1+F2+F3 ukończone, 133/133 testów zielonych'
  34: - 2026-05-02 01:20 | HANDOFF: sesja zamknięta, ostatnie current='brak — CC monitoring ukończony, 100/100 testów zielonych'
  35: - 2026-05-02 01:17 | HANDOFF: sesja zamknięta, ostatnie current='brak — CC monitoring ukończony, 100/100 testów zielonych'

## CHANGELOG.md

   3: - session:1 | 2026-04-30 | szkielet pakietu razd/ + pyproject.toml + ruff config
   4: - session:1 | 2026-04-30 | entry point: razd/__init__.py rejestracja w CEM (top menu hook)
   5: - session:1 | 2026-04-30 | RazdMainWindow z QTabWidget (dwie zakładki: TimeTracking, FocusTimer) — pusty szkielet
   6: - session:1 | 2026-04-30 | schema SQLite: events, processes, categories, url_mappings, user_decisions + repository.py
   7: - session:1 | 2026-04-30 | Tracker.active_window: pywin32 GetForegroundWindow + GetWindowText
   8: - session:1 | 2026-04-30 | Tracker.idle: GetLastInputInfo, threshold 60s = idle
   9: - session:1 | 2026-04-30 | Tracker.browser_url: uiautomation extract URL z Chrome/Edge + privacy filter
  10: - session:1 | 2026-04-30 | Tracker.poller: agreguje sygnały, emituje EventDTO co 2s (QObject + QTimer)
  11: - session:1 | 2026-04-30 | format strumienia eventów JSON do agenta (EventDTO.to_json())
  12: - session:1 | 2026-04-30 | integracja claude-code-sdk: RazdAgentThread (QThread) + RazdAgentWorker + asyncio queue
  13: - session:1 | 2026-04-30 | custom tools MCP: save_category, ask_user, query_knowledge (in-process MCP server)
  14: - session:1 | 2026-04-30 | privacy filter: regex sanitize_url w browser_url.py
  15: - session:1 | 2026-04-30 | dialog Qt RazdAskUserDialog + ask_user_blocking (marshal UI thread przez _DialogBridge)
  16: - session:1 | 2026-04-30 | RazdMainWindow spina Tracker → Agent → UI (poller, agent thread, repo)
  17: - session:1 | 2026-04-30 | TimeTrackingTab: akumulacja sekund per kategoria, oś czasu QGraphicsView z blokami, QListWidget kategorii z czasem, wybór dnia przez QCalendarWidget, ładowanie historii z DB
  18: - session:1 | 2026-04-30 | FocusTimerTab: whitelist QListWidget + Add/Remove, QSpinBox + presety 30/60/90/120min, _FocusState machine, QTimer countdown, start/pause/resume/reset, QSystemTrayIcon ping, _EscapeDialog gdy app spoza whitelisty
  19: - session:1 | 2026-04-30 | config TOML: defaults.toml + RazdSettings (load/save, deep merge user override, ścieżki posix)
  21: - session:1 | 2026-04-30 | dokumentacja install: INSTALL.md — wymagania, wpięcie w CEM, konfiguracja CC SDK, config TOML, przepływ agenta, ograniczenia MVP
  22: - session:2 | 2026-05-01 | Notion integration: razd/notion/ — schema.py (NotionActivityRecord), exporter.py (RazdNotionExporter upsert), sync_worker.py (RazdNotionSyncThread cykliczny sync)
  23: - session:2 | 2026-05-01 | RazdSettings: sekcja [notion] — enabled, sync_interval_mins, export_urls
  24: - session:2 | 2026-05-01 | RazdMainWindow: wpięcie RazdNotionSyncThread gdy notion.enabled=true
  25: - session:2 | 2026-05-01 | testy notion: 12 testów (normalize, map_category, record properties, export session upsert/update/no-events/missing-token, url privacy) — 12/12 pass
  26: - session:2 | 2026-05-01 | fix: test_export_session_updates_existing_page — mock search zamiast databases.query
  28: - 2026-04-29 01:41 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  29: - 2026-04-29 01:43 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  30: - 2026-04-29 01:47 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  31: - 2026-04-30 | session:2 | zakończono TimeTrackingTab (oś czasu, kategorie, historia DB, wybór dnia) + FocusTimerTab (whitelist, countdown, tray ping, escape dialog)
  32: - 2026-04-30 11:40 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  33: - 2026-04-30 13:28 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  34: - 2026-04-30 13:32 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  35: - 2026-04-30 13:37 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  36: - 2026-04-30 13:42 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'
  37: - 2026-04-30 13:45 | HANDOFF: sesja zamknięta, ostatnie current='Bootstrap projektu — szkielet razd/ + integracja z top menu CEM, pusty RazdMainWindow z dwiema zakładkami'

## README.md

   2: Moduł CEM do automatycznego trackingu czasu pracy i fokusu, sterowany agentem Claude Code.
   3: Działa w tle na Windows, kategoryzuje aktywność przez AI i uczy się zachowań użytkownika przez dialog.
   5: ```bash
  10: | Warstwa | Technologia |
  12: | Tracker | psutil · pywin32 · uiautomation |
  13: | Agent | claude-agent-sdk (Claude Code) |
  14: | Baza danych | SQLite (lokalnie) |
  15: | Eksport | notion-client 3.x |
  17: [Tracker poll 2s] ──► [EventDTO JSON] ──► [Claude Code Agent (QThread)]
  18:                                          [SQLite — events / categories /
  19:                                           url_mappings / user_decisions /
  20:                                           focus_sessions / cc_sessions /
  21:                                           break_events / distraction_events]
  22:                               ┌─────────────────────┴──────────────────────┐
  23:                               ▼                                             ▼
  24:                    [TimeTrackingTab — oś czasu]              [FocusTimerTab — timer]
  27: - Polling co 2s: aktywne okno, tytuł, nazwa procesu
  28: - Detekcja idle przez `GetLastInputInfo` (próg 60s)
  29: - Ekstrakcja URL z Chrome / Edge przez UI Automation
  30: - Filtr prywatności: tokeny i hasła z query string są usuwane przed zapisem
  32: - Persistent sesja Claude Code Agent przez `claude-agent-sdk`
  33: - Tools: `save_category`, `ask_user`, `query_knowledge`
  34: - Gdy agent napotka nieznany proces/URL → dialog Qt z pytaniem do użytkownika
  35: - Odpowiedź trafia do SQLite i jest używana w kolejnych sesjach
  37: - Oś czasu dnia z blokami aktywności per kategoria (kolory)
  38: - Fioletowe bloki sesji Focus, zielone bloki sesji Claude Code
  39: - Panel statystyk: czas aktywny / produktywny / idle
  40: - Historia dni przez `QCalendarWidget`
  41: - Wskaźnik rozproszenia (przełączenia/min) w czasie rzeczywistym
  42: - Eksport CSV
  44: - Whitelist aplikacji (dodaj / usuń)
  45: - Czas sesji: 30 / 60 / 90 / 120 min (preset lub własny)
  46: - Stany: start → running → paused → ended
  47: - Gdy aktywna aplikacja nie jest na whiteliście → tray ping + dialog ostrzegawczy
  48: - Po zakończeniu: wynik skupienia 1–10 (% czasu spędzonego w aplikacjach z whitelisty)
  49: - Wynik i czas sesji zapisywane do SQLite
  51: - Śledzi ciągły czas pracy bez przerwy
  52: - Domyślny interwał: 50 min (konfigurowalny w `defaults.toml`)
  53: - Po przekroczeniu interwału: powiadomienie tray + sygnał do UI
  54: - Reset przy idle > 5 min lub ręcznym potwierdzeniu przerwy
  56: - Sliding window 60s: zlicza przełączenia między aplikacjami
  57: - Alert tray gdy > 6 przełączeń/min przez 3 kolejne pomiary
  58: - Score (przełączenia/min) aktualizowany w TimeTrackingTab na żywo
  60: - Automatyczne wykrywanie procesów `cc.exe`, `claude.exe` i Node.js z `@anthropic` w cmdline
  61: - Sesje Claude Code zapisywane do `cc_sessions` / `cc_snapshots` w SQLite
  62: - Zielone bloki sesji CC na osi czasu
  63: - Panel aktywnych sesji CC w bieżącym dniu
  65: - Dialog `RazdDailyReportDialog` z pełną analityką:
  66:   - Wynik produktywności 0–100 (kolor zielony/żółty/czerwony)
  67:   - Czas aktywny / produktywny / idle
  68:   - Top kategorie z paskami procentowymi
  69:   - Lista sesji Focus z wynikami
  70:   - Lista sesji Claude Code z projektami
  71:   - Compliance przerw (zasugerowane vs wzięte)
  72:   - Liczba alertów rozproszenia i średnie przełączenia/min
  74: - `RazdNotionExporter` — dzienne podsumowanie czasu per aplikacja do bazy Notion
  75: - `RazdNotionSyncThread` — automatyczna synchronizacja co N minut (konfigurowalny interwał)
  76: - Opcjonalny eksport URLi (włączany w konfiguracji)
  77: - Token i DB ID przez zmienne środowiskowe: `RAZD_NOTION_TOKEN`, `RAZD_NOTION_DB_ID`
  79: - Rejestracja w `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  80: - Włącz/wyłącz z menu tray → "Autostart z Windows"
  81: - Tryb `--minimized`: start bez okna, tracker i agent w tle od razu
  84: - Zamknięcie okna (X) = przejście w tło, nie zamknięcie aplikacji
  85: - Toolbar: "Przejdź w tło" ukrywa okno bez zatrzymywania serwisów
  86: - Podwójne kliknięcie na ikonę tray = przywróć okno
  88: Plik `razd/config/defaults.toml` — nadpisywany przez `~/.razd/settings.toml`:
  89: ```toml
  90: [tracking]
  91: poll_interval_s = 2
  92: idle_threshold_s = 60
  93: [break]
  94: work_interval_min = 50
  95: [distraction]
  96: threshold_spm = 6.0
  97: [notion]
  98: enabled = false
  99: sync_interval_mins = 30
 100: export_urls = false
 102: SQLite w `~/.razd/razd.db`. Główne tabele:
 103: | Tabela | Zawartość |
 104: | `events` | surowe eventy trackera |
 105: | `processes` | znane procesy z kategorią |
 106: | `categories` | słownik kategorii |
 107: | `url_mappings` | mapowania URL → kategoria |
 108: | `user_decisions` | odpowiedzi użytkownika na pytania agenta |
 109: | `focus_sessions` | sesje Focus Timera z wynikiem |
 110: | `focus_process_samples` | próbki procesu w trakcie sesji focus |
 111: | `cc_sessions` | sesje Claude Code |
 112: | `cc_snapshots` | snapshoty procesów CC |
 113: | `break_events` | zasugerowane i wzięte przerwy |
 114: | `distraction_events` | alerty rozproszenia |
 117: ```bash
 120: - Windows 10/11 only (pywin32, uiautomation)
 121: - URL extraction tylko Chrome / Edge (Firefox UI Automation niestabilne)
 122: - Wymaga aktywnej subskrypcji Claude Code lub klucza API
 123: - Privacy: URLs zapisywane bez tokenów/haseł (regex sanitize)
