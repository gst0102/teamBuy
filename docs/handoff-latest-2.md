# 资料整理助手阶段性交接归档 2

更新时间：2026-06-19  
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`  
当前分支：`main`  
当前 Git 状态：`main...origin/main [ahead 3]`，本轮改动尚未提交。

本文适合直接给新 Codex 会话继续执行。新会话必须先读取：

```text
AGENTS.md
docs/project-memory.md
docs/decisions.md
docs/pitfalls.md
docs/dev-log.md
docs/handoff-latest.md
docs/handoff-latest-2.md
```

并执行：

```text
git status --short --branch
git diff --stat
```

## 1. 项目背景与目标

teamBuy 当前正式产品名是“资料整理助手”，面向微信私域资料沉淀与复用场景。第一优先用户是房产中介，第二优先用户是团购团长。

项目当前不是交易平台，不做支付、订单、库存、核销和分账。v0.1 目标是验证：

```text
企业微信 / 会话存档 / 手动入口导入资料
  -> ContentObject
  -> content-to-note 生成 UserNote
  -> 小程序资料库
  -> 自动识别房源 / 团购 / 普通笔记 / 链接 / 小程序卡
  -> 高置信直接展示工作台
  -> 分享、留联系方式、预约、接龙、轻 SCRM 跟进
```

长期架构原则仍以 `docs/stage2-docs/08-plugin-architecture.md` 为准：稳定基座负责企业微信通信、会话内容存档、身份识别、笔记库和展示页基础能力；具体内容处理能力以 Skill 插件化扩展。

旧 `Card`、`card-view`、`card-edit` 仍保留，但用户已确认：旧详情页先不要删，先隐藏起来并记录好；已认领导入资料必须优先走新 `UserNote` 资料卡链路。兼容旧 Card 通过 `sourceNoteId` 映射回新笔记页。

## 2. 当前阶段目标

当前阶段已从“房源/团购 4 态显性流程”调整为“自动生成结果 + 轻量整理”的两层工作台。

阶段目标：

- 高置信房源 / 团购：直接展示结果工作台，不让用户先理解整理流程。
- 中置信资料：普通资料卡上轻提示用户确认类型。
- 低置信资料：直接作为普通笔记，不打扰用户。
- 4 态流程只保留为后台生命周期语义，不再作为主 UI。
- 资料库不做传统多级文件夹树，采用默认最新上传、自动标签、专题轻文件夹、未整理入口、宽松模糊搜索。
- 贝壳等第三方小程序房源不能稳定抓到详情图、价格、户型、经纬度时，先保存原小程序入口，允许用户在我们自己的房源卡里补字段、图片、视频，并继续使用客户页、轻 SCRM、留联系方式、预约和微信咨询。
- 客户页链接是主分享路径；分享图只是辅助素材，用于保存到相册、发朋友圈图片或发群图。
- 房源 / 团购工作台顶部主动作已调整为一行三列：“分享文案 / 转发给好友 / 客户页预览”；“保存分享图”保留为弱入口。
- 下一阶段重点只做“客户页动作持久化”，并按 `customer-action-plugin` 可复用插件设计。长标题不拆字段、不改标题；封面裁切、三条亮点等旁支优化先不做。
- 当前 `customer-action-plugin` 第一版已落地：`lead-contact` 和 `appointment` 会写入 `customer_actions`，并投影到现有 `lead_reminders`；客户页 `note-preview` 已改为真实 API 提交。

## 3. 已完成的功能

### 3.1 多类型资料卡与识别

- 后端 `content-to-note` 已支持规则识别：
  - `property_listing` 房源字段卡。
  - `groupbuy_product` 团购商品卡。
  - `text_note` 普通文本卡。
  - `link` 链接 / 文章收藏卡。
  - `miniapp_card` 小程序卡片外壳。
- 后端规则识别已支持置信度机制：
  - 高置信写入 `recognitionConfidence.level=high` 并直接 `cardState=generated`。
  - 中置信保留普通资料卡并写入 `typeSuggestions`。
  - 低置信不提示。
- 房源识别增强：
  - 支持 `小区 + 户型 + 价格 + 位置` 等组合信号。
  - 支持 emoji 字段标签，例如 `🍊小区：`。
  - 增加 `area` 面积字段。
  - 价格识别优先读取价格关键词行，并避开服务费、面积、房号数字抢占。
  - 标题里的小区名也参与房源高置信判断。
- 团购识别增强：
  - 高置信要求商品、价格、规格 / 自提 / 配送 / 截止 / 接龙等组合信号。
- 普通 URL 默认走轻收藏 `link-bookmark`，明确命令如 `整理链接` 才走深度整理。

### 3.2 企业微信小程序卡 / 贝壳房源

- 企业微信 `msgtype=weapp` 已支持入库，不再生成空普通笔记。
- `ContentObjectPayload.metadata` 保存小程序元数据。
- `ContentObjectAdapter`、`WecomMessageNormalizer`、`MessageAggregator`、`MessageType` 均支持小程序卡片。
- 小程序卡前台保存为：
  - `sourceType=miniapp`
  - `systemCategory=小程序`
  - `visibilityConfig.structuredData.miniapp`
- 生产 2026-06-19 02:41 用户转发贝壳房源小程序给企业微信，实际归档只拿到外壳字段：
  - `appid=wxcfd8224218167d98`
  - 标题 `三江尊园 全天采光 好楼层 拎包入住`
  - 来源 `贝壳找房丨二手房新房租房装修`
  - `pagepath`
  - `houseCode=101137825091`
  - `cityId=150200`
  - 没有价格、户型、面积、图片、地址、经纬度。
- 贝壳小程序卡只给“可能是房源信息”的中置信提示，不自动高置信生成完整房源工作台。
- `miniapp_card` 不提取手机号，避免 `pagepath` 数字污染电话字段。
- 编辑页新增“原小程序房源”块，客户页新增“查看贝壳原房源”动作，使用 `wx.navigateToMiniProgram` 跳贝壳原房源；失败时复制房源编码兜底。
- 后端会为可识别的贝壳房源生成候选网页 URL，例如 `https://m.ke.com/baotou/ershoufang/101137825091.html`，写入 `visibilityConfig.sourceUrl` 和 `structuredData.miniapp.webUrl`。该 URL 可能触发贝壳验证码，只作为备用打开 / 复制，不作为稳定爬虫来源。
- 已修复小程序卡确认成房源字段卡时丢失 `miniapp` 元数据的问题。
- 生产历史空笔记 `note_4ecff85fca` 已修复为 `property_listing + sourceType=miniapp`，保留 `houseCode=101137825091` 和完整 `pagePath`。

