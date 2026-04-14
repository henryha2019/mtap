# MTAP — Manufacturing Test Automation Platform

Production-style manufacturing test automation stack:

- TCP/IP DUT simulator (fault injection + deterministic mode)
- YAML plan-driven test runner (multi-SN, retries, per-step timeouts)
- Audit artifacts: requirement traceability + coverage matrix
- Structured logs (JSONL + CSV) + HTML qualification report
- Yield analytics (FPY/FTY, Pareto, stratification)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .
```

## Run from CLI

1) Start DUT simulator:

```bash
mtap dut
```

2) Run a batch against the DUT (in a second terminal):

```bash
mtap batch \
  --batch-id LOCAL_BATCH \
  --station-id STATION_01 \
  --sns SN0001,SN0002,SN0003 \
  --stage EVT \
  --plan test_framework/test_plan.yaml
```

Outputs are written under `runs/<run_id>/` (events.jsonl, events.csv, results_summary.json, coverage_matrix.csv, qualification_report.html).

3) Run analytics for a completed run:

```bash
mtap analytics --run-dir runs/<run_id>
```

### Fault profiles

The DUT defaults to a **clean (non-flaky)** profile for deterministic runs.

To enable a flaky profile:

```bash
export MTAP_FAULT_PROFILE=factory-flaky
# or: markov-flaky
mtap dut
```

## Docker Compose

Build and run the DUT + runner containers:

```bash
docker compose build
docker compose up
```

The runner container waits for the DUT health check before executing. Artifacts are written to `./runs/`.

Stop:

```bash
docker compose down
```

## Tests

```bash
pytest -q
```

All 9 tests pass (analytics, fault injection, imports, plan validation, runner smoke).

## Project Structure

```
src/mtap/          Core package (CLI, DUT, runner, analytics, reporting, storage, traceability)
test_framework/    Compatibility re-exports for resume-aligned folder name
test_plans/        Example test plan YAML
tests/             pytest test suite
dut/               DUT config (dev workflow)
traceability/      Requirement traceability YAML
templates/         Jinja2 HTML report template
runs/              Runtime artifacts (gitignored)
```

## Project Entrypoint

- Console script: `mtap ...`
- Module entrypoint: `python -m mtap ...`
