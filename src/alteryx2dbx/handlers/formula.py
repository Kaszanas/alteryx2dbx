from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep
from alteryx2dbx.transpiler.expression_emitter import transpile_expression

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class FormulaHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        formula_fields = tool.config.get("formula_fields", [])

        lines = [f"# {tool.annotation or 'Formula'} (Tool {tool.tool_id})"]
        lines.append(f"df_{tool.tool_id} = {input_df}")
        all_notes: list[str] = []
        min_confidence = 1.0

        for ff in formula_fields:
            field_name = ff.get("field", "unknown_field")
            expression = ff.get("expression", "")
            try:
                pyspark_expr = transpile_expression(expression)
                lines.append(
                    f'df_{tool.tool_id} = df_{tool.tool_id}.withColumn("{field_name}", {pyspark_expr})'
                )
            except Exception as e:
                lines.append(f"# FAILED: {field_name} = {expression}")
                lines.append(f"# Error: {e}")
                lines.append(
                    f'# df_{tool.tool_id} = df_{tool.tool_id}.withColumn("{field_name}", ...)'
                )
                all_notes.append(f"Failed to transpile formula for {field_name}: {e}")
                min_confidence = min(min_confidence, 0.3)

        return GeneratedStep(
            step_name=f"formula_{tool.annotation or tool.tool_id}".lower().replace(" ", "_"),
            code="\n".join(lines),
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=all_notes,
            confidence=min_confidence,
        )


register_type_handler("Formula", FormulaHandler)
