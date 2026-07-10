"""Handler for Alteryx Box Input tool (box_input_v*)."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler, py_str_literal
from alteryx2dbx.handlers.registry import register_prefix_handler


_DELIMITER_MAP = {
    "COMMA": ",",
    "TAB": "\\t",
    "PIPE": "|",
    "SPACE": " ",
}


class BoxInputHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        config = tool.config
        box_file_id = config.get("box_file_id", "UNKNOWN_FILE_ID")
        file_name = config.get("file_name", "unknown")
        file_format = config.get("file_format", "Delimited")
        output_df = f"df_{tool.tool_id}"

        imports = {"from io import BytesIO", "import pandas as pd"}
        notes = [
            f"Box source: {file_name} (ID: {box_file_id})",
            "Box auth requires Databricks Secret scope — see _config.py",
        ]

        if file_format == "Avro":
            code = (
                f"# Box Input: {tool.annotation or file_name}\n"
                f"# TODO: Avro format from Box not auto-converted — implement manually\n"
                f"# Box file ID: {box_file_id}, file: {file_name}\n"
                f"{output_df} = spark.createDataFrame([], schema=None)  # PLACEHOLDER"
            )
            return GeneratedStep(
                step_name=f"box_input_{tool.tool_id}",
                code=code,
                imports=set(),
                input_dfs=[],
                output_df=output_df,
                notes=notes + ["Avro from Box: manual implementation required"],
                confidence=0.3,
            )

        read_expr = self._read_expression(tool.tool_id, config, file_format)

        code = (
            f"# Box Input: {tool.annotation or file_name} (file: {file_name})\n"
            f"_box_bytes_{tool.tool_id} = BytesIO(box_client.file({py_str_literal(box_file_id)}).content())\n"
            f"{output_df} = spark.createDataFrame({read_expr})"
        )

        return GeneratedStep(
            step_name=f"box_input_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[],
            output_df=output_df,
            notes=notes,
            confidence=0.8,
        )

    @staticmethod
    def _read_expression(tool_id: int, config: dict, file_format: str) -> str:
        if file_format == "Excel":
            sheet = config.get("excel_sheet", "Sheet1")
            return f"pd.read_excel(_box_bytes_{tool_id}, sheet_name={py_str_literal(sheet)})"
        elif file_format == "JSON":
            return f"pd.read_json(_box_bytes_{tool_id})"
        else:
            delimiter = _DELIMITER_MAP.get(
                config.get("delimiter", "COMMA"), ","
            )
            has_header = config.get("has_header", True)
            header_param = "0" if has_header else "None"
            return f'pd.read_csv(_box_bytes_{tool_id}, sep="{delimiter}", header={header_param})'


register_prefix_handler("box_input_v", BoxInputHandler)
register_prefix_handler("BoxInput", BoxInputHandler)
