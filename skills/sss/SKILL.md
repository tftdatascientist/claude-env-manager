---
name: sss
description: SSS (Scripted Skills System) v2 — workflow projektu Claude Code w systemie DPS (Dev Python System). Używaj zawsze gdy user inicjuje nowy projekt CC, prosi o "rundę developmentu" / "rundę serwisową" / "zakończenie projektu", chce wystartować od szablonów (CLAUDE.md/PLAN.md/ARCHITECTURE.md/CONVENTIONS.md), wspomina o buforze w PLAN.md, mówi "stwórz mi nowy projekt", "zacznij projekt", "service round", "finalize", "wygeneruj README + repo", używa komend /go /ser /serwis /end. Także gdy Claude Code ma kontynuować pracę nad istniejącym projektem DPS i potrzebuje wiedzieć, w której rundzie jest. Skill orchestruje 3 rundy (Wstępna z 9 pytaniami i panelem 5 sędziów → Development → Serwis) plus opcjonalne Zakończenie, używając deterministycznych skryptów Pythona, slash commands w .claude/commands/, hooków w .claude/hooks/ oraz sub-agentów w .claude/agents/.
allowed-tools: Bash, Read, Write, Edit, Task
---

# SSS v2 — Scripted Skills System dla DPS

Workflow projektu Claude Code oparty na 4 plikach startowych (`CLAUDE.md`, `ARCHITECTURE.md`, `PLAN.md`, `CONVENTIONS.md`), 2 końcowych (`CHANGELOG.md`, `README.md`) oraz pliku oceny intake (`PS.md` — Prompt Score).

Wszystkie operacje rutynowe są **deterministyczne** — robią je skrypty Pythona w `.claude/skills/sss/scripts/`. AI orchestruje workflow, prowadzi wywiad i deleguje sub-agentom.

Po zainicjalizowaniu projektu, w katalogu projektu są dostępne:
- **slash commands**: `/go`, `/ser`, `/serwis`, `/end`
- **hooki**: `buffer_monitor` (PostToolUse na PLAN.md), `prompt_length_check` (UserPromptSubmit)
- **sub-agenci sędziowie**: `judge-business`, `judge-architect`, `judge-pm`, `judge-devops`, `judge-devil`

## Reguły żelazne

- W **Rundzie Developmentu** modyfikujesz **tylko `PLAN.md`**. Każda informacja, która powinna trafić do `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` lub `CHANGELOG.md` — idzie do **bufora** w `PLAN.md` przez `plan_buffer.py add`.
- Sekcje w plikach .md są oznaczone markerami `<!-- SECTION:name -->` ... `<!-- /SECTION:name -->`. Nie ruszaj markerów.
- Klucze i nazwy sekcji są po angielsku w snake_case. Treści wartości — po polsku.
- Skrypty robią pliki — AI nie pisze plików ręcznie poza buforowaniem przez `plan_buffer.py` i wpisywaniem zadań do `next` przez `Edit`.
- **Sub-agentów sędziów wywołujesz przez `Task` tool** — nazwa sub-agenta = nazwa pliku w `.claude/agents/` bez `.md`.

## Komendy slash

Po zainicjalizowaniu projektu user dysponuje 4 komendami:

| Komenda     | Skutek |
|-------------|--------|
| `/go`       | Start/kontynuacja Rundy Developmentu (czyta PLAN.md, bierze zadanie z `next`) |
| `/ser`      | Runda Serwisowa: czyszczenie `done` → CHANGELOG, dystrybucja bufora, wpis do session_log |
| `/serwis`   | Alias dla `/ser` |
| `/end`      | Serwis + README + git push (finalizacja projektu) |

Pliki definicji komend są w `.claude/commands/` w projekcie — kopiowane przez `init_project.py`.

## 3 rundy + zakończenie

### Runda Wstępna (z panelem sędziów i 9 pytaniami)

User opisuje projekt jednym promptem. Twój flow:

#### Krok 1: walidacja długości promptu

Hook `prompt_length_check.py` (jeśli zainstalowany w docelowym katalogu — uwaga, w nowym projekcie jeszcze go nie ma!) podpowiada, ale i tak sprawdź sam:

- Jeśli prompt **≥ 1000 znaków** → idziesz do scoringu kompetencji.
- Jeśli prompt **< 1000 znaków** → **ostrzeż usera**: `"Twój opis ma X znaków. Próg do oceniania przez panel sędziów to 1000. Brakuje Y znaków. Czy chcesz: (a) rozszerzyć opis i dostać ocenę, czy (b) kontynuować bez oceny?"`. Jeśli (a) — czekaj na rozszerzony prompt. Jeśli (b) — pomijasz score_competence i score_architecture, ale i tak robisz 9 pytań i score_difficulty (te działają niezależnie od długości).

