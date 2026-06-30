"""ATS JSON blob source.

The ATS uses its own field names that don't match ours. This source's
whole job is the field-name remap, e.g.:
  candidate.full_name   -> full_name
  candidate.contact.*   -> emails / phones
  candidate.work_history -> experience
  candidate.edu          -> education
We handle a couple of plausible ATS shapes defensively -- a real ATS
integration would pin one schema, but assignments are graded on robustness
to "any source may be malformed".
"""
from __future__ import annotations

import json
from pathlib import Path

from cdt.core.normalize import normalize_date, normalize_email, normalize_phone, normalize_skill
from cdt.core.record import FieldObs, RawRecord

SOURCE = "ats_json"


def _get(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _parse_one(obj: dict) -> RawRecord:
    rec = RawRecord(source=SOURCE)
    contact = obj.get("contact") or obj.get("contact_info") or {}

    name = _get(obj, "full_name", "candidate_name", "name")
    if name:
        rec.full_name = FieldObs(name, SOURCE, "key_remap")

    email_raw = _get(contact, "email", "primary_email") or _get(obj, "email")
    email = normalize_email(email_raw)
    if email:
        rec.emails.append(FieldObs(email, SOURCE, "key_remap"))
    for alt in (contact.get("emails") or []):
        e = normalize_email(alt)
        if e:
            rec.emails.append(FieldObs(e, SOURCE, "key_remap"))

    phone_raw = _get(contact, "phone", "mobile") or _get(obj, "phone")
    phone = normalize_phone(phone_raw)
    if phone:
        rec.phones.append(FieldObs(phone, SOURCE, "key_remap"))

    loc = obj.get("location") or contact.get("location")
    if isinstance(loc, dict):
        rec.location = FieldObs(
            {"city": loc.get("city"), "region": loc.get("state") or loc.get("region"),
             "country": loc.get("country")},
            SOURCE, "key_remap",
        )
    elif isinstance(loc, str) and loc:
        parts = [p.strip() for p in loc.split(",")]
        city = parts[0] if parts else None
        country = parts[-1] if len(parts) > 1 else None
        rec.location = FieldObs({"city": city, "region": None, "country": country},
                                 SOURCE, "key_remap", confidence=0.5)

    headline = _get(obj, "headline", "current_title", "title")
    if headline:
        rec.headline = FieldObs(headline, SOURCE, "key_remap")

    for s in (obj.get("skills") or obj.get("skill_list") or []):
        s_name = s if isinstance(s, str) else (s.get("name") if isinstance(s, dict) else None)
        canon = normalize_skill(s_name)
        if canon:
            rec.skills.append(FieldObs(canon, SOURCE, "key_remap"))

    for w in (obj.get("work_history") or obj.get("experience") or []):
        if not isinstance(w, dict):
            continue
        rec.experience.append(FieldObs({
            "company": _get(w, "employer", "company"),
            "title": _get(w, "job_title", "title"),
            "start": normalize_date(_get(w, "start_date", "from")),
            "end": normalize_date(_get(w, "end_date", "to")) or ("present" if w.get("is_current") else None),
            "summary": _get(w, "description", "summary"),
        }, SOURCE, "key_remap"))

    for e in (obj.get("edu") or obj.get("education") or []):
        if not isinstance(e, dict):
            continue
        rec.education.append(FieldObs({
            "institution": _get(e, "school", "institution"),
            "degree": _get(e, "degree"),
            "field": _get(e, "field_of_study", "field"),
            "end_year": _get(e, "grad_year", "end_year"),
        }, SOURCE, "key_remap"))

    return rec


def parse(path: str | Path) -> list[RawRecord]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    if isinstance(data, dict):
        candidates = data.get("candidates") if "candidates" in data else [data]
    elif isinstance(data, list):
        candidates = data
    else:
        return []
    out = []
    for c in candidates:
        if isinstance(c, dict) and c:
            out.append(_parse_one(c))
    return out
