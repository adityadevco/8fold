import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cdt.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_inputs"


def test_merges_same_candidate_across_csv_ats_resume():
    outputs = run_pipeline([
        str(SAMPLES / "recruiter_export.csv"),
        str(SAMPLES / "ats_export.json"),
        str(SAMPLES / "aditi_sharma_resume.txt"),
    ])
    aditi = next(o for o in outputs if o["full_name"] == "Aditi Sharma")
    assert aditi["emails"] == ["aditi.sharma@gmail.com"]
    sources = {s for sk in aditi["skills"] for s in sk["sources"]}
    assert "ats_json" in sources and "resume" in sources
    assert aditi["overall_confidence"] > 0


def test_malformed_json_does_not_crash_pipeline():
    outputs = run_pipeline([str(SAMPLES / "broken_ats_export.json")])
    assert outputs == []


def test_missing_file_does_not_crash_pipeline():
    outputs = run_pipeline([str(SAMPLES / "does_not_exist.csv")])
    assert outputs == []


def test_empty_rows_and_null_candidates_are_dropped():
    outputs = run_pipeline([
        str(SAMPLES / "recruiter_export.csv"),
        str(SAMPLES / "ats_export.json"),
    ])
    # the blank CSV row and the null-name ATS entry must not produce phantom profiles
    assert all(o["full_name"] for o in outputs)


def test_custom_config_renames_and_normalizes_fields():
    import json
    config = json.loads((ROOT / "configs" / "recruiter_view.json").read_text())
    outputs = run_pipeline([str(SAMPLES / "recruiter_export.csv")], config)
    rohan = next(o for o in outputs if o["full_name"] == "Rohan Verma")
    assert "primary_email" in rohan and "emails" not in rohan
    assert rohan["phone"].startswith("+")


def test_required_field_missing_triggers_error_policy():
    config = {
        "fields": [{"path": "full_name", "type": "string", "required": True},
                   {"path": "linkedin_url", "from": "links.linkedin", "required": True}],
        "on_missing": "error",
    }
    # Rohan has no linkedin in our sample data -> should raise inside project()
    import pytest
    from cdt.core.project import ProjectionError
    with pytest.raises(ProjectionError):
        run_pipeline([str(SAMPLES / "recruiter_export.csv")], config)
