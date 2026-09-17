"""Device-independent checks for the targeted WeChat inventory helpers."""
import ast
from pathlib import Path

import pytest


@pytest.fixture
def inventory_logic():
    source = Path(__file__).resolve().parents[2] / (
        "automation/ascript/wechat_group_inventory/__init__.py"
    )
    module = ast.parse(source.read_text())
    selected = {"_search_empty_result_marker"}
    module.body = [
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name in selected
    ]
    namespace = {
        "WECHAT_PACKAGE": "com.tencent.mm",
        "UI_MODE": 6,
        "SEARCH_EMPTY_RESULT_MARKERS": (
            "无搜索结果",
            "没有找到相关结果",
            "没有找到结果",
            "暂无相关结果",
            "无相关结果",
            "未找到相关结果",
        ),
        "_dump": lambda mode: {"childs": []},
        "_walk": lambda value: [],
        "_rect": lambda item: tuple(item.get("rect") or (0, 0, 0, 0)),
        "_valid_rect": lambda rect: rect[2] > rect[0] and rect[3] > rect[1],
    }
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


def test_empty_search_marker_is_a_normal_zero_row_state(inventory_logic):
    marker = "没有找到相关结果"
    tree = {
        "packageName": "com.tencent.mm",
        "visible": True,
        "childs": [{
            "packageName": "com.tencent.mm",
            "visible": True,
            "text": marker,
            "rect": [10, 400, 600, 470],
        }],
    }
    inventory_logic["_dump"] = lambda mode: tree
    inventory_logic["_walk"] = lambda value: [[value], [value, value["childs"][0]]]
    assert inventory_logic["_search_empty_result_marker"]() == marker


def test_targeted_scan_accepts_empty_marker_after_submit():
    source = Path(__file__).resolve().parents[2] / (
        "automation/ascript/wechat_group_inventory/__init__.py"
    )
    source_text = source.read_text()
    assert "or _search_empty_result_marker()" in source_text
    assert "TARGET_SEARCH_EMPTY_RESULT" in source_text
