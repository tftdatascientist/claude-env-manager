# CCDEVS — Mapa sesji deweloperskich Claude Manager

Dokument synchronizacyjny dla sesji CC pracujących równolegle nad CM.
Każda sesja opisuje swój zakres, zbudowane pliki i otwarte punkty integracji.

---

## Model mentalny CM

```
claude-env-manager/          ← główne repo, aplikacja desktopowa
├── src/ui/                  ← wszystkie panele PySide6
├── src/cc_launcher/         ← backend launcha (config, stats, session)
├── src/projektant/          ← silnik szablonów PCC
├── src/workflow.py          ← round_end / git_push / clean_plan
├── src/watchers/            ← polling transkryptów CC
├── system-start/            ← PCC instance dla własnego dev CM
└── VS_CLAUDE/               ← cc-panel (VS Code extension, osobne repo)

cem_modul_konfiguracji_projektow_claude_code/   ← osobne repo
    = referencyjna implementacja PCC
    = backend: controller, skill, validator, notion_sync, hook_stop
    = WZORZEC dla plików generowanych przez Projektant w CM
```

**Zasada:** CM generuje pliki PCC dla nowych projektów i odpala CC.
Repo PCC dostarcza backend (controller + SKILLe) który działa w tych projektach.
Oba repozytoria są niezależne — CM nie importuje kodu PCC runtime'owo.

---

## Menu CM (aktualne)

```
File | Projekty | Develop | Claude Code | Websites | Web_Dev | Tools | View | Help

Projekty    → Resources (Ctrl+1), Projects (Ctrl+2), All Projects (Ctrl+4),
               Active Projects (Ctrl+3), Hidden (Ctrl+5)
Develop     → Projektant (Ctrl+7), Sesje CC (Ctrl+8)
Claude Code → COA, ISO, Ingest, Wiki (BB modules), CZY
Tools       → Simulator (Ctrl+6), cc-panel, TOST
```

Nawigacja: `QStackedWidget` (brak paska zakładek), strony 0–8+.

---

## Sesja 1 — zakres i zmiany

### Co zbudowałem

**1. Reorganizacja menu i layoutu (`src/ui/main_window.py`)**
- `QTabWidget` → `QStackedWidget` — brak paska zakładek, nawigacja przez menu
- Usunięto `TreePanel` jako stały sidebar — `Resources` to pełnoekranowy `EditorPanel`
- Nowe menu: `Projekty`, `Develop`
- Symulator przeniesiony do `Tools`
- `View` uproszczony (Expand/Collapse/Reset colors)
- Stałe `_PAGE_RESOURCES=0` … `_PAGE_SESJE_CC=7`, BB panele od 8+

**2. Zmiana nazwy CEM → Claude Manager**
- `setWindowTitle("Claude Manager")`, `setApplicationName("Claude Manager")`
- `CLAUDE.md` — tytuł, opis, skróty `CEM` → `CM`
- `editor_panel.py` ekran powitalny, `About` dialog — wersja `v0.2`

**3. Projektant — nowe szablony PCC (`src/projektant/templates/`)**

| Plik | Format | Sekcje kluczowe |
|------|--------|-----------------|
| `CLAUDE.md` | Python-adapted | `project`, `stack`, `key_files` |
| `ARCHITECTURE.md` | PCC | `overview`, `components`, `external_deps`, `constraints`, `data_flow`, `decisions` |
| `PLAN.md` | PCC v2.0 | `meta`, `current`, `next`, `done`, `blockers`, `session_log` |
| `CONVENTIONS.md` | nowy | `naming`, `file_layout`, `code_style`, `commit_style`, `testing`, `anti_patterns` |

`PROJECT_FILES = ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]`
Usunięte: `STATUS.md`, `CHANGELOG.md`

**4. `src/projektant/template_parser.py` — PCC v2.0 API**

Nowe funkcje (zastąpiły stare `plan_check_step` / `plan_set_status`):

