"""End-to-end pipeline: detect source type -> parse -> merge -> project -> validate.

Source detection is by file extension + a peek at content, never by
filename convention alone, so a misnamed file degrades gracefully
instead of crashing.
"""
from __future__ import annotations

import json
from pathlib import Path

from cdt.core.merge import merge_all
from cdt.core.project import project, validate
from cdt.core.record import RawRecord
from cdt.ingest import ats_json_source, csv_source, recruiter_notes_source, resume_source

_NOTES_HINTS = ("note", "notes", "recruiter")


def detect_and_parse(path: str) -> list[RawRecord]:
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix == ".csv":
            return csv_source.parse(p)
        if suffix == ".json":
            return ats_json_source.parse(p)
        if suffix in (".pdf", ".docx"):
            return resume_source.parse(p)
        if suffix == ".txt":
            if any(h in p.stem.lower() for h in _NOTES_HINTS):
                return recruiter_notes_source.parse(p)
            return resume_source.parse(p)  # plain-text resume fallback
    except Exception:
        # Constraint: a malformed/garbage source must never crash the run.
        return []
    return []


def run_pipeline(input_paths: list[str], config: dict | None = None) -> list[dict]:
    all_records: list[RawRecord] = []
    for path in input_paths:
        all_records.extend(detect_and_parse(path))

    profiles = merge_all(all_records)

    outputs = []
    for profile in profiles:
        projected = project(profile, config)
        problems = validate(projected, config)
        if problems:
            projected["_validation_warnings"] = problems
        outputs.append(projected)
    return outputs


def run_pipeline_to_file(input_paths: list[str], output_path: str, config: dict | None = None) -> None:
    outputs = run_pipeline(input_paths, config)
    Path(output_path).write_text(json.dumps(outputs, indent=2), encoding="utf-8")
