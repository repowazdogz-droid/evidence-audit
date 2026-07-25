"""Acceptance test: the case-03 discriminator, and the general rule behind it."""

from pathlib import Path

import pytest

from evidence_audit import analyze_file, analyze_text
from evidence_audit.grade import evidence_score, grade_cohort
from evidence_audit.record import Grade, Verdict

CASE = Path(__file__).resolve().parents[1] / "case-studies" / "03-loom-false-green-governor"


def _load_all():
    files = sorted(CASE.glob("output-*.txt"))
    assert len(files) == 5, f"expected all five case-03 outputs, found {len(files)}"
    return {f.name: analyze_file(f) for f in files}


def test_false_green_ranks_below_the_instrumented_pass():
    """The headline: two loom runs, both reporting `1 passed`, must not grade equal.

    Nothing here names 9 or 54. The rule is that materially different
    exploration behind the same verdict is materially different evidence.
    """
    recs = _load_all()
    grade_cohort(list(recs.values()))

    b = recs["output-B-unshimmed-LOSTUPDATE-FALSE-GREEN.txt"]
    c = recs["output-C-shimmed-clean.txt"]

    assert b.verdict == Verdict.PASS and c.verdict == Verdict.PASS
    assert evidence_score(b) < evidence_score(c)


def test_general_rule_is_not_tied_to_these_numbers():
    """Same rule on synthetic counts, so the test cannot pass by memorising 9 vs 54."""
    thin = analyze_text("LOOM EXPLORED 3 EXECUTIONS\ntest result: ok. 1 passed; 0 failed;")
    thick = analyze_text("LOOM EXPLORED 4000 EXECUTIONS\ntest result: ok. 1 passed; 0 failed;")
    grade_cohort([thin, thick])
    assert evidence_score(thin) < evidence_score(thick)
    assert thin.has_flag("LOW_RELATIVE_EXPLORATION")
    assert not thick.has_flag("LOW_RELATIVE_EXPLORATION")


def test_comparable_counts_are_not_demoted():
    """Soundness: a run that explored nearly as much is NOT flagged."""
    a = analyze_text("LOOM EXPLORED 90 EXECUTIONS\ntest result: ok. 1 passed; 0 failed;")
    b = analyze_text("LOOM EXPLORED 100 EXECUTIONS\ntest result: ok. 1 passed; 0 failed;")
    grade_cohort([a, b])
    assert not a.has_flag("LOW_RELATIVE_EXPLORATION")
    assert not b.has_flag("LOW_RELATIVE_EXPLORATION")


def test_zero_instrumented_ops_is_inert_regardless_of_count():
    """A loom run with no instrumented sync operations is flagged whatever it explored."""
    rec = analyze_text(
        "LOOM EXPLORED 999999 EXECUTIONS\n"
        "LOOM INSTRUMENTED OPS: 0\n"
        "test result: ok. 1 passed; 0 failed;"
    )
    grade_cohort([rec])
    assert rec.has_flag("LOOM_NO_INSTRUMENTED_OPS")
    assert rec.grade == Grade.INERT


def test_missing_instrumentation_count_is_recorded_as_undetectable():
    """Stock loom does not report instrumented ops. The absence of the flag must
    never read as the absence of the problem."""
    recs = _load_all()
    b = recs["output-B-unshimmed-LOSTUPDATE-FALSE-GREEN.txt"]
    assert any("instrumented-sync-op" in u for u in b.undetectable)


def test_the_two_unshimmed_runs_are_indistinguishable():
    """The honest limit of v0.1: clean and lost-update, both uninstrumented,
    produce identical output and therefore identical grades. The tool must not
    pretend otherwise."""
    recs = _load_all()
    grade_cohort(list(recs.values()))
    a = recs["output-A-unshimmed-clean.txt"]
    b = recs["output-B-unshimmed-LOSTUPDATE-FALSE-GREEN.txt"]
    assert evidence_score(a) == evidence_score(b)
