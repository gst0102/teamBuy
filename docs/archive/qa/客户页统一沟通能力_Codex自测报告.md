# 客户页统一沟通能力 Codex 自测报告

## 结论

代码实现完成，静态检查和针对性后端回归通过；尚未完成微信开发者工具真机验收，也未部署本轮后端改动。

## 本轮实现

- 新增共享小程序组件 `miniprogram/components/customer-communication/`，统一提供两列沟通入口和底部主 CTA。
- `note-preview` 的名片、服务、文章、图文、图片、文字、房源和商品分支统一复用该组件。
- 名片支持电话、微信、邮箱、留言、留下需求和分享；历史名片即使旧配置关闭 `collectLeads`，公开客户页仍展示名片的留资入口。
- 合集页复用同一视觉组件，提供电话、微信和分享；留言/留需求继续落到具体资料详情页，避免将线索错误归到整合集合或第一张资料。
- 名片编辑保存和后端名片默认配置改为开启 `collectLeads`。

## 已执行检查

- `node --check`：共享组件、资料详情页、合集页、名片编辑页，通过。
- 小程序 JSON 解析：共享组件、资料详情页、合集页，通过。
- `python -m compileall`：`backend/app/services/app_service.py`，通过。
- 目标页面结构断言：旧名片动作栏、资料详情页重复沟通 markup 已清除；统一组件引用完整，通过。
- `PYTHONPATH=backend .venv312/bin/python -m pytest backend/tests/test_app.py -q -k 'business_card or customer_action'`：5 passed，177 deselected。
- `git diff --check`：通过。

## 尚未覆盖

- 微信开发者工具编译、真实匿名访客/非发布者身份点击电话、微信、留言、留需求、分享。
- 合集级别的留言/留需求持久化接口；当前设计要求用户打开具体资料后提交，以保留线索归属。
- 本轮后端改动尚未部署生产；小程序改动也尚未上传体验版。

## 用户验收顺序

1. 部署后端后，用微信开发者工具打开 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram`，清缓存并重新编译上传体验版。
2. 用非发布者身份打开名片，确认沟通区为两列，点击“留言咨询/留下需求”能复用现有表单和消息链路。
3. 打开合集，确认底部出现统一“方便沟通”区；电话和微信动作能正常触发，点击具体资料后再测试留言和留需求。
