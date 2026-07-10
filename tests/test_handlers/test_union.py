from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.union import UnionHandler


def _make_tool(tool_id=30, annotation="Union Data"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Union",
        tool_type="Union",
        config={},
        annotation=annotation,
    )


class TestUnionHandler:
    def test_union_by_name(self):
        handler = UnionHandler()
        step = handler.convert(
            _make_tool(), input_df_names=["df_1", "df_2", "df_3"]
        )
        assert "unionByName" in step.code
        assert "allowMissingColumns=True" in step.code

    def test_multiple_inputs(self):
        handler = UnionHandler()
        step = handler.convert(
            _make_tool(), input_df_names=["df_1", "df_2", "df_3"]
        )
        assert step.input_dfs == ["df_1", "df_2", "df_3"]

    def test_chains_unions(self):
        handler = UnionHandler()
        step = handler.convert(
            _make_tool(tool_id=10), input_df_names=["df_1", "df_2", "df_3"]
        )
        assert "df_10 = df_1" in step.code
        assert "df_10 = df_10.unionByName(df_2" in step.code
        assert "df_10 = df_10.unionByName(df_3" in step.code

    def test_output_df_name(self):
        handler = UnionHandler()
        step = handler.convert(
            _make_tool(tool_id=50), input_df_names=["df_1", "df_2"]
        )
        assert step.output_df == "df_50"

    def test_confidence_is_1(self):
        handler = UnionHandler()
        step = handler.convert(_make_tool(), input_df_names=["df_1", "df_2"])
        assert step.confidence == 1.0

    def test_single_input(self):
        handler = UnionHandler()
        step = handler.convert(_make_tool(tool_id=10), input_df_names=["df_1"])
        assert "df_10 = df_1" in step.code
        assert "unionByName" not in step.code
