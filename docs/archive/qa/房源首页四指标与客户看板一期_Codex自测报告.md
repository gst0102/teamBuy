# 房源首页四指标与客户看板一期_Codex自测报告

更新时间：2026-06-23

## 1. 自测结论

代码侧通过，真机侧需要人工确认。

本轮已按 `docs/stage2-docs/18-property-home-customer-dashboard-v1.md` 和 `docs/qa/房源首页四指标与客户看板一期_测试清单与验收标准.md` 完成一期实现。

## 2. 已实现内容

### 首页四指标

- 房源工作台首页四指标改为：`房源 / 打开 / 访客 / 待跟进`。
- 房源模式下标题改为 `今日概览`，副标题为 `房源、浏览和客户反馈一眼看清`。
- 房源指标按房源资料聚合，不再直接使用全量资料总数。
- 待跟进优先使用客户摘要里的 `pending`，否则兼容客户活动数。

### 首页点击映射

- `房源`：进入资料页，并自动只看房源资料。
- `打开`：进入 `pages/business-dashboard/index?mode=property&tab=propertyEffect`。
- `访客`：进入 `pages/business-dashboard/index?mode=property&tab=visitors`。
- `待跟进`：进入 `pages/business-dashboard/index?mode=property&tab=followup`。

### 客户看板

- 房源模式下客户看板标题为 `房源客户看板`。
- 房源模式默认 Tab 为 `待跟进`。
- Tab 顺序为：`待跟进 / 最近访客 / 房源效果 / 推荐包效果`。
- `待跟进` 首屏展示可处理客户动作，并提供外呼、复制微信、备注、已联系等入口。
- `推荐包效果` 保留原展示页能力，并用“多套房源一起发给客户”的文案解释。
- 匿名访客以匿名方式展示，不伪造成实名客户。

### 资料页

- 支持从房源首页进入资料页后自动应用房源筛选。
- 增加入口筛选提示，可一键切回全部。
- 增加列表 / 双列切换，默认从房源入口进入时使用列表，避免大屏只显示半张卡。
- 资料卡直接展示打开、访客、客户动态。

### 模式边界补充

- 已补充工作台页进入客户看板时携带当前 `workspaceMode`。
- 房源进入房源客户看板；普通资料、团购、服务进入对应非房源模式，避免默认被房源文案污染。

## 3. 已验证命令

```text
node --check miniprogram/pages/home/index.js
node --check miniprogram/pages/business-dashboard/index.js
node --check miniprogram/pages/library/index.js
node --check miniprogram/pages/visits/index.js
node --check miniprogram/utils/workspace-mode.js
node --check miniprogram/services/api.js
python3 递归解析 miniprogram/*.json
git diff --check
```

结果：

```text
全部通过
```

## 4. 仍需真机确认

- 房源首页四个指标在手机和 iPad 上是否居中、不卡字。
- 点击 `房源 / 打开 / 访客 / 待跟进` 是否进入正确页面。
- 客户看板首屏是否默认显示 `待跟进`，不是推荐包效果。
- 空态文案是否能让中介理解下一步。
- 推荐包效果是否能继续找到原展示页数据。
- 资料页房源筛选和列表 / 双列切换在 iPad 上是否完整可读。

## 5. 未做事项

- 未部署生产后端。
- 未上传小程序体验版。
- 未新增复杂 CRM、客户画像、企业微信主动推送或 BI 漏斗。

## 6. 2026-06-23 追加收口

- 后端 `GET /api/dashboard/business` 已增加 `mode=property` 专属房源客户看板口径。
- 房源模式只统计房源资料、房源推荐包、房源客户动作和房源待跟进线索。
- 推荐包内如果混入服务/普通资料，非房源 `note_click` 不会进入房源看板的资料排行、推荐包拆解和访客画像。
- 首页房源四指标优先使用后端房源看板汇总。
- 资料卡有 note 级客户动作时，客户入口优先进入 `pages/note-actions`，避免旧访问详情看不到待跟进。
- 本地后端测试环境统一为 `.venv312`，Python `3.12.13`。

追加验证：

```text
.venv312/bin/python -m pytest backend/tests/test_app.py -q
.venv312/bin/python -m compileall backend/app
node --check miniprogram/pages/home/index.js
node --check miniprogram/services/api.js
node --check miniprogram/pages/business-dashboard/index.js
node --check miniprogram/pages/library/index.js
git diff --check -- backend/tests/test_app.py backend/app/api/routes_dashboard.py backend/app/services/app_service.py miniprogram/pages/home/index.js miniprogram/services/api.js miniprogram/pages/business-dashboard/index.js miniprogram/pages/library/index.js .gitignore
```

结果：

```text
98 passed
其余检查全部通过
```

## 7. 2026-06-23 今日/累计追加自测

- 首页房源概览新增“今日 / 累计”切换。
- 后端房源看板返回 `todaySummary`，不再把累计数据冒充今日。
- 点击今日 `打开 / 访客 / 待跟进` 会带 `range=today` 进入客户看板。
- 客户看板按 `isToday` 过滤今日访客和今日客户动作。
- 单条房源直接打开也会进入访客画像，用于展示“他看了哪套房源”。

追加验证：

```text
.venv312/bin/python -m pytest backend/tests/test_app.py -q
node --check miniprogram/pages/home/index.js
node --check miniprogram/pages/business-dashboard/index.js
git diff --check -- backend/app/services/app_service.py backend/tests/test_app.py miniprogram/pages/home/index.js miniprogram/pages/home/index.wxml miniprogram/pages/home/index.wxss miniprogram/pages/business-dashboard/index.js miniprogram/pages/business-dashboard/index.wxml
```

结果：

```text
98 passed
其余检查全部通过
```

## 8. 2026-06-23 待跟进列表一致性追加自测

- 修复首页 `待跟进` 有数字但客户看板列表为空的问题。
- 待跟进列表现在同时包含：
  - note 级客户动作投影出的线索；
  - 旧访问详情/旧卡片投影出的 pending `LeadReminder`。
- 对无客户动作的线索生成 `lead-followup` 行，可进入线索详情。

验证：

```text
.venv312/bin/python -m pytest backend/tests/test_app.py -q
98 passed
```
