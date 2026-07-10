from alteryx2dbx.transpiler.expression_emitter import transpile_expression


def test_emit_field_ref():
    assert transpile_expression("[Revenue]") == 'F.col("Revenue")'


def test_emit_number():
    result = transpile_expression("42")
    assert "42" in result


def test_emit_string():
    result = transpile_expression('"hello"')
    assert "hello" in result


def test_emit_comparison_gt():
    result = transpile_expression("[Revenue] > 100")
    assert 'F.col("Revenue")' in result
    assert "> " in result or ">" in result


def test_emit_and():
    result = transpile_expression("[a] > 1 AND [b] > 2")
    assert "&" in result


def test_emit_or():
    result = transpile_expression("[a] > 1 OR [b] > 2")
    assert "|" in result


def test_emit_not():
    result = transpile_expression("NOT [deleted]")
    assert "~" in result


def test_emit_if_then_else():
    result = transpile_expression('IF [x] > 100 THEN "High" ELSE "Low" ENDIF')
    assert "F.when" in result
    assert "otherwise" in result


def test_emit_if_elseif():
    result = transpile_expression(
        'IF [x] > 100 THEN "A" ELSEIF [x] > 50 THEN "B" ELSE "C" ENDIF'
    )
    assert "when" in result


def test_emit_isnull():
    result = transpile_expression("IsNull([Revenue])")
    assert "isNull" in result


def test_emit_contains():
    result = transpile_expression('Contains([Name], "Smith")')
    assert "contains" in result


def test_emit_null():
    result = transpile_expression("NULL()")
    assert "None" in result


def test_emit_arithmetic():
    result = transpile_expression("[price] * [quantity]")
    assert 'F.col("price")' in result
    assert "*" in result


def test_emit_iif():
    result = transpile_expression('IIF([x] > 0, "pos", "neg")')
    assert "F.when" in result
    assert "otherwise" in result


def test_emit_round():
    result = transpile_expression("Round([Revenue], 2)")
    assert "round" in result.lower() or "F.round" in result


def test_emit_trim():
    result = transpile_expression("Trim([Name])")
    assert "trim" in result.lower()


def test_emit_length():
    result = transpile_expression("Length([Name])")
    assert "length" in result.lower()


def test_emit_left():
    result = transpile_expression("Left([Name], 3)")
    assert "substring" in result.lower()


def test_emit_uppercase():
    result = transpile_expression("Uppercase([Name])")
    assert "upper" in result.lower()


def test_emit_substring_zero_based():
    result = transpile_expression("Substring([Name], 0, 3)")
    assert "substring" in result.lower()
    # Should offset start by +1 (0 → 1)
    assert "1" in result


def test_emit_tostring():
    result = transpile_expression("ToString([Revenue])")
    assert "cast" in result and "string" in result


def test_emit_tonumber():
    result = transpile_expression("ToNumber([Price])")
    assert "cast" in result and "double" in result


def test_emit_eq_string_case_insensitive():
    result = transpile_expression('[status] = "Active"')
    assert "lower" in result
