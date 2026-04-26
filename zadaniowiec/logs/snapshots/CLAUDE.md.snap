# Moduł Zadania  PLAN.md

<!-- SECTION:project -->
- name: Moduł Zadania  PLAN.md
- type:
- client:
- stack: Python · CustomTkinter (GUI) · Claude AI (subskrypcja, bez klucza API) · regex · pathlib · markdown
<!-- /SECTION:project -->

Interfejs w Claude Manager do tworzenia i zarządzania zadaniami w plikach PLAN.md zgodnych z formatem DPS.

## Instrukcje dla agenta

Agent edytuje wyłącznie `PLAN.md` w trakcie rundy.
Pozostałe pliki (`ARCHITECTURE.md`, `CONVENTIONS.md`) są chronione.

## Stack
<!-- SECTION:stack -->
- Python · CustomTkinter (GUI) · Claude AI (subskrypcja, bez klucza API) · regex · pathlib · markdown
<!-- /SECTION:stack -->

## Key Files
<!-- SECTION:key_files -->
- Plik | Rola
--- | ---
- `claude_manager.py` | Punkt wejścia aplikacji, inicjalizacja GUI
- `modules/tasks_panel.py` | Panel Zadania w sekcji menu Develop → Sesje CC
- `modules/plan_handler.py` | Odczyt, zapis i walidacja pliku PLAN.md (regex DPS)
- `modules/ai_client.py` | Komunikacja z Claudem przez subskrypcję (bez klucza API)
- `ARCHIWUM.md` | Archiwum starych zadań i logów sesji przenoszonych przez Oczyszczenie
<!-- /SECTION:key_files -->

## Zasady kodowania

- Nie modyfikuj sekcji PLAN.md poza znacznikami `<!-- SECTION:next -->`
- Waliduj strukturę pliku regexem przed zapisem
- Oddziel logikę GUI od logiki przetwarzania planu
- Nie twórz abstrakcji ponad wymagania — jeden moduł, jedna odpowiedzialność
- Przy braku pliku PLAN.md zapytaj użytkownika o decyzję DPS/normalny

## Uruchomienie

```bash
python claude_manager.py
```

## Off-limits w trakcie rundy

- Nie edytuj `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` bezpośrednio
- Nie commituj bez walidacji
