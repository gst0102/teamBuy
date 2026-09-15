# teamBuy 阶段性交接归档 7

更新时间：2026-06-22
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`
当前分支：`main`，本地 `ahead 18`，存在大量未提交改动和未跟踪文件。
重要提醒：小程序上传体验版/正式版默认由用户在微信开发者工具手动完成，Codex 不要反复尝试调用微信开发者工具 CLI。

## 1. 项目背景与目标

当前产品正式方向是“资料整理助手”。

核心目标：

- 帮房产中介、团购/电商团长等用户，把企业微信、小程序、微信笔记、图片、手动输入等来源的内容迁移到统一笔记库。
- 统一保存为 `UserNote`，再按资料类型展示为普通笔记、房源、商品团购、图片资料、链接/文章等 typed card。
- 对房源和商品资料提供可运营能力：展示页、客户打开追踪、资料点击、电话咨询、复制微信、留资、预约、接龙/下单、经营看板和客户处理闭环。
- 普通笔记保持极简，不强行进入复杂房源/商品工作台；只有高置信识别为业务资料时，才提示并引导整理成房源或商品草稿。

长期架构原则以 `AGENTS.md` 和 `docs/stage2-docs/08-plugin-architecture.md` 为准：

- 稳定基座负责企业微信通信、内容存档、用户身份、笔记库、展示页、经营看板、支付/权益等。
- Skill 只做具体内容处理能力。
- 文字类来源统一抽象为 `ContentObject`，统一进入 `content-to-note`。
- 不新增房源表/商品表，第一阶段继续使用 `UserNote.visibilityConfig.cardType/structuredData/conversionConfig`。
- 用户身份锚点是小程序微信 `openid`；`userId` 是后端内部主键。

## 2. 当前阶段目标

当前阶段正在收口 MVP 后半段，重点不是继续做大功能，而是把“迁移 -> 整理 -> 分享 -> 客户打开 -> 经营看板 -> 具体人处理”的闭环打磨到真机可验收。

本阶段目标：

- 迁移链路：企业微信、手动文字、图片资料、普通笔记都能稳定进入笔记库。
- 业务识别：高置信房源/商品自动进入对应工作台；中置信提供确认；低置信保留普通笔记。
- 普通笔记：只进入轻量可编辑笔记器，不默认展示复杂运营工作台。
- 展示页：能发布、分享、客户打开，公开页读取发布快照。
- 分享追踪：能看到真实分享批次、客户打开、资料点击、电话咨询、复制微信。
- 经营闭环：经营看板、客户库、待联系、订单/接龙能落到具体客户/买家，并支持外呼、复制微信、进入业务详情。
- UI 收口：真机上按钮、标签、数量胶囊、头像兜底、列表操作区不变形；所有核心尺寸默认用 `rpx`。

## 3. 已完成的功能

### 3.1 Typed Card 与笔记库基座

- 已实现 `UserNote` typed card 架构，支持 `property_listing`、`groupbuy_product`、`text_note`、`image_ocr`、`link/article` 等类型。
- 后端 `content-to-note` 支持房源、商品团购、普通文本、链接/文章、图片资料等规则整理。
- 房源字段包括小区、户型、价格、水电物业、商圈、地址、服务费、备注、联系方式、图片等。
- 商品字段包括商品名、价格、规格、SKU、截止时间、自提/配送、取货地点、库存备注、联系方式、图片等。
- `conversionConfig` 支持电话、轻 CRM、留资、预约、私聊咨询、团购接龙、下单等配置。
- 老 Card/资源详情未物理删除，但 owner 侧入口优先跳到新 `UserNote` 工作台。

### 3.2 企业微信/手动/图片迁移

- 企业微信文本、微信笔记、小程序卡片、图片资料等统一沉淀为 `UserNote`。
- 贝壳小程序卡片已作为 `sourceType=miniapp` 保存，不自动高置信生成房源；保留 `houseCode/pagePath/webUrl`。
- 手动添加入口已从多步骤选择页收敛为极简“放进笔记库”笔记器：
  - 普通文字低置信直接保存普通笔记。
  - 高置信房源/团购文案保存为对应业务草稿，并用方案 B 提示“已帮你整理成房源/商品草稿”。
  - 图片按钮在笔记器中只保存图片资料，不强制 OCR；图片详情页保留“识别图片文字”按钮，用户主动触发 OCR。
- 后端新增/使用 `POST /api/notes/manual-draft`、`POST /api/notes/quick-capture`、图片保存/识别接口。
- 已处理 emoji 入库问题，引入文本安全/编码相关保护，避免普通文字带 emoji 保存失败。

### 3.3 普通笔记体验

- 普通笔记无业务候选时显示“普通笔记”，不计入“待处理/待整理”。
- 进入 `note-edit` 时默认只显示轻量笔记编辑：标题、摘要、正文、保存/删除。
- 仅通过小按钮 `扩展为可运营资料` 才展开功能组、标签、专题等运营能力。
- “我的笔记”新增显式分类：`全部 / 普通笔记 / 房源 / 商品团购`。
- 普通笔记筛选按 `text_note` 且无房源/团购候选本地过滤。

### 3.4 展示页构建与分享

- 展示页构建器 V1 已实现：
  - 资料选择区可列表/双列卡片切换。
  - 展示页默认模板为 `featured_window`。
  - 支持四套模板参考方向：精选橱窗、朋友圈长页、清单目录、品牌名片。
  - 展示页保存时按分类兜底生成名称、简介、分享标题、联系文案。
  - 不再向用户暴露复杂“展示方式”入口，前期固定按标签/默认结构组织。
- 展示页发布时生成 `publicSnapshot`，公开页优先读发布快照。
- 删除资料时同步修剪相关展示页快照，避免已删除资料继续出现在客户页。
- 展示页列表卡片操作区已减负：已发布常驻 `发给客户 + 更多`，草稿/下架常驻 `编辑 + 更多`。

### 3.5 分享追踪 V1 与经营看板

- 展示页分享路径带 `shareId/sid/from/scene/ref`，用于真实分享批次追踪。
- 客户打开展示页、点击资料、电话咨询、复制微信都会记录事件。
- 后端新增/使用经营看板聚合接口 `GET /api/dashboard/business?ownerUserId=...`。
- 经营看板包括：
  - 顶部总数：打开、访客、看资料、咨询。
  - 按展示页拆解。
  - 分享来源/分享批次。
  - 资料点击排行。
  - 访客详情/客户资料/动作流水。
- “资料点击排行”点击后默认下钻到点过这条资料的具体访客。
- 访客列表点击后先打开页内客户详情处理卡，展示来源、看过资料、分享批次、电话、微信、动作入口。
- 用户已真机确认经营看板/客户详情/头像等核心信息“都能看到了”，经营闭环 P0 可关闭；仍需新体验版继续验收后续 UI 小优化。

### 3.6 客户库、待联系、订单/接龙处理链路

- 客户库：
  - 支持阶段、来源、意向、标签、搜索等筛选。
  - 点击客户头像/姓名区域先打开客户详情处理卡。
  - 详情卡展示阶段、意向、联系方式、来源资料、最近查看、最近跟进、订单状态、标签。
  - 原外呼、复制微信、订单、跟进等快操作保留。
- 待联系：
  - 支持状态、来源、时间筛选。
  - 点击线索头像/姓名区域先打开线索详情处理卡。
  - 详情卡展示状态、来源、查看次数、电话、微信、备注、最近跟进、归档原因。
- 订单/接龙：
  - 商家订单中心支持状态和来源商品拆解。
  - 点击订单卡后先打开买家订单处理卡。
  - 处理卡展示买家、来源商品、规格/数量、类型、备注、地址、电话、微信。
  - 商家侧可外呼、复制微信、查看订单或立即处理。
- “我的”页主入口已收敛：不再放访客线索/待联系/客户库主入口，保留经营看板和订单入口；客户库/待联系底层页面暂不删除。

### 3.7 头像与个人资料

- 后端新增 `PATCH /api/auth/users/{user_id}/profile`，支持昵称、手机号、头像保存。
- 小程序“我的 -> 编辑资料/设置中心”支持选择头像、昵称、手机号。
- 头像规则已收紧：
  - 后端只接受稳定 HTTPS 头像。
  - 小程序过滤空头像、`example.com`、`avatar-default`、本地临时路径、非 HTTPS。
  - 无效头像统一显示彩色首字兜底。
- 已扩大头像兜底覆盖到首页访客、访客线索、资源管理页、经营看板、客户库、待联系、订单、展示页列表、展示页公开页、资料动作页、消息页、接龙名单等。
- “我的”页已把 `编辑资料` 和 `退出登录` 移到头像昵称下方，底部退出按钮删除。
- 编辑资料弹窗已去掉“头像链接”输入，只保留选择头像、昵称、手机号。

### 3.8 UI 与项目规则

- `AGENTS.md` 已新增：
  - UI 参考稿必须作为验收标准。
  - 小程序按钮/标签必须 flex 居中，重置原生 button 默认样式。
  - 小程序核心尺寸默认用 `rpx`，统计数字、头像、按钮、宫格、数量胶囊必须显式 `rpx` 尺寸。
- “我的笔记”顶部“保存图片”入口已删除。
- “最近迁入 X 条待处理”点击后整卡变绿色选中态，避免只看到条数变化。
- 蓝色数量胶囊改为显式 `rpx` 字号 + flex 居中，适配 iPad/大屏。

### 3.9 生产部署与验证

- 经营看板相关后端已多次部署到生产 `https://teambuy.lifelove.top`。
- 生产服务器信息在 `AGENTS.md`：
  - IP `81.70.84.35`
  - user `ubuntu`
  - project dir `/home/ubuntu/teamBuy`
  - domain `https://teambuy.lifelove.top`
  - ssh key `/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`
