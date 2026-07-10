from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.sort import SortHandler


def _make_tool(tool_id=8, sort_fields=None, annotation="Sort Data"):
    if sort_fields is None:
        sort_fields = [
            {"field": "Amount", "order": "Descending"},
            {"field": "Name", "order": "Ascending"},
        ]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Sort",
        tool_type="Sort",
        config={"sort_fields": sort_fields},
        annotation=annotation,
    )


class TestSortHandler:
    def test_orderby_generated(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_3"])
        assert ".orderBy(" in step.code

    def test_descending_order(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_3"])
        assert 'F.col("Amount").desc()' in step.code

    def test_ascending_order(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_3"])
        assert 'F.col("Name").asc()' in step.code

    def test_output_df_name(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(tool_id=12), input_df_names=["df_5"])
        assert step.output_df == "df_12"

    def test_confidence_is_1(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert step.confidence == 1.0

    def test_input_dfs(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_3"])
        assert step.input_dfs == ["df_3"]

    def test_imports_include_pyspark_functions(self):
        handler = SortHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert "from pyspark.sql import functions as F" in step.imports

    def test_no_sort_fields(self):
        handler = SortHandler()
        step = handler.convert(
            _make_tool(sort_fields=[]), input_df_names=["df_1"]
        )
        assert "No sort fields" in step.code
