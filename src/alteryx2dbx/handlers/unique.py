"""Handler for Alteryx Unique tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class UniqueHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        tid = tool.tool_id

        unique_fields = tool.config.get("unique_fields", [])
        fields_repr = repr(unique_fields) if unique_fields else "[]"

        notes: list[str] = []
        if not unique_fields:
            notes.append(
                "No unique fields specified; deduplicating on all columns"
            )

        if unique_fields:
            dedup_call = f"{input_df}.dropDuplicates({fields_repr})"
            dup_call = f"{input_df}.subtract(df_{tid}_unique)"
        else:
            dedup_call = f"{input_df}.dropDuplicates()"
            dup_call = f"{input_df}.subtract(df_{tid}_unique)"

        code = (
            f"# {tool.annotation or 'Unique'} (Tool {tid})\n"
            f"df_{tid}_unique = {dedup_call}\n"
            f"df_{tid}_duplicates = {dup_call}\n"
            f"df_{tid} = df_{tid}_unique  # Default: Unique output"
        )

        return GeneratedStep(
            step_name=f"unique_{tid}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tid}",
            notes=notes,
            confidence=1.0,
        )


register_type_handler("Unique", UniqueHandler)
