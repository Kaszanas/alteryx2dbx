"""Tests for traceability comments in generated notebooks."""

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
        name="trace_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "input.csv"},
                annotation="Load Sales Data",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.Filter.Filter",
                tool_type="Filter",
                config={"expression": "[Revenue] > 1000"},
                annotation="Filter High Revenue",
            ),
            3: AlteryxTool(
                tool_id=3,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "output.csv"},
                annotation="Write Results",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(2, "True", 3, "Input"),
        ],
    )


def test_traceability_comments_present(tmp_path: Path):
    """Each tool cell should have an '# Alteryx: Tool' comment."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "trace_wf"
    load = (wf_dir / "01_load_sources.py").read_text(encoding="utf-8")
    transform = (wf_dir / "02_transformations.py").read_text(encoding="utf-8")
    output = (wf_dir / "03_write_outputs.py").read_text(encoding="utf-8")

    assert "# Alteryx: Tool 1 (DbFileInput): Load Sales Data" in load
    assert "# Alteryx: Tool 2 (Filter): Filter High Revenue" in transform
    assert "# Alteryx: Tool 3 (DbFileOutput): Write Results" in output


def test_no_annotation_shows_fallback(tmp_path: Path):
    """Tools with empty annotation should show 'No annotation'."""
    wf = AlteryxWorkflow(
        name="no_annot_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "input.csv"},
                annotation="",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "output.csv"},
                annotation="",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
        ],
    )
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "no_annot_wf"
    load = (wf_dir / "01_load_sources.py").read_text(encoding="utf-8")
    assert "# Alteryx: Tool 1 (DbFileInput): No annotation" in load


def test_low_confidence_gets_confidence_comment(tmp_path: Path):
    """Tools with confidence < 1.0 should get a '# Confidence:' line."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "trace_wf"
    # Read all notebooks and check for any confidence comments
    all_content = ""
    for nb in (
        "01_load_sources.py",
        "02_transformations.py",
        "03_write_outputs.py",
    ):
        all_content += (wf_dir / nb).read_text(encoding="utf-8")

    # The simple workflow tools likely have confidence=1.0 from the handlers,
    # so confidence comments should NOT appear for full-confidence tools
    # We need to test with a tool that produces low confidence — use an unsupported type
    wf2 = AlteryxWorkflow(
        name="lowconf_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "input.csv"},
                annotation="Input",
            ),
            10: AlteryxTool(
                tool_id=10,
                plugin="SomeUnknownPlugin",
                tool_type="UnknownTool",
                config={},
                annotation="Mystery Tool",
            ),
            99: AlteryxTool(
                tool_id=99,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "out.csv"},
                annotation="Output",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 10, "Input"),
            AlteryxConnection(10, "Output", 99, "Input"),
        ],
    )
    generate_notebooks_v2(wf2, tmp_path)

    wf_dir2 = tmp_path / "lowconf_wf"
    transform = (wf_dir2 / "02_transformations.py").read_text(encoding="utf-8")

    # Unsupported tools get confidence=0.0
    assert "# Confidence:" in transform
    assert "review recommended" in transform


def test_notes_rendered_as_note_comments(tmp_path: Path):
    """Notes on steps should appear as '# NOTE:' comment lines."""
    # Network paths trigger notes via _detect_network_paths
    wf = AlteryxWorkflow(
        name="notes_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "\\\\server\\share\\input.csv"},
                annotation="Network Input",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "output.csv"},
                annotation="Output",
            ),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
        ],
    )
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "notes_wf"
    load = (wf_dir / "01_load_sources.py").read_text(encoding="utf-8")
    assert "# NOTE:" in load


def test_full_confidence_no_confidence_comment(tmp_path: Path):
    """Tools at confidence=1.0 should NOT get a confidence comment."""
    wf = _simple_workflow()
    generate_notebooks_v2(wf, tmp_path)

    wf_dir = tmp_path / "trace_wf"
    transform = (wf_dir / "02_transformations.py").read_text(encoding="utf-8")
    # Filter with a parseable expression should have confidence=1.0 — no confidence line
    assert "# Alteryx: Tool 2 (Filter): Filter High Revenue" in transform
    assert "# Confidence:" not in transform
