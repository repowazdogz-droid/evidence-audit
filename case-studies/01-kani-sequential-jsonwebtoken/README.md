# Case 01. The baseline: a passing harness that was actually characterised

The other two cases are failures of characterisation. This one is the control:
a two-assertion Kani harness where **each assertion is shown to have its own failing
mode**, by a separate injected bug, with the other assertion still reached and passing in
the same run. It is what cases 02 and 03 are measured against.

**Target:** `jsonwebtoken` v11.0.0, commit `900010fb1be550ec2cfa8c32038eb154f9ef56d7`
(github.com/Keats/jsonwebtoken), MIT.
**Tool:** `kani 0.67.0` with `-Z stubbing` (RFC-0002), aarch64-apple-darwin.
**Date generated:** 2026-07-25.

## Property

    validate(claims, options).is_ok()
      ⟹ exp is present                                (A1, "exp" ∈ required_spec_claims)
      ∧ (options.validate_exp ⟹ exp ≥ now − leeway)    (A2)

`now` comes from a stub replacing the wall-clock `get_current_timestamp()`.

## The evidence

| Run | A1 | A2 | Verdict | Time |
|---|---|---|---|---|
| clean v11.0.0 | SUCCESS | SUCCESS | `0 of 3300 failed (46 unreachable)` | 271 s |
| bug 1, expiry comparison `<` → `>` | **SUCCESS** | **FAILURE** | `1 of 3300 failed` | 384 s |
| bug 2, required-claim enforcement dropped | **FAILURE** | **SUCCESS** | `1 of 3299 failed` | 317 s |

Read the two control rows together. Each fails exactly one assertion while the other is
reached and passes. Neither assertion is taking the other's word for it, and neither
passed only because it was never evaluated. Compare case 02, where one control was
mistaken for two.

Integrity of the clean pass: unwinding assertions present and passing, both assertions
reached (neither UNREACHABLE), zero UNDETERMINED checks.

## What made this harness hard

Two obstructions, both recorded in `targets/jsonwebtoken-spike/`:

1. `Validation::default()` builds a `HashSet<String>`, whose `RandomState::new()` reaches
   the macOS `CCRandomGenerateBytes` FFI that Kani cannot model
   ([kani#2423](https://github.com/model-checking/kani/issues/2423)). Symptom: `1 of 3428
   failed` with **3427 UNDETERMINED**. That run is the reference instance for this repo's
   `MOSTLY_UNDETERMINED` flag: a verdict was printed, and nothing was decided.
2. CBMC then diverged unwinding hashbrown's probe loop, killed at iteration 798 with no
   verdict. Fixed with `#[kani::unwind(10)]`. **That bound is load-bearing**: without it
   the harness does not terminate, and it is sound here only because the unwinding
   assertions pass.

## Reproduction

```sh
git clone https://github.com/Keats/jsonwebtoken.git
cd jsonwebtoken && git checkout 900010fb1be550ec2cfa8c32038eb154f9ef56d7
cat /path/to/validation_rs_appended_harness.rs >> src/validation.rs

cargo kani -Z stubbing --harness ok_implies_exp_within_leeway   # ~271 s, SUCCESSFUL

# controls, each on a fresh copy
patch -p1 < bug1-expiry-comparison-flip.patch && cargo kani -Z stubbing --harness ok_implies_exp_within_leeway
patch -p1 < bug2-drop-required-claims.patch   && cargo kani -Z stubbing --harness ok_implies_exp_within_leeway
```

Patch headers carry absolute paths from the machine that produced them; apply with
`patch -p<n>` or re-create by hand. Bug 1 is one character (`<` → `>`) at line 284. Bug 2
deletes the three-line `if !present { return Err(...) }` block.

## Scope

Symbolic proof over: `reject_tokens_expiring_in_less_than = 0`, `validate_aud = false`,
`validate_nbf = false`, `now ≥ leeway` assumed, `exp` ∈ {Parsed(any u64), FailedToParse,
NotPresent}, other claims NotPresent, loops unwound to 10. Silent on the aud/iss/sub
matching paths, on `nbf` validation, and on everything upstream of `validate()`:
signature verification, base64, JSON parsing.

No defect in `jsonwebtoken` is claimed. Both bugs here were injected by us into a local
copy to test our own harness. The clean run passed.