- 已知生产部署注意：
  - 后端在 Docker 镜像内，单纯 `scp + restart` 不生效；需要 `docker compose build backend && docker compose up -d backend`。
  - 不要覆盖生产 `.env`、`backend/secrets/`、媒体目录和运行态数据。
  - 不要执行 destructive prune，除非用户明确确认。

## 4. 已修改/新增的文件

当前 `git status` 显示工作区很脏，且包含多轮连续开发成果。不要随意回滚任何未确认改动。

### 4.1 后端已修改文件

- `backend/app/api/routes_auth.py`
- `backend/app/api/routes_notes.py`
- `backend/app/api/routes_showcases.py`
- `backend/app/core/config.py`
- `backend/app/core/schema.sql`
- `backend/app/main.py`
- `backend/app/models/domain.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/cards.py`
- `backend/app/schemas/notes.py`
- `backend/app/schemas/showcases.py`
- `backend/app/services/app_service.py`
- `backend/app/services/repository.py`
- `backend/app/services/skill_router_service.py`
- `backend/tests/test_app.py`
- `backend/tests/test_postgres_repository_schema.py`

### 4.2 后端新增文件

- `backend/app/api/routes_dashboard.py`
- `backend/app/services/text_safety.py`

### 4.3 小程序已修改文件

