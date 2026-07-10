from pathlib import Path
from click.testing import CliRunner
from alteryx2dbx.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_document_single_file(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "document",
            str(FIXTURES / "simple_filter.yxmd"),
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    report = tmp_path / "simple_filter" / "migration_report.md"
    assert report.exists()
    content = report.read_text()
    assert "## Executive Summary" in content
    assert "## Data Flow Diagram" in content


def test_document_directory(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "document",
            str(FIXTURES),
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "portfolio_report.md").exists()


def test_document_no_confluence_prints_tip(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "document",
            str(FIXTURES / "simple_filter.yxmd"),
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Tip" in result.output or "confluence" in result.output.lower()
