"""PySpark expression emitter — transforms Lark parse trees to PySpark column expressions."""

from __future__ import annotations

import re
from lark import Transformer, Token

from alteryx2dbx.transpiler.expression_parser import parse_expression


# Direct function mappings: Alteryx name (lowered) → PySpark function
_DIRECT_MAP: dict[str, str] = {
    "trim": "F.trim",
    "trimleft": "F.ltrim",
    "trimright": "F.rtrim",
    "length": "F.length",
    "uppercase": "F.upper",
    "lowercase": "F.lower",
    "round": "F.round",
    "ceil": "F.ceil",
    "floor": "F.floor",
    "abs": "F.abs",
    "pow": "F.pow",
    "sqrt": "F.sqrt",
    "min": "F.least",
    "max": "F.greatest",
    "padleft": "F.lpad",
    "padright": "F.rpad",
    "regex_replace": "F.regexp_replace",
    "replacechar": "F.translate",
    "titlecase": "F.initcap",
    "reversestring": "F.reverse",
    "log": "F.log",
    "log10": "F.log10",
    "log2": "F.log2",
    "exp": "F.exp",
    "sin": "F.sin",
    "cos": "F.cos",
    "tan": "F.tan",
    "asin": "F.asin",
    "acos": "F.acos",
    "atan": "F.atan",
    "atan2": "F.atan2",
    "rand": "F.rand",
    "sign": "F.signum",
}


