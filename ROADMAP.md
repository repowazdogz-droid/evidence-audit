# Roadmap

## v0.1 (this release)

Reads recorded outputs and grades them. Analyzers for Kani, loom and `cargo test`. Four
Lean checks over recorded artifacts. Three acceptance tests running in CI against the four
case studies, covering all three demonstrated catches.

## Deferred from v0.1

**(e) Vacuity probe.** Deciding whether a passing property could have failed on any input,
rather than inferring it from exploration counts. This is the check the whole tool is
pointed at, and it is out of v0.1 because doing it properly means running the verifier
with a mutated property and comparing, not reading a recorded output. That makes it a
tool runner, which v0.1 deliberately is not.

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
