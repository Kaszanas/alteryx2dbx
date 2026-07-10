from alteryx2dbx.transpiler.expression_parser import parse_expression


def test_parse_number():
    tree = parse_expression("42")
    assert tree is not None


def test_parse_float():
    tree = parse_expression("3.14")
    assert tree is not None


def test_parse_string():
    tree = parse_expression('"hello"')
    assert tree is not None


def test_parse_field_ref():
    tree = parse_expression("[Revenue]")
    assert tree is not None


def test_parse_comparison():
    tree = parse_expression("[Revenue] > 100")
    assert tree is not None


def test_parse_and():
    tree = parse_expression('[status] = "active" AND [revenue] > 100')
    assert tree is not None


def test_parse_or():
    tree = parse_expression("[a] = 1 OR [b] = 2")
    assert tree is not None


def test_parse_if_then_else():
    tree = parse_expression('IF [Revenue] > 1000 THEN "High" ELSE "Low" ENDIF')
    assert tree is not None


def test_parse_if_elseif():
    tree = parse_expression(
        'IF [x] > 100 THEN "A" ELSEIF [x] > 50 THEN "B" ELSE "C" ENDIF'
    )
    assert tree is not None


def test_parse_function_call():
    tree = parse_expression('Contains([Name], "Smith")')
    assert tree is not None


def test_parse_nested_function():
    tree = parse_expression("ToString(Round([Revenue] * 1.1, 2))")
    assert tree is not None


def test_parse_iif():
    tree = parse_expression('IIF([x] > 0, "pos", "neg")')
    assert tree is not None


def test_parse_null():
    tree = parse_expression("NULL()")
    assert tree is not None


def test_parse_isnull():
    tree = parse_expression("IsNull([Revenue])")
    assert tree is not None


def test_parse_arithmetic():
    tree = parse_expression("[price] * [quantity] - [discount]")
    assert tree is not None


def test_parse_string_concat():
    tree = parse_expression('[first] + " " + [last]')
    assert tree is not None


def test_parse_not():
    tree = parse_expression("NOT [is_deleted]")
    assert tree is not None


def test_parse_row_ref():
    tree = parse_expression("[Row-1:Revenue]")
    assert tree is not None


def test_parse_negative_number():
    tree = parse_expression("-1.5")
    assert tree is not None


def test_parse_boolean_true():
    tree = parse_expression("True")
    assert tree is not None


def test_parse_parenthesized():
    tree = parse_expression("([a] + [b]) * [c]")
    assert tree is not None


def test_parse_complex_expression():
    tree = parse_expression(
        'IF [Revenue] > 1000 AND Contains([Category], "Tech") THEN ToString(Round([Revenue] * 1.1, 2)) + " USD" ELSEIF IsNull([Revenue]) THEN "N/A" ELSE "Low" ENDIF'
    )
    assert tree is not None
