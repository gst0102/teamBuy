# 资料整理助手插件化架构计划

## 目标

资料整理助手分为两层：

- 稳定基座：企业微信通信、会话内容存档、用户身份识别、会话管理、合规、支付、笔记库、展示页基础能力。
- 可插拔 Skill：围绕具体内容处理的独立功能，例如内容整理成笔记、笔记生成漫画图、展示页辅助配置。

核心原则是“企业微信做入口，基座管稳定能力，Skill 管多变能力”。企业微信回调、会话存档、身份和支付不应写死到某个内容整理功能里。

## 混合驱动模式

默认采用快捷指令 / 菜单点按 + AI 意图识别兜底：

1. 优先匹配快捷指令：稳定、明确、不会误判。
2. 再走规则匹配：链接、关键词、已知来源类型等可确定场景。
3. 最后才进入 AI 意图识别：只处理用户自由输入。
4. AI 只返回固定枚举和置信度，不直接执行业务动作。
5. 低置信度、非法 JSON、未知意图都返回确认菜单，由用户点选。

第一批快捷指令：

- 整理笔记
- 整理聊天
- 整理链接
- 生成漫画图
- 创建展示页
- 我的资料
- 购买套餐

AI 意图枚举固定为：

- `content_to_note`
- `note_to_comic_image`
- `showcase_builder`
- `billing`
- `help`
- `unknown`

## 内容抽象

所有文字来源先统一为 `ContentObject`：

```text
企业微信消息 / 微信笔记 / 聊天记录 / 链接文章 / 图片 OCR
  -> Input Adapter
  -> ContentObject
  -> content-to-note
  -> UserNote
  -> 小程序笔记库 / 展示页 / 漫画图
```

微信笔记、聊天记录、链接文章不是三个不同 Skill，而是同一个 `content-to-note` 的不同输入来源：

- `input.wecom-thread`
- `input.chat-thread`
- `input.link-article`
- `input.manual-text`
- 后续 `input.image-ocr`

输入差异由 Adapter 处理，输出差异由模板处理。

## 核心模块

- `wecom-archive-core`：企业微信会话内容存档，保存消息、媒体、会话、外部联系人、游标和审计日志。
- `identity-core`：统一企业微信外部联系人、小程序用户和付费账户，处理首次导入后的补绑定。
- `skill-router`：快捷指令、规则匹配、AI 意图识别兜底，生成 `IntentResult` 和 `SkillRun`。
- `content-core`：定义 `ContentObject`，管理输入适配器。
- `content-to-note`：核心文字整理 Skill，规则优先，大模型兜底，输出 `UserNote`。
- `note-library-core`：小程序用户笔记库，支持编辑、删除、分类、搜索、来源追溯。
- `showcase-builder`：多笔记展示页构建器，支持模板、分类、瀑布流、字段开关、发布分享。
- `note-to-comic-image`：单笔记或文章摘要生成漫画图、宣传图或长图。
- `billing-core`：微信支付、H5 支付、订单、权益和额度。

## 公开类型

- `ContentObject`：`sourceType`、`title`、`textBlocks`、`media`、`links`、`participants`、`timestamps`、`sourceRefs`、`rawMessageIds`。
- `UserNote`：`ownerUserId`、`title`、`summary`、`body`、`coverUrl`、`media`、`categoryIds`、`phone`、`locationText`、`sourceRefs`、`visibilityConfig`。
- `SkillCommand`：`commandText`、`aliases`、`skillId`、`inputAdapter`、`requiresPayment`、`enabled`。
- `IntentResult`：`intent`、`skillId`、`confidence`、`source`、`needsConfirm`。
- `SkillRun`：`skillId`、`status`、`inputSnapshot`、`outputRef`、`modelProvider`、`errorMessage`、`cost`、`startedAt`、`endedAt`。
- `ShowcasePage`：`ownerUserId`、`name`、`description`、`bannerUrl`、`templateId`、`status`、`sharePath`、`contactConfig`。
- `ShowcaseItem`：只保存 `noteId`、排序、分类、字段显示配置，不复制完整笔记正文。
- `ComicImageArtifact`：`noteId`、`imageUrl`、`status`、`promptSnapshot`、`errorMessage`。

## 主要流程

### 企业微信整理笔记

