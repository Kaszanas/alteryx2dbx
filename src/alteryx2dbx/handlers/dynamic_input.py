"""Handler for Alteryx DynamicInput tool — wildcard/glob file input."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class DynamicInputHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        tid = tool.tool_id
        file_path = tool.config.get("file_path", "UNKNOWN_PATH")

        code = (
            f"# {tool.annotation or 'Dynamic Input'} (Tool {tid})\n"
            f"# Original path: {file_path}\n"
            f"# TODO: Update glob pattern to Databricks-accessible location\n"
            f'df_{tid} = spark.read.format("csv") \\\n'
            f'    .option("header", "true") \\\n'
            f'    .option("inferSchema", "true") \\\n'
            f'    .load("{file_path}")'
        )
        return GeneratedStep(
            step_name=f"dynamic_input_{tid}",
            code=code,
            imports=set(),
            input_dfs=[],
            output_df=f"df_{tid}",
            notes=["Dynamic Input — verify glob pattern works in Databricks"],
            confidence=0.8,
        )


register_type_handler("DynamicInput", DynamicInputHandler)
