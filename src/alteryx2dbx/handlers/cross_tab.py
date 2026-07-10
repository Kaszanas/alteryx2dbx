"""Handler for Alteryx CrossTab tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class CrossTabHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        group_fields = tool.config.get("ct_group_fields", [])
        header_field = tool.config.get("ct_header_field", "")
        data_field = tool.config.get("ct_data_field", "")
        method = tool.config.get("ct_method", "Sum")

        method_map = {
            "Sum": "F.sum",
            "Count": "F.count",
            "Avg": "F.avg",
            "Min": "F.min",
            "Max": "F.max",
        }
        agg_func = method_map.get(method, "F.sum")

        group_cols = ", ".join(f'"{f}"' for f in group_fields)

        lines = [
            f"# {tool.annotation or 'CrossTab'} (Tool {tool.tool_id})",
        ]
        if group_fields and header_field and data_field:
            lines.append(
                f"df_{tool.tool_id} = {input_df}"
                f".groupBy({group_cols})"
                f'.pivot("{header_field}")'
                f'.agg({agg_func}("{data_field}"))'
            )
        else:
            lines.append(
                f"df_{tool.tool_id} = {input_df}  # CrossTab: missing config"
            )

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"cross_tab_{tool.tool_id}",
            code=code,
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=0.9,
        )


register_type_handler("CrossTab", CrossTabHandler)
