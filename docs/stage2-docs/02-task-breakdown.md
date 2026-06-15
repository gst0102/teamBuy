# 任务拆解

## 1. 任务总览

阶段三应按里程碑实现，不要一次性堆完整项目。

推荐顺序：

1. 初始化项目结构
2. 建立数据模型和 mock 数据
3. 实现后端核心服务骨架
4. 实现小程序核心页面
5. 接入导入聚合和卡片生成
6. 实现浏览统计和接龙
7. 完成素材库搜索、分类、一键复用
8. 自测、修复和验收

## 2. 推荐目录结构

```text
teamBuy/
├─ AGENTS.md
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  └─ main.py
│  ├─ tests/
│  ├─ requirements.txt
│  └─ README.md
├─ miniprogram/
│  ├─ app.js
│  ├─ app.json
│  ├─ app.wxss
│  ├─ pages/
│  ├─ components/
│  ├─ services/
│  ├─ utils/
│  └─ README.md
├─ docs/
│  ├─ stage2-docs/
│  └─ qa/
├─ skills/
└─ stage1-thinking/
```

v0.1 不创建 PC Web 管理端目录。若后续确认需要企业微信客服侧边栏或工具栏 H5，可在 P2 新增：

```text
web-tool/
```

## 3. 功能模块拆解

| 模块 | 任务 | 优先级 | 产出 |
|---|---|---|---|
| 项目初始化 | 创建原生小程序和 FastAPI 基础结构 | P0 | 可启动的前后端骨架 |
| 配置管理 | 定义环境变量、密钥读取、配置校验 | P0 | 后端配置模块和 `.env.example` |
| 企业微信回调 | 实现回调 URL、Token 验证、事件入口 | P0 | 回调 API |
| 消息拉取 | 封装 `sync_msg` 调用 | P0 | 企业微信消息服务 |
| 消息聚合 | 按用户、会话、60 秒窗口聚合消息 | P0 | 导入批次生成逻辑 |
| 媒体转存 | 下载 media_id 并转存 | P0 | 存储服务抽象 |
| 规则解析 | 从文本、图片、链接、位置、视频生成卡片草稿 | P0 | 解析服务 |
| 大模型兜底 | 对低质量草稿做文本清洗和字段补全 | P1 | LLM 服务抽象 |
| 认领流程 | 待认领导入记录和用户归属 | P0 | 认领 API 和页面 |
| 卡片编辑 | 编辑和保存通用字段 | P0 | 卡片 API 和编辑页 |
| 卡片查看 | 分享页展示、电话拨号、字段复制 | P0 | 查看页 |
| 浏览统计 | 登录用户和匿名用户浏览记录 | P0 | 统计 API 和管理展示 |
| 接龙 | 登录接龙、手机号/地址可选字段 | P0 | 接龙 API 和页面 |
| 团长管理 | 名单查看、删除无效、标记跟进 | P0 | 管理页 |
| 素材库 | 列表、搜索、分类、一键复用 | P1 | 素材库页 |
| 客服侧边栏/H5 发卡片 | 企业微信客服侧边栏中搜索并发送小程序卡片 | P2 | 技术预研和独立 H5 工具页 |

## 4. 小程序组件拆解

| 组件 | 用途 | 优先级 |
|---|---|---|
| `card-preview` | 卡片列表和查看页复用的卡片摘要 | P0 |
| `media-gallery` | 图片和视频展示 | P0 |
| `field-copy-row` | 可复制字段展示 | P0 |
| `phone-action` | 电话直拨按钮 | P0 |
| `view-stats-panel` | 浏览人数、次数、用户列表 | P1 |
| `relay-form` | 接龙表单 | P0 |
| `relay-list` | 接龙名单和跟进状态 | P0 |
| `category-filter` | 素材分类筛选 | P1 |

## 5. 后端服务拆解

