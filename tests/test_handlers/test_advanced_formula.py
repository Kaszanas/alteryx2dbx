from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.multi_row_formula import MultiRowFormulaHandler
from alteryx2dbx.handlers.multi_field_formula import MultiFieldFormulaHandler


# ── MultiRowFormula helpers ──────────────────────────────────────


def _make_mrf_tool(
    tool_id=20,
    expression="[Row-1:Revenue]",
    field="PrevRevenue",
    group_fields=None,
    num_rows="1",
    annotation="Multi-Row",
):
    config = {
        "mrf_expression": expression,
        "mrf_field": field,
        "mrf_num_rows": num_rows,
    }
    if group_fields:
        config["mrf_group_fields"] = group_fields
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.MultiRowFormula",
        tool_type="MultiRowFormula",
        config=config,
        annotation=annotation,
    )


# ── MultiFieldFormula helpers ────────────────────────────────────


def _make_mff_tool(
    tool_id=30,
    expression="Trim(_CurrentField_)",
    fields=None,
    annotation="Multi-Field",
):
    if fields is None:
        fields = ["Name", "City"]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.MultiFieldFormula",
        tool_type="MultiFieldFormula",
        config={
            "mff_expression": expression,
            "mff_fields": fields,
        },
        annotation=annotation,
    )


# ── MultiRowFormula tests ────────────────────────────────────────


class TestMultiRowFormulaHandler:
    def test_lag_expression_with_window(self):
        handler = MultiRowFormulaHandler()
        tool = _make_mrf_tool(expression="[Row-1:Revenue]", field="PrevRevenue")
        step = handler.convert(tool, input_df_names=["df_10"])

        assert step.output_df == "df_20"
        assert "F.lag" in step.code
        assert ".over(_window_20)" in step.code
        assert '.withColumn("PrevRevenue",' in step.code

    def test_window_with_group_fields(self):
        handler = MultiRowFormulaHandler()
        tool = _make_mrf_tool(
            expression="[Row-1:Amount]",
            field="PrevAmount",
            group_fields=["Region", "Category"],
        )
        step = handler.convert(tool, input_df_names=["df_5"])

        assert 'Window.partitionBy("Region", "Category")' in step.code
        assert "from pyspark.sql.window import Window" in step.imports

    def test_confidence_is_08_for_valid(self):
        handler = MultiRowFormulaHandler()
        tool = _make_mrf_tool()
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 0.8

    def test_failed_expression_confidence_03(self):
        handler = MultiRowFormulaHandler()
        tool = _make_mrf_tool(expression="<<<INVALID>>>")
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 0.3
        assert any("Failed" in n for n in step.notes)
        assert "TODO" in step.code

    def test_no_group_fields_window(self):
        handler = MultiRowFormulaHandler()
        tool = _make_mrf_tool(expression="[Row-1:Sales]", field="PrevSales")
        step = handler.convert(tool, input_df_names=["df_3"])

        assert "Window.orderBy(F.monotonically_increasing_id())" in step.code
        assert "partitionBy" not in step.code


# ── MultiFieldFormula tests ──────────────────────────────────────


class TestMultiFieldFormulaHandler:
    def test_trim_applied_to_multiple_fields(self):
        handler = MultiFieldFormulaHandler()
        tool = _make_mff_tool(
            expression="Trim(_CurrentField_)",
            fields=["Name", "City", "State"],
        )
        step = handler.convert(tool, input_df_names=["df_5"])

        assert step.output_df == "df_30"
        assert step.code.count(".withColumn(") == 3
        assert '.withColumn("Name",' in step.code
        assert '.withColumn("City",' in step.code
        assert '.withColumn("State",' in step.code
        assert "F.trim" in step.code

    def test_current_field_name_substitution(self):
        handler = MultiFieldFormulaHandler()
        tool = _make_mff_tool(
            expression='_CurrentFieldName_ + ": " + _CurrentField_',
            fields=["Revenue"],
        )
        step = handler.convert(tool, input_df_names=["df_1"])

        # _CurrentFieldName_ should become "Revenue" (a string literal)
        # _CurrentField_ should become [Revenue] (a field ref)
        assert '.withColumn("Revenue",' in step.code

    def test_confidence_1_for_valid(self):
        handler = MultiFieldFormulaHandler()
        tool = _make_mff_tool(
            expression="Uppercase(_CurrentField_)", fields=["A", "B"]
        )
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 1.0
        assert step.notes == []

    def test_partial_failure_reduces_confidence(self):
        handler = MultiFieldFormulaHandler()
        # First field should succeed, expression with invalid syntax for second
        tool = _make_mff_tool(
            expression="Trim(_CurrentField_)",
            fields=["Good"],
        )
        step_good = handler.convert(tool, input_df_names=["df_1"])
        assert step_good.confidence == 1.0

        # Now test with an expression that will fail
        tool_bad = _make_mff_tool(
            expression="<<<INVALID>>>",
            fields=["Bad"],
        )
        step_bad = handler.convert(tool_bad, input_df_names=["df_1"])
        assert step_bad.confidence == 0.3
        assert any("Bad" in n for n in step_bad.notes)

    def test_empty_fields_list(self):
        handler = MultiFieldFormulaHandler()
        tool = _make_mff_tool(expression="Trim(_CurrentField_)", fields=[])
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.output_df == "df_30"
        assert step.confidence == 1.0
        assert step.code.count(".withColumn(") == 0
