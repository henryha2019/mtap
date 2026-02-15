# MTAP — Manufacturing Test Automation Platform

Production-style manufacturing test automation stack:

- TCP/IP DUT simulator (fault injection + deterministic mode)
- YAML plan-driven test runner (multi-SN, retries, per-step timeouts)
- Audit artifacts: requirement traceability + coverage matrix
- Structured logs (JSONL + CSV) + HTML qualification report
- Yield analytics (FPY/FTY, Pareto, stratification)
- Streamlit dashboard for run log exploration (KPIs, Pareto, heatmaps, SN history)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .
```

Optional (web UI deps: Streamlit + future web hooks):

```bash
pip install -r requirements-web.txt
```

Tip: there is a Makefile shortcut:

```bash
make venv
```

## Run from CLI

1. Start DUT simulator:

```bash
mtap dut
```

2. Run a batch against the DUT (in a second terminal):

```bash
mtap batch \
  --batch-id LOCAL_BATCH \
  --station-id STATION_01 \
  --sns SN0001,SN0002,SN0003 \
  --stage EVT \
  --plan test_framework/test_plan.yaml
# (alternative plan path: test_plans/test_plan.yaml)
```

Outputs are written under `runs/<run_id>/`:

* `events.jsonl`
* `events.csv`
* `results_summary.json`
* `coverage_matrix.csv`
* `qualification_report.html`

3. Run analytics for a completed run:

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

## Dashboard (Streamlit)

The dashboard reads MTAP run logs and visualizes:

* Units + FPY/FTY + flaky rate
* Pareto (failed steps / error codes)
* Failure heatmaps
* Per-SN timeline + final step outcomes

Run from the repo root:

```bash
streamlit run dashboard/app.py
# or: make dashboard
```

Then upload: `runs/<run_id>/events.jsonl`

Note: Streamlit changes Python’s import path when executing scripts. `dashboard/app.py` includes a small `sys.path` bootstrap so `dashboard.*` and `mtap.*` imports work reliably when launched via Streamlit.

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

All tests pass (analytics, fault injection, imports, plan validation, runner smoke).

## Project Structure

```
src/mtap/          Core package (CLI, DUT, runner, analytics, reporting, storage, traceability)
dashboard/         Streamlit dashboard (events.jsonl explorer)
test_framework/    Compatibility re-exports + example test plan (resume-aligned folder name)
test_plans/        Example test plan YAML (alternate location)
traceability/      Requirement traceability YAML
templates/         Jinja2 HTML report template (dev-friendly location)
analytics/         Compatibility re-exports for analytics modules
storage/           Compatibility re-exports for storage helpers
docs/              Supporting docs (requirements notes, etc.)
tests/             pytest test suite
dut/               DUT config (dev workflow)
runs/              Runtime artifacts (gitignored)
```

## Project Entrypoint

* Console script: `mtap ...`
* Module entrypoint: `python -m mtap ...`