### 3.3 资料库与搜索

- 小程序“我的笔记”列表已分型展示链接卡、房源卡、团购卡、普通文本卡、小程序卡。
- 默认按上传 / 导入时间倒序。
- 每个资料卡显示 `上传时间 YYYY年M月D日`。
- 分类首行收敛为最近使用、笔记、展开箭头。
- 标签首行收敛为最近使用、房产、户外、团购、添加标签、展开箭头。
- 新增“未整理”轻入口。
- 普通笔记列表展示中置信提示，例如 `可能是：房源 / 团购`。
- 搜索增强：
  - 覆盖标题、摘要、正文、结构化字段、标签、专题、来源、上传日期。
  - 日期索引支持 `YYYY年M月D日`、`YYYY-MM-DD`、`M月D日`、`MD`、`YYYYMMDD`。
  - 数字归一化搜索支持 `6`、`618`、`6月`、`2026-06-18` 这类召回。

### 3.4 资料详情 / 工作台

- 小程序 `pages/note-edit/index` 已从 4 态流程页改成工作台页。
- 房源 / 团购展示：顶部工作台、房源 / 商品卡、图片与视频、功能组、轻 SCRM、基础信息、标签与专题。
- 核心板块支持隐藏 / 恢复。
- 字段区已改成更清晰的信息块样式，常见字段提供快捷项，仍保留输入框自由修改。
- 户型、水电物业、商圈、服务费、自提 / 配送、库存等已有快捷项。
- 标签默认值直接展示并可删除，系统提供推荐标签快捷项。
- 专题提供推荐快捷项，点击后自动创建或加入已有专题，已加入专题可从资料详情移出。
- 普通笔记可通过 `+ 添加功能` 添加轻 CRM、留资表单、预约、接龙。
- 中置信资料可点选切换成房源、团购或普通笔记。
- 编辑页已有浅绿色小尺寸悬浮保存按钮，默认吸附右侧中部，拖动后按左右距离吸附；底部保存仍保留。
- 发布者联系方式会本地记忆手机号；新资料没识别出联系方式时默认带入上次手机号。

