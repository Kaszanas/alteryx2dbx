"""Handler for Alteryx Sample tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class SampleHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tid = tool.tool_id

        mode = tool.config.get("sample_mode", "First")
        n = tool.config.get("sample_n", 1)
        pct = tool.config.get("sample_pct", 0.1)

        imports: set[str] = set()
        confidence = 1.0
        notes: list[str] = []

        if mode == "First":
            transform = f"{input_df}.limit({n})"
        elif mode == "Last":
            # PySpark has no native .tail() that returns a DataFrame; reverse-sort by row index
            imports.add("from pyspark.sql import functions as F")
            imports.add("from pyspark.sql import Window")
            transform = (
                f"{input_df}.withColumn('_row_num_{tid}', F.monotonically_increasing_id())"
                f".orderBy(F.desc('_row_num_{tid}')).limit({n})"
                f".drop('_row_num_{tid}')"
            )
            confidence = 0.5
            notes.append(
                "Last-N sampling approximated via monotonically_increasing_id ordering"
            )
        elif mode == "Random":
            imports.add("from pyspark.sql import functions as F")
            transform = f"{input_df}.orderBy(F.rand()).limit({n})"
        elif mode == "Percentage":
            transform = f"{input_df}.sample(fraction={pct})"
            confidence = 0.5
            notes.append("Percentage sampling is approximate in Spark")
        else:
            transform = f"{input_df}.limit({n})"
            notes.append(f"Unknown sample mode '{mode}', defaulting to First-N")

        code = f"# {tool.annotation or 'Sample'} (Tool {tid})\ndf_{tid} = {transform}"

        return GeneratedStep(
            step_name=f"sample_{tid}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tid}",
            notes=notes,
            confidence=confidence,
        )


register_type_handler("Sample", SampleHandler)
