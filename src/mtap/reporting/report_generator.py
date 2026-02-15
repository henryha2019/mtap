from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, PackageLoader, ChoiceLoader, select_autoescape

from mtap.reporting.logger import LOG_SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quantile(values: List[int], q: float) -> int:
    if not values:
        return 0
    xs = sorted(values)
    # nearest-rank method
    idx = int(round((len(xs) - 1) * q))
    idx = max(0, min(len(xs) - 1, idx))
    return int(xs[idx])


@dataclass(frozen=True)
class ReportPaths:
    run_dir: Path
    events_jsonl: Path
    events_csv: Path
    summary_json: Path
    coverage_csv: Path
    report_html: Path


def default_paths(run_dir: Path) -> ReportPaths:
    return ReportPaths(
        run_dir=run_dir,
        events_jsonl=run_dir / "events.jsonl",
        events_csv=run_dir / "events.csv",
        summary_json=run_dir / "results_summary.json",
        coverage_csv=run_dir / "coverage_matrix.csv",
        report_html=run_dir / "qualification_report.html",
    )


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_summary(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def generate_report(run_dir: Path, *, template_dir: Optional[Path] = None) -> Path:
    paths = default_paths(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    events = _read_jsonl(paths.events_jsonl)
    summary = _load_summary(paths.summary_json)

    run_id = str(summary.get("run_id", run_dir.name))
    batch_id = str(summary.get("batch_id", "UNKNOWN"))
    station_id = str(summary.get("station_id", "UNKNOWN"))
    stage = str(summary.get("stage", "UNKNOWN"))
    per_sn = summary.get("per_sn") or {}

    # SN rows (deterministic ordering)
    sn_rows = []
    fw_versions = set()
    for sn in sorted(per_sn.keys()):
        ss = per_sn[sn] or {}
        fw = str(ss.get("fw_version", "unknown"))
        fw_versions.add(fw)
        sn_rows.append(
            {
                "sn": sn,
                "fw": fw,
                "passed": bool(ss.get("passed", False)),
                "failures": list(ss.get("failures", [])),
            }
        )

    overall_passed = bool(summary.get("overall_passed", False))
    sn_count = len(sn_rows)

    # Failure summary table: one row per failing step, with attempt count aggregated from events
    attempt_count: Dict[Tuple[str, str], int] = {}
    last_message: Dict[Tuple[str, str], str] = {}
    last_code: Dict[Tuple[str, str], Optional[str]] = {}
    last_cmd: Dict[Tuple[str, str], str] = {}
    for ev in events:
        sn = str(ev.get("sn", ""))
        step = str(ev.get("test_step", ""))
        key = (sn, step)
        attempt = int(ev.get("attempt", 1) or 1)
        attempt_count[key] = max(attempt_count.get(key, 0), attempt)
        last_message[key] = str(ev.get("message", "") or "")
        last_code[key] = ev.get("error_code", None)
        last_cmd[key] = str(ev.get("command", "") or "")

    fail_rows = []
    for row in sn_rows:
        if row["passed"]:
            continue
        for f in row["failures"]:
            step_id = str(f.get("step_id", ""))
            key = (row["sn"], step_id)
            fail_rows.append(
                {
                    "sn": row["sn"],
                    "step_id": step_id,
                    "cmd": str(f.get("cmd", last_cmd.get(key, ""))),
                    "error_code": str(f.get("error_code", last_code.get(key, ""))),
                    "message": str(f.get("message", last_message.get(key, ""))),
                    "attempts": attempt_count.get(key, 1),
                }
            )
    # deterministic ordering
    fail_rows.sort(key=lambda x: (x["sn"], x["step_id"], x["error_code"]))

    # Duration stats per step (across all attempts)
    durations: Dict[str, List[int]] = {}
    for ev in events:
        step = str(ev.get("test_step", ""))
        d = int(ev.get("duration_ms", 0) or 0)
        durations.setdefault(step, []).append(d)

    duration_rows = []
    for step in sorted(durations.keys()):
        xs = durations[step]
        duration_rows.append(
            {
                "test_step": step,
                "count": len(xs),
                "p50": _quantile(xs, 0.50),
                "p95": _quantile(xs, 0.95),
            }
        )

    loaders = []
    if template_dir is not None:
        loaders.append(FileSystemLoader(str(template_dir)))
    else:
        # Prefer repo-local templates when running from a working tree, but fall back
        # to packaged templates for clean installs.
        loaders.append(FileSystemLoader(str(Path("templates"))))
        loaders.append(PackageLoader("mtap", "templates"))
    env = Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html", "xml"]))
    tpl = env.get_template("report.html")

    html = tpl.render(
        run_id=run_id,
        batch_id=batch_id,
        station_id=station_id,
        stage=stage,
        sn_count=sn_count,
        fw_versions=sorted(fw_versions),
        overall_passed=overall_passed,
        generated_at=_utc_now_iso(),
        log_schema_version=LOG_SCHEMA_VERSION,
        sn_rows=sn_rows,
        fail_rows=fail_rows,
        duration_rows=duration_rows,
        has_coverage=paths.coverage_csv.exists(),
    )

    paths.report_html.write_text(html, encoding="utf-8")
    return paths.report_html
