from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

import random


@dataclass
class DeviceState:
    sn: str
    fw: str
    mode: str  # NORMAL | SAFE
    temp_c: float
    vbat_v: float

    temp_noise_sigma: float
    vbat_noise_sigma: float

    temp_drift_per_cycle_c: float
    vbat_drift_per_cycle_v: float

    # Fault-profile-induced offsets (e.g., drift engine)
    drift_offset_c: float = 0.0
    drift_offset_v: float = 0.0

    self_test_fail_p_base: float = 0.01
    burn_in_fail_slope: float = 0.00005

    cycles: int = 0
    last_update_s: float = 0.0


class DeviceModel:
    """Stateful DUT model with temperature + voltage + burn-in.

    Deterministic mode is achieved by injecting a seeded RNG.
    """

    def __init__(self, rng: random.Random, defaults: Dict) -> None:
        self._rng = rng
        self._defaults = defaults
        self._devices: Dict[str, DeviceState] = {}

    def get_or_create(self, sn: str) -> DeviceState:
        if sn not in self._devices:
            d = DeviceState(
                sn=sn,
                fw=str(self._defaults.get("fw", "1.0.0")),
                mode=str(self._defaults.get("mode", "NORMAL")).upper(),
                temp_c=float(self._defaults.get("temp_c", 25.0)),
                vbat_v=float(self._defaults.get("vbat_v", 12.0)),
                temp_noise_sigma=float(self._defaults.get("temp_noise_sigma", 0.05)),
                vbat_noise_sigma=float(self._defaults.get("vbat_noise_sigma", 0.02)),
                temp_drift_per_cycle_c=float(self._defaults.get("temp_drift_per_cycle_c", 0.0)),
                vbat_drift_per_cycle_v=float(self._defaults.get("vbat_drift_per_cycle_v", 0.0)),
                self_test_fail_p_base=float(self._defaults.get("self_test_fail_p_base", 0.01)),
                burn_in_fail_slope=float(self._defaults.get("burn_in_fail_slope", 0.00005)),
                cycles=0,
                last_update_s=time.time(),
            )
            if d.mode not in {"NORMAL", "SAFE"}:
                d.mode = "NORMAL"
            self._devices[sn] = d
        return self._devices[sn]

    def _update_signals(self, d: DeviceState) -> None:
        now = time.time()
        dt = max(0.0, now - d.last_update_s)
        d.last_update_s = now

        # Small time-based random walk (SAFE is more stable)
        wander_scale = 0.01 if d.mode == "NORMAL" else 0.005
        d.temp_c += wander_scale * dt * (self._rng.random() - 0.5)

        v_wander_scale = 0.005 if d.mode == "NORMAL" else 0.003
        d.vbat_v += v_wander_scale * dt * (self._rng.random() - 0.5)

        d.temp_c = min(max(d.temp_c, -40.0), 125.0)
        d.vbat_v = min(max(d.vbat_v, 9.0), 16.0)

    def _apply_burn_in(self, d: DeviceState) -> None:
        d.cycles += 1
        d.temp_c += d.temp_drift_per_cycle_c
        d.vbat_v += d.vbat_drift_per_cycle_v

    def ping(self, sn: str) -> Dict:
        d = self.get_or_create(sn)
        self._update_signals(d)
        return {
            "sn": d.sn,
            "fw": d.fw,
            "mode": d.mode,
            "vbat_v": round(d.vbat_v + d.drift_offset_v, 4),
        }

    def read_temp(self, sn: str) -> Dict:
        d = self.get_or_create(sn)
        self._apply_burn_in(d)
        self._update_signals(d)

        temp_true = d.temp_c + d.drift_offset_c
        vbat_true = d.vbat_v + d.drift_offset_v

        temp_meas = temp_true + self._rng.gauss(0.0, d.temp_noise_sigma)
        vbat_meas = vbat_true + self._rng.gauss(0.0, d.vbat_noise_sigma)

        return {
            "sn": d.sn,
            "temp_c": round(temp_meas, 4),
            "vbat_v": round(vbat_meas, 4),
            "cycles": d.cycles,
        }

    def self_test(self, sn: str) -> Dict:
        d = self.get_or_create(sn)
        self._apply_burn_in(d)
        self._update_signals(d)

        p_fail = d.self_test_fail_p_base + d.burn_in_fail_slope * d.cycles
        if d.mode == "SAFE":
            p_fail *= 0.7

        failed = self._rng.random() < p_fail
        return {
            "sn": d.sn,
            "self_test_ok": (not failed),
            "p_fail": round(p_fail, 6),
            "cycles": d.cycles,
        }

    def set_temp(self, sn: str, temp_c: float) -> Dict:
        d = self.get_or_create(sn)
        d.temp_c = float(temp_c)
        return {"sn": d.sn, "temp_c": round(d.temp_c, 4)}

    def set_mode(self, sn: str, mode: str) -> Dict:
        d = self.get_or_create(sn)
        m = mode.strip().upper()
        if m not in {"NORMAL", "SAFE"}:
            m = "NORMAL"
        d.mode = m
        return {"sn": d.sn, "mode": d.mode}
