from __future__ import annotations

from pathlib import Path
from typing import Optional

from mtap.analytics.io import read_events_jsonl
from mtap.analytics.yield_analysis import compute_yields, write_yield_csv, write_step_rates_csv
from mtap.analytics.pareto import pareto_failures, write_pareto_csv, plot_pareto
from mtap.analytics.stratification import stratify, write_strat_csv


def run_analytics(run_dir: Path) -> Path:
    """Run analytics from raw logs only. Writes CSV summaries + plots under run_dir/analytics/."""
    events = read_events_jsonl(run_dir / "events.jsonl")
    out_dir = run_dir / "analytics"
    out_dir.mkdir(parents=True, exist_ok=True)

    ys = compute_yields(events)
    write_yield_csv(ys, out_dir)
    write_step_rates_csv(ys, out_dir)

    pareto = pareto_failures(events)
    write_pareto_csv(pareto, out_dir)
    plot_pareto(pareto["by_step"], out_dir / "pareto_steps.png", title="Pareto: failing steps")
    plot_pareto(pareto["by_error"], out_dir / "pareto_error_codes.png", title="Pareto: error codes")
    plot_pareto(pareto["by_batch"], out_dir / "pareto_batches.png", title="Pareto: batches")

    for key in ["fw_version", "stage", "batch_id", "temp_bin"]:
        rows = stratify(events, key=key)
        write_strat_csv(rows, out_dir, key=key)

    return out_dir
