"""Handler for Alteryx Tile tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class TileHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tile_method = tool.config.get("tile_method", "EqualRecords")
        tile_num = tool.config.get("tile_num", 4)
        tile_field = tool.config.get("tile_field", "")

        imports = {
            "from pyspark.sql import functions as F",
            "from pyspark.sql.window import Window",
        }

        lines = [
            f"# {tool.annotation or 'Tile'} (Tool {tool.tool_id})",
        ]

        if tile_field:
            order_col = f'"{tile_field}"'
        else:
            order_col = "F.monotonically_increasing_id()"

        lines.append(
            f"_tile_window_{tool.tool_id} = Window.orderBy({order_col})"
        )
        lines.append(
            f"df_{tool.tool_id} = {input_df}.withColumn("
            f'"Tile", F.ntile({tile_num}).over(_tile_window_{tool.tool_id}))'
        )

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"tile_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[f"Tile method: {tile_method}"],
            confidence=0.85,
        )


register_type_handler("Tile", TileHandler)
