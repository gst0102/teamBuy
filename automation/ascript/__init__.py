# -*- coding: utf-8 -*-
"""资料整理助手：AScript 统一九宫格入口。

AScript 设备端只启动这个入口工程。原有功能目录保留为内部模块，避免
用户从本地小程序列表里逐个启动探针工程。所有涉及微信发送的动作仍由
各模块自己的安全门禁控制，入口不会自动发送消息。

Android AScript runtime is Python 3.8. Keep this file compatible with 3.8.
"""

from __future__ import print_function

import json
import importlib.util
import os
import queue
import sys
import threading
import time

from ascript.android.ui import Dialog, WebWindow
from ascript.android.system import Device, R


FEATURES = {
    "xhs_find_group": {
        "title": "小红书找群",
        "subtitle": "搜索群信息并回传 PC",
        "module": "xhs_find_group",
    },
    "join_wechat_group": {
        "title": "加微信群",
        "subtitle": "读取待加入任务并执行",
        "module": None,
    },
    "wechat_group_inventory": {
        "title": "扫描微信群",
        "subtitle": "扫描原生群聊并入库",
        "module": "wechat_group_inventory",
    },
    "wechat_group_library": {
        "title": "微信群库",
        "subtitle": "查看 PC 端群库状态",
        "module": None,
    },
    "wechat_marketing": {
        "title": "群营销",
        "subtitle": "执行已审核的单群任务",
        "module": "wechat_marketing_sender",
    },
    "wechat_accounts": {
        "title": "微信账号",
        "subtitle": "识别两个微信昵称",
        "module": "wechat_account_identity",
    },
    "device_status": {
        "title": "设备状态",
        "subtitle": "检查当前输入通道",
        "module": None,
    },
    "task_logs": {
        "title": "任务日志",
        "subtitle": "查看最近执行结果",
        "module": None,
    },
    "settings": {
        "title": "设置",
        "subtitle": "设备和接口配置",
        "module": None,
    },
}


def _keep_screen_awake():
    try:
        Device.wake_up()
        Device.keep_screen_on()
    except Exception as exc:
        print("开启屏幕常亮失败:", exc)


def _status_message(feature):
    if feature["module"]:
        return "正在启动：{}".format(feature["title"])
    if feature["title"] == "微信群库":
        return "微信群库在 PC 运营后台查看；手机端负责扫描和回传。"
    if feature["title"] == "设备状态":
        return "当前使用 AScript 原生输入，ESP32 暂停使用。"
    if feature["title"] == "任务日志":
        return "执行结果会由模块回传 PC，日志页面下一步接入。"
    if feature["title"] == "设置":
        return "设备配置页面下一步接入。"
    return "该功能页面下一步接入。"


def _device_status():
    result = {
        "inputMode": "ascript_native",
        "message": "当前开发模式使用 AScript 原生控件、OCR 和 action 输入；ESP32 暂停使用。",
        "optionalEsp32": "not_loaded",
    }
    Dialog.alert(
        json.dumps(result, ensure_ascii=False, indent=2),
        submit="返回九宫格",
    )


