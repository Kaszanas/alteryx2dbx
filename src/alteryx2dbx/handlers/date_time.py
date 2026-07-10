"""Handler for Alteryx DateTime tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler

# Alteryx C-style format tokens to Spark Java-style format tokens
ALTERYX_TO_SPARK_FORMAT: dict[str, str] = {
    "%Y": "yyyy",
    "%y": "yy",
    "%m": "MM",
    "%d": "dd",
    "%H": "HH",
    "%M": "mm",
    "%S": "ss",
    "%p": "a",
    "%B": "MMMM",
    "%b": "MMM",
}


def _convert_format(alteryx_fmt: str) -> str:
    """Convert Alteryx C-style date format to Spark Java-style format."""
    result = alteryx_fmt
    for alt_token, spark_token in ALTERYX_TO_SPARK_FORMAT.items():
        result = result.replace(alt_token, spark_token)
    return result


class DateTimeHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        dt_field = tool.config.get("dt_field", "")
        dt_format_in = tool.config.get("dt_format_in", "")
        dt_format_out = tool.config.get("dt_format_out", "")
        dt_conversion = tool.config.get("dt_conversion", "DateTimeToString")

        imports = {"from pyspark.sql import functions as F"}

        lines = [
            f"# {tool.annotation or 'DateTime'} (Tool {tool.tool_id})",
        ]

        if dt_conversion == "DateTimeToString":
            spark_fmt = _convert_format(dt_format_out) if dt_format_out else "yyyy-MM-dd"
            lines.append(
                f'df_{tool.tool_id} = {input_df}.withColumn('
                f'"{dt_field}", '
                f'F.date_format(F.col("{dt_field}"), "{spark_fmt}"))'
            )
        elif dt_conversion == "StringToDateTime":
            spark_fmt = _convert_format(dt_format_in) if dt_format_in else "yyyy-MM-dd"
            lines.append(
                f'df_{tool.tool_id} = {input_df}.withColumn('
                f'"{dt_field}", '
                f'F.to_timestamp(F.col("{dt_field}"), "{spark_fmt}"))'
            )
        else:
            lines.append(
                f"df_{tool.tool_id} = {input_df}  "
                f"# DateTime: unsupported conversion '{dt_conversion}'"
            )

        code = "\n".join(lines)
        return GeneratedStep(
            step_name=f"datetime_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=f"df_{tool.tool_id}",
            notes=[],
            confidence=0.9,
        )


register_type_handler("DateTime", DateTimeHandler)