### 3.5 图片 / 视频补传

- 资料详情“图片与视频”板块新增“添加”入口。
- 支持从相册 / 相机添加图片。
- 支持从相册 / 相机添加视频。
- 上传复用现有 `POST /api/uploads/asset` / `api.uploadAsset()`。
- 上传成功后自动保存当前资料。
- 首张图片自动作为封面。
- 媒体列表避免封面图重复显示，同一张图若是封面则只显示一次并标记“封面”。
- 删除封面媒体时会自动换下一张图片或清空封面。
- 编辑页视频素材可直接播放。
- 客户页预览新增“房源视频”展示区，用户补传的视频可以展示给客户。

### 3.6 地图定位

- 房源地址字段支持微信原生腾讯地图选点，保存到 `structuredData.mapLocation`。
- 后端新增 `GET /api/location/geocode`，由后端使用 `TENCENT_MAP_KEY` 调腾讯地图地理编码，把默认地址转成经纬度。
- 地图 Key 只配置在后端，不暴露给小程序前端。
- `backend/.env.example` 已增加 `TENCENT_MAP_KEY` / `TENCENT_MAP_GEOCODER_URL`。
- 腾讯地图 Key 已配置到本地和生产后端 `.env`，生产后端已重建；公网 `/api/location/geocode` 已验证可返回坐标。
- 编辑页和客户页在有默认地址但没有坐标时会尝试自动解析地图点。
- 解析成功后显示腾讯地图和小房子 marker。
- 解析失败或未配置 Key 时继续用微信原生选点 / 复制地址兜底。
- 客户页不显示经纬度数字，只展示地图结果和“小房子”位置标记。
- 地图动作支持“选择导航App / 微信内置地图 / 复制地址”，`openMapApp` 不支持时回退微信内置地图。
- 最近一次房源城市会本地记忆；地址不含城市时，用最近城市补全后再请求地理编码，减少同名小区误匹配。

### 3.7 客户页与分享图

- `pages/note-preview/index` 已作为客户可见内容预览。
- 客户页支持微信好友分享和朋友圈分享配置。
- 客户页动作已改成客户能理解的文案：
  - `电话咨询`
  - `留下电话/微信`
  - `预约看房`
  - `微信咨询`
  - `地图定位`
  - `参与接龙`
- 留联系方式支持电话或微信二选一；客户页留资手机号会本地记忆并默认带入。
- 预约看房默认今天，支持今天 / 明天快捷项和日期 / 时间选择器，精确到分钟。
- 客户页已展示房源图片横向图库；视频展示区也已补充。
- 正文内大面积分享按钮已移除，右侧靠下有固定浮动“好友 / 朋友圈”按钮。
- 客户页链接是主分享路径，负责详情展示和转化动作。
- `pages/note-poster/index` 已从“海报入口”改为“分享图”辅助页。
- 资料详情顶部主动作保留：
  - `分享文案`
  - `客户页预览`
  - `转发给好友`
- 原 `朋友圈海报` 主按钮已移除，弱化为 `保存分享图`。
- 分享图页面支持 5 个强调色切换。
- 分享图页面新增 `保存海报` 按钮，使用 canvas 生成静态图并调用保存到相册。
- 分享图页面保留 `客户页` 和 `复制文案` 作为次级动作。
- 功能组文案从 `生成海报` 改为 `保存分享图`，避免和客户页链接混淆。
- 分享图标题已压平换行并限制为最多 3 行，canvas 保存图片时会为价格和详情行保留安全空间，避免长标题重叠。

### 3.9 客户页动作插件化方向

- 新增架构文档：`docs/stage2-docs/13-customer-action-plugin-architecture.md`。
- 客户页动作持久化必须做成可复用插件，不写死在房源客户页。
- 第一批动作插件：
  - `lead-contact`：留下电话/微信，投影到线索。
  - `appointment`：预约看房/预约沟通，投影到线索跟进或后续预约模型。
  - `relay-intent`：接龙/报名/参与意向，投影到接龙名单。
  - `consult-click`：电话咨询、微信咨询、复制联系方式，作为高意向信号。
  - `navigation-click`：地图、导航、复制地址，作为高意向信号。
  - `external-open`：打开原小程序、原文或外部详情页。
