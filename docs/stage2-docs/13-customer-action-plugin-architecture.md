# 客户页动作持久化插件架构

## 1. 背景

房源客户页第一版已经有 `电话咨询`、`留下电话/微信`、`预约看房`、`微信咨询`、`地图定位`、`参与接龙`、`查看原小程序` 等动作。

这些动作不是房源独有。后续普通笔记、团购、链接资料、活动报名、课程资料、清单资料等场景也会需要：

- 收集联系方式。
- 记录预约或报名意向。
- 记录咨询动作。
- 记录接龙或参与意向。
- 进入统一轻 SCRM 跟进。

因此客户页动作持久化必须做成可复用插件，不写死在 `property_listing` 房源客户页里。

## 2. 定位

模块名建议：`customer-action-plugin`。

它不是 `content-to-note` 这类内容整理 Skill，也不是房源专属业务逻辑，而是客户页通用转化动作插件：

```text
UserNote + conversionConfig + Action Plugin Registry
  -> 客户页可用动作列表
  -> 用户提交动作
  -> CustomerActionRecord 通用记录
  -> 线索 / 预约 / 接龙 / 跟进投影
```

核心原则：

- 客户页动作由插件注册，不由房源页面硬编码。
- 不同资料类型只决定默认启用哪些动作，不复制一套提交逻辑。
- 动作提交先落通用动作记录，再按动作类型投影到已有线索、预约、接龙、跟进列表。
- 后续新增场景只新增插件配置和必要投影，不改客户页主流程。

## 3. 第一版插件清单

### `lead-contact`

用途：客户留下电话或微信。

适用：

- 房源：留下电话/微信。
- 团购：留下联系方式。
- 普通笔记：资料咨询。
- 后续活动/课程：报名联系。

提交字段：

- `name`
- `phone`
- `wechat`
- `remark`

持久化：

- 写入通用 `customer_actions`。
- 同步 upsert 到 `lead_reminders`，作为待跟进线索。

### `appointment`

用途：客户提交预约时间。

适用：

- 房源：预约看房。
- 服务类资料：预约沟通。
- 活动类资料：预约参与。

提交字段：

- `date`
- `time`
- `remark`

持久化：

- 写入通用 `customer_actions`。
- 同步 upsert 到 `lead_reminders.followUpLogs` 或后续 `appointments` 投影。
- 第一版可以先把预约内容追加到线索跟进记录，并设置 `nextFollowUpAt`。

### `relay-intent`

用途：客户提交接龙 / 参与 / 购买意向。

适用：

- 团购：参与接龙。
- 活动：报名接龙。
- 房源：感兴趣登记也可复用，但默认优先用 `lead-contact`。

提交字段：

- `name`
- `phone`
- `address`
- `quantity`
- `remark`

持久化：

- 写入通用 `customer_actions`。
- 对旧 Card 分享链路可继续投影到 `relay_entries`。
- 对新 `UserNote` 链路建议后续新增 note 维度接龙投影，避免长期依赖旧 `cardId`。

### `consult-click`

用途：记录客户点击电话咨询、微信咨询、复制联系方式等动作。

适用：

- 所有可联系资料。

提交字段：

- `contactType`: `phone` / `wechat` / `copy`
- `contactValueMasked`

持久化：

- 写入通用 `customer_actions`。
- 可更新 `lead_reminders.lastViewedAt` / `viewCount` / 跟进记录，用于判断高意向。

### `navigation-click`

用途：记录客户打开地图、复制地址、选择导航 App。

适用：

- 房源、门店、活动地点。

提交字段：

- `navigationType`: `map_app` / `wechat_map` / `copy_address`
- `address`

持久化：

- 写入通用 `customer_actions`。
- 不默认生成线索，但可作为高意向信号。

### `external-open`

用途：记录客户打开原小程序、原文链接、第三方详情页。

适用：

- 贝壳小程序房源。
- 链接文章。
- 外部活动页。

提交字段：

- `targetType`: `miniapp` / `web_url` / `article`
- `targetTitle`
- `targetRef`

持久化：

- 写入通用 `customer_actions`。
- 不默认生成线索，但可作为浏览和兴趣信号。

## 4. 数据结构建议

第一版新增通用动作记录：

