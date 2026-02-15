from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class YieldSummary:
    total_units: int
    fpy: float
    fty: float
    overall_pass_first_pass: int
    overall_pass_final: int
    flaky_rate: float  # fraction of step-instances that were fail->pass
    step_fail_rate_units: Dict[str, float]  # step -> fraction of units that failed at least once on step
    step_fail_rate_attempts: Dict[str, float]  # step -> failed_attempts / attempts


def _group_events(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_sn: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        sn = str(ev.get("sn", ""))
        by_sn.setdefault(sn, []).append(ev)
    # deterministic ordering
    for sn in by_sn:
        by_sn[sn].sort(key=lambda e: (str(e.get("test_step","")), int(e.get("attempt",1))))
    return by_sn


def compute_yields(events: List[Dict[str, Any]]) -> YieldSummary:
    """Compute manufacturing yield metrics from raw event logs only."""
    by_sn = _group_events(events)
    sns = sorted([sn for sn in by_sn.keys() if sn])

    # Determine final outcome per step per SN (max attempt)
    per_sn_step: Dict[Tuple[str, str], Dict[str, Any]] = {}
    per_sn_step_attempts: Dict[Tuple[str, str], int] = {}
    per_sn_step_any_fail: Dict[Tuple[str, str], bool] = {}

    all_steps = set()

    for sn in sns:
        for ev in by_sn[sn]:
            step = str(ev.get("test_step", ""))
            all_steps.add(step)
            key = (sn, step)
            att = int(ev.get("attempt", 1) or 1)
            per_sn_step_attempts[key] = max(per_sn_step_attempts.get(key, 0), att)
            if not bool(ev.get("passed", False)):
                per_sn_step_any_fail[key] = True
            # last attempt wins by attempt index
            if key not in per_sn_step or att >= int(per_sn_step[key].get("attempt", 1) or 1):
                per_sn_step[key] = ev

    steps_sorted = sorted([s for s in all_steps if s])

    # FPY: unit passes with ALL steps passing on attempt==1 (no retries)
    pass_first_pass = 0
    pass_final = 0

    # Flaky: step instance where at least one fail occurred and final outcome passed
    flaky_instances = 0
    total_step_instances = 0

    # Step fail rate (units)
    step_fail_units_count = {s: 0 for s in steps_sorted}

    # Step fail rate (attempts)
    step_attempts = {s: 0 for s in steps_sorted}
    step_failed_attempts = {s: 0 for s in steps_sorted}

    for sn in sns:
        unit_first_pass_ok = True
        unit_final_ok = True

        for step in steps_sorted:
            key = (sn, step)
            if key not in per_sn_step:
                # Missing step means unit didn't complete plan -> treat as fail
                unit_first_pass_ok = False
                unit_final_ok = False
                step_fail_units_count[step] += 1
                continue

            final_ev = per_sn_step[key]
            final_passed = bool(final_ev.get("passed", False))
            final_attempt = int(final_ev.get("attempt", 1) or 1)
            any_failed = bool(per_sn_step_any_fail.get(key, False))

            total_step_instances += 1

            # Unit fail on this step (at least once)
            if any_failed:
                step_fail_units_count[step] += 1

            # Attempts accounting (all attempts from raw logs)
            # Count attempts by scanning SN events for this step
            for ev in by_sn[sn]:
                if str(ev.get("test_step","")) != step:
                    continue
                step_attempts[step] += 1
                if not bool(ev.get("passed", False)):
                    step_failed_attempts[step] += 1

            # FPY requirement: final attempt must be 1 and passed, and no intermediate fails
            if not (final_passed and final_attempt == 1 and not any_failed):
                unit_first_pass_ok = False

            if not final_passed:
                unit_final_ok = False

            # Flaky instance: had failures but eventually passed
            if any_failed and final_passed:
                flaky_instances += 1

        if unit_first_pass_ok:
            pass_first_pass += 1
        if unit_final_ok:
            pass_final += 1

    total_units = len(sns) if sns else 0
    fpy = (pass_first_pass / total_units) if total_units else 0.0
    fty = (pass_final / total_units) if total_units else 0.0

    flaky_rate = (flaky_instances / total_step_instances) if total_step_instances else 0.0

    step_fail_rate_units = {s: (step_fail_units_count[s] / total_units if total_units else 0.0) for s in steps_sorted}
    step_fail_rate_attempts = {
        s: (step_failed_attempts[s] / step_attempts[s] if step_attempts[s] else 0.0) for s in steps_sorted
    }

    return YieldSummary(
        total_units=total_units,
        fpy=fpy,
        fty=fty,
        overall_pass_first_pass=pass_first_pass,
        overall_pass_final=pass_final,
        flaky_rate=flaky_rate,
        step_fail_rate_units=step_fail_rate_units,
        step_fail_rate_attempts=step_fail_rate_attempts,
    )


def write_yield_csv(summary: YieldSummary, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "yield_summary.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["total_units", summary.total_units])
        w.writerow(["fpy", round(summary.fpy, 6)])
        w.writerow(["fty", round(summary.fty, 6)])
        w.writerow(["overall_pass_first_pass", summary.overall_pass_first_pass])
        w.writerow(["overall_pass_final", summary.overall_pass_final])
        w.writerow(["flaky_rate", round(summary.flaky_rate, 6)])

    return path


def write_step_rates_csv(summary: YieldSummary, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "step_fail_rates.csv"

    steps = sorted(summary.step_fail_rate_units.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test_step", "fail_rate_units", "fail_rate_attempts"])
        for s in steps:
            w.writerow([s, round(summary.step_fail_rate_units[s], 6), round(summary.step_fail_rate_attempts[s], 6)])
    return path
