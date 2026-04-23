# Claude Environment Manager - Architektura GUI

Dokument referencyjny opisujacy interfejs graficzny aplikacji. Sluzy jako specyfikacja dla odtworzenia UI lub implementacji nowych funkcji.

## Stack technologiczny

- **Python 3.13** z type hints
- **PySide6** (Qt6) - framework UI
- **Ciemny motyw VS Code** - zdefiniowany globalnie w `main.py` jako stylesheet QApplication

## Struktura okna glownego

```
+-----------------------------------------------------------+
|  Menu: File | View | Help                                  |
+----------------+------------------------------------------+
|                | [Resources][History][Active][Web][Hidden]  |
|   TreePanel    |                                           |
|   (QTreeView)  | Tab Resources: EditorPanel               |
|                |   Header: "SCOPE: path [READ-ONLY]"      |
|   Kategorie:   |   QPlainTextEdit (Consolas 10, read-only) |
|   - Managed    |                                           |
|   - User       | Tab History: HistoryPanel                 |
|   - Projects   |   [Search: ___] [N msg / N thr / N proj] |
|   - External   |   [v]Active [v]Web columns + checkboxes  |
|                |   Groups (gold #e5c07b) na gorze          |
|  PPM:          |   Project > Thread > Msg tree             |
|  Explorer      |   Detail panel (max 180px)                |
|  VS Code       |                                           |
|  Terminal      | Tab Active Projects: ActiveProjectsPanel  |
|  Copy path     |   Lista projektow | Drzewo plikow        |
|  Rename...     |                   | Podglad pliku         |
|  Hide          |                                           |
|  Group         | Tab Websites: WebsiteProjectsPanel        |
|                |   Lista projektow | Placeholder           |
|                |                                           |
|                | Tab Hidden: HiddenProjectsPanel           |
|                |   Lista ukrytych + PPM Unhide             |
+----------------+------------------------------------------+
| Status: sciezka_pliku | scope | type | read-only | data    |
+-----------------------------------------------------------+
```

## Hierarchia widgetow

```
MainWindow (QMainWindow, 1400x800, min 1000x600)
 ├── MenuBar
 │    ├── File: Refresh (F5), Quit (Ctrl+Q)
 │    ├── View: Expand All, Collapse All, Resources (Ctrl+1), History (Ctrl+2),
 │    │         Active Projects (Ctrl+3), Websites (Ctrl+4), Hidden (Ctrl+5), Reset colors
 │    └── Help: About
 ├── QSplitter (Horizontal, proporcje 1:3, rozmiary 300:900)
 │    ├── TreePanel (QWidget)
 │    │    └── QVBoxLayout (margins=0)
 │    │         └── QTreeView (model=QStandardItemModel)
 │    └── QTabWidget (5 zakladek)
 │         ├── Tab 0 "Resources": EditorPanel (QWidget)
 │         │    └── QVBoxLayout (margins=0, spacing=0)
 │         │         ├── QLabel (header - scope + path + read-only badge)
 │         │         └── QPlainTextEdit (read-only, Consolas 10, no wrap)
 │         ├── Tab 1 "History": HistoryPanel (QWidget)
 │         │    └── QVBoxLayout (margins=0)
 │         │         ├── QHBoxLayout (filter bar, margins=4)
 │         │         │    ├── QLabel "Search:"
 │         │         │    ├── QLineEdit (placeholder="Search prompts...")
 │         │         │    └── QLabel (count: "N messages / N threads / N projects")
 │         │         └── QSplitter (Vertical, proporcje 3:1)
 │         │              ├── QTreeWidget (5 kolumn, ExtendedSelection)
 │         │              └── QPlainTextEdit (detail, read-only, Consolas 10, maxHeight=180)
 │         ├── Tab 2 "Active Projects": ActiveProjectsPanel (QWidget)
 │         │    └── QSplitter (Horizontal, 1:3, 250:750)
 │         │         ├── QWidget (left)
 │         │         │    ├── QLabel header "Active Projects"
 │         │         │    └── QListWidget (project list)
 │         │         └── QSplitter (Vertical, 3:1)
 │         │              ├── QTreeView (QFileSystemModel, only Name column)
 │         │              └── QWidget (preview)
 │         │                   ├── QLabel header (file path)
 │         │                   └── QPlainTextEdit (read-only, Consolas 10, no wrap)
 │         ├── Tab 3 "Websites": WebsiteProjectsPanel (QWidget)
 │         │    └── QSplitter (Horizontal, 1:3, 250:750)
 │         │         ├── QWidget (left)
 │         │         │    ├── QLabel header "Website Projects"
 │         │         │    └── QListWidget (project list)
 │         │         └── QLabel (placeholder content area)
 │         └── Tab 4 "Hidden": HiddenProjectsPanel (QWidget)
 │              └── QVBoxLayout (margins=0)
 │                   ├── QLabel header "Hidden projects — right-click to unhide"
 │                   ├── QTreeWidget (3 kolumny: Project, Path, Status)
 │                   └── QLabel (count: "N hidden project(s)")
 └── StatusBar (QStatusBar)
      ├── QLabel _path_label (stretch=1) - sciezka lub "Ready"
      └── QLabel _info_label (permanent) - "scope | type | read-only | data" lub "N resources found"
```

