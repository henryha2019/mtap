import random
from mtap.dut.fault_injection import FaultInjector

def _profile(p_fail=0.03):
    return {
        "default": {
            "timeout": {"p": 0.0, "mode": "delay", "delay_s": [0.0, 0.0]},
            "fail": {"p": p_fail},
            "drift": {"temp_offset_per_cycle_c": 0.01, "vbat_offset_per_cycle_v": 0.001},
            "burn_in": {"fail_p_multiplier_per_1k_cycles": 0.2, "drift_multiplier_per_1k_cycles": 0.3},
            "busy": {"min_interval_ms": 0, "p": 0.0},
        },
        "per_command": {"PING": {"fail": {"p": 0.0}}},
        "intermittent_markov": {"enabled": False},
    }

def test_per_command_toggle():
    rng = random.Random(0)
    inj = FaultInjector(rng, _profile(p_fail=1.0))
    for _ in range(100):
        assert not inj.should_fail("PING", "SN1", cycles=0).should

def test_flaky_rate_controlled():
    rng = random.Random(123)
    inj = FaultInjector(rng, _profile(p_fail=0.03))
    n = 4000
    fails = 0
    for i in range(n):
        if inj.should_fail("READ_TEMP", "SN1", cycles=i).should:
            fails += 1
    rate = fails / n
    assert 0.02 <= rate <= 0.05

def test_drift_and_burn_in_increase_over_time():
    rng = random.Random(0)
    inj = FaultInjector(rng, _profile(p_fail=0.0))
    t, v = 0.0, 0.0
    t1, v1 = inj.apply_drift("READ_TEMP", cycles=0, temp_offset_c=t, vbat_offset_v=v)
    t2, v2 = inj.apply_drift("READ_TEMP", cycles=2000, temp_offset_c=t1, vbat_offset_v=v1)
    assert t2 > t1
    assert v2 > v1

def test_markov_bursts_exist():
    rng = random.Random(7)
    prof = _profile(p_fail=0.0)
    prof["intermittent_markov"] = {
        "enabled": True,
        "p_good_to_bad": 0.05,
        "p_bad_to_good": 0.2,
        "fail_p_bad_state": 0.8,
        "timeout_p_bad_state": 0.0,
        "timeout_delay_s": [0.0, 0.0],
    }
    inj = FaultInjector(rng, prof)

    run = 0
    max_run = 0
    for i in range(250):
        if inj.should_fail("READ_TEMP", "SN1", cycles=i).should:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    assert max_run >= 3
