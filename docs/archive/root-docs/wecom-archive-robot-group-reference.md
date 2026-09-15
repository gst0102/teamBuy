# 企业微信会话归档 / 智能机器人 / 建群能力参考

本文档用于集中整理 `teamBuy` 项目里和以下能力相关的资料、配置参数、接口与迁移注意事项：

- 企业微信客服回调
- 企业微信会话内容存档
- 智能机器人查询网关
- 企业微信群机器人群发
- 企业微信群“入群方式 / 建群承接”
- 群二维码上传与资源导入

适用场景：

- 旧项目查阅
- 新项目迁移
- 交给其他开发继续接手
- 部署前快速核对配置

---

## 1. 一眼看懂：这几块能力分别做什么

### 1.1 企业微信客服回调

作用：

- 接收企业微信客服回调事件
- 做 URL 验证
- 触发真实 `sync_msg` 拉取或 mock 导入

当前固定回调地址：

```text
https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback
```

代码位置：

- `backend/app/api/routes_wecom.py`

关键常量：

```text
KF_CALLBACK_PATH = "/kf/teamBuy/callback"
```

---

### 1.2 会话内容存档

作用：

- 接收企业微信“会话内容存档”事件
- 拉取 archive 消息
- 处理消息、补媒体、写入数据库
- 给后续“资料卡 / 机器人 / 跟进”提供真实会话底座

当前固定事件服务器地址：

```text
https://teambuy.lifelove.top/api/wecom/archive/callback
```

代码位置：

- `backend/app/api/routes_wecom.py`
- `backend/app/services/wecom_archive_client.py`
- `backend/app/worker.py`

关键常量：

```text
ARCHIVE_CALLBACK_PATH = "/archive/callback"
```

---

### 1.3 智能机器人查询网关

作用：

- 让外部机器人或中间层把“某个用户 / 某个群”的问题转给后端
- 后端按 scope 判断是查个人资料、群内容，还是要求先绑定

当前不是企业微信群发机器人，而是“查询型机器人入口”。

代码位置：

- `backend/app/api/routes_robot.py`

接口前缀：

```text
/api/robot
```

---

### 1.4 企业微信群机器人群发

作用：

- 给企业微信群发固定模板消息
- 当前支持中午播报 / 下午入群口径 / 晚间总结 / 自定义
- 支持文本和小程序卡片

代码位置：

- `backend/app/api/routes_wecom.py`
- `backend/app/api/routes_ops_admin.py`

注意：

- webhook 只能由后端白名单配置，不允许前端直接传 webhook URL

---

### 1.5 建群 / 入群方式

作用：

- 通过企业微信 `add_join_way` 生成“可点击加入群聊”的配置
- 保存 `config_id`
- 后续可在 PC 运营后台管理

代码位置：

- `backend/app/api/routes_ops_admin.py`
- `backend/app/services/wecom_client.py`

---

### 1.6 群二维码上传

作用：

- 批量上传群二维码到服务器
- 生成公网 URL
- 供资源导入模板直接使用

对应交接文档：

- `docs/stage2-docs/30-group-qr-server-upload-handoff.md`

---

## 2. 重要文档索引

最值得先看的文档如下：

### 会话归档

- `docs/stage2-docs/10-wecom-archive-config.md`
- `docs/project-memory.md`
- `docs/qa/企业微信真实联调记录.md`

### 企业群机器人 / 群消息模板

- `docs/stage2-docs/31-enterprise-group-daily-operations-v1.md`
- `docs/stage2-docs/32-enterprise-group-bot-message-templates-v1.md`

### 建群 / 群二维码

- `docs/stage2-docs/30-group-qr-server-upload-handoff.md`

### 项目级迁移与交接

- `docs/config-migration-reference.md`
- `docs/new-project-migration-checklist.md`
- `docs/handoff-latest.md`

---

## 3. 代码入口索引

### 后端路由

- `backend/app/api/routes_wecom.py`
- `backend/app/api/routes_robot.py`
- `backend/app/api/routes_ops_admin.py`

### 配置

- `backend/.env.example`
- `backend/app/core/config.py`

### 服务层

- `backend/app/services/wecom_client.py`
- `backend/app/services/wecom_archive_client.py`
- `backend/app/services/ops_console_store.py`

### worker

- `backend/app/worker.py`

---

## 4. 配置参数总表

下面按用途分组。

### 4.1 企业微信客服 / 真实同步

```text
PUBLIC_BASE_URL
WECOM_ADMIN_TOKEN
WECOM_USE_MOCK
WECOM_API_BASE_URL
WECOM_CORP_ID
WECOM_KF_CALLBACK_TOKEN
WECOM_KF_SECRET
WECOM_KF_ENCODING_AES_KEY
WECOM_OPEN_KFID
WECOM_SYNC_CURSOR
WECOM_SYNC_LIMIT
WECOM_SYNC_LOCK_TIMEOUT_SECONDS
WECOM_BIND_INTENT_TTL_SECONDS
WECOM_UNCLAIMED_DEFAULT_OWNER_USER_ID
```

