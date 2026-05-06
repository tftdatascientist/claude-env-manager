"""service_round.py — Runda Serwisowa: czyszczenie PLAN.md i dystrybucja bufora.

Krok po kroku:
1. Wczytaj PLAN.md
2. Z sekcji `done` weź wszystkie checked items "- [x] ..."
   → dopisz do CHANGELOG.md sekcja `entries` z prefixem timestampu sesji
   → wyczyść sekcję `done` w PLAN.md
3. Z sekcji `buffer` weź wszystkie wpisy "- TARGET | DATE | content"
   → dla każdego: dopisz do TARGET pliku, w sekcji wg mapowania
   → wyczyść sekcję `buffer` w PLAN.md
4. Aktualizuj `meta.updated`
5. Wypisz raport tekstowy (do pokazania userowi)

Użycie:
    python service_round.py --target /path/do/projektu
"""
from __future__ import annotations
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402
import events  # noqa: E402

# Mapowanie target file → docelowa sekcja
TARGET_SECTION = {
    'CLAUDE.md': 'specifics',
    'ARCHITECTURE.md': 'decisions',
    'CONVENTIONS.md': 'anti_patterns',
    'CHANGELOG.md': 'entries',
}

BUFFER_LINE_RE = re.compile(r'^-\s*([\w.]+)\s*\|\s*([\d:\-\s]+?)\s*\|\s*(.+)$')


def now_stamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def get_session_number(plan_text: str) -> int:
    """Wyciąga numer sesji z meta sekcji."""
    meta = p.read_section(plan_text, 'meta')
    for line in meta.splitlines():
        line = line.strip()
        if line.startswith('- session:'):
            try:
                return int(line.split(':', 1)[1].strip())
            except ValueError:
                pass
    return 1


def update_meta_timestamp(plan_text: str) -> str:
    """Aktualizuje pole `- updated:` w sekcji meta."""
    meta = p.read_section(plan_text, 'meta')
    new_lines = []
    found = False
    for line in meta.splitlines():
        if line.strip().startswith('- updated:'):
            new_lines.append(f'- updated: {now_stamp()}')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'- updated: {now_stamp()}')
    return p.write_section(plan_text, 'meta', '\n'.join(new_lines))


