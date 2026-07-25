//! SPIKE-ONLY loom test. Run with: RUSTFLAGS="--cfg loom" cargo test --test loom_spike -- --nocapture
#![cfg(loom)]

use core::time::Duration;
use governor::clock::FakeRelativeClock;
use governor::{Quota, RateLimiter};
use loom::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering as StdOrdering};

/// Counts how many distinct executions loom actually ran (std atomic; loom does not reset it).
static EXECUTIONS: AtomicUsize = AtomicUsize::new(0);

/// Two threads, one shared direct rate limiter, quota = 1 cell / 100ns, burst 1.
/// Across ALL interleavings loom explores: exactly one of the two must be admitted
/// at t=0, and the post-join state must still refuse a third cell.
#[test]
fn at_most_one_cell_admitted_at_t0() {
    loom::model(|| {
        EXECUTIONS.fetch_add(1, StdOrdering::SeqCst);
        let clock = FakeRelativeClock::default();
        let quota = Quota::with_period(Duration::from_nanos(100)).unwrap();
        let lim = Arc::new(RateLimiter::direct_with_clock(quota, clock));

        let l1 = Arc::clone(&lim);
        let l2 = Arc::clone(&lim);
        let l3 = Arc::clone(&lim);
        let t1 = loom::thread::spawn(move || l1.check().is_ok());
        let t2 = loom::thread::spawn(move || l2.check().is_ok());
        let t3 = loom::thread::spawn(move || l3.check().is_ok());

        let admitted = (t1.join().unwrap() as u32) + (t2.join().unwrap() as u32) + (t3.join().unwrap() as u32);
        assert_eq!(admitted, 1, "expected exactly 1 admitted cell at t=0, got {admitted}");
        assert!(lim.check().is_err(), "lost update: a third cell was admitted at t=0");
    });
    println!("LOOM EXPLORED {} EXECUTIONS", EXECUTIONS.load(StdOrdering::SeqCst));
}
