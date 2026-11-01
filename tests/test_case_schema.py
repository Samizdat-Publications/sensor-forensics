"""UFO Case Files schema v0.1 and the exporter (M6.1, M6.2)."""

import copy
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools import export_cases

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "ufo-case-file.schema.json").read_text(encoding="utf-8"))

MINIMAL = {
    "schema_version": "0.1", "case_id": "example-1", "kind": "video_case", "title": "Example",
    "event": {"date": None},
    "sources": [{"id": "v", "role": "video"}],
    "verdict": {"text": "No ranking.", "conditions": [], "decisive": False},
    "provenance": {"repo": "x", "commit": "abc1234", "lab_version": "0.1.0", "generated": "2026-11-01T00:00:00Z"},
}


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(SCHEMA)


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("cases")
    paths = export_cases.export_all(out)
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in paths}


def test_schema_is_valid_2020_12():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_minimal_example_passes(validator):
    assert list(validator.iter_errors(MINIMAL)) == []


@pytest.mark.parametrize("field", SCHEMA["required"])
def test_missing_required_field_fails(validator, field):
    doc = copy.deepcopy(MINIMAL)
    del doc[field]
    assert list(validator.iter_errors(doc)), f"missing {field} should fail"


def test_bad_values_fail(validator):
    for patch in ({"schema_version": "0.2"}, {"kind": "other"}, {"case_id": "Bad Id"},
                  {"sources": []}, {"provenance": {"repo": "x", "commit": "zz", "lab_version": "1", "generated": "t"}}):
        doc = {**copy.deepcopy(MINIMAL), **patch}
        assert list(validator.iter_errors(doc)), patch


def test_unknown_optional_fields_are_allowed(validator):
    doc = {**copy.deepcopy(MINIMAL), "future_field": {"a": 1}}
    assert list(validator.iter_errors(doc)) == []


@pytest.mark.parametrize("case", ["gimbal", "gofast", "flir1", "pursue-triage"])
def test_exporter_output_validates(validator, exported, case):
    assert case in exported
    errs = [e.message for e in validator.iter_errors(exported[case])]
    assert errs == []


def test_exported_cases_have_content(exported):
    for cid in ("gimbal", "gofast", "flir1"):
        c = exported[cid]
        assert c["hypotheses"] and c["sources"][0]["sha256"]
        assert c["provenance"]["commit"] and len(c["provenance"]["commit"]) == 40
        assert c["testimony"]["claims_total"] > 0
        for h in c["hypotheses"]:
            assert "total_physics_only" in h and "total_testimony_weighted" in h
    assert exported["pursue-triage"]["triage"]["clips_total"] == 134
    assert {"gimbal", "gofast", "flir1"} <= set(exported)


def test_no_em_dashes_in_exports(exported):
    for cid, c in exported.items():
        assert "—" not in json.dumps(c, ensure_ascii=False), cid


def test_exports_are_strict_json(exported):
    for c in exported.values():
        json.dumps(c, allow_nan=False)


def test_schema_files_have_no_em_dashes():
    for p in ("schemas/ufo-case-file.schema.json", "schemas/README.md", "tools/export_cases.py", "tools/validate_cases.py"):
        assert "—" not in (ROOT / p).read_text(encoding="utf-8"), p