## Paleta kolorow (ciemny motyw VS Code)

### Kolory tla
| Element | Kolor | Uzycie |
|---------|-------|--------|
| `#1e1e1e` | Ciemne tlo | QMainWindow, QPlainTextEdit, QTabWidget pane, QTreeWidget |
| `#252526` | Lekko jasniejsze | QTreeView, QMenu, QComboBox dropdown |
| `#2d2d2d` | Srednie | QTabBar tab nieaktywny, header EditorPanel, headery paneli |
| `#333333` | Jasne | QMenuBar, QHeaderView, QSplitter handle |
| `#3c3c3c` | Najjasniejsze | QLineEdit, QComboBox |

### Kolory tekstu
| Element | Kolor |
|---------|-------|
| `#cccccc` | Domyslny tekst |
| `#d4d4d4` | Tekst w edytorze |
| `#ffffff` | Aktywna zakladka |
| `#969696` | Nieaktywna zakladka |
| `#666666` | Placeholder header |

### Kolory interakcji
| Element | Kolor |
|---------|-------|
| `#094771` | Zaznaczenie (selected) - tree, menu, tab |
| `#2a2d2e` | Hover - tree items |
| `#264f78` | Zaznaczenie tekstu w edytorze |
| `#007acc` | Akcent - focus border, aktywna zakladka dolna linia, status bar tlo |
| `#454545` | Bordery - QLineEdit, QMenu, QComboBox |

### Kolory kategorii w drzewie zasobow (konfigurowalne przez PPM)
| Kategoria | Domyslny kolor | Styl |
|-----------|---------------|------|
| `Managed (read-only)` | `#e06c75` czerwony | bold |
| `User` | `#c678dd` fioletowy | bold |
| `Projects (N)` | `#61afef` niebieski | bold |
| `External` | `#98c379` zielony | bold |
| `Rules/` | `#d19a66` pomaranczowy | bold |
| `Skills/` | `#56b6c2` cyjan | bold |
| `Agents/` | `#e5c07b` zolty | bold |
| `Memory/` | `#c678dd` fioletowy | bold |
| `SSH keys/` | `#98c379` zielony | bold |
| `Environment variables` | `#d19a66` pomaranczowy | bold |

Kolory zapisywane w `colors_config.json`. PPM na kategorii -> "Change color..." / "Reset to default color".

### Kolory w panelu historii
| Element | Kolor | Znaczenie |
|---------|-------|-----------|
| `#e5c07b` zloty | Grupa projektow (na gorze listy) |
| `#569cd6` niebieski | Projekt istnieje na dysku |
| `#4ec9b0` turkusowy | Projekt przeniesiony (relokacja) |
| `#808080` szary | Projekt nie znaleziony / specjalne katalogi |
| `#dcdcaa` zolty | Nazwy watkow (threads) |
| `#cccccc` jasny szary | Pojedyncze wiadomosci |

## Panele - szczegoly implementacji

### TreePanel (`src/ui/tree_panel.py`)

**Widok:** QTreeView + QStandardItemModel z wlasnym modelem danych.