```text
用户在企业微信点“整理笔记”
  -> 后端收到标准指令
  -> 从当前会话窗口收集消息
  -> input.wecom-thread 转为 ContentObject
  -> content-to-note 生成 UserNote
  -> 保存到小程序笔记库
  -> 企业微信回复“已整理，可在小程序查看/编辑”
```

### 用户自由输入

```text
用户输入“帮我把刚才客户发的内容整理一下”
  -> 无精确指令
  -> 规则匹配不确定
  -> AI 意图识别
  -> 识别为 content_to_note
  -> 置信度足够才执行
  -> 置信度不足则回复确认菜单
```

### 链接整理

```text
用户发送链接或点“整理链接”
  -> input.link-article 提取标题、正文、封面
  -> ContentObject
  -> content-to-note
  -> UserNote
```

### 漫画图生成

```text
用户在笔记详情点“生成漫画图”
  -> note-to-comic-image
  -> 生成 ComicImageArtifact
  -> 可设为封面或保存到笔记素材
```

### 展示页创建

```text
用户进入小程序展示页入口
  -> 选择模板
  -> 填店名/banner/简介
  -> 从笔记库搜索筛选并勾选笔记
  -> 设置分类和字段开关
  -> 预览
  -> 发布成小程序分享页
```

展示页不是 AI 全自动生成，而是小程序可视化配置工具。AI 只做辅助：推荐分类、生成店铺简介、优化标题、生成 banner 文案。

### 支付

```text
用户触发付费 Skill 或额度不足
  -> billing-core 创建订单
  -> 小程序支付或企业微信 H5 支付链接
  -> 支付成功后发放权益
  -> Skill 可继续执行
```

## 模型策略

不把核心编排绑定在 LangChain 上。后端自研轻量路由和状态机：

- `RuleRouter`
- `SkillRouter`
- `ModelAdapter`
- `OutputValidator`
- `ArtifactWriter`

模型供应商通过 Adapter 接入：DeepSeek、OpenAI、通义、智谱，后续可扩展。

大模型只做意图分类兜底、内容摘要、字段候选提取、标题优化、分类推荐、漫画图提示词生成。大模型不能直接改数据库，所有输出必须经过结构化校验。

## 实施阶段

### Phase 1：架构文档和插件边界

- 新增插件架构文档。
- 明确基座、Skill、Adapter、Template、Renderer 边界。
- 现有企业微信导入先标记为 `content-to-note` 的早期实现。
- 先实现无状态 `skill-router` 和 `ContentObject`/`UserNoteDraft` 接口，供后续企业微信和小程序接入。

### Phase 2：Skill Router

- 实现快捷指令注册表。
- 实现精确匹配、规则匹配、AI 意图识别兜底。
- 增加 `SkillRun` 日志。
- 企业微信欢迎语和菜单文案先用固定文本。

### Phase 3：统一 ContentObject 和 content-to-note

- 把微信多消息、聊天、链接统一转为 `ContentObject`。
- 输出 `UserNote`。
- 小程序增加“我的笔记”基础管理。

### Phase 4：企业微信会话内容存档基座

- 接入会话内容存档。
- 保存原始消息和媒体。
- 做授权、合规、游标、审计。
- 与现有 `sync_msg` 并行一段时间。

### Phase 5：展示页构建器

- 小程序做展示页创建、编辑、预览、发布。
- 支持两个默认模板。
- 支持字段开关、分类、瀑布流。
- 分享可看，不做交易支付。

### Phase 6：漫画图 Skill

- 单笔记生成漫画图。
- 生成状态、失败重试。
- 可设置为笔记封面或展示页素材。

### Phase 7：支付和权益

- 微信支付订单。
- 企业微信 H5 支付链接。
- 免费额度、套餐权益、Skill 执行权限。

## 当前落地范围

本轮先落地 Phase 1 的可运行后端骨架：

- `/api/skills/commands`：查看快捷指令注册表。
- `/api/skills/route`：执行快捷指令和规则路由，未知输入返回确认菜单。
- `/api/skills/content-to-note/run`：把 `ContentObject` 转为规则版 `UserNoteDraft`，暂不持久化。

暂不在本轮做数据库迁移、支付、会话内容存档 SDK 接入、展示页编辑器和漫画图生成。这样可以先固定边界，再逐层接入已有企业微信导入链路和小程序页面。
