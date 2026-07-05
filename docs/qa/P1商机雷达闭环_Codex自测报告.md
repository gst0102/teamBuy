# P1 商机雷达闭环 Codex 自测报告

时间：2026-07-01 22:16

## 2026-07-02 真机反馈修复复测

新增覆盖：

- 我的雷达保存失败提示与登录态校验。
- 发布供需类型胶囊样式修复。
- 发布供需关联资料从资料库/合集选择，不再手填 ID。
- 供需广场城市、行业、需求类型支持自定义输入。

执行命令：

```bash
node --check miniprogram/pages/supply-demand-publish/index.js
node --check miniprogram/pages/opportunity-market/index.js
node --check miniprogram/pages/opportunity-radar/index.js
node --check miniprogram/services/api.js
```

结果：通过。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-bugfix-radar-supply.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q
```

结果：1 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-bugfix-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"
```

结果：13 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-bugfix-compile.json .venv312/bin/python -m compileall -q backend/app
git diff --check
```

结果：通过。

## 范围

本轮覆盖 P1 1-5：

- 订阅雷达真实保存
- 联系方式解锁
- 回应包雷达反馈页
- 我的发布 / 发布供给
- 供给审核后台

## 自测结论

通过本地自测。后端闭环、前端语法、小程序 JSON 和空白检查均通过。

本轮未部署生产，也未上传小程序。

## 已执行验证

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-test2.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q
```

结果：1 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"
```

结果：13 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-compile.json .venv312/bin/python -m compileall -q backend/app
```

结果：通过。

```bash
node --check miniprogram/services/api.js
node --check miniprogram/pages/opportunity-subscription/index.js
node --check miniprogram/pages/opportunity-detail/index.js
node --check miniprogram/pages/opportunity-radar/index.js
node --check miniprogram/pages/opportunity-market/index.js
node --check miniprogram/pages/response-package/index.js
node --check miniprogram/pages/response-package-radar/index.js
node --check miniprogram/pages/supply-demand-publish/index.js
node --check miniprogram/pages/supply-demand-my/index.js
```

结果：通过。

```bash
python3 -m json.tool miniprogram/app.json
python3 -m json.tool miniprogram/pages/response-package-radar/index.json
python3 -m json.tool miniprogram/pages/supply-demand-publish/index.json
python3 -m json.tool miniprogram/pages/supply-demand-my/index.json
```

结果：通过。

```bash
git diff --check
```

结果：通过。

## 补充完整回归

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-full-test.json .venv312/bin/python -m pytest backend/tests/test_app.py -q
```

结果：162 passed，1 failed。

失败用例：`test_health_reports_database_configuration`。

原因：本地隔离测试显式使用 `DATABASE_BACKEND=json`，该用例断言 `/health` 返回的数据库后端必须是 `postgres`。本轮 P1 相关业务用例和完整业务回归均已通过，失败不属于商机雷达业务逻辑。

## 仍需人工确认

- 小程序真机 UI 是否符合用户对胶囊按钮、底部按钮宽度和供需广场入口的预期。
- PC 后台供给审核在真实管理员 token 下的页面操作体验。
- 是否将本轮 P1 代码部署到测试环境或生产环境。

## 后续建议

- P2 再做资料选择器、付费/保证金、供需合作申请和主动推送。
- 进入部署前先确认小程序当前环境配置，避免测试环境和生产环境混用。

## 2026-07-01 P1 体验补强复测

新增覆盖：

- 已保存跟进台：状态筛选、提醒时间保存、回应包状态筛选、最近跟进返回。
- 订阅匹配结果：按订阅条件和筛选参数生成“今日推荐机会”。
- 回应包可选资料：预览和生成都使用 `selectedAssetIds`。
- 供需广场筛选：城市、行业、需求/供给方向、联系方式状态接真实接口参数。

执行命令：

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-test.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q
```

结果：1 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"
```

结果：13 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-compile.json .venv312/bin/python -m compileall -q backend/app
```

结果：通过。

## 2026-07-01 供需详情、合作申请、站内主动推荐复测

新增覆盖：

- 供需卡详情接口和小程序详情页。
- 供需卡合作申请、收到的申请列表、申请通过/拒绝。
- 我的发布页申请管理。
- 站内主动推荐摘要生成、列表、标记已读。

执行命令：

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-test.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q
```

结果：1 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"
```

结果：13 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-compile.json .venv312/bin/python -m compileall -q backend/app
```

结果：通过。

```bash
node --check miniprogram/services/api.js
node --check miniprogram/pages/supply-demand-detail/index.js
node --check miniprogram/pages/supply-demand-my/index.js
node --check miniprogram/pages/opportunity-radar/index.js
node --check miniprogram/pages/opportunity-market/index.js
git diff --check
```

结果：通过。

说明：主动推送当前验证的是站内摘要，不包含微信/企微外发。

## 2026-07-01 P1 尾巴复测

新增覆盖：

- 我的发布编辑回填：owner 可读取自己的草稿并更新原供需卡。
- 我申请的合作列表：申请人视角接口已覆盖，小程序已展示列表。
- 后台触发站内推荐摘要：PC 后台按钮调用 ops 接口批量生成摘要。

执行命令：

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-test3.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q
```

结果：1 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-regression2.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"
```

结果：13 passed。

```bash
PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-compile.json .venv312/bin/python -m compileall -q backend/app
```

结果：通过。

```bash
node --check miniprogram/services/api.js
node --check miniprogram/pages/supply-demand-publish/index.js
node --check miniprogram/pages/supply-demand-my/index.js
node --check miniprogram/pages/supply-demand-detail/index.js
node --check miniprogram/pages/opportunity-radar/index.js
git diff --check
```

结果：通过。

```bash
node --check miniprogram/services/api.js
node --check miniprogram/pages/opportunity-saved/index.js
node --check miniprogram/pages/response-package/index.js
node --check miniprogram/pages/opportunity-market/index.js
node --check miniprogram/pages/opportunity-radar/index.js
git diff --check
```

结果：通过。
