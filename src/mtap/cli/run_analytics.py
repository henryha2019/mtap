from __future__ import annotations

import argparse
from pathlib import Path

from mtap.analytics.run_analytics import run_analytics


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Run MTAP yield analytics from raw logs.")
    p.add_argument("--run-dir", required=True, help="runs/<run_id>")
    args = p.parse_args(argv)

    out_dir = run_analytics(Path(args.run_dir))
    print(f"[analytics] wrote outputs under: {out_dir}")

if __name__ == "__main__":
    main()