- `miniprogram/app.json`
- `miniprogram/app.wxss`
- `miniprogram/services/api.js`
- `miniprogram/utils/dashboard.js`
- `miniprogram/project.config.json`
- `miniprogram/components/relay-list/index.js`
- `miniprogram/components/relay-list/index.wxml`
- `miniprogram/components/relay-list/index.wxss`
- `miniprogram/pages/card-view/index.js`
- `miniprogram/pages/customers/index.js`
- `miniprogram/pages/customers/index.wxml`
- `miniprogram/pages/customers/index.wxss`
- `miniprogram/pages/home/index.wxml`
- `miniprogram/pages/home/index.wxss`
- `miniprogram/pages/leads/index.js`
- `miniprogram/pages/leads/index.wxml`
- `miniprogram/pages/leads/index.wxss`
- `miniprogram/pages/login/index.js`
- `miniprogram/pages/manager/index.js`
- `miniprogram/pages/manager/index.wxml`
- `miniprogram/pages/manager/index.wxss`
- `miniprogram/pages/message-thread/index.js`
- `miniprogram/pages/note-actions/index.js`
- `miniprogram/pages/note-actions/index.wxml`
- `miniprogram/pages/note-actions/index.wxss`
- `miniprogram/pages/note-edit/index.js`
- `miniprogram/pages/note-edit/index.wxml`
- `miniprogram/pages/note-edit/index.wxss`
- `miniprogram/pages/note-preview/index.js`
- `miniprogram/pages/notes/index.js`
- `miniprogram/pages/notes/index.wxml`
- `miniprogram/pages/notes/index.wxss`
- `miniprogram/pages/order-detail/index.js`
- `miniprogram/pages/order-detail/index.wxml`
- `miniprogram/pages/order-detail/index.wxss`
- `miniprogram/pages/orders/index.js`
- `miniprogram/pages/orders/index.wxml`
- `miniprogram/pages/orders/index.wxss`
- `miniprogram/pages/profile/index.js`
- `miniprogram/pages/profile/index.wxml`
- `miniprogram/pages/profile/index.wxss`
- `miniprogram/pages/resource-create/index.js`
- `miniprogram/pages/resource-create/index.wxml`
- `miniprogram/pages/resource-create/index.wxss`
- `miniprogram/pages/showcase-edit/index.js`
- `miniprogram/pages/showcase-edit/index.json`
- `miniprogram/pages/showcase-edit/index.wxml`
- `miniprogram/pages/showcase-edit/index.wxss`
- `miniprogram/pages/showcase-view/index.js`
- `miniprogram/pages/showcase-view/index.wxml`
- `miniprogram/pages/showcase-view/index.wxss`
- `miniprogram/pages/showcases/index.js`
- `miniprogram/pages/showcases/index.wxml`
- `miniprogram/pages/showcases/index.wxss`
- `miniprogram/pages/visits/index.js`
- `miniprogram/pages/visits/index.wxml`
- `miniprogram/pages/visits/index.wxss`

