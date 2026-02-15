from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Iterable, Tuple

import yaml


def load_requirements(path: Path) -> Dict[str, Dict]:
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return d.get("requirements", {}) or {}


def generate_coverage_matrix(requirements: Dict[str, Dict], steps: Iterable[Tuple[str, List[str]]]) -> List[List[str]]:
    """Generate coverage rows.

    Args:
        requirements: {REQ-XXX: {title: ...}}
        steps: iterable of (step_id, req_ids)

    Returns rows with columns:
      req_id, title, covered, mapped_steps
    """
    req_to_steps: Dict[str, List[str]] = {rid: [] for rid in requirements.keys()}
    for step_id, req_ids in steps:
        for rid in req_ids:
            req_to_steps.setdefault(rid, []).append(step_id)

    rows: List[List[str]] = []
    for rid, info in sorted(requirements.items()):
        title = str(info.get("title", ""))
        mapped = req_to_steps.get(rid, [])
        covered = "Y" if mapped else "N"
        rows.append([rid, title, covered, ",".join(mapped)])
    return rows


def validate_coverage(requirements: Dict[str, Dict], step_req_pairs: Iterable[Tuple[str, List[str]]]) -> None:
    """Enforce audit-ready traceability constraints."""
    req_ids = set(requirements.keys())
    step_pairs = list(step_req_pairs)

    # 1) Every requirement maps to >= 1 step
    covered = set()
    for _, rids in step_pairs:
        covered.update(rids)
    missing = sorted(req_ids - covered)
    if missing:
        raise ValueError(f"Uncovered requirements: {missing}")

    # 2) Every step req_id must exist in requirement set
    referenced = sorted(set(covered) - req_ids)
    if referenced:
        raise ValueError(f"Plan references unknown requirements: {referenced}")


def write_csv(path: Path, rows: List[List[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["req_id", "title", "covered", "mapped_steps"])
        w.writerows(rows)
