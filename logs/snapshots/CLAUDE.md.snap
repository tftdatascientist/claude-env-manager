# Claude Manager
Centralna aplikacja desktopowa Windows 11 (PySide6) zarządzająca wszystkimi narzędziami i zasobami Claude Code z jednego miejsca.
## Uruchomienie
```bash
.venv/Scripts/python.exe main.py          # aplikacja
.venv/Scripts/python.exe -m pytest tests/ -v  # testy
## Stack
Python 3.13 · PySide6 (Qt6) · watchdog · pytest · pywin32
## Zasady kodowania
- Python 3.12+ z type hints, PEP 8, max line 120
- `pathlib.Path` wszedzie; sciezki tylko przez `src/utils/paths.py`
- Brak hardkodowanych sciezek, brak zbednych abstrakcji
- Ciemny motyw definiowany globalnie w `main.py`
- Testy pytest dla: scanner, parsers, models, simulator engine
## Podprojekty zagnieżdżone (IZOLOWANE)
Poniższe foldery to **osobne projekty** z własnym CLAUDE.md i własnym kontekstem.
Jeśli sesja CC jest uruchamiana z ich katalogu — kontekst CM NIE dotyczy tamtej pracy.
| Folder | Projekt | Relacja do CM |
| `BB/` | Boris Best — baza wiedzy CC | moduł CM (integracja przez COA panel) |
| `ccnsr/` | CC Notion Skills Repository | niezależny pipeline GitHub→Notion |
| `VS_CLAUDE/` | cc-panel — rozszerzenie VS Code | niezależne repo, własny stack TS |
| `project/` | Projektant CC — szablony projektowe | moduł CM LUB samodzielny projekt |
| `planist/` | PLAN.md - Moduł do obsługi | moduł CM LUB samodzielny projekt |
**Zasada:** Nie czytaj CLAUDE.md podprojektu jeśli pracujesz nad CM i odwrotnie.
## Dokumentacja — gdzie szukac
| Dokument | Zawiera |
| `docs/ARCHITECTURE.md` | Struktura katalogow, lista modułów, pliki JSON, architektura Simulatora |
| `GUI_ARCHITECTURE.md` | Layout okna, hierarchia widgetow, skroty klawiszowe, stylesheet |
| `docs/FEATURES.md` | Hash-dekodowanie projektow, grupy, relokacje, aliasy, context menu |
| `docs/DATA_SOURCES.md` | 6 poziomow zasobow, hierarchia CLAUDE.md, hooki, zmienne srod. |
| `docs/SIMULATOR.md` | Spec funkcjonalna: profile, sceny, aktywnosci, algorytm, cennik |
| `docs/SIMULATOR_ARCH.md` | Architektura klas, schematy dataclass, format JSON, testy |