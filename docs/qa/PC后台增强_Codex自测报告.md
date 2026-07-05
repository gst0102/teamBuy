# PC 后台增强 Codex 自测报告

日期：2026-07-01

## 范围

- 商机线索运营看板。
- 商机线索快捷下架。
- 积分账本用户列表和人工调整。
- 回应包记录列表。

## 已覆盖

- 新增运营接口均要求 `X-Admin-Token`。
- 后台下架线索后，公开商机详情接口返回 404。
- 积分调整写入统一积分流水。
- 回应包记录展示关联用户、商机、资料数、消耗和最近打开时间。
- PC 后台页面脚本语法检查。

## 验证命令

```bash
DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-ops-pc.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "ops_opportunity_dashboard or response_package or opportunity_lead or resource_wallet"
DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-ops-pc.json .venv312/bin/python -m compileall -q backend/app
node - <<'NODE'
const fs = require('fs');
const html = fs.readFileSync('backend/app/static/ops-admin/index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n');
new Function(scripts);
console.log('ops admin script ok');
NODE
```

结果：通过。

## 未覆盖

- 尚未部署测试后端后用浏览器打开 `/ops` 做真实点击验收。
- 供给卡审核未纳入本轮实现，等待供需广场模型稳定后再补。
