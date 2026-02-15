# Project Overview

MTAP is a production-style manufacturing test automation platform.

## Goals
- Plan-driven execution (YAML source of truth)
- Traceability artifacts (REQ → TEST → RESULT)
- Structured logs (JSONL + CSV) for downstream analytics
- Qualification-style HTML report suitable for review

## Deployment Modes
1. Local dev: run DUT → run batch → generate artifacts
2. Batch simulation: multi-SN + fault profiles → create yield datasets
3. CI mode: docker-compose boot → smoke plan → upload artifacts
