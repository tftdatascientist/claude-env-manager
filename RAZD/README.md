# RAZD — Time Tracking & Focus

Moduł CEM do automatycznego trackingu czasu pracy i fokusu, sterowany agentem Claude Code.
Działa w tle na Windows, kategoryzuje aktywność przez AI i uczy się zachowań użytkownika przez dialog.

## Uruchomienie

```bash
.venv/Scripts/python.exe main.py               # normalny start
.venv/Scripts/python.exe main.py --minimized   # start w tle (autostart)
.venv/Scripts/python.exe -m pytest tests/ -v   # testy (133 pass)
```

## Stack

| Warstwa | Technologia |
|---------|-------------|
| UI | Python 3.13 · PySide6 (Qt6) |
| Tracker | psutil · pywin32 · uiautomation |
| Agent | claude-agent-sdk (Claude Code) |
| Baza danych | SQLite (lokalnie) |
| Eksport | notion-client 3.x |

## Architektura

```
[Tracker poll 2s] ──► [EventDTO JSON] ──► [Claude Code Agent (QThread)]
                                                    │
                                         [SQLite — events / categories /
                                          url_mappings / user_decisions /
                                          focus_sessions / cc_sessions /
                                          break_events / distraction_events]
                                                    │
                              ┌─────────────────────┴──────────────────────┐
                              ▼                                             ▼
                   [TimeTrackingTab — oś czasu]              [FocusTimerTab — timer]
```

## Funkcje

### Śledzenie aktywności (Tracker)
- Polling co 2s: aktywne okno, tytuł, nazwa procesu
- Detekcja idle przez `GetLastInputInfo` (próg 60s)
- Ekstrakcja URL z Chrome / Edge przez UI Automation
- Filtr prywatności: tokeny i hasła z query string są usuwane przed zapisem

### AI Kategoryzacja (Agent)
- Persistent sesja Claude Code Agent przez `claude-agent-sdk`
- Tools: `save_category`, `ask_user`, `query_knowledge`
- Gdy agent napotka nieznany proces/URL → dialog Qt z pytaniem do użytkownika
- Odpowiedź trafia do SQLite i jest używana w kolejnych sesjach

### Time Tracking Tab
- Oś czasu dnia z blokami aktywności per kategoria (kolory)
- Fioletowe bloki sesji Focus, zielone bloki sesji Claude Code
- Panel statystyk: czas aktywny / produktywny / idle
- Historia dni przez `QCalendarWidget`
- Wskaźnik rozproszenia (przełączenia/min) w czasie rzeczywistym
- Eksport CSV

### Focus Timer Tab
- Whitelist aplikacji (dodaj / usuń)
- Czas sesji: 30 / 60 / 90 / 120 min (preset lub własny)
- Stany: start → running → paused → ended
- Gdy aktywna aplikacja nie jest na whiteliście → tray ping + dialog ostrzegawczy
- Po zakończeniu: wynik skupienia 1–10 (% czasu spędzonego w aplikacjach z whitelisty)
- Wynik i czas sesji zapisywane do SQLite

### Break Engine
- Śledzi ciągły czas pracy bez przerwy
- Domyślny interwał: 50 min (konfigurowalny w `defaults.toml`)
- Po przekroczeniu interwału: powiadomienie tray + sygnał do UI
- Reset przy idle > 5 min lub ręcznym potwierdzeniu przerwy

### Distraction Detector
- Sliding window 60s: zlicza przełączenia między aplikacjami
- Alert tray gdy > 6 przełączeń/min przez 3 kolejne pomiary
- Score (przełączenia/min) aktualizowany w TimeTrackingTab na żywo

### CC Monitoring
- Automatyczne wykrywanie procesów `cc.exe`, `claude.exe` i Node.js z `@anthropic` w cmdline
- Sesje Claude Code zapisywane do `cc_sessions` / `cc_snapshots` w SQLite
- Zielone bloki sesji CC na osi czasu
- Panel aktywnych sesji CC w bieżącym dniu

### Raport Dnia
- Dialog `RazdDailyReportDialog` z pełną analityką:
  - Wynik produktywności 0–100 (kolor zielony/żółty/czerwony)
  - Czas aktywny / produktywny / idle
  - Top kategorie z paskami procentowymi
  - Lista sesji Focus z wynikami
  - Lista sesji Claude Code z projektami
  - Compliance przerw (zasugerowane vs wzięte)
  - Liczba alertów rozproszenia i średnie przełączenia/min

### Eksport do Notion
- `RazdNotionExporter` — dzienne podsumowanie czasu per aplikacja do bazy Notion
- `RazdNotionSyncThread` — automatyczna synchronizacja co N minut (konfigurowalny interwał)
- Opcjonalny eksport URLi (włączany w konfiguracji)
- Token i DB ID przez zmienne środowiskowe: `RAZD_NOTION_TOKEN`, `RAZD_NOTION_DB_ID`

### Autostart Windows
- Rejestracja w `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Włącz/wyłącz z menu tray → "Autostart z Windows"
- Tryb `--minimized`: start bez okna, tracker i agent w tle od razu

### Tray & Background
- Ikona systemowa (litera R, niebieski kwadrat) zawsze w zasobniku
- Zamknięcie okna (X) = przejście w tło, nie zamknięcie aplikacji
- Toolbar: "Przejdź w tło" ukrywa okno bez zatrzymywania serwisów
- Podwójne kliknięcie na ikonę tray = przywróć okno

## Konfiguracja

Plik `razd/config/defaults.toml` — nadpisywany przez `~/.razd/settings.toml`:

```toml
[tracking]
poll_interval_s = 2
idle_threshold_s = 60

[break]
work_interval_min = 50

[distraction]
threshold_spm = 6.0

[notion]
enabled = false
sync_interval_mins = 30
export_urls = false
```

## Baza danych

SQLite w `~/.razd/razd.db`. Główne tabele:

| Tabela | Zawartość |
|--------|-----------|
| `events` | surowe eventy trackera |
| `processes` | znane procesy z kategorią |
| `categories` | słownik kategorii |
| `url_mappings` | mapowania URL → kategoria |
| `user_decisions` | odpowiedzi użytkownika na pytania agenta |
| `focus_sessions` | sesje Focus Timera z wynikiem |
| `focus_process_samples` | próbki procesu w trakcie sesji focus |
| `cc_sessions` | sesje Claude Code |
| `cc_snapshots` | snapshoty procesów CC |
| `break_events` | zasugerowane i wzięte przerwy |
| `distraction_events` | alerty rozproszenia |

## Testy

133 testów pytest (pytest-qt). Pokrycie: tracker, db, agent, UI smoke, focus timer, CC scanner, break engine, distraction detector, daily report, Notion exporter.

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

## Ograniczenia MVP

- Windows 10/11 only (pywin32, uiautomation)
- URL extraction tylko Chrome / Edge (Firefox UI Automation niestabilne)
- Wymaga aktywnej subskrypcji Claude Code lub klucza API
- Privacy: URLs zapisywane bez tokenów/haseł (regex sanitize)
