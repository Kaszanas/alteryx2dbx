"""Handler for Alteryx Select tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class SelectHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        select_fields = tool.config.get("select_fields", [])

        drops: list[str] = []
        renames: dict[str, str] = {}
        selected: list[str] = []

        for f in select_fields:
            field_name = f.get("field", "")
            is_selected = f.get("selected", "True") == "True"
            rename = f.get("rename", "")

            if not is_selected:
                drops.append(field_name)
            else:
                if rename:
                    renames[field_name] = rename
                    selected.append(rename)
                else:
                    selected.append(field_name)

        lines: list[str] = [
            f"# {tool.annotation or 'Select'} (Tool {tool.tool_id})",
            f"df_{tool.tool_id} = {input_df}",
        ]

        if drops:
            drop_args = ", ".join(f'"{d}"' for d in drops)
            lines.append(f"df_{tool.tool_id} = df_{tool.tool_id}.drop({drop_args})")

        for old_name, new_name in renames.items():
            lines.append(
                f'df_{tool.tool_id} = df_{tool.tool_id}.withColumnRenamed("{old_name}", "{new_name}")'
            )

        if selected:
            select_args = ", ".join(f'"{s}"' for s in selected)
            lines.append(f"df_{tool.tool_id} = df_{tool.tool_id}.select({select_args})")

        code = "\n".join(lines)

        return GeneratedStep(
            step_name=f"select_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("Select", SelectHandler)
register_type_handler("AlteryxSelect", SelectHandler)
