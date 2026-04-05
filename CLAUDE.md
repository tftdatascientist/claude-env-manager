# Claude Environment Manager

Desktopowa aplikacja Windows 11 do przegladania i edycji WSZYSTKICH lokalnych zasobow Claude Code i Claude.ai z jednego miejsca.

## Cel

Uzytkownik (Slawek) ma rozproszone pliki konfiguracji, pamieci, regul, skilli, hookow i serwerow MCP w wielu lokalizacjach na dysku. Aplikacja ma je wszystkie wyswietlic w jednym oknie z drzewem nawigacji, edytorem z podswietlaniem skladni i podgladem mergeowanych ustawien.

## Stan implementacji

### ZROBIONE (Faza 1 MVP + rozszerzenia)

- **Scanner** - wykrywanie zasobow na 6 poziomach (managed, user, project, local, auto-memory, external)
- **TreeView** - drzewo zasobow z kategoriami (bold) i zasobami (klikalne)
- **Editor** - QPlainTextEdit read-only z naglowkiem scope/path
- **History** - przegladarka historii promptow z `~/.claude/history.jsonl`
- **Relocations** - naprawianie przeniesionych/usunietych projektow przez wskazanie nowej lokalizacji
- **Context menu** - prawy klik na projekcie: Open in Explorer / VS Code / Terminal / Copy path
- **Path resolver** - dekodowanie hash-nazw katalogow Claude Code na rzeczywiste sciezki Windows
- **Dark theme** - VS Code style, ciemny motyw
- **Desktop shortcut** - launcher.pyw + create_shortcut.py
- **Testy** - 26 testow pytest (parsers, models, scanner)

### DO ZROBIENIA (Fazy 2-5)

