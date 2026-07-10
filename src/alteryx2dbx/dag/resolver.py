from __future__ import annotations

import networkx as nx

from alteryx2dbx.parser.models import AlteryxWorkflow


class CyclicWorkflowError(Exception):
    pass


def resolve_dag(workflow: AlteryxWorkflow) -> list[int]:
    """Return tool IDs in topological order based on workflow connections."""
    if not workflow.tools:
        return []

    g = nx.DiGraph()
    for tool_id in workflow.tools:
        g.add_node(tool_id)
    for conn in workflow.connections:
        if (
            conn.source_tool_id in workflow.tools
            and conn.target_tool_id in workflow.tools
        ):
            g.add_edge(conn.source_tool_id, conn.target_tool_id)

    if not nx.is_directed_acyclic_graph(g):
        cycles = list(nx.simple_cycles(g))
        raise CyclicWorkflowError(f"Workflow contains cycles: {cycles}")

    return list(nx.topological_sort(g))
