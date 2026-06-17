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
```

注意：

- `WECOM_ARCHIVE_SECRET` 不能提交 Git。
- `WECOM_ARCHIVE_SECRET` 不等于微信客服 `WECOM_SECRET`。
- 私钥不能粘贴到企业微信后台，也不能写入文档正文。
- 会话存档事件服务器当前可以先复用微信客服回调的 `WECOM_CALLBACK_TOKEN` 和 `WECOM_ENCODING_AES_KEY`；如后续拆独立密钥，再填写 `WECOM_ARCHIVE_CALLBACK_TOKEN` 和 `WECOM_ARCHIVE_ENCODING_AES_KEY`。
- 后续接官方 SDK 时再填写 `WECOM_ARCHIVE_SDK_LIB_PATH`。

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

- `GET /api/wecom/archive/callback`
  - 企业微信后台事件服务器 URL 验证。
  - 成功时以 `text/plain` 原样返回 `echostr`。

- `POST /api/wecom/archive/callback`
  - 接收会话存档相关事件。
  - 当前先记录接收结果，后续接 SDK 拉取任务。

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

1. 在企业微信后台保存事件服务器、公钥和可信 IP。
2. 把后台生成的会话内容存档 Secret 写入生产 `backend/.env`。
3. 调用生产 `/api/wecom/archive/config-check`，确认 `missing=[]` 且 `callbackUrl` 正确。
4. 接入官方会话存档 SDK：
   - 拉取加密消息。
   - 使用本地私钥解密会话密钥。
   - 解密消息体并写入 `wecom_archive_messages`。
   - 推进 `wecom_archive_cursors.seq`。
5. 将解密后的文字、链接、媒体引用转为 `ContentObject`，再进入 `content-to-note`。