#### Krok 2: zainicjalizuj PS.md i (jeśli prompt ≥1000) odpal panel sędziów na ocenę kompetencji

```bash
echo '{"prompt": "<oryginalny prompt>", "title": "<wstępna nazwa>"}' | \
  python .claude/skills/sss/scripts/score_intake.py --mode init --target .
```

Jeśli prompt ≥ 1000 znaków — wywołaj **5 sędziów RÓWNOLEGLE** przez `Task` tool, każdy w trybie `score_competence`. Każde wywołanie powinno przekazać sędziemu prompt + tryb. Output: 5 osobnych odpowiedzi, każda w formacie:
```
SCORE: <1-10>
COMMENT: <...>
ADVICE: <...>
```

Zbierz odpowiedzi do JSON-a i zapisz:
```bash
echo '[{"judge":"judge-business","score":7,"comment":"...","advice":"..."}, ...5 elementów...]' | \
  python .claude/skills/sss/scripts/score_intake.py --mode write_competence --target .
```

#### Krok 3: Runda 1 pytań (statyczna, prowadzi główny Claude)

Zadaj **dokładnie 3 pytania**, które rozwiążą największe niejasności w prompcie. Standardowo:
1. O klienta i sukces (kto, jak liczy że projekt się udał)
2. O stack i ograniczenia techniczne (z czym musisz się zintegrować, czego unikasz)
3. O zakres i deadline (co musi być na MVP, kiedy)

Każde pytanie = jeden konkret. Po odpowiedziach zapisz rundę:
```bash
echo '{"questions":[{"q":"...","a":"..."},{"q":"...","a":"..."},{"q":"...","a":"..."}]}' | \
  python .claude/skills/sss/scripts/score_intake.py --mode write_round --round 1 --target .
```

#### Krok 4: Runda 2 pytań (5 sędziów proponuje, orchestrator wybiera 3)

Wywołaj **5 sędziów RÓWNOLEGLE** przez `Task` tool, każdy w trybie `propose_questions`. Sędzia widzi: oryginalny prompt + 3 pytania i odpowiedzi z Rundy 1. Każdy zwraca 3 pytania → razem 15 propozycji.

Twoja praca jako orchestratora: z 15 propozycji wybierz **3 finalne**:
- różne wymiary (nie 3 pytania devops, jeśli devops zaproponował świetne)
- nie powtórki z Rundy 1
- najwyższa wartość: na które user prawdopodobnie odpowie konkretem

Dla każdego wybranego pytania zachowaj `source_judge`. Zadaj userowi 3 pytania, zbierz odpowiedzi.

```bash
echo '{"questions":[{"q":"...","source_judge":"judge-architect","a":"..."}, ...], "proposals_log":"15 propozycji: 3xbusiness, 3xarchitect, ..."}' | \
  python .claude/skills/sss/scripts/score_intake.py --mode write_round --round 2 --target .
```

#### Krok 5: Runda 3 pytań (jak Runda 2)

Powtórz proces: 5 sędziów dostaje prompt + Runda 1 + Runda 2, każdy proponuje 3 pytania, ty wybierasz 3 finalne. Pytania mają domknąć wszystko, czego brakuje do zbudowania `intake.json`.

Zapisz przez `--mode write_round --round 3`.

#### Krok 6: Score architektury (panel sędziów) i score difficulty (sam Claude)

Jeśli prompt ≥ 1000 znaków — wywołaj 5 sędziów w trybie `score_architecture`, każdy widzi prompt + wszystkie 9 odpowiedzi.

```bash
echo '[{...5 wyników...}]' | \
  python .claude/skills/sss/scripts/score_intake.py --mode write_architecture --target .
```

Następnie **ty sam** (główny Claude) wystaw ocenę trudności 1-10 z krótkim uzasadnieniem i listą 2-3 głównych ryzyk:
```bash
echo '{"score":6,"reasoning":"...","main_risks":"..."}' | \
  python .claude/skills/sss/scripts/score_intake.py --mode write_difficulty --target .
```

Wygeneruj summary:
```bash
python .claude/skills/sss/scripts/score_intake.py --mode summarize --target .
```

#### Krok 7: Zbuduj intake.json i odpal init_project.py

Na podstawie odpowiedzi z 9 pytań zbuduj `intake.json` (struktura w sekcji "Format intake.json" niżej) i uruchom:

```bash
python .claude/skills/sss/scripts/init_project.py --intake intake.json --target .
```