```python
plan_write_current(path, task, file, started)
plan_move_to_done(path, timestamp)
plan_append_session_log(path, entry, max_entries=10)
plan_flush(path)        # Done+Current+Next+Blockers → empty, status→idle
plan_validate(path)     # zwraca list[str] błędów, [] = OK
```

**5. Wizard PCC (`src/ui/projektant_wizard.py`) — przepisany**
- Usunięte: `StatusTab`, `ChangelogTab`
- Nowe: `ConventionsTab` z domyślnymi konwencjami Python
- `PlanTab` → PCC v2.0 (`current/next/blockers` zamiast `steps/notes`)
- `ArchitectureTab` + `external_deps`, `constraints`
- `build_overrides()` zsynchronizowany z nowymi sekcjami

**6. AI Project Wizard (`src/ui/ai_project_wizard.py`) — nowy plik**

Fazy: `describe` → `generating` → `review` → `create`

```
_GenWorker(QThread):
  cc --print <_p_meta(opis)>            → sekwencyjnie (metadata)
  ThreadPoolExecutor(3) równolegle:
    cc --print <_p_arch(...)>
    cc --print <_p_conv(...)>
    cc --print <_p_plan(...)>

_FieldWorker(QThread):
  cc --print <_p_regen_field(...)>      → regeneracja pojedynczego pola
```

- Brak API key — używa `cc --print` (`shutil.which("cc")`)
- `CREATE_NO_WINDOW` na Windows — brak migającego okna konsoli
- Po `[✓ Utwórz pliki]` → `write_project_files(dest, title, fields)` → 4 pliki PCC
- Opcja otwarcia w VS Code po utworzeniu

**7. Integracja Projektant → Sesje CC**

```python
# projektant_panel.py
project_ready = Signal(Path)   # emitowany po KAŻDYM nowym projekcie
                               # (nowy projekt / kreator / AI wizard)

# cc_launcher_panel.py
def assign_project(self, path: Path) -> int:
    # wpisuje ścieżkę do pierwszego wolnego slotu (T1–T4)
    # reload_plan + reload_stats + reload_md_files
    # przełącza _slot_tabs na ten slot
    # zwraca numer slotu (1-4)

# main_window.py
self._projektant_panel.project_ready.connect(self._on_project_ready)

def _on_project_ready(self, path):
    slot = self._cc_launcher_panel.assign_project(Path(path))
    self._show_page(self._PAGE_SESJE_CC)
```

### Pliki dotknięte przez Sesję 1

```
src/ui/main_window.py              ← reorganizacja, sygnały, _on_project_ready
src/ui/projektant_panel.py         ← project_ready signal, _open_ai_wizard
src/ui/projektant_wizard.py        ← przepisany pod PCC
src/ui/ai_project_wizard.py        ← NOWY — AI Wizard (cc --print)
src/ui/cc_launcher_panel.py        ← assign_project()
src/projektant/template_parser.py  ← PCC v2.0 API
src/projektant/templates/*.md      ← 4 nowe szablony (CONVENTIONS.md — nowy)
src/ui/editor_panel.py             ← Claude Manager w ekranie powitalnym
main.py                            ← Claude Manager w tytule/nazwie
CLAUDE.md                          ← CEM → CM
GUI_ARCHITECTURE.md                ← QStackedWidget, nowe menu
```

---

## Sesja 3 — zakres i zmiany

Zakres: workflow backend dla sesji CC — od momentu startu sesji do jej zamknięcia.
CM nie importuje kodu PCC runtime'owo — sesja 3 odpowiada za logikę CM-side.

### Co zbudowała

**1. `src/workflow.py` — nowy plik**

Backend operacji na projekcie, uruchamianych z CM UI. Każda funkcja obsługuje
dwa formaty PLAN.md: PCC v2.0 (`<!-- SECTION:name -->`) przez `template_parser`
i legacy (`## Nagłówek`) przez fallback regex.

```python
clean_plan(project_path)    # plan_flush() (PCC v2.0) + fallback regex (## Done/Current)
git_push(project_path, msg) # git add -A + commit + push, obsługuje "nothing to commit"
round_end(project_path)     # clean_plan + plan_append_session_log + git_push

WorkflowRunner(QObject):    # wrapper Qt — każda operacja w osobnym _Worker(QThread)
  run_clean_plan(path)      # nie blokuje UI
  run_git_push(path)
  run_round_end(path)
  operation_done = Signal(name: str, ok: bool, msg: str)
```

