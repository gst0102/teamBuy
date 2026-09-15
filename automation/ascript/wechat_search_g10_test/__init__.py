# -*- coding: utf-8 -*-
"""Minimal Android test: open WeChat search, enter g10, show results, exit.

This project is intentionally isolated from the production launcher and backend.
It uses the live mode-6 tree for perception and the official ESP32 BleDevice for
every WeChat tap and text-input action.
"""

from __future__ import print_function

import json
import time

from ascript.android import node
from ascript.android.system import Clipboard, Device
from ascript.android.system import open as open_app
from ascript.android.ui import Dialog


WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
UI_MODE = 6
LEO_WECHAT_ID = "qq673105954"
LEO_CHOOSER_INDEX = 1
SEARCH_MARKER = "页面设置"
SEARCH_KEYWORDS = ("搜索指定内容", "朋友圈", "公众号", "小程序", "视频号")
SEARCH_RESULT_KEYWORDS = (
    "最近使用",
    "最近搜索",
    "群聊",
    "更多群聊",
    "聊天记录",
    "搜索网络结果",
)


def _rect(item):
    value = item.get("rect") or {}
    return (
        int(value.get("left", 0)),
        int(value.get("top", 0)),
        int(value.get("right", 0)),
        int(value.get("bottom", 0)),
    )


def _valid(rect):
    return rect[2] > rect[0] and rect[3] > rect[1]


def _walk(value, parents=None):
    parents = parents or []
    if isinstance(value, list):
        for item in value:
            for found in _walk(item, parents):
                yield found
        return
    if not isinstance(value, dict):
        return
    current = parents + [value]
    yield current
    for view in value.get("views", []) or []:
        for found in _walk(view, parents):
            yield found
    for child in value.get("childs", []) or []:
        for found in _walk(child, current):
            yield found


def _dump():
    node.Selector.refresh(UI_MODE)
    raw = node.Selector.dump(UI_MODE)
    return json.loads(raw) if isinstance(raw, str) else raw


def _device_size():
    display = Device.display()
    return int(display.widthPixels), int(display.heightPixels)


def _ble():
    from ascript.android import plug

    plug.load("esp32")
    from esp32 import BleDevice

    device = BleDevice()
    if not device.is_conncted():
        try:
            device.re_connect()
        except Exception:
            pass
    if not device.is_conncted():
        raise RuntimeError("官方 ESP32 HID 未连接")
    print("HID_READY name={} mac={}".format(device.get_name(), device.get_mac_address()))
    return device


def _action_rect(path):
    item = path[-1]
    own = _rect(item)
    if item.get("clickable") is True and _valid(own):
        return own
    for parent in reversed(path[:-1]):
        rect = _rect(parent)
        if parent.get("clickable") is True and _valid(rect):
            return rect
    return own


def _text_rects(text, top=0, bottom=None):
    try:
        tree = _dump()
    except Exception:
        return []
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != text:
            continue
        item_rect = _rect(item)
        rect = _action_rect(path)
        if not _valid(rect) or not _valid(item_rect):
            continue
        if item_rect[1] < top or (bottom is not None and item_rect[3] > bottom):
            continue
        matches.append(rect)
    return sorted(set(matches))


def _desc_or_id_rect(descs=(), ids=(), top=0, bottom=None):
    try:
        tree = _dump()
    except Exception:
        return None
    short_ids = {str(value).rsplit("/", 1)[-1] for value in ids}
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        desc = str(item.get("desc") or item.get("contentDesc") or "").strip()
        item_id = str(item.get("id") or "").strip()
        if desc not in descs and item_id not in ids and item_id.rsplit("/", 1)[-1] not in short_ids:
            continue
        rect = _action_rect(path)
        if not _valid(rect) or rect[1] < top:
            continue
        if bottom is not None and rect[3] > bottom:
            continue
        matches.append(rect)
    matches = sorted(set(matches))
    return matches[0] if len(matches) == 1 else None


