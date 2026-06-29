# 电子名片与服务方案卡 V1

更新时间：2026-06-22

## 1. 目标

在现有资料库里新增两类可运营资料卡：

- `business_card`：个人顾问电子名片。
- `service_offer`：非标准销售 / 服务方案卡。

两类都继续复用 `UserNote + structuredData + conversionConfig + CustomerAction + LeadReminder`，不另起 SCRM 系统。

## 2. 产品边界

- 电子名片第一版面向个人顾问，不做门店团队和企业品牌主页。
- 服务方案第一版面向服务销售，不做 SKU、支付、库存、核销和正式订单。
- 两类资料先通过明确入口创建，不加入自动识别规则。
- 客户动作默认是电话咨询、微信咨询、留下电话/微信、预约沟通和站内留言。

## 3. 字段结构

### 电子名片 `business_card`

- `name`：姓名。
- `title`：职位 / 身份。
- `company`：公司 / 门店。
- `serviceScope`：服务范围。
- `headline`：一句话介绍。
- `bio`：个人介绍。
- `phone`：电话。
- `wechat`：微信。
- `city`：城市 / 服务区域。
- `avatarUrl`：头像。
- `qrCodeUrl`：二维码 / 微信图片。
- `images`：补充图片。

### 服务方案 `service_offer`

- `serviceName`：服务名称。
- `headline`：一句话卖点。
- `targetAudience`：适合人群。
- `serviceContent`：服务内容。
- `pricingNote`：价格 / 报价说明。
- `serviceProcess`：服务流程。
- `caseHighlights`：案例 / 成果。
- `serviceArea`：服务地区。
- `phone`：电话。
- `wechat`：微信。
- `email`：邮箱。
- `website`：公司网址 / 介绍链接。
- `contact`：兼容旧数据的联系方式。
- `appointmentNote`：预约说明。
- `images`：案例图片。

## 4. UI 原型

黑白线框保存在：

- `docs/png/business-card-edit-wireframe.svg`
- `docs/png/business-card-preview-wireframe.svg`
- `docs/png/service-offer-edit-wireframe.svg`
- `docs/png/service-offer-preview-wireframe.svg`

开发验收时必须对照这些结构检查：顶部主体、核心字段、转化动作、图片 / 二维码、保存和客户页预览入口。

## 5. 验收标准

- 可以从添加入口创建空白电子名片和服务方案。
- 电子名片能从用户资料带入昵称、头像、电话。
- 两类资料在资料库显示为“名片 / 服务”，并可筛选。
- 编辑页保存后不丢字段、头像、图片和联系方式。
- 客户页不展示商品 SKU、团购接龙和房源地图。
- 客户页支持电话咨询、微信咨询、留资、预约沟通和站内留言。
- 留资和预约进入客户动作与待联系线索。

## 6. 模板库 V1

本阶段把“填写资料”前置改成“先选模板，再改内容”。模板配置保存在 `miniprogram/utils/sales-page-templates.js`，模板选择页为 `miniprogram/pages/sales-template-select/index`。

模板总览图保存在：

- `docs/png/business-card-service-offer-template-library.svg`

第一批 8 个模板按业务场景组织，不按单纯颜色皮肤组织：

### 电子名片

- 专业顾问：适合房产、保险、咨询、顾问，重点突出专业身份、服务范围和联系方式。
- 门店名片：适合门店、本地生活、美业、装修，重点突出门店、同城服务和预约入口。
- 专家介绍：适合课程、陪跑、知识服务，重点突出擅长领域、方法和成果背书。
- 简洁微信风：适合快速转发，重点像微信个人页一样突出“人”和联系方式。

### 服务方案

- 咨询预约：适合一对一咨询、课程、陪跑，重点突出适合谁、解决什么和预约沟通。
- 服务报价：适合装修、设计、财税、企业服务，重点突出服务范围、报价方式和交付流程。
- 案例背书：适合需要展示成果的服务，重点突出案例、过程和客户反馈。
- 活动招募：适合体验课、团体服务、短期活动，重点突出时间、名额、适合人群和报名咨询。

## 7. 后续模板增强方向

- 当前缩略图是小程序 CSS 结构预览，先解决“选哪个模板”的决策入口。
- 客户页已接入模板化展示：电子名片突出人、身份、服务标签和联系方式；服务方案突出服务标题、卖点、适合对象、流程、报价、案例和行动按钮。
- 不同模板已经能影响客户页 tone、顶部结构和关键模块呈现；后续可继续做更高保真视觉、行业专属插图和封面组件。
- 模板库后续可以继续增加行业包，例如房产顾问、装修设计师、家政阿姨、保险顾问、课程老师、美业顾问、企业服务顾问。
- 模板不要只做换色皮肤，每个模板必须对应明确销售场景、默认文案、模块顺序和客户动作重点。

## 8. 服务方案销售页 V1 落地

2026-06-22 已新增独立服务方案工作台 `miniprogram/pages/service-offer-studio`：

- 创建路径：添加页“服务方案”直接进入工作台，旧模板选择页选择服务方案时也跳转到工作台。
- 编辑路径：已有 `service_offer` 在笔记编辑页通过“设置方案样式”进入。
- 工作台流程：选风格、填方案、确认效果；同一份内容可切换 4 种模板。
- 客户页：`pages/note-preview` 中 `service_offer` 走专属服务销售页结构，不复用商品 SKU、团购接龙、房源地图或电子名片人设模块。
- 转化：电话、微信、邮箱按字段动态显示；留资、预约、站内留言继续复用 `CustomerAction -> LeadReminder`。
