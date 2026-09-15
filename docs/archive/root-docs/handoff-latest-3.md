# 资料整理助手阶段性交接归档 3

更新时间：2026-06-19  
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`  
当前分支：`main`  
当前 Git 状态：`main...origin/main [ahead 3]`，工作区有未提交改动。

本文适合直接给新 Codex 会话继续执行。新会话必须先读取：

```text
AGENTS.md
docs/project-memory.md
docs/decisions.md
docs/pitfalls.md
docs/dev-log.md
docs/handoff-latest.md
docs/handoff-latest-2.md
docs/handoff-latest-3.md
```

并执行：

```text
git status --short --branch
git diff --stat
```

## 1. 项目背景与目标

teamBuy 当前正式产品名是“资料整理助手”，面向微信私域资料沉淀与复用场景。

第一优先用户是房产中介，第二优先用户是团购团长。当前产品不是交易平台，不做支付、订单、库存、核销和分账。

v0.1 目标是验证：

```text
企业微信 / 会话存档 / 手动入口导入资料
  -> ContentObject
  -> content-to-note 生成 UserNote
  -> 小程序资料库
  -> 自动识别房源 / 团购 / 普通笔记 / 链接 / 小程序卡
  -> 高置信直接展示工作台
  -> 分享、留资、预约、接龙、轻 SCRM 跟进
