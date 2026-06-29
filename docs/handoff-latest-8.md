# teamBuy 阶段性交接归档 8

更新时间：2026-06-23
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`
当前分支：`main`
当前 Git 状态：本地 `ahead 18`，工作区很脏，存在大量已修改和未跟踪文件；不要随意回滚任何非本轮明确确认的改动。
重要约定：小程序体验版/正式版上传默认由用户在微信开发者工具手动完成，Codex 不要反复尝试调用 CLI 上传。

最新补充：

- 2026-06-23 验收官已输出 `docs/qa/工作台第一期_验收报告.md`，结论为“不通过”；Codex 重新自测报告为 `docs/qa/工作台第一期_Codex重新自测报告.md`。
- 重新自测确认 P0-23 未闭环：业务识别后缺少“切换对应工作台 / 继续当前工作台”的专门双选。
- 重新自测确认 P0-27 未闭环：`GET /api/dashboard/business` 只接收 `ownerUserId`，缺少 requester 身份参数或鉴权证据，仍需补专项权限测试和可能的后端鉴权修复。
- 本次重新自测已执行：小程序全量 JS 检查、JSON 递归解析 44 个、`git diff --check`、权限相关后端专项测试 `8 passed, 88 deselected`。
- 2026-06-23 已完成首页 / Tabbar / 工作台模式一期代码实现：底部 Tabbar 为：首页 / 资料 / 合集 / 工作台 / 我的。
- 新增 `miniprogram/utils/workspace-mode.js`，本地保存常用工作台 `workspaceMode`，支持日常资料台、房源工作台、团购工作台、服务工作台。
- 首页首次进入会要求选择“你想先整理哪类资料？”，二次进入按模式显示今日待处理、快捷开始、最近成果和最近反馈。
- `pages/visits` 已从“访客线索”归位为“工作台 / 反馈中心”，普通资料台显示分享效果，业务模式显示客户看板、接龙看板或咨询看板，底层复用原数据逻辑。
- “我的”移除经营区域，经营看板入口迁到工作台；“我的”新增常用工作台设置。
- `pages/showcases` 已作为“合集”Tab，前台叫资料包 / 合集，一期只做轻版入口和空态，底层仍复用展示页接口。
- 新增自测报告：`docs/qa/首页Tabbar工作台模式一期_Codex自测报告.md`。
- 2026-06-23 已修正“我的笔记资料详情”底部标签与专题默认房产化问题。
- 非 `property_listing` 资料会过滤旧默认房产上下文标签 / 专题，例如“房产 / 房源 / 租房 / 万家丽 / 公寓”等；房源资料本身不受影响。
- 用户手动添加的标签通过 `userTags` 保留，不会因为包含房产词被误删。
- 标签和专题输入提示已改成通用示例：客户、重点、待跟进、客户资料、服务案例。
- 同步修正资料库列表展示，避免列表仍显示旧房产标签而详情页已过滤。
- 已验证：`note-edit`、`note-display`、`notes` 的 JS 静态检查通过，旧房产 placeholder 扫描未命中，`note-edit` 页面核心 `px` 扫描未命中，`git diff --check` 通过。

## 1. 项目背景与目标

当前正式产品名是“资料整理助手”。

项目核心目标：

- 把企业微信、小程序、微信笔记、图片、手动输入等来源内容统一沉淀到资料库。
- 基于 `UserNote + visibilityConfig + structuredData + conversionConfig` 做 typed card，而不是拆多套独立业务表。
- 已有重点业务场景包括：
  - 普通笔记
  - 电商团购 / 商品资料
  - 房产中介 / 房源资料
  - 电子名片 `business_card`
  - 服务方案 `service_offer`
- 所有资料共享同一套公开页、客户动作、轻 SCRM、经营看板、客户库、待联系、订单/接龙回流链路。

长期架构以 [AGENTS.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/AGENTS.md) 和 [08-plugin-architecture.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/stage2-docs/08-plugin-architecture.md) 为准：

- 稳定基座负责身份、会话、笔记库、展示页、经营闭环、支付与合规。
- Skill 负责具体内容处理能力。
- 用户身份唯一锚点是小程序微信 `openid`。
- typed card 第一阶段继续基于 `UserNote.visibilityConfig.cardType` 承载。

## 2. 当前阶段目标

当前阶段重点已经从“普通资料链路”切到“资料库新增销售型资料卡”。

当前正在推进的阶段目标：

- 电子名片：完成独立工作台、4 套模板、客户详情页、微信转发封面、已有名片切换模板闭环。
- 服务方案：完成独立工作台、4 套模板、专属客户销售页、分享封面、已有服务方案可切换模板闭环。
- 先把“选模板 -> 填资料 -> 确认效果 -> 保存/分享”的用户心智跑通，不做自由装修器。
- 当前最高优先级阻塞问题是：`service-offer-studio` 真机打开白屏，代码侧已修复并补兜底，但仍需用户重新上传体验版验证真机结果。

## 3. 已完成的功能

### 3.1 资料库与 typed card 基座

- 普通笔记、房源、商品团购已可统一进入 `UserNote` 体系。
- 经营看板、客户库、待联系、订单中心已基本形成“总览 -> 来源/状态 -> 具体人 -> 处理卡 -> 外呼/复制/业务详情”的闭环。
- 头像兜底、按钮居中、`rpx` 核心尺寸约束等 UI 基础规则已补进 [AGENTS.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/AGENTS.md)。

### 3.2 电子名片 `business_card`

- 后端和前端已支持 `business_card` 类型。
- 已做成独立三步式工作台：`pages/business-card-studio`
  - 选风格
  - 填资料
  - 确认效果
- 资料库新增“电子名片”独立入口，旧“添加”页中的电子名片入口也改跳工作台。
- 已支持 4 套电子名片模板：
  - 专业顾问
  - 门店名片
  - 专家介绍
  - 简洁微信风
- 已支持：
  - 模板列表 / 双列切换
  - 两男两女样板头像
  - 服务器 WebP 模板头像
  - 已有名片通过 `?id=noteId` 进入工作台继续换风格
  - 详情页独立名片化设计，不再复用普通客户页
  - 微信分享封面独立生成，不再依赖普通小程序卡片逻辑
- 电子名片内容和风格已分离：
  - 内容字段可复用
  - 模板可自由切换
  - 不需要重新填写
- 动作区已改成动态联系方式：
  - 电话
  - 微信
  - 邮箱
  - 留下电话/微信
- 电子名片已移除“预约沟通”主动作；预约保留给服务方案。

### 3.3 服务方案 `service_offer`

- 后端和前端已支持 `service_offer` 类型。
- 服务方案已从“普通笔记里的一个分型字段”升级为独立工作台：`pages/service-offer-studio`
- 创建路径已打通：
  - 添加页“服务方案”直接进入工作台
  - 旧模板页选择服务方案时也跳到该工作台
  - 已有 `service_offer` 在 `note-edit` 中通过“设置方案样式”进入工作台
- 已支持 4 套服务方案模板：
  - 咨询预约
  - 服务报价
  - 案例背书
  - 活动招募
- 服务方案字段已拆开，不再混成一个联系方式字段：
  - 电话
  - 微信
  - 邮箱
  - 公司网址 / 介绍链接
- 客户页 `note-preview` 已支持服务方案专属详情结构，不复用商品 SKU、团购接龙、房源地图或电子名片人设模块。
- 服务方案分享图已接入运行时模板化封面生成，不额外塞本地大图资源。

### 3.4 服务方案白屏修复

- 已定位白屏直接原因：
  - `service-offer-studio` 默认表单初始化里错误引用未定义变量。
  - 预览构建阶段缺少图片数组兜底，导致页面运行时异常。
- 已完成代码修复：
  - 补齐默认模板、默认表单、默认预览。
  - 页面初始化增加 `pageError` 可见错误态。
  - 未登录、模板加载失败、读取已有方案失败时显示“重试 / 去登录”，避免纯白屏。
  - `chooseMedia` 增加向 `chooseImage` 的兼容回退。
  - `showLoading/hideLoading/showToast` 增加安全封装，降低环境差异引起的运行时异常概率。
- 已完成代码侧验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js` 通过
  - 小程序全量 JS `node --check` 通过
  - 小程序 JSON 解析检查通过
  - 模拟 Page/getApp/wx 环境加载通过
  - 模拟有用户加载：4 套模板正常出现
  - 模拟无用户加载：显示登录提示，不白屏
