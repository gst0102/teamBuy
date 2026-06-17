# 企业微信会话内容存档配置清单

更新时间：2026-06-17

## 当前状态

- 企业微信后台页面：`https://work.weixin.qq.com/wework_admin/frame#financial/corpEncryptData`
- 本轮已生成会话内容存档 RSA 密钥对：
  - 私钥：`backend/secrets/wecom_archive_private.pem`
  - 公钥：`backend/secrets/wecom_archive_public.pem`
- `*.pem` 已在 `.gitignore` 中排除，私钥和公钥文件不会提交 Git。
- 后端已新增配置检查接口：`GET /api/wecom/archive/config-check`。
- 后端已新增会话存档事件服务器接口：`/api/wecom/archive/callback`。
- 原始会话存档消息只能通过 admin token 查询或写入样例。

## 企业微信后台需要配置

在“会话内容存档”配置页中填写/确认：

- 开启会话内容存档能力。
- 保存页面展示的会话内容存档 `Secret`，写入后端环境变量 `WECOM_ARCHIVE_SECRET`。
- 公钥填写下方 `RSA Public Key`。
- 如果后台要求配置可信 IP，把生产后端出口 IP 加入可信 IP。当前生产服务器 IP 按历史记录为 `81.70.84.35`。
- 保存前确认这是“会话内容存档”页面，不是“微信客服 API 接收消息”页面。

## RSA Public Key

```text
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqmGanX/GYvXZcc5Mj5gA
3IE2vZ7Hc2fXegrlB57SGCd+qyTyv7tRJZBKug1qL6Nx38cXZxy0FM9qDKigYa/o
LfOWzzcgrhShEzLr8Uny3QXnFeRhekdaK3sDxaRioMwLIuO07ioAQD6L5ShIlewv
BNft0xX5L7bCdChrhcDSMnzPW+KZZ7B1fpnWnLWlcY9itiS+ChlZm/LZsGw4h3OC
mzXUgVoxiM3NP/ReOg9HCAzBAD62FOalQtKIqpmgFXpP2JnjYmgJd7gPngwimJbM
sqhojPYznIsfZbRYYAxArRQXeobJ50mqk6PoLru6rvJEXslAZhBk9uKBlLm+OCLy
5wIDAQAB
-----END PUBLIC KEY-----
```

## 后端环境变量

```text
WECOM_ARCHIVE_ENABLED=true
WECOM_ARCHIVE_SECRET=企业微信后台会话内容存档Secret
# 可先留空，系统会复用 WECOM_CALLBACK_TOKEN / WECOM_ENCODING_AES_KEY。
WECOM_ARCHIVE_CALLBACK_TOKEN=
WECOM_ARCHIVE_ENCODING_AES_KEY=
WECOM_ARCHIVE_PRIVATE_KEY_PATH=backend/secrets/wecom_archive_private.pem
WECOM_ARCHIVE_PUBLIC_KEY_PATH=backend/secrets/wecom_archive_public.pem
WECOM_ARCHIVE_SDK_LIB_PATH=
WECOM_ARCHIVE_PULL_LIMIT=100
WECOM_ARCHIVE_SDK_TIMEOUT_SECONDS=30
WECOM_ARCHIVE_PROXY=
WECOM_ARCHIVE_PROXY_PASSWORD=
```

注意：

- `WECOM_ARCHIVE_SECRET` 不能提交 Git。
- `WECOM_ARCHIVE_SECRET` 不等于微信客服 `WECOM_SECRET`。
- 私钥不能粘贴到企业微信后台，也不能写入文档正文。
- 会话存档事件服务器当前可以先复用微信客服回调的 `WECOM_CALLBACK_TOKEN` 和 `WECOM_ENCODING_AES_KEY`；如后续拆独立密钥，再填写 `WECOM_ARCHIVE_CALLBACK_TOKEN` 和 `WECOM_ARCHIVE_ENCODING_AES_KEY`。
- 接官方 SDK 时必须填写 `WECOM_ARCHIVE_SDK_LIB_PATH`。生产 Docker 环境要填容器内绝对路径，例如 `/app/secrets/libWeWorkFinanceSdk_C.so`。

## 事件服务器配置

当前后台“设置接收事件服务器”填写：

```text
URL=https://teambuy.lifelove.top/api/wecom/archive/callback
Token=backend/.env 里的 WECOM_CALLBACK_TOKEN
EncodingAESKey=backend/.env 里的 WECOM_ENCODING_AES_KEY
```

保存前确认生产环境已经部署包含 `/api/wecom/archive/callback` 的代码。

## 后端接口

- `GET /api/wecom/archive/config-check`
  - 检查会话内容存档配置项、私钥/公钥文件是否可读。
  - 返回公钥，便于复制到企业微信后台。
  - `success=true` 表示基础配置、公钥和私钥可读。
  - `sdkConfigured=true` 才表示真实拉取 SDK 已具备。

- `GET /api/wecom/archive/callback`
  - 企业微信后台事件服务器 URL 验证。
  - 成功时以 `text/plain` 原样返回 `echostr`。

- `POST /api/wecom/archive/callback`
  - 接收会话存档相关事件。
  - 当前先记录接收结果，后续接 SDK 拉取任务。

- `POST /api/wecom/archive/pull`
  - 需要 admin token。
  - 调用官方会话存档 SDK 拉取并解密消息。
  - 成功后写入 `wecom_archive_messages` 并推进 `wecom_archive_cursors.seq`。
  - SDK 缺失或拉取失败时返回 502，并记录 failed 游标。

- `POST /api/wecom/archive/process`
  - 需要 admin token。
  - 将已解密且未处理的归档消息转换为 `ContentObject -> content-to-note -> UserNote`。
  - 成功后在原始归档消息上记录 `generatedNoteId`、`generatedCardId` 和 `processedAt`。
  - 重复调用不会重复生成笔记。

- `GET /api/wecom/archive/cursor`
  - 需要 admin token。
  - 查看当前会话存档拉取 seq 游标。

- `GET /api/wecom/archive/messages`
  - 需要 admin token。
  - 查看已保存的原始会话存档消息。

- `POST /api/wecom/archive/mock-messages`
  - 需要 admin token。
  - 骨架阶段用于保存样例消息并推进游标。
  - 后续真实 SDK 拉取成功后，应改由后台拉取任务写入同一套仓储。

## P0 下一步

1. 企业微信后台事件服务器已保存成功后，继续确认公钥和可信 IP。
2. 将官方会话存档 Linux SDK 动态库放入生产容器可读路径。
3. 设置生产 `WECOM_ARCHIVE_SDK_LIB_PATH` 为容器内绝对路径。
4. 重启 backend，调用生产 `/api/wecom/archive/config-check`，确认 `missing=[]`、`sdkConfigured=true`。
5. 让企业微信真实产生一条测试会话消息。
6. 调用生产 `POST /api/wecom/archive/pull`：
   - 如果 `savedCount>0`，说明真实归档消息已入库。
   - 如果返回 502，优先看 `detail.error` 和 cursor 的 failed 原因。
7. 调用生产 `POST /api/wecom/archive/process`，确认生成 `UserNote`。
8. 在小程序“我的笔记”查看、编辑、删除这条笔记。
