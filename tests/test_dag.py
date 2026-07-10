import pytest
from alteryx2dbx.parser.models import (
    AlteryxWorkflow,
    AlteryxTool,
    AlteryxConnection,
)
from alteryx2dbx.dag.resolver import resolve_dag, CyclicWorkflowError


def _make_workflow(tools_ids, connections):
    tools = {tid: AlteryxTool(tool_id=tid, plugin="test", tool_type="Test", config={}) for tid in tools_ids}
    conns = [AlteryxConnection(source_tool_id=s, source_anchor="Output", target_tool_id=t, target_anchor="Input") for s, t in connections]
    return AlteryxWorkflow(name="test", version="1.0", tools=tools, connections=conns)


def test_resolve_linear_chain():
    wf = _make_workflow([1, 2, 3], [(1, 2), (2, 3)])
    order = resolve_dag(wf)
    assert order == [1, 2, 3]


def test_resolve_returns_all_tools():
    wf = _make_workflow([1, 2, 3], [(1, 2), (2, 3)])
    order = resolve_dag(wf)
    assert set(order) == {1, 2, 3}


def test_resolve_respects_dependencies():
    wf = _make_workflow([1, 2, 3], [(1, 2), (2, 3)])
    order = resolve_dag(wf)
    assert order.index(1) < order.index(2)
    assert order.index(2) < order.index(3)


def test_resolve_diamond():
    # 1 → 2, 1 → 3, 2 → 4, 3 → 4
    wf = _make_workflow([1, 2, 3, 4], [(1, 2), (1, 3), (2, 4), (3, 4)])
    order = resolve_dag(wf)
    assert order.index(1) < order.index(2)
    assert order.index(1) < order.index(3)
    assert order.index(2) < order.index(4)
    assert order.index(3) < order.index(4)


def test_resolve_empty_workflow():
    wf = AlteryxWorkflow(name="empty", version="1.0")
    order = resolve_dag(wf)
    assert order == []


def test_resolve_single_tool():
    wf = _make_workflow([1], [])
    order = resolve_dag(wf)
    assert order == [1]


def test_resolve_cycle_raises():
    wf = _make_workflow([1, 2], [(1, 2), (2, 1)])
    with pytest.raises(CyclicWorkflowError):
        resolve_dag(wf)
