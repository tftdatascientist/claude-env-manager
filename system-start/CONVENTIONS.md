<!-- CONVENTIONS v1.1 -->

## Naming
<!-- SECTION:naming -->
- files: snake_case.py / kebab-case.md
- classes: PascalCase (np. PlanController)
- functions: snake_case z czasownikiem (np. flush_plan, sync_notion, append_decision)
- variables: snake_case; stałe UPPER_SNAKE_CASE
- SKILLe: pcc_<akcja> (np. pcc_status, pcc_step_done, pcc_decision)
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
- src/controller.py: Python Controller — zapis/walidacja PLAN.md i append_decision do ARCHITECTURE.md
- src/skill.py: SKILL Agent — pcc_status, pcc_step_start, pcc_step_done, pcc_decision, pcc_round_end
- src/notion_sync.py: Notion Sync — push 4 MD jako podstrony do PCC_Projects (notion-client 3.0.0)
- src/hook_stop.py: Hook Stop — handoff do session_log przy zamknięciu sesji CC
- src/validator.py: Validator — format decisions (3 pola po |), components (- nazwa: opis)
- src/pcc_unpack.py: Unpacker — JSON z wizarda → 4 pliki MD (CLI via typer)
- templates/plan_template.md: szablon PLAN.md z placeholderami {{GOAL}}, {{SESSION}} itd.
- tests/: testy jednostkowe i integracyjne (51 testów, wszystkie zielone)
- .env: NOTION_TOKEN + NOTION_PCC_DB + NOTION_PARENT_PAGE (nie commitować)
- .env.example: szablon .env do wypełnienia
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
- każda zmiana pliku MD przechodzi przez controller.py — nigdy przez bezpośredni zapis
- SKILL podejmuje decyzję, Python wykonuje — separacja odpowiedzialności
- błędy skryptu muszą być obsłużone zanim subagent przejmie kontrolę
- funkcje kontrolera są idempotentne — wielokrotne wywołanie nie psuje stanu
- decyzje architektoniczne: wyłącznie przez pcc_decision() / append_decision(), nigdy agent bezpośrednio
- Notion API: chunki rich_text max 1990 znaków; używaj _md_to_blocks() do podziału
- CLI output: tylko ASCII w print() — terminale Windows (cp1250) nie obsługują strzałek Unicode
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
- feat(plan): opis zmiany w PLAN.md lub logice rundy
- feat(skill): nowy lub rozszerzony SKILL pcc_*
- fix(controller): naprawa skryptu Python lub walidacji MD
- fix(notion): naprawa integracji Notion API
- sync(notion): aktualizacja mapowania lub struktury Notion
- test: dodanie lub naprawa testów
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
- każda funkcja controller.py pokryta testem jednostkowym z mockowanym systemem plików (tmp_path)
- testy notion_sync.py używają MagicMock — nie uderzają w live API
- testy integracyjne (test_e2e.py) weryfikują pełny cykl: step_start → step_done → round_end
- testy uruchamiane przed każdym merge do main
- match w pytest.raises używa ASCII — polskie znaki w komunikatach nie są matchowane przez regex w cp1250
<!-- /SECTION:testing -->

## Anti Patterns
<!-- SECTION:anti_patterns -->
- nigdy nie zapisuj do CLAUDE.md / ARCHITECTURE.md / CONVENTIONS.md z poziomu agenta w trakcie rundy
- wyjątek od powyższego: ARCHITECTURE/decisions — tylko przez pcc_decision() / append_decision()
- nigdy nie uruchamiaj plan mode przed wygenerowaniem szablonu.md
- nigdy nie pomijaj walidacji Python Controller nawet przy drobnych zmianach
- nigdy nie synchronizuj Notion ręcznie z pominięciem notion_sync.py
- nigdy nie używaj databases.query — w notion-client 3.0.0 nie istnieje; używaj data_sources.query
- nigdy nie przekazuj database_id jako parent przy tworzeniu rekordu — używaj data_source_id
- nigdy nie wysyłaj bloku rich_text > 1990 znaków do Notion API
<!-- /SECTION:anti_patterns -->
