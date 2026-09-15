# 资料整理助手：五类编辑器数据、路由与附件技术规格

更新时间：2026-08-13

状态：开发前锁定规格。产品与 UI 结论见 `docs/stage2-docs/39-content-editor-product-design-decisions.md`。

## 1. 目标与约束

本轮实现五类编辑器：

1. 通用编辑器：文字、图片、文章链接三种内容模式。
2. 房源编辑器。
3. 商品 / 团购编辑器。
4. 服务 / 合作编辑器。
5. 电子名片编辑器。

必须继续使用 `UserNote` 作为统一内容容器，不新建五张平行业务主表。编辑器、客户页、分享、生成同款和雷达都围绕同一个 `noteId` 工作。

核心约束：

- 创建成功后只更新同一条 `UserNote`，不得因改类型、换样式、预览或返回编辑重复创建资料。
- 所有可分享资料默认进入基础 SCRM 记录；前端不暴露 SCRM 开关。
- 私密字段不得进入公开 API、客户页、分享封面、生成同款或精选资料快照。
- 身份与联系方式以“我的”个人资料为唯一来源。
- 不碰生产环境；测试环境仍使用 `/test-api`、`/test-media`。

## 2. 现状与必须修正的差距

### 2.1 可复用现状

- 统一主模型：`backend/app/models/domain.py::UserNote`。
- 统一 CRUD：`GET/PUT/DELETE /api/notes/{note_id}`。
- 创建入口：`/api/notes/quick-capture`、`/api/notes/manual-draft`、`/api/notes/image-capture`。
- 类型确认：`POST /api/notes/{note_id}/confirm-type`。
- 客户公开页：`GET /api/notes/public/{note_id}` 和 `pages/note-preview/index`。
- 浏览记录：`POST /api/notes/{note_id}/view`。
- 客户动作：`POST /api/notes/{note_id}/customer-actions/{action_key}`。
- 生成同款与邀请归因：`POST /api/scrm/same-style/generate`。

### 2.2 已知缺口

- `note-edit` 同时混入类型表单、客户反馈、能力开关、标签和分享工具，需要按新规格收口。
- 入口导航分散在多个页面，没有唯一的 `cardType -> editor route` 解析器。
- `ContentMediaPayload` 字段过松，没有附件 ID、大小、MIME、排序、状态等稳定契约。
- `/api/uploads/asset` 接受 `mediaType=file`，但当前实现仍按图片存储路径处理，不能视为 PDF 已可用。
- 现有浏览事件能保存 `focusSections`，但没有稳定的附件点击事件类型和附件 ID。
- 公共用户资料目前只有昵称、头像、微信和电话；职位、公司、一句话介绍、二维码等名片共享身份字段尚无单一数据源。
- 现有 4 个名片模板包含行业默认文案，切换模板可能改变内容；必须迁移为纯视觉样式。
- 现有生成同款底层仍复用房源克隆逻辑，必须按不同 `cardType` 做剥离策略。

## 3. 统一 UserNote 契约

继续保留 `UserNote` 顶层字段：