**Role danych (Qt.ItemDataRole.UserRole+):**
- `RESOURCE_ROLE` (UserRole + 1) - obiekt `Resource` przypisany do elementu liscia
- `CATEGORY_LABEL_ROLE` (UserRole + 2) - string etykiety kategorii (dla wezlow-folderow)

**Struktura drzewa:**
```
Root (niewidoczny)
 ├── Managed (read-only)     [bold, #e06c75]
 │    ├── managed-settings.json    [resource leaf]
 │    └── CLAUDE.md                [resource leaf]
 ├── User                    [bold, #c678dd]
 │    ├── settings.json            [resource leaf]
 │    ├── .credentials.json        [resource leaf, masked]
 │    ├── CLAUDE.md                [resource leaf]
 │    ├── .mcp.json                [resource leaf]
 │    ├── Rules/              [bold, #d19a66]
 │    │    └── rule_name.md
 │    ├── Skills/             [bold, #56b6c2]
 │    │    └── skill_name/SKILL.md
 │    └── Memory/             [bold, #c678dd]
 │         └── MEMORY.md
 ├── Projects (49)           [bold, #61afef]
 │    ├── project-name [5s]   [resource=PROJECT_INFO, klikalne]
 │    │    ├── CLAUDE.md
 │    │    ├── settings.json
 │    │    ├── Rules/
 │    │    │    └── ...
 │    │    └── Memory/
 │    │         └── ...
 │    └── ...
 └── External                [bold, #98c379]
      ├── .gitconfig
      ├── VS Code settings.json
      ├── SSH keys/           [bold, #98c379]
      │    ├── SSH: id_rsa        [masked - content hidden]
      │    └── SSH: id_ed25519
      └── Environment variables [bold, #d19a66]
           ├── ANTHROPIC_API_KEY  [masked]
           └── CLAUDE_CONFIG_DIR
```

**Zachowania:**
- Klikniecie na lisc z `Resource` -> emituje `resource_selected(Resource)` -> przelacza na tab Resources + wyswietla zawartosc
- Klikniecie na kategorie (bold) -> nic nie robi (brak resource)
- Start -> `expandAll()` po zaladowaniu drzewa
- Indentation: 20px

**Context menu (PPM):**
- Na kategorii: Change color... / Reset to default color
- Na zasobie z istniejacym katalogiem: Open in Explorer, Open in VS Code, Open terminal here, ---, Copy path
- Na projekcie (ResourceType.PROJECT_INFO): + Rename..., Remove alias (jesli alias istnieje)

### EditorPanel (`src/ui/editor_panel.py`)

