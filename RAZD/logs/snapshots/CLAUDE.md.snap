<!-- CLAUDE v1.0 -->

# RAZD

Moduł CEM do auto-trackingu czasu i fokusu, sterowany agentem Claude Code który uczy się znaczenia procesów/URLs przez dialog z userem.

## Imports
<!-- SECTION:imports -->
@ARCHITECTURE.md
@PLAN.md
@CONVENTIONS.md
<!-- /SECTION:imports -->

## Project
<!-- SECTION:project -->
- name: RAZD
- type: moduł desktop (PySide6) w Claude Env Manager
- client: własny (Radek)
<!-- /SECTION:project -->

## Stack
<!-- SECTION:stack -->
- Python 3.13
- PySide6
- psutil
- pywin32
- uiautomation
- claude-agent-sdk
- SQLite
<!-- /SECTION:stack -->

## Off Limits
<!-- SECTION:off_limits -->
- nie używaj zewnętrznych API trackingu (Toggl, RescueTime, Clockify) — wszystko lokalnie
- nie blokuj Qt UI threada — każdy I/O i polling w QThread/QTimer
- nie modyfikuj struktury CEM poza punktem wpięcia (top menu)
- nie wysyłaj danych aktywności poza maszynę bez zgody usera (privacy first)
- nie hardkoduj ścieżek do Chrome/Edge — discover przez registry/where
<!-- /SECTION:off_limits -->

## Specifics
<!-- SECTION:specifics -->
- moduł wpina się w CEM przez QMenuBar (top menu CEM → RAZD)
- AI engine to Claude Code przez claude-agent-sdk (Python), nie bezpośredni Claude API
- agent CC działa persistent w tle gdy komputer włączony, czyta strumień zdarzeń trackera
- nieznany proces/URL → agent generuje pytanie → dialog Qt do usera → odpowiedź → zapis w SQLite
- konwencje CEM obowiązują: ruff, pyproject.toml, pytest + pytest-qt, type hints
- platforma MVP: Windows-only (pywin32, uiautomation API), cross-platform na fazę 2
- rozróżniamy dwie role: Tracker (zbiera surowe sygnały) vs Agent (interpretuje, kategoryzuje, pyta)
<!-- /SECTION:specifics -->
