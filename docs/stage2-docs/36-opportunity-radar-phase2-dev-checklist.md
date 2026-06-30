# 商机线索二期开发任务清单 V1

更新时间：2026-06-30

## 1. 本文档目标

本文档用于把“资源工具 / 商机线索 / 供需广场 / 回应包 / 积分账本”拆成可交给开发 Codex 执行的二期任务。

相关产品文档：

```text
docs/stage2-docs/33-resource-tools-opportunity-radar-v1.md
docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md
docs/stage2-docs/35-response-package-monetization-v1.md
```

二期开发目标不是一次做完完整商业化，而是先把核心闭环跑通：

```text
线索入库
  ↓
用户看到高匹配机会
  ↓
用户保存 / 生成回应包
  ↓
回应包引用用户已有资料
  ↓
积分扣减和免费额度后端化
  ↓
雷达记录打开和跟进状态
```

## 2. 二期核心原则

### 2.1 先闭环，不堆功能

第一版不要做成大而全的需求平台。

优先跑通：

```text
少量高质量线索
少量高匹配推荐
少量可用回应包
清晰积分账本
可追踪跟进状态
```

### 2.2 资源工具不能孤立

资源工具必须和现有工作台打通。

正确关系：

```text
商机线索负责发现机会
工作台负责生成用户自己的成交素材
回应包负责把素材组合给具体机会
雷达负责追踪反馈
```

### 2.3 积分必须后端化

当前小程序本地积分只适合演示，不适合正式收费或开放资源工具。

二期 P0 必须把积分改为后端账本。

### 2.4 UI 不能做成功能版

商机线索是付费主线，必须按 `34` 号 UI 规格先做静态 UI，再接数据。

不得把页面退化成：

```text
普通列表
普通收藏夹
普通 AI 文案生成
普通黄页
```

## 3. P0 开发范围

P0 是二期必须做完才算核心闭环成立的范围。

### 3.1 后端积分账本

目标：

> 所有资源工具、企业查询、联系方式查看、回应包生成，都必须绑定真实用户并走后端积分账本。

必须实现：

- 用户积分余额后端存储。
- 积分流水后端记录。
- 免费额度后端记录。
- 同一用户跨设备、退出重登后积分不重置。
- 后台可查看和人工调整积分。
- 所有扣分接口必须绑定 `openid -> userId`。

建议数据表：

```text
resource_wallet
resource_point_ledger
resource_free_quota
resource_unlock_record
```

字段建议：

```text
resource_wallet:
  id
  user_id
  points_balance
  frozen_points
  created_at
  updated_at

resource_point_ledger:
  id
  user_id
  change_type
  points_delta
  balance_after
  biz_type
  biz_id
  reason
  operator_id
  created_at

resource_free_quota:
  id
  user_id
  quota_type
  period_key
  used_count
  limit_count
  created_at
  updated_at

resource_unlock_record:
  id
  user_id
  target_type
  target_id
  action_type
  points_cost
  free_quota_used
  expire_at
  created_at
```

P0 验收：

- 同一用户退出重新登录，积分不重置。
- 清理小程序缓存后重新登录，积分不重置。
- 不同用户积分隔离。
- 后台调整积分后，小程序能看到变化。
- 同一企业同一功能 24 小时内不重复扣分。
- 同一回应包重复打开不重复扣生成费用。

### 3.2 商机线索基础数据模型

目标：

> 平台可以录入、审核、展示、保存、匹配线索。

建议数据表：

```text
opportunity_lead
opportunity_lead_source
opportunity_lead_contact
opportunity_lead_match
opportunity_lead_save
opportunity_lead_followup
```

字段建议：

