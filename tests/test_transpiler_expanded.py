"""Tests for expanded expression grammar: IN, Switch, and 40+ new functions."""

from alteryx2dbx.transpiler.expression_emitter import transpile_expression


# ── IN expression ────────────────────────────────────────────


def test_in_expr_two_values():
    result = transpile_expression('[Status] IN ("Active", "Pending")')
    assert ".isin(" in result
    assert 'F.col("Status")' in result
    assert "Active" in result
    assert "Pending" in result


def test_in_expr_numbers():
    result = transpile_expression("[Code] IN (1, 2, 3)")
    assert ".isin(" in result
    assert "F.lit(1)" in result
    assert "F.lit(3)" in result


def test_in_expr_single_value():
    result = transpile_expression('[Type] IN ("A")')
    assert ".isin(" in result


# ── Switch function ──────────────────────────────────────────


def test_switch_basic():
    result = transpile_expression(
        'Switch([Type], "Other", "A", "Alpha", "B", "Beta")'
    )
    assert "F.when(" in result
    assert ".otherwise(" in result
    assert "Alpha" in result
    assert "Beta" in result
    assert "Other" in result


def test_switch_numeric():
    result = transpile_expression(
        'Switch([Code], "Unknown", 1, "One", 2, "Two")'
    )
    assert "F.when(" in result
    assert ".otherwise(" in result


# ── Conversion functions ─────────────────────────────────────


def test_tointeger():
    result = transpile_expression("ToInteger([Price])")
    assert '.cast("int")' in result


def test_todate():
    result = transpile_expression("ToDate([DateStr])")
    assert '.cast("date")' in result


def test_todatetime():
    result = transpile_expression("ToDateTime([DateStr])")
    assert '.cast("timestamp")' in result


# ── Null handling ────────────────────────────────────────────


def test_coalesce():
    result = transpile_expression("Coalesce([a], [b], [c])")
    assert "F.coalesce(" in result
    assert 'F.col("a")' in result
    assert 'F.col("c")' in result


def test_ifnull():
    result = transpile_expression("IfNull([Revenue], 0)")
    assert "F.coalesce(" in result
    assert 'F.col("Revenue")' in result


def test_nullif():
    result = transpile_expression("NullIf([a], [b])")
    assert "F.when(" in result
    assert "F.lit(None)" in result
    assert ".otherwise(" in result


# ── DateTime functions ───────────────────────────────────────


def test_datetimeformat():
    result = transpile_expression('DateTimeFormat([dt], "%Y-%m-%d")')
    assert "F.date_format(" in result
    assert "yyyy-MM-dd" in result


def test_datetimeparse():
    result = transpile_expression('DateTimeParse([s], "%Y-%m-%d %H:%M:%S")')
    assert "F.to_timestamp(" in result
    assert "yyyy-MM-dd HH:mm:ss" in result


def test_datetimeadd_days():
    result = transpile_expression('DateTimeAdd([dt], 5, "days")')
    assert "F.date_add(" in result


def test_datetimeadd_months():
    result = transpile_expression('DateTimeAdd([dt], 3, "months")')
    assert "F.add_months(" in result


def test_datetimeadd_years():
    result = transpile_expression('DateTimeAdd([dt], 1, "years")')
    assert "F.add_months(" in result
    assert "* 12" in result


def test_datetimediff():
    result = transpile_expression("DateTimeDiff([a], [b])")
    assert "F.datediff(" in result


def test_datetimetoday():
    result = transpile_expression("DateTimeToday()")
    assert "F.current_date()" in result


def test_datetimeyear():
    result = transpile_expression("DateTimeYear([dt])")
    assert "F.year(" in result


def test_datetimemonth():
    result = transpile_expression("DateTimeMonth([dt])")
    assert "F.month(" in result


def test_datetimeday():
    result = transpile_expression("DateTimeDay([dt])")
    assert "F.dayofmonth(" in result


def test_datetimehour():
    result = transpile_expression("DateTimeHour([dt])")
    assert "F.hour(" in result


def test_datetimeminutes():
    result = transpile_expression("DateTimeMinutes([dt])")
    assert "F.minute(" in result


def test_datetimeseconds():
    result = transpile_expression("DateTimeSeconds([dt])")
    assert "F.second(" in result


def test_datetimedayofweek():
    result = transpile_expression("DateTimeDayOfWeek([dt])")
    assert "F.dayofweek(" in result


def test_datetimefirstofmonth():
    result = transpile_expression("DateTimeFirstOfMonth([dt])")
    assert "F.date_trunc(" in result
    assert "month" in result


def test_datetimetrim():
    result = transpile_expression('DateTimeTrim([dt], "month")')
    assert "F.date_trunc(" in result
    assert "month" in result


# ── Math functions ───────────────────────────────────────────


def test_log():
    result = transpile_expression("Log([x])")
    assert "F.log(" in result


def test_log10():
    result = transpile_expression("Log10([x])")
    assert "F.log10(" in result


def test_log2():
    result = transpile_expression("Log2([x])")
    assert "F.log2(" in result


def test_exp():
    result = transpile_expression("Exp([x])")
    assert "F.exp(" in result


def test_sin():
    result = transpile_expression("Sin([x])")
    assert "F.sin(" in result


def test_cos():
    result = transpile_expression("Cos([x])")
    assert "F.cos(" in result


def test_tan():
    result = transpile_expression("Tan([x])")
    assert "F.tan(" in result


def test_rand():
    result = transpile_expression("Rand()")
    assert "F.rand()" in result


def test_sign():
    result = transpile_expression("Sign([x])")
    assert "F.signum(" in result


# ── String functions ─────────────────────────────────────────


def test_titlecase():
    result = transpile_expression("TitleCase([Name])")
    assert "F.initcap(" in result


def test_reversestring():
    result = transpile_expression("ReverseString([Name])")
    assert "F.reverse(" in result


def test_replace():
    result = transpile_expression('Replace([Name], "old", "new")')
    assert "F.regexp_replace(" in result


def test_countwords():
    result = transpile_expression("CountWords([Text])")
    assert "F.size(" in result
    assert "F.split(" in result


# ── Test functions ───────────────────────────────────────────


def test_isnumber():
    result = transpile_expression("IsNumber([x])")
    assert '.cast("double")' in result
    assert ".isNotNull()" in result


def test_isinteger():
    result = transpile_expression("IsInteger([x])")
    assert '.cast("int")' in result
    assert ".isNotNull()" in result


# ── Mid function ─────────────────────────────────────────────


def test_mid_zero_based():
    result = transpile_expression("Mid([Name], 0, 3)")
    assert "F.substring(" in result
    # 0-based → 1-based: start 0 becomes 1
    assert ", 1," in result


def test_mid_nonzero_start():
    result = transpile_expression("Mid([Name], 2, 5)")
    assert "F.substring(" in result
    # 2 → 3
    assert ", 3," in result
