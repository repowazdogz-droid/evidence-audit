"""Tests for Lean checks (a)-(d), including the false-clean hazard in (d)."""

from evidence_audit.lean import (
    check_axiom_policy,
    check_opaque_in_cone,
    check_placeholder_scan,
    check_sorry_in_statement,
)

CLEAN = {
    "Clean.lean": """
/-- An honest little theorem. -/
theorem refl_nat (n : Nat) : n = n := by rfl

theorem also_fine (n : Nat) : n + 0 = n := by simp
"""
}


def test_clean_source_passes_every_check():
    """Soundness priority 1: no false flags on clean input."""
    assert check_opaque_in_cone(CLEAN, ["refl_nat"]).outcome == "PASS"
    assert check_sorry_in_statement(CLEAN).outcome == "PASS"
    assert check_placeholder_scan(CLEAN).outcome == "PASS"


def test_comments_do_not_trigger_the_placeholder_scan():
    src = {"C.lean": "-- this proof used to contain sorry\n/- and sorry here too -/\ntheorem t : True := trivial\n"}
    assert check_placeholder_scan(src).outcome == "PASS"


def test_opaque_in_cone_reports_a_candidate_not_a_violation():
    src = {"O.lean": "opaque hidden : Nat\n\ntheorem leans_on_it : hidden = hidden := by rfl\n"}
    res = check_opaque_in_cone(src, ["leans_on_it"])
    assert res.outcome == "FAIL"
    assert [f.severity for f in res.findings] == ["CANDIDATE"]
    assert res.blind_spots


def test_sorry_in_statement_is_distinguished_from_sorry_in_proof():
    proof_hole = {"P.lean": "theorem t (n : Nat) : n = n := by sorry\n"}
    stmt_hole = {"S.lean": "theorem t : (sorry : Prop) := by trivial\n"}
    assert check_sorry_in_statement(proof_hole).outcome == "PASS"
    assert check_sorry_in_statement(stmt_hole).outcome == "FAIL"
    # but the placeholder scan catches the proof hole
    assert check_placeholder_scan(proof_hole).outcome == "FAIL"


def test_axiom_policy_matches_fully_qualified_names():
    out = "'MyNs.thm' does not depend on any axioms"
    assert check_axiom_policy(out, ["thm"]).outcome == "PASS"


def test_absent_axiom_line_is_unknown_not_pass():
    """The false-clean hazard: no output and clean output are the same text.
    A missing theorem must never grade as PASS."""
    res = check_axiom_policy("'Other.thm' does not depend on any axioms", ["missing_thm"])
    assert res.outcome == "UNKNOWN"
    assert res.findings[0].severity == "UNKNOWN"


def test_sorryAx_is_rejected_even_if_explicitly_allowed():
    out = "'N.t' depends on axioms: [sorryAx]"
    res = check_axiom_policy(out, ["t"], allowed_axioms=["sorryAx", "propext"])
    assert res.outcome == "FAIL"


def test_ambiguous_name_match_is_unknown():
    out = "'A.thm' does not depend on any axioms\n'B.thm' does not depend on any axioms"
    res = check_axiom_policy(out, ["thm"])
    assert res.outcome == "UNKNOWN"


def test_policy_allows_declared_axioms():
    out = "'N.t' depends on axioms: [propext, Quot.sound]"
    assert check_axiom_policy(out, ["t"], allowed_axioms=["propext", "Quot.sound"]).outcome == "PASS"
    assert check_axiom_policy(out, ["t"]).outcome == "FAIL"