```text
opportunity_lead:
  id
  title
  summary
  city
  district
  industry
  demand_type
  content
  contact_status
  trust_status
  status
  expires_at
  created_at
  updated_at

opportunity_lead_source:
  id
  lead_id
  source_platform
  source_url
  source_author
  source_published_at
  source_captured_at
  raw_text
  raw_images

opportunity_lead_contact:
  id
  lead_id
  contact_type
  contact_value_encrypted
  contact_masked
  verify_status
  created_at

opportunity_lead_match:
  id
  lead_id
  user_id
  match_score
  match_reasons
  status
  created_at

opportunity_lead_save:
  id
  lead_id
  user_id
  status
  note
  reminder_at
  created_at
  updated_at

opportunity_lead_followup:
  id
  lead_id
  user_id
  action_type
  note
  created_at
```

P0 验收：

- 后台或脚本可录入线索。
- 小程序能展示官方收录线索。
- 前台不显眼展示微博、小红书等具体来源。
- 后台保留来源字段。
- 用户可保存线索。
- 用户可标记已联系、跟进中、无效。
- 线索联系方式默认受权限控制。

### 3.3 商机线索小程序页面

目标：

> 用户能在资源工具里进入商机线索，并看到“机会雷达”感。

P0 页面：

```text
资源工具入口
商机线索 / 我的机会
供需广场
线索详情
已保存
订阅雷达
```

P0 UI 要求：

- 我的机会必须有匹配度和雷达图。
- 供需广场必须区分“我要找”和“我能提供”。
- 线索详情必须突出 `生成回应包`。
- 已保存必须是跟进台，不是收藏夹。
- 订阅雷达要让用户配置“我在找 / 我能提供 / 城市 / 关键词”。

P0 验收：

- 先提供静态 UI 截图。
- 再接 mock 数据。
- 最后接真实接口。
- 提供真机截图。
- 说明与参考图一致和替代的地方。

### 3.4 回应包 P0

目标：

> 用户看到线索后，能用自己的已有资料生成一份可发送的回应包。

P0 功能：

- 从线索详情点击 `生成回应包`。
- 系统列出用户已有资料供选择。
- 默认推荐 1-3 个资料。
- 生成首次联系话术。
- 生成可追踪链接或预留追踪链接结构。
- 回应包保存到该线索的跟进记录。
- 已保存线索能看到是否已生成回应包。

建议数据表：

```text
response_package
response_package_item
response_package_event
```

字段见：

```text
docs/stage2-docs/35-response-package-monetization-v1.md
```

P0 验收：

- 回应包不能只是一段 AI 文案。
- 必须能看到推荐资料。
- 必须能看到推荐理由。
- 必须能复制话术。
- 必须记录生成次数和消耗。
- 用户未确认前不得自动联系对方。

### 3.5 免费额度与积分扣减

目标：

> 先建立收费口径，但不急着上线支付。

P0 建议规则：

```text
商机线索搜索 / 浏览：免费
线索摘要：免费
查看联系方式：20 分
生成回应包：免费额度内免费，超额 20 分
企业资源基础信息：10 分
企业深度功能：20 分
同用户同目标同功能 24 小时内不重复扣
```

回应包免费额度：

```text
新用户：5 次
普通用户：每月 3 次
```

P0 验收：

- 免费额度用完后才扣积分。
- 扣积分前有确认。
- 扣分失败不展示受限内容。
- 扣分成功后记录流水。
- 重复访问已解锁内容不重复扣。

### 3.6 PC 运营后台二期能力

目标：

> 运营能看数据、录入线索、处理供给、调整积分。

P0 后台功能：

- 今日新增用户。
- 今日资源工具使用人数。
- 今日积分消耗。
- 积分消耗排行。
- 用户积分查询和调整。
- 线索列表。
- 线索新增 / 编辑 / 下架。
- 供给卡审核。
- 举报 / 反馈处理。

P0 验收：

- 管理员操作必须有口令或权限。
- 积分调整必须写流水。
- 下架线索后小程序不可见。
- 审核供给卡后前台状态变化。

## 4. P1 开发范围

P1 是 P0 闭环稳定后增强体验和留存。

### 4.1 精准推送

- 根据订阅雷达生成每日匹配。
- 微信客服推送高匹配机会摘要。
- 免费用户每日最多 1 次。
- 付费用户可更高频或更精准。

