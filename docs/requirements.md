# MTAP Requirements (simulated)

This is a minimal, audit-style requirement set used for **REQ → TEST → RESULT** traceability.

The authoritative mapping is:
- Requirements list: `traceability/req_traceability.yaml`
- Test steps declare coverage via `req_ids` in `test_framework/test_plan.yaml`
- Coverage matrix is generated automatically into `coverage_matrix.csv`

## Requirement list

- **REQ-001**: DUT shall respond to `PING` with identity (SN, FW, mode) and voltage.
- **REQ-002**: DUT shall report temperature (°C) on `READ_TEMP`.
- **REQ-003**: DUT shall report voltage (V) on `READ_TEMP` within nominal range.
- **REQ-004**: DUT shall execute `SELF_TEST` and report pass/fail.
