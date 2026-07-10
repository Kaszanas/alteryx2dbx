from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.formula import FormulaHandler


def _make_tool(tool_id=8, formula_fields=None, annotation="Calc Fields"):
    if formula_fields is None:
        formula_fields = [
            {
                "field": "FullName",
                "expression": '[FirstName] + " " + [LastName]',
                "type": "V_String",
                "size": 100,
            }
        ]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Formula",
        tool_type="Formula",
        config={"formula_fields": formula_fields},
        annotation=annotation,
    )


class TestFormulaHandler:
    def test_single_formula_generates_withcolumn(self):
        handler = FormulaHandler()
        tool = _make_tool(
            formula_fields=[
                {"field": "Upper_Name", "expression": "Uppercase([Name])"}
            ]
        )
        step = handler.convert(tool, input_df_names=["df_5"])

        assert '.withColumn("Upper_Name",' in step.code
        assert "F.upper" in step.code

    def test_multiple_formula_fields_generate_multiple_withcolumns(self):
        handler = FormulaHandler()
        tool = _make_tool(
            formula_fields=[
                {"field": "A", "expression": "[X] + [Y]"},
                {"field": "B", "expression": "Uppercase([Name])"},
            ]
        )
        step = handler.convert(tool, input_df_names=["df_3"])

        assert step.code.count(".withColumn(") == 2
        assert '.withColumn("A",' in step.code
        assert '.withColumn("B",' in step.code

    def test_output_df_is_correct(self):
        handler = FormulaHandler()
        tool = _make_tool(tool_id=15)
        step = handler.convert(tool, input_df_names=["df_10"])

        assert step.output_df == "df_15"

    def test_confidence_is_1_for_valid_expressions(self):
        handler = FormulaHandler()
        tool = _make_tool(
            formula_fields=[
                {"field": "Total", "expression": "[Price] * [Qty]"},
            ]
        )
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 1.0
        assert step.notes == []

    def test_confidence_drops_on_failed_formula(self):
        handler = FormulaHandler()
        tool = _make_tool(
            formula_fields=[
                {"field": "Good", "expression": "[X] + [Y]"},
                {"field": "Bad", "expression": "<<<INVALID>>>"},
            ]
        )
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 0.3
        assert any("Bad" in n for n in step.notes)
        assert "# FAILED: Bad" in step.code

    def test_empty_formula_fields(self):
        handler = FormulaHandler()
        tool = _make_tool(formula_fields=[])
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.output_df == "df_8"
        assert step.confidence == 1.0
        assert "df_8 = df_1" in step.code

    def test_imports_include_pyspark_functions(self):
        handler = FormulaHandler()
        tool = _make_tool()
        step = handler.convert(tool, input_df_names=["df_1"])

        assert "from pyspark.sql import functions as F" in step.imports
