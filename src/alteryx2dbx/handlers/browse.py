"""Handler for Alteryx Browse / BrowseV2 tool — passthrough viewer."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class BrowseHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        code = (
            f"# {tool.annotation or 'Browse'} (Tool {tool.tool_id})\n"
            f"# Browse is a viewer tool — displaying first 20 rows\n"
            f"df_{tool.tool_id} = {input_df}\n"
            f"df_{tool.tool_id}.show(20, truncate=False)"
        )
        return GeneratedStep(
            step_name=f"browse_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            confidence=1.0,
        )


register_type_handler("BrowseV2", BrowseHandler)
register_type_handler("Browse", BrowseHandler)
