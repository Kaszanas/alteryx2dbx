from __future__ import annotations

from abc import ABC, abstractmethod

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep


def py_str_literal(value: str) -> str:
    """Render a string as a safely escaped Python string literal."""
    return repr(value)


def is_unc_path(path: str) -> bool:
    """Return True if path looks like a UNC/network path."""
    return path.startswith("\\\\") or path.startswith("//")


class ToolHandler(ABC):
    @abstractmethod
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep: ...


class UnsupportedHandler(ToolHandler):
    def convert(self, tool, input_df_names=None):
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        raw_xml = tool.config.get("_raw_xml", "<!-- no config -->")
        code = (
            f"# \u26a0\ufe0f UNSUPPORTED TOOL: {tool.tool_type} (Tool ID: {tool.tool_id})\n"
            f"# Annotation: {tool.annotation}\n"
            f"# Original config:\n"
            + "\n".join(f"# {line}" for line in raw_xml.split("\n"))
            + f"\n# TODO: Implement this transformation manually\n"
            f"df_{tool.tool_id} = {input_df}  # PASSTHROUGH"
        )
        return GeneratedStep(
            step_name=f"unsupported_{tool.tool_type.lower()}_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[f"Unsupported tool: {tool.tool_type} ({tool.plugin})"],
            confidence=0.0,
        )
