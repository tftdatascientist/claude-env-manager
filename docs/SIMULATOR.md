# Token Simulator v2 — Specyfikacja funkcjonalna

Modul CEM symulujący zuzycie tokenow Claude Code dla roznych konfiguracji srodowiska.
Panel PySide6 zintegrowany z glownym oknem CEM.

## Cel

Odpowiedz na pytanie: **ile tokenow i dolarow kosztuje moja konfiguracja CC dla typowego scenariusza pracy?**

Porownanie dwoch profili dla tego samego scenariusza scen.

---

## Profile

### Co to jest profil

Profil = snapshot konfiguracji srodowiska CC wplywajacy na zuzycie tokenow.
Maksymalnie 10 profili. Kazdy ma nazwe i kolor identyfikujacy go w UI.

### Pola profilu (MVP - wartosci wpisywane recznie w tokenach)

| Pole | Typ | Opis |
|------|-----|------|
| `name` | str | Nazwa profilu np. "Power Setup" |
| `model` | enum | claude-opus-4 / claude-sonnet-4 / claude-haiku-4 |
| `system_prompt_tokens` | int | Bazowy system prompt CC |
| `system_tools_tokens` | int | Narzedzia wbudowane CC |
| `skills_tokens` | int | Laczny koszt aktywnych skilli |
| `mcp_tokens` | int | Laczny koszt opisow serwerow MCP |
| `plugins_tokens` | int | Pluginy CC |
| `global_claude_md_lines` | int | Liczba linii globalnego CLAUDE.md |
| `project_claude_md_lines` | int | Liczba linii projektowego CLAUDE.md |
| `memory_tokens` | int | Memory files / MEMORY.md |
| `line_token_ratio` | float | Przelicznik linii → tokeny (domyslnie 10, kalibrowalny) |
| `cache_hit_rate` | float | % historii trafiajacej w cache (domyslnie 0.70) |
| `ctx_limit` | int | Limit okna kontekstu modelu (domyslnie 200000) |
| `autocompact_threshold` | float | % okna przy ktorym odpala autocompact (domyslnie 0.90) |

> **Oznaczenie TODO w UI:** Pola `skills_tokens`, `mcp_tokens`, `plugins_tokens` maja
> byc w przysztosci rozbite na pojedyncze komponenty z indywidualnymi kosztami.
> W MVP wpisujemy sume. Zaznaczyc to w UI ikoną/tooltip "Szczegolowy breakdown — wkrotce".

### Obliczenie static_overhead profilu

```
static_overhead =
    system_prompt_tokens
  + system_tools_tokens
  + skills_tokens
  + mcp_tokens
  + plugins_tokens
  + global_claude_md_lines  * line_token_ratio
  + project_claude_md_lines * line_token_ratio
  + memory_tokens
```

`static_overhead` = liczba tokenow dodawana do KAZDEJ wiadomosci jako kontekst systemowy.

---

## Sceny

### Co to jest scena

Scena = jeden krok rozmowy z CC:
- wiadomosc uzytkownika (w tokenach)
- odpowiedz CC (w tokenach)
- lista aktywnosci CC wykonanych w tej turze

Sceny mozna: tworzyc, edytowac, zapisywac, usuwac, klonowac.
Sceny sa wspoldzielone miedzy scenariuszami (biblioteka scen).

### Aktywnosci CC (pelna lista)

| ID | Nazwa | Input tok | Output tok | Opis |
|----|-------|-----------|------------|------|
| `file_read` | Read file | 800 | 50 | Odczyt pliku ~200 linii |
| `file_read_large` | Read file (large) | 2400 | 50 | Odczyt pliku ~600 linii |
| `file_edit` | Edit file | 300 | 100 | Edycja istniejacego pliku |
| `file_write` | Write file | 200 | 500 | Zapis nowego pliku |
| `file_multi_read` | Multi-file read | 1600 | 50 | Odczyt 2+ plikow naraz |
| `bash_cmd` | Bash command | 150 | 300 | Wykonanie komendy shell |
| `bash_long_output` | Bash (long output) | 150 | 1200 | Komenda z dlugim outputem |
| `grep_glob` | Grep/Glob search | 100 | 200 | Szukanie po plikach |
| `skill_invoke` | Skill invocation | 1500 | 300 | Zaladowanie i uzycie skilla |
| `mcp_call` | MCP tool call | 400 | 600 | Wywolanie narzedzia MCP |
| `web_search` | Web search | 200 | 1500 | Wyszukiwanie w sieci |
| `web_fetch` | Web fetch | 200 | 3000 | Pobranie strony |
| `subagent_launch` | Sub-agent | 500 | 2000 | Uruchomienie subagenta |
| `todo_read` | TodoRead | 50 | 50 | Odczyt listy todo |
| `todo_write` | TodoWrite | 50 | 100 | Zapis listy todo |
| `memory_read` | Memory read | 300 | 50 | Odczyt pliku pamieci |
| `memory_write` | Memory write | 100 | 50 | Zapis do pamieci |
| `context_view` | /context command | 50 | 400 | Podglad okna kontekstu |
| `git_status` | Git status inject | 200 | 50 | Odswiezenie git status |
| `lint_run` | Linter / tests | 150 | 800 | Wynik lintowania / testow |

