from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import random

from .protocol import E_BUSY, E_INTERNAL, E_TIMEOUT


@dataclass(frozen=True)
class TimeoutDecision:
    should: bool
    mode: str  # "delay" | "drop"
    delay_s: float


@dataclass(frozen=True)
class FailDecision:
    should: bool
    error_code: str
    message: str


@dataclass(frozen=True)
class BusyDecision:
    should: bool
    error_code: str
    message: str


@dataclass
class FaultContext:
    markov_state: str = "GOOD"  # GOOD | BAD
    last_cmd_ts: float = 0.0


class FaultInjector:
    """Industrial-grade fault injection with per-command toggles + Markov bursts."""

    def __init__(self, rng: random.Random, profile: Dict[str, Any]) -> None:
        self._rng = rng
        self.profile = profile
        self._ctx: Dict[Tuple[str, str], FaultContext] = {}

    def _cfg_for(self, cmd: str) -> Dict[str, Any]:
        base = (self.profile.get("default") or {})
        per = (self.profile.get("per_command") or {}).get(cmd, {}) or {}

        def merged(section: str) -> Dict[str, Any]:
            d = dict(base.get(section) or {})
            d.update(per.get(section) or {})
            return d

        return {
            "timeout": merged("timeout"),
            "fail": merged("fail"),
            "drift": merged("drift"),
            "burn_in": merged("burn_in"),
            "busy": merged("busy"),
        }

    def _ctx_for(self, sn: str, cmd: str) -> FaultContext:
        key = (sn, cmd)
        if key not in self._ctx:
            self._ctx[key] = FaultContext()
        return self._ctx[key]

    # ---- required APIs ----
    def should_timeout(self, cmd: str, sn: str, cycles: int) -> TimeoutDecision:
        cfg = self._cfg_for(cmd)["timeout"]
        p = float(cfg.get("p", 0.0))

        p_markov, delay_override = self._markov_timeout_add(cmd, sn)
        p_eff = min(1.0, p + p_markov)

        mode = str(cfg.get("mode", "delay")).lower()
        lo, hi = cfg.get("delay_s", [0.0, 0.0])
        delay = float(self._rng.uniform(float(lo), float(hi))) if float(hi) > 0 else 0.0
        if delay_override is not None:
            delay = delay_override

        return TimeoutDecision(should=(self._rng.random() < p_eff), mode=mode, delay_s=delay)

    def should_fail(self, cmd: str, sn: str, cycles: int) -> FailDecision:
        cfg = self._cfg_for(cmd)["fail"]
        p = float(cfg.get("p", 0.0))
        p *= self.burn_in_effect(cycles).get("fail_multiplier", 1.0)
        p = min(1.0, p + self._markov_fail_add(cmd, sn))

        if self._rng.random() < p:
            return FailDecision(True, E_INTERNAL, "Simulated intermittent/internal fault")
        return FailDecision(False, "", "")

    def apply_drift(self, cmd: str, cycles: int, *, temp_offset_c: float, vbat_offset_v: float) -> Tuple[float, float]:
        cfg = self._cfg_for(cmd)["drift"]
        dtemp = float(cfg.get("temp_offset_per_cycle_c", 0.0))
        dv = float(cfg.get("vbat_offset_per_cycle_v", 0.0))
        mult = self.burn_in_effect(cycles).get("drift_multiplier", 1.0)
        return (temp_offset_c + dtemp * mult, vbat_offset_v + dv * mult)

    def burn_in_effect(self, cycles: int) -> Dict[str, float]:
        # Use default burn_in config (common across commands)
        b = self._cfg_for("READ_TEMP")["burn_in"]
        k = cycles / 1000.0
        fail_mult = 1.0 + float(b.get("fail_p_multiplier_per_1k_cycles", 0.0)) * k
        drift_mult = 1.0 + float(b.get("drift_multiplier_per_1k_cycles", 0.0)) * k
        return {"fail_multiplier": max(0.0, fail_mult), "drift_multiplier": max(0.0, drift_mult)}

    def should_busy(self, cmd: str, sn: str) -> BusyDecision:
        cfg = self._cfg_for(cmd)["busy"]
        min_interval_ms = int(cfg.get("min_interval_ms", 0))
        p = float(cfg.get("p", 0.0))

        ctx = self._ctx_for(sn, cmd)
        now = time.time()

        # Deterministic rate limit
        if min_interval_ms > 0 and (now - ctx.last_cmd_ts) * 1000.0 < min_interval_ms:
            return BusyDecision(True, E_BUSY, f"Rate-limited: min_interval_ms={min_interval_ms}")

        # Probabilistic BUSY
        if p > 0 and self._rng.random() < p:
            return BusyDecision(True, E_BUSY, "Simulated resource contention (BUSY)")

        return BusyDecision(False, "", "")

    # ---- Markov intermittent ----
    def _markov_cfg(self) -> Dict[str, Any]:
        return self.profile.get("intermittent_markov") or {}

    def _markov_step(self, cmd: str, sn: str) -> str:
        m = self._markov_cfg()
        if not bool(m.get("enabled", False)):
            return "GOOD"
        ctx = self._ctx_for(sn, cmd)
        p_gb = float(m.get("p_good_to_bad", 0.0))
        p_bg = float(m.get("p_bad_to_good", 0.0))

        if ctx.markov_state == "GOOD" and self._rng.random() < p_gb:
            ctx.markov_state = "BAD"
        elif ctx.markov_state == "BAD" and self._rng.random() < p_bg:
            ctx.markov_state = "GOOD"
        return ctx.markov_state

    def _markov_fail_add(self, cmd: str, sn: str) -> float:
        m = self._markov_cfg()
        if not bool(m.get("enabled", False)):
            return 0.0
        st = self._markov_step(cmd, sn)
        if st != "BAD":
            return 0.0
        return float(m.get("fail_p_bad_state", 0.0))

    def _markov_timeout_add(self, cmd: str, sn: str) -> Tuple[float, Optional[float]]:
        m = self._markov_cfg()
        if not bool(m.get("enabled", False)):
            return 0.0, None
        st = self._markov_step(cmd, sn)
        if st != "BAD":
            return 0.0, None
        p = float(m.get("timeout_p_bad_state", 0.0))
        lo, hi = m.get("timeout_delay_s", [0.0, 0.0])
        delay = float(self._rng.uniform(float(lo), float(hi))) if float(hi) > 0 else None
        return p, delay

    # ---- server-facing evaluation ----
    def evaluate(self, cmd: str, sn: str, cycles: int) -> Dict[str, Any]:
        ctx = self._ctx_for(sn, cmd)
        ctx.last_cmd_ts = time.time()

        busy = self.should_busy(cmd, sn)
        if busy.should:
            return {"action": "RESPOND", "error_code": busy.error_code, "message": busy.message}

        fail = self.should_fail(cmd, sn, cycles)
        if fail.should:
            return {"action": "RESPOND", "error_code": fail.error_code, "message": fail.message}

        to = self.should_timeout(cmd, sn, cycles)
        if to.should:
            if to.mode == "drop":
                return {"action": "DROP", "delay_s": to.delay_s}
            return {"action": "DELAY", "delay_s": to.delay_s}

        return {"action": "PASS"}
