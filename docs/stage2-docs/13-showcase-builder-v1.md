# 展示页构建器 V1 开发文档

更新时间：2026-06-21

## 1. 目标

展示页构建器 V1 是 P1 的第一条主线。目标是让发布者从自己的资料库中选择多条 `UserNote`，配置店名、简介、banner、联系方式和展示顺序，生成一个可分享的小程序展示页。

展示页不是 AI 自动全权生成，也不是 PC 官网。它是小程序里的可视化配置工具，承接“资料整理助手”的资料库价值：

```text
资料库 UserNote
  -> 勾选多条资料
  -> 配置展示页基础信息
  -> 预览
  -> 发布
  -> 客户打开展示页
  -> 进入单条客户页 / 留联系方式 / 发消息
```

## 2. 范围

### 2.1 本轮做

- 后端新增展示页模型和接口。
- 展示页只保存 `noteId`、排序和展示配置，不复制资料正文。
- 小程序新增展示页列表 / 编辑构建页 / 客户展示页。
- 发布者可创建、编辑、预览、发布和下架展示页。
- 客户可打开已发布展示页，查看店铺信息和资料列表，并进入单条资料客户页。
- 支持基础联系配置：电话、微信号、联系文案。
- V1 固定按标签分组，不在编辑页暴露复杂展示方式。
- V1 固定四个标准模板：精选橱窗、朋友圈长页、清单目录、品牌名片。
- 支持展示页真实效果追踪：打开、资料点击、电话咨询、复制微信、分享。
- owner 展示页列表提供轻量效果看板：PV/UV、咨询点击、资料点击排行、最近访客。

### 2.2 本轮不做

- 不做 AI 自动生成完整展示页。
- 不做多模板商城、复杂装修器、拖拽自由布局。
- 不做支付、会员权益拦截和展示页数量计费。
- 不做独立 PC 管理后台。
- 不做展示页级实时 IM；消息入口继续复用已有单条资料消息能力。
- 不复制资料正文到展示页，避免资料更新后出现两份不一致内容。
- 不做四模板多尺寸精修和商品/房源混合资料的复杂模板规则，先等真实上线反馈。
- 不做复杂分享来源归因、渠道码、转化漏斗和客户画像，只做基础真实事件统计。

## 3. 数据结构

### 3.1 ShowcasePage

字段建议：

- `id`：展示页 ID。
- `ownerUserId`：发布者用户 ID。
- `status`：`draft / published / archived`。
- `name`：店名或展示页名称。
- `description`：简介。
- `bannerUrl`：banner 图片。
- `templateId`：模板 ID，V1 默认 `featured_window`；四个固定模板为 `featured_window`、`moments_story`、`catalog_list`、`brand_card`。
- `shareTitle`：分享标题。
- `contactConfig`：
  - `phone`
  - `wechat`
  - `contactText`
  - `showPhone`
  - `showWechat`
- `displayConfig`：
  - `groupBy`：`none / cardType / tag / custom`
  - `showSearch`
  - `showTags`
  - `primaryColor`
- `items`：`ShowcaseItem[]`。
- `publishedAt`
- `createdAt`
- `updatedAt`

### 3.2 ShowcaseItem

字段建议：

- `noteId`：关联资料。
- `sortOrder`：排序。
- `sectionTitle`：自定义分组标题。
- `displayTitle`：可选展示标题，默认用资料标题。
- `visible`：是否展示。
- `fieldConfig`：字段展示配置，V1 先保留对象字段，不做复杂 UI。

### 3.3 ShowcaseEvent

字段建议：

- `id`：事件 ID。
- `showcaseId`：展示页 ID。
- `ownerUserId`：展示页发布者。
- `eventType`：`view / note_click / phone_click / wechat_copy / share`。
- `noteId`：点击资料时记录对应资料，其他事件为空。
- `viewerUserId`：登录访客 ID，可为空。
- `anonymousId`：匿名访客本地 ID，可为空。
- `viewType`：`logged_in / anonymous`。
- `nickname` / `avatarUrl`：登录访客展示信息。
- `createdAt`
- `dateKey`

## 4. 后端接口

### 发布者接口

- `GET /api/showcases?ownerUserId=xxx`
  - 查询自己的展示页列表。
- `POST /api/showcases`
  - 创建展示页草稿。
- `GET /api/showcases/{showcase_id}?ownerUserId=xxx`
  - 获取自己的展示页详情，可查看草稿。
- `PUT /api/showcases/{showcase_id}`
  - 更新展示页基础信息和 items。
- `POST /api/showcases/{showcase_id}/publish`
  - 发布展示页。
