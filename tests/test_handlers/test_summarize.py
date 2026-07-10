from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.summarize import SummarizeHandler


def _make_tool(tool_id=15, summarize_fields=None, annotation="Summarize Data"):
    if summarize_fields is None:
        summarize_fields = [
            {"field": "Region", "action": "GroupBy", "rename": ""},
            {"field": "Sales", "action": "Sum", "rename": "TotalSales"},
            {"field": "OrderID", "action": "Count", "rename": "OrderCount"},
        ]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Summarize",
        tool_type="Summarize",
        config={"summarize_fields": summarize_fields},
        annotation=annotation,
    )


class TestSummarizeHandler:
    def test_groupby_and_agg(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert '.groupBy("Region")' in step.code
        assert ".agg(" in step.code

    def test_sum_aggregation(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert 'F.sum("Sales").alias("TotalSales")' in step.code

    def test_count_aggregation(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert 'F.count("OrderID").alias("OrderCount")' in step.code

    def test_no_groupby_fields(self):
        fields = [
            {"field": "Amount", "action": "Avg", "rename": "AvgAmount"},
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        assert "groupBy" not in step.code
        assert "df_1.agg(" in step.code

    def test_concat_action(self):
        fields = [
            {"field": "Name", "action": "Concat", "rename": "AllNames"},
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        assert "F.concat_ws" in step.code
        assert "F.collect_list" in step.code
        assert '.alias("AllNames")' in step.code

    def test_count_distinct(self):
        fields = [
            {
                "field": "CustID",
                "action": "CountDistinct",
                "rename": "UniqueCusts",
            },
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        assert 'F.countDistinct("CustID")' in step.code

    def test_output_df_name(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(tool_id=25), input_df_names=["df_3"])
        assert step.output_df == "df_25"

    def test_confidence_is_1(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert step.confidence == 1.0

    def test_input_dfs(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert step.input_dfs == ["df_5"]

    def test_imports_include_pyspark_functions(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert "from pyspark.sql import functions as F" in step.imports

    def test_ambiguous_first_aggregation(self):
        fields = [
            {"field": "Region", "action": "GroupBy", "rename": ""},
            {"field": "Name", "action": "First", "rename": "FirstName"},
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        assert any(
            "AMBIGUOUS" in n and "'First'" in n and "'Name'" in n
            for n in step.notes
        )

    def test_ambiguous_last_aggregation(self):
        fields = [
            {"field": "Region", "action": "GroupBy", "rename": ""},
            {"field": "Timestamp", "action": "Last", "rename": "LastTS"},
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        assert any(
            "AMBIGUOUS" in n and "'Last'" in n and "'Timestamp'" in n
            for n in step.notes
        )

    def test_ambiguous_first_and_last(self):
        fields = [
            {"field": "A", "action": "First", "rename": "FirstA"},
            {"field": "B", "action": "Last", "rename": "LastB"},
        ]
        handler = SummarizeHandler()
        step = handler.convert(
            _make_tool(summarize_fields=fields), input_df_names=["df_1"]
        )
        ambiguous_notes = [n for n in step.notes if "AMBIGUOUS" in n]
        assert len(ambiguous_notes) == 2

    def test_no_ambiguous_notes_for_clean_summarize(self):
        handler = SummarizeHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert not any("AMBIGUOUS" in n for n in step.notes)
