"""Wiki renderer — parsuje hooks-guide.jsx i generuje HTML dla QTextBrowser."""

from __future__ import annotations

import re
from pathlib import Path

JSX_PATH = Path(__file__).resolve().parents[3] / "hooker" / "hooks-guide.jsx"

# ------------------------------------------------------------------ parser

def _extract_array_block(text: str, var_name: str) -> str:
    """Zwraca zawartość const VAR = [...] jako string (z nawiasami)."""
    m = re.search(rf'const {var_name}\s*=\s*\[', text)
    if not m:
        return "[]"
    start = m.end() - 1
    depth = 0
    for i, ch in enumerate(text[start:]):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[start : start + i + 1]
    return "[]"


def _split_top_objects(block: str) -> list[str]:
    """Dzieli blok [...] na listę tekstów pojedynczych obiektów {}."""
    inner = block[1:-1]  # strip [ ]
    objects: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(inner):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                objects.append(inner[start : i + 1])
                start = -1
    return objects


def _str_field(obj: str, field: str) -> str:
    m = re.search(rf"\b{field}:\s*'([^']*)'", obj)
    if not m:
        m = re.search(rf'\b{field}:\s*"([^"]*)"', obj)
    return m.group(1) if m else ""


def _arr_field(obj: str, field: str) -> list[str]:
    m = re.search(rf'\b{field}:\s*\[([^\]]*)\]', obj, re.DOTALL)
    if not m:
        return []
    return re.findall(r"'([^']+)'", m.group(1))


