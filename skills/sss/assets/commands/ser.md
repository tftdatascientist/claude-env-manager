---
description: Runda Serwisowa — czyszczenie PLAN.md, dystrybucja bufora, session log
allowed-tools: Bash, Read, Write, Edit
---

Wywołujesz Rundę Serwisową bez pytania o zgodę — to deterministyczna konserwacja.

Kroki:

1. Uruchom skrypt:
   ```bash
   python .claude/skills/sss/scripts/service_round.py --target .
   ```
2. Skrypt zrobi:
   - przenosi checked items z `done` (PLAN.md) → `entries` (CHANGELOG.md) z timestampem sesji
   - rozdystrybuuje bufor PLAN.md → docelowe pliki (CLAUDE/ARCHITECTURE/CONVENTIONS/CHANGELOG) wg mapowania
   - dopisze wpis do `session_log` (PLAN.md) — co zrobiono w sesji, hash commit jeśli jest, timestamp
   - wyczyści `done` i `buffer` w PLAN.md
   - wypisze raport tekstowy
3. Pokaż userowi raport ze skryptu **dosłownie**.
4. Po serwisie:
   - jeśli `next` pusty + user uznaje projekt za gotowy → użyj `/end`
   - jeśli `next` pusty + user mówi że projekt nie gotowy → poproś o opis braków, dopisz `- [ ] ...` do `next` przez `Edit`, wracaj do `/go`
   - jeśli `next` ma jeszcze zadania → wracaj do `/go`

Pełne instrukcje: `.claude/skills/sss/SKILL.md` (sekcja "Runda Serwisowa").
