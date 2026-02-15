from __future__ import annotations

from pathlib import Path
from typing import Dict
from xml.etree.ElementTree import Element, SubElement, tostring


def write_junit(path: Path, summary: Dict) -> None:
    testsuite = Element("testsuite")
    testsuite.set("name", "mtap_batch")
    testsuite.set("tests", str(summary.get("sn_count", 0)))
    testsuite.set("failures", str(summary.get("failed_count", 0)))

    per_sn = summary.get("per_sn") or {}
    for sn, info in per_sn.items():
        tc = SubElement(testsuite, "testcase")
        tc.set("classname", "mtap")
        tc.set("name", sn)
        if not info.get("passed", False):
            f = SubElement(tc, "failure")
            f.text = str(info.get("failures", []))

    path.write_bytes(tostring(testsuite, encoding="utf-8"))