- `POST /api/showcases/{showcase_id}/archive`
  - 下架展示页。
- `GET /api/showcases/{showcase_id}/analytics?ownerUserId=xxx`
  - 发布者查看展示页效果。
  - 返回 PV/UV、资料点击、咨询点击、最近访客、最近动作。

### 客户公开接口

- `GET /api/showcases/public/{showcase_id}`
  - 只返回已发布展示页。
  - 返回页面配置和可见资料摘要。
  - 不返回未发布、已删除或不属于该展示页的资料。
- `POST /api/showcases/{showcase_id}/events`
  - 客户页上报真实事件。
  - 只接受已发布展示页。
  - 事件只用于发布者看板，不在客户页公开展示。

## 5. 后端规则

- 创建和更新时必须校验 owner 存在。
- `items.noteId` 必须属于 `ownerUserId`，且资料不是 deleted。
- 同一个展示页内同一 noteId 只保留一条，按第一次出现的顺序去重。
- 发布时至少需要：
  - `name` 非空。
  - 至少 1 条可见且有效的资料。
- 客户公开接口只允许访问 `published` 展示页。
- 资料摘要需要复用 `UserNote` 的可见字段：
  - `id`
  - `title`
  - `summary`
  - `coverUrl`
  - `visibilityConfig.cardType`
  - `visibilityConfig.systemCategory`
  - `visibilityConfig.tags`
  - `updatedAt`
- 不把匿名用户展示为实名浏览用户。
- 展示页效果看板只能由 owner 查看。
- 匿名访客只统计数量，不展示成实名客户。
- 展示页不得展示无法由系统证明的服务客户数、成交数或好评率。

## 6. 小程序页面

### 6.1 owner 展示页列表

路径建议：`pages/showcases/index`

能力：

- 展示自己的展示页列表。
- 可创建新展示页。
- 可进入编辑。
- 可打开客户展示页预览。
- 已发布展示页显示轻量效果摘要。
- 可展开效果看板，查看打开、访客、资料点击、咨询点击、最近访客和资料点击排行。

### 6.2 owner 构建页

路径建议：`pages/showcase-edit/index`

能力：

- 编辑店名、简介、分享标题、联系方式。
- 输入 banner 图片地址，或从相册/相机上传 banner 图片。
- 从资料库勾选资料。
- 对已选资料排序、隐藏、移除。
- 对单条已选资料设置展示标题和自定义分组标题。
- 保存草稿。
- 发布 / 下架。
- 预览客户展示页。

### 6.3 客户展示页

路径建议：`pages/showcase-view/index`

能力：

- 展示 banner、店名、简介、联系方式。
- 展示资料列表。
- 支持按基础分组展示。
- 点击资料进入 `pages/note-preview/index?noteId=xxx`。
- 电话/微信联系能力只展示发布者配置，不自动创建线索。
- 真实客户打开时记录 `view`，发布者预览不记录。
- 点击资料记录 `note_click`。
- 电话咨询记录 `phone_click`。
- 复制微信记录 `wechat_copy`。
- 触发分享记录 `share`。

## 7. 验收标准

- 发布者能创建展示页草稿。
- 发布者能从资料库选择多条资料并保存。
- 后端拒绝选择其他用户资料。
- 未发布展示页不能通过公开接口访问。
- 无有效资料时不能发布。
- 发布后客户页可打开并展示资料摘要。
- 下架后公开接口不可访问。
- 资料更新后展示页公开接口读取到最新资料摘要。
- 小程序 JS 和 JSON 检查通过。
- 后端测试覆盖创建、更新、发布、公开访问、权限和下架。
- 后端测试覆盖展示页事件记录、owner analytics 权限、PV/UV、资料点击和咨询点击统计。

## 8. P2 暂缓项

以下能力暂不开发，等真实上线和用户反馈后再排期：

- 四套模板在更多手机尺寸上的细节视觉回归。
- 商品/房源混合资料时的专门模板策略。
- 多渠道分享归因、渠道码和转化漏斗。
- 更细的客户画像、客户分层和跨展示页行为合并。
- 模板商城、自由装修器和更多自定义品牌组件。

## 9. Codex 执行说明

开发顺序：

1. 补测试清单。
2. 增加后端模型、schema、repository、service、routes 和测试。
3. 增加小程序 API 方法。
4. 增加 `pages/showcases`、`pages/showcase-edit`、`pages/showcase-view`。
5. 在合适入口接入展示页列表，V1 可先从“我的”页进入。
6. 运行后端测试、小程序 JS 检查、JSON 检查和 `git diff --check`。