Skrypt:
- stworzy 4 pliki startowe (CLAUDE/ARCHITECTURE/CONVENTIONS/PLAN)
- zainstaluje `.claude/commands/`, `.claude/hooks/`, `.claude/agents/` (jeśli nie ma — kopiuje z assets)
- **skopiuje `SKILL.md` i `scripts/` do `.claude/skills/sss/`** — projekt staje się samowystarczalny i ścieżki w komendach slash (`.claude/skills/sss/scripts/...`) faktycznie istnieją
- scali `.claude/settings.local.json` z konfiguracją hooków SSS
- bez `--force` przerywa jeśli któryś z plików startowych już istnieje (zapobiega utracie pracy)
- zwróci podsumowanie max 300 znaków

#### Krok 8: pokaż userowi wyniki

Pokaż userowi:
1. Podsumowanie z `init_project.py`
2. **Sekcję `summary` z PS.md** (3 oceny + top 3 advices)
3. Jeśli były skipy (prompt < 1000) — wyraźnie zaznacz że score_competence i score_architecture są puste

Zapytaj o akceptację. Jeśli user nie akceptuje — popraw `intake.json`, uruchom `init_project.py` ponownie.

Po akceptacji jesteś gotowy do `/go` (Runda Developmentu).

### Runda Developmentu — `/go`

Pracujesz nad zadaniami z `PLAN.md` sekcja `next`:

1. Czytasz `PLAN.md`, bierzesz pierwsze nieukończone zadanie z `next`, przenosisz do `current`, robisz robotę.
2. Po skończeniu → przenosisz do `done` (z timestampem), bierzesz kolejne z `next`.
3. **Każdą informację dla innego pliku niż `PLAN.md`** zapisujesz do bufora:
   ```bash
   python .claude/skills/sss/scripts/plan_buffer.py add \
     --target ARCHITECTURE.md \
     --content "Decyzja: użyć httpx zamiast requests bo async"
   ```
   Dozwolone wartości `--target`: `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `CHANGELOG.md`.
4. **Sygnalizacja przepełnienia bufora — dwa źródła**:
   - `plan_buffer.py add` po dodaniu wpisu wypisuje na stdout `[BUFFER_COUNT] N/10`. Przy ≥8 emituje `[SSS-WARN]`, przy ≥10 emituje `[SSS-STOP]`. To **primary signal** — widzisz go natychmiast w wyniku Bash.
   - Hook `buffer_monitor.py` (PostToolUse na `Write|Edit|MultiEdit|Bash`) jest backupem — odpala się też po Edit na PLAN.md (np. ruch zadania next→current) i sprawdza bufor. Reaguj na sygnał z któregokolwiek źródła i odpalaj `/ser`.
5. **Stop conditions** (kontynuacja niedozwolona):
   - sekcja `next` w PLAN.md jest pusta
   - user napisał stop / pauza / czekaj
   - hook zasygnalizował bufor ≥ 10
   - `/context` pokazuje `>= 66%` zajętości

### Runda Serwisowa — `/ser` lub `/serwis`

Wywołujesz **bez pytania o zgodę** — to deterministyczna konserwacja.

```bash
python .claude/skills/sss/scripts/service_round.py --target .
```

Skrypt zrobi:
- przeniesie checked items z `done` (PLAN.md) → `entries` (CHANGELOG.md) z timestampem sesji
- rozdystrybuuje wpisy bufora do plików docelowych wg mapowania (niżej)
- **dopisze wpis do `session_log` w PLAN.md** z podsumowaniem sesji + commit hash (jeśli git działa)
- wyczyści `done` i `buffer` w PLAN.md
- zbumpa `meta.session` (numer sesji +1)
- wypisze raport tekstowy

Pokaż userowi raport ze skryptu **dosłownie**. Po serwisie:
- jeśli `next` pusty + user uznaje projekt za gotowy → `/end`
- jeśli `next` pusty + user mówi że nie gotowy → user opisuje braki, ty tworzysz `- [ ] ...` w `next` przez `Edit`, wracasz do `/go`
- jeśli `next` ma jeszcze zadania → wracasz do `/go`

### Zakończenie — `/end`

```bash
python .claude/skills/sss/scripts/finalize.py --target . --repo-name SLUG
```

Skrypt robi:
1. Pełną Rundę Serwisową
2. Generuje `README.md` na podstawie sekcji z CLAUDE/ARCHITECTURE/CHANGELOG
3. `git init` jeśli brak, commit "feat: finalize project"
4. Jeśli `gh` dostępny → `gh repo create SLUG --private --source=. --remote=origin --push`
5. Wypisuje raport końcowy

## Format intake.json

```json
{
  "project": {
    "title": "Chatbot Agencji Nieruchomości",
    "type": "chatbot",
    "client": "Agencja XYZ",
    "stack": "Python 3.13, n8n, OpenAI embeddings, WordPress",
    "one_liner": "Chatbot WP z logiką w n8n, embeddings na bazie ofert."
  },
  "claude": {
    "off_limits": "- nie używaj Redis (constraint klienta)",
    "specifics": "- klient B2B, dwutygodniowy sprint"
  },
  "architecture": {
    "overview": "...",
    "components": "- n8n: orchestracja\n- OpenAI: embeddings",
    "data_flow": "user → WP → n8n → OpenAI → response",
    "decisions": "- [x] embeddings zamiast RAG | 2026-04-28 | prostsze",
    "constraints": "- brak Redis"
  },
  "conventions": {
    "naming": "snake_case dla plików",
    "file_layout": "- src/: kod\n- workflows/: n8n",
    "anti_patterns": "- nie hardkoduj kluczy"
  },
  "plan": {
    "goal": "Chatbot odpowiadający na pytania o oferty",
    "current": "Postawić n8n lokalnie",
    "current_file": "docker-compose.yml",
    "next": "- [ ] schema Notion bazy ofert\n- [ ] webhook WP→n8n\n- [ ] embeddings pipeline"
  }
}
```

## Co zrobić w bash gdy nie wiadomo, w której rundzie jesteś

```bash
python .claude/skills/sss/scripts/state.py --target .
```

JSON: `{"phase": "init|dev|service_due|done", "buffer_count": N, "next_open": N, "done_count": N}`. Użyj do wyboru kolejnego kroku **bez pytania usera**.

## Mapowanie bufora na sekcje docelowe

| Target file        | Sekcja docelowa  |
|--------------------|------------------|
| `CLAUDE.md`        | `specifics`      |
| `ARCHITECTURE.md`  | `decisions`      |
| `CONVENTIONS.md`   | `anti_patterns`  |
| `CHANGELOG.md`     | `entries`        |

Format wpisu w buforze: `- TARGET | YYYY-MM-DD HH:MM | treść`. Przy dystrybucji skrypt zachowuje timestamp i treść — odrzuca tylko prefix `TARGET |`.

## Pliki w skillu

```
sss/
├── SKILL.md
├── scripts/
│   ├── parser.py          # regex parsing markerów SECTION (shared lib)
│   ├── init_project.py    # Runda Wstępna: bootstrap 4 plików + instalacja .claude/
│   ├── plan_buffer.py     # add/count wpisów w buforze PLAN.md
│   ├── service_round.py   # Runda Serwisowa: czyszczenie + dystrybucja + session_log
│   ├── finalize.py        # Zakończenie: README + repo
│   ├── state.py           # detekcja aktualnej fazy projektu
│   └── score_intake.py    # zapis ocen z panelu sędziów do PS.md
└── assets/
    ├── templates/
    │   ├── CLAUDE.md
    │   ├── ARCHITECTURE.md
    │   ├── CONVENTIONS.md
    │   ├── PLAN.md
    │   ├── CHANGELOG.md
    │   ├── README.md
    │   └── PS.md          # Prompt Score template
    ├── commands/
    │   ├── go.md
    │   ├── ser.md
    │   ├── serwis.md
    │   └── end.md
    ├── hooks/
    │   ├── buffer_monitor.py
    │   ├── prompt_length_check.py
    │   └── settings.local.json
    └── agents/
        ├── judge-business.md
        ├── judge-architect.md
        ├── judge-pm.md
        ├── judge-devops.md
        └── judge-devil.md
```

## Czego nie robić

- Nie modyfikuj `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `CHANGELOG.md` ręcznie podczas Rundy Developmentu — wszystko przez bufor.
- Nie pisz markerów `<!-- SECTION:... -->` ręcznie. Skrypty same dbają o markery.
- Nie zadawaj userowi pytań które rozwiąże skrypt — sprawdź `state.py` zanim zapytasz "w której jesteśmy rundzie?".
- Nie wymyślaj treści, których user nie podał. Pola w `intake.json` mogą być puste — skrypty obsłużą.
- **Nie pomijaj ostrzeżenia o promptzie < 1000 znaków** — user musi świadomie wybrać czy rozszerzyć czy kontynuować bez oceny.
- **Nie wywołuj sędziów sekwencyjnie** — zawsze równolegle przez 5 osobnych Task calls w jednej turze.
- Nie próbuj zapisywać do PS.md ręcznie — używaj `score_intake.py` z odpowiednim trybem.