Zależności: `src/projektant/template_parser.py` (`plan_flush`, `plan_append_session_log`).
Timeout git push: 30s. Brak blokowania UI — każde wywołanie w QThread.

**2. Zakładka PCC w `ProjectSlotWidget` — nowa zakładka (3. pozycja)**

Read-only dashboard stanu bieżącej rundy. Odświeżana automatycznie przy załadowaniu
projektu, wyborze folderu i po każdym udanym `round_end`.

```
Stan rundy
├── Status:         ● active (zielony) / ◌ idle (szary)
├── Cel:            tekst z meta.goal
├── Sesja:          meta.session
└── Zaktualizowany: meta.updated

Aktywne zadanie
├── Zadanie:        current.task  (Consolas)
├── Plik:           current.file
└── Rozpoczęte:     current.started

Następne           [szare tło, 100px — lista [ ] zadań]
Ukończone          [zielone tło, 130px — lista [x] z datami, odwrócona kolejność]
Session Log        [ciemne tło, 160px — najnowsze na górze]
```

Parsowanie przez `template_parser.read_section()` + `parse_dict()` + `parse_list()`.

**3. Action bar — nowe przyciski**

```
[▶ Start CC ──────────────]  [OKNO]  [↑ Push]  [⟳ Runda]  [KONIEC]
```

- `↑ Push` — `WorkflowRunner.run_git_push()`, nie pyta o potwierdzenie
- `⟳ Runda` — `WorkflowRunner.run_round_end()`, pyta QMessageBox przed wykonaniem
- Oba blokują się na czas operacji (`setEnabled(False)`) — bez możliwości duplikacji

**4. `_on_stop` + `round_end` integracja — dialog 3 opcji**

```python
# CCLauncherPanel._on_stop(slot_id)
[Zakoncz + Runda]   # AcceptRole
[Tylko zakoncz]     # DestructiveRole
[Anuluj]            # RejectRole
```

Ścieżka "Zakończ + Runda":
```
slot.stop_with_round_end()
  → _stop_pending = True
  → WorkflowRunner.run_round_end(path)      # w QThread, nie blokuje UI
  → operation_done → _on_workflow_done()
      → _stop_pending check
      → (błąd: warning, ale i tak terminuje)
      → terminate_vscode_session(slot_id)
      → stop_completed.emit(slot_id)
      → CCLauncherPanel._on_stop_completed()
          → QTimer(1000) → watcher.force_refresh
```

Nowe elementy w `ProjectSlotWidget`:
```python
stop_completed = Signal(int)      # emitowany po zakończeniu sekwencji stop
_stop_pending: bool               # flaga — blokuje QMessageBox po round_end
stop_with_round_end()             # publiczna metoda — round_end → terminate
```

### Pliki dotknięte przez Sesję 3

```
src/workflow.py                ← NOWY
src/ui/cc_launcher_panel.py    ← WorkflowRunner, PCC tab, Push/Runda,
                                  _on_stop dialog, stop_with_round_end,
                                  stop_completed signal, reload_pcc()
```

### Zasady które obowiązują w tym zakresie

- `WorkflowRunner` zawsze w QThread — nigdy synchronicznie w UI thread
- Przyciski blokowane na czas operacji — brak duplikatów wywołań
- `_stop_pending` reset zawsze w `_on_workflow_done` — nawet przy błędzie
- Fallback regex w `clean_plan()` nie rzuca wyjątku — milczy jeśli brak sekcji
- `stop_with_round_end()` terminuje sesję nawet gdy round_end się nie powiódł

---

## Otwarte punkty integracji

---

## Sesja 2 — zakres (repo PCC)

