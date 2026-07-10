from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.output_data import OutputDataHandler


def _make_tool(
    tool_id=40,
    file_path=r"C:\Output\results.csv",
    format_type="0",
    annotation="Write Output",
):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
        tool_type="DbFileOutput",
        config={"File": file_path, "FormatType": format_type},
        annotation=annotation,
    )


class TestOutputDataHandler:
    def test_csv_output(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_10"])
        assert '.write.format("csv")' in step.code
        assert '"header", "true"' in step.code
        assert ".save(" in step.code

    def test_excel_output(self):
        handler = OutputDataHandler()
        step = handler.convert(
            _make_tool(file_path=r"C:\Output\report.xlsx", format_type="19"),
            input_df_names=["df_10"],
        )
        assert ".toPandas().to_excel(" in step.code
        assert "index=False" in step.code

    def test_parquet_output(self):
        handler = OutputDataHandler()
        step = handler.convert(
            _make_tool(file_path=r"C:\Output\data.parquet", format_type="25"),
            input_df_names=["df_10"],
        )
        assert ".write.parquet(" in step.code

    def test_todo_comment(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_10"])
        assert "TODO: Update the file path" in step.code

    def test_output_df_name(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(tool_id=55), input_df_names=["df_10"])
        assert step.output_df == "df_55"

    def test_confidence_is_1(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_10"])
        assert step.confidence == 1.0

    def test_input_dfs(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_10"])
        assert step.input_dfs == ["df_10"]

    def test_notes_include_format(self):
        handler = OutputDataHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_10"])
        assert any("csv" in n.lower() for n in step.notes)
