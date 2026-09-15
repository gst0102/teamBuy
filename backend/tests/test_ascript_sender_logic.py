"""只测试设备无关的生产函数；不导入或模拟执行 AScript 手机工程。"""
import ast
from pathlib import Path
import re
from types import SimpleNamespace

import pytest


@pytest.fixture
def sender_logic():
    source = Path(__file__).resolve().parents[2] / "automation/ascript/wechat_marketing_sender/__init__.py"
    class SenderStopStub(RuntimeError):
        def __init__(self, message, **_kwargs):
            super().__init__(message)

    names = {
        "_rect", "_valid_rect", "_walk", "_chat_header_rects", "_header_has",
        "_clickable_ancestor", "_wechat_actionbar_back_rects", "_forward_outcome_counts",
        "_material_chat_history_rect", "_card_scroll_budget", "_is_wechat_chat_list",
        "_validate_task", "_search_input_item", "_tree_has_exact_text",
        "_search_page_signature", "_wechat_home_tree_signature",
        "_tree_has_top_text", "_tree_tab_is_selected", "_truthy_tree_value",
        "_scroll_chat_to_older", "_is_explicit_missing_target_status",
        "_queue_empty_reason", "_current_duplicate_result_rect",
        "_same_name_result_count_options",
        "_expand_same_name_targets_to_observed_count", "_request_device_batch_run",
        "_validate_test_configuration", "_send_mode_enabled",
    }
    module = ast.parse(source.read_text())
    module.body = [item for item in module.body if isinstance(item, ast.FunctionDef) and item.name in names]
    namespace = {
        "re": re, "WECHAT_PACKAGE": "com.tencent.mm", "MATERIAL_GROUP_NAME": "卡片素材群",
        "_device_size": lambda: (1080, 2400),
        "Ocr": SimpleNamespace(find_all=lambda **kwargs: []),
        "SEARCH_PAGE_MARKER": "页面设置",
        "SEARCH_PAGE_KEYWORDS": ("搜索指定内容", "朋友圈", "公众号", "小程序", "视频号"),
        "GROUP_BATCH_FUNCTION_ID": "wechat.send_group_batch", "TEST_MODE": "TEST_ONLY",
        "TEST_GROUP_CODE": "c1001", "TEST_CARD_ID": "act-001",
        "ACCOUNT_SLOTS": {"wechat-one": 0}, "DEVICE_ID": "android-01",
        "time": SimpleNamespace(time=lambda: 123.0),
        "ACTIVE_WECHAT_ACCOUNT_ID": "wechat-one",
        "SenderStop": SenderStopStub,
    }
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("visible,expected", [(["act-002"], 2), (["act-100"], 100), (["act-200"], 200), ([], 1)])
def test_card_budget_uses_number_without_twelve_floor_or_120_cap(sender_logic, visible, expected):
    assert sender_logic["_card_scroll_budget"]("act-001", visible) == expected


def test_send_mode_requires_explicit_test_configuration(sender_logic):
    sender_logic["TEST_MODE"] = ""
    assert sender_logic["_send_mode_enabled"]() is False
    sender_logic["TEST_MODE"] = "TEST_SINGLE"
    assert sender_logic["_send_mode_enabled"]() is True


@pytest.mark.parametrize("ocr_header", [False, True])
def test_material_history_accepts_same_title_evidence_as_header_check(sender_logic, ocr_header):
    header = {"text": "卡片素材群(4)", "rect": [300, 100, 750, 220]}
    tree = {"packageName": "com.tencent.mm", "rect": [0, 0, 1080, 2400], "childs": [
        {"type": "FrameLayout", "rect": [0, 250, 1080, 2150], "childs": [
            {"text": "act-002", "rect": [100, 1000, 300, 1100]},
        ]},
        {"type": "EditText", "rect": [100, 2200, 850, 2300]},
    ]}
    if ocr_header:
        sender_logic["Ocr"].find_all = lambda **kwargs: [header]
    else:
        tree["childs"].append(header)
    sender_logic["_dump"] = lambda: tree
    assert sender_logic["_header_has"]("卡片素材群")
    region, evidence = sender_logic["_material_chat_history_rect"](tree)
    assert region == (0, 250, 1080, 2150)
    assert "ancestor_fallback=true" in evidence
    # 标题存在也不能把整个屏幕当成历史滑动区域。
    tree["childs"][0]["childs"] = []
    assert sender_logic["_material_chat_history_rect"](tree)[0] is None


