# PCC — Project Cycle Controller

System zarządzania cyklem pracy w projektach Claude Code. Chroni integralność czterech plików MD przez deterministyczny kontroler Python, synchronizuje stan z Notion po każdej rundzie i eksponuje pięć SKILLi do manipulacji PLAN.md.

---

## Spis treści

1. [Koncepcja](#koncepcja)
2. [Struktura projektu](#struktura-projektu)
3. [Cykl rundy](#cykl-rundy)
4. [Pliki MD — format i reguły](#pliki-md--format-i-reguły)
5. [Moduły Python](#moduły-python)
6. [SKILLe](#skille)
7. [Notion — baza PCC_Projects](#notion--baza-pcc_projects)
8. [Konfiguracja (.env)](#konfiguracja-env)
9. [Uruchomienie i testy](#uruchomienie-i-testy)
10. [Wizard i pcc_unpack](#wizard-i-pcc_unpack)
11. [Hook Stop](#hook-stop)
12. [Ograniczenia i anti-patterns](#ograniczenia-i-anti-patterns)

---

## Koncepcja

Projekt operuje na czterech plikach MD pełniących rolę "pamięci projektu":

| Plik | Rola |
|------|------|
| `CLAUDE.md` | Instrukcje dla agenta, reguły off-limits, meta projektu |
| `ARCHITECTURE.md` | Komponenty, przepływ danych, decyzje, ograniczenia |
| `PLAN.md` | Stan bieżącej rundy: current/next/done/blockers/session_log |
| `CONVENTIONS.md` | Konwencje nazewnictwa, styl kodu, anti-patterns |

**Zasada naczelna:** Agent edytuje tylko `PLAN.md`. Pozostałe trzy pliki są chronione przez kontroler i aktualizowane wyłącznie przez `pcc_round_end` po zakończeniu rundy — z wyjątkiem `ARCHITECTURE/decisions`, gdzie jedyną autoryzowaną ścieżką jest `pcc_decision()`.

---

## Struktura projektu

```
system-start/
├── CLAUDE.md               # instrukcje agenta (tylko do odczytu w rundzie)
├── ARCHITECTURE.md         # architektura projektu (tylko append decisions)
├── PLAN.md                 # jedyny plik edytowalny w rundzie
├── CONVENTIONS.md          # konwencje kodu (tylko do odczytu w rundzie)
├── .env                    # NOTION_TOKEN + ID baz (nie commitować)
├── .env.example            # szablon .env
├── src/
│   ├── controller.py       # Python Controller — API do PLAN.md
│   ├── skill.py            # SKILL Agent — 5 funkcji pcc_*
│   ├── notion_sync.py      # push 4 MD jako podstrony do Notion
│   ├── hook_stop.py        # handoff do session_log przy zamknięciu CC
│   ├── validator.py        # walidacja formatów decisions i components
│   └── pcc_unpack.py       # JSON z wizarda → 4 pliki MD (CLI typer)
├── templates/
│   └── plan_template.md    # szablon PLAN.md z placeholderami {{...}}
└── tests/
    ├── test_controller.py
    ├── test_controller_extended.py
    ├── test_decisions.py
    ├── test_e2e.py
    ├── test_notion_sync.py
    └── test_template_parser.py
```

---

## Cykl rundy

```
Wizard JSON
    │
    ▼
pcc_unpack.py ──► 4 pliki MD wygenerowane w katalogu projektu
    │
    ▼
[start sesji CC]
    │
    ├── pcc_status()         ← raport: current + ostatni log
    │
    ├── pcc_step_start()     ← zapisz co robisz → PLAN/current
    │
    │   [praca agenta — tylko PLAN.md edytowalny]
    │
    ├── pcc_decision()       ← opcjonalnie: zapisz decyzję → ARCHITECTURE/decisions
    │
    ├── pcc_step_done()      ← current → done, pop next[0] → current
    │
    │   [kolejne iteracje step_start / step_done]
    │
    ▼
pcc_round_end()
    ├── validate_plan()      ← sprawdź format PLAN.md
    ├── notion_sync.sync()   ← push 4 MD do Notion (PRZED czyszczeniem)
    └── flush_plan()         ← wyczyść done/current/next/blockers, status→idle
```

Po `pcc_round_end` PLAN.md jest czysty i gotowy na następną rundę.

---

## Pliki MD — format i reguły

### PLAN.md

Używa HTML-komentarzy jako tagów sekcji:

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
- [ ] Zadanie 2
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
- [x] Ukończone zadanie @ 2026-04-24 09:00
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- 2026-04-24 10:00 | opis zdarzenia
<!-- /SECTION:session_log -->
```

Wymagane sekcje: `meta`, `current`, `next`, `done`, `blockers`, `session_log`.
`session_log` ma max 10 wpisów (FIFO, starsze usuwane przez `append_rotating`).

### ARCHITECTURE.md — sekcja Decisions

Format każdej linii (walidowany przez regex):

```
- [x] opis decyzji | YYYY-MM-DD | uzasadnienie
- [ ] planowana decyzja | YYYY-MM-DD | uzasadnienie
```

Jedyna autoryzowana ścieżka zapisu: `pcc_decision()` → `append_decision()` → plik.

### ARCHITECTURE.md — sekcja Components

Format każdej linii:

```
- NazwaKomponentu: opis co robi
```

---

## Moduły Python

### `src/controller.py`

Niskopoziomowe API do PLAN.md. Wszystkie operacje są idempotentne.

| Funkcja | Opis |
|---------|------|
| `read_plan()` | Zwraca `dict[sekcja → treść]` |
| `read_current()` | Parsuje sekcję `current` jako `{task, file, started}` |
| `write_current(task, file, started)` | Nadpisuje sekcję `current` |
| `update_plan_section(section, body)` | Nadpisuje dowolną sekcję |
| `update_plan_meta(status, goal)` | Aktualizuje pola w sekcji `meta` |
| `mark_task_done(task_text)` | Przenosi zadanie z `next` → `done` |
| `flush_plan()` | Czyści done/current/next/blockers, status→idle |
| `append_session_log(entry)` | Dodaje wpis do `session_log` |
| `append_rotating(section, item, max)` | FIFO append z limitem |
| `append_decision(description, reason, done)` | Append-only do ARCHITECTURE/decisions |
| `validate_plan()` | Zwraca listę błędów (pusta = OK) |

**Ochrona plików:** `_write()` rzuca `PermissionError` przy próbie zapisu do `CLAUDE.md`, `ARCHITECTURE.md` lub `CONVENTIONS.md`. Wyjątek: `append_decision()` pisze bezpośrednio z pominięciem `_write()` — jest jedynym autoryzowanym wyjątkiem.

### `src/skill.py`

Warstwa SKILL — wywoływana przez agenta CC. Deleguje do controllera.

### `src/notion_sync.py`

Push 4 plików MD jako podstrony Notion. Szczegóły w sekcji [Notion](#notion--baza-pcc_projects).

### `src/validator.py`

Waliduje format plików MD bez modyfikowania ich.

```bash
python src/validator.py          # waliduj wszystkie MD, exit 1 jeśli błędy
```

### `src/hook_stop.py`

Uruchamiany przez hook CC `Stop`. Zapisuje handoff do `session_log`.

### `src/pcc_unpack.py`

CLI do generowania 4 plików MD z JSON-a. Szczegóły w sekcji [Wizard](#wizard-i-pcc_unpack).

---

## SKILLe

Dostępne w `src/skill.py`. Wywoływane przez agenta CC — nigdy bezpośrednio przez użytkownika (chyba że testowo przez Python).

### `pcc_status()`

```python
from src.skill import pcc_status
print(pcc_status())
```

Zwraca raport: bieżące `current`, liczba zadań w `next`, ostatni wpis `session_log`, `meta.status`.

### `pcc_step_start(task, file="")`

Zapisuje nowe zadanie do `current`. Wywołaj gdy zaczynasz nowe zadanie.

```python
pcc_step_start("Zaimplementować parser MD", "src/parser.py")
```

### `pcc_step_done(timestamp=None)`

Przenosi `current` → `done` z timestampem. Jeśli `next` nie jest puste, pierwszy element staje się nowym `current`.

```python
pcc_step_done()  # timestamp generowany automatycznie
```

### `pcc_decision(description, reason, done=False)`

Jedyna autoryzowana ścieżka zapisu do `ARCHITECTURE/decisions` w trakcie rundy.

```python
pcc_decision(
    description="Użyć data_sources.query zamiast databases.query",
    reason="notion-client 3.0.0 usunął databases.query",
    done=True
)
```

### `pcc_round_end(notion_sync=True)`

Zamknięcie rundy:
1. Waliduje `PLAN.md` — blokuje jeśli błędy
2. Pushuje 4 MD do Notion (przed czyszczeniem)
3. Wywołuje `flush_plan()` — czyści PLAN.md
4. Loguje `round-end` w `session_log`

```python
pcc_round_end()               # z synchronizacją Notion
pcc_round_end(notion_sync=False)  # bez Notion (tryb offline)
```

---

## Notion — baza PCC_Projects

### Identyfikatory (z `.env`)

| Zmienna | Wartość domyślna | Opis |
|---------|-----------------|------|
| `NOTION_TOKEN` | *(wymagany)* | Token integracji Notion |
| `NOTION_PCC_DB` | `f36ea465-e2f3-4be6-8152-e8c0e71ae909` | `data_source_id` bazy PCC_Projects |
| `NOTION_PARENT_PAGE` | `32e94cf5-6a52-8116-99b1-cc84ad68b573` | ID strony-rodzica LAB_CC_System |

### Schemat bazy PCC_Projects

| Właściwość Notion | Typ | Opis |
|-------------------|-----|------|
| `Name` | title | Nazwa projektu (= nazwa katalogu) |
| `Status` | select | Wartość z `meta.status` w PLAN.md (`active` / `idle`) |
| `Goal` | rich_text | Wartość z `meta.goal` w PLAN.md |
| `Session` | number | Numer sesji z `meta.session` w PLAN.md |
| `Sync_Log` | rich_text | Ostatni wpis `session_log` z PLAN.md |
| `Last Updated` | date | Data synca (UTC, tylko data) |
| `CLAUDE_md` | url | Link do podstrony z treścią CLAUDE.md |
| `ARCHITECTURE_md` | url | Link do podstrony z treścią ARCHITECTURE.md |
| `PLAN_md` | url | Link do podstrony z treścią PLAN.md |
| `CONVENTIONS_md` | url | Link do podstrony z treścią CONVENTIONS.md |

### Podstrony MD

Każdy plik MD trafia jako osobna podstrona Notion (dziecko `NOTION_PARENT_PAGE`). Tytuł podstrony: `{nazwa_projektu} / {plik.md}`.

Treść dzielona na bloki kodu `markdown` po max **1990 znaków** (limit API Notion wynosi 2000 znaków na `rich_text`).

### Logika sync (idempotentna)

```
sync() wywołana:
  1. data_sources.query(NOTION_PCC_DS, filter={Name == project_name})
     ├── rekord istnieje → pobierz URL-e istniejących podstron
     │     └── dla każdego MD: usuń stare bloki, dodaj nowe (_update_md_subpage)
     └── rekord nie istnieje → utwórz podstrony (_create_md_subpage)
  2. Zaktualizuj/utwórz rekord w PCC_Projects (pages.update / pages.create)
```

### Ważne: notion-client 3.0.0

- Zamiast `databases.query` → `data_sources.query(data_source_id, filter=...)`
- Przy `pages.create` dla rekordu w bazie: `parent={"type": "data_source_id", "data_source_id": NOTION_PCC_DS}`
- Dla podstron-dzieci strony: `parent={"type": "page_id", "page_id": NOTION_PARENT_PAGE}`
- Właściwość `text` w schemacie bazy przyjmuje w API `rich_text`

---

## Konfiguracja (.env)

```bash
cp .env.example .env
# Uzupełnij NOTION_TOKEN
```

Plik `.env` jest ładowany przez `python-dotenv` automatycznie przy imporcie `notion_sync.py`.

```env
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxx
NOTION_PCC_DB=f36ea465-e2f3-4be6-8152-e8c0e71ae909
NOTION_PARENT_PAGE=32e94cf5-6a52-8116-99b1-cc84ad68b573
```

`NOTION_PCC_DB` i `NOTION_PARENT_PAGE` mają wartości domyślne zakodowane w `notion_sync.py` — można je pominąć w `.env` jeśli baza nie była przenoszona.

---

## Uruchomienie i testy

### Wymagania

```
Python 3.13+
notion-client==3.0.0
python-dotenv
typer>=0.12
pytest>=8.2
```

### Testy (51 testów, wszystkie zielone)

```bash
python -m pytest tests/ -v
```

| Plik testów | Co testuje |
|-------------|------------|
| `test_controller.py` | Podstawowe API controllera (read/write/flush) |
| `test_controller_extended.py` | append_rotating, update_plan_meta, validate_plan |
| `test_decisions.py` | append_decision, pcc_decision, walidacja formatu |
| `test_e2e.py` | Pełny cykl: step_start → step_done → round_end |
| `test_notion_sync.py` | sync() z MagicMock (nie uderza w live API) |
| `test_template_parser.py` | Poprawność pliku templates/plan_template.md |

### Sync Notion z CLI

```bash
python src/notion_sync.py                          # sync katalogu bieżącego
python src/notion_sync.py /ścieżka/do/projektu    # sync konkretnego katalogu
python src/notion_sync.py /ścieżka NazwaProjektu  # z nadpisaną nazwą
```

### Walidacja MD

```bash
python src/validator.py   # exit 0 = OK, exit 1 = błędy
```

---

## Wizard i pcc_unpack

Wizard (zewnętrzne narzędzie) generuje JSON z danymi projektu. `pcc_unpack.py` rozpakuje go do 4 plików MD.

### Format wejściowy JSON

```json
{
  "project": {
    "name": "Nazwa Projektu",
    "type": "web|cli|lib|other",
    "client": "własny|nazwa-klienta",
    "stack": "Python, FastAPI, PostgreSQL"
  },
  "architecture": {
    "overview": "Opis architektury...",
    "components": [
      "NazwaKomponentu: co robi"
    ],
    "decisions": [
      "Opis decyzji | 2026-04-24 | uzasadnienie"
    ],
    "external_deps": ["python: 3.13+", "fastapi: 0.110+"],
    "constraints": ["constraint 1"],
    "data_flow": "User → API → DB"
  },
  "plan": {
    "goal": "Cel sesji 1",
    "session": 1,
    "current_task": "Pierwsze zadanie",
    "tasks": ["Zadanie 2", "Zadanie 3"]
  },
  "conventions": {
    "naming": "snake_case dla plików...",
    "file_layout": "src/ testy/ docs/...",
    "code_style": "PEP8, type hints...",
    "commit_style": "feat/fix/docs...",
    "testing": "pytest z tmp_path...",
    "anti_patterns": ["nie rób X", "nie rób Y"]
  }
}
```

### Użycie

```bash
python src/pcc_unpack.py payload.json              # generuje w bieżącym katalogu
python src/pcc_unpack.py payload.json --out ./MojProjekt
```

Generuje: `CLAUDE.md`, `ARCHITECTURE.md`, `PLAN.md`, `CONVENTIONS.md`.

---

## Hook Stop

Skrypt uruchamiany przez hook `Stop` w Claude Code. Zapisuje handoff do `session_log`.

### Konfiguracja hooka w Claude Code (`settings.json`)

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python C:/Users/Sławek/claude-env-manager/system-start/src/hook_stop.py"
          }
        ]
      }
    ]
  }
}
```

Po każdym zamknięciu sesji CC w `session_log` pojawia się wpis:

```
- 2026-04-24 14:30 | HANDOFF: sesja zamknięta, ostatnie current='Nazwa zadania'
```

---

## Ograniczenia i anti-patterns

### Absolutne zakazy w trakcie rundy

- Nie zapisuj bezpośrednio do `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` — kontroler rzuci `PermissionError`
- Nie uruchamiaj `plan mode` przed wygenerowaniem `templates/plan_template.md`
- Nie pomijaj walidacji Python Controller przed commitem
- Nie synchronizuj Notion ręcznie z pominięciem `notion_sync.py`

### Ograniczenia Notion API

- Max **1990 znaków** na jeden blok `rich_text` w kodzie — `_md_to_blocks()` dzieli automatycznie
- Właściwość `Name` w `pages.create` przy rekordzie DB wymaga `data_source_id` w `parent`, nie `database_id`
- `data_sources.query` zamiast `databases.query` (notion-client 3.0.0)

### Encoding

- Wszystkie pliki MD: UTF-8
- Skrypty Python używają `encoding="utf-8"` jawnie
- Terminale Windows (cp1250): używaj `io.TextIOWrapper(..., encoding='utf-8')` przy ręcznym wywoływaniu SKILLi przez Bash
- W testach `pytest.raises` — dopasowania ASCII; polskie znaki w komunikatach nie są matchowane przez regex w cp1250

### Podstrony Notion — przy aktualizacji

Aktualizacja podstrony usuwa wszystkie istniejące bloki i tworzy nowe (`_update_md_subpage`). Nie ma merge'owania historii wewnątrz podstrony.