```json
{
  "id": "action_xxx",
  "ownerUserId": "user_owner",
  "noteId": "note_xxx",
  "sourceCardId": "card_xxx",
  "viewerUserId": "user_viewer_or_mock",
  "anonymousId": "anon_xxx",
  "actionKey": "lead-contact",
  "actionLabel": "留下电话/微信",
  "payload": {
    "name": "张三",
    "phone": "138****8888",
    "wechat": "wxid_xxx",
    "remark": "周末看房"
  },
  "projectionRefs": {
    "leadReminderId": "lead_xxx",
    "relayEntryId": null
  },
  "createdAt": "2026-06-19T10:00:00+08:00",
  "updatedAt": "2026-06-19T10:00:00+08:00"
}
```

注意：

- `payload` 服务端保存真实值，但返回客户页时必须避免把他人隐私回显给普通客户。
- 发布者管理页可看到自己资料下的动作明细。
- 匿名客户必须用 `anonymousId` 区分，不能错误展示成实名浏览用户。
- `noteId` 是新链路主键；`sourceCardId` 仅作旧 Card 兼容。

## 5. API 建议

### 获取客户页动作

```text
GET /api/notes/{note_id}/customer-actions/config?viewerUserId=...
```

返回：

- 当前资料可用动作。
- 每个动作的文案、表单字段、是否已提交、提交后的展示状态。
- 当前客户自己的动作状态，不返回其他客户隐私。

### 提交客户动作

```text
POST /api/notes/{note_id}/customer-actions/{action_key}
```

请求：

```json
{
  "viewerUserId": "user_viewer",
  "anonymousId": "anon_xxx",
  "payload": {}
}
```

返回：

- 动作记录。
- 投影后的线索 / 接龙摘要。
- 客户页可展示的状态文案。

### 发布者查看动作

跨资料待办继续复用现有线索页：

```text
GET /api/lead-reminders?ownerUserId=...
```

单条资料工作台使用 note 级入口：

```text
GET /api/notes/{note_id}/customer-actions?ownerUserId=...
```

用于查看某条资料下全部客户动作流水、汇总数量和已投影线索。房源资料详情“轻 SCRM”板块已接入该接口，并用待跟进线索数量显示红点提醒。

## 6. 前端接入方式

`pages/note-preview/index` 不再自己判断每个动作的提交逻辑，而是：

1. 读取 `UserNote.visibilityConfig.conversionConfig`。
2. 调接口获取可用动作配置。
3. 根据插件返回的表单 schema 渲染表单。
4. 提交时统一调用 `submitCustomerAction(noteId, actionKey, payload)`。
5. 根据返回状态刷新客户页动作状态。

房源、团购、普通笔记只负责决定默认启用哪些插件：

- 房源默认：`lead-contact`、`appointment`、`consult-click`、`navigation-click`、`external-open`。
- 团购默认：`lead-contact`、`relay-intent`、`consult-click`。
- 普通笔记按用户添加功能组启用。

## 7. 验收重点

P0：

- 客户提交电话/微信后，发布者能在线索列表看到。
- 客户提交预约后，发布者能看到预约时间和备注。
- 客户提交接龙后，发布者能看到接龙名单。
- 普通客户不能看到其他客户的电话、微信、预约或接龙隐私。
- 匿名客户不能被错误展示为实名浏览用户。
- 同一客户重复提交时要更新或提示，不能无限生成重复脏数据。

P1：

- 电话咨询、微信咨询、地图定位、打开原小程序等点击动作可作为高意向信号记录。
- 房源、团购、普通笔记都能复用同一套动作提交接口。
- 旧 Card 分享链路不被破坏。

## 8. 暂不做

- 不做标题拆字段。
- 不做封面裁切焦点。
- 不做房源亮点三条自动生成。
- 不新增完整团队协作 CRM。
- 不把动作插件和支付、订单、库存耦合。

## 9. 第一版落地状态

已落地：

- 通用 `CustomerAction` / `customer_actions`。
- `lead-contact` 提交接口和线索投影。
- `appointment` 提交接口和线索投影。
- 客户页 `note-preview` 已从本地假提交改为真实 API 提交。
- 客户页刷新时会读取动作配置，恢复当前客户自己的已提交状态。
- 发布者可从房源资料详情“轻 SCRM”进入 `pages/note-actions/index`，按当前 `noteId` 查看动作时间线和线索。

待落地：

- `relay-intent` 的 note 维度投影。
- `consult-click`、`navigation-click`、`external-open` 的高意向行为记录。
