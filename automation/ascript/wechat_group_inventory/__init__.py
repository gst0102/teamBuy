# -*- coding: utf-8 -*-
"""Read-only targeted inventory for native WeChat groups.

The production preflight searches the current account's WeChat home for the
PC-configured group-code prefixes (for example ``g10`` and test scope
``c1001``), opens ``更多群聊``, reads the live group rows, and synchronizes
the account-scoped mapping to the PC. PC may select scan-only mode to prevent
the scan from creating any send task.
It never opens a row merely to scan it, reads messages, sends a message,
joins a group, or changes a group remark.

Native WeChat groups do not expose an invitation QR in this list. The PC API
therefore receives ``source=wechat_native`` and a null ``groupQRCode``.
"""

from __future__ import print_function

import json
import os
import re
import time
from urllib.parse import quote
import urllib.error
import urllib.request

import cv2
from ascript.android.action import Ime
from ascript.android import node
from ascript.android.screen import Ocr, capture_cv
from ascript.android.system import Clipboard, Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "official_esp32_hid"
try:
    from . import local_config as _local_config
except Exception:
    _local_config = None

_configured_device_id = getattr(_local_config, "DEVICE_ID", DEVICE_ID)
if " ".join(str(_configured_device_id or "").split()):
    DEVICE_ID = " ".join(str(_configured_device_id).split())[:128]

BACKEND_URL = getattr(_local_config, "BACKEND_URL", "")
DEVICE_TOKEN = getattr(_local_config, "DEVICE_TOKEN", "")
WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
INSTANCE_SLOTS = tuple(
    getattr(
        _local_config,
        "INSTANCE_SLOTS",
        ("wechat-instance-1", "wechat-instance-2"),
    )
)


def _scan_slot_indices():
    """Return the explicitly scoped slots for this run, or all slots by default."""
    raw = str(os.environ.get("TEAMBUY_SCAN_SLOT_INDICES", "") or "").strip()
    if not raw:
        return tuple(range(len(INSTANCE_SLOTS)))
    values = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            index = int(value)
        except (TypeError, ValueError):
            raise RuntimeError("微信群扫描账号槽位范围无效")
        if index < 0 or index >= len(INSTANCE_SLOTS) or index in values:
            raise RuntimeError("微信群扫描账号槽位范围越界或重复")
        values.append(index)
    if not values:
        raise RuntimeError("微信群扫描账号槽位范围为空")
    return tuple(values)


SCAN_SLOT_INDICES = _scan_slot_indices()
# Keep Selector.dump aligned with the phone's HID run mode.  Mode 2 is the
# accessibility tree and is unavailable when accessibility is disabled.
UI_MODE = 6
HID_POST_ACTION_SETTLE_SECONDS = 1.5
SCAN_MODE = str(os.environ.get("TEAMBUY_SCAN_MODE", "targeted") or "targeted").strip().lower()
if SCAN_MODE != "targeted":
    raise RuntimeError("生产微信群扫描仅支持 targeted 搜索路径")
PREFLIGHT_ONLY = str(os.environ.get("TEAMBUY_PREFLIGHT_ONLY", "") or "").strip().lower() in {
    "1", "true", "yes"
}
def _normalize_group_search_prefixes(values):
    """Accept only explicit g/c group-code prefixes from the PC config."""
    if isinstance(values, str):
        values = re.split(r"[,，\n]", values)
    result = []
    for value in values or ():
        prefix = "".join(str(value or "").split()).lower()
        if not prefix:
            continue
        if not re.fullmatch(r"[gc]\d{1,8}", prefix):
            raise RuntimeError("群编号扫描配置无效：{}；仅允许 g/c 开头编号".format(prefix))
        if prefix not in result:
            result.append(prefix)
    if not result or len(result) > 12:
        raise RuntimeError("群编号扫描配置必须包含 1 至 12 个不同前缀")
    return tuple(result)


GROUP_SEARCH_PREFIXES = _normalize_group_search_prefixes(
    getattr(_local_config, "GROUP_SEARCH_PREFIXES", ("g10",))
)
SCAN_ONLY = False
MAX_TARGETED_SCROLLS = 36
# Returning to the WeChat chat-list home is navigation, not content scrolling.
# Use the official HID back key only after the live mode-6 tree identifies a
# known WeChat child page.
MAX_HOME_BACKS = 5
WECHAT_ROOT_TAB_STATES = ("contacts", "discover", "profile")
SEARCH_PAGE_MARKER = "页面设置"
SEARCH_PAGE_KEYWORDS = ("搜索指定内容", "朋友圈", "公众号", "小程序", "视频号")
SEARCH_PAGE_RESULT_KEYWORDS = (
    "最近使用",
    "最近搜索",
    "群聊",
    "更多群聊",
    "聊天记录",
    "搜索网络结果",
)
# WeChat can render an empty query result without any 群聊 row or 更多群聊
# link. These labels are state evidence for a completed zero-row search, not
# a reason to block the next configured prefix.
SEARCH_EMPTY_RESULT_MARKERS = (
    "无搜索结果",
    "没有找到相关结果",
    "没有找到结果",
    "暂无相关结果",
    "无相关结果",
    "未找到相关结果",
)

HID_DEVICE = None


def _keep_screen_awake():
    try:
        Device.wake_up()
        Device.keep_screen_on()
        print("已开启屏幕常亮")
    except Exception as exc:
        print("开启屏幕常亮失败:", exc)


_keep_screen_awake()


def _hid():
    """Load the official ESP32 HID device once for this AScript run."""
    global HID_DEVICE
    if HID_DEVICE is not None:
        return HID_DEVICE
    from ascript.android import plug

    plug.load("esp32")
    from esp32 import BleDevice

    HID_DEVICE = BleDevice()
    if not HID_DEVICE.is_conncted():
        try:
            HID_DEVICE.re_connect()
        except Exception:
            pass
    if not HID_DEVICE.is_conncted():
        raise RuntimeError("官方 ESP32 HID 未连接")
    print(
        "HID_READY name={} mac={}".format(
            HID_DEVICE.get_name(), HID_DEVICE.get_mac_address()
        )
    )
    return HID_DEVICE


def _device_size():
    display = Device.display()
    return int(display.widthPixels), int(display.heightPixels)


def _dump(mode=None):
    mode = UI_MODE if mode is None else mode
    node.Selector.refresh(mode)
    raw = node.Selector.dump(mode)
    return json.loads(raw) if isinstance(raw, str) else raw


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
    # Device-side Selector.dump() returns {config, views}; views are the
    # actual roots and are not nested under ``childs``.
    for view in value.get("views", []) or []:
        for found in _walk(view, parents):
            yield found
    for child in value.get("childs", []) or []:
        for found in _walk(child, current):
            yield found


def _rect(item):
    rect = item.get("rect") or {}
    if isinstance(rect, dict):
        return (
            int(rect.get("left", 0)),
            int(rect.get("top", 0)),
            int(rect.get("right", 0)),
            int(rect.get("bottom", 0)),
        )
    return 0, 0, 0, 0


def _valid_rect(rect):
    return rect[2] > rect[0] and rect[3] > rect[1]


def _wait_for(predicate, timeout=10, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("等待微信界面失败：{}".format(exc))
        time.sleep(interval)
    return None


def _tap(x, y, expected=None, action_name=""):
    if expected:
        _before_action(expected, action_name, point=(x, y))
    width, height = _device_size()
    x, y = int(x), int(y)
    if not (0 <= x < width and 0 <= y < height):
        raise RuntimeError("控件树坐标超出 HID 触控范围：({}, {})".format(x, y))
    _hid().click(x, y, dur=35)
    _settle_after_hid(action_name or "click")


def _settle_after_hid(action_name, seconds=HID_POST_ACTION_SETTLE_SECONDS):
    """Give WeChat one bounded render period after a complete HID action."""
    delay = max(1.0, min(2.0, float(seconds)))
    print("HID_ACTION_SETTLE action={} seconds={}".format(action_name, delay))
    time.sleep(delay)


def _hid_swipe(x, y, x1, y1, action_name="滑动"):
    """Send one explicit official HID swipe: down, move, then up."""
    hid = _hid()
    start = (int(x), int(y))
    end = (int(x1), int(y1))
    hid.touch_down(start[0], start[1], dur=20)
    try:
        hid.touch_move(end[0], end[1], dur=450)
    finally:
        hid.touch_up(end[0], end[1], dur=20)
    print(
        "HID_SWIPE_PRIMITIVES action={} start={} end={}".format(
            action_name, start, end
        )
    )
    _settle_after_hid(action_name)


def _swipe(x, y, x1, y1):
    _hid_swipe(x, y, x1, y1)


def _back():
    _hid().back()
    _settle_after_hid("返回")


def _home():
    _hid().home()
    _settle_after_hid("系统Home")


def _capture_blocker_screenshot(stage, error=None):
    """Save a device screenshot for a blocked scan without exposing secrets."""
    safe_stage = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stage or "blocked"))[:80]
    path = "sdcard/airscript/screen/gp/teamBuy_blocker_{}_{}.jpg".format(
        safe_stage,
        int(time.time()),
    )
    try:
        bitmap = capture_cv()
        saved = bool(bitmap is not None and cv2.imwrite(path, bitmap))
        print(
            "BLOCKER_SCREENSHOT path={} saved={} error={}".format(
                path,
                saved,
                str(error or "")[:240],
            )
        )
        return path if saved else None
    except Exception as exc:
        print(
            "BLOCKER_SCREENSHOT_FAILED stage={} error={}".format(
                safe_stage,
                str(exc)[:240],
            )
        )
        return None


def _clickable_ancestor(path):
    for item in reversed(path[:-1]):
        rect = _rect(item)
        if item.get("clickable") is True and _valid_rect(rect):
            return rect
    return None


def _action_rect(path):
    """Prefer a clickable node's own live rect; otherwise use its clickable ancestor."""
    item = path[-1]
    own = _rect(item)
    if item.get("clickable") is True and _valid_rect(own):
        return own
    return _clickable_ancestor(path) or own