def _run_module(feature):
    module_name = feature.get("module")
    if not module_name:
        Dialog.alert(_status_message(feature), submit="返回九宫格")
        return

    # AScript runs this file as the project entry, but the feature folders are
    # not top-level import paths. Load each feature as a synthetic package so
    # its local relative imports (for example .local_config) still work.
    project_root = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(project_root, module_name)
    module_file = os.path.join(module_dir, "__init__.py")
    if not os.path.isfile(module_file):
        raise ImportError("找不到功能模块文件: {}".format(module_file))
    package_name = "_team_buy_ascript_{}".format(module_name)
    spec = importlib.util.spec_from_file_location(
        package_name,
        module_file,
        submodule_search_locations=[module_dir],
    )
    if spec is None or spec.loader is None:
        raise ImportError("无法加载功能模块: {}".format(module_name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)


HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; background: #080d1d; color: #f4f7ff; font-family: sans-serif; }
  body { padding: 28px 20px 24px; }
  .eyebrow { color: #69d7a1; font-size: 13px; letter-spacing: 2px; }
  h1 { margin: 8px 0 6px; font-size: 30px; }
  .intro { margin: 0 0 22px; color: #aab6d2; font-size: 15px; line-height: 1.5; }
  .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  button { min-height: 142px; padding: 16px 10px; border: 1px solid #283657; border-radius: 18px; background: #121b32; color: #f4f7ff; text-align: left; }
  button:active { background: #1d2b4b; border-color: #69d7a1; }
  .num { display: inline-flex; width: 28px; height: 28px; align-items: center; justify-content: center; border-radius: 9px; background: #253557; color: #9fe8c3; font-size: 13px; }
  .title { display: block; margin-top: 18px; font-size: 17px; font-weight: 700; }
  .sub { display: block; margin-top: 7px; color: #96a4c3; font-size: 11px; line-height: 1.35; }
  .exit { display: flex; width: 100%; min-height: 44px; margin-top: 16px; padding: 10px 14px; align-items: center; justify-content: center; border: 1px solid #3a496b; border-radius: 12px; background: #0d1428; color: #aab6d2; font-size: 14px; }
  .footer { margin-top: 22px; padding-top: 14px; border-top: 1px solid #1f2a45; color: #71809f; font-size: 12px; }
</style>
</head>
<body>
  <div class="eyebrow">ASCRIPT TOOLBOX</div>
  <h1>资料整理助手</h1>
  <p class="intro">一个入口，九个功能。手机负责执行，PC 负责审核和查看记录。</p>
  <div class="grid">
    <button onclick="pick('xhs_find_group')"><span class="num">1</span><span class="title">小红书找群</span><span class="sub">搜索群信息并回传 PC</span></button>
    <button onclick="pick('join_wechat_group')"><span class="num">2</span><span class="title">加微信群</span><span class="sub">读取待加入任务</span></button>
    <button onclick="pick('wechat_group_inventory')"><span class="num">3</span><span class="title">扫描微信群</span><span class="sub">原生群聊入库</span></button>
    <button onclick="pick('wechat_group_library')"><span class="num">4</span><span class="title">微信群库</span><span class="sub">查看 PC 群库状态</span></button>
    <button onclick="pick('wechat_marketing')"><span class="num">5</span><span class="title">群营销</span><span class="sub">执行已审核任务</span></button>
    <button onclick="pick('wechat_accounts')"><span class="num">6</span><span class="title">微信账号</span><span class="sub">识别两个微信昵称</span></button>
  <button onclick="pick('device_status')"><span class="num">7</span><span class="title">设备状态</span><span class="sub">检查当前输入通道</span></button>
    <button onclick="pick('task_logs')"><span class="num">8</span><span class="title">任务日志</span><span class="sub">查看执行结果</span></button>
    <button onclick="pick('settings')"><span class="num">9</span><span class="title">设置</span><span class="sub">设备和接口配置</span></button>
  </div>
  <button class="exit" onclick="exitLauncher()">退出九宫格</button>
  <div class="footer">当前版本：统一入口第一版 · 旧探针不再作为操作入口</div>
<script>
  function pick(id) { window.airscript.call('feature', id); }
  function exitLauncher() { window.airscript.call('window_closed', 'user_exit'); }
  window.addEventListener('pagehide', function() {
    window.airscript.call('window_closed', '1');
  });
</script>
</body>
</html>
"""


def main():
    _keep_screen_awake()
    state = {"window": None, "closing_for_feature": False}
    events = queue.Queue()

    def tunnel(key, value):
        if key == "window_closed":
            if state["closing_for_feature"]:
                state["closing_for_feature"] = False
                return
            events.put(("closed", None))
            return
        if key != "feature":
            return
        feature = FEATURES.get(str(value))
        if not feature:
            return
        window = state.get("window")
        if window is not None:
            state["closing_for_feature"] = True
            window.close()
        events.put(("feature", feature))

    # Prefer the portable packaged-resource path.  The local AScript 4.0.03
    # runner may lose the resource-root context for a Chinese-named project,
    # so keep the confirmed device path only as a local-runner fallback.
    device_launcher_path = "/storage/emulated/0/airscript/model/资料整理助手/res/ui/launcher.html"
    if os.path.exists(device_launcher_path):
        launcher_path = device_launcher_path
    else:
        launcher_path = (
            R.ui("launcher.html")
            or R.res("ui", "launcher.html")
            or R.root("res", "ui", "launcher.html")
        )
    # A fixed WebWindow id can be reused by AScript 4.0.03 after a previous
    # run and leave the new script behind the host Activity.  Use a short-lived
    # id per launch so every run gets a fresh foreground window.
    def show_launcher():
        # A fixed WebWindow id can be reused by AScript 4.0.03 after a
        # previous run and leave the new script behind the host Activity.
        window_id = 10000 + (int(time.time()) % 90000)
        window = WebWindow(launcher_path, tunnel=tunnel, id=window_id)
        state["window"] = window
        # The launcher is the product UI, not a passive overlay. On Android 15
        # / AScript 4.0.03, mode(0) is the supported foreground path.
        window.mode(0)
        window.background("#080d1d")
        window.dim_amount(0)
        window.size("100vw", "100vh")
        window.show(wait=False)

    while True:
        show_launcher()
        event_type, payload = events.get()
        window = state.get("window")
        state["window"] = None
        if event_type == "closed":
            if window is not None:
                try:
                    window.close()
                except Exception:
                    pass
            return
        if event_type != "feature":
            continue
        try:
            if payload.get("title") == "设备状态":
                _device_status()
            else:
                _run_module(payload)
        except Exception as exc:
            Dialog.alert(
                "{} 执行失败：\n{}".format(payload["title"], exc),
                submit="返回九宫格",
            )


if __name__ == "__main__":
    main()
