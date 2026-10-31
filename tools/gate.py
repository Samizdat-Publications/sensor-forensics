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

    code, out = run([sys.executable, "-m", "pytest", "-rs", "-q"])
    tail = out.strip().splitlines()[-1] if out.strip() else "(no output)"
    print(f"pytest: {tail}")
    if code != 0:
        ok = False
        print(out[-4000:])
    if re.search(r"\bskipped\b", tail):
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
