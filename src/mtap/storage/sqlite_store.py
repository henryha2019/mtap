from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from mtap.reporting.logger import CSV_COLUMNS, StepEvent


SCHEMA_VERSION = 1


class SQLiteStore:
    """Optional append-only event store for replay and querying."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS step_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schema_version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    sn TEXT NOT NULL,
                    fw_version TEXT NOT NULL,
                    test_step TEXT NOT NULL,
                    command TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    retry_count INTEGER NOT NULL,
                    retries_allowed INTEGER NOT NULL,
                    timeout_s REAL NOT NULL,
                    backoff_ms INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    error_code TEXT,
                    measurement TEXT,
                    value_json TEXT,
                    units TEXT,
                    message TEXT,
                    data_json TEXT
                );
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_run_id ON step_events(run_id);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_sn ON step_events(sn);")
            con.commit()

    def append(self, ev: StepEvent) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """
                INSERT INTO step_events (
                    schema_version,timestamp,run_id,batch_id,station_id,stage,sn,fw_version,
                    test_step,command,attempt,retry_count,retries_allowed,timeout_s,backoff_ms,duration_ms,
                    passed,error_code,measurement,value_json,units,message,data_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ev.schema_version,
                    ev.timestamp,
                    ev.run_id,
                    ev.batch_id,
                    ev.station_id,
                    ev.stage,
                    ev.sn,
                    ev.fw_version,
                    ev.test_step,
                    ev.command,
                    ev.attempt,
                    ev.retry_count,
                    ev.retries_allowed,
                    ev.timeout_s,
                    ev.backoff_ms,
                    ev.duration_ms,
                    1 if ev.passed else 0,
                    ev.error_code,
                    ev.measurement,
                    json.dumps(ev.value, ensure_ascii=False),
                    ev.units,
                    ev.message,
                    json.dumps(ev.data, ensure_ascii=False),
                ),
            )
            con.commit()
