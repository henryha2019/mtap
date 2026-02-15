PY=python
PIP=pip

.PHONY: venv lint test run-dut run-batch docker-up docker-down

venv:
	$(PY) -m venv .venv
	. .venv/bin/activate && $(PIP) install -r requirements-dev.txt
	. .venv/bin/activate && $(PIP) install -e .

test:
	. .venv/bin/activate && pytest

run-dut:
	. .venv/bin/activate && $(PY) -m mtap dut

run-batch:
	. .venv/bin/activate && $(PY) -m mtap batch --batch-id LOCAL --station-id ST01 --sns SN0001 --stage EVT --plan test_framework/test_plan.yaml

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down


dashboard:
	. .venv/bin/activate && streamlit run dashboard/app.py
