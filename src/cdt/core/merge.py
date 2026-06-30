"""Merge / conflict-resolution / confidence engine.

Policy (documented in the design doc too):

MATCHING / CLUSTERING
  Two RawRecords are the same person if they share a normalized email,
  OR share a normalized phone, OR have an exact case-insensitive full-name
  match (name-only matches are weaker and never override an email/phone
  mismatch). Implemented as union-find over these three keys.

CONFLICT RESOLUTION (per scalar field)
  Each source has a fixed trust weight (SOURCE_WEIGHT below) reflecting how
  authoritative it is -- ATS/CSV (recruiter-entered, structured) are
  trusted over resume/notes (unstructured, heuristically parsed). For a
  given field we pick the observation that maximizes
      source_weight * observation_confidence
  and record every other distinct value seen as provenance, so nothing is
  silently dropped -- only the canonical record exports a single winner per
  scalar field. List fields (emails, phones, skills, experience, education)
  are UNIONED and deduped rather than collapsed to one winner, since a
  candidate genuinely can have two emails.

CONFIDENCE
  - Each field's confidence = the winning weighted score, capped at 1.0,
    with a small boost (+0.1, capped at 1.0) if >=2 independent sources
    agree on the same normalized value (corroboration).
  - overall_confidence = mean of all populated field confidences.
"""
from __future__ import annotations

from collections import defaultdict

from cdt.core.record import FieldObs, RawRecord
from cdt.core.schema import (
    CanonicalProfile, Education, Experience, Links, Location, Provenance, Skill,
)

SOURCE_WEIGHT = {
    "ats_json": 1.0,
    "recruiter_csv": 0.9,
    "github": 0.75,
    "linkedin": 0.75,
    "resume": 0.6,
    "recruiter_notes": 0.4,
}


def _weighted(obs: FieldObs) -> float:
    return SOURCE_WEIGHT.get(obs.source, 0.5) * obs.confidence


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _cluster(records: list[RawRecord]) -> list[list[RawRecord]]:
    """Group RawRecords across all sources into one cluster per candidate."""
    uf = _UnionFind()
    key_of_record: list[tuple[str, ...]] = []

    for rec in records:
        keys = []
        for e in rec.emails:
            keys.append(f"email:{e.value}")
        for ph in rec.phones:
            keys.append(f"phone:{ph.value}")
        if rec.full_name:
            keys.append(f"name:{str(rec.full_name.value).strip().lower()}")
        key_of_record.append(tuple(keys) or (f"anon:{id(rec)}",))

    # union all keys belonging to the same record
    for keys in key_of_record:
        for i in range(1, len(keys)):
            uf.union(keys[0], keys[i])
    # union records that share ANY key (prefer email/phone keys over name-only)
    key_to_root: dict[str, str] = {}
    for keys in key_of_record:
        email_phone_keys = [k for k in keys if k.startswith(("email:", "phone:"))]
        strong_keys = email_phone_keys or keys
        roots = {uf.find(k) for k in strong_keys}
        if len(roots) > 1:
            roots = list(roots)
            for r in roots[1:]:
                uf.union(roots[0], r)

    clusters: dict[str, list[RawRecord]] = defaultdict(list)
    for rec, keys in zip(records, key_of_record):
        root = uf.find(keys[0])
        clusters[root].append(rec)
    return list(clusters.values())


def _resolve_scalar(observations: list[FieldObs]):
    if not observations:
        return None, 0.0, []
    best = max(observations, key=_weighted)
    score = min(1.0, _weighted(best))
    agreeing_sources = {o.source for o in observations if o.value == best.value}
    if len(agreeing_sources) >= 2:
        score = min(1.0, score + 0.1)
    provenance = [(best.value, o.source, o.method) for o in observations]
    return best.value, score, provenance


def _dedupe_list(observations: list[FieldObs]) -> dict:
    """Returns {normalized_value: (best_confidence, [sources])}."""
    grouped: dict = {}
    for o in observations:
        key = o.value if not isinstance(o.value, dict) else tuple(sorted(o.value.items()))
        bucket = grouped.setdefault(key, {"value": o.value, "score": 0.0, "sources": set()})
        bucket["score"] = max(bucket["score"], _weighted(o))
        bucket["sources"].add(o.source)
    return grouped


