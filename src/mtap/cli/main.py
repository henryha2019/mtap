from __future__ import annotations

import argparse


def main() -> None:
    p = argparse.ArgumentParser(prog="mtap", description="Manufacturing Test Automation Platform (MTAP)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # dut
    p_dut = sub.add_parser("dut", help="Run the TCP DUT simulator")
    p_dut.set_defaults(_entry="mtap.cli.run_dut")

    # batch
    p_batch = sub.add_parser("batch", help="Run a multi-SN batch against the DUT")
    p_batch.add_argument("--batch-id", required=True)
    p_batch.add_argument("--station-id", required=True)
    p_batch.add_argument("--sns", default="", help="Comma-separated SN list (defaults from plan)")
    p_batch.add_argument("--stage", default="EVT")
    p_batch.add_argument("--plan", required=True, help="Path to test plan YAML")
    p_batch.add_argument("--sqlite", default="", help="Optional path to SQLite db for events")
    p_batch.set_defaults(_entry="mtap.cli.run_batch")

    # analytics
    p_an = sub.add_parser("analytics", help="Run yield analytics for a run")
    p_an.add_argument("--run-dir", required=True, help="runs/<run_id>")
    p_an.set_defaults(_entry="mtap.cli.run_analytics")

    args = p.parse_args()

    if args._entry == "mtap.cli.run_dut":
        from mtap.cli.run_dut import main as _m

        _m([])
        return

    if args._entry == "mtap.cli.run_batch":
        from mtap.cli.run_batch import main as _m

        argv = [
            "--batch-id",
            args.batch_id,
            "--station-id",
            args.station_id,
            "--sns",
            args.sns,
            "--stage",
            args.stage,
            "--plan",
            args.plan,
        ]
        if args.sqlite:
            argv += ["--sqlite", args.sqlite]
        _m(argv)
        return

    if args._entry == "mtap.cli.run_analytics":
        from mtap.cli.run_analytics import main as _m

        _m(["--run-dir", args.run_dir])
        return

    raise SystemExit(2)
