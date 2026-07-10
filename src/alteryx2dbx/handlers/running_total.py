"""Handler for Alteryx RunningTotal tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class RunningTotalHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        running_field = tool.config.get("rt_running_field", "")
        group_fields = tool.config.get("rt_group_fields", [])

        imports = {
            "from pyspark.sql import functions as F",
            "from pyspark.sql.window import Window",
        }

        lines = [
            f"# {tool.annotation or 'RunningTotal'} (Tool {tool.tool_id})",
        ]

        if running_field:
            if group_fields:
                partition_cols = ", ".join(f'"{f}"' for f in group_fields)
                window_expr = (
                    f"Window.partitionBy({partition_cols})"
                    f".rowsBetween(Window.unboundedPreceding, Window.currentRow)"
                )
            else:
                window_expr = (
                    "Window.orderBy(F.monotonically_increasing_id())"
                    ".rowsBetween(Window.unboundedPreceding, Window.currentRow)"
                )
            lines.append(f"_window_{tool.tool_id} = {window_expr}")
            lines.append(
                f"df_{tool.tool_id} = {input_df}.withColumn("
                f'"RunningTotal_{running_field}", '
                f'F.sum("{running_field}").over(_window_{tool.tool_id}))'
            )
        else:
            lines.append(
                f"df_{tool.tool_id} = {input_df}  # RunningTotal: no field specified"
            )

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"running_total_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=0.9,
        )


register_type_handler("RunningTotal", RunningTotalHandler)