def test_home_detection_calls_zero_argument_dump(sender_logic):
    tree = {"home": True}
    sender_logic["_dump"] = lambda: tree
    sender_logic["_wechat_home_tree_signature"] = lambda actual: actual is tree
    assert sender_logic["_is_wechat_chat_list"]() is True


def test_home_signature_uses_tab_selection_or_tab_and_search_fallback(sender_logic):
    def home_tree(chat_selected=None, me_selected=None, search_editor=False):
        chat_tab = {
            "packageName": "com.tencent.mm", "visible": True, "text": "微信",
            "rect": [100, 2200, 260, 2300],
        }
        me_tab = {
            "packageName": "com.tencent.mm", "visible": True, "text": "我",
            "rect": [820, 2200, 980, 2300],
        }
        if chat_selected is not None:
            chat_tab["selected"] = chat_selected
        if me_selected is not None:
            me_tab["selected"] = me_selected
        children = [
            {"packageName": "com.tencent.mm", "visible": True, "text": "搜索",
             "rect": [80, 100, 300, 200]},
            chat_tab,
            me_tab,
        ]
        if search_editor:
            children.append({
                "packageName": "com.tencent.mm", "visible": True,
                "type": "EditText", "id": "com.tencent.mm:id/f8",
                "rect": [80, 100, 900, 200],
            })
        return {"childs": children}

    # Some mode-6 frames omit reliable selected flags: the visible WeChat and
    # Me tabs plus the top search entry are the structural fallback.
    assert sender_logic["_wechat_home_tree_signature"](home_tree()) is True
    assert sender_logic["_wechat_home_tree_signature"](
        home_tree(chat_selected=True, me_selected=False)
    ) is True
    assert sender_logic["_wechat_home_tree_signature"](
        home_tree(chat_selected=False, me_selected=True)
    ) is False
    assert sender_logic["_wechat_home_tree_signature"](home_tree(search_editor=True)) is False


def test_forward_outcome_counts_do_not_turn_cleanup_failure_into_target_failure(sender_logic):
    targets = [
        {"groupName": "互助群", "status": "send_action_sent_unverified"},
        {"groupName": "测试群", "status": "send_action_sent_unverified"},
    ]
    assert sender_logic["_forward_outcome_counts"](targets) == (0, 2, 0)
    assert sender_logic["_forward_outcome_counts"](
        targets + [{"groupName": "已移出群", "status": "group_not_found"}]
    ) == (0, 2, 1)


def test_test_only_accepts_two_distinct_candidates_with_the_same_group_name(sender_logic):
    payload = {
        "groupCode": "c1001",
        "batchNo": 1,
        "cardId": "act-001",
        "cardTitle": "测试卡片",
        "targets": [
            {"candidateId": "candidate-a", "groupCode": "c1001", "groupName": "重名群"},
            {"candidateId": "candidate-b", "groupCode": "c1001", "groupName": "重名群"},
        ],
    }
    validated = sender_logic["_validate_task"]({
        "functionId": "wechat.send_group_batch",
        "targetWechatAccountId": "wechat-one",
        "payload": payload,
    })
    assert [item["candidateId"] for item in validated["targets"]] == ["candidate-a", "candidate-b"]