说明：

- `WECOM_KF_SECRET` 是客服 / 应用侧 Secret，不等于会话存档 Secret。
- `PUBLIC_BASE_URL` 决定回调地址与外部可访问地址。
- `WECOM_USE_MOCK=false` 才是走真实企业微信链路。

---

### 4.2 会话内容存档

```text
WECOM_ARCHIVE_ENABLED
WECOM_ARCHIVE_SECRET
WECOM_ARCHIVE_CALLBACK_TOKEN
WECOM_ARCHIVE_ENCODING_AES_KEY
WECOM_ARCHIVE_PRIVATE_KEY_PATH
WECOM_ARCHIVE_PUBLIC_KEY_PATH
WECOM_ARCHIVE_SDK_LIB_PATH
WECOM_ARCHIVE_PULL_LIMIT
WECOM_ARCHIVE_SDK_TIMEOUT_SECONDS
WECOM_ARCHIVE_PROXY
WECOM_ARCHIVE_PROXY_PASSWORD
WECOM_ARCHIVE_WORKER_ENABLED
WECOM_ARCHIVE_WORKER_INTERVAL_SECONDS
```

说明：

- `WECOM_ARCHIVE_SECRET` 是会话内容存档后台给的 Secret，独立于 `WECOM_KF_SECRET`。
- `WECOM_ARCHIVE_PRIVATE_KEY_PATH` 指向私钥，只能放服务器或本地安全目录，不能进 Git。
- `WECOM_ARCHIVE_SDK_LIB_PATH` 在真实拉取时必填，通常是容器内绝对路径，例如：

```text
/app/secrets/libWeWorkFinanceSdk_C.so
```

- `WECOM_ARCHIVE_CALLBACK_TOKEN` / `WECOM_ARCHIVE_ENCODING_AES_KEY` 可以独立配置；如果不配，代码会回退复用普通客服回调的 token / aes key。

---

### 4.3 智能机器人

```text
ROBOT_GATEWAY_TOKEN
```

说明：

- 机器人入口调用后端时，需带：

```text
Authorization: Bearer <ROBOT_GATEWAY_TOKEN>
```

---

### 4.4 企业群机器人

```text
WECOM_GROUP_BOT_WEBHOOKS
```

格式：

```json
{
  "property": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
  "cooperation": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=yyy"
}
```

说明：

- 这是 `groupId -> webhook` 的后端白名单。
- 真实 webhook 只能保存在后端环境或 PC 后台渠道映射，不可放前端，不可写死到请求 body。

---

## 5. 当前已知生产 / 部署信息

生产服务器：

```text
IP: 81.70.84.35
user: ubuntu
project dir: /home/ubuntu/teamBuy
domain: https://teambuy.lifelove.top
```

项目里已固定的重要公网地址：

```text
企业微信客服回调：
https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback

会话归档回调：
https://teambuy.lifelove.top/api/wecom/archive/callback
```

说明：

- 这两个地址后续如果迁项目，最容易漏改。
- 新项目如果域名变了，企业微信后台和后端 `.env` 要一起改。

---

## 6. 关键接口一览

### 6.1 客服 / 同步 / 归档接口

文件：

- `backend/app/api/routes_wecom.py`

核心接口：

```text
GET  /api/wecom/kf/teamBuy/callback
POST /api/wecom/kf/teamBuy/callback

GET  /api/wecom/config-check
GET  /api/wecom/customer-service-config
POST /api/wecom/real-sync
POST /api/wecom/real-sync/unlock

GET  /api/wecom/archive/config-check
GET  /api/wecom/archive/callback
POST /api/wecom/archive/callback
POST /api/wecom/archive/pull
POST /api/wecom/archive/process
POST /api/wecom/archive/media-backfill
GET  /api/wecom/archive/cursor
GET  /api/wecom/archive/messages
POST /api/wecom/archive/mock-messages
```

---

### 6.2 企业群机器人接口

文件：

- `backend/app/api/routes_wecom.py`

接口：

```text
GET  /api/wecom/group-bot/config
POST /api/wecom/group-bot/broadcast
```

请求鉴权：

```text
X-Admin-Token: <WECOM_ADMIN_TOKEN>
```

关键规则：

- 默认 `dryRun=true`
- 只有显式传 `dryRun=false` 才真正发消息
- 支持 `template = midday / afternoon / evening / custom`
- 支持 `messageType = text / miniapp_card`

---

### 6.3 智能机器人接口

文件：

- `backend/app/api/routes_robot.py`

接口：

```text
POST /api/robot/query
```

请求字段：

```json
{
  "corpId": "wwxxx",
  "chatType": "private",
  "fromUserId": "zhangsan",
  "externalUserId": "woAJ...",
  "roomId": "wr123",
  "text": "我最近保存的资料",
  "limit": 5
}
```

当前逻辑特征：

- 支持个人资料查询语义
- 支持群语义识别
- 未绑定用户时返回 `bind_required`
- 群场景下返回“群消息可进入 archive，后续可生成日报/广告提醒/待跟进事项”的提示型结果

