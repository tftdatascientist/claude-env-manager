#!/usr/bin/env python3
"""prompt_length_check.py — hook UserPromptSubmit dla SSS.

Uruchamia się przy KAŻDYM prompcie usera. Działa tylko gdy:
- katalog NIE ma jeszcze PLAN.md (czyli to nowy projekt, prawdopodobnie pierwszy prompt opisujący projekt)
- prompt nie jest komendą slash (`/go`, `/ser`, `/end`, `/serwis`)
- prompt ma >50 znaków (żeby nie reagować na "ok", "tak", "kontynuuj")

Jeśli warunki spełnione i prompt < 1000 znaków:
emituje ostrzeżenie ile brakuje do progu oceniania.

Komunikacja: stdin JSON, stdout tekst do kontekstu Claude'a.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

THRESHOLD = 1000
WARN_FROM = 50  # poniżej tego nie reagujemy w ogóle


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = payload.get('prompt', '') or ''
    cwd = payload.get('cwd', '') or '.'

    # nie reaguj na komendy slash
    stripped = prompt.strip()
    if stripped.startswith('/'):
        return 0

    # nie reaguj na krótkie odpowiedzi
    if len(prompt) < WARN_FROM:
        return 0

    # tylko nowy projekt — brak PLAN.md
    plan = Path(cwd) / 'PLAN.md'
    if plan.exists():
        return 0

    if len(prompt) >= THRESHOLD:
        # prompt wystarczająco długi — wyślij sygnał że można scoring odpalić
        print(
            f'[SSS] Wykryto opis nowego projektu ({len(prompt)} znaków, '
            f'≥{THRESHOLD}). Uruchom Rundę Wstępną SSS — szczegóły w '
            '.claude/skills/sss/SKILL.md (sekcja "Runda Wstępna"). '
            'Zacznij od score_intake.py --mode init, potem panel sędziów przez Task tool.'
        )
        return 0

    # poniżej progu — ostrzeż, ale nie blokuj
    missing = THRESHOLD - len(prompt)
    print(
        f'[SSS] Wykryto opis nowego projektu ale prompt ma tylko {len(prompt)} '
        f'znaków. Brakuje {missing} znaków do progu oceniania ({THRESHOLD}). '
        'Zapytaj usera czy chce rozszerzyć opis (rekomendowane — dostanie ocenę '
        'kompetencji od panelu sędziów) czy kontynuować bez oceny.'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
