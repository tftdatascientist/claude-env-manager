## Next
## Done
- [x] Dodaj zakładkę `CleanClearPanel` do głównego okna CM (PySide6, `QWidget` z layout pionowym)
- [x] Zaimplementuj skaner plików MD projektu: standardowe (`CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `PLAN.md`, `CHANGELOG.md`, `README.md`) + możliwość ręcznego zaznaczenia plików niestandardowych z listy wszystkich `.md` w folderze
- [x] Zaimplementuj parser linii każdego pliku MD — podziel na linie z metadanymi (numer linii, treść, plik źródłowy)
- [x] Zaimplementuj klasyfikator linii: heurystyka oparta na słowach kluczowych, wynik: `ważne` / `zależy` / `nieważne` dla każdej linii
- [x] Wyświetl statystykę klasyfikacji w panelu: tabela per plik z kolumnami `ważne` / `zależy` / `nieważne` (liczba linii każdej kategorii)
- [x] Dodaj UI do wyboru zakresu czyszczenia: checkboxy filtrujące kategorie (`usuń nieważne`, `usuń zależy`, `usuń ważne`)
- [x] Zaimplementuj operację czyszczenia: usuń wybrane linie z plików MD, zapisz oczyszczone wersje (z podglądem diff przed zapisem)
- [x] Zaimplementuj zapis usuniętych linii do `CLEANING.md`: sekcje nagłówkowe per plik źródłowy (`## CLAUDE.md`, `## ARCHITECTURE.md` itd.), linie w kolejności oryginalnej z numerem linii
- [x] Dodaj przycisk `Podgląd` otwierający diff przed i po czyszczeniu (`QDialog` z `QTextEdit` w trybie read-only) — czyszczenie następuje dopiero po potwierdzeniu
- [x] Napisz testy pytest dla: skanera plików, klasyfikatora, generatora `CLEANING.md`

## Next
- [x] Dodaj `SssV3Target = Literal["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]` w `llm_contract.py` i zamień wszystkie użycia `SssV2Target` na `SssV3Target`
- [x] Zaktualizuj stałą `_CLASSIFY_SYSTEM` w `pipeline.py` — dodaj wariant `sss_v2` do listy klasyfikowanych formatów (projekty już skonwertowane do v2 ale nie v3)
- [x] Zaktualizuj `_EXTRACT_SYSTEM` w `pipeline.py` — uwzględnij nowe sekcje PLAN.md v3: `meta`, `goal`, `current`, `next`, `done`, `buffer`, `session_log` (zamiast lub obok poprzednich sekcji v2)
- [x] Rozszerz logikę `_build_extract_prompt` w `pipeline.py` — dodaj informację o docelowych sekcjach v3 per plik (na podstawie szablonów z `~/.claude/skills/sss/assets/templates/`)
- [x] Dodaj `PS.md` do listy plików docelowych w `pipeline.py` (lista `targets`) — v3 wymaga pliku transkrypcji Fazy Plan jako 5. pliku startowego
- [x] Zaktualizuj `validator.py` — sprawdzenie wymaganych plików startowych v3 (dodaj `PS.md`) oraz wymaganych sekcji w `PLAN.md` v3 (`buffer`, `session_log`)
- [x] Zaktualizuj `detector.py` — detekcja `already_sss_v3` na podstawie obecności wszystkich 5 plików + markera `<!-- SECTION:session_log -->` w PLAN.md; istniejący `already_sss_v2` pozostaje jako osobny wariant wymagający konwersji v2→v3
- [x] Zaktualizuj `sss_parser.py` (integration wrapper) — waliduj że ładowany parser pochodzi z `~/.claude/skills/sss/scripts/parser.py` (v3); dodaj `render_template` do `required` API parsera

## Next
- [x] Dodaj logowanie do `_on_launch()` w `cc_launcher_panel.py` — wypisuje `slot_id`, `terminal_count`, timestamp i elapsed od ostatniego launchu
- [x] Sprawdź czy sygnał `launch_requested` nie jest podłączony wielokrotnie — dodano `_signals_connected` guard w `_connect_signals()` z print przy duplikacie
- [x] Dodaj `--new-window` do wywołania `code` w `session_manager.py:prepare_and_launch()` — wymusza nowe okno VS Code zamiast reaktywacji istniejącego
- [x] Zbadano cc-panel `ccPanel.launchSlot` — komenda zarejestrowana w extension.ts:289; pracuje w bieżącym oknie (terminale w dock, nie nowe okno VS Code); wywołana też z setTimeout(1500ms) przy aktywacji
- [x] Timing launch-request.json — OK: plik zapisywany przed `code`, extension czyta z 1500ms opóźnieniem; plik atomowy (usuwany po 1. odczycie)
- [x] Dodano logowanie do pliku `~/.claude/cc-panel/launch-debug.log` w `handleLaunchSlot()` w extension.ts — log: czy plik istnieje, slotId/terminalCount/projectPath, które terminale pominięte/utworzone
- [x] Dodano debounce guard w `_on_launch()` (5s) — blokuje ponowne wywołanie przy double-click lub duplikacie sygnału

## Next
- [x] Utwórz klasę `ExplorerSection` w `src/ui/projektant_panel.py` — `QSplitter(Horizontal)` z drzewkiem plików (`QTreeView` + `QFileSystemModel`, 30% szerokości) po lewej i edytorem/podglądem po prawej (70%)
- [x] W `ExplorerSection` podłącz `QFileSystemModel` ustawiając root na katalog bieżącego projektu — wyświetlaj pliki i katalogi bez filtrowania
- [x] W `ExplorerSection` zaimplementuj panel prawostronny jako `QStackedWidget`: dla plików `.md` renderuj podgląd Markdown (`QTextBrowser`), dla plików `.py` wyświetlaj kod z podświetleniem (`QPlainTextEdit` read-only + monospace), dla pozostałych plików wyświetlaj komunikat "Podgląd niedostępny"
- [x] Podłącz kliknięcie węzła w `QTreeView` do przełączania widoku w panelu prawostronnym `ExplorerSection` — otwieraj plik wskazany przez `QFileSystemModel.filePath(index)`
- [x] Utwórz klasę `ReadmeSection` w `src/ui/projektant_panel.py` — `QTextBrowser` (Markdown, read-only) ładujący `README.md` z katalogu projektu; jeśli plik nie istnieje, wyświetlaj komunikat "Brak README.md"
- [x] Utwórz klasę `ChangelogSection` w `src/ui/projektant_panel.py` — analogicznie do `ReadmeSection`, ładuje `CHANGELOG.md` z katalogu projektu
- [x] W `ProjectantPanel` dodaj nowe sekcje do listy plików (`QListWidget` lub odpowiednika) między pozycją ZADANIA a PLAN.md w kolejności: Explorer → README.md → CHANGELOG.md
- [x] W `QStackedWidget` w `ProjectantPanel` dodaj widgety `ExplorerSection`, `ReadmeSection`, `ChangelogSection` i podłącz ich wyświetlanie do odpowiednich pozycji na liście
- [x] Zaimplementuj metodę `set_project(path: Path)` w każdej z trzech nowych klas — odświeża model/zawartość przy zmianie aktywnego projektu w CM
