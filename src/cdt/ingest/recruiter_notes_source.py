"""Recruiter notes (.txt free text) source.

Lowest-trust source: a recruiter's scratch notes. Useful mainly for
skills mentioned in passing and contact info if not captured elsewhere.
Everything from here gets the lowest confidence of any source.
"""
from __future__ import annotations

import re
from pathlib import Path

from cdt.core.normalize import normalize_email, normalize_phone, normalize_skill
from cdt.core.record import FieldObs, RawRecord
from cdt.ingest.resume_source import _EMAIL_RE, _PHONE_RE

SOURCE = "recruiter_notes"

# A small fixed vocabulary we scan for in free text -- intentionally
# conservative (precision over recall) since this is our least-trusted source.
_KNOWN_SKILL_TOKENS = [
    "python", "javascript", "typescript", "react", "node", "sql", "machine learning",
    "deep learning", "nlp", "tensorflow", "pytorch", "aws", "docker", "kubernetes",
    "fastapi", "java", "c++", "go",
]


def parse(path: str | Path) -> list[RawRecord]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    if not text.strip():
        return []

    rec = RawRecord(source=SOURCE)

    email_match = _EMAIL_RE.search(text)
    if email_match:
        e = normalize_email(email_match.group(0))
        if e:
            rec.emails.append(FieldObs(e, SOURCE, "regex", confidence=0.7))

    phone_match = _PHONE_RE.search(text)
    if phone_match:
        ph = normalize_phone(phone_match.group(0))
        if ph:
            rec.phones.append(FieldObs(ph, SOURCE, "regex", confidence=0.4))

    lower = text.lower()
    for token in _KNOWN_SKILL_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", lower):
            canon = normalize_skill(token)
            if canon:
                rec.skills.append(FieldObs(canon, SOURCE, "keyword_scan", confidence=0.35))

    name_match = re.search(r"(?:candidate|name)\s*[:\-]\s*([A-Z][a-zA-Z.]+(?:\s+[A-Z][a-zA-Z.]+){0,3})", text)
    if name_match:
        rec.full_name = FieldObs(name_match.group(1).strip(), SOURCE, "regex", confidence=0.45)

    return [rec]
