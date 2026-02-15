from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_events_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read MTAP events.jsonl into a list of dicts (append-only replay)."""
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


def iter_events_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Streaming iterator variant."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
