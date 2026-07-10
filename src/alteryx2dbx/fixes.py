"""Semantic fix registry for post-processing generated PySpark code.

Each fix is a function that takes a code string + context dict and returns
a tuple of (modified_code, was_applied). Fixes are registered in the FIXES
dict and applied via apply_fixes().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FixResult:
    """Result of applying all applicable fixes to a code string."""

    code: str
    applied_fixes: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Individual fix functions
# ---------------------------------------------------------------------------


def _fix_case_insensitive_join(code: str, context: dict) -> tuple[str, bool]:
    """Wrap string join key references in F.lower() for case-insensitive matching.

    Applies when tool_type is "Join" and join_fields are present.
    Transforms patterns like df_1["Col"] == df_2["Col"] into
    F.lower(df_1["Col"]) == F.lower(df_2["Col"]).
    """
    if context.get("tool_type") != "Join":
        return code, False

    join_fields = context.get("join_fields")
    if not join_fields:
        return code, False

    modified = code
    applied = False

    for jf in join_fields:
        left_col = jf.get("left", "")
        right_col = jf.get("right", "")

        # Collect all unique column names from join fields
        col_names = set()
        for col in (left_col, right_col):
            if col:
                col_names.add(col)

        for col_name in col_names:
            # Pattern: df_ref["col_name"] at a word boundary, not already wrapped
            # Use (?<!\() to avoid re-wrapping already-wrapped refs
            pattern = re.compile(
                r'(?<!\()(\b\w+\["' + re.escape(col_name) + r'"\])'
            )
            new_code = pattern.sub(r"F.lower(\1)", modified)
            if new_code != modified:
                applied = True
                modified = new_code

    return modified, applied


def _fix_null_safe_equality(code: str, context: dict) -> tuple[str, bool]:
    """Replace F.col("x") == F.lit("y") with F.col("x").eqNullSafe(F.lit("y")).

    Applies when tool_type is "Filter" or "Formula".
    """
    tool_type = context.get("tool_type", "")
    if tool_type not in ("Filter", "Formula"):
        return code, False

    # Match: F.col("...") == F.lit("...")
    # Use quoted string matching to handle column names with special chars like )
    pattern = re.compile(r'(F\.col\("[^"]*"\))\s*==\s*(F\.lit\("[^"]*"\))')

    new_code = pattern.sub(r"\1.eqNullSafe(\2)", code)
    applied = new_code != code
    return new_code, applied


def _fix_numeric_cast(code: str, context: dict) -> tuple[str, bool]:
    """Add explicit .cast(DecimalType(p,s)) for FixedDecimal output fields.

    Scans output_fields for FixedDecimal types and adds cast expressions
    to matching withColumn calls only.
    """
    output_fields = context.get("output_fields", [])
    decimal_fields = [
        f
        for f in output_fields
        if f.get("type") == "FixedDecimal" and f.get("size") and f.get("scale")
    ]
    if not decimal_fields:
        return code, False

    applied = False
    lines = code.split("\n")
    new_lines = []
    for line in lines:
        if ".withColumn(" in line:
            for f in decimal_fields:
                name = f["name"]
                pattern = re.compile(rf'F\.col\("{re.escape(name)}"\)')
                if pattern.search(line):
                    p, s = f["size"], f["scale"]
                    replacement = f'F.col("{name}").cast(DecimalType({p},{s}))'
                    line = pattern.sub(replacement, line)
                    applied = True
        new_lines.append(line)
    return "\n".join(new_lines), applied


def _fix_coalesce_typing(code: str, context: dict) -> tuple[str, bool]:
    """Fix COALESCE type mismatch: wrap numeric columns with CAST AS STRING when coalescing with empty string."""
    output_fields = context.get("output_fields", [])
    if not output_fields:
        return code, False

    _NUMERIC_TYPES = {
        "Int16",
        "Int32",
        "Int64",
        "Byte",
        "Double",
        "Float",
        "FixedDecimal",
    }
    numeric_cols = {
        fld["name"]
        for fld in output_fields
        if fld.get("type") in _NUMERIC_TYPES and fld.get("name")
    }
    if not numeric_cols:
        return code, False

    modified = code
    applied = False

    for col_name in numeric_cols:
        # Match COALESCE(col_name, '') or COALESCE(col_name, "")
        pattern = re.compile(
            r"""COALESCE\(\s*"""
            + re.escape(col_name)
            + r"""\s*,\s*(?:''|"")\s*\)""",
            re.IGNORECASE,
        )
        replacement = f"COALESCE(CAST({col_name} AS STRING), '')"
        new_code = pattern.sub(replacement, modified)
        if new_code != modified:
            applied = True
            modified = new_code

    return modified, applied


def _fix_safe_date_parsing(code: str, context: dict) -> tuple[str, bool]:
    """Replace TO_DATE / TO_TIMESTAMP with TRY_TO_DATE / TRY_TO_TIMESTAMP for null-safe date parsing."""
    modified = code
    modified = re.sub(r"\bTO_DATE\b", "TRY_TO_DATE", modified)
    modified = re.sub(r"\bTO_TIMESTAMP\b", "TRY_TO_TIMESTAMP", modified)
    return modified, modified != code


def _fix_safe_casting(code: str, context: dict) -> tuple[str, bool]:
    """Replace CAST( with TRY_CAST( inside F.expr() for Formula tools."""
    if context.get("tool_type") not in ("Formula", "MultiFieldFormula"):
        return code, False

    # Avoid double-wrapping: don't match CAST that's already TRY_CAST
    modified = re.sub(r"(?<!\bTRY_)\bCAST\(", "TRY_CAST(", code)
    return modified, modified != code


def _fix_float64_integer_keys(code: str, context: dict) -> tuple[str, bool]:
    """Warn about float64 coercion of integer join keys."""
    if context.get("tool_type") != "Join":
        return code, False

    _INT_TYPES = {"Int16", "Int32", "Int64", "Byte"}
    output_fields = context.get("output_fields", [])
    has_int = any(fld.get("type") in _INT_TYPES for fld in output_fields)
    if not has_int:
        return code, False

    warning = (
        "\n# WARNING: Integer columns may be read as float64 by pandas."
        ' Add .astype("Int64") before string casting to prevent scientific notation in join keys.'
    )
    return code + warning, True


def _fix_withcolumn_loop(code: str, context: dict) -> tuple[str, bool]:
    """Flag excessive sequential .withColumn() calls for performance."""
    count = len(re.findall(r"\.withColumn\(", code))
    if count < 10:
        return code, False

    warning = (
        f"\n# PERFORMANCE: {count} sequential .withColumn() calls detected."
        " Consider rewriting as a single .select() with column expressions"
        " for better Catalyst optimization."
    )
    return code + warning, True


def _fix_date_placeholder_clamping(
    code: str, context: dict
) -> tuple[str, bool]:
    """Warn about dates before 1900-01-01 crashing Excel/xlsxwriter."""
    has_excel_code = bool(re.search(r"\bto_excel\b|\bxlsxwriter\b", code))

    tool_type = context.get("tool_type", "")
    file_format = context.get("file_format", "")
    has_excel_context = (
        tool_type == "OutputData"
        and isinstance(file_format, str)
        and "xlsx" in file_format.lower()
    )

    if not has_excel_code and not has_excel_context:
        return code, False

    warning = (
        "\n# WARNING: Dates before 1900-01-01 will crash Excel/xlsxwriter."
        ' Consider: .withColumn("col", F.when(F.year(F.col("col")) < 1900, None).otherwise(F.col("col")))'
    )
    return code + warning, True


# ---------------------------------------------------------------------------
# Fix registry
# ---------------------------------------------------------------------------

FIXES: dict[str, dict] = {
    "case_insensitive_join": {
        "description": "Wrap string join keys in F.lower() for case-insensitive matching",
        "severity": "warning",
        "fn": _fix_case_insensitive_join,
        "phase": "general",
    },
    "null_safe_equality": {
        "description": "Replace == with eqNullSafe for null-safe comparisons in filters/formulas",
        "severity": "info",
        "fn": _fix_null_safe_equality,
        "phase": "general",
    },
    "numeric_cast": {
        "description": "Add explicit .cast(DecimalType(p,s)) for FixedDecimal output fields",
        "severity": "warning",
        "fn": _fix_numeric_cast,
        "phase": "general",
    },
    "coalesce_typing": {
        "description": "CAST numeric columns to STRING in COALESCE(..., '') expressions",
        "severity": "warning",
        "fn": _fix_coalesce_typing,
        "phase": "type-safety",
    },
    "safe_date_parsing": {
        "description": "Replace TO_DATE/TO_TIMESTAMP with TRY_TO_DATE/TRY_TO_TIMESTAMP",
        "severity": "warning",
        "fn": _fix_safe_date_parsing,
        "phase": "date-handling",
    },
    "safe_casting": {
        "description": "Replace CAST with TRY_CAST in Formula/MultiFieldFormula tools",
        "severity": "warning",
        "fn": _fix_safe_casting,
        "phase": "type-safety",
    },
    "float64_integer_keys": {
        "description": "Warn about integer join keys potentially read as float64 by pandas",
        "severity": "warning",
        "fn": _fix_float64_integer_keys,
        "phase": "key-integrity",
    },
    "withcolumn_loop": {
        "description": "Flag 10+ sequential .withColumn() calls for performance",
        "severity": "info",
        "fn": _fix_withcolumn_loop,
        "phase": "performance",
    },
    "date_placeholder_clamping": {
        "description": "Warn about pre-1900 dates crashing Excel/xlsxwriter",
        "severity": "info",
        "fn": _fix_date_placeholder_clamping,
        "phase": "date-handling",
    },
}


def register_fix(
    fix_id: str, description: str, severity: str, fn, phase: str = "general"
):
    """Register a new fix dynamically (for plugin system)."""
    FIXES[fix_id] = {
        "description": description,
        "severity": severity,
        "fn": fn,
        "phase": phase,
    }


def apply_fixes(code: str, context: dict) -> FixResult:
    """Run all registered fixes against the given code and context.

    Returns a FixResult with the (potentially modified) code and a list of
    dicts describing which fixes were applied.
    """
    result = FixResult(code=code)

    for fix_id, entry in FIXES.items():
        new_code, was_applied = entry["fn"](result.code, context)
        if was_applied:
            result.code = new_code
            result.applied_fixes.append(
                {
                    "fix_id": fix_id,
                    "description": entry["description"],
                    "severity": entry["severity"],
                }
            )

    return result