- Faza 2: Edycja plikow (QScintilla, podswietlanie skladni, zapis Ctrl+S, taby, walidacja JSON)
- Faza 3: Wizualny konfigurator hookow i MCP (formularze, drag & drop)
- Faza 4: Merged settings + diff (preview panel, porownanie scope'ow)
- Faza 5: File watching + .exe (watchdog, auto-refresh, PyInstaller)

## Uruchomienie

```bash
# Z konsoli
.venv/Scripts/python.exe main.py

# Testy
.venv/Scripts/python.exe -m pytest tests/ -v

# Skrot na pulpicie (jednorazowo)
.venv/Scripts/python.exe create_shortcut.py
```

## Stack

- **Python 3.13** (.venv w katalogu projektu)
- **PySide6** (Qt6) - UI framework
- **watchdog** - monitorowanie zmian plikow (zainstalowany, uzyty w fazie 5)
- **pytest** - testy
- **pywin32** - tworzenie skrotu na pulpicie

## Struktura projektu

```
claude-env-manager/
  CLAUDE.md                # ten plik - specyfikacja i dokumentacja
  requirements.txt         # PySide6, QScintilla, watchdog, pytest
  main.py                  # entry point (QApplication + dark theme)
  launcher.pyw             # launcher bez konsoli (pythonw.exe)
  create_shortcut.py       # tworzy skrot .lnk na pulpicie
  relocations.json         # mapowanie starych sciezek projektow na nowe (generowany)
  src/
    scanner/
      __init__.py
      discovery.py         # wykrywanie sciezek i plikow na 6 poziomach
      indexer.py           # budowanie TreeNode z wykrytych zasobow
    models/
      __init__.py
      resource.py          # dataclass Resource (path, type, scope, content, read_only, masked)
      project.py           # dataclass Project (name, root_path, resources[], session_count)
      history.py           # dataclass HistoryEntry + load_history() z history.jsonl
    ui/
      __init__.py
      main_window.py       # QMainWindow z QSplitter + QTabWidget (Resources | History)
      tree_panel.py        # QTreeView + QStandardItemModel + context menu
      editor_panel.py      # QPlainTextEdit read-only z naglowkiem
      history_panel.py     # QTreeWidget z grupowaniem Project > Thread > Message
      status_bar.py        # sciezka, scope, typ, timestamp
    watchers/
      __init__.py           # (puste - do fazy 5)
    utils/
      __init__.py
      parsers.py           # read_text, parse_json, extract_frontmatter, detect_file_format
      paths.py             # wszystkie sciezki Claude Code (managed, user, projects, external)
      security.py          # mask_value, mask_dict - maskowanie credentials
      relocations.py       # load/save/remove relokacji przeniesionych projektow
  tests/
    __init__.py
    test_scanner.py        # testy indexer + TreeNode
    test_parsers.py        # testy parsers (JSON, frontmatter, format detection)
    test_models.py         # testy Resource + Project
```

## Kluczowe mechanizmy

### Dekodowanie hash-nazw projektow (discovery.py)

Claude Code koduje sciezki projektow w `~/.claude/projects/` zamieniajac kazdy nie-alfanumeryczny znak (w tym `.`, `_`, `!`, spacje, separatory, znaki non-ASCII) na `-`. Np:

- `C:\Users\Slawek\Documents\.MD\PARA\SER\10_PROJEKTY\SIDE\code-matrix`
- -> `C--Users-S-awek-Documents--MD-PARA-SER-10-PROJEKTY-SIDE-code-matrix`

Resolver w `_walk_resolve()` idzie od katalogu domowego, na kazdym poziomie listuje istniejace katalogi, koduje ich nazwy i porownuje z hashem (greedy longest match). Dziala z:
- Znakami specjalnymi (`!Projekty` -> `-Projekty`)
- Kropkami (`.MD` -> `-MD`)
- Podkresleniami (`10_PROJEKTY` -> `10-PROJEKTY`)
- Znakami non-ASCII (`Slawek` -> `S-awek`)
- Case-insensitive drive letter (`c--` = `C--`)

### Historia (history_panel.py)

Plik `~/.claude/history.jsonl` - kazda linia to JSON:
```json
{"display": "tresc prompta", "timestamp": 1775401252442, "project": "C:\\...", "sessionId": "uuid"}
```

Grupowanie: **Projekt** (pelna sciezka) > **Watek** (sessionId, tytul = pierwszy prompt) > **Wiadomosci** (chronologicznie).

Kolory w drzewie:
- Niebieski (#569cd6) = projekt istnieje na dysku
- Turkusowy (#4ec9b0) = projekt przeniesiony (relokacja)
- Szary (#808080) = projekt nie znaleziony

### Relokacje (relocations.py)

Plik `relocations.json` w katalogu aplikacji. Mapowanie `stara_sciezka -> nowa_sciezka`. Prawy klik na szarym projekcie -> "Relocate project..." -> dialog wyboru katalogu. Relokacje mozna usunac ("Remove relocation").

### Context menu (tree_panel.py, history_panel.py)

Prawy klik na projekcie/zasobie:
- Open in Explorer (`os.startfile`)
- Open in VS Code (`code <path>`)
- Open terminal here (`cmd /k cd /d <path>`)
- Copy path
- Relocate project... (tylko dla brakujacych)
- Remove relocation (tylko dla przeniesionych)

## Zrodla danych - KOMPLETNA LISTA

Aplikacja wykrywa i wyswietla WSZYSTKIE ponizsze zasoby. Sciezki sa dla Windows 11, user `Slawek`.

### Poziom 1: MANAGED (read-only, najwyzszy priorytet)

| Zasob | Sciezka | Format | Edytowalny |
|---|---|---|---|
| Managed settings | `C:\Program Files\ClaudeCode\managed-settings.json` | JSON | NIE (read-only) |
| Managed CLAUDE.md | `C:\Program Files\ClaudeCode\CLAUDE.md` | Markdown | NIE (read-only) |

### Poziom 2: USER (globalne, osobiste)

| Zasob | Sciezka | Format | Dane |
|---|---|---|---|
| Settings globalne | `~\.claude\settings.json` | JSON | permissions, hooks, env, model, autoMemoryEnabled, theme, sandbox |
| Settings lokalne | `~\.claude\settings.local.json` | JSON | Nadpisania (wyzszy priorytet niz settings.json) |
| Credentials | `~\.claude\.credentials.json` | JSON | oauth tokens, api_key, provider - **MASKOWAC** |
| CLAUDE.md osobisty | `~\.claude\CLAUDE.md` | Markdown | Instrukcje ladowane na starcie kazdej sesji |
| MCP serwery | `~\.claude\.mcp.json` | JSON | mcpServers.{nazwa}.type/command/args/env/auth |
| Reguly osobiste | `~\.claude\rules\*.md` | Markdown | Pliki .md z opcjonalnym frontmatter `paths:` |
| Skille | `~\.claude\skills\*\SKILL.md` | Markdown | Frontmatter: title, description, trigger, permissions[], tools[], model |
| Stan globalny | `~\.claude.json` | JSON | theme, userId, lastLogin, mcpServers, keybindings |
| Historia promptow | `~\.claude\history.jsonl` | JSONL | display, timestamp, project, sessionId, pastedContents |

### Poziom 3: PROJECT (per-projekt, wspoldzielone via git)

Dla KAZDEGO wykrytego projektu (katalogu z `.git/`):

| Zasob | Sciezka wzgledna | Format | Dane |
|---|---|---|---|
| CLAUDE.md projektowy | `.\CLAUDE.md` lub `.\.claude\CLAUDE.md` | Markdown | Instrukcje projektowe |
| Settings projektu | `.\.claude\settings.json` | JSON | permissions, hooks, env |
| Reguly projektu | `.\.claude\rules\*.md` | Markdown | Reguly per-sciezka |
| Agenty projektu | `.\.claude\agents\*.md` | Markdown | name, description, scope, model, permissions, autoMemoryEnabled |
| MCP projektu | `.\.mcp.json` | JSON | Serwery MCP per-projekt |
| Podkatalogowe CLAUDE.md | `.\src\CLAUDE.md`, `.\tests\CLAUDE.md` itd. | Markdown | Ladowane on-demand |

### Poziom 4: LOCAL (osobiste per-projekt, nie commitowane)

| Zasob | Sciezka wzgledna | Format |
|---|---|---|
| CLAUDE.local.md | `.\CLAUDE.local.md` | Markdown |
| Settings lokalne projektu | `.\.claude\settings.local.json` | JSON |

### Poziom 5: AUTO-MEMORY (generowane przez Claude)

| Zasob | Sciezka | Format |
|---|---|---|
| Indeks pamieci | `~\.claude\projects\<hash>\memory\MEMORY.md` | Markdown |
| Pliki tematyczne | `~\.claude\projects\<hash>\memory\*.md` | Markdown |
| Pamiec subagentow | `~\.claude\projects\<hash>\agents\<name>\memory\*.md` | Markdown |
| Logi sesji | `~\.claude\projects\<hash>\*.jsonl` | JSONL |

Hash projektu jest oparty o sciezke git repo. Wszystkie worktree wspoldziela pamiec.

### Poziom 6: ZEWNETRZNE (powiazane z Claude)

| Zasob | Sciezka | Format | Dane |
|---|---|---|---|
| Git config | `~\.gitconfig` | INI-like | user.name, user.email, signingkey |
| VS Code settings | `%APPDATA%\Code\User\settings.json` | JSON | Rozszerzenia Claude, keybindings |
| SSH keys | `~\.ssh\` | Rozne | Klucze do podpisywania commitow |
| Zmienne srodowiskowe | System | - | ANTHROPIC_API_KEY, CLAUDE_CONFIG_DIR, CLAUDE_CODE_GIT_BASH_PATH itd. |

## Hierarchia priorytetow ustawien

```
1. Managed policy          (najwyzszy - nie mozna nadpisac)
2. Local project           (.claude/settings.local.json)
3. Project                 (.claude/settings.json)
4. User                    (~/.claude/settings.json)
```

## Hierarchia CLAUDE.md

```
1. Managed CLAUDE.md       (nie mozna wykluczyc)
2. Project CLAUDE.md       (root + przodkowie katalogu)
3. User CLAUDE.md          (~/.claude/CLAUDE.md)
4. Local CLAUDE.md         (CLAUDE.local.md)
   + Podkatalogi           (ladowane on-demand)
```

## Hooki - pelna lista eventow

Aplikacja musi wyswietlac i umozliwiac edycje hookow. Dostepne eventy:

`SessionStart`, `InstructionsLoaded`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`, `Notification`, `Stop`, `ConfigChange`, `CwdChanged`, `FileChanged`, `PreCompact`, `PostCompact`, `SessionEnd`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `WorktreeCreate`, `WorktreeRemove`

Format w settings.json:
```json
{
  "hooks": {
    "EventName": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "sciezka/do/skryptu"
      }]
    }]
  }
}
```

## Layout UI (aktualny)

```
+---------------------------------------------------+
|  Menu: File | View | Help                          |
+----------+----------------------------------------+
|          | [Resources] [History]    <- QTabWidget   |
| TreeView |                                         |
|          | Tab Resources:                          |
| Kategorie|   Header: SCOPE: path [READ-ONLY]      |
| - Managed|   QPlainTextEdit (read-only)            |
| - User   |                                         |
| - Projects| Tab History:                           |
| - External|   [Search: ___] [812/812]              |
|          |   Project > Thread > Message tree       |
| PPM:     |   Detail panel (prompt + metadata)      |
| Explorer |                                         |
| VS Code  |                                         |
| Terminal |                                         |
| Copy path|                                         |
+----------+----------------------------------------+
| Status: sciezka | scope | type | timestamp         |
+---------------------------------------------------+
```

### Skroty klawiszowe

- `F5` - Refresh (zasoby + historia)
- `Ctrl+Q` - Quit
- `Ctrl+1` - Tab Resources
- `Ctrl+2` - Tab History
- `View > Expand All / Collapse All`

## Bezpieczenstwo

- **Credentials masking:** `.credentials.json` wyswietlany z zamaskowanymi wartosciami (np. `sk-ant-...****`). Edycja wymaga odblokowania.
- **Managed = read-only:** Pliki z `C:\Program Files\ClaudeCode\` sa zawsze read-only w edytorze.
- **Backup przed zapisem:** Przed kazda edycja tworz kopie `.bak` pliku. (do implementacji w fazie 2)
- **SSH keys:** Tylko wyswietlanie nazw plikow, NIE tresci kluczy prywatnych.

## Zasady kodowania

- Python 3.12+ z type hints
- PEP 8, max line length 120
- Docstrings tylko dla publicznych klas i metod
- `pathlib.Path` zamiast `os.path`
- Wszystkie sciezki Windows obslugiwane przez `Path.home()` i `Path.expanduser()`
- Brak hardkodowanych sciezek - wszystko przez `paths.py` utility
- Testy pytest dla scanner, parsers, models
- Kazdy modul niezalezny (loose coupling)
- Ciemny motyw (VS Code style) definiowany w `main.py` stylesheet

## Zmienne srodowiskowe Claude Code

Do wyswietlenia w sekcji "External":

| Zmienna | Opis |
|---|---|
| `CLAUDE_CONFIG_DIR` | Nadpisanie katalogu konfiguracji |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Wylacz auto-pamiec |
| `CLAUDE_CODE_GIT_BASH_PATH` | Sciezka do Git Bash |
| `CLAUDE_PROJECT_DIR` | Katalog projektu |
| `CLAUDE_ENV_FILE` | Plik env dla Bash |
| `CLAUDE_CODE_REMOTE` | Flaga sesji zdalnej |
| `ANTHROPIC_API_KEY` | Klucz API - **MASKOWAC** |
| `ANTHROPIC_AUTH_TOKEN` | Token Bearer - **MASKOWAC** |

## Uwagi implementacyjne

- Na Windows `~` to `C:\Users\Slawek` - uzywaj `Path.home()`
- Hash projektu w `~/.claude/projects/<hash>/` - skanuj caly katalog `projects/`, nie probuj odgadywac hashy
- Dekodowanie hashy: `_encode_name()` w discovery.py zamienia nie-alnum (bez `-`) na `-`, potem `_walk_resolve()` porownuje z zawartoscia katalogow
- Pliki `.local.json` i `CLAUDE.local.md` moga nie istniec - to normalne
- `rules/` i `skills/` moga byc puste lub nie istniec
- Frontmatter YAML w plikach .md zaczyna sie od `---` na poczatku pliku
- `@sciezka/do/pliku` w CLAUDE.md to import (do 5 poziomow rekursji) - wyswietl jako link
- Projekty usiniete z dysku (20 z 49) wyswietlane sa na szaro z opcja relokacji
- `relocations.json` przechowuje mapowania starych sciezek na nowe
