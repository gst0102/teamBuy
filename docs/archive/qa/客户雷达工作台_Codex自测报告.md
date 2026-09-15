# 客户雷达工作台 Codex 自测报告

日期：2026-08-26

## 交付范围

- 雷达页收敛为“待跟进 / 活跃访客 / 已放弃”三个状态，不再把“资料优化”混在客户工作流中。
- 顶部三项数字从当前页面投影动态计算：待跟进、活跃访客、已放弃；完成动作后先本地更新，再由服务端结果校正。
- 客户卡统一展示身份、意向、最近行为和客户实际看到的内容；来源资料使用真实 note ID 跳转，不再固定展示房源。
- 卡片只保留三个明确入口：处理情况、原资料、放弃跟进。已放弃卡片提供恢复跟进和清空删除。
- 后端新增 `abandonedProfiles` 投影、`restore` 动作和 `deleted` tombstone，避免清空后历史浏览事件把客户重新召回。
- 雷达刷新保留已有内存快照，只显示轻量更新提示；移除本页无 UI 消费的提醒配置预加载。

## 验收标准与结果

| 项目 | 结果 |
| --- | --- |
| 待跟进、活跃访客、已放弃数字动态变化 | 通过：由三组当前列表派生，动作后乐观更新 |
| 放弃后同时从待跟进和活跃访客移除 | 通过：前端按客户身份批量出队，后端关闭状态统一过滤 |
| 已放弃列表可恢复 | 通过：`restore` 写回 `pending`，并返回未移出雷达标记 |
| 清空后不因历史事件重新出现 | 通过：`deleted` tombstone 保留身份过滤边界 |
| 来源资料动态 | 通过：使用 profile 的 note ID、标题和 focusSections |
| 匿名访客不冒充实名 | 通过：卡片明确显示“匿名访客”，不猜测姓名 |
| 页面按钮文字和布局 | 通过：新 WXML 使用两列 flex 居中按钮，核心尺寸使用 rpx |
| 旧“资料优化”页签和“查看资料/复制首句”卡片动作 | 通过：已从雷达工作流移除 |

## 自动化验证

- `backend/tests/test_sales_scrm.py`：16 passed。
- 全量 `backend/tests`：290 passed，1 failed。
- 失败项是本轮之前已存在的 `test_note_preview_view_updates_note_list_stats`，分享统计仍为 `shareCount == 0`；本轮未修改分享统计链路，单独重跑仍复现。
- `node --check miniprogram/pages/visits/index.js`：通过。
- `node --check miniprogram/pages/home/index.js`：通过。
- `python3 -m py_compile backend/app/models/domain.py backend/app/services/app_service.py`：通过。
- `git diff --check`：通过。

## 仍需人工验收

本轮未部署生产，也未上传微信体验版。请在微信开发者工具重新编译 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram` 后检查：

1. 雷达页是否与已确认效果稿一致，三项数字和三个页签是否清晰。
2. 待跟进/访客卡的“处理情况、原资料、放弃跟进”点击区域是否符合预期。
3. 放弃后切换到“已放弃”，恢复和清空是否立即更新；再次刷新后状态是否保持。
4. 真实资料、名片、合集来源是否分别跳转到对应客户页，而不是固定房源页面。
