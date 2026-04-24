"""
pcc_unpack.py — rozpakowanie JSON z wizarda do 4 plików .md w katalogu projektu.

Format wejściowy (JSON):
{
  "project": {"name": ..., "type": ..., "client": ..., "stack": ...},
  "architecture": {"overview": ..., "components": [...], "decisions": [...], ...},
  "plan": {"goal": ..., "session": ..., "tasks": [...], "current_task": ...},
  "conventions": {"naming": ..., "code_style": ..., "anti_patterns": [...]}
}

Użycie:
  python src/pcc_unpack.py payload.json [--out ./]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


def _render_claude(data: dict) -> str:
    p = data.get("project", {})
    return f"""\
<!-- CLAUDE v1.1 -->

# {p.get('name', 'Projekt')}

## Imports
<!-- SECTION:imports -->
@ARCHITECTURE.md
@PLAN.md
@CONVENTIONS.md
<!-- /SECTION:imports -->

## Project
<!-- SECTION:project -->
- name: {p.get('name', '')}
- type: {p.get('type', '')}
- client: {p.get('client', '')}
- stack: {p.get('stack', '')}
<!-- /SECTION:project -->

## Off Limits
<!-- SECTION:off_limits -->
- nie edytuj CLAUDE.md, ARCHITECTURE.md ani CONVENTIONS.md ręcznie w trakcie sesji
- nie pomijaj walidacji pythonowego skryptu kontrolnego przy zmianach plików MD
- nie zapisuj informacji poza PLAN.md podczas aktywnej rundy
<!-- /SECTION:off_limits -->

## Specifics
<!-- SECTION:specifics -->
- PLAN.md to jedyny plik edytowalny w trakcie rundy
- po zakończeniu rundy PLAN.md jest czyszczony; informacje segregowane do odpowiednich MD przez SKILL
- subagenci ingerują tylko przy awarii skryptu deterministycznego
<!-- /SECTION:specifics -->
"""


def _render_architecture(data: dict) -> str:
    a = data.get("architecture", {})
    components = "\n".join(f"- {c}" for c in a.get("components", []))
    decisions = "\n".join(
        f"- [ ] {d}" if not str(d).startswith("[") else f"- {d}"
        for d in a.get("decisions", [])
    )
    deps = "\n".join(f"- {d}" for d in a.get("external_deps", []))
    constraints = "\n".join(f"- {c}" for c in a.get("constraints", []))
    return f"""\
## Overview
{a.get('overview', '')}
## Components
{components}
## Data Flow
{a.get('data_flow', '')}
## External Deps
{deps}
## Decisions
{decisions}
## Constraints
{constraints}
"""


def _render_plan(data: dict) -> str:
    p = data.get("plan", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tasks = "\n".join(f"- [ ] {t}" for t in p.get("tasks", []))
    current = p.get("current_task", "")
    return f"""\
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: {p.get('goal', '')}
- session: {p.get('session', 1)}
- updated: {now}
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: {current}
- file:
- started: {now}
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
{tasks}
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- {now} | projekt rozpakowany przez pcc_unpack.py
<!-- /SECTION:session_log -->
"""


def _render_conventions(data: dict) -> str:
    c = data.get("conventions", {})
    anti = "\n".join(f"- {a}" for a in c.get("anti_patterns", []))
    return f"""\
## Naming
{c.get('naming', '')}
## File Layout
{c.get('file_layout', '')}
## Code Style
{c.get('code_style', '')}
## Commit Style
{c.get('commit_style', '')}
## Testing
{c.get('testing', '')}
## Anti Patterns
{anti}
"""


RENDERERS = {
    "CLAUDE.md": _render_claude,
    "ARCHITECTURE.md": _render_architecture,
    "PLAN.md": _render_plan,
    "CONVENTIONS.md": _render_conventions,
}


@app.command()
def unpack(
    payload: Path = typer.Argument(..., help="Ścieżka do pliku JSON z wizarda"),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Katalog docelowy"),
) -> None:
    if not payload.exists():
        typer.echo(f"ERROR: plik {payload} nie istnieje.", err=True)
        raise typer.Exit(1)

    data = json.loads(payload.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)

    for filename, renderer in RENDERERS.items():
        content = renderer(data)
        target = out / filename
        target.write_text(content, encoding="utf-8")
        typer.echo(f"  → {target}")

    typer.echo("OK: 4 pliki MD wygenerowane.")


if __name__ == "__main__":
    app()