def test_test_single_accepts_pc_targets_without_static_group_name_allowlist(sender_logic):
    sender_logic["TEST_MODE"] = "TEST_SINGLE"
    names = ["测试群", "互助群", "Python 资料", "👸公主说的都对"]
    payload = {
        "groupCode": "c1001",
        "batchNo": 1,
        "cardId": "act-001",
        "cardTitle": "测试卡片",
        "targets": [
            {
                "candidateId": "candidate-{}".format(index),
                "groupCode": "c1001",
                "groupName": name,
            }
            for index, name in enumerate(names)
        ],
    }

    validated = sender_logic["_validate_task"]({
        "functionId": "wechat.send_group_batch",
        "targetWechatAccountId": "wechat-one",
        "payload": payload,
    })

    assert [target["groupName"] for target in validated["targets"]] == names


def test_test_only_queue_uses_pc_targets_within_group_code_scope(sender_logic):
    names = ["测试群", "互助群", "Python 资料", "👸公主说的都对"]
    task = {
        "id": "task-c1001",
        "targetWechatAccountId": "wechat-one",
        "payload": {
            "groupCode": "c1001",
            "cardId": "act-001",
            "targets": [
                {
                    "candidateId": "candidate-{}".format(index),
                    "groupCode": "c1001",
                    "groupName": name,
                    "targetWechatAccountId": "wechat-one",
                }
                for index, name in enumerate(names)
            ],
        },
    }
    response = {
        "data": {
            "createdCount": 1,
            "targetCount": len(names),
            "skippedCount": 0,
            "tasks": [task],
        }
    }
    requests = []

    def request(path, payload):
        requests.append((path, payload))
        return response

    sender_logic["_json_request"] = request
    queued = sender_logic["_request_device_batch_run"](["wechat-one"], 1)

    assert requests[0][0] == "/api/automation/group-content-plans/device-run"
    assert requests[0][1]["groupCodes"] == ["c1001"]
    assert requests[0][1]["maxTargets"] == 1000
    assert [target["groupName"] for target in queued["tasks"][0]["payload"]["targets"]] == names


def test_test_only_rejects_duplicate_candidate_identity_even_when_names_match(sender_logic):
    payload = {
        "groupCode": "c1001",
        "batchNo": 1,
        "cardId": "act-001",
        "cardTitle": "测试卡片",
        "targets": [
            {"candidateId": "candidate-a", "groupCode": "c1001", "groupName": "重名群"},
            {"candidateId": "candidate-a", "groupCode": "c1001", "groupName": "重名群"},
        ],
    }
    with pytest.raises(RuntimeError, match="重复候选 ID"):
        sender_logic["_validate_task"]({
            "functionId": "wechat.send_group_batch",
            "targetWechatAccountId": "wechat-one",
            "payload": payload,
        })


def test_test_only_expands_one_route_bundle_to_each_same_name_selection(sender_logic):
    payload = {
        "groupCode": "c1001",
        "batchNo": 1,
        "cardId": "act-001",
        "cardTitle": "测试卡片",
        "targets": [
            {
                "candidateId": "candidate-a",
                "candidateIds": ["candidate-a", "candidate-b"],
                "groupCode": "c1001",
                "groupName": "重名群",
                "groupOccurrenceCount": 2,
            }
        ],
    }

    validated = sender_logic["_validate_task"]({
        "functionId": "wechat.send_group_batch",
        "targetWechatAccountId": "wechat-one",
        "payload": payload,
    })

    assert [item["candidateId"] for item in validated["targets"]] == [
        "candidate-a",
        "candidate-a",
    ]
    assert [item["selectionOccurrence"] for item in validated["targets"]] == [1, 2]
    assert all(
        item["candidateIds"] == ["candidate-a", "candidate-b"]
        for item in validated["targets"]
    )


