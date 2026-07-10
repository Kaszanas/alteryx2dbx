import json
from pathlib import Path

from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxField,
    AlteryxTool,
    AlteryxWorkflow,
)
from alteryx2dbx.manifest import load_manifest, serialize_manifest


def _sample_workflow() -> AlteryxWorkflow:
    """Build a sample workflow with 2 tools, 1 connection, and fields."""
    field_a = AlteryxField(name="Revenue", type="Double", size=8, scale=2)
    field_b = AlteryxField(name="Name", type="V_WString", size=256, scale=None)

    tool_1 = AlteryxTool(
        tool_id=1,
        plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
        tool_type="Input",
        config={
            "filename": "data.csv",
            "_raw_xml": "<Configuration><Filename>data.csv</Filename></Configuration>",
        },
        annotation="Load data",
        input_fields=[],
        output_fields=[field_a, field_b],
    )
    tool_2 = AlteryxTool(
        tool_id=2,
        plugin="AlteryxBasePluginsGui.Filter.Filter",
        tool_type="Filter",
        config={"expression": "[Revenue] > 100"},
        annotation="Filter high revenue",
        input_fields=[field_a, field_b],
        output_fields=[field_a, field_b],
    )

    conn = AlteryxConnection(
        source_tool_id=1,
        source_anchor="Output",
        target_tool_id=2,
        target_anchor="Input",
    )

    return AlteryxWorkflow(
        name="test_workflow",
        version="11.7",
        tools={1: tool_1, 2: tool_2},
        connections=[conn],
        properties={"author": "test", "comment": "demo workflow"},
    )


def test_field_roundtrip():
    f = AlteryxField(name="Revenue", type="Double", size=8, scale=2)
    assert AlteryxField.from_dict(f.to_dict()) == f


def test_field_roundtrip_none_optionals():
    f = AlteryxField(name="Name", type="V_WString")
    d = f.to_dict()
    assert d["size"] is None
    assert d["scale"] is None
    assert AlteryxField.from_dict(d) == f


def test_connection_roundtrip():
    c = AlteryxConnection(
        source_tool_id=1,
        source_anchor="Output",
        target_tool_id=2,
        target_anchor="Input",
    )
    assert AlteryxConnection.from_dict(c.to_dict()) == c


def test_tool_roundtrip():
    field = AlteryxField(name="X", type="Int32", size=4, scale=None)
    t = AlteryxTool(
        tool_id=5,
        plugin="SomePlugin",
        tool_type="Select",
        config={"keep": ["X"]},
        annotation="note",
        input_fields=[field],
        output_fields=[field],
    )
    assert AlteryxTool.from_dict(t.to_dict()) == t


def test_tool_config_raw_xml_survives():
    raw = "<Configuration><Filename>data.csv</Filename></Configuration>"
    t = AlteryxTool(
        tool_id=1,
        plugin="P",
        tool_type="T",
        config={"_raw_xml": raw},
    )
    restored = AlteryxTool.from_dict(t.to_dict())
    assert restored.config["_raw_xml"] == raw


def test_serialize_roundtrip(tmp_path: Path):
    wf = _sample_workflow()
    manifest_path = tmp_path / "manifest.json"

    serialize_manifest(wf, manifest_path)

    # Verify file is valid JSON
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Tool keys in JSON must be strings
    assert all(isinstance(k, str) for k in raw["tools"].keys())

    loaded = load_manifest(manifest_path)

    assert loaded.name == wf.name
    assert loaded.version == wf.version
    assert loaded.properties == wf.properties
    assert len(loaded.tools) == 2
    assert len(loaded.connections) == 1

    # Tool IDs are ints after loading
    assert set(loaded.tools.keys()) == {1, 2}

    # Deep equality
    assert loaded == wf


def test_serialize_empty_workflow(tmp_path: Path):
    wf = AlteryxWorkflow(name="empty", version="2024.1")
    manifest_path = tmp_path / "empty.json"

    serialize_manifest(wf, manifest_path)
    loaded = load_manifest(manifest_path)

    assert loaded == wf
    assert loaded.tools == {}
    assert loaded.connections == []
    assert loaded.properties == {}
