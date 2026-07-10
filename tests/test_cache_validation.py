"""Tests for Task 9: Fan-out cache hints and syntax validation."""

from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxTool,
    AlteryxWorkflow,
    GeneratedStep,
)
from alteryx2dbx.generator.notebook import (
    _insert_cache_hints,
    _validate_syntax,
    _detect_network_paths,
)


# ── Fan-out cache hints ──────────────────────────────────────────────


def _make_workflow(tools, connections):
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools={t.tool_id: t for t in tools},
        connections=connections,
    )


class TestInsertCacheHints:
    def test_fanout_adds_cache(self):
        """A df used by 2+ downstream tools gets .cache()."""
        tools = [
            AlteryxTool(
                tool_id=1,
                plugin="x.InputData",
                tool_type="InputData",
                config={},
            ),
            AlteryxTool(
                tool_id=2, plugin="x.Filter", tool_type="Filter", config={}
            ),
            AlteryxTool(
                tool_id=3, plugin="x.Sort", tool_type="Sort", config={}
            ),
        ]
        connections = [
            AlteryxConnection(1, "Output", 2, "Input"),
            AlteryxConnection(1, "Output", 3, "Input"),
        ]
        wf = _make_workflow(tools, connections)
        steps = {
            1: GeneratedStep(
                step_name="load",
                code="df_1 = spark.read.csv('x')",
                output_df="df_1",
            ),
        }
        _insert_cache_hints(wf, steps)
        assert ".cache()" in steps[1].code
        assert "used by 2 downstream" in steps[1].code

    def test_no_cache_for_single_use(self):
        """A df used by only 1 downstream tool should NOT get .cache()."""
        tools = [
            AlteryxTool(
                tool_id=1,
                plugin="x.InputData",
                tool_type="InputData",
                config={},
            ),
            AlteryxTool(
                tool_id=2, plugin="x.Filter", tool_type="Filter", config={}
            ),
        ]
        connections = [
            AlteryxConnection(1, "Output", 2, "Input"),
        ]
        wf = _make_workflow(tools, connections)
        steps = {
            1: GeneratedStep(
                step_name="load",
                code="df_1 = spark.read.csv('x')",
                output_df="df_1",
            ),
        }
        _insert_cache_hints(wf, steps)
        assert ".cache()" not in steps[1].code

    def test_fanout_with_dual_output(self):
        """Filter True output used by 2 downstream tools should cache."""
        tools = [
            AlteryxTool(
                tool_id=5, plugin="x.Filter", tool_type="Filter", config={}
            ),
            AlteryxTool(
                tool_id=6, plugin="x.Sort", tool_type="Sort", config={}
            ),
            AlteryxTool(
                tool_id=7, plugin="x.Sort", tool_type="Sort", config={}
            ),
        ]
        connections = [
            AlteryxConnection(5, "True", 6, "Input"),
            AlteryxConnection(5, "True", 7, "Input"),
        ]
        wf = _make_workflow(tools, connections)
        steps = {
            5: GeneratedStep(
                step_name="filter",
                code="df_5_true = df_1.filter(...)",
                output_df="df_5_true",
            ),
        }
        _insert_cache_hints(wf, steps)
        assert "df_5_true.cache()" in steps[5].code


# ── Syntax validation ────────────────────────────────────────────────


class TestValidateSyntax:
    def test_valid_python(self, tmp_path):
        p = tmp_path / "good.py"
        p.write_text("x = 1 + 2\nprint(x)\n", encoding="utf-8")
        assert _validate_syntax(p) is True

    def test_invalid_python(self, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text("def foo(\n", encoding="utf-8")
        assert _validate_syntax(p) is False

    def test_databricks_notebook_syntax(self, tmp_path):
        """Typical Databricks notebook content should pass validation."""
        p = tmp_path / "notebook.py"
        p.write_text(
            "# Databricks notebook source\n# COMMAND ----------\nx = 1\n",
            encoding="utf-8",
        )
        assert _validate_syntax(p) is True


# ── Network path detection ───────────────────────────────────────────


class TestDetectNetworkPaths:
    def test_unc_path_detected(self):
        steps = {
            1: GeneratedStep(
                step_name="load",
                code='df_1 = spark.read.csv("\\\\\\\\server\\\\share\\\\file.csv")',
                output_df="df_1",
            ),
        }
        _detect_network_paths(steps)
        assert any("Network path" in n for n in steps[1].notes)

    def test_no_network_path(self):
        steps = {
            1: GeneratedStep(
                step_name="load",
                code='df_1 = spark.read.csv("/dbfs/data/file.csv")',
                output_df="df_1",
            ),
        }
        _detect_network_paths(steps)
        assert len(steps[1].notes) == 0
