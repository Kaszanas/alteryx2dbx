"""Tests for .yxzp unpacker and .yxmd passthrough."""

import zipfile
from pathlib import Path

import pytest

from alteryx2dbx.parser.unpacker import unpack_source


def test_yxmd_passthrough(tmp_path: Path):
    """A .yxmd file is returned as-is with no temp dir or assets."""
    yxmd = tmp_path / "workflow.yxmd"
    yxmd.write_text("<AlteryxDocument/>")

    result = unpack_source(yxmd)

    assert result.workflow_path == yxmd
    assert result.assets == []
    assert result.macros == []
    assert result._temp_dir is None


def test_yxzp_extraction(tmp_path: Path):
    """A .yxzp is unzipped; primary .yxmd, macros, and assets are detected."""
    # Build a fake .yxzp (it's just a zip archive)
    yxzp_path = tmp_path / "bundle.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("workflow.yxmd", "<AlteryxDocument/>")
        zf.writestr("macros/helper.yxmc", "<AlteryxDocument/>")
        zf.writestr("data/input.csv", "a,b\n1,2\n")

    result = unpack_source(yxzp_path)

    assert result.workflow_path.name == "workflow.yxmd"
    assert result.workflow_path.exists()
    assert len(result.macros) == 1
    assert result.macros[0].name == "helper.yxmc"
    assert len(result.assets) == 1
    assert result.assets[0].name == "input.csv"
    assert result._temp_dir is not None

    result.cleanup()


def test_yxzp_prefers_root_level_yxmd(tmp_path: Path):
    """When multiple .yxmd files exist, prefer the root-level one."""
    yxzp_path = tmp_path / "bundle.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("main.yxmd", "<AlteryxDocument/>")
        zf.writestr("subfolder/other.yxmd", "<AlteryxDocument/>")

    result = unpack_source(yxzp_path)

    # Root-level main.yxmd should be chosen over subfolder/other.yxmd
    assert result.workflow_path.name == "main.yxmd"
    # The parent of the workflow should be the temp dir root (not a subfolder)
    assert result.workflow_path.parent == result._temp_dir

    result.cleanup()


def test_yxzp_cleanup(tmp_path: Path):
    """cleanup() removes the temp directory."""
    yxzp_path = tmp_path / "bundle.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("workflow.yxmd", "<AlteryxDocument/>")

    result = unpack_source(yxzp_path)
    temp_dir = result._temp_dir
    assert temp_dir is not None
    assert temp_dir.exists()

    result.cleanup()

    assert not temp_dir.exists()


def test_yxzp_cleanup_idempotent(tmp_path: Path):
    """Calling cleanup() twice does not raise."""
    yxzp_path = tmp_path / "bundle.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("workflow.yxmd", "<AlteryxDocument/>")

    result = unpack_source(yxzp_path)
    result.cleanup()
    result.cleanup()  # Should not raise


def test_unsupported_extension(tmp_path: Path):
    """Non-.yxmd/.yxzp extensions raise ValueError."""
    bad_file = tmp_path / "workflow.txt"
    bad_file.write_text("hello")

    with pytest.raises(ValueError, match="Unsupported"):
        unpack_source(bad_file)


def test_yxmd_passthrough_nonexistent():
    """A nonexistent .yxmd raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        unpack_source(Path("nonexistent.yxmd"))


def test_yxzp_no_yxmd_inside(tmp_path: Path):
    """A .yxzp with no .yxmd inside raises ValueError."""
    yxzp_path = tmp_path / "empty.yxzp"
    with zipfile.ZipFile(yxzp_path, "w") as zf:
        zf.writestr("readme.txt", "no workflow here")

    with pytest.raises(ValueError, match="No .yxmd"):
        unpack_source(yxzp_path)
