# 阶段三 MVP Codex 自测报告

## 1. 本轮实现范围

- FastAPI 后端骨架与 JSON 本地持久化
- 企业微信本地 mock 导入、60 秒聚合、媒体转存占位、卡片草稿生成
- 企业微信客服配置清单、`.env` 本地读取、回调签名校验/解密入口、真实 `sync_msg` 客户端骨架
- PostgreSQL 过渡仓储、核心字段拆列、热点索引、连接健康检查、本地 JSON 兜底
- `AppService` 热路径迁移到按模块 CRUD：导入、卡片、浏览、接龙不再全量读写 `AppState`
- 企业微信导入产物写入事务化：`raw_messages + import_batch + card_draft + notification` 通过单个仓储事务提交
- `sync_msg` 幂等去重：`raw_messages` 保存 `wecomMsgId`、`wecomToken`、`openKfid`，并在导入前过滤重复企业微信消息
- `sync_msg` 标准化适配层：将真实 text/image/link/video/location 消息映射到内部统一消息结构
- `real-sync` 完整入口：mock 真实响应或真实 `sync_msg` 响应都会进入 normalizer -> 幂等过滤 -> 事务写入导入产物主链路
- `sync_cursor` 持久化与推进：每页成功导入后记录 `next_cursor`、`has_more`、来源和最近 payload，并支持真实 `sync_msg` 按页循环拉取
- `real-sync` 手动触发锁：同一 `open_kfid` 的同步任务运行中会返回 running 状态，避免重复触发并发推进 cursor
- mock 导入成功/失败通知抽象和通知查询接口
- 链接缩略图、来源 URL、视频 media mock 转存解析增强
- 导入认领、卡片编辑、发布、一键复用
- 浏览统计、匿名浏览隔离、实名接龙、团长删除/跟进
- 原生微信小程序本地联调骨架页面

## 2. 关键改动

- `backend/app/`：新增 API、领域模型、服务层、mock 聚合与测试
- `backend/mock/`：新增微信笔记、链接、卡片、浏览、接龙 mock 数据
- `backend/app/core/schema.sql`：PostgreSQL 过渡表结构、字段化列和热点索引
- `docs/qa/企业微信客服配置清单.md`：整理真实接入前需要用户提供的配置
- `miniprogram/`：新增登录、待认领、素材库、编辑、查看、管理页面及组件
- `backend/.env.example`、`backend/Dockerfile`、`backend/README.md`、`miniprogram/README.md`

## 3. 运行方式

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 小程序

1. 用微信开发者工具打开 `miniprogram/`
2. 确保后端运行在 `http://127.0.0.1:8000`
3. 如需真机联调，将 `miniprogram/app.js` 的 `apiBaseUrl` 改为局域网地址

## 4. 已执行验证

- `cd backend && pytest`，当前 30 项通过
- `cd backend && python -m compileall app`

## 5. 已通过测试项

- TC-001 企业微信回调 GET 验证
- TC-002 企业微信回调 POST 接收入口
- TC-003 `sync_msg` 客户端调用保护
- TC-004 微信笔记 60 秒聚合生成导入批次
- TC-007 媒体转存 mock URL，图片和视频后缀区分
- TC-009 卡片草稿生成
- TC-010 链接消息生成来源链接、标题候选、缩略图封面
- TC-013 导入成功通知 mock 记录
- TC-015 待认领导入列表
- TC-016 成功认领
- TC-020 卡片发布后可查看
- TC-023 登录用户浏览统计
- TC-024 匿名浏览统计隔离
- TC-027 手机号必填校验
- TC-036 一键复用生成新卡片
- TC-037 新旧卡片统计隔离
- 仓储迁移防回退测试：导入、卡片、浏览、接龙热路径不调用全量 `_load()` / `_save()`
- 导入事务测试：原始消息、导入批次、卡片草稿、导入通知一起写入
- 重复 `sync_msg` 测试：同一批企业微信消息重复触发不会生成第二张卡片
- 标准化适配测试：真实 text/image/link/video/location 形态可转换为内部消息结构

## 6. 已实现但未自动化覆盖完成的项

- TC-002 回调 POST 接收：已实现 JSON/mock 与 XML 加密消息解析入口，真实字段需账号实测
- TC-003 `sync_msg` 拉取：已实现真实客户端骨架，当前未用真实凭证执行
- TC-007/TC-008 媒体转存：当前为本地 mock URL，占位逻辑已通，未接真实下载
- TC-018 卡片编辑保存：已实现页面与接口，未补页面自动化
- TC-021 电话拨号：页面已接入，需小程序环境人工确认
- TC-022 字段复制：组件已接入，需小程序环境人工确认
- TC-026/TC-029/TC-030/TC-031/TC-032：后端逻辑已实现，建议后续补更多 API 用例和小程序人工回归
- TC-033/TC-034/TC-035：素材库列表与搜索已实现，分类接口和页面入口仍可继续增强

## 7. 未覆盖项与限制

- 未用真实企业微信账号完成回调、`sync_msg`、媒体下载端到端验收
- 未接入真实微信登录 code 换 openid
- 未接入对象存储；PostgreSQL 已有过渡仓储，但尚未做细粒度关系表查询优化
- 小程序页面尚未在微信开发者工具内完成人工截图式验收
- 当前 PostgreSQL 仓储使用 JSONB payload 过渡结构，适合继续开发，后续可按查询热点拆细字段和索引
- 误生成的空目录 `backend/backend/mock/` 仍在仓库中，但其中多余运行态文件已删除

## 8. 已知问题

- 回调验签和解密入口已实现，但真实 XML 字段映射还需企业微信账号实测后收敛
- 卡片分类只有查询过滤能力，暂无独立分类管理 API
- 小程序没有配置 tabBar，当前页面通过 `navigateTo`/`redirectTo` 串联
- 当前全局 Python 环境安装依赖时提示 `sse-starlette` 与 `starlette` 版本约束冲突，建议后续使用项目虚拟环境

## 9. 下一步建议

1. 接入真实企业微信回调与 `sync_msg`，优先完成 TC-002、TC-003、TC-007、TC-008、TC-013、TC-014
2. 把小程序在微信开发者工具里跑一遍，补拨号、复制、接龙、管理的人工验收记录
3. 将 PostgreSQL 过渡仓储进一步拆成细粒度 CRUD 查询，优先处理导入批次、卡片、浏览、接龙四组热点表
