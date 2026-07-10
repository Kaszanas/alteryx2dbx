"""Tests for safe Python string-literal escaping in generated notebook code."""

import warnings
from pathlib import Path

from alteryx2dbx.generator.notebook import generate_notebooks
from alteryx2dbx.handlers.base import is_unc_path, py_str_literal
from alteryx2dbx.parser.xml_parser import parse_yxmd

FIXTURES = Path(__file__).parent / "fixtures"


class TestPyStrLiteral:
    def test_escapes_backslashes(self):
        assert py_str_literal("\\\\server\\data\\customers.xlsx") == repr(
            "\\\\server\\data\\customers.xlsx"
        )

    def test_round_trips(self):
        original = "\\\\server\\data\\customers.xlsx"
        literal = py_str_literal(original)
        assert eval(literal) == original


class TestIsUncPath:
    def test_backslash_backslash_prefix(self):
        assert is_unc_path("\\\\server\\data\\customers.xlsx") is True

    def test_forward_slash_slash_prefix(self):
        assert is_unc_path("//server/data/customers.xlsx") is True

    def test_regular_path_not_unc(self):
        assert is_unc_path("/dbfs/mnt/data/customers.csv") is False


class TestGeneratedNotebookIsValidPython:
    def test_no_invalid_escape_sequence_warnings(self, tmp_path):
        wf = parse_yxmd(FIXTURES / "simple_filter.yxmd")
        generate_notebooks(wf, tmp_path)
        wf_dir = tmp_path / "simple_filter"

        for py_file in wf_dir.glob("*.py"):
            source = py_file.read_text()
            with warnings.catch_warnings():
                warnings.simplefilter("error", SyntaxWarning)
                compile(source, str(py_file), "exec")

    def test_unc_path_todo_in_load_sources(self, tmp_path):
        wf = parse_yxmd(FIXTURES / "simple_filter.yxmd")
        generate_notebooks(wf, tmp_path)
        content = (
            tmp_path / "simple_filter" / "01_load_sources.py"
        ).read_text()
        assert "UNC/network path" in content
        assert "migrate to cloud storage" in content

    def test_unc_path_todo_in_orchestrate(self, tmp_path):
        wf = parse_yxmd(FIXTURES / "simple_filter.yxmd")
        generate_notebooks(wf, tmp_path)
        content = (tmp_path / "simple_filter" / "03_orchestrate.py").read_text()
        assert "UNC/network path" in content
        assert "migrate to cloud storage" in content
