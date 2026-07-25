"""Acceptance test: the case-02 vacuous pass, detected from output alone."""

from pathlib import Path

from evidence_audit import analyze_file, analyze_text
from evidence_audit.grade import grade_cohort, grade_one
from evidence_audit.record import Grade, Verdict

CASE = Path(__file__).resolve().parents[1] / "case-studies" / "02-kani-vacuous-pass-governor"


def test_bugA_run_is_flagged_assertion_never_exercised():
    """Required: from output-bugA.txt alone, the tool must report that an
    assertion was never exercised. The run failed on assertion 1; assertion 2
    was UNREACHABLE, so its status says nothing about the property it states."""
    rec = analyze_file(CASE / "output-bugA.txt")
    assert rec.tool == "kani"
    assert rec.verdict == Verdict.FAIL
    assert rec.has_flag("USER_ASSERTION_UNREACHABLE")
    msg = next(f.message for f in rec.flags if f.code == "USER_ASSERTION_UNREACHABLE")
    assert "never exercised" in msg
    assert "period boundary" in msg


def test_bugB_run_exercises_both_assertions():
    """The contrast that makes case 02 a case: bug B fails its own assertion
    while the other is reached and passes, so no unreachable flag is raised."""
    rec = analyze_file(CASE / "output-bugB.txt")
    assert rec.verdict == Verdict.FAIL
    assert not rec.has_flag("USER_ASSERTION_UNREACHABLE")
    statuses = {a.description[:20]: a.status for a in rec.assertions if a.user_authored}
    assert "FAILURE" in statuses.values()
    assert "SUCCESS" in statuses.values()


def test_clean_run_raises_no_flags():
    """Soundness priority 1: a clean run must not produce a false flag."""
    rec = analyze_file(CASE / "output-clean.txt")
    grade_one(rec)
    assert rec.verdict == Verdict.PASS
    assert [f.code for f in rec.flags] == []


def test_user_assertions_are_distinguished_from_compiler_checks():
    """Kani double-quotes a user assert! message. Compiler-generated checks are
    single-quoted. Only user assertions can be 'never exercised' in the sense
    the flag means."""
    rec = analyze_file(CASE / "output-bugA.txt")
    user = [a for a in rec.assertions if a.user_authored]
    compiler = [a for a in rec.assertions if not a.user_authored]
    assert len(user) == 2
    assert any("multiply with overflow" in a.description for a in compiler)


def test_mostly_undetermined_run_is_inert():
    """The other Kani inertness mode: an unsupported construct leaves nearly
    every check UNDETERMINED, which is not a safety result."""
    text = "\n".join(
        [f'Check {i}: foo.assertion.{i}\n\t - Status: UNDETERMINED\n\t - Description: "x"'
         for i in range(1, 21)]
        + ["** 0 of 20 failed", "VERIFICATION:- SUCCESSFUL"]
    )
    rec = analyze_text(text)
    grade_cohort([rec])
    assert rec.has_flag("MOSTLY_UNDETERMINED")
    assert rec.grade == Grade.INERT


def test_concurrency_sequentialised_is_flagged():
    """Kani compiles threads as sequential and says so. A pass under that
    warning explored no interleaving."""
    rec = analyze_text(
        "warning: Kani currently does not support concurrency. The following "
        "constructs will be treated as sequential operations:\n"
        "** 0 of 10 failed\nVERIFICATION:- SUCCESSFUL"
    )
    assert rec.has_flag("CONCURRENCY_SEQUENTIALISED")