- 尚未完成的验证：
  - 真机重新上传体验版后的实际打开结果

## 4. 已修改/新增的文件

说明：仓库当前有大量历史脏改动，下面只列本阶段和“电子名片 / 服务方案 / 白屏修复”强相关、接手时必须关注的关键文件。

### 4.1 关键文档

- [AGENTS.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/AGENTS.md)
- [docs/dev-log.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/dev-log.md)
- [docs/decisions.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/decisions.md)
- [docs/pitfalls.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/pitfalls.md)
- [docs/handoff-latest.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/handoff-latest.md)
- [docs/stage2-docs/16-business-card-service-offer.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/stage2-docs/16-business-card-service-offer.md)
- [docs/qa/电子名片与服务方案卡V1_Codex自测报告.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/qa/电子名片与服务方案卡V1_Codex自测报告.md)
- [docs/qa/电子名片与服务方案模板库V1_Codex自测报告.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/qa/电子名片与服务方案模板库V1_Codex自测报告.md)

### 4.2 电子名片 / 服务方案模板与分享

- [miniprogram/utils/sales-page-templates.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/utils/sales-page-templates.js)
- [miniprogram/utils/business-card-share.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/utils/business-card-share.js)
- [miniprogram/utils/note-display.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/utils/note-display.js)

