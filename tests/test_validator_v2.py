"""Tests for validator_v2 — smart validation generator with auto-detected join keys."""

from __future__ import annotations

from pathlib import Path


from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxField,
    AlteryxTool,
    AlteryxWorkflow,
    GeneratedStep,
)
from alteryx2dbx.generator.validator_v2 import (
    detect_join_keys,
    generate_validator_v2,
)


def _make_workflow(
    tools: dict[int, AlteryxTool] | None = None,
    connections: list[AlteryxConnection] | None = None,
) -> AlteryxWorkflow:
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools=tools or {},
        connections=connections or [],
    )


# ── detect_join_keys ─────────────────────────────────────────────────


class TestDetectJoinKeys:
    def test_detect_join_keys_from_join_tool(self):
        """Workflow with a Join tool → finds the join key from config."""
        join_tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.Join.Join",
            tool_type="Join",
            config={
                "join_fields": [
                    {"left": "customer_id", "right": "cust_id"},
                    {"left": "order_date", "right": "date"},
                ],
            },
        )
        wf = _make_workflow(tools={1: join_tool})
        keys = detect_join_keys(wf)
        assert "customer_id" in keys
        assert "order_date" in keys

    def test_detect_keys_from_unique_tool(self):
        """Unique tool config provides key candidates."""
        unique_tool = AlteryxTool(
            tool_id=2,
            plugin="AlteryxBasePluginsGui.Unique.Unique",
            tool_type="Unique",
            config={"unique_fields": ["account_id", "region"]},
        )
        wf = _make_workflow(tools={2: unique_tool})
        keys = detect_join_keys(wf)
        assert "account_id" in keys
        assert "region" in keys

    def test_detect_keys_heuristic(self):
        """No join/unique tools; output field named order_id detected via heuristic."""
        tool = AlteryxTool(
            tool_id=3,
            plugin="AlteryxBasePluginsGui.Select.Select",
            tool_type="Select",
            config={},
            output_fields=[
                AlteryxField(name="order_id", type="Int64"),
                AlteryxField(name="amount", type="Double"),
                AlteryxField(name="status_code", type="String"),
                AlteryxField(name="primary_key", type="Int64"),
            ],
        )
        wf = _make_workflow(tools={3: tool})
        keys = detect_join_keys(wf)
        assert "order_id" in keys
        assert "status_code" in keys
        assert "primary_key" in keys
        # 'amount' should NOT be detected
        assert "amount" not in keys

    def test_detect_keys_deduplication(self):
        """Duplicate key names across tools are deduplicated."""
        join_tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.Join.Join",
            tool_type="Join",
            config={"join_fields": [{"left": "id", "right": "id"}]},
        )
        unique_tool = AlteryxTool(
            tool_id=2,
            plugin="AlteryxBasePluginsGui.Unique.Unique",
            tool_type="Unique",
            config={"unique_fields": ["id"]},
        )
        wf = _make_workflow(tools={1: join_tool, 2: unique_tool})
        keys = detect_join_keys(wf)
        assert keys.count("id") == 1

    def test_detect_keys_empty_workflow(self):
        """Empty workflow returns empty list."""
        wf = _make_workflow()
        keys = detect_join_keys(wf)
        assert keys == []

    def test_join_tool_priority_over_heuristic(self):
        """Join tool keys come before heuristic keys, with no duplicates."""
        join_tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.Join.Join",
            tool_type="Join",
            config={
                "join_fields": [{"left": "customer_id", "right": "cust_id"}]
            },
        )
        select_tool = AlteryxTool(
            tool_id=2,
            plugin="AlteryxBasePluginsGui.Select.Select",
            tool_type="Select",
            config={},
            output_fields=[
                AlteryxField(name="customer_id", type="Int64"),
                AlteryxField(name="order_id", type="Int64"),
            ],
        )
        wf = _make_workflow(tools={1: join_tool, 2: select_tool})
        keys = detect_join_keys(wf)
        # customer_id from join comes first, order_id from heuristic
        assert keys[0] == "customer_id"
        assert "order_id" in keys
        assert keys.count("customer_id") == 1


# ── generate_validator_v2 ────────────────────────────────────────────


