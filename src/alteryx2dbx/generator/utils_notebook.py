"""Emit the standard _utils.py Databricks notebook."""

from __future__ import annotations

from pathlib import Path

_UTILS_TEMPLATE = r'''# Databricks notebook source
# _utils — shared helper functions for converted Alteryx workflows

# COMMAND ----------

import logging
from datetime import datetime
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

logger = logging.getLogger(__name__)

# COMMAND ----------

def log_step(step_name: str, df: DataFrame) -> DataFrame:
    """Log step name and row count, return df for chaining."""
    count = df.count()
    logger.info("[%s] %s — %d rows", datetime.now().strftime("%H:%M:%S"), step_name, count)
    return df

# COMMAND ----------

def null_safe_join(left: DataFrame, right: DataFrame, left_key: str, right_key: str, how: str = "inner") -> DataFrame:
    """Join two DataFrames using F.lower() on both keys for case-insensitive matching."""
    return left.join(
        right,
        F.lower(F.col(left_key)) == F.lower(F.col(right_key)),
        how=how,
    )

# COMMAND ----------

def check_row_count(df: DataFrame, expected: int, tolerance: float = 0.05, step_name: str = "") -> bool:
    """Check that df row count is within tolerance of expected.

    Returns True if within tolerance, raises ValueError otherwise.
    """
    actual = df.count()
    lower = int(expected * (1 - tolerance))
    upper = int(expected * (1 + tolerance))
    if lower <= actual <= upper:
        logger.info("[%s] Row count OK: %d (expected %d ±%d%%)", step_name, actual, expected, int(tolerance * 100))
        return True
    msg = f"[{step_name}] Row count {actual} outside tolerance: expected {expected} ±{int(tolerance * 100)}% ({lower}–{upper})"
    logger.warning(msg)
    raise ValueError(msg)

# COMMAND ----------

def safe_cast(df: DataFrame, col_name: str, target_type) -> DataFrame:
    """Cast a column to target_type, preserving nulls."""
    return df.withColumn(
        col_name,
        F.when(F.col(col_name).isNull(), F.lit(None).cast(target_type))
         .otherwise(F.col(col_name).cast(target_type)),
    )
'''


_BOX_UTILS_TEMPLATE = r'''
# COMMAND ----------

# Box.com client — authenticated via Databricks Secrets
import json
from boxsdk import JWTAuth, Client

def get_box_client():
    """Return an authenticated Box client using JWT credentials from Databricks Secrets."""
    jwt_config = json.loads(dbutils.secrets.get(BOX_SECRET_SCOPE, "jwt_config"))
    auth = JWTAuth.from_settings_dictionary(jwt_config)
    return Client(auth)

box_client = get_box_client()
'''


def generate_utils_notebook(output_dir: Path, *, has_box: bool = False) -> Path:
    """Write the _utils.py Databricks notebook into *output_dir*.

    Returns the path to the written file.
    """
    content = _UTILS_TEMPLATE
    if has_box:
        content += _BOX_UTILS_TEMPLATE
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "_utils.py"
    path.write_text(content, encoding="utf-8")
    return path
