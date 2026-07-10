"""Handler for Alteryx TextToColumns tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class TextToColumnsHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        ttc_field = tool.config.get("ttc_field", "")
        ttc_delimiter = tool.config.get("ttc_delimiter", ",")
        ttc_num_columns = tool.config.get("ttc_num_columns", 2)
        ttc_split_to_rows = tool.config.get("ttc_split_to_rows", False)
        ttc_root_name = tool.config.get("ttc_root_name", ttc_field)

        imports = {"from pyspark.sql import functions as F"}

        lines = [
            f"# {tool.annotation or 'TextToColumns'} (Tool {tool.tool_id})",
        ]

        if ttc_split_to_rows:
            lines.append(
                f"df_{tool.tool_id} = {input_df}.withColumn("
                f'"{ttc_root_name}", '
                f'F.explode(F.split(F.col("{ttc_field}"), "{ttc_delimiter}")))'
            )
        else:
            # Split to columns
            lines.append(
                f'_split_{tool.tool_id} = F.split(F.col("{ttc_field}"), "{ttc_delimiter}")'
            )
            assigns = []
            for i in range(ttc_num_columns):
                col_name = f"{ttc_root_name}{i + 1}"
                assigns.append(
                    f'.withColumn("{col_name}", _split_{tool.tool_id}.getItem({i}))'
                )
            chain = "\n    ".join(assigns)
            lines.append(f"df_{tool.tool_id} = {input_df}\\\n    {chain}")

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"text_to_columns_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=0.9,
        )


register_type_handler("TextToColumns", TextToColumnsHandler)
