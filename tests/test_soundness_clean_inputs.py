"""Soundness sweep: every recorded clean run in this repo must grade without
a false flag. A grader that cries wolf gets ignored, so this runs on every push."""

from pathlib import Path

import pytest

from evidence_audit import analyze_file
from evidence_audit.grade import grade_one
from evidence_audit.record import Verdict

ROOT = Path(__file__).resolve().parents[1]

CLEAN_RUNS = [
    "case-studies/01-kani-sequential-jsonwebtoken/output-clean.txt",
    "case-studies/02-kani-vacuous-pass-governor/output-clean.txt",
    "case-studies/03-loom-false-green-governor/output-C-shimmed-clean.txt",
    "case-studies/03-loom-false-green-governor/output-E-shimmed-clean-3threads.txt",
]


@pytest.mark.parametrize("rel", CLEAN_RUNS)
def test_clean_run_has_no_flags(rel):
    rec = analyze_file(ROOT / rel)
    grade_one(rec)
    assert rec.verdict == Verdict.PASS, f"{rel} should parse as a pass"
    assert [f.code for f in rec.flags] == [], f"{rel} raised {[f.code for f in rec.flags]}"


def test_every_recorded_output_parses_to_a_verdict():
    """No recorded output in the repo should fall through to UNKNOWN."""
    unknown = []
    for p in (ROOT / "case-studies").rglob("output-*.txt"):
        rec = analyze_file(p)
        if rec.verdict == Verdict.UNKNOWN:
            unknown.append(str(p.relative_to(ROOT)))
    assert unknown == [], f"unparsed outputs: {unknown}"
