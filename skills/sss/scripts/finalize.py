"""finalize.py — Zakończenie projektu: service round + README.md + git repo.

Procedura:
1. Wykonaj pełną Rundę Serwisową przez subprocess
2. Wygeneruj README.md z sekcji w CLAUDE.md, ARCHITECTURE.md, CHANGELOG.md
3. git init + gh repo create (lub fallback do instrukcji ręcznej)

Użycie:
    python finalize.py --target /path/do/projektu --repo-name SLUG [--public]
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402
import events  # noqa: E402

TEMPLATES_DIR = Path(__file__).parent.parent / 'assets' / 'templates'


def run_service_round(target: Path) -> int:
    script = Path(__file__).parent / 'service_round.py'
    r = subprocess.run(
        [sys.executable, str(script), '--target', str(target)],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
    return r.returncode


def gather_for_readme(target: Path) -> dict:
    """Zbiera dane z plików projektu do README."""
    data = {
        'title': '',
        'one_liner': '',
        'project_meta': '',
        'stack': '',
        'overview': '',
        'components': '',
        'changelog_entries': '',
    }

    claude_path = target / 'CLAUDE.md'
    if claude_path.exists():
        ctext = p.read_file(claude_path)
        # title z pierwszego "# " w pliku
        for line in ctext.splitlines():
            if line.startswith('# ') and not line.startswith('# {{'):
                data['title'] = line[2:].strip()
                break
        # one_liner — pierwszy paragraph po H1 (nie sekcja, nie marker)
        in_body = False
        for line in ctext.splitlines():
            if line.startswith('# '):
                in_body = True
                continue
            if in_body and line.strip() and not line.startswith('<!--') and not line.startswith('#'):
                data['one_liner'] = line.strip()
                break
        data['project_meta'] = p.read_section(ctext, 'project')
        data['stack'] = p.read_section(ctext, 'stack')

    arch_path = target / 'ARCHITECTURE.md'
    if arch_path.exists():
        atext = p.read_file(arch_path)
        data['overview'] = p.read_section(atext, 'overview')
        data['components'] = p.read_section(atext, 'components')

    cl_path = target / 'CHANGELOG.md'
    if cl_path.exists():
        cltext = p.read_file(cl_path)
        data['changelog_entries'] = p.read_section(cltext, 'entries')

    return data


def render_readme(data: dict) -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    parts = [f'# {data["title"] or "Projekt"}', '']
    if data['one_liner']:
        parts.extend([data['one_liner'], ''])
    if data['project_meta']:
        parts.extend(['## Projekt', '', data['project_meta'], ''])
    if data['stack']:
        parts.extend(['## Stack', '', data['stack'], ''])
    if data['overview']:
        parts.extend(['## Overview', '', data['overview'], ''])
    if data['components']:
        parts.extend(['## Komponenty', '', data['components'], ''])
    if data['changelog_entries']:
        parts.extend(['## Historia (CHANGELOG)', '', data['changelog_entries'], ''])
    parts.extend(['---', f'_Wygenerowane: {today} przez sss/finalize.py_', ''])
    return '\n'.join(parts)


def init_repo(target: Path, repo_name: str, public: bool) -> str:
    """Zwraca status: 'gh' / 'git_only' / 'manual'."""
    if not (target / '.git').exists():
        subprocess.run(['git', 'init'], cwd=target, check=True, capture_output=True)
        # minimalny .gitignore
        gi = target / '.gitignore'
        if not gi.exists():
            gi.write_text('__pycache__/\n*.pyc\n.env\n.venv/\nnode_modules/\n', encoding='utf-8')
        subprocess.run(['git', 'add', '-A'], cwd=target, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial commit (sss finalize)'],
            cwd=target, check=False, capture_output=True,
        )

    has_gh = shutil.which('gh') is not None
    if not has_gh:
        return 'git_only'

    visibility = '--public' if public else '--private'
    r = subprocess.run(
        ['gh', 'repo', 'create', repo_name, visibility, '--source=.', '--remote=origin', '--push'],
        cwd=target, capture_output=True, text=True,
    )
    if r.returncode == 0:
        return 'gh'
    print(f'[WARN] gh repo create failed: {r.stderr.strip()}')
    return 'git_only'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', required=True)
    ap.add_argument('--repo-name', required=True, help='slug repo na GitHub')
    ap.add_argument('--public', action='store_true', help='public repo (default: private)')
    ap.add_argument('--skip-repo', action='store_true', help='pomiń git/gh, tylko README')
    args = ap.parse_args()

    target = Path(args.target).resolve()

    print('[1/3] Runda Serwisowa...')
    rc = run_service_round(target)
    if rc != 0:
        print('[ERR] service_round nieudana — przerwanie')
        sys.exit(rc)

    print('[2/3] Generuję README.md...')
    data = gather_for_readme(target)
    readme = render_readme(data)
    (target / 'README.md').write_text(readme, encoding='utf-8')
    print(f'[OK] README.md zapisany ({len(readme)} znaków)')

    if args.skip_repo:
        print('[SKIP] git/gh pominięte (--skip-repo)')
        print('[DONE] Zakończenie projektu')
        return

    print('[3/3] Inicjalizuję repo...')
    status = init_repo(target, args.repo_name, args.public)
    if status == 'gh':
        print(f'[OK] Repo utworzone na GitHub i wypchnięte: {args.repo_name}')
    elif status == 'git_only':
        print(f'[OK] git init zrobiony lokalnie. Brak gh CLI lub gh failed.')
        print(f'[INSTRUKCJA] Aby wypchnąć ręcznie:')
        vis = 'public' if args.public else 'private'
        print(f'    gh repo create {args.repo_name} --{vis} --source=. --remote=origin --push')
        print(f'    # lub przez UI GitHub: utwórz repo i:')
        print(f'    git remote add origin git@github.com:USER/{args.repo_name}.git')
        print(f'    git push -u origin main')

    import os
    session_id = os.environ.get('SSM_SESSION_ID') or events.new_session_id()
    repo_url = ''
    if status == 'gh':
        repo_url = f'https://github.com/{args.repo_name}'
    events.append_event(
        target, 'repo_finalized', session_id,
        round='service',
        payload={'repo_name': args.repo_name, 'remote_url': repo_url, 'status': status},
    )

    print('[DONE] Zakończenie projektu')


if __name__ == '__main__':
    main()
