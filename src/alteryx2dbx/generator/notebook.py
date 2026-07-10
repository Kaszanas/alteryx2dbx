"""Main orchestrator — generates Databricks notebook bundle from an AlteryxWorkflow."""

from __future__ import annotations

import logging
from pathlib import Path

from alteryx2dbx.parser.models import AlteryxWorkflow, GeneratedStep
from alteryx2dbx.dag.resolver import resolve_dag
from alteryx2dbx.handlers.registry import get_handler
import alteryx2dbx.handlers  # noqa: F401  — triggers handler registration

from alteryx2dbx.generator.config import generate_config
from alteryx2dbx.generator.validator import generate_validator
from alteryx2dbx.generator.report import generate_report

logger = logging.getLogger(__name__)

_LOAD_TYPES = {"DbFileInput", "TextInput", "InputData"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData", "Browse"}


def generate_notebooks(workflow: AlteryxWorkflow, output_dir: Path) -> dict:
    """Generate the full 4-notebook Databricks bundle for *workflow*.

    Creates ``output_dir/<workflow.name>/`` containing:
    - 01_load_sources.py
    - 02_transformations.py
    - 03_orchestrate.py
    - 04_validate.py
    - config.yml
    - conversion_report.md
    - alteryx_output/   (empty directory for validation artefacts)
    """
    wf_dir = output_dir / workflow.name
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "alteryx_output").mkdir(exist_ok=True)

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

    # 4. Insert fan-out cache hints for shared DataFrames
    _insert_cache_hints(workflow, steps)

    # 5. Detect network paths and add warnings
    _detect_network_paths(steps)

    # 6. Classify steps
    load_ids = [
        tid
        for tid in execution_order
        if workflow.tools[tid].tool_type in _LOAD_TYPES
    ]
    output_ids = [
        tid
        for tid in execution_order
        if workflow.tools[tid].tool_type in _OUTPUT_TYPES
    ]
    transform_ids = [
        tid
        for tid in execution_order
        if tid not in load_ids and tid not in output_ids
    ]

    # 7. Write notebooks
    load_path = wf_dir / "01_load_sources.py"
    transform_path = wf_dir / "02_transformations.py"
    orchestrator_path = wf_dir / "03_orchestrate.py"

    _write_notebook(
        load_path, f"01 — Load Sources: {workflow.name}", load_ids, steps
    )
    _write_notebook(
        transform_path,
        f"02 — Transformations: {workflow.name}",
        transform_ids,
        steps,
    )
    _write_orchestrator(orchestrator_path, workflow.name, output_ids, steps)

    # 8. Syntax-validate generated notebooks
    syntax_errors: list[str] = []
    for nb_path in (load_path, transform_path, orchestrator_path):
        if not _validate_syntax(nb_path):
            syntax_errors.append(nb_path.name)

    # 9. Validator
    last_output_df = (
        steps[output_ids[-1]].output_df if output_ids else "df_result"
    )
    generate_validator(wf_dir, last_output_df)

    # 10. Config
    generate_config(workflow, wf_dir)

    # 11. Report
    generate_report(wf_dir, workflow.tools, steps, execution_order)

    # 12. Return stats for batch report
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
            # Order by target_anchor: left/find/targets first, right/replace/source second
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
        lines.append(step.code)

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_orchestrator(
    path: Path,
    workflow_name: str,
    output_ids: list[int],
    steps: dict[int, GeneratedStep],
) -> None:
    """Write 03_orchestrate.py that runs notebooks 01 & 02, then outputs."""
    lines = [
        "# Databricks notebook source",
        f"# 03 — Orchestrate: {workflow_name}",
        "",
        "# COMMAND ----------",
        "",
        "# Run load sources notebook",
        'dbutils.notebook.run("01_load_sources", timeout_seconds=600)',
        "",
        "# COMMAND ----------",
        "",
        "# Run transformations notebook",
        'dbutils.notebook.run("02_transformations", timeout_seconds=600)',
    ]

    # Imports for output steps
    imports = _collect_imports(output_ids, steps)
    if imports:
        lines.append("")
        lines.append("# COMMAND ----------")
        lines.append("")
        for imp in sorted(imports):
            lines.append(imp)

    # Output cells
    for tid in output_ids:
        step = steps[tid]
        lines.append("")
        lines.append("# COMMAND ----------")
        lines.append("")
        lines.append(step.code)

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _insert_cache_hints(
    workflow: AlteryxWorkflow, steps: dict[int, GeneratedStep]
) -> None:
    """Append .cache() to DataFrames that fan out to 2+ downstream tools."""
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
                steps[
                    tool_id
                ].code += f"\n{df_name}.cache()  # Fan-out: used by {count} downstream tools"


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
