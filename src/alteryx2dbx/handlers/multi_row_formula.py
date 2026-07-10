from __future__ import annotations

import re

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep
from alteryx2dbx.transpiler.expression_emitter import transpile_expression

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class MultiRowFormulaHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        expression = tool.config.get("mrf_expression", "")
        field = tool.config.get("mrf_field", "unknown_field")
        group_fields = tool.config.get("mrf_group_fields", [])

        # Alteryx's configured look-back/look-forward row count for this tool. Not
        # used here: the actual F.lag()/F.lead() offset is parsed per-reference
        # directly out of the expression string's [Row-N:Field] tokens in the
        # transpiler (expression_emitter.py), so this config value is redundant.
        num_rows = tool.config.get("mrf_num_rows", "1")  # noqa: F841

        lines = [
            f"# {tool.annotation or 'MultiRowFormula'} (Tool {tool.tool_id})"
        ]
        imports = {
            "from pyspark.sql import functions as F",
            "from pyspark.sql.window import Window",
        }

        # Build window spec
        if group_fields:
            partition_str = ", ".join(f'"{g}"' for g in group_fields)
            window_def = f"_window_{tool.tool_id} = Window.partitionBy({partition_str}).orderBy(F.monotonically_increasing_id())"
        else:
            window_def = f"_window_{tool.tool_id} = Window.orderBy(F.monotonically_increasing_id())"

        lines.append(window_def)

        notes: list[str] = []
        confidence = 0.8  # Window ordering may not match Alteryx row order

        try:
            pyspark_expr = transpile_expression(expression)
            # Append .over(window) to any F.lag(...) calls in the expression
            pyspark_expr = pyspark_expr.replace("F.lag(", "F.lag(")
            # Use regex to append .over() after F.lag(..., N) patterns
            pyspark_expr = re.sub(
                r"(F\.lag\(F\.col\([^)]+\),\s*\d+\))",
                rf"\1.over(_window_{tool.tool_id})",
                pyspark_expr,
            )
            lines.append(
                f'df_{tool.tool_id} = {input_df}.withColumn("{field}", {pyspark_expr})'
            )
        except Exception as e:
            lines.append(
                f"# TODO: MultiRowFormula expression failed: {expression}"
            )
            lines.append(f"# Error: {e}")
            lines.append(
                f'# df_{tool.tool_id} = {input_df}.withColumn("{field}", ...)'
            )
            lines.append(f"df_{tool.tool_id} = {input_df}  # PASSTHROUGH")
            notes.append(f"Failed to transpile MultiRowFormula: {e}")
            confidence = 0.3

        if confidence == 0.8:
            notes.append(
                "Window ordering uses monotonically_increasing_id(); may not match Alteryx row order"
            )

        return GeneratedStep(
            step_name=f"multi_row_formula_{tool.tool_id}",
            code="\n".join(lines),
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=notes,
            confidence=confidence,
        )


register_type_handler("MultiRowFormula", MultiRowFormulaHandler)
