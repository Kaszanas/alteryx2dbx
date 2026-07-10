"""Serverless-safe notebook generator — emits Databricks notebooks using temp views
instead of .cache(), and %run chains for config/utils."""

from __future__ import annotations

import logging
from pathlib import Path

from alteryx2dbx.parser.models import (
    AlteryxTool,
    AlteryxWorkflow,
    GeneratedStep,
)
from alteryx2dbx.parser.schema_drift import detect_schema_drift, SchemaDiff
from alteryx2dbx.parser.column_tracker import detect_column_mismatches
from alteryx2dbx.dag.resolver import resolve_dag
from alteryx2dbx.handlers.registry import get_handler
from alteryx2dbx.fixes import apply_fixes
import alteryx2dbx.handlers  # noqa: F401  — triggers handler registration

from alteryx2dbx.generator.config_notebook import generate_config_notebook
from alteryx2dbx.generator.utils_notebook import generate_utils_notebook
from alteryx2dbx.generator.validator_v2 import generate_validator_v2
from alteryx2dbx.generator.report import generate_report
from alteryx2dbx.manifest import serialize_manifest
from alteryx2dbx.lessons.capture import auto_capture
from alteryx2dbx.lessons.store import LessonStore

logger = logging.getLogger(__name__)

_LOAD_TYPES = {"DbFileInput", "TextInput", "InputData"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData", "Browse"}


def _has_box_tools(workflow: AlteryxWorkflow) -> bool:
    return any(
        t.plugin.startswith("box_input_v")
        or t.plugin.startswith("box_output_v")
        for t in workflow.tools.values()
    )


def generate_notebooks_v2(workflow: AlteryxWorkflow, output_dir: Path) -> dict:
    """Generate the full serverless-safe Databricks notebook bundle for *workflow*.

    Creates ``output_dir/<workflow.name>/`` containing:
    - _config.py
    - _utils.py
    - 01_load_sources.py
    - 02_transformations.py
    - 03_write_outputs.py
    - 04_validate.py
    - 05_orchestrate.py
    - manifest.json
    - conversion_report.md
    """
    wf_dir = output_dir / workflow.name
    wf_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve execution order
    execution_order = resolve_dag(workflow)

    # 2. Build input map: tool_id → list of df variable names that feed into it
    input_map: dict[int, list[str]] = _build_input_map(workflow)

    # 3. Run each tool through its handler
    steps: dict[int, GeneratedStep] = {}
    for tool_id in execution_order:
        tool = workflow.tools[tool_id]
        handler = get_handler(tool)
        input_dfs = input_map.get(tool_id, [])
        step = handler.convert(tool, input_df_names=input_dfs or None)
        steps[tool_id] = step

    # 3b. Apply semantic fixes
    for tool_id in execution_order:
        tool = workflow.tools[tool_id]
        step = steps[tool_id]
        context = {
            "tool_type": tool.tool_type,
            **tool.config,
            "output_fields": [
                {
                    "name": f.name,
                    "type": f.type,
                    "size": f.size,
                    "scale": f.scale,
                }
                for f in tool.output_fields
            ],
        }
        fix_result = apply_fixes(step.code, context)
        step.code = fix_result.code
        for fix in fix_result.applied_fixes:
            step.notes.append(
                f"Fix applied: {fix['fix_id']} — {fix['description']}"
            )

    # 4. Insert temp view hints (instead of .cache()) for fan-out DataFrames
    _insert_temp_view_hints(workflow, steps)

    # 5. Detect network paths and add warnings
    _detect_network_paths(steps)

    # 5b. Schema drift detection
    schema_warnings: list[SchemaDiff] = []
    for tid in execution_order:
        tool = workflow.tools.get(tid)
        if tool and tool.output_fields and "select_fields" in tool.config:
            diff = detect_schema_drift(
                tid, tool.output_fields, tool.config["select_fields"]
            )
            if diff.has_drift:
                schema_warnings.append(diff)
                if tid in steps:
                    steps[tid].notes.append(
                        f"Schema drift: +{len(diff.added)} new, -{len(diff.removed)} missing, ~{len(diff.type_changed)} type changes"
                    )

    # 5c. Column mapping — detect stale references by walking the DAG
    column_warnings = detect_column_mismatches(workflow, execution_order)
    for warning in column_warnings:
        if warning.tool_id in steps:
            steps[warning.tool_id].notes.append(f"STALE_REF: {warning.detail}")

    # 6. Classify steps
    load_ids = [
        tid
        for tid in execution_order
        if workflow.tools[tid].tool_type in _LOAD_TYPES
        or workflow.tools[tid].plugin.startswith("box_input_v")
    ]
    output_ids = [
        tid
        for tid in execution_order
        if workflow.tools[tid].tool_type in _OUTPUT_TYPES
        or workflow.tools[tid].plugin.startswith("box_output_v")
    ]
    transform_ids = [
        tid
        for tid in execution_order
        if tid not in load_ids and tid not in output_ids
    ]

    # 7. Write notebooks
    load_path = wf_dir / "01_load_sources.py"
    transform_path = wf_dir / "02_transformations.py"
    output_path = wf_dir / "03_write_outputs.py"
    orchestrator_path = wf_dir / "05_orchestrate.py"

    _write_notebook(
        load_path,
        f"01 — Load Sources: {workflow.name}",
        load_ids,
        steps,
        workflow.tools,
    )
    _write_notebook(
        transform_path,
        f"02 — Transformations: {workflow.name}",
        transform_ids,
        steps,
        workflow.tools,
    )
    _write_notebook(
        output_path,
        f"03 — Write Outputs: {workflow.name}",
        output_ids,
        steps,
        workflow.tools,
    )
    _write_orchestrator(orchestrator_path, workflow.name)

    # 8. Syntax-validate generated notebooks
    syntax_errors: list[str] = []
    for nb_path in (load_path, transform_path, output_path):
        if not _validate_syntax(nb_path):
            syntax_errors.append(nb_path.name)

    # 9. Config notebook
    has_box = _has_box_tools(workflow)
    generate_config_notebook(workflow, wf_dir, has_box=has_box)

    # 10. Utils notebook
    generate_utils_notebook(wf_dir, has_box=has_box)

    # 11. Validator v2
    generate_validator_v2(wf_dir, workflow, steps, execution_order)

    # 12. Manifest
    serialize_manifest(workflow, wf_dir / "manifest.json")

    # 13. Report
    generate_report(
        wf_dir,
        workflow.tools,
        steps,
        execution_order,
        schema_warnings=schema_warnings,
        column_warnings=column_warnings,
    )

    # 14. Auto-capture lessons
    try:
        captured = auto_capture(workflow.name, steps, execution_order)
        if captured:
            store = LessonStore()
            for lesson in captured:
                store.add(lesson)
    except Exception:
        pass  # lessons are best-effort, never block migration

    # 15. Return stats for batch report
    return {
        "name": workflow.name,
        "tools_total": len(steps),
        "tools_converted": sum(1 for s in steps.values() if s.confidence > 0),
        "avg_confidence": sum(s.confidence for s in steps.values()) / len(steps)
        if steps
        else 0,
        "unsupported_tools": [
            workflow.tools[tid].tool_type
            for tid, s in steps.items()
            if s.confidence == 0
        ],
        "errors": [],
        "syntax_errors": syntax_errors,
    }


# ── Private helpers ──────────────────────────────────────────────────


def _resolve_source_df_name(source_tool_id: int, source_anchor: str) -> str:
    """Derive the df variable name from a connection's source tool and anchor.

    Dual-output tools use anchor names to distinguish their outputs:
    - Filter: True / False
    - Unique: Unique (U) / Duplicates (D)
    - Join: Join (J) / Left (L) / Right (R)
    """
    anchor = source_anchor.lower()
    if anchor in ("true",):
        return f"df_{source_tool_id}_true"
    elif anchor in ("false",):
        return f"df_{source_tool_id}_false"
    elif anchor in ("unique", "u"):
        return f"df_{source_tool_id}_unique"
    elif anchor in ("duplicates", "d"):
        return f"df_{source_tool_id}_duplicates"
    elif anchor in ("join", "j"):
        return f"df_{source_tool_id}_joined"
    elif anchor in ("left", "l"):
        return f"df_{source_tool_id}_left_only"
    elif anchor in ("right", "r"):
        return f"df_{source_tool_id}_right_only"
    else:
        return f"df_{source_tool_id}"


def _build_input_map(workflow: AlteryxWorkflow) -> dict[int, list[str]]:
    """For each tool, compute which df variable names feed into it.

    For Join tools, inputs are ordered [left_df, right_df] based on target_anchor.
    For Filter True/False outputs, the source anchor determines the df name suffix.
    """
    # First pass: collect all inputs with their target anchor info
    raw_inputs: dict[
        int, list[tuple[str, str]]
    ] = {}  # tool_id → [(df_name, target_anchor)]
    for conn in workflow.connections:
        df_name = _resolve_source_df_name(
            conn.source_tool_id, conn.source_anchor
        )
        raw_inputs.setdefault(conn.target_tool_id, []).append(
            (df_name, conn.target_anchor)
        )

    # Second pass: order inputs correctly for dual-input tools
    _LEFT_ANCHORS = {"left", "find", "targets", "f", "#1"}
    _RIGHT_ANCHORS = {"right", "replace", "source", "r", "s", "#2"}

    input_map: dict[int, list[str]] = {}
    for tool_id, inputs in raw_inputs.items():
        tool = workflow.tools.get(tool_id)
        if (
            tool
            and tool.tool_type in ("Join", "FindReplace", "AppendFields")
            and len(inputs) >= 2
        ):
            left_dfs = [
                df for df, anchor in inputs if anchor.lower() in _LEFT_ANCHORS
            ]
            right_dfs = [
                df for df, anchor in inputs if anchor.lower() in _RIGHT_ANCHORS
            ]
            other_dfs = [
                df
                for df, anchor in inputs
                if anchor.lower() not in _LEFT_ANCHORS
                and anchor.lower() not in _RIGHT_ANCHORS
            ]
            input_map[tool_id] = left_dfs + right_dfs + other_dfs
        else:
            input_map[tool_id] = [df for df, _ in inputs]

    return input_map


def _collect_imports(
    tool_ids: list[int], steps: dict[int, GeneratedStep]
) -> set[str]:
    """Merge imports across steps."""
    imports: set[str] = set()
    for tid in tool_ids:
        imports.update(steps[tid].imports)
    return imports


def _write_notebook(
    path: Path,
    title: str,
    tool_ids: list[int],
    steps: dict[int, GeneratedStep],
    tools: dict[int, AlteryxTool] | None = None,
) -> None:
    """Write a Databricks notebook (.py) with a cell per tool."""
    lines = ["# Databricks notebook source", f"# {title}"]

    # Imports cell
    imports = _collect_imports(tool_ids, steps)
    if imports:
        lines.append("")
        lines.append("# COMMAND ----------")
        lines.append("")
        for imp in sorted(imports):
            lines.append(imp)

    # One cell per step
    for tid in tool_ids:
        step = steps[tid]
        lines.append("")
        lines.append("# COMMAND ----------")
        lines.append("")
        # Traceability comments
        if tools and tid in tools:
            tool = tools[tid]
            lines.append(
                f"# Alteryx: Tool {tid} ({tool.tool_type}): {tool.annotation or 'No annotation'}"
            )
            if step.confidence < 1.0:
                lines.append(
                    f"# Confidence: {step.confidence:.0%} — review recommended"
                )
            if step.notes:
                for note in step.notes:
                    lines.append(f"# NOTE: {note}")
        lines.append(step.code)

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_orchestrator(path: Path, workflow_name: str) -> None:
    """Write 05_orchestrate.py that uses %run to chain all notebooks."""
    lines = [
        "# Databricks notebook source",
        f"# 05 — Orchestrate: {workflow_name}",
        "",
        "# COMMAND ----------",
        "",
        "# MAGIC %run ./_config",
        "",
        "# COMMAND ----------",
        "",
        "# MAGIC %run ./_utils",
        "",
        "# COMMAND ----------",
        "",
        "# MAGIC %run ./01_load_sources",
        "",
        "# COMMAND ----------",
        "",
        "# MAGIC %run ./02_transformations",
        "",
        "# COMMAND ----------",
        "",
        "# MAGIC %run ./03_write_outputs",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _insert_temp_view_hints(
    workflow: AlteryxWorkflow, steps: dict[int, GeneratedStep]
) -> None:
    """Append createOrReplaceTempView for DataFrames that fan out to 2+ downstream tools.

    Unlike v1 which used .cache(), this uses temp views for serverless compatibility.
    """
    usage_count: dict[str, int] = {}
    for conn in workflow.connections:
        df_name = _resolve_source_df_name(
            conn.source_tool_id, conn.source_anchor
        )
        usage_count[df_name] = usage_count.get(df_name, 0) + 1

    for df_name, count in usage_count.items():
        if count >= 2:
            # Extract tool_id from df_name (format: df_{id} or df_{id}_{suffix})
            parts = df_name.split("_")
            try:
                tool_id = int(parts[1])
            except (ValueError, IndexError):
                continue
            if tool_id in steps:
                view_name = f"_tmp_{workflow.name}_{tool_id}"
                steps[tool_id].code += (
                    f'\n{df_name}.createOrReplaceTempView("{view_name}")'
                    f"  # Fan-out: used by {count} downstream tools"
                )


def _validate_syntax(path: Path) -> bool:
    """Compile-check a generated .py file and log a warning on syntax errors."""
    code = path.read_text(encoding="utf-8")
    try:
        compile(code, str(path), "exec")
        return True
    except SyntaxError as e:
        logger.warning(
            "Syntax error in %s line %s: %s", path.name, e.lineno, e.msg
        )
        return False


def _detect_network_paths(steps: dict[int, GeneratedStep]) -> None:
    """Flag steps whose generated code references UNC / network paths."""
    for _tid, step in steps.items():
        if "\\\\" in step.code or "\\\\server" in step.code.lower():
            step.notes.append(
                "Network path detected — update to Databricks-accessible location (DBFS, S3, ADLS)"
            )
