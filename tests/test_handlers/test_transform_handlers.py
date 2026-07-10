"""Tests for transform handlers: CrossTab, Transpose, RunningTotal, GenerateRows, Tile."""

from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.cross_tab import CrossTabHandler
from alteryx2dbx.handlers.transpose import TransposeHandler
from alteryx2dbx.handlers.running_total import RunningTotalHandler
from alteryx2dbx.handlers.generate_rows import GenerateRowsHandler
from alteryx2dbx.handlers.tile import TileHandler


# ── CrossTab ──────────────────────────────────────────────────────────


def _make_cross_tab_tool(**overrides):
    defaults = dict(
        tool_id=20,
        plugin="AlteryxBasePluginsEngine.CrossTab",
        tool_type="CrossTab",
        config={
            "ct_group_fields": ["Region"],
            "ct_header_field": "Product",
            "ct_data_field": "Sales",
            "ct_method": "Sum",
        },
        annotation="CrossTab",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestCrossTabHandler:
    def test_pivot_generated(self):
        step = CrossTabHandler().convert(
            _make_cross_tab_tool(), input_df_names=["df_5"]
        )
        assert ".pivot(" in step.code
        assert ".groupBy(" in step.code

    def test_agg_function(self):
        step = CrossTabHandler().convert(
            _make_cross_tab_tool(), input_df_names=["df_5"]
        )
        assert 'F.sum("Sales")' in step.code

    def test_avg_method(self):
        tool = _make_cross_tab_tool(
            config={
                "ct_group_fields": ["Region"],
                "ct_header_field": "Product",
                "ct_data_field": "Sales",
                "ct_method": "Avg",
            }
        )
        step = CrossTabHandler().convert(tool, input_df_names=["df_5"])
        assert 'F.avg("Sales")' in step.code

    def test_output_df(self):
        step = CrossTabHandler().convert(
            _make_cross_tab_tool(tool_id=30), input_df_names=["df_5"]
        )
        assert step.output_df == "df_30"

    def test_imports(self):
        step = CrossTabHandler().convert(
            _make_cross_tab_tool(), input_df_names=["df_5"]
        )
        assert "from pyspark.sql import functions as F" in step.imports


# ── Transpose ─────────────────────────────────────────────────────────


def _make_transpose_tool(**overrides):
    defaults = dict(
        tool_id=21,
        plugin="AlteryxBasePluginsEngine.Transpose",
        tool_type="Transpose",
        config={
            "tp_key_fields": ["ID", "Name"],
            "tp_data_fields": ["Q1", "Q2", "Q3"],
        },
        annotation="Transpose",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestTransposeHandler:
    def test_stack_generated(self):
        step = TransposeHandler().convert(
            _make_transpose_tool(), input_df_names=["df_5"]
        )
        assert "stack(" in step.code

    def test_data_fields_in_stack(self):
        step = TransposeHandler().convert(
            _make_transpose_tool(), input_df_names=["df_5"]
        )
        assert "'Q1'" in step.code
        assert "'Q2'" in step.code
        assert "'Q3'" in step.code

    def test_output_df(self):
        step = TransposeHandler().convert(
            _make_transpose_tool(tool_id=31), input_df_names=["df_5"]
        )
        assert step.output_df == "df_31"


# ── RunningTotal ──────────────────────────────────────────────────────


def _make_running_total_tool(**overrides):
    defaults = dict(
        tool_id=22,
        plugin="AlteryxBasePluginsEngine.RunningTotal",
        tool_type="RunningTotal",
        config={
            "rt_running_field": "Amount",
            "rt_group_fields": ["Region"],
        },
        annotation="RunningTotal",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestRunningTotalHandler:
    def test_window_sum(self):
        step = RunningTotalHandler().convert(
            _make_running_total_tool(), input_df_names=["df_5"]
        )
        assert 'F.sum("Amount")' in step.code
        assert ".over(" in step.code

    def test_partition_by(self):
        step = RunningTotalHandler().convert(
            _make_running_total_tool(), input_df_names=["df_5"]
        )
        assert 'Window.partitionBy("Region")' in step.code

    def test_no_group_fields(self):
        tool = _make_running_total_tool(
            config={"rt_running_field": "Amount", "rt_group_fields": []}
        )
        step = RunningTotalHandler().convert(tool, input_df_names=["df_5"])
        assert "monotonically_increasing_id" in step.code

    def test_imports_include_window(self):
        step = RunningTotalHandler().convert(
            _make_running_total_tool(), input_df_names=["df_5"]
        )
        assert "from pyspark.sql.window import Window" in step.imports


# ── GenerateRows ──────────────────────────────────────────────────────


def _make_generate_rows_tool(**overrides):
    defaults = dict(
        tool_id=23,
        plugin="AlteryxBasePluginsEngine.GenerateRows",
        tool_type="GenerateRows",
        config={
            "gr_init": "i = 1",
            "gr_condition": "i <= 100",
            "gr_loop": "i = i + 1",
        },
        annotation="GenerateRows",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestGenerateRowsHandler:
    def test_spark_range(self):
        step = GenerateRowsHandler().convert(
            _make_generate_rows_tool(), input_df_names=["df_5"]
        )
        assert "spark.range" in step.code

    def test_low_confidence(self):
        step = GenerateRowsHandler().convert(
            _make_generate_rows_tool(), input_df_names=["df_5"]
        )
        assert step.confidence == 0.5

    def test_todo_comment(self):
        step = GenerateRowsHandler().convert(
            _make_generate_rows_tool(), input_df_names=["df_5"]
        )
        assert "TODO" in step.code

    def test_original_expressions_in_comments(self):
        step = GenerateRowsHandler().convert(
            _make_generate_rows_tool(), input_df_names=["df_5"]
        )
        assert "i = 1" in step.code
        assert "i <= 100" in step.code


# ── Tile ──────────────────────────────────────────────────────────────


def _make_tile_tool(**overrides):
    defaults = dict(
        tool_id=24,
        plugin="AlteryxBasePluginsEngine.Tile",
        tool_type="Tile",
        config={
            "tile_method": "EqualRecords",
            "tile_num": 5,
            "tile_field": "Score",
        },
        annotation="Tile",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestTileHandler:
    def test_ntile(self):
        step = TileHandler().convert(_make_tile_tool(), input_df_names=["df_5"])
        assert "F.ntile(5)" in step.code

    def test_order_by_field(self):
        step = TileHandler().convert(_make_tile_tool(), input_df_names=["df_5"])
        assert '"Score"' in step.code

    def test_output_df(self):
        step = TileHandler().convert(
            _make_tile_tool(tool_id=40), input_df_names=["df_5"]
        )
        assert step.output_df == "df_40"

    def test_imports(self):
        step = TileHandler().convert(_make_tile_tool(), input_df_names=["df_5"])
        assert "from pyspark.sql.window import Window" in step.imports
