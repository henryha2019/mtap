from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List


LOG_SCHEMA_VERSION = 1

# Stable CSV column order (append-only evolution: only add new columns at the end)
CSV_COLUMNS: List[str] = [
    "schema_version",
    "timestamp",
    "run_id",
    "batch_id",
    "station_id",
    "stage",
    "sn",
    "fw_version",
    "test_step",
    "command",
    "attempt",
    "retry_count",
    "retries_allowed",
    "timeout_s",
    "backoff_ms",
    "duration_ms",
    "passed",
    "error_code",
    "measurement",
    "value",
    "units",
    "message",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StepEvent:
    # Meta
    schema_version: int
    timestamp: str
    run_id: str
    batch_id: str
    station_id: str
    stage: str
    sn: str
    fw_version: str

    # Step
    test_step: str
    command: str
    attempt: int
    retry_count: int
    retries_allowed: int
    timeout_s: float
    backoff_ms: int
    duration_ms: int

    # Outcome
    passed: bool
    error_code: Optional[str]

    # Measurement (optional)
    measurement: Optional[str]
    value: Optional[Any]
    units: Optional[str]

    # Human message (optional)
    message: str

    # Extra payload for replay/debug (kept in JSONL only)
    data: Dict[str, Any]

    @staticmethod
    def make(
        *,
        run_id: str,
        batch_id: str,
        station_id: str,
        stage: str,
        sn: str,
        fw_version: str,
        test_step: str,
        command: str,
        attempt: int,
        retries_allowed: int,
        timeout_s: float,
        backoff_ms: int,
        duration_ms: int,
        passed: bool,
        error_code: Optional[str],
        measurement: Optional[str] = None,
        value: Optional[Any] = None,
        units: Optional[str] = None,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> "StepEvent":
        return StepEvent(
            schema_version=LOG_SCHEMA_VERSION,
            timestamp=_utc_now_iso(),
            run_id=run_id,
            batch_id=batch_id,
            station_id=station_id,
            stage=stage,
            sn=sn,
            fw_version=fw_version,
            test_step=test_step,
            command=command,
            attempt=attempt,
            retry_count=max(0, attempt - 1),
            retries_allowed=retries_allowed,
            timeout_s=float(timeout_s),
            backoff_ms=int(backoff_ms),
            duration_ms=int(duration_ms),
            passed=bool(passed),
            error_code=error_code,
            measurement=measurement,
            value=value,
            units=units,
            message=message,
            data=data or {},
        )

    def to_jsonl_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # keep 'data' in JSONL
        return d

    def to_csv_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("data", None)  # CSV is flat
        return d


class RunLogger:
    """Append-only logger: emits one JSONL row per attempt + mirrored CSV row."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.run_dir / "events.jsonl"
        self.csv_path = self.run_dir / "events.csv"

        # Initialize CSV header once
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()

    def log(self, ev: StepEvent) -> None:
        # JSONL (append-only)
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev.to_jsonl_dict(), ensure_ascii=False) + "\n")

        # CSV (append-only, stable columns)
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            row = ev.to_csv_row()
            # ensure only known columns (future-proof: missing -> blank)
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
