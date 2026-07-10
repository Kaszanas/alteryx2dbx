"""Handler for Alteryx Transpose tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class TransposeHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        key_fields = tool.config.get("tp_key_fields", [])
        data_fields = tool.config.get("tp_data_fields", [])

        key_cols = ", ".join(f'"{f}"' for f in key_fields)

        # Build stack expression: stack(N, 'col1', col1, 'col2', col2, ...)
        stack_parts = []
        for f in data_fields:
            stack_parts.append(f"'{f}', `{f}`")
        stack_expr = f"stack({len(data_fields)}, {', '.join(stack_parts)}) as (Name, Value)"

        lines = [
            f"# {tool.annotation or 'Transpose'} (Tool {tool.tool_id})",
        ]
        if data_fields:
            select_cols = ", ".join(f'"{f}"' for f in key_fields) if key_fields else ""
            select_args = f'{select_cols}, "{stack_expr}"' if select_cols else f'"{stack_expr}"'
            lines.append(
                f"df_{tool.tool_id} = {input_df}.selectExpr({select_args})"
            )
        else:
            lines.append(
                f"df_{tool.tool_id} = {input_df}  # Transpose: no data fields"
            )

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"transpose_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=0.9,
        )


register_type_handler("Transpose", TransposeHandler)
