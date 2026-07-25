# Case 04. An axiom audit that cannot tell a faithful model from a wrong one

Two Lean models of the same Rust function. One pins the per-type sizes to the real kernel
UAPI layout. The other returns 0 for every type. Both prove the same no-panic theorem, and
`#print axioms` returns **byte-identical output** for both.

That identity is the finding. An axiom audit answers "what did the kernel have to trust".
It was never able to answer "does this model correspond to the code", and on this pair it
visibly does not. What did distinguish the two models was a set of value lemmas proved by
`rfl` against the pinned sizes, which fail to compile on the wrong model.

**Upstream credit.** The spike being modelled is
[runtimeverification/kernel-rust-verification-spike](https://github.com/runtimeverification/kernel-rust-verification-spike),
a Runtime Verification feasibility study extracting Linux kernel Rust Binder parsers into
LLBC via Charon toward Lean 4 verification. The Binder deserializer, the union-free remodel,
the Charon and Aeneas extraction pipeline and the no-panic theorems are theirs. The
`RustSized` typeclass model, the wrong-value variant, the value lemmas and every run
recorded here are ours, made on a fork. **No defect in the upstream spike is claimed.**

Fork and branches used:
- `repowazdogz-droid/kernel-rust-verification-spike`, branch **`spike-typeclass`** at
  `4da5c96`: the `RustSized` typeclass model that pins sizes. This is the branch the
  correct and wrong-value variants come from.
- Same fork, branch **`discharge-size-of-axiom`** at `9b3408b`: the earlier model where
  `size_of` is `opaque rustSizeOf (T : Type) : Std.Usize`, an unspecified value. Used here
  for check (a).

Neither branch exists in the upstream repository. `git ls-remote --heads` on
`runtimeverification/kernel-rust-verification-spike` returns `main`, `improve-reports` and
`union-free-remodel` only. Both branches used here are ours, on the fork, so do not look
for them upstream.

Environment: Lean `v4.31.0`, Aeneas at `c2015b86`, mathlib per Aeneas's pin, Darwin 24.6.0
arm64. Recorded 2026-07-25.

## The exhibit

`axioms-correct-model.txt` and `axioms-wrong-value-model.txt` are the `#print axioms`
output for the four no-panic theorems, from the two models. They are identical:

```
$ diff axioms-correct-model.txt axioms-wrong-value-model.txt
$ shasum -a 256 axioms-correct-model.txt axioms-wrong-value-model.txt
b4faba10a3aeab78d9d349eed25f8ccbced39c6bdd44cda724af028d14231798  axioms-correct-model.txt
b4faba10a3aeab78d9d349eed25f8ccbced39c6bdd44cda724af028d14231798  axioms-wrong-value-model.txt
```

Both read:

```
'NoPanicRemodel.type_to_size_no_panic_uncond' depends on axioms: [propext, Classical.choice, Quot.sound]
'NoPanicRemodel.size_no_panic_uncond' depends on axioms: [propext, Classical.choice, Quot.sound]
'NoPanicRemodel.parse_one_no_panic_uncond' depends on axioms: [propext, Classical.choice, Quot.sound]
'NoPanicRemodel.parse_one_no_panic' depends on axioms: [propext, Classical.choice, Quot.sound]
```

The models differ only in five lines:

```
-instance : RustSized uapi.flat_binder_object     := ⟨24#usize⟩
-instance : RustSized uapi.binder_fd_object       := ⟨24#usize⟩
-instance : RustSized uapi.binder_buffer_object   := ⟨40#usize⟩
-instance : RustSized uapi.binder_fd_array_object := ⟨32#usize⟩
-instance : RustSized Std.Usize                   := ⟨8#usize⟩
+instance : RustSized uapi.flat_binder_object     := ⟨0#usize⟩
+instance : RustSized uapi.binder_fd_object       := ⟨0#usize⟩
+instance : RustSized uapi.binder_buffer_object   := ⟨0#usize⟩
+instance : RustSized uapi.binder_fd_array_object := ⟨0#usize⟩
+instance : RustSized Std.Usize                   := ⟨0#usize⟩
```

The no-panic theorem does not depend on the values, only on totality, so it proves either
way. A reader auditing the axiom output alone has no signal that anything changed.

One thing normalised, stated plainly: the wrong-value variant has the layout fidelity gate
removed, because those lemmas do not compile against it (see below). The four no-panic
`#print axioms` lines keep their original line positions in both files, so the comparison is
of like with like. The raw build output is `build-correct-model-full.txt`.

## What did distinguish them

`value-lemmas-wrong-value-model-FAIL.txt`: the wrong-value model with the layout gate left
in place fails to build.

```
error: NoPanicRemodel.lean:244:0: Not a definitional equality: the left-hand side
  core.mem.size_of uapi.flat_binder_object
is not definitionally equal to the right-hand side
  ok 24#usize
```

All five size lemmas fail, and so does `type_to_size_ptr`. On the correct model the same
lemmas close by `rfl` with no errors.

`value-lemma-99-FAIL.txt` is the mirror: correct instances, one lemma asserting the wrong
value.

```
error: NoPanicRemodel.lean:244:0: Not a definitional equality: the left-hand side
  core.mem.size_of uapi.flat_binder_object
is not definitionally equal to the right-hand side
  ok 99#usize
```

The lemmas are a real gate in both directions. They fail on a wrong model, and they fail on
a wrong claim about a correct model.

## Why `opaque` is worse than a wrong value

A wrong value is at least a value, and a `rfl` lemma can catch it. The earlier model made
`size_of` an `opaque` constant, which has no value to check and does not appear in the axiom
output at all.

`probe/Probe.lean` is a twelve-line file with no dependencies that shows this directly. Run
it with Lean v4.31.0:

```lean
opaque mySize (T : Type) : Nat
def sizeOf' (T : Type) : Option Nat := some (mySize T)
theorem sizeOf'_total (T : Type) : ∃ n, sizeOf' T = some n := ⟨_, rfl⟩

class Sized (T : Type) where size : Nat
def sizeOf2 (T : Type) [inst : Sized T] : Option Nat := some inst.size
theorem sizeOf2_total (T : Type) [Sized T] : ∃ n, sizeOf2 T = some n := ⟨_, rfl⟩

#print axioms sizeOf'_total
#print axioms sizeOf2_total
```

Output (`probe/probe-output.txt`):

```
'sizeOf'_total' does not depend on any axioms
'sizeOf2_total' does not depend on any axioms
```

An `opaque` declaration is not an axiom and never shows up in `#print axioms`. The two
theorems are indistinguishable by the audit, and one of them rests on a value nobody has
constrained.

This is why check (a), opaque-in-cone, exists. It reaches something `#print axioms` cannot
see by construction, rather than doing the same job better.

## What the checks do on this case

| Check | Correct model | Wrong-value model | Opaque model |
|---|---|---|---|
| (d) axiom-policy diff | PASS | PASS, findings identical | PASS |
| (a) opaque-in-cone | PASS | PASS | **FAIL**, flags `rustSizeOf` as `CANDIDATE` |

Check (a)'s PASS on the typeclass model is checked against ground truth rather than
trusted: the model contains two extraction `axiom` declarations, the checker parses both,
and they are genuinely outside `parse_one_no_panic`'s cone. Lean's own audit agrees, listing
only `propext, Classical.choice, Quot.sound` and no `core.option` axiom. A test asserts all
of that, so the PASS cannot come from the checker failing to see the axioms at all.

Check (a) remains a `CANDIDATE` finding, never a `VIOLATION`. Its cone is textual, so it
over-approximates within the files it is given and under-approximates across the wider
environment.

## Reproduction

Aeneas and mathlib take roughly an hour to build the first time. The probe needs neither.

```sh
# The probe, on its own, in about two seconds
elan run leanprover/lean4:v4.31.0 lean probe/Probe.lean

# The full case
git clone https://github.com/AeneasVerif/aeneas.git ~/aeneas-project/aeneas
cd ~/aeneas-project/aeneas && git checkout c2015b86
cd backends/lean && lake exe cache get && lake build Aeneas

git clone -b spike-typeclass \
  https://github.com/repowazdogz-droid/kernel-rust-verification-spike.git ~/kernel-rust-verification-spike
cd ~/kernel-rust-verification-spike/lean

# correct model: builds, value lemmas close by rfl
lake build NoPanicRemodel

# wrong-value model: set all five RustSized instances to 0 in SpikeBinderRemodel.lean
#   -> with the layout gate present, the build FAILS at the value lemmas
#   -> with the gate removed, it builds and prints the identical axiom lines
```

The spike repo must sit at `~/kernel-rust-verification-spike` for its lakefile to find
Aeneas at the relative path it expects.

`model/` holds the correct typeclass model as recorded. `model-opaque/` holds the earlier
opaque model from the other branch. Neither is modified from the fork.
