## Naming
<!-- SECTION:naming -->
- Pliki modułów: snake_case (np. task_manager.py, plan_parser.py). Klasy: PascalCase (np. TaskManager, PlanFileHandler). Funkcje i metody: snake_case z czasownikiem (np. create_task(), parse_plan_file()). Zmienne lokalne: snake_case opisowe (np. plan_content, task_list); stałe: UPPER_SNAKE_CASE (np. SECTION_REGEX, DEFAULT_WEIGHT).
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
- claude_manager/
- ├── gui/
- │   ├── menu_develop.py
- │   └── tasks_panel.py
- ├── core/
- │   ├── plan_parser.py
- │   ├── plan_writer.py
- │   └── ai_client.py
- ├── models/
- │   └── task_model.py
- └── utils/
- └── file_utils.py
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
- Każdy moduł ma jedną odpowiedzialność; GUI (CustomTkinter) oddzielone od logiki biznesowej i parsowania plików PLAN.md. Sekcje PLAN.md identyfikowane wyłącznie przez regex (<!-- SECTION:xxx --> / <!-- /SECTION:xxx -->); nigdy przez pozycję linii. Funkcje AI (generowanie zadań) hermetyzowane w osobnej klasie bez bezpośredniego importu klucza API — dostęp przez subskrypcję CC.
- PEP8 obowiązkowy; długość linii max 100 znaków (black --line-length 100). Wcięcia: 4 spacje, bez tabulatorów. Importy grupowane: stdlib → third-party (customtkinter, pathlib) → lokalne; każda grupa oddzielona pustą linią.
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
- Typy commitów: feat (nowa funkcja), fix (naprawa), refactor (bez zmiany zachowania), docs (PLAN.md / README), test (testy), chore (konfiguracja). Format: 'typ(zakres): opis po polsku', np. 'feat(tasks): dodaj wariant A generowania zadań DPS'. Zakres odpowiada nazwie modułu lub sekcji GUI.
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
- Testy w pytest umieszczone w katalogu tests/ z prefiksem test_ (np. test_plan_parser.py). Każda funkcja parsująca regex musi mieć test jednostkowy z przykładowym PLAN.md jako fixture. Testy GUI pomijane w CI (marker @pytest.mark.gui); logika biznesowa testowana bez uruchamiania okna.
<!-- /SECTION:testing -->

## Anti-patterns
<!-- SECTION:anti_patterns -->
<!-- /SECTION:anti_patterns -->