```

长期架构原则以 `docs/stage2-docs/08-plugin-architecture.md` 为准：稳定基座负责企业微信通信、会话内容存档、身份识别、笔记库和展示页基础能力；具体内容处理能力以 Skill / 插件化扩展。

旧 `Card`、`card-view`、`card-edit` 仍保留。已认领导入资料优先走新 `UserNote` 资料卡链路；兼容旧 Card 通过 `sourceNoteId` 映射回新笔记页。

## 2. 当前阶段目标

当前阶段从“房源/团购 4 态显性流程”调整为“自动生成结果 + 轻量整理”的两层工作台：

- 高置信房源 / 团购：直接展示结果工作台，不让用户先理解整理流程。
- 中置信资料：普通资料卡上轻提示用户确认类型。
- 低置信资料：直接作为普通笔记，不打扰用户。
- 4 态流程只保留为后台生命周期语义，不再作为主 UI。
- 资料库采用默认最新上传、自动标签、专题轻文件夹、未整理入口、宽松模糊搜索。
- 客户页链接是主分享路径；分享图只是辅助素材。
- 客户页动作持久化按 `customer-action-plugin` 可复用插件方向实现，房源、团购、普通笔记只决定默认启用哪些动作。

本阶段房源场景已收口。用户已确认：房源长标题通常是中介主动展示价格、地铁口、户型、亮点的方式，不拆字段、不改标题。

## 3. 已完成的功能

### 3.1 多类型资料卡与识别

- 后端 `content-to-note` 已支持：
  - `property_listing` 房源字段卡。
  - `groupbuy_product` 团购商品卡。
  - `text_note` 普通文本卡。
  - `link` 链接 / 文章收藏卡。
  - `miniapp_card` 小程序卡片外壳。
- 识别已支持 `recognitionConfidence`：
  - 高置信写入 `level=high` 并直接 `cardState=generated`。
  - 中置信保留普通资料卡并写入 `typeSuggestions`。
  - 低置信不提示。
- 房源识别支持小区、户型、价格、位置、面积、emoji 字段标签等组合信号。
- 团购识别支持商品、价格、规格、自提/配送、截止、接龙等组合信号。
- 普通 URL 默认走轻收藏 `link-bookmark`，明确命令如 `整理链接` 才走深度整理。

### 3.2 企业微信小程序卡 / 贝壳房源

- 企业微信 `msgtype=weapp` 已支持入库，不再生成空普通笔记。
- 小程序卡前台保存为：
  - `sourceType=miniapp`
  - `systemCategory=小程序`
  - `visibilityConfig.structuredData.miniapp`
- 贝壳小程序卡只给“可能是房源信息”的中置信提示，不自动伪造完整房源字段。
- 编辑页新增“原小程序房源”块，客户页新增“查看贝壳原房源”动作，使用 `wx.navigateToMiniProgram` 跳贝壳原房源；失败时复制房源编码兜底。
- 确认成房源字段卡时保留 `structuredData.miniapp`。

### 3.3 资料库与搜索

- 小程序“我的笔记”列表已分型展示链接卡、房源卡、团购卡、普通文本卡、小程序卡。
- 默认按上传 / 导入时间倒序。
- 每个资料卡显示上传时间。
- 分类首行收敛为最近使用、笔记、展开箭头。
- 标签首行收敛为最近使用、房产、户外、团购、添加标签、展开箭头。
- 新增“未整理”轻入口。
- 普通笔记列表展示中置信提示，例如 `可能是：房源 / 团购`。
- 搜索覆盖标题、摘要、正文、结构化字段、标签、专题、来源、上传日期。
- 日期和数字归一化搜索支持 `6`、`618`、`6月`、`2026-06-18` 等召回。
- 搜索按钮已移除，搜索框使用整行输入，回车/输入触发模糊搜索。

### 3.4 资料详情 / 房源工作台

- `pages/note-edit/index` 已从 4 态流程页改成工作台页。
- 房源 / 团购展示：顶部工作台、房源/商品卡、图片与视频、功能组、轻 SCRM、基础信息、标签与专题。
- 顶部主动作一行展示：
  - `分享文案`
  - `转发给好友`
  - `客户页预览`
- `保存分享图` 弱化为次级入口。
- 新增 `复制客户话术`，用于快速复制给客户的房源说明。
- 房源状态使用 `structuredData.propertyStatus`：
  - `active`：推广中
  - `rented`：已租
  - `paused`：暂停推广
- 资料详情可切换房源状态并立即保存。
- 我的笔记房源卡片显示房源状态 chip。
- 字段区常见字段提供快捷项，仍保留输入框自由修改。
- 标题保持用户原始表达，不做自动拆字段提示。
- 发布者联系方式会本地记忆手机号；新资料没识别出联系方式时默认带入上次手机号。

### 3.5 图片 / 视频补传与排序

- 资料详情“图片与视频”板块支持添加图片、添加视频。
- 上传复用现有 `POST /api/uploads/asset` / `api.uploadAsset()`。
- 上传成功后自动保存当前资料。
- 首张图片自动作为封面。
- 设置封面后立即保存。
- 删除图片 / 视频后立即保存。
- 删除封面媒体时会自动换下一张图片或清空封面。
- 封面角标改为淡红底 / 红字，字号略大。
- 图片 / 视频素材支持上移、下移排序，并立即保存排序结果。
- 素材排序会重写 `sortOrder` 并同步 `structuredData.images`。
- 客户页预览展示房源图片横向图库和房源视频区。

### 3.6 地图定位

- 房源地址字段支持微信原生腾讯地图选点，保存到 `structuredData.mapLocation`。
- 后端新增 `GET /api/location/geocode`，由后端使用 `TENCENT_MAP_KEY` 调腾讯地图地理编码。
- 地图 Key 只配置在后端，不暴露给小程序前端。
- 编辑页和客户页在有默认地址但没有坐标时会尝试自动解析地图点。
- 解析成功后显示腾讯地图和小房子 marker。
- 解析失败或未配置 Key 时继续用微信原生选点 / 复制地址兜底。
- 客户页不显示经纬度数字，只展示地图结果和位置标记。
- 地图动作支持“选择导航App / 微信内置地图 / 复制地址”。
- 最近一次房源城市会本地记忆；地址不含城市时，用最近城市补全后再请求地理编码。

### 3.7 客户页与分享图

- `pages/note-preview/index` 已作为客户可见内容预览。
- 客户页支持微信好友分享和朋友圈分享配置。
- 客户页动作文案：
  - `电话咨询`
  - `留下电话/微信`
  - `预约看房`
  - `微信咨询`
  - `地图定位`
  - `参与接龙`
- 留联系方式支持电话或微信二选一；客户页留资手机号会本地记忆并默认带入。
- 预约看房默认今天，支持今天 / 明天快捷项和日期 / 时间选择器。
- 客户页右侧靠下有固定浮动“好友 / 朋友圈”按钮。
- 已租 / 暂停推广的房源客户页会关闭新增电话咨询、留资、预约、私聊、接龙等转化动作，只保留原房源 / 地图等信息入口。
- `pages/note-poster/index` 是分享图辅助页，支持 5 个强调色切换和保存到相册。

### 3.8 客户动作持久化插件第一版

- 新增架构文档：`docs/stage2-docs/13-customer-action-plugin-architecture.md`。
- 新增通用 `CustomerAction` / `customer_actions`。
- 新增后端接口：
  - `GET /api/notes/{note_id}/customer-actions/config`
  - `POST /api/notes/{note_id}/customer-actions/{action_key}`
  - `GET /api/notes/{note_id}/customer-actions?ownerUserId=...`
- 第一版已接入：
  - `lead-contact`：留下电话/微信，写 `customer_actions` 并投影到 `lead_reminders`。
  - `appointment`：预约看房，写 `customer_actions` 并投影到 `lead_reminders`。
- 客户页 `note-preview` 已从本地假提交改为真实 API 提交。
- 生产后端已部署 customer-actions 相关路由，手机/iPad 上的路由级 `Not Found` 已修复。
- 未来可继续接：
  - `relay-intent`
  - `consult-click`
  - `navigation-click`
  - `external-open`

### 3.9 房源轻 SCRM / 客户信息

- 房源资料详情“轻 SCRM”板块是单房源客户动作主入口。
- 我的笔记房源/团购卡片增加“客户信息”快捷入口，避免入口藏太深。
- 卡片右上角有未读红点。
- 红点基于“最新客户动作时间 > 本机已读时间”，点击客户信息页后红点立即消失。
- 卡片客户信息文案：
  - 有待跟进：`待跟进 N`
  - 有线索：`客户 N`
  - 无数据：`客户信息`
- 新增 `pages/note-actions/index`：
  - 按当前 noteId 展示动作和线索。
  - 分层展示“新线索 / 待跟进、预约看房、已联系 / 已归档、全部客户动作”。
  - 可进入线索详情。
  - 电话旁有拨号入口。
- 全局线索页和线索详情页也已补电话拨号入口。
- 拨号成功后提示是否标记已联系；确认后更新 `lead_reminders.status=contacted` 并写入“已电话联系客户”的跟进记录。

### 3.10 真机身份隔离与测试数据

- 后端新增 `POST /api/auth/wechat-login`，支持小程序 `wx.login` code 换 openid。
- 生产后端已部署该路由。
- 当前生产服务器尚未配置 `WECHAT_MINIAPP_SECRET`，因此正式 openid 登录未启用。
- 小程序登录优先走微信登录；未配置 AppSecret 时使用设备级唯一 mock openid 兜底，避免两个微信共用“本地测试用户”。
- 小程序启动时清理旧 `openid_本地测试用户` 缓存。
- 后端新增 `POST /api/notes/demo-data?ownerUserId=...`。
- 小程序“我的”页新增“生成测试房源数据”。
- 每次会给当前用户生成 3 条房源资料、2 条线索、3 条客户动作。
- 生产后端已部署并验证 demo data 接口可用。

### 3.11 旧详情页隐藏策略

- 后端 `/api/cards` 和 `/api/cards/{card_id}` 响应新增 `sourceNoteId`。
- 小程序新增 `miniprogram/utils/resource-navigation.js`。
- 有 `sourceNoteId` 时打开 `/pages/note-edit/index`。
- 无 `sourceNoteId` 时回退旧 `card-view` / `card-edit`。
- 已接入资源库、首页热门资源、访问记录、客户资料库、待联系列表、线索详情、管理页等入口。
- 旧 `card-view` / `card-edit` 文件仍保留。

## 4. 已修改 / 新增的文件

### 后端能力

- `backend/.env.example`
- `backend/app/api/routes_auth.py`
- `backend/app/api/routes_cards.py`
- `backend/app/api/routes_location.py`
- `backend/app/api/routes_notes.py`
- `backend/app/core/config.py`
- `backend/app/core/schema.sql`
- `backend/app/main.py`
- `backend/app/models/domain.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/notes.py`
- `backend/app/schemas/skills.py`
- `backend/app/services/app_service.py`
- `backend/app/services/bootstrap.py`
- `backend/app/services/content_object_adapter.py`
- `backend/app/services/message_aggregator.py`
- `backend/app/services/repository.py`
- `backend/app/services/skill_router_service.py`
- `backend/app/services/wecom_message_normalizer.py`
- `backend/mock/customer-actions.json`
- `backend/tests/test_app.py`
- `backend/tests/test_skill_router.py`

### 小程序体验

- `miniprogram/app.js`
- `miniprogram/app.json`
- `miniprogram/services/api.js`
- `miniprogram/utils/resource-navigation.js`
- `miniprogram/pages/card-edit/index.js`
- `miniprogram/pages/card-view/index.js`
- `miniprogram/pages/customers/index.js`
- `miniprogram/pages/home/index.js`
- `miniprogram/pages/lead-detail/index.js`
- `miniprogram/pages/lead-detail/index.wxml`
- `miniprogram/pages/lead-detail/index.wxss`
- `miniprogram/pages/leads/index.js`
- `miniprogram/pages/leads/index.wxml`
- `miniprogram/pages/leads/index.wxss`
- `miniprogram/pages/library/index.js`
- `miniprogram/pages/login/index.js`
- `miniprogram/pages/login/index.wxml`
- `miniprogram/pages/login/index.wxss`
- `miniprogram/pages/manager/index.js`
- `miniprogram/pages/note-actions/index.js`
- `miniprogram/pages/note-actions/index.json`
- `miniprogram/pages/note-actions/index.wxml`
- `miniprogram/pages/note-actions/index.wxss`
- `miniprogram/pages/note-edit/index.js`
- `miniprogram/pages/note-edit/index.wxml`
- `miniprogram/pages/note-edit/index.wxss`
- `miniprogram/pages/note-poster/index.js`
- `miniprogram/pages/note-poster/index.json`
- `miniprogram/pages/note-poster/index.wxml`
- `miniprogram/pages/note-poster/index.wxss`
- `miniprogram/pages/note-preview/index.js`
- `miniprogram/pages/note-preview/index.json`
- `miniprogram/pages/note-preview/index.wxml`
- `miniprogram/pages/note-preview/index.wxss`
- `miniprogram/pages/notes/index.js`
- `miniprogram/pages/notes/index.wxml`
- `miniprogram/pages/notes/index.wxss`
- `miniprogram/pages/profile/index.js`
- `miniprogram/pages/profile/index.wxml`
- `miniprogram/pages/profile/index.wxss`
- `miniprogram/pages/visits/index.js`

### 文档

- `docs/decisions.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/handoff-latest-2.md`
- `docs/handoff-latest-3.md`
- `docs/pitfalls.md`
- `docs/project-memory.md`
- `docs/stage2-docs/13-customer-action-plugin-architecture.md`

### 本地杂项

- `miniprogram/project.config.json` 有微信开发者工具本地变化，不确定是否应提交。
- `企业微信客服服务须知.pdf` 为未跟踪 PDF，不要擅自删除或提交。
- `docs/handoff-latest-2.md`、`docs/handoff-latest-3.md` 当前是未跟踪新增文档，属于应提交的交接文档。

## 5. 当前代码状态

当前 `git status --short --branch`：

```text
## main...origin/main [ahead 3]
```

工作区有大量未提交改动，包含：

- 后端 customer actions、微信登录、demo data、地理编码、小程序卡识别、旧 Card 到新 Note 映射等能力。
- 小程序 note-edit、note-preview、note-poster、note-actions、notes、profile、login、leads、lead-detail 等体验改动。
- 文档更新。
- 未跟踪文件：`backend/app/api/routes_location.py`、`backend/mock/customer-actions.json`、`docs/handoff-latest-2.md`、`docs/handoff-latest-3.md`、`docs/stage2-docs/13-customer-action-plugin-architecture.md`、`miniprogram/pages/note-actions/`、`miniprogram/pages/note-poster/`、`miniprogram/pages/note-preview/`、`miniprogram/utils/resource-navigation.js`、`企业微信客服服务须知.pdf`。

最近验证结果：

```text
find miniprogram -name '*.js' -not -path '*/miniprogram_npm/*' -print0 | xargs -0 -n 1 node --check
通过

