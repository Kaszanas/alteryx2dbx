"""Handler for Alteryx CountRecords tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class CountRecordsHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tid = tool.tool_id

        code = (
            f"# {tool.annotation or 'CountRecords'} (Tool {tid})\n"
            f'df_{tid} = spark.createDataFrame([({input_df}.count(),)], ["Count"])'
        )

        return GeneratedStep(
            step_name=f"count_records_{tid}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tid}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("CountRecords", CountRecordsHandler)
