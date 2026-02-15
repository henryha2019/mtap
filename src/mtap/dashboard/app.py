from __future__ import annotations

import json

import pandas as pd
import streamlit as st

st.title("MTAP Dashboard (minimal)")

uploaded = st.file_uploader("Upload results_summary.json", type=["json"])
if uploaded:
    summary = json.load(uploaded)
    st.metric("SN Count", summary.get("sn_count", 0))
    st.metric("Passed", summary.get("passed_count", 0))
    st.metric("Failed", summary.get("failed_count", 0))

    rows = []
    for sn, info in (summary.get("per_sn") or {}).items():
        rows.append({"sn": sn, "passed": info.get("passed", False), "failures": str(info.get("failures", []))})
    st.dataframe(pd.DataFrame(rows))
else:
    st.info("Run `make run-batch` then upload runs/<run>/results_summary.json")