- 房源、团购、普通笔记只通过 `conversionConfig` 决定默认启用哪些动作插件。
- 动作提交先落通用动作记录，再投影到线索、预约、接龙、跟进。
- 已新增后端接口：
  - `GET /api/notes/{note_id}/customer-actions/config`
  - `POST /api/notes/{note_id}/customer-actions/{action_key}`
- 已新增 `CustomerAction` / `customer_actions`，并补 `backend/mock/customer-actions.json`。
- 第一版已接入 `lead-contact` 和 `appointment`，后续继续接 `relay-intent`、`consult-click`、`navigation-click`、`external-open`。

### 3.8 旧详情页隐藏策略

- 后端 `/api/cards` 和 `/api/cards/{card_id}` 响应新增 `sourceNoteId`。
- 小程序新增 `miniprogram/utils/resource-navigation.js`，统一处理资源跳转。
- 有 `sourceNoteId` 时打开 `/pages/note-edit/index`。
- 无 `sourceNoteId` 时才回退旧 `card-view` / `card-edit`。
- 已接入统一跳转的入口包括：
  - 资源库
  - 首页热门资源
  - 访问记录
  - 客户资料库
  - 待联系列表
  - 线索详情
  - 管理页打开 / 编辑资源
- 旧 `card-view` / `card-edit` 文件仍保留；拥有者直接打开带 `sourceNoteId` 的旧页会自动跳转新笔记页。
- 客户分享访问旧 `card-view` 暂不强制拦截，避免新客户展示页完成前影响外部查看。

## 4. 已修改 / 新增的文件

当前 `git diff --stat` 显示 36 个已跟踪文件变更，另有若干新增未跟踪文件。本轮和相关未提交改动主要涉及：

### 后端

- `backend/.env.example`
- `backend/app/api/routes_cards.py`
- `backend/app/api/routes_location.py`（新增）
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/models/domain.py`
- `backend/app/schemas/skills.py`
- `backend/app/services/app_service.py`
- `backend/app/services/content_object_adapter.py`
- `backend/app/services/message_aggregator.py`
- `backend/app/services/skill_router_service.py`
- `backend/app/services/wecom_message_normalizer.py`
- `backend/tests/test_app.py`
- `backend/tests/test_skill_router.py`

### 小程序

- `miniprogram/app.json`
- `miniprogram/services/api.js`
- `miniprogram/utils/resource-navigation.js`（新增）
- `miniprogram/pages/note-edit/index.js`
- `miniprogram/pages/note-edit/index.wxml`
- `miniprogram/pages/note-edit/index.wxss`
- `miniprogram/pages/note-preview/`（新增）
- `miniprogram/pages/note-poster/`（新增）
- `miniprogram/pages/notes/index.js`
- `miniprogram/pages/notes/index.wxml`
- `miniprogram/pages/notes/index.wxss`
- `miniprogram/pages/card-edit/index.js`
- `miniprogram/pages/card-view/index.js`
- `miniprogram/pages/customers/index.js`
- `miniprogram/pages/home/index.js`
- `miniprogram/pages/lead-detail/index.js`
- `miniprogram/pages/leads/index.js`
- `miniprogram/pages/library/index.js`
- `miniprogram/pages/manager/index.js`
- `miniprogram/pages/visits/index.js`

### 文档

- `docs/decisions.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/handoff-latest-2.md`（本文件）
- `docs/handoff-latest-3.md`
- `docs/pitfalls.md`
- `docs/project-memory.md`

### 本地脏文件，不要随手提交

- `miniprogram/project.config.json`：微信开发者工具本地配置扰动。
- `企业微信客服服务须知.pdf`：未跟踪 PDF，本地参考文件，不要擅自删除或提交。

## 5. 当前代码状态

当前分支：

```text
main...origin/main [ahead 3]
```

当前仍有大量未提交改动，既包含本轮功能，也包含上一轮尚未提交的旧详情页隐藏 / 新资料卡跳转改动。提交前必须认真分组，不要把 `miniprogram/project.config.json` 和 PDF 混入。

近期验证记录：

```text
后端完整测试：
pytest backend/tests -q
98 passed

小程序 JS 静态检查：
通过

小程序 JSON 解析检查：
通过

git diff --check：
通过
```

注意：分享图保存到相册、微信地图选点、`wx.navigateToMiniProgram` 跳贝壳原房源、`openMapApp` 导航 App 选择等能力必须在微信开发者工具 / 真机环境重新编译后人工验证。静态检查不能替代微信运行环境。

生产后端状态：

- 部署地址：`https://teambuy.lifelove.top`
- `/health` 已通过。
- `generate` 路由已上线。
- `GET /api/location/geocode` 已上线并验证可返回坐标。
- 当前贝壳历史 note 已在生产修复并保留小程序元数据。

