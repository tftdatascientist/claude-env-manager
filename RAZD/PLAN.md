## Meta
## Current
## Next
## Done
## Buffer
## Blockers
## Session Log

## Next

## Done
- [x] BUGFIX: poller nigdy nie zapisywał do tabeli `events` — insert_event dodany do `_poll()`, teraz Timeline i raporty mają dane
- [x] BUGFIX: _load_day_from_db tworzył 1 segment per event (2s → 0.056px niewidoczne) — scalanie bloków tej samej kategorii
- [x] BUGFIX: kolor OFF (#1B2A3B) niewidoczny na tle #111 — zmieniony na #2D3F52 alpha 230
- [x] BUGFIX: poller używał UTC timezone → ts z +00:00, zapytania LIKE gubił wieczorne wpisy — zmieniony na datetime.now()
- [x] Ikona aplikacji wielowarstwowa (16/32/48/64/128/256px) — `_make_tray_icon` w `main_window.py`, lepsza jakość na pasku zadań i tray
- [x] `generate_icon()` w `shortcut.py` — skrót na pulpicie z ikoną 256px (Pillow multi-ICO lub Qt fallback)
- [x] `RazdMonthlyStatsWidget` dodany do sidebara zakładki Timeline (w `QScrollArea` pod weekly)
- [x] Statystyki tygodnia i miesiąca dodane do `RazdDailyReportDialog` (gdy przekazano `repo=`)
- [x] Dodać kontrolkę suwaka/przycisków zoom (+/-) do widoku osi czasu — przyciski 3h/6h/12h/24h/72h w `timeline_widget.py`
- [x] Zaimplementować obsługę zdarzenia `wheelEvent` na widoku osi czasu — scroll w górę przybliża, w dół oddala skalę
- [x] Przerysowywać oś czasu i bloki aktywności przy każdej zmianie skali (sygnał scale_changed → repaint)
- [x] Zbadać i naprawić logikę liczenia czasu w raporcie dnia — nakładające się eventy dawały duration ≤ 0 → pominięcie; poprawka: `max(2, min(..., 120))`
- [x] Zdefiniować i zaimplementować `DayStats` dataclass + `compute_day_stats(date) -> DayStats` w `RazdRepository`
- [x] Dodać widżet statystyk tygodniowych `RazdWeeklyStatsWidget` — ostatnie 7 dni, paski PC ON/Praca/Idle w sidebarze Timeline
- [x] Dodać widżet statystyk miesięcznych `RazdMonthlyStatsWidget` — tabela 30 dni w `stats_widget.py`
- [x] Napisać testy pytest dla `compute_day_stats` — 7 testów: brak danych, single event, active+idle, uptime 8h, nakładające się ts, edge 23:59, typ zwracany