class TestGenerateValidatorV2:
    def test_generates_validation_notebook(self, tmp_path: Path):
        """File exists and contains row count, schema, datacompy, and detected key."""
        join_tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.Join.Join",
            tool_type="Join",
            config={
                "join_fields": [{"left": "account_id", "right": "acct_id"}]
            },
            output_fields=[
                AlteryxField(name="account_id", type="Int64"),
                AlteryxField(name="balance", type="Double"),
            ],
        )
        output_tool = AlteryxTool(
            tool_id=2,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
        )
        wf = _make_workflow(
            tools={1: join_tool, 2: output_tool},
            connections=[
                AlteryxConnection(
                    source_tool_id=1,
                    source_anchor="Join",
                    target_tool_id=2,
                    target_anchor="Input",
                )
            ],
        )
        steps = {
            1: GeneratedStep(
                step_name="join", code="df_1 = ...", output_df="df_1"
            ),
            2: GeneratedStep(
                step_name="output", code="df_2 = df_1", output_df="df_2"
            ),
        }

        generate_validator_v2(tmp_path, wf, steps, [1, 2])

        out_file = tmp_path / "04_validate.py"
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")

        # Databricks notebook marker
        assert "# Databricks notebook source" in content
        # Section markers
        assert "Row Count" in content
        assert "Schema" in content
        assert "datacompy" in content.lower() or "DataComPy" in content
        # Detected key used (not TODO placeholder)
        assert "account_id" in content

    def test_fallback_to_todo_key(self, tmp_path: Path):
        """When no keys detected, falls back to TODO_primary_key."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.Select.Select",
            tool_type="Select",
            config={},
            output_fields=[
                AlteryxField(name="name", type="String"),
                AlteryxField(name="amount", type="Double"),
            ],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="select", code="df_1 = ...", output_df="df_1"
            ),
        }

        generate_validator_v2(tmp_path, wf, steps, [1])

        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")
        assert "TODO_primary_key" in content

    def test_notebook_has_all_sections(self, tmp_path: Path):
        """Verify all 8 validation sections are present."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[
                AlteryxField(name="order_id", type="Int64"),
                AlteryxField(name="total", type="Double"),
            ],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            ),
        }

        generate_validator_v2(tmp_path, wf, steps, [1])

        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        # All original sections present
        assert "Load Alteryx" in content or "baseline" in content.lower()
        assert "Row Count" in content
        assert "Schema" in content
        assert "Aggregate" in content
        assert "DataComPy" in content or "datacompy" in content

        # New sections present
        assert "SECTION 3b" in content
        assert "SECTION 3c" in content
        assert "SECTION 6" in content

    def test_aggregate_checks_on_numeric_columns(self, tmp_path: Path):
        """Aggregate section references numeric columns for sum/min/max."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[
                AlteryxField(name="id", type="Int64"),
                AlteryxField(name="revenue", type="Double"),
                AlteryxField(name="name", type="String"),
            ],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            ),
        }

        generate_validator_v2(tmp_path, wf, steps, [1])

        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")
        # Numeric columns should appear in aggregate checks
        assert "revenue" in content

    def test_config_cell_present(self, tmp_path: Path):
        """Config cell with VOLATILE_COLUMNS, KNOWN_DIFFERENCES, ROW_COUNT_TOLERANCE_PCT."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "VOLATILE_COLUMNS = []" in content
        assert "KNOWN_DIFFERENCES = {}" in content
        assert "ROW_COUNT_TOLERANCE_PCT = 0.0" in content

    def test_row_count_uses_tolerance(self, tmp_path: Path):
        """Row count section references ROW_COUNT_TOLERANCE_PCT."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        # The row count section should use tolerance, not a simple assert ==
        assert "ROW_COUNT_TOLERANCE_PCT" in content
        assert "row_diff_pct" in content

    def test_verdict_cell_present(self, tmp_path: Path):
        """Verdict cell has 3-tier description."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "VALIDATION VERDICT" in content
        assert "IDENTICAL" in content
        assert "CODE LOGIC VERIFIED" in content
        assert "FAIL" in content

    def test_column_order_check(self, tmp_path: Path):
        """Section 3b checks column order."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "Column Order Check" in content
        assert "order_match" in content

    def test_column_type_check(self, tmp_path: Path):
        """Section 3c checks column types."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "Column Type Comparison" in content
        assert "type_mismatches" in content

    def test_null_empty_count_section(self, tmp_path: Path):
        """Section 6 compares null/empty counts."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "Null and Empty Count Comparison" in content
        assert "VOLATILE_COLUMNS" in content
        assert "KNOWN_DIFFERENCES" in content

    def test_section6_uses_isNull_not_cast(self, tmp_path: Path):
        """Section 6 uses isNull() and does not use cast('string') == ''."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        assert "isNull()" in content
        assert 'cast("string") == ""' not in content

    def test_section5_uses_volatile_columns(self, tmp_path: Path):
        """Section 5 (DataComPy) filters out VOLATILE_COLUMNS before comparison."""
        tool = AlteryxTool(
            tool_id=1,
            plugin="AlteryxBasePluginsGui.OutputData.OutputData",
            tool_type="OutputData",
            config={},
            output_fields=[AlteryxField(name="id", type="Int64")],
        )
        wf = _make_workflow(tools={1: tool})
        steps = {
            1: GeneratedStep(
                step_name="output", code="df_1 = ...", output_df="df_1"
            )
        }

        generate_validator_v2(tmp_path, wf, steps, [1])
        content = (tmp_path / "04_validate.py").read_text(encoding="utf-8")

        # Section 5 should drop VOLATILE_COLUMNS before DataComPy comparison
        assert "compare_alt = alteryx_df.drop(*VOLATILE_COLUMNS)" in content
        assert "compare_dbx = " in content
        assert "base_df=compare_alt" in content
        assert "compare_df=compare_dbx" in content
