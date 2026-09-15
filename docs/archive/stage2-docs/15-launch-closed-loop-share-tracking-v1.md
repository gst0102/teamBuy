# 上线闭环与真实分享追踪 V1 开发文档

更新时间：2026-06-21

## 1. 阶段目标

把“用户创建展示页 -> 发给客户 -> 客户打开 -> 客户看资料/咨询/下单 -> 发布者在看板和客户资料中跟进”串成真实闭环。

本阶段不再新增大而散的页面，重点是让现有展示页、经营看板、线索、订单和客户资料使用同一套行为数据。

## 2. 业务范围

### P0 必须完成

1. 展示页真实分享追踪
   - 发布者从展示页列表或展示页预览点击“发给客户”时，生成一次分享批次 `shareId`。
   - 分享路径携带 `showcaseId/shareId/shareFromUserId`。
   - 分享入口统一落到已有非 tab 页面 `pages/showcases/index`，再由该页跳转公开展示页，降低真机“页面不存在”风险。
   - 客户打开后，展示页打开事件必须记录到对应 `shareId`。

2. 客户打开与资料点击追踪
   - 客户打开展示页记录 `view`。
   - 客户点击展示页中的资料记录 `note_click`。
   - 事件必须包含展示页、资料、访客身份或匿名身份、分享批次。

3. 咨询动作追踪
   - 客户点击电话记录 `phone_click`。
   - 客户复制微信记录 `wechat_copy`。
   - 咨询动作必须能在展示页效果、经营看板和客户资料中反查。

4. 经营看板反查闭环
   - 展示页效果看板显示打开、访客、看资料、咨询。
   - 访客详情能看到来源展示页、最近行为和对应资料。
   - 客户资料页能看到浏览、资料点击、咨询、下单/接龙和跟进记录。

5. 权限与隐私
   - 展示页公开访问只允许访问已发布页面。
   - 只有 owner 能查看展示页效果和经营看板。
   - 普通访客不能看到发布者后台统计。
   - 匿名访客不能伪装成实名客户。

### P1 建议完成

- 分享入口文案、封面、标题稳定。
- 单个展示页效果页补“分享批次”维度摘要。
- 经营看板里最近访客和最新动作跳转到对应客户资料/资料详情。
- 客户资料页统一展示手机号外呼、微信复制、跟进和备注。

### P2 暂缓

- 渠道码、群来源、跨展示页归因。
- 趋势图、转化漏斗、客户画像标签。
- 多端登录后的匿名访客合并。
- 企业微信客户身份和小程序 openid 的自动强绑定。

## 3. 数据结构设计

### ShowcaseEvent 扩展字段

在现有展示页事件上增加：

- `shareId`：本次分享批次 ID。
- `shareFromUserId`：发起分享的用户 ID。
- `scene`：事件来源场景，例如 `showcase_list_share`、`showcase_preview_share`、`public_showcase`。
- `referrer`：可选来源说明。

事件类型继续保持：

- `view`
- `note_click`
- `phone_click`
- `wechat_copy`
- `share`

### 分享批次 ID 规则

第一版不单独建分享批次表，使用前端生成的稳定字符串：

```text
share_{showcaseId}_{timestamp}_{random}
```

原因：

- 微信小程序分享回调不适合在分享前强依赖后端建批次。
- 分享批次当前只用于追踪归因，不需要独立编辑和管理。
- 后续如果要做渠道码或批次列表，再升级为独立 `showcase_shares` 表。

## 4. 前端规则

### 展示页列表

- 已发布展示页主按钮为“发给客户”。
- 分享时生成 `shareId`。
- 分享路径：

```text
/pages/showcases/index?shareTarget=showcase&showcaseId={showcaseId}&sid={shareId}&from={ownerUserId}&src=showcase_list_share
```

- 同时记录 `share` 事件。

### 展示页预览页

- 预览态点击“发给客户”也生成 `shareId`。
- 分享路径同上，`src=showcase_preview_share`。
- 预览态自身不记录浏览事件，但分享动作要记录。

### 客户公开展示页

- 中转页读取 `showcaseId/sid/from/src/ref` 后跳转公开展示页。
- 公开展示页读取 `sid/from/src/ref` 参数并保存到页面状态；兼容旧链接里的 `scene` 参数。
- 打开页面时记录 `view`。
- 点击资料时记录 `note_click`。
- 电话和复制微信记录咨询事件。
- 所有事件携带 `shareId/shareFromUserId/scene`。

## 5. 后端规则

- `POST /api/showcases/{id}/events` 接收扩展字段。
- 后端只接受已发布展示页事件。
- `noteId` 必须属于当前展示页有效资料，否则后端置空或拒绝。
- analytics 返回中增加：
  - `shareCount`
  - `shareSourceCount`
  - `topShares`
  - 最近事件里的 `shareId/scene`
- 经营看板返回中增加：
  - `summary.shareCount`
  - `summary.shareSourceCount`
  - `topShares`

## 6. 验收标准

- 发布者分享展示页后，客户打开能产生 `view`。
- 客户点击资料能产生 `note_click`。
- 客户点击电话/复制微信能产生咨询计数。
- 同一个 `shareId` 下的打开、资料点击和咨询能在 analytics 中看到。
- 未发布展示页不能记录事件。
- 非 owner 不能查看 analytics。
- 匿名访客只显示匿名，不显示成实名客户。

## 7. 开发顺序

1. 扩展 ShowcaseEvent 数据字段和接口请求。
2. 修改展示页分享路径，生成并携带 `shareId`。
3. 公开展示页记录事件时带上分享来源。
4. analytics 和经营看板聚合分享来源。
5. 补后端测试和小程序静态检查。
6. 部署生产后端，并由用户上传小程序体验版真机回归。
