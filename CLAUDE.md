# Claude Environment Manager

Desktopowa aplikacja Windows 11 do przegladania i edycji WSZYSTKICH lokalnych zasobow Claude Code i Claude.ai z jednego miejsca.

## Cel

Uzytkownik (SĹ‚awek) ma rozproszone pliki konfiguracji, pamieci, regul, skilli, hookow i serwerow MCP w wielu lokalizacjach na dysku. Aplikacja ma je wszystkie wyswietlic w jednym oknie z drzewem nawigacji, edytorem z podswietlaniem skladni i podgladem mergeowanych ustawien.

## Stack

- **Python 3.12+**
- **PySide6** (Qt6) - UI framework
- **QScintilla** - edytor kodu z podswietlaniem skladni (Markdown, JSON)
- **watchdog** - monitorowanie zmian plikow (live reload)
- **PyInstaller** - pakowanie do .exe (faza 5)
- **pytest** - testy

## Struktura projektu

```
claude-env-manager/
  CLAUDE.md              # ten plik
  requirements.txt       # PySide6, QScintilla, watchdog, pytest
  main.py                # entry point (QApplication)
  src/
    scanner/
      __init__.py
      discovery.py       # wykrywanie sciezek i plikow
      indexer.py         # budowanie modelu drzewa
    models/
      __init__.py
      resource.py        # dataclass Resource (path, type, scope, content)
      project.py         # dataclass Project (name, root_path, resources[])
    ui/
      __init__.py
      main_window.py     # QMainWindow z layout
      tree_panel.py      # QTreeView + model
      editor_panel.py    # QScintilla editor z tabami
      preview_panel.py   # podglad merged settings / diff
      status_bar.py      # sciezka, status watch, timestamp
    watchers/
      __init__.py
      file_watcher.py    # watchdog FileSystemEventHandler
    utils/
      __init__.py
      parsers.py         # JSON, Markdown, YAML frontmatter
      paths.py           # rozwiazywanie sciezek Windows
      security.py        # maskowanie credentials
  tests/
    test_scanner.py
    test_parsers.py
    test_models.py
```

## Zrodla danych - KOMPLETNA LISTA

Aplikacja musi wykrywac i wyswietlac WSZYSTKIE ponizsze zasoby. Sciezki sa dla Windows 11, user `SĹ‚awek`.

### Poziom 1: MANAGED (read-only, najwyzszy priorytet)

| Zasob | Sciezka | Format | Edytowalny |
|---|---|---|---|
| Managed settings | `C:\Program Files\ClaudeCode\managed-settings.json` | JSON | NIE (read-only) |
| Managed CLAUDE.md | `C:\Program Files\ClaudeCode\CLAUDE.md` | Markdown | NIE (read-only) |

### Poziom 2: USER (globalne, osobiste)

| Zasob | Sciezka | Format | Dane |
|---|---|---|---|
| Settings globalne | `C:\Users\SĹ‚awek\.claude\settings.json` | JSON | permissions, hooks, env, model, autoMemoryEnabled, theme, sandbox |
| Settings lokalne | `C:\Users\SĹ‚awek\.claude\settings.local.json` | JSON | Nadpisania (wyzszy priorytet niz settings.json) |
| Credentials | `C:\Users\SĹ‚awek\.claude\.credentials.json` | JSON | oauth tokens, api_key, provider - **MASKOWAC** |
| CLAUDE.md osobisty | `C:\Users\SĹ‚awek\.claude\CLAUDE.md` | Markdown | Instrukcje ladowane na starcie kazdej sesji |
| MCP serwery | `C:\Users\SĹ‚awek\.claude\.mcp.json` | JSON | mcpServers.{nazwa}.type/command/args/env/auth |
| Reguly osobiste | `C:\Users\SĹ‚awek\.claude\rules\*.md` | Markdown | Pliki .md z opcjonalnym frontmatter `paths:` |
| Skille | `C:\Users\SĹ‚awek\.claude\skills\*\SKILL.md` | Markdown | Frontmatter: title, description, trigger, permissions[], tools[], model |
| Stan globalny | `C:\Users\SĹ‚awek\.claude.json` | JSON | theme, userId, lastLogin, mcpServers, keybindings |

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
| Indeks pamieci | `C:\Users\SĹ‚awek\.claude\projects\<hash>\memory\MEMORY.md` | Markdown |
| Pliki tematyczne | `C:\Users\SĹ‚awek\.claude\projects\<hash>\memory\*.md` | Markdown |
| Pamiec subagentow | `C:\Users\SĹ‚awek\.claude\projects\<hash>\agents\<name>\memory\*.md` | Markdown |

Hash projektu jest oparty o sciezke git repo. Wszystkie worktree wspoldziela pamiec.

### Poziom 6: ZEWNETRZNE (powiazane z Claude)