## 6. 已知问题和风险

- 小程序 UI 尚需在微信开发者工具里重新编译 / 预览，特别是新增的补传图片视频、保存分享图、客户页视频、地图自动解析和跳贝壳小程序。
- `POST /api/notes/{note_id}/generate` 目前只是写入生成态配置和启用动作清单，不是真正的场景生成 Skill。
- 分享图页面已能用 canvas 保存静态图片，但不是最终精美海报 Skill；真机保存到相册权限弹窗需人工验证。
- 客户页目前是 owner 侧预览 / 可分享页面雏形，正式客户展示链路仍需继续打磨。
- 贝壳等第三方小程序不能假设能抓到完整素材；不要把自动抓图、抓价格、抓户型作为主链路依赖。
- 贝壳候选网页 URL 可能触发验证码，仅作备用，不作为稳定爬虫来源。
- 地图地理编码存在歧义，尤其同名小区跨城市；当前用最近城市补全，但仍需人工校验。
- 识别逻辑第一版是硬规则，宁可保守，不应为了多命中而把普通笔记误判成房源 / 团购。
- 旧 `Card` 详情页仍存在，外部客户访问旧 `card-view` 暂不强制拦截。
- `miniprogram/project.config.json` 是微信开发者工具本地变化，不确定是否要提交。
- 生产环境参与真实企业微信 / 地图联调，后续进入更稳定阶段应拆 staging/test，避免生产试错扩大风险。
- 房源资料详情“轻 SCRM”已成为单房源客户动作主入口：通过 `GET /api/notes/{note_id}/customer-actions?ownerUserId=...` 按 noteId 查看留资、预约和投影线索；`pages/note-actions/index` 展示动作时间线和线索列表。
- 轻 SCRM 红点绑定待跟进线索 `pending`，不是历史动作总数；人工验收时应验证线索标记已联系 / 归档后红点是否消失。
- 客户动作接口已部署生产：公网 customer-actions 路由不再返回路由级 `Not Found`。手机/iPad 继续测试前，需要在微信开发者工具重新编译/上传新版小程序前端，才能看到按钮适配修复。
- 真机身份隔离已补：小程序新增微信 code 登录，后端新增 `/api/auth/wechat-login` 并已部署生产；服务器尚未配置 `WECHAT_MINIAPP_SECRET`，当前会用设备级唯一 mock openid 兜底，避免两个微信继续共用“本地测试用户”。正式 openid 登录需补服务器 `.env` 后重启 backend。
- 轻 SCRM 红点改为本机已读模型，点开“查看客户动作 / 查看线索”后红点消失；待联系列表、线索详情、SCRM 线索页已在手机号旁加入拨号入口。
- “我的”页已新增“生成测试房源数据”：调用 `POST /api/notes/demo-data?ownerUserId=...`，给当前用户生成 3 条房源、2 条线索、3 条客户动作；生产后端已部署并验证可用。
- 房产场景体验继续补强：房源卡片显示推广状态；客户信息入口显示“待跟进 N / 客户 N”；资料详情可复制客户话术、切换推广中/已租/暂停推广、图片视频上移下移；客户页遇到已租/暂停推广会关闭新增留资/预约/咨询动作；客户动作页按待跟进、预约、已处理和全部动作分层；拨号成功后可顺手标记已联系并写跟进记录。
- 本轮验证：小程序全量 JS `node --check` 通过；相关页面 JSON 解析通过；`git diff --check` 通过；Python 3.12 环境后端 `compileall` 通过；`pytest backend/tests -q` 100 passed。

## 7. 用户已经确认过的产品 / 技术决策

- 不要把“整理流程”当卖点；整理是后台能力，用户只想看到结果。
- 房源 / 团购前台体验采用两层：自动生成工作台 + 板块级编辑。
- 置信度机制是正确方向：
  - 高置信自动生成。
  - 中置信轻确认。
  - 低置信普通笔记。
