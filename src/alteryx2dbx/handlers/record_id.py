"""Handler for Alteryx RecordID tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class RecordIDHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tid = tool.tool_id

        field_name = tool.config.get("FieldName", "RecordID")

        code = (
            f"# {tool.annotation or 'RecordID'} (Tool {tid})\n"
            f'df_{tid} = {input_df}.withColumn("{field_name}", F.monotonically_increasing_id() + 1)'
        )

        return GeneratedStep(
            step_name=f"record_id_{tid}",
            code=code,
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[input_df],
            output_df=f"df_{tid}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("RecordID", RecordIDHandler)
