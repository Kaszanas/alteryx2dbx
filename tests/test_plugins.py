"""Tests for the plugin discovery and registration system."""

from __future__ import annotations

import sys
import types


from alteryx2dbx.plugins.loader import (
    discover_plugins,
    _load_module_from_path,
    register_plugins,
)
from alteryx2dbx.fixes import FIXES, register_fix


# ---------------------------------------------------------------------------
# _load_module_from_path
# ---------------------------------------------------------------------------


def test_load_module_from_valid_path(tmp_path):
    """Loading a valid .py file returns a module."""
    plugin_file = tmp_path / "my_plugin.py"
    plugin_file.write_text("VALUE = 42\n")

    module = _load_module_from_path(plugin_file)
    assert module is not None
    assert module.VALUE == 42
    # cleanup
    sys.modules.pop("alteryx2dbx._plugins.my_plugin", None)


def test_load_module_namespaced(tmp_path):
    """Plugin module names are namespaced under alteryx2dbx._plugins."""
    plugin_file = tmp_path / "my_ns_plugin.py"
    plugin_file.write_text("VALUE = 99\n")

    module = _load_module_from_path(plugin_file)
    assert module is not None
    assert "alteryx2dbx._plugins.my_ns_plugin" in sys.modules
    # Ensure the bare name is NOT in sys.modules (no stdlib clobbering)
    assert "my_ns_plugin" not in sys.modules
    # cleanup
    sys.modules.pop("alteryx2dbx._plugins.my_ns_plugin", None)


def test_load_module_from_nonexistent_path(tmp_path):
    """Loading a nonexistent path returns None."""
    result = _load_module_from_path(tmp_path / "does_not_exist.py")
    assert result is None


def test_load_module_from_broken_file(tmp_path):
    """Loading a file with a syntax error returns None (no crash)."""
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def oops(:\n")

    result = _load_module_from_path(bad_file)
    assert result is None


# ---------------------------------------------------------------------------
# discover_plugins — local plugins/ directory
# ---------------------------------------------------------------------------


def test_discover_plugins_from_local_dir(tmp_path, monkeypatch):
    """Discovers .py files in a local plugins/ directory."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "alpha.py").write_text("NAME = 'alpha'\n")
    (plugins_dir / "beta.py").write_text("NAME = 'beta'\n")

    monkeypatch.chdir(tmp_path)
    plugins = discover_plugins()

    assert len(plugins) >= 2
    names = [p.NAME for p in plugins if hasattr(p, "NAME")]
    assert "alpha" in names
    assert "beta" in names

    sys.modules.pop("alteryx2dbx._plugins.alpha", None)
    sys.modules.pop("alteryx2dbx._plugins.beta", None)


def test_discover_plugins_skips_private_files(tmp_path, monkeypatch):
    """Files starting with _ are skipped."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "__init__.py").write_text("")
    (plugins_dir / "_private.py").write_text("SECRET = True\n")
    (plugins_dir / "public.py").write_text("NAME = 'public'\n")

    monkeypatch.chdir(tmp_path)
    plugins = discover_plugins()

    names = [p.NAME for p in plugins if hasattr(p, "NAME")]
    assert "public" in names
    # _private and __init__ should not be loaded
    assert not any(hasattr(p, "SECRET") for p in plugins)

    sys.modules.pop("alteryx2dbx._plugins.public", None)


def test_discover_plugins_from_config(tmp_path, monkeypatch):
    """Discovers plugins specified in config['plugins']."""
    plugin_file = tmp_path / "custom_plugin.py"
    plugin_file.write_text("NAME = 'custom'\n")

    # chdir somewhere without a plugins/ dir
    monkeypatch.chdir(tmp_path)

    config = {"plugins": [str(plugin_file)]}
    plugins = discover_plugins(config)

    assert any(getattr(p, "NAME", None) == "custom" for p in plugins)
    sys.modules.pop("alteryx2dbx._plugins.custom_plugin", None)


def test_discover_plugins_no_sources(tmp_path, monkeypatch):
    """Returns empty list when no plugin sources exist."""
    monkeypatch.chdir(tmp_path)
    plugins = discover_plugins()
    assert plugins == []


# ---------------------------------------------------------------------------
# register_plugins
# ---------------------------------------------------------------------------


def test_register_plugins_with_handlers():
    """Plugin with register_handlers gets called."""
    calls = []

    plugin = types.ModuleType("test_handler_plugin")
    plugin.register_handlers = lambda reg: calls.append(("handlers", reg))

    registry_mock = object()
    summary = register_plugins([plugin], handler_registry=registry_mock)

    assert summary["handlers"] == 1
    assert len(calls) == 1
    assert calls[0] == ("handlers", registry_mock)


def test_register_plugins_with_fixes():
    """Plugin with register_fixes gets called."""
    calls = []

    plugin = types.ModuleType("test_fix_plugin")
    plugin.register_fixes = lambda fn: calls.append(("fixes", fn))

    summary = register_plugins([plugin], fix_registry=register_fix)

    assert summary["fixes"] == 1
    assert len(calls) == 1
    assert calls[0] == ("fixes", register_fix)


def test_register_plugins_with_neither():
    """Plugin with no registration functions doesn't crash."""
    plugin = types.ModuleType("empty_plugin")
    summary = register_plugins(
        [plugin], handler_registry=object(), fix_registry=register_fix
    )

    assert summary["handlers"] == 0
    assert summary["fixes"] == 0


def test_register_plugins_handler_error():
    """Plugin that raises in register_handlers doesn't crash the system."""
    plugin = types.ModuleType("bad_plugin")

    def bad_register(reg):
        raise RuntimeError("boom")

    plugin.register_handlers = bad_register
    summary = register_plugins([plugin], handler_registry=object())
    assert summary["handlers"] == 0


# ---------------------------------------------------------------------------
# Full flow: discover -> register -> verify
# ---------------------------------------------------------------------------


def test_full_flow_plugin_registers_fix(tmp_path, monkeypatch):
    """End-to-end: a plugin file registers a custom fix into FIXES."""
    fix_id = "_test_plugin_custom_fix"

    # Clean up in case of prior test leakage
    FIXES.pop(fix_id, None)

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "custom_fix.py").write_text(f'''
def _my_fix(code, context):
    return code.replace("old", "new"), "old" in code

def register_fixes(register_fn):
    register_fn(
        fix_id="{fix_id}",
        description="Test plugin fix",
        severity="info",
        fn=_my_fix,
        phase="general",
    )
''')

    monkeypatch.chdir(tmp_path)

    plugins = discover_plugins()
    assert len(plugins) >= 1

    register_plugins(plugins, fix_registry=register_fix)

    assert fix_id in FIXES
    assert FIXES[fix_id]["description"] == "Test plugin fix"

    # Verify the fix actually works
    result_code, applied = FIXES[fix_id]["fn"]("old value", {})
    assert applied is True
    assert result_code == "new value"

    # Cleanup
    FIXES.pop(fix_id, None)
    sys.modules.pop("alteryx2dbx._plugins.custom_fix", None)
