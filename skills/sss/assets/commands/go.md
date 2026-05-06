---
description: Start/kontynuacja Rundy Developmentu w SSS
allowed-tools: Bash, Read, Write, Edit
---

Uruchamiasz Rundę Developmentu w systemie SSS (Scripted Skills System).

Kroki:

1. Sprawdź fazę projektu:
   ```bash
   python .claude/skills/sss/scripts/state.py --target .
   ```
2. Jeśli `phase != "dev"` — postąp zgodnie z hintem w odpowiedzi state.py (np. `init` → Runda Wstępna, `service_due` → uruchom `/ser`).
3. Jeśli `phase == "dev"`:
   - Przeczytaj `PLAN.md` sekcję `next` i `current`
   - Weź pierwsze nieukończone zadanie z `next` jako bieżące, przenieś do `current` (przez `Edit`)
   - Zacznij robotę
   - Każdą informację dla CLAUDE.md/ARCHITECTURE.md/CONVENTIONS.md/CHANGELOG.md → bufor:
     ```bash
     python .claude/skills/sss/scripts/plan_buffer.py add --target ARCHITECTURE.md --content "..."
     ```
   - Po skończeniu zadania → przenieś do `done` z timestampem, weź kolejne z `next`

Stop conditions: bufor ≥10, `next` pusty, user mówi stop, `/context` ≥66%.

Przed startem przeczytaj pełne instrukcje w `.claude/skills/sss/SKILL.md` (sekcja "Runda Developmentu").
