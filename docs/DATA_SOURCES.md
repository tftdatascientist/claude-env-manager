# Zrodla danych

Aplikacja wykrywa i wyswietla wszystkie ponizsze zasoby. Sciezki dla Windows 11, user `Slawek`.

## Poziom 1: MANAGED (read-only, najwyzszy priorytet)

| Zasob | Sciezka | Format | Edytowalny |
|---|---|---|---|
| Managed settings | `C:\Program Files\ClaudeCode\managed-settings.json` | JSON | NIE (read-only) |
| Managed CLAUDE.md | `C:\Program Files\ClaudeCode\CLAUDE.md` | Markdown | NIE (read-only) |

## Poziom 2: USER (globalne, osobiste)

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

## Poziom 3: PROJECT (per-projekt, wspoldzielone via git)

Dla kazdego wykrytego projektu (katalogu z `.git/`):

| Zasob | Sciezka wzgledna | Format | Dane |
|---|---|---|---|
| CLAUDE.md projektowy | `.\CLAUDE.md` lub `.\.claude\CLAUDE.md` | Markdown | Instrukcje projektowe |
| Settings projektu | `.\.claude\settings.json` | JSON | permissions, hooks, env |
| Reguly projektu | `.\.claude\rules\*.md` | Markdown | Reguly per-sciezka |
| Agenty projektu | `.\.claude\agents\*.md` | Markdown | name, description, scope, model, permissions, autoMemoryEnabled |
| MCP projektu | `.\.mcp.json` | JSON | Serwery MCP per-projekt |
| Podkatalogowe CLAUDE.md | `.\src\CLAUDE.md`, `.\tests\CLAUDE.md` itd. | Markdown | Ladowane on-demand |

## Poziom 4: LOCAL (osobiste per-projekt, nie commitowane)

| Zasob | Sciezka wzgledna | Format |
|---|---|---|
| CLAUDE.local.md | `.\CLAUDE.local.md` | Markdown |
| Settings lokalne projektu | `.\.claude\settings.local.json` | JSON |

## Poziom 5: AUTO-MEMORY (generowane przez Claude)

| Zasob | Sciezka | Format |
|---|---|---|
| Indeks pamieci | `~\.claude\projects\<hash>\memory\MEMORY.md` | Markdown |
| Pliki tematyczne | `~\.claude\projects\<hash>\memory\*.md` | Markdown |
| Pamiec subagentow | `~\.claude\projects\<hash>\agents\<n>\memory\*.md` | Markdown |
| Logi sesji | `~\.claude\projects\<hash>\*.jsonl` | JSONL |

Hash projektu jest oparty o sciezke git repo. Wszystkie worktree wspoldziela pamiec.

## Poziom 6: ZEWNETRZNE (powiazane z Claude)

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

Format w `settings.json`:

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

## Bezpieczenstwo

- **Credentials masking:** `.credentials.json` wyswietlany z zamaskowanymi wartosciami (np. `sk-ant-...****`). Edycja wymaga odblokowania. Helpery w `src/utils/security.py` (`mask_value`, `mask_dict`).
- **Managed = read-only:** Pliki z `C:\Program Files\ClaudeCode\` sa zawsze read-only w edytorze.
- **Backup przed zapisem:** Przed kazda edycja tworz kopie `.bak` pliku. (do implementacji w fazie 2)
- **SSH keys:** Tylko wyswietlanie nazw plikow, NIE tresci kluczy prywatnych.
