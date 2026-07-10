"""Tests for the serverless-safe v2 notebook generator."""

from __future__ import annotations

from pathlib import Path


from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxTool,
    AlteryxWorkflow,
)
from alteryx2dbx.generator.notebook_v2 import generate_notebooks_v2


def _simple_workflow():
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "input.csv"},
                annotation="Input",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.Filter.Filter",
                tool_type="Filter",
                config={"expression": "[Revenue] > 1000"},
                annotation="Filter High",
            ),
            3: AlteryxTool(
                tool_id=3,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "output.csv"},
                annotation="Output",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(2, "True", 3, "Input"),
        ],
    )


def test_generates_all_notebooks(tmp_path: Path):
    """Verify all 7 files exist: _config.py, _utils.py, 01-05, manifest.json."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "test_wf"
    expected_files = [
        "_config.py",
        "_utils.py",
        "01_load_sources.py",
        "02_transformations.py",
        "03_write_outputs.py",
        "04_validate.py",
        "05_orchestrate.py",
        "manifest.json",
    ]
    for fname in expected_files:
        assert (wf_dir / fname).exists(), f"Missing expected file: {fname}"


def test_no_cache_in_output(tmp_path: Path):
    """No .cache() or .persist() in any generated .py file."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "test_wf"
    for py_file in wf_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert ".cache()" not in content, f".cache() found in {py_file.name}"
        assert ".persist()" not in content, (
            f".persist() found in {py_file.name}"
        )


def test_orchestrator_uses_run(tmp_path: Path):
    """Orchestrator contains %run for _config, _utils, and notebooks 01-03."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    orch = (tmp_path / "test_wf" / "05_orchestrate.py").read_text(
        encoding="utf-8"
    )
    assert "%run ./_config" in orch
    assert "%run ./_utils" in orch
    assert "%run ./01_load_sources" in orch
    assert "%run ./02_transformations" in orch
    assert "%run ./03_write_outputs" in orch


def test_manifest_included_in_output(tmp_path: Path):
    """manifest.json exists in output."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    assert (tmp_path / "test_wf" / "manifest.json").exists()


def test_temp_view_hints_for_fanout(tmp_path: Path):
    """When a DataFrame fans out to 2+ tools, a temp view is created instead of .cache()."""
    wf = AlteryxWorkflow(
        name="fanout_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "input.csv"},
                annotation="Input",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.Filter.Filter",
                tool_type="Filter",
                config={"expression": "[A] > 1"},
                annotation="Filter A",
            ),
            3: AlteryxTool(
                tool_id=3,
                plugin="AlteryxBasePluginsGui.Filter.Filter",
                tool_type="Filter",
                config={"expression": "[B] > 2"},
                annotation="Filter B",
            ),
            4: AlteryxTool(
                tool_id=4,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "out_a.csv"},
                annotation="Out A",
            ),
            5: AlteryxTool(
                tool_id=5,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "out_b.csv"},
                annotation="Out B",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(1, "Output", 3, "Input"),  # fan-out from tool 1
            AlteryxConnection(2, "True", 4, "Input"),
            AlteryxConnection(3, "True", 5, "Input"),
        ],
    )
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "fanout_wf"
    # Check that createOrReplaceTempView appears somewhere in the load notebook
    load_content = (wf_dir / "01_load_sources.py").read_text(encoding="utf-8")
    assert "createOrReplaceTempView" in load_content
    # And no .cache() anywhere
    for py_file in wf_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert ".cache()" not in content, f".cache() found in {py_file.name}"


def test_conversion_report_exists(tmp_path: Path):
    """Conversion report should be generated."""
    wf = AlteryxWorkflow(
        name="fix_test",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "a.csv"},
                annotation="A",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "out.csv"},
                annotation="Out",
            ),
        },
        connections=[AlteryxConnection(1, "Output", 2, "Input")],
    )
    generate_notebooks_v2(wf, tmp_path)
    report = (tmp_path / "fix_test" / "conversion_report.md").read_text()
    assert "Conversion Report" in report


def test_returns_stats_dict(tmp_path: Path):
    """generate_notebooks_v2 returns a stats dict with expected keys."""
    wf = _simple_workflow()
    stats = generate_notebooks_v2(wf, tmp_path)

    assert stats["name"] == "test_wf"
    assert "tools_total" in stats
    assert "tools_converted" in stats
    assert "avg_confidence" in stats
    assert "unsupported_tools" in stats
    assert "errors" in stats
