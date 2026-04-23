# Features - szczegoly mechanizmow

Dokument referencyjny opisujacy mechanizmy zaimplementowane w aplikacji. Wszystkie sciezki dla Windows 11.

## Dekodowanie hash-nazw projektow (`src/scanner/discovery.py`)

Claude Code koduje sciezki projektow w `~/.claude/projects/` zamieniajac kazdy nie-alfanumeryczny znak (w tym `.`, `_`, `!`, spacje, separatory, znaki non-ASCII) na `-`. Przyklad:

- `C:\Users\Slawek\Documents\.MD\PARA\SER\10_PROJEKTY\SIDE\code-matrix`
- -> `C--Users-S-awek-Documents--MD-PARA-SER-10-PROJEKTY-SIDE-code-matrix`

Resolver `_walk_resolve()` idzie od katalogu domowego, na kazdym poziomie listuje istniejace katalogi, koduje ich nazwy i porownuje z hashem (greedy longest match). Dziala z:

- Znakami specjalnymi (`!Projekty` -> `-Projekty`)
- Kropkami (`.MD` -> `-MD`)
- Podkresleniami (`10_PROJEKTY` -> `10-PROJEKTY`)
- Znakami non-ASCII (`Slawek` -> `S-awek`)
- Case-insensitive drive letter (`c--` = `C--`)

Funkcja pomocnicza `_encode_name()` zamienia nie-alnum (bez `-`) na `-`.

## Historia (`src/ui/history_panel.py`)

Plik `~/.claude/history.jsonl` - kazda linia to JSON:

```json
{"display": "tresc prompta", "timestamp": 1775401252442, "project": "C:\\...", "sessionId": "uuid"}
```

**Grupowanie:** Projekt (pelna sciezka) > Watek (sessionId, tytul = pierwszy prompt) > Wiadomosci (chronologicznie).

**Kolory w drzewie:**
- Zloty (`#e5c07b`) - grupa projektow (na gorze listy)
- Niebieski (`#569cd6`) - projekt istnieje na dysku
- Turkusowy (`#4ec9b0`) - projekt przeniesiony (relokacja)
- Szary (`#808080`) - projekt nie znaleziony
- Zolty (`#dcdcaa`) - nazwy watkow

**Kolumny QTreeWidget:** `[Nazwa | Active | Web | Messages | Time range]`
- Active (kol 1) - checkbox do pinowania w zakladce Active Projects
- Web (kol 2) - checkbox oznaczania jako strona WWW

**Skracanie sciezek w labelach** (`_shorten_path()`):
- `\SER\...` -> ukrywa prefix do `SER` wlacznie
- `\Documents\...` -> ukrywa prefix do `Documents` wlacznie
- Pelna sciezka w tooltipie

**Multi-select:** `ExtendedSelection` - Ctrl+klik zaznacza wiele projektow do grupowania.

## Grupy projektow (`src/utils/project_groups.py`)

Plik `project_groups.json` - lista grup `[{main: path, members: [paths]}]`.

- Tworzenie: zaznacz 2+ projektow (Ctrl+klik) -> PPM -> "Group selected..." -> dialog wyboru glownego
- Wyswietlanie: na gorze listy History w kolorze zlotym `#e5c07b`
- Struktura w drzewie: `▸ main-project (N projects)` > `★ main` + pozostali > watki
- PPM na grupie: Ungroup
- PPM na czlonku: Remove from group, Set as group main

## Ukrywanie projektow (`src/utils/hidden_projects.py`)

Plik `hidden_projects.json` - lista ukrytych sciezek.

- PPM na projekcie w History -> "Hide" -> projekt znika z History
- Zakladka Hidden -> lista ukrytych -> PPM -> "Unhide" -> wraca do History

## Relokacje (`src/utils/relocations.py`)

Plik `relocations.json` - mapowanie `stara_sciezka -> nowa_sciezka`.

- PPM na szarym (brakujacym) projekcie -> "Relocate project..." -> dialog wyboru katalogu
- Po relokacji projekt zmienia kolor na turkusowy
- Mozna usunac przez "Remove relocation"

## Aliasy nazw (`src/utils/aliases.py`)

Plik `aliases.json` - mapowanie `{sciezka: nazwa_wyswietlana}`.

- PPM -> "Rename..." na projekcie w History lub TreeView
- "Remove alias" przywraca oryginalna nazwe folderu

## Context menu

### `tree_panel.py` (PPM na projekcie/zasobie)
- Open in Explorer (`os.startfile`)
- Open in VS Code (`code <path>`, shell=True)
- Open terminal here (`cmd /k cd /d <path>`)
- Copy path
- Rename... / Remove alias

### `history_panel.py` - single select
- Open in Explorer / VS Code / Terminal
- Relocate project... (tylko dla brakujacych)
- Remove relocation (tylko dla przeniesionych)
- Copy path / Copy original path
- Rename... / Remove alias
- Remove from group / Set as group main (jesli w grupie)
- Hide

### `history_panel.py` - multi-select (2+ projektow)
- Group selected (N projects)...

### `history_panel.py` - PPM na grupie (zloty `▸` node)
- Ungroup

## Uwagi implementacyjne

- Na Windows `~` to `C:\Users\Slawek` - uzywaj `Path.home()`
- Hash projektu w `~/.claude/projects/<hash>/` - skanuj caly katalog `projects/`, nie probuj odgadywac hashy
- Pliki `.local.json` i `CLAUDE.local.md` moga nie istniec - to normalne
- `rules/` i `skills/` moga byc puste lub nie istniec
- Frontmatter YAML w plikach .md zaczyna sie od `---` na poczatku pliku
- `@sciezka/do/pliku` w CLAUDE.md to import (do 5 poziomow rekursji) - wyswietl jako link
- Projekty usuniete z dysku (~20 z 49) wyswietlane sa na szaro z opcja relokacji
- `subprocess.Popen(["code", ...], shell=True)` - wymagane na Windows zeby znalezc `code.cmd`