**Header (QLabel):**
- Domyslnie: "Select a resource from the tree" (kolor #666)
- Po wyborze: "SCOPE: sciezka/do/pliku [READ-ONLY]" (tlo #2d2d2d, kolor #ccc, font 11px)
- Scope wyswietlany jako UPPERCASE (np. "MANAGED", "USER", "PROJECT")
- Badge `[READ-ONLY]` tylko gdy `resource.read_only == True`

**Edytor (QPlainTextEdit):**
- Font: Consolas, 10pt
- Read-only (faza 1)
- Line wrap: wylaczony (NoWrap)
- Placeholder: "Select a resource from the tree to view its content."

**Logika wyswietlania tresci:**
1. `ENV_VAR` -> wyswietla "NAZWA=wartosc" (maskuje jesli `resource.masked`)
2. `PROJECT_INFO` -> wyswietla `resource.content` (wygenerowane podsumowanie projektu)
3. SSH private keys (masked + display_name startswith "SSH:") -> "[Private key - content hidden for security]"
4. Plik z dysku -> `resource.load_content()`, jesli nie istnieje -> "[File not found or unreadable]"
5. JSON + masked (credentials) -> parsuje JSON, maskuje wartosci przez `mask_dict()`, formatuje z indent=2

### HistoryPanel (`src/ui/history_panel.py`)

**Filter bar (gora):**
- QLabel "Search:" + QLineEdit (placeholder "Search prompts...") + QLabel z licznikami
- Filtrowanie case-insensitive po tresci promptow
- Licznik formatu: "N messages / N threads / N projects"

**QTreeWidget (srodek):**
- 5 kolumn: nazwa (550px), Active (50px), Web (50px), Messages (70px), Time range (200px)
- `alternatingRowColors = True`
- `ExtendedSelection` - Ctrl+klik zaznacza wiele projektow (do grupowania)
- Kolumny Active i Web maja checkboxy na projektach istniejacych na dysku

**Skracanie sciezek (`_shorten_path()`):**
- `\SER\...` -> ucina prefix do `\SER\` wlacznie
- `\Documents\...` -> ucina prefix do `\Documents\` wlacznie
- Pelna sciezka dostepna w tooltipie

**Struktura drzewa z grupami:**
```
▸ main-project  (3 projects)  [gold #e5c07b, bold]  | msg | threads
 ├── ★ main-project  —  skrocona/sciezka  [gold]    | msg | threads
 │    ├── watek (zolty #dcdcaa)                      | N   | zakres
 │    │    └── wiadomosc (#ccc)
 │    └── ...
 ├── sub-project  —  skrocona/sciezka  [gold]        | msg | threads
 │    └── ...
 └── ...
Normalny projekt  —  skrocona/sciezka  [niebieski]   | msg | threads
 ├── watek (zolty)                                    | N   | zakres
 │    └── wiadomosc (#ccc)
 └── ...
```

**Sortowanie:**
- Grupy: zawsze na gorze, od najnowszej aktywnosci
- Niezgrupowane projekty: od najnowszej aktywnosci (malejaco)
- Watki w projekcie: od najnowszego (malejaco)
- Wiadomosci w watku: chronologicznie (rosnaco)
- Ukryte projekty: pomijane (filtrowane w `_apply_filter`)

**Detail panel (dol, QPlainTextEdit, max 180px):**
- Klikniecie na wiadomosc: pelna tresc + metadane (czas, projekt, sesja, pasted contents)
- Klikniecie na watek: lista wszystkich promptow z watku
- Klikniecie na projekt: nazwa, sciezka, relokacja, status + info o grupie (jesli jest)
- Klikniecie na grupe: nazwa glownego, lista czlonkow

**Context menu (PPM):**

Multi-select (2+ projektow zaznaczonych):
- Group selected (N projects)... -> dialog wyboru glownego projektu

Na grupie (zloty `▸` node, data[0]=="group"):
- Ungroup

Single project:
- Open in Explorer / VS Code / Terminal (jesli na dysku)
- Relocate project... (jesli brakujacy)
- Remove relocation (jesli przeniesiony)
- Copy path / Copy original path
- Rename... / Remove alias
- Remove from group / Set as group main (jesli w grupie)
- Hide

**Dane w itemach (UserRole):**
- Grupa: `("group", main_path, [member_paths])`
- Projekt: `("project", original_path, resolved_path, was_relocated)`
- Watek: `("thread", session_id, messages_chrono_list)`
- Wiadomosc: `("message", HistoryEntry)`

**Sygnaly:**
- `active_projects_changed` - checkbox Active zmieniony
- `website_projects_changed` - checkbox Web zmieniony
- `project_hidden` - projekt ukryty

### ActiveProjectsPanel (`src/ui/active_projects_panel.py`)

**Layout:** QSplitter horizontal (1:3, 250:750)
- Lewo: QLabel header + QListWidget z lista aktywnych projektow
- Prawo: QSplitter vertical (3:1)
  - QTreeView z QFileSystemModel (tylko kolumna Name, ukryte Size/Type/Date)
  - QWidget z QLabel header + QPlainTextEdit preview (read-only, Consolas 10, no wrap)

**Kolorowanie specjalnych katalogow:**
Szary (#808080) italic (przez _SpecialDirDelegate) dla:
`node_modules`, `.git`, `__pycache__`, `.venv`, `venv`, `.env`, `dist`, `build`, `.next`, `.cache`, `.tox`, `.egg-info`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`

**Interakcje:**
- Klik na projekt w liscie -> ustawia root QFileSystemModel na ten katalog
- Klik na plik w drzewie -> podglad tresci (limit 1MB)
- Dwuklik na plik -> `os.startfile()` (otwiera w domyslnej aplikacji)
- PPM na pliku/folderze -> Open in Explorer, Open in VS Code, Open terminal here, Copy path

**Odswiezanie:** `refresh()` przeladowuje liste z `active_projects.json`

### WebsiteProjectsPanel (`src/ui/website_projects_panel.py`)

**Layout:** QSplitter horizontal (1:3, 250:750)
- Lewo: QLabel header "Website Projects" + QListWidget
- Prawo: QLabel placeholder (do przyszlej implementacji)

**Odswiezanie:** `refresh()` przeladowuje z `website_projects.json`

### HiddenProjectsPanel (`src/ui/hidden_projects_panel.py`)

**Layout:** QVBoxLayout
- QLabel header "Hidden projects — right-click to unhide"
- QTreeWidget (3 kolumny: Project 300px, Path 500px, Status 100px, bez dekoracji root)
- QLabel count "N hidden project(s)"

**Wyswietlanie:** Kazdy ukryty projekt jako wiersz z:
- Nazwa (bold, niebieski jesli istnieje, szary jesli nie)
- Pelna sciezka (szary)
- Status: Found / Missing / Relocated

**Context menu (PPM):**
- Unhide -> usuwa z hidden_projects.json, emituje `project_unhidden`
- Copy path

**Sygnal:** `project_unhidden` -> odswierza HistoryPanel

### StatusBar (`src/ui/status_bar.py`)

- Tlo: `#007acc` (niebieski VS Code), tekst bialy, font 12px
- Lewa strona (stretch=1): sciezka do pliku lub "Ready" / "Scanning resources..."
- Prawa strona (permanent): "scope | type | read-only | 2025-04-01 10:00" lub "N resources found"

## Modele danych

### Resource (`src/models/resource.py`)
```python
@dataclass
class Resource:
    path: Path                        # sciezka do pliku lub katalogu projektu
    resource_type: ResourceType       # settings, memory, rules, skills, hooks, mcp, agents, claude_md, credentials, external, env_var, project_info, history
    scope: ResourceScope              # managed, user, project, local, auto_memory, external
    display_name: str                 # nazwa wyswietlana w drzewie
    content: str | None = None        # tresc inline (env_var, project_info) lub cache
    last_modified: datetime | None    # z os.stat po load_content()
    read_only: bool = False           # managed + project_info
    masked: bool = False              # credentials, api keys, ssh keys
    children: list[Resource]          # nieuzywane w UI (legacy)
```

### TreeNode (`src/scanner/indexer.py`)
```python
@dataclass
class TreeNode:
    label: str                        # tekst wyswietlany w drzewie
    resource: Resource | None = None  # None = kategoria (folder), Resource = lisc (klikalne)
    children: list[TreeNode]          # potomkowie
    expanded: bool = True             # hint dla UI (nieuzywany - expandAll)
```

### HistoryEntry (`src/models/history.py`)
```python
@dataclass
class HistoryEntry:
    display: str              # pelna tresc prompta
    timestamp: int            # ms od epoch
    project: str              # sciezka do projektu
    session_id: str           # UUID sesji
    pasted_contents: dict     # wklejone pliki {nazwa: tresc}
    # Properties: datetime, project_name, time_str, short_display (120 znakow)
```

### ProjectGroup (`src/utils/project_groups.py`)
```python
@dataclass
class ProjectGroup:
    main: str                 # sciezka glownego projektu
    members: list[str]        # wszystkie sciezki czlonkow (wlacznie z main)
    # Property: all_paths -> set[str]
```

## Sygnaly i przeplywy danych

```
[Start]
  MainWindow.__init__()
    -> _setup_menu()
    -> _setup_ui()
        -> TreePanel(), EditorPanel(), HistoryPanel(),
           ActiveProjectsPanel(), WebsiteProjectsPanel(), HiddenProjectsPanel()
        -> connect: TreePanel.resource_selected -> MainWindow._on_resource_selected
        -> connect: TreePanel.refresh_requested -> MainWindow._scan_resources
        -> connect: HistoryPanel.active_projects_changed -> ActiveProjectsPanel.refresh
        -> connect: HistoryPanel.website_projects_changed -> WebsiteProjectsPanel.refresh
        -> connect: HistoryPanel.project_hidden -> HiddenProjectsPanel.refresh
        -> connect: HiddenProjectsPanel.project_unhidden -> HistoryPanel.refresh
    -> _scan_resources()

[Klikniecie na zasob w drzewie]
  TreePanel._on_item_clicked()
    -> resource_selected.emit(Resource)
    -> MainWindow._on_resource_selected(Resource)
        -> QTabWidget.setCurrentIndex(0)  # przelacz na Resources
        -> EditorPanel.show_resource(Resource)
        -> StatusBar.show_resource_info(Resource)

[Checkbox Active/Web w History]
  HistoryPanel._on_item_changed(item, column)
    -> column 1: add/remove_active_project() -> active_projects_changed.emit()
    -> column 2: add/remove_website_project() -> website_projects_changed.emit()
    -> odpowiedni panel robi refresh()

[Hide w History]
  HistoryPanel._hide_project(path)
    -> add_hidden_project() -> _apply_filter() -> project_hidden.emit()
    -> HiddenProjectsPanel.refresh()

[Unhide w Hidden]
  HiddenProjectsPanel._unhide_project(path)
    -> remove_hidden_project() -> refresh() -> project_unhidden.emit()
    -> HistoryPanel.refresh()

[Grupowanie w History]
  Ctrl+klik na 2+ projektach -> PPM -> "Group selected..."
    -> QInputDialog wybor glownego -> create_group() -> _apply_filter()

[F5 Refresh]
  MainWindow._refresh_all()
    -> _scan_resources() + HistoryPanel.refresh()
    -> ActiveProjectsPanel.refresh() + WebsiteProjectsPanel.refresh()
    -> HiddenProjectsPanel.refresh()
```

## Pliki konfiguracyjne aplikacji (generowane w katalogu projektu)

| Plik | Format | Zawiera |
|------|--------|---------|
| `colors_config.json` | JSON | Nadpisania domyslnych kolorow kategorii `{label: hex}` |
| `aliases.json` | JSON | Aliasy nazw projektow `{path: display_name}` |
| `relocations.json` | JSON | Relokacje przeniesionych projektow `{old_path: new_path}` |
| `active_projects.json` | JSON | Lista pinowanych projektow `[path, ...]` |
| `website_projects.json` | JSON | Lista projektow-stron WWW `[path, ...]` |
| `hidden_projects.json` | JSON | Lista ukrytych projektow `[path, ...]` |
| `project_groups.json` | JSON | Grupy projektow `[{main: path, members: [paths]}, ...]` |

## Konwencje implementacyjne

1. **Margins i spacing:** Panele ustawiaja `contentsMargins(0,0,0,0)` - bez dodatkowych marginesow
2. **Fonty:** Consolas 10pt dla edytorow; systemowy font dla drzew z `setBold(True)` dla kategorii
3. **Separator splitterow:** 2px szerokosc, kolor `#333333`
4. **Proporcje splitterow:** TreePanel:Content = 1:3 (300:900px), History tree:detail = 3:1, Active/Web list:content = 1:3 (250:750)
5. **Tab widget:** Dolna linia aktywnej zakladki = `#007acc` (2px border-bottom)
6. **Context menu:** Uzywa `QMenu`, pozycjonowanie przez `viewport().mapToGlobal(pos)`
7. **Lazy loading:** Tresc plikow ladowana on-demand przy kliknieciu (`resource.load_content()`)
8. **Maskowanie:** Credentials i API keys zawsze zamaskowane w widoku (security.py)
9. **Sortowanie projektow:** Alfabetycznie w drzewie zasobow; w History: grupy na gorze, potem od najnowszej aktywnosci
10. **Tree expand:** Po kazdym `populate()` automatycznie `expandAll()`
11. **VS Code:** `subprocess.Popen(["code", ...], shell=True)` - wymagane na Windows zeby znalezc `code.cmd`
12. **Skracanie sciezek:** `_shorten_path()` ucina prefixy `\SER\` i `\Documents\` w labelach History
13. **Persystencja:** Kazda funkcja (active, websites, hidden, groups, aliases, colors, relocations) ma wlasny plik JSON w katalogu projektu
14. **Specjalne katalogi:** W ActiveProjectsPanel szary italic dla node_modules, .git, __pycache__ itd. (przez _SpecialDirDelegate)
15. **Multi-select:** History uzywa ExtendedSelection, PPM rozroznia multi-select (grupowanie) vs single-select (standardowe opcje)
