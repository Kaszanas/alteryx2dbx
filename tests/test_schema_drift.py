"""Tests for schema drift detection."""

from __future__ import annotations


from alteryx2dbx.parser.models import AlteryxField, AlteryxTool, GeneratedStep
from alteryx2dbx.parser.schema_drift import SchemaDiff, detect_schema_drift


# ── Helpers ──────────────────────────────────────────────────────────


def _fields(*names_and_types: tuple[str, str]) -> list[AlteryxField]:
    return [AlteryxField(name=n, type=t) for n, t in names_and_types]


def _select(*entries: tuple[str, str, str]) -> list[dict]:
    """Build select_fields list. Each entry = (field, type, selected)."""
    return [{"field": f, "type": t, "selected": s} for f, t, s in entries]


# ── Unit tests ───────────────────────────────────────────────────────


class TestDetectSchemaDrift:
    def test_matching_schemas_no_drift(self):
        output = _fields(("id", "Int32"), ("name", "V_WString"))
        select = _select(("id", "Int32", "True"), ("name", "V_WString", "True"))
        diff = detect_schema_drift(1, output, select)
        assert not diff.has_drift
        assert diff.added == []
        assert diff.removed == []
        assert diff.type_changed == []

    def test_added_fields(self):
        output = _fields(("id", "Int32"))
        select = _select(
            ("id", "Int32", "True"), ("ghost_field", "V_WString", "True")
        )
        diff = detect_schema_drift(1, output, select)
        assert diff.has_drift
        assert diff.added == ["ghost_field"]
        assert diff.removed == []

    def test_removed_fields(self):
        output = _fields(
            ("id", "Int32"), ("name", "V_WString"), ("extra", "Bool")
        )
        select = _select(("id", "Int32", "True"))
        diff = detect_schema_drift(1, output, select)
        assert diff.has_drift
        assert sorted(diff.removed) == ["extra", "name"]
        assert diff.added == []

    def test_type_changes(self):
        output = _fields(("id", "Int32"), ("amount", "Double"))
        select = _select(("id", "Int64", "True"), ("amount", "Double", "True"))
        diff = detect_schema_drift(1, output, select)
        assert diff.has_drift
        assert diff.type_changed == [
            {"field": "id", "from": "Int32", "to": "Int64"}
        ]

    def test_mixed_drift(self):
        output = _fields(("id", "Int32"), ("old_col", "V_WString"))
        select = _select(
            ("id", "Int64", "True"),
            ("new_col", "Bool", "True"),
        )
        diff = detect_schema_drift(5, output, select)
        assert diff.has_drift
        assert diff.tool_id == 5
        assert diff.added == ["new_col"]
        assert diff.removed == ["old_col"]
        assert diff.type_changed == [
            {"field": "id", "from": "Int32", "to": "Int64"}
        ]

    def test_unselected_fields_excluded(self):
        output = _fields(("id", "Int32"), ("name", "V_WString"))
        select = _select(
            ("id", "Int32", "True"),
            ("name", "V_WString", "True"),
            ("dropped", "Bool", "False"),
        )
        diff = detect_schema_drift(1, output, select)
        assert not diff.has_drift
        assert "dropped" not in diff.added

    def test_has_drift_property_false(self):
        diff = SchemaDiff(tool_id=1, added=[], removed=[], type_changed=[])
        assert not diff.has_drift

    def test_has_drift_property_true_added(self):
        diff = SchemaDiff(tool_id=1, added=["x"], removed=[], type_changed=[])
        assert diff.has_drift

    def test_has_drift_property_true_removed(self):
        diff = SchemaDiff(tool_id=1, added=[], removed=["x"], type_changed=[])
        assert diff.has_drift

    def test_has_drift_property_true_type_changed(self):
        diff = SchemaDiff(
            tool_id=1,
            added=[],
            removed=[],
            type_changed=[{"field": "x", "from": "A", "to": "B"}],
        )
        assert diff.has_drift

    def test_empty_select_fields(self):
        output = _fields(("id", "Int32"))
        diff = detect_schema_drift(1, output, [])
        assert diff.has_drift
        assert diff.removed == ["id"]

    def test_empty_output_fields(self):
        select = _select(("id", "Int32", "True"))
        diff = detect_schema_drift(1, [], select)
        assert diff.has_drift
        assert diff.added == ["id"]

    def test_type_change_only_when_type_present(self):
        """No type change reported when select field has empty type."""
        output = _fields(("id", "Int32"))
        select = [{"field": "id", "type": "", "selected": "True"}]
        diff = detect_schema_drift(1, output, select)
        assert diff.type_changed == []


class TestSchemaDriftIntegration:
    def test_drift_notes_appended_to_step(self):
        """Simulate what notebook_v2 does: detect drift and append notes."""
        tool = AlteryxTool(
            tool_id=10,
            plugin="AlteryxBasePluginsEngine.dll",
            tool_type="Select",
            config={
                "select_fields": _select(
                    ("id", "Int64", "True"),
                    ("ghost", "V_WString", "True"),
                ),
            },
            output_fields=_fields(("id", "Int32"), ("name", "V_WString")),
        )
        step = GeneratedStep(step_name="select_10", code="# placeholder")

        diff = detect_schema_drift(
            tool.tool_id, tool.output_fields, tool.config["select_fields"]
        )
        assert diff.has_drift
        if diff.has_drift:
            step.notes.append(
                f"Schema drift: +{len(diff.added)} new, -{len(diff.removed)} missing, ~{len(diff.type_changed)} type changes"
            )

        assert len(step.notes) == 1
        assert "Schema drift" in step.notes[0]
        assert "+1 new" in step.notes[0]
        assert "-1 missing" in step.notes[0]
        assert "~1 type changes" in step.notes[0]