def test_same_name_recipient_reselects_from_live_remaining_rows(sender_logic):
    live_rects = [(100, 520, 980, 650), (100, 690, 980, 820)]
    reads = []

    def fresh_results(group_name):
        reads.append(group_name)
        return live_rects

    sender_logic["_group_search_result_rects"] = fresh_results
    # The second same-name row is re-resolved from the current snapshot rather
    # than reusing the rectangle captured before the first row was selected.
    assert sender_logic["_current_duplicate_result_rect"]("测试群", 2, 2) == live_rects[1]
    assert reads == ["测试群"]

    # WeChat may hide the first row after it is selected. The remaining result
    # becomes index one, and the caller verifies that 完成(n) increments.
    sender_logic["_group_search_result_rects"] = lambda _name: live_rects[:1]
    assert sender_logic["_current_duplicate_result_rect"]("测试群", 2, 2) == live_rects[0]

    # A missing first result is not interpreted as a selected row; the live
    # result count must match either all targets or exactly the unselected ones.
    with pytest.raises(sender_logic["SenderStop"], match="remaining=2 observed=1"):
        sender_logic["_current_duplicate_result_rect"]("测试群", 1, 2)
    sender_logic["_group_search_result_rects"] = lambda _name: []
    with pytest.raises(sender_logic["SenderStop"], match="实时结果数与剩余未选目标不符"):
        sender_logic["_current_duplicate_result_rect"]("测试群", 2, 2)


@pytest.mark.parametrize(
    "duplicate_index,total,expected",
    [
        (1, 2, (2,)),
        (2, 2, (1, 2)),
        (2, 3, (2, 3)),
        (3, 3, (1, 3)),
        (1, 1, (1,)),
    ],
)
def test_same_name_search_accepts_only_full_or_remaining_rows(
    sender_logic, duplicate_index, total, expected
):
    assert sender_logic["_same_name_result_count_options"](
        duplicate_index, total
    ) == expected


def test_live_duplicate_rows_expand_underreported_c_test_route(sender_logic):
    targets = [
        {
            "candidateId": "candidate-test",
            "candidateIds": ["candidate-test", "legacy-alias"],
            "groupName": "测试群",
            "groupOccurrenceCount": 1,
            "selectionOccurrence": 1,
        },
        {
            "candidateId": "candidate-other",
            "groupName": "互助群",
            "groupOccurrenceCount": 1,
            "selectionOccurrence": 1,
        },
    ]

    added = sender_logic["_expand_same_name_targets_to_observed_count"](
        targets, "测试群", 2
    )

    assert len(added) == 1
    assert added[0]["candidateId"] == "candidate-test"
    assert added[0]["candidateIds"] == ["candidate-test", "legacy-alias"]
    assert added[0]["groupOccurrenceCount"] == 2
    assert added[0]["selectionOccurrence"] == 2
    assert added[0]["liveOccurrenceExpanded"] is True
    assert sender_logic["_expand_same_name_targets_to_observed_count"](
        targets + added, "测试群", 2
    ) == []


def test_live_duplicate_expansion_does_not_shrink_or_guess_targets(sender_logic):
    targets = [
        {
            "candidateId": "candidate-test",
            "groupName": "测试群",
            "selectionOccurrence": 1,
        },
    ]

    assert sender_logic["_expand_same_name_targets_to_observed_count"](
        targets, "测试群", 1
    ) == []
    assert sender_logic["_expand_same_name_targets_to_observed_count"](
        targets, "不存在的目标", 2
    ) == []