Kazda aktywnosc ma pole `count` (ile razy wystapila w tej scenie).

---

## Scenariusze

### Co to jest scenariusz

Scenariusz = nazwana, uporzadkowana sekwencja scen.
Scenariusze mozna: tworzyc, edytowac, zapisywac, usuwac.
W MVP: jeden aktywny scenariusz na raz.

### Tryby budowania scenariusza

**Tryb interaktywny (scena po scenie):**
1. Ustaw parametry sceny (tokeny, aktywnosci przez przyciski)
2. Dodaj scene
3. Przejdz do nastepnej lub uruchom symulacje w dowolnym momencie

**Tryb batchowy:**
1. Wstaw N scen (reczne lub klonowanie istniejacych)
2. Uruchom symulacje jednym przyciskiem

---

## Silnik symulacji

### Algorytm (pseudokod)

```python
def simulate(profile, scenario):
    history_tokens = 0
    session_cost = 0.0
    results = []

    # Koszt startu sesji (session_start komponenty - jednorazowe)
    # W MVP: static_overhead juz zawiera wszystko per-message
    # session_start_cost = profile.session_start_tokens * rate.input

    for scene in scenario.scenes:
        # Aktywnosci w tej scenie
        tool_input  = sum(ACTIVITY[a.id].input  * a.count for a in scene.activities)
        tool_output = sum(ACTIVITY[a.id].output * a.count for a in scene.activities)

        # Cache: czesc historii moze byc serwowana z cache
        cached_history   = int(history_tokens * profile.cache_hit_rate)
        uncached_history = history_tokens - cached_history

        # Tokeny wejscia dla tej wiadomosci
        input_tokens  = (profile.static_overhead
                        + scene.user_message_tokens
                        + uncached_history
                        + tool_input)
        cached_tokens = cached_history
        output_tokens = scene.assistant_response_tokens + tool_output

        # Calkowity kontekst po tej turze
        total_ctx = (profile.static_overhead
                    + history_tokens
                    + input_tokens + output_tokens)

        # Autocompact: jesli przekroczono prog, historia jest resetowana
        if total_ctx > profile.ctx_limit * profile.autocompact_threshold:
            history_tokens = 33000  # bufor po compakcie (ze screena: ~33k tok)
            autocompact_fired = True
        else:
            new_turn_tokens = (scene.user_message_tokens + output_tokens
                               + tool_input + tool_output)
            history_tokens += new_turn_tokens
            autocompact_fired = False

        cost = calc_cost(profile.model, input_tokens, cached_tokens, output_tokens)
        session_cost += cost

        results.append(SceneResult(
            scene=scene,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_ctx=total_ctx,
            history_tokens=history_tokens,
            cost=cost,
            cumulative_cost=session_cost,
            autocompact_fired=autocompact_fired,
        ))

    return SimResult(profile=profile, scenes=results, total_cost=session_cost)
```

### Cennik (per 1M tokenow, stan: kwiecien 2025)

| Model | Input | Output | Cache Read | Cache Creation |
|-------|-------|--------|------------|----------------|
| claude-opus-4 | $15.00 | $75.00 | $1.50 | $18.75 |
| claude-sonnet-4 | $3.00 | $15.00 | $0.30 | $3.75 |
| claude-haiku-4 | $0.80 | $4.00 | $0.08 | $1.00 |

---

## Modul kalibracji (calibrator.py)

### Problem

Wartosci tokenow aktywnosci to oszacowania. Bez kalibracji symulator moze roznic sie od prawdy o 20-50%.

### MVP kalibracji

1. **Import sesji z TOST** — uzytkownik wkleja `session_id` z bazy TOST (SQLite `tost.db`)
2. **Porownanie** — rzeczywiste delty per wiadomosc vs symulowane wartosci
3. **Raport bledu** — MAE (sredni bezwzgledny blad), % odchylenia na koniec sesji
4. **Wyswietlenie** — tabela: scena | symulowane | rzeczywiste | delta%

### Docelowo (Faza 2 kalibracji)

- Automatyczna korekta wspolczynnikow `ACTIVITY_TOKENS` na podstawie bledow
- Zapis skalibrowanych wartosci per profil
- Heatmapa: ktore aktywnosci sa przeszacowane / niedoszacowane

---

## UI — wytyczne implementacyjne

### Styl wizualny

Terminal aesthetic w Qt. Dokladnie nasladzac wyglad `/context` z CC i status bara z dolu ekranu.

