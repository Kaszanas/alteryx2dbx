"""Handler for Alteryx Sort tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class SortHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        sort_fields = tool.config.get("sort_fields", [])

        order_exprs: list[str] = []
        for sf in sort_fields:
            field = sf.get("field", "")
            order = sf.get("order", "Ascending")
            if order == "Descending":
                order_exprs.append(f'F.col("{field}").desc()')
            else:
                order_exprs.append(f'F.col("{field}").asc()')

        order_str = ", ".join(order_exprs) if order_exprs else ""

        lines = [
            f"# {tool.annotation or 'Sort'} (Tool {tool.tool_id})",
        ]
        if order_str:
            lines.append(f"df_{tool.tool_id} = {input_df}.orderBy({order_str})")
        else:
            lines.append(f"df_{tool.tool_id} = {input_df}  # No sort fields specified")

        code = "\n".join(lines)

        return GeneratedStep(
            step_name=f"sort_{tool.tool_id}",
            code=code,
            imports={"from pyspark.sql import functions as F"} if order_exprs else set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("Sort", SortHandler)
