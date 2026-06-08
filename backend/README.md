# teamBuy Backend

本目录提供 teamBuy 阶段三本地开发用的 FastAPI MVP。

## 能力范围

- 企业微信回调 GET 校验和本地 mock POST 导入
- 企业微信回调签名校验、加密 `echostr` 解密和 XML 消息解析入口
- 真实 `sync_msg` 客户端骨架
- mock `sync_msg` 拉取、60 秒消息聚合、媒体转存占位
- 卡片草稿生成、认领、编辑、发布、一键复用
- 浏览统计、匿名浏览隔离、实名接龙和团长管理
- PostgreSQL 过渡仓储，数据库暂不可用时回退 JSON 文件便于本地联调
- mock 导入通知记录，后续可替换为真实微信客服消息回发

## 本地运行

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认接口地址：`http://127.0.0.1:8000`

企业微信客服真实配置请填写 `backend/.env`，配置项说明见 `docs/qa/企业微信客服配置清单.md`。

数据库使用 PostgreSQL。请在 `backend/.env` 填写：

```text
DATABASE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg://teambuy:your_password@127.0.0.1:5432/teambuy
```

检查配置：

```bash
curl http://127.0.0.1:8000/api/wecom/config-check
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
```

当前 PostgreSQL 仓储采用“一实体一表 + 核心字段列 + JSONB payload”的过渡结构，表结构见 `app/core/schema.sql`。热点字段已拆列并加索引：导入批次、原始消息、卡片、浏览记录、接龙记录。仓储层也提供了按 owner/status/card/batch 查询的读取方法，后续业务层可以逐步迁过去。如果 `DATABASE_URL` 暂时不可用，后端会回退到本地 JSON mock 仓储，方便企业微信认证前继续开发。

真实 `sync_msg` 重试和重复 cursor 场景通过 `raw_messages.wecom_msg_id` 做幂等去重。`wecom_msg_id` 在 PostgreSQL 中有唯一约束；导入前也会先过滤已存在的企业微信消息，避免重复生成卡片草稿。

真实 `sync_msg` 返回数据先进入 `app/services/wecom_message_normalizer.py` 标准化层，统一映射为内部消息结构，再进入聚合、解析、事务写入主链路。后续拿到企业微信真实样例时，优先修 normalizer，不要直接改业务主链路。
`POST /api/wecom/real-sync` 已接入完整主链路：`WECOM_USE_MOCK=true` 时读取 `backend/mock/mock-real-sync-response.json`，认证通过并切到 `WECOM_USE_MOCK=false` 后只把数据源替换为真实 `sync_msg` 客户端，后续仍复用同一套 normalizer、幂等过滤和事务写入逻辑。
`POST /api/wecom/callback` keeps mock fixture import while `WECOM_USE_MOCK=true`; when `WECOM_USE_MOCK=false`, a callback queues a background real-sync task and returns quickly. The background task uses the same cursor, lock, media transfer, and compensation pipeline as manual real-sync.
Callback-triggered real-sync tasks are persisted in PostgreSQL tables `sync_tasks` and `sync_task_logs`. API startup recovers queued, retrying, and stale running tasks, and PostgreSQL conditional updates prevent multiple Docker containers from claiming the same task.
`WECOM_SYNC_CURSOR` is only a first-run fallback. After the first real pull, the latest cursor is persisted in `sync_cursors`; normally leave the env value empty.
`sync_cursor` 会在每页成功导入后持久化 `next_cursor`、`has_more`、来源和最近 payload；真实模式会按 `has_more` 循环拉取分页，服务重启或重试时从仓储里的最新 cursor 继续。
`real-sync` also uses a persisted per-`open_kfid` task lock. A second manual trigger while `syncStatus=running` returns a running status instead of starting another cursor-advancing sync.
Stale locks are recoverable: `WECOM_SYNC_LOCK_TIMEOUT_SECONDS` defaults to 600 seconds, and `POST /api/wecom/real-sync/unlock` can force-release a stuck lock for manual recovery.
The unlock endpoint is protected by `WECOM_ADMIN_TOKEN`; pass it through `X-Admin-Token` or the `adminToken` query parameter.
For real image/video messages, `real-sync` downloads WeCom `media_id` assets before import and stores them through `MediaStorageService`. Local development can use `STORAGE_MODE=local`, `MEDIA_STORAGE_DIR=backend/mock/media`, and `MEDIA_PUBLIC_URL_PREFIX=/media`; future COS support can replace only the storage adapter.
`MediaStorageService` now supports `mock`, `local`, `cos`, and `s3` modes. COS/S3 use the S3-compatible `put_object` adapter with `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_BUCKET`, credentials, and `OBJECT_STORAGE_PUBLIC_BASE_URL`.
If media download or upload fails during real sync, the API records a `media_retry_jobs` compensation task. Admins can inspect `GET /api/wecom/media-retries` and retry with `POST /api/wecom/media-retries/retry`; successful retries are reused by the next `real-sync`.

查看 mock 导入通知：

```bash
curl http://127.0.0.1:8000/api/wecom/notifications
```

真实拉取消息前，需要把 `WECOM_USE_MOCK=false`。

## 测试

```bash
cd backend
pytest
```

## Docker Compose

From the project root:

```bash
docker compose up -d --build
docker compose logs -f backend
```

The compose stack starts `postgres` and `backend`. Keep real secrets in `backend/.env`; Compose overrides `DATABASE_URL` so the backend container connects to the `postgres` service instead of `127.0.0.1`.

## 关键文件

- `app/main.py`：FastAPI 入口
- `app/services/message_aggregator.py`：60 秒聚合规则
- `app/services/card_parser_service.py`：卡片草稿解析
- `app/services/app_service.py`：认领、卡片、统计、接龙主逻辑
- `mock/`：本地联调用 mock 数据和运行态 JSON
