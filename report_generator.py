"""CLI-importable report generator entry point.

Core implementation: `mtap.reporting.report_generator.generate_report`.
"""
from pathlib import Path
from mtap.reporting.report_generator import generate_report

__all__ = ["generate_report", "Path"]
