# 生产热修与二期后端合并计划

日期：2026-07-02

## 背景

当前生产环境已经上线了一组房源和 OCR 相关热修：

- 后端拆成 `backend` API、`backend-worker` OCR worker、`archive-worker` 会话归档 worker。
- 图片上传后先返回 OCR `queued`，后台 worker 异步识别。
- `property-table-ocr` 专项链路已部署，用于 007 这类表格房源图片。
- 生产 Postgres 连接要求 `DATABASE_REQUIRE_POSTGRES=true`，避免 API 和 worker 数据源分裂。
- Postgres schema 初始化使用 advisory lock，避免多进程启动 DDL deadlock。
- 房源公开联系方式和上游私密备注规则已经进入生产。

同时，本地二期后端代码包含商机、供需、资源钱包等大范围改动。二期代码不能直接覆盖生产，否则可能丢失已上线热修。

## 已归档的生产基线

生产关键文件已拉取到：

```text
artifacts/prod-baseline-20260702-ocr-property/
```

归档来源：

```text
ubuntu@81.70.84.35:/home/ubuntu/teamBuy
```

归档文件：

- `docker-compose.yml`
- `backend/app/api/dependencies.py`
- `backend/app/worker.py`
- `backend/app/services/app_service.py`
- `backend/app/services/repository.py`
- `backend/app/services/sync_task_queue.py`
- `backend/app/services/background_task_worker.py`
- `backend/app/services/property_table_ocr_service.py`
- `backend/app/services/property_table_ocr_worker.py`

## 当前合并判断

本地和生产一致的重点文件：

- `docker-compose.yml`
- `backend/app/api/dependencies.py`
- `backend/app/worker.py`
- `backend/app/services/sync_task_queue.py`
- `backend/app/services/background_task_worker.py`
- `backend/app/services/property_table_ocr_service.py`
- `backend/app/services/property_table_ocr_worker.py`

必须人工合并的高风险文件：

- `backend/app/services/app_service.py`
- `backend/app/services/repository.py`

原因：本地这两个文件已经包含二期商机、供需、资源钱包等代码；生产版本包含已经验证的 OCR/房源热修。二期上线前必须确认两边能力同时存在。

## 二期上线前统一分支流程

建议使用一个统一集成分支，例如：

```bash
git switch -c codex/integration-phase2-with-prod-hotfix
```

如果当前工作树未提交，先不要切分支。应先把当前工作按功能拆成 commit，至少拆成：

- `prod-hotfix-ocr-property-baseline`
- `phase2-opportunity-resource-wallet`
- `phase2-miniprogram-pages`
- `docs-and-qa`

统一分支必须满足：

1. 从当前生产热修基线合入 OCR/房源能力。
2. 再合入二期后端能力。
3. 对 `app_service.py` 和 `repository.py` 做人工合并，不使用整文件覆盖。
4. 合并后跑完整回归。
5. 只从统一分支部署测试环境。
6. 测试环境通过后，再从同一个统一分支部署生产。

## 必须保留的生产能力清单

二期上线前逐项检查：

- `docker-compose.yml` 包含 `backend`、`backend-worker`、`archive-worker`。
- 生产环境保持 `DATABASE_REQUIRE_POSTGRES=true`。
- `backend/app/worker.py` 存在，且 worker 入口正常。
- `BackgroundTaskWorker` 支持按任务名拉取。
- `SyncTaskQueue` 支持 `auto_schedule=false`、`task_names`、`max_running`。
- `dependencies.py` 注册 `ocr-recognize-note` 和 `property-table-ocr`。
- `PropertyTableOcrService` 存在。
- `property_table_ocr_worker.py` 存在。
- `AppService.recognize_ocr_note_image()` 对表格图先走表格 OCR。
- `AppService.recognize_property_table_ocr_note_image()` 存在。
- `AppService._parse_property_table_ocr_text()` 能解析 `1, 600. 00` 这类价格。
- `Repository.init_schema()` 保留 Postgres advisory lock。
- 生产 Postgres 连接失败时不静默 fallback 到 JSON。
- 房源原文电话进入 `privateData.upstreamPhones`，不进入公开联系电话。
- 用户资料手机号/微信可自动补到房源公开联系方式。

## 回归测试顺序

合并后的统一分支至少跑：

```bash
.venv312/bin/python -m compileall -q backend/app backend/tests
.venv312/bin/python -m pytest backend/tests/test_app.py backend/tests/test_sync_task_queue.py -q -k "ocr or image_capture or property_batch or archive_worker or sync_task"
.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q
git diff --check
```

部署测试环境后验证：

- `/test-api/health` 正常。
- 图片上传接口立即返回 OCR `queued`。
- worker 能把 OCR task 消费到 `success` 或可解释状态。
- 007 表格图片能进入 `property-table-ocr` 链路。
- 文字批量房源仍能拆多套。
- 单条租房笔记仍能高置信生成房源。
- 房源公开 payload 不包含上游电话。

生产部署前验证：

- 先备份服务器 `backend` 和 `docker-compose.yml`。
- 不覆盖 `backend/.env`、`backend/secrets/`、媒体目录、数据库卷。
- 先部署测试环境，同一 commit 通过后再部署生产。
- 生产部署后检查 `docker compose ps`，必须看到 API、OCR worker、archive worker 都 Up。
- 公网 `https://teambuy.lifelove.top/health` 返回 200。

## 禁止动作

- 禁止从二期分支直接整文件覆盖生产 `app_service.py` 和 `repository.py`。
- 禁止只部署 API，不部署 worker。
- 禁止让生产 Postgres 失败后 fallback 到 JSON。
- 禁止覆盖生产 `.env`、`secrets`、媒体目录和运行态数据。
- 禁止跳过 007 表格 OCR、普通 OCR、会话归档 worker 的回归。

