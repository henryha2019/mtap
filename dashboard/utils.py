from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


REQUIRED_COLS = [
    "timestamp", "sn", "batch_id", "station_id", "stage", "fw_version",
    "test_step", "command", "attempt", "passed", "error_code",
    "duration_ms", "measurement", "value",
]


def file_fingerprint(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()[:16]


def parse_events_jsonl_bytes(data: bytes, *, max_rows: Optional[int] = None) -> pd.DataFrame:
    """Parse MTAP JSONL event log bytes into a DataFrame.

    Designed for Streamlit upload use:
    - Line-by-line parsing (streaming friendly)
    - Keeps only stable columns needed for analytics/triage
    """
    rows: List[Dict[str, Any]] = []
    bio = io.BytesIO(data)
    i = 0
    for raw in bio:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw.decode("utf-8"))
        except Exception:
            # skip malformed line
            continue

        row = {k: ev.get(k, None) for k in REQUIRED_COLS}
        # Nested debug payload
        d = ev.get("data", {}) or {}
        row["retry_reason"] = d.get("retry_reason", None)
        row["will_retry"] = d.get("will_retry", None)

        rows.append(row)
        i += 1
        if max_rows is not None and i >= max_rows:
            break

    df = pd.DataFrame(rows)

    # Normalize types
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    for c in ["attempt", "duration_ms"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    if "passed" in df.columns:
        df["passed"] = df["passed"].astype(bool)

    # temp_bin derived from temp measurements (pass-only by default later)
    df["temp_bin"] = None
    m = df["measurement"] == "temp_c"
    if m.any():
        vals = pd.to_numeric(df.loc[m, "value"], errors="coerce")
        bins = pd.cut(vals, bins=[-1e9, 20, 30, 40, 1e9], labels=["<20C", "20-30C", "30-40C", ">=40C"])
        df.loc[m, "temp_bin"] = bins.astype(str)

    return df


def compute_unit_fty(df: pd.DataFrame) -> pd.Series:
    """Unit final pass per SN based on final attempt per (SN, step)."""
    if df.empty:
        return pd.Series(dtype=bool)
    # final attempt per sn+step
    last = df.sort_values(["sn", "test_step", "attempt"]).groupby(["sn", "test_step"]).tail(1)
    # unit pass if all steps final passed
    unit = last.groupby("sn")["passed"].all()
    return unit


def compute_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"units": 0, "fpy": 0.0, "fty": 0.0, "flaky_rate": 0.0}

    # FPY: all steps pass on attempt==1 and no fail attempts for that step
    by = df.sort_values(["sn", "test_step", "attempt"]).groupby(["sn", "test_step"])
    final = by.tail(1).copy()
    any_fail = by["passed"].apply(lambda s: (~s).any()).rename("any_fail")

    merged = final.merge(any_fail.reset_index(), on=["sn", "test_step"], how="left")
    merged["first_pass_ok_step"] = (merged["passed"] == True) & (merged["attempt"] == 1) & (merged["any_fail"] == False)

    unit_first_pass = merged.groupby("sn")["first_pass_ok_step"].all()
    unit_final = merged.groupby("sn")["passed"].all()

    units = int(unit_final.shape[0]) if unit_final is not None else 0
    fpy = float(unit_first_pass.mean()) if units else 0.0
    fty = float(unit_final.mean()) if units else 0.0

    # Flaky: step instance fail->pass
    merged["flaky_step"] = (merged["any_fail"] == True) & (merged["passed"] == True)
    flaky_rate = float(merged["flaky_step"].mean()) if merged.shape[0] else 0.0

    return {"units": units, "fpy": fpy, "fty": fty, "flaky_rate": flaky_rate}
