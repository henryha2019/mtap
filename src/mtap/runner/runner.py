from __future__ import annotations

import time
import importlib.resources as importlib_resources
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mtap.dut.protocol import E_TIMEOUT
from mtap.reporting.logger import RunLogger, StepEvent
from mtap.runner.client import DutClient
from mtap.runner.plan_loader import Plan, StepSpec, load_plan, load_plan_raw
from mtap.traceability.coverage import (
    generate_coverage_matrix,
    load_requirements,
    validate_coverage,
    write_csv,
)


@dataclass(frozen=True)
class StepAttemptResult:
    passed: bool
    error_code: Optional[str]
    message: str
    data: Dict[str, Any]
    duration_ms: int


@dataclass
class SnSummary:
    sn: str
    fw_version: str
    passed: bool
    failures: List[Dict[str, Any]]


@dataclass
class RunSummary:
    run_id: str
    batch_id: str
    station_id: str
    stage: str
    overall_passed: bool
    per_sn: Dict[str, SnSummary]


class TestRunner:
    def __init__(
        self,
        *,
        host: str,
        dut_port: int,
        timeout_s_default: float,
        run_dir: Path,
        batch_id: str,
        station_id: str,
        stage: str,
        plan_path: Path,
        sqlite_db_path: Optional[Path] = None,
    ) -> None:
        self.client = DutClient(host, dut_port, timeout_s_default)
        self.run_dir = run_dir
        self.logger = RunLogger(run_dir)
        self.batch_id = batch_id
        self.station_id = station_id
        self.stage = stage
        self.plan_path = plan_path

        self.plan: Plan = load_plan(plan_path, stage=stage)        # Traceability validation + coverage matrix (audit)
        reqs = None
        reqs_path = Path("traceability/req_traceability.yaml")
        if reqs_path.exists():
            reqs = load_requirements(reqs_path)
        else:
            # clean installs: fall back to packaged defaults
            try:
                txt = importlib_resources.files("mtap").joinpath("resources/req_traceability.yaml").read_text(encoding="utf-8")
                # load_requirements expects a Path; parse here with yaml via its internal parser
                import yaml
                reqs = (yaml.safe_load(txt) or {}).get("requirements", {})
            except Exception:
                reqs = None

        if reqs is not None:
            # Coverage should reason about full plan intent (ungated) to ensure no stage regressions.
            raw_plan = load_plan_raw(plan_path)
            step_pairs = [(s.id, list(s.req_ids)) for s in raw_plan.steps]
            validate_coverage(reqs, step_pairs)
            rows = generate_coverage_matrix(reqs, step_pairs)
            write_csv(run_dir / "coverage_matrix.csv", rows)

        # Optional SQLite store
        self.sqlite = None
        if sqlite_db_path is not None:
            from mtap.storage.sqlite_store import SQLiteStore
            self.sqlite = SQLiteStore(sqlite_db_path)

    def _ping_fw(self, sn: str) -> str:
        res = self.client.call("PING", sn)
        if res.ok:
            fw = str(res.data.get("fw", "unknown"))
            return fw
        return "unknown"

    def _evaluate_limits(self, step: StepSpec, data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[Any], Optional[str]]:
        """Return (passed, error_code, measurement, value, units)."""
        limits = step.limits
        if limits is None:
            return True, None, None, None, None

        field = limits.field
        measurement = str(field)
        value = data.get(field)
        units = limits.units

        if limits.equals is not None:
            passed = value == limits.equals
            return passed, (None if passed else "LIMIT_FAIL"), measurement, value, units

        # range
        mn = limits.min
        mx = limits.max
        passed = True
        if mn is not None and value is not None:
            passed = passed and (float(value) >= float(mn))
        if mx is not None and value is not None:
            passed = passed and (float(value) <= float(mx))
        return passed, (None if passed else "LIMIT_FAIL"), measurement, value, units

    def run_step(self, *, run_id: str, sn: str, fw_version: str, step: StepSpec) -> StepAttemptResult:
        cmd = step.cmd
        step_id = step.id
        step_name = step.name
        req_ids = list(step.req_ids or [])
        retries_allowed = int(step.retries)
        backoff_ms = int(step.backoff_ms)
        timeout_s = float(step.timeout_s or self.client.timeout_s)

        # per-step timeout override (client instance is simple; temporarily override)
        original_timeout = self.client.timeout_s
        self.client.timeout_s = timeout_s

        last: StepAttemptResult = StepAttemptResult(False, "E_INTERNAL", "Uninitialized", {}, 0)
        for attempt in range(1, retries_allowed + 2):
            t0 = time.time()
            res = self.client.call(cmd, sn)
            dt_ms = int((time.time() - t0) * 1000)

            passed = bool(res.ok)
            error_code = res.error_code
            message = res.message
            data = dict(res.data or {})
            data["req_ids"] = req_ids

            # Apply limit checks (may convert ok->fail)
            if passed:
                lim_ok, lim_ec, meas, val, units = self._evaluate_limits(step, data)
                if not lim_ok:
                    passed = False
                    error_code = lim_ec
            else:
                meas = None
                val = None
                units = None

            will_retry = (not passed) and (attempt <= retries_allowed)
            retry_reason = None
            if will_retry:
                retry_reason = error_code or "UNKNOWN"

            ev = StepEvent.make(
                run_id=run_id,
                batch_id=self.batch_id,
                station_id=self.station_id,
                stage=self.stage,
                sn=sn,
                fw_version=fw_version,
                test_step=step_id,
                command=cmd,
                attempt=attempt,
                retries_allowed=retries_allowed,
                timeout_s=timeout_s,
                backoff_ms=backoff_ms,
                duration_ms=dt_ms,
                passed=passed,
                error_code=error_code,
                measurement=meas,
                value=val,
                units=units,
                message=message,
                data={
                    "step_name": step_name,
                    "req_ids": req_ids,
                    "will_retry": will_retry,
                    "retry_reason": retry_reason,
                    "raw": res.raw,
                },
            )
            self.logger.log(ev)
            if self.sqlite is not None:
                self.sqlite.append(ev)

            last = StepAttemptResult(passed, error_code, message, data, dt_ms)
            if passed:
                break

            if will_retry and backoff_ms > 0:
                time.sleep(backoff_ms / 1000.0)

        self.client.timeout_s = original_timeout
        return last

    def run_sn(self, *, run_id: str, sn: str) -> SnSummary:
        fw = self._ping_fw(sn)
        failures: List[Dict[str, Any]] = []

        sn_passed = True
        for step in self.plan.steps:
            out = self.run_step(run_id=run_id, sn=sn, fw_version=fw, step=step)
            if not out.passed:
                sn_passed = False
                failures.append(
                    {
                        "step_id": step.id,
                        "cmd": step.cmd,
                        "error_code": out.error_code,
                        "message": out.message,
                        "duration_ms": out.duration_ms,
                        "data": out.data,
                    }
                )

        return SnSummary(sn=sn, fw_version=fw, passed=sn_passed, failures=failures)

    def run_batch(self, *, run_id: str, sns: List[str]) -> RunSummary:
        per_sn: Dict[str, SnSummary] = {}
        overall = True
        for sn in sns:
            s = self.run_sn(run_id=run_id, sn=sn)
            per_sn[sn] = s
            overall = overall and s.passed

        return RunSummary(
            run_id=run_id,
            batch_id=self.batch_id,
            station_id=self.station_id,
            stage=self.stage,
            overall_passed=overall,
            per_sn=per_sn,
        )
