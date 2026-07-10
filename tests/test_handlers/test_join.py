from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.join import JoinHandler


def _make_tool(
    tool_id=20, join_type="Inner", join_fields=None, annotation="Join Data"
):
    if join_fields is None:
        join_fields = [{"left": "CustomerID", "right": "CustID"}]
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Join",
        tool_type="Join",
        config={"join_type": join_type, "join_fields": join_fields},
        annotation=annotation,
    )


class TestJoinHandler:
    def test_inner_join_code(self):
        handler = JoinHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert "df_1.join(df_2" in step.code
        assert '"inner"' in step.code

    def test_two_input_dfs(self):
        handler = JoinHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert step.input_dfs == ["df_1", "df_2"]

    def test_three_outputs(self):
        handler = JoinHandler()
        step = handler.convert(
            _make_tool(tool_id=5), input_df_names=["df_1", "df_2"]
        )
        assert "df_5_joined" in step.code
        assert "df_5_left_only" in step.code
        assert "df_5_right_only" in step.code
        assert "df_5 = df_5_joined" in step.code

    def test_output_df_name(self):
        handler = JoinHandler()
        step = handler.convert(
            _make_tool(tool_id=30), input_df_names=["df_1", "df_2"]
        )
        assert step.output_df == "df_30"

    def test_confidence_is_1(self):
        handler = JoinHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert step.confidence == 1.0

    def test_join_condition_references_fields(self):
        handler = JoinHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert '"CustomerID"' in step.code
        assert '"CustID"' in step.code

    def test_left_join(self):
        handler = JoinHandler()
        step = handler.convert(
            _make_tool(join_type="Left"), input_df_names=["df_1", "df_2"]
        )
        assert '"left"' in step.code

    def test_multiple_join_fields(self):
        handler = JoinHandler()
        fields = [
            {"left": "ID", "right": "ID"},
            {"left": "Date", "right": "TxnDate"},
        ]
        step = handler.convert(
            _make_tool(join_fields=fields), input_df_names=["df_1", "df_2"]
        )
        assert '"ID"' in step.code
        assert '"TxnDate"' in step.code

    def test_ambiguous_no_join_fields(self):
        handler = JoinHandler()
        step = handler.convert(
            _make_tool(join_fields=[]), input_df_names=["df_1", "df_2"]
        )
        assert any(
            "AMBIGUOUS" in n and "No join fields" in n for n in step.notes
        )

    def test_ambiguous_no_join_type(self):
        handler = JoinHandler()
        tool = AlteryxTool(
            tool_id=20,
            plugin="AlteryxBasePluginsEngine.Join",
            tool_type="Join",
            config={"join_fields": [{"left": "ID", "right": "ID"}]},
            annotation="Join Data",
        )
        step = handler.convert(tool, input_df_names=["df_1", "df_2"])
        assert any(
            "AMBIGUOUS" in n and "Join type not specified" in n
            for n in step.notes
        )

    def test_no_ambiguous_notes_for_clean_join(self):
        handler = JoinHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert not any("AMBIGUOUS" in n for n in step.notes)

    def test_ambiguous_both_missing(self):
        handler = JoinHandler()
        tool = AlteryxTool(
            tool_id=20,
            plugin="AlteryxBasePluginsEngine.Join",
            tool_type="Join",
            config={},
            annotation="Join Data",
        )
        step = handler.convert(tool, input_df_names=["df_1", "df_2"])
        ambiguous_notes = [n for n in step.notes if "AMBIGUOUS" in n]
        assert len(ambiguous_notes) == 2