def _point_for_text_in_tree(tree, text, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    matches = []
    width, height = _device_size()
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("packageName") != package
            or item.get("text") != text
            or any(parent.get("visible") is False for parent in path)
        ):
            continue
        rect = _action_rect(path)
        if not _valid_rect(rect):
            continue
        if rect[0] < 0 or rect[1] < 0 or rect[2] > width or rect[3] > height:
            continue
        if rect[1] < min_top or (max_top is not None and rect[1] > max_top):
            continue
        matches.append(rect)
    matches = sorted(set(matches))
    if len(matches) != 1:
        return None
    rect = matches[0]
    return int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)


def _point_for_text(text, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    try:
        tree = _dump()
    except Exception:
        return None
    return _point_for_text_in_tree(tree, text, package, min_top, max_top)


def _point_for_id_in_tree(tree, resource_id, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("packageName") != package
            or str(item.get("id") or "").rsplit("/", 1)[-1]
            != str(resource_id).rsplit("/", 1)[-1]
        ):
            continue
        rect = _action_rect(path)
        if not _valid_rect(rect):
            continue
        if rect[1] < min_top or (max_top is not None and rect[1] > max_top):
            continue
        matches.append(rect)
    matches = sorted(set(matches))
    if len(matches) != 1:
        return None
    rect = matches[0]
    return int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)


def _point_for_id(resource_id, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    try:
        tree = _dump()
    except Exception:
        return None
    return _point_for_id_in_tree(tree, resource_id, package, min_top, max_top)


def _find_desc_or_id_rect(descs=(), ids=(), top=0, bottom=None):
    """Find one visible action rectangle from the mode-6 tree."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    short_ids = set(str(value).rsplit("/", 1)[-1] for value in ids)
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        if item.get("visible") is False:
            continue
        desc = str(item.get("desc") or item.get("contentDesc") or "").strip()
        item_id = str(item.get("id") or "").strip()
        if desc not in descs and item_id not in ids and item_id.rsplit("/", 1)[-1] not in short_ids:
            continue
        short_id = item_id.rsplit("/", 1)[-1]
        is_input = (
            item.get("type") in ("EditText", "AutoCompleteTextView")
            or item.get("editable") is True
            or short_id in {"f8", "search_src_text"}
        )
        # An EditText must be clicked on its own live rect. Its clickable
        # ancestor may be the whole toolbar and will not focus the editor.
        rect = _rect(item) if is_input else _action_rect(path)
        if not _valid_rect(rect) or rect[1] < top:
            continue
        if bottom is not None and rect[3] > bottom:
            continue
        matches.append(rect)
    matches = sorted(set(matches))
    return matches[0] if len(matches) == 1 else None


def _find_editable_rect(top=0, bottom=None):
    """Find the live WeChat search EditText; never use a screen coordinate fallback."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    matches = []
    preferred = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") not in (WECHAT_PACKAGE, None, ""):
            continue
        if item.get("visible") is False:
            continue
        if item.get("type") not in ("EditText", "AutoCompleteTextView") and item.get("editable") is not True:
            continue
        # Never replace an editor's own rectangle with a clickable toolbar
        # ancestor; that would send HID input to the wrong target.
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] < top:
            continue
        if bottom is not None and rect[3] > bottom:
            continue
        matches.append(rect)
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint", "id")
        )
        if "搜索本地或网络结果" in label:
            preferred.append(rect)
    preferred = sorted(set(preferred))
    if len(preferred) == 1:
        return preferred[0]
    matches = sorted(set(matches))
    return matches[0] if len(matches) == 1 else None


def _search_input_item(tree):
    """Return the live search input path and its own rectangle."""
    preferred = []
    editable = []
    placeholder = []
    for path in _walk(tree):
        item = path[-1]
        # Android 15/HID can put packageName on the WeChat container while
        # leaving it empty on the dynamic d98 input leaf.  Require a WeChat
        # ancestor, rather than the leaf alone, so the AScript launcher cannot
        # be mistaken for the WeChat editor.
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if item.get("visible") is False:
            continue
        item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        is_known = item_id in {"f8", "search_src_text"}
        is_editable = item.get("type") in ("EditText", "AutoCompleteTextView") or item.get("editable") is True
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint", "id")
        )
        is_placeholder = "搜索本地或网络结果" in label
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] >= 460 or not (
            is_known or is_editable or is_placeholder
        ):
            continue
        if is_known:
            preferred.append((path, rect))
        if is_editable:
            editable.append((path, rect))
        if is_placeholder:
            placeholder.append((path, rect))
    if preferred:
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
    placeholder_rects = sorted(set(value[1] for value in placeholder))
    if len(placeholder_rects) == 1:
        return next(value for value in placeholder if value[1] == placeholder_rects[0])
    # Android 15/HID may expose the visible search editor and its background
    # editor with short dynamic IDs.  When the query is present, the editor
    # carrying the non-empty text is the only safe live search target.
    with_text = [
        value
        for value in editable
        if str(value[0][-1].get("text") or "").strip()
    ]
    if len(with_text) == 1:
        return with_text[0]
    return None


def _search_input_action_rect():
    """Return the unique live rectangle of the current search editor."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    item = _search_input_item(tree)
    if not item:
        return None
    rect = _rect(item[0][-1])
    return rect if _valid_rect(rect) else None


def _search_input_focused():
    """Confirm that a visible search editor, not its toolbar, owns focus."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return False
    item = _search_input_item(tree)
    if item and item[0][-1].get("focused") is True:
        return True
    for path in _walk(tree):
        node_item = path[-1]
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if node_item.get("visible") is False:
            continue
        rect = _rect(node_item)
        if not _valid_rect(rect) or rect[1] >= 460:
            continue
        is_editable = (
            node_item.get("type") in ("EditText", "AutoCompleteTextView")
            or node_item.get("editable") is True
        )
        if is_editable and node_item.get("focused") is True:
            return True
    return False


def _search_input_has_text(tree, expected):
    """Check every live search-editor leaf, not only the action target.

    Android 15/HID can expose a WeChat editor and a same-rect child editor;
    the query text may be published on one while the other still exposes the
    placeholder.  Content verification must not select the placeholder leaf
    merely because it was the preferred action node.
    """
    expected = str(expected or "").strip()
    if not expected:
        return False
    for path in _walk(tree):
        item = path[-1]
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if item.get("visible") is False:
            continue
        if item.get("type") not in ("EditText", "AutoCompleteTextView") and item.get(
            "editable"
        ) is not True:
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] >= 460 or rect[3] > 520:
            continue
        if str(item.get("text") or "").strip() == expected:
            return True
    return False


def _tree_has_exact_text(tree, value, min_top=0, max_bottom=None):
    """Check a visible WeChat text marker without using it as an action rect."""
    expected = str(value or "").strip()
    if not expected:
        return False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != expected:
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] < min_top:
            continue
        if max_bottom is not None and rect[3] > max_bottom:
            continue
        return True
    return False


def _search_page_signature(tree, search_item):
    """Recognize WeChat search from the requested page marker and context."""
    if not search_item:
        return False
    # The empty search page has the unique “页面设置” DOM marker and the
    # visible search-category keywords.  The marker is only a state signal;
    # actions still use the live search input rectangle.
    if _tree_has_exact_text(tree, SEARCH_PAGE_MARKER) and any(
        _tree_has_exact_text(tree, keyword)
        for keyword in SEARCH_PAGE_KEYWORDS
    ):
        return True
    # Once a query is entered, WeChat may hide the category panel, result
    # section and marker from mode 6 even though they are visibly rendered.
    # A non-empty live editor plus the top cancel action is already a unique
    # search-page signature; do not downgrade this page to ``unknown`` and
    # block the bounded right-swipe reset.
    query = str(search_item[0][-1].get("text") or "").strip()
    return bool(query and _tree_has_exact_text(tree, "取消", max_bottom=420))


def _wechat_tree_fingerprint(tree):
    """Summarize visible WeChat tree content to verify a HID swipe changed it."""
    observed = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        text = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint")
        ).strip()
        if not text and item.get("scrollable") is not True:
            continue
        observed.append(
            (
                text,
                str(item.get("type") or ""),
                str(item.get("id") or ""),
                rect,
                bool(item.get("scrollable")),
            )
        )
    return tuple(sorted(observed, key=repr))


