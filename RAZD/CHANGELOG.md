# Changelog — RAZD

## [Unreleased]

### Dodano
- Focus Timer: domyślna wartość timera zmieniona z 25 na 60 minut
- Focus Timer: dźwięk po zakończeniu sesji (`winsound.Beep`, 3× dwutonowy sygnał, wątek tła)
- Zadania: filtry statusów (Wszystkie / Do zrobienia / W trakcie / Do zrobienia + W trakcie / Gotowe)
- Zadania: edycja zadania (tytuł, deadline, szczegóły) przez kliknięcie karty — sync do Notion w tle
- Zadania: `_EditTaskDialog` + `_UpdateThread` + `update_task_fields_local` w repository
- ASUS: zakładka "Pliki" — podgląd i edycja README.md, CHANGELOG.md, ROADMAP.md z poziomu aplikacji

### Naprawiono
- Zadania: pobieranie zadań z Notion (notion-client 3.x: `data_sources.query` zamiast `databases.query`)
- Zadania: poprawna nazwa relacji (`Projekt` zamiast `Project related`)
- Zadania: normalizacja UUID (`.env` bez myślników → Notion API z myślnikami)
- Zadania: tworzenie zadań (`parent={"data_source_id": ...}` zamiast `{"database_id": ...}`)
- Projekty → Zadania: zmiana projektów w zakładce Projekty propaguje się do zakładki Zadania (sygnał `pinned_changed`)
- Kolory: ciemne tła pod kolorowymi etykietami w zakładkach Zadania i Projekty

---

## [0.1.0] — 2026-05-02

### Dodano
- Inicjalny release: Time Tracking, Focus Timer, Timeline, Projekty, Notion Sync
- Autostart Windows + tray icon + tryb minimized start
- Notion: eksport integracja z sync worker
- Testy pytest-qt: 54 testów (focus timer state machine, TimeTrackingTab, RazdSettings, UI smoke)
