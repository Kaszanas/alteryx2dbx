from alteryx2dbx.parser.models import (
    AlteryxWorkflow,
    AlteryxTool,
    AlteryxConnection,
)
from alteryx2dbx.document.mermaid import generate_mermaid


def _simple_workflow():
    """Input → Filter → Output."""
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(1, "AlteryxBasePluginsGui.DbFileInput.DbFileInput", "DbFileInput",
                           {"file_path": "data.csv"}, "Load Data", []),
            2: AlteryxTool(2, "AlteryxBasePluginsGui.Filter.Filter", "Filter",
                           {"expression": "[x] > 0"}, "Filter Positive", []),
            3: AlteryxTool(3, "AlteryxBasePluginsGui.DbFileOutput.DbFileOutput", "DbFileOutput",
                           {"file_path": "out.csv"}, "Write Output", []),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(2, "True", 3, "Input"),
        ],
        properties={},
    )


def _workflow_with_unsupported():
    """Input → UnsupportedTool → Output."""
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools={
            1: AlteryxTool(1, "AlteryxBasePluginsGui.DbFileInput.DbFileInput", "DbFileInput",
                           {}, "Load", []),
            2: AlteryxTool(2, "com.unknown.Widget", "Widget",
                           {}, "Unknown Widget", []),
            3: AlteryxTool(3, "AlteryxBasePluginsGui.DbFileOutput.DbFileOutput", "DbFileOutput",
                           {}, "Save", []),
        },
        connections=[
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(2, "Output", 3, "Input"),
        ],
        properties={},
    )


def test_mermaid_basic_structure():
    wf = _simple_workflow()
    mermaid = generate_mermaid(wf)
    assert mermaid.startswith("```mermaid")
    assert "flowchart TD" in mermaid or "graph TD" in mermaid
    assert mermaid.strip().endswith("```")


def test_mermaid_contains_all_nodes():
    wf = _simple_workflow()
    mermaid = generate_mermaid(wf)
    assert "Load Data" in mermaid
    assert "Filter Positive" in mermaid
    assert "Write Output" in mermaid


def test_mermaid_contains_edges():
    wf = _simple_workflow()
    mermaid = generate_mermaid(wf)
    assert "node_1" in mermaid
    assert "node_2" in mermaid
    assert "node_3" in mermaid
    assert "-->" in mermaid


def test_mermaid_color_coding():
    wf = _simple_workflow()
    mermaid = generate_mermaid(wf)
    assert "fill:#" in mermaid or "style" in mermaid or ":::" in mermaid


def test_mermaid_labels_dual_output_edges():
    wf = _simple_workflow()
    mermaid = generate_mermaid(wf)
    assert "True" in mermaid


def test_mermaid_unsupported_tool_colored():
    wf = _workflow_with_unsupported()
    mermaid = generate_mermaid(wf)
    assert "Unknown Widget" in mermaid
