# jsonwebtoken: Kani stubbing spike (pipeline target, confirmed)

Materials behind decision **D169**. Confirms that Kani function stubbing (RFC-0002) reaches
the real `validate()` path in `jsonwebtoken` v11.0.0.

**Target:** github.com/Keats/jsonwebtoken, commit `900010fb1be550ec2cfa8c32038eb154f9ef56d7`
(= tag `v11.0.0`, `version = "11.0.0"`), MIT.
**Tool:** `kani 0.67.0`, aarch64-apple-darwin. **Date:** 2026-07-25.

Not an evidence-audit case study. This is the pipeline target's feasibility spike. Kept
outside `~/evidence-audit-cases/` for that reason.

## Property

    validate(claims, options).is_ok()
      ⟹ exp is present                                    (A1, "exp" ∈ required_spec_claims)
      ∧ (options.validate_exp ⟹ exp ≥ now − leeway)        (A2)

with `now` supplied by a stub replacing the wall-clock `get_current_timestamp()`,
`reject_tokens_expiring_in_less_than = 0` (the default), and `assume(now ≥ leeway)`.

## Results

| Run | A1 | A2 | Verdict | Time |
|---|---|---|---|---|
| clean v11.0.0 | SUCCESS | SUCCESS | `0 of 3300 failed (46 unreachable)` | 271 s |
| bug 1, expiry comparison `<` → `>` | **SUCCESS** | **FAILURE** | `1 of 3300 failed` | 384 s |
| bug 2, required-claim enforcement dropped | **FAILURE** | **SUCCESS** | `1 of 3299 failed` | 317 s |

Each control fails its own assertion **with the other still exercised and passing in the same
run**. That is the point: one control is not enough to characterise a two-assertion harness.

Clean run integrity: unwinding assertions present and passing, both assertions reached
(neither UNREACHABLE), 0 UNDETERMINED checks.

## Two obstructions, both load-bearing

1. **`RandomState` → `CCRandomGenerateBytes`.** `Validation::default()` builds a
   `HashSet<String>`, whose `RandomState::new()` reaches a macOS Security-framework FFI that
   Kani cannot model (kani#2423). Symptom: `1 of 3428 failed`, **3427 UNDETERMINED**.
   Fix: stub `std::collections::hash_map::RandomState::new` with a zeroed instance
   (`RandomState` is two `u64` keys; all-zero is valid and deterministic).
2. **hashbrown probe-loop divergence.** With the FFI cleared, CBMC diverges unwinding
   `hashbrown::raw::RawTableInner::find_or_find_insert_slot_inner`, killed at **iteration
   798** after >10 min with no verdict (`output-diverged-no-unwind-bound.log`).
   Fix: `#[kani::unwind(10)]`. This bound is **load-bearing**: without it the harness does not
   terminate. It is sound here only because the unwinding assertions pass; if a future change
   makes 10 insufficient, Kani will fail the unwinding assertion rather than silently truncate.

**Cost to budget for the pipeline: ~5 min of CBMC per harness run.**

## Underflow probe (separate question)

`src/validation.rs:284` computes `now - options.leeway` on `u64` with no guard.
**VERIFIED REACHABLE**, debug builds:

    PROBE: now = 1784976283, leeway = 18446744073709551615
    panicked at src/validation.rs:284:68: attempt to subtract with overflow
    CONTROL: validate returned Ok(())        <- control passes in the same run

Release build (`--release`, overflow-checks off) wraps and returns `Err(ExpiredSignature)`,
fail-closed. Requires a caller to set `leeway` above the current Unix time (≈1.78×10⁹ s ≈ 56
years); the default is 60. **This is a debug-build panic on an absurd configuration, not an
authentication bypass, and no defect claim is made beyond that.**

Not probed: line 289's mirror case, `nbf > now + options.leeway` (addition overflow).

## Reproduction

```sh
git clone https://github.com/Keats/jsonwebtoken.git
cd jsonwebtoken && git checkout 900010fb1be550ec2cfa8c32038eb154f9ef56d7
cat /path/to/validation_rs_appended_harness.rs >> src/validation.rs

cargo kani -Z stubbing --harness ok_implies_exp_within_leeway   # ~271 s, SUCCESSFUL
cargo test --lib underflow_probe -- --nocapture                 # debug: panics
cargo test --release --lib underflow_probe -- --nocapture       # release: ExpiredSignature

# controls (each on a fresh copy)
patch -p1 < bug1-expiry-comparison-flip.patch  && cargo kani -Z stubbing --harness ok_implies_exp_within_leeway
patch -p1 < bug2-drop-required-claims.patch    && cargo kani -Z stubbing --harness ok_implies_exp_within_leeway
```

Patch headers carry absolute scratch paths (`diff -u` between working copies); apply with
`patch -p<n>` or re-create by hand. Bug 1 is one character (`<`→`>`) at line 284, bug 2
deletes the three-line `if !present { return Err(...) }` block.

## Scope of the clean result

Symbolic proof over: `reject_tokens_expiring_in_less_than = 0`, `validate_aud = false`,
`validate_nbf = false`, `now ≥ leeway`, `exp` ∈ {Parsed(any u64), FailedToParse, NotPresent},
all other claims NotPresent, loops unwound to 10. Silent on the aud/iss/sub matching paths,
on `nbf` validation, on non-zero `reject_tokens_expiring_in_less_than`, and on everything
upstream of `validate()` (signature verification, base64, JSON parsing).