### 4.3 新增工作台页面

- [miniprogram/pages/business-card-studio/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/business-card-studio/index.js)
- [miniprogram/pages/business-card-studio/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/business-card-studio/index.wxml)
- [miniprogram/pages/business-card-studio/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/business-card-studio/index.wxss)
- [miniprogram/pages/business-card-studio/index.json](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/business-card-studio/index.json)
- [miniprogram/pages/service-offer-studio/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/service-offer-studio/index.js)
- [miniprogram/pages/service-offer-studio/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/service-offer-studio/index.wxml)
- [miniprogram/pages/service-offer-studio/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/service-offer-studio/index.wxss)
- [miniprogram/pages/service-offer-studio/index.json](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/service-offer-studio/index.json)

### 4.4 入口与编辑页联动

- [miniprogram/app.json](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/app.json)
- [miniprogram/pages/library/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.js)
- [miniprogram/pages/library/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.wxml)
- [miniprogram/pages/library/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.wxss)
- [miniprogram/pages/resource-create/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-create/index.js)
- [miniprogram/pages/resource-create/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-create/index.wxml)
- [miniprogram/pages/resource-create/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-create/index.wxss)
- [miniprogram/pages/sales-template-select/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/sales-template-select/index.js)
- [miniprogram/pages/note-edit/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-edit/index.js)
- [miniprogram/pages/note-edit/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-edit/index.wxml)
- [miniprogram/pages/note-edit/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-edit/index.wxss)

### 4.5 客户预览页与分享联动

- [miniprogram/pages/note-preview/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-preview/index.js)
- [miniprogram/pages/note-preview/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-preview/index.wxml)
- [miniprogram/pages/note-preview/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/note-preview/index.wxss)
- [miniprogram/pages/notes/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/notes/index.js)
- [miniprogram/pages/notes/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/notes/index.wxml)
- [miniprogram/pages/notes/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/notes/index.wxss)

