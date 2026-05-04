# RAZD — Instalacja i konfiguracja

## Wymagania

- Windows 10/11 (64-bit)
- Python 3.13+
- Claude Code CLI zainstalowany globalnie (`cc --version` działa)
- Aktywna subskrypcja Claude lub klucz API w zmiennej `ANTHROPIC_API_KEY`
- Claude Env Manager (CEM) z PySide6

## 1. Instalacja zależności

Z katalogu `claude-env-manager/`:

```bash
.venv/Scripts/python.exe -m pip install psutil pywin32 uiautomation claude-code-sdk
```

Jeśli używasz `pyproject.toml` w RAZD:

```bash
.venv/Scripts/pip install -e RAZD/
```

## 2. Wpięcie w CEM (top menu)

W pliku startowym CEM (`main.py` lub odpowiednik) dodaj po inicjalizacji `QMainWindow`:

```python
import razd

# menu_bar to QMenuBar głównego okna CEM
razd.register_menu(menu_bar)
```

`register_menu` dodaje pozycję **RAZD** do paska menu. Kliknięcie "Otwórz RAZD" otwiera okno modułu (lazy init — tworzone przy pierwszym otwarciu, następne wywołania pokazują to samo okno).

## 3. Konfiguracja Claude Code SDK

RAZD używa `claude-code-sdk` do komunikacji z agentem CC. SDK wymaga działającego procesu Claude Code CLI.

### Sprawdź dostępność CC CLI

```bash
cc --version
```

SDK szuka `cc` w `PATH`. Jeśli CLI jest zainstalowany w niestandardowym miejscu, ustaw zmienną środowiskową:

```
CLAUDE_CODE_PATH=C:\ścieżka\do\cc.exe
```

### Klucz API

Ustaw przed uruchomieniem CEM:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Lub trwale przez Panel sterowania → Zmienne środowiskowe systemu.

## 4. Konfiguracja RAZD (`~/.razd/config.toml`)

Plik tworzony automatycznie przy pierwszym zapisie ustawień. Możesz też stworzyć go ręcznie:

```
C:\Users\<TwójLogin>\.razd\config.toml
```

Przykład z nadpisaniem domyślnych wartości:

```toml
[tracking]
poll_interval_ms = 3000       # odpytuj co 3s zamiast 2s
idle_threshold_secs = 120     # idle po 2 minutach bez ruchu

[focus]
default_duration_mins = 50    # domyślna długość focus session
whitelist = [
    "python.exe",
    "code.exe",
    "WindowsTerminal.exe",
]

[paths]
db = "D:/dane/razd.db"        # niestandardowa lokalizacja bazy
```

Pełna lista opcji z domyślnymi wartościami: `razd/config/defaults.toml`.

## 5. Baza danych SQLite

Baza tworzy się automatycznie przy starcie modułu w lokalizacji:

```
C:\Users\<TwójLogin>\.razd\razd.db
```

Schemat: tabele `events`, `processes`, `categories`, `url_mappings`, `user_decisions`.  
Backup: wystarczy skopiować plik `.razd/razd.db`.

## 6. Uruchomienie testów

```bash
cd RAZD
..\\.venv\Scripts\python.exe -m pytest tests/ -v
```

Oczekiwany wynik: **54 passed**.

## 7. Jak działa agent (przepływ)

```
[Tracker poll 2s]
    → EventDTO (process, title, url, idle)
    → RazdAgentThread (QThread z asyncio)
        → claude-code-sdk query()
            → jeśli nieznany proces/URL → mcp tool ask_user
                → RazdAskUserDialog (UI thread przez _DialogBridge)
                → odpowiedź → SQLite (categories + processes/url_mappings)
    → TimeTrackingTab.on_event() — aktualizacja osi czasu
    → FocusTimerTab.check_active_app() — sprawdzenie whitelisty
```

Agent CC uczy się kontekstu przez dialog z userem. Po jednorazowej odpowiedzi proces/URL jest zapamiętany i nie jest pytany ponownie (cooldown: 300s, konfigurowalne).

## 8. Znane ograniczenia MVP

- Ekstrakcja URL tylko z Chrome i Edge (Firefox wymaga dodatkowej konfiguracji)
- Agent CC wymaga połączenia z internetem (API Anthropic)
- `uiautomation` może wymagać uruchomienia CEM **bez** UAC elevation (lub z tym samym poziomem uprawnień co przeglądarka)
- Na pierwszym uruchomieniu Windows Defender może blokować `uiautomation` — dodaj wyjątek dla procesu python.exe
