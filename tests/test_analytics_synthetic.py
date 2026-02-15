from __future__ import annotations

import json
from pathlib import Path

from mtap.analytics.io import read_events_jsonl
from mtap.analytics.yield_analysis import compute_yields
from mtap.analytics.pareto import pareto_failures
from mtap.analytics.stratification import stratify


def _write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_known_small_dataset(tmp_path: Path) -> None:
    # 2 SNs, 2 steps (ping, read_temp). SN2 flakes on read_temp then passes.
    events = [
        # SN1 - clean pass
        {"sn":"SN0001","batch_id":"B1","station_id":"S1","stage":"DVT","fw_version":"1.0.0","test_step":"ping","command":"PING","attempt":1,"passed":True,"error_code":None,"duration_ms":10,"measurement":None,"value":None},
        {"sn":"SN0001","batch_id":"B1","station_id":"S1","stage":"DVT","fw_version":"1.0.0","test_step":"read_temp","command":"READ_TEMP","attempt":1,"passed":True,"error_code":None,"duration_ms":20,"measurement":"temp_c","value":25.0},
        # SN2 - ping pass, read_temp fails then passes
        {"sn":"SN0002","batch_id":"B1","station_id":"S1","stage":"DVT","fw_version":"1.0.1","test_step":"ping","command":"PING","attempt":1,"passed":True,"error_code":None,"duration_ms":12,"measurement":None,"value":None},
        {"sn":"SN0002","batch_id":"B1","station_id":"S1","stage":"DVT","fw_version":"1.0.1","test_step":"read_temp","command":"READ_TEMP","attempt":1,"passed":False,"error_code":"E_TIMEOUT","duration_ms":1000,"measurement":"temp_c","value":None},
        {"sn":"SN0002","batch_id":"B1","station_id":"S1","stage":"DVT","fw_version":"1.0.1","test_step":"read_temp","command":"READ_TEMP","attempt":2,"passed":True,"error_code":None,"duration_ms":25,"measurement":"temp_c","value":26.0},
    ]
    p = tmp_path / "events.jsonl"
    _write_jsonl(p, events)
    rows = read_events_jsonl(p)

    ys = compute_yields(rows)

    assert ys.total_units == 2
    # FPY: only SN1 passes first pass (SN2 needed retry)
    assert ys.overall_pass_first_pass == 1
    assert abs(ys.fpy - 0.5) < 1e-9
    # FTY: both pass finally
    assert ys.overall_pass_final == 2
    assert abs(ys.fty - 1.0) < 1e-9

    # Flaky: SN2 read_temp fail->pass counts as 1 flaky step instance out of 4 step instances total (2 SN * 2 steps)
    assert abs(ys.flaky_rate - (1/4)) < 1e-9

    pareto = pareto_failures(rows)
    assert pareto["by_step"]["read_temp"] == 1
    assert pareto["by_error"]["E_TIMEOUT"] == 1

    fw_rows = stratify(rows, key="fw_version")
    # Two FW groups, each with 1 unit, both FTY=1.0
    assert {r.group for r in fw_rows} == {"1.0.0", "1.0.1"}
    assert all(abs(r.fty - 1.0) < 1e-9 for r in fw_rows)