python3 -m json.tool 相关小程序页面 JSON
通过

git diff --check
通过

/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests
通过

/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests -q
100 passed
```

注意：项目根目录 `.venv` 当前是较低 Python 版本，直接跑 `.venv/bin/python -m pytest backend/tests -q` 会因 `dataclass(slots=True)` 报错。后端测试需继续使用 Python 3.10+，本轮使用 `/tmp/teambuy-pytest-venv312/bin/python`。

## 6. 已知问题和风险

- 生产服务器还未配置真实 `WECHAT_MINIAPP_SECRET`；`/api/auth/wechat-login` 已部署，但正式 openid 登录尚未启用。当前真机测试靠设备级唯一 mock openid 兜底隔离。
- 前端最新房源体验改动需要重新编译 / 预览 / 上传小程序后，手机和 iPad 才能看到。
- 微信原生能力必须真机人工验收：保存到相册、微信分享、朋友圈、`wx.navigateToMiniProgram` 跳贝壳原房源、地图选点、导航 App 打开、电话拨号。
- 客户动作第一版只接了 `lead-contact` 和 `appointment`；`relay-intent`、`consult-click`、`navigation-click`、`external-open` 还未落地。
- 当前前端仍显式传 `ownerUserId`，正式上线后应升级为服务端 session/token 校验，避免弱权限边界。
- 企业微信真实会话存档 / sync_msg / 媒体下载仍是 P0 主链路风险，需要继续按项目文档验证真实生产链路。
- 地图地理编码存在同名小区、地址不完整、城市不准等歧义；当前用最近城市补全，但仍需人工校验。
- 贝壳等第三方小程序不能假设能抓到完整素材；当前只稳定保存原小程序入口，用户可在我们的房源卡补字段、图片、视频。
- `miniprogram/project.config.json` 是本地开发者工具配置变化，提交前需要用户确认。
- `企业微信客服服务须知.pdf` 是未跟踪参考文件，不要批量删除或随手提交。
- 工作区改动很多，提交前必须分组复核，避免把不相关本地杂项混入。

## 7. 用户已经确认过的产品 / 技术决策

- 不要把“整理流程”当卖点；整理是后台能力，用户只想看到结果。
- 房源 / 团购前台体验采用两层：自动生成工作台 + 板块级编辑。
- 置信度机制正确：
  - 高置信自动生成。
  - 中置信轻确认。
  - 低置信普通笔记。
- 房源长标题不拆字段、不改标题；中介会刻意把价格、地铁口、户型、亮点放进标题。
- CRM、留资、预约、接龙作为功能组，不做自由开关堆砌。
- 客户页链接是主分享路径；分享图只是辅助素材。
- 房源默认带轻 SCRM、留资、预约看房、微信咨询、分享能力。
- 团购默认带轻 SCRM、留资、接龙、分享能力。
- 普通笔记也可以按需添加功能组。
- 每个资料卡都要显示上传时间，方便用户搜索和记忆。
- 不做传统多级文件夹；专题作为轻文件夹，一条资料可进入多个专题。
- 默认最新上传在前，用户通过标签、专题和搜索归纳。
- 旧详情页先不要删，先隐藏和保留回退；新链路测试稳定后再处理旧页。
- 贝壳等小程序房源可以只保留原小程序入口和标题，用户在我们的小程序里补字段、图片、视频，并继续使用 SCRM 等能力。
- 地图 Key 只能放后端，不能写入小程序前端或 Git。
- 客户动作保存到通用 `customer_actions`，再投影到线索、预约、接龙、跟进。
- 房源工作台内查看客户动作比全局线索列表更符合房产使用习惯；全局线索列表主要用于跨资料排待办。
- 红点是未读心智，不等同于待跟进数量；点开客户动作页后红点应消失，待跟进数量保留为数字。
- 房源状态属于结构化字段，不属于标题重写；已租 / 暂停推广应影响客户页转化动作。
- 电话拨号后应提示是否标记已联系，确认后写跟进记录。
- 房源场景目前已收口，没有新的必须补项。

## 8. 下一步建议执行顺序

1. 做一次完整 diff 复核并分组确认提交范围：
   - 后端能力。
   - 小程序体验。
   - 文档。
   - 本地杂项。
2. 明确排除：
   - `miniprogram/project.config.json`，除非用户确认要提交。
   - `企业微信客服服务须知.pdf`。
3. 重新编译 / 预览小程序，做一轮真机冒烟：
   - 两个微信账号是否隔离。
   - 生成测试房源数据。
   - 我的笔记房源卡片状态、客户信息入口、红点。
   - 房源资料详情：图片/视频、设封面、删除、排序、复制客户话术、切换房源状态。
   - 客户页：留资、预约、已租/暂停推广动作关闭、地图、分享。
   - 客户动作页：待跟进、预约、已处理分层。
   - 拨号后标记已联系。
4. 如真机验收通过，按组提交：
   - 后端 customer-action-plugin / auth / demo-data / geocode / miniapp card。
   - 小程序房源工作台 / 客户页 / 客户动作 / 资料库体验。
   - 文档归档。
5. 生产正式 openid 登录前，给服务器 `.env` 补真实 `WECHAT_MINIAPP_SECRET` 并重启 backend。
6. 房源场景收口后，下一条产品线可转向团购场景客户动作、接龙投影，或继续企业微信真实会话存档 P0 联调。

## 9. 新 Codex 会话接手时的第一条提示词

```text
请先读取 AGENTS.md、docs/project-memory.md、docs/decisions.md、docs/pitfalls.md、docs/dev-log.md、docs/handoff-latest.md、docs/handoff-latest-2.md、docs/handoff-latest-3.md，并执行 git status --short --branch、git diff --stat。

当前房源场景已经收口：长标题不拆字段；客户页链接是主分享路径；customer-action-plugin 第一版已落地 lead-contact 和 appointment；房源工作台内可按 noteId 查看客户动作和线索；我的笔记卡片有客户信息入口和红点；图片/视频支持封面、删除、排序；房源状态支持推广中/已租/暂停推广；客户页会根据状态关闭新增转化动作；拨号后可标记已联系。

请不要从头重构。下一步先做完整 diff 复核，按“后端能力 / 小程序体验 / 文档 / 本地杂项”分组确认哪些应提交，明确排除 miniprogram/project.config.json 和 企业微信客服服务须知.pdf。然后建议在微信开发者工具重新编译/真机冒烟，确认无问题后分组提交。
```
