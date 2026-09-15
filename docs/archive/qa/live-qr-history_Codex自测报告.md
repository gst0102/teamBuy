# 我的活码历史与到期提醒：Codex 自测报告

日期：2026-09-01

## 结论

后端与小程序代码已完成本轮实现，后端已部署生产；微信体验版尚需用户在微信开发者工具中手动上传后进行真机验收。

## 本轮覆盖

- “我的活码”当前记录、固定入口、7 天有效期、剩余天数、下载、更新、删除和最近历史记录。
- 更新二维码复用原活码 `code`，递增版本并刷新有效期；管理员更新同样记录历史元数据。
- 互助积分状态读取不再对 PostgreSQL 全量回写旧 `AppState`，避免覆盖活码和媒体记录。
- 活码列表请求失败时保留最近成功列表。
- 到期提醒使用独立 `live_qr_expiry` 场景，剩余两天内按活码 ID + 版本幂等排队；发送后可通过页面按钮主动授权下一次提醒。

## 自动化验证

- `./.venv312/bin/python -m pytest -q backend/tests`：326 passed。
- `node --check miniprogram/pages/group-resource-library/index.js`：通过。
- `node --check miniprogram/services/subscription.js`：通过。
- `python3 -m compileall -q backend/app backend/tests`：通过。
- `git diff --check`：通过。
- 全仓测试未通过：既有 `platform/wecom-archive-core/tests/test_engine.py` 无法导入 `app.codec`，属于测试运行路径问题，未因本轮改动产生。

## 生产验证

- API、backend-worker、archive-worker、PostgreSQL 均 healthy。
- 本地与公网 `/health` 均返回数据库 backend 为 PostgreSQL 且 status 为 ok。
- 生产端口确认 `0.0.0.0:8004 -> 8000`。
- 运行时确认活码订阅模板、字段映射、页面配置已加载，`LiveQrCode.targetQrHistory` 已注册，相关 OpenAPI 路由已注册。
- 生产备份：`/home/ubuntu/teambuy-backups/20260901-215205-live-qr-history/`。
- 旧三份镜像保留回滚标签：`rollback-20260901-215205-live-qr-history`。

## 未覆盖与人工验收

- 微信开发者工具清缓存、重新编译、上传体验版后，使用真实群二维码验证创建、固定入口访问、保存、更新、历史和删除。
- 在微信后台确认模板字段类型与字段序号匹配，并由用户在页面主动允许订阅；不能依赖后台静默获得下一次授权。
- 不创建生产测试活码，不创建充值订单，不调用 `test-confirm`。
