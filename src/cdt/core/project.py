"""Projection layer.

Takes a CanonicalProfile (internal, full-fidelity) and a runtime config and
produces the JSON-serializable output the caller asked for. This is the
ONLY place that knows about user-supplied config -- core/merge.py and the
ingest sources are completely config-agnostic, which is what lets us
support arbitrary reshaping "with no code changes".
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cdt.core.schema import CanonicalProfile

DEFAULT_FIELDS = [
    "candidate_id", "full_name", "emails", "phones", "location", "links",
    "headline", "years_experience", "skills", "experience", "education",
]


class ProjectionError(Exception):
    pass


def _profile_to_dict(profile: CanonicalProfile) -> dict[str, Any]:
    d = asdict(profile)
    return d


def _get_path(d: dict, path: str):
    """Resolve a dotted/bracket path like 'emails[0]' or 'skills[].name'."""
    cur = d
    for part in path.replace("]", "").split("."):
        if "[" in part:
            key, idx = part.split("[")
            if key:
                cur = cur.get(key) if isinstance(cur, dict) else None
            if cur is None:
                return None
            if idx == "":
                if not isinstance(cur, list):
                    return None
                return cur  # caller wants the whole list (mapped per-item below)
            try:
                cur = cur[int(idx)]
            except (IndexError, ValueError, TypeError):
                return None
        else:
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                return None
    return cur


def _resolve_field(d: dict, from_path: str | None, default_path: str):
    path = from_path or default_path
    if ".name" in path and path.endswith(".name") and "[]" in path:
        list_path = path.split("[]")[0]
        items = d.get(list_path) or []
        return [it.get("name") for it in items if isinstance(it, dict) and it.get("name") is not None] or None
    return _get_path(d, path)


def project(profile: CanonicalProfile, config: dict | None) -> dict[str, Any]:
    full = _profile_to_dict(profile)
    config = config or {}
    on_missing = config.get("on_missing", "null")
    if on_missing not in ("null", "omit", "error"):
        raise ProjectionError(f"invalid on_missing: {on_missing}")
    include_confidence = config.get("include_confidence", True)
    include_provenance = config.get("include_provenance", config.get("include_confidence", True))

    field_specs = config.get("fields")
    if not field_specs:
        field_specs = [{"path": f, "from": f, "required": False} for f in DEFAULT_FIELDS]

    out: dict[str, Any] = {}
    for spec in field_specs:
        out_path = spec["path"]
        from_path = spec.get("from")
        required = spec.get("required", False)
        value = _resolve_field(full, from_path, out_path)

        if spec.get("normalize") == "E164" and value and not str(value).startswith("+"):
            from cdt.core.normalize import normalize_phone
            value = normalize_phone(str(value))
        if spec.get("normalize") == "canonical" and isinstance(value, list):
            from cdt.core.normalize import normalize_skill
            seen = []
            for v in value:
                nv = normalize_skill(v)
                if nv and nv not in seen:
                    seen.append(nv)
            value = seen

        is_missing = value is None or value == [] or value == ""
        if is_missing:
            if required and on_missing == "error":
                raise ProjectionError(f"required field '{out_path}' is missing")
            if on_missing == "omit":
                continue
            value = None  # 'null' policy (default)
        out[out_path] = value

    if include_confidence:
        out["overall_confidence"] = full.get("overall_confidence", 0.0)
    if include_provenance:
        out["provenance"] = full.get("provenance", [])

    return out


def validate(output: dict, config: dict | None) -> list[str]:
    """Lightweight structural validation against the requested schema.
    Returns a list of problems (empty == valid)."""
    problems = []
    config = config or {}
    field_specs = config.get("fields") or [{"path": f, "type": None, "required": False} for f in DEFAULT_FIELDS]
    on_missing = config.get("on_missing", "null")
    for spec in field_specs:
        path = spec["path"]
        if path not in output:
            if on_missing != "omit":
                problems.append(f"expected field '{path}' missing from output")
            continue
        expected_type = spec.get("type")
        val = output[path]
        if val is None:
            continue
        if expected_type == "string" and not isinstance(val, str):
            problems.append(f"field '{path}' expected string, got {type(val).__name__}")
        if expected_type == "string[]" and not (isinstance(val, list) and all(isinstance(v, str) for v in val)):
            problems.append(f"field '{path}' expected string[], got {val!r}")
        if expected_type == "number" and not isinstance(val, (int, float)):
            problems.append(f"field '{path}' expected number, got {type(val).__name__}")
    return problems
