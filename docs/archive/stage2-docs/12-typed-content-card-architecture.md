# 资料整理助手：多类型资料卡与结构化业务信息架构

更新时间：2026-06-18

## 1. 核心结论

资料整理助手不是单一笔记工具，而是多类型信息结构化系统。

统一的是用户流程：

```text
收藏 -> 编辑 -> 整理 -> 生成
```

不统一的是数据结构和行为能力：

- URL / 公众号文章：链接卡 / 阅读卡。
- 微信笔记 / 普通文字：文本卡。
- 房源信息：字段卡。
- 团购信息：商品卡。
- 图片 / 截图：OCR 卡。

产品原则：

```text
UI 流程统一，数据结构分型，行为能力按场景区分。
```

## 2. 和强标签体系的关系

`docs/stage2-docs/11-tag-topic-search-architecture.md` 继续有效。

多类型资料卡不替代“强标签、弱分类、专题聚合”，而是在单条资料内部增加 `cardType` 和 `structuredData`：

- `sourceType`：来源类型，类似微信收藏的基础类型，例如笔记、链接、图片与视频、聊天记录、文件、小程序。
- `systemCategory`：系统弱分类，例如文章、房源、团购、图片、文件、待整理。
- `tags`：核心组织方式，用于搜索、筛选、召回。
- `topics`：用户行为集合，用于长期场景聚合。
- `cardType`：资料卡结构类型，决定编辑表单和整理/生成能力。

分类仍弱化，标签仍强化，专题仍替代多级文件夹。

## 3. 第一版数据形态

第一版不新建房源表或团购表，继续用 `UserNote` 作为统一容器，在 `visibilityConfig` 里扩展：

```json
{
  "contentMode": "structured_card",
  "cardType": "property_listing",
  "cardState": "collected",
  "sourceType": "note",
  "systemCategory": "房源",
  "tags": ["房产", "房源"],
  "tagLevels": {
    "rule": ["房产", "房源"],
    "light": [],
    "deep": []
  },
  "structuredData": {
    "community": "碧桂园城市之光1栋1210",
    "layout": "公寓一房",
    "price": "1600元/月",
    "utilities": "自缴",
    "businessArea": "万家丽、高桥北",
    "address": "",
    "serviceFee": "服务费200",
    "remark": "",
    "contact": "",
    "images": []
  },
  "conversionConfig": {
    "showContactPhone": true,
    "enableLightScrm": true,
    "collectLeads": true,
    "enableAppointment": true,
    "enablePrivateConsultation": true,
    "enableSharePoster": true,
    "enableGroupRelay": false,
    "enablePaymentPlaceholder": false
  },
  "typeSuggestions": []
}
```

`cardState` 取值：

- `collected`：收藏态，先保存成功，不阻塞。
- `editing`：编辑态，用户人工修正字段、标签、专题。
- `organized`：整理态，系统完成规则整理或后续 AI 增强。
- `generated`：生成态，已生成海报、图文页、话术等可直接使用结果。

`conversionConfig` 是第二态到第四态的转化能力配置，不属于房源/商品本体字段：

- `showContactPhone`：生成页是否展示联系电话。
- `enableLightScrm`：是否记录浏览、收藏、咨询、预约、接龙等轻 SCRM 行为。
- `collectLeads`：是否允许用户提交联系方式和备注。
- `enableAppointment`：房源是否展示预约看房。
- `enablePrivateConsultation`：房源是否展示私聊咨询。
- `enableSharePoster`：是否保留生成海报入口。
- `enableGroupRelay`：团购是否展示接龙/报名入口。
- `enablePaymentPlaceholder`：团购是否展示“下单按钮预留”；当前不接真实支付。

## 4. 类型识别规则

第一版只做规则识别，不调用大模型。

识别原则：

- URL 默认进入链接卡，不自动转房源或团购。
- 房源字段命中足够多时，进入 `property_listing`。
- 团购字段命中足够多时，进入 `groupbuy_product`。
- 低置信时仍保存为 `text_note`，并在 `typeSuggestions` 里提示“可能是房源 / 团购”。
- 规则失败不影响收藏成功。

房源关键词：

```text
小区、户型、价格、租金、水电、物业、商圈、区域、地址、位置、服务费、公寓、一房、两房、三房
```

团购关键词：

```text
团购、拼单、商品、规格、价格、包邮、自提、接龙、截止、库存、取货、配送、现摘、现发
```

## 5. 卡片行为

### 链接卡 / 阅读卡

收藏态只保存标题、封面、来源、链接、摘要、标签和专题。

用户点击卡片默认打开原文；普通网页受小程序限制时复制链接。

点击“整理”后升级为阅读卡 / 文章摘要卡，不默认转房源或团购。

### 房源字段卡

字段包括：

- 小区 / 标题
- 户型
- 价格 / 租金
- 水电物业
- 商圈 / 区域
- 地址 / 位置
- 服务费
- 备注
- 图片
- 联系方式

整理态只做字段标准化、摘要、标签和生成建议，不直接生成最终海报。

编辑态到生成态允许配置：

- 是否展示联系电话。
- 是否开启轻 SCRM 跟进。
- 是否收集线索。
- 是否允许预约看房。
- 是否允许私聊咨询。
- 是否保留生成海报入口。

可生成能力预留：

- 房源推广图
- 微信群文案
- 客户话术
- 对比表

### 团购商品卡

字段包括：

- 商品名
- 价格
- 规格
- 截止时间
- 自提 / 配送方式
- 取货地点
- 联系方式
- 库存或数量备注
- 图片

整理态只做商品字段标准化、摘要、标签和生成建议，不直接开团或交易。

编辑态到生成态允许配置：

- 是否展示联系电话。
- 是否开启轻 SCRM 跟进。
- 是否收集线索。
- 是否开启团购接龙。
- 是否保留生成海报入口。
- 是否展示“下单按钮预留”；当前不接真实支付。

可生成能力预留：

- 团购海报
- 发群文案
- 接龙格式
- 商品卖点

### 图片 / OCR 卡

第一版只保留图片资料卡位置。

后续流程：

```text
图片 -> OCR 文本 -> 类型识别 -> 文本卡 / 房源卡 / 团购卡
```

## 6. Skill 边界

新增逻辑属于 `content-to-note` 内部的结构识别层，不新增重复 Skill。

推荐边界：

- `content-type-router`：判断资料卡类型。
- `structure-to-card`：把半结构化文本转成 typed `UserNote`。
- `content-to-note`：继续负责文本 / 链接 / 聊天等内容入库。
- 场景生成 Skill：后续负责房源推广图、团购海报、群文案等。

大模型仍不是前提：

- 收藏态不等 AI。
- 规则识别先跑。
- 用户点击“整理”或“生成”后，才允许进入更高成本模型能力。
- 模型输出必须结构化校验，不能直接覆盖用户手改字段。

## 7. 验收标准

- 普通 URL 入库仍是链接卡。
- 房源文本能识别为 `property_listing`，并提取小区、户型、价格、商圈、备注、图片。
- 团购文本能识别为 `groupbuy_product`，并提取商品名、价格、规格、自提 / 配送、截止时间。
- 识别不确定时资料仍可收藏成功。
- 用户编辑结构化字段后，标签、专题、图片和来源不丢失。
- 搜索能命中结构化字段，例如小区、商圈、商品规格。
- 用户手改字段不得被后续规则整理静默覆盖。
- 生成海报、推广图、接龙格式属于后续 Skill，不在第一版强行完成。
