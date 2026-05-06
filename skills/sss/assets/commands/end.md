---
description: Zakończenie projektu — runda serwisowa + README + git push
allowed-tools: Bash, Read, Write, Edit
---

Wywołujesz Zakończenie projektu. Procedura:

1. Zapytaj usera o nazwę repo (slug, np. `chatbot-agencja-xyz`). Jeśli nie poda — wygeneruj z `project.title` w PLAN.md (kebab-case, ASCII).
2. Uruchom:
   ```bash
   python .claude/skills/sss/scripts/finalize.py --target . --repo-name SLUG
   ```
3. Skrypt zrobi:
   - pełną Rundę Serwisową (jak `service_round.py`)
   - wygeneruje `README.md` na podstawie sekcji z CLAUDE.md/ARCHITECTURE.md/CHANGELOG.md
   - zainicjalizuje git (`git init` jeśli brak), commit "feat: finalize project"
   - jeśli `gh` dostępny → `gh repo create SLUG --private --source=. --remote=origin --push`
   - jeśli `gh` brak → wypisze pełną komendę dla usera do wykonania ręcznie
4. Pokaż userowi raport końcowy ze skryptu.
5. Koniec sesji.

Pełne instrukcje: `.claude/skills/sss/SKILL.md` (sekcja "Zakończenie").
