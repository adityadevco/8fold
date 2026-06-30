"""Pure, deterministic normalization functions.

Every function here either returns a normalized value or None. They never
raise on bad input -- "unknown values become null, never invented" is a
hard constraint from the spec, so these are defensive by design.
"""
from __future__ import annotations

import re
from datetime import datetime

_PHONE_DIGITS = re.compile(r"\d+")

# Minimal country-calling-code -> ISO-3166 alpha-2 map, enough for the
# sample data. In production this would be a full libphonenumber table.
_CALLING_CODE_TO_ISO = {
    "91": "IN", "1": "US", "44": "GB", "61": "AU", "65": "SG", "971": "AE",
}

_COUNTRY_NAME_TO_ISO = {
    "india": "IN", "united states": "US", "usa": "US", "u.s.": "US",
    "united kingdom": "GB", "uk": "GB", "australia": "AU", "singapore": "SG",
    "canada": "CA", "germany": "DE",
}

# Canonical skill name -> set of aliases (lowercased) it should absorb.
_SKILL_CANON = {
    "Python": {"python", "python3", "py"},
    "JavaScript": {"javascript", "js", "es6"},
    "TypeScript": {"typescript", "ts"},
    "React": {"react", "react.js", "reactjs"},
    "Node.js": {"node", "node.js", "nodejs"},
    "SQL": {"sql", "postgresql", "postgres", "mysql"},
    "Machine Learning": {"machine learning", "ml"},
    "Deep Learning": {"deep learning", "dl"},
    "Natural Language Processing": {"nlp", "natural language processing"},
    "TensorFlow": {"tensorflow", "tf"},
    "PyTorch": {"pytorch", "torch"},
    "AWS": {"aws", "amazon web services"},
    "Docker": {"docker"},
    "Kubernetes": {"kubernetes", "k8s"},
    "FastAPI": {"fastapi"},
    "Java": {"java"},
    "C++": {"c++", "cpp"},
    "Go": {"go", "golang"},
}
_ALIAS_TO_CANON = {
    alias: canon for canon, aliases in _SKILL_CANON.items() for alias in aliases
}


def normalize_phone(raw: str | None, default_country: str = "IN") -> str | None:
    """Best-effort E.164 normalization. Returns None if too short/garbage."""
    if not raw:
        return None
    plus = raw.strip().startswith("+")
    digits = "".join(_PHONE_DIGITS.findall(raw))
    if not digits:
        return None
    if plus:
        return f"+{digits}"
    # No leading +: guess based on length / known calling codes.
    if len(digits) == 10:
        cc = "91" if default_country == "IN" else "1"
        return f"+{cc}{digits}"
    for cc in sorted(_CALLING_CODE_TO_ISO, key=len, reverse=True):
        if digits.startswith(cc) and len(digits) - len(cc) >= 7:
            return f"+{digits}"
    if 8 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def normalize_country(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    return _COUNTRY_NAME_TO_ISO.get(raw.lower())


_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) if m}
_MONTH_FULL = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def normalize_date(raw: str | None) -> str | None:
    """Normalize a date-ish string to YYYY-MM. Returns 'present' as-is."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ("present", "current", "now", "ongoing"):
        return "present"
    fmts = ["%Y-%m-%d", "%Y-%m", "%m/%Y", "%d/%m/%Y", "%B %Y", "%b %Y"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(raw, fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            continue
    m = re.match(r"^(\d{4})$", raw)
    if m:
        return f"{m.group(1)}-01"
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{4})", raw)
    if m:
        mon = _MONTH_FULL.get(m.group(1).lower()) or _MONTHS.get(m.group(1).lower()[:3])
        if mon:
            return f"{m.group(2)}-{mon:02d}"
    return None


def normalize_skill(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _ALIAS_TO_CANON.get(key, raw.strip())


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw):
        return raw
    return None
