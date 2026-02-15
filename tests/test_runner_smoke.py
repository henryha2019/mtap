from pathlib import Path
from mtap.runner.plan_loader import load_plan

# Resolve path relative to project root (parent of tests/)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_plan():
    plan = load_plan(_PROJECT_ROOT / "test_framework" / "test_plan.yaml")
    assert plan.sn_count >= 1
    assert len(plan.steps) >= 1
