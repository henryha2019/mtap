from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

Stage = Literal["EVT", "DVT", "PVT", "MP"]


class PlanMeta(BaseModel):
    name: str
    version: int = 1


class Station(BaseModel):
    name: str
    stage: Stage
    fw_expected: str


class Batch(BaseModel):
    sn_count: int = Field(ge=1, le=1000)


class Limits(BaseModel):
    field: str
    min: Optional[float] = None
    max: Optional[float] = None
    equals: Optional[Any] = None

    @model_validator(mode="after")
    def _one_of(self) -> "Limits":
        # either min/max range OR equals, but allow min-only/max-only
        if self.equals is not None and (self.min is not None or self.max is not None):
            raise ValueError("limits: cannot specify equals with min/max")
        if self.equals is None and self.min is None and self.max is None:
            raise ValueError("limits: specify at least one of min/max/equals")
        return self


class Step(BaseModel):
    id: str
    name: str
    cmd: str
    params: Dict[str, Any] = Field(default_factory=dict)

    limits: Optional[Limits] = None

    retries: int = Field(ge=0, le=10, default=0)
    backoff_ms: int = Field(ge=0, le=10_000, default=0)
    timeout_s: float = Field(gt=0.0, le=30.0, default=2.0)

    req_ids: List[str] = Field(min_length=1)
    stages: List[Stage] = Field(default_factory=lambda: ["EVT", "DVT", "PVT", "MP"])

    @field_validator("req_ids")
    @classmethod
    def _req_ids_format(cls, v: List[str]) -> List[str]:
        for rid in v:
            if not rid.startswith("REQ-"):
                raise ValueError(f"bad req_id format: {rid}")
        return v


class TestPlan(BaseModel):
    plan: PlanMeta
    station: Station
    batch: Batch
    steps: List[Step]

    @model_validator(mode="after")
    def _unique_step_ids(self) -> "TestPlan":
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate step.id values found")
        return self
