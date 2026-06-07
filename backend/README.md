# teamBuy Backend

本目录提供 teamBuy 阶段三本地开发用的 FastAPI MVP。

## 能力范围

- 企业微信回调 GET 校验和本地 mock POST 导入
- 企业微信回调签名校验、加密 `echostr` 解密和 XML 消息解析入口
- 真实 `sync_msg` 客户端骨架
- mock `sync_msg` 拉取、60 秒消息聚合、媒体转存占位
- 卡片草稿生成、认领、编辑、发布、一键复用
- 浏览统计、匿名浏览隔离、实名接龙和团长管理
- JSON 文件持久化，便于本地联调

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

真实拉取消息前，需要把 `WECOM_USE_MOCK=false`。

## 测试

```bash
cd backend
pytest
```

## 关键文件

- `app/main.py`：FastAPI 入口
- `app/services/message_aggregator.py`：60 秒聚合规则
- `app/services/card_parser_service.py`：卡片草稿解析
- `app/services/app_service.py`：认领、卡片、统计、接龙主逻辑
- `mock/`：本地联调用 mock 数据和运行态 JSON
