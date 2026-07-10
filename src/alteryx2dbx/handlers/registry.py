from __future__ import annotations

from alteryx2dbx.parser.models import AlteryxTool

from alteryx2dbx.handlers.base import ToolHandler, UnsupportedHandler


class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, type[ToolHandler]] = {}
        self._type_handlers: dict[str, type[ToolHandler]] = {}
        self._prefix_handlers: dict[str, type[ToolHandler]] = {}

    def register(self, plugin: str, handler_cls: type[ToolHandler]):
        self._handlers[plugin] = handler_cls

    def register_type(self, tool_type: str, handler_cls: type[ToolHandler]):
        self._type_handlers[tool_type] = handler_cls

    def register_prefix(self, prefix: str, handler_cls: type[ToolHandler]):
        self._prefix_handlers[prefix] = handler_cls

    def get(self, tool: AlteryxTool) -> ToolHandler:
        handler_cls = self._handlers.get(tool.plugin)
        if handler_cls:
            return handler_cls()
        handler_cls = self._type_handlers.get(tool.tool_type)
        if handler_cls:
            return handler_cls()
        for prefix, cls in self._prefix_handlers.items():
            if tool.plugin.startswith(prefix) or tool.tool_type.startswith(
                prefix
            ):
                return cls()
        return UnsupportedHandler()


_registry = HandlerRegistry()


def get_handler(tool: AlteryxTool) -> ToolHandler:
    return _registry.get(tool)


def register_handler(plugin: str, handler_cls: type[ToolHandler]):
    _registry.register(plugin, handler_cls)


def register_type_handler(tool_type: str, handler_cls: type[ToolHandler]):
    _registry.register_type(tool_type, handler_cls)


def register_prefix_handler(prefix: str, handler_cls: type[ToolHandler]):
    _registry.register_prefix(prefix, handler_cls)
