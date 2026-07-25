//! SPIKE-ONLY Kani harness. Not part of governor.
//! Property under test (bounded instance of the GCRA rate guarantee):
//! with a quota of one cell per PERIOD nanoseconds and a burst of 1, a fresh
//! direct rate limiter admits its first cell, and admits the second cell
//! *exactly when* at least PERIOD nanoseconds have elapsed since the first.

use crate::clock::FakeRelativeClock;
use crate::{Quota, RateLimiter};
use core::time::Duration;

const PERIOD: u64 = 100;

#[kani::proof]
#[kani::unwind(3)]
fn second_cell_admitted_iff_period_elapsed() {
    let elapsed: u64 = kani::any();
    kani::assume(elapsed <= 4 * PERIOD); // keep the fake clock inside a small window

    let clock = FakeRelativeClock::default();
    let quota = Quota::with_period(Duration::from_nanos(PERIOD)).unwrap();
    let lim = RateLimiter::direct_with_clock(quota, clock.clone());

    // A fresh limiter must admit the very first cell.
    assert!(lim.check().is_ok(), "first cell was refused by a fresh limiter");

    clock.advance(Duration::from_nanos(elapsed));

    let second = lim.check().is_ok();
    assert_eq!(
        second,
        elapsed >= PERIOD,
        "second cell admission did not match the GCRA period boundary"
    );
}
