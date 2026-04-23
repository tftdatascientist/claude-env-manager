# Claude Environment Manager (CEM)

Desktopowa aplikacja Windows 11 (PySide6) do przeglądania i edycji wszystkich lokalnych zasobów Claude Code i Claude.ai z jednego miejsca.

## Funkcje

- **Przeglądarka zasobów** — drzewo plików CLAUDE.md, hooków, zmiennych środowiskowych z 6 poziomów (globalny → projekty)
- **Historia projektów** — wątki konwersacji, wiadomości, metadane sesji Claude Code
- **Aktywne projekty** — pinowanie, grupowanie, relokacje przeniesionych projektów
- **Aliasy** — własne nazwy dla skrótów hash-owych projektów
- **Simulator kosztów** — modelowanie zużycia tokenów i kosztów API dla różnych profili pracy
- **Integracje BB** — moduły COA, ISO, Ingest, Wiki, CZY (Boris Best knowledge base)

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

- **Python 3.13** + type hints
- **PySide6** (Qt6) — GUI
- **watchdog** — monitorowanie plików
- **pywin32** — integracja Windows
- **pytest** — testy jednostkowe

## Struktura

```
claude-env-manager/
  main.py                    # entry point, globalny dark stylesheet
  launcher.pyw               # launcher bez konsoli
  src/
    scanner/                 # discovery i indexowanie zasobów CC
    models/                  # Resource, Project, HistoryEntry, Simulator models
    simulator/               # silnik symulacji kosztów tokenów
    ui/                      # wszystkie panele PySide6
    utils/                   # paths, parsers, aliases, relocations, colors
    watchers/                # monitorowanie zmian (watchdog)
  tests/                     # testy pytest
  docs/                      # dokumentacja architektoniczna
```

## Dokumentacja

| Dokument | Zawiera |
|----------|---------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Struktura katalogów, lista modułów, pliki JSON |
| [`GUI_ARCHITECTURE.md`](GUI_ARCHITECTURE.md) | Layout okna, hierarchia widgetów, skróty klawiszowe |
| [`docs/FEATURES.md`](docs/FEATURES.md) | Hash-dekodowanie projektów, grupy, relokacje, aliasy |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | 6 poziomów zasobów, hierarchia CLAUDE.md, hooki |
| [`docs/SIMULATOR.md`](docs/SIMULATOR.md) | Spec funkcjonalna: profile, sceny, algorytm, cennik |
| [`docs/SIMULATOR_ARCH.md`](docs/SIMULATOR_ARCH.md) | Architektura klas Simulatora, schematy dataclass |

## Podprojekty (izolowane)

| Folder | Projekt | Uwagi |
|--------|---------|-------|
| `BB/` | Boris Best — baza wiedzy CC | Integracja przez COA panel |
| `ccnsr/` | CC Notion Skills Repository | Niezależny pipeline GitHub→Notion |
| `VS_CLAUDE/` | cc-panel — rozszerzenie VS Code | Osobne repo, stack TypeScript |
| `project/` | Projektant CC — szablony projektowe | Moduł CEM lub samodzielny projekt |

Podprojekty mają własne CLAUDE.md i własny kontekst — nie są commitowane do tego repo.

## Wymagania

- Windows 11
- Python 3.13+
- Claude Code CLI (`cc`) zainstalowany lokalnie