验收：

- 可按用户订阅匹配。
- 连续不打开自动降频。
- 用户可关闭或修改订阅。

### 4.2 回应包雷达事件

- 打开记录。
- 联系方式点击记录。
- 保存记录。
- 跟进提醒。

验收：

- 用户能看到回应包是否被打开。
- 用户能看到下一步建议。
- 事件不泄露未授权访问者隐私。

### 4.3 我的发布

- 用户发布需求。
- 用户发布供给。
- 我的发布管理。
- 查看曝光、保存、申请联系。

验收：

- 发布供给必须绑定已有资料。
- 供给卡待审核前不进广场。
- 用户可编辑、下架。

## 5. P2 后置范围

这些不建议二期第一版就做。

```text
充值支付
会员订阅
保证金认证
双向收费
需求置顶
供给卡付费曝光
复杂争议处理
多平台自动爬虫全自动入库
AI 自动联系需求方
```

原因：

- 冷启动阶段先验证“线索 -> 回应包 -> 跟进”价值。
- 支付和保证金会增加合规、售后和争议处理压力。
- 自动联系容易带来骚扰风险。

## 6. 推荐开发顺序

### 第 1 步：后端积分账本

先把积分从本地缓存迁到后端。

原因：

- 后续所有资源工具都依赖积分。
- 不先做账本，后面收费逻辑都会返工。

### 第 2 步：商机线索数据模型和后台录入

先让后台能录入少量高质量线索。

原因：

- 前期内容不多，不需要复杂爬虫。
- 运营可先人工或半自动导入测试数据。

### 第 3 步：小程序静态 UI

先按 34 号文档还原页面。

原因：

- 商机线索付费感主要来自页面表达。
- 先做功能容易变成普通列表。

### 第 4 步：接 mock 数据和真实接口

从假数据切到真实数据。

顺序：

```text
我的机会
供需广场
线索详情
已保存
订阅雷达
```

### 第 5 步：回应包 P0

让用户从线索详情生成回应包。

原因：

- 这是成交助手的核心差异。
- 有回应包，线索才不是普通信息。

### 第 6 步：PC 后台增强

补齐运营需要的线索、积分、审核、反馈处理。

### 第 7 步：精准推送和雷达事件

等前面闭环稳定，再做推送和更细的雷达。

## 7. 接口清单建议

### 7.1 积分接口

```text
GET  /api/resource-wallet/me
POST /api/resource-wallet/consume
GET  /api/resource-wallet/ledger
POST /api/ops/resource-wallet/adjust
```

### 7.2 线索接口

```text
GET  /api/opportunities
GET  /api/opportunities/mine
GET  /api/opportunities/{id}
POST /api/opportunities/{id}/save
POST /api/opportunities/{id}/followup
POST /api/opportunities/{id}/unlock-contact
```

### 7.3 订阅接口

```text
GET  /api/opportunity-subscriptions/me
POST /api/opportunity-subscriptions
PUT  /api/opportunity-subscriptions/{id}
DELETE /api/opportunity-subscriptions/{id}
```

### 7.4 回应包接口

```text
POST /api/opportunities/{id}/response-packages/preview
POST /api/opportunities/{id}/response-packages
GET  /api/response-packages/{id}
POST /api/response-packages/{id}/events
```

### 7.5 供需广场接口

```text
GET  /api/supply-demand/cards
POST /api/supply-demand/cards
GET  /api/supply-demand/cards/me
PUT  /api/supply-demand/cards/{id}
POST /api/supply-demand/cards/{id}/submit
POST /api/ops/supply-demand/cards/{id}/review
```

### 7.6 运营后台接口

```text
GET  /api/ops/opportunities
POST /api/ops/opportunities
PUT  /api/ops/opportunities/{id}
POST /api/ops/opportunities/{id}/offline
GET  /api/ops/resource-wallet/users
POST /api/ops/resource-wallet/users/{user_id}/adjust
GET  /api/ops/opportunity-dashboard
```