| 服务 | 职责 | 真实接入 / mock |
|---|---|---|
| `wecom_callback_service` | 接收企业微信事件 | 真实接入优先，开发可 mock XML/JSON |
| `wecom_message_service` | 调用 `sync_msg` 拉消息 | 真实接入优先，开发可 mock 消息列表 |
| `message_aggregator` | 生成导入批次 | 真实逻辑 |
| `media_storage_service` | 下载并转存媒体 | 接口真实，开发可 mock 本地 URL |
| `card_parser_service` | 规则解析生成草稿 | 真实逻辑 |
| `llm_parser_service` | 大模型兜底 | P1，可 mock 返回结构化结果 |
| `claim_service` | 待认领导入归属 | 真实逻辑 |
| `card_service` | 卡片增删改查和复用 | 真实逻辑 |
| `view_tracking_service` | PV/UV 和浏览用户 | 真实逻辑 |
| `relay_service` | 接龙和名单管理 | 真实逻辑 |

## 6. API 拆解

| API | 方法 | 用途 | 优先级 |
|---|---|---|---|
| `/api/wecom/kf/teamBuy/callback` | GET/POST | 企业微信回调验证和事件接收 | P0 |
| `/api/imports/pending` | GET | 获取待认领导入记录 | P0 |
| `/api/imports/{id}/claim` | POST | 认领导入记录 | P0 |
| `/api/cards` | GET/POST | 卡片列表和创建 | P0 |
| `/api/cards/{id}` | GET/PUT | 卡片详情和编辑保存 | P0 |
| `/api/cards/{id}/publish` | POST | 发布卡片 | P0 |
| `/api/cards/{id}/duplicate` | POST | 一键复用卡片 | P0 |
| `/api/cards/{id}/view` | POST | 记录浏览 | P0 |
| `/api/cards/{id}/stats` | GET | 获取浏览和接龙统计 | P1 |
| `/api/cards/{id}/relay` | POST | 提交接龙 | P0 |
| `/api/cards/{id}/relays` | GET | 获取接龙名单 | P0 |
| `/api/relays/{id}` | DELETE | 删除无效接龙 | P0 |
| `/api/relays/{id}/follow-up` | POST | 标记已跟进 | P0 |

## 7. 资源任务

- 准备小程序图标、空状态图、默认封面图。
- 准备导入成功、导入失败、认领提示、接龙提示文案。
- 准备 mock 微信笔记消息、mock 链接消息、mock 图片媒体。
- 准备测试用卡片、浏览记录、接龙记录。

## 8. 开发里程碑

### M1：项目骨架

- 建立小程序和 FastAPI 项目结构。
- 建立配置和基础 API。
- 建立 mock 数据。

### M2：导入与卡片生成

- 实现企业微信回调入口。
- 实现 mock `sync_msg` 数据导入。
- 实现消息聚合和规则解析。
- 生成待认领卡片草稿。

### M3：小程序核心页面

- 登录页
- 待认领导入页
- 素材库页
- 卡片编辑页
- 卡片查看页

### M4：查看、统计、接龙

- 浏览统计
- 登录浏览用户列表
- 匿名浏览总量
- 接龙提交
- 接龙名单管理

### M5：复用与验收

- 一键复用
- 搜索和分类
- P0 自测
- QA 验收文档

## 9. mock 和真实接入边界

必须真实实现：

- 数据结构
- 消息聚合逻辑
- 卡片生成逻辑
- 认领逻辑
- 卡片编辑保存
- 浏览统计逻辑
- 接龙逻辑
- 一键复用逻辑

可在本地开发阶段 mock：

- 企业微信真实回调
- `sync_msg` 返回数据
- media_id 下载结果
- 对象存储上传结果
- 大模型解析结果
- 微信登录 code 换 openid

上线前必须真实接入：

- 企业微信回调 URL
- `sync_msg`
- 媒体下载和转存
- 小程序登录
- 线上数据库
- 线上对象存储

暂不纳入 v0.1：

- PC Web 管理后台
- 企业微信客服侧边栏/H5 主动发送小程序卡片
- `window.toolkit.sendChatMessage` 或类似客服工具栏发消息能力

如后续要实现客服侧边栏发卡片，必须先单独验证官方接口可用性、身份绑定方式、小程序卡片参数格式和企业微信后台配置要求。
