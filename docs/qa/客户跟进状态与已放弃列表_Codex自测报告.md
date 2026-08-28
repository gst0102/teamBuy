# 客户跟进状态与已放弃列表 Codex 自测报告

日期：2026-08-27

## 结论

本地回归通过，后端已部署生产，等待小程序体验版人工验证。

## 已覆盖

- `deleted` 线索状态可被领域模型和服务层兼容，清空后的 tombstone 不进入工作列表。
- 无真实 `paused` 线索档案的历史访客不会进入 `abandonedProfiles`。
- 开始跟进会把线索置为 `following`，并写入“已开始跟进”。
- 继续跟进复用原线索、保持跟进中状态，并写入“已继续跟进”。
- 跟进中客户从待跟进和访客列表移除，进入独立的“跟进中”列表，数量动态更新。
- 客户详情从 `leadId` 入口可执行跟进，成功后原地更新，不跳转雷达。
- 雷达摘要向详情缓存首屏提供最近跟进记录。

## 自动化验证

- `./.venv313/bin/pytest -q backend/tests/test_sales_scrm.py backend/tests/test_customer_info_chain_control.py`：20 passed。
- `python3 -m py_compile backend/app/models/domain.py backend/app/services/app_service.py backend/app/api/routes_ops_admin.py backend/app/api/routes_scrm.py`：通过。
- 相关小程序页面 `node --check`：通过。
- `git diff --check`：通过。

## 生产部署验证

- 线上备份：`/home/ubuntu/teambuy-backups/follow-up-status-20260827-063235`。
- backend、backend-worker、archive-worker、Postgres 均运行；API 绑定原端口 `8004`。
- 本机与公网 `/health` 均返回 200。
- 未登录访问 SCRM 路由返回 401，而不是 404。

## 未覆盖 / 人工验收

- 尚未用真实线上账号执行开始/继续跟进，需要用户在体验版验证真实历史 `deleted` 数据与跟进状态。
- 微信开发者工具需清缓存、重新编译并上传体验版，验证开始/继续跟进、返回雷达、跟进中数量和详情原地刷新。
- 生产部署时需保证领域模型、服务层和 SCRM 路由同版本；本次已完成后端同版本发布，小程序页面仍待体验版发布。
