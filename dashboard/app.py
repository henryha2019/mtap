from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for p in (REPO_ROOT, SRC_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


from dashboard.utils import file_fingerprint, parse_events_jsonl_bytes, compute_kpis, compute_unit_fty
from mtap.analytics.pareto import pareto_failures


st.set_page_config(page_title="MTAP Dashboard", layout="wide")


@st.cache_data(show_spinner=False)
def _load_df(data: bytes, max_rows: int) -> Tuple[pd.DataFrame, str]:
    fp = file_fingerprint(data)
    df = parse_events_jsonl_bytes(data, max_rows=max_rows)
    return df, fp


def _apply_filters(df: pd.DataFrame, *, stage: str, fw: str, batch: str, station: str) -> pd.DataFrame:
    out = df
    if stage != "ALL":
        out = out[out["stage"] == stage]
    if fw != "ALL":
        out = out[out["fw_version"] == fw]
    if batch != "ALL":
        out = out[out["batch_id"] == batch]
    if station != "ALL":
        out = out[out["station_id"] == station]
    return out


def _kpi_cards(df: pd.DataFrame) -> None:
    k = compute_kpis(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Units", f"{k['units']}")
    c2.metric("FPY", f"{k['fpy']*100:.1f}%")
    c3.metric("FTY", f"{k['fty']*100:.1f}%")
    c4.metric("Flaky rate", f"{k['flaky_rate']*100:.1f}%")


def _pareto_section(df: pd.DataFrame) -> None:
    st.subheader("Pareto")
    if df.empty:
        st.info("No data after filters.")
        return

    # Convert filtered df to events list for pareto computation
    events = df.to_dict(orient="records")
    counts = pareto_failures(events)

    col1, col2 = st.columns(2)
    with col1:
        st.caption("Top failing steps (failed attempts)")
        items = sorted(counts["by_step"].items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        if not items:
            st.write("—")
        else:
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            plt.figure()
            plt.bar(labels, values)
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            st.pyplot(plt.gcf())
            plt.close()

    with col2:
        st.caption("Top error codes (failed attempts)")
        items = sorted(counts["by_error"].items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        if not items:
            st.write("—")
        else:
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            plt.figure()
            plt.bar(labels, values)
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            st.pyplot(plt.gcf())
            plt.close()


def _heatmap_section(df: pd.DataFrame) -> None:
    st.subheader("Failure heatmap")
    if df.empty:
        st.info("No data after filters.")
        return

    mode = st.radio("Heatmap type", ["Step vs Batch", "Step vs Temp bin"], horizontal=True)

    fails = df[df["passed"] == False].copy()
    if fails.empty:
        st.success("No failures in filtered data.")
        return

    if mode == "Step vs Batch":
        x_field = "batch_id"
        fails[x_field] = fails[x_field].fillna("UNKNOWN")
    else:
        x_field = "temp_bin"
        # derive temp_bin by SN: use last known temp_bin per SN (from temp measurements)
        temp_meas = df[df["measurement"] == "temp_c"].copy()
        if temp_meas.empty:
            st.warning("No temp measurements found; temp-bin heatmap unavailable.")
            return
        last_temp = temp_meas.sort_values(["sn", "timestamp"]).groupby("sn").tail(1)[["sn", "temp_bin"]]
        fails = fails.merge(last_temp, on="sn", how="left", suffixes=("", "_sn"))
        fails["temp_bin"] = fails["temp_bin_sn"].fillna("UNKNOWN")
        fails.drop(columns=["temp_bin_sn"], inplace=True)
        fails[x_field] = fails[x_field].fillna("UNKNOWN")

    # Pivot counts
    pivot = fails.pivot_table(index="test_step", columns=x_field, values="sn", aggfunc="count", fill_value=0)

    plt.figure()
    plt.imshow(pivot.values, aspect="auto")
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    plt.title(f"Failures count: test_step vs {x_field}")
    plt.tight_layout()
    st.pyplot(plt.gcf())
    plt.close()

    st.caption("Values = failed attempts count (after filters).")
    st.dataframe(pivot)


def _sn_history_section(df: pd.DataFrame) -> None:
    st.subheader("SN timeline / history")
    if df.empty:
        st.info("No data after filters.")
        return

    sns = sorted([s for s in df["sn"].dropna().unique().tolist() if str(s)])
    if not sns:
        st.info("No SNs found.")
        return
    sn = st.selectbox("Select SN", sns)

    d = df[df["sn"] == sn].copy()
    d = d.sort_values(["timestamp", "test_step", "attempt"])

    # Show per-step outcomes (final attempt)
    last = d.sort_values(["test_step", "attempt"]).groupby("test_step").tail(1)[["test_step","passed","error_code","attempt","duration_ms"]]
    st.caption("Final outcome per step (latest attempt)")
    st.dataframe(last.reset_index(drop=True))

    # Timeline plot: attempt outcomes over time
    st.caption("Attempt timeline (pass/fail)")
    if d["timestamp"].isna().all():
        st.write("No valid timestamps.")
        return

    d["pass_int"] = d["passed"].astype(int)
    plt.figure()
    plt.plot(d["timestamp"], d["pass_int"], marker="o")
    plt.yticks([0,1], ["FAIL","PASS"])
    plt.xlabel("time (UTC)")
    plt.ylabel("result")
    plt.title(f"{sn} attempt outcomes over time")
    plt.tight_layout()
    st.pyplot(plt.gcf())
    plt.close()

    st.caption("Raw events for SN")
    st.dataframe(d[["timestamp","test_step","command","attempt","passed","error_code","duration_ms","measurement","value"]])


def main() -> None:
    st.title("MTAP — Manufacturing Test Dashboard")

    st.sidebar.header("Input")
    uploaded = st.sidebar.file_uploader("Upload events.jsonl", type=["jsonl", "txt", "log"])
    max_rows = st.sidebar.number_input("Max rows to read (for huge logs)", min_value=1000, max_value=5_000_000, value=500_000, step=1000)

    if uploaded is None:
        st.info("Upload a MTAP `events.jsonl` to begin.")
        return

    data = uploaded.getvalue()
    df, fp = _load_df(data, int(max_rows))

    st.sidebar.header("Filters")
    stages = ["ALL"] + sorted([x for x in df["stage"].dropna().unique().tolist() if str(x)])
    fws = ["ALL"] + sorted([x for x in df["fw_version"].dropna().unique().tolist() if str(x)])
    batches = ["ALL"] + sorted([x for x in df["batch_id"].dropna().unique().tolist() if str(x)])
    stations = ["ALL"] + sorted([x for x in df["station_id"].dropna().unique().tolist() if str(x)])

    stage = st.sidebar.selectbox("Stage", stages)
    fw = st.sidebar.selectbox("FW", fws)
    batch = st.sidebar.selectbox("Batch", batches)
    station = st.sidebar.selectbox("Station", stations)

    dff = _apply_filters(df, stage=stage, fw=fw, batch=batch, station=station)

    st.caption(f"Loaded {len(df):,} events (fingerprint {fp}). Showing {len(dff):,} after filters.")
    _kpi_cards(dff)

    tabs = st.tabs(["Overview", "Pareto", "Heatmap", "SN History", "Raw"])
    with tabs[0]:
        st.subheader("Overview")
        unit_final = compute_unit_fty(dff)
        if not unit_final.empty:
            st.write("Final unit outcome (FTY) per SN")
            st.dataframe(unit_final.rename("final_passed").reset_index().rename(columns={"index":"sn"}))
    with tabs[1]:
        _pareto_section(dff)
    with tabs[2]:
        _heatmap_section(dff)
    with tabs[3]:
        _sn_history_section(dff)
    with tabs[4]:
        st.subheader("Raw events")
        st.dataframe(dff)

if __name__ == "__main__":
    main()
