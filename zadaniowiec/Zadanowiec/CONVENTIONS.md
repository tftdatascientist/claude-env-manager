## Naming
<!-- SECTION:naming -->
- snake_case dla plików i modułów Python
- PascalCase dla klas
- UPPER_CASE dla stałych modułowych
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
- src/ — kod źródłowy
- tests/ — testy pytest
- docs/ — dokumentacja (opcjonalnie)
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
- PEP 8, type hints (Python 3.12+)
- max line 120 znaków
- pathlib.Path zamiast os.path
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
- feat/fix/docs/refactor/test/chore
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
- pytest z tmp_path dla plików tymczasowych
- brak hardkodowanych ścieżek w testach
<!-- /SECTION:testing -->

## Anti-patterns
<!-- SECTION:anti_patterns -->
- [ ] nie hardkoduj ścieżek absolutnych
- [ ] nie pomijaj type hints
- [ ] nie używaj os.path (używaj pathlib.Path)
<!-- /SECTION:anti_patterns -->