def _template_field(obj: str, field: str) -> str:
    m = re.search(rf'\b{field}:\s*`(.*?)`', obj, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_objects(block: str, fields: list[str], arr_fields: list[str] | None = None,
                   tpl_fields: list[str] | None = None) -> list[dict]:
    arr_fields = arr_fields or []
    tpl_fields = tpl_fields or []
    result = []
    for obj in _split_top_objects(block):
        d: dict = {}
        for f in fields:
            d[f] = _str_field(obj, f)
        for f in arr_fields:
            d[f] = _arr_field(obj, f)
        for f in tpl_fields:
            d[f] = _template_field(obj, f)
        if any(d.values()):
            result.append(d)
    return result


def parse_jsx(path: Path = JSX_PATH) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")

    sections_block = _extract_array_block(text, "SECTIONS")
    sections = _parse_objects(sections_block, ["id", "name", "hint"])

    events_block = _extract_array_block(text, "EVENTS")
    events = _parse_objects(
        events_block,
        ["id", "cat", "cadence", "fires", "example", "important", "version"],
        arr_fields=["payload", "control"],
        tpl_fields=["config"],
    )

    handlers_block = _extract_array_block(text, "HANDLERS")
    handlers = _parse_objects(
        handlers_block,
        ["id", "name", "color", "tagline", "mechanics", "when", "important"],
        arr_fields=["pros", "cons"],
        tpl_fields=["config"],
    )

    mechanisms_block = _extract_array_block(text, "CONTROL_MECHANISMS")
    mechanisms = _parse_objects(
        mechanisms_block,
        ["id", "name", "color", "short", "desc", "where", "realWorld"],
        arr_fields=["flow"],
        tpl_fields=["output"],
    )

    patterns_block = _extract_array_block(text, "PATTERNS")
    patterns = _parse_objects(
        patterns_block,
        ["id", "name", "color", "problem", "solution", "impact"],
        tpl_fields=["config"],
    )

    return {
        "sections": sections,
        "events": events,
        "handlers": handlers,
        "mechanisms": mechanisms,
        "patterns": patterns,
    }


# ------------------------------------------------------------------ renderer

_CSS = """
body { background:#0f172a; color:#cbd5e1; font-family:sans-serif; font-size:13px; margin:16px; }
h1 { color:#f8fafc; font-size:18px; border-bottom:1px solid #334155; padding-bottom:6px; }
h2 { color:#94a3b8; font-size:15px; margin-top:24px; border-bottom:1px solid #1e293b; padding-bottom:4px; }
h3 { font-size:13px; margin:12px 0 4px 0; }
p  { margin:4px 0 8px 0; line-height:1.5; }
pre { background:#1e293b; color:#a3e635; padding:8px; border-radius:4px; font-size:11px;
      white-space:pre-wrap; word-break:break-all; margin:6px 0; border:1px solid #334155; }
ul  { margin:4px 0; padding-left:20px; }
li  { margin:2px 0; line-height:1.4; }
.badge { display:inline-block; padding:1px 6px; border-radius:3px; font-size:11px; font-weight:bold; }
.card { background:#1e293b; border:1px solid #334155; border-radius:6px;
        padding:10px 12px; margin:10px 0; }
.tag { color:#64748b; font-size:11px; }
.imp { color:#f97316; font-size:11px; }
.anchor { }
"""

_CAT_COLORS = {
    "session": "#a3e635", "turn": "#22d3ee", "tool": "#fbbf24",
    "subagent": "#c084fc", "mcp": "#f472b6", "compact": "#fb923c",
}


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section_anchor(sid: str) -> str:
    return f'<a name="{sid}"></a>'


def _render_intro(data: dict) -> str:
    return f"""
{_section_anchor("intro")}
<h1>Hooks Guide — Claude Code</h1>
<p>Interaktywna dokumentacja systemu hooków CC. Hooki pozwalają intercept każdego zdarzenia
w cyklu życia sesji: przed/po wywołaniu narzędzia, przy starcie/zakończeniu sesji, przy wysłaniu
promptu, przy kompresji kontekstu i wielu innych.</p>

<div class="card">
  <b style="color:#a3e635">Czym są hooki?</b>
  <p>Hooki to skrypty shell, endpointy HTTP, prompty lub sub-agenci uruchamiani przez CC
  w odpowiedzi na zdarzenia. Mogą <b>blokować</b> akcje, <b>modyfikować</b> argumenty,
  <b>wstrzykiwać kontekst</b> i <b>kontrolować flow</b> sesji.</p>
  <b style="color:#22d3ee">Format konfiguracji (settings.json)</b>
  <pre>{{"hooks": {{"PreToolUse": [{{"matcher": "Bash", "hooks": [{{"type": "command", "command": "/path/to/hook.py"}}]}}]}}}}</pre>
</div>

<p><b>Sekcje w tym przewodniku:</b></p>
<ul>
  <li><a href="#events"><b>Lifecycle Events</b></a> — 21 zdarzeń w cyklu życia sesji CC</li>
  <li><a href="#handlers"><b>Handler Types</b></a> — command, http, prompt, agent</li>
  <li><a href="#control"><b>Mechanizmy kontroli</b></a> — block, modify, inject, flow</li>
  <li><a href="#patterns"><b>Zaawansowane wzorce</b></a> — produkcyjne use-case'y</li>
</ul>
"""


def _render_events(events: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = {}
    for e in events:
        by_cat.setdefault(e.get("cat", "?"), []).append(e)

    cat_labels = {
        "session": "Session lifecycle", "turn": "Turn cycle",
        "tool": "Tool execution", "subagent": "Subagent / Skills",
        "mcp": "MCP integration", "compact": "Context management",
    }

    html = f"{_section_anchor('events')}<h1>Lifecycle Events</h1>\n"

    for cat, label in cat_labels.items():
        cat_events = by_cat.get(cat, [])
        if not cat_events:
            continue
        color = _CAT_COLORS.get(cat, "#94a3b8")
        html += f'<h2 style="color:{color}">{label} ({len(cat_events)})</h2>\n'

        for ev in cat_events:
            eid = ev.get("id", "?")
            color_badge = _CAT_COLORS.get(cat, "#94a3b8")
            html += f'<a name="ev_{eid}"></a>\n'
            html += f'<div class="card">\n'
            html += f'<h3><span style="color:{color_badge}"><b>{_esc(eid)}</b></span>'
            if ev.get("version"):
                html += f' <span class="tag"> {_esc(ev["version"])}</span>'
            html += f'</h3>\n'
            if ev.get("fires"):
                html += f'<p><b>Kiedy:</b> {_esc(ev["fires"])}</p>\n'
            if ev.get("cadence"):
                html += f'<p class="tag">Cadence: {_esc(ev["cadence"])}</p>\n'
            if ev.get("payload"):
                html += "<p><b>Payload:</b></p><ul>"
                for item in ev["payload"]:
                    html += f"<li><code>{_esc(item)}</code></li>"
                html += "</ul>"
            if ev.get("control"):
                html += "<p><b>Możliwości kontroli:</b></p><ul>"
                for item in ev["control"]:
                    html += f"<li>{_esc(item)}</li>"
                html += "</ul>"
            if ev.get("example"):
                html += f'<p><b>Przykład:</b> {_esc(ev["example"])}</p>\n'
            if ev.get("important"):
                html += f'<p class="imp">⚠ {_esc(ev["important"])}</p>\n'
            if ev.get("config"):
                html += f'<pre>{_esc(ev["config"])}</pre>\n'
            html += "</div>\n"

    return html


def _render_handlers(handlers: list[dict]) -> str:
    html = f"{_section_anchor('handlers')}<h1>Handler Types</h1>\n"
    html += "<p>Cztery sposoby reakcji hooka na zdarzenie CC.</p>\n"

    for h in handlers:
        color = h.get("color", "#94a3b8")
        hid = _esc(h.get("id", ""))
        html += f'<a name="h_{hid}"></a>\n'
        html += f'<div class="card">\n'
        html += f'<h3><b style="color:{color}">{_esc(h.get("name", "?"))}</b></h3>\n'
        if h.get("tagline"):
            html += f'<p><i>{_esc(h["tagline"])}</i></p>\n'
        if h.get("mechanics"):
            html += f'<p>{_esc(h["mechanics"])}</p>\n'
        if h.get("pros"):
            html += "<p><b style='color:#a3e635'>Zalety:</b></p><ul>"
            for item in h["pros"]:
                html += f"<li>{_esc(item)}</li>"
            html += "</ul>"
        if h.get("cons"):
            html += "<p><b style='color:#f43f5e'>Wady:</b></p><ul>"
            for item in h["cons"]:
                html += f"<li>{_esc(item)}</li>"
            html += "</ul>"
        if h.get("when"):
            html += f'<p><b>Kiedy używać:</b> {_esc(h["when"])}</p>\n'
        if h.get("important"):
            html += f'<p class="imp">⚠ {_esc(h["important"])}</p>\n'
        if h.get("config"):
            html += f'<pre>{_esc(h["config"])}</pre>\n'
        html += "</div>\n"

    return html


def _render_mechanisms(mechanisms: list[dict]) -> str:
    html = f"{_section_anchor('control')}<h1>Mechanizmy kontroli</h1>\n"
    html += "<p>Co hook może powiedzieć CC.</p>\n"

    for m in mechanisms:
        color = m.get("color", "#94a3b8")
        html += f'<div class="card">\n'
        html += f'<h3><b style="color:{color}">{_esc(m.get("name", "?"))}</b>'
        if m.get("short"):
            html += f' <span class="tag">— {_esc(m["short"])}</span>'
        html += "</h3>\n"
        if m.get("desc"):
            html += f'<p>{_esc(m["desc"])}</p>\n'
        if m.get("where"):
            html += f'<p class="tag"><b>Gdzie działa:</b> {_esc(m["where"])}</p>\n'
        if m.get("flow"):
            html += "<p><b>Flow:</b></p><ul>"
            for step in m["flow"]:
                html += f"<li>{_esc(step)}</li>"
            html += "</ul>"
        if m.get("realWorld"):
            html += f'<p><b>Real-world:</b> {_esc(m["realWorld"])}</p>\n'
        if m.get("output"):
            html += f'<pre>{_esc(m["output"])}</pre>\n'
        html += "</div>\n"

    return html


def _render_patterns(patterns: list[dict]) -> str:
    html = f"{_section_anchor('patterns')}<h1>Zaawansowane wzorce</h1>\n"
    html += "<p>Produkcyjne use-case'y dla 4×CC setup.</p>\n"

    for p in patterns:
        color = p.get("color", "#94a3b8")
        html += f'<div class="card">\n'
        html += f'<h3><b style="color:{color}">{_esc(p.get("name", "?"))}</b></h3>\n'
        if p.get("problem"):
            html += f'<p><b style="color:#f43f5e">Problem:</b> {_esc(p["problem"])}</p>\n'
        if p.get("solution"):
            html += f'<p><b style="color:#a3e635">Rozwiązanie:</b> {_esc(p["solution"])}</p>\n'
        if p.get("impact"):
            html += f'<p><b style="color:#22d3ee">Impact:</b> {_esc(p["impact"])}</p>\n'
        if p.get("config"):
            html += f'<pre>{_esc(p["config"])}</pre>\n'
        html += "</div>\n"

    return html


def render_html(jsx_path: Path = JSX_PATH) -> str:
    """Zwraca pełny HTML dokumentu wiki."""
    data = parse_jsx(jsx_path)
    if not data:
        return "<html><body><p style='color:#ef4444'>Nie znaleziono hooks-guide.jsx</p></body></html>"

    body = (
        _render_intro(data)
        + _render_events(data.get("events", []))
        + _render_handlers(data.get("handlers", []))
        + _render_mechanisms(data.get("mechanisms", []))
        + _render_patterns(data.get("patterns", []))
    )

    return f"<html><head><style>{_CSS}</style></head><body>{body}</body></html>"
