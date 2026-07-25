/-- [core::mem::size_of]:
    Source: '/rustc/library/core/src/mem/mod.rs', lines 373:0-373:34
    Name pattern: [core::mem::size_of]
    Visibility: public -/
-- HAND-APPLIED PATCH (not produced by Aeneas; re-running the extraction will
-- overwrite it). Aeneas emits `axiom core.mem.size_of (T : Type) : Result
-- Std.Usize` because its standard library carries no model for
-- `core::mem::size_of`. As an axiom it admits `fail`, which is false of Rust:
-- `size_of::<T>()` is total for every `Sized` T. Modelling it as a total
-- definition removes the axiom and encodes that true fact.
--
-- The value is left unspecified. Aeneas's extraction erases layout, and the
-- relevant types are not provably distinct in Lean (`uapi.flat_binder_object`
-- and `uapi.binder_fd_object` differ only in a field name), so no per-type size
-- is provable here; asserting 24/40/32 would be unverifiable decoration. The
-- real sizes stay pinned by the `const _: () = { assert!(size_of::<..>() == ..) }`
-- checks in `remodel/src/lib.rs`. See PLAN.md §2-§4.
opaque rustSizeOf (T : Type) : Std.Usize

@[rust_fun "core::mem::size_of"]
def core.mem.size_of (T : Type) : Result Std.Usize := ok (rustSizeOf T)

/-- `size_of` is total: it always returns a value, never `fail`.
    This is what the `hsz` hypotheses in `NoPanicRemodel.lean` assumed. -/
theorem core.mem.size_of_total (T : Type) : ∃ n, core.mem.size_of T = ok n :=
  ⟨_, rfl⟩

/-- [core::option::{impl core::ops::try_trait::Try for core::option::Option<T>}::branch]:
    Source: '/rustc/library/core/src/option.rs', lines 2779:4-2779:64
    Name pattern: [core::option::{core::ops::try_trait::Try<core::option::Option<@T>>}::branch]
    Visibility: public -/
