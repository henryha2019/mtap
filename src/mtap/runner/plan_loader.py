from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from mtap.runner.plan_schema import Stage, TestPlan


@dataclass(frozen=True)
class StationSpec:
    name: str
    stage: str
    fw_expected: str


@dataclass(frozen=True)
class Plan:
    station: StationSpec
    sn_count: int
    steps: List["StepSpec"]


@dataclass(frozen=True)
class LimitsSpec:
    field: str
    min: Optional[float] = None
    max: Optional[float] = None
    equals: Optional[Any] = None
    units: Optional[str] = None


@dataclass(frozen=True)
class StepSpec:
    id: str
    name: str
    cmd: str
    params: Dict[str, Any]
    retries: int
    backoff_ms: int
    timeout_s: float
    limits: Optional[LimitsSpec]
    req_ids: List[str]



def load_plan_raw(plan_path: Path) -> TestPlan:
    """Load + validate plan YAML but do NOT apply stage gating.

    Used for traceability/coverage generation where we want to reason
    about the full test intent across stages.
    """
    raw: Dict[str, Any] = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    try:
        return TestPlan.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid test plan YAML: {plan_path}\n{e}") from e


def load_plan(plan_path: Path, *, stage: Optional[str] = None) -> Plan:
    """Load + validate a test plan.

    Validation:
    - Pydantic schema validation (required keys, types, ranges)
    - Unique step IDs
    - Stage gating: only include steps enabled for station.stage
    """
    raw: Dict[str, Any] = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}

    try:
        parsed = TestPlan.model_validate(raw)
    except ValidationError as e:
        # Re-raise with a cleaner message for CLI usage
        raise ValueError(f"Invalid test plan YAML: {plan_path}\n{e}") from e

    effective_stage: Stage
    if stage is None or str(stage).strip() == "":
        effective_stage = parsed.station.stage
    else:
        allowed = list(Stage.__args__)  # type: ignore[attr-defined]
        if stage not in allowed:
            raise ValueError(f"Invalid stage: {stage}. Expected one of: {allowed}")
        effective_stage = stage  # type: ignore[assignment]

    station_spec = StationSpec(name=parsed.station.name, stage=effective_stage, fw_expected=parsed.station.fw_expected)

    # Stage gating
    active_steps = [s for s in parsed.steps if effective_stage in s.stages]

    steps: List[StepSpec] = []
    for s in active_steps:
        lim = None
        if s.limits is not None:
            lim = LimitsSpec(
                field=s.limits.field,
                min=s.limits.min,
                max=s.limits.max,
                equals=s.limits.equals,
            )
        steps.append(
            StepSpec(
                id=s.id,
                name=s.name,
                cmd=s.cmd,
                params=s.params,
                retries=s.retries,
                backoff_ms=s.backoff_ms,
                timeout_s=s.timeout_s,
                limits=lim,
                req_ids=list(s.req_ids),
            )
        )

    return Plan(station=station_spec, sn_count=parsed.batch.sn_count, steps=steps)