### 4.6 相关原型 / 参考资产

- [docs/png/business-card-edit-wireframe.svg](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/png/business-card-edit-wireframe.svg)
- [docs/png/business-card-preview-wireframe.svg](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/png/business-card-preview-wireframe.svg)
- [docs/png/service-offer-edit-wireframe.svg](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/png/service-offer-edit-wireframe.svg)
- [docs/png/service-offer-preview-wireframe.svg](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/png/service-offer-preview-wireframe.svg)
- [docs/png/business-card-service-offer-template-library.svg](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/png/business-card-service-offer-template-library.svg)
- 用户最新提供的高保真服务方案参考图不在仓库内，但已在本轮上下文中作为服务方案后续复刻基准。

## 5. 当前代码状态

- Git 状态：
  - `main...origin/main [ahead 18]`
  - 大量已修改文件
  - 大量未跟踪文件
- 代码完成度判断：
  - 电子名片：功能主链路基本成型，核心剩余工作偏真机验收与细节 polish。
  - 服务方案：独立工作台、模板、详情页结构已经有了，但仍处于“代码版已成型，真机和高保真视觉未收口”的阶段。
- 当前阻塞：
  - 用户反馈“打开时白屏”，针对 `service-offer-studio` 的代码级修复已经完成，但真机是否完全恢复尚未得到新一轮上传验证。
- 最近代码侧验证已通过：
  - `node --check miniprogram/pages/service-offer-studio/index.js`
  - 小程序全量 JS `node --check`
  - 小程序 JSON 解析检查
  - `git diff --check` 针对服务方案白屏修复相关文件
  - 模拟 `Page/getApp/wx` 的服务方案页面加载
- 未完成验证：
  - 微信开发者工具重新上传体验版后的真机打开
  - 服务方案 4 套模板在真机上的视觉一致性
  - 分享卡片和客户详情页的最终真实表现

## 6. 已知问题和风险

### 6.1 当前明确问题

- 服务方案页面此前出现白屏，代码层已修，但还没有真机重新确认。
- 用户已经明确指出：服务方案后续要尽量按提供的高保真参考图复刻，目前只是结构和模板逻辑已落地，还不是最终精美版本。

### 6.2 代码与协作风险

- 仓库工作区很脏，且不是只有电子名片/服务方案相关改动；新 Codex 接手时不要轻易清理、回滚或“顺手整理”。
- `miniprogram/project.config.json` 多半含微信开发者工具本地扰动，默认不要作为业务功能依据，也不要轻易提交。
- 真机与开发者工具环境差异仍存在：
  - `chooseMedia`
  - 分享卡片
  - 拨号 / 复制
  - canvas 封面
  - 体验版权限
- 微信聊天里的小程序卡片不是客户页 WXML，电子名片已做独立封面生成器；服务方案虽然能控制分享图，但聊天气泡结构本身不可改。

### 6.3 产品风险

- 电子名片和服务方案不能退回“普通资料详情页”心智，否则用户会觉得模板没有真正生效。
- 服务方案不能误接成商品链路：
  - 不要启用 SKU
  - 不要启用接龙
  - 不要启用支付 / 订单占位
- 服务方案模板的价值不只是换色，而是场景差异；后续复刻时不能把 4 套模板做成同构卡片。

## 7. 用户已经确认过的产品/技术决策

- 电子名片和服务方案继续复用现有资料库与 SCRM 基座，不另起一套独立客户系统。
- 电子名片单独开工作台，不放在“我的笔记”或输入笔记器里。
- 服务方案也走独立销售页工作台，不继续塞在普通笔记编辑体验里。
- 先做模板库，不做自由装修器。
- 第一批固定 8 个模板：
  - 4 个电子名片
  - 4 个服务方案
- 电子名片内容和风格分离：
  - 内容只填一次
  - 模板可自由切换
