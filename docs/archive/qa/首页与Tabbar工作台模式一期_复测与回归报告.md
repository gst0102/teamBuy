# 首页与Tabbar工作台模式一期_复测与回归报告

更新时间：2026-06-23

## 1. 复测结论

结论：需要人工确认。

原因：

- 两个 P0 在代码和自动化证据层面已闭环。
- 权限 / 隐私专项复测通过，后端主测试通过。
- 但本轮未在微信开发者工具或真机体验版中截图确认新增提示卡 UI，因此不能直接判定“通过”。

可以进入最终人工确认。最终确认重点是小程序体验版真机 UI 和主流程体验。

## 2. P0 复测结果

### BUG-01：业务识别后缺少切换工作台专门提示

复测结果：自动化 / 静态层面通过，真机 UI 待人工确认。

已确认：

- `miniprogram/pages/resource-create/index.wxml` 已新增工作台切换提示区。
- 提示文案包含“是否切换到{{businessPromptWorkspaceName}}？”。
- 提供两个明确动作：
  - `继续当前工作台`
  - `切换到对应工作台`
- `miniprogram/pages/resource-create/index.js` 已新增 `handleWorkspaceSwitch` 和 `handleWorkspaceStay`。
- 切换动作调用 `saveWorkspaceMode`，只更新本地 `workspaceMode`。
- 未看到修改资料 owner、删除资料或强制改变资料归属的逻辑。
- 样式位于 `miniprogram/pages/resource-create/index.wxss`，使用 `rpx`、grid/flex 与居中规则。

回归覆盖：

- P0-03：首次模式选择不受该提示改动阻断。
- P0-04：工作台模式仍复用 `workspaceMode` 保存逻辑。
- P0-07：首页 / 工作台读取同一模式偏好。
- P0-22：切换只影响展示偏好，不改资料归属。
- P0-23：业务识别后已有“切换 / 继续”双选。

### BUG-02：权限和隐私未形成专项回归证据

复测结果：通过。

已确认：

- `GET /api/dashboard/business` 已新增 `requesterUserId` 参数。
- 后端 `get_business_dashboard` 已校验请求者身份：
  - owner 本人可查看。
  - 非 owner 返回 `403`。
  - 缺少请求者身份返回 `401`。
- `backend/tests/test_app.py` 已补充 owner、非 owner、匿名访客三类身份回归。
- 权限证据覆盖工作台总看板、展示页效果、单条资料互动三类后台数据入口。

回归覆盖：

- P0-14：工作台反馈中心 owner 可访问。
- P0-15：展示页效果权限未倒退。
- P0-16：单条资料互动权限未倒退。
- P0-25：相关接口和路由无阻断。
- P0-27：owner / 非 owner / 匿名访客专项证据已补齐。

## 3. 已执行复测命令

已通过：

```text
node --check miniprogram/pages/resource-create/index.js
node --check miniprogram/services/api.js
git diff --check
递归解析 miniprogram 下所有 .json：44 个通过
/tmp/teambuy-py312-test/bin/pytest backend/tests/test_app.py -q -k "business_dashboard_aggregates_real_customer_data or create_note_demo_data_for_owner or showcase or customer_actions"
/tmp/teambuy-py312-test/bin/pytest backend/tests/test_app.py -q
```

结果：

- 小程序关键 JS 语法检查：通过。
- 小程序 JSON 解析检查：通过，44 个 JSON。
- `git diff --check`：通过。
- 权限 / 隐私专项测试：`7 passed, 89 deselected`。
- 后端主测试：`96 passed`。

## 4. P1 剩余项

以下 P1 本轮未修，不阻断 P0 闭环，但建议进入下一轮体验优化：

- BUG-03：首页最近反馈按类型进入筛选。
- BUG-04：资料页按 `workspaceMode` 默认筛选或推荐，同时保留“全部资料”。
- BUG-05：合集页按当前模式动态突出推荐方向。
- BUG-06：`workspaceMode` 后端持久化。当前仍为小程序本地缓存，清缓存、换设备或重新登录后需要重新选择。

## 5. 未覆盖与需要人工确认

本轮未覆盖：

- 微信开发者工具预览截图。
- 真机体验版按钮视觉检查。
- 真实业务识别后从提示卡切换到首页 / 工作台的端到端手动路径。

需要用户人工确认：

- 业务识别提示卡是否真实出现“继续当前工作台 / 切换到对应工作台”两个按钮。
- 两个按钮文字是否上下左右居中、不拆行、不挤压。
- 点击“切换到对应工作台”后，首页和工作台 Tab 是否按新模式展示。
- 点击“继续当前工作台”后，当前模式是否保持不变，资料是否仍可查看和编辑。
- 最新体验版中：首页、资料、合集、工作台、我的五个 Tab 无白屏、无页面不存在、无明显错位。

## 6. 是否可以进入最终人工确认

可以进入最终人工确认。

进入条件说明：

- P0 的代码和自动化证据已闭环。
- 当前剩余问题主要是真机 UI 与体验版路径确认。
- 若真机确认新增提示卡按钮异常、页面白屏、按钮截字或切换后首页 / 工作台未随模式变化，应重新开 Bug 单。
