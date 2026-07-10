"""Handler for Alteryx AppendFields tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class AppendFieldsHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        target_df = (
            input_df_names[0]
            if input_df_names and len(input_df_names) > 0
            else "df_target"
        )
        source_df = (
            input_df_names[1]
            if input_df_names and len(input_df_names) > 1
            else "df_source"
        )
        tid = tool.tool_id

        code = (
            f"# {tool.annotation or 'AppendFields'} (Tool {tid})\n"
            f"df_{tid} = {target_df}.crossJoin({source_df})"
        )

        return GeneratedStep(
            step_name=f"append_fields_{tid}",
            code=code,
            imports=set(),
            input_dfs=[target_df, source_df],
            output_df=f"df_{tid}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("AppendFields", AppendFieldsHandler)
