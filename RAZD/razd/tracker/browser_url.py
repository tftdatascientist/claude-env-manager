from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(
    r"(?<=[?&])("
    r"token|access_token|id_token|refresh_token|api_key|apikey|key|secret|password|passwd|pwd|auth|bearer"
    r")=[^&]+",
    re.IGNORECASE,
)

BROWSER_PROCESSES = frozenset({"chrome.exe", "msedge.exe"})


def get_browser_url(process_name: str) -> str | None:
    """Wyciąga URL z paska adresu Chrome/Edge przez UI Automation. Zwraca None gdy niedostępne."""
    if process_name.lower() not in BROWSER_PROCESSES:
        return None
    try:
        import uiautomation as auto

        # Szukamy kontrolki paska adresu (Edit z nazwą "Address and search bar" lub podobną)
        ctrl = auto.GetForegroundControl()
        if ctrl is None:
            return None

        edit = _find_address_bar(ctrl)
        if edit is None:
            return None

        url = edit.GetValuePattern().Value
        return sanitize_url(url) if url else None
    except Exception:
        return None


def _find_address_bar(root) -> object | None:
    import uiautomation as auto

    for name in ("Address and search bar", "Pasek adresu i wyszukiwania"):
        ctrl = root.EditControl(Name=name, searchDepth=8)
        if ctrl.Exists(0):
            return ctrl

    # Fallback: każda kontrolka Edit w toolbarze z URL-em
    edit = root.EditControl(searchDepth=8)
    if edit.Exists(0):
        val = edit.GetValuePattern().Value
        if val and (val.startswith("http://") or val.startswith("https://")):
            return edit
    return None


def sanitize_url(url: str) -> str:
    """Usuwa tokeny i hasła z query string przed zapisem."""
    return _TOKEN_PATTERN.sub(lambda m: m.group(0).split("=")[0] + "=***", url)
