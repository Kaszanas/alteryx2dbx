"""Generate 04_validate.py — DataComPy validation boilerplate."""

from __future__ import annotations

from pathlib import Path


def generate_validator(output_dir: Path, last_output_df: str) -> None:
    """Write 04_validate.py with DataComPy comparison boilerplate."""
    lines = [
        "# Databricks notebook source",
        "# 04 — Validation: Compare Alteryx vs Databricks output",
        "",
        "# COMMAND ----------",
        "",
        "import datacompy",
        "",
        "# COMMAND ----------",
        "",
        "# TODO: Load the original Alteryx output for comparison",
        '# alteryx_df = spark.read.format("csv").option("header", "true").load("alteryx_output/<filename>")',
        "",
        f"databricks_df = {last_output_df}",
        "",
        "# COMMAND ----------",
        "",
        "# TODO: Replace join_columns with the actual key column(s)",
        "comparison = datacompy.SparkCompare(",
        "    spark,",
        "    base_df=alteryx_df,",
        "    compare_df=databricks_df,",
        '    join_columns=["TODO_join_column"],  # TODO: Set correct join key(s)',
        ")",
        "",
        "# COMMAND ----------",
        "",
        "print(comparison.report())",
    ]

    with open(output_dir / "04_validate.py", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
