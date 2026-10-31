"""Checkpoint gate: runs every test suite and fails on any failure OR skip.

Usage (from the repo root):
    .venv/Scripts/python tools/gate.py

A skipped test is treated as a failure, because a gate that silently skips
proves nothing (lesson carried over from the sister projects).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    ok = True

    # Read counts from a JUnit report rather than the console: pyproject's addopts already
    # passes -q, and stacked -q flags suppress the summary line a regex would need.
    import xml.etree.ElementTree as ET

    report = ROOT / "artifacts" / "tmp" / "gate-junit.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    code, out = run([sys.executable, "-m", "pytest", "-rs", f"--junitxml={report}"])
    suite = ET.parse(report).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    counts = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    print(f"pytest: {counts['tests']} tests, {counts['failures']} failures, "
          f"{counts['errors']} errors, {counts['skipped']} skipped")
    if code != 0 or counts["failures"] or counts["errors"]:
        ok = False
        print(out[-4000:])
    if counts["skipped"]:
        ok = False
        print("GATE FAIL: skipped tests count as failures.")

    js_tests = sorted((ROOT / "tests" / "js").glob("*.test.mjs"))
    if js_tests:
        node = shutil.which("node")
        if node is None:
            ok = False
            print("GATE FAIL: node not found but JS tests exist.")
        else:
            code, out = run([node, "--test", *[str(p) for p in js_tests]])
            print(f"node --test: exit {code}")
            if code != 0 or re.search(r"^# skip [1-9]", out, re.M):
                ok = False
                print(out[-4000:])

    print("GATE PASS" if ok else "GATE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