def test_forward_card_researches_each_same_name_candidate_before_tapping():
    source = Path(__file__).resolve().parents[2] / (
        "automation/ascript/wechat_marketing_sender/__init__.py"
    )
    module = ast.parse(source.read_text())
    forward_card = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_forward_card"
    )
    duplicate_loop = next(
        node
        for node in ast.walk(forward_card)
        if isinstance(node, ast.For)
        and any(
            isinstance(name, ast.Name) and name.id == "duplicate_index"
            for name in ast.walk(node.target)
        )
    )
    calls = [
        node
        for node in ast.walk(duplicate_loop)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    search_lines = [
        node.lineno
        for node in calls
        if node.func.id == "_search_forward_group_by_name"
    ]
    resolve_lines = [
        node.lineno
        for node in calls
        if node.func.id == "_current_duplicate_result_rect"
    ]
    assert search_lines and resolve_lines
    assert min(search_lines) < min(resolve_lines)


def test_unified_launcher_scans_both_slots_before_one_sender_run():
    source_path = Path(__file__).resolve().parents[2] / "automation/ascript/__init__.py"
    source = source_path.read_text()
    ast.parse(source)
    # Both account scans must finish before the independent sender module is
    # loaded once with the complete account set; TEST_ONLY validates both.
    assert source.index("for slot_index in (0, 1):") < source.index(
        "sender = _load_feature_module(module_name)"
    )
    assert "_run_scoped_sender" not in source
    assert "for scan_record in scan_records" not in source


def test_chat_back_control_requires_unique_live_wechat_node(sender_logic):
    base = {
        "packageName": "com.tencent.mm",
        "id": "com.tencent.mm:id/actionbar_up_indicator",
        "rect": [12, 100, 82, 220],
        "visible": True,
        "clickable": True,
    }
    tree = {"childs": [dict(base)]}
    assert sender_logic["_wechat_actionbar_back_rects"](tree) == [(12, 100, 82, 220)]
    tree["childs"].append(dict(base, rect=[15, 110, 85, 230]))
    assert len(sender_logic["_wechat_actionbar_back_rects"](tree)) == 2


def test_search_results_page_is_recognized_by_query_and_unique_live_back(sender_logic):
    tree = {
        "packageName": "com.tencent.mm",
        "childs": [
            {
                "type": "ImageView",
                "id": "com.tencent.mm:id/actionbar_up_indicator",
                "packageName": "com.tencent.mm",
                "rect": [12, 100, 82, 220],
                "visible": True,
                "clickable": True,
            },
            {
                "type": "EditText",
                "id": "com.tencent.mm:id/f8",
                "packageName": "com.tencent.mm",
                "text": "卡片素材群",
                "rect": [100, 120, 900, 230],
                "visible": True,
            },
        ],
    }
    search_item = sender_logic["_search_input_item"](tree)

    assert search_item is not None
    assert sender_logic["_search_page_signature"](tree, search_item) is True

    # A query alone is insufficient: without a unique live back node the page
    # remains unknown and no return action can be safely targeted.
    tree["childs"].pop(0)
    search_item = sender_logic["_search_input_item"](tree)
    assert sender_logic["_search_page_signature"](tree, search_item) is False


@pytest.mark.parametrize("names", [["测试群", "互助群"], ["测试群"], ["重名群", "重名群"]])
def test_claimed_test_task_preserves_pc_candidate_targets(sender_logic, names):
    task = {
        "functionId": "wechat.send_group_batch", "targetWechatAccountId": "wechat-one",
        "payload": {
            "groupCode": "c1001", "batchNo": 1, "cardId": "act-001", "cardTitle": "卡片",
            "targets": [{"candidateId": str(i), "groupName": name} for i, name in enumerate(names)],
        },
    }
    assert [row["groupName"] for row in sender_logic["_validate_task"](task)["targets"]] == names


@pytest.mark.parametrize(
    "status,allowed",
    [
        ("group_not_found", True),
        ("search_no_results", True),
        ("search_input_unverified", False),
        ("selection_unconfirmed", False),
        ("search_unconfirmed", False),
        ("", False),
    ],
)
def test_only_explicit_missing_group_results_allow_partial_send(sender_logic, status, allowed):
    assert sender_logic["_is_explicit_missing_target_status"](status) is allowed


@pytest.mark.parametrize(
    "queued,expected_status,expected_reason",
    [
        (
            {"targetCount": 0, "skippedCount": 0},
            "idle",
            "当前微信账号本批次没有可发送目标",
        ),
        (
            {"targetCount": 2, "skippedCount": 1},
            "failed",
            "PC 报告仍有 2 个可发送目标，但没有创建任何发送任务",
        ),
        (
            {"targetCount": 0, "skippedCount": 1},
            "idle",
            "当前账号没有可发送目标；PC 跳过了 1 项，详见 QUEUE_SKIPPED",
        ),
    ],
)
def test_empty_account_queue_has_an_explicit_outcome(sender_logic, queued, expected_status, expected_reason):
    outcome = sender_logic["_queue_empty_reason"](queued)
    assert outcome["status"] == expected_status
    assert outcome["reason"] == expected_reason


def test_unconfigured_send_mode_fails_loudly_instead_of_completing_dry_run():
    source_path = Path(__file__).resolve().parents[2] / "automation/ascript/wechat_marketing_sender/__init__.py"
    module = ast.parse(source_path.read_text())
    run_one = next(
        item for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name == "_run_one"
    )
    calls = [
        node.func.id
        for node in ast.walk(run_one)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "SenderStop" in calls
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_result"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "dry_run"
        for node in ast.walk(run_one)
    )


def test_history_scroll_waits_past_first_stale_tree(sender_logic):
    frames = iter(["before", "before", "changed"])
    sender_logic.update({
        "_dump": lambda: next(frames),
        "_visible_tree_signature": lambda tree: tree,
        "_material_chat_history_rect": lambda tree: ((0, 250, 1080, 2150), "live"),
        "_chat_header_rects": lambda name, tree: [(300, 100, 750, 220)],
        "_before_action": lambda *args: None,
        "CHAT_TREE_WAIT_TIMEOUT_SECONDS": 8,
        "CHAT_TREE_POLL_INTERVAL_SECONDS": 0.8,
    })
    def poll(predicate, **kwargs):
        for _ in range(3):
            result = predicate()
            if result:
                return result
        return None
    sender_logic["_wait_for"] = poll
    gestures = []
    sender_logic["_hid_history_scroll"] = lambda *args: gestures.append(args)
    steps = []
    log = SimpleNamespace(items=steps, add=lambda *args: steps.append(args))
    assert sender_logic["_scroll_chat_to_older"](object(), log) is True
    assert len(gestures) == 1


def _load_forward_search_function(source_path, namespace):
    module = ast.parse(source_path.read_text())
    function = next(
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef)
        and item.name == "_search_forward_group_by_name"
    )
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["_search_forward_group_by_name"]


