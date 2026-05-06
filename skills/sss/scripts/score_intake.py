"""score_intake.py — orchestracja zapisu ocen z panelu sędziów do PS.md.

Skrypt jest **deterministycznym writerem** — sam nie wywołuje sędziów, bo to
robi główny Claude przez Task tool. Skrypt służy do:

1. Zainicjalizowania PS.md z oryginalnym promptem (mode=init)
2. Zapisania wyników score_competence (mode=write_competence)
3. Zapisania pytań i odpowiedzi rund 1/2/3 (mode=write_round)
4. Zapisania wyników score_architecture (mode=write_architecture)
5. Zapisania difficulty score (mode=write_difficulty)
6. Wygenerowania finalnego summary (mode=summarize)

Każdy mode czyta JSON z stdin (struktura niżej) i modyfikuje PS.md
przez markery SECTION.

Użycie:
    echo '{"prompt": "...", "title": "..."}' | \
        python score_intake.py --mode init --target .

    echo '[{"judge":"judge-business","score":7,"comment":"...","advice":"..."}, ...]' | \
        python score_intake.py --mode write_competence --target .
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402


THRESHOLD = 1000
JUDGES = ['judge-business', 'judge-architect', 'judge-pm', 'judge-devops', 'judge-devil']


def now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def ensure_ps(target: Path, payload: dict) -> Path:
    """Tworzy PS.md z template jeśli nie istnieje."""
    ps_path = target / 'PS.md'
    if ps_path.exists():
        return ps_path

    template_dir = Path(__file__).parent.parent / 'assets' / 'templates'
    tmpl = (template_dir / 'PS.md').read_text(encoding='utf-8')

    prompt = (payload.get('prompt') or '').strip()
    title = (payload.get('title') or 'untitled').strip()
    plen = len(prompt)
    status = 'scored' if plen >= THRESHOLD else 'skipped_too_short'

    filled = (
        tmpl
        .replace('{{title}}', title)
        .replace('{{created}}', now_iso())
        .replace('{{prompt_length}}', str(plen))
        .replace('{{status}}', status)
        .replace('{{prompt}}', prompt or '(brak — projekt zainicjowany bez opisowego promptu)')
    )
    ps_path.write_text(filled, encoding='utf-8')
    return ps_path


def fmt_judge_block(j: dict) -> str:
    """Formatuje wynik jednego sędziego jako blok markdown."""
    return (
        f"### {j['judge']}\n"
        f"- score: {j.get('score', '-')}\n"
        f"- comment: {j.get('comment', '-').strip()}\n"
        f"- advice: {j.get('advice', '-').strip()}"
    )


def fmt_aggregate(judges_results: list[dict]) -> str:
    scores = [int(j['score']) for j in judges_results if j.get('score') is not None]
    if not scores:
        return (
            "### aggregate\n"
            "- mean: -\n- median: -\n- distribution: -\n- top_advice: -"
        )
    mean_s = round(statistics.mean(scores), 2)
    med_s = statistics.median(scores)
    dist = ', '.join(str(s) for s in scores)

    # top_advice: najczęstszy temat z `advice` — heurystyka prosta, weź advice od
    # sędziego z najniższym score (najwięcej do poprawy)
    worst = min(judges_results, key=lambda j: int(j.get('score', 10)))
    top = worst.get('advice', '-').strip()
    src = worst.get('judge', '-')

    return (
        "### aggregate\n"
        f"- mean: {mean_s}\n"
        f"- median: {med_s}\n"
        f"- distribution: [{dist}]\n"
        f"- top_advice: ({src}) {top}"
    )


def write_score_section(ps_text: str, section: str, judges_results: list[dict]) -> str:
    """Zastępuje całą sekcję `score_competence` lub `score_architecture`
    blokami sędziów + aggregate."""
    blocks = []
    by_judge = {j['judge']: j for j in judges_results}
    for jname in JUDGES:
        if jname in by_judge:
            blocks.append(fmt_judge_block(by_judge[jname]))
        else:
            blocks.append(
                f"### {jname}\n- score: -\n- comment: -\n- advice: -"
            )
    blocks.append(fmt_aggregate(judges_results))
    return p.write_section(ps_text, section, '\n\n'.join(blocks))


def write_round(ps_text: str, round_num: int, payload: dict) -> str:
    """Zapisuje rundę pytań — questions[] + optional proposals_log."""
    section = f'round_{round_num}'
    questions = payload.get('questions', []) or []
    proposals = payload.get('proposals_log', '') or ''

    lines = []
    if round_num == 1:
        lines.append('### Round 1 (statyczna, główny Claude)')
    else:
        lines.append(f'### Round {round_num} (panel sędziów → orchestrator wybiera 3 z 15)')

    for i, q in enumerate(questions, 1):
        text = q.get('q', '-')
        ans = q.get('a', '-')
        lines.append(f'- Q{i}: {text}')
        if round_num > 1 and q.get('source_judge'):
            lines.append(f'  - source_judge: {q["source_judge"]}')
        lines.append(f'  - A: {ans}')

    if round_num > 1 and proposals:
        lines.append(f'- proposals_log: {proposals}')

    return p.write_section(ps_text, section, '\n'.join(lines))


def write_difficulty(ps_text: str, payload: dict) -> str:
    score = payload.get('score', '-')
    reasoning = (payload.get('reasoning') or '-').strip()
    risks = (payload.get('main_risks') or '-').strip()
    body = (
        f'- score: {score}\n'
        f'- reasoning: {reasoning}\n'
        f'- main_risks: {risks}'
    )
    return p.write_section(ps_text, 'score_difficulty', body)


def summarize(ps_text: str) -> str:
    """Generuje sekcję summary na podstawie istniejących sekcji."""
    comp = p.read_section(ps_text, 'score_competence')
    arch = p.read_section(ps_text, 'score_architecture')
    diff = p.read_section(ps_text, 'score_difficulty')

    def extract_mean(section_text: str) -> str:
        for line in section_text.splitlines():
            line = line.strip()
            if line.startswith('- mean:'):
                return line.split(':', 1)[1].strip()
        return '-'

    def extract_diff_score(diff_text: str) -> str:
        for line in diff_text.splitlines():
            line = line.strip()
            if line.startswith('- score:'):
                return line.split(':', 1)[1].strip()
        return '-'

    def extract_advices(section_text: str) -> list[str]:
        # zbierz wszystkie linie `- advice:` (5 sędziów)
        out = []
        for line in section_text.splitlines():
            ls = line.strip()
            if ls.startswith('- advice:'):
                out.append(ls.split(':', 1)[1].strip())
        return out

    comp_mean = extract_mean(comp)
    arch_mean = extract_mean(arch)
    diff_score = extract_diff_score(diff)

    advices = extract_advices(comp) + extract_advices(arch)
    advices = [a for a in advices if a and a != '-']
    # weź 3 pierwsze unikalne
    seen = set()
    top3 = []
    for a in advices:
        key = a[:80]
        if key not in seen:
            seen.add(key)
            top3.append(a)
        if len(top3) == 3:
            break
    while len(top3) < 3:
        top3.append('-')

    body = (
        f'- Business+Tech competence: {comp_mean}/10\n'
        f'- Architecture: {arch_mean}/10\n'
        f'- Difficulty: {diff_score}/10\n'
        '- Top 3 actionable advices:\n'
        f'  1. {top3[0]}\n'
        f'  2. {top3[1]}\n'
        f'  3. {top3[2]}'
    )
    return p.write_section(ps_text, 'summary', body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=True, choices=[
        'init', 'write_competence', 'write_round',
        'write_architecture', 'write_difficulty', 'summarize',
    ])
    ap.add_argument('--target', default='.')
    ap.add_argument('--round', type=int, choices=[1, 2, 3], help='dla mode=write_round')
    args = ap.parse_args()

    target = Path(args.target)

    # init nie wymaga stdin payload jeśli już istnieje PS.md, ale zwykle wymaga
    if args.mode == 'init':
        try:
            payload = json.load(sys.stdin)
        except Exception:
            payload = {}
        ps_path = ensure_ps(target, payload)
        plen = len((payload.get('prompt') or '').strip())
        msg = (
            f'[OK] PS.md zainicjalizowany ({plen} znaków promptu, próg {THRESHOLD}).'
        )
        if plen < THRESHOLD and plen > 0:
            missing = THRESHOLD - plen
            msg += (
                f'\n[WARN] prompt poniżej progu — brakuje {missing} znaków '
                'do oceniania przez panel sędziów. Sekcje score_* zostaną puste.'
            )
        print(msg)
        return

    ps_path = target / 'PS.md'
    if not ps_path.exists():
        sys.exit(f'[ERR] brak PS.md w {target} — najpierw mode=init')

    ps_text = p.read_file(ps_path)

    # summarize nie wymaga payload z stdin
    if args.mode == 'summarize':
        ps_text = summarize(ps_text)
        p.write_file(ps_path, ps_text)
        print('[OK] summary wygenerowane.')
        return

    payload = json.load(sys.stdin)

    if args.mode == 'write_competence':
        ps_text = write_score_section(ps_text, 'score_competence', payload)
        print('[OK] score_competence zapisane.')
    elif args.mode == 'write_round':
        if not args.round:
            sys.exit('[ERR] --round wymagany dla write_round')
        ps_text = write_round(ps_text, args.round, payload)
        print(f'[OK] round_{args.round} zapisana.')
    elif args.mode == 'write_architecture':
        ps_text = write_score_section(ps_text, 'score_architecture', payload)
        print('[OK] score_architecture zapisane.')
    elif args.mode == 'write_difficulty':
        ps_text = write_difficulty(ps_text, payload)
        print('[OK] score_difficulty zapisane.')

    p.write_file(ps_path, ps_text)


if __name__ == '__main__':
    main()
