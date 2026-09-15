# 互帮互助执行者详情页与跨设备任务可用性修复：Codex 自测报告

日期：2026-09-07

## 结论

代码层自测通过；本轮尚未部署生产，也未上传微信体验版，真机视觉和微信小程序跳转仍需人工验收。

## 已覆盖

- 执行者设备不再使用本地发布者积分缓存判断 `taskClosed`。
- 后端任务 payload 返回服务端权威字段 `taskClosed`。
- 发布中且仍有剩余次数的任务，在执行者详情页可继续打开入口。
- 已结束、暂停、删除和无剩余次数的任务仍会被正确拦截。
- 详情页按执行顺序重排：打开入口、完成体验、返回提交；奖励、规则、标准改为紧凑信息区。
- 保留浅色/深色主题切换、羊毛解锁、评论、图片反馈和分享逻辑。
- 三类任务统一详情页骨架：小程序任务执行并提交、普通任务提交材料、羊毛任务解锁/使用福利。
- 羊毛任务锁定状态显示查看费用和解锁按钮；解锁后显示福利入口，不显示普通任务提交按钮。
- 普通任务没有入口时显示阅读说明引导，不渲染无效入口操作。

## 自动检查

- `node --check miniprogram/subpackages/my-tools-mutual-help/shared.js`：通过
- `node --check miniprogram/subpackages/my-tools-mutual-help/task-detail/index.js`：通过
- `python -m compileall -q backend/app/services/app_service.py`：通过
- `git diff --check`：通过
- `./.venv312/bin/pytest -q backend/tests/test_mutual_help_points.py backend/tests/test_mutual_points_dual_ledger.py`：12 passed
- `./.venv312/bin/pytest -q backend/tests/test_app.py`：186 passed
- 三项测试合并回归：`198 passed`

## 待人工验收

1. 发布者账号发布一个仍有次数的小程序任务。
2. 另一账号通过分享卡片进入详情页，确认不是“任务结束”。
3. 点击“打开小程序”，返回后确认按钮变为可提交状态。
4. 提交完成记录，确认发布者端能看到待审核记录，奖励结算规则不变。
5. 用已结束或剩余 0 次的任务复测，确认入口和提交仍被拦截。
6. 在微信开发者工具重新编译并上传体验版后，按效果图检查布局、字号、按钮居中和滚动体验。