| Zasob | Sciezka | Format | Dane |
|---|---|---|---|
| Git config | `C:\Users\SĹ‚awek\.gitconfig` | INI-like | user.name, user.email, signingkey |
| VS Code settings | `%APPDATA%\Code\User\settings.json` | JSON | Rozszerzenia Claude, keybindings |
| SSH keys | `C:\Users\SĹ‚awek\.ssh\` | Rozne | Klucze do podpisywania commitow |
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

## Layout UI

```
+---------------------------------------------------+
|  Menu: File | View | Tools | Help                  |
+----------+------------------------+---------------+
|          |                        |               |
| TreeView |   Editor (tabs)        | Preview Panel |
|          |                        | (opcjonalny)  |
| Kategorie|   QScintilla           |               |
| - Settings|  Markdown/JSON        | Merged view   |
| - Memory |   podswietlanie       | Diff view     |
| - Rules  |                        |               |
| - Skills |                        |               |
| - Hooks  |                        |               |
| - MCP    |                        |               |
| - Agents |                        |               |
| - External|                       |               |
|          |                        |               |
+----------+------------------------+---------------+
| Status: sciezka | watch status | ostatnia zmiana  |
+---------------------------------------------------+
```

### TreeView - struktura drzewa

```
Managed (read-only)
  managed-settings.json
  CLAUDE.md
User
  settings.json
  settings.local.json
  CLAUDE.md
  .credentials.json [MASKED]
  .mcp.json
  .claude.json
  Rules/
    rule1.md
    rule2.md
  Skills/
    skill1/SKILL.md
Projects/
  project-name-1/
    CLAUDE.md
    CLAUDE.local.md
    settings.json
    settings.local.json
    .mcp.json
    Rules/
    Agents/
    Memory/
      MEMORY.md
      debugging.md
  project-name-2/
    ...
External
  .gitconfig
  VS Code settings.json
  SSH keys/
  Environment variables
```

## Fazy implementacji

### Faza 1: Scanner + TreeView + odczyt (MVP)

1. `discovery.py` - skanowanie sciezek, wykrywanie plikow
2. `resource.py` - dataclass z polami: path, type (settings/memory/rules/skills/hooks/mcp/agents), scope (managed/user/project/local), content, last_modified
3. `indexer.py` - budowanie drzewa z wykrytych zasobow
4. `main_window.py` - QMainWindow z QSplitter (tree | editor)
5. `tree_panel.py` - QTreeView z QStandardItemModel
6. `editor_panel.py` - QPlainTextEdit (prosty, bez QScintilla) z read-only wyswietlaniem
7. `main.py` - entry point

**Cel:** Uruchomienie okna, zobaczenie drzewa zasobow, klikniecie = podglad tresci.

### Faza 2: Edycja + podswietlanie

1. Zamiana QPlainTextEdit na QScintilla
2. Podswietlanie Markdown i JSON
3. Zapis zmian (Ctrl+S)
4. Taby w edytorze (wiele otwartych plikow)
5. Walidacja JSON przed zapisem

### Faza 3: Wizualny konfigurator hookow i MCP

1. Formularzowy edytor hookow (wybor eventu, matcher, komenda)
2. Formularzowy edytor MCP servers (nazwa, type, command, args, env)
3. Drag & drop priorytety

### Faza 4: Merged settings + diff

1. Preview panel - wynik mergeowania ustawien ze wszystkich scope'ow
2. Diff view - porownanie miedzy scope'ami (np. user vs project)
3. Kolorowanie zrodel (ktore ustawienie z ktorego scope'u)

### Faza 5: File watching + .exe

1. `file_watcher.py` - watchdog observer na wszystkich skanowanych sciezkach
2. Auto-refresh drzewa i edytora przy zmianach zewnetrznych
3. PyInstaller spec + pakowanie do .exe
4. Ikona w tray (opcjonalnie)

## Bezpieczenstwo

- **Credentials masking:** `.credentials.json` wyswietlany z zamaskowanymi wartosciami (np. `sk-ant-...****`). Edycja wymaga odblokowania.
- **Managed = read-only:** Pliki z `C:\Program Files\ClaudeCode\` sa zawsze read-only w edytorze.
- **Backup przed zapisem:** Przed kazda edycja tworz kopie `.bak` pliku.
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

- Na Windows `~` to `C:\Users\SĹ‚awek` - uzywaj `Path.home()`
- Hash projektu w `~/.claude/projects/<hash>/` - skanuj caly katalog `projects/`, nie probuj odgadywac hashy
- Pliki `.local.json` i `CLAUDE.local.md` moga nie istniec - to normalne
- `rules/` i `skills/` moga byc puste lub nie istniec
- Frontmatter YAML w plikach .md zaczyna sie od `---` na poczatku pliku
- `@sciezka/do/pliku` w CLAUDE.md to import (do 5 poziomow rekursji) - wyswietl jako link