def _generic_wechat_gesture_rect():
    """Find a live WeChat content area for one bounded right-edge swipe."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    width, height = _device_size()
    candidates = []
    broad = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        raw_rect = _rect(item)
        rect = (
            max(0, min(width, raw_rect[0])),
            max(0, min(height, raw_rect[1])),
            max(0, min(width, raw_rect[2])),
            max(0, min(height, raw_rect[3])),
        )
        if not _valid_rect(rect):
            continue
        if rect[2] - rect[0] < int(width * 0.70) or rect[3] - rect[1] < 300:
            continue
        is_generic_fullscreen = (
            rect[0] <= 16
            and rect[1] <= 160
            and rect[2] >= width - 16
            and rect[3] >= int(height * 0.92)
        )
        if is_generic_fullscreen:
            continue
        broad.append(rect)
        label = " ".join(
            str(item.get(key) or "").strip().lower()
            for key in ("type", "className", "id", "resourceName")
        )
        if item.get("scrollable") is True or any(
            marker in label for marker in ("listview", "recyclerview", "scrollview")
        ):
            candidates.append(rect)
    if candidates:
        return max(candidates, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
    if broad:
        return (
            min(rect[0] for rect in broad),
            min(rect[1] for rect in broad),
            max(rect[2] for rect in broad),
            max(rect[3] for rect in broad),
        )
    return None


def _right_swipe_to_wechat_home(reason=""):
    """Return to chat home with at most two live, atomic right swipes."""
    for attempt in range(2):
        if _wechat_home_ready():
            print(
                "WECHAT_HOME_RESET_DONE strategy=right_swipe swipes={}".format(
                    attempt
                )
            )
            return
        # The targeted result list is already a live mode-6 action rectangle,
        # but some WeChat builds expose it only as a ListView with a neutral
        # package name. Reuse that live rectangle before declaring the swipe
        # unavailable; never fall back to a fixed screen coordinate.
        gesture_rect = _generic_wechat_gesture_rect() or _targeted_scroll_bounds()
        if not gesture_rect:
            raise RuntimeError(
                "{}前未找到实时微信滑动区域，停止右滑".format(reason or "返回首页")
            )
        left, top, right, bottom = gesture_rect
        # Search-page return uses the requested live-area left-to-middle
        # gesture.  This path is only for leaving search/results; profile
        # return uses the bottom “微信” tab instead.
        content_width = right - left
        start_x = int(left + content_width * 0.00)
        end_x = int(left + content_width * 0.50)
        start_y = int(top + (bottom - top) * 0.50)
        width, height = _device_size()
        if not (
            0 <= start_x < width
            and 0 <= end_x < width
            and 0 <= start_y < height
            and start_x < end_x
        ):
            raise RuntimeError("{}右滑实时区域超出 HID 范围".format(reason or "返回首页"))
        _hid_swipe(
            start_x,
            start_y,
            end_x,
            start_y,
            "右滑返回微信首页 {}/2".format(attempt + 1),
        )
        if _wait_for(_wechat_home_ready, timeout=5, interval=0.25):
            print(
                "WECHAT_HOME_RESET_DONE strategy=right_swipe swipes={}".format(
                    attempt + 1
                )
            )
            return
    raise RuntimeError(
        "{}后两次右滑仍未确认微信首页".format(reason or "返回首页")
    )


def _tree_has_top_text(tree, value, max_bottom=520):
    expected = str(value or "").strip()
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != expected:
            continue
        rect = _rect(item)
        if _valid_rect(rect) and rect[1] <= max_bottom:
            return True
    return False


def _truthy_tree_value(value):
    return str(value).strip().lower() in {"1", "true", "yes", "selected", "checked"}


def _tree_tab_is_selected(path):
    """Prefer an explicit selected marker when this WeChat tree exposes one."""
    for item in reversed(path):
        for key in ("selected", "isSelected", "activated", "checked"):
            if _truthy_tree_value(item.get(key)):
                return True
        marker = " ".join(
            str(item.get(key) or "").strip()
            for key in ("stateDescription", "desc", "contentDesc")
        )
        if re.search(r"(?:已)?选中|selected", marker, re.IGNORECASE):
            return True
    return False


def _wechat_home_tree_signature(tree):
    """Require the actual WeChat chat-list tab, not merely bottom-tab nodes."""
    if not tree or _search_input_item(tree):
        return False
    # On this verified WeChat build, the chat-list home may expose an action-
    # bar back control together with the bottom tabs and search entry. Preserve
    # that known-good fallback; reject only the explicit sibling-tab titles
    # and a live search editor below.
    # These titles identify sibling WeChat tabs/pages.  Their bottom-tab nodes
    # can remain in the accessibility tree, so they must not count as home.
    if any(_tree_has_top_text(tree, title) for title in ("通讯录", "发现", "我")):
        return False
    _, height = _device_size()
    chat_tabs = []
    me_tabs = []
    chat_tab_selected = []
    me_tab_selected = []
    top_search = False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[1] >= int(height * 0.72):
            text = str(item.get("text") or "").strip()
            if text == "微信":
                chat_tabs.append(item)
                chat_tab_selected.append(_tree_tab_is_selected(path))
            elif text == "我":
                me_tabs.append(item)
                me_tab_selected.append(_tree_tab_is_selected(path))
        if rect[1] <= 260:
            label = " ".join(
                str(item.get(key) or "").strip()
                for key in ("text", "desc", "contentDesc", "hint", "id")
            )
            if "搜索" in label or "search" in label.lower():
                top_search = True
    if not chat_tabs or not me_tabs or not top_search:
        return False
    # Prefer explicit selection metadata when it is available. This Android /
    # WeChat build can expose checked=false on ordinary tab nodes, so absence
    # of a positive marker is not a negative signal; the structural signature
    # is the bounded fallback. A positive “我” marker is conclusive.
    if any(me_tab_selected) and not any(chat_tab_selected):
        return False
    return True


def _wechat_page_state(tree=None):
    """Classify the visible WeChat page from one live mode-6 tree snapshot."""
    if tree is None:
        try:
            tree = _dump(UI_MODE)
        except Exception:
            return "unknown", ""
    if not any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    ):
        return "unknown", ""

    search_item = _search_input_item(tree)
    if _search_page_signature(tree, search_item):
        query = str(search_item[0][-1].get("text") or "").strip()
        return "search", query

    width, height = _device_size()
    has_message_editor = False
    top_texts = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        text = str(item.get("text") or "").strip()
        if text and rect[3] <= 360:
            top_texts.append(text)
        if rect[1] >= int(height * 0.62) and (
            item.get("type") in ("EditText", "AutoCompleteTextView")
            or item.get("editable") is True
        ):
            has_message_editor = True

    # Confirm the positive home signature before interpreting a stale
    # action-bar container as a child-page back button.
    if _wechat_home_tree_signature(tree):
        return "home", ""

    up = _point_for_id_in_tree(
        tree,
        "com.tencent.mm:id/actionbar_up_indicator",
        max_top=320,
    )
    if up:
        if has_message_editor and any(
            re.search(r"[（(]\\s*\\d{1,5}\\s*[)）]", text) for text in top_texts
        ):
            return "group_chat", ""
        if has_message_editor:
            return "chat", ""
        return "child", ""

    # WeChat can resume on a root tab such as “我” or “通讯录”. These pages
    # have no action-bar back button; the caller uses the bounded live-area
    # right-swipe reset and then confirms the fresh home tree.
    for title, state in (("通讯录", "contacts"), ("发现", "discover"), ("我", "profile")):
        if _tree_has_top_text(tree, title):
            return state, ""
    return "unknown", ""


def _reset_from_search_page():
    """Return to chat-list home with bounded official HID right swipes."""
    if _wait_for(_wechat_home_ready, timeout=2, interval=0.25):
        print("WECHAT_HOME_RESET_SKIPPED reason=home_signature_already_true")
        return
    print("WECHAT_HOME_RESET_DIRECT reason=home_signature_not_confirmed")
    _right_swipe_to_wechat_home("微信页面返回")


def _action_scene_matches(expected, point=None):
    """Check the live page immediately before an inventory HID action."""
    page_state, _ = _wechat_page_state()
    if isinstance(expected, (tuple, list, set)):
        if page_state == "unknown" and "unknown" in expected:
            return _wechat_context_present()
        return page_state in expected
    if expected in ("home", "chat_list"):
        return page_state == "home" and _wechat_home_ready()
    if expected == "profile":
        return bool(_read_wechat_id())
    if expected == "search":
        # The live WeChat EditText is the reliable action target. The
        # surrounding search-page marker may lag or be absent while the page
        # is rendering, so do not block input when the editable node exists.
        try:
            tree = _dump(UI_MODE)
        except Exception:
            return False
        return bool(_search_input_item(tree))
    if expected == "targeted_results":
        return page_state == "search" and bool(_target_group_rows())
    if expected == "group_chat":
        return page_state in ("group_chat", "chat")
    if expected == "chooser":
        if point is None:
            return bool(_chooser_points())
        current = _chooser_points()
        return any(
            abs(int(x) - int(point[0])) <= 4 and abs(int(y) - int(point[1])) <= 4
            for x, y in current
        )
    return page_state == expected


def _before_action(expected, action_name, point=None):
    """Keep page classification observational; never gate a live target action."""
    print(
        "TARGET_ACTION_PAGE_GATE_SKIPPED action={} expected={} reason=live_target_only".format(
            action_name, expected
        )
    )


def _search_icon_rect():
    """Locate the WeChat search action from a live mode-6 tree."""
    width, _ = _device_size()
    try:
        tree = _dump(UI_MODE)
    except Exception as exc:
        print("TARGET_SEARCH_TREE_ERROR", str(exc)[:160])
        return None
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        if item.get("visible") is False:
            continue
        rect = _action_rect(path)
        if not _valid_rect(rect) or rect[1] >= 360 or rect[0] < int(width * 0.55):
            continue
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "id")
        )
        if "搜索" in label or "search" in label.lower():
            matches.append(rect)
    matches = sorted(set(matches))
    return matches[0] if len(matches) == 1 else None


def _text_rects(text, top=0, bottom=None, contains=False):
    """Return action rectangles for exact/contained text from mode 6."""
    wanted = str(text or "").strip()
    if not wanted:
        return []
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return []
    matches = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") not in (WECHAT_PACKAGE, None, "") or item.get("visible") is False:
            continue
        value = str(item.get("text") or "").strip()
        if (wanted not in value) if contains else (value != wanted):
            continue
        # “更多群聊” is a text link inside a clickable ListView.  Its own
        # live rect is the actionable target; the ListView rect is the whole
        # result page and would click an unrelated point.
        rect = _rect(item) if value == wanted else _action_rect(path)
        if not _valid_rect(rect) or rect[1] < top:
            continue
        if bottom is not None and rect[3] > bottom:
            continue
        matches.append(rect)
    return sorted(set(matches))


def _search_empty_result_marker():
    """Return an explicit WeChat empty-result label, if the live tree has one."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") not in (WECHAT_PACKAGE, None, ""):
            continue
        if any(node.get("visible") is False for node in path):
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] < 250 or rect[3] > 1800:
            continue
        labels = (
            item.get("text"),
            item.get("desc"),
            item.get("contentDesc"),
        )
        for marker in SEARCH_EMPTY_RESULT_MARKERS:
            if any(marker in " ".join(str(label or "").split()) for label in labels):
                return marker
    return None


