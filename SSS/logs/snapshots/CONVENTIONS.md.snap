<!-- CONVENTIONS v1.0 -->

## Naming
<!-- SECTION:naming -->
- snake_case dla plików i modułów
- PascalCase dla klas Qt (View/Widget/Spawner/Watcher/Store)
- prefix qt_ dla sygnałów własnych
- session_id format: YYYYMMDD_HHMMSS_slug
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
- src/cm/sss_module/: cały moduł
- src/cm/sss_module/views/: PySide6 widgets (intake_view.py, logs_view.py)
- src/cm/sss_module/core/: logika (spawner.py, plan_watcher.py, round_watcher.py, log_store.py, sss_bridge.py)
- src/cm/sss_module/db/: schema SQLite, migracje
- tests/sss_module/: pytest
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
- type hints wszędzie (3.13)
- pathlib.Path zamiast os.path
- Qt sygnały zamiast callbacków
- żadnych prints — logging.getLogger(__name__)
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
- feat(sss): nowa funkcja
- fix(sss): bug
- refactor(sss): zmiana wewnętrzna
- test(sss): testy
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
- pytest + pytest-qt do widgetów
- tmp_path dla fake projektów
- mock subprocess.Popen przy testach Spawnera
- testy log_store na :memory: SQLite
<!-- /SECTION:testing -->

## Anti Patterns
<!-- SECTION:anti_patterns -->
- nigdy nie modyfikuj plików .md projektu CC z poziomu CM (read-only po spawnie)
- nigdy nie blokuj UI thread czytaniem plików — używaj QThread/QTimer
- nigdy nie hardkoduj ścieżek absolutnych w kodzie — tylko w configu
- nigdy nie polluj logów print()-ami
<!-- /SECTION:anti_patterns -->
