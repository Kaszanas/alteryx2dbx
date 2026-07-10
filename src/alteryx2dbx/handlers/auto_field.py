"""Handler for Alteryx AutoField tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class AutoFieldHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tid = tool.tool_id

        code = (
            f"# {tool.annotation or 'AutoField'} (Tool {tid})\n"
            f"# AutoField is a passthrough — Spark handles type optimization natively\n"
            f"df_{tid} = {input_df}"
        )

        return GeneratedStep(
            step_name=f"auto_field_{tid}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tid}",
            notes=["AutoField is a no-op in PySpark; Spark infers optimal types natively"],
            confidence=1.0,
        )


register_type_handler("AutoField", AutoFieldHandler)