def _more_group_link_rects():
    """读取实时 mode=6 树中的“更多群聊”文字区域，兼容附带数量的文案。"""
    tree = _dump(UI_MODE)
    if not tree:
        return []
    screen_width, screen_height = _device_size()
    matches = []
    for path in _walk(tree):
        item = path[-1]
        package_name = item.get("packageName")
        if package_name not in (WECHAT_PACKAGE, None, ""):
            continue
        if any(node.get("visible") is False for node in path):
            continue
        labels = (
            item.get("text"),
            item.get("desc"),
            item.get("contentDesc"),
        )
        has_more_label = any(
            "更多群聊" in " ".join(str(label or "").split())
            for label in labels
        )
        if not has_more_label:
            continue
        # 使用文字节点自己的实时范围，避免点到包住链接的整块 ListView。
        rect = _rect(item)
        if (
            not _valid_rect(rect)
            or rect[1] < 250
            or rect[2] > screen_width
            or rect[3] > screen_height
        ):
            continue
        matches.append(rect)
    return sorted(set(matches))


def _resolve_more_group_link_rect(rects, prefix, visible_group_count):
    """No link means this query has no extra page; duplicate links are ambiguous."""
    if len(rects) == 1:
        return rects[0]
    if not rects:
        print(
            "TARGET_SEARCH_NO_MORE_GROUP_LINK prefix={} visibleRows={} stop=targeted_no_more_group_link".format(
                prefix, visible_group_count
            )
        )
        return None
    print(
        "TARGET_MORE_GROUPS_LINK_AMBIGUOUS prefix={} matches={} visibleRows={} action=abort_scan".format(
            prefix, len(rects), visible_group_count
        )
    )
    raise RuntimeError(
        "实时控件树出现多个“更多群聊”入口，无法安全点击："
        "prefix={} matches={} visibleRows={}".format(
            prefix, len(rects), visible_group_count
        )
    )


def _search_submit_rect():
    """Return the live WeChat search-submit button, if this build exposes it."""
    return _find_desc_or_id_rect(
        descs=("搜索", "Search"),
        ids=(WECHAT_PACKAGE + ":id/mdg",),
        top=150,
        bottom=360,
    )


def _targeted_scroll_bounds():
    """Return the live WeChat result-list rect for HID scrolling.

    WeChat's mode-6 auxiliary tree may expose the result ``ListView`` while
    reporting ``scrollable=false``.  The list type and its live rectangle are
    still valid action evidence; requiring the boolean would incorrectly stop
    after the first visible page.  Generic full-screen containers remain
    excluded so this never becomes a fixed-coordinate fallback.
    """
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    candidates = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") not in (WECHAT_PACKAGE, None, ""):
            continue
        if item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[2] - rect[0] <= 300 or rect[3] - rect[1] <= 300:
            continue
        node_type = " ".join(
            str(item.get(key) or "").strip().lower()
            for key in ("type", "className", "id", "resourceName")
        )
        is_list = any(
            marker in node_type
            for marker in ("listview", "recyclerview", "scrollview", "mfg")
        )
        is_scrollable = item.get("scrollable") is True
        _, device_height = _device_size()
        is_generic_fullscreen = (
            not is_list
            and rect[0] <= 16
            and rect[1] <= 160
            and rect[2] >= _device_size()[0] - 16
            and rect[3] >= int(device_height * 0.92)
        )
        if is_generic_fullscreen:
            continue
        area = (rect[2] - rect[0]) * (rect[3] - rect[1])
        score = (3 if is_list else 0) + (2 if is_scrollable else 0)
        candidates.append((score, area, rect))
    if not candidates:
        return None
    return max(candidates, key=lambda value: (value[0], value[1]))[2]


GROUP_CODE_PATTERN = re.compile(r"^[gc]\d{1,8}$", re.IGNORECASE)


def _target_group_row_rect(path):
    """Find the nearest result-row container around a 群聊名 node."""
    _, height = _device_size()
    for item in reversed(path[:-1]):
        rect = _rect(item)
        row_height = rect[3] - rect[1]
        if (
            _valid_rect(rect)
            and rect[2] - rect[0] >= int(_device_size()[0] * 0.65)
            and 70 <= row_height <= min(520, int(height * 0.35))
        ):
            return rect
    return _rect(path[-1])