### 4.4 小程序新增文件

- `miniprogram/components/business-dashboard/index.js`
- `miniprogram/components/business-dashboard/index.json`
- `miniprogram/components/business-dashboard/index.wxml`
- `miniprogram/components/business-dashboard/index.wxss`
- `miniprogram/components/note-select-card/index.js`
- `miniprogram/components/note-select-card/index.json`
- `miniprogram/components/note-select-card/index.wxml`
- `miniprogram/components/note-select-card/index.wxss`
- `miniprogram/pages/business-dashboard/index.js`
- `miniprogram/pages/business-dashboard/index.json`
- `miniprogram/pages/business-dashboard/index.wxml`
- `miniprogram/pages/business-dashboard/index.wxss`
- `miniprogram/pages/showcase-analytics/index.js`
- `miniprogram/pages/showcase-analytics/index.json`
- `miniprogram/pages/showcase-analytics/index.wxml`
- `miniprogram/pages/showcase-analytics/index.wxss`
- `miniprogram/pages/showcase-share/index.js`
- `miniprogram/pages/showcase-share/index.json`
- `miniprogram/pages/showcase-share/index.wxml`
- `miniprogram/pages/showcase-share/index.wxss`
- `miniprogram/utils/note-display.js`
- `miniprogram/utils/showcase-templates.js`

### 4.5 文档已修改文件

- `AGENTS.md`
- `docs/decisions.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/pitfalls.md`
- `docs/stage2-docs/13-showcase-builder-v1.md`
- `docs/qa/展示页构建器V1_测试清单与验收标准.md`

### 4.6 文档/资产新增文件

