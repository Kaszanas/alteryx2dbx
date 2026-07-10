"""End-to-end integration tests for the full alteryx2dbx pipeline.

Validates: XML parser -> DAG resolver -> expression transpiler -> tool handlers
           -> notebook generator -> CLI output.
"""

from pathlib import Path
from click.testing import CliRunner
from alteryx2dbx.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_e2e_simple_filter(tmp_path):
    """Full pipeline: parse -> DAG -> handlers -> generate -> validate all output files."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", str(FIXTURES / "simple_filter.yxmd"), "-o", str(tmp_path)],
    )
    assert result.exit_code == 0

    wf_dir = tmp_path / "simple_filter"

    # All output files exist
    assert (wf_dir / "config.yml").exists()
    assert (wf_dir / "01_load_sources.py").exists()
    assert (wf_dir / "02_transformations.py").exists()
    assert (wf_dir / "03_orchestrate.py").exists()
    assert (wf_dir / "04_validate.py").exists()
    assert (wf_dir / "conversion_report.md").exists()
    assert (wf_dir / "alteryx_output").is_dir()

    # Load sources has the input tool
    load = (wf_dir / "01_load_sources.py").read_text()
    assert "Databricks notebook source" in load
    assert "spark.read" in load
    assert "customers.xlsx" in load

    # Transformations has the filter with Alteryx expression transpiled
    transform = (wf_dir / "02_transformations.py").read_text()
    assert "filter" in transform.lower()
    assert "active" in transform
    assert "COMMAND" in transform

    # Orchestrator chains steps
    orch = (wf_dir / "03_orchestrate.py").read_text()
    assert "01_load_sources" in orch
    assert "02_transformations" in orch

    # Validator has datacompy
    validate = (wf_dir / "04_validate.py").read_text()
    assert "datacompy" in validate
    assert "SparkCompare" in validate

    # Config has sources and outputs
    config = (wf_dir / "config.yml").read_text()
    assert "customers.xlsx" in config

    # Report shows all tools with confidence
    report = (wf_dir / "conversion_report.md").read_text()
    assert "Filter" in report
    assert "DbFileInput" in report


def test_e2e_join_workflow(tmp_path):
    """Multi-tool workflow: 2 inputs -> Join -> Summarize -> Sort -> Output."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", str(FIXTURES / "join_workflow.yxmd"), "-o", str(tmp_path)],
    )
    assert result.exit_code == 0

    wf_dir = tmp_path / "join_workflow"
    assert (wf_dir / "01_load_sources.py").exists()
    assert (wf_dir / "02_transformations.py").exists()
    assert (wf_dir / "03_orchestrate.py").exists()
    assert (wf_dir / "04_validate.py").exists()
    assert (wf_dir / "config.yml").exists()
    assert (wf_dir / "conversion_report.md").exists()
    assert (wf_dir / "alteryx_output").is_dir()

    # Load sources has both inputs
    load = (wf_dir / "01_load_sources.py").read_text()
    assert "customers.xlsx" in load
    assert "orders.csv" in load

    # Transformations has the join, summarize, sort
    transform = (wf_dir / "02_transformations.py").read_text()
    assert "join" in transform.lower()
    assert (
        "groupBy" in transform or "group_by" in transform or "agg" in transform
    )
    assert (
        "orderBy" in transform
        or "order_by" in transform
        or "sort" in transform.lower()
    )

    # Report shows all tools with confidence
    report = (wf_dir / "conversion_report.md").read_text()
    assert "Join" in report
    assert "Summarize" in report
    assert "Sort" in report
    assert "DbFileInput" in report
    assert "DbFileOutput" in report

    # Config has both source files
    config = (wf_dir / "config.yml").read_text()
    assert "customers.xlsx" in config
    assert "orders.csv" in config


def test_e2e_analyze():
    runner = CliRunner()
    result = runner.invoke(
        main, ["analyze", str(FIXTURES / "simple_filter.yxmd")]
    )
    assert result.exit_code == 0
    assert "simple_filter" in result.output
    assert "Filter" in result.output
    assert "Coverage" in result.output


def test_e2e_tools_command():
    runner = CliRunner()
    result = runner.invoke(main, ["tools"])
    assert result.exit_code == 0
    # Should list all Phase 1 handlers
    for tool_type in [
        "Filter",
        "Formula",
        "Join",
        "Select",
        "Sort",
        "Summarize",
        "Union",
        "DbFileInput",
        "DbFileOutput",
    ]:
        assert tool_type in result.output


def test_e2e_batch_convert(tmp_path):
    """Batch mode: convert all .yxmd files in fixtures directory."""
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", str(FIXTURES), "-o", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "Done" in result.output
    # Both workflows should be converted
    assert (tmp_path / "simple_filter" / "01_load_sources.py").exists()
    assert (tmp_path / "join_workflow" / "01_load_sources.py").exists()
