# 腾讯云 Docker Compose 真实联调清单

适用场景：企业微信客服认证已通过，准备在腾讯云服务器用 Docker Compose 跑真实 `sync_msg`、回调、媒体转存和 PostgreSQL 持久化队列。

## 0. teamBuy 生产默认发布策略（2026-08-28）

当前 teamBuy 生产容器不挂载宿主机源码，后端代码变更必须让新代码进入运行镜像。由于生产构建曾在基础镜像的 `apt-get update` 阶段长时间无响应，后端发布的默认路径改为：

1. 先检查 `df -h /`、`docker system df`、容器状态和当前宿主机端口；确认旧容器健康后再动手。
2. 备份 Compose 文件和本次明确要覆盖的源码到 `/home/ubuntu/teambuy-backups/<timestamp>/`；严禁覆盖 `backend/.env`、`backend/secrets/`、媒体目录和数据库卷。
3. 给当前 API、`backend-worker`、`archive-worker` 镜像分别打 `rollback-<timestamp>` 标签。
4. 仅在“没有新增 Python/系统依赖”的前提下，用当前镜像创建临时容器，逐个 `docker cp` 明确的源码文件到 `/app/app/...`，再 `docker commit` 生成范围明确的热修复镜像。上传多个文件时必须使用各自的远端绝对路径，并用 `sha256sum` 核对本地、宿主机和容器内文件。
5. 使用原生产端口显式重建运行服务，并依次检查容器、数据库、本机 `8004` 和公网 `/health`；业务接口还要检查新 schema、路由和 service 签名已进入容器。

本默认路径禁止先执行 `docker compose build`。完整构建只有在已确认 Debian/PyPI 网络可用、确实需要新依赖，并由执行人显式设置 `ALLOW_NETWORK_BUILD=1` 后才允许执行；如果 `apt-get update` 无进展，应停止本次明确的构建进程、保留旧容器和回滚标签，不得反复等待、重启或执行全局 Docker 清理。

热修复切换必须使用与线上 Compose 相同的服务镜像名，不能只给新镜像起一个未被 Compose 使用的标签。切换后如果公网出现 502，先核对 `docker compose port backend 8000`、`ss -ltnp` 与 Nginx 上游是否仍为 `8004`，不要先修改业务代码。

## 1. 构建加速

`docker-compose.yml` 已默认把后端构建参数设为清华 PyPI 源：

```text
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

只有满足上一节的完整构建例外条件时，服务器构建才显式指定：

```bash
ALLOW_NETWORK_BUILD=1 PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple docker compose build backend
```

注意：`backend/.dockerignore` 已排除 `.env`、缓存和本地媒体文件，避免真实密钥被打进镜像层。

## 2. 服务器 `.env` 要点

真实联调时在服务器的 `backend/.env` 保留真实配置，但不要提交到 Git。

关键项建议如下：

```text
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
PUBLIC_BASE_URL=https://你的公网域名

DATABASE_BACKEND=postgres

WECOM_USE_MOCK=false
WECOM_API_BASE_URL=https://qyapi.weixin.qq.com
WECOM_CORP_ID=企业微信企业ID
WECOM_KF_CALLBACK_TOKEN=企业微信客服回调Token
WECOM_KF_SECRET=企业微信客服Secret
WECOM_KF_ENCODING_AES_KEY=企业微信客服EncodingAESKey
WECOM_OPEN_KFID=客服账号ID
WECOM_SYNC_CURSOR=
WECOM_SYNC_LIMIT=100
WECOM_SYNC_LOCK_TIMEOUT_SECONDS=600
WECOM_ADMIN_TOKEN=足够长的管理员操作令牌

STORAGE_MODE=local
MEDIA_STORAGE_DIR=/app/mock/media
MEDIA_PUBLIC_URL_PREFIX=/media

PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

`WECOM_SYNC_CURSOR` 首次真实联调可以留空；成功拉取后系统会把新 cursor 写入 PostgreSQL 的 `sync_cursors`。

## 3. 启动顺序

在服务器项目根目录执行。正常业务代码发布不要直接套用完整构建命令；先按第 0 节完成备份、回滚标签和镜像热修复。切换服务时必须显式保留当前 Nginx 使用的 `APP_PORT=8004`：

```bash
sudo env APP_PORT=8004 docker compose up -d --no-build backend backend-worker archive-worker
docker compose ps
docker compose logs --tail=100 backend
```

Compose 中的 PostgreSQL 默认只暴露在 Docker 内部网络，后端通过 `postgres:5432` 访问；不映射宿主机 `5432`，避免和服务器已有 PostgreSQL 冲突。

不要把 `docker compose config` 的输出发到公开渠道，因为它会展开 `backend/.env` 中的真实密钥。

## 4. 健康检查

```bash
curl http://127.0.0.1:8004/health
curl http://127.0.0.1:8004/health/db
curl http://127.0.0.1:8004/api/wecom/config-check
```

预期：

```text
/health 返回 status=ok
/health/db 返回 connected=true
/api/wecom/config-check 返回 success=true 且 missing=[]
```

## 5. 企业微信后台配置

在企业微信客服后台把回调 URL 配成：

```text
https://你的公网域名/api/wecom/kf/teamBuy/callback
```

Token 和 EncodingAESKey 必须与服务器 `backend/.env` 完全一致。

## 6. 首次真实联调

建议按这个顺序做：

1. 先在企业微信后台保存并验证 callback URL。
2. 从客服会话发送一条纯文本消息给客服账号。
3. 查看回调是否快速入队：

```bash
curl http://127.0.0.1:8004/api/wecom/sync-tasks
curl http://127.0.0.1:8004/api/wecom/sync-tasks/logs
```

4. 查看导入结果：

```bash
curl http://127.0.0.1:8004/api/imports/pending
curl http://127.0.0.1:8004/api/wecom/notifications
```

5. 再分别发送链接、图片、视频、位置、微信笔记内容，观察 normalizer、媒体转存和补偿队列：

```bash
curl http://127.0.0.1:8004/api/wecom/media-retries
```

## 7. 手动触发兜底

如果企业微信回调已配置但没有自动触发，可以先手动拉取验证 `sync_msg` 主链路：

```bash
curl -X POST "http://127.0.0.1:8004/api/wecom/real-sync?max_pages=10"
```

如果同步锁卡住，管理员可释放：

```bash
curl -X POST "http://127.0.0.1:8004/api/wecom/real-sync/unlock?reason=manual-recovery" \
  -H "X-Admin-Token: 你的WECOM_ADMIN_TOKEN"
```

## 8. 本轮真实联调结论记录

真实联调完成后建议补一份记录到：

```text
docs/qa/企业微信真实联调记录.md
```

至少记录：

- 企业微信 callback URL 是否验证通过
- `sync_msg` 是否成功返回真实消息
- cursor 是否写入 `sync_cursors`
- 文本/链接/图片/视频/位置/微信笔记是否能生成导入批次或补偿任务
- 媒体是否成功转存
- 失败通知和补偿队列是否可观察
