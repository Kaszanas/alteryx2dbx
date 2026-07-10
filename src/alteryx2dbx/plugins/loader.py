"""Plugin discovery and registration."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from importlib.metadata import entry_points
from pathlib import Path


def discover_plugins(config: dict | None = None) -> list:
    """Load plugins from 3 sources in order:

    1. Python entry_points group 'alteryx2dbx.plugins'
    2. Paths listed in config['plugins'] from .alteryx2dbx.yml
    3. ./plugins/ directory if it exists
    """
    plugins = []

    # 1. Entry points
    try:
        eps = entry_points()
        if hasattr(eps, "select"):
            group = eps.select(group="alteryx2dbx.plugins")
        else:
            group = eps.get("alteryx2dbx.plugins", [])
        for ep in group:
            try:
                module = ep.load()
                plugins.append(module)
            except Exception as e:
                print(
                    f"Warning: failed to load plugin {ep.name}: {e}",
                    file=sys.stderr,
                )
    except Exception as e:
        print(f"Warning: failed to load entry points: {e}", file=sys.stderr)

    # 2. Config-specified paths
    if config and "plugins" in config:
        for path_str in config["plugins"]:
            path = Path(path_str)
            module = _load_module_from_path(path)
            if module:
                plugins.append(module)

    # 3. Local plugins/ directory
    plugins_dir = Path.cwd() / "plugins"
    if plugins_dir.is_dir():
        for py_file in sorted(plugins_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module = _load_module_from_path(py_file)
            if module:
                plugins.append(module)

    return plugins


def _load_module_from_path(path: Path):
    """Dynamically load a Python module from a file path."""
    if not path.exists():
        return None
    try:
        module_name = f"alteryx2dbx._plugins.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
    except SystemExit:
        print(
            f"Warning: plugin {path.stem} called sys.exit(), ignoring",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        print(f"Warning: failed to load plugin {path}: {e}", file=sys.stderr)
        return None
    return None


def register_plugins(
    plugins: list, handler_registry=None, fix_registry=None
) -> dict:
    """Call registration functions on each plugin.

    Plugins can expose:
    - register_handlers(registry) -- add custom tool handlers
    - register_fixes(register_fn) -- add custom fixes via register_fix()

    Returns a summary dict of what was registered.
    """
    summary = {"handlers": 0, "fixes": 0}

    for plugin in plugins:
        if (
            hasattr(plugin, "register_handlers")
            and handler_registry is not None
        ):
            try:
                plugin.register_handlers(handler_registry)
                summary["handlers"] += 1
            except SystemExit:
                print(
                    f"Warning: plugin {getattr(plugin, '__name__', plugin)} called sys.exit() in register_handlers, ignoring",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Warning: failed to load plugin {getattr(plugin, '__name__', plugin)}: {e}",
                    file=sys.stderr,
                )

        if hasattr(plugin, "register_fixes") and fix_registry is not None:
            try:
                plugin.register_fixes(fix_registry)
                summary["fixes"] += 1
            except SystemExit:
                print(
                    f"Warning: plugin {getattr(plugin, '__name__', plugin)} called sys.exit() in register_fixes, ignoring",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Warning: failed to load plugin {getattr(plugin, '__name__', plugin)}: {e}",
                    file=sys.stderr,
                )

    return summary
