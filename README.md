# evidence-audit

Grades recorded verification outputs by what they actually establish, rather than by the
verdict they print.

A verification run that passes has told you one of two things, and its output usually does
not distinguish them: the property holds, or the run could not have failed. This tool reads
recorded outputs from Kani, loom and `cargo test`, extracts what was actually explored, and
grades the run on that basis. It also runs four checks over recorded Lean artifacts.

Version 0.1. It reads recorded outputs. It does not run any verifier.

## Three catches, all demonstrated in this repository

Each has its inputs, its patches, its outputs and its reproduction commands under
`case-studies/`. Every output file was produced by running the named tool on the code in
the patch beside it.

**A concurrency model checker that passed while modelling nothing**
(`case-studies/03-loom-false-green-governor/`). A loom test reports `1 passed` on a build
containing a textbook lost update, because the atomic under test was never
loom-instrumented. The clean run and the broken run produce byte-identical output. What
separates them is an execution count: 9 explored interleavings uninstrumented against 54
instrumented, on the same test.

**A passing assertion that was never reached**
(`case-studies/02-kani-vacuous-pass-governor/`). A Kani harness with two assertions,
where the first injected bug fails assertion 1 and leaves assertion 2 UNREACHABLE.
Assertion 2's status in that run carries no information about the property it states. One
control was mistaken for two until a second, independent bug was built.

**An axiom audit that could not tell a faithful model from a wrong one**
(`case-studies/04-lean-opaque-wrong-value/`). Two Lean models of the same Rust function,
one pinning the real per-type sizes and one returning 0 for every type. Both prove the same
no-panic theorem, and `#print axioms` returns byte-identical output for both, same SHA-256.
What distinguished them was a set of value lemmas proved by `rfl`, which fail to compile on
the wrong model. An earlier model put the size behind an `opaque` declaration, which has no
value to check and never appears in `#print axioms` at all; a twelve-line probe in that case
reproduces the invisibility with no dependencies.

`case-studies/01-kani-sequential-jsonwebtoken/` is the baseline the others are measured
against: a harness where each assertion is separately shown to have its own failing mode.

## What it does

```sh
pip install -e .
evidence-audit case-studies/03-loom-false-green-governor --cohort
```

```
WEAK    PASS  loom       explored=9        .../output-A-unshimmed-clean.txt
WEAK    PASS  loom       explored=9        .../output-B-unshimmed-LOSTUPDATE-FALSE-GREEN.txt
WEAK    PASS  loom       explored=54       .../output-C-shimmed-clean.txt
SOUND   FAIL  loom       explored=-        .../output-D-shimmed-LOSTUPDATE-caught.txt
SOUND   PASS  loom       explored=41958    .../output-E-shimmed-clean-3threads.txt
```

Runs sort by evidential strength, weakest first. B and C both report `1 passed`; B sorts
below C because it explored a sixth as much. B and A are tied, which is the honest answer:
one of them contains a lost update and their outputs are identical.

The `--cohort` flag compares runs against each other. Without it, each run is graded only
on its own output.

## The grading rubric, as implemented

Two parts, because one number cannot carry both judgements.

**Categorical grade** (`evidence_audit/grade.py`), what kind of thing a run is:

| Grade | Meaning |
|---|---|
| `INVALID` | No verdict could be parsed from the output. |
| `INERT` | Passed, and the output shows the run could not have failed. |
| `WEAK` | Passed, but the exploration behind the pass is thin or unevidenced. |
| `SOUND` | Passed with substantive exploration, or failed for a real reason. |

A failing run grades `SOUND`. A run that actually failed has demonstrated that its checks
have a failing mode, which is exactly what an inert run cannot demonstrate.

**Exploration count**, which orders runs inside a grade. Two passes with the same
categorical grade and materially different exploration are not equally good evidence.
`evidence_score(record)` returns the pair, giving a total order. A run reporting no count
at all sorts below any run that reported one.

The comparative rule: within one tool and one verdict, a run that explored less than half
of the best comparable run is demoted and flagged. The threshold is deliberately loose so
that a demotion is only ever raised on a real gap. It is a constant in `grade.py`, not a
hardcoded pair of numbers, and the test suite checks the rule on synthetic counts as well
as on the recorded ones.

**Comparability is the caller's claim.** Nothing in a recorded output says which runs are
the same experiment. Thread counts, quotas and harness parameters do not appear in the
text. Group runs you believe are comparable, and read a demotion as "less was explored
here", not as "this run is wrong".

## Checks, with status and blind spot

