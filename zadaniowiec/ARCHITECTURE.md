## Overview
<!-- SECTION:overview -->
Użytkownik wypełnia formularz (cel, kontekst, stan, waga) w panelu Zadania → core/ai_client.py wysyła dane do Claude przez interfejs subskrypcji i odbiera listę zadań w formacie markdown → plan_writer.py wstrzykuje wyniki do sekcji <!-- SECTION:next --> w wybranym pliku PLAN.md, obsługując warianty A/B/C przez plan_parser.py.
<!-- /SECTION:overview -->

## Directory Structure

```
claude_manager/
├── gui/
│   ├── menu_develop.py
│   └── tasks_panel.py
├── core/
│   ├── plan_parser.py
│   ├── plan_writer.py
│   └── ai_client.py
├── models/
│   └── task_model.py
└── utils/
    └── file_utils.py
```

## Components
<!-- SECTION:components -->
- Moduł | Plik(i) | Odpowiedzialność
--- | --- | ---
- GUI Zadania | tasks_panel.py, menu_develop.py | Panel zadań w sekcji Develop, formularz danych wejściowych, wyświetlanie wyników w scrollowanym oknie 20%
- Parser PLAN | plan_parser.py | Wykrywanie wariantów A/B/C, parsowanie sekcji DPS przez regex, ekstrakcja bloków <!-- SECTION:* -->
- Klient AI | ai_client.py | Komunikacja z Claude przez subskrypcję (bez klucza API), wysyłanie kontekstu i odbieranie listy zadań
- Zapis Planu | plan_writer.py | Wstrzykiwanie zadań do sekcji Next, konwersja do formatu DPS, obsługa archiwizacji
- Model Zadania | task_model.py | Dataclass dla zadania: cel, kontekst, stan, waga, lista wynikowych tasków
<!-- /SECTION:components -->

## External Dependencies
<!-- SECTION:external_deps -->
- Lib/API | Cel | Wersja
--- | --- | ---
- customtkinter | Widgety GUI (scrollowany panel, przyciski, formularz) | >=5.2
- pathlib | Operacje na ścieżkach plików PLAN.md | stdlib
- re | Parsowanie sekcji DPS przez wyrażenia regularne | stdlib
- subprocess / cc CLI | Wywołanie Claude AI przez subskrypcję bez klucza API | stdlib
- markdown / pathlib | Odczyt i zapis plików .md z zachowaniem kodowania UTF-8 | stdlib
<!-- /SECTION:external_deps -->

## Constraints
<!-- SECTION:constraints -->
<!-- /SECTION:constraints -->

## Data Flow
<!-- SECTION:data_flow -->
Użytkownik wypełnia formularz (cel, kontekst, stan, waga) w panelu Zadania → core/ai_client.py wysyła dane do Claude przez interfejs subskrypcji i odbiera listę zadań w formacie markdown → plan_writer.py wstrzykuje wyniki do sekcji <!-- SECTION:next --> w wybranym pliku PLAN.md, obsługując warianty A/B/C przez plan_parser.py.
<!-- /SECTION:data_flow -->

## Decisions
<!-- SECTION:decisions -->
- [ ] 1. Oddzielenie parsera od writera — plan_parser.py tylko czyta i wykrywa format, plan_writer.py tylko modyfikuje, co ułatwia testy jednostkowe. | 2026-04-26 | AI Wizard
- [ ] 2. Brak klucza API — ai_client.py korzysta z sesji subskrypcji Claude (np. przez cc CLI lub webdriver), bez przechowywania poświadczeń w kodzie. | 2026-04-26 | AI Wizard
- [ ] 3. Regex DPS jako standard — sekcje <!-- SECTION:name --> traktowane jako jedyny kanoniczny format; warianty B/C wymagają decyzji użytkownika przed zapisem. | 2026-04-26 | AI Wizard
- [ ] 4. GUI osadzone w istniejącym menu Develop — tasks_panel.py dziedzieczy po bazowym panelu Claude Manager, nie tworzy nowego okna, zachowując spójność UX. | 2026-04-26 | AI Wizard
<!-- /SECTION:decisions -->
