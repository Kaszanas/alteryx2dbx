"""Tests for parse handlers: RegEx, TextToColumns, DateTime."""

from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.regex import RegExHandler
from alteryx2dbx.handlers.text_to_columns import TextToColumnsHandler
from alteryx2dbx.handlers.date_time import DateTimeHandler, _convert_format


# ── RegEx ─────────────────────────────────────────────────────────────


def _make_regex_tool(**overrides):
    defaults = dict(
        tool_id=30,
        plugin="AlteryxBasePluginsEngine.RegEx",
        tool_type="RegEx",
        config={
            "rx_field": "Email",
            "rx_expression": r"@.*$",
            "rx_mode": "Replace",
            "rx_replace": "@company.com",
        },
        annotation="RegEx Replace",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestRegExHandler:
    def test_replace_mode(self):
        step = RegExHandler().convert(
            _make_regex_tool(), input_df_names=["df_5"]
        )
        assert "F.regexp_replace" in step.code
        assert "@company.com" in step.code

    def test_match_mode(self):
        tool = _make_regex_tool(
            config={
                "rx_field": "Email",
                "rx_expression": r"^[a-z]+@",
                "rx_mode": "Match",
            }
        )
        step = RegExHandler().convert(tool, input_df_names=["df_5"])
        assert ".filter(" in step.code
        assert ".rlike(" in step.code

    def test_parse_mode_with_output_fields(self):
        tool = _make_regex_tool(
            config={
                "rx_field": "FullName",
                "rx_expression": r"(\w+)\s(\w+)",
                "rx_mode": "Parse",
                "rx_output_fields": ["FirstName", "LastName"],
            }
        )
        step = RegExHandler().convert(tool, input_df_names=["df_5"])
        assert "F.regexp_extract" in step.code
        assert '"FirstName"' in step.code
        assert '"LastName"' in step.code

    def test_tokenize_mode(self):
        tool = _make_regex_tool(
            config={
                "rx_field": "Tags",
                "rx_expression": r",\s*",
                "rx_mode": "Tokenize",
            }
        )
        step = RegExHandler().convert(tool, input_df_names=["df_5"])
        assert "F.explode" in step.code
        assert "F.split" in step.code

    def test_output_df(self):
        step = RegExHandler().convert(
            _make_regex_tool(tool_id=50), input_df_names=["df_5"]
        )
        assert step.output_df == "df_50"


# ── TextToColumns ─────────────────────────────────────────────────────


def _make_ttc_tool(**overrides):
    defaults = dict(
        tool_id=31,
        plugin="AlteryxBasePluginsEngine.TextToColumns",
        tool_type="TextToColumns",
        config={
            "ttc_field": "Address",
            "ttc_delimiter": ",",
            "ttc_num_columns": 3,
            "ttc_split_to_rows": False,
            "ttc_root_name": "Part",
        },
        annotation="TextToColumns",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestTextToColumnsHandler:
    def test_split_to_columns(self):
        step = TextToColumnsHandler().convert(
            _make_ttc_tool(), input_df_names=["df_5"]
        )
        assert "F.split(" in step.code
        assert ".getItem(0)" in step.code
        assert '"Part1"' in step.code
        assert '"Part3"' in step.code

    def test_split_to_rows(self):
        tool = _make_ttc_tool(
            config={
                "ttc_field": "Tags",
                "ttc_delimiter": ",",
                "ttc_num_columns": 1,
                "ttc_split_to_rows": True,
                "ttc_root_name": "Tag",
            }
        )
        step = TextToColumnsHandler().convert(tool, input_df_names=["df_5"])
        assert "F.explode" in step.code

    def test_output_df(self):
        step = TextToColumnsHandler().convert(
            _make_ttc_tool(tool_id=41), input_df_names=["df_5"]
        )
        assert step.output_df == "df_41"


# ── DateTime ──────────────────────────────────────────────────────────


def _make_datetime_tool(**overrides):
    defaults = dict(
        tool_id=32,
        plugin="AlteryxBasePluginsEngine.DateTime",
        tool_type="DateTime",
        config={
            "dt_field": "OrderDate",
            "dt_format_out": "%Y-%m-%d",
            "dt_conversion": "DateTimeToString",
        },
        annotation="DateTime",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


class TestDateTimeHandler:
    def test_date_format_conversion(self):
        step = DateTimeHandler().convert(
            _make_datetime_tool(), input_df_names=["df_5"]
        )
        assert "F.date_format" in step.code
        assert "yyyy-MM-dd" in step.code

    def test_string_to_datetime(self):
        tool = _make_datetime_tool(
            config={
                "dt_field": "DateStr",
                "dt_format_in": "%Y-%m-%d %H:%M:%S",
                "dt_conversion": "StringToDateTime",
            }
        )
        step = DateTimeHandler().convert(tool, input_df_names=["df_5"])
        assert "F.to_timestamp" in step.code
        assert "yyyy-MM-dd HH:mm:ss" in step.code

    def test_no_flit_in_format(self):
        """Format strings must be plain strings, not wrapped in F.lit()."""
        step = DateTimeHandler().convert(
            _make_datetime_tool(), input_df_names=["df_5"]
        )
        assert "F.lit(" not in step.code

    def test_output_df(self):
        step = DateTimeHandler().convert(
            _make_datetime_tool(tool_id=42), input_df_names=["df_5"]
        )
        assert step.output_df == "df_42"


class TestConvertFormat:
    def test_basic_date(self):
        assert _convert_format("%Y-%m-%d") == "yyyy-MM-dd"

    def test_datetime(self):
        assert _convert_format("%Y-%m-%d %H:%M:%S") == "yyyy-MM-dd HH:mm:ss"

    def test_short_year(self):
        assert _convert_format("%y/%m/%d") == "yy/MM/dd"

    def test_month_name(self):
        assert _convert_format("%B %d, %Y") == "MMMM dd, yyyy"

    def test_ampm(self):
        assert _convert_format("%H:%M %p") == "HH:mm a"
