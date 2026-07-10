"""Unpack .yxmd and .yxzp workflow sources.

For .yxmd files, the path is returned as-is.  For .yxzp bundles (which are
zip archives), the archive is extracted to a temporary directory.  The primary
workflow, bundled macros (.yxmc), and other asset files are catalogued in the
returned :class:`UnpackResult`.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UnpackResult:
    """Result of unpacking a workflow source."""

    workflow_path: Path
    assets: list[Path] = field(default_factory=list)
    macros: list[Path] = field(default_factory=list)
    _temp_dir: Path | None = field(default=None, repr=False)

    def cleanup(self) -> None:
        """Remove the temporary directory, if one was created."""
        if self._temp_dir is not None and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)


def unpack_source(source: Path) -> UnpackResult:
    """Unpack a workflow source and return an :class:`UnpackResult`.

    Parameters
    ----------
    source:
        Path to a ``.yxmd`` workflow file or a ``.yxzp`` bundle.

    Returns
    -------
    UnpackResult
        Contains the primary workflow path, detected macros, and other assets.

    Raises
    ------
    FileNotFoundError
        If *source* does not exist.
    ValueError
        If the file extension is not ``.yxmd`` or ``.yxzp``, or if a
        ``.yxzp`` archive contains no ``.yxmd`` file.
    """
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    suffix = source.suffix.lower()

    if suffix == ".yxmd":
        return UnpackResult(workflow_path=source)

    if suffix == ".yxzp":
        return _unpack_yxzp(source)

    raise ValueError(
        f"Unsupported file extension: {suffix!r}. Expected .yxmd or .yxzp"
    )


def _unpack_yxzp(source: Path) -> UnpackResult:
    """Extract a .yxzp bundle and catalogue its contents."""
    temp_dir = Path(tempfile.mkdtemp(prefix="alteryx2dbx_"))

    with zipfile.ZipFile(source, "r") as zf:
        zf.extractall(temp_dir)

    # Collect all extracted files
    all_files = [p for p in temp_dir.rglob("*") if p.is_file()]

    # Find .yxmd files, preferring root-level ones
    yxmd_files = [p for p in all_files if p.suffix.lower() == ".yxmd"]
    if not yxmd_files:
        shutil.rmtree(temp_dir)
        raise ValueError(f"No .yxmd workflow found inside {source.name}")

    # Prefer root-level: sort by depth (number of parts relative to temp_dir)
    yxmd_files.sort(key=lambda p: len(p.relative_to(temp_dir).parts))
    primary = yxmd_files[0]

    # Collect macros (.yxmc)
    macros = [p for p in all_files if p.suffix.lower() == ".yxmc"]

    # Assets: everything that is not the primary workflow and not a macro
    non_asset_set = {primary} | set(macros)
    # Also exclude other .yxmd files from assets
    non_asset_set.update(yxmd_files)
    assets = [p for p in all_files if p not in non_asset_set]

    return UnpackResult(
        workflow_path=primary,
        assets=assets,
        macros=macros,
        _temp_dir=temp_dir,
    )
