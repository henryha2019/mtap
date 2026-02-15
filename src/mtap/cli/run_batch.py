from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from mtap.config import load_settings
from mtap.runner.runner import TestRunner
from mtap.reporting.report_generator import generate_report


def _parse_sns(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="MTAP batch test runner (multi-SN).")
    p.add_argument("--batch-id", required=True)
    p.add_argument("--station-id", required=True)
    p.add_argument("--sns", default="")
    p.add_argument("--stage", default="")
    p.add_argument("--plan", required=True, help="Path to test plan YAML")
    p.add_argument("--sqlite", default="", help="Optional path to SQLite db for events")
    args = p.parse_args(argv)

    s = load_settings()
    stage = args.stage or "EVT"

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    plan_path = Path(args.plan)
    sns = _parse_sns(args.sns) if args.sns else []

    # If sns not provided, auto-generate from plan sn_count if present
    if not sns:
        import yaml
        plan_raw = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        n = int(((plan_raw.get("batch") or {}).get("sn_count")) or 1)
        sns = [f"SN{str(i+1).zfill(4)}" for i in range(n)]

    runner = TestRunner(
        host=s.host,
        dut_port=s.dut_port,
        timeout_s_default=s.timeout_s,
        run_dir=run_dir,
        batch_id=args.batch_id,
        station_id=args.station_id,
        stage=stage,
        plan_path=plan_path,
        sqlite_db_path=Path(args.sqlite) if args.sqlite else None,
    )

    summary = runner.run_batch(run_id=run_id, sns=sns)

    (run_dir / "results_summary.json").write_text(
        json.dumps(
            {
                "run_id": summary.run_id,
                "batch_id": summary.batch_id,
                "station_id": summary.station_id,
                "stage": summary.stage,
                "overall_passed": summary.overall_passed,
                "per_sn": {
                    sn: {
                        "fw_version": ss.fw_version,
                        "passed": ss.passed,
                        "failures": ss.failures,
                    }
                    for sn, ss in summary.per_sn.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Qualification report (HTML)
    generate_report(run_dir)

    raise SystemExit(0 if summary.overall_passed else 1)


if __name__ == "__main__":
    main()
