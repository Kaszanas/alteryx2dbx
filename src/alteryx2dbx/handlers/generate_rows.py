"""Handler for Alteryx GenerateRows tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class GenerateRowsHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        init_expr = tool.config.get("gr_init", "")
        condition_expr = tool.config.get("gr_condition", "")
        loop_expr = tool.config.get("gr_loop", "")

        lines = [
            f"# {tool.annotation or 'GenerateRows'} (Tool {tool.tool_id})",
            f"# Alteryx GenerateRows config:",
            f"#   Init: {init_expr}",
            f"#   Condition: {condition_expr}",
            f"#   Loop: {loop_expr}",
            f"# TODO: Translate loop logic manually — approximated with spark.range",
            f'df_{tool.tool_id} = spark.range(1, 101).toDF("RowCount")',
        ]

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"generate_rows_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[
                "GenerateRows approximated with spark.range — review loop logic manually",
            ],
            confidence=0.5,
        )


register_type_handler("GenerateRows", GenerateRowsHandler)
