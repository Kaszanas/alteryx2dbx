"""Generate config.yml for a converted workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

from alteryx2dbx.parser.models import AlteryxWorkflow


_LOAD_TYPES = {"DbFileInput", "TextInput", "InputData"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData", "Browse"}


def generate_config(workflow: AlteryxWorkflow, output_dir: Path) -> None:
    """Write config.yml with workflow metadata, sources, and outputs."""
    sources = []
    outputs = []

    for tool_id, tool in workflow.tools.items():
        entry = {
            "tool_id": tool_id,
            "type": tool.tool_type,
            "path": tool.config.get("file_path", tool.config.get("File", "")),
            "annotation": tool.annotation,
        }
        if tool.tool_type in _LOAD_TYPES:
            sources.append(entry)
        elif tool.tool_type in _OUTPUT_TYPES:
            outputs.append(entry)

    config = {
        "workflow": {
            "name": workflow.name,
            "version": workflow.version,
        },
        "sources": sources,
        "outputs": outputs,
    }

    with open(output_dir / "config.yml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
