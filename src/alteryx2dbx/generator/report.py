"""Generate conversion_report.md — summary of conversion results."""

from __future__ import annotations

from pathlib import Path

from alteryx2dbx.parser.models import GeneratedStep, AlteryxTool
from alteryx2dbx.parser.schema_drift import SchemaDiff
from alteryx2dbx.parser.column_tracker import ColumnWarning


def generate_report(
    output_dir: Path,
    tools: dict[int, AlteryxTool],
    steps: dict[int, GeneratedStep],
    execution_order: list[int],
    schema_warnings: list[SchemaDiff] | None = None,
    column_warnings: list[ColumnWarning] | None = None,
) -> None:
    """Write conversion_report.md with summary stats and per-tool table."""
    total = len(execution_order)
    confidences = [
        steps[tid].confidence for tid in execution_order if tid in steps
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    manual_review = sum(1 for c in confidences if c < 1.0)

    lines = [
        "# Conversion Report",
        "",
        "## Summary",
        "",
        f"- **Tools converted**: {total}",
        f"- **Average confidence**: {avg_confidence:.0%}",
        f"- **Manual review needed**: {manual_review}",
        "",
        "## Tool Details",
        "",
        "| Tool ID | Type | Annotation | Confidence | Notes |",
        "|---------|------|------------|------------|-------|",
    ]

    for tid in execution_order:
        tool = tools.get(tid)
        step = steps.get(tid)
        if tool and step:
            notes_str = "; ".join(step.notes) if step.notes else ""
            lines.append(
                f"| {tid} | {tool.tool_type} | {tool.annotation} "
                f"| {step.confidence:.0%} | {notes_str} |"
            )

    if schema_warnings:
        lines.append("")
        lines.append("## Schema Drift Warnings")
        lines.append("")
        lines.append(
            "| Tool ID | Added Fields | Removed Fields | Type Changed |"
        )
        lines.append(
            "|---------|-------------|----------------|--------------|"
        )
        for diff in schema_warnings:
            added = ", ".join(diff.added) if diff.added else "-"
            removed = ", ".join(diff.removed) if diff.removed else "-"
            changed = (
                ", ".join(d["field"] for d in diff.type_changed)
                if diff.type_changed
                else "-"
            )
            lines.append(
                f"| {diff.tool_id} | {added} | {removed} | {changed} |"
            )

    if column_warnings:
        lines.append("")
        lines.append("## Column Mapping Warnings")
        lines.append("")
        lines.append("| Tool ID | Field | Issue | Detail |")
        lines.append("|---------|-------|-------|--------|")
        for w in column_warnings:
            lines.append(
                f"| {w.tool_id} | {w.field} | {w.issue} | {w.detail} |"
            )

    with open(output_dir / "conversion_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
