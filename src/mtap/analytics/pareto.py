from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib

# Headless-safe backend for CI/Docker
matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def pareto_failures(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Return counts for pareto analysis from raw events.

    Counts are over FAILED ATTEMPTS (more sensitive to flakes).
    Outputs:
      - by_step: test_step -> failed_attempts
      - by_error: error_code -> failed_attempts
      - by_batch: batch_id -> failed_attempts
    """
    by_step: Dict[str, int] = {}
    by_error: Dict[str, int] = {}
    by_batch: Dict[str, int] = {}

    for ev in events:
        if bool(ev.get("passed", False)):
            continue
        step = str(ev.get("test_step", ""))
        code = str(ev.get("error_code", ""))
        batch = str(ev.get("batch_id", ""))
        by_step[step] = by_step.get(step, 0) + 1
        by_error[code] = by_error.get(code, 0) + 1
        by_batch[batch] = by_batch.get(batch, 0) + 1

    return {"by_step": by_step, "by_error": by_error, "by_batch": by_batch}


def write_pareto_csv(counts: Dict[str, Dict[str, int]], out_dir: Path) -> Dict[str, Path]:
    _ensure_dir(out_dir)
    out: Dict[str, Path] = {}

    for key, m in counts.items():
        path = out_dir / f"pareto_{key}.csv"
        items = sorted(m.items(), key=lambda kv: (-kv[1], kv[0]))
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([key.replace("by_", ""), "failed_attempts"])
            for name, c in items:
                w.writerow([name, c])
        out[key] = path

    return out


def plot_pareto(m: Dict[str, int], out_path: Path, *, title: str, top_n: int = 10) -> Path:
    items = sorted(m.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    plt.figure()
    plt.bar(labels, values)
    plt.title(title)
    plt.xlabel("category")
    plt.ylabel("failed attempts")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()
    return out_path