class PySparkEmitter(Transformer):
    """Walk Lark parse tree and emit PySpark column expression strings."""

    # ── Atoms ──────────────────────────────────────────────────

    def start(self, children):
        return children[0]

    def number(self, children):
        token = children[0]
        val = str(token)
        if "." in val:
            return f"F.lit({val})"
        return f"F.lit({val})"

    def string(self, children):
        token = str(children[0])
        # Normalize to double-quoted
        inner = token[1:-1]  # strip quotes
        return f'F.lit("{inner}")'

    def boolean(self, children):
        token = str(children[0]).lower()
        val = "True" if token == "true" else "False"
        return f"F.lit({val})"

    def null_func(self, children):
        return "F.lit(None)"

    def field_ref(self, children):
        token = str(children[0])
        name = token[1:-1]  # strip [ ]
        return f'F.col("{name}")'

    def row_ref(self, children):
        token = str(children[0])
        # [Row-1:Revenue] → extract offset and field
        m = re.match(r"\[Row-(\d+):(.+)\]", token)
        if m:
            offset = m.group(1)
            field = m.group(2)
            return f'F.lag(F.col("{field}"), {offset})'
        return f"# TODO: unparsed row_ref {token}"

    # ── Arithmetic ─────────────────────────────────────────────

    def add(self, children):
        return f"({children[0]} + {children[1]})"

    def sub(self, children):
        return f"({children[0]} - {children[1]})"

    def mul(self, children):
        return f"({children[0]} * {children[1]})"

    def div(self, children):
        return f"({children[0]} / {children[1]})"

    def mod(self, children):
        return f"({children[0]} % {children[1]})"

    def neg(self, children):
        return f"(-{children[0]})"

    # ── Comparison ─────────────────────────────────────────────

    def _is_string_lit(self, expr: str) -> bool:
        return expr.startswith('F.lit("') and expr.endswith('")')

    def _extract_string_val(self, expr: str) -> str:
        # F.lit("Active") → Active
        m = re.match(r'^F\.lit\("(.*)"\)$', expr)
        return m.group(1) if m else ""

    def eq(self, children):
        left, _op, right = children[0], children[1], children[2]
        # Case-insensitive string comparison
        if self._is_string_lit(right):
            val = self._extract_string_val(right)
            return f'(F.lower({left}) == F.lit("{val.lower()}"))'
        if self._is_string_lit(left):
            val = self._extract_string_val(left)
            return f'(F.lit("{val.lower()}") == F.lower({right}))'
        # NULL-safe equality
        return f"({left}.eqNullSafe({right}))"

    def neq(self, children):
        left, _op, right = children[0], children[1], children[2]
        if self._is_string_lit(right):
            val = self._extract_string_val(right)
            return f'(F.lower({left}) != F.lit("{val.lower()}"))'
        if self._is_string_lit(left):
            val = self._extract_string_val(left)
            return f'(F.lit("{val.lower()}") != F.lower({right}))'
        return f"({left} != {right})"

    def gt(self, children):
        return f"({children[0]} > {children[2]})"

    def gte(self, children):
        return f"({children[0]} >= {children[2]})"

    def lt(self, children):
        return f"({children[0]} < {children[2]})"

    def lte(self, children):
        return f"({children[0]} <= {children[2]})"

    def in_expr(self, children):
        value = children[0]
        # children[1] is IN token, rest are args
        args = []
        for c in children[1:]:
            if isinstance(c, Token):
                continue
            if isinstance(c, list):
                args = c
            else:
                args.append(c)
        values_str = ", ".join(str(a) for a in args)
        return f"{value}.isin({values_str})"

    # ── Logical ────────────────────────────────────────────────

    def or_expr(self, children):
        # children: [left, OR_token, right]
        return f"({children[0]} | {children[2]})"

    def and_expr(self, children):
        return f"({children[0]} & {children[2]})"

    def not_expr(self, children):
        # children: [NOT_token, expr]
        return f"(~{children[1]})"

    # ── IF / ELSEIF / ELSE ────────────────────────────────────

    def if_expr(self, children):
        # children: IF, cond, THEN, then_val, *[elseif_clause...], ELSE, else_val, ENDIF
        # Filter out keyword tokens
        parts = []
        for c in children:
            if isinstance(c, Token):
                continue
            parts.append(c)

        # parts[0] = condition, parts[1] = then_val, ..., last = else_val
        # elseif clauses are tuples (cond, val)
        cond = parts[0]
        then_val = parts[1]
        elseifs = []
        else_val = parts[-1]

        for p in parts[2:-1]:
            # elseif_clause returns a tuple
            if isinstance(p, tuple):
                elseifs.append(p)

        result = f"F.when({cond}, {then_val})"
        for ei_cond, ei_val in elseifs:
            result += f".when({ei_cond}, {ei_val})"
        result += f".otherwise({else_val})"
        return result

    def elseif_clause(self, children):
        # children: ELSEIF_token, cond, THEN_token, val
        parts = [c for c in children if not isinstance(c, Token)]
        return (parts[0], parts[1])

    # ── Date format conversion ───────────────────────────────────

    _DT_FMT_MAP = {
        "%Y": "yyyy",
        "%y": "yy",
        "%m": "MM",
        "%d": "dd",
        "%H": "HH",
        "%M": "mm",
        "%S": "ss",
        "%p": "a",
        "%B": "MMMM",
        "%b": "MMM",
        "%A": "EEEE",
        "%a": "EEE",
    }

    def _convert_dt_format(self, fmt):
        result = fmt
        for ayx, spark in self._DT_FMT_MAP.items():
            result = result.replace(ayx, spark)
        return result

    # ── Function calls ─────────────────────────────────────────

    def func_call(self, children):
        func_name = str(children[0])
        args = children[1] if len(children) > 1 else []
        if not isinstance(args, list):
            args = []

        func_lower = func_name.lower()

        # Special-case functions
        if func_lower == "isnull":
            return f"{args[0]}.isNull()"
        if func_lower == "isempty":
            return f'({args[0]} == F.lit(""))'
        if func_lower == "iif":
            cond, t, f = args[0], args[1], args[2]
            return f"F.when({cond}, {t}).otherwise({f})"
        if func_lower == "contains":
            col, val = args[0], args[1]
            inner_val = self._extract_string_val(val)
            return f'F.lower({col}).contains("{inner_val.lower()}")'
        if func_lower == "startswith":
            return f"{args[0]}.startswith({args[1]})"
        if func_lower == "endswith":
            return f"{args[0]}.endswith({args[1]})"
        if func_lower == "left":
            return f"F.substring({args[0]}, 1, {args[1]})"
        if func_lower == "right":
            return f"F.substring({args[0]}, -{args[1]}, {args[1]})"
        if func_lower == "substring":
            # 0-based → 1-based: offset start by +1
            start_expr = args[1]
            # Try to evaluate numeric start
            m = re.match(r"F\.lit\((\d+)\)", start_expr)
            if m:
                start_val = int(m.group(1)) + 1
                return f"F.substring({args[0]}, {start_val}, {args[2]})"
            return (
                f"F.substring({args[0]}, ({start_expr} + F.lit(1)), {args[2]})"
            )
        if func_lower == "findstring":
            return f"(F.locate({args[1]}, {args[0]}) - 1)"
        if func_lower == "tostring":
            return f'{args[0]}.cast("string")'
        if func_lower == "tonumber":
            return f'{args[0]}.cast("double")'
        if func_lower == "regex_match":
            return f"{args[0]}.rlike({args[1]})"
        if func_lower == "getword":
            return f'F.split({args[0]}, " ").getItem({args[1]})'
        if func_lower == "datetimenow":
            return "F.current_timestamp()"

        # Switch
        if func_lower == "switch":
            # Switch(field, default, val1, result1, val2, result2, ...)
            field_expr = args[0]
            default_expr = args[1]
            pairs = list(zip(args[2::2], args[3::2]))
            result = ""
            for val, res in pairs:
                if result:
                    result += f".when({field_expr} == {val}, {res})"
                else:
                    result = f"F.when({field_expr} == {val}, {res})"
            result += f".otherwise({default_expr})"
            return result

        # Conversion
        if func_lower == "tointeger":
            return f'{args[0]}.cast("int")'
        if func_lower == "todate":
            return f'{args[0]}.cast("date")'
        if func_lower == "todatetime":
            return f'{args[0]}.cast("timestamp")'

        # Null handling
        if func_lower == "coalesce":
            return f"F.coalesce({', '.join(args)})"
        if func_lower == "ifnull":
            return f"F.coalesce({args[0]}, {args[1]})"
        if func_lower == "nullif":
            return f"F.when({args[0]} == {args[1]}, F.lit(None)).otherwise({args[0]})"

        # DateTime — format strings must be plain strings, NOT F.lit()
        if func_lower == "datetimeformat":
            fmt = (
                self._extract_string_val(args[1])
                if len(args) > 1 and self._is_string_lit(args[1])
                else "yyyy-MM-dd"
            )
            spark_fmt = self._convert_dt_format(fmt)
            return f'F.date_format({args[0]}, "{spark_fmt}")'

        if func_lower == "datetimeparse":
            fmt = (
                self._extract_string_val(args[1])
                if len(args) > 1 and self._is_string_lit(args[1])
                else "yyyy-MM-dd"
            )
            spark_fmt = self._convert_dt_format(fmt)
            return f'F.to_timestamp({args[0]}, "{spark_fmt}")'

        if func_lower == "datetimeadd":
            dt, interval = args[0], args[1]
            unit = (
                self._extract_string_val(args[2]).lower()
                if len(args) > 2 and self._is_string_lit(args[2])
                else "day"
            )
            if unit in ("day", "days"):
                return f"F.date_add({dt}, {interval})"
            elif unit in ("month", "months"):
                return f"F.add_months({dt}, {interval})"
            elif unit in ("year", "years"):
                return f"F.add_months({dt}, ({interval}) * 12)"
            return f"F.date_add({dt}, {interval})"

        if func_lower == "datetimediff":
            return f"F.datediff({args[0]}, {args[1]})"

        if func_lower == "datetimetoday":
            return "F.current_date()"

        if func_lower in ("datetimeyear", "year"):
            return f"F.year({args[0]})"
        if func_lower in ("datetimemonth", "month"):
            return f"F.month({args[0]})"
        if func_lower in ("datetimeday", "day"):
            return f"F.dayofmonth({args[0]})"
        if func_lower in ("datetimehour", "hour"):
            return f"F.hour({args[0]})"
        if func_lower in ("datetimeminutes", "minute"):
            return f"F.minute({args[0]})"
        if func_lower in ("datetimeseconds", "second"):
            return f"F.second({args[0]})"
        if func_lower in ("datetimedayofweek", "dayofweek"):
            return f"F.dayofweek({args[0]})"

        if func_lower == "datetimefirstofmonth":
            return f"F.date_trunc('month', {args[0]})"

        if func_lower == "datetimetrim":
            unit = (
                self._extract_string_val(args[1])
                if len(args) > 1 and self._is_string_lit(args[1])
                else "day"
            )
            return f"F.date_trunc('{unit}', {args[0]})"

        # String extras
        if func_lower == "countwords":
            return f'F.size(F.split(F.trim({args[0]}), "\\\\s+"))'
        if func_lower == "replace":
            return f"F.regexp_replace({args[0]}, {args[1]}, {args[2]})"
        if func_lower == "replacefirst":
            return f"F.regexp_replace({args[0]}, {args[1]}, {args[2]})"

        # Test
        if func_lower == "isnumber":
            return f'{args[0]}.cast("double").isNotNull()'
        if func_lower == "isinteger":
            return f'{args[0]}.cast("int").isNotNull()'

        # Mid (alias for Substring, 0-based)
        if func_lower == "mid":
            start = args[1]
            m = re.match(r"F\.lit\((\d+)\)", start)
            if m:
                start_val = int(m.group(1)) + 1
                return f"F.substring({args[0]}, {start_val}, {args[2]})"
            return f"F.substring({args[0]}, ({start} + F.lit(1)), {args[2]})"

        # Direct-mapped functions
        if func_lower in _DIRECT_MAP:
            pyspark_func = _DIRECT_MAP[func_lower]
            args_str = ", ".join(args)
            return f"{pyspark_func}({args_str})"

        # Unknown function
        args_str = ", ".join(args)
        return f"# TODO: unmapped function {func_name}({args_str})"

    def func_args(self, children):
        return list(children)


def transpile_expression(expr: str) -> str:
    """Parse Alteryx expression and return PySpark column expression string."""
    tree = parse_expression(expr)
    emitter = PySparkEmitter()
    return emitter.transform(tree)
