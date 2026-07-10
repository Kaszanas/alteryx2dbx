"""Tests for _config.py Databricks notebook generator."""

from alteryx2dbx.parser.models import AlteryxTool, AlteryxWorkflow
from alteryx2dbx.generator.config_notebook import generate_config_notebook


def _make_workflow(**overrides):
    """Create a minimal workflow for testing."""
    defaults = dict(
        name="test_workflow",
        version="2024.1",
        tools={},
        connections=[],
        properties={},
    )
    defaults.update(overrides)
    return AlteryxWorkflow(**defaults)


def test_generates_config_notebook(tmp_path):
    """File exists, has Databricks header, has SOURCES/OUTPUTS."""
    wf = _make_workflow(
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "/data/input.csv"},
                annotation="Load sales data",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                tool_type="DbFileOutput",
                config={"file_path": "/data/output.csv"},
                annotation="Write results",
            ),
        }
    )
    generate_config_notebook(wf, tmp_path)
    config_path = tmp_path / "_config.py"
    assert config_path.exists()
    content = config_path.read_text()
    assert "# Databricks notebook source" in content
    assert "SOURCES" in content
    assert "OUTPUTS" in content


def test_config_has_widgets(tmp_path):
    """dbutils.widgets.text for catalog, schema, env."""
    wf = _make_workflow()
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    assert 'dbutils.widgets.text("catalog"' in content
    assert 'dbutils.widgets.text("schema"' in content
    assert 'dbutils.widgets.text("env"' in content
    assert 'CATALOG = dbutils.widgets.get("catalog")' in content
    assert 'SCHEMA = dbutils.widgets.get("schema")' in content
    assert 'ENV = dbutils.widgets.get("env")' in content


def test_config_flags_network_paths(tmp_path):
    """UNC paths get TODO warnings."""
    wf = _make_workflow(
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                tool_type="DbFileInput",
                config={"file_path": "\\\\server\\share\\data.csv"},
                annotation="Network source",
            ),
        }
    )
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    assert "TODO" in content
    assert "\\\\server\\share\\data.csv" in content or "UNC" in content.upper() or "network" in content.lower()


def test_config_has_workflow_constants(tmp_path):
    """WORKFLOW_NAME and WORKFLOW_VERSION constants are present."""
    wf = _make_workflow(name="my_workflow", version="2024.2")
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    assert 'WORKFLOW_NAME = "my_workflow"' in content
    assert 'WORKFLOW_VERSION = "2024.2"' in content


def test_config_has_command_separators(tmp_path):
    """Cells separated by COMMAND separator."""
    wf = _make_workflow()
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    assert "# COMMAND ----------" in content


def test_sources_contain_load_type_tools(tmp_path):
    """SOURCES dict includes all load-type tools."""
    wf = _make_workflow(
        tools={
            1: AlteryxTool(
                tool_id=1,
                plugin="AlteryxBasePluginsGui.TextInput.TextInput",
                tool_type="TextInput",
                config={},
                annotation="Inline data",
            ),
            2: AlteryxTool(
                tool_id=2,
                plugin="AlteryxBasePluginsGui.InputData.InputData",
                tool_type="InputData",
                config={"file_path": "/tmp/input.xlsx"},
                annotation="Excel input",
            ),
            3: AlteryxTool(
                tool_id=3,
                plugin="AlteryxBasePluginsGui.DynamicInput.DynamicInput",
                tool_type="DynamicInput",
                config={"file_path": "/tmp/dynamic.csv"},
                annotation="Dynamic load",
            ),
        }
    )
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    # All three tool IDs should appear in SOURCES
    assert "1:" in content or "1 :" in content
    assert "2:" in content or "2 :" in content
    assert "3:" in content or "3 :" in content


def test_outputs_contain_output_type_tools(tmp_path):
    """OUTPUTS dict includes output-type tools only."""
    wf = _make_workflow(
        tools={
            10: AlteryxTool(
                tool_id=10,
                plugin="AlteryxBasePluginsGui.OutputData.OutputData",
                tool_type="OutputData",
                config={"file_path": "/tmp/out.csv"},
                annotation="CSV output",
            ),
        }
    )
    generate_config_notebook(wf, tmp_path)
    content = (tmp_path / "_config.py").read_text()
    assert "10:" in content or "10 :" in content
    assert "OUTPUTS" in content
