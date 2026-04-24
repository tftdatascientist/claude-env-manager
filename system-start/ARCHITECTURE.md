<!-- ARCHITECTURE v1.2 -->

## Overview
<!-- SECTION:overview -->
System zarządza cyklem życia projektu Claude Code poprzez cztery pliki MD (CLAUDE, ARCHITECTURE, PLAN, CONVENTIONS), których integralność chroniona jest deterministycznym skryptem Python. Jedynym plikiem modyfikowanym przez agentów w trakcie sesji jest PLAN.md; pozostałe aktualizowane są po rundzie przez komponent SKILL. Wszystkie pozycje są zsynchronizowane z Notion (baza PCC_Projects) i weryfikowane dwukrotnie na okno kontekstowe.
<!-- /SECTION:overview -->

## Components
<!-- SECTION:components -->
- SKILL Agent: podejmuje decyzje o zmianach w plikach MD i deleguje zapisy do skryptu Python
- Python Controller: deterministyczny skrypt wykonujący zapis/walidację plików MD poza PLAN.md (src/controller.py)
- PLAN.md Runtime: jedyny plik edytowalny w trakcie rundy; czyszczony po jej zakończeniu
- Notion Sync: push 4 plików MD jako podstrony do bazy PCC_Projects po każdej rundzie (src/notion_sync.py)
- Template Engine: generuje szablon.md przed uruchomieniem plan mode (templates/plan_template.md)
- Plan Mode: na podstawie szablonu.md poprawia i zatwierdza strukturę PLAN.md
- Hook Stop: src/hook_stop.py — zapisuje 1-linijkowy handoff do session_log przy zamknięciu sesji CC
- Validator: src/validator.py — waliduje format decisions (3 pola po |) i components (- nazwa: opis)
- Unpacker: src/pcc_unpack.py — JSON z wizarda → 4 pliki MD w katalogu projektu (CLI via typer)
<!-- /SECTION:components -->

## SKILLs
<!-- SECTION:skills -->
- pcc_status: czyta PLAN/current + session_log[-1], zwraca raport gdzie jestem
- pcc_step_start: user mówi co robi, zapisuje do PLAN/current
- pcc_step_done: przenosi current→done z timestampem, pop next[0]→current
- pcc_decision: append-only zapis decyzji do ARCHITECTURE/decisions (jedyna ścieżka w trakcie rundy)
- pcc_round_end: sync Notion → flush PLAN/done+current+next → log handoff
<!-- /SECTION:skills -->

## Data Flow
<!-- SECTION:data_flow -->
User/Agent → PLAN.md → [koniec rundy] → pcc_round_end → Notion Sync → Python Controller → CLAUDE/ARCHITECTURE/CONVENTIONS.md
Agent chce zapisać decyzję → pcc_decision → append_decision() → ARCHITECTURE/decisions (append-only, w trakcie rundy)
<!-- /SECTION:data_flow -->

## External Deps
<!-- SECTION:external_deps -->
- python: 3.13+
- notion-client: 3.0.0
- python-dotenv: dowolna
- typer: 0.12+
- pytest: 8.2+
<!-- /SECTION:external_deps -->

## Decisions
<!-- SECTION:decisions -->
- [x] skrypt Python jako jedyny zapis do MD | 2026-04-24 | eliminuje niespójności przy równoległych agentach
- [x] PLAN.md czyszczony po rundzie nie w trakcie | 2026-04-24 | zachowana ciągłość kontekstu sesji
- [x] Notion jako source of truth dla audytu | 2026-04-24 | umożliwia śledzenie historii zmian poza repo
- [x] subagenci tylko jako fallback | 2026-04-24 | deterministyczny flow jest przewidywalny i testowalny
- [x] notion-client 3.0.0: data_sources.query zamiast databases.query | 2026-04-24 | databases.query usuniete w 3.0.0 — nowe API wymaga data_source_id
- [x] parent rekordu DB: data_source_id zamiast database_id | 2026-04-24 | notion-client 3.0.0 wymaga data_source_id przy tworzeniu stron w kolekcji
- [x] bloki kodu MD: max 1990 znakow na chunk | 2026-04-24 | Notion API odrzuca rich_text powyzej 2000 znakow — chunking w _md_to_blocks()
- [x] append_decision jako jedyny wyjatek zapisu do ARCHITECTURE.md w trakcie rundy | 2026-04-24 | decyzje architektoniczne musza byc rejestrowane na biezaco bez czekania na round-end
- [x] SKILL pcc_decision jako jedyna sciezka agenta do ARCHITECTURE/decisions | 2026-04-24 | separacja odpowiedzialnosci — agent wywoluje SKILL, nie pisze bezposrednio do pliku
<!-- /SECTION:decisions -->

## Constraints
<!-- SECTION:constraints -->
- skrypt Python musi zakończyć się sukcesem przed każdym commitem do plików MD
- Notion sync musi odbyć się dwukrotnie w oknie kontekstowym (start i koniec) — przez pcc_round_end
- plan mode uruchamiany wyłącznie po wygenerowaniu szablonu.md
- decyzje architektoniczne zapisywane wyłącznie przez pcc_decision / append_decision(), nigdy bezpośrednio
- bloki MD w Notion: max 1990 znaków na chunk (limit API 2000)
<!-- /SECTION:constraints -->