def test_forward_search_refocuses_after_clear_before_typing(sender_logic):
    source_path = Path(__file__).resolve().parents[2] / "automation/ascript/wechat_marketing_sender/__init__.py"
    events = []

    class StepLog:
        def __init__(self):
            self.items = []

        def add(self, *args):
            self.items.append(args)

    namespace = {
        "_record_target_stage": lambda *args: events.append(("stage", args[4], args[5])),
        "_focus_search_input": lambda ble, step_log, action_name, expected=None: (
            events.append(("focus", action_name)) or (10, 20, 30, 40)
        ),
        "_before_action": lambda *args, **kwargs: None,
        "_hid_clear": lambda ble, step_log, action_name, settle_seconds=None: events.append(("clear", settle_seconds)),
        "_paste": lambda ble, value, step_log, action_name, **kwargs: events.append(("input", value)),
        "_wait_for": lambda predicate, **kwargs: predicate(),
        "_search_input_has_value": lambda value: True,
        "_search_input_has_value_ocr": lambda value: False,
        "_group_search_result_rects": lambda value: [(50, 60, 150, 160)],
        "_explicit_group_missing_message": lambda: None,
        "SenderStop": RuntimeError,
    }
    search = _load_forward_search_function(source_path, namespace)

    result = search(object(), "互助群", StepLog(), [], 2, 2)

    assert result == [(50, 60, 150, 160)]
    actions = [event for event in events if event[0] in ("focus", "clear", "input")]
    assert actions == [
        ("focus", "聚焦转发搜索框"),
        ("clear", 0.6),
        ("focus", "清空后重新聚焦转发搜索框"),
        ("input", "互助群"),
    ]