**Kolory (dark theme, VS Code style):**
- Tlo: `#1e1e1e`
- Tekst: `#d4d4d4`
- Akcent/naglowek: `#569cd6` (niebieski)
- Wartosc: `#b5cea8` (zielony/jasny)
- Ostrzezenie: `#ce9178` (pomaranczowy)
- Blad / koszt wysoki: `#f44747` (czerwony)
- Font: `Consolas, 'Courier New', monospace`

**Status bar** (dokladnie jak na screenie CCBAR.png):
```
Model: Opus 4.6 | Ctx: 31.0% | Session: 5.0% | Cost: $0.00 | Msgs: 0
```
Aktualizuje sie po kazdej symulowanej scenie.

**Context widget** (dokladnie jak /context na screenie):
```
 Context Usage
 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   [progressbar tokenow]

  Estimated usage by category
  ● System prompt:  6.6k  ( 3.3%)
  ● System tools:   8.4k  ( 4.2%)
  ● Memory files:   6.8k  ( 3.4%)
  ● Skills:          785  ( 0.4%)
  ● Messages:      38.9k  (19.5%)
  □ Free space:   105.5k  (52.7%)
  ⊠ Autocompact:   33.0k  (16.5%)
```
Dwa takie widgety obok siebie (Profil A | Profil B).

### Glowny layout panelu

```
┌─ SIMULATOR ──────────────────────────────────────────────────────┐
│  [Profile A ▼]  [Edytuj]        vs        [Profile B ▼]  [Edytuj]│
├──────────────────────────┬───────────────────────────────────────┤
│   /context widget A      │         /context widget B             │
│   (aktualizuje sie)      │         (aktualizuje sie)             │
├──────────────────────────┴───────────────────────────────────────┤
│ STATUS BAR: Model A | Ctx A% | Cost A$   vs   Model B | Ctx B%  │
├──────────────────────────────────────────────────────────────────┤
│ SCENARIO: [nazwa scenariusza ▼]  [Nowy] [Zapisz] [Usun]         │
├──────────────────────────────────────────────────────────────────┤
│ SCENE BUILDER                                                    │
│  User msg tok: [___]    Response tok: [___]                      │
│  Aktywnosci:                                                     │
│  [Read file] [Edit file] [Bash] [MCP] [Skill] [Web] [Memory]... │
│  Aktywne: read_file x2, bash_cmd x1, mcp_call x1               │
│  [+ Dodaj scene] [Wyczysc]                                       │
├──────────────────────────────────────────────────────────────────┤
│ KOLEJKA SCEN                                                     │
│  #1 Scena "init"    #2 Scena "read+edit"    #3 [...]            │
│  [▲][▼][✕] per scena        [▶ Uruchom symulacje]               │
├──────────────────────────────────────────────────────────────────┤
│ WYNIKI                                                           │
│ Sc│CtxA   │CtxB   │CostA  │CostB  │Delta  │CumA   │CumB       │
│ 1 │ 15.2k │ 10.4k │$0.012 │$0.008 │ -33%  │$0.012 │$0.008    │
│ 2 │ 24.8k │ 16.1k │$0.019 │$0.013 │ -32%  │$0.031 │$0.021    │
└──────────────────────────────────────────────────────────────────┘
```

### Interakcja scene builder

- Kazdy przycisk aktywnosci to toggle: pierwsze klikniecie dodaje (pokazuje x1), kolejne inkrementuje licznik, PPM resetuje do 0
- Po dodaniu sceny: scena laduje do kolejki, builder sie czysci
- Sceny w kolejce mozna przeciagac (drag&drop), edytowac (dwuklik), usuwac (✕)
- Symulacja uruchamia sie przyciskiem lub po kazdym dodaniu sceny (toggleable: "Auto-simulate")

---

## Persystencja danych

Plik: `simulator_data.json` w katalogu projektu CEM.

```json
{
  "profiles": [...],
  "scenes": [...],
  "scenarios": [...],
  "activity_tokens": {...},
  "calibration": {
    "sessions": [],
    "corrections": {}
  }
}
```

Ladowany przy starcie panelu, zapisywany przy kazdej zmianie (debounce 500ms).

---

## Testy (test_simulator_engine.py)

Wymagane przypadki testowe:
- `test_static_overhead_calculation` — poprawne sumowanie tokenow profilu
- `test_scene_cost_no_history` — koszt pierwszej sceny bez historii
- `test_history_accumulation` — sprawdzenie ze historia rosnie poprawnie miedzy scenami
- `test_cache_hit_reduces_cost` — cache_hit_rate > 0 obniza koszt
- `test_autocompact_fires` — przy przekroczeniu progu historia resetuje sie do 33k
- `test_two_profiles_delta` — porownanie dwoch profili daje prawidlowe delty
- `test_calibrator_mae` — MAE liczy sie poprawnie dla znanych wartosci
