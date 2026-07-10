"""Handler for Alteryx Box Output tool (box_output_v*)."""
from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_prefix_handler


class BoxOutputHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        input_df = input_df_names[0] if input_df_names else "df_unknown"
        config = tool.config
        box_file_id = config.get("box_file_id", "UNKNOWN_FILE_ID")
        box_parent_id = config.get("box_parent_id", "UNKNOWN_FOLDER_ID")
        file_name = config.get("file_name", "output.csv")
        file_format = config.get("file_format", "Delimited")
        existing_behavior = config.get("existing_file_behavior", "Overwrite")
        output_df = f"df_{tool.tool_id}"

        imports = {"from io import BytesIO", "import pandas as pd"}
        notes = [
            f"Box output: {file_name} (folder ID: {box_parent_id})",
            "Box auth requires Databricks Secret scope — see _config.py",
        ]

        write_code = self._write_code(tool.tool_id, input_df, file_format)
        upload_code = self._upload_code(
            tool.tool_id, box_file_id, box_parent_id, file_name, existing_behavior
        )

        code = (
            f"# Box Output: {tool.annotation or file_name} (file: {file_name})\n"
            f"{write_code}\n"
            f"{upload_code}\n"
            f"{output_df} = {input_df}  # Passthrough for downstream"
        )

        return GeneratedStep(
            step_name=f"box_output_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[input_df],
            output_df=output_df,
            notes=notes,
            confidence=0.7,
        )

    @staticmethod
    def _write_code(tool_id: int, input_df: str, file_format: str) -> str:
        buf = f"_out_bytes_{tool_id}"
        if file_format == "Excel":
            return (
                f"{buf} = BytesIO()\n"
                f"{input_df}.toPandas().to_excel({buf}, index=False)\n"
                f"{buf}.seek(0)"
            )
        elif file_format == "JSON":
            return (
                f"{buf} = BytesIO()\n"
                f"{buf}.write({input_df}.toPandas().to_json(orient='records').encode())\n"
                f"{buf}.seek(0)"
            )
        else:
            return (
                f"{buf} = BytesIO()\n"
                f"{input_df}.toPandas().to_csv({buf}, index=False)\n"
                f"{buf}.seek(0)"
            )

    @staticmethod
    def _upload_code(
        tool_id: int,
        box_file_id: str,
        box_parent_id: str,
        file_name: str,
        existing_behavior: str,
    ) -> str:
        buf = f"_out_bytes_{tool_id}"
        if existing_behavior == "Overwrite":
            return f'box_client.file("{box_file_id}").update_contents_with_stream({buf})'
        elif existing_behavior == "Abort":
            return (
                f"# ExistingFileBehavior: Abort — TODO: check if file exists before upload\n"
                f'box_client.folder("{box_parent_id}").upload_stream({buf}, "{file_name}")'
            )
        else:
            return (
                f"# TODO: ExistingFileBehavior '{existing_behavior}' — implement manually\n"
                f'box_client.folder("{box_parent_id}").upload_stream({buf}, "{file_name}")'
            )


register_prefix_handler("box_output_v", BoxOutputHandler)
register_prefix_handler("BoxOutput", BoxOutputHandler)
