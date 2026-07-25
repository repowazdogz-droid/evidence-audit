// ---------------------------------------------------------------------------
// SPIKE-ONLY Kani harness. Not part of jsonwebtoken.
// Run: cargo kani -Z stubbing --harness ok_implies_exp_within_leeway
// ---------------------------------------------------------------------------
#[cfg(kani)]
mod kani_spike {
    use super::*;

    static mut STUB_NOW: u64 = 0;

    /// Stub replacing the wall-clock `get_current_timestamp()`.
    fn stub_now() -> u64 {
        unsafe { STUB_NOW }
    }

    /// Stub replacing `RandomState::new()`, which reaches the macOS
    /// `CCRandomGenerateBytes` FFI that Kani cannot model (kani#2423).
    /// RandomState is two u64 keys; all-zero is a valid deterministic instance.
    fn stub_random_state() -> std::collections::hash_map::RandomState {
        unsafe { std::mem::zeroed() }
    }

    fn any_exp() -> TryParse<u64> {
        match kani::any::<u8>() % 3 {
            0 => TryParse::Parsed(kani::any()),
            1 => TryParse::FailedToParse,
            _ => TryParse::NotPresent,
        }
    }

    #[kani::proof]
    #[kani::unwind(10)]
    #[kani::stub(crate::validation::get_current_timestamp, stub_now)]
    #[kani::stub(std::collections::hash_map::RandomState::new, stub_random_state)]
    fn ok_implies_exp_within_leeway() {
        let now: u64 = kani::any();
        let leeway: u64 = kani::any();
        kani::assume(now >= leeway); // underflow of `now - leeway` handled separately
        unsafe { STUB_NOW = now };

        let mut options = Validation::default(); // required_spec_claims = {"exp"}, reject_... = 0
        options.leeway = leeway;
        options.validate_aud = false;
        options.validate_nbf = false;
        options.validate_exp = kani::any();

        let exp = any_exp();
        let exp_val: Option<u64> = match exp {
            TryParse::Parsed(v) => Some(v),
            _ => None,
        };

        let claims: ClaimsForValidation<'static> = ClaimsForValidation {
            exp,
            nbf: TryParse::NotPresent,
            sub: TryParse::NotPresent,
            iss: TryParse::NotPresent,
            aud: TryParse::NotPresent,
        };

        if validate(claims, &options).is_ok() {
            // A1 — required-claim enforcement ("exp" is required by default).
            assert!(exp_val.is_some(), "A1: accepted a token with no exp while exp was required");
            // A2 — the expiry bound.
            if options.validate_exp {
                assert!(
                    exp_val.unwrap() >= now - leeway,
                    "A2: accepted a token whose exp is before now - leeway"
                );
            }
        }
    }
}

#[cfg(test)]
mod underflow_probe {
    use super::*;

    fn claims_with_exp(exp: u64) -> ClaimsForValidation<'static> {
        ClaimsForValidation {
            exp: TryParse::Parsed(exp),
            nbf: TryParse::NotPresent,
            sub: TryParse::NotPresent,
            iss: TryParse::NotPresent,
            aud: TryParse::NotPresent,
        }
    }

    /// Probe: is `now - options.leeway` reachable with leeway > now?
    #[test]
    fn leeway_greater_than_now() {
        let mut v = Validation::default(); // validate_exp = true, reject_... = 0
        v.validate_aud = false;
        v.leeway = u64::MAX;
        let now = get_current_timestamp();
        println!("PROBE: now = {now}, leeway = {}", v.leeway);
        let r = validate(claims_with_exp(0), &v);
        println!("PROBE: validate returned {r:?}");
    }

    /// Control: the same call with the default leeway must not panic.
    #[test]
    fn default_leeway_control() {
        let mut v = Validation::default();
        v.validate_aud = false;
        let r = validate(claims_with_exp(u64::MAX), &v);
        println!("CONTROL: validate returned {r:?}");
        assert!(r.is_ok(), "control should accept a far-future exp");
    }
}
