from dataclasses import dataclass, asdict
import json
import uuid

CATEGORIES = [
    "behavioral_difference",
    "tool_mapping",
    "expression_syntax",
    "data_loading",
    "validation",
]


@dataclass
class Lesson:
    id: str
    date: str
    workflow: str
    symptom: str
    root_cause: str
    fix: str
    category: str
    promoted: bool = False
    auto_captured: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(
            **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, line: str) -> "Lesson":
        return cls.from_dict(json.loads(line))

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())[:12]
