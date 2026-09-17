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
    selected = {
        "_search_empty_result_marker",
        "_search_query_persisted",
        "_search_page_signature",
        "_search_input_item",
        "_search_input_has_text",
        "_tree_has_exact_text",
    }
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
        "SEARCH_PAGE_MARKER": "页面设置",
        "SEARCH_PAGE_KEYWORDS": ("搜索指定内容", "朋友圈", "公众号", "小程序", "视频号"),
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
    assert 'prefix.lower().startswith("c")' in source_text
    assert "_search_query_persisted(prefix)" in source_text


def test_query_persisted_accepts_non_group_search_sections(inventory_logic):
    tree = {
        "packageName": "com.tencent.mm",
        "visible": True,
        "childs": [
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "type": "EditText",
                "editable": True,
                "text": "c10",
                "id": "search_src_text",
                "rect": [40, 120, 700, 210],
            },
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "聊天记录",
                "rect": [40, 800, 300, 860],
            },
        ],
    }

    def walk(value, parents=None):
        parents = parents or []
        if isinstance(value, dict):
            current = parents + [value]
            yield current
            for child in value.get("childs") or []:
                yield from walk(child, current)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child, parents)

    inventory_logic["_dump"] = lambda mode: tree
    inventory_logic["_walk"] = walk
    assert inventory_logic["_search_query_persisted"]("c10") is True