def _editable_item(tree=None):
    tree = tree if tree is not None else _dump()
    preferred = []
    editable = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") not in (WECHAT_PACKAGE, None, "") or item.get("visible") is False:
            continue
        item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        is_known = item_id in {"f8", "search_src_text"}
        is_editable = item.get("type") in ("EditText", "AutoCompleteTextView") or item.get("editable") is True
        rect = _rect(item)
        if not _valid(rect) or rect[1] >= 460 or not (is_known or is_editable):
            continue
        value = (path, rect)
        if is_known:
            preferred.append(value)
        if is_editable:
            editable.append(value)
    if preferred:
        with_text = [value for value in preferred if str(value[0][-1].get("text") or "").strip()]
        if len(with_text) == 1:
            return with_text[0]
        return sorted(preferred, key=lambda value: (value[1][1], value[1][0]))[0]
    labeled = [
        value
        for value in editable
        if "搜索" in " ".join(
            str(value[0][-1].get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint", "id")
        )
    ]
    if len(labeled) == 1:
        return labeled[0]
    if len(editable) == 1:
        return editable[0]
    with_text = [value for value in editable if str(value[0][-1].get("text") or "").strip()]
    return with_text[0] if len(with_text) == 1 else None


def _has_text(tree, text):
    return any(
        path[-1].get("packageName") == WECHAT_PACKAGE
        and path[-1].get("visible") is not False
        and str(path[-1].get("text") or "").strip() == text
        for path in _walk(tree)
    )


def _wechat_identity_is_leo():
    try:
        tree = _dump()
    except Exception:
        return False
    expected = {"微信号：" + LEO_WECHAT_ID, "微信号:" + LEO_WECHAT_ID}
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        values = (
            str(item.get("text") or "").strip(),
            str(item.get("desc") or "").strip(),
            str(item.get("contentDesc") or "").strip(),
        )
        if any(value in expected for value in values):
            return True
    return False


def _has_back_indicator(tree):
    """A live WeChat action-bar back node means this is a child page."""
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        desc = str(item.get("desc") or item.get("contentDesc") or "").strip()
        item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        if desc == "返回" or item_id in {"actionbar_up_indicator", "actionbar_up_indicator_btn"}:
            if _valid(_rect(item)):
                return True
    return False


def _is_search_page(tree=None):
    """The unique 页面设置 marker identifies the empty WeChat search page."""
    tree = tree if tree is not None else _dump()
    if not any(
        path[-1].get("packageName") == WECHAT_PACKAGE
        and path[-1].get("visible") is not False
        for path in _walk(tree)
    ):
        return False
    # Do not require the EditText here. It may be attached a moment later,
    # while 页面设置 is already present in the live mode-6 tree.
    if _has_text(tree, SEARCH_MARKER):
        return True
    if not _has_text(tree, "取消"):
        return False
    return any(_has_text(tree, keyword) for keyword in SEARCH_RESULT_KEYWORDS)


def _wechat_home(tree=None):
    tree = tree if tree is not None else _dump()
    width, height = _device_size()
    if not any(
        path[-1].get("packageName") == WECHAT_PACKAGE
        and path[-1].get("visible") is not False
        for path in _walk(tree)
    ):
        return False
    chat = _text_rects_from_tree(tree, "微信", min_top=int(height * 0.72))
    me = _text_rects_from_tree(tree, "我", min_top=int(height * 0.72))
    if not chat or not me:
        return False
    return not _editable_item(tree) and not _has_back_indicator(tree)


def _text_rects_from_tree(tree, text, min_top=0, max_top=None):
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != text:
            continue
        item_rect = _rect(item)
        rect = _action_rect(path)
        if not _valid(rect) or not _valid(item_rect):
            continue
        if item_rect[1] < min_top or (max_top is not None and item_rect[1] > max_top):
            continue
        matches.append(rect)
    return sorted(set(matches))


def _chooser_points(tree=None):
    tree = tree if tree is not None else _dump()
    points = []
    chooser_marker = any(
        str(path[-1].get("text") or "").strip() in ("请选择要使用的应用", "取消")
        for path in _walk(tree)
    )
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("visible") is False
            or str(item.get("text") or "").strip() != "微信"
        ):
            continue
        # The native resolver may expose its labels under a system package
        # instead of the manufacturer's dual-app package.  The action target
        # remains valid only when the live tree also exposes the chooser marker
        # and a GridView item container; no OCR or fixed coordinate is used.
        if item.get("packageName") != DUAL_APP_PACKAGE and not chooser_marker:
            continue
        grid_index = None
        for index in range(len(path) - 1, -1, -1):
            if str(path[index].get("type") or "") == "GridView":
                grid_index = index
                break
        if grid_index is None or grid_index + 1 >= len(path):
            continue
        container = path[grid_index + 1]
        rect = _rect(container)
        if _valid(rect) and rect[2] - rect[0] < int(_device_size()[0] * 0.75):
            points.append((int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)))
    points = sorted(set(points), key=lambda point: point[0])
    return points if len(points) == 2 else []


def _tap(ble, rect, label):
    width, height = _device_size()
    x = int((rect[0] + rect[2]) / 2)
    y = int((rect[1] + rect[3]) / 2)
    if not (0 <= x < width and 0 <= y < height):
        raise RuntimeError("控件树矩形中心超出 HID 范围：{}".format(label))
    print("HID_TAP label={} rect={} center=({}, {})".format(label, rect, x, y))
    ble.click(x, y, dur=35)
    time.sleep(0.6)


