"""Canonical candidate profile schema.

This is the single internal representation every source gets mapped into.
The projection layer (project.py) is the ONLY thing that knows about the
runtime output config -- nothing upstream of merge.py should ever look at
a user-supplied config. That separation is what makes "same engine, no
code changes" actually true.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldValue:
    """A single observed value for a field, plus where it came from."""
    value: object
    source: str          # e.g. "recruiter_csv", "ats_json", "resume", "notes"
    method: str           # e.g. "direct", "regex", "heuristic", "header_match"
    raw_confidence: float  # 0..1, confidence of THIS observation alone


@dataclass
class Provenance:
    field: str
    source: str
    method: str


@dataclass
class Skill:
    name: str
    confidence: float
    sources: list[str] = field(default_factory=list)


@dataclass
class Experience:
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM
    end: Optional[str] = None    # YYYY-MM or "present"
    summary: Optional[str] = None


@dataclass
class Education:
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


@dataclass
class Location:
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


@dataclass
class Links:
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = field(default_factory=list)


@dataclass
class CanonicalProfile:
    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    location: Location = field(default_factory=Location)
    links: Links = field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    overall_confidence: float = 0.0
