"""Lean checks (a)-(d).

These operate on recorded artifacts: Lean source text, and captured
`#print axioms` output. They do not invoke Lean. Check (d) is the strongest of
the four and the only one whose PASS is a statement about the kernel; (a) is
lexical and over-approximates, so it reports candidates rather than violations.

The axiom-parsing discipline here is carried over from the verify-mcp lean
tooling, including its central hazard: `#print axioms Foo` reports the
FULLY-QUALIFIED name (`'Ns.Foo' depends on axioms: [...]`), so a naive
exact-name grep finds nothing, and "found nothing" is textually identical to
"no axioms". A theorem with no line at all must therefore resolve to UNKNOWN,
never to PASS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: `'Name' depends on axioms: [a, b]` | `'Name' does not depend on any axioms`
_AXIOM_LINE = re.compile(
    r"'(?P<name>[^']+)'\s+(?:depends on axioms:\s*\[(?P<axioms>[^\]]*)\]"
    r"|does not depend on any axioms)"
)

_DECL = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+)*"
    r"(?P<kind>theorem|lemma|def|opaque|axiom|abbrev|instance)\s+(?P<name>[A-Za-z_][\w'.]*)",
    re.M,
)

#: Tokens that stand in for a proof or short-circuit the kernel.
PLACEHOLDER_TOKENS = {
    "sorry": "an admitted hole; the theorem is not proved",
    "admit": "an admitted hole",
    "native_decide": "delegates to compiled code, widening the trusted base beyond the kernel",
    "#exit": "halts elaboration; declarations after it are never checked",
}

#: Line comments and block comments, blanked before scanning so that a token
#: inside a comment is not reported as a real placeholder.
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/-.*?-/", re.S)


@dataclass
class Finding:
    check: str
    severity: str  # VIOLATION | CANDIDATE | UNKNOWN
    where: str
    message: str


@dataclass
class CheckResult:
    check: str
    outcome: str  # PASS | FAIL | UNKNOWN
    findings: list[Finding] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)


def strip_comments(text: str) -> str:
    """Blank comments while preserving line numbering."""
    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return _LINE_COMMENT.sub(blank, _BLOCK_COMMENT.sub(blank, text))


# --------------------------------------------------------------------------- a
def check_opaque_in_cone(sources: dict[str, str], theorems: list[str]) -> CheckResult:
    """(a) Does a named theorem's proof reach an `opaque` declaration?

    Lexical and OVER-APPROXIMATING: it follows identifier occurrences, not the
    elaborated dependency cone, so a name mentioned in a comment-free string or
    shadowed locally will be followed anyway. Findings are CANDIDATE, never
    VIOLATION, and must be confirmed against Lean's own environment.
    """
    res = CheckResult(check="a:opaque-in-cone", outcome="PASS")
    res.blind_spots = [
        "identifier matching is textual, so within the given sources the cone "
        "over-approximates: a name mentioned but not actually depended on is followed",
        "the cone also UNDER-approximates across the environment: anything declared "
        "outside the sources passed in is invisible, as is any dependency introduced "
        "by elaboration (typeclass instances, implicits, tactic-generated terms)",
        "does not invoke Lean; a PASS here is not a statement about the kernel. It is "
        "worth something only when checked against Lean's own audit, as case 04 does",
    ]

    bodies = _declaration_bodies(sources)
    opaques = {
        name for name, (kind, _body) in bodies.items() if kind in ("opaque", "axiom")
    }
    if not opaques:
        return res

    for thm in theorems:
        if thm not in bodies:
            res.outcome = "UNKNOWN"
            res.findings.append(
                Finding("a:opaque-in-cone", "UNKNOWN", thm,
                        f"no declaration named {thm!r} found in the given sources")
            )
            continue
        reached = _reachable(thm, bodies)
        hits = sorted(reached & opaques)
        if hits:
            res.outcome = "FAIL" if res.outcome != "UNKNOWN" else res.outcome
            for h in hits:
                res.findings.append(
                    Finding("a:opaque-in-cone", "CANDIDATE", thm,
                            f"{thm} may reach opaque/axiom declaration {h!r}; confirm in Lean")
                )
    return res


def _declaration_bodies(sources: dict[str, str]) -> dict[str, tuple[str, str]]:
    bodies: dict[str, tuple[str, str]] = {}
    for text in sources.values():
        clean = strip_comments(text)
        marks = list(_DECL.finditer(clean))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(clean)
            bodies[m.group("name")] = (m.group("kind"), clean[m.end() : end])
    return bodies


def _reachable(root: str, bodies: dict[str, tuple[str, str]]) -> set[str]:
    seen: set[str] = set()
    stack = [root]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in bodies:
            continue
        seen.add(cur)
        _kind, body = bodies[cur]
        for ident in re.findall(r"[A-Za-z_][\w'.]*", body):
            if ident in bodies and ident not in seen:
                stack.append(ident)
    seen.discard(root)
    return seen


# --------------------------------------------------------------------------- b
def check_sorry_in_statement(sources: dict[str, str]) -> CheckResult:
    """(b) Does `sorry` appear in a theorem's STATEMENT rather than its proof?

    A `sorry` in the proof means the theorem is unproved. A `sorry` in the
    statement means the theorem does not say what it appears to say, which is
    the worse and quieter failure.
    """
    res = CheckResult(check="b:sorry-in-statement", outcome="PASS")
    res.blind_spots = [
        "the statement/proof split is found by scanning for the first top-level ':=' "
        "or 'by', which a term-mode proof with an unusual layout can defeat",
        "lexical: reports the token, not an elaborated hole",
    ]

    for path, text in sources.items():
        clean = strip_comments(text)
        marks = list(_DECL.finditer(clean))
        for i, m in enumerate(marks):
            if m.group("kind") not in ("theorem", "lemma"):
                continue
            end = marks[i + 1].start() if i + 1 < len(marks) else len(clean)
            decl = clean[m.end() : end]
            split = _statement_end(decl)
            statement = decl[:split]
            if re.search(r"\bsorry\b", statement):
                line = clean.count("\n", 0, m.start()) + 1
                res.outcome = "FAIL"
                res.findings.append(
                    Finding("b:sorry-in-statement", "VIOLATION",
                            f"{path}:{line}",
                            f"'sorry' occurs in the STATEMENT of {m.group('name')}, "
                            f"so the theorem does not state what it appears to")
                )
    return res


def _statement_end(decl: str) -> int:
    depth = 0
    i = 0
    while i < len(decl):
        c = decl[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0:
            if decl.startswith(":=", i):
                return i
            if re.match(r"\bby\b", decl[i:]):
                return i
        i += 1
    return len(decl)


# --------------------------------------------------------------------------- c
def check_placeholder_scan(sources: dict[str, str]) -> CheckResult:
    """(c) Are proof placeholders or kernel-widening tactics present anywhere?"""
    res = CheckResult(check="c:placeholder-scan", outcome="PASS")
    res.blind_spots = [
        "token-level: a placeholder introduced by a macro or an imported tactic is invisible here",
        "reports presence, not reachability; a placeholder in dead code is still reported",
    ]

    for path, text in sources.items():
        clean = strip_comments(text)
        for token, why in PLACEHOLDER_TOKENS.items():
            pattern = re.escape(token) if token.startswith("#") else rf"\b{re.escape(token)}\b"
            for m in re.finditer(pattern, clean):
                line = clean.count("\n", 0, m.start()) + 1
                res.outcome = "FAIL"
                res.findings.append(
                    Finding("c:placeholder-scan", "VIOLATION", f"{path}:{line}",
                            f"{token!r}: {why}")
                )
    return res


# --------------------------------------------------------------------------- d
def check_axiom_policy(
    print_axioms_output: str,
    required_theorems: list[str],
    allowed_axioms: list[str] | None = None,
) -> CheckResult:
    """(d) Diff each theorem's actual axiom set against the policy.

    `allowed_axioms=None` means zero-axiom. `sorryAx` is never permitted,
    whatever the policy says.

    The false-clean hazard is handled explicitly: a required theorem with no
    reported line resolves to UNKNOWN, because absent output and clean output
    are the same text.
    """
    allowed = set(allowed_axioms or [])
    res = CheckResult(check="d:axiom-policy", outcome="PASS")
    res.blind_spots = [
        "parses recorded output; it does not re-run Lean, so a stale capture grades as current",
        "says nothing about whether the theorem states the intended property",
    ]

    reported = _parse_axiom_lines(print_axioms_output)

    for thm in required_theorems:
        matches = [full for full in reported if full == thm or full.endswith("." + thm)]
        if not matches:
            res.outcome = "UNKNOWN"
            res.findings.append(
                Finding("d:axiom-policy", "UNKNOWN", thm,
                        f"no '#print axioms' line for {thm!r}; absent output is not a clean result")
            )
            continue
        if len(matches) > 1:
            res.outcome = "UNKNOWN"
            res.findings.append(
                Finding("d:axiom-policy", "UNKNOWN", thm,
                        f"{thm!r} matches several reported names {matches!r}; cannot attribute")
            )
            continue
        axioms = reported[matches[0]]
        bad = sorted((set(axioms) - allowed) | ({"sorryAx"} & set(axioms)))
        if bad:
            if res.outcome != "UNKNOWN":
                res.outcome = "FAIL"
            res.findings.append(
                Finding("d:axiom-policy", "VIOLATION", matches[0],
                        f"{matches[0]} depends on disallowed axioms {bad!r}")
            )
    return res


def _parse_axiom_lines(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in _AXIOM_LINE.finditer(text):
        raw = m.group("axioms")
        out[m.group("name")] = (
            [a.strip() for a in raw.split(",") if a.strip()] if raw is not None else []
        )
    return out