## 8. 页面清单

### 8.1 小程序页面

```text
pages/profile/index
  资源工具区增加商机线索入口状态

pages/opportunity-radar/index
  我的机会

pages/opportunity-market/index
  供需广场

pages/opportunity-detail/index
  线索详情

pages/opportunity-saved/index
  已保存 / 跟进台

pages/opportunity-subscription/index
  订阅雷达

pages/response-package/index
  回应包生成

pages/response-package-radar/index
  回应包雷达

pages/supply-demand-publish/index
  发布需求 / 供给

pages/supply-demand-my/index
  我的发布
```

### 8.2 PC 运营后台页面

```text
/ops
  增加二期 Tab：
    商机线索
    供给审核
    积分账本
    回应包记录
    反馈举报
```

## 9. 测试清单

### 9.1 P0 测试

- 新用户登录后有初始积分。
- 退出重登积分不重置。
- 清缓存后积分不重置。
- 查看联系方式扣积分。
- 重复查看已解锁联系方式不重复扣。
- 回应包免费额度生效。
- 超过免费额度扣积分。
- 积分不足时不能生成付费回应包。
- 后台调整积分后前台同步。
- 保存线索后进入已保存。
- 线索状态可标记已联系、跟进中、无效。
- 线索下架后前台不可见。
- 回应包生成后可在跟进台看到。
- 回应包没有自动联系对方。

### 9.2 UI 测试

- 我的机会首屏有雷达图。
- 线索详情主按钮是 `生成回应包`。
- 供需广场能区分需求和供给。
- 已保存不是普通收藏夹。
- 按钮文字上下左右居中。
- 标签不异常换行。
- 真机截图通过。

### 9.3 权限测试

- 未登录不能解锁联系方式。
- 用户 A 不能看到用户 B 的已保存线索。
- 用户 A 不能查看用户 B 的回应包。
- 后台接口必须鉴权。
- 联系方式字段前台默认脱敏。

## 10. 开发 Codex 执行提示词

可复制给开发 Codex：

```text
请先读取 AGENTS.md、docs/project-memory.md、docs/decisions.md、docs/pitfalls.md、docs/dev-log.md、docs/handoff-latest.md，然后读取：

docs/stage2-docs/33-resource-tools-opportunity-radar-v1.md
docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md
docs/stage2-docs/35-response-package-monetization-v1.md
docs/stage2-docs/36-opportunity-radar-phase2-dev-checklist.md

再执行 git status --short --branch 和 git diff --stat。

本轮目标是商机线索二期开发。请不要一次性做完整商业化，优先按 36 号文档 P0 顺序推进：

1. 后端积分账本
2. 商机线索数据模型和后台录入
3. 小程序静态 UI
4. 接 mock 数据和真实接口
5. 回应包 P0
6. PC 后台增强

开发前先输出你理解的项目目标、当前代码状态、重要决策、当前风险、建议执行顺序。获得确认后再开发。
```

## 11. 第一版不做什么

明确不做：

- 不做自动私信。
- 不做自动批量联系。
- 不做保证金扣罚上线。
- 不做充值支付上线。
- 不做复杂会员权益。
- 不做全自动爬虫直接无审核入库。
- 不把第三方来源显眼展示给前台用户。

这些后续可以做，但不要挡住二期核心闭环。

## 12. 二期完成标准

二期 P0 完成后，用户应能完成这条链路：

```text
打开我的
  ↓
进入资源工具
  ↓
进入商机线索
  ↓
看到高匹配机会
  ↓
查看详情
  ↓
保存线索
  ↓
生成回应包
  ↓
选择自己的资料
  ↓
复制话术和链接
  ↓
回到已保存查看跟进状态
```

运营应能完成这条链路：

```text
后台录入线索
  ↓
审核 / 下架线索
  ↓
查看用户使用情况
  ↓
查看积分消耗
  ↓
人工调整积分
  ↓
处理举报和反馈
```

这两条链路跑通，二期才算真正成立。

