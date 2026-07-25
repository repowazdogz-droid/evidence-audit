# evidence-audit — case studies (staging)

Launch evidence for the **evidence-audit** tool. Each case is a real, reproducible instance
of a verification artefact that reported success while establishing less than its output
implied. These are not hypotheticals and not reconstructions: every output file in here was
produced by running the tool on the code in the patch beside it, on this machine, on the
date in the case README.

Staged 2026-07-25 from a scoping session. **No tool code exists yet** — this directory is
collection only.

## Cases

| # | Case | Tool | The defect the case exhibits |
|---|---|---|---|
| 02 | `02-kani-vacuous-pass-governor` | Kani 0.67.0 | A two-assertion harness where the first injected bug fails assertion 1 and never reaches assertion 2. Assertion 2's PASS was uncharacterised until a second, independent bug was built. **Vacuous pass.** |
| 03 | `03-loom-false-green-governor` | loom 0.7.2 | A concurrency model checker reporting `1 passed` on a build containing a textbook lost update, because the atomic under test was never loom-instrumented. **False green / detached label.** |

Case numbering starts at 02 because 01 is reserved for the sequential-Kani baseline
(a passing harness with no defect), which is not yet staged.

## Why these two together

They are the two halves of the same question and they fail differently:

- **Case 02** — the check *could* fail, and did, but only on one of its two claims. The other
  claim was never exercised. You cannot see this from the verdict; you see it only by reading
  which checks were reached.
- **Case 03** — the check *could not* fail at all on the input class it exists to detect. The
  verdict, the exit code, and the test name were all correct and all uninformative.

Both were found the same way, and neither would have been found by reading the passing
output: **feed the check a known-bad input and confirm it goes red.** In case 03 the
supporting signal was quantitative — an execution counter showing 9 explored interleavings
uninstrumented versus 54 instrumented, on a byte-identical test.

## What a tool built on these would need to do

Stated as observations from the cases, not as a design:

1. Report per-assertion reachability, not just an aggregate verdict. Case 02's bug-A run says
   `1 of 611 failed`; it does not say that assertion 2 was never reached.
2. Demand a negative control per assertion, not per harness. One control passing is not
   evidence that a second assertion has a failing mode.
3. Surface the model's own size (executions explored, states visited, checks reached) so an
   inert run is distinguishable from a thorough one. Case 03 is invisible without it.
4. Distinguish a verdict that was *computed* from one that was *assigned* by a default or
   error path.

## Provenance

Both cases target `governor` v0.10.4, commit `9f3a79dd47dd32acd589c562b8d4fefe99b93372`
(MIT). No defect in `governor` is claimed or implied: every bug in these cases was
deliberately injected by us into a local copy in order to test our own checks. `governor`
passed every clean run.

Environment: Darwin 24.6.0 arm64, `rustc 1.95.0`, `kani 0.67.0`, `loom 0.7.2`.
