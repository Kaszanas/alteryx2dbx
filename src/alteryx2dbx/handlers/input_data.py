"""Handler for Alteryx InputData / DbFileInput tool types."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool, GeneratedStep

from alteryx2dbx.handlers.base import ToolHandler
from alteryx2dbx.handlers.registry import register_type_handler


# Alteryx FileFormat codes → human-readable format names
_FORMAT_MAP: dict[str, str] = {
    "0": "csv",
    "19": "excel",
    "25": "parquet",
}


class InputDataHandler(ToolHandler):
    def convert(
        self, tool: AlteryxTool, input_df_names: list[str] | None = None
    ) -> GeneratedStep:
        config = tool.config
        file_path = config.get(
            "file_path", config.get("File", config.get("file", "UNKNOWN_PATH"))
        )
        file_format_code = config.get(
            "FormatType", config.get("FileFormat", "0")
        )
        fmt = _FORMAT_MAP.get(str(file_format_code), "csv")
        header = config.get("HeaderRow", "true").lower() == "true"
        output_df = f"df_{tool.tool_id}"

        imports: set[str] = {"from pyspark.sql import SparkSession"}
        notes: list[str] = []

        if fmt == "excel":
            code = self._excel_code(output_df, file_path, config)
            notes.append(
                "Uses com.crealytics.spark.excel; ensure the JAR is on the cluster."
            )
        elif fmt == "parquet":
            code = self._parquet_code(output_df, file_path)
        else:
            code = self._csv_code(output_df, file_path, header)

        # Always remind about path
        code = (
            f"# TODO: Update the file path below to a Databricks-accessible location\n"
            f"# Original Alteryx path: {file_path}\n" + code
        )

        notes.append(f"Source format: {fmt}")

        return GeneratedStep(
            step_name=f"input_{tool.tool_id}",
            code=code,
            imports=imports,
            input_dfs=[],
            output_df=output_df,
            notes=notes,
            confidence=0.9,
        )

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _csv_code(output_df: str, path: str, header: bool) -> str:
        header_str = "true" if header else "false"
        return (
            f'{output_df} = spark.read.format("csv")\\\n'
            f'    .option("header", "{header_str}")\\\n'
            f'    .option("inferSchema", "true")\\\n'
            f'    .load("{path}")'
        )

    @staticmethod
    def _excel_code(output_df: str, path: str, config: dict) -> str:
        sheet = config.get("Sheet", "Sheet1")
        return (
            f'{output_df} = spark.read.format("com.crealytics.spark.excel")\\\n'
            f'    .option("header", "true")\\\n'
            f'    .option("dataAddress", "\'{sheet}\'!A1")\\\n'
            f'    .option("inferSchema", "true")\\\n'
            f'    .load("{path}")'
        )

    @staticmethod
    def _parquet_code(output_df: str, path: str) -> str:
        return f'{output_df} = spark.read.parquet("{path}")'


register_type_handler("DbFileInput", InputDataHandler)
