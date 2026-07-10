"""Tests for Task 8: DAG anchor routing for dual-output tools (Unique, Join)."""

from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxTool,
    AlteryxWorkflow,
)
from alteryx2dbx.generator.notebook import (
    _build_input_map,
    _resolve_source_df_name,
)


# ── _resolve_source_df_name unit tests ────────────────────────────────


class TestResolveSourceDfName:
    def test_true_anchor(self):
        assert _resolve_source_df_name(5, "True") == "df_5_true"

    def test_false_anchor(self):
        assert _resolve_source_df_name(5, "False") == "df_5_false"

    def test_unique_anchor_full(self):
        assert _resolve_source_df_name(7, "Unique") == "df_7_unique"

    def test_unique_anchor_short(self):
        assert _resolve_source_df_name(7, "U") == "df_7_unique"

    def test_duplicates_anchor_full(self):
        assert _resolve_source_df_name(7, "Duplicates") == "df_7_duplicates"

    def test_duplicates_anchor_short(self):
        assert _resolve_source_df_name(7, "D") == "df_7_duplicates"

    def test_join_anchor_full(self):
        assert _resolve_source_df_name(10, "Join") == "df_10_joined"

    def test_join_anchor_short(self):
        assert _resolve_source_df_name(10, "J") == "df_10_joined"

    def test_left_anchor_full(self):
        assert _resolve_source_df_name(10, "Left") == "df_10_left_only"

    def test_left_anchor_short(self):
        assert _resolve_source_df_name(10, "L") == "df_10_left_only"

    def test_right_anchor_full(self):
        assert _resolve_source_df_name(10, "Right") == "df_10_right_only"

    def test_right_anchor_short(self):
        assert _resolve_source_df_name(10, "R") == "df_10_right_only"

    def test_output_anchor_default(self):
        assert _resolve_source_df_name(3, "Output") == "df_3"

    def test_empty_anchor(self):
        assert _resolve_source_df_name(3, "") == "df_3"


# ── _build_input_map integration tests ───────────────────────────────


def _make_workflow(tools, connections):
    return AlteryxWorkflow(
        name="test_wf",
        version="2024.1",
        tools={t.tool_id: t for t in tools},
        connections=connections,
    )


class TestBuildInputMapUniqueAnchors:
    """Verify that Unique tool output anchors produce correct df names."""

    def test_unique_and_duplicates_routed(self):
        unique_tool = AlteryxTool(
            tool_id=5,
            plugin="AlteryxBasePluginsEngine.Unique",
            tool_type="Unique",
            config={},
        )
        downstream_a = AlteryxTool(
            tool_id=6,
            plugin="AlteryxBasePluginsEngine.Sort",
            tool_type="Sort",
            config={},
        )
        downstream_b = AlteryxTool(
            tool_id=7,
            plugin="AlteryxBasePluginsEngine.Sort",
            tool_type="Sort",
            config={},
        )
        connections = [
            AlteryxConnection(
                source_tool_id=5,
                source_anchor="Unique",
                target_tool_id=6,
                target_anchor="Input",
            ),
            AlteryxConnection(
                source_tool_id=5,
                source_anchor="Duplicates",
                target_tool_id=7,
                target_anchor="Input",
            ),
        ]
        wf = _make_workflow(
            [unique_tool, downstream_a, downstream_b], connections
        )
        input_map = _build_input_map(wf)

        assert input_map[6] == ["df_5_unique"]
        assert input_map[7] == ["df_5_duplicates"]


class TestBuildInputMapJoinAnchors:
    """Verify that Join tool output anchors produce correct df names."""

    def test_join_three_outputs_routed(self):
        join_tool = AlteryxTool(
            tool_id=10,
            plugin="AlteryxBasePluginsEngine.Join",
            tool_type="Join",
            config={},
        )
        ds_joined = AlteryxTool(
            tool_id=11, plugin="x.Sort", tool_type="Sort", config={}
        )
        ds_left = AlteryxTool(
            tool_id=12, plugin="x.Sort", tool_type="Sort", config={}
        )
        ds_right = AlteryxTool(
            tool_id=13, plugin="x.Sort", tool_type="Sort", config={}
        )
        connections = [
            AlteryxConnection(
                source_tool_id=10,
                source_anchor="Join",
                target_tool_id=11,
                target_anchor="Input",
            ),
            AlteryxConnection(
                source_tool_id=10,
                source_anchor="Left",
                target_tool_id=12,
                target_anchor="Input",
            ),
            AlteryxConnection(
                source_tool_id=10,
                source_anchor="Right",
                target_tool_id=13,
                target_anchor="Input",
            ),
        ]
        wf = _make_workflow(
            [join_tool, ds_joined, ds_left, ds_right], connections
        )
        input_map = _build_input_map(wf)

        assert input_map[11] == ["df_10_joined"]
        assert input_map[12] == ["df_10_left_only"]
        assert input_map[13] == ["df_10_right_only"]

    def test_left_right_as_target_anchors_still_ordered(self):
        """Left/Right as TARGET anchors should still be ordered correctly for dual-input tools."""
        src_a = AlteryxTool(
            tool_id=1, plugin="x.InputData", tool_type="InputData", config={}
        )
        src_b = AlteryxTool(
            tool_id=2, plugin="x.InputData", tool_type="InputData", config={}
        )
        join_tool = AlteryxTool(
            tool_id=3, plugin="x.Join", tool_type="Join", config={}
        )
        connections = [
            AlteryxConnection(
                source_tool_id=1,
                source_anchor="Output",
                target_tool_id=3,
                target_anchor="Left",
            ),
            AlteryxConnection(
                source_tool_id=2,
                source_anchor="Output",
                target_tool_id=3,
                target_anchor="Right",
            ),
        ]
        wf = _make_workflow([src_a, src_b, join_tool], connections)
        input_map = _build_input_map(wf)

        # Target anchors Left/Right should order inputs: left first, right second
        assert input_map[3] == ["df_1", "df_2"]