def _wait(predicate, timeout=10, interval=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("WAIT_ERROR", type(exc).__name__)
        time.sleep(interval)
    return None


def _open_selected_wechat(ble):
    Device.wake_up()
    try:
        Device.keep_screen_on()
    except Exception:
        pass
    # Leave the AScript project list through the official HID home key before
    # opening WeChat; Device.home() is not part of the AScript runtime.
    ble.home()
    time.sleep(0.8)
    open_app(WECHAT_PACKAGE)
    points = _wait(_chooser_points, timeout=10)
    if not points:
        tree = _dump()
        config = (tree.get("data") or {}).get("config") or {}
        raise RuntimeError(
            "双开选择器控件树不可用：mode={} viewCount={}；未取得右侧 leo 实时矩形".format(
                config.get("mode"), config.get("viewCount")
            )
        )
    if len(points) <= LEO_CHOOSER_INDEX:
        raise RuntimeError("双开选择器未找到 leo 对应微信入口")
    x, y = points[LEO_CHOOSER_INDEX]
    _tap(ble, (x, y, x, y), "双开 leo 微信")
    if not _wait(lambda: _wechat_visible(), timeout=15):
        raise RuntimeError("微信页面未进入前台")
    if not _wait(_wechat_identity_is_leo, timeout=12):
        raise RuntimeError("当前双开入口未核验为 leo（微信号：{}），禁止继续测试".format(LEO_WECHAT_ID))
    print("WECHAT_ID_CONFIRMED {}".format(LEO_WECHAT_ID))


def _wechat_visible():
    try:
        tree = _dump()
    except Exception:
        return False
    return any(
        path[-1].get("packageName") == WECHAT_PACKAGE
        and path[-1].get("visible") is not False
        and _valid(_rect(path[-1]))
        for path in _walk(tree)
    )


def _ensure_chat_home(ble):
    if _wait(lambda: _wechat_home(), timeout=2):
        return
    tree = _dump()
    height = _device_size()[1]
    chat_tabs = _text_rects_from_tree(tree, "微信", min_top=int(height * 0.60))
    me_tabs = _text_rects_from_tree(tree, "我", min_top=int(height * 0.60))
    if len(chat_tabs) == 1 and me_tabs:
        _tap(ble, chat_tabs[0], "返回微信会话列表")
        # This isolated test only needs the live home search entry.  Avoid a
        # second, stricter home classifier that can reject a valid tree while
        # WeChat is still rendering.
        if _wait(_search_entry_rect, timeout=8):
            return
        raise RuntimeError("点击微信页签后未出现首页搜索入口")
    raise RuntimeError("控件树未找到唯一的微信首页页签")


def _search_entry_rect():
    rect = _desc_or_id_rect(
        descs=("搜索", "Search"),
        ids=(WECHAT_PACKAGE + ":id/actionbar_search",),
        top=0,
        bottom=360,
    )
    if rect:
        return rect
    rects = _text_rects("搜索", top=0, bottom=360)
    return rects[0] if len(rects) == 1 else None


def _open_search(ble):
    rect = _wait(_search_entry_rect, timeout=10)
    if not rect:
        raise RuntimeError("控件树未找到微信首页搜索入口")
    _tap(ble, rect, "打开微信搜索")
    if not _wait(lambda: _is_search_page(), timeout=8):
        raise RuntimeError("打开搜索后控件树未确认页面设置")


def _input_g10(ble):
    item = _wait(_editable_item, timeout=8)
    if not item:
        raise RuntimeError("搜索页控件树未找到输入框")
    _tap(ble, item[1], "聚焦搜索框")
    if not _wait(_is_search_page, timeout=3):
        raise RuntimeError("聚焦后控件树不再确认搜索页")
    Clipboard.put("g10")
    ble.paste()
    print("HID_PASTE value=g10")
    if not _wait(lambda: _query_is_g10(), timeout=8):
        raise RuntimeError("控件树未核验搜索框内容 g10")


def _query_is_g10():
    item = _editable_item()
    return bool(item and str(item[0][-1].get("text") or "").strip() == "g10")


def _result_summary():
    tree = _dump()
    values = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        value = " ".join(str(item.get("text") or "").split())
        if value and value not in values and len(values) < 40:
            values.append(value)
    return values


def main():
    started = time.time()
    try:
        ble = _ble()
        _open_selected_wechat(ble)
        _ensure_chat_home(ble)
        _open_search(ble)
        _input_g10(ble)
        results = _wait(_result_summary, timeout=8) or []
        detail = "搜索页已确认：页面设置\n已通过官方 ESP32 HID 输入：g10\n\n控件树文本：\n{}\n\n耗时：{:.2f} 秒".format(
            "\n".join(results[:30]) or "（未读到结果文本）",
            time.time() - started,
        )
        print("SEARCH_G10_TEST_DONE", json.dumps({"resultCount": len(results)}, ensure_ascii=False))
        Dialog.alert(detail, title="微信搜索 g10 测试", submit="退出测试")
    except Exception as exc:
        print("SEARCH_G10_TEST_FAILED", type(exc).__name__, str(exc))
        try:
            Dialog.alert("测试失败：\n{}\n\n请保留当前页面和日志。".format(exc), title="微信搜索 g10 测试", submit="退出测试")
        except Exception:
            pass


main()
