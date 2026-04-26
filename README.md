# Claude Environment Manager (CEM)

Desktopowa aplikacja Windows 11 (PySide6) do zarządzania wszystkimi narzędziami i zasobami Claude Code z jednego miejsca.

## Funkcje

### Develop
- **Sesje CC** (`Ctrl+8`) — 4 równoległe sloty projektów z pełnym monitoringiem sesji Claude Code: model, koszt, kontekst%, faza pracy. Każdy slot zawiera zakładki: Dane, ZADANIA, PLAN.md, CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md, Sesje
- **Zadania** (`Ctrl+Z`) — moduł zarządzania zadaniami w plikach PLAN.md zgodnych z formatem DPS. Auto-wykrywanie formatu, dialog konwersji, edytor sekcji `next`, archiwizacja `done` → ARCHIWUM.md, zintegrowany panel AI

### Projekty
- **Przeglądarka zasobów** — drzewo plików CLAUDE.md, hooków, zmiennych środowiskowych z 6 poziomów (globalny → projekty)
- **Historia projektów** — wątki konwersacji, wiadomości, metadane sesji Claude Code
- **Aktywne projekty** — pinowanie, grupowanie, relokacje przeniesionych projektów

### Tools
- **Simulator kosztów** (`Ctrl+6`) — modelowanie zużycia tokenów i kosztów API dla różnych profili pracy
- **Projektant** (`Ctrl+7`) — wizard tworzenia nowych projektów CC z szablonami DPS

### Claude Code (BB modules)
- **COA** — Konsultant (Boris Best)
- **ISO** — Walidator
- **Ingest** — Dodaj do vaultu
- **Wiki** — Przeglądarka bazy wiedzy

---

## Moduł Zadania — szczegóły

Panel `Develop → Zadania` obsługuje pliki PLAN.md w formacie DPS (Dynamic Planning System).

### Format DPS
Pliki PLAN.md z nagłówkiem `<!-- PLAN v2.0 -->` i sekcjami `<!-- SECTION:name -->`. Zawierają: meta, current, next, done, blockers, session\_log.

### Wariant auto-wykrywania

| Sytuacja | Działanie |
|---|---|
| PLAN.md istnieje + jest DPS | Ładuje od razu |
| PLAN.md istnieje, zwykły MD | Dialog konwersji do DPS |
| Brak PLAN.md | Dialog: utwórz nowy / konwertuj / wybierz plik |

### Panel AI (zakładka `✦ AI`)

Tryby generowania zadań przez Claude Code CLI (`cc`):

| Tryb | Opis |
|---|---|
| Generuj zadania | Generuje listę `- [ ]` na podstawie celu i kontekstu planu |
| Do-planowanie | Rozkłada wybrane zadanie na mniejsze kroki |
| Nadinterpretacja | Analizuje plan, wskazuje ryzyka i brakujące zależności |
| PLAN B | Proponuje alternatywne podejście przy blokadzie |

Wynik AI trafia do edytora sekcji `next` przyciskiem **→ Wstaw do Next**. Komunikacja przez `QProcess` (nieblokująca Qt), streaming JSON.

### Integracja z Sesje CC
Przejście do `Develop → Zadania` automatycznie ładuje projekt z aktywnego slotu Sesje CC (jeśli ustawiony).

---

## Uruchomienie

```bash
# Instalacja zależności
pip install -r requirements.txt

# Uruchomienie aplikacji
.venv/Scripts/python.exe main.py

# Testy
.venv/Scripts/python.exe -m pytest tests/ -v
```

## Stack

- **Python 3.13** + type hints, PEP 8
- **PySide6** (Qt6) — GUI, QStackedWidget, QProcess
- **watchdog** — monitorowanie plików sesji CC
- **pywin32** — integracja Windows
- **pytest** — testy jednostkowe

## Skróty klawiszowe

| Skrót | Panel |
|---|---|
| `Ctrl+6` | Simulator |
| `Ctrl+7` | Projektant |
| `Ctrl+8` | Sesje CC |
| `Ctrl+Z` | Zadania |
| `Ctrl+9` | COA — Konsultant |
| `Ctrl+0` | ISO — Walidator |
| `Ctrl+W` | Ingest |
| `Ctrl+Shift+W` | Wiki |
| `F5` | Odśwież wszystko |

## Struktura

```
claude-env-manager/
  main.py                      # entry point, globalny dark stylesheet
  launcher.pyw                 # launcher bez konsoli
  src/
    cc_launcher/               # konfiguracja slotów, stats, session history
    scanner/                   # discovery i indeksowanie zasobów CC
    models/                    # Resource, Project, HistoryEntry, Simulator models
    simulator/                 # silnik symulacji kosztów tokenów
    ui/
      main_window.py           # routing QStackedWidget, menu
      cc_launcher_panel.py     # panel Sesje CC (4 sloty, ProjectSlotWidget)
      zadania_panel.py         # moduł Zadania — DPS, edytor next, panel AI
      projektant_panel.py      # wizard projektów
      simulator/               # UI Simulatora
      ...                      # pozostałe panele
    utils/                     # paths, parsers, aliases, relocations, colors
    watchers/                  # monitorowanie zmian (watchdog, session_watcher)
  zadaniowiec/                 # własny PLAN.md modułu Zadania (DPS)
  tests/                       # testy pytest
  docs/                        # dokumentacja architektoniczna
```

## Dokumentacja

| Dokument | Zawiera |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Struktura katalogów, lista modułów, pliki JSON |
| [`GUI_ARCHITECTURE.md`](GUI_ARCHITECTURE.md) | Layout okna, hierarchia widgetów, skróty klawiszowe |
| [`docs/FEATURES.md`](docs/FEATURES.md) | Hash-dekodowanie projektów, grupy, relokacje, aliasy |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | 6 poziomów zasobów, hierarchia CLAUDE.md, hooki |
| [`docs/SIMULATOR.md`](docs/SIMULATOR.md) | Spec funkcjonalna: profile, sceny, algorytm, cennik |
| [`docs/SIMULATOR_ARCH.md`](docs/SIMULATOR_ARCH.md) | Architektura klas Simulatora, schematy dataclass |

## Podprojekty (izolowane)

| Folder | Projekt | Uwagi |
|---|---|---|
| `BB/` | Boris Best — baza wiedzy CC | Integracja przez COA panel |
| `ccnsr/` | CC Notion Skills Repository | Niezależny pipeline GitHub→Notion |
| `VS_CLAUDE/` | cc-panel — rozszerzenie VS Code | Osobne repo, stack TypeScript |
| `project/` | Projektant CC — szablony projektowe | Moduł CEM lub samodzielny projekt |

Podprojekty mają własne CLAUDE.md i własny kontekst — nie są commitowane do tego repo.

## Wymagania

- Windows 11
- Python 3.13+
- Claude Code CLI (`cc`) zainstalowany i dostępny w PATH
