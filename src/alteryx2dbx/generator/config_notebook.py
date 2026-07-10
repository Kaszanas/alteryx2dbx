"""Generate a _config.py Databricks notebook with widgets for parameterization."""

from __future__ import annotations

from pathlib import Path

from alteryx2dbx.parser.models import AlteryxWorkflow, AlteryxTool

_LOAD_TYPES = {"DbFileInput", "TextInput", "InputData", "DynamicInput"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData"}

_CELL_SEP = "\n# COMMAND ----------\n"


def _is_unc_path(path: str) -> bool:
    """Return True if path looks like a UNC/network path."""
    return path.startswith("\\\\") or path.startswith("//")


def _tool_path(tool: AlteryxTool) -> str:
    """Extract the file path from a tool's config."""
    return tool.config.get("file_path", tool.config.get("File", ""))


def _build_dict_entries(
    tools: dict[int, AlteryxTool], type_set: set[str]
) -> list[str]:
    """Build Python dict literal entries for matching tools, with UNC warnings."""
    entries: list[str] = []
    for tool_id, tool in sorted(tools.items()):
        if tool.tool_type not in type_set:
            continue
        path = _tool_path(tool)
        annotation = tool.annotation or ""
        line = f'    {tool_id}: {{"path": {path!r}, "annotation": {annotation!r}}},'
        if _is_unc_path(path):
            line += "  # TODO: UNC/network path — migrate to cloud storage"
        entries.append(line)
    return entries


def generate_config_notebook(
    workflow: AlteryxWorkflow, output_dir: Path, *, has_box: bool = False
) -> None:
    """Write a _config.py Databricks notebook with widget-based parameterization."""
    cells: list[str] = []

    # Cell 1: Header
    cells.append("# Databricks notebook source")

    # Cell 2: Widget declarations
    cells.append(
        "# Widget parameters\n"
        'dbutils.widgets.text("catalog", "dev", "Catalog")\n'
        'dbutils.widgets.text("schema", "default", "Schema")\n'
        'dbutils.widgets.text("env", "dev", "Environment")'
    )

    # Cell 3: Widget getters + workflow constants
    cells.append(
        "# Configuration values\n"
        'CATALOG = dbutils.widgets.get("catalog")\n'
        'SCHEMA = dbutils.widgets.get("schema")\n'
        'ENV = dbutils.widgets.get("env")\n'
        "\n"
        f'WORKFLOW_NAME = "{workflow.name}"\n'
        f'WORKFLOW_VERSION = "{workflow.version}"'
    )

    # Cell 4: SOURCES dict
    source_entries = _build_dict_entries(workflow.tools, _LOAD_TYPES)
    sources_body = (
        "\n".join(source_entries)
        if source_entries
        else "    # No source tools found"
    )
    cells.append(f"# Source data references\nSOURCES = {{\n{sources_body}\n}}")

    # Cell 5: OUTPUTS dict
    output_entries = _build_dict_entries(workflow.tools, _OUTPUT_TYPES)
    outputs_body = (
        "\n".join(output_entries)
        if output_entries
        else "    # No output tools found"
    )
    cells.append(f"# Output data references\nOUTPUTS = {{\n{outputs_body}\n}}")

    if has_box:
        cells.append(
            "# Box.com configuration\n"
            'dbutils.widgets.text("box_secret_scope", "box", "Databricks Secret scope for Box JWT credentials")\n'
            'BOX_SECRET_SCOPE = dbutils.widgets.get("box_secret_scope")'
        )

    content = _CELL_SEP.join(cells) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_config.py").write_text(content, encoding="utf-8")
