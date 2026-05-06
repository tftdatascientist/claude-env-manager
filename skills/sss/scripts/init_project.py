"""init_project.py — Runda Wstępna: bootstrap 4 plików startowych z intake.json.

Użycie:
    python init_project.py --intake intake.json --target /path/do/projektu

Skrypt:
1. Czyta intake.json (struktura w SKILL.md)
2. Kopiuje 4 szablony z assets/templates/ do --target
3. Wypełnia sekcje na podstawie intake.json przez parser.write_section
4. Wypisuje na stdout podsumowanie max 300 znaków (do akceptacji przez usera)
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402

ASSETS_DIR = Path(__file__).parent.parent / 'assets'
TEMPLATES_DIR = ASSETS_DIR / 'templates'
COMMANDS_DIR = ASSETS_DIR / 'commands'
HOOKS_DIR = ASSETS_DIR / 'hooks'
AGENTS_DIR = ASSETS_DIR / 'agents'
STARTUP_FILES = ['CLAUDE.md', 'ARCHITECTURE.md', 'CONVENTIONS.md', 'PLAN.md']

# mapowanie intake.json sections → (file, section_name)
FIELD_MAP = {
    ('claude', 'off_limits'): ('CLAUDE.md', 'off_limits'),
    ('claude', 'specifics'): ('CLAUDE.md', 'specifics'),
    ('architecture', 'overview'): ('ARCHITECTURE.md', 'overview'),
    ('architecture', 'components'): ('ARCHITECTURE.md', 'components'),
    ('architecture', 'data_flow'): ('ARCHITECTURE.md', 'data_flow'),
    ('architecture', 'decisions'): ('ARCHITECTURE.md', 'decisions'),
    ('architecture', 'constraints'): ('ARCHITECTURE.md', 'constraints'),
    ('conventions', 'naming'): ('CONVENTIONS.md', 'naming'),
    ('conventions', 'file_layout'): ('CONVENTIONS.md', 'file_layout'),
    ('conventions', 'code_style'): ('CONVENTIONS.md', 'code_style'),
    ('conventions', 'commit_style'): ('CONVENTIONS.md', 'commit_style'),
    ('conventions', 'testing'): ('CONVENTIONS.md', 'testing'),
    ('conventions', 'anti_patterns'): ('CONVENTIONS.md', 'anti_patterns'),
}


def now_stamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def install_claude_dir(target: Path) -> dict:
    """Kopiuje commands/hooks/agents/scripts/SKILL.md do .claude/ w projekcie + scala settings.

    Zwraca słownik z licznikami dla raportu.
    """
    counts = {
        'commands': 0, 'hooks': 0, 'agents': 0,
        'scripts': 0, 'skill_md': False, 'settings_merged': False,
    }
    claude_dir = target / '.claude'
    claude_dir.mkdir(exist_ok=True)

    # skills/sss/ — skopiuj SKILL.md + scripts/ żeby projekt był samowystarczalny
    # i ścieżki ".claude/skills/sss/scripts/..." w komendach slash działały
    skill_dst = claude_dir / 'skills' / 'sss'
    skill_dst.mkdir(parents=True, exist_ok=True)

    skill_md_src = Path(__file__).parent.parent / 'SKILL.md'
    if skill_md_src.exists():
        shutil.copy2(skill_md_src, skill_dst / 'SKILL.md')
        counts['skill_md'] = True

    scripts_src_dir = Path(__file__).parent  # /<skill_root>/scripts/
    scripts_dst = skill_dst / 'scripts'
    scripts_dst.mkdir(exist_ok=True)
    for f in scripts_src_dir.iterdir():
        if f.is_file() and f.suffix == '.py':
            shutil.copy2(f, scripts_dst / f.name)
            counts['scripts'] += 1

    # commands/
    cmd_dst = claude_dir / 'commands'
    cmd_dst.mkdir(exist_ok=True)
    if COMMANDS_DIR.exists():
        for f in COMMANDS_DIR.iterdir():
            if f.is_file() and f.suffix == '.md':
                shutil.copy2(f, cmd_dst / f.name)
                counts['commands'] += 1

    # hooks/
    hooks_dst = claude_dir / 'hooks'
    hooks_dst.mkdir(exist_ok=True)
    if HOOKS_DIR.exists():
        for f in HOOKS_DIR.iterdir():
            if f.is_file() and f.suffix == '.py':
                dst = hooks_dst / f.name
                shutil.copy2(f, dst)
                dst.chmod(0o755)
                counts['hooks'] += 1

    # agents/
    agents_dst = claude_dir / 'agents'
    agents_dst.mkdir(exist_ok=True)
    if AGENTS_DIR.exists():
        for f in AGENTS_DIR.iterdir():
            if f.is_file() and f.suffix == '.md':
                shutil.copy2(f, agents_dst / f.name)
                counts['agents'] += 1

    # settings.local.json — scal z istniejącym jeśli jest
    settings_template = HOOKS_DIR / 'settings.local.json'
    settings_dst = claude_dir / 'settings.local.json'
    if settings_template.exists():
        new_settings = json.loads(settings_template.read_text(encoding='utf-8'))
        if settings_dst.exists():
            try:
                existing = json.loads(settings_dst.read_text(encoding='utf-8'))
            except Exception:
                existing = {}
            # scal hooks: dodaj nasze, ale nie duplikuj
            existing_hooks = existing.setdefault('hooks', {})
            for event, entries in new_settings.get('hooks', {}).items():
                existing_hooks.setdefault(event, [])
                for entry in entries:
                    # deduplikacja po command string
                    cmds_in_entry = {
                        h.get('command') for h in entry.get('hooks', [])
                    }
                    already = False
                    for ex in existing_hooks[event]:
                        ex_cmds = {
                            h.get('command') for h in ex.get('hooks', [])
                        }
                        if cmds_in_entry & ex_cmds:
                            already = True
                            break
                    if not already:
                        existing_hooks[event].append(entry)
            settings_dst.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        else:
            shutil.copy2(settings_template, settings_dst)
        counts['settings_merged'] = True

    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--intake', required=True, help='ścieżka do intake.json')
    ap.add_argument('--target', required=True, help='katalog projektu docelowego')
    ap.add_argument('--force', action='store_true',
                    help='nadpisz istniejące pliki startowe (CLAUDE/ARCHITECTURE/CONVENTIONS/PLAN)')
    args = ap.parse_args()

    intake = json.loads(Path(args.intake).read_text(encoding='utf-8'))
    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    # ZABEZPIECZENIE: bez --force nie nadpisuj plików startowych
    if not args.force:
        existing = [f for f in STARTUP_FILES if (target / f).exists()]
        if existing:
            sys.exit(
                f'[ERR] istnieją już pliki startowe: {", ".join(existing)}\n'
                f'      Użyj --force żeby nadpisać, albo uruchom na pustym katalogu.\n'
                f'      Bez --force ryzykujesz utratę PLAN.md/CLAUDE.md/etc.'
            )

    project = intake.get('project', {})

    # 1. Kopiuj szablony i wypełnij każdy plik
    for fname in STARTUP_FILES:
        src = TEMPLATES_DIR / fname
        dst = target / fname
        text = src.read_text(encoding='utf-8')

        # CLAUDE.md ma {{project_name}} placeholder + sekcje project, stack
        if fname == 'CLAUDE.md':
            text = text.replace('{{project_name}}', project.get('title', 'Untitled'))
            text = text.replace('{{one_liner}}', project.get('one_liner', ''))
            project_block = (
                f"- name: {project.get('title', '')}\n"
                f"- type: {project.get('type', '')}\n"
                f"- client: {project.get('client', 'własny')}"
            )
            text = p.write_section(text, 'project', project_block)
            stack_lines = [s.strip() for s in project.get('stack', '').split(',') if s.strip()]
            stack_block = '\n'.join(f'- {s}' for s in stack_lines) if stack_lines else ''
            text = p.write_section(text, 'stack', stack_block)

        # PLAN.md — sekcje meta + current + next + reszta pusta
        if fname == 'PLAN.md':
            plan = intake.get('plan', {})
            meta_block = (
                f"- status: active\n"
                f"- goal: {plan.get('goal', '')}\n"
                f"- session: 1\n"
                f"- updated: {now_stamp()}"
            )
            text = p.write_section(text, 'meta', meta_block)
            current_block = (
                f"- task: {plan.get('current', '')}\n"
                f"- file: {plan.get('current_file', '-')}\n"
                f"- started: {now_stamp()}"
            )
            text = p.write_section(text, 'current', current_block)
            text = p.write_section(text, 'next', plan.get('next', ''))
            text = p.write_section(
                text, 'session_log',
                f'- session:1 | {today()} | projekt zainicjalizowany przez sss'
            )

        # Wypełnij sekcje wg FIELD_MAP
        for (intake_key, field), (target_file, section) in FIELD_MAP.items():
            if target_file != fname:
                continue
            value = intake.get(intake_key, {}).get(field, '').strip()
            if value:
                text = p.write_section(text, section, value)

        dst.write_text(text, encoding='utf-8')

    # 2. Podsumowanie max 300 znaków
    title = project.get('title', '?')
    typ = project.get('type', '?')
    client = project.get('client', 'własny')
    one_liner = project.get('one_liner', '')
    next_count = len([l for l in intake.get('plan', {}).get('next', '').splitlines() if l.strip().startswith('- [')])

    summary = (
        f'[{title}] typ={typ}, klient={client}. '
        f'{one_liner} '
        f'Zadania w next: {next_count}. '
        f'Pliki: CLAUDE/ARCHITECTURE/CONVENTIONS/PLAN.'
    )
    if len(summary) > 300:
        summary = summary[:297] + '...'

    print(f'[OK] zainicjalizowano projekt w {target}')
    print(f'[FILES] {", ".join(STARTUP_FILES)}')

    # 3. Zainstaluj .claude/ (commands + hooks + agents + scripts + SKILL.md + settings)
    counts = install_claude_dir(target)
    print(
        f'[CLAUDE_DIR] commands: {counts["commands"]}, '
        f'hooks: {counts["hooks"]}, agents: {counts["agents"]}, '
        f'scripts: {counts["scripts"]}, skill_md: {counts["skill_md"]}, '
        f'settings_merged: {counts["settings_merged"]}'
    )

    print(f'[SUMMARY ({len(summary)}/300)]')
    print(summary)


if __name__ == '__main__':
    main()
