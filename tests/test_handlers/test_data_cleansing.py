from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.data_cleansing import DataCleansingHandler


def _make_tool(
    tool_id=10,
    annotation="Clean Data",
    remove_null=False,
    remove_whitespace=False,
    trim_whitespace=False,
    modify_case="",
    fields=None,
):
    config = {
        "RemoveNull": remove_null,
        "RemoveWhitespace": remove_whitespace,
        "TrimWhitespace": trim_whitespace,
        "ModifyCase": modify_case,
    }
    if fields:
        config["cleansing_fields"] = fields
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.DataCleansing",
        tool_type="DataCleansing",
        config=config,
        annotation=annotation,
    )


class TestDataCleansingHandler:
    def test_trim_whitespace_generates_trim(self):
        handler = DataCleansingHandler()
        tool = _make_tool(trim_whitespace=True, fields=["Name"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.trim" in step.code
        assert '"Name"' in step.code

    def test_remove_whitespace_generates_regexp_replace(self):
        handler = DataCleansingHandler()
        tool = _make_tool(remove_whitespace=True, fields=["City"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.regexp_replace" in step.code
        assert "\\s+" in step.code

    def test_modify_case_upper(self):
        handler = DataCleansingHandler()
        tool = _make_tool(modify_case="Upper", fields=["Status"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.upper" in step.code

    def test_modify_case_lower(self):
        handler = DataCleansingHandler()
        tool = _make_tool(modify_case="Lower", fields=["Status"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.lower" in step.code

    def test_modify_case_title(self):
        handler = DataCleansingHandler()
        tool = _make_tool(modify_case="Title", fields=["Status"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.initcap" in step.code

    def test_remove_null_generates_coalesce(self):
        handler = DataCleansingHandler()
        tool = _make_tool(remove_null=True, fields=["Email"])
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.coalesce" in step.code
        assert 'F.lit("")' in step.code

    def test_chained_operations(self):
        handler = DataCleansingHandler()
        tool = _make_tool(
            trim_whitespace=True,
            modify_case="Upper",
            remove_null=True,
            fields=["Name"],
        )
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.trim" in step.code
        assert "F.upper" in step.code
        assert "F.coalesce" in step.code

    def test_multiple_fields(self):
        handler = DataCleansingHandler()
        tool = _make_tool(
            trim_whitespace=True, fields=["Name", "City", "State"]
        )
        step = handler.convert(tool, input_df_names=["df_5"])

        assert step.code.count("withColumn") == 3

    def test_no_fields_applies_to_all_strings(self):
        handler = DataCleansingHandler()
        tool = _make_tool(trim_whitespace=True, fields=None)
        step = handler.convert(tool, input_df_names=["df_5"])

        assert (
            "all string columns" in step.code.lower()
            or "StringType" in step.code
        )

    def test_output_df_name(self):
        handler = DataCleansingHandler()
        tool = _make_tool(tool_id=15, trim_whitespace=True, fields=["X"])
        step = handler.convert(tool, input_df_names=["df_8"])

        assert step.output_df == "df_15"

    def test_confidence_is_1(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=["A"])
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 1.0

    def test_imports_include_pyspark_functions(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=["A"])
        step = handler.convert(tool, input_df_names=["df_1"])

        assert "from pyspark.sql import functions as F" in step.imports

    def test_default_input_df_when_none(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=["A"])
        step = handler.convert(tool, input_df_names=None)

        assert "df_unknown" in step.code

    # --- Cleanse macro decoding tests ---

    def test_macro_columns_used_as_fields(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["FirstName", "LastName"]
        tool.config["macro_trim"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert 'withColumn("FirstName"' in step.code
        assert 'withColumn("LastName"' in step.code
        assert step.confidence == 0.65

    def test_macro_uppercase_sets_case_and_warning(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["City"]
        tool.config["macro_uppercase"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.upper" in step.code
        assert any(
            "uppercase config may be inaccurate" in n for n in step.notes
        )
        assert step.confidence == 0.65

    def test_macro_lowercase(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Status"]
        tool.config["macro_lowercase"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.lower" in step.code

    def test_macro_titlecase(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Name"]
        tool.config["macro_titlecase"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.initcap" in step.code

    def test_macro_trim_enables_trim(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Addr"]
        tool.config["macro_trim"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.trim" in step.code

    def test_macro_remove_tabs_enables_regexp(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Notes"]
        tool.config["macro_remove_tabs"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.regexp_replace" in step.code

    def test_macro_remove_extra_whitespace_enables_regexp(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Desc"]
        tool.config["macro_remove_extra_whitespace"] = True
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.regexp_replace" in step.code

    def test_macro_confidence_is_065(self):
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["X"]
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 0.65

    def test_non_macro_confidence_still_1(self):
        """Existing non-macro behavior unchanged."""
        handler = DataCleansingHandler()
        tool = _make_tool(trim_whitespace=True, fields=["A"])
        step = handler.convert(tool, input_df_names=["df_1"])

        assert step.confidence == 1.0
        assert step.notes == []

    def test_partial_macro_config(self):
        """Only some macro values present — others default to off."""
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = ["Col1"]
        tool.config["macro_trim"] = True
        # No macro_uppercase, macro_lowercase etc.
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "F.trim" in step.code
        assert "F.upper" not in step.code
        assert "F.lower" not in step.code
        assert step.confidence == 0.65

    def test_macro_empty_columns_falls_through_to_dynamic(self):
        """macro_columns present but empty list — dynamic all-string path."""
        handler = DataCleansingHandler()
        tool = _make_tool(fields=None)
        tool.config["macro_columns"] = []
        step = handler.convert(tool, input_df_names=["df_5"])

        assert "StringType" in step.code
        assert step.confidence == 0.65
