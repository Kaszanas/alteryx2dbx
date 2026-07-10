"""Load .alteryx2dbx.yml configuration."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_config(
    start_dir: Path, *, config_path: Path | None = None
) -> dict | None:
    if config_path:
        if config_path.exists():
            return _parse_and_resolve(config_path)
        return None

    current = start_dir.resolve()
    while True:
        candidate = current / ".alteryx2dbx.yml"
        if candidate.exists():
            return _parse_and_resolve(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _parse_and_resolve(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    confluence = config.get("confluence", {})
    pat = confluence.get("pat", "")
    if not pat:
        pat = os.environ.get("CONFLUENCE_PAT", "")
    confluence["pat"] = pat

    return config
