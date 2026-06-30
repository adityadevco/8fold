"""Intermediate, per-source representation before merge.

Each ingest source parses its raw input into a list of RawRecord (usually
one per candidate found in that source). merge.py is responsible for
clustering RawRecords across sources into one CanonicalProfile per person.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldObs:
    """A single field observation: value + provenance + this source's
    self-reported confidence in the observation."""
    value: object
    source: str
    method: str
    confidence: float = 0.85


@dataclass
class RawRecord:
    source: str
    full_name: FieldObs | None = None
    emails: list[FieldObs] = field(default_factory=list)
    phones: list[FieldObs] = field(default_factory=list)
    headline: FieldObs | None = None
    location: FieldObs | None = None  # value = dict(city, region, country)
    links: FieldObs | None = None     # value = dict(linkedin, github, portfolio)
    years_experience: FieldObs | None = None
    skills: list[FieldObs] = field(default_factory=list)       # value = skill name str
    experience: list[FieldObs] = field(default_factory=list)   # value = dict
    education: list[FieldObs] = field(default_factory=list)    # value = dict
