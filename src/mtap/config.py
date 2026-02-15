from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    dut_port: int
    runs_dir: Path
    log_level: str
    retry_max: int
    timeout_s: float
    sn_count: int


def load_settings() -> Settings:
    load_dotenv(override=False)

    host = os.getenv("MTAP_HOST", "127.0.0.1")
    dut_port = int(os.getenv("MTAP_DUT_PORT", "9000"))
    runs_dir = Path(os.getenv("MTAP_RUNS_DIR", "runs"))
    log_level = os.getenv("MTAP_LOG_LEVEL", "INFO")
    retry_max = int(os.getenv("MTAP_RETRY_MAX", "2"))
    timeout_s = float(os.getenv("MTAP_TIMEOUT_S", "2.0"))
    sn_count = int(os.getenv("MTAP_SN_COUNT", "3"))

    return Settings(
        host=host,
        dut_port=dut_port,
        runs_dir=runs_dir,
        log_level=log_level,
        retry_max=retry_max,
        timeout_s=timeout_s,
        sn_count=sn_count,
    )
