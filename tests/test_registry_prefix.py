from alteryx2dbx.handlers.registry import HandlerRegistry
from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep


class FakeBoxHandler(ToolHandler):
    def convert(self, tool, input_df_names=None):
        return GeneratedStep(
            step_name="fake_box",
            code="# fake",
            imports=set(),
            input_dfs=[],
            output_df="df_1",
            notes=[],
            confidence=0.8,
        )


def _make_tool(plugin: str, tool_type: str = "") -> AlteryxTool:
    return AlteryxTool(
        tool_id=1,
        plugin=plugin,
        tool_type=tool_type or plugin,
        config={},
        annotation="",
        output_fields=[],
    )


def test_prefix_match_box_input():
    reg = HandlerRegistry()
    reg.register_prefix("box_input_v", FakeBoxHandler)
    handler = reg.get(_make_tool("box_input_v1.0.3"))
    assert type(handler).__name__ == "FakeBoxHandler"


def test_prefix_match_box_input_different_version():
    reg = HandlerRegistry()
    reg.register_prefix("box_input_v", FakeBoxHandler)
    handler = reg.get(_make_tool("box_input_v2.5.7"))
    assert type(handler).__name__ == "FakeBoxHandler"


def test_prefix_does_not_match_unrelated():
    reg = HandlerRegistry()
    reg.register_prefix("box_input_v", FakeBoxHandler)
    handler = reg.get(
        _make_tool("AlteryxBasePluginsGui.Filter.Filter", "Filter")
    )
    assert type(handler).__name__ == "UnsupportedHandler"


def test_exact_match_takes_priority_over_prefix():
    reg = HandlerRegistry()

    class ExactHandler(ToolHandler):
        def convert(self, tool, input_df_names=None):
            return GeneratedStep("exact", "# exact", set(), [], "df_1", [], 1.0)

    reg.register("box_input_v1.0.3", ExactHandler)
    reg.register_prefix("box_input_v", FakeBoxHandler)
    handler = reg.get(_make_tool("box_input_v1.0.3"))
    assert type(handler).__name__ == "ExactHandler"


def test_type_match_takes_priority_over_prefix():
    reg = HandlerRegistry()

    class TypeHandler(ToolHandler):
        def convert(self, tool, input_df_names=None):
            return GeneratedStep("type", "# type", set(), [], "df_1", [], 1.0)

    reg.register_type("box_input_v1.0.3", TypeHandler)
    reg.register_prefix("box_input_v", FakeBoxHandler)
    handler = reg.get(_make_tool("box_input_v1.0.3"))
    assert type(handler).__name__ == "TypeHandler"
