# 资料助手绑定接口同步部署 Codex 自测报告

日期：2026-08-24

## 结论

生产接口已同步，点击资料助手时的 404 根因已修复。小程序错误文案已在本地补充，需上传体验版后生效。

## 根因

前端调用 `GET /api/auth/wecom-bind-status`，生产旧版本未注册该路由；同时绑定卡接口和请求模型也未同步，导致后续完整绑定链路仍有风险。前端原先把 404 统一显示为“登录状态异常”。

## 变更

- 同步生产 `backend/app/api/routes_auth.py`。
- 同步生产 `backend/app/schemas/auth.py`。
- 本地 `library`、`home` 两个入口按 401/404/其他错误区分提示。

## 验证

- 公网 `/health`：200，PostgreSQL configured。
- 生产路由：已注册 `wecom-bind-status`、`wecom-bind-card`。
- 带真实签名会话查询绑定状态：`success=true`、`status=unbound`。
- 无效绑定卡请求：返回预期 400“绑定卡片无效”，未写入数据。
- 容器启动日志：无 `ImportError`、`Traceback`、`Internal Server Error`。

## 备份与剩余动作

- 备份：`/home/ubuntu/teamBuy-backups/wecom-bind-routes-20260824-233812/`。
- 上传小程序体验版后，人工验证点击资料助手能显示绑定引导；完整绑定需要使用真实企业微信流程，不能用伪造 token。
