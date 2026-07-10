from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep
from alteryx2dbx.transpiler.expression_emitter import transpile_expression

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class FilterHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        expression = tool.config.get("expression", "True")
        try:
            pyspark_expr = transpile_expression(expression)
            confidence = 1.0
            notes: list[str] = []
        except Exception as e:
            pyspark_expr = f"F.lit(True)  # FAILED TO TRANSPILE: {expression}"
            confidence = 0.3
            notes = [f"Expression transpilation failed: {e}"]

        code = (
            f"# {tool.annotation or 'Filter'} (Tool {tool.tool_id})\n"
            f"# Alteryx expression: {expression}\n"
            f"_filter_cond_{tool.tool_id} = {pyspark_expr}\n"
            f"df_{tool.tool_id}_true = {input_df}.filter(_filter_cond_{tool.tool_id})\n"
            f"df_{tool.tool_id}_false = {input_df}.filter(~(_filter_cond_{tool.tool_id}))\n"
            f"df_{tool.tool_id} = df_{tool.tool_id}_true  # Default: True branch"
        )
        if "." in expression and "[" in expression:
            notes.append("AMBIGUOUS: Filter expression may reference multiple tables — verify column source after migration")

        return GeneratedStep(
            step_name=f"filter_{tool.annotation or tool.tool_id}".lower().replace(" ", "_"),
            code=code,
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=notes,
            confidence=confidence,
        )


register_type_handler("Filter", FilterHandler)
