# 客户详情页放弃跟进｜Codex 自测报告

日期：2026-08-26

## 结论

代码层自测通过，已实现“直接放弃跟进、保留历史、从雷达移除”的最小闭环。后端需要部署，小程序需要重新上传体验版；微信真机点击和生产接口仍需人工验收。

## 已覆盖

- 客户详情固定底部只保留“记录跟进/开始跟进”和浅橙色“放弃跟进”两个等宽动作。
- 点击“放弃跟进”不弹确认框，复用已有跟进接口写入 `paused`、结论和日志。
- 无跟进记录时先建立客户跟进档案，再写入 `paused`。
- 放弃成功后清理客户雷达内存缓存并返回雷达列表。
- 后端雷达过滤 `paused`、`invalid`、`completed` 客户，防止其因浏览事件或高意向评分再次出现。
- 客户详情和历史记录仍能读取已放弃的客户，且可以恢复为 `pending`。

## 命令与结果

- `node --check miniprogram/pages/customer-detail/index.js`：通过。
- `python -m compileall -q backend/app/services/app_service.py`：通过。
- `backend/tests/test_sales_scrm.py`：16 passed。
- `backend/tests/test_app.py -k lead_reminder_flow_persists_status_note_and_filters`：1 passed。

补充修复：原先放弃成功后使用 `wx.redirectTo` 进入 TabBar 雷达页，微信不会按预期切换；已改为 `wx.switchTab`，并通过源码检查确认客户详情不再对雷达使用 `redirectTo`。

## 未覆盖 / 需人工确认

- 生产后端部署后的真实接口响应和权限状态。
- 微信开发者工具重新编译上传后的浅橙色按钮、安全区和返回雷达行为。
- 无 `leadId` 客户首次点击放弃时的真机表现。
- 恢复跟进后雷达排序和数量是否符合运营预期。
- 微信真机点击放弃后是否立即切换到雷达 Tab，并刷新到最新列表。

## 2026-08-26 追加：雷达处理动作统一出队

### 本次修复

- “开始/继续跟进”写入 `contacted`；“放弃跟进”写入 `paused`。
- 两种状态均从雷达“待跟进”和“访客”列表移除，客户详情、来源资料、联系方式和历史记录继续保留。
- 新增 `/api/scrm/customer-followups/action`，无档案客户一次完成建档和目标状态写入，避免原先的 ensure + update 双请求。
- 成功后小程序清理客户雷达内存缓存，并用 `wx.switchTab` 返回雷达；已有档案的“继续跟进”文案不再伪装成仅打开记录表单。

### 验证结果

- `.venv313/bin/pytest -q backend/tests/test_sales_scrm.py`：16 passed。
- `.venv313/bin/pytest -q backend/tests/test_app.py -k 'lead_reminder_flow_persists_status_note_and_filters or customer_intelligence'`：1 passed。
- `.venv313/bin/pytest -q backend/tests`：290 passed，1 failed；失败项为既有资料分享统计测试 `test_note_preview_view_updates_note_list_stats`，与本次客户跟进动作无关。
- `node --check`：客户详情 JS、API JS 通过；Python compileall 和 `git diff --check` 通过。
- 生产 `/health`：Postgres 正常；生产动作接口未授权请求返回 401，鉴权链正常。

### 人工验收

需在微信开发者工具重新编译上传 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram` 体验版后，分别点击“开始/继续跟进”和“放弃跟进”，确认两者都快速返回雷达且不再显示在待跟进、访客列表。
