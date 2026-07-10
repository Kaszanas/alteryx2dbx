"""Handler for Alteryx DbFileOutput tool type."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


_FORMAT_MAP: dict[str, str] = {
    "0": "csv",
    "19": "excel",
    "25": "parquet",
}


class OutputDataHandler(ToolHandler):
    def convert(self, tool: AlteryxTool, input_df_names: list[str] | None = None) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        config = tool.config
        file_path = config.get("file_path", config.get("File", config.get("file", "UNKNOWN_PATH")))
        file_format_code = config.get("FormatType", config.get("FileFormat", "0"))
        fmt = _FORMAT_MAP.get(str(file_format_code), "csv")

        output_df = f"df_{tool.tool_id}"
        notes: list[str] = []

        lines = [
            f"# TODO: Update the file path below to a Databricks-accessible location",
            f"# Original Alteryx path: {file_path}",
            f"# {tool.annotation or 'Output Data'} (Tool {tool.tool_id})",
        ]

        if fmt == "excel":
            lines.append(f'{input_df}.toPandas().to_excel("{file_path}", index=False)')
            notes.append("Uses toPandas() for Excel output; consider performance for large datasets.")
        elif fmt == "parquet":
            lines.append(f'{input_df}.write.parquet("{file_path}")')
        else:
            lines.append(
                f'{input_df}.write.format("csv").option("header", "true").save("{file_path}")'
            )

        lines.append(f"{output_df} = {input_df}  # Passthrough for downstream")
        code = "\n".join(lines)
        notes.append(f"Output format: {fmt}")

        return GeneratedStep(
            step_name=f"output_{tool.tool_id}",
            code=code,
            imports=set(),
            input_dfs=[input_df],
            output_df=output_df,
            notes=notes,
            confidence=1.0,
        )


register_type_handler("DbFileOutput", OutputDataHandler)
