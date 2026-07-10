"""Handler for Alteryx Union tool type."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


class UnionHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        dfs = input_df_names if input_df_names else ["df_unknown"]

        lines = [f"# {tool.annotation or 'Union'} (Tool {tool.tool_id})"]

        if len(dfs) == 1:
            lines.append(f"df_{tool.tool_id} = {dfs[0]}")
        else:
            lines.append(f"df_{tool.tool_id} = {dfs[0]}")
            for df in dfs[1:]:
                lines.append(
                    f"df_{tool.tool_id} = df_{tool.tool_id}.unionByName({df}, allowMissingColumns=True)"
                )

        code = "\n".join(lines)

        return GeneratedStep(
            step_name=f"union_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=dfs,
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=1.0,
        )


register_type_handler("Union", UnionHandler)
