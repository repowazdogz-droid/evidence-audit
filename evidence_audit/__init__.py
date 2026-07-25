"""evidence-audit: grade recorded verification outputs by what they establish."""

__version__ = "0.1.0"

from .record import EvidenceRecord, Grade, Verdict  # noqa: F401
from .grade import grade_one, grade_cohort, evidence_score  # noqa: F401
from .analyzers import analyze_text, analyze_file  # noqa: F401
