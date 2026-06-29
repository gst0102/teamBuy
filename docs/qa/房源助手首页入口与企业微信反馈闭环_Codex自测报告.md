# 房源助手首页入口与企业微信反馈闭环 Codex 自测报告

日期：2026-06-26

## 本轮改动

- 首页保留原房源工作台结构，只在 banner 和常用入口中增强房源助手入口。
- 常用入口标题从“租房中介常用入口”改为“常用入口”。
- 常用入口第一项改为“添加房源助手”，使用 `miniprogram/static/icons/wechat.svg`。
- 首页新增 `openPropertyAssistant`：
  - 优先读取 `/api/wecom/customer-service-config`。
  - 配置完整时调用 `wx.openCustomerServiceChat`。
  - 失败时复制给房源助手的提示文案。
- 后端 `ImportNotification` 增加结果路径、动作、发送状态字段。
- 企业微信真实 `sync_msg` 导入完成后尝试通过微信客服发送文本完成反馈。
- 发送失败只记录状态，不阻断资料生成。

## 已验证

- `node --check miniprogram/pages/home/index.js`
- `node --check miniprogram/utils/workspace-mode.js`
- `node --check miniprogram/services/api.js`
- `.venv312/bin/python -m py_compile backend/app/services/wecom_client.py backend/app/services/import_notification_service.py backend/app/services/app_service.py backend/app/api/routes_wecom.py backend/app/models/domain.py`
- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "mock_import_creates_claimable_batch or real_sync_sends_wecom_completion_feedback or real_sync_paginates_and_persists_cursor"`

## 自动化结果

- 3 个后端相关测试通过。
- 小程序关键 JS 静态检查通过。
- 后端关键 Python 文件编译通过。

## 未覆盖

- 尚未真机确认首页微信 SVG 图标在小程序中渲染效果。
- 尚未真机确认 `wx.openCustomerServiceChat` 能在当前体验版中正常打开企业微信客服。
- 文本反馈已经本地测试，真实企业微信发送仍需生产环境触发一次真实消息验证。
