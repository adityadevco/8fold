"""Resume source (PDF / DOCX / plain text).

Unstructured prose, so extraction is heuristic and gets a lower
per-field confidence than structured sources. Strategy:
  1. Get raw text (pdfminer for PDF, python-docx for DOCX, else read as text).
  2. Regex for email / phone (high precision, cheap).
  3. Line-based section detection for SKILLS / EXPERIENCE / EDUCATION.
  4. Skip gracefully -- if a parser lib is missing, return [] rather than crash.
"""
from __future__ import annotations

import re
from pathlib import Path

from cdt.core.normalize import normalize_email, normalize_phone, normalize_skill
from cdt.core.record import FieldObs, RawRecord

SOURCE = "resume"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{8,16}\d)")
_SECTION_HEADERS = {
    "skills": "skills", "technical skills": "skills", "skill set": "skills",
    "experience": "experience", "work experience": "experience",
    "professional experience": "experience", "employment": "experience",
    "education": "education", "academics": "education",
}


def _extract_text(p: Path) -> str:
    suffix = p.suffix.lower()
    try:
        if suffix == ".pdf":
            try:
                from pdfminer.high_level import extract_text
                return extract_text(str(p)) or ""
            except ImportError:
                return ""
        if suffix == ".docx":
            try:
                import docx
                d = docx.Document(str(p))
                return "\n".join(par.text for par in d.paragraphs)
            except ImportError:
                return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "header"
    sections[current] = []
    for line in lines:
        stripped = line.strip()
        key = _SECTION_HEADERS.get(stripped.lower().rstrip(":"))
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def parse(path: str | Path) -> list[RawRecord]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    text = _extract_text(p)
    if not text.strip():
        return []

    rec = RawRecord(source=SOURCE)
    lines = [l for l in text.splitlines() if l.strip()]

    if lines:
        # Heuristic: the candidate's name is usually the first non-empty
        # line if it's short, title-cased, and has no digits/@ in it.
        first = lines[0].strip()
        if 1 <= len(first.split()) <= 5 and not any(ch.isdigit() for ch in first) and "@" not in first:
            rec.full_name = FieldObs(first, SOURCE, "heuristic_first_line", confidence=0.55)

    email_match = _EMAIL_RE.search(text)
    if email_match:
        e = normalize_email(email_match.group(0))
        if e:
            rec.emails.append(FieldObs(e, SOURCE, "regex", confidence=0.8))

    phone_match = _PHONE_RE.search(text)
    if phone_match:
        ph = normalize_phone(phone_match.group(0))
        if ph:
            rec.phones.append(FieldObs(ph, SOURCE, "regex", confidence=0.6))

    sections = _split_sections(lines)
    for raw_skill_line in sections.get("skills", []):
        for token in re.split(r"[,/|•\u2022]", raw_skill_line):
            token = token.strip(" -:")
            if token and len(token) <= 30:
                canon = normalize_skill(token)
                if canon:
                    rec.skills.append(FieldObs(canon, SOURCE, "section_split", confidence=0.5))

    exp_lines = sections.get("experience", [])
    if exp_lines:
        rec.experience.append(FieldObs({
            "company": None, "title": None, "start": None, "end": None,
            "summary": " ".join(exp_lines)[:500],
        }, SOURCE, "section_dump", confidence=0.3))

    edu_lines = sections.get("education", [])
    if edu_lines:
        rec.education.append(FieldObs({
            "institution": edu_lines[0].strip() if edu_lines else None,
            "degree": None, "field": None, "end_year": None,
        }, SOURCE, "section_dump", confidence=0.3))

    return [rec]
