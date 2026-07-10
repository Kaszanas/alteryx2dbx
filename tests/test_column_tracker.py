"""Tests for column tracking — stale reference detection across the DAG."""

from __future__ import annotations


from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxField,
    AlteryxTool,
    AlteryxWorkflow,
    GeneratedStep,
)
from alteryx2dbx.parser.column_tracker import detect_column_mismatches


# ── Helpers ──────────────────────────────────────────────────────────


def _field(name: str, type_: str = "V_WString") -> AlteryxField:
    return AlteryxField(name=name, type=type_)


def _tool(
    tool_id: int,
    tool_type: str = "Select",
    output_fields: list[AlteryxField] | None = None,
    config: dict | None = None,
) -> AlteryxTool:
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.dll",
        tool_type=tool_type,
        config=config or {},
        output_fields=output_fields or [],
    )


def _conn(src: int, tgt: int) -> AlteryxConnection:
    return AlteryxConnection(
        source_tool_id=src,
        source_anchor="Output",
        target_tool_id=tgt,
        target_anchor="Input",
    )


def _workflow(
    tools: list[AlteryxTool],
    connections: list[AlteryxConnection] | None = None,
) -> AlteryxWorkflow:
    return AlteryxWorkflow(
        name="test_wf",
        version="1.0",
        tools={t.tool_id: t for t in tools},
        connections=connections or [],
    )


# ── Unit tests ───────────────────────────────────────────────────────


class TestDetectColumnMismatches:
    def test_matching_columns_no_warnings(self):
        """Select references fields that exist upstream — no warnings."""
        upstream = _tool(
            1, "InputData", output_fields=[_field("id"), _field("name")]
        )
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "name", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_stale_ref_detected(self):
        """Field in Select config doesn't exist in upstream output."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "ghost_field", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert len(warnings) == 1
        assert warnings[0].tool_id == 2
        assert warnings[0].field == "ghost_field"
        assert warnings[0].issue == "STALE_REF"

    def test_wildcard_fields_skipped(self):
        """Fields starting with * should be ignored."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "*Unknown", "selected": "True"},
                    {"field": "id", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_unselected_fields_skipped(self):
        """Fields with selected=False should not trigger warnings."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "dropped_field", "selected": "False"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_no_upstream_data_no_warnings(self):
        """Tool with no upstream connections should produce no warnings."""
        select = _tool(
            1,
            "Select",
            config={
                "select_fields": [
                    {"field": "ghost", "selected": "True"},
                ],
            },
        )
        wf = _workflow([select])
        warnings = detect_column_mismatches(wf, [1])
        assert warnings == []

    def test_no_upstream_output_fields_no_warnings(self):
        """Upstream tool exists but has no output_fields — skip comparison."""
        upstream = _tool(1, "InputData", output_fields=[])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "ghost", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_multiple_upstream_tools_union(self):
        """Columns from multiple upstream tools are unioned."""
        upstream_a = _tool(
            1, "InputData", output_fields=[_field("id"), _field("name")]
        )
        upstream_b = _tool(
            2, "InputData", output_fields=[_field("amount"), _field("date")]
        )
        select = _tool(
            3,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "amount", "selected": "True"},
                    {"field": "missing_col", "selected": "True"},
                ],
            },
        )
        wf = _workflow(
            [upstream_a, upstream_b, select],
            [_conn(1, 3), _conn(2, 3)],
        )
        warnings = detect_column_mismatches(wf, [1, 2, 3])
        assert len(warnings) == 1
        assert warnings[0].field == "missing_col"

    def test_no_select_fields_no_warnings(self):
        """Tool with no select_fields in config should be skipped."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        formula = _tool(2, "Formula", config={"formula_fields": []})
        wf = _workflow([upstream, formula], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_empty_field_name_skipped(self):
        """Select entries with empty field name are skipped."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "", "selected": "True"},
                    {"field": "id", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert warnings == []

    def test_multiple_stale_refs(self):
        """Multiple stale references in same Select tool."""
        upstream = _tool(1, "InputData", output_fields=[_field("id")])
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "ghost_a", "selected": "True"},
                    {"field": "ghost_b", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])
        warnings = detect_column_mismatches(wf, [1, 2])
        assert len(warnings) == 2
        assert {w.field for w in warnings} == {"ghost_a", "ghost_b"}


class TestColumnTrackerIntegration:
    def test_stale_ref_notes_in_step(self):
        """Verify STALE_REF notes appear in step.notes (simulates notebook_v2 integration)."""
        upstream = _tool(
            1, "InputData", output_fields=[_field("id"), _field("name")]
        )
        select = _tool(
            2,
            "Select",
            config={
                "select_fields": [
                    {"field": "id", "selected": "True"},
                    {"field": "removed_col", "selected": "True"},
                ],
            },
        )
        wf = _workflow([upstream, select], [_conn(1, 2)])

        steps = {
            1: GeneratedStep(step_name="input_1", code="# input"),
            2: GeneratedStep(step_name="select_2", code="# select"),
        }

        warnings = detect_column_mismatches(wf, [1, 2])
        for warning in warnings:
            if warning.tool_id in steps:
                steps[warning.tool_id].notes.append(
                    f"STALE_REF: {warning.detail}"
                )

        assert len(steps[2].notes) == 1
        assert "STALE_REF" in steps[2].notes[0]
        assert "removed_col" in steps[2].notes[0]
        assert steps[1].notes == []
