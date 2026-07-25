"""Analyzer for a plain `cargo test` run (no model checker behind it)."""

from __future__ import annotations

import re

from ..record import EvidenceRecord, Verdict

_RESULT = re.compile(
    r"^test result:\s*(?P<outcome>ok|FAILED)\.\s*(?P<passed>\d+)\s+passed;\s*(?P<failed>\d+)\s+failed",
    re.M,
)


def sniff(text: str) -> bool:
    return bool(_RESULT.search(text))


def analyze(text: str, source: str = "<memory>") -> EvidenceRecord:
    rec = EvidenceRecord(source=source, tool="cargo-test")
    m = _RESULT.search(text)
    if m:
        rec.verdict = Verdict.PASS if m.group("outcome") == "ok" else Verdict.FAIL
        rec.exploration["tests_passed"] = int(m.group("passed"))
        rec.exploration["tests_failed"] = int(m.group("failed"))
    rec.undetectable.append(
        "a test run reports only the inputs it was given; it says nothing about "
        "inputs nobody wrote a test for"
    )
    return rec