```json
{
  "id": "note_xxx",
  "ownerUserId": "user_xxx",
  "status": "draft|active|deleted",
  "title": "客户可见标题",
  "summary": "系统生成或用户修正的列表摘要",
  "body": "主要正文或详细说明",
  "coverUrl": "第一张公开图片或自动文字封面地址",
  "media": [],
  "categoryIds": [],
  "locationText": "兼容旧数据的公开位置摘要",
  "sourceRefs": [],
  "visibilityConfig": {},
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

`phone` 仅保留旧数据兼容，不再作为各编辑器联系方式真源。

### 3.1 visibilityConfig 公共结构

```json
{
  "schemaVersion": 2,
  "cardType": "text_note|image_ocr|link|property_listing|groupbuy_product|service_offer|business_card",
  "sourceType": "manual|text|image|link|wechat|wecom_archive|same_style",
  "cardState": "collected|editing|ready",
  "structuredData": {},
  "displayConfig": {},
  "conversionConfig": {
    "enableLightScrm": true
  },
  "privateData": {},
  "recognition": {
    "suggestedCardType": "",
    "confidence": 0,
    "privacyWarnings": []
  }
}
```

规则：

- `structuredData` 只能放允许进入公开净化流程的业务字段。
- `privateData` 只允许拥有者读取，公共 API 必须整体删除。
- `displayConfig` 只保存样式和展示选择，不保存用户业务内容。
- `conversionConfig.enableLightScrm` 后端统一为 `true`；其他客户动作由场景默认规则生成，不在编辑器展示开关。
- `cardState` 只用于系统和列表状态，不在编辑器显示“收藏/整理/生成”工作流。

## 4. 各类型 structuredData

### 4.1 通用文字 `text_note`

```json
{
  "contentMode": "text",
  "autoSummary": "",
  "publicSourceLabel": "",
  "rawText": "仅兼容识别来源，公开克隆前需净化"
}
```

- `title`、`body` 使用 `UserNote` 顶层字段。
- 无图封面由分享渲染层生成，不强制上传图片。

### 4.2 通用图片 `image_ocr`

```json
{
  "contentMode": "image",
  "caption": "选填说明",
  "ocrText": "",
  "ocrStatus": "pending|success|failed",
  "privacyWarnings": []
}
```

- 图片存在统一 `media` 附件数组。
- OCR 文本默认不在客户页重复展示。

### 4.3 文章链接 `link`

```json
{
  "contentMode": "link",
  "sourceUrl": "https://...",
  "sourceTitle": "",
  "sourceName": "",
  "sourceDomain": "",
  "sourceCoverUrl": "",
  "sourceDescription": "",
  "sellerRecommendation": ""
}
```

- 客户页不复制第三方全文。
- “查看原文”点击必须记录独立附件/链接事件。

### 4.4 房源 `property_listing`

```json
{
  "transactionType": "rent|sale",
  "community": "",
  "displayTitle": "",
  "price": "",
  "priceUnit": "元/月|万元",
  "layout": "",
  "area": "",
  "businessArea": "",
  "highlights": [],
  "remark": "",
  "propertyStatus": "active|paused|closed",
  "rentDetails": {
    "paymentMethod": "",
    "utilities": "",
    "moveInTime": "",
    "customerServiceFee": ""
  },
  "saleDetails": {
    "unitPrice": "",
    "orientation": "",
    "floor": "",
    "elevator": "",
    "decoration": "",
    "ownershipTaxNote": ""
  },
  "publicLocation": {
    "name": "",
    "address": "",
    "latitude": null,
    "longitude": null,
    "navigationLabel": "导航到小区"
  }
}
```

`privateData`：

```json
{
  "exactLocation": {
    "building": "",
    "unit": "",
    "room": "",
    "exactAddress": "",
    "latitude": null,
    "longitude": null
  },
  "upstreamContact": "",
  "upstreamPhones": [],
  "upstreamWechat": "",
  "commission": "",
  "lockNote": "",
  "lockPassword": "",
  "viewingNote": "",
  "privateRemark": "",
  "sourceUrl": ""
}
```

出租和出售字段可同时存在于历史数据中，但公开展示和编辑器只读取当前 `transactionType` 对应分组。

### 4.5 商品 / 团购 `groupbuy_product`

```json
{
  "salesMode": "inquiry|relay",
  "productName": "",
  "headline": "",
  "highlights": [],
  "remark": "",
  "variants": [
    {
      "id": "variant_xxx",
      "name": "3斤装",
      "priceFen": 4990,
      "stockStatus": "available|sold_out",
      "sortOrder": 0
    }
  ],
  "fulfillment": {
    "methods": ["shipping|local_delivery|store_pickup|community_pickup|offline_contact"],
    "shippingFeeNote": "",
    "deliveryArea": "",
    "deliveryFeeNote": "",
    "availableTime": "",
    "pickupLocation": {
      "name": "",
      "address": "",
      "latitude": null,
      "longitude": null
    }
  },
  "relayConfig": {
    "deadlineAt": null,
    "stockNote": "",
    "limitPerPerson": null,
    "fulfillmentNote": ""
  }
}
```

`privateData` 保存供应商、供应商联系方式、成本、利润、内部库存、采购链接和内部备注。

金额新字段使用整数分 `priceFen`；读取旧 `price`/SKU 时做兼容转换，禁止浮点金额作为新真源。

### 4.6 服务 / 合作 `service_offer`

```json
{
  "serviceName": "",
  "headline": "",
  "detailText": "",
  "serviceScope": "",
  "pricingOrTerms": "",
  "primaryAction": "consult"
}
```

- 不增加行业子类型。
- 图片、PDF、链接全部进入统一附件数组。
- 旧 `targetAudience/serviceProcess/caseHighlights/...` 只做只读迁移：合并进 `detailText` 或保留兼容，不再在新编辑器形成独立输入框。

### 4.7 电子名片 `business_card`

`structuredData` 只保存名片独有展示内容和引用：

```json
{
  "headline": "",
  "serviceKeywords": [],
  "bio": "",
  "featuredNoteIds": []
}
```

`displayConfig`：

```json
{
  "styleId": "business_blue|clean_white|warm_gold|fresh_green"
}
```

姓名、头像、职位、公司、城市、手机号、微信、二维码、邮箱、网址必须来自统一用户资料，不复制进名片作为另一套真源。

## 5. 用户销售身份模型

现有 `User` 只有昵称、头像、微信、电话，需扩展一个统一的 `salesProfile`（可作为 User 字段或独立一对一 Profile 模型，优先选择符合现有 repository 的最小改动）：

```json
{
  "displayName": "",
  "avatarUrl": "",
  "jobTitle": "",
  "company": "",
  "city": "",
  "phone": "",
  "wechat": "",
  "wechatQrUrl": "",
  "email": "",
  "website": ""
}
```

规则：

- `openid` 仍是用户身份唯一锚点。
- 修改销售身份后，电子名片和所有资料客户页实时读取新值。
- 公开 API 按当前资料动作需要返回脱敏或允许公开的联系方式；拥有者 API 返回完整字段。
- 不通过批量复制方式回写每条历史资料。

## 6. 统一附件模型

### 6.1 UserNote.media 作为公开附件唯一真源

```json
{
  "id": "att_xxx",
  "type": "image|pdf|link",
  "url": "https://...",
  "name": "服务价目表.pdf",
  "title": "公司服务介绍",
  "description": "",
  "mimeType": "application/pdf",
  "sizeBytes": 880640,
  "pageCount": 3,
  "coverUrl": "",
  "sortOrder": 0,
  "source": "upload|external_link|wechat|wecom_archive",
  "status": "ready|failed"
}
```

兼容规则：

- 旧 `{type,url,title,mediaId,sourceRef}` 在读取层补齐默认值。
- 新写入必须有稳定 `id`、`type`、`url`、`sortOrder`。
- 图片 `coverUrl` 可为空；PDF 的 `pageCount` 获取不到时允许为空，不能伪造页数。
- 外部链接必须是 `https`，服务端校验协议并防止危险 scheme。
- 私密附件不能放入 `UserNote.media`，应放在 `privateData.privateAttachments`，公共净化时整体删除。

### 6.2 第一版限制

- 图片：每份资料最多 9 张，支持 JPG/PNG/WebP；上传后沿用现有压缩处理。
- PDF：每份资料最多 5 份，单份建议上限 20MB；只接受真实 `application/pdf` 和 `.pdf` 一致文件。
- 外部链接：每份资料最多 5 条，必须为 HTTPS。
- 单份资料公开附件总数建议不超过 12；超限时前端阻止并给出明确提示。
- 视频不纳入本轮五编辑器 P0；保留旧数据展示兼容，不新增视频编辑能力。

部署前应核对测试 Nginx 上传限制高于应用限制。本轮不得修改生产 Nginx。

### 6.3 上传与访问接口

建议在现有 `/api/uploads/asset` 基础上修正，而非增加重复上传服务：

- `mediaType=image`：沿用图片压缩。
- `mediaType=pdf`：不进入图片处理器，保留 PDF 字节与 MIME，返回附件 ID、名称、大小；可选提取页数，失败不阻塞上传。
- 后端校验扩展名、MIME 和文件签名，拒绝伪装文件。
- 删除附件时只移除当前资料引用；底层文件回收遵守现有媒体引用机制，不能误删其他资料共用资源。

小程序来源：

- 图片：`wx.chooseMedia`。
- PDF：`wx.chooseMessageFile`，限制扩展名为 PDF；预览使用 `wx.openDocument`。
- 链接：手动粘贴或从新建页识别。

## 7. 附件与客户行为事件

保留 `/api/notes/{note_id}/view` 记录页面打开、停留、滚动；新增或扩展一个显式互动事件接口，推荐：

```text
POST /api/notes/{note_id}/events
```

请求：

```json
{
  "eventType": "image_open|pdf_open|link_open|contact_click|phone_click|wechat_qr_open|map_open",
  "attachmentId": "att_xxx",
  "viewerUserId": null,
  "anonymousId": "anon_xxx",
  "shareId": "share_xxx",
  "shareFromUserId": "user_xxx",
  "sessionId": "session_xxx",
  "scene": "note_preview",
  "metadata": {}
}
```

规则：

- 服务端校验 `attachmentId` 必须属于该公开资料，不能任意伪造其他资料附件。
- 拥有者预览不计入客户信号。
- PDF 只能记录点击/打开，不能记录“读完”或页码。
- 外部链接先成功记录点击，再调用小程序允许的打开方式；失败需要给客户可理解提示。
- 相同 `sessionId + eventType + attachmentId` 可做短时间幂等去重，避免连续点击污染雷达。

## 8. 页面路由

### 8.1 唯一路由解析器

`miniprogram/utils/resource-navigation.js` 是当前唯一编辑器路由解析器，所有入口只调用 `editorPathForCardType()` / `navigateToNoteEditor()`。

```js
resolveNoteEditorRoute(cardType, noteId, options)
```

映射固定为：

| cardType | 编辑路由 |
|---|---|
| `text_note` | `/pages/note-edit/index?id={noteId}` |
| `image_ocr` | `/pages/note-edit/index?id={noteId}` |
| `mixed_content` | `/pages/note-edit/index?id={noteId}` |
| `pdf_document` | `/pages/note-edit/index?id={noteId}` |
| `link` | `/pages/link-confirm/index?id={noteId}` |
| `article` | `/pages/link-editor/index?id={noteId}` |
| `property_listing` | `/pages/property-editor/index?id={noteId}` |
| `groupbuy_product` | `/pages/product-editor/index?id={noteId}` |
| `service_offer` | `/pages/service-offer-studio/index?id={noteId}` |
| `business_card` | `/pages/business-card-studio/index?id={noteId}` |

说明：

- 通用 `note-edit` 重构为三种轻内容模式，不再承载房源、商品、名片和服务巨型表单。
- URL 采用“解析确认 -> 作者编辑 -> 客户阅读”独立链路，不再进入 `note-edit`。
- 通用页使用显式白名单；未知类型失败关闭，不得兜底渲染旧 DOM。
- 房源和商品从旧 `note-edit` 分离为独立页面，减少条件分支和回归风险。
- 现有服务与名片 studio 路由保留，但内部按新轻量稿重构，避免全局入口大规模失效。
- `library`、`home`、`imports`、`notes`、`card-edit/view`、`resource-create` 等所有入口改用统一解析器。

### 8.2 新建流程

统一入口：

```text
/pages/resource-create/index?scene={scene}
```

scene：

```text
quick_note | property_listing | groupbuy_product | service_offer | business_card
```

流程：

```text
输入文字/图片/链接/PDF
-> 创建一条 draft UserNote
-> 识别或用户确认 cardType
-> 使用同一 noteId 跳转对应编辑器
-> 保存并预览
-> /pages/note-preview/index?id={noteId}
```

电子名片若用户已有主名片，入口直接编辑现有 `noteId`，不得创建第二张。

### 8.3 客户页与分享

统一客户页继续使用：

```text
/pages/note-preview/index?id={noteId}&sid={shareId}&from={shareFromUserId}&src={scene}&ref={parentShareId}
```

- `note-preview` 按 `cardType` 渲染对应客户页面。
- 分享 `shareId`、来源用户、父分享和场景必须完整透传。
- 分享封面按类型/名片样式生成；“生成同款”文案按产品结论展示。

### 8.4 生成同款

新增通用页面路由：

```text
/pages/same-style/index?sourceNoteId={id}&sid={shareId}&from={sourceOwnerId}
```

旧 `/pages/property-same/index` 保留兼容入口，房源可重定向到通用页。

后端继续使用 `/api/scrm/same-style/generate`，但需重构为按 `cardType` 的净化策略：

- 通用、房源、商品、服务：复制公开内容与公开附件，剥离身份、统计、客户、私密字段并生成新 `noteId`。
- 电子名片：不复制姓名、头像、职位、公司、介绍、二维码、联系方式和精选资料，只保留样式 ID，并读取新用户资料。
- 新资料必须产生独立统计链路；幂等键重复请求不能重复创建。

## 9. 公开净化规则

`GET /api/notes/public/{id}` 与生成同款必须复用同一个公开净化器，禁止各写一套字段黑名单。

必须删除：

- `privateData`、`privateTags`、内部标签和内部备注。
- 房源具体楼栋、单元、房号、密码、精确私密坐标、上游联系人和佣金。
- 商品供应商、成本、利润、内部库存、采购链接、接龙名单。
- 服务内部备注（若历史数据存在）。
- 客户身份、访问、留言、跟进、订单/接龙记录和统计快照。
- 原作者的直接联系方式副本；公开页面运行时从当前拥有者销售资料附加。

## 10. 四个名片轻样式

```text
business_blue  商务蓝（默认）
clean_white    简洁白
warm_gold      暖灰金
fresh_green    清新绿
```

切换只更新 `visibilityConfig.displayConfig.styleId`。不得：

- 写入模板默认姓名、公司、职位、服务内容。
- 清空或覆盖用户资料。
- 新建 `UserNote`。
- 重置客户统计、分享归因或精选资料。

资料库列表保持统一卡片；样式影响客户名片主页和微信分享封面。

## 11. 参考图

以下图片是开发验收参考：

- `docs/png/editor-design/01-text-three-scenes.png`
- `docs/png/editor-design/02-image-three-scenes.png`
- `docs/png/editor-design/03-link-three-scenes.png`
- `docs/png/editor-design/04-property-editor.png`
- `docs/png/editor-design/05-product-editor.png`
- `docs/png/editor-design/06-service-collaboration-editor.png`
- `docs/png/editor-design/07-business-card-three-scenes.png`

注意：此前生成的复杂专业服务方案编辑器已经废弃，不在本目录，不得作为实现依据。

## 12. 推荐开发顺序

1. 补统一附件模型、PDF真实上传/预览和公开净化测试。
2. 补统一编辑路由解析器和新建后单 `noteId` 跳转。
3. 重构通用编辑器和客户页三种模式。
4. 分离房源、商品编辑器并迁移旧数据。
5. 重构轻量服务/合作编辑器。
6. 重构电子名片、统一销售身份和 4 个轻样式。
7. 补通用生成同款净化、分享封面和附件事件。
8. 运行测试清单并统一进行对抗式审查。
