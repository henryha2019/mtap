from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class StratRow:
    key: str
    group: str
    units: int
    fty: float


def _final_pass_by_sn(events: List[Dict[str, Any]]) -> Dict[str, bool]:
    # Determine final pass per SN per step by max attempt; unit passes if all steps final passed
    per_sn_steps: Dict[Tuple[str, str], Dict[str, Any]] = {}
    steps = set()
    sns = set()

    for ev in events:
        sn = str(ev.get("sn",""))
        step = str(ev.get("test_step",""))
        sns.add(sn)
        steps.add(step)
        key = (sn, step)
        att = int(ev.get("attempt",1) or 1)
        if key not in per_sn_steps or att >= int(per_sn_steps[key].get("attempt",1) or 1):
            per_sn_steps[key] = ev

    steps = {s for s in steps if s}
    sns = {s for s in sns if s}

    out: Dict[str, bool] = {}
    for sn in sns:
        ok = True
        for step in steps:
            key = (sn, step)
            if key not in per_sn_steps:
                ok = False
                break
            if not bool(per_sn_steps[key].get("passed", False)):
                ok = False
                break
        out[sn] = ok
    return out


def stratify(events: List[Dict[str, Any]], *, key: str) -> List[StratRow]:
    """Compute FTY stratified by a field (fw_version, stage, batch_id, temp_bin)."""
    final_pass = _final_pass_by_sn(events)

    # Attach group values per SN
    group_by_sn: Dict[str, str] = {}

    if key in {"fw_version", "stage", "batch_id"}:
        # pick the first seen (stable via timestamp order in logs)
        for ev in events:
            sn = str(ev.get("sn",""))
            if sn in group_by_sn:
                continue
            group_by_sn[sn] = str(ev.get(key, "UNKNOWN"))
    elif key == "temp_bin":
        # derive from temperature measurements (measurement==temp_c); use average of PASS temps
        temps: Dict[str, List[float]] = {}
        for ev in events:
            if str(ev.get("measurement","")) != "temp_c":
                continue
            if not bool(ev.get("passed", False)):
                continue
            sn = str(ev.get("sn",""))
            v = ev.get("value", None)
            if v is None:
                continue
            try:
                temps.setdefault(sn, []).append(float(v))
            except Exception:
                continue
        for sn, xs in temps.items():
            if not xs:
                continue
            avg = sum(xs)/len(xs)
            # bins: <20, 20-30, 30-40, >=40
            if avg < 20:
                b = "<20C"
            elif avg < 30:
                b = "20-30C"
            elif avg < 40:
                b = "30-40C"
            else:
                b = ">=40C"
            group_by_sn[sn] = b
    else:
        raise ValueError(f"Unsupported stratification key: {key}")

    # Aggregate
    groups: Dict[str, List[str]] = {}
    for sn, passed in final_pass.items():
        g = group_by_sn.get(sn, "UNKNOWN")
        groups.setdefault(g, []).append(sn)

    rows: List[StratRow] = []
    for g in sorted(groups.keys()):
        sns = groups[g]
        units = len(sns)
        if units == 0:
            fty = 0.0
        else:
            fty = sum(1 for sn in sns if final_pass.get(sn, False)) / units
        rows.append(StratRow(key=key, group=g, units=units, fty=fty))

    return rows


def write_strat_csv(rows: List[StratRow], out_dir: Path, *, key: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"strat_{key}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "group", "units", "fty"])
        for r in rows:
            w.writerow([r.key, r.group, r.units, round(r.fty, 6)])
    return path