def merge_cluster(cluster: list[RawRecord], candidate_id: str) -> CanonicalProfile:
    profile = CanonicalProfile(candidate_id=candidate_id)
    field_confidences = []

    name_obs = [r.full_name for r in cluster if r.full_name]
    val, score, prov = _resolve_scalar(name_obs)
    if val:
        profile.full_name = val
        profile.provenance.append(Provenance("full_name", *_winner_source(prov, val)))
        field_confidences.append(score)

    email_obs = [e for r in cluster for e in r.emails]
    for key, bucket in _dedupe_list(email_obs).items():
        profile.emails.append(bucket["value"])
        for s in bucket["sources"]:
            profile.provenance.append(Provenance("emails", s, "merge"))
    if email_obs:
        field_confidences.append(max(_weighted(o) for o in email_obs))

    phone_obs = [p for r in cluster for p in r.phones]
    for key, bucket in _dedupe_list(phone_obs).items():
        profile.phones.append(bucket["value"])
        for s in bucket["sources"]:
            profile.provenance.append(Provenance("phones", s, "merge"))
    if phone_obs:
        field_confidences.append(max(_weighted(o) for o in phone_obs))

    headline_obs = [r.headline for r in cluster if r.headline]
    val, score, prov = _resolve_scalar(headline_obs)
    if val:
        profile.headline = val
        profile.provenance.append(Provenance("headline", *_winner_source(prov, val)))
        field_confidences.append(score)

    loc_obs = [r.location for r in cluster if r.location]
    val, score, prov = _resolve_scalar(loc_obs)
    if val:
        from cdt.core.normalize import normalize_country
        profile.location = Location(
            city=val.get("city"), region=val.get("region"),
            country=normalize_country(val.get("country")),
        )
        profile.provenance.append(Provenance("location", *_winner_source(prov, val)))
        field_confidences.append(score)

    link_obs = [r.links for r in cluster if r.links]
    val, score, prov = _resolve_scalar(link_obs)
    if val:
        profile.links = Links(
            linkedin=val.get("linkedin"), github=val.get("github"),
            portfolio=val.get("portfolio"), other=val.get("other") or [],
        )
        profile.provenance.append(Provenance("links", *_winner_source(prov, val)))
        field_confidences.append(score)

    years_obs = [r.years_experience for r in cluster if r.years_experience]
    val, score, prov = _resolve_scalar(years_obs)
    if val is not None:
        try:
            profile.years_experience = float(val)
            profile.provenance.append(Provenance("years_experience", *_winner_source(prov, val)))
            field_confidences.append(score)
        except (TypeError, ValueError):
            pass

    skill_obs = [s for r in cluster for s in r.skills]
    skill_buckets = _dedupe_list(skill_obs)
    for key, bucket in skill_buckets.items():
        if not bucket["value"]:
            continue
        profile.skills.append(Skill(
            name=bucket["value"], confidence=round(min(1.0, bucket["score"] + (0.1 if len(bucket["sources"]) >= 2 else 0)), 2),
            sources=sorted(bucket["sources"]),
        ))
        for s in bucket["sources"]:
            profile.provenance.append(Provenance("skills", s, "merge"))
    if skill_obs:
        field_confidences.append(sum(s.confidence for s in profile.skills) / max(1, len(profile.skills)))

    exp_obs = [e for r in cluster for e in r.experience]
    seen_exp = set()
    for o in exp_obs:
        d = o.value or {}
        sig = (d.get("company"), d.get("title"), d.get("start"))
        if sig in seen_exp or not any(d.values()):
            continue
        seen_exp.add(sig)
        profile.experience.append(Experience(**{k: d.get(k) for k in ("company", "title", "start", "end", "summary")}))
        profile.provenance.append(Provenance("experience", o.source, o.method))
    if exp_obs:
        field_confidences.append(max(_weighted(o) for o in exp_obs))

    edu_obs = [e for r in cluster for e in r.education]
    seen_edu = set()
    for o in edu_obs:
        d = o.value or {}
        sig = (d.get("institution"), d.get("degree"))
        if sig in seen_edu or not any(d.values()):
            continue
        seen_edu.add(sig)
        profile.education.append(Education(**{k: d.get(k) for k in ("institution", "degree", "field", "end_year")}))
        profile.provenance.append(Provenance("education", o.source, o.method))
    if edu_obs:
        field_confidences.append(max(_weighted(o) for o in edu_obs))

    profile.overall_confidence = round(sum(field_confidences) / len(field_confidences), 2) if field_confidences else 0.0
    return profile


def _winner_source(prov: list[tuple], winning_value) -> tuple[str, str]:
    for value, source, method in prov:
        if value == winning_value:
            return source, method
    return "unknown", "unknown"


def _is_empty(rec: RawRecord) -> bool:
    return not (
        rec.full_name or rec.emails or rec.phones or rec.headline or rec.location
        or rec.links or rec.years_experience or rec.skills or rec.experience or rec.education
    )


def merge_all(records: list[RawRecord]) -> list[CanonicalProfile]:
    records = [r for r in records if not _is_empty(r)]
    clusters = _cluster(records)
    profiles = []
    for i, cluster in enumerate(clusters, start=1):
        profiles.append(merge_cluster(cluster, candidate_id=f"cand_{i:04d}"))
    return profiles