- CRM、留联系方式、预约、接龙作为功能组，不做自由开关堆砌。
- 房源默认带轻 CRM、留联系方式、预约看房、微信咨询、分享能力。
- 团购默认带轻 CRM、留联系方式、接龙、分享能力。
- 普通笔记也可以按需添加功能组。
- 每个资料卡都要显示上传时间，方便用户搜索和记忆。
- 不做传统多级文件夹；专题作为轻文件夹，一条资料可进入多个专题。
- 默认最新上传在前，用户通过标签、专题和搜索归纳。
- 搜索必须宽松，`6`、`618`、`6月`、`2026-06-18` 都应尽量召回日期资料。
- 旧详情页先不要删，先隐藏和保留回退；新链路测试稳定后再处理旧页。
- 贝壳等小程序房源可只保留原小程序入口和标题，用户在我们的小程序里补字段、图片、视频，并继续使用 SCRM 等能力。
- 地图 Key 只能放后端，不能写入小程序前端或 Git。
- 客户页链接是主分享路径；分享图只是辅助素材，不应抢主路径。
- 朋友圈优先发客户页链接；分享图适合保存到相册、发朋友圈图片、发群图或私聊图片。
- 房源工作台内查看客户动作比全局线索列表更符合使用习惯；全局线索列表主要用于跨资料排待办。

## 8. 下一步建议执行顺序

1. 在微信开发者工具重新编译 / 预览小程序，先做人工冒烟：
   - 我的笔记列表上传时间、未整理入口、中置信提示。
   - 明显房源是否直接进入房源工作台。
   - 明显团购是否直接进入团购工作台。
   - 普通笔记添加功能组是否自然。
2. 重点验收最近新增的真机能力：
   - 资料详情添加图片。
   - 资料详情添加视频。
   - 上传后自动保存、首图设封面、客户页图片 / 视频展示。
   - 分享图页面 `保存海报` 是否触发相册权限并成功保存。
   - 客户页 `转发给好友` / `朋友圈` 是否路径正确。
   - 房源详情轻 SCRM 是否显示客户动作、留资、待跟进数量。
   - 点击“查看客户动作 / 查看线索”是否只展示当前房源的留资、预约和线索。
   - 有待跟进线索时红点是否显示，处理后是否消失。
3. 验证贝壳小程序房源链路：
   - 新贝壳小程序卡入库后是否显示“原小程序房源”。
   - 点击能否跳贝壳原房源；失败时是否复制房源信息。
   - 用户确认成房源卡后是否保留 `structuredData.miniapp`。
   - 用户能否补图片、视频、价格、地址并生成客户页。
4. 验证地图链路：
   - 默认地址是否能自动解析地图点。
   - 小房子 marker 是否显示。
   - 点击地图动作是否能选择导航 App / 微信内置地图 / 复制地址。
   - 同名小区或地址不完整时是否需要人工选点。
5. 若 UI 和真机能力基本通过，再分组提交：
   - 后端小程序卡 / 识别 / 地图 geocode。
   - 小程序两层工作台、客户页、分享图、补传图片视频。
   - 旧详情页隐藏 / `sourceNoteId` 跳转。
   - 文档更新。
6. 提交前明确排除：
   - `miniprogram/project.config.json`，除非用户确认要纳入。
   - `企业微信客服服务须知.pdf`。
7. 后续再考虑真正场景生成 Skill：
   - 更精美分享图 / 海报。
   - 客户话术。
   - 房源推广图。
   - 团购接龙格式。

## 9. 新 Codex 会话接手时的第一条提示词

```text
请先读取 AGENTS.md、docs/project-memory.md、docs/decisions.md、docs/pitfalls.md、docs/dev-log.md、docs/handoff-latest.md、docs/handoff-latest-2.md，并执行 git status --short --branch、git diff --stat。

当前产品方向已经从房源/团购显性 4 态流程，改为“自动生成结果 + 轻量整理”的两层工作台。不要再把 4 态流程推到用户前台。客户页链接是主分享路径，分享图只是保存到相册的辅助素材，不要把海报重新做成主路径。

请重点核对本地未提交改动：后端 weapp/贝壳小程序卡解析、识别置信度、模糊搜索、腾讯地图 geocode；小程序 note-edit 工作台、notes 列表上传时间/未整理入口/中置信提示、note-preview 客户页、note-poster 分享图保存、资料详情图片/视频补传、旧详情页 sourceNoteId 跳转。

下一步优先在微信开发者工具/真机预览验证：明显房源、明显团购、中置信资料、低置信普通笔记、贝壳小程序房源、图片/视频补传、保存分享图、地图定位和客户页分享。
```
