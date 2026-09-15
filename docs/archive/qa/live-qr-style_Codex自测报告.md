# 活码投放样式切换：Codex 自测报告

日期：2026-09-01

## 结论

代码已完成“纯二维码 / 保留原图”投放样式切换，并已部署后端。保留原图模式以用户上传图片为视觉来源，只替换二维码；微信体验版未上传。

## 覆盖内容

- 新建活码时可选择“纯二维码”或“保留原图”。
- 已有活码可切换样式；切换不改变固定入口。
- 更新目标二维码时，保留原图模式会重新生成投放图。
- 原始目标二维码和派生投放图分别登记媒体引用。
- 保存投放图后询问是否开启到期提醒，卡片保留“开启提醒”入口。

## 自动化验证

- `./.venv312/bin/python -m pytest -q backend/tests`：327 passed。
- `node --check miniprogram/pages/group-resource-library/index.js`：通过。
- `node --check miniprogram/services/api.js`：通过。
- `node --check miniprogram/services/subscription.js`：通过。
- `./.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- `git diff --check`：通过。
- 生成的投放图使用固定入口编码，OpenCV 解码结果与固定入口一致。

## 生产部署验证

- 备份：`/home/ubuntu/teambuy-backups/20260901-230846-live-qr-style/`。
- 新镜像标签：`20260901-230846-live-qr-style`；旧镜像回滚标签：`rollback-20260901-230846-live-qr-style`。
- API、backend-worker、archive-worker、PostgreSQL 均 healthy，8004 映射、公网 `/health` 和 `/health/db` 通过。
- OpenAPI 已注册 `/api/live-qr-codes/{qr_id}/style`，容器内 4 个部署文件哈希与本地一致。

## 尚需人工验收

- 微信开发者工具重新编译并手动上传体验版。
- 上传真实带群头像、群名称和排版的二维码，检查“保留原图”是否只替换二维码区域。
- 在微信内保存投放图并扫码，确认能进入固定入口；再更新二维码，确认外部固定入口不变。
- 确认保存后的到期提醒授权弹窗，以及拒绝后卡片内“开启提醒”入口仍可使用。
