"""Handler for Alteryx RegEx tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class RegExHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        rx_field = tool.config.get("rx_field", "")
        rx_expression = tool.config.get("rx_expression", "")
        rx_mode = tool.config.get("rx_mode", "Replace")
        rx_replace = tool.config.get("rx_replace", "")
        rx_output_fields = tool.config.get("rx_output_fields", [])

        imports = {"from pyspark.sql import functions as F"}
        lines = [
            f"# {tool.annotation or 'RegEx'} (Tool {tool.tool_id})",
            f"# Mode: {rx_mode}, Pattern: {rx_expression}",
        ]

        confidence = 0.9

        if rx_mode == "Replace":
            lines.append(
                f'df_{tool.tool_id} = {input_df}.withColumn('
                f'"{rx_field}", '
                f'F.regexp_replace(F.col("{rx_field}"), r"{rx_expression}", "{rx_replace}"))'
            )
        elif rx_mode == "Parse":
            if rx_output_fields:
                assigns = []
                for i, out_field in enumerate(rx_output_fields, start=1):
                    assigns.append(
                        f'.withColumn("{out_field}", '
                        f'F.regexp_extract(F.col("{rx_field}"), r"{rx_expression}", {i}))'
                    )
                chain = "\n    ".join(assigns)
                lines.append(f"df_{tool.tool_id} = {input_df}\\\n    {chain}")
            else:
                lines.append(
                    f'df_{tool.tool_id} = {input_df}.withColumn('
                    f'"RegEx_Match", '
                    f'F.regexp_extract(F.col("{rx_field}"), r"{rx_expression}", 0))'
                )
        elif rx_mode == "Match":
            lines.append(
                f'df_{tool.tool_id} = {input_df}.filter('
                f'F.col("{rx_field}").rlike(r"{rx_expression}"))'
            )
        elif rx_mode == "Tokenize":
            lines.append(
                f'df_{tool.tool_id} = {input_df}.withColumn('
                f'"{rx_field}", '
                f'F.explode(F.split(F.col("{rx_field}"), r"{rx_expression}")))'
            )
        else:
            lines.append(
                f"df_{tool.tool_id} = {input_df}  # RegEx: unsupported mode '{rx_mode}'"
            )
            confidence = 0.3

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"regex_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=confidence,
        )


register_type_handler("RegEx", RegExHandler)
