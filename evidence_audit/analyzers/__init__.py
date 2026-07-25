"""Output analyzers. Order matters: the first module whose `sniff` accepts the
text owns it, so more specific tools are tried before more general ones."""

from __future__ import annotations

from pathlib import Path

from ..record import EvidenceRecord
from . import cargo_test, kani, loom

MODULES = (kani, loom, cargo_test)


def analyze_text(text: str, source: str = "<memory>") -> EvidenceRecord:
    for mod in MODULES:
        if mod.sniff(text):
            return mod.analyze(text, source=source)
    rec = EvidenceRecord(source=source, tool="unknown")
    rec.undetectable.append("no analyzer recognised this output format")
    return rec


def analyze_file(path: str | Path) -> EvidenceRecord:
    p = Path(path)
    return analyze_text(p.read_text(encoding="utf-8", errors="replace"), source=str(p))
