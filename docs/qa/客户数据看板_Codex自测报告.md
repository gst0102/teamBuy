# 客户数据看板 Codex 自测报告

更新时间：2026-06-21

## 1. 开发范围

本轮按照客户数据关系与组件化方案完成：

- 新增后端聚合接口：`GET /api/dashboard/business?ownerUserId=xxx`。
- 新增小程序组件：`miniprogram/components/business-dashboard/`，作为后续嵌入式看板备用。
- “我的”页只保留经营看板小入口，不展示整块经营看板。
- “访客线索”页新增经营看板入口。
- 新增小程序页面：`miniprogram/pages/business-dashboard/index`。
- 保持线索、订单/接龙、客户库、展示页效果为独立处理入口。
- 新增后端测试用例覆盖经营看板聚合口径。
- 本轮继续补齐经营看板可点击处理、商品/团购订单分组和商品名单状态处理。
- 已增强服务器演示数据接口：`POST /api/notes/demo-data?ownerUserId=xxx` 会写入真实后端数据，包括笔记、展示页、展示页访问事件、留资/预约和商品接龙，不是前端 mock。

## 2. 已实现能力

### 2.1 后端经营看板接口

接口返回：

- `summary`：打开、访客、看资料、咨询、待联系、客户资料、订单/接龙、今日动作等统计。
- `entries`：展示页效果、客户线索、订单/接龙、客户资料四个入口。
- `recentVisitors`：最近展示页访客，匿名只显示“匿名客户”。
- `topNotes`：资料点击排行。
- `latestActions`：最近客户动作，包括留资、预约、下单、接龙。

### 2.2 小程序经营看板组件

组件特点：

- 只展示事实数据，不展示“行为强度分层”等内部概念。
- 不展示服务客户数、成交案例、好评率等无法证明的假指标。
- 入口点击统一抛出事件，由页面决定跳转。
- 当前用于“我的”页，后续可复用到首页、展示页管理、电子名片管理等场景。

### 2.3 访客线索入口与详情页

“我的”页保留账号、资源和常用工具，不再展示大面积经营看板。

“访客线索”页新增：

- 经营看板入口。
- 点击后进入独立经营看板详情页。
- 经营看板资料点击排行可进入笔记客户动作页。
- 经营看板最近客户动作可进入线索详情、订单详情或笔记客户动作页。

经营看板详情页新增 4 个 Tab：

- 展示页效果。
- 访客详情。
- 笔记数据。
- 客户资料。

线索、订单/接龙、客户库、展示页管理作为详情页内“去处理”按钮，不再由我的页看板入口直接跳转。

### 2.4 商品/团购轻订单

- 订单列表新增汇总：全部、待处理、已联系、已完成、已取消、接龙、下单。
- 商家订单页新增状态筛选：全部、待处理、已联系、已完成、已取消。
- 商品接龙/下单名单页可直接把单条记录标记为已联系、已完成或取消。
- 商品下单/接龙继续复用 `CustomerAction(order-intent/relay-intent)`，不默认进入 `LeadReminder`。

## 3. 自动化与静态验证

| 验证项 | 结果 |
| --- | --- |
| `python3 -m compileall backend/app backend/tests` | 通过 |
| 小程序全量 JS `node --check` | 通过 |
| 小程序全量 JSON 解析 | 通过 |
| `git diff --check` | 通过 |
| `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q` | 76 passed |
| `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q` | 113 passed |
| 生产 `/health` | 通过，返回 200 |
| 生产 `/api/dashboard/business?ownerUserId=user_test` | 通过，返回业务级“用户不存在”，不再是路由级 404 |
| 生产演示用户经营看板 | 通过，`user_836a4a8986` 汇总打开 2、访客 2、看资料 1、咨询 2、订单 1 |
| 生产演示用户展示页列表 | 通过，返回 1 个已发布展示页和 5 条真实行为事件 |
| 生产演示用户订单列表 | 通过，返回 1 条待处理接龙 |
| `python3 -m pytest backend/tests/test_app.py -q` | 未通过执行，系统 Python 缺少 pytest |
| `./.venv/bin/python -m pytest backend/tests/test_app.py -q` | 环境阻塞：Python 3.9 不支持 `dataclass(slots=True)` |
| Codex Python 3.12 执行 pytest | 环境阻塞：Codex Python 3.12 缺少 pytest |
| Codex Python 3.12 + `.venv` site-packages | 环境阻塞：`.venv` 的 `pydantic_core` 二进制与 Python 3.12 不兼容 |

## 4. 新增测试覆盖

新增 `test_business_dashboard_aggregates_real_customer_data`，覆盖：

- owner 展示页事件进入经营看板。
- 其他 owner 展示页事件不会混入当前 owner。
- 登录访客和匿名访客分别计数。
- 匿名访客显示为匿名，不进入实名客户资料。
- 展示页点击进入资料排行。
- 商品接龙进入订单/接龙待处理。
- demo 商品接龙不进入待联系线索。

该测试已通过临时 Python 3.12 测试环境执行。商品/团购轻订单测试也已补充订单汇总、状态文案和商家状态更新断言。

## 5. 未覆盖与需要人工确认

- 小程序真机“访客线索”页经营看板入口视觉是否符合预期。
- 经营看板详情页四个 Tab 在体验版中是否可正常切换。
- 详情页“去处理”按钮是否进入展示页、待联系、商家订单和客户库。
- 小程序体验版仍需用户在微信开发者工具手动上传后，才能用真机确认最新“访客线索 -> 经营看板”页面。

## 6. 自测结论

代码静态验证、后端全量测试和生产后端接口部署验证均已通过。当前仍保留“需要人工确认”，原因是小程序体验版视觉、四个 Tab 切换和跳转需要用户真机确认。
