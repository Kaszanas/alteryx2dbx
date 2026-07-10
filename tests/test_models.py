from alteryx2dbx.parser.models import (
    AlteryxField,
    AlteryxConnection,
    AlteryxTool,
    AlteryxWorkflow,
    GeneratedStep,
)


def test_alteryx_field_creation():
    field = AlteryxField(name="Revenue", type="Double", size=None, scale=None)
    assert field.name == "Revenue"
    assert field.type == "Double"


def test_alteryx_connection_creation():
    conn = AlteryxConnection(
        source_tool_id=1,
        source_anchor="Output",
        target_tool_id=2,
        target_anchor="Input",
    )
    assert conn.source_tool_id == 1
    assert conn.target_tool_id == 2


def test_alteryx_tool_creation():
    tool = AlteryxTool(
        tool_id=1,
        plugin="AlteryxBasePluginsGui.Filter.Filter",
        tool_type="Filter",
        config={"expression": "[Revenue] > 100"},
        annotation="Filter High Revenue",
    )
    assert tool.tool_type == "Filter"
    assert tool.annotation == "Filter High Revenue"


def test_alteryx_workflow_creation():
    wf = AlteryxWorkflow(name="test_workflow", version="11.7")
    assert wf.name == "test_workflow"


def test_generated_step_creation():
    step = GeneratedStep(
        step_name="filter_active",
        code='df_5 = df_1.filter(F.col("status") == F.lit("active"))',
        imports={"from pyspark.sql import functions as F"},
        input_dfs=["df_1"],
        output_df="df_5",
        notes=[],
        confidence=1.0,
    )
    assert step.confidence == 1.0
    assert step.output_df == "df_5"


def test_generated_step_with_warnings():
    step = GeneratedStep(
        step_name="multi_row",
        code="df_10 = df_8  # PASSTHROUGH",
        imports=set(),
        input_dfs=["df_8"],
        output_df="df_10",
        notes=["Self-referencing multi-row formula detected"],
        confidence=0.5,
    )
    assert len(step.notes) == 1
    assert step.confidence == 0.5