- 电子名片首屏、模板预览、编辑页预览、客户详情页首屏、微信分享封面应尽量统一视觉母版。
- 电子名片分享卡片要单独做封面生成器，不能依赖普通小程序默认分享样式。
- 电子名片详情页不复用普通客户预览页。
- 电子名片头像和二维码属于图片字段，不以 URL 文本形式暴露给用户。
- 电子名片不保留“预约沟通”主动作，改成电话 / 微信 / 邮箱 / 留资动态展示。
- 服务方案保留预约沟通，作为销售动作之一。
- 模板头像资源不放前端包，改放服务器 WebP，避免再次触发 2MB 主包限制。
- 小程序上传体验版由用户手动完成，Codex 默认不反复尝试 CLI 上传。

## 8. 下一步建议执行顺序

1. 先让用户重新上传最新体验版，从资料库“服务方案”入口真机打开 `service-offer-studio`，确认白屏是否已消失。
2. 如果白屏仍在，优先收集真机报错截图或开发者工具 console，再继续定位；不要先盲目重做页面。
3. 如果白屏已消失，下一步直接进入服务方案高保真复刻：
   - 以用户提供的参考图为验收基准
   - 先改模板选择页
   - 再改确认页
   - 再改客户详情页
4. 服务方案 4 套模板要拉开明确视觉差异，不只是换颜色。
5. 真机补验：
   - 服务方案保存
   - 详情页打开
   - 分享图
   - 电话 / 微信 / 邮箱 / 留资 / 预约动作
6. 电子名片这条线暂时不要大改结构，除非用户在真机继续指出明显不一致点。

## 9. 新 Codex 会话接手时的第一条提示词

建议新会话第一条直接使用下面这段：

```md
请先读取以下文件：

- AGENTS.md
- docs/project-memory.md
- docs/decisions.md
- docs/pitfalls.md
- docs/dev-log.md
- docs/handoff-latest.md
- docs/handoff-latest-8.md
- docs/stage2-docs/16-business-card-service-offer.md

然后读取当前 git status 和 git diff --stat。

先不要改代码。

请先输出：
1. 你理解的项目目标
2. 当前代码状态
3. 已确认的重要决策
4. 当前风险
5. 针对“服务方案工作台真机白屏与高保真复刻”的下一步建议执行顺序

注意：
- 当前重点不是从头重构，而是继续接手电子名片 / 服务方案这条线。
- `service-offer-studio` 代码侧白屏修复已做，但还缺真机重新上传后的验证。
- 仓库工作区很脏，不要随意回滚无关改动。
- 小程序上传体验版由用户手动在微信开发者工具完成。
```

## 2026-06-23 续更

- 服务方案工作台第二轮已经继续落地，不再停在“做一半”状态。
- 已完成：
  - 顶部步骤条改为横向三段。
  - 模板选择区改为横向卡片，点击即联动预览。
  - 报价型和案例型模板补入服务器 WebP 默认图片。
  - 资源库新增“服务方案”独立入口，放在“电子名片”旁边。
- 当前待验收重点：
  - 真机看服务方案工作台是否明显变短。
  - 模板横向切换时预览是否流畅联动。
  - “服务报价 / 案例背书”是否不再出现发白占位。
  - 资源库入口层级是否符合用户心智。

## 2026-06-23 再续更

- 用户截图反馈第二轮仍然变形：
  - 顶部标题和步骤区被横向内容撑开。
  - 模板卡副标题没有稳定换行。
  - 报价/案例图低清且裁切不美观。
- 已继续处理：
  - 顶部步骤区改为电子名片同款三列固定布局。
  - 页面和模板卡补齐 `min-width: 0`、自动换行和 rpx 尺寸约束。
  - 模板卡去掉缩略图，只保留模板名称、标签和适合场景；图片只在下方联动预览里展示。
  - 报价/案例默认图替换为 v2 高分辨率源图转存后的服务器 WebP 资源。
  - 小程序前端 `miniprogram/static/service-offer` 图片文件已删除，不再占用前端包体积。
