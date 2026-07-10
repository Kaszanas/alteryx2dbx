"""Generate migration_report.md for a single workflow."""
from __future__ import annotations

from pathlib import Path
from datetime import date

from alteryx2dbx.parser.models import AlteryxWorkflow
from alteryx2dbx.parser.schema_drift import detect_schema_drift
from alteryx2dbx.parser.column_tracker import detect_column_mismatches
from alteryx2dbx.dag.resolver import resolve_dag
from alteryx2dbx.handlers.registry import get_handler
from alteryx2dbx.fixes import apply_fixes
from alteryx2dbx.document.mermaid import generate_mermaid
import alteryx2dbx.handlers  # noqa: F401

_INPUT_TYPES = {"DbFileInput", "TextInput", "InputData", "DynamicInput"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData", "Browse"}
_BOX_INPUT_PREFIX = "box_input_v"
_BOX_OUTPUT_PREFIX = "box_output_v"


def generate_migration_report(workflow: AlteryxWorkflow, output_dir: Path) -> Path:
    """Generate migration_report.md and return its path."""
    execution_order = resolve_dag(workflow)
    steps = _run_handlers(workflow, execution_order)
    lines = []

    lines.append(f"# {workflow.name}")
    lines.append("")
    lines.extend(_executive_summary(workflow, steps, execution_order))
    lines.append("## Data Flow Diagram")
    lines.append("")
    lines.append(generate_mermaid(workflow))
    lines.append("")
    lines.extend(_data_source_inventory(workflow, execution_order))
    lines.extend(_output_inventory(workflow, execution_order))
    lines.extend(_business_logic_summary(workflow, steps, execution_order))
    lines.extend(_conversion_details(workflow, steps, execution_order))
    lines.extend(_schema_drift_section(workflow, execution_order))
    lines.extend(_column_mapping_section(workflow, execution_order))
    lines.extend(_review_checklist(workflow, steps, execution_order))

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "migration_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _run_handlers(workflow, execution_order):
    input_map = {}
    for conn in workflow.connections:
        df_name = f"df_{conn.source_tool_id}"
        input_map.setdefault(conn.target_tool_id, []).append(df_name)
    steps = {}
    for tool_id in execution_order:
        tool = workflow.tools[tool_id]
        handler = get_handler(tool)
        input_dfs = input_map.get(tool_id, [])
        step = handler.convert(tool, input_df_names=input_dfs or None)
        context = {"tool_type": tool.tool_type, **tool.config,
                   "output_fields": [{"name": f.name, "type": f.type, "size": f.size, "scale": f.scale}
                                     for f in tool.output_fields]}
        fix_result = apply_fixes(step.code, context)
        step.code = fix_result.code
        steps[tool_id] = step
    return steps


def _is_input_tool(tool):
    return tool.tool_type in _INPUT_TYPES or tool.plugin.startswith(_BOX_INPUT_PREFIX)

def _is_output_tool(tool):
    return tool.tool_type in _OUTPUT_TYPES or tool.plugin.startswith(_BOX_OUTPUT_PREFIX)


def _executive_summary(workflow, steps, execution_order):
    lines = ["## Executive Summary", ""]
    meta = workflow.properties.get("MetaInfo", {})
    author = meta.get("Author", "Unknown")
    description = meta.get("Description", "")
    total = len(execution_order)
    confidences = [steps[tid].confidence for tid in execution_order if tid in steps]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    supported = sum(1 for c in confidences if c > 0)
    unsupported = total - supported

    readiness = "Ready" if avg_conf > 0.9 else "Needs Review" if avg_conf > 0.7 else "Significant Manual Work"
    complexity = "Simple" if total < 10 else "Medium" if total < 30 else "Complex"

    lines.append(f"- **Workflow**: {workflow.name}")
    if author and author != "Unknown":
        lines.append(f"- **Author**: {author}")
    if description:
        lines.append(f"- **Description**: {description}")
    lines.append(f"- **Readiness**: {readiness}")
    lines.append(f"- **Confidence**: {avg_conf:.0%}")
    lines.append(f"- **Complexity**: {complexity} ({total} tools)")
    lines.append(f"- **Supported**: {supported}/{total} tools")
    if unsupported > 0:
        lines.append(f"- **Unsupported**: {unsupported} tools")
    lines.append(f"- **Generated**: {date.today().isoformat()}")
    lines.append("")
    return lines


def _data_source_inventory(workflow, execution_order):
    lines = ["## Data Source Inventory", ""]
    lines.append("| Tool ID | Type | Source | Format | Fields | Notes |")
    lines.append("|---------|------|--------|--------|--------|-------|")
    for tid in execution_order:
        tool = workflow.tools[tid]
        if not _is_input_tool(tool):
            continue
        config = tool.config
        source = config.get("file_path", config.get("File", ""))
        if tool.plugin.startswith(_BOX_INPUT_PREFIX):
            source = f"Box: {config.get('file_name', source)} (ID: {config.get('box_file_id', '?')})"
        fmt = config.get("file_format", config.get("FileFormat", ""))
        field_count = len(tool.output_fields)
        notes = tool.annotation or ""
        lines.append(f"| {tid} | {tool.tool_type} | {source} | {fmt} | {field_count} | {notes} |")
    lines.append("")
    return lines


def _output_inventory(workflow, execution_order):
    lines = ["## Output Inventory", ""]
    lines.append("| Tool ID | Type | Destination | Format | Notes |")
    lines.append("|---------|------|-------------|--------|-------|")
    for tid in execution_order:
        tool = workflow.tools[tid]
        if not _is_output_tool(tool):
            continue
        config = tool.config
        dest = config.get("file_path", config.get("File", ""))
        if tool.plugin.startswith(_BOX_OUTPUT_PREFIX):
            dest = f"Box: {config.get('file_name', dest)} (folder: {config.get('box_parent_id', '?')})"
        fmt = config.get("file_format", config.get("FileFormat", ""))
        notes = tool.annotation or ""
        lines.append(f"| {tid} | {tool.tool_type} | {dest} | {fmt} | {notes} |")
    lines.append("")
    return lines


def _business_logic_summary(workflow, steps, execution_order):
    lines = ["## Business Logic Summary", ""]
    found_logic = False
    for tid in execution_order:
        tool = workflow.tools[tid]
        config = tool.config
        step = steps.get(tid)
        flag = "" if not step or step.confidence >= 1.0 else " :warning:"

        if tool.tool_type == "Filter":
            expr = config.get("expression", "?")
            lines.append(f"- **[{tid}] Filter: {tool.annotation or 'Filter'}**{flag}")
            lines.append(f"  - Filters rows where `{expr}`")
            found_logic = True
        elif tool.tool_type == "Join":
            fields = config.get("join_fields", [])
            field_str = ", ".join(f"{f['left']} = {f['right']}" for f in fields) if fields else "?"
            lines.append(f"- **[{tid}] Join: {tool.annotation or 'Join'}**{flag}")
            lines.append(f"  - Joins on: {field_str}")
            found_logic = True
        elif tool.tool_type == "Formula":
            for ff in config.get("formula_fields", []):
                lines.append(f"- **[{tid}] Formula: {tool.annotation or 'Formula'}**{flag}")
                lines.append(f"  - Sets `{ff.get('field', '?')}` = `{ff.get('expression', '?')}`")
                found_logic = True
        elif tool.tool_type == "Summarize":
            fields = config.get("summarize_fields", [])
            group_fields = [f.get("field", "") for f in fields if f.get("action") == "GroupBy"]
            agg_fields = [f"{f.get('action', '?')} of {f.get('field', '?')}" for f in fields if f.get("action") != "GroupBy"]
            lines.append(f"- **[{tid}] Summarize: {tool.annotation or 'Summarize'}**{flag}")
            if group_fields:
                lines.append(f"  - Groups by: {', '.join(group_fields)}")
            if agg_fields:
                lines.append(f"  - Aggregates: {', '.join(agg_fields)}")
            found_logic = True
        elif tool.tool_type in ("AlteryxSelect", "Select"):
            fields = config.get("select_fields", [])
            dropped = [f for f in fields if f.get("selected") == "False"]
            renamed = [f for f in fields if f.get("rename")]
            if dropped or renamed:
                lines.append(f"- **[{tid}] Select: {tool.annotation or 'Select'}**{flag}")
                if dropped:
                    lines.append(f"  - Drops {len(dropped)} field(s)")
                if renamed:
                    lines.append(f"  - Renames {len(renamed)} field(s)")
                found_logic = True

    if not found_logic:
        lines.append("No business logic tools detected.")
    lines.append("")
    return lines


def _conversion_details(workflow, steps, execution_order):
    lines = ["## Conversion Details", ""]
    lines.append("| Tool ID | Type | Annotation | Confidence | Notes |")
    lines.append("|---------|------|------------|------------|-------|")
    for tid in execution_order:
        tool = workflow.tools.get(tid)
        step = steps.get(tid)
        if tool and step:
            notes_str = "; ".join(step.notes) if step.notes else ""
            lines.append(f"| {tid} | {tool.tool_type} | {tool.annotation} | {step.confidence:.0%} | {notes_str} |")
    lines.append("")
    return lines


def _schema_drift_section(workflow, execution_order):
    lines = []
    warnings = []
    for tid in execution_order:
        tool = workflow.tools.get(tid)
        if tool and tool.output_fields and "select_fields" in tool.config:
            diff = detect_schema_drift(tid, tool.output_fields, tool.config["select_fields"])
            if diff.has_drift:
                warnings.append(diff)
    if warnings:
        lines.append("## Schema Drift Warnings")
        lines.append("")
        lines.append("| Tool ID | Added Fields | Removed Fields | Type Changed |")
        lines.append("|---------|-------------|----------------|--------------|")
        for diff in warnings:
            added = ", ".join(diff.added) if diff.added else "-"
            removed = ", ".join(diff.removed) if diff.removed else "-"
            changed = ", ".join(d["field"] for d in diff.type_changed) if diff.type_changed else "-"
            lines.append(f"| {diff.tool_id} | {added} | {removed} | {changed} |")
        lines.append("")
    return lines


def _column_mapping_section(workflow, execution_order):
    lines: list[str] = []
    execution_order_list = list(execution_order)
    warnings = detect_column_mismatches(workflow, execution_order_list)
    if warnings:
        lines.append("## Column Mapping Warnings")
        lines.append("")
        lines.append("| Tool ID | Field | Issue | Detail |")
        lines.append("|---------|-------|-------|--------|")
        for w in warnings:
            lines.append(f"| {w.tool_id} | {w.field} | {w.issue} | {w.detail} |")
        lines.append("")
    return lines


def _review_checklist(workflow, steps, execution_order):
    lines = ["## Manual Review Checklist", ""]
    items = []
    for tid in execution_order:
        tool = workflow.tools[tid]
        step = steps.get(tid)
        if not step:
            continue
        if step.confidence == 0.0:
            items.append(f"- [ ] **Tool {tid} ({tool.tool_type})**: Unsupported — needs manual implementation")
        elif step.confidence < 0.7:
            items.append(f"- [ ] **Tool {tid} ({tool.tool_type})**: Low confidence ({step.confidence:.0%}) — review generated code")
        if tool.plugin.startswith(_BOX_INPUT_PREFIX) or tool.plugin.startswith(_BOX_OUTPUT_PREFIX):
            items.append(f"- [ ] **Tool {tid} ({tool.tool_type})**: Box auth setup required (Databricks Secret scope)")
        for note in step.notes:
            if "network path" in note.lower() or "unc" in note.lower():
                items.append(f"- [ ] **Tool {tid}**: Network/UNC path needs remapping to cloud storage")
                break
        if "TODO" in step.code:
            items.append(f"- [ ] **Tool {tid} ({tool.tool_type})**: Contains TODO comments — review generated code")

    if not items:
        lines.append("No items require manual review.")
    else:
        lines.extend(items)
    lines.append("")
    return lines
