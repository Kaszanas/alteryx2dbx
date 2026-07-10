from alteryx2dbx.generator.utils_notebook import generate_utils_notebook


def test_generates_utils_notebook(tmp_path):
    generate_utils_notebook(tmp_path)
    path = tmp_path / "_utils.py"
    assert path.exists()
    content = path.read_text()
    assert content.startswith("# Databricks notebook source")


def test_utils_has_logging(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "def log_step" in content


def test_utils_has_null_safe_join(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "def null_safe_join" in content


def test_utils_has_quality_check(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "def check_row_count" in content


def test_utils_has_safe_cast(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "def safe_cast" in content


def test_utils_has_command_separators(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "# COMMAND ----------" in content


def test_utils_has_imports(tmp_path):
    generate_utils_notebook(tmp_path)
    content = (tmp_path / "_utils.py").read_text()
    assert "import logging" in content
    assert "pyspark.sql" in content