- 下一步真机重点：
  - 不再横向撑屏。
  - 副标题自然换行。
  - 模板卡和预览图铺满且不拉伸。

## 2026-06-23 三续更

- 用户继续反馈：
  - 顶部三步和模板横滑区基本正常。
  - 4 个样板预览、下方内容、填写资料页底部按钮、确认效果页手机端仍有溢出。
  - 要求宽度 100%，同时保留 rpx 留白。
- 已继续处理：
  - 服务方案工作台阶段卡、样板预览、表单卡、确认页预览补齐 `width/max-width/min-width` 约束。
  - 内层关键卡片改成 `calc(100% - 4rpx)`，左右保留 `2rpx` 安全留白。
  - 缩小手机端容易挤压的预览头像、英雄区边距和标题字号。
  - 确认页 4 个动作改为 2 列，底部操作条改为 flex 收缩。
  - “下一步：确认效果”缩短为“确认效果”，避免文字超出按钮背景。
- 已验证：
  - 服务方案页面 JS 语法检查通过。
  - 工作台 WXSS/WXML 没发现核心布局使用 `px`。
  - 前端没有重新引入 `/static/service-offer` 图片，`miniprogram/static` 未发现超过 200KB 的静态文件。
- 下一步真机重点：
  - 用普通手机验模板预览区、填写资料底部按钮、确认效果客户预览页是否还会横向滚动。

## 2026-06-23 四续更

- 用户继续反馈：
  - 工作台底部“返回 / 使用这个模板”等按钮挡住模板和上方区域，需要给底部留白并向下。
  - 服务方案微信转发卡片不能退回默认小程序卡片，要像电子名片一样保持模板、微信转发和“我的笔记”列表展示一致。
- 已继续处理：
  - 服务方案工作台增加底部 spacer，并把 sticky 操作条更贴近安全区。
  - `note-display` 增加 `serviceOfferPreview`，列表和分享优先使用用户封面，缺省时使用模板默认图。
  - “我的笔记”服务方案列表改为专属方案预览卡，不再使用普通左图右文卡。
  - 列表页分享预生成从只支持电子名片扩展为电子名片 + 服务方案，服务方案调用 `generateServiceOfferShareImage` 生成横版封面。
- 已验证：
  - 服务方案工作台、我的笔记、客户预览、分享图生成相关 JS 语法检查通过。
  - 相关 WXML/WXSS 没发现核心布局使用 `px`。
  - 前端静态目录仍约 `88K`，没有新增默认大图。
- 下一步真机重点：
  - 重新上传体验版后，验证底部按钮不遮挡最后一屏内容。
  - 从“我的笔记”的服务方案点“发方案”，确认微信聊天卡片显示完整横版方案封面。

## 2026-06-23 五续更

- 用户确认当前测试没有问题，并要求统一处理剩余 P0/P1 开发操作。
- 已继续处理：
  - 服务方案双列卡片增加专属迷你方案预览。
  - 电子名片 / 服务方案分享按钮增加“封面准备中”状态，生成结束后恢复“发名片 / 发方案”。
  - 服务方案继续以 `serviceOfferPreview` 作为列表、双列卡片和分享封面的统一数据源。
  - 新增自测报告：`docs/qa/电子名片与服务方案P0P1收口_Codex自测报告.md`。
  - 确认生产 mock 登录关闭已有后端开关和自动化测试覆盖。
- 已验证：
  - 相关小程序 JS 语法检查通过。
  - 工作台 / 我的笔记相关 WXML/WXSS 没发现核心布局使用 `px`。
  - 小程序前端未发现真实密钥。
  - 前端静态目录仍约 `88K`，未新增大图。
  - `git diff --check` 通过。
- 待用户体验版确认：
  - 分享按钮准备状态、服务方案双列卡片、微信聊天横版方案封面。