def bump_session_number(plan_text: str, new_num: int) -> str:
    """Aktualizuje pole `- session:` w sekcji meta."""
    meta = p.read_section(plan_text, 'meta')
    new_lines = []
    found = False
    for line in meta.splitlines():
        if line.strip().startswith('- session:'):
            new_lines.append(f'- session: {new_num}')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'- session: {new_num}')
    return p.write_section(plan_text, 'meta', '\n'.join(new_lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True, help='katalog projektu')
    args = ap.parse_args()

    target = Path(args.target)
    plan_path = target / 'PLAN.md'
    if not plan_path.exists():
        sys.exit(f'[ERR] brak PLAN.md w {target}')

    plan_text = p.read_file(plan_path)
    session_num = get_session_number(plan_text)
    moves = {'done_to_changelog': 0, 'buffer_dist': {}}
    warnings = []

    import os
    session_id = os.environ.get('SSM_SESSION_ID') or events.new_session_id()
    events.append_event(
        target, 'script_run', session_id,
        round='service',
        payload={'script': 'service_round.py', 'session': session_num},
    )

    # === KROK 1: done → CHANGELOG.md ===
    done_section = p.read_section(plan_text, 'done')
    done_items = [
        l.strip() for l in done_section.splitlines()
        if l.strip().startswith('- [x]') or l.strip().startswith('- [X]')
    ]

    if done_items:
        changelog_path = target / 'CHANGELOG.md'
        if not changelog_path.exists():
            # Stwórz minimalny CHANGELOG.md jeśli nie istnieje
            template_dir = Path(__file__).parent.parent / 'assets' / 'templates'
            changelog_path.write_text(
                (template_dir / 'CHANGELOG.md').read_text(encoding='utf-8'),
                encoding='utf-8',
            )

        cl_text = p.read_file(changelog_path)
        for item in done_items:
            # zachowaj timestamp sesji w wpisie CHANGELOG
            entry = f'- session:{session_num} | {today()} | {item[6:].strip()}'
            cl_text = p.append_to_section(cl_text, 'entries', entry)
        p.write_file(changelog_path, cl_text)

        # wyczyść done w PLAN.md
        plan_text = p.write_section(plan_text, 'done', '')
        moves['done_to_changelog'] = len(done_items)

    # === KROK 2: bufor → pliki docelowe ===
    buffer_section = p.read_section(plan_text, 'buffer')
    buffer_items = [l.strip() for l in buffer_section.splitlines() if l.strip().startswith('- ')]

    distributed = {}  # target_file -> list of content lines

    for raw in buffer_items:
        m = BUFFER_LINE_RE.match(raw)
        if not m:
            warnings.append(f'pominięto malformed: {raw[:60]}')
            continue
        target_file, ts, content = m.group(1), m.group(2).strip(), m.group(3).strip()
        if target_file not in TARGET_SECTION:
            warnings.append(f'nieznany target: {target_file}')
            continue
        # format wpisu w pliku docelowym: "- ts | content"
        line = f'- {ts} | {content}'
        distributed.setdefault(target_file, []).append(line)

    for target_file, lines in distributed.items():
        section = TARGET_SECTION[target_file]
        path = target / target_file
        if not path.exists():
            template_dir = Path(__file__).parent.parent / 'assets' / 'templates'
            tmpl = template_dir / target_file
            if tmpl.exists():
                path.write_text(tmpl.read_text(encoding='utf-8'), encoding='utf-8')
            else:
                warnings.append(f'brak {target_file} i brak szablonu — pominięto')
                continue
        ftext = p.read_file(path)
        try:
            for line in lines:
                ftext = p.append_to_section(ftext, section, line)
            p.write_file(path, ftext)
            moves['buffer_dist'][target_file] = len(lines)
            events.append_event(
                target, 'buffer_distribute', session_id,
                round='service',
                payload={'target_file': target_file, 'section': section, 'count': len(lines)},
            )
        except ValueError as e:
            warnings.append(f'{target_file}: {e}')

    # wyczyść bufor
    if buffer_items:
        plan_text = p.write_section(plan_text, 'buffer', '')

    # KROK 2.5: dopisz wpis do session_log
    session_summary_parts = []
    if moves['done_to_changelog']:
        session_summary_parts.append(f'{moves["done_to_changelog"]} zadań → CHANGELOG')
    for tf, n in moves['buffer_dist'].items():
        session_summary_parts.append(f'{n} → {tf}')
    if not session_summary_parts:
        session_summary_parts.append('serwis bez zmian (bufor pusty, done puste)')

    # spróbuj wyłapać commit hash z git
    commit_hash = ''
    try:
        import subprocess
        r = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=target, capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            commit_hash = r.stdout.strip()
    except Exception:
        pass

    log_entry = (
        f'- session:{session_num} | {now_stamp()} | '
        f'{", ".join(session_summary_parts)}'
    )
    if commit_hash:
        log_entry += f' | commit:{commit_hash}'
    plan_text = p.append_to_section(plan_text, 'session_log', log_entry)

    # KROK 3: aktualizuj meta.updated + bump session + zapisz PLAN
    plan_text = update_meta_timestamp(plan_text)
    plan_text = bump_session_number(plan_text, session_num + 1)
    p.write_file(plan_path, plan_text)

    # === RAPORT ===
    print('[OK] Runda Serwisowa zakończona')
    print(f'[DONE->CHANGELOG] {moves["done_to_changelog"]} pozycji')
    if moves['buffer_dist']:
        for tf, n in moves['buffer_dist'].items():
            print(f'[BUFFER→{tf}] {n} wpisów → sekcja {TARGET_SECTION[tf]}')
    else:
        print('[BUFFER] pusty (nic do dystrybucji)')
    if warnings:
        print('[WARNINGS]')
        for w in warnings:
            print(f'  - {w}')

    # phase hint dla AI
    next_section = p.read_section(plan_text, 'next')
    next_count = sum(1 for l in next_section.splitlines() if l.strip().startswith('- ['))
    print(f'[NEXT_COUNT] {next_count}')
    if next_count == 0:
        print('[HINT] sekcja next pusta — zapytaj usera czy projekt gotowy')
    else:
        print('[HINT] są jeszcze zadania w next — kontynuuj Rundę Developmentu')


if __name__ == '__main__':
    main()
