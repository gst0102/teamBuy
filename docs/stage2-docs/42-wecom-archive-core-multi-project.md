# WeCom 会话存档共享平台与多项目路由

## 结论

企业微信会话内容存档采用“一个归档入口、一个 Finance SDK Worker、多个项目消费者”的最终架构。

项目可以共享同一个企业微信和同一套 Archive Secret/RSA 私钥，但产品项目不能各自调用 Finance SDK，也不能各自推进企业级 `seq`。

平台代码位于：

```text
platform/wecom-archive-core/
```

## 平台职责

共享核心唯一负责：

1. 企业微信归档回调验签和 AES 解密；
2. Finance SDK 拉取、RSA 解密和全局游标；
3. 归档事件幂等保存；
4. 按项目、真实群 `chat_id` 和消息类型路由；
5. 投递重试、项目幂等键和失败记录；
6. 通过受保护媒体代理提供 `sdkfileid` 对应的媒体。

共享核心不负责：

- Petlove 的群内容候选和日报；
- teamBuy 的资料导入、客户归属和通知；
- 任何项目的用户身份绑定或业务发布。

## 项目接入规则

项目通过 `WECOM_ARCHIVE_CORE_PROJECTS_JSON` 注册：

```json
[
  {
    "projectId": "teamBuy",
    "endpointUrl": "http://host.docker.internal:8004/api/wecom/archive/core-events",
    "token": "runtime-secret",
    "chatIds": ["wr_customer_group_id"],
    "includeDirectMessages": true,
    "toUserIds": ["teamBuy_sales_userid"],
    "messageTypes": ["text", "image"]
  },
  {
    "projectId": "petlove",
    "endpointUrl": "http://host.docker.internal:8002/api/wecom/archive/core-events",
    "token": "runtime-secret",
    "chatIds": ["wr_pet_group_id"],
    "messageTypes": ["text", "image"]
  }
]
```

空 `chatIds` 默认不匹配任何群，只有显式 `allowAllChats: true` 才匹配全部群，防止新项目注册时意外接收全企业消息。
一对一消息没有 `roomId`，必须显式设置 `includeDirectMessages: true`；如同一企业还有多个项目处理私聊，必须继续配置项目对应的 `fromUserIds` 或 `toUserIds`，不能让多个项目同时无条件接收全部私聊。

如果新项目是在平台已经开始拉取之后才加入，新增路由不会自动回放历史事件。先重启核心使路由生效，再由管理员调用：

```text
POST /v1/admin/replay/{projectId}?afterSeq=0&limit=1000
X-Archive-Admin-Token: <core admin token>
```

该操作只为匹配当前路由的已保存事件创建投递记录，不会重新调用 Finance SDK，也不会修改全局游标。

项目消费者必须：

- 使用独立项目 token；
- 先持久化再返回 2xx；
- 使用 `eventId` 或消息 ID 幂等；
- 不保存或记录 Finance SDK 原始密文；
- 媒体只通过核心媒体代理读取；
- 维护自己的业务处理状态，不推进平台游标。

## 迁移顺序

1. 部署独立 `archive-core-postgres`、`archive-core` 和单个 `archive-core-worker`。
2. 在核心项目路由中填入真实 `chat_id` 和项目 token。
3. 将 Petlove、teamBuy 的 `WECOM_ARCHIVE_SOURCE` 改为 `shared`。
4. 将两个项目的本地 Archive Worker 改为只处理已接收的本地待处理消息，不再调用 Finance SDK。
5. 将企业微信后台唯一事件服务器地址改为：

   ```text
   https://api.lifelove.top/wecom/archive/callback
   ```

6. 验证核心游标只在核心数据库推进，两个项目都能收到各自路由消息。
7. 确认无重复业务记录后，再关闭 Petlove staging 的真实归档能力和旧项目回调入口。

## 原始归档留存

共享核心不是项目业务数据库，只保存加密后的短期中转 payload。默认配置为
`WECOM_ARCHIVE_CORE_RAW_RETENTION_HOURS=24`：从核心入库时间起超过 24 小时，且所有项目投递记录均为 `delivered` 后，由核心 worker 分批删除消息及其投递记录。

仍处于 `pending` 或其他非 `delivered` 状态的事件不会被清理。项目必须在返回 2xx 前完成自己的业务持久化；清理后历史消息和核心媒体代理不再可回放，项目自己的业务库不受影响。

项目的 `WECOM_ARCHIVE_CORE_MEDIA_BASE_URL` 应指向能访问核心媒体代理的共享 HTTPS 域名；不要在跨容器部署中填写项目容器自己的 `127.0.0.1:8050`。

## 回滚

回滚时先停止共享核心 Worker，再将目标项目切回 `WECOM_ARCHIVE_SOURCE=direct`，恢复对应项目的 Finance SDK 配置和游标。不能在共享 Worker 与项目直拉 Worker 同时开启的情况下回滚。
