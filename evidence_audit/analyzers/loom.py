"""Analyzer for recorded loom output (a cargo test run under --cfg loom)."""

from __future__ import annotations

import re

from ..record import EvidenceRecord, Flag, Verdict

_RESULT = re.compile(
    r"^test result:\s*(?P<outcome>ok|FAILED)\.\s*(?P<passed>\d+)\s+passed;\s*(?P<failed>\d+)\s+failed",
    re.M,
)

#: Harness-emitted execution count. loom itself does not print one, so this is a
#: convention the harness must opt into. See BLIND SPOTS in the README.
_EXECUTIONS = re.compile(r"LOOM EXPLORED\s+(?P<n>\d+)\s+EXECUTIONS", re.M)

#: Optional harness-emitted count of loom-instrumented sync operations. Nothing
#: in stock loom emits this; when it is absent the tool records the gap rather
#: than treating its absence as evidence of instrumentation.
_INSTRUMENTED = re.compile(r"LOOM INSTRUMENTED OPS:\s*(?P<n>\d+)", re.M)


def sniff(text: str) -> bool:
    return bool(_EXECUTIONS.search(text)) or (
        "loom" in text.lower() and bool(_RESULT.search(text))
    )


def analyze(text: str, source: str = "<memory>") -> EvidenceRecord:
    rec = EvidenceRecord(source=source, tool="loom")

    m = _RESULT.search(text)
    if m:
        rec.verdict = Verdict.PASS if m.group("outcome") == "ok" else Verdict.FAIL
        rec.exploration["tests_passed"] = int(m.group("passed"))
        rec.exploration["tests_failed"] = int(m.group("failed"))

    em = _EXECUTIONS.search(text)
    if em:
        rec.exploration["executions_explored"] = int(em.group("n"))

    im = _INSTRUMENTED.search(text)
    if im:
        rec.exploration["instrumented_sync_ops"] = int(im.group("n"))

    _flag(rec)
    _record_undetectable(rec, im is not None, em is not None)
    return rec


def _flag(rec: EvidenceRecord) -> None:
    ops = rec.exploration.get("instrumented_sync_ops")
    if ops == 0:
        rec.flags.append(
            Flag(
                "LOOM_NO_INSTRUMENTED_OPS",
                "the harness reports zero loom-instrumented sync operations; "
                "loom had no preemption point, so no interleaving was explored",
                proves_inert=True,
            )
        )


def _record_undetectable(rec: EvidenceRecord, has_ops: bool, has_execs: bool) -> None:
    if not has_execs:
        rec.undetectable.append(
            "no execution count in this output; loom does not emit one by default, "
            "so an inert run and a thorough run are indistinguishable here"
        )
    if not has_ops:
        rec.undetectable.append(
            "no instrumented-sync-op count in this output; stock loom does not emit one, "
            "so an uninstrumented atomic cannot be ruled out from the output alone"
        )
