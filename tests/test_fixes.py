"""Tests for the semantic fix registry."""

from __future__ import annotations

from alteryx2dbx.fixes import FIXES, FixResult, apply_fixes, register_fix


class TestRegistryHasKnownFixes:
    def test_registry_contains_case_insensitive_join(self):
        assert "case_insensitive_join" in FIXES

    def test_registry_contains_null_safe_equality(self):
        assert "null_safe_equality" in FIXES

    def test_registry_contains_numeric_cast(self):
        assert "numeric_cast" in FIXES

    def test_each_fix_has_required_keys(self):
        for fix_id, entry in FIXES.items():
            assert "description" in entry, f"{fix_id} missing description"
            assert "severity" in entry, f"{fix_id} missing severity"
            assert "fn" in entry, f"{fix_id} missing fn"
            assert callable(entry["fn"]), f"{fix_id} fn not callable"


class TestCaseInsensitiveJoinFix:
    def test_lower_added_to_string_join_keys(self):
        code = 'df_1["CustomerID"] == df_2["CustID"]'
        context = {
            "tool_type": "Join",
            "join_fields": [{"left": "CustomerID", "right": "CustID"}],
        }
        result = apply_fixes(code, context)
        assert "F.lower" in result.code
        assert "CustomerID" in result.code
        assert "CustID" in result.code

    def test_lower_wraps_col_references(self):
        code = 'df_1["Name"] == df_2["Name"]'
        context = {
            "tool_type": "Join",
            "join_fields": [{"left": "Name", "right": "Name"}],
        }
        result = apply_fixes(code, context)
        assert 'F.lower(df_1["Name"])' in result.code
        assert 'F.lower(df_2["Name"])' in result.code


class TestNullSafeEqualityFix:
    def test_eq_replaced_with_eqnullsafe_in_filter(self):
        code = 'F.col("status") == F.lit("active")'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        assert "eqNullSafe" in result.code
        assert 'F.col("status").eqNullSafe(F.lit("active"))' in result.code

    def test_eq_replaced_in_formula(self):
        code = 'F.col("x") == F.lit("y")'
        context = {"tool_type": "Formula"}
        result = apply_fixes(code, context)
        assert "eqNullSafe" in result.code

    def test_multiple_equalities_replaced(self):
        code = 'F.col("a") == F.lit("1") & F.col("b") == F.lit("2")'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        assert result.code.count("eqNullSafe") == 2


