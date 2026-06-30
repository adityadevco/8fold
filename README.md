# Multi-Source Candidate Data Transformer

Eightfold Engineering Intern (Jul–Dec 2026) take-home assignment.

Turns messy, multi-source candidate data into one canonical, deduplicated
profile per candidate, with full provenance and confidence, and a
config-driven projection layer that reshapes the output at runtime with
**no code changes**.

## Sources implemented

| Source | Group | File ext |
|---|---|---|
| Recruiter CSV export | structured | `.csv` |
| ATS JSON blob | structured | `.json` |
| Resume (plain text / PDF / DOCX) | unstructured | `.txt` / `.pdf` / `.docx` |
| Recruiter notes | unstructured | `.txt` (filename contains "note(s)") |

This covers both required groups twice over for robustness. GitHub and
LinkedIn ingestion were **intentionally descoped** under time pressure —
see "What I'd add next" below; the ingest interface (`parse(path) ->
list[RawRecord]`) is already source-agnostic, so plugging them in later is
additive, not a redesign.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # optional: only needed for PDF/DOCX resumes

# default schema
python3 -m cdt.cli \
  --inputs sample_inputs/recruiter_export.csv sample_inputs/ats_export.json \
           sample_inputs/aditi_sharma_resume.txt sample_inputs/recruiter_notes.txt \
  --config configs/default.json \
  --out sample_outputs/default_output.json

# custom/runtime-configured schema (renamed fields, E.164 phone, canonical skills)
python3 -m cdt.cli \
  --inputs sample_inputs/recruiter_export.csv \
  --config configs/recruiter_view.json
```

Set `PYTHONPATH=src` if not installing the package, or `pip install -e .`
Run tests with:

```bash
PYTHONPATH=src python3 -m pytest tests/ -v
```

## Architecture

```
detect (by extension) -> parse (per-source) -> [normalize at ingest]
   -> cluster/merge (dedupe across sources, resolve conflicts, score confidence)
   -> project (apply runtime config: select / rename / normalize / on_missing)
   -> validate (check output against requested schema)
```

- `src/cdt/ingest/*` — one module per source type. Each `parse()` never
  raises; a missing/empty/malformed file returns `[]` and the pipeline
  continues.
- `src/cdt/core/record.py` — `RawRecord`/`FieldObs`: per-source observations
  with provenance, before any cross-source merging happens.
- `src/cdt/core/normalize.py` — pure functions for phone (E.164), dates
  (YYYY-MM), skill canonicalization, country (ISO-3166 alpha-2).
- `src/cdt/core/merge.py` — clustering (union-find on email/phone/name) +
  conflict resolution (source-trust-weighted) + confidence scoring.
- `src/cdt/core/schema.py` — the canonical, full-fidelity internal record.
- `src/cdt/core/project.py` — the **only** module that reads the runtime
  config; turns a canonical profile into the requested output shape and
  validates it.

### Matching / merge policy

Two records are the same candidate if they share a normalized email OR a
normalized phone OR an exact case-insensitive full name (name-only matches
never override a structured-source-vs-resume conflict on email/phone —
see `merge.py` docstring for the full policy).

### Conflict resolution & confidence

Each source has a fixed trust weight (ATS JSON > recruiter CSV > resume >
recruiter notes — structured/recruiter-entered data outranks heuristically
parsed prose). For scalar fields we keep the highest `weight × confidence`
observation and record every other value as provenance, never silently
dropping data. Confidence gets a small corroboration bonus when ≥2
independent sources agree. List fields (emails, skills, experience…) are
unioned and deduped rather than collapsed to a single winner.

## Edge cases handled

1. **Empty/blank rows** in CSV — skipped, not turned into phantom candidates.
2. **Malformed JSON** (`sample_inputs/broken_ats_export.json`) — caught,
   returns `[]`, pipeline continues with other sources.
3. **Null/empty candidate objects** inside an otherwise-valid ATS blob —
   dropped before clustering rather than emitted as an all-null profile.
4. **Same person across 3+ sources** with different field names (`name` vs
   `full_name` vs `candidate_name`) and partially conflicting values (e.g.
   CSV's `current_company` says the wrong title) — merged into one
   profile with the higher-trust source winning.
5. **Required field missing** with `on_missing: "error"` config — raises
   `ProjectionError` instead of silently emitting `null`.

## Known limitation (deliberately scoped out)

`recruiter_notes_source.py` treats one `.txt` file as **one candidate's**
notes. `sample_inputs/recruiter_notes.txt` actually mentions two people
(Karthik and Priya) in one file, and the parser's single name-regex +
single phone-regex will misattribute Priya's phone number to Karthik's
record. A correct fix is a per-paragraph/per-mention splitter before
field extraction; I scoped this out to keep the heuristic extractor
simple and auditable, and call it out here rather than hide it. In a
real system, recruiter notes would more likely arrive as one note per
candidate (tied to an ATS record ID) rather than freeform multi-candidate
text, which is the assumption the rest of the design leans on.

## What I'd add next with more time

- GitHub REST/GraphQL + LinkedIn ingestion (interface is ready for it).
- Per-paragraph splitting for multi-candidate recruiter notes.
- Fuzzy name matching (Jaro-Winkler) for clustering instead of exact match,
  with a confidence-weighted threshold instead of a hard boundary.
- A `years_experience` estimator derived from the earliest `experience[].start`
  rather than requiring it as direct input.
