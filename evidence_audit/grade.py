"""The grading rubric.

Two stages. `grade_one` judges a run on its own output. `grade_cohort` adds the
only judgement that needs more than one run: two runs that reported the same
verdict, but explored materially different amounts, did not establish the same
thing, and must not receive the same grade.
"""

from __future__ import annotations

from .record import EvidenceRecord, Flag, Grade, Verdict

#: A run whose exploration count is below this fraction of the best comparable
#: run is treated as materially thinner. Deliberately loose: at 0.5 a run must
#: explore less than half as much before it is demoted, so the demotion is only
#: ever raised on a real gap.
MATERIAL_EXPLORATION_RATIO = 0.5


def grade_one(rec: EvidenceRecord) -> EvidenceRecord:
    """Grade a single run from its own output. Sets `rec.grade` and returns rec."""
    notes: list[str] = []

    if rec.verdict in (Verdict.UNKNOWN, Verdict.ERROR):
        rec.grade = Grade.INVALID
        notes.append("no usable verdict in this output")
        rec.grade_notes = notes
        return rec

    if rec.verdict == Verdict.FAIL:
        # A run that actually failed demonstrated that its checks have a failing
        # mode. Whatever else is wrong with it, it is not inert.
        rec.grade = Grade.SOUND
        notes.append("run failed for a real reason, so its checks demonstrably can fail")
        rec.grade_notes = notes
        return rec

    inert = [f for f in rec.flags if f.proves_inert]
    if inert:
        rec.grade = Grade.INERT
        notes.extend(f"could not have failed: {f.message}" for f in inert)
        rec.grade_notes = notes
        return rec

    grade = Grade.SOUND

    if rec.has_flag("USER_ASSERTION_UNREACHABLE"):
        grade = Grade.WEAK
        notes.append(
            "at least one user assertion was never exercised; its status carries no "
            "information about the property it states"
        )

    if rec.primary_exploration is None:
        grade = min(grade, Grade.WEAK)
        notes.append(
            "no exploration count in this output, so a thorough run and an inert one "
            "are indistinguishable from it"
        )

    rec.grade = grade
    rec.grade_notes = notes
    return rec


def evidence_score(rec: EvidenceRecord) -> tuple[int, int]:
    """A total order on evidential strength, for comparing runs.

    Two parts, because one number cannot carry both judgements. The first is the
    categorical grade: what kind of thing this run is. The second is how much it
    explored, which orders runs that land in the same category. Two passes with
    the same category and materially different exploration are not equally good
    evidence, and this is where that shows up.

    A run with no exploration count scores -1 on the second part: unevidenced
    ranks below any run that reported a count, and never above one.
    """
    grade = rec.grade if rec.grade is not None else Grade.INVALID
    count = rec.primary_exploration
    return (int(grade), count if count is not None else -1)


def grade_cohort(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Grade runs against each other as well as on their own terms.

    The comparative rule: within one tool and one verdict, a run that explored
    materially less than the best comparable run is demoted. This is what
    separates a pass that modelled the system from a pass that modelled almost
    nothing, when both printed the same verdict.

    COMPARABILITY IS THE CALLER'S CLAIM, NOT THE TOOL'S FINDING. Nothing in a
    recorded output says which runs are the same experiment: thread counts,
    quotas and harness parameters do not appear in the text. Passing runs from
    different configurations into one cohort will demote the smaller
    configuration for being smaller, which is not a defect finding. Group runs
    you believe are comparable, and read the demotion as "less was explored
    here", not as "this run is wrong".
    """
    for rec in records:
        grade_one(rec)

    groups: dict[tuple[str, str], list[EvidenceRecord]] = {}
    for rec in records:
        groups.setdefault((rec.tool, rec.verdict), []).append(rec)

    for (_tool, verdict), group in groups.items():
        if verdict != Verdict.PASS or len(group) < 2:
            continue
        counts = [
            r.primary_exploration for r in group if r.primary_exploration is not None
        ]
        if not counts:
            continue
        best = max(counts)
        if best <= 0:
            continue
        for rec in group:
            count = rec.primary_exploration
            if count is None or count >= best * MATERIAL_EXPLORATION_RATIO:
                continue
            rec.flags.append(
                Flag(
                    "LOW_RELATIVE_EXPLORATION",
                    f"explored {count} against {best} for a comparable run with the same "
                    f"verdict; the two passes do not establish the same thing",
                )
            )
            if rec.grade is not None and rec.grade > Grade.WEAK:
                rec.grade = Grade.WEAK
            rec.grade_notes.append(
                f"demoted: exploration {count} is below {MATERIAL_EXPLORATION_RATIO:g} "
                f"of the best comparable run ({best})"
            )

    return records
