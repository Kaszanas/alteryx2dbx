"""Column tracking — walks the DAG to detect stale column references in Select tool configs."""

from __future__ import annotations

from dataclasses import dataclass

from alteryx2dbx.parser.models import AlteryxWorkflow


@dataclass
class ColumnWarning:
    tool_id: int
    field: str
    issue: str  # "STALE_REF" or "NEW_COLUMN"
    detail: str


def detect_column_mismatches(
    workflow: AlteryxWorkflow,
    execution_order: list[int],
) -> list[ColumnWarning]:
    """Walk DAG and compare upstream output_fields against downstream Select field references."""

    # Build output columns map: tool_id -> set of column names it outputs
    output_columns: dict[int, set[str]] = {}
    for tid in execution_order:
        tool = workflow.tools.get(tid)
        if tool and tool.output_fields:
            output_columns[tid] = {f.name for f in tool.output_fields}

    # Build upstream map from connections
    upstream: dict[int, list[int]] = {}
    for conn in workflow.connections:
        upstream.setdefault(conn.target_tool_id, []).append(conn.source_tool_id)

    warnings: list[ColumnWarning] = []
    for tid in execution_order:
        tool = workflow.tools.get(tid)
        if not tool:
            continue

        select_fields = tool.config.get("select_fields", [])
        if not select_fields:
            continue

        # Collect all upstream output column names
        upstream_cols: set[str] = set()
        for src_tid in upstream.get(tid, []):
            upstream_cols |= output_columns.get(src_tid, set())

        if not upstream_cols:
            continue  # No upstream data to compare against

        # Check each selected field reference against upstream
        for sf in select_fields:
            field_name = sf.get("field", "")
            if not field_name or field_name.startswith("*"):
                continue
            if sf.get("selected", "True") == "False":
                continue
            if field_name not in upstream_cols:
                warnings.append(
                    ColumnWarning(
                        tool_id=tid,
                        field=field_name,
                        issue="STALE_REF",
                        detail=f"Field '{field_name}' referenced in Select config but not found in upstream output fields",
                    )
                )

    return warnings