- `docs/handoff-latest-6.md`
- `docs/handoff-latest-7.md`
- `docs/deploy/dashboard-closeout-server-commands.sh`
- `docs/stage2-docs/14-customer-data-dashboard-architecture.md`
- `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
- `docs/png/showcase-template-00-all.png`
- `docs/png/showcase-template-01-featured-window.png`
- `docs/png/showcase-template-02-moments-story.png`
- `docs/png/showcase-template-03-catalog-list.png`
- `docs/png/showcase-template-04-brand-card.png`
- `docs/png/showcase-template-mockups.html`
- `docs/qa/上线闭环与真实分享追踪V1_Codex自测报告.md`
- `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`
- `docs/qa/客户数据看板_Codex自测报告.md`
- `docs/qa/客户数据看板_上线部署与回归清单.md`
- `docs/qa/客户数据看板_复测与回归报告.md`
- `docs/qa/客户数据看板_测试清单与验收标准.md`
- `docs/qa/客户数据看板_验收报告.md`
- `docs/qa/当前项目_验收报告m2.md`
- `docs/qa/经营闭环头像与处理链路_Codex自测报告.md`
- `docs/qa/经营闭环头像与处理链路_真机回归清单.md`
- `docs/qa/经营闭环头像与处理链路_真机验收记录模板.md`
- `docs/qa/经营闭环头像与处理链路_验收报告.md`
- `docs/qa/迁移链路小收口V1_测试清单与验收标准.md`

### 4.7 不要误处理的文件

- `miniprogram/project.config.json` 有微信开发者工具自动改动，除非明确需要，不要随意回滚或纳入无关提交。
- 未跟踪 PDF `企业微信客服服务须知.pdf` 不属于当前代码功能，未纳入交付判断。

## 5. 当前代码状态

最新状态：

- `main...origin/main [ahead 18]`
- 工作区有大量 modified/untracked 文件，属于多轮连续功能开发结果。
- 最近一次静态验证通过：
  - 小程序全量 JS：`find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`
  - 小程序 JSON 解析：通过
  - `git diff --check`：通过
- 近期多次后端测试曾通过：
  - 经营闭环阶段后端全量测试曾到 `131 passed`。
  - 后续有些小程序 UI 收口未重新跑后端全量测试，因为不涉及后端。
- 生产后端已有多次部署，`/health` 曾验证正常；但本地未提交不等于线上已生效，凡涉及后端新改动仍需部署。
- 小程序前端改动必须由用户重新上传体验版/正式版后，真机才能看到。

本次交接文件生成前只做了读取状态和写文档，没有改业务代码。

## 6. 已知问题和风险

### 6.1 真机版本风险

- 用户多次真机问题都和“体验版不是最新代码”或“另一个微信不是体验成员/登录态”有关。
- 新小程序前端改动不会自动生效，必须用户在微信开发者工具上传体验版。
- 分享打不开时，先查小程序版本、体验成员、分享路径参数、公开接口是否 200，不要先乱改后端。

### 6.2 工作区过脏风险

- 当前本地改动跨后端、小程序、文档、测试、未跟踪资产，范围很大。
- 新 Codex 接手前必须先 `git status --short --branch` 和 `git diff --stat`，不要误回滚用户或前序 Codex 的改动。
- 如要提交，建议按功能拆分提交，排除 `miniprogram/project.config.json` 和无关 PDF。

### 6.3 生产部署风险

- 后端代码改完不等于线上生效。
- Docker 后端必须重建镜像，单纯重启容器不一定加载新代码。
- 生产服务器磁盘可能接近满盘，部署前先查 `df -h` 和 `docker system df`。
- 不要覆盖生产 `.env`、`backend/secrets/`、媒体目录和运行态数据。

### 6.4 客户库/待联系去留风险

- “我的”页已经隐藏访客线索、待联系、客户库主入口。
- 但客户库/待联系底层页面暂不删除，因为经营看板下钻、历史路径、客户档案能力仍可能依赖。
- 若后续确认废弃，必须单独做依赖扫描后再删路由/代码/接口。

### 6.5 头像风险

- 微信登录不天然给头像昵称；没有真实头像时必须用彩色文字兜底。
- 不要再写入 `example.com`、`avatar-default`、`wxfile://`、`/tmp` 等头像。
- 真机白头像如果再出现，先记录页面名、客户/用户、接口返回头像字段，再查渲染过滤。

### 6.6 UI 验收风险

- 用户非常在意参考图一致性和真机视觉。
- 有参考图的页面不能只说“功能可用”；必须对照头像、统计卡、列表、按钮、空态、底部操作等。
- 小程序按钮/标签/数量必须 flex 居中，核心尺寸用 `rpx`。

## 7. 用户已经确认过的产品/技术决策

