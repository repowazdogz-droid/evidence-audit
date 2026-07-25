# Case 03 — A concurrency model checker that passed while modelling nothing

**What this case exhibits:** the headline exhibit is `output-B-unshimmed-LOSTUPDATE-FALSE-GREEN.txt`
— loom reports `1 passed` on a build containing a textbook lost update. The test runs, prints
green, and cannot fail, because the atomic it is supposed to be modelling is not a loom atomic.
Nothing in loom's output says so.

Two separate defects converge here: the check reads a label (`test result: ok`) that is
detached from the work it is supposed to summarise, and the check has no failing mode on the
input class it exists to detect. The only thing that distinguishes the inert test from the
real one is the execution counter and the negative control.

**Target:** `governor` v0.10.4, commit `9f3a79dd47dd32acd589c562b8d4fefe99b93372`, MIT.
**Tool:** `loom 0.7.2` (latest stable; no release since 2024-04-23).
**Date generated:** 2026-07-25.

## The 2×2 matrix

| | clean upstream code | injected lost update |
|---|---|---|
| **no `cfg(loom)` shim** | PASS — `LOOM EXPLORED 9 EXECUTIONS` (`output-A`) | **PASS — `LOOM EXPLORED 9 EXECUTIONS` (`output-B`) ← THE EXHIBIT** |
| **`cfg(loom)` shim applied** | PASS — `LOOM EXPLORED 54 EXECUTIONS` (`output-C`) | **FAIL — `got 2` (`output-D`)** |

Scaling, shimmed and clean: 3 threads → `LOOM EXPLORED 41958 EXECUTIONS`, 7.81 s (`output-E`).
2→3 threads is a ~777× increase in explored executions; 4 threads is very likely out of reach.

**Why the false green happens.** `governor`'s `InMemoryState` is
`portable_atomic::AtomicU64` (`src/state/in_memory.rs`), and the crate carries no `cfg(loom)`
shim. Loom only preempts at loom-instrumented synchronisation operations, so with an
uninstrumented atomic there is no preemption point between the load and the store, and the
interleaving that loses an update is unreachable by construction. The 9 executions it does
explore come from `loom::thread::spawn` and `loom::sync::Arc` alone.

**The detector.** The execution counter is what makes the inert run visible:
9 executions (uninstrumented) vs 54 (instrumented) on the identical test. A loom suite that
does not report how many executions it explored cannot be distinguished from one that
explores one.

## Reproduction

```sh
git clone https://github.com/boinkor-net/governor.git
cd governor && git checkout 9f3a79dd47dd32acd589c562b8d4fefe99b93372

# 1. install test + Cargo.toml additions (see cargo-toml-additions.txt)
cp /path/to/loom_spike_2threads.rs governor/tests/loom_spike.rs
cat /path/to/cargo-toml-additions.txt >> governor/Cargo.toml

# 2. run A — unshimmed, clean  → passes, 9 executions
cd governor && RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture

# 3. run B — unshimmed + lost update → STILL PASSES. the exhibit.
git apply ../lost-update.patch
RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture
git checkout src/state/in_memory.rs

# 4. run C — shim + clean → passes, 54 executions
git apply ../shim-cfg-loom.patch
RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture

# 5. run D — shim + lost update → FAILS "got 2"
git apply ../lost-update.patch
RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture

# 6. run E — shim + clean, 3 threads → 41958 executions
git checkout src/state/in_memory.rs && git apply ../shim-cfg-loom.patch
cp /path/to/loom_spike_3threads.rs tests/loom_spike.rs
RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture
```

The `[lints.rust] unexpected_cfgs` entry in `cargo-toml-additions.txt` is **required**:
`governor` sets `#![deny(warnings)]`, so an unknown `cfg` name is a hard build error, not a
warning. Reproducing case 03 alone needs `cfg(loom)` in the check-cfg list; reproducing it in
a tree that also carries case 02's harness needs `cfg(kani)` too.

Patch headers carry absolute scratch paths (produced by `diff -u` between working copies);
apply with `patch -p<n>` or re-create by hand. `shim-cfg-loom.patch` is a 4-line change to the
`use portable_atomic::AtomicU64;` line in `src/state/in_memory.rs`; `lost-update.patch`
replaces the compare-exchange retry loop in `measure_and_replace_one` with a plain
load/store.

## Scope

The shimmed result is an exhaustive search over the interleavings loom models, bounded at
2–3 threads, over `InMemoryState` only. It is not a proof. The keyed `DashMapStateStore` is
out of scope: its concurrency lives in third-party `dashmap` (6.2.1 vendored source contains
zero `loom` references, so it cannot be instrumented without patching another crate).
`FakeRelativeClock` remains an uninstrumented `Arc<portable_atomic::AtomicU64>` — unmodelled,
not wrong, because this test never advances the clock concurrently.
