"""Tests for easy handlers: Sample, Unique, RecordID, AutoField, CountRecords, AppendFields."""

from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.sample import SampleHandler
from alteryx2dbx.handlers.unique import UniqueHandler
from alteryx2dbx.handlers.record_id import RecordIDHandler
from alteryx2dbx.handlers.auto_field import AutoFieldHandler
from alteryx2dbx.handlers.count_records import CountRecordsHandler
from alteryx2dbx.handlers.append_fields import AppendFieldsHandler


# ── Sample ───────────────────────────────────────────────────────────────────


def _sample_tool(tool_id=10, mode="First", n=100, pct=0.1, annotation="Sample"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Sample",
        tool_type="Sample",
        config={"sample_mode": mode, "sample_n": n, "sample_pct": pct},
        annotation=annotation,
    )


class TestSampleHandler:
    def test_first_n_uses_limit(self):
        step = SampleHandler().convert(
            _sample_tool(mode="First", n=50), ["df_1"]
        )
        assert ".limit(50)" in step.code
        assert step.confidence == 1.0

    def test_percentage_uses_sample(self):
        step = SampleHandler().convert(
            _sample_tool(mode="Percentage", pct=0.25), ["df_1"]
        )
        assert ".sample(fraction=0.25)" in step.code
        assert step.confidence == 0.5

    def test_random_uses_rand_and_limit(self):
        step = SampleHandler().convert(
            _sample_tool(mode="Random", n=10), ["df_1"]
        )
        assert "F.rand()" in step.code
        assert ".limit(10)" in step.code

    def test_output_df_name(self):
        step = SampleHandler().convert(_sample_tool(tool_id=7), ["df_3"])
        assert step.output_df == "df_7"

    def test_annotation_in_code(self):
        step = SampleHandler().convert(
            _sample_tool(annotation="Top 100"), ["df_1"]
        )
        assert "Top 100" in step.code


# ── Unique ───────────────────────────────────────────────────────────────────


def _unique_tool(tool_id=15, fields=None, annotation="Unique"):
    config = {}
    if fields is not None:
        config["unique_fields"] = fields
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.Unique",
        tool_type="Unique",
        config=config,
        annotation=annotation,
    )


class TestUniqueHandler:
    def test_dedup_with_fields(self):
        step = UniqueHandler().convert(
            _unique_tool(fields=["Name", "Date"]), ["df_2"]
        )
        assert ".dropDuplicates(" in step.code
        assert "'Name'" in step.code
        assert "'Date'" in step.code

    def test_dual_output(self):
        step = UniqueHandler().convert(_unique_tool(tool_id=5), ["df_1"])
        assert "df_5_unique" in step.code
        assert "df_5_duplicates" in step.code
        assert "df_5 = df_5_unique" in step.code

    def test_no_fields_dedup_all(self):
        step = UniqueHandler().convert(_unique_tool(fields=None), ["df_1"])
        assert ".dropDuplicates()" in step.code
        assert any("all columns" in n for n in step.notes)

    def test_output_df_name(self):
        step = UniqueHandler().convert(_unique_tool(tool_id=22), ["df_3"])
        assert step.output_df == "df_22"


# ── RecordID ─────────────────────────────────────────────────────────────────


def _record_id_tool(tool_id=30, field_name="RecordID", annotation="RecordID"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.RecordID",
        tool_type="RecordID",
        config={"FieldName": field_name},
        annotation=annotation,
    )


class TestRecordIDHandler:
    def test_adds_record_id_column(self):
        step = RecordIDHandler().convert(_record_id_tool(), ["df_5"])
        assert "monotonically_increasing_id()" in step.code
        assert '"RecordID"' in step.code

    def test_custom_field_name(self):
        step = RecordIDHandler().convert(
            _record_id_tool(field_name="RowNum"), ["df_5"]
        )
        assert '"RowNum"' in step.code

    def test_imports_pyspark_functions(self):
        step = RecordIDHandler().convert(_record_id_tool(), ["df_1"])
        assert "from pyspark.sql import functions as F" in step.imports

    def test_output_df_name(self):
        step = RecordIDHandler().convert(_record_id_tool(tool_id=8), ["df_1"])
        assert step.output_df == "df_8"


# ── AutoField ────────────────────────────────────────────────────────────────


def _auto_field_tool(tool_id=40, annotation="AutoField"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.AutoField",
        tool_type="AutoField",
        config={},
        annotation=annotation,
    )


class TestAutoFieldHandler:
    def test_passthrough(self):
        step = AutoFieldHandler().convert(
            _auto_field_tool(tool_id=12), ["df_7"]
        )
        assert "df_12 = df_7" in step.code

    def test_confidence_is_1(self):
        step = AutoFieldHandler().convert(_auto_field_tool(), ["df_1"])
        assert step.confidence == 1.0

    def test_no_imports(self):
        step = AutoFieldHandler().convert(_auto_field_tool(), ["df_1"])
        assert step.imports == set()

    def test_note_about_noop(self):
        step = AutoFieldHandler().convert(_auto_field_tool(), ["df_1"])
        assert any("no-op" in n for n in step.notes)


# ── CountRecords ─────────────────────────────────────────────────────────────


def _count_records_tool(tool_id=50, annotation="CountRecords"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.CountRecords",
        tool_type="CountRecords",
        config={},
        annotation=annotation,
    )


class TestCountRecordsHandler:
    def test_creates_count_dataframe(self):
        step = CountRecordsHandler().convert(_count_records_tool(), ["df_3"])
        assert "spark.createDataFrame" in step.code
        assert "df_3.count()" in step.code
        assert '"Count"' in step.code

    def test_output_df_name(self):
        step = CountRecordsHandler().convert(
            _count_records_tool(tool_id=9), ["df_1"]
        )
        assert step.output_df == "df_9"

    def test_confidence_is_1(self):
        step = CountRecordsHandler().convert(_count_records_tool(), ["df_1"])
        assert step.confidence == 1.0


# ── AppendFields ─────────────────────────────────────────────────────────────


def _append_fields_tool(tool_id=60, annotation="AppendFields"):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="AlteryxBasePluginsEngine.AppendFields",
        tool_type="AppendFields",
        config={},
        annotation=annotation,
    )


class TestAppendFieldsHandler:
    def test_cross_join(self):
        step = AppendFieldsHandler().convert(
            _append_fields_tool(), ["df_1", "df_2"]
        )
        assert "df_1.crossJoin(df_2)" in step.code

    def test_two_input_dfs(self):
        step = AppendFieldsHandler().convert(
            _append_fields_tool(), ["df_1", "df_2"]
        )
        assert step.input_dfs == ["df_1", "df_2"]

    def test_output_df_name(self):
        step = AppendFieldsHandler().convert(
            _append_fields_tool(tool_id=25), ["df_a", "df_b"]
        )
        assert step.output_df == "df_25"

    def test_default_df_names_when_none(self):
        step = AppendFieldsHandler().convert(_append_fields_tool(), None)
        assert "df_target" in step.code
        assert "df_source" in step.code