- 产品名和方向：资料整理助手，主价值是资料迁移和经营闭环，不是纯笔记 App。
- 数据模型：房源、商品、普通笔记、图片资料等统一保存为 `UserNote`；首版不新增房源表/商品表。
- 手动新建：不做复杂多页表单，使用极简随手记/粘贴文案入口，高置信自动分流到房源/商品草稿。
- 业务提示：采用方案 B，高置信识别后在页面内弹出“已帮你整理成房源/商品草稿”类提示，不强制跳转。
- 普通笔记：没有进入业务场景时，只显示轻量笔记器；可以有小按钮扩展为可运营资料。
- 图片资料：笔记器里传图片只保存原图，不自动 OCR；图片资料详情页提供主动“识别图片文字”。
- 展示页分享：用 `shareId/sid` 追踪真实分享批次，第一版不建单独分享批次表。
- 展示页公开页：必须读取发布快照 `publicSnapshot`，保证客户页稳定。
- 经营看板：作为主经营入口；用户自己的客户手机号/微信不脱敏，支持外呼和复制。
- 经营处理心智：总览/来源/状态 -> 具体人 -> 处理卡 -> 外呼/复制/业务详情。
- 客户库和待联系：底层能力暂保留，但不作为“我的”页主入口。
- 头像规则：只接受稳定 HTTPS；无效头像统一彩色文字兜底。
- 小程序上传：用户手动上传体验版/正式版，Codex 默认不调用微信开发者工具 CLI。
- UI 规则：参考图是验收标准；按钮、标签、数量胶囊必须居中；核心尺寸用 `rpx`。

## 8. 下一步建议执行顺序

1. **先做交接后首轮体检**
   - 读取 `AGENTS.md`、`docs/project-memory.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/dev-log.md`、`docs/handoff-latest-7.md`。
   - 执行 `git status --short --branch` 和 `git diff --stat`。
   - 明确本轮只做用户指定任务，不顺手改大范围代码。

2. **上传最新版小程序体验版后真机验收**
   - 重点验收“我的笔记”：普通笔记分类、迁入待处理绿色态、顶部保存图片按钮消失、数量胶囊大屏比例。
   - 重点验收“我的”：编辑资料/退出登录在头像昵称下方、按钮不变形、头像链接输入消失、经营入口收敛。
   - 回归普通笔记详情：非业务普通笔记只显示轻量笔记器。
   - 回归房源/团购高置信分流提示和进入对应工作台。

3. **经营闭环真机回归**
   - 使用 `docs/qa/经营闭环头像与处理链路_真机回归清单.md`。
   - 检查展示页分享、另一个微信打开、点击资料、电话咨询、复制微信、经营看板分享来源。
   - 检查头像兜底、客户处理卡、客户库、待联系、订单/接龙。

4. **整理提交范围**
   - 当前工作区很大，建议按功能拆分提交：
     - 展示页构建/分享追踪。
     - 经营看板/客户闭环。
     - 手动添加/普通笔记/图片资料。
     - UI 小优化和文档。
   - 排除或单独处理 `miniprogram/project.config.json`。
   - 不提交无关 PDF，除非用户明确要求归档。

5. **如涉及后端新改动，再部署生产**
   - 部署前备份服务器文件。
   - 检查磁盘。
   - 重建 Docker 后端。
   - 公网验证 `/health` 和相关接口。
   - 再提醒用户上传小程序体验版。

6. **如用户继续要删客户库/待联系**
   - 先做依赖扫描：`app.json`、经营看板跳转、客户库跳转、待联系跳转、历史分享/页面路径、API 调用。
   - 输出删/藏/合并判断，不要直接物理删除。

## 9. 新 Codex 会话接手时的第一条提示词

```text
请先读取并遵守：
- AGENTS.md
- docs/project-memory.md
- docs/decisions.md
- docs/pitfalls.md
- docs/dev-log.md
- docs/handoff-latest-7.md

然后执行：
- git status --short --branch
- git diff --stat

先不要改代码。请先输出你理解的：
1. 项目目标
2. 当前阶段目标
3. 当前代码状态
4. 已确认的重要决策
5. 当前风险
6. 下一步建议执行顺序

注意：
- 当前工作区很脏，不能回滚未确认改动。
- 小程序上传体验版由用户手动完成，Codex 默认只做代码、静态检查、后端测试和必要部署提醒。
- 如果涉及 UI，请遵守参考图验收、按钮/标签 flex 居中、核心尺寸使用 rpx。
- 如果分享打不开，先查小程序版本、体验成员、分享路径参数和公开接口 200，不要先乱改后端。
- 如果处理“我的”页入口，不要物理删除客户库/待联系底层页面，除非先完成依赖扫描并得到用户确认。
```