class TestNumericCastFix:
    def test_decimal_cast_added(self):
        code = 'df = df.withColumn("amount", F.col("amount"))'
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {
                    "name": "amount",
                    "type": "FixedDecimal",
                    "size": 10,
                    "scale": 2,
                },
            ],
        }
        result = apply_fixes(code, context)
        assert ".cast(DecimalType(10,2))" in result.code

    def test_no_cast_for_non_decimal(self):
        code = 'df = df.withColumn("name", F.col("name"))'
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {"name": "name", "type": "V_String", "size": 50, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        assert "DecimalType" not in result.code


class TestFixReportTracksApplied:
    def test_applied_fixes_populated(self):
        code = 'F.col("x") == F.lit("y")'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        assert isinstance(result, FixResult)
        assert len(result.applied_fixes) > 0
        fix_ids = [f["fix_id"] for f in result.applied_fixes]
        assert "null_safe_equality" in fix_ids

    def test_applied_fixes_have_fix_id(self):
        code = 'F.col("x") == F.lit("y")'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        for fix in result.applied_fixes:
            assert "fix_id" in fix


class TestNoFixesWhenNotApplicable:
    def test_filter_code_gets_no_join_fixes(self):
        code = 'df = df.filter(F.col("x") > 5)'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        fix_ids = [f["fix_id"] for f in result.applied_fixes]
        assert "case_insensitive_join" not in fix_ids

    def test_join_code_gets_no_null_safe_fix(self):
        code = 'df_1["ID"] == df_2["ID"]'
        context = {
            "tool_type": "Join",
            "join_fields": [{"left": "ID", "right": "ID"}],
        }
        result = apply_fixes(code, context)
        fix_ids = [f["fix_id"] for f in result.applied_fixes]
        assert "null_safe_equality" not in fix_ids

    def test_no_fixes_returns_empty_list(self):
        code = "df = spark.table('my_table')"
        context = {"tool_type": "InputData"}
        result = apply_fixes(code, context)
        assert result.applied_fixes == []
        assert result.code == code


# ---------------------------------------------------------------------------
# New fix tests
# ---------------------------------------------------------------------------


class TestRegisterFix:
    def test_register_fix_adds_to_registry(self):
        def _dummy(code, context):
            return code, False

        register_fix("test_dummy", "A test fix", "info", _dummy, phase="test")
        assert "test_dummy" in FIXES
        assert FIXES["test_dummy"]["phase"] == "test"
        # Cleanup
        del FIXES["test_dummy"]

    def test_register_fix_default_phase(self):
        def _dummy(code, context):
            return code, False

        register_fix("test_dummy2", "A test fix", "info", _dummy)
        assert FIXES["test_dummy2"]["phase"] == "general"
        del FIXES["test_dummy2"]


class TestCoalesceTypingFix:
    def test_numeric_coalesce_gets_cast(self):
        code = """df = df.withColumn("x", F.expr("COALESCE(amount, '')"))"""
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {
                    "name": "amount",
                    "type": "Double",
                    "size": None,
                    "scale": None,
                },
            ],
        }
        result = apply_fixes(code, context)
        assert "CAST(amount AS STRING)" in result.code

    def test_string_coalesce_unchanged(self):
        code = """df = df.withColumn("x", F.expr("COALESCE(name, '')"))"""
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {"name": "name", "type": "V_String", "size": 50, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        assert "CAST(" not in result.code

    def test_double_quotes_in_coalesce(self):
        code = 'df = df.withColumn("x", F.expr(\'COALESCE(price, "")\'))'
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {"name": "price", "type": "Int64", "size": None, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        assert "CAST(price AS STRING)" in result.code

    def test_no_output_fields_noop(self):
        code = """F.expr("COALESCE(amount, '')")"""
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "CAST(" not in result.code


class TestSafeDateParsingFix:
    def test_to_date_replaced(self):
        code = """F.expr("TO_DATE(col, 'yyyy-MM-dd')")"""
        context = {"tool_type": "Formula"}
        result = apply_fixes(code, context)
        assert "TRY_TO_DATE" in result.code
        assert "TO_DATE" not in result.code.replace("TRY_TO_DATE", "")

    def test_to_timestamp_replaced(self):
        code = """F.expr("TO_TIMESTAMP(col, 'yyyy-MM-dd HH:mm:ss')")"""
        context = {"tool_type": "Formula"}
        result = apply_fixes(code, context)
        assert "TRY_TO_TIMESTAMP" in result.code

    def test_try_to_date_not_doubled(self):
        code = """F.expr("TRY_TO_DATE(col, 'yyyy-MM-dd')")"""
        context = {"tool_type": "Formula"}
        result = apply_fixes(code, context)
        assert "TRY_TRY_TO_DATE" not in result.code

    def test_no_date_functions_noop(self):
        code = """df = df.withColumn("x", F.col("y"))"""
        context = {"tool_type": "Formula"}
        result = apply_fixes(code, context)
        fix_ids = [f["fix_id"] for f in result.applied_fixes]
        assert "safe_date_parsing" not in fix_ids


class TestSafeCastingFix:
    def test_cast_replaced_in_formula(self):
        code = """df = df.withColumn("x", F.expr("CAST(col AS INT)"))"""
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "TRY_CAST(" in result.code
        # The bare CAST should be gone
        assert result.code.count("CAST(") == result.code.count("TRY_CAST(")

    def test_cast_not_replaced_in_join(self):
        code = """df = df.withColumn("x", F.expr("CAST(col AS INT)"))"""
        context = {"tool_type": "Join", "output_fields": []}
        result = apply_fixes(code, context)
        assert "TRY_CAST" not in result.code

    def test_try_cast_not_double_wrapped(self):
        code = """F.expr("TRY_CAST(col AS INT)")"""
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "TRY_TRY_CAST" not in result.code
        assert result.code.count("TRY_CAST") == 1

    def test_multifieldformula_also_applies(self):
        code = """F.expr("CAST(x AS STRING)")"""
        context = {"tool_type": "MultiFieldFormula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "TRY_CAST(" in result.code


class TestFloat64IntegerKeysFix:
    def test_warning_added_for_int_join(self):
        code = 'df = df_1.join(df_2, on="id")'
        context = {
            "tool_type": "Join",
            "output_fields": [
                {"name": "id", "type": "Int64", "size": None, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        assert "float64" in result.code
        assert "WARNING" in result.code

    def test_no_warning_for_string_join(self):
        code = 'df = df_1.join(df_2, on="id")'
        context = {
            "tool_type": "Join",
            "output_fields": [
                {"name": "id", "type": "V_String", "size": 50, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        assert "float64" not in result.code

    def test_no_warning_for_non_join(self):
        code = 'df = df.withColumn("x", F.col("y"))'
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {"name": "x", "type": "Int32", "size": None, "scale": None},
            ],
        }
        result = apply_fixes(code, context)
        fix_ids = [f["fix_id"] for f in result.applied_fixes]
        assert "float64_integer_keys" not in fix_ids


class TestWithColumnLoopFix:
    def test_warning_at_10_calls(self):
        code = "\n".join(
            [f'df = df.withColumn("col_{i}", F.lit({i}))' for i in range(10)]
        )
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "PERFORMANCE" in result.code
        assert "10 sequential" in result.code

    def test_no_warning_under_10(self):
        code = "\n".join(
            [f'df = df.withColumn("col_{i}", F.lit({i}))' for i in range(9)]
        )
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "PERFORMANCE" not in result.code

    def test_correct_count_in_message(self):
        code = "\n".join(
            [f'df = df.withColumn("col_{i}", F.lit({i}))' for i in range(15)]
        )
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "15 sequential" in result.code


class TestDatePlaceholderClampingFix:
    def test_warning_for_to_excel(self):
        code = "df.to_excel('output.xlsx')"
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "1900-01-01" in result.code

    def test_warning_for_xlsxwriter(self):
        code = "writer = pd.ExcelWriter('out.xlsx', engine='xlsxwriter')"
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "1900-01-01" in result.code

    def test_warning_for_output_data_xlsx(self):
        code = "df.write.save('output')"
        context = {
            "tool_type": "OutputData",
            "file_format": "xlsx",
            "output_fields": [],
        }
        result = apply_fixes(code, context)
        assert "1900-01-01" in result.code

    def test_no_warning_for_csv(self):
        code = "df.write.csv('output.csv')"
        context = {
            "tool_type": "OutputData",
            "file_format": "csv",
            "output_fields": [],
        }
        result = apply_fixes(code, context)
        assert "1900-01-01" not in result.code

    def test_no_warning_for_unrelated_code(self):
        code = "df = df.withColumn('x', F.col('y'))"
        context = {"tool_type": "Formula", "output_fields": []}
        result = apply_fixes(code, context)
        assert "1900-01-01" not in result.code


class TestNewFixesRegistered:
    def test_all_new_fixes_in_registry(self):
        expected = [
            "coalesce_typing",
            "safe_date_parsing",
            "safe_casting",
            "float64_integer_keys",
            "withcolumn_loop",
            "date_placeholder_clamping",
        ]
        for fix_id in expected:
            assert fix_id in FIXES, f"{fix_id} not in FIXES"

    def test_all_fixes_have_phase(self):
        for fix_id, entry in FIXES.items():
            assert "phase" in entry, f"{fix_id} missing phase"


class TestNumericCastNoOverMatch:
    def test_no_cast_in_filter(self):
        code = (
            'df = df.filter(F.col("amount") > 0)\n'
            'df = df.withColumn("total", F.col("total"))'
        )
        context = {
            "tool_type": "Formula",
            "output_fields": [
                {
                    "name": "amount",
                    "type": "FixedDecimal",
                    "size": 10,
                    "scale": 2,
                },
            ],
        }
        result = apply_fixes(code, context)
        # The filter line must NOT get a cast
        assert 'df = df.filter(F.col("amount") > 0)' in result.code
        assert "DecimalType" not in result.code.split("\n")[0]


class TestNullSafeEqualityParenInColName:
    def test_column_name_with_closing_paren(self):
        code = 'F.col("Revenue (USD)") == F.lit("high")'
        context = {"tool_type": "Filter"}
        result = apply_fixes(code, context)
        assert 'F.col("Revenue (USD)").eqNullSafe(F.lit("high"))' in result.code
