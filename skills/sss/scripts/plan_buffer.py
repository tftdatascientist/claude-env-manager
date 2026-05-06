"""plan_buffer.py — operacje na buforze w PLAN.md.

Bufor to sekcja <!-- SECTION:buffer --> w PLAN.md. Każdy wpis to linia:
    - TARGET | YYYY-MM-DD HH:MM | treść

Komendy:
    add    --target FILE.md --content "..."   dopisuje wpis
    count                                     wypisuje liczbę wpisów
    list                                      wypisuje wszystkie wpisy
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402

ALLOWED_TARGETS = {'CLAUDE.md', 'ARCHITECTURE.md', 'CONVENTIONS.md', 'CHANGELOG.md'}
PLAN_FILE = 'PLAN.md'


def find_plan(start: Path = Path.cwd()) -> Path:
    """Szuka PLAN.md w cwd lub --target. Tu używamy cwd jako default."""
    candidate = start / PLAN_FILE
    if not candidate.exists():
        raise FileNotFoundError(f'Brak {PLAN_FILE} w {start}. Uruchom z katalogu projektu lub podaj --target.')
    return candidate


def now_stamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def cmd_add(args):
    if args.target not in ALLOWED_TARGETS:
        sys.exit(f'[ERR] target musi być jednym z: {sorted(ALLOWED_TARGETS)}')
    plan = find_plan(Path(args.dir))
    text = p.read_file(plan)
    line = f'- {args.target} | {now_stamp()} | {args.content.strip()}'
    text = p.append_to_section(text, 'buffer', line)
    p.write_file(plan, text)

    # po dodaniu — wypisz aktualny count żeby Claude od razu widział czy nie 10
    count = len(p.list_checkbox_items(p.read_section(text, 'buffer'))) + sum(
        1 for l in p.read_section(text, 'buffer').splitlines() if l.strip().startswith('- ')
    )
    # uproszczenie: liczymy linie zaczynające się od "- "
    buffer_text = p.read_section(text, 'buffer')
    count = sum(1 for l in buffer_text.splitlines() if l.strip().startswith('- '))
    print(f'[OK] dodano do bufora: {args.target}')
    print(f'[BUFFER_COUNT] {count}/10')
    if count >= 10:
        print('[SSS-STOP] bufor pełny (10/10) — wywołaj /ser przed kolejnymi operacjami na PLAN.md')
    elif count >= 8:
        print(f'[SSS-WARN] bufor zbliża się do progu ({count}/10) — rozważ /ser')


def cmd_count(args):
    plan = find_plan(Path(args.dir))
    text = p.read_file(plan)
    buffer_text = p.read_section(text, 'buffer')
    count = sum(1 for l in buffer_text.splitlines() if l.strip().startswith('- '))
    print(count)


def cmd_list(args):
    plan = find_plan(Path(args.dir))
    text = p.read_file(plan)
    buffer_text = p.read_section(text, 'buffer')
    if not buffer_text.strip():
        print('[EMPTY] bufor pusty')
        return
    print(buffer_text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='.', help='katalog projektu (default: cwd)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    add_p = sub.add_parser('add')
    add_p.add_argument('--target', required=True, choices=sorted(ALLOWED_TARGETS))
    add_p.add_argument('--content', required=True)
    add_p.set_defaults(func=cmd_add)

    sub.add_parser('count').set_defaults(func=cmd_count)
    sub.add_parser('list').set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
