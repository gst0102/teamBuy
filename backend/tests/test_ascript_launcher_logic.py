"""Pure checks for the AScript unified-launcher safety boundary."""

import ast
from pathlib import Path


def _launcher_function(name):
    source = Path(__file__).resolve().parents[2] / "automation/ascript/__init__.py"
    module = ast.parse(source.read_text())
    function = next(item for item in module.body if isinstance(item, ast.FunctionDef) and item.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


def test_scan_only_switch_is_sticky_and_reported_in_config():
    merge_scan_config = _launcher_function("_merge_scan_config")
    state = {"scanOnly": False, "scanConfig": {"searchPrefixes": [], "scanOnly": False}}

    merge_scan_config(state, {"searchPrefixes": ["g10"], "scanOnly": True})
    assert state["scanOnly"] is True
    assert state["scanConfig"] == {"searchPrefixes": ["g10"], "scanOnly": True}

    # A later slot/config response must not clear a safety decision already
    # made by an earlier slot.
    merge_scan_config(state, {"searchPrefixes": ["c10"], "scanOnly": False})
    assert state["scanOnly"] is True
    assert state["scanConfig"] == {"searchPrefixes": ["c10"], "scanOnly": True}