---

### 6.4 PC 后台建群 / 群发渠道接口

文件：

- `backend/app/api/routes_ops_admin.py`

接口：

```text
GET  /api/ops-admin/group-bot-channels
POST /api/ops-admin/group-bot-channels

GET  /api/ops-admin/wecom-customer-groups
GET  /api/ops-admin/wecom-group-join-ways
POST /api/ops-admin/wecom-group-join-ways
```

说明：

- `wecom-group-join-ways` 会调用企业微信 `externalcontact/groupchat/add_join_way`
- 返回的 `config_id` 会保存，供后续“点击入群”能力使用

---

## 7. 功能边界：最容易混淆的几件事

### 7.1 `WECOM_KF_SECRET` 不等于 `WECOM_ARCHIVE_SECRET`

- 前者偏客服 / 应用能力
- 后者是会话内容存档专用

不能混用。

### 7.2 `routes_robot.py` 不是“群发机器人”

- `routes_robot.py` 是查询型、对话型入口
- 真正的企业群消息广播在 `routes_wecom.py` 的 `/api/wecom/group-bot/*`

### 7.3 “建群”不等于“群二维码上传”

- `add_join_way` 是企业微信官方入群配置能力
- 群二维码上传是把已有二维码图托管到服务器，适合做资源卡 / 导入模板

两条链路不同，可以并存。

### 7.4 会话归档 worker 不等于 callback

- callback 只负责接收事件 / 验证
- 真正持续拉取和处理 archive，通常还要依赖 worker

如果只部署接口、不启 worker，归档链路会看起来“已接通但不持续工作”。

---

## 8. 新项目迁移时建议优先复用什么

建议优先迁这几块“底座思路”：

### 8.1 企业微信回调骨架

- `routes_wecom.py` 的 callback 验证方式
- `customer-service-config`
- `config-check`

### 8.2 会话归档骨架

- archive 独立 env 分组
- archive callback
- pull / process / cursor / worker 设计

### 8.3 机器人网关骨架

- `ROBOT_GATEWAY_TOKEN`
- `POST /api/robot/query` 的统一入口思路

### 8.4 企业群机器人白名单机制

- 后端保存 webhook 白名单
- `dryRun` 默认开启
- 支持模板消息和小程序卡片

### 8.5 建群后台能力

- `add_join_way`
- `config_id` 存档
- PC 后台运营管理

---

## 9. 新项目迁移时不要直接照搬什么

### 9.1 不要照搬真实值

以下内容必须重配：

- 域名
- 企业微信 CorpID / Secret / KfID
- archive Secret
- archive RSA 私钥 / 公钥
- webhook
- admin token
- robot token

### 9.2 不要把旧项目文案 / 业务标签强塞过去

例如：

- 房源 / 商机 / 资源工具特定字段
- 历史运营分组命名
- 旧模板消息内容

### 9.3 不要把 Git 文档里的占位符误当真实配置

仓库里的文档适合当说明，不代表里面就是线上当前值。

---

## 10. 已知风险与踩坑提醒

### 10.1 Secrets 泄露风险

绝对不要提交：

- `WECOM_KF_SECRET`
- `WECOM_ARCHIVE_SECRET`
- archive 私钥
- webhook
- `ROBOT_GATEWAY_TOKEN`

### 10.2 archive 典型缺项

最常见的不是 callback，而是：

- `WECOM_ARCHIVE_SDK_LIB_PATH` 没配
- 私钥路径错误
- worker 没开
- 可信 IP / SDK 环境不完整

### 10.3 群机器人误用风险

- 不要让前端传 webhook URL
- 不要默认直接真发
- 先 `dryRun` 预览，再 `dryRun=false`

### 10.4 建群能力误判

- `add_join_way` 生成的是官方入群配置，不是自动创建一个真实聊天群本身的全部运营流程
- 仍要结合 PC 后台、群主、群欢迎语、承接页一起用

---

## 11. 最后给接手开发的最短阅读顺序

如果另一个项目开发只想用 10 分钟先搞明白，建议按这个顺序读：

1. `docs/wecom-archive-robot-group-reference.md`
2. `backend/.env.example`
3. `backend/app/core/config.py`
4. `backend/app/api/routes_wecom.py`
5. `backend/app/api/routes_robot.py`
6. `backend/app/api/routes_ops_admin.py`
7. `docs/stage2-docs/10-wecom-archive-config.md`
8. `docs/stage2-docs/32-enterprise-group-bot-message-templates-v1.md`
9. `docs/stage2-docs/30-group-qr-server-upload-handoff.md`

---

## 12. 一句话总结

这套能力里，最值得复用的不是某一页业务 UI，而是这条底座：

```text
企业微信回调 -> 会话归档 -> 机器人入口 -> 群机器人广播 -> 建群/入群配置 -> 小程序/H5承接
```

新项目如果要迁，优先迁“接线方式和配置分层”，不要整包迁旧业务字段。
