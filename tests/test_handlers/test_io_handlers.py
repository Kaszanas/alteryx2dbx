"""Tests for TextInput, Browse, and DynamicInput handlers."""

from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.text_input import TextInputHandler
from alteryx2dbx.handlers.browse import BrowseHandler
from alteryx2dbx.handlers.dynamic_input import DynamicInputHandler


# ── TextInput ────────────────────────────────────────────────


def test_text_input_with_data():
    tool = AlteryxTool(
        tool_id=3,
        plugin="AlteryxBasePluginsGui.TextInput.TextInput",
        tool_type="TextInput",
        config={
            "ti_fields": ["Name", "Age"],
            "ti_data": [["Alice", "30"], ["Bob", "25"]],
        },
        annotation="Inline Data",
    )
    step = TextInputHandler().convert(tool)

    assert step.output_df == "df_3"
    assert "spark.createDataFrame" in step.code
    assert "Alice" in step.code
    assert "'Name'" in step.code
    assert step.confidence == 1.0
    assert step.input_dfs == []


def test_text_input_empty_data():
    tool = AlteryxTool(
        tool_id=7,
        plugin="AlteryxBasePluginsGui.TextInput.TextInput",
        tool_type="TextInput",
        config={"ti_fields": [], "ti_data": []},
        annotation="",
    )
    step = TextInputHandler().convert(tool)

    assert step.output_df == "df_7"
    assert "TODO" in step.code
    assert step.confidence == 0.5


def test_text_input_no_config_keys():
    """Config missing ti_fields/ti_data entirely."""
    tool = AlteryxTool(
        tool_id=9,
        plugin="",
        tool_type="TextInput",
        config={},
        annotation="",
    )
    step = TextInputHandler().convert(tool)

    assert step.output_df == "df_9"
    assert step.confidence == 0.5
    assert "TODO" in step.code


# ── Browse ───────────────────────────────────────────────────


def test_browse_passthrough():
    tool = AlteryxTool(
        tool_id=5,
        plugin="AlteryxBasePluginsGui.BrowseV2.BrowseV2",
        tool_type="BrowseV2",
        config={},
        annotation="View Results",
    )
    step = BrowseHandler().convert(tool, input_df_names=["df_4"])

    assert step.output_df == "df_5"
    assert "df_5 = df_4" in step.code
    assert ".show(20" in step.code
    assert step.confidence == 1.0
    assert step.input_dfs == ["df_4"]


def test_browse_no_input():
    tool = AlteryxTool(
        tool_id=11,
        plugin="AlteryxBasePluginsGui.Browse.Browse",
        tool_type="Browse",
        config={},
        annotation="",
    )
    step = BrowseHandler().convert(tool, input_df_names=None)

    assert step.output_df == "df_11"
    assert "df_unknown" in step.code


def test_browse_annotation_in_comment():
    tool = AlteryxTool(
        tool_id=2,
        plugin="",
        tool_type="BrowseV2",
        config={},
        annotation="Final Check",
    )
    step = BrowseHandler().convert(tool, input_df_names=["df_1"])
    assert "Final Check" in step.code


# ── DynamicInput ─────────────────────────────────────────────


def test_dynamic_input_with_path():
    tool = AlteryxTool(
        tool_id=8,
        plugin="AlteryxBasePluginsGui.DynamicInput.DynamicInput",
        tool_type="DynamicInput",
        config={"file_path": r"C:\Data\*.csv"},
        annotation="Read All CSVs",
    )
    step = DynamicInputHandler().convert(tool)

    assert step.output_df == "df_8"
    assert "spark.read" in step.code
    assert r"C:\Data\*.csv" in step.code
    assert "TODO" in step.code
    assert step.confidence == 0.8
    assert step.input_dfs == []
    assert any(
        "glob" in n.lower() or "dynamic" in n.lower() for n in step.notes
    )


def test_dynamic_input_unknown_path():
    tool = AlteryxTool(
        tool_id=14,
        plugin="",
        tool_type="DynamicInput",
        config={},
        annotation="",
    )
    step = DynamicInputHandler().convert(tool)

    assert step.output_df == "df_14"
    assert "UNKNOWN_PATH" in step.code
    assert step.confidence == 0.8
