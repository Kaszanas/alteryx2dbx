"""Handler for Alteryx Summarize tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


_AGG_MAP = {
    "Sum": "F.sum",
    "Count": "F.count",
    "Avg": "F.avg",
    "Min": "F.min",
    "Max": "F.max",
    "First": "F.first",
    "Last": "F.last",
    "CountDistinct": "F.countDistinct",
}


class SummarizeHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        summarize_fields = tool.config.get("summarize_fields", [])

        group_cols: list[str] = []
        agg_exprs: list[str] = []

        for sf in summarize_fields:
            field = sf.get("field", "")
            action = sf.get("action", "")
            rename = sf.get("rename", "") or field

            if action == "GroupBy":
                group_cols.append(field)
            elif action == "Concat":
                agg_exprs.append(
                    f'F.concat_ws(",", F.collect_list("{field}")).alias("{rename}")'
                )
            elif action in _AGG_MAP:
                func = _AGG_MAP[action]
                agg_exprs.append(f'{func}("{field}").alias("{rename}")')
            else:
                agg_exprs.append(
                    f'F.lit(None).alias("{rename}")  # UNSUPPORTED action: {action}'
                )

        agg_str = ", ".join(agg_exprs)
        lines = [f"# {tool.annotation or 'Summarize'} (Tool {tool.tool_id})"]

        if group_cols:
            group_str = ", ".join(f'"{g}"' for g in group_cols)
            lines.append(f"df_{tool.tool_id} = {input_df}.groupBy({group_str}).agg({agg_str})")
        else:
            lines.append(f"df_{tool.tool_id} = {input_df}.agg({agg_str})")

        code = "\n".join(lines)

        notes: list[str] = []
        for sf in summarize_fields:
            field_name = sf.get("field", "")
            action = sf.get("action", "")
            if action == "First":
                notes.append(f"AMBIGUOUS: 'First' aggregation on '{field_name}' has no ORDER BY — result is non-deterministic in Spark")
            elif action == "Last":
                notes.append(f"AMBIGUOUS: 'Last' aggregation on '{field_name}' has no ORDER BY — result is non-deterministic in Spark")

        return GeneratedStep(
            step_name=f"summarize_{tool.tool_id}",
            code=code,
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=notes,
            confidence=1.0,
        )


register_type_handler("Summarize", SummarizeHandler)
