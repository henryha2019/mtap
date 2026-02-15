from pathlib import Path
import pytest

from mtap.runner.plan_loader import load_plan

def test_plan_validation_catches_missing_keys(tmp_path: Path):
    bad = tmp_path / "bad_plan.yaml"
    bad.write_text(
        """station: {name: X, stage: EVT, fw_expected: '1.0.0'}\nbatch: {sn_count: 1}\nsteps: []\n""",
        encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_plan(bad)

def test_stage_gating_filters_steps(tmp_path: Path):
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        """
plan: {name: T, version: 1}
station: {name: S, stage: EVT, fw_expected: '1.0.0'}
batch: {sn_count: 1}
steps:
  - {id: a, name: A, cmd: PING, params: {}, timeout_s: 1.0, retries: 0, backoff_ms: 0, req_ids: [REQ-001], stages: [EVT]}
  - {id: b, name: B, cmd: SELF_TEST, params: {}, timeout_s: 1.0, retries: 0, backoff_ms: 0, req_ids: [REQ-004], stages: [DVT]}
""".lstrip(),
        encoding="utf-8"
    )
    p = load_plan(plan)
    assert [s.id for s in p.steps] == ["a"]
