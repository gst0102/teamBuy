# 商机线索接口与回应包 P0 Codex 自测报告

日期：2026-07-01

## 范围

- 小程序商机页接真实接口，接口失败或无数据时使用 mock 兜底。
- 新增回应包页面，支持预览、生成、复制回应内容。
- 后端新增回应包 P0 接口、数据模型、积分/免费额度消耗和事件记录。

## 已覆盖

- 商机列表、详情、保存列表读取接口。
- 回应包预览不扣积分。
- 回应包正式生成使用免费额度。
- 同一用户同一商机重复生成不重复扣积分。
- 他人不能通过 ownerUserId 查看别人的回应包。
- 回应包 view 事件会更新 lastViewedAt。
- 小程序商机相关 JS 语法检查。
- 小程序页面 JSON 格式检查。

## 验证命令

```bash
node --check miniprogram/services/api.js
node --check miniprogram/pages/opportunity-radar/index.js
node --check miniprogram/pages/opportunity-detail/index.js
node --check miniprogram/pages/opportunity-market/index.js
node --check miniprogram/pages/opportunity-saved/index.js
node --check miniprogram/pages/opportunity-subscription/index.js
node --check miniprogram/pages/response-package/index.js
python3 -m json.tool miniprogram/app.json >/dev/null
python3 -m json.tool miniprogram/pages/response-package/index.json >/dev/null
DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-response-package.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "response_package or opportunity_lead or resource_wallet"
DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-response-package.json .venv312/bin/python -m compileall -q backend/app
git diff --check
```

结果：上述命令通过。

## 全量测试说明

使用本地 JSON 测试库跑全量后端测试：

- 198 passed
- 1 failed

失败项：`test_health_reports_database_configuration` 固定断言数据库 backend 为 `postgres`。本次为避开本机 Postgres 密码问题使用了 `DATABASE_BACKEND=json`，因此该失败不指向本轮商机/回应包改动。

## 未覆盖

- 尚未在微信开发者工具真机验收回应包页面视觉效果。
- 尚未部署测试后端，因此小程序真实接口需要部署后再做联调。
- 订阅雷达保存、主动推送、支付、保证金、自动联系均未纳入 P0。
