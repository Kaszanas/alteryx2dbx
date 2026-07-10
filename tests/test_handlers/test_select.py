from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.select import SelectHandler


def _make_tool(tool_id=10, select_fields=None, annotation="Select Fields"):
    if select_fields is None:
        select_fields = [
            {
                "field": "Name",
                "selected": "True",
                "rename": "",
                "type": "String",
                "size": "50",
            },
            {
                "field": "Age",
                "selected": "True",
                "rename": "CustomerAge",
                "type": "Int32",
                "size": "4",
            },
            {
                "field": "TempCol",
                "selected": "False",
                "rename": "",
                "type": "String",
                "size": "100",
            },
        ]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Select",
        tool_type="Select",
        config={"select_fields": select_fields},
        annotation=annotation,
    )


class TestSelectHandler:
    def test_drops_deselected_fields(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert '.drop("TempCol")' in step.code

    def test_renames_fields(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert '.withColumnRenamed("Age", "CustomerAge")' in step.code

    def test_selects_remaining_fields_in_order(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_5"])
        assert '.select("Name", "CustomerAge")' in step.code

    def test_output_df_name(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(tool_id=15), input_df_names=["df_3"])
        assert step.output_df == "df_15"

    def test_confidence_is_1(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1"])
        assert step.confidence == 1.0

    def test_input_dfs(self):
        handler = SelectHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_7"])
        assert step.input_dfs == ["df_7"]

    def test_no_fields_passthrough(self):
        handler = SelectHandler()
        step = handler.convert(
            _make_tool(select_fields=[]), input_df_names=["df_1"]
        )
        assert "df_10 = df_1" in step.code
