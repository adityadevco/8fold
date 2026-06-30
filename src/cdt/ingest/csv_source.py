"""Recruiter CSV export source.

Columns expected (header names may vary in case/spacing; we match
case-insensitively and strip whitespace): name, email, phone,
current_company, title.
"""
from __future__ import annotations

import csv
from pathlib import Path

from cdt.core.normalize import normalize_email, normalize_phone
from cdt.core.record import FieldObs, RawRecord

SOURCE = "recruiter_csv"


def parse(path: str | Path) -> list[RawRecord]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    records: list[RawRecord] = []
    try:
        with p.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return []
            norm_headers = {h.strip().lower(): h for h in reader.fieldnames}
            for row in reader:
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
                if not any(row.values()):
                    continue
                rec = RawRecord(source=SOURCE)
                name = row.get("name")
                if name:
                    rec.full_name = FieldObs(name, SOURCE, "csv_column")
                email = normalize_email(row.get("email"))
                if email:
                    rec.emails.append(FieldObs(email, SOURCE, "csv_column"))
                phone = normalize_phone(row.get("phone"))
                if phone:
                    rec.phones.append(FieldObs(phone, SOURCE, "csv_column"))
                company = row.get("current_company")
                title = row.get("title")
                if company or title:
                    rec.experience.append(FieldObs(
                        {"company": company or None, "title": title or None,
                         "start": None, "end": "present", "summary": None},
                        SOURCE, "csv_column",
                    ))
                if title:
                    rec.headline = FieldObs(title, SOURCE, "csv_column", confidence=0.5)
                records.append(rec)
    except (csv.Error, UnicodeDecodeError, OSError):
        return []
    return records
