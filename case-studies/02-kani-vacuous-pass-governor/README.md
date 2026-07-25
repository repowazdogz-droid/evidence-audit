# Case 02. A passing verification harness that could not have failed

**What this case exhibits:** a Kani harness with two assertions, where the first injected
bug fails assertion 1 and *never exercises* assertion 2. Assertion 2's PASS in that run
carries zero bits: it was never reached. A second, independent bug is required to show
assertion 2 has a failing mode at all.

This is the vacuous-pass axis. The harness ran, returned a verdict, and the verdict was
correct, but one of its two claims was uncharacterised until a second control was built.

**Target:** `governor` v0.10.4, commit `9f3a79dd47dd32acd589c562b8d4fefe99b93372`
(github.com/boinkor-net/governor), MIT.
**Tool:** `kani 0.67.0` / `cargo-kani 0.67.0`, aarch64-apple-darwin.
**Date generated:** 2026-07-25.

## The evidence

| Run | Assertion 1 (`first cell was refused by a fresh limiter`) | Assertion 2 (`second cell admission did not match the GCRA period boundary`) | Verdict |
|---|---|---|---|
| clean upstream | SUCCESS | SUCCESS | `0 of 609 failed`, SUCCESSFUL |
| **bug A** (`t0 < earliest_time` → `t0 <= earliest_time`) | **FAILURE** | **not reached** | `1 of 611 failed`, FAILED |
| **bug B** (`tat - tau` → `tat - (tau + t)`) | SUCCESS | **FAILURE** | `1 of 621 failed`, FAILED |

Bug A alone would have licensed the sentence "the harness catches injected bugs." It does,
but only assertion 1 was ever shown to have a failing mode. Bug B is what makes assertion 2
evidence rather than decoration.

Outputs: `output-clean.txt`, `output-bugA.txt`, `output-bugB.txt`.
In `output-bugB.txt`, note `Check 8 ... assertion.2 - Status: SUCCESS` alongside
`Check 9 ... assertion.3 - Status: FAILURE`. Assertion 1 is exercised and passing in the
same run where assertion 2 fails. That co-occurrence is the point of the case.

## Reproduction

```sh
git clone https://github.com/boinkor-net/governor.git
cd governor && git checkout 9f3a79dd47dd32acd589c562b8d4fefe99b93372

# 1. install the harness
cp /path/to/kani_spike.rs governor/src/kani_spike.rs
# insert after the `mod gcra;` line in governor/src/lib.rs:
#     #[cfg(kani)]
#     mod kani_spike;

# 2. clean run
cd governor && cargo kani --harness second_cell_admitted_iff_period_elapsed

# 3. bug A
git apply ../bugA-boundary-off-by-one.patch     # (paths are relative to the repo root)
cargo kani --harness second_cell_admitted_iff_period_elapsed
git checkout governor/src/gcra.rs

# 4. bug B
git apply ../bugB-admits-too-early.patch
cargo kani --harness second_cell_admitted_iff_period_elapsed
```

Note: the patches in this directory were produced with `diff -u` between two working copies,
so their headers carry absolute scratch paths. Apply with `patch -p<n>` or re-create the
two one-line edits by hand. They are each a single changed line in
`governor/src/gcra.rs`, inside `Gcra::test_and_update`.

## Scope of what the clean run establishes

Symbolic proof over the assumed input region only: `elapsed <= 4 * PERIOD`, burst B=1, one
quota, exactly two `check()` calls, single-threaded. Not an unbounded ∀ over quotas or cell
counts. Kani treats concurrency as sequential (see case 03).
