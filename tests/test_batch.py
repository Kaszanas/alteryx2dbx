"""Tests for batch mode and batch report generation."""

from pathlib import Path

from click.testing import CliRunner

from alteryx2dbx.cli import main
from alteryx2dbx.generator.batch_report import generate_batch_report

FIXTURES = Path(__file__).parent / "fixtures"


# ── Unit tests for generate_batch_report ──────────────────────────────


def test_batch_report_basic(tmp_path):
    results = [
        {
            "name": "workflow_a",
            "tools_total": 5,
            "tools_converted": 4,
            "avg_confidence": 0.85,
            "unsupported_tools": ["SpatialMatch"],
            "errors": [],
        },
        {
            "name": "workflow_b",
            "tools_total": 3,
            "tools_converted": 3,
            "avg_confidence": 1.0,
            "unsupported_tools": [],
            "errors": [],
        },
    ]
    generate_batch_report(tmp_path, results)
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    assert "# Batch Conversion Report" in report
    assert "**Workflows converted**: 2" in report
    assert "**Total tools**: 8" in report
    assert "**Tools converted**: 7 (88%)" in report
    assert "workflow_a" in report
    assert "workflow_b" in report


def test_batch_report_with_errors(tmp_path):
    results = [
        {
            "name": "bad_workflow",
            "tools_total": 0,
            "tools_converted": 0,
            "avg_confidence": 0,
            "unsupported_tools": [],
            "errors": ["XML parse error"],
        },
    ]
    generate_batch_report(tmp_path, results)
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    assert "## Errors" in report
    assert "**bad_workflow**: XML parse error" in report


def test_batch_report_unsupported_truncation(tmp_path):
    results = [
        {
            "name": "big_workflow",
            "tools_total": 10,
            "tools_converted": 5,
            "avg_confidence": 0.5,
            "unsupported_tools": ["ToolA", "ToolB", "ToolC", "ToolD", "ToolE"],
            "errors": [],
        },
    ]
    generate_batch_report(tmp_path, results)
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    assert "+2 more" in report


def test_batch_report_empty(tmp_path):
    generate_batch_report(tmp_path, [])
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    assert "**Workflows converted**: 0" in report


def test_batch_report_sorted_by_confidence(tmp_path):
    results = [
        {
            "name": "high_conf",
            "tools_total": 3,
            "tools_converted": 3,
            "avg_confidence": 1.0,
            "unsupported_tools": [],
            "errors": [],
        },
        {
            "name": "low_conf",
            "tools_total": 3,
            "tools_converted": 1,
            "avg_confidence": 0.3,
            "unsupported_tools": ["X", "Y"],
            "errors": [],
        },
    ]
    generate_batch_report(tmp_path, results)
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    # low_conf should appear before high_conf (sorted ascending by confidence)
    assert report.index("low_conf") < report.index("high_conf")


# ── CLI integration tests ─────────────────────────────────────────────


def test_cli_convert_with_report_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "convert",
            str(FIXTURES / "simple_filter.yxmd"),
            "-o",
            str(tmp_path),
            "--report",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "batch_report.md").exists()
    report = (tmp_path / "batch_report.md").read_text(encoding="utf-8")
    assert "simple_filter" in report
    assert "**Workflows converted**: 1" in report


def test_cli_convert_without_report_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", str(FIXTURES / "simple_filter.yxmd"), "-o", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert not (tmp_path / "batch_report.md").exists()


def test_cli_convert_directory_with_report(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", str(FIXTURES), "-o", str(tmp_path), "--report"]
    )
    assert result.exit_code == 0
    assert (tmp_path / "batch_report.md").exists()
    assert "Report:" in result.output
