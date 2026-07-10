"""Serialize and load AlteryxWorkflow IR as JSON manifests."""

from __future__ import annotations

import json
from pathlib import Path

from alteryx2dbx.parser.models import AlteryxWorkflow


def serialize_manifest(workflow: AlteryxWorkflow, path: Path) -> None:
    """Write a workflow IR to *path* as indented JSON."""
    path.write_text(
        json.dumps(workflow.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_manifest(path: Path) -> AlteryxWorkflow:
    """Read a JSON manifest and return an AlteryxWorkflow."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return AlteryxWorkflow.from_dict(data)
