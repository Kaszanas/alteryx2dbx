from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class AlteryxField:
    name: str
    type: str
    size: int | None = None
    scale: int | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "scale": self.scale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AlteryxField:
        return cls(
            name=d["name"],
            type=d["type"],
            size=d.get("size"),
            scale=d.get("scale"),
        )


@dataclass
class AlteryxConnection:
    source_tool_id: int
    source_anchor: str
    target_tool_id: int
    target_anchor: str

    def to_dict(self) -> dict:
        return {
            "source_tool_id": self.source_tool_id,
            "source_anchor": self.source_anchor,
            "target_tool_id": self.target_tool_id,
            "target_anchor": self.target_anchor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AlteryxConnection:
        return cls(
            source_tool_id=d["source_tool_id"],
            source_anchor=d["source_anchor"],
            target_tool_id=d["target_tool_id"],
            target_anchor=d["target_anchor"],
        )


@dataclass
class AlteryxTool:
    tool_id: int
    plugin: str
    tool_type: str
    config: dict
    annotation: str = ""
    input_fields: list[AlteryxField] = field(default_factory=list)
    output_fields: list[AlteryxField] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tool_id": self.tool_id,
            "plugin": self.plugin,
            "tool_type": self.tool_type,
            "config": self.config,
            "annotation": self.annotation,
            "input_fields": [f.to_dict() for f in self.input_fields],
            "output_fields": [f.to_dict() for f in self.output_fields],
        }

    @classmethod
    def from_dict(cls, d: dict) -> AlteryxTool:
        return cls(
            tool_id=d["tool_id"],
            plugin=d["plugin"],
            tool_type=d["tool_type"],
            config=d["config"],
            annotation=d.get("annotation", ""),
            input_fields=[
                AlteryxField.from_dict(f) for f in d.get("input_fields", [])
            ],
            output_fields=[
                AlteryxField.from_dict(f) for f in d.get("output_fields", [])
            ],
        )


@dataclass
class AlteryxWorkflow:
    name: str
    version: str
    tools: dict[int, AlteryxTool] = field(default_factory=dict)
    connections: list[AlteryxConnection] = field(default_factory=list)
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "tools": {
                str(tid): tool.to_dict() for tid, tool in self.tools.items()
            },
            "connections": [c.to_dict() for c in self.connections],
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AlteryxWorkflow:
        return cls(
            name=d["name"],
            version=d["version"],
            tools={
                int(tid): AlteryxTool.from_dict(t)
                for tid, t in d.get("tools", {}).items()
            },
            connections=[
                AlteryxConnection.from_dict(c) for c in d.get("connections", [])
            ],
            properties=d.get("properties", {}),
        )


@dataclass
class GeneratedStep:
    step_name: str
    code: str
    imports: set[str] = field(default_factory=set)
    input_dfs: list[str] = field(default_factory=list)
    output_df: str = ""
    notes: list[str] = field(default_factory=list)
    confidence: float = 1.0
