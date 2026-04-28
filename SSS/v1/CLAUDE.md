<!-- CLAUDE v1.0 -->

# SSS Module dla Claude Manager

Podmoduł CM (Develop → Sesje CC → Logi): UI do startu projektu CC w plan mode, polling PLAN.md, logowanie wszystkich rund SSS.

## Imports
<!-- SECTION:imports -->
@ARCHITECTURE.md
@PLAN.md
@CONVENTIONS.md
<!-- /SECTION:imports -->

## Project
<!-- SECTION:project -->
- name: SSS Module dla Claude Manager
- type: desktop
- client: własny
<!-- /SECTION:project -->

## Stack
<!-- SECTION:stack -->
- Python 3.13
- PySide6
- VS Code wtyczka VS_CLAUDE
- Claude Code CLI
<!-- /SECTION:stack -->

## Off Limits
<!-- SECTION:off_limits -->
- nie modyfikuj plików projektu CC z poziomu CM (tylko read-only poza spawnem inicjalnym)
- nie używaj plansDirectory innego niż '.' w settings.json projektu spawnowanego
<!-- /SECTION:off_limits -->

## Specifics
<!-- SECTION:specifics -->
- workflow: user wpisuje prompt + nazwę + lokalizację w CM, klik wysyła prompt do CC w plan mode i otwiera VS Code z wtyczką VS_CLAUDE
- baza: C:\Users\Sławek\claude-env-manager, wtyczka: C:\Users\Sławek\claude-env-manager\VS_CLAUDE
- aktualnie istnieje przycisk Start CC robiący przejście z Pythona do VS Code — przerabiamy ten flow na wysyłkę prompta + auto-otwarcie
- logi pod menu CM: Develop → Sesje CC → Logi
- jeden rekord = jedno zdarzenie (event-sourced log)
- CHANGELOG.md projektu CC nie istnieje aż do pierwszej Rundy Serwisowej — wtedy tworzy go skill /sss; w logach CM pojawia się wpis o utworzeniu w sekcji SSS
<!-- /SECTION:specifics -->
