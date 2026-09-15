"""只检查 AScript 扫描器的纯控件树判定，不导入或运行手机 API。"""
import ast
from pathlib import Path
import re

import pytest


@pytest.fixture
def inventory_logic():
    source = (
        Path(__file__).resolve().parents[2]
        / "automation/ascript/wechat_group_inventory/__init__.py"
    )
    names = {
        "_walk",
        "_rect",
        "_valid_rect",
        "_search_input_item",
        "_tree_has_top_text",
        "_truthy_tree_value",
        "_tree_tab_is_selected",
        "_wechat_home_tree_signature",
        "_more_group_link_rects",
        "_resolve_more_group_link_rect",
        "_target_group_row_rect",
        "_clickable_ancestor",
        "_target_group_rows",
        "_target_group_signature",
    }
    module = ast.parse(source.read_text())
    module.body = [
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name in names
    ]
    namespace = {
        "re": re,
        "UI_MODE": 6,
        "WECHAT_PACKAGE": "com.tencent.mm",
        "GROUP_CODE_PATTERN": re.compile(r"^[gc]\d{1,8}$", re.IGNORECASE),
        "_device_size": lambda: (1080, 2400),
        "_dump": lambda _mode=None: {},
    }
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


def _home_tree():
    return {
        "childs": [
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "搜索",
                "rect": {"left": 820, "top": 99, "right": 950, "bottom": 229},
            },
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "微信",
                "rect": {"left": 100, "top": 2340, "right": 200, "bottom": 2384},
            },
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "我",
                "rect": {"left": 900, "top": 2340, "right": 980, "bottom": 2384},
            },
        ]
    }


def test_home_signature_preserves_verified_tab_search_fallback_with_back_control(inventory_logic):
    tree = _home_tree()
    assert inventory_logic["_wechat_home_tree_signature"](tree) is True

    # This WeChat build can expose a back control on the already-verified
    # home, so it must not override the bottom-tabs-plus-search fallback.
    tree["childs"].append(
        {
            "packageName": "com.tencent.mm",
            "visible": True,
            "type": "ImageView",
            "id": "com.tencent.mm:id/actionbar_up_indicator_btn",
            "desc": "返回",
            "rect": {"left": 0, "top": 99, "right": 113, "bottom": 229},
        }
    )
    assert inventory_logic["_wechat_home_tree_signature"](tree) is True


def test_home_signature_still_rejects_explicit_sibling_tab_and_search_editor(inventory_logic):
    tree = _home_tree()
    tree["childs"].append(
        {
            "packageName": "com.tencent.mm",
            "visible": True,
            "text": "通讯录",
            "rect": {"left": 100, "top": 132, "right": 300, "bottom": 195},
        }
    )
    assert inventory_logic["_wechat_home_tree_signature"](tree) is False

    tree = _home_tree()
    tree["childs"].append(
        {
            "packageName": "com.tencent.mm",
            "visible": True,
            "type": "EditText",
            "id": "com.tencent.mm:id/f8",
            "rect": {"left": 80, "top": 100, "right": 900, "bottom": 200},
        }
    )
    assert inventory_logic["_wechat_home_tree_signature"](tree) is False


def test_more_group_link_match_uses_its_live_text_rect_and_accepts_count_suffix(inventory_logic):
    tree = {
        "childs": [
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "更多群聊(8)",
                "rect": {"left": 80, "top": 520, "right": 330, "bottom": 600},
            },
            {
                "packageName": "com.tencent.mm",
                "visible": False,
                "text": "更多群聊(9)",
                "rect": {"left": 80, "top": 620, "right": 330, "bottom": 700},
            },
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "desc": "更多群聊",
                "rect": {"left": 80, "top": 720, "right": 330, "bottom": 800},
            },
        ]
    }
    inventory_logic["_dump"] = lambda _mode=None: tree

    assert inventory_logic["_more_group_link_rects"]() == [
        (80, 520, 330, 600),
        (80, 720, 330, 800),
    ]


def test_absent_more_group_link_is_terminal_but_ambiguous_link_stops(inventory_logic):
    resolve_link = inventory_logic["_resolve_more_group_link_rect"]
    assert resolve_link([(80, 520, 330, 600)], "c10", 3) == (80, 520, 330, 600)
    assert resolve_link([], "c10", 1) is None

    with pytest.raises(RuntimeError, match="出现多个.*无法安全点击"):
        resolve_link([(80, 520, 330, 600), (80, 620, 330, 700)], "c10", 3)


def test_same_code_and_name_rows_are_aggregated_by_live_rect_count(inventory_logic):
    def row(top):
        return {
            "packageName": "com.tencent.mm",
            "type": "LinearLayout",
            "visible": True,
            "clickable": True,
                "rect": {"left": 30, "top": top, "right": 1050, "bottom": top + 180},
            "childs": [
                {
                    "packageName": "com.tencent.mm",
                    "visible": True,
                    "text": "c1001",
                    "rect": {"left": 190, "top": top + 16, "right": 340, "bottom": top + 58},
                },
                {
                    "packageName": "com.tencent.mm",
                    "visible": True,
                    "text": "群聊名：测试群",
                    "rect": {"left": 190, "top": top + 84, "right": 620, "bottom": top + 132},
                },
            ],
        }

    tree = {
        "childs": [
            {
                "packageName": "com.tencent.mm",
                "visible": True,
                "text": "群聊",
                "rect": {"left": 40, "top": 260, "right": 220, "bottom": 310},
            },
            row(340),
            row(540),
        ]
    }
    inventory_logic["_dump"] = lambda _mode=None: tree

    rows = inventory_logic["_target_group_rows"]()
    assert len(rows) == 1
    assert rows[0]["groupCode"] == "c1001"
    assert rows[0]["groupName"] == "测试群"
    assert rows[0]["occurrenceCount"] == 2
    assert len(rows[0]["rowRects"]) == 2
    assert len(set(inventory_logic["_target_group_signature"](rows))) == 2
