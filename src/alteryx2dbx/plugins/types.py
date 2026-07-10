"""Protocol classes that plugins must follow."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PluginHandler(Protocol):
    """Protocol for custom tool handlers."""

    tool_type: str

    def convert(self, tool, input_df_names: list[str]):
        """Convert an Alteryx tool to a GeneratedStep."""
        ...


@runtime_checkable
class PluginFix(Protocol):
    """Protocol for custom fix functions."""

    fix_id: str
    description: str
    severity: str
    phase: str

    def apply(self, code: str, context: dict) -> tuple[str, bool]:
        """Apply the fix. Returns (modified_code, was_applied)."""
        ...
