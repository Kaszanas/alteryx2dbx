from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep
from alteryx2dbx.transpiler.expression_emitter import transpile_expression

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class MultiFieldFormulaHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        expression = tool.config.get("mff_expression", "")
        fields = tool.config.get("mff_fields", [])

        lines = [
            f"# {tool.annotation or 'MultiFieldFormula'} (Tool {tool.tool_id})"
        ]
        lines.append(f"df_{tool.tool_id} = {input_df}")
        imports = {"from pyspark.sql import functions as F"}

        notes: list[str] = []
        min_confidence = 1.0

        for field_name in fields:
            # Substitute Alteryx placeholders
            subst_expr = expression.replace("_CurrentField_", f"[{field_name}]")
            subst_expr = subst_expr.replace(
                "_CurrentFieldName_", f'"{field_name}"'
            )

            try:
                pyspark_expr = transpile_expression(subst_expr)
                lines.append(
                    f'df_{tool.tool_id} = df_{tool.tool_id}.withColumn("{field_name}", {pyspark_expr})'
                )
            except Exception as e:
                lines.append(
                    f"# TODO: MultiFieldFormula failed for field {field_name}: {subst_expr}"
                )
                lines.append(f"# Error: {e}")
                lines.append(
                    f'# df_{tool.tool_id} = df_{tool.tool_id}.withColumn("{field_name}", ...)'
                )
                notes.append(f"Failed to transpile for field {field_name}: {e}")
                min_confidence = min(min_confidence, 0.3)

        return GeneratedStep(
            step_name=f"multi_field_formula_{tool.tool_id}",
            code="\n".join(lines),
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=notes,
            confidence=min_confidence,
        )


register_type_handler("MultiFieldFormula", MultiFieldFormulaHandler)
