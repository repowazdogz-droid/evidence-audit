"""Acceptance test: case 04, the founding catch.

Two Lean models of the same Rust function. One pins the per-type sizes, the
other returns 0 for every type. The standard axiom audit cannot tell them
apart. Check (d) is asked to confirm that, rather than to catch it, because
confirming it IS the finding.
"""

from pathlib import Path

import pytest

from evidence_audit.lean import check_axiom_policy, check_opaque_in_cone
from evidence_audit.lean.checks import _declaration_bodies, _reachable

CASE = Path(__file__).resolve().parents[1] / "case-studies" / "04-lean-opaque-wrong-value"

THEOREMS = [
    "type_to_size_no_panic_uncond",
    "size_no_panic_uncond",
    "parse_one_no_panic_uncond",
    "parse_one_no_panic",
]
#: The axioms Lean reports for these theorems. Standard Lean axioms, not sorryAx.
POLICY = ["propext", "Classical.choice", "Quot.sound"]


def _sources(subdir: str) -> dict[str, str]:
    d = CASE / subdir
    return {p.name: p.read_text() for p in sorted(d.glob("*.lean"))}


# ---------------------------------------------------------------- check (d)
def test_axiom_captures_are_byte_identical():
    """The exhibit. Two different models, the same audit output, to the byte."""
    correct = (CASE / "axioms-correct-model.txt").read_bytes()
    wrong = (CASE / "axioms-wrong-value-model.txt").read_bytes()
    assert correct == wrong


def test_axiom_policy_cannot_distinguish_the_two_models():
    """Check (d) returns the same verdict and the same findings for both.

    This test passing is the finding, not a failure of the check. An axiom
    audit answers 'what did the kernel trust', and both models trust exactly
    the same things. It was never able to answer 'is this model faithful'.
    """
    correct = check_axiom_policy(
        (CASE / "axioms-correct-model.txt").read_text(), THEOREMS, allowed_axioms=POLICY
    )
    wrong = check_axiom_policy(
        (CASE / "axioms-wrong-value-model.txt").read_text(), THEOREMS, allowed_axioms=POLICY
    )
    assert correct.outcome == "PASS"
    assert wrong.outcome == "PASS"
    assert correct.outcome == wrong.outcome
    assert [f.message for f in correct.findings] == [f.message for f in wrong.findings]


def test_all_four_theorems_were_actually_reported():
    """Guard against the false-clean hazard: a PASS here must come from four
    matched axiom lines, not from four theorems being silently absent."""
    text = (CASE / "axioms-correct-model.txt").read_text()
    for thm in THEOREMS:
        assert f"'NoPanicRemodel.{thm}'" in text
    missing = check_axiom_policy(text, ["a_theorem_that_is_not_there"], allowed_axioms=POLICY)
    assert missing.outcome == "UNKNOWN"


# ---------------------------------------------------------------- check (a)
def test_opaque_in_cone_flags_rustSizeOf_in_the_opaque_model():
    """Check (a) reaches what the axiom audit structurally cannot see.

    `opaque` declarations never appear in `#print axioms` (see probe/), so an
    unspecified value behind one is invisible to check (d) by construction.
    """
    res = check_opaque_in_cone(_sources("model-opaque"), ["parse_one_no_panic"])
    assert res.outcome == "FAIL"
    assert any("rustSizeOf" in f.message for f in res.findings)
    assert all(f.severity == "CANDIDATE" for f in res.findings)


def test_opaque_in_cone_does_not_fire_on_the_typeclass_model():
    """Soundness: the model that pins its values must not be flagged."""
    res = check_opaque_in_cone(_sources("model"), ["parse_one_no_panic"])
    assert res.outcome == "PASS"


def test_the_typeclass_model_pass_is_not_blindness_to_axioms():
    """The PASS above must come from the axioms being outside the cone, not
    from the checker failing to parse them at all.

    Ground truth: Lean's own audit reports parse_one_no_panic depending on
    [propext, Classical.choice, Quot.sound] and NOT on the two extraction
    axioms, so the checker's cone agrees with the kernel here.
    """
    bodies = _declaration_bodies(_sources("model"))
    axioms = {n for n, (kind, _) in bodies.items() if kind in ("opaque", "axiom")}
    assert len(axioms) == 2, f"expected the two extraction axioms, got {sorted(axioms)}"
    cone = _reachable("parse_one_no_panic", bodies)
    assert "core.mem.size_of" in cone, "the cone must reach size_of for this case to mean anything"
    assert not (cone & axioms)
    capture = (CASE / "axioms-correct-model.txt").read_text()
    assert "core.option" not in capture


# ---------------------------------------------------- what did distinguish
def test_value_lemmas_are_what_caught_the_wrong_model():
    """The recorded Lean runs: rfl against the pinned sizes fails on the wrong
    model, and fails on a wrong asserted value. This is the discrimination the
    axiom audit could not provide."""
    wrong_model = (CASE / "value-lemmas-wrong-value-model-FAIL.txt").read_text()
    assert "Not a definitional equality" in wrong_model

    ninety_nine = (CASE / "value-lemma-99-FAIL.txt").read_text()
    assert "ok 99#usize" in ninety_nine
    assert "Not a definitional equality" in ninety_nine


def test_correct_model_build_had_no_errors():
    build = (CASE / "build-correct-model-full.txt").read_text()
    assert "Build completed successfully" in build
    assert "error" not in build


def test_minimal_probe_reproduces_the_invisibility():
    """A twelve-line file, no Aeneas, showing an opaque-backed theorem and a
    pinned-value theorem printing the same axiom line."""
    out = (CASE / "probe" / "probe-output.txt").read_text()
    assert out.count("does not depend on any axioms") == 2
    src = (CASE / "probe" / "Probe.lean").read_text()
    assert "opaque mySize" in src
    assert "class Sized" in src
