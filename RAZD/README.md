# RAZD — Time Tracking & Focus

Desktopowa aplikacja Windows 11 do śledzenia aktywności, zarządzania czasem i sesji głębokiego skupienia. Integruje się z Notion (projekty i zadania) oraz Claude Code (CC sessions).

## Uruchomienie

```
.venv/Scripts/python.exe main.py               # normalny start
.venv/Scripts/python.exe main.py --minimized   # start w tle (autostart z Windows)
.venv/Scripts/python.exe -m pytest tests/ -v   # testy
```

## Stack

| Warstwa       | Technologia                              |
|---------------|------------------------------------------|
| UI            | Python 3.13 · PySide6 (Qt6)             |
| Baza danych   | SQLite (via `razd/db/repository.py`)     |
| Integracja AI | claude-agent-sdk (CC sessions)           |
| Notion        | notion-client 3.x (`data_sources` API)  |
| Tracker       | psutil + polling co 3s                  |
| Testy         | pytest + pytest-qt                      |

## Architektura

```
razd/
  tracker/         # poller aktywności + klasyfikator AI
  agent/           # klient CC (claude-agent-sdk)
  db/              # SQLite schema + repository
  notion/          # projects_fetcher, tasks_fetcher, sync_worker
  ui/              # wszystkie zakładki Qt
  config/          # ustawienia (TOML + dataclasses)
  autostart.py     # rejestr Windows (autostart)
  shortcut.py      # skrót na pulpicie (.lnk)
main.py            # entry point
```

## Funkcje

### Śledzenie aktywności (Tracker)
Poller co 3s rejestruje aktywną aplikację i okno. Zapisuje eventy do SQLite. Wykrywa sesje CC (Claude Code) i mierzy ich czas.

### AI Kategoryzacja (Agent)
Wątek `RazdAgentThread` klasyfikuje procesy przez claude-agent-sdk. Przypisuje kategorie (praca/rozrywka/inne) i liczy czas na kategorie.

### Time Tracking Tab
Oś czasu dzisiejszej aktywności. Grupy aplikacji (CC sessions, focus sessions, rozrywka). Liczniki uptime App / PC w toolbarze.

### Focus Timer Tab
Okrągła tarcza timera (30–120 min, domyślnie 60 min). Whitelist aplikacji — alert gdy wyjdziesz poza focus. Wynik sesji 1–10 na podstawie whitelist compliance. Dźwięk po zakończeniu. Sync czasu do Notion.

### Break Engine
Alert po skonfigurowanym czasie ciągłej pracy (domyślnie 45 min).

### Distraction Detector
Wykrywa szybkie przełączanie aplikacji (>N przełączeń/min) i wysyła alert do tray.

### Projekty
Pobiera projekty z bazy Notion. 4 sloty pinnowanych projektów z kolorowymi kartami i statystykami czasu.

### Zadania (Kanban)
Kanban board 3 kolumny (Do zrobienia / W trakcie / Gotowe) dla każdego pinnowanego projektu. Filtry statusów. Tworzenie i edycja zadań (tytuł, deadline, szczegóły) z synchronizacją do Notion.

### Eksport do Notion
Sync danych dziennych do wybranych baz Notion co N minut.

### Autostart Windows
Wpis w rejestrze `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Konfigurowalny z menu tray.

### Tray & Background
Ikona R (niebieski kwadrat) zawsze w zasobniku. X na oknie = przejście w tło, nie zamknięcie. Menu tray: pokaż, autostart, skrót na pulpicie, zakończ.

## Konfiguracja

Plik `.env` w katalogu projektu:

```
RAZD_NOTION_TOKEN=secret_...
RAZD_NOTION_PROJECTS_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RAZD_NOTION_TASKS_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Pozostałe ustawienia: `razd/config/defaults.toml`.

## Baza danych

SQLite w `~/.razd/razd.db`. Schemat: `razd/db/schema.sql`.

Główne tabele: `activity_events`, `focus_sessions`, `focus_process_samples`, `notion_projects`, `notion_tasks`, `pinned_projects`.

## Testy

```
.venv/Scripts/python.exe -m pytest tests/ -v
```

Pokrycie: tracker, db, agent, UI smoke, focus timer, CC scanner, break engine, distraction detector, daily report, Notion exporter.

## Ograniczenia MVP

- Brak obsługi wielu użytkowników
- Tracker działa tylko na Windows (psutil + win32)
- Notion API: tylko bazy `data_sources` (notion-client 3.x)
