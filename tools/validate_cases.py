"""Validate every file in exports/cases/ against schemas/ufo-case-file.schema.json.

Usage (from the repo root):
    .venv/Scripts/python tools/validate_cases.py [directory]

Prints PASS or FAIL per file; exit 1 on any failure (or if the directory has no files).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "ufo-case-file.schema.json"


def validate_file(path: Path, validator: Draft202012Validator) -> list[str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"not valid JSON: {e}"]
    return [f"{'/'.join(str(x) for x in e.absolute_path) or '(root)'}: {e.message[:200]}"
            for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))]


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else ROOT / "exports" / "cases"
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    files = sorted(folder.glob("*.json"))
    if not files:
        print(f"FAIL no case files in {folder}")
        return 1
    bad = 0
    for f in files:
        errs = validate_file(f, validator)
        if errs:
            bad += 1
            print(f"FAIL {f.name}")
            for e in errs[:10]:
                print(f"    {e}")
        else:
            print(f"PASS {f.name}")
    print(f"{len(files) - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
