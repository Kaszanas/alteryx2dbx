import json
import zipfile
from pathlib import Path
from click.testing import CliRunner
from alteryx2dbx.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

MINIMAL_YXMD = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Properties><MetaInfo><Name>ParseTest</Name></MetaInfo></Properties>
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput"/>
      <Properties><Configuration><File>data/input.csv</File></Configuration></Properties>
    </Node>
  </Nodes>
  <Connections></Connections>
</AlteryxDocument>
"""


def test_cli_convert_single_file(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", str(FIXTURES / "simple_filter.yxmd"), "-o", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / "simple_filter" / "01_load_sources.py").exists()


def test_cli_convert_directory(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main, ["convert", str(FIXTURES), "-o", str(tmp_path)]
    )
    assert result.exit_code == 0


def test_cli_analyze():
    runner = CliRunner()
    result = runner.invoke(
        main, ["analyze", str(FIXTURES / "simple_filter.yxmd")]
    )
    assert result.exit_code == 0
    assert "simple_filter" in result.output


def test_cli_tools():
    runner = CliRunner()
    result = runner.invoke(main, ["tools"])
    assert result.exit_code == 0
    assert "Filter" in result.output


def test_parse_yxmd(tmp_path):
    """Parse a single .yxmd file and verify manifest.json is produced."""
    wf_file = tmp_path / "ParseTest.yxmd"
    wf_file.write_text(MINIMAL_YXMD, encoding="utf-8")
    out_file = tmp_path / "manifest.json"

    runner = CliRunner()
    result = runner.invoke(main, ["parse", str(wf_file), "-o", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["name"] == "ParseTest"


def test_parse_yxzp(tmp_path):
    """Parse a .yxzp bundle and verify manifest.json is produced."""
    wf_content = MINIMAL_YXMD
    yxzp_path = tmp_path / "bundle.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("ParseTest.yxmd", wf_content)

    out_file = tmp_path / "manifest.json"
    runner = CliRunner()
    result = runner.invoke(main, ["parse", str(yxzp_path), "-o", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["name"] == "ParseTest"


def test_parse_batch(tmp_path):
    """Parse a directory of .yxmd files and verify individual manifests."""
    src_dir = tmp_path / "workflows"
    src_dir.mkdir()
    for i in range(3):
        content = MINIMAL_YXMD.replace("ParseTest", f"Workflow{i}")
        (src_dir / f"wf{i}.yxmd").write_text(content, encoding="utf-8")

    out_dir = tmp_path / "manifests"
    runner = CliRunner()
    result = runner.invoke(main, ["parse", str(src_dir), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) == 3


def test_generate_from_manifest(tmp_path):
    """Generate production notebooks from a manifest.json."""
    manifest = {
        "name": "gen_test",
        "version": "2024.1",
        "tools": {
            "1": {
                "tool_id": 1,
                "plugin": "AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                "tool_type": "DbFileInput",
                "config": {"file_path": "input.csv"},
                "annotation": "Input",
                "input_fields": [],
                "output_fields": [],
            },
            "2": {
                "tool_id": 2,
                "plugin": "AlteryxBasePluginsGui.Filter.Filter",
                "tool_type": "Filter",
                "config": {"expression": "[Revenue] > 1000"},
                "annotation": "Filter",
                "input_fields": [],
                "output_fields": [],
            },
            "3": {
                "tool_id": 3,
                "plugin": "AlteryxBasePluginsGui.DbFileOutput.DbFileOutput",
                "tool_type": "DbFileOutput",
                "config": {"file_path": "output.csv"},
                "annotation": "Output",
                "input_fields": [],
                "output_fields": [],
            },
        },
        "connections": [
            {
                "source_tool_id": 1,
                "source_anchor": "Output",
                "target_tool_id": 2,
                "target_anchor": "Input",
            },
            {
                "source_tool_id": 2,
                "source_anchor": "True",
                "target_tool_id": 3,
                "target_anchor": "Input",
            },
        ],
        "properties": {},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    out_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(
        main, ["generate", str(manifest_path), "-o", str(out_dir)]
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "gen_test" / "_config.py").exists()
    assert (out_dir / "gen_test" / "_utils.py").exists()
    assert (out_dir / "gen_test" / "05_orchestrate.py").exists()


def test_analyze_yxzp(tmp_path):
    yxzp = tmp_path / "test.yxzp"
    with zipfile.ZipFile(yxzp, "w") as zf:
        zf.writestr("inner.yxmd", MINIMAL_YXMD)
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(yxzp)])
    assert result.exit_code == 0
    assert "Coverage:" in result.output