> Pracujesz w: `C:\cc-tools\Projekty_CC\cem_modul_konfiguracji_projektow_claude_code\`
> To jest **osobne repo** — nie dotykasz `claude-env-manager`.
> Twój ewentualny `launcher.py` to duplikat — usuń, launch logika żyje w CM.

### Co zbudowała

**`src/pcc_unpack.py` — nowy plik**

CLI Typer: JSON payload Wizarda → 4 pliki MD projektu.

```bash
python src/pcc_unpack.py payload.json
python src/pcc_unpack.py payload.json --out ./MojProjekt
```

Generuje: `PLAN.md` (z szablonu `templates/plan_template.md`), `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`.
Eksponuje też `unpack_dict(payload, out_dir)` — API do wywołania z kodu (bez CLI).

Format wejściowy JSON: sekcje `project`, `architecture`, `plan`, `conventions` — pełna specyfikacja w `SZABLONREADME.md`.

**`src/skill.py` — dwie poprawki**

1. `pcc_round_end` — usunięty parametr `notion_sync` i cały blok Notion sync.
   Notion nie jest częścią standardowego flow CM. `notion_sync.py` zostaje w repo jako opcjonalny eksport CLI.
   Nowa sygnatura: `pcc_round_end(project_dir=".")` → walidacja + session_log + flush.

2. `pcc_step_done` — naprawiony bug: current task nie trafiał do `done`, a `next[0]` po awansie na current nie był usuwany z `next`.
   Teraz: current → done z timestampem, `next[0]` → nowy current + usunięty z `next`.

**`tests/` — 6 plików, 61 testów, wszystkie zielone**

| Plik | Co testuje | Testów |
|------|-----------|--------|
| `test_controller.py` | Podstawowe API (read/write/flush/protect) | 13 |
| `test_controller_extended.py` | append_rotating, update_plan_meta, validate_plan | 10 |
| `test_decisions.py` | append_decision, pcc_decision, format regex | 10 |
| `test_e2e.py` | Pełny cykl: step_start → step_done → round_end | 10 |
| `test_notion_sync.py` | sync() z MagicMock (nie uderza w live API) | 8 |
| `test_template_parser.py` | plan_template.md + pcc_unpack end-to-end | 10 |

```
61 passed in 2.30s  ✓
```

### Pliki dotknięte przez Sesję 2

```
src/pcc_unpack.py     ← NOWY — CLI typer, JSON → 4 MD
src/skill.py          ← pcc_round_end bez Notion, pcc_step_done naprawiony
tests/conftest.py     ← NOWY — shared fixtures
tests/test_controller.py           ← NOWY
tests/test_controller_extended.py  ← NOWY
tests/test_decisions.py            ← NOWY
tests/test_e2e.py                  ← NOWY
tests/test_notion_sync.py          ← NOWY
tests/test_template_parser.py      ← NOWY
```

### Twój zakres

```
src/controller.py     ← PLAN.md API: read/write/flush/validate sekcji PCC v2.0
src/skill.py          ← 5 SKILLi: pcc_status, step_start, step_done, decision, round_end
src/validator.py      ← walidacja PLAN.md bez modyfikacji (exit 0/1)
src/notion_sync.py    ← push 4 MD → Notion PCC_Projects (notion-client 3.0.0)
src/hook_stop.py      ← handoff do session_log przy Stop CC
src/pcc_unpack.py     ← JSON payload → 4 pliki MD (CLI typer)
tests/                ← cel: 51 testów zielonych
```

### Jak CM korzysta z Twojej pracy

CM NIE importuje Twojego kodu. Integracja przez pliki MD na dysku:
- CM generuje 4 pliki PCC w katalogu projektu (`Projektant` / `AI Wizard`)
- CC w terminalu wczytuje `CLAUDE.md` + `PLAN.md` i używa SKILLi z `src/skill.py`
- CM czyta stan projektu przez `plan_parser.py` i `template_parser.py` (własne parsery)

### Format PLAN.md który musisz obsługiwać

```markdown
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active|idle
- goal: Cel bieżącej rundy
- session: 1
- updated: 2026-04-24 10:00
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: Nazwa zadania
- file: src/example.py
- started: 2026-04-24 10:00
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] Zadanie 1
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- 2026-04-24 10:00 | opis zdarzenia
<!-- /SECTION:session_log -->
```

### Zasady notion-client 3.0.0 (WAŻNE)

```python
# POPRAWNIE:
client.data_sources.query(data_source_id, filter=...)
parent={"type": "data_source_id", "data_source_id": NOTION_PCC_DS}

