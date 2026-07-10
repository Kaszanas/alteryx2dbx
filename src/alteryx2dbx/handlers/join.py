"""Handler for Alteryx Join tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


_JOIN_TYPE_MAP = {
    "Inner": "inner",
    "Left": "left",
    "Right": "right",
    "Full": "full",
}


class JoinHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        left_df = (
            input_df_names[0]
            if input_df_names and len(input_df_names) > 0
            else "df_left"
        )
        right_df = (
            input_df_names[1]
            if input_df_names and len(input_df_names) > 1
            else "df_right"
        )

        join_type_raw = tool.config.get("join_type", "Inner")
        join_type = _JOIN_TYPE_MAP.get(join_type_raw, "inner")
        join_fields = tool.config.get("join_fields", [])

        # Build join condition
        conditions: list[str] = []
        for jf in join_fields:
            left_col = jf.get("left", "")
            right_col = jf.get("right", "")
            conditions.append(
                f'{left_df}["{left_col}"] == {right_df}["{right_col}"]'
            )

        if conditions:
            condition_str = " & ".join(f"({c})" for c in conditions)
        else:
            condition_str = "F.lit(True)"

        tid = tool.tool_id
        lines = [
            f"# {tool.annotation or 'Join'} (Tool {tid})",
            f"_join_cond_{tid} = {condition_str}",
            f'df_{tid}_joined = {left_df}.join({right_df}, _join_cond_{tid}, "{join_type}")',
            f'df_{tid}_left_only = {left_df}.join({right_df}, _join_cond_{tid}, "left_anti")',
            f'df_{tid}_right_only = {right_df}.join({left_df}, _join_cond_{tid}, "left_anti")',
            f"df_{tid} = df_{tid}_joined  # Default: Joined output",
        ]

        code = "\n".join(lines)
        imports: set[str] = set()
        if not conditions:
            imports.add("from pyspark.sql import functions as F")

        notes: list[str] = []
        if not join_fields:
            notes.append(
                "AMBIGUOUS: No join fields specified — may be cross join or join-by-position"
            )
        if "join_type" not in tool.config:
            notes.append(
                "AMBIGUOUS: Join type not specified — defaulting to inner join, verify this is correct"
            )

        return GeneratedStep(
            step_name=f"join_{tid}",
            code=code,
            imports=imports,
            input_dfs=[left_df, right_df],
            output_df=f"df_{tid}",
            notes=notes,
            confidence=1.0,
        )


register_type_handler("Join", JoinHandler)
