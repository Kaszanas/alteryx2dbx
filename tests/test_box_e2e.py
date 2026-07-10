from pathlib import Path
from click.testing import CliRunner
from alteryx2dbx.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_box_workflow_convert_full(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "convert",
            str(FIXTURES / "box_workflow.yxmd"),
            "-o",
            str(tmp_path),
            "--full",
        ],
    )
    assert result.exit_code == 0, result.output
    wf_dir = tmp_path / "box_workflow"
    assert (wf_dir / "01_load_sources.py").exists()
    assert (wf_dir / "02_transformations.py").exists()
    assert (wf_dir / "03_write_outputs.py").exists()
    assert (wf_dir / "_config.py").exists()
    assert (wf_dir / "_utils.py").exists()

    load_content = (wf_dir / "01_load_sources.py").read_text()
    assert "box_client.file" in load_content
    assert "123456789" in load_content

    output_content = (wf_dir / "03_write_outputs.py").read_text()
    assert "update_contents_with_stream" in output_content

    config_content = (wf_dir / "_config.py").read_text()
    assert "BOX_SECRET_SCOPE" in config_content

    utils_content = (wf_dir / "_utils.py").read_text()
    assert "get_box_client" in utils_content


def test_box_workflow_analyze():
    runner = CliRunner()
    result = runner.invoke(
        main, ["analyze", str(FIXTURES / "box_workflow.yxmd")]
    )
    assert result.exit_code == 0
    assert "[OK]" in result.output
    assert "box_input" in result.output.lower() or "Box" in result.output
