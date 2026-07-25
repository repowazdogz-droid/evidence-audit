# Roadmap

## v0.1 (this release)

Reads recorded outputs and grades them. Analyzers for Kani, loom and `cargo test`. Four
Lean checks over recorded artifacts. Two acceptance tests running in CI against the case
studies.

## Deferred from v0.1

**(e) Vacuity probe.** Deciding whether a passing property could have failed on any input,
rather than inferring it from exploration counts. This is the check the whole tool is
pointed at, and it is out of v0.1 because doing it properly means running the verifier
with a mutated property and comparing, not reading a recorded output. That makes it a
tool runner, which v0.1 deliberately is not.

**A Lean case study.** Check (a) is implemented and unit-tested but has no recorded
instance in this repository, so the README does not claim it as a demonstrated catch. The
next case study should be a real Lean development where an `opaque` declaration stands in
the dependency cone of a theorem that appears to prove something about a real value.

**Instrumented-operation counts from loom.** v0.1 reads a harness-emitted
`LOOM INSTRUMENTED OPS:` line, which nothing in stock loom produces. Either a small loom
patch or a harness macro would make the strongest signal available by default, rather than
by convention.

**Comparability inference.** The comparative rule currently trusts the caller's grouping.
Recording harness parameters alongside outputs, so that thread counts and bounds travel
with the run, would let the tool group runs itself and refuse comparisons it should not
make.

## Not planned

Running verifiers. Other tools do that well, and a grader that also runs the tool inherits
the tool's failure modes at the moment it is supposed to be judging them.