def _target_group_rows():
    """Read visible code/name rows from WeChat's 群聊 search result list."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return []
    items = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        text = " ".join(str(item.get("text") or "").split())
        rect = _rect(item)
        if text and _valid_rect(rect):
            items.append({"text": text, "rect": rect, "path": path})

    # Search can show a “最常使用/最近使用” section before the actual
    # “群聊” section.  Only rows below the live “群聊” header belong to the
    # targeted inventory; if WeChat omits the header after “更多群聊”, keep
    # all visible result rows.
    group_headers = [
        item["rect"]
        for item in items
        if item["text"] == "群聊"
    ]
    group_section_top = min((rect[3] for rect in group_headers), default=None)

    name_items = []
    for item in items:
        match = re.match(r"^群聊名\s*[:：]\s*(.+?)\s*$", item["text"])
        if match:
            row_rect = _target_group_row_rect(item["path"])
            name_items.append((match.group(1).strip(), item, row_rect))

    rows_by_route = {}
    for name, item, row_rect in name_items:
        name_center = (item["rect"][1] + item["rect"][3]) / 2.0
        if group_section_top is not None and name_center < group_section_top:
            continue
        row_center = (row_rect[1] + row_rect[3]) / 2.0
        row_height = max(1, row_rect[3] - row_rect[1])
        code_items = []
        for candidate in items:
            if not GROUP_CODE_PATTERN.match(candidate["text"]):
                continue
            center = (candidate["rect"][1] + candidate["rect"][3]) / 2.0
            in_row = row_rect[1] - 8 <= center <= row_rect[3] + 8
            near_row = abs(center - row_center) <= max(90, row_height * 0.75)
            if in_row or near_row:
                code_items.append((abs(center - row_center), candidate["text"].lower()))
        if not code_items:
            print("TARGET_GROUP_ROW_WITHOUT_CODE", name)
            continue
        group_code = sorted(code_items, key=lambda value: value[0])[0][1]
        action_rect = _clickable_ancestor(item["path"]) or row_rect
        if not _valid_rect(action_rect):
            continue
        key = (group_code, name)
        row = rows_by_route.get(key)
        if row is None:
            row = {
                "groupCode": group_code,
                "groupName": name,
                "rect": action_rect,
                "rowRects": [],
                "occurrenceCount": 0,
            }
            rows_by_route[key] = row
        # A single visible WeChat row can expose duplicate text nodes. Count
        # distinct live row rectangles only; equal route labels at different
        # rectangles become one aggregate route with a physical multiplicity.
        if action_rect not in row["rowRects"]:
            row["rowRects"].append(action_rect)
            row["occurrenceCount"] += 1
            row["rect"] = min(row["rowRects"], key=lambda rect: rect[1])
    return sorted(
        rows_by_route.values(),
        key=lambda value: (value["rect"][1], value["groupCode"], value["groupName"]),
    )


def _target_group_signature(rows):
    # Include each visible same-name row's current rectangle, not just the
    # aggregate label, so movement detection remains sensitive while scrolling.
    return tuple(sorted(
        (
            row["groupCode"],
            row["groupName"],
            int(rect[1]),
            int(rect[3]),
        )
        for row in rows
        for rect in (row.get("rowRects") or [row["rect"]])
    ))


def _scan_targeted_group_rows(prefix=None, progress=None):
    """Search one PC-configured group-code prefix and read all matching rows."""
    prefix = str(prefix or GROUP_SEARCH_PREFIXES[0]).strip()
    if not prefix:
        raise RuntimeError("未配置微信群编号搜索前缀")
    progress = progress if isinstance(progress, dict) else {}

    def _mark_progress(stage, **values):
        # Preserve the last completed phase and actual HID scroll count if a
        # later UI read raises; the caller includes this snapshot in the report.
        progress["stage"] = stage
        progress.update(values)
        print(
            "TARGET_PREFIX_STAGE prefix={} stage={} scrolls={} groups={}".format(
                prefix,
                stage,
                progress.get("scrollCount", 0),
                progress.get("groupCount", 0),
            )
        )

    _mark_progress("locate_search", scrollCount=0, groupCount=0)
    search = _wait_for(
        lambda: _find_desc_or_id_rect(
            descs=("搜索", "Search"),
            ids=(WECHAT_PACKAGE + ":id/actionbar_search",),
            top=0,
            bottom=360,
        )
        or _search_icon_rect(),
        timeout=10,
    )
    if not search:
        raise RuntimeError("控件树未暴露唯一的微信搜索入口")
    _mark_progress("open_search")
    _tap(
        (search[0] + search[2]) / 2,
        (search[1] + search[3]) / 2,
        expected="home",
        action_name="打开微信搜索",
    )
    input_rect = _wait_for(_search_input_action_rect, timeout=8)
    if not input_rect:
        raise RuntimeError("微信搜索框未出现")
    _mark_progress("focus_search")
    focused = False
    for attempt in range(2):
        if attempt > 0:
            input_rect = _wait_for(_search_input_action_rect, timeout=3)
            if not input_rect:
                break
        _tap(
            (input_rect[0] + input_rect[2]) / 2,
            (input_rect[1] + input_rect[3]) / 2,
            action_name="聚焦微信群搜索框" if attempt == 0 else "再次聚焦微信群搜索框",
        )
        print(
            "TARGET_ACTION_HID_OK action={} state=search".format(
                "聚焦微信群搜索框" if attempt == 0 else "再次聚焦微信群搜索框"
            )
        )
        time.sleep(1.2)
        focused = bool(_wait_for(_search_input_focused, timeout=3, interval=0.25))
        print(
            "TARGET_SEARCH_FOCUS_CONFIRMED attempt={} focused={}".format(
                attempt + 1, focused
            )
        )
        if focused:
            break
    if not focused:
        raise RuntimeError("微信搜索框点击后未在控件树中确认获得焦点")
    _mark_progress("input_query")
    def _query_matches():
        try:
            tree = _dump(UI_MODE)
        except Exception:
            return False
        return _search_input_has_text(tree, prefix)

    def _search_results_visible():
        return bool(
            _target_group_rows()
            or _more_group_link_rects()
            or _search_empty_result_marker()
        )

    print("TARGET_ACTION_WAIT action=输入微信群编号 seconds=1.2")
    # The controlled experiment uses AScript's official IME API for the
    # focused search editor.  Taps, navigation and scrolling remain official
    # ESP32 HID actions; this changes only the search-text injection channel.
    if re.fullmatch(r"[\x20-\x7e]+", prefix):
        if not Ime.is_active():
            raise RuntimeError("AScript 输入法未处于激活状态")
        Ime.input(prefix)
        print(
            "TARGET_ACTION_IME_OK action=输入微信群编号 method=ascript_ime_input state=search"
        )
    else:
        Clipboard.put(prefix)
        _hid().paste()
        print(
            "TARGET_ACTION_HID_OK action=输入微信群编号 method=clipboard_paste state=search"
        )
    time.sleep(1.5)
    print("TARGET_ACTION_WAIT action=核验微信群编号 seconds=1.5")
    query_verified = bool(_wait_for(_query_matches, timeout=6, interval=0.25))
    if not query_verified:
        # On this Android 15/Gboard build, HID paste can leave the value in
        # the IME composition strip while the WeChat EditText remains empty.
        # Commit that live keyboard value with the official HID Enter key; do
        # not click a guessed keyboard coordinate.
        print("TARGET_SEARCH_QUERY_EMPTY_AFTER_IME_INPUT prefix={}".format(prefix))
        _hid().enter()
        print("TARGET_ACTION_HID_OK action=提交微信群搜索输入 state=search")
        _settle_after_hid("提交微信群搜索输入")
        query_verified = bool(_wait_for(_query_matches, timeout=3, interval=0.25))
        if not query_verified and not _wait_for(
            _search_results_visible, timeout=5, interval=0.25
        ):
            raise RuntimeError("输入微信群编号后未在控件树中核验到搜索内容")
    _mark_progress("submit_search")
    if query_verified:
        print("TARGET_SEARCH_QUERY prefix={}".format(prefix))
        submit_rect = _wait_for(_search_submit_rect, timeout=3, interval=0.25)
        if submit_rect:
            _tap(
                (submit_rect[0] + submit_rect[2]) / 2,
                (submit_rect[1] + submit_rect[3]) / 2,
                action_name="点击微信搜索",
            )
            if not _wait_for(_search_results_visible, timeout=10, interval=0.25):
                raise RuntimeError("点击微信搜索后未读到搜索结果")
            empty_marker = _search_empty_result_marker()
            if empty_marker:
                print(
                    "TARGET_SEARCH_EMPTY_RESULT prefix={} marker={} stop=targeted_no_more_group_link".format(
                        prefix,
                        empty_marker,
                    )
                )
            print("TARGET_SEARCH_SUBMIT_CONFIRMED prefix={}".format(prefix))

    initial_rows = _target_group_rows()
    _mark_progress("open_more_groups", groupCount=len(initial_rows))
    more_rects = _wait_for(_more_group_link_rects, timeout=8) or []
    more_rect = _resolve_more_group_link_rect(
        more_rects, prefix=prefix, visible_group_count=len(initial_rows)
    )
    if more_rect is None:
        # WeChat omits this link when the prefix has no additional group page;
        # in that case the visible rows are the complete result for this query.
        stop_reason = "targeted_no_more_group_link"
        _mark_progress(
            "complete",
            groupCount=len(initial_rows),
            scrollCount=0,
            stopReason=stop_reason,
        )
        return initial_rows, stop_reason, 0
    _tap(
        (more_rect[0] + more_rect[2]) / 2,
        (more_rect[1] + more_rect[3]) / 2,
        expected="search",
        action_name="打开更多群聊",
    )
    if not _wait_for(_target_group_rows, timeout=12):
        raise RuntimeError("点击“更多群聊”后未读到群编号和群聊名")

    collected_by_route = {}
    previous_signature = None
    unchanged_rounds = 0
    scroll_count = 0
    stop_reason = "targeted_scroll_limit"
    _mark_progress("collect_rows", scrollCount=0, groupCount=0)
    for _ in range(MAX_TARGETED_SCROLLS + 1):
        rows = _target_group_rows()
        signature = _target_group_signature(rows)
        if not rows:
            stop_reason = "targeted_rows_empty"
            break
        for row in rows:
            key = (row["groupCode"], row["groupName"])
            existing = collected_by_route.get(key)
            if existing is None:
                collected_by_route[key] = dict(row)
            else:
                # Adjacent scroll snapshots overlap. The maximum co-visible
                # multiplicity avoids counting the same rows twice; row index
                # or screen position is never promoted to a persistent ID.
                existing["occurrenceCount"] = max(
                    int(existing.get("occurrenceCount") or 1),
                    int(row.get("occurrenceCount") or 1),
                )
        collected = list(collected_by_route.values())
        collected_count = sum(int(row.get("occurrenceCount") or 1) for row in collected)
        _mark_progress("collect_rows", groupCount=collected_count)
        if signature and signature == previous_signature:
            unchanged_rounds += 1
        else:
            unchanged_rounds = 0
        if unchanged_rounds >= 2:
            stop_reason = "targeted_bottom_stable"
            break
        previous_signature = signature
        bounds = _targeted_scroll_bounds()
        if not bounds:
            stop_reason = "targeted_no_live_list_rect"
            break
        left, top, right, bottom = bounds
        if bottom - top < 300:
            stop_reason = "targeted_invalid_scroll_rect"
            break
        x = int((left + right) / 2)
        margin = max(80, min(220, int((bottom - top) * 0.12)))
        _before_action("search", "滚动群聊搜索结果")
        _mark_progress("hid_scroll", groupCount=collected_count)
        _swipe(x, bottom - margin, x, top + margin)
        scroll_count += 1
        _mark_progress("wait_scroll_result", scrollCount=scroll_count, groupCount=collected_count)
        moved = _wait_for(
            lambda: _target_group_signature(_target_group_rows()) != signature,
            timeout=4,
            interval=0.25,
        )
        if moved:
            unchanged_rounds = 0
    print(
        "TARGET_SEARCH_SCAN_DONE prefix={} rows={} scrolls={} stopReason={}".format(
            prefix, sum(int(row.get("occurrenceCount") or 1) for row in collected), scroll_count, stop_reason
        )
    )
    _mark_progress(
        "complete",
        groupCount=sum(int(row.get("occurrenceCount") or 1) for row in collected),
        scrollCount=scroll_count,
        stopReason=stop_reason,
    )
    return collected, stop_reason, scroll_count


def _chooser_points():
    points = []
    try:
        tree = _dump(UI_MODE)
        chooser_marker = any(
            str(path[-1].get("text") or "").strip()
            in ("请选择要使用的应用", "取消")
            for path in _walk(tree)
        )
        for path in _walk(tree):
            item = path[-1]
            if (
                item.get("text") == "微信"
                and item.get("visible") is not False
            ):
                # System resolvers may publish the label under a system
                # package. The exact GridView item rect is still mandatory.
                if item.get("packageName") != DUAL_APP_PACKAGE and not chooser_marker:
                    continue
                # Both labels live under one clickable GridView. Resolve the
                # nearest per-entry container immediately below that GridView;
                # using the shared ancestor would send both slots to one point.
                grid_index = None
                for index in range(len(path) - 1, -1, -1):
                    if str(path[index].get("type") or "") == "GridView":
                        grid_index = index
                        break
                if grid_index is None or grid_index + 1 >= len(path):
                    continue
                item_container = path[grid_index + 1]
                if str(item_container.get("type") or "") == "GridView":
                    continue
                rect = _rect(item_container)
                if _valid_rect(rect) and rect[2] - rect[0] < int(_device_size()[0] * 0.75):
                    points.append(
                        (int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2))
                    )
    except Exception as exc:
        print("微信双开选择器读取失败:", exc)
    points = sorted(set(points), key=lambda point: point[0])
    return points if len(points) == 2 else []


def _select_wechat_instance(slot_index):
    points = _wait_for(_chooser_points, timeout=10)
    if not points or len(points) <= slot_index:
        raise RuntimeError("未找到双开微信选择器的两个微信入口")
    _tap(
        *points[slot_index],
        expected="chooser",
        action_name="选择双开微信槽位 {}".format(slot_index),
    )


def _wechat_home_point():
    """Return the live ``我`` rect only from one valid mode-6 snapshot."""
    _, height = _device_size()
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    if not any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    ):
        return None
    if not _wechat_home_tree_signature(tree):
        return None
    return _point_for_text_in_tree(tree, "我", min_top=int(height * 0.72))


def _wechat_profile_tab_point():
    """Return the live bottom ``我`` target without using page classification."""
    _, height = _device_size()
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    if not any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    ):
        return None
    return _point_for_text_in_tree(tree, "我", min_top=int(height * 0.72))


def _wechat_home_ready():
    """Require the actual chat-list home before reading the profile."""
    return bool(_wechat_home_point())


def _wechat_chat_tab_point():
    """Return the live bottom “微信” tab used to leave the profile page."""
    _, height = _device_size()
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return None
    if not any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    ):
        return None
    return _point_for_text_in_tree(tree, "微信", min_top=int(height * 0.72))


def _open_wechat(slot_index):
    print("TARGET_WECHAT_OPEN_BEGIN slot={}".format(slot_index))
    _home()
    print("TARGET_WECHAT_HOME_SENT slot={}".format(slot_index))
    open_app(WECHAT_PACKAGE)
    print("TARGET_WECHAT_PACKAGE_OPENED slot={}".format(slot_index))
    _select_wechat_instance(slot_index)
    print("TARGET_WECHAT_INSTANCE_SELECTED slot={}".format(slot_index))
    print("TARGET_WECHAT_TREE_WAIT slot={} seconds=2".format(slot_index))
    time.sleep(2.0)
    deadline = time.time() + 25
    empty_tree_logged = False
    last_page_observation = None
    while time.time() < deadline:
        profile_tab_point = _wechat_profile_tab_point()
        if profile_tab_point:
            print("TARGET_WECHAT_PROFILE_TAB_READY slot={} target=我".format(slot_index))
            # Return the live “我” tab rectangle so the caller can inspect the
            # full profile page and confirm the account identity.  Do not
            # swipe before this target action; page classification is only
            # observational and may lag on Android 15/HID.
            return profile_tab_point
        if not empty_tree_logged:
            try:
                tree = _dump(UI_MODE)
                has_wechat_node = any(
                    item.get("packageName") == WECHAT_PACKAGE
                    and item.get("visible") is not False
                    for path in _walk(tree)
                    for item in (path[-1],)
                )
            except Exception:
                has_wechat_node = False
            if not has_wechat_node:
                print("TARGET_WECHAT_TREE_WAITING slot={} reason=empty_or_unavailable".format(slot_index))
                empty_tree_logged = True
        if not _wechat_context_present():
            time.sleep(1.2)
            continue
        page_state, query = _wechat_page_state()
        # Do not execute a recovery swipe before the required “我” action.
        # If the live target cannot be located, stop with the blocker capture
        # path instead of navigating from an ambiguous page.
        observation = (page_state, query)
        if observation != last_page_observation:
            print("TARGET_WECHAT_PAGE_STATE slot={} state={} query={}".format(slot_index, page_state, query))
            last_page_observation = observation
        time.sleep(1.2)
    raise RuntimeError("微信首页未出现可唯一定位的“我”入口，未执行右滑")


def _open_wechat_chat_home():
    """Return from the profile page by clicking the live “微信” tab."""
    chat_tab_point = _wait_for(_wechat_chat_tab_point, timeout=8, interval=0.25)
    if not chat_tab_point:
        raise RuntimeError("微信“我”页未找到唯一的“微信”Tab，未执行滑动")
    _tap(
        *chat_tab_point,
        expected="profile",
        action_name="点击微信Tab返回首页",
    )
    if not _wait_for(_wechat_home_ready, timeout=8, interval=0.25):
        raise RuntimeError("点击微信Tab后未确认微信首页聊天列表")
    print("TARGET_CHAT_HOME_READY strategy=wechat_tab")


def _wechat_context_present():
    """Return whether the live tree still contains a visible WeChat page."""
    try:
        tree = _dump(UI_MODE)
    except Exception:
        return False
    return any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    )


def _reset_to_wechat_home(reason):
    """Finish one account on the top-level WeChat chat-list home."""
    if not _wait_for(_wechat_context_present, timeout=5, interval=0.25):
        raise RuntimeError("{}时微信控件树不可用，未执行盲操作".format(reason))
    if _wait_for(_wechat_home_ready, timeout=3, interval=0.25):
        print("TARGET_WECHAT_HOME_RESET_DONE reason={} strategy=existing_home".format(reason))
        return
    # Page classification is observational only. If the live tree has not
    # confirmed home, the bounded HID reset is the next action; ``unknown``
    # must not suppress it because search-result trees are incomplete on this
    # Android/WeChat build.
    print("TARGET_WECHAT_HOME_RESET_DIRECT reason={}".format(reason))
    _reset_from_search_page()
    if not _wait_for(_wechat_home_ready, timeout=8, interval=0.25):
        _open_wechat_chat_home()
    if not _wait_for(_wechat_home_ready, timeout=8, interval=0.25):
        raise RuntimeError("{}后未确认微信首页聊天列表".format(reason))
    print("TARGET_WECHAT_HOME_RESET_DONE reason={}".format(reason))


def _read_nickname():
    try:
        tree = _dump()
    except Exception:
        tree = None
    texts = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        text = str(item.get("text") or "").strip()
        if text and _valid_rect(rect):
            texts.append((text, rect))
    anchors = [(text, rect) for text, rect in texts if text.startswith(("微信号：", "微信号:"))]
    if anchors:
        _, anchor_rect = anchors[0]
        candidates = [
            (text, rect)
            for text, rect in texts
            if not text.startswith(("微信号：", "微信号:"))
            and not text.startswith("+")
            and re.search(r"[A-Za-z\u4e00-\u9fff0-9]", text)
            and rect[3] <= anchor_rect[1]
            and rect[3] > 100
            and 2 <= len(text) <= 80
        ]
        if candidates:
            return max(candidates, key=lambda item: item[1][3])[0]

    matches = Ocr.find_all(rect=[0, 150, _device_size()[0], 650]) or []
    anchor = next(
        (
            item
            for item in matches
            if "微信号：" in str(item.get("text", ""))
            or "微信号:" in str(item.get("text", ""))
        ),
        None,
    )
    if not anchor:
        return None
    anchor_rect = _rect(anchor)
    for candidate in sorted(matches, key=lambda item: _rect(item)[3], reverse=True):
        text = str(candidate.get("text") or "").strip()
        rect = _rect(candidate)
        if (
            text
            and text != str(anchor.get("text") or "").strip()
            and "微信号" not in text
            and not text.startswith("+")
            and re.search(r"[A-Za-z\u4e00-\u9fff0-9]", text)
            and len(text) >= 2
            and rect[2] <= 850
            and rect[3] <= anchor_rect[1]
        ):
            return text
    return None


def _normalize_wechat_id(value):
    value = re.sub(r"\s+", "", str(value or "").strip())
    value = re.sub(r"^微信号[:：]?", "", value)
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$", value):
        return None
    return value.lower()


def _read_wechat_id():
    """Read one stable WeChat ID; return None for absent or ambiguous state."""
    try:
        tree = _dump()
    except Exception:
        tree = None
    texts = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        text = str(item.get("text") or "").strip()
        if text and _valid_rect(rect):
            texts.append((text, rect))
    candidates = set()
    anchors = []
    for text, rect in texts:
        if text.startswith(("微信号：", "微信号:")):
            anchors.append(rect)
            value = _normalize_wechat_id(text)
            if value:
                candidates.add(value)
    for anchor_rect in anchors:
        for text, rect in texts:
            if rect[1] < anchor_rect[3] or rect[1] > anchor_rect[3] + 180:
                continue
            value = _normalize_wechat_id(text)
            if value:
                candidates.add(value)

    try:
        matches = Ocr.find_all(rect=[0, 150, _device_size()[0], 650]) or []
    except Exception:
        matches = []
    for item in matches:
        text = str(item.get("text") or "").strip()
        if "微信号" in text:
            value = _normalize_wechat_id(text)
            if value:
                candidates.add(value)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _account_id(wechat_id):
    wechat_id = _normalize_wechat_id(wechat_id)
    if not wechat_id:
        raise RuntimeError("微信号格式无效，拒绝使用昵称生成账号 ID")
    return "wechat-id-" + wechat_id


def _post_json(path, payload, timeout=8):
    request = urllib.request.Request(
        BACKEND_URL.rstrip("/") + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Automation-Device-Token": DEVICE_TOKEN,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        # FastAPI carries the actionable validation/conflict reason in its
        # response body; HTTPError.__str__ alone hides it from the run report.
        try:
            body = exc.read().decode("utf-8", "replace")
            detail = json.loads(body) if body else {}
            detail = detail.get("detail", detail) if isinstance(detail, dict) else detail
            detail = str(detail)[:240]
        except Exception:
            detail = "响应正文不可读"
        raise RuntimeError(
            "PC 请求失败 HTTP {} {}: {}".format(exc.code, path, detail)
        )
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))[:180]
        raise RuntimeError("PC 请求失败 {}: {}".format(path, reason))


def _get_json(path):
    """Read PC-owned device configuration with the existing device token."""
    request = urllib.request.Request(
        BACKEND_URL.rstrip("/") + path,
        headers={"X-Automation-Device-Token": DEVICE_TOKEN},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _load_pc_scan_config():
    """Load PC scope; use local defaults only when backend auth is not configured."""
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {
            "searchPrefixes": list(GROUP_SEARCH_PREFIXES),
            "scanOnly": False,
            "source": "local_fallback",
        }
    response = _get_json(
        "/api/automation/devices/{}/group-scan-config".format(
            quote(DEVICE_ID, safe="")
        )
    )
    config = response.get("data") if isinstance(response, dict) else None
    if not isinstance(config, dict):
        raise RuntimeError("PC 未返回有效的微信群扫描配置")
    return {
        "searchPrefixes": list(_normalize_group_search_prefixes(config.get("searchPrefixes"))),
        "scanOnly": bool(config.get("scanOnly", False)),
        "source": "pc",
    }


def _heartbeat(account_id, nickname, wechat_id):
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    return _post_json(
        "/api/automation/devices/heartbeat",
        {
            "deviceId": DEVICE_ID,
            "name": DEVICE_NAME,
            "hidDeviceId": None,
            "status": "busy",
            "activeWechatAccountId": account_id,
            "capabilities": [
                "ascript",
                "official-esp32-hid",
                "double-wechat",
                "wechat-native-group-inventory",
            ],
            "metadata": {
                "identitySource": "wechat_profile_id",
                "wechatId": wechat_id,
                "nickname": nickname,
                "inputMode": INPUT_MODE,
            },
        },
    )


def _reconcile_account(
    account_id,
    nickname,
    contacts_group_names,
    contacts_scan_stop_reason,
    chat_group_names,
    chat_scan_stop_reason,
    scan_mode,
    group_mappings=None,
):
    # The phone's local scan strategy is named "targeted", but the currently
    # deployed PC API accepts only "full" or "incremental". A targeted scan
    # is a partial upsert, so report it as incremental on the wire; coverage
    # remains partial and cannot delete groups omitted from this scan.
    reconcile_scan_mode = "incremental" if scan_mode == "targeted" else scan_mode
    group_names = []
    for group_name in contacts_group_names + chat_group_names:
        if group_name not in group_names:
            group_names.append(group_name)
    contacts_complete = contacts_scan_stop_reason in {"reported_total", "stable"}
    chat_complete = chat_scan_stop_reason in {"bottom_stable", "empty_list"}
    coverage = (
        "complete"
        if reconcile_scan_mode == "full" and contacts_complete and chat_complete
        else "partial"
    )
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {
            "sent": False,
            "reason": "backend_not_configured",
            "coverage": coverage,
            "groupCount": len(group_names),
        }
    scan_id = "native-groups:{}:{}:{}".format(
        DEVICE_ID,
        account_id,
        int(time.time()),
    )
    # Inventory reconciliation can touch many existing group rows. Its old
    # 8-second limit could mark a completed scan degraded before PC replied;
    # keep the wait bounded while giving this write endpoint time to respond.
    return _post_json(
        "/api/automation/group-candidates/reconcile",
        {
            "deviceId": DEVICE_ID,
            "wechatAccountId": account_id,
            "wechatAccountName": nickname,
            "scanId": scan_id,
            "scanMode": reconcile_scan_mode,
            "coverage": coverage,
            "contactsScanStopReason": contacts_scan_stop_reason,
            "chatListScanStopReason": chat_scan_stop_reason,
            "contactsGroupCount": len(contacts_group_names),
            "chatListGroupCount": len(chat_group_names),
            "groupNames": group_names,
            "groupMappings": group_mappings or [],
            # Only a scanner that proves both lists reached their end may
            # remove stale native-group rows. Partial scans only upsert data.
            "deleteMissing": coverage == "complete",
        },
        timeout=30,
    )


def _preflight_batch_no():
    try:
        value = int(str(os.environ.get("TEAMBUY_SEND_BATCH_NO", "1") or "1").strip())
    except Exception:
        value = 1
    return max(1, min(value, 100))


def _preflight_group_codes():
    raw = str(os.environ.get("TEAMBUY_SEND_GROUP_CODES", "c1001") or "c1001")
    result = []
    for value in raw.split(","):
        code = " ".join(value.split()).strip()
        if code and code not in result:
            result.append(code)
    return result or ["c1001"]


def _queue_preflight_tasks(accounts, scan_errors):
    """Create PC-side tasks only; the sender is intentionally not loaded."""
    batch_no = _preflight_batch_no()
    group_codes = _preflight_group_codes()
    run_id = "wechat-preflight:{}:{}".format(DEVICE_ID, int(time.time()))
    successful_accounts = [
        account["accountId"]
        for account in accounts
        if account.get("status") == "success" and account.get("accountId")
    ]
    if scan_errors or len(successful_accounts) != len(SCAN_SLOT_INDICES):
        return {
            "runId": run_id,
            "batchNo": batch_no,
            "groupCodes": group_codes,
            "createdCount": 0,
            "targetCount": 0,
            "skipped": "scan_not_complete_for_all_accounts",
        }
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {
            "runId": run_id,
            "batchNo": batch_no,
            "groupCodes": group_codes,
            "createdCount": 0,
            "targetCount": 0,
            "skipped": "backend_not_configured",
        }
    response = _post_json(
        "/api/automation/group-content-plans/device-run",
        {
            "deviceId": DEVICE_ID,
            "batchNo": batch_no,
            "wechatAccountIds": successful_accounts,
            "groupCodes": group_codes,
            "maxTargets": 1000,
            "runId": run_id,
        },
    )
    result = response.get("data") if isinstance(response, dict) else None
    result = result if isinstance(result, dict) else {}
    print(
        "BATCH_RUN_QUEUED runId={} batchNo={} groupCodes={} accounts={} tasks={} targets={}".format(
            run_id,
            batch_no,
            ",".join(group_codes),
            len(successful_accounts),
            result.get("createdCount", 0),
            result.get("targetCount", 0),
        )
    )
    skipped_items = result.get("skippedItems", [])
    for skipped_item in skipped_items:
        if not isinstance(skipped_item, dict):
            continue
        print(
            "BATCH_TARGET_SKIPPED candidateId={} groupCode={} groupName={} reasonCode={} reason={}".format(
                skipped_item.get("candidateId", ""),
                skipped_item.get("groupCode", ""),
                skipped_item.get("groupName", ""),
                skipped_item.get("reasonCode", ""),
                skipped_item.get("reason", ""),
            )
        )
    return {
        "runId": run_id,
        "batchNo": batch_no,
        "groupCodes": group_codes,
        "createdCount": result.get("createdCount", 0),
        "candidateCount": result.get("candidateCount", 0),
        "targetCount": result.get("targetCount", 0),
        "skippedCount": result.get("skippedCount", 0),
        "skippedItems": skipped_items,
    }


def _notify_preflight_completion(report):
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    try:
        response = _post_json("/api/automation/runs/complete", report)
        result = response.get("data") if isinstance(response, dict) else None
        return result if isinstance(result, dict) else {"sent": False, "reason": "empty_response"}
    except Exception as exc:
        print("运行完成通知回传失败：{}".format(exc))
        # Keep the failure class available to the launcher status record while
        # avoiding persistence of request headers or credential material.
        return {
            "sent": False,
            "reason": "completion_callback_failed",
            "errorType": type(exc).__name__,
        }


accounts = []
errors = []
seen_account_ids = set()
scan_started_at = time.time()
SCAN_CONFIG_ERROR = None
PC_SCAN_CONFIG = {}
# Keep a defined safe value when the PC config request itself fails.  The
# failure path must report the scan error and stop, rather than raising a
# secondary NameError while constructing SCAN_RESULT.
SCAN_ONLY = False
try:
    PC_SCAN_CONFIG = _load_pc_scan_config()
    GROUP_SEARCH_PREFIXES = tuple(PC_SCAN_CONFIG["searchPrefixes"])
    SCAN_ONLY = bool(PC_SCAN_CONFIG.get("scanOnly"))
    print(
        "GROUP_SCAN_CONFIG source={} prefixes={} scanOnly={}".format(
            PC_SCAN_CONFIG.get("source"),
            ",".join(GROUP_SEARCH_PREFIXES),
            SCAN_ONLY,
        )
    )
except Exception as exc:
    # If a configured PC is unreachable or returns invalid scope, do not fall
    # back to a different group set and risk silently scanning the wrong code.
    SCAN_CONFIG_ERROR = str(exc)
    errors.append({"stage": "scan_config", "error": SCAN_CONFIG_ERROR})
    print("GROUP_SCAN_CONFIG_FAILED error={}".format(SCAN_CONFIG_ERROR))

scan_slots = SCAN_SLOT_INDICES if not SCAN_CONFIG_ERROR else ()
for slot_index in scan_slots:
    slot_name = INSTANCE_SLOTS[slot_index]
    account_scan_started_at = time.time()
    wechat_context_seen = _wechat_context_present()
    cleanup_failed = False
    try:
        print("TARGET_SLOT_START slot={}".format(slot_name))
        home_point = _open_wechat(slot_index)
        wechat_context_seen = True
        print("TARGET_WECHAT_HOME_READY slot={}".format(slot_name))
        _tap(
            *home_point,
            expected="home",
            action_name="进入微信我页核验账号",
        )
        nickname = _wait_for(_read_nickname, timeout=10)
        wechat_id = _wait_for(_read_wechat_id, timeout=10)
        if not wechat_id:
            raise RuntimeError("微信“我”页未读到唯一微信号")
        account_id = _account_id(wechat_id)
        if account_id in seen_account_ids:
            raise RuntimeError("两个微信实例登录微信号相同，拒绝把群记录串到同一账号")
        seen_account_ids.add(account_id)
        nickname = nickname or ""
        _heartbeat(account_id, nickname, wechat_id)
        print(
            "ACCOUNT_IDENTITY slot={} accountId={} nickname={}".format(
                slot_name,
                account_id,
                nickname or "(未读到昵称，使用微信号身份)",
            )
        )
        print("TARGET_PROFILE_SETTLE seconds={}".format(HID_POST_ACTION_SETTLE_SECONDS))
        time.sleep(HID_POST_ACTION_SETTLE_SECONDS)
        if SCAN_MODE == "targeted":
            _open_wechat_chat_home()
            target_rows = []
            prefix_stop_reasons = []
            prefix_errors = []
            # Keep one outcome per configured query so a partial scan report
            # identifies the exact prefix that stopped, not just an aggregate.
            prefix_runs = []
            target_scrolls = 0
            target_rows_by_route = {}
            for prefix_index, prefix in enumerate(GROUP_SEARCH_PREFIXES):
                prefix_progress = {
                    "stage": "reset_to_home" if prefix_index else "start_prefix",
                    "scrollCount": 0,
                    "groupCount": 0,
                }
                print(
                    "TARGET_PREFIX_SCAN_START slot={} prefix={} index={}/{}".format(
                        slot_name,
                        prefix,
                        prefix_index + 1,
                        len(GROUP_SEARCH_PREFIXES),
                    )
                )
                try:
                    if prefix_index:
                        _reset_to_wechat_home(
                            "切换到第 {} 个群编号前缀扫描".format(prefix_index + 1)
                        )
                    prefix_rows, prefix_stop_reason, prefix_scrolls = (
                        _scan_targeted_group_rows(prefix, prefix_progress)
                    )
                except Exception as prefix_exc:
                    # A later prefix can fail after earlier prefixes already
                    # produced valid rows. Keep those rows for partial upsert,
                    # but stop UI navigation and block task creation for this
                    # run because the configured scan scope is incomplete.
                    prefix_error = {
                        "stage": "scan_prefix",
                        "prefix": prefix,
                        "error": str(prefix_exc),
                    }
                    prefix_errors.append(prefix_error)
                    prefix_runs.append(
                        {
                            "prefix": prefix,
                            "status": "failed",
                            "groupCount": 0,
                            "uniqueGroupCount": 0,
                            "scrollCount": prefix_progress.get("scrollCount", 0),
                            "stage": prefix_progress.get("stage", "unknown"),
                            "stopReason": "exception",
                            "groupCountBeforeFailure": prefix_progress.get("groupCount", 0),
                            "error": str(prefix_exc)[:180],
                        }
                    )
                    errors.append(
                        {
                            "slot": slot_name,
                            "stage": "scan_prefix",
                            "prefix": prefix,
                            "error": str(prefix_exc),
                            "scanDurationSeconds": round(
                                time.time() - account_scan_started_at, 3
                            ),
                        }
                    )
                    prefix_stop_reasons.append("{}:failed".format(prefix))
                    _capture_blocker_screenshot(
                        "scan_prefix_{}_{}".format(slot_name, prefix), prefix_exc
                    )
                    print(
                        "TARGET_PREFIX_SCAN_FAILED slot={} prefix={} error={} action=stop_remaining_preserve_collected_rows".format(
                            slot_name, prefix, str(prefix_exc)[:240]
                        )
                    )
                    break
                prefix_stop_reasons.append("{}:{}".format(prefix, prefix_stop_reason))
                target_scrolls += int(prefix_scrolls or 0)
                # Overlapping PC prefixes can return the same code/name route.
                # Merge snapshots by maximum observed multiplicity, not by
                # summing them, because the same WeChat rows may appear twice.
                unique_prefix_count = 0
                for row in prefix_rows:
                    key = (row["groupCode"], row["groupName"])
                    existing = target_rows_by_route.get(key)
                    row_count = int(row.get("occurrenceCount") or 1)
                    if existing is None:
                        target_rows_by_route[key] = dict(row)
                        unique_prefix_count += row_count
                    else:
                        previous_count = int(existing.get("occurrenceCount") or 1)
                        if row_count > previous_count:
                            unique_prefix_count += row_count - previous_count
                            existing["occurrenceCount"] = row_count
                target_rows = list(target_rows_by_route.values())
                prefix_runs.append(
                    {
                        "prefix": prefix,
                        "status": "success",
                        "groupCount": sum(
                            int(row.get("occurrenceCount") or 1)
                            for row in prefix_rows
                        ),
                        "uniqueGroupCount": unique_prefix_count,
                        "scrollCount": int(prefix_scrolls or 0),
                        "stage": prefix_progress.get("stage", "complete"),
                        "stopReason": prefix_stop_reason,
                    }
                )
            target_stop_reason = "targeted_prefixes:" + ";".join(prefix_stop_reasons)
            if prefix_errors:
                target_stop_reason += ";partial_prefix_failure"
            target_group_names = []
            target_group_mappings = []
            for row in target_rows:
                if row["groupName"] not in target_group_names:
                    target_group_names.append(row["groupName"])
                target_group_mappings.append(
                    {
                        "groupCode": row["groupCode"],
                        "groupName": row["groupName"],
                        "occurrenceCount": int(row.get("occurrenceCount") or 1),
                    }
                )
            reconcile = {}
            post_errors = list(prefix_errors)
            # Do not send an empty reconcile when the first prefix failed.
            # If earlier prefixes yielded rows, partial reconcile is safe:
            # _reconcile_account sets deleteMissing=False for targeted scans.
            if target_rows or not prefix_errors:
                try:
                    reconcile = _reconcile_account(
                        account_id,
                        nickname,
                        [],
                        "targeted_search",
                        target_group_names,
                        target_stop_reason,
                        SCAN_MODE,
                        target_group_mappings,
                    )
                except Exception as exc:
                    post_errors.append({"stage": "reconcile", "error": str(exc)})
                    _capture_blocker_screenshot("reconcile_{}".format(slot_name), exc)
            else:
                reconcile = {
                    "sent": False,
                    "reason": "prefix_scan_failed_before_any_rows",
                }
            reconcile_data = (
                reconcile.get("data")
                if isinstance(reconcile, dict) and isinstance(reconcile.get("data"), dict)
                else reconcile
            )
            reconcile_data = reconcile_data if isinstance(reconcile_data, dict) else {}
            # A configured URL/token or an empty response is not proof that PC
            # accepted this account's scan. The entry sender gate requires the
            # matching account and acknowledged scan id.
            reconcile_confirmed = (
                reconcile_data.get("wechatAccountId") == account_id
                and bool(reconcile_data.get("scanId"))
            )
            if not reconcile_confirmed and not post_errors:
                post_errors.append(
                    {
                        "stage": "reconcile_response",
                        "error": "PC 未返回匹配当前微信账号的群台账确认",
                    }
                )
            accounts.append(
                {
                    "slot": slot_name,
                    "scanMode": SCAN_MODE,
                    "searchPrefixes": list(GROUP_SEARCH_PREFIXES),
                    "nickname": nickname,
                    "wechatId": wechat_id,
                    "accountId": account_id,
                    "groupCount": sum(
                        int(row.get("occurrenceCount") or 1)
                        for row in target_rows
                    ),
                    "groupRows": target_rows,
                    "groupNames": target_group_names,
                    "contactsGroupCount": 0,
                    "contactsScanStopReason": "targeted_search_not_run",
                    "chatListGroupCount": len(target_rows),
                    "chatListScanStopReason": target_stop_reason,
                    "chatListScanScrolls": target_scrolls,
                    "prefixRuns": prefix_runs,
                    "memberCountChecks": [],
                    "memberCountCheckCount": 0,
                    "coverage": reconcile_data.get("coverage", "partial"),
                    "reconcile": reconcile,
                    "createdCount": reconcile_data.get("createdCount") if reconcile_confirmed else None,
                    "updatedCount": reconcile_data.get("updatedCount") if reconcile_confirmed else None,
                    "missingCount": reconcile_data.get("missingCount") if reconcile_confirmed else None,
                    "deletedCount": reconcile_data.get("deletedCount") if reconcile_confirmed else None,
                    "backendWriteConfirmed": reconcile_confirmed,
                    "postErrors": post_errors,
                    "status": "success" if reconcile_confirmed and not post_errors else "degraded",
                    "scanDurationSeconds": round(time.time() - account_scan_started_at, 3),
                }
            )
            print(
                "已完成定向群台账同步 slot={} accountId={} 群数={} created={} updated={} stopReason={}".format(
                    slot_name,
                    account_id,
                    len(target_group_names),
                    reconcile_data.get("createdCount", 0),
                    reconcile_data.get("updatedCount", 0),
                    target_stop_reason,
                )
            )
            continue
    except Exception as exc:
        _capture_blocker_screenshot("scan_{}".format(slot_name), exc)
        errors.append(
            {
                "slot": slot_name,
                "error": str(exc),
                "scanDurationSeconds": round(time.time() - account_scan_started_at, 3),
            }
        )
        print("扫描失败 slot={} error={}".format(slot_name, exc))
    finally:
        if wechat_context_seen:
            try:
                _reset_to_wechat_home("账号 {} 扫描结束".format(slot_name))
            except Exception as cleanup_exc:
                cleanup_failed = True
                _capture_blocker_screenshot("cleanup_{}".format(slot_name), cleanup_exc)
                errors.append(
                    {
                        "slot": slot_name,
                        "stage": "cleanup_home",
                        "error": str(cleanup_exc),
                        "scanDurationSeconds": round(time.time() - account_scan_started_at, 3),
                    }
                )
                print(
                    "TARGET_WECHAT_HOME_RESET_FAILED slot={} error={}".format(
                        slot_name, cleanup_exc
                    )
                )
        else:
            print("TARGET_WECHAT_HOME_RESET_SKIP slot={} reason=wechat_not_entered".format(slot_name))
    if cleanup_failed:
        print("TARGET_SCAN_STOP reason=wechat_home_reset_failed slot={}".format(slot_name))
        break

scan_summary = {
    "accountCount": len(accounts),
    "errorCount": len(errors),
    "groupCount": sum(int(account.get("groupCount") or 0) for account in accounts),
    "durationSeconds": round(time.time() - scan_started_at, 3),
    "mode": SCAN_MODE,
}
SCAN_RESULT = {
    "deviceId": DEVICE_ID,
    "functionId": "wechat.scan_native_groups",
    "source": "wechat_native",
    "accounts": accounts,
    "errors": errors,
    "scanSummary": scan_summary,
    "scanConfig": {
        "searchPrefixes": list(GROUP_SEARCH_PREFIXES),
        "scanOnly": SCAN_ONLY,
        "source": (PC_SCAN_CONFIG or {}).get("source", "unavailable"),
    },
    "status": "success" if accounts and not errors else "degraded" if accounts else "failed",
    "inputMode": INPUT_MODE,
}
_result = json.dumps(
    SCAN_RESULT,
    ensure_ascii=False,
)
if PREFLIGHT_ONLY:
    result = json.loads(_result)
    queue_summary = {}
    if SCAN_ONLY:
        queue_summary = {
            "runId": "wechat-scan-only:{}:{}".format(DEVICE_ID, int(time.time())),
            "batchNo": _preflight_batch_no(),
            "groupCodes": [],
            "createdCount": 0,
            "targetCount": 0,
            "skipped": "scan_only_configuration",
        }
        print("BATCH_RUN_NOT_QUEUED reason=scan_only_configuration")
    else:
        try:
            queue_summary = _queue_preflight_tasks(accounts, errors)
        except Exception as exc:
            queue_summary = {
                "runId": "wechat-preflight:{}:{}".format(DEVICE_ID, int(time.time())),
                "batchNo": _preflight_batch_no(),
                "groupCodes": _preflight_group_codes(),
                "createdCount": 0,
                "targetCount": 0,
                "error": str(exc),
            }
            print("BATCH_RUN_QUEUE_FAILED error={}".format(exc))
    result["preflightOnly"] = True
    result["queue"] = queue_summary
    result["status"] = (
        "success"
        if result.get("status") == "success" and not queue_summary.get("error")
        else "degraded"
        if result.get("accounts")
        else "failed"
    )
    notification = _notify_preflight_completion(
        {
            "deviceId": DEVICE_ID,
            "runId": queue_summary.get("runId", "wechat-preflight"),
            "status": result["status"],
            "batchNo": queue_summary.get("batchNo"),
            "groupCodes": queue_summary.get("groupCodes", []),
            "accounts": result.get("accounts", []),
            "scanSummary": result.get("scanSummary", {}),
            "scanConfig": result.get("scanConfig", {}),
            "queueSummary": queue_summary,
        }
    )
    result["completionNotification"] = notification
    _result = json.dumps(result, ensure_ascii=False)
    print(
        "PREFLIGHT_ONLY_DONE status={} accounts={} tasks={} targets={} emailSent={}".format(
            result["status"],
            len(result.get("accounts", [])),
            queue_summary.get("createdCount", 0),
            queue_summary.get("targetCount", 0),
            bool((notification.get("email") or {}).get("sent")),
        )
    )
print(_result)
