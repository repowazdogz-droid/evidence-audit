"""The graded evidence record: what a recorded verification run actually establishes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Grade(IntEnum):
    """How much a recorded run establishes about the property it was pointed at.

    This is an ordinal scale over *evidential strength*, not over good news.
    A run that FAILED sits at SOUND, because a real failure proves the check
    had a failing mode. A run that passed while unable to fail sits at INERT.
    """

    INVALID = 0  # no verdict could be parsed, or the tool itself errored
    INERT = 1  # passed, and the output shows it could not have failed
    WEAK = 2  # passed, but the exploration behind it is thin or unevidenced
    SOUND = 3  # passed with substantive exploration, or failed for a real reason


GRADE_REASON = {
    Grade.INVALID: "no verdict could be parsed from this output",
    Grade.INERT: "passed, but the output shows the run could not have failed",
    Grade.WEAK: "passed, but the exploration behind the pass is thin or unevidenced",
    Grade.SOUND: "passed with substantive exploration, or failed for a real reason",
}


class Verdict:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Flag:
    """A red flag raised against a run. `proves_inert` means the flag alone
    establishes that this run could not have produced a different answer."""

    code: str
    message: str
    proves_inert: bool = False


@dataclass(frozen=True)
class Assertion:
    name: str
    status: str  # SUCCESS | FAILURE | UNREACHABLE | UNDETERMINED
    description: str
    user_authored: bool


@dataclass
class EvidenceRecord:
    """One recorded run, parsed. `undetectable` is load-bearing: it names what
    this analyzer could NOT determine from this output, so that the absence of
    a flag is never read as the absence of the problem."""

    source: str
    tool: str
    verdict: str = Verdict.UNKNOWN
    exploration: dict[str, int] = field(default_factory=dict)
    assertions: list[Assertion] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    undetectable: list[str] = field(default_factory=list)
    grade: Grade | None = None
    grade_notes: list[str] = field(default_factory=list)

    @property
    def primary_exploration(self) -> int | None:
        """The single count used for cross-run comparison, if the tool reports one."""
        for key in ("executions_explored", "checks_reached"):
            if key in self.exploration:
                return self.exploration[key]
        return None

    def has_flag(self, code: str) -> bool:
        return any(f.code == code for f in self.flags)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "tool": self.tool,
            "verdict": self.verdict,
            "exploration": dict(self.exploration),
            "assertions": [
                {
                    "name": a.name,
                    "status": a.status,
                    "description": a.description,
                    "user_authored": a.user_authored,
                }
                for a in self.assertions
            ],
            "flags": [
                {"code": f.code, "message": f.message, "proves_inert": f.proves_inert}
                for f in self.flags
            ],
            "undetectable": list(self.undetectable),
            "grade": self.grade.name if self.grade is not None else None,
            "grade_notes": list(self.grade_notes),
        }
