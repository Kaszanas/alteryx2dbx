"""Generate Mermaid.js flowchart from an AlteryxWorkflow."""

from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxWorkflow
from alteryx2dbx.handlers.registry import get_handler
import alteryx2dbx.handlers  # noqa: F401

_INPUT_TYPES = {"DbFileInput", "TextInput", "InputData", "DynamicInput"}
_OUTPUT_TYPES = {"DbFileOutput", "OutputData", "Browse"}

_LABELED_ANCHORS = {
    "True",
    "False",
    "Join",
    "Left",
    "Right",
    "Unique",
    "Duplicates",
    "J",
    "L",
    "R",
    "U",
    "D",
}


def _classify_tool(tool) -> str:
    if tool.tool_type in _INPUT_TYPES or tool.plugin.startswith("box_input_v"):
        return "input"
    if tool.tool_type in _OUTPUT_TYPES or tool.plugin.startswith(
        "box_output_v"
    ):
        return "output"
    handler = get_handler(tool)
    if type(handler).__name__ == "UnsupportedHandler":
        return "unsupported"
    return "transform"


def _escape_mermaid(text: str) -> str:
    return text.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")


def generate_mermaid(workflow: AlteryxWorkflow) -> str:
    lines = ["```mermaid", "flowchart TD"]

    for tool_id, tool in sorted(workflow.tools.items()):
        label = _escape_mermaid(tool.annotation or tool.tool_type)
        node_label = f"[{tool_id}] {tool.tool_type}: {label}"
        lines.append(f'    node_{tool_id}["{_escape_mermaid(node_label)}"]')

    lines.append("")

    for conn in workflow.connections:
        src = f"node_{conn.source_tool_id}"
        dst = f"node_{conn.target_tool_id}"
        if conn.source_anchor in _LABELED_ANCHORS:
            lines.append(f"    {src} -->|{conn.source_anchor}| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")

    lines.append("")

    lines.append("    %% Color coding")
    for tool_id, tool in sorted(workflow.tools.items()):
        category = _classify_tool(tool)
        if category == "input":
            lines.append(
                f"    style node_{tool_id} fill:#d4edda,stroke:#28a745"
            )
        elif category == "output":
            lines.append(
                f"    style node_{tool_id} fill:#cce5ff,stroke:#007bff"
            )
        elif category == "unsupported":
            lines.append(
                f"    style node_{tool_id} fill:#f8d7da,stroke:#dc3545"
            )

    lines.append("```")
    return "\n".join(lines)
