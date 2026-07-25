"""Command line: grade recorded verification outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzers import analyze_file
from .grade import evidence_score, grade_cohort


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="evidence-audit",
        description="Grade recorded verification outputs by what they establish.",
    )
    ap.add_argument("paths", nargs="+", help="output files, or directories of them")
    ap.add_argument("--json", action="store_true", help="emit the records as JSON")
    ap.add_argument(
        "--cohort",
        action="store_true",
        help="compare the given runs against each other as one experiment "
             "(you are asserting they are comparable; the tool cannot check that)",
    )
    args = ap.parse_args(argv)

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.is_file() and q.suffix in (".txt", ".log")))
        else:
            files.append(p)

    records = [analyze_file(f) for f in files]
    if args.cohort:
        grade_cohort(records)
    else:
        from .grade import grade_one

        for r in records:
            grade_one(r)

    if args.json:
        print(json.dumps([r.to_dict() for r in records], indent=2))
        return 0

    for r in sorted(records, key=evidence_score):
        grade = r.grade.name if r.grade else "?"
        count = r.primary_exploration
        shown = count if count is not None else "-"
        print(f"{grade:<7} {r.verdict:<5} {r.tool:<10} explored={shown:<8} {r.source}")
        for f in r.flags:
            marker = "!!" if f.proves_inert else " !"
            print(f"        {marker} {f.code}: {f.message}")
        for note in r.grade_notes:
            print(f"         . {note}")
        for u in r.undetectable:
            print(f"         ? cannot tell from this output: {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
