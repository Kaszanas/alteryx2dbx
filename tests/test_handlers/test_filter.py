from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.filter import FilterHandler


def _make_tool(
    tool_id=5, expression='[Status] == "Active"', annotation="Active Filter"
):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Filter",
        tool_type="Filter",
        config={"expression": expression},
        annotation=annotation,
    )


class TestFilterHandler:
    def test_custom_expression_generates_filter_code(self):
        handler = FilterHandler()
        tool = _make_tool(expression='[Status] == "Active"')
        step = handler.convert(tool, input_df_names=["df_3"])

        assert "_filter_cond_5" in step.code
        assert "df_3.filter(_filter_cond_5)" in step.code
        assert '# Alteryx expression: [Status] == "Active"' in step.code

    def test_output_df_name_is_correct(self):
        handler = FilterHandler()
        tool = _make_tool(tool_id=12)
        step = handler.convert(tool, input_df_names=["df_10"])

        assert step.output_df == "df_12"

    def test_includes_true_and_false_branches(self):
        handler = FilterHandler()
        tool = _make_tool(tool_id=7)
        step = handler.convert(tool, input_df_names=["df_4"])

        assert "df_7_true" in step.code
        assert "df_7_false" in step.code
        assert "df_7 = df_7_true" in step.code

    def test_confidence_is_1_for_valid_expression(self):
        handler = FilterHandler()
        tool = _make_tool(expression="[Amount] > 100")
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 1.0
        assert step.notes == []

    def test_confidence_drops_on_failed_transpilation(self):
        handler = FilterHandler()
        # Use an expression that will fail to parse
        tool = _make_tool(expression="<<<INVALID>>>")
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 0.3
        assert len(step.notes) > 0
        assert "FAILED TO TRANSPILE" in step.code

    def test_default_input_df_when_none(self):
        handler = FilterHandler()
        tool = _make_tool()
        step = handler.convert(tool, input_df_names=None)

        assert "df_unknown" in step.code
        assert step.input_dfs == ["df_unknown"]

    def test_imports_include_pyspark_functions(self):
        handler = FilterHandler()
        tool = _make_tool()
        step = handler.convert(tool, input_df_names=["df_1"])

        assert "from pyspark.sql import functions as F" in step.imports

    def test_ambiguous_multi_table_reference(self):
        handler = FilterHandler()
        tool = _make_tool(
            expression='[Orders.Status] == "Active" && [Customers.Region] == "EU"'
        )
        step = handler.convert(tool, input_df_names=["df_1"])
        assert any(
            "AMBIGUOUS" in n and "multiple tables" in n for n in step.notes
        )

    def test_no_ambiguous_for_simple_expression(self):
        handler = FilterHandler()
        tool = _make_tool(expression='[Status] == "Active"')
        step = handler.convert(tool, input_df_names=["df_1"])
        assert not any("AMBIGUOUS" in n for n in step.notes)

    def test_no_ambiguous_dot_only_no_bracket(self):
        handler = FilterHandler()
        tool = _make_tool(expression='something.field == "test"')
        step = handler.convert(tool, input_df_names=["df_1"])
        assert not any(
            "AMBIGUOUS" in n and "multiple tables" in n for n in step.notes
        )

    def test_ambiguous_note_appended_to_existing_notes(self):
        handler = FilterHandler()
        # Use invalid expression that also has dot+bracket pattern
        tool = _make_tool(expression="<<<[foo.bar]>>>")
        step = handler.convert(tool, input_df_names=["df_1"])
        # Should have both the transpilation failure note AND the ambiguous note
        assert any("transpilation failed" in n.lower() for n in step.notes)
        assert any("AMBIGUOUS" in n for n in step.notes)