# BŁĄD — stary API (usunięty w 3.0.0):
client.databases.query(...)
parent={"type": "database_id", ...}
```

### Stan z session_log (system-start/PLAN.md)

```
session:1 | notion_sync.py + PCC_Projects DB — 34/34 testów zielonych
session:1 | append_decision + pcc_decision — 51/51 testów zielonych
2026-04-24 15:51 | step-start: logi Notion, fix PCC_Projects ID, NotionLogHandler, README
```

Backend jest zaawansowany. Uruchom `pytest tests/ -v` i uzupełnij braki.

---

## Pełny workflow end-to-end

```
[CM — Develop → Projektant]
  └── ✨ AI Wizard / Kreator / + Nowy projekt
          ↓
    cc --print × 4  (AI Wizard, równolegle)
    lub create_from_template × 4  (Kreator / Nowy)
          ↓
    dest/
    ├── CLAUDE.md        (PCC v2.0)
    ├── ARCHITECTURE.md  (PCC v2.0)
    ├── PLAN.md          (PCC v2.0)
    └── CONVENTIONS.md   (PCC v2.0)
          ↓
    project_ready.emit(dest)
          ↓
[CM — auto → Develop → Sesje CC]
  assign_project(dest) → pierwszy wolny slot T1–T4
  reload_plan + reload_stats + reload_md_files
          ↓
  Użytkownik konfiguruje w zakładce "Dane":
  ├── Model (claude-sonnet-4-6 / opus / haiku)
  ├── Effort (low / medium / high)
  ├── Uprawnienia (default / bypass / ...)
  ├── Terminale CC (1–4)
  └── Vibe prompt (zakładka "Vibe Code")
          ↓
  [▶ Start CC]
  prepare_and_launch(slot_id, project_path, terminal_count, vibe_prompt)
          ↓
  VS Code otwiera się z projektem
  cc-panel uruchamia N terminali z CC
  CC wczytuje CLAUDE.md + PLAN.md
          ↓
  [praca dewelopera]
  pcc_step_start() / pcc_step_done() / pcc_decision()  ← SKILLe z repo PCC
          ↓
  [⟳ Runda] lub [KONIEC → opcja rundy]
  WorkflowRunner.run_round_end(project_path)
  ├── plan_flush()          (template_parser.py w CM)
  ├── session_log += wpis
  └── git add -A + commit + push
```

---

## Tabela zależności między sesjami

| Zależność | Właściciel | Konsument | Stan |
|-----------|-----------|-----------|------|
| `assign_project()` w CCLauncherPanel | Sesja 1 | Sesja 3 | ✓ gotowe |
| `project_ready` signal | Sesja 1 | main_window | ✓ gotowe |
| `WorkflowRunner` + Push/Runda w action barze | Sesja 3 | — | ✓ gotowe |
| Zakładka PCC (stan rundy, read-only) | Sesja 3 | — | ✓ gotowe |
| `_on_stop` + `round_end` + dialog 3 opcji | Sesja 3 | — | ✓ gotowe |
| PCC backend (controller, skill) | Sesja 2 | projekty użytkownika | ✓ gotowe |
| `pcc_unpack.py` — JSON → 4 MD (CLI) | Sesja 2 | Projektant / AI Wizard | ✓ gotowe |
| `pcc_round_end` bez Notion, `pcc_step_done` fix | Sesja 2 | — | ✓ gotowe |
| 61 testów pytest (backend PCC) | Sesja 2 | CI | ✓ gotowe |
| `hook_stop.py` wired w settings.json CC | Sesja 2 | CM session stop | ⬜ do zrobienia |

---

*Dokument aktualizowany przez każdą sesję po zakończeniu swojego zakresu.*
