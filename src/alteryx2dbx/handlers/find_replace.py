from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class FindReplaceHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_dfs = input_df_names or ["df_unknown", "df_unknown"]
        data_df = input_dfs[0] if len(input_dfs) > 0 else "df_unknown"
        lookup_df = input_dfs[1] if len(input_dfs) > 1 else "df_unknown"
        tid = tool.tool_id
        config = tool.config

        find_field = config.get("find_field", "find")
        replace_field = config.get("replace_field", "replace")
        find_mode = config.get("find_mode", "Normal")

        code = (
            f'# {tool.annotation or "Find Replace"} (Tool {tid})\n'
            f'df_{tid} = {data_df}.join(\n'
            f'    {lookup_df}.select(F.col("{find_field}").alias("_fr_find_{tid}"), '
            f'F.col("{replace_field}").alias("_fr_replace_{tid}")),\n'
            f'    F.lower({data_df}["{find_field}"]) == F.lower(F.col("_fr_find_{tid}")), "left"\n'
            f')\n'
            f'df_{tid} = df_{tid}.withColumn("{find_field}", '
            f'F.coalesce(F.col("_fr_replace_{tid}"), {data_df}["{find_field}"]))\n'
            f'df_{tid} = df_{tid}.drop("_fr_find_{tid}", "_fr_replace_{tid}")'
        )

        return GeneratedStep(
            step_name=f"find_replace_{tid}",
            code=code,
            imports={"from pyspark.sql import functions as F"},
            input_dfs=[data_df, lookup_df],
            output_df=f"df_{tid}",
            notes=[f"FindReplace mode: {find_mode}"],
            confidence=0.9,
        )


register_type_handler("FindReplace", FindReplaceHandler)
