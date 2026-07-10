"""Handler for Alteryx TextInput tool — inline embedded data."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class TextInputHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        tid = tool.tool_id
        fields = tool.config.get("ti_fields", [])
        data = tool.config.get("ti_data", [])

        if data and fields:
            rows_str = repr(data)
            cols_str = repr(fields)
            code = (
                f"# {tool.annotation or 'Text Input'} (Tool {tid})\n"
                f"df_{tid} = spark.createDataFrame({rows_str}, {cols_str})"
            )
        else:
            code = (
                f"# {tool.annotation or 'Text Input'} (Tool {tid})\n"
                f"# TODO: TextInput data not parsed — check raw XML\n"
                f"df_{tid} = spark.createDataFrame([], [])"
            )

        return GeneratedStep(
            step_name=f"text_input_{tid}",
            code=code,
            imports=set(),
            input_dfs=[],
            output_df=f"df_{tid}",
            confidence=1.0 if data else 0.5,
        )


register_type_handler("TextInput", TextInputHandler)
