# 首页与Tabbar工作台模式一期_Bug修复报告

更新时间：2026-06-23

## 1. 修复结论

本轮优先闭环两个 P0：

- BUG-01：已修复。业务资料识别提示卡新增“继续当前工作台 / 切换到对应工作台”专门双选。
- BUG-02：已修复并补充自动化证据。工作台总看板接口新增 requester 校验，并补 owner、非 owner、匿名访客三类身份回归。

P1 本轮未展开实现，避免拖慢 P0 闭环。

## 2. 修复内容

### BUG-01：业务识别后切换工作台专门提示

涉及文件：

- `miniprogram/pages/resource-create/index.js`
- `miniprogram/pages/resource-create/index.wxml`
- `miniprogram/pages/resource-create/index.wxss`

修复内容：

- 房源资料建议切换到 `workspaceMode=property`。
- 商品 / 团购资料建议切换到 `workspaceMode=groupbuy`。
- 服务方案 / 电子名片资料建议切换到 `workspaceMode=service`。
- 识别提示卡新增专门区域：
  - `继续当前工作台`
  - `切换到对应工作台`
- 点击“切换到对应工作台”只调用本地 `saveWorkspaceMode` 保存工作台偏好，不修改资料 owner、不删除资料、不改变资料类型归属。
- 点击“继续当前工作台”保持当前 `workspaceMode`，资料仍保留在当前流程内。
- 按钮样式使用 `rpx` 和 flex 居中，避免真机文字偏上、偏下或挤压。

回归覆盖：

- P0-03：首次模式选择不受影响。
- P0-04：工作台模式保存逻辑复用原 `saveWorkspaceMode`。
- P0-07：首页 / 工作台后续读取同一 `workspaceMode`。
- P0-22：切换只改展示偏好，不改资料数据。
- P0-23：业务识别后已有切换与继续双选。

### BUG-02：权限和隐私专项回归证据

涉及文件：

- `backend/app/api/routes_dashboard.py`
- `backend/app/services/app_service.py`
- `backend/tests/test_app.py`
- `miniprogram/services/api.js`

修复内容：

- `GET /api/dashboard/business` 新增 `requesterUserId` 参数。
- 后端校验规则：
  - owner 本人可查看自己的工作台总看板。
  - 非 owner 请求 owner 工作台总看板返回 `403`。
  - 匿名 / 缺少请求者身份返回 `401`。
- 小程序 `fetchBusinessDashboard` 默认把当前 owner 作为 requester 传入，不影响正常 owner 自查。
- 后端专项测试补充覆盖：
  - 工作台总览 / 客户看板数据：owner 可读，非 owner 403，匿名 401。
  - 展示页效果：owner 可读，非 owner 403，匿名缺身份 422 拒绝。
  - 单条资料互动：owner 可读，非 owner 403，匿名缺身份 422 拒绝。

回归覆盖：

- P0-14：工作台反馈中心 owner 可访问。
- P0-15：展示页效果入口保留且权限不倒退。
- P0-16：单条资料互动入口保留且权限不倒退。
- P0-25：相关接口和路由无阻断。
- P0-27：已形成 owner / 非 owner / 匿名访客专项证据。

## 3. 未修项及原因

- BUG-03：首页最近反馈按类型进入筛选：P1，未修。原因：本轮按用户要求优先闭环 P0，避免扩大首页和工作台路由改动。
- BUG-04：资料页按 `workspaceMode` 默认筛选或推荐：P1，未修。原因：需要触达资料页筛选策略，留到 P0 复测后处理。
- BUG-05：合集页按当前模式动态推荐：P1，未修。原因：一期合集页保持轻版，不在本轮扩展推荐排序。
- BUG-06：`workspaceMode` 后端持久化：P1，未做后端改造。当前仍按一期决策仅保存小程序本地缓存；清缓存、换设备或重新登录后需要重新选择，但不会影响资料安全和资料归属。

## 4. 执行的检查命令

已通过：

```text
node --check miniprogram/pages/resource-create/index.js
node --check miniprogram/services/api.js
python3 -m py_compile backend/app/api/routes_dashboard.py backend/app/services/app_service.py backend/tests/test_app.py
find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check
递归解析 miniprogram 下所有 .json：44 个通过
git diff --check
/tmp/teambuy-py312-test/bin/pytest backend/tests/test_app.py -q -k "business_dashboard_aggregates_real_customer_data or create_note_demo_data_for_owner or showcase or customer_actions"
/tmp/teambuy-py312-test/bin/pytest backend/tests/test_app.py -q
```

结果：

- 小程序 JS 语法检查：通过。
- 小程序 JSON 解析检查：通过，44 个 JSON。
- `git diff --check`：通过。
- 权限 / 隐私专项后端测试：`7 passed, 89 deselected`。
- 后端主测试：`96 passed`。

说明：

- 本机没有 `python` 命令，已使用 `python3` 和项目既有 Python 3.12 测试环境 `/tmp/teambuy-py312-test/bin/pytest` 完成检查。

## 5. 需要真机确认事项

- 业务识别提示卡在真机上是否出现“继续当前工作台 / 切换到对应工作台”两个按钮。
- 两个按钮文字是否上下左右居中、不拆行、不挤压。
- 点击“切换到对应工作台”后，回到首页和工作台 Tab 是否按新模式展示。
- 点击“继续当前工作台”后，当前模式是否保持不变，资料是否仍可查看和编辑。
- 最新小程序体验版上传后，确认 Tabbar、首页、资料、合集、工作台、我的无白屏和无页面不存在。

小程序预览、上传体验版和提交审核仍由用户在微信开发者工具中手动完成。
