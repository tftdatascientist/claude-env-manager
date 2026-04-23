"""
Template parser for Projektant CC module.

Handles reading/writing of structured markdown sections using HTML comment markers:
    <!-- SECTION:name --> ... <!-- /SECTION:name -->

Two section types are supported:
- dict: lines in the format `- key: value`
- list: lines in the format `- [ ] text | date` or `- [x] text | date`
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

_SECTION_RE = re.compile(
    r"<!-- SECTION:(?P<name>\w+) -->\n(?P<body>.*?)<!-- /SECTION:(?P=name) -->",
    re.DOTALL,
)
_DICT_LINE_RE = re.compile(r"^- (?P<key>[^:]+): ?(?P<value>.*)$")
_LIST_LINE_RE = re.compile(r"^- \[(?P<done>[x ])\] (?P<text>[^|]+?)(?:\s*\|\s*(?P<date>.+))?$")


# ---------------------------------------------------------------------------
# Low-level section I/O
# ---------------------------------------------------------------------------

def read_section(text: str, name: str) -> str | None:
    """Return raw body of a named section, or None if not found."""
    for m in _SECTION_RE.finditer(text):
        if m.group("name") == name:
            return m.group("body")
    return None


def write_section(text: str, name: str, body: str) -> str:
    """Replace body of a named section. Raises ValueError if section not found."""
    pattern = re.compile(
        rf"(<!-- SECTION:{re.escape(name)} -->\n).*?(<!-- /SECTION:{re.escape(name)} -->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f"Section '{name}' not found in text")
    return pattern.sub(rf"\g<1>{body}\2", text)


# ---------------------------------------------------------------------------
# Parsers / builders
# ---------------------------------------------------------------------------

def parse_dict(body: str) -> dict[str, str]:
    """Parse a dict-type section body into {key: value}."""
    result: dict[str, str] = {}
    for line in body.splitlines():
        m = _DICT_LINE_RE.match(line.strip())
        if m:
            result[m.group("key").strip()] = m.group("value").strip()
    return result


def build_dict(data: dict[str, str]) -> str:
    """Build a dict-type section body from {key: value}."""
    lines = [f"- {k}: {v}" for k, v in data.items()]
    return "\n".join(lines) + "\n" if lines else ""


def parse_list(body: str) -> list[dict]:
    """Parse a list-type section body into list of {done, text, date}."""
    result = []
    for line in body.splitlines():
        m = _LIST_LINE_RE.match(line.strip())
        if m:
            result.append({
                "done": m.group("done") == "x",
                "text": m.group("text").strip(),
                "date": (m.group("date") or "").strip(),
            })
    return result


def build_list(items: list[dict]) -> str:
    """Build a list-type section body from list of {done, text, date?}."""
    lines = []
    for item in items:
        mark = "x" if item.get("done") else " "
        text = item["text"]
        date = item.get("date", "")
        if date:
            lines.append(f"- [{mark}] {text} | {date}")
        else:
            lines.append(f"- [{mark}] {text}")
    return "\n".join(lines) + "\n" if lines else ""


# ---------------------------------------------------------------------------
# File-level helpers
# ---------------------------------------------------------------------------

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def read_section_dict(path: Path, name: str) -> dict[str, str]:
    text = read_file(path)
    body = read_section(text, name)
    if body is None:
        return {}
    return parse_dict(body)


def read_section_list(path: Path, name: str) -> list[dict]:
    text = read_file(path)
    body = read_section(text, name)
    if body is None:
        return []
    return parse_list(body)


def update_section_dict(path: Path, name: str, data: dict[str, str]) -> None:
    text = read_file(path)
    text = write_section(text, name, build_dict(data))
    write_file(path, text)


def update_section_list(path: Path, name: str, items: list[dict]) -> None:
    text = read_file(path)
    text = write_section(text, name, build_list(items))
    write_file(path, text)


# ---------------------------------------------------------------------------
# STATUS.md operations
# ---------------------------------------------------------------------------

def status_bump_session(path: Path) -> None:
    """Increment session counter and update timestamp in STATUS meta section."""
    meta = read_section_dict(path, "meta")
    meta["session"] = str(int(meta.get("session", "1")) + 1)
    meta["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    update_section_dict(path, "meta", meta)


def status_touch(path: Path) -> None:
    """Update only the timestamp in STATUS meta section."""
    meta = read_section_dict(path, "meta")
    meta["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    update_section_dict(path, "meta", meta)


def status_move_to_done(path: Path, text_fragment: str) -> bool:
    """Move first matching task from 'next' to 'done' (marks as done with today's date)."""
    today = datetime.now().strftime("%Y-%m-%d")
    next_items = read_section_list(path, "next")
    done_items = read_section_list(path, "done")

    idx = next(
        (i for i, item in enumerate(next_items) if text_fragment.lower() in item["text"].lower()),
        None,
    )
    if idx is None:
        return False

    task = next_items.pop(idx)
    task["done"] = True
    if not task.get("date"):
        task["date"] = today
    done_items.append(task)

    update_section_list(path, "next", next_items)
    update_section_list(path, "done", done_items)
    return True


def status_pop_current(path: Path) -> bool:
    """Move current task to 'done' based on 'task' field in current section."""
    current = read_section_dict(path, "current")
    task_name = current.get("task", "").strip()
    if not task_name:
        return False
    return status_move_to_done(path, task_name)


# ---------------------------------------------------------------------------
# PLAN.md operations
# ---------------------------------------------------------------------------

def plan_check_step(path: Path, text_fragment: str) -> bool:
    """Mark first matching step as done."""
    steps = read_section_list(path, "steps")
    idx = next(
        (i for i, s in enumerate(steps) if text_fragment.lower() in s["text"].lower()),
        None,
    )
    if idx is None:
        return False
    steps[idx]["done"] = True
    if not steps[idx].get("date"):
        steps[idx]["date"] = datetime.now().strftime("%Y-%m-%d")
    update_section_list(path, "steps", steps)
    return True


def plan_set_status(path: Path, status: str) -> None:
    """Set plan status in PLAN meta section (e.g. 'active', 'done', 'cancelled')."""
    meta = read_section_dict(path, "meta")
    meta["status"] = status
    meta["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    update_section_dict(path, "meta", meta)


# ---------------------------------------------------------------------------
# Template instantiation
# ---------------------------------------------------------------------------

def create_from_template(template_name: str, dest_path: Path, overrides: dict[str, dict] | None = None) -> None:
    """
    Create a project file from a template.

    Args:
        template_name: filename without extension, e.g. 'STATUS'
        dest_path: destination file path
        overrides: mapping of {section_name: dict_data or list_data}
    """
    src = TEMPLATES_DIR / f"{template_name}.md"
    if not src.exists():
        raise FileNotFoundError(f"Template not found: {src}")

    text = src.read_text(encoding="utf-8")

    if overrides:
        for section, data in overrides.items():
            if isinstance(data, dict):
                text = write_section(text, section, build_dict(data))
            elif isinstance(data, list):
                # list[str] → simple bullet list; list[dict] → task list
                if data and isinstance(data[0], str):
                    body = "".join(f"- {item}\n" for item in data)
                    text = write_section(text, section, body)
                else:
                    text = write_section(text, section, build_list(data))
            elif isinstance(data, str):
                text = write_section(text, section, data + "\n" if data else "")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:  # pragma: no cover
    """
    Usage:
        python template_parser.py create STATUS /path/to/project
        python template_parser.py read STATUS meta /path/to/project/STATUS.md
        python template_parser.py bump-session /path/to/project/STATUS.md
        python template_parser.py touch /path/to/project/STATUS.md
        python template_parser.py move-done <fragment> /path/to/project/STATUS.md
        python template_parser.py check-step <fragment> /path/to/project/PLAN.md
        python template_parser.py plan-status <status> /path/to/project/PLAN.md
    """
    args = sys.argv[1:]
    if not args:
        print(_cli.__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "create":
        template, dest_dir = args[1], Path(args[2])
        dest_path = dest_dir / f"{template}.md"
        create_from_template(template, dest_path)
        print(f"Created {dest_path}")

    elif cmd == "read":
        template_type, section, file_path = args[1], args[2], Path(args[3])
        if template_type in ("dict", "STATUS", "PLAN", "CLAUDE", "ARCHITECTURE"):
            data = read_section_dict(file_path, section)
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            items = read_section_list(file_path, section)
            for item in items:
                mark = "x" if item["done"] else " "
                date = f" | {item['date']}" if item.get("date") else ""
                print(f"[{mark}] {item['text']}{date}")

    elif cmd == "bump-session":
        status_bump_session(Path(args[1]))
        print("Session bumped")

    elif cmd == "touch":
        status_touch(Path(args[1]))
        print("Timestamp updated")

    elif cmd == "move-done":
        fragment, file_path = args[1], Path(args[2])
        ok = status_move_to_done(file_path, fragment)
        print("Moved" if ok else "Not found")

    elif cmd == "check-step":
        fragment, file_path = args[1], Path(args[2])
        ok = plan_check_step(file_path, fragment)
        print("Checked" if ok else "Not found")

    elif cmd == "plan-status":
        status_val, file_path = args[1], Path(args[2])
        plan_set_status(file_path, status_val)
        print(f"Plan status set to '{status_val}'")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
