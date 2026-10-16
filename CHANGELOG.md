# Changelog

## Unreleased

- README: opens with the claim, a Try it block and a "What this does not show" section; test
  count (35) and the three CI acceptance tests stated to match `pytest` and `ci.yml`.
- Added `CITATION.cff` and this changelog.
- `case-studies/README.md`: replaced a stale staging note (2026-09-02).

No code change since v0.1.

## v0.1 (2026-07-25)

First release, tagged `v0.1`.

- Grades recorded outputs from Kani, loom and `cargo test` into `INVALID`, `INERT`, `WEAK` or
  `SOUND`, ordered within a grade by exploration count; `--cohort` demotes a pass that explored
  less than half of the best comparable run.
- Four checks over recorded Lean artifacts: opaque-in-cone (candidates only), sorry in a
  statement, placeholder scan, axiom-policy diff.
- Four case studies with inputs, patches, recorded outputs and reproduction commands
  (`jsonwebtoken` baseline, Kani unreachable assertion, loom uninstrumented atomic, Lean
  opaque and wrong-value model).
- Acceptance tests for cases 02, 03 and 04 run in CI.
- Directory scans read `output-*` files and report the files they skipped.
