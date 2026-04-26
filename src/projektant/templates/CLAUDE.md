# <!-- PROJECT_NAME -->

<!-- SECTION:project -->
- name: 
- type: 
- client: 
- stack: Python 3.13+
<!-- /SECTION:project -->

## Instrukcje dla agenta

Agent edytuje wyłącznie `PLAN.md` w trakcie rundy.
Pozostałe pliki (`ARCHITECTURE.md`, `CONVENTIONS.md`) są chronione — aktualizowane tylko przez autoryzowane funkcje po zakończeniu rundy.

## Stack
<!-- SECTION:stack -->
- python: 3.13+
- pytest: 8.2+
<!-- /SECTION:stack -->

## Key Files
<!-- SECTION:key_files -->
- src/ — kod źródłowy
- tests/ — testy pytest
<!-- /SECTION:key_files -->

## Off-limits w trakcie rundy

- Nie edytuj `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` bezpośrednio
- Nie commituj bez przejścia walidacji
- Nie synchronizuj Notion ręcznie z pominięciem `notion_sync.py`
