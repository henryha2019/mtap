from __future__ import annotations

import datetime


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def utc_ts_compact() -> str:
    return utc_now().strftime("%Y-%m-%dT%H-%M-%SZ")