| Check | Status in v0.1 | A PASS means | Blind spot |
|---|---|---|---|
| Kani output analyzer | IN | The output parsed, and no inertness pattern matched | Cannot see anything absent from the capture. A summary-only output has no per-check statuses, and the tool says so instead of scoring it |
| loom output analyzer | IN | The output parsed, and no inertness pattern matched | Stock loom reports neither an execution count nor an instrumented-operation count. Both are harness conventions. When they are missing the tool records the gap |
| `cargo test` analyzer | IN, thin | Tests passed | A test run reports only the inputs someone wrote a test for |
| (a) opaque-in-cone | IN, candidates only | No `opaque` or `axiom` declaration was reached from the named theorem, textually | Identifier matching is textual, so the cone over-approximates. A constant reached through a typeclass instance is missed. Findings are `CANDIDATE`, never `VIOLATION` |
| (b) sorry-in-statement | IN, lexical | No `sorry` token in a theorem's statement region | The statement/proof split is found by scanning for the first top-level `:=` or `by`, which an unusual term-mode layout can defeat |
| (c) placeholder scan | IN, lexical | No `sorry`, `admit`, `native_decide` or `#exit` outside comments | Token-level. A placeholder introduced by a macro is invisible. Reports presence, not reachability |
| (d) axiom-policy diff | IN, strongest of the four | Every named theorem has a reported axiom line, and every axiom is within policy | Parses a recorded capture, so a stale capture grades as current. Says nothing about whether the theorem states the intended property |
| (e) vacuity probe | OUT of v0.1 | | See `ROADMAP.md` |

Case 04 is what checks (a) and (d) are for, and it shows their division of labour. Check (d) returns the same PASS for both models, which is correct: an axiom audit reports what the kernel trusted, and both models trusted the same things. Check (a) reaches the one thing the audit cannot see, because an `opaque` declaration is not an axiom.

Check (d) carries the hazard that motivated it. `#print axioms Foo` reports the fully
qualified name, so `'Ns.Foo' depends on axioms: [...]`. A naive exact-name grep finds
nothing, and "found nothing" is textually identical to "no axioms". A required theorem
with no reported line resolves to `UNKNOWN`, never to `PASS`.

## The honest limit of v0.1

In case 03, the clean uninstrumented run and the lost-update uninstrumented run receive
**identical grades**, because their outputs are identical. The tool cannot tell them
apart, and a test asserts that it does not pretend to. What it does instead is decline to
certify either, and name what it could not determine. Every record carries an
`undetectable` list for exactly this: the absence of a flag must never read as the absence
of the problem.

## Prior art

These ideas are not new, and the calibration matters more than the novelty. Each sentence
below points at a body of work; the citations were resolved against Crossref, and none is
cited for a specific finding.

- Grading a passing check by whether it could have failed is the question mutation testing
  asks of a test suite. DeMillo, Lipton and Sayward, "Hints on Test Data Selection: Help
  for the Practicing Programmer", *Computer*, 1978. [doi:10.1109/c-m.1978.218136](https://doi.org/10.1109/c-m.1978.218136)
- A property that passes for a trivial reason is the subject of vacuity detection in model
  checking. Beer, Ben-David, Eisner and Rodeh, "Efficient Detection of Vacuity in Temporal
  Model Checking", *Formal Methods in System Design*, 2001.
  [doi:10.1023/a:1008779610539](https://doi.org/10.1023/a:1008779610539). Also Kupferman
  and Vardi, "Vacuity detection in temporal model checking", *STTT*, 2003.
  [doi:10.1007/s100090100062](https://doi.org/10.1007/s100090100062)
- Asking how much of a system a passing verification run actually touched is the subject of
  coverage metrics for model checking. Chockler, Kupferman and Vardi, "Coverage metrics for
  temporal logic model checking", *Formal Methods in System Design*, 2006.
  [doi:10.1007/s10703-006-0001-6](https://doi.org/10.1007/s10703-006-0001-6)
- loom's own README states that it permutes executions under the C11 memory model and uses
  state reduction techniques, linking to Norris and Demsky, "A Practical Approach for Model
  Checking C/C++11 Code", *ACM TOPLAS*, 2016. [doi:10.1145/2806886](https://doi.org/10.1145/2806886)

What this repository adds is not a new idea. It is two recorded instances of the failure
occurring in real tooling on a real crate, with the negative controls that establish them,
and a grader that reads the artifacts those runs leave behind.

## Provenance and scope of claims

Cases 02 and 03 target `governor` v0.10.4, commit `9f3a79dd47dd32acd589c562b8d4fefe99b93372`,
MIT. Case 01 targets `jsonwebtoken` v11.0.0, commit
`900010fb1be550ec2cfa8c32038eb154f9ef56d7`, MIT.

**No defect in `governor` or `jsonwebtoken` is claimed.** Every bug in these materials was
deliberately injected by us into a local copy in order to test our own checks. Both crates
passed every clean run. `targets/jsonwebtoken-spike/README.md` records a `u64` underflow
reachable in debug builds only when `leeway` exceeds the current Unix time, which is
fail-closed in release builds and is not presented as a security defect.

Environment that produced the recorded outputs: Darwin 24.6.0 arm64, `rustc 1.95.0`,
`kani 0.67.0`, `loom 0.7.2`.

## Development

```sh
python3 -m pytest tests/ -q
```

CI runs the same suite on every push. The two acceptance tests are
`tests/test_case03_loom_discriminator.py` and `tests/test_case02_kani_vacuous.py`.

MIT licensed.
