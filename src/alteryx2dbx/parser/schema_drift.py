"""Schema drift detection — compares RecordInfo metadata against Select tool configs."""
from __future__ import annotations

from dataclasses import dataclass, field

from alteryx2dbx.parser.models import AlteryxField


@dataclass
class SchemaDiff:
    tool_id: int
    added: list[str] = field(default_factory=list)       # fields in select config but not in RecordInfo
    removed: list[str] = field(default_factory=list)      # fields in RecordInfo but not in select config
    type_changed: list[dict] = field(default_factory=list)  # {"field": str, "from": str, "to": str}

    @property
    def has_drift(self) -> bool:
        return bool(self.added or self.removed or self.type_changed)


def detect_schema_drift(
    tool_id: int,
    output_fields: list[AlteryxField],
    select_fields: list[dict],
) -> SchemaDiff:
    """Compare RecordInfo output_fields against Select tool config fields.

    output_fields: from RecordInfo (ODBC truth)
    select_fields: from Select tool config (potentially stale)
    """
    output_names = {f.name for f in output_fields}

    # Only consider selected fields (selected != "False")
    selected = {
        sf["field"] for sf in select_fields
        if sf.get("selected", "True") != "False" and sf.get("field")
    }

    # Fields referenced in Select but not in upstream RecordInfo = potentially stale
    added = sorted(selected - output_names)

    # Fields in RecordInfo but not selected = potentially missing
    removed = sorted(output_names - selected)

    # Type changes
    type_changed = []
    output_type_map = {f.name: f.type for f in output_fields}
    for sf in select_fields:
        name = sf.get("field", "")
        sf_type = sf.get("type", "")
        if name in output_type_map and sf_type and sf_type != output_type_map[name]:
            type_changed.append({
                "field": name,
                "from": output_type_map[name],
                "to": sf_type,
            })

    return SchemaDiff(
        tool_id=tool_id,
        added=added,
        removed=removed,
        type_changed=type_changed,
    )
