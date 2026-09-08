"""
Password strength rules, shared by registration and password-reset.

Rules (all required):
  - at least 7 characters long
  - at least one uppercase letter (A-Z)
  - at least one digit (0-9)
  - at least one special character (anything that isn't a letter or digit)

The same rule set is mirrored in static/js/password_strength.js so the
user gets live feedback in the browser as they type — but the server
always re-checks these rules before accepting any password, since
client-side JS can be bypassed.
"""
import re

MIN_LENGTH = 7

_UPPERCASE_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"[0-9]")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def check_password_requirements(password: str) -> dict:
    """Return a dict of which individual requirements are met, e.g.
    {"length": True, "uppercase": False, "digit": True, "special": True}."""
    password = password or ""
    return {
        "length": len(password) >= MIN_LENGTH,
        "uppercase": bool(_UPPERCASE_RE.search(password)),
        "digit": bool(_DIGIT_RE.search(password)),
        "special": bool(_SPECIAL_RE.search(password)),
    }


def validate_password_strength(password: str):
    """Return (is_valid, [list of human-readable missing requirements])."""
    checks = check_password_requirements(password)
    messages = {
        "length": f"at least {MIN_LENGTH} characters",
        "uppercase": "at least one uppercase letter (A-Z)",
        "digit": "at least one number (0-9)",
        "special": "at least one special character (e.g. ! @ # $ %)",
    }
    missing = [messages[key] for key, ok in checks.items() if not ok]
    return (len(missing) == 0), missing
