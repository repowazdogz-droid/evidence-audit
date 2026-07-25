"""Analyzer for recorded Kani (CBMC) output."""

from __future__ import annotations

import re

from ..record import Assertion, EvidenceRecord, Flag, Verdict

# "Check 9: some::path.assertion.3"
_CHECK = re.compile(r"^Check\s+(?P<n>\d+):\s+(?P<name>\S+)\s*$", re.M)
_STATUS = re.compile(r"^\s*-\s*Status:\s*(?P<status>\w+)\s*$", re.M)
_DESC = re.compile(r'^\s*-\s*Description:\s*(?P<desc>.*?)\s*$', re.M)

# "** 1 of 611 failed (6 unreachable)"
_SUMMARY = re.compile(
    r"\*\*\s+(?P<failed>\d+)\s+of\s+(?P<total>\d+)\s+failed"
    r"(?:\s+\((?P<unreachable>\d+)\s+unreachable\))?"
)
_VERIFICATION = re.compile(r"^VERIFICATION:-\s*(?P<v>\w+)", re.M)

# Kani wraps a user-authored assert! message in its own quotes, so a user
# assertion's Description is double-quoted while a compiler-generated one
# ("attempt to multiply with overflow") is single-quoted. This is the only
# discriminator available from the output text alone; see BLIND SPOTS below.
_USER_DESC = re.compile(r'^""(?P<msg>.*)""$', re.S)

_ASSERTION_NAME = re.compile(r"\.assertion\.\d+$")

#: Fraction of checks that must be UNDETERMINED before a pass is treated as inert.
UNDETERMINED_INERT_RATIO = 0.5


def sniff(text: str) -> bool:
    return "VERIFICATION:-" in text or "Manual Harness Summary" in text


def analyze(text: str, source: str = "<memory>") -> EvidenceRecord:
    rec = EvidenceRecord(source=source, tool="kani")

    m = _VERIFICATION.search(text)
    if m:
        rec.verdict = {"SUCCESSFUL": Verdict.PASS, "FAILED": Verdict.FAIL}.get(
            m.group("v").upper(), Verdict.UNKNOWN
        )

    sm = _SUMMARY.search(text)
    if sm:
        total = int(sm.group("total"))
        failed = int(sm.group("failed"))
        rec.exploration["checks_total"] = total
        rec.exploration["checks_failed"] = failed
        if sm.group("unreachable") is not None:
            unreachable = int(sm.group("unreachable"))
            rec.exploration["checks_unreachable"] = unreachable
            rec.exploration["checks_reached"] = total - unreachable
        if rec.verdict == Verdict.UNKNOWN:
            rec.verdict = Verdict.PASS if failed == 0 else Verdict.FAIL

    rec.assertions = _parse_checks(text)

    statuses = [a.status for a in rec.assertions]
    if statuses:
        undet = sum(1 for s in statuses if s == "UNDETERMINED")
        rec.exploration["checks_undetermined"] = undet

    rec.exploration["unwinding_assertions"] = len(
        re.findall(r"unwinding assertion loop", text)
    )

    _flag(rec, text)
    _record_undetectable(rec, text)
    return rec


def _parse_checks(text: str) -> list[Assertion]:
    out: list[Assertion] = []
    matches = list(_CHECK.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end() : end]
        sm = _STATUS.search(block)
        dm = _DESC.search(block)
        if not sm:
            continue
        raw_desc = dm.group("desc") if dm else ""
        um = _USER_DESC.match(raw_desc)
        name = m.group("name")
        out.append(
            Assertion(
                name=name,
                status=sm.group("status").upper(),
                description=um.group("msg") if um else raw_desc.strip('"'),
                user_authored=bool(um) and bool(_ASSERTION_NAME.search(name)),
            )
        )
    return out


def _flag(rec: EvidenceRecord, text: str) -> None:
    total = rec.exploration.get("checks_total")
    undet = rec.exploration.get("checks_undetermined", 0)

    # An overwhelmingly UNDETERMINED run has not decided the property. Kani
    # emits this when it hits an unsupported construct (e.g. a foreign C call).
    if total and undet and undet / total >= UNDETERMINED_INERT_RATIO:
        rec.flags.append(
            Flag(
                "MOSTLY_UNDETERMINED",
                f"{undet} of {total} checks are UNDETERMINED; the run did not decide the property",
                proves_inert=True,
            )
        )

    if "not currently supported by Kani" in text:
        rec.flags.append(
            Flag(
                "UNSUPPORTED_CONSTRUCT",
                "output reports a Rust construct Kani does not support; results past it are not decided",
            )
        )

    if "does not support concurrency" in text:
        rec.flags.append(
            Flag(
                "CONCURRENCY_SEQUENTIALISED",
                "Kani reports it compiled concurrent constructs as sequential; no interleaving was explored",
            )
        )

    # The case-02 defect: a user assertion that was never reached. Its SUCCESS
    # or absence carries no information about the property it states.
    for a in rec.assertions:
        if a.user_authored and a.status == "UNREACHABLE":
            rec.flags.append(
                Flag(
                    "USER_ASSERTION_UNREACHABLE",
                    f"assertion never exercised: {a.description!r} was UNREACHABLE in this run",
                )
            )


def _record_undetectable(rec: EvidenceRecord, text: str) -> None:
    if not rec.assertions:
        rec.undetectable.append(
            "per-check statuses absent from this output (summary-only capture); "
            "cannot tell whether any assertion was unreachable"
        )
    if rec.exploration.get("unwinding_assertions", 0) == 0:
        rec.undetectable.append(
            "no unwinding assertions in this output; cannot confirm loop bounds were sufficient"
        )
