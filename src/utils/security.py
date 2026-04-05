"""Masking sensitive values in credentials and environment variables."""

import re

SENSITIVE_KEY_PATTERNS = re.compile(
    r"(key|token|secret|password|credential|auth)", re.IGNORECASE
)


def mask_value(value: str) -> str:
    """Mask a sensitive string, showing only prefix and last 4 chars."""
    if len(value) <= 8:
        return "****"
    return value[:6] + "..." + "****"


def mask_dict(data: dict, parent_key: str = "") -> dict:
    """Recursively mask sensitive values in a dict."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = mask_dict(value, key)
        elif isinstance(value, str) and SENSITIVE_KEY_PATTERNS.search(key):
            result[key] = mask_value(value)
        else:
            result[key] = value
    return result
