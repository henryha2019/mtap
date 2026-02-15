# Architecture

## Interfaces
- **Runner ↔ DUT**: TCP socket, newline-framed text requests (`CMD [arg1] [arg2]`) and newline-framed JSON responses.
- Responses always include:
  - `ok` (bool)
  - `error_code` (string or null)
  - `data` (object)

## Key modules
- `mtap.dut.server`: TCP server, command dispatch, per-connection handling
- `mtap.dut.device_model`: device state + signals
- `mtap.dut.fault_injection`: fault profiles (timeouts, drift, intermittent)
- `mtap.runner.runner`: plan execution, retries, timeouts, multi-SN
- `mtap.reporting`: JSONL/CSV logging, HTML report, JUnit output
- `mtap.traceability`: requirement mapping and coverage matrix generation

## Artifact contract (per run folder)
- `events.jsonl`, `events.csv`
- `results_summary.json`
- `coverage_matrix.csv`
- `report.html`
- `junit.xml`
