# teamBuy 阶段性交接归档

更新时间：2026-06-20
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`
当前分支：`main`  
当前最新提交：以 `git log -1 --oneline` 为准。
本地状态：当前订单 / 消息 / 商品 P1 / 站内消息左右气泡已完成两组代码提交；仍需排除微信开发者工具自动改动 `miniprogram/project.config.json` 和未跟踪 PDF `企业微信客服服务须知.pdf`。

最新补充：
- 2026-06-20 收口：已完成当前大 diff 复核，未跟踪 PDF 不纳入提交，`miniprogram/project.config.json` 暂不纳入提交。
- 已提交后端能力：`feat: add lightweight orders and messaging backend`，包含订单接口、消息接口、消息模型、归档 parser、schema、测试和 mock 数据。
- 已提交小程序体验：`feat: add miniapp orders and messaging flows`，包含订单页、消息页、消息入口组件、商品 SKU/名单体验、客户页和我的页入口。
- 本轮收口验证：小程序全量 JS 检查通过；小程序 JSON 解析通过；Python 3.12 `compileall` 通过；`pytest backend/tests/test_app.py -q` 为 66 passed；`pytest backend/tests -q` 为 103 passed；`git diff --check` 通过。
- 下一步继续执行生产后端部署，部署后补充公网验证结果；小程序体验版仍由用户在微信开发者工具中手动上传。
- 站内消息详情页已改为微信式左右对话：当前登录用户消息在右侧，绿色气泡，头像在右；对方消息在左侧，白色气泡，头像在左，并展示对方昵称。
- 已修正“我的消息头像在气泡右边但整组仍贴左侧”的问题：消息行保持 `justify-content:flex-end`，只对我的头像/气泡设置排序，不再反转整条 flex 主轴。
- 后端消息线程行已返回 `participants`，包含 owner/buyer 的角色、昵称和头像；消息页不再只能按 senderUserId 猜测展示。
- 本次补充验证：小程序全量 JS 检查通过；小程序 JSON 解析通过；Python 3.12 环境下 `pytest backend/tests/test_app.py -q` 为 66 passed；compileall 通过；`git diff --check` 通过。
- `AGENTS.md` 已新增小程序上传约定：小程序预览、上传体验版和提交审核默认由用户在微信开发者工具中手动完成；Codex 不再默认尝试 CLI 上传，只做代码实现、JS/JSON 检查、后端测试和上传提醒。
- 商品 P1 已补：客户页 SKU 选择有属性组时按分组按钮展示，无属性组时保留组合 SKU 卡片兜底。
- SKU 选择售罄逻辑已优化：选项只要存在任一未售罄组合就可点，点击后会自动切到可买组合；提交时仍由后端校验具体组合是否售罄。
- 后端客户动作配置接口已为已提交 `order-intent / relay-intent` 回传 `submittedPayload`，客户再次进入可恢复已提交 SKU、数量、电话、地址、微信和备注。
- 团长 `note-actions` 商品下单/接龙名单已支持按 SKU 筛选；复制汇总、复制单条和发消息均基于当前筛选结果。
- 本轮验证：小程序全量 JS `node --check` 通过；小程序 JSON 解析通过；`git diff --check` 通过；Python 3.12 环境下 `pytest backend/tests/test_app.py -q` 为 66 passed；`.venv` 是 Python 3.9.6，跑 pytest 会卡在 `dataclass(slots=True)`，后续测试请用 Codex runtime Python 3.12。
- 本轮已实现“商品展示基座 + 团购模式”：`groupbuy_product` 继续兼容旧类型，但小程序前台改为商品展示口径。
- 商品 SKU 配置保存到 `structuredData.skuConfig`，支持属性组、选项、组合 SKU、价格、说明和售罄状态；截止时间选填。
- `conversionConfig.enableGroupRelay` 控制是否开启团购接龙；未开启时客户页只展示商品，开启后客户可选 SKU、数量并提交电话 / 微信 / 备注。
- 团购接龙使用 `customer_actions` 的 `relay-intent` 保存，不投影到 `lead_reminders`，不进入轻 SCRM；同一客户同一商品只允许一条有效接龙。
- 后端会拒绝关闭团购后的新增接龙、售罄 SKU 提交和重复提交；本轮不引入地图、支付、订单、库存扣减、核销、分账接口。
- 团长端 `note-actions` 已针对商品展示为“接龙名单”，支持查看头像、昵称、SKU、数量、联系方式、备注、提交时间，并支持复制汇总、复制单条和电话拨号。
- 我的笔记商品卡已改为展示“接龙 N / 接龙名单”，进入名单后沿用客户动作已读逻辑。
- 本地 mock 已补商品资料 `note_seed_groupbuy_product_001` 和接龙样例 `action_seed_relay_001`；当前运行态可直接测商品工作台、客户页 SKU 接龙和团长接龙名单，且 `lead_reminders=0`。
- 小程序“我的”页的“生成测试数据”现在会给当前登录用户生成 3 条房源 + 1 条商品，解决 seed owner 与设备本地 mock 用户不一致时看不到商品数据的问题。
- 当前小程序 `apiBaseUrl` 已恢复为生产 `https://teambuy.lifelove.top`。企业微信客服接收消息和真机微信登录都应以生产环境为主测入口；本地 mock 只作辅助。
- 商品接龙名单和商品工作台顶部动作已修移动端布局：接龙卡头像/昵称/状态不再挤压，按钮不再占满整行；窄屏下顶部主动作可自然换行。
- 本地 mock 模式下“微信登录”不走 mock 身份；正式微信登录需要线上 HTTPS 后端配置小程序 AppSecret，本地测试请点“本地 mock 登录”。
- 商品工作台底部标签 / 专题输入已修手机宽度溢出；SKU 新增选项现在为空输入 + placeholder，不会要求先删除“选项3”。
- 商品价格规则已调整：不在商品基础字段前置展示单一价格；有 SKU 时以 SKU 价格为准，未设置 SKU 属性时才显示“单一价格”兜底。
- 资料详情底部“删除 / 保存”改为左右分布，避免手机端按钮错位。
- 2026-06-19 02:41 用户转发贝壳房源小程序给企业微信，生产会话存档收到 `msgtype=weapp`，字段只有小程序外壳：`appid=wxcfd8224218167d98`、标题 `三江尊园 全天采光 好楼层 拎包入住`、来源 `贝壳找房丨二手房新房租房装修`、`pagepath`、`houseCode=101137825091`、`cityId=150200`；没有价格、户型、面积、图片、地址和经纬度。
- 已修复 `weapp` 解析：`ContentObjectPayload.metadata` 保存小程序元数据，`ContentObjectAdapter`、`WecomMessageNormalizer`、`MessageAggregator`、`MessageType` 均支持小程序卡片；普通客服同步和会话存档都能入库。
- 小程序卡片前台保存为 `sourceType=miniapp`、`systemCategory=小程序`，正文只展示标题、来源、appid、houseCode，完整 `pagePath` 放在 `visibilityConfig.structuredData.miniapp.pagePath`。
- 贝壳小程序卡片只给“可能是房源信息”的中置信提示，不自动高置信生成房源工作台；`miniapp_card` 不提取手机号，避免 pagepath 数字污染电话字段。
- 已修复生产历史空笔记 `note_4ecff85fca` / `card_336b070ffc` / archive `wecom_archive_msg_04c9699da3`，公网读取确认 `phone=null`、`sourceType=miniapp`、`typeSuggestions` 含房源提示。
- 生产后端已重新部署，`https://teambuy.lifelove.top/health` 通过；本地后端验证 `pytest backend/tests -q` 为 98 passed。
- 小程序 `app.json` 已配置贝壳 appid 到 `navigateToMiniProgramAppIdList`；地图选点只声明 `chooseLocation`。
- 编辑页新增“原小程序房源”块，客户页新增“查看贝壳原房源”动作，使用 `wx.navigateToMiniProgram` 跳贝壳原房源；失败时复制房源编码兜底。
- 后端已为当前贝壳小程序卡生成并保存候选网页 URL：`https://m.ke.com/baotou/ershoufang/101137825091.html`，写入 `visibilityConfig.sourceUrl` 和 `structuredData.miniapp.webUrl`；该 URL 可能触发贝壳验证码，仅作备用打开/复制，不作为稳定爬虫来源。
- 贝壳小程序房源候选默认开启轻 SCRM、留资、预约、微信咨询和分享图入口，不开启联系电话展示。
- 已修复“小程序卡确认成房源字段卡时丢失 miniapp 元数据”的问题；生产 `note_4ecff85fca` 当前为 `property_listing + sourceType=miniapp`，保留 `houseCode=101137825091` 和完整 `pagePath`。
- 后端房源高置信识别已把标题小区名纳入 `community` 信号；新增测试覆盖标题为小区名、正文含户型/价格/位置的高置信房源。
- 编辑页和客户页会记住最近一次房源城市；地址不含城市时会用最近城市补全后再请求腾讯地图地理编码，减少同名小区误匹配。
- 客户页动作文案已改为客户语言：`电话咨询`、`留下电话/微信`、`预约看房`、`微信咨询`。
- 客户页留联系方式支持电话或微信二选一；预约看房支持今天/明天快捷项，并可选择具体日期和时间，精确到分钟。
- 房源/团购列表主动作已从“生成推广/生成海报”改为“转发给好友”，并接入微信原生分享；工作台顶部主动作已调整为一行三列：“分享文案 / 转发给好友 / 客户页预览”，分享图入口已弱化为“保存分享图”。
- `pages/note-edit/index` 已新增浅绿色小尺寸悬浮保存按钮，默认吸附右侧中部，拖动后按左右距离吸附；底部保存按钮仍保留。
- 发布者房源/团购联系方式会本地记忆手机号；客户页留资手机号也会本地记忆，后续默认带入但可修改。
- 客户页预览已补充房源图片横向图库，分享卡片仍用封面图，页面内可查看完整图片；正文里的分享按钮已移除，改为右侧靠下两个固定浮动按钮。
- 客户页地图动作已改为“选择导航App / 微信内置地图 / 复制地址”，导航 App 不支持时回退微信内置地图。
- 客户页地图头部已去掉经纬度数字，只展示“腾讯地图 / 正在匹配默认地址 / 按默认地址定位”。
- 新增后端 `GET /api/location/geocode`，由后端使用 `TENCENT_MAP_KEY` 调腾讯地图地理编码，把房源默认地址转成经纬度；Key 不暴露给小程序。
- 编辑页和客户页在有默认地址但没有坐标时会尝试自动解析地图点，成功后显示小房子 marker；解析失败或未配置 Key 时继续用微信原生选点兜底。
- `backend/.env.example` 已增加 `TENCENT_MAP_KEY` / `TENCENT_MAP_GEOCODER_URL`，上线要在后端环境变量补真实腾讯地图 Key。
- 腾讯地图 Key 已配置到本地和生产后端 `.env`，生产后端已重建；公网 `/api/location/geocode` 已验证可返回坐标。
- 产品方向已从显性的房源/团购 4 态流程，收敛为“自动生成结果 + 轻量整理”的两层工作台。
- 高置信房源/团购：后端直接写入 `cardState=generated`，小程序打开 `pages/note-edit/index` 时直接看到工作台，而不是流程步骤页。
- 中置信资料：保留普通资料卡，写入 `typeSuggestions`，小程序提示“这条资料像是？房源 / 团购 / 普通笔记”。
- 低置信资料：直接作为普通笔记，不打扰用户。
- 小程序 `pages/note-edit/index` 已重构为工作台 UI：房源/商品卡、图片与视频、功能组、轻 SCRM、基础信息、标签与专题；核心板块支持隐藏/恢复。
- 普通笔记可通过 `+ 添加功能` 增加轻 CRM、留资表单、预约、接龙功能组。
- `pages/notes/index` 保留每个资料块的上传时间，新增中置信轻提示和“未整理”轻入口；默认仍按上传/导入时间倒序。
- 后端笔记搜索已支持宽松模糊搜索：结构化字段、标签、专题、上传日期、归一化日期数字都参与搜索，`618` 可命中 `6月18日` / `2026-06-18` 类日期。
- 工作台编辑体验已细化：字段输入区改为更清晰的信息块样式，常见字段增加快捷项，图片素材支持设封面和从当前资料卡删除。
- “客户页”已新增 `pages/note-preview/index` 作为 owner 侧客户可见内容预览；`pages/note-poster/index` 已改为“分享图”辅助页，用于保存静态图片和复制发群文案。
- 分享图页已改浅色背景，提供 5 个强调色可选，并新增“保存海报”到相册；分享图标题限制为最多 3 行，canvas 保存时给价格和详情行保留安全空间；客户页动作按钮已改为动作卡，支持分享、联系、留资、预约、接龙和地图定位。
- 房源编辑页地址字段已支持微信原生腾讯地图选点，保存 `structuredData.mapLocation` 后客户页可调用 `wx.openLocation`。
- 标签和专题已增加推荐快捷项，默认标签直接显示并可删除，减少手动输入。
- 商圈字段已增加快捷点选，并会把识别出的商圈拆成短标签候选；`未整理`、`待跟进` 和过长标签已从前台推荐/展示中过滤。
- 地址字段会先展示默认地址；选过地图点后展示真实小地图预览。
- `app.json` 已声明 `chooseLocation` 私密接口；地图选点成功后会自动保存经纬度，不必再手动保存。
- 客户页和编辑页地图 marker 已增加 `🏠` label / callout；客户页会展示经纬度，没经纬度时提示先在编辑页选择小区位置。
- 价格识别已优化为优先读取价格关键词行，并避开服务费/面积/房号数字抢占。
- 本轮验证：后端编译通过，`pytest backend/tests -q` 93 passed，小程序 JS/JSON 静态检查通过。
- 用户确认旧资源详情页先不要删，先隐藏起来并记录好，强制已认领资料走新的 `UserNote` 资料卡链路。
- 后端 `/api/cards` 和 `/api/cards/{card_id}` 已新增 `sourceNoteId`，用于把兼容旧 Card 映射回新 `UserNote`。
- 小程序新增 `miniprogram/utils/resource-navigation.js`，统一处理资源跳转：有 `sourceNoteId` 时打开 `/pages/note-edit/index`，没有时才回退旧 `card-view/card-edit`。
- 已接入统一跳转的入口包括：资源库、首页热门资源、访问记录、客户资料库、待联系列表、线索详情、管理页打开/编辑资源。
- 旧 `card-view` 和 `card-edit` 文件仍保留；拥有者直接打开带 `sourceNoteId` 的旧页面时会自动重定向到新笔记编辑页。
- 客户分享访问旧 `card-view` 暂不强制拦截，避免新客户展示页完成前影响外部查看。
- 本轮验证：后端编译通过，`pytest backend/tests -q` 91 项通过，小程序 JS/JSON 静态检查通过。

最新完成：
- 新增 `docs/stage2-docs/12-typed-content-card-architecture.md`。
- 固定产品原则：统一流程是“收藏 -> 编辑 -> 整理 -> 生成”，但数据结构必须分型。
- 后端 `content-to-note` 已支持规则识别 `property_listing` 房源字段卡、`groupbuy_product` 团购商品卡、`text_note` 文本卡、`link` 链接卡。
- 第一版 typed card 数据继续放在 `UserNote.visibilityConfig.cardType/cardState/structuredData/typeSuggestions`，不新建房源/团购表。
- 房源字段第一版：小区、户型、价格、水电物业、商圈、地址、服务费、备注、联系方式、图片。
- 团购字段第一版：商品名、价格、规格、截止时间、自提/配送、取货地点、库存备注、联系方式、图片。
- “整理”接口已按 `cardType` 分型：链接转文章/阅读卡口径，房源/团购补摘要和生成建议。
- 房源/团购已新增 `conversionConfig`：控制联系电话展示、轻 SCRM、线索收集、预约看房、私聊咨询、团购接龙、分享图入口和下单按钮预留。
- 新增 `/api/notes/{note_id}/generate`：当前生成 `generated` 状态和启用动作清单，正式海报/场景页渲染后续由场景生成 Skill 接管。
- 搜索已覆盖 `structuredData`，可按小区、商圈、商品规格等字段命中。
- 小程序“我的笔记”列表已分型展示链接卡、房源卡、团购卡、普通文本卡。
- 小程序笔记编辑页已增加房源和团购字段表单，同时保留来源类型、弱分类、标签和专题编辑；房源/团购还新增“功能配置”和“生成场景页”动作。
- 静态测试 `test_import_flow_uses_single_import_artifact_transaction` 已校准为检查真实成功保存入口 `_process_import_batch`。

最新验证：
- `python -m compileall backend/app backend/tests`：通过。
- `pytest backend/tests -q`：91 passed。
- 小程序所有 `.js` `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- 生产 backend 已部署到 `https://teambuy.lifelove.top`，健康检查通过。
- 生产 generate 路由已验证：假 note 请求返回“笔记不存在”，说明接口已挂载。

当前注意：
- 本轮为规则版，不调用大模型。
- 低置信内容会保留为 `text_note` 并写入 `typeSuggestions`，但小程序“手动转换类型”还没做。
- 当前 `generate` 只是生成态配置结果，不是真正的场景生成 Skill。客户页链接是主分享路径；分享图只是可保存到相册的辅助素材，后续可再增强为更精美的推广图。
- 失败导入路径仍因没有 Card artifact 而走分散保存，后续如要完全事务化，需要先调整仓储接口；已写入 `docs/pitfalls.md`。

上一轮已提交修复：
- `relay-list` 组件已增加接龙时间和跟进状态兜底格式化，资源详情页不再直接显示 ISO 时间或 `pending`。
- 资源详情页已绑定已接龙名单的 `标记已跟进` 和 `删除无效` 操作。
- 卡片编辑页素材上移/下移已修复旧 `sortOrder` 导致排序回弹的问题。
- 小程序内“发给客服”入口已改为“添加 / 快速入库”：中间 tab 指向手动添加资源页，`pages/imports/index` 仅作为外部导入后的“待认领导入”页。
- 小程序可见页面已移除“发给客服 / 立即发给客服 / 去发给客服”和可见 mock 导入按钮。
- 已验证：小程序 JS 静态检查通过，小程序 JSON 解析通过，`pytest backend\tests\test_app.py -q` 34 项通过。

本轮改动：
- 后端上传接口和企微媒体转存已接入媒体处理服务，图片通过 Pillow 转 WebP，视频通过 ffmpeg 转 H.264/AAC MP4。
- 上传响应新增 `originalSize`、`storedSize`、`compressed`。
- 小程序新增原生 `resource-store`，承担 Pinia 类似的资源集中管理职责。
- 小程序新增媒体缓存工具，页面展示使用 `coverDisplayUrl` / `media[].displayUrl`，保存仍提交正式 URL。
- 高意向访客待联系 / 已联系 / 备注已从小程序本地 storage 升级到后端 `lead_reminders`。
- 新增统一“待联系”页面 `pages/leads/index`，可跨资源处理待联系线索。
- 资源详情页发布者入口已改成更明显的“线索管理”提示条。
- 待联系页筛选项已改成胶囊样式，线索卡片会展示来源资料，并分别提供“资源详情”和“线索管理”入口。
- 线索第三阶段已新增个人跟进记录和下次跟进日期：后端保存 `followUpLogs` / `nextFollowUpAt`，待联系页可追加跟进记录。
- 线索第四阶段已新增时间筛选和跟进优先级排序：全部时间、今日、逾期、未来、未设置；卡片展示最近 3 条跟进记录。
- 线索第五阶段已新增页内提醒看板：今日待跟进、已逾期、一键只看未处理；暂不接微信通知。
- 线索第六阶段已新增归档结论：无效、暂不跟进、已完成；保存归档原因和归档时间。
- 线索第七阶段已新增线索详情页：列表页只保留摘要和关键动作，详情页承载备注、跟进记录、归档原因和状态操作。
- 线索第八阶段已新增发布者私有客户资料：手机号、微信号、预算、意向等级。
- 线索第九阶段已新增客户资料库 `pages/customers/index`：按意向等级筛选，入口位于“我的”和“待联系”。
- 客户资料库第二阶段已新增搜索和快捷复制：可搜昵称、手机号、微信号、预算、来源资料；手机号/微信号可一键复制。
- 客户资料库第三阶段已新增排序和快捷筛选：高意向优先、最近更新、有电话、有微信、有预算。
- 客户资料库第四阶段已新增“复制客户摘要”：复制当前筛选结果为表格文本。
- 客户资料库第五阶段已强化客户详情页：客户资料区前移，并支持复制单个客户完整档案。
- 已验证：`python -m compileall backend\app backend\tests` 通过，`pytest backend\tests -q` 60 项通过，小程序 JS/JSON 检查通过。

## 1. 项目背景与目标

teamBuy 是一个面向微信私域场景的小程序工具。当前产品名和 UI 方向为“资料整理助手”。

项目核心目标不是做团购交易系统，也不是做支付、订单、库存、分账或完整 CRM，而是验证一条“微信内容资源助理”主链路：

```text
企业微信客服收到用户转发的微信笔记 / 链接 / 图片 / 视频 / 位置等素材
  -> 后端通过企业微信客服回调与 sync_msg 拉取消息
  -> 聚合消息并生成资源卡片草稿
  -> 小程序端认领、编辑、保存、发布
  -> 分享给客户查看
  -> 客户浏览、电话直拨、复制字段、实名接龙
  -> 发布者查看访问统计、接龙名单、跟进状态
  -> 资源库搜索、筛选、复用
```

第一优先用户是房产中介，第二优先用户是团购团长。当前 v0.1 重点是把“素材归档 -> 资源卡片 -> 分享查看 -> 浏览/接龙/跟进 -> 资源库复用”跑通。

需要特别注意：企业微信真实 `sync_msg` 主链路目前仍因企业微信认证/权限配置问题阻塞，不能把手动添加资源或 mock 链路当作最终上线通过。

## 2. 当前阶段目标

当前阶段处于 v0.1 小程序产品化与本地可验收链路补齐阶段。

阶段目标：

- 在企业微信真实权限暂时无法继续推进时，先把小程序端资源管理、发布、分享、接龙、线索跟进体验打磨完整。
- 参考 `docs/png/` 里的页面图，尽量复刻页面功能与体验，但 `docs/png/` 仅作为参考图，不纳入资源入库。
- 保持真实企业微信导入为最终主链路；手动添加资源只是临时可用入口和本地验收入口。
- 所有小程序页面使用自定义导航 `navigationStyle: "custom"`。
- 阶段完成后需要在微信开发者工具里人工验收，自动化测试不能替代真实小程序运行环境验收。

## 3. 已完成的功能

### 3.1 后端基础能力

- FastAPI 后端骨架。
- 本地 JSON/mock 持久化与 PostgreSQL 目标仓储适配。
- `/health` 健康检查。
- 企业微信客服回调 GET/POST 骨架。
- `sync_msg` 客户端、cursor、任务锁、任务日志、媒体转存抽象。
- mock 企业微信导入、消息聚合、卡片草稿生成。
- 卡片创建、更新、发布、复制复用。
- 浏览统计、匿名浏览隔离、登录访客统计。
- 实名接龙、删除无效接龙、标记已跟进。
- 资源分类标签接口。
- 卡片 `media` 字段，支持图片/视频结构化保存。
- 手动上传资源文件接口 `POST /api/uploads/asset`，当前用于小程序本地上传图片/视频。
- 手动上传图片/视频会先压缩再存储，图片为 WebP，视频为 H.264/AAC MP4，默认不保存原始大文件。
- 删除资源时同步清理该资源的访问记录和接龙线索。
- 删除资源时同步清理该资源的访问记录、接龙线索和待联系提醒。
- 登录访客统计增强：
  - 同一登录用户重复访问聚合为一条记录。
  - 返回 `viewCount`。
  - `viewedAt` 使用最新访问时间。
- 接龙状态增强：
  - 同一用户对同一资源只允许一条 active 接龙。
  - stats 返回 `currentUserRelay`。
  - 发布者标记已跟进后，客户侧能读取到 `followUpStatus=followed`。

### 3.2 小程序基础页面

- 登录页。
- 首页。
- 资源库页。
- 添加资源页。
- 待认领导入页。
- 手动添加资源页。
- 标签管理页。
- 资源编辑页。
- 资源详情 / 分享查看页。
- 管理页 / 访问详情页。
- 访问记录页。
- 我的页。
- 自定义导航组件 `custom-nav`。
- tabBar 图标已接入 `miniprogram/static/tab`。

### 3.3 资源库与标签

- 资源库支持真实搜索。
- 资源库支持分类筛选与标签筛选。
- 第二排标签只展示真实自定义标签，不再混入“客服接收 / 手动添加 / 可接龙 / 带链接”等伪标签。
- 标签管理支持新增、删除。
- 卡片可绑定 `categoryIds`。
- 删除标签时会从用户卡片中移除对应绑定。
- 资源库支持删除资源。

### 3.4 手动添加资源与素材

- 手动添加资源页支持上传图片、视频、文件。
- 图片/视频上传到后端后会压缩，资料库保存压缩后的展示 URL。
- 图片/视频写入卡片结构化 `media`。
- 附件类文件继续补充到详情文本。
- 首张图片默认作为封面。
- 多图上传时明确首图为封面，其余图片/视频进入详情。
- 手动添加资源可选择自定义标签。
- 可保存到资源库、进入编辑页。
- 可发布并预览。

### 3.5 资源编辑页

- 编辑页改成接近最终发布页的“所见即所得”结构。
- 顶部封面区可直接编辑标题、项目名、位置。
- 不再显示“封面图片链接”技术字段。
- 详情素材在编辑页内按正式展示形态呈现。
- 点击图片可设为封面。
- 支持删除素材、上移、下移。
- 支持发布后继续上传图片/视频。
- 新上传素材写入当前卡片 `media`，保存修改后持久化。
- 编辑页按钮文案已改为“保存修改 / 发布并查看”，避免“保存草稿”误解。

### 3.6 资源详情 / 客户分享页

- 资源详情页展示封面、标题、项目、位置、详情文本、字段复制、详情素材。
- 详情素材支持多图预览和视频播放。
- 电话直拨。
- 复制信息。
- 复制来源链接。
- 分享资源使用小程序原生 `open-type="share"` 调起微信分享面板。
- 客户视角不展示 PV/UV/接龙数统计。
- 客户视角不展示接龙名单。
- “访问详情”仅发布者可见。
- 客户提交接龙后：
  - 页面切换为“已提交接龙”状态。
  - 输入框和提交按钮隐藏。
  - 刷新后通过 `currentUserRelay` 恢复已提交状态。
- 发布者标记已跟进后：
  - 客户重新打开资源页显示“发布者已跟进”。
  - “已提交”和“已跟进”有不同状态卡样式。

### 3.7 管理页 / 访问详情页

- 发布者可查看 PV、UV、匿名 PV、接龙数。
- 发布者可查看登录访客列表。
- 发布者可查看接龙名单。
- 接龙名单按状态分组：
  - 待跟进
  - 已跟进
  - 全部
- 默认展示待跟进线索。
- 接龙线索支持：
  - 电话直拨
  - 复制电话
  - 复制地址
  - 标记已跟进
  - 删除无效
- 待跟进线索高亮。
- 登录访客区支持：
  - 高意向
  - 最近
  - 全部
- 当前高意向规则：
  - `viewCount >= 2`
  - 且该用户尚未接龙
- 访客标记：
  - 重复访问但未接龙：高意向
  - 已提交接龙：已接龙
  - 其他：普通访问
- 高意向访客支持：
  - 复制昵称
  - 加入待联系
- 待联系提醒支持：
  - 标记已联系
  - 取消待联系
  - 已联系后清除记录
- 待联系提醒已升级为后端持久化：
  - 数据模型为 `LeadReminder` / `lead_reminders`
  - 支持 `pending` / `contacted`
  - 支持备注 `note`
  - 同一资源同一访客只保留一条提醒
  - 用户换手机后仍可读取自己的待联系线索

### 3.9 统一待联系页

- 新增小程序 `pages/leads/index`。
- 我的页新增“待联系线索”入口。
- 页面支持待联系、已联系、全部筛选。
- 筛选项使用胶囊样式。
- 每条线索展示来源资料名称。
- 支持保存备注、标记已联系、恢复待联系、清除线索。
- 支持选择下次跟进日期、追加跟进记录，并展示最近一条跟进记录。
- 支持按跟进时间筛选，并按逾期、今日、未来、未设置、已完成排序。
- 跟进记录区展示最近 3 条记录。
- 顶部提醒看板支持点击今日 / 逾期 / 未处理快速筛选。
- 支持已归档筛选、无效 / 暂不跟进 / 已完成结论动作，以及归档原因记录。
- 线索详情页支持完整编辑备注、追加跟进、选择下次跟进、归档结论和恢复待联系。
- 线索详情页支持维护发布者私有客户资料：手机号、微信号、预算、意向等级。
- 客户资料库集中展示已沉淀客户资料的线索，并支持按意向等级筛选。
- 客户资料库支持搜索和手机号 / 微信号复制。
- 客户资料库支持高意向优先 / 最近更新排序，以及有电话 / 有微信 / 有预算筛选。
- 客户资料库支持复制当前筛选结果的客户摘要。
- 线索详情页支持复制单个客户完整档案。
- 支持从线索打开对应资源详情页和资源管理页。

### 3.8 已通过的自动化检查

最近一次相关检查已通过：

```text
小程序所有 .js：node --check 通过
小程序所有 .json：JSON 解析通过
python -m compileall backend\app backend\tests：通过
pytest backend\tests -q：60 passed
```

注意：这些只代表本地逻辑和静态检查通过，不等于微信开发者工具或真实企业微信链路验收通过。

## 4. 已修改 / 新增的文件

### 4.1 主要后端文件

- `backend/app/services/app_service.py`
- `backend/app/services/repository.py`
- `backend/app/api/routes_cards.py`
- `backend/app/schemas/cards.py`
- `backend/app/models/domain.py`
- `backend/tests/test_app.py`
- `backend/tests/test_media_processing_service.py`
- `backend/tests/test_media_storage_service.py`
- `backend/core/schema.sql` 相关迁移/表结构文件已在历史提交中维护

### 4.2 主要小程序文件

- `miniprogram/app.js`
- `miniprogram/app.json`
- `miniprogram/app.wxss`
- `miniprogram/services/api.js`
- `miniprogram/utils/request.js`
- `miniprogram/utils/dashboard.js`
- `miniprogram/utils/nav.js`
- `miniprogram/components/custom-nav/*`
- `miniprogram/components/relay-list/*`
- `miniprogram/components/field-copy-row/*`
- `miniprogram/components/card-preview/*`
- `miniprogram/pages/home/*`
- `miniprogram/pages/library/*`
- `miniprogram/pages/imports/*`
- `miniprogram/pages/resource-create/*`
- `miniprogram/pages/tag-manage/*`
- `miniprogram/pages/card-edit/*`
- `miniprogram/pages/card-view/*`
- `miniprogram/pages/manager/*`
- `miniprogram/pages/leads/*`
- `miniprogram/pages/visits/*`
- `miniprogram/pages/profile/*`
- `miniprogram/pages/login/*`
- `miniprogram/static/tab/*`

### 4.3 文档文件

- `AGENTS.md`
- `docs/project-memory.md`
- `docs/decisions.md`
- `docs/pitfalls.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/prompts/codex-start.md`
- `docs/prompts/codex-handoff.md`
- `docs/stage2-docs/*`
- `docs/qa/*`

### 4.4 当前不要纳入提交的文件/目录

- `docs/png/`
  - 这是页面参考图目录，只用于参考，不加入资源入库，不应随便提交。
- `backend/mock/runtime-state.json`
  - 当前为本地运行态数据，已被多轮手动测试污染，除非明确要固化 mock 状态，否则不要提交。
- `miniprogram/project.config.json`
- `miniprogram/project.private.config.json`
  - 微信开发者工具本地配置，当前为未跟踪文件，不要默认提交。
- `docs/qa/当前项目_验收报告m1.md`
  - 当前为未跟踪文件，未确认是否应纳入提交。

## 5. 当前代码状态

当前 `git status --short --branch`：

```text
## main...origin/main [ahead 27]
 M backend/mock/runtime-state.json
?? docs/png/
?? docs/qa/当前项目_验收报告m1.md
?? miniprogram/project.config.json
?? miniprogram/project.private.config.json
```

最新提交：

```text
feat: persist lead reminders and webp media
```

本地 `main` 已领先远端 `origin/main` 27 个提交，尚未推送。本轮未纳入 `backend/mock/runtime-state.json`、`docs/png/`、`docs/qa/当前项目_验收报告m1.md`、微信开发者工具本地配置。

最近关键提交包括：

```text
35c6a5f feat: manage visitor follow-up reminder states
feat: manage visitor follow-up reminder states
43e51cf feat: convert visitors into follow-up reminders
ae218b3 feat: highlight manager visitor intent
a0617c8 feat: filter manager relay leads
44016de feat: add relay lead quick actions
9753b99 feat: show followed relay status to customers
ece6e60 feat: close relay submission follow-up loop
3725ff0 feat: hide customer-facing private resource stats
d0d9f4a feat: support edit page media upload and sharing guard
548a65e feat: make card edit mirror published page
943640d feat: manage card edit media assets
```

当前没有需要继续提交的业务代码改动，工作区剩余改动主要是运行态数据和未跟踪本地/参考文件。

## 6. 已知问题和风险

### 6.0 2026-06-19 房产场景体验补强已完成

本轮继续围绕房源工作台优化了 5 类能力：

- 我的笔记房源卡片显示推广状态；客户信息入口文案更贴近业务，显示“待跟进 N / 客户 N”。
- 资料详情新增“复制客户话术”和“房源状态”：推广中 / 已租 / 暂停推广。
- 客户页遇到已租 / 暂停推广时，关闭新增电话咨询、留资、预约、私聊、接龙动作，只保留原房源 / 地图等信息入口。
- 图片与视频素材支持上移 / 下移排序，并立即保存排序结果。
- 客户动作页按“新线索 / 待跟进、预约看房、已联系 / 已归档、全部客户动作”分层；拨号成功后可提示标记已联系并写入跟进记录。

本轮验证：

- 小程序全量 JS `node --check`：通过。
- 相关页面 JSON 解析：通过。
- `git diff --check`：通过。
- Python 3.12 环境后端 `compileall`：通过。
- `pytest backend/tests -q`：100 passed。

### 6.1 P0：真实企业微信 `sync_msg` 仍未跑通

真实企业微信客服主链路仍卡在：

```text
errcode=48002
errmsg=api forbidden
from ip=81.70.84.35
```

当前判断更像企业微信后台权限、Secret、API 管理、客服账号权限、可信 IP 或认证状态问题，不应盲目大改代码。

企业微信认证目前用户侧也有问题，需要和官方沟通后才能继续真实权限配置。

### 6.2 手动添加资源不是最终主链路

手动添加资源已经可用于本地验收，但它不能替代：

- 企业微信客服真实接收微信笔记/链接。
- `sync_msg` 拉取真实消息。
- 图片/视频 `media_id` 及时下载与转存。
- 导入成功/失败通知。
- 用户认领真实导入内容。

### 6.3 小程序仍需微信开发者工具人工验收

自动化检查不能替代微信环境验收。尤其需要人工确认：

- 登录。
- 上传图片/视频预览。
- 保存、发布、查看。
- 微信原生分享面板。
- 电话直拨。
- 复制字段。
- 接龙提交。
- 发布者和普通客户身份切换后的权限差异。

### 6.4 待联系提醒仍不是完整团队协作能力

高意向访客“加入待联系 / 标记已联系 / 取消待联系 / 备注”已升级为后端持久化，但当前仍是发布者个人待办：

- 暂不支持多人分配。
- 暂不支持跟进提醒通知。
- 暂不支持跟进历史时间线。
- 暂不支持客户手机号自动沉淀为 CRM 客户档案。

如果后续要做团队协作，需要在当前 `lead_reminders` 之上继续增加负责人、提醒时间、跟进记录和权限模型。

### 6.5 隐私与权限风险

必须继续保持：

- 普通客户看不到统计卡片。
- 普通客户看不到接龙名单。
- 普通客户看不到电话、地址、快捷动作。
- `relay-list` 只有 `isOwner=true` 时渲染电话、地址和快捷动作。
- 后端非发布者 stats/list relays 必须继续脱敏，电话和地址置空。

### 6.6 工作区风险

当前存在未提交运行态数据和未跟踪参考文件。新会话不要批量删除或随便提交。

项目规则明确禁止批量删除文件或目录，不要使用：

```text
del /s
rd /s
rmdir /s
Remove-Item -Recurse
rm -rf
```

## 7. 用户已经确认过的产品 / 技术决策

- v0.1 不做交易系统，不做支付、订单、库存、核销、分账。
- 第一批优先用户是房产中介，其次是团购团长。
- 企业微信客服接收微信笔记/链接并自动归档，是最终核心主链路。
- 企业微信客服导入发生在小程序外部会话；小程序内不提供“发给客服”入口，中间加号是“添加 / 快速入库”。
- `pages/imports/index` 只作为外部导入后的待认领页，不暴露 mock 导入按钮。
- 企业微信权限认证问题暂时无法推进时，先继续小程序产品化开发。
- `docs/png/` 是页面参考图，不加入资源入库。
- 小程序所有页面使用 `navigationStyle: "custom"`。
- 原生小程序不直接使用 Pinia；资源状态集中到 `miniprogram/stores/resource-store.js`。
- 图片/视频会缓存到用户手机，本地展示路径和后端正式 URL 分离。
- 自定义导航标题不要用 WXML 属性实体串传递，避免显示 `&#x...`。
- tabBar 图标使用 `miniprogram/static/tab`，`-a` 未选中，`-b` 选中。
- 手动添加资源是临时入口，不替代企业微信导入。
- 手动上传的图片/视频作为结构化 `media` 保存，不塞进纯文本详情。
- 编辑页尽量接近用户最终看到的发布页，减少学习成本。
- 不向用户暴露“封面图片链接”这类技术字段。
- 资源进入编辑页后已经在资料库中，按钮使用“保存修改 / 发布并查看”，不再叫“保存草稿”。
- 资源详情页分享使用小程序原生 `open-type="share"`。
- 访问详情、统计、接龙名单属于发布者能力，普通客户不应看到。
- 同一用户对同一资源只允许一条有效接龙。
- 发布者标记已跟进后，客户侧应看到“发布者已跟进”。
- 管理页线索优先处理待跟进，支持按状态筛选。
- 高意向访客规则当前为“重复访问且未接龙”。
- 高意向访客待联系 / 已联系 / 备注已做后端持久化。
- 待联系提醒需要支持取消和标记已联系，避免本地提醒越积越多。

## 8. 下一步建议执行顺序

建议新会话按以下顺序继续：

1. 先读取项目规则和记忆文档：
   - `AGENTS.md`
   - `docs/project-memory.md`
   - `docs/decisions.md`
   - `docs/pitfalls.md`
   - `docs/dev-log.md`
   - `docs/handoff-latest.md`

2. 检查当前工作区：
   - `git status --short --branch`
   - `git diff --stat`
   - 确认不要提交 `backend/mock/runtime-state.json`、`docs/png/`、微信开发者工具本地配置。

3. 在微信开发者工具里人工验收最近补齐的小程序链路：
   - 手动添加资源。
   - 编辑页继续上传素材。
   - 保存修改、发布并查看。
   - 客户视角资源页隐私。
   - 客户提交接龙后已提交状态。
   - 发布者标记已跟进后客户侧已跟进状态。
   - 管理页接龙筛选、快捷动作。
   - 管理页访客高意向筛选与待联系提醒。
   - 待联系提醒的加入、标记已联系、取消待联系、清除记录。

4. 如果继续开发产品体验，优先做：
   - 给待联系线索增加跟进时间线和下次提醒时间。
   - 给线索增加手机号/微信号等客户字段，但注意普通客户侧隐私。
   - 客户资料库已支持私有客户标签、来源资料筛选、活跃/沉睡筛选、卡片快捷跟进和复制当前筛选跟进清单；后续如扩展标签，注意不要混用资源分类标签。
   - 继续补资源库/管理页的真实小程序人工验收问题。

5. 如果回到核心 P0 主链路，优先做：
   - 等用户解决企业微信认证/权限问题后，继续排查 `sync_msg 48002 api forbidden`。
   - 核对 `WECOM_SECRET` 是否为微信客服 Secret。
   - 核对企业微信后台是否允许 API 管理微信客服账号。
   - 核对 `WECOM_OPEN_KFID` 对应客服账号权限。
   - 核对可信 IP 是否包含 `81.70.84.35`。
   - 跑真实企业微信客服导入验收。

6. 每轮开发结束必须：
   - 运行小程序 JS 静态检查。
   - 运行小程序 JSON 解析检查。
   - 涉及后端时运行 `pytest backend\tests\test_app.py -q`。
   - 更新 `docs/dev-log.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/handoff-latest.md`。
   - 合理 commit。

## 9. 新 Codex 会话接手时的第一条提示词

可直接复制给新 Codex：

```text
请先读取：

- AGENTS.md
- docs/project-memory.md
- docs/decisions.md
- docs/pitfalls.md
- docs/dev-log.md
- docs/handoff-latest.md

然后执行：

- git status --short --branch
- git diff --stat

请先不要改代码。请输出：

1. 你理解的项目目标
2. 当前代码状态
3. 已确认的重要决策
4. 当前风险
5. 下一步建议执行顺序

注意：

- docs/png/ 是页面参考图，不要提交或入库。
- backend/mock/runtime-state.json 是本地运行态数据，默认不要提交。
- miniprogram/project.config.json 和 project.private.config.json 是本地微信开发者工具配置，默认不要提交。
- 当前真实企业微信 sync_msg 仍卡在 48002 api forbidden，手动添加资源不能替代最终主链路。
- 客户资料库常用视图目前是小程序本地 storage 偏好，不是后端持久客户数据。
- 客户资料库卡片已按客户资料、跟进状态、来源和操作分区，后续新增字段时不要再平铺堆到卡片主区域。
- 禁止批量删除文件或目录，严格遵守 AGENTS.md。
```
## 2026-06-10 补充：企业微信客服回调地址已拆分

- teamBuy 当前企业微信客服回调地址已从 `/api/wecom/callback` 调整为 `/api/wecom/kf/teamBuy/callback`。
- 企业微信后台请填写：`https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback`。
- 后端 `GET` 验证、`POST` 事件接收和 `/api/wecom/config-check` 的推荐回调地址已同步新路径。
- README、企业微信客服配置清单、真实联调记录、MVP 测试清单和腾讯云部署文档已同步新路径。
- 已验证：`python -m compileall backend\app backend\tests` 通过；`pytest backend\tests\test_app.py -q -k "wecom_callback or wecom_config_check"` 4 项通过。
- 注意：整份 `pytest backend\tests\test_app.py -q` 当前仍有 1 个与本次无关的环境断言失败，原因是本机 `DATABASE_BACKEND` 读取为 `postgresql`，测试期望 `postgres`。
- 生产补充：已 SSH 登录 `ubuntu@81.70.84.35`，同步生产后端路由文件并重建/重启 `backend` 容器。公网新地址已返回 `"hello-teamBuy"`，`config-check` 已返回新 callbackUrl。生产 `WECOM_CALLBACK_TOKEN` 已同步为企业微信页面当前 Token，原 `.env` 已备份到服务器 `backend/.env.callback-backup-20260610-1616`。若后台保存仍失败，优先核对完整 43 位 `WECOM_ENCODING_AES_KEY`。
## 2026-06-10 补充：企业微信回调新地址已保存成功

- 当前企业微信后台 `API接收消息` 已保存为：`https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback`。
- 本次失败根因不是新路径不可达，而是 FastAPI GET 验证接口直接返回字符串时被编码为 JSON 字符串；企业微信要求纯文本原样返回 `echostr`。
- 已修复 `backend/app/api/routes_wecom.py`：`GET /api/wecom/kf/teamBuy/callback` 使用 `PlainTextResponse` 返回验证明文。
- 已部署生产并重启 backend 容器；公网验证返回 `200 text/plain`，正文为 `hello-teamBuy`。
- 企业微信后台页面已由 Codex 操作点击保存，页面提示“保存成功”；生产日志确认企业微信请求命中新路径并返回 200。
- 本地验证：`python -m compileall backend\app backend\tests` 通过；`pytest backend\tests\test_app.py -q -k "wecom_callback or wecom_config_check"` 4 项通过。

## 2026-06-15 补充：提交前整理规则

- 当前正式产品名已按用户修正为“资料整理助手”；小程序分享兜底标题也应使用“资料整理助手资源”。
- 本轮可提交范围是企业微信客服回调新路径、`text/plain` 验证响应、测试和配套文档。
- 默认不要提交 `backend/mock/runtime-state.json`、`docs/png/`、`miniprogram/project.config.json`、`miniprogram/project.private.config.json`、未确认验收报告草稿。
- `docs/悦享互动宝 MVP 产品开发文档.md` 当前存在疑似换行符扰动，除非专门处理品牌文档，否则不要混入回调修复提交。
- 本轮验证需注意：当前 shell 没有 `python` / `pytest` 命令；系统 `python3` 为 3.9，不适合跑本项目 pytest。使用 Python 3.12 临时环境验证通过。
- `backend/requirements.txt` 已将不可安装的 `Pillow==12.2.0` 调整为当前可安装的 `Pillow==11.3.0`。
- 最近验证：`python -m compileall backend/app backend/tests` 通过；`pytest backend/tests/test_app.py -q -k "wecom_callback or wecom_config_check"` 4 项通过；小程序 `.js` `node --check` 通过。
- 后续每次遇到错误、失败验证或规避规则，都要同步写入长期记忆文档，避免只留在聊天记录里。

## 2026-06-15 补充：企业微信资料归档接口前的媒体容错准备

- 已补强真实 `sync_msg` 收档链路：图片/视频 `media_id` 下载失败时，写入 `media_retry_jobs`，但不再阻断同批文本、链接等内容生成待认领草稿。
- 已关闭真实链路的 mock 媒体 fallback，避免下载失败时生成假的 `/mock-media/...` URL。
- mock 链路仍保留 fallback，方便本地演示。
- 图片压缩已改为 Pillow 转 WebP，视频继续使用 ffmpeg；避免本地或部署环境缺少 ffmpeg 图片编码能力时回退原图。
- 最近验证：`python -m compileall backend/app backend/tests` 通过；`pytest backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q` 41 项通过。
- 明天拿到企业微信资料归档接口权限后，优先用真实转发笔记验证：回调触发任务、`sync_msg` 拉取、文本成草稿、图片/视频转存、失败时补偿队列可见。

## 2026-06-17 补充：插件化架构 Phase 1 已落地

- 当前正式架构方向已固定为“企业微信稳定基座 + 混合驱动 Skill + 小程序笔记与展示页”。
- 完整架构文档已新增：`docs/stage2-docs/08-plugin-architecture.md`。
- 后端已新增第一版无状态 `skill-router`：
  - `GET /api/skills/commands`：返回快捷指令注册表。
  - `POST /api/skills/route`：快捷指令优先、规则匹配其次，未知输入返回确认菜单。
  - `POST /api/skills/content-to-note/run`：将 `ContentObject` 转为规则版 `UserNoteDraft`，暂不持久化。
- 已确认文字类来源统一进入 `content-to-note`：微信笔记、聊天记录、链接文章、手动文字和后续 OCR 都由 Adapter 转成 `ContentObject`。
- 已确认 `note-to-comic-image` 作为独立渲染型 Skill 保留；`showcase-builder` 是小程序可视化配置工具，不是 AI 自动全权生成。
- 本轮补丁遇到一次依赖装配文件上下文不匹配，原因是 `backend/app/api/dependencies.py` 已采用新服务装配结构；已按当前结构修正。
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：6 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：47 项通过。
- 当前仍不要提交：
  - `backend/mock/runtime-state.json`
  - `docs/png/`
  - `docs/qa/当前项目_验收报告m1.md`
  - `miniprogram/project.config.json`
  - `miniprogram/project.private.config.json`
  - `docs/悦享互动宝 MVP 产品开发文档.md` 的疑似换行符扰动
- 下一步建议：
  1. 将现有企业微信 `sync_msg` 聚合结果接入 `ContentObject`，让真实导入和 Skill Router 共用同一条 `content-to-note` 入口。
  2. 增加 `SkillRun` 持久化和失败日志。
  3. 小程序新增“我的笔记”基础管理，再逐步承接展示页构建器。
  4. 等企业微信资料归档接口权限到位后，继续做 `wecom-archive-core` 的会话内容存档接入。

## 2026-06-17 补充：企业微信导入已接入 content-to-note

- `AGENTS.md` 已新增长期架构总纲，后续会话应优先遵守：
  - 完整架构文档入口：`docs/stage2-docs/08-plugin-architecture.md`。
  - 企业微信入口混合驱动：快捷指令优先、规则其次、AI 兜底。
  - 文字类来源统一进 `ContentObject -> content-to-note`。
  - 漫画图和展示页保持独立 Skill 边界。
- 已新增 `backend/app/services/content_object_adapter.py`，负责把企业微信 `RawMessage` 批次转为 `ContentObject`。
- `AppService.import_synced_messages()` 已改为先跑 `ContentObject -> content-to-note -> UserNoteDraft`，再兼容生成当前小程序依赖的 `Card` 草稿。
- 当前仍保留 `generatedCard`，不是最终笔记库模型；这是为了不打断现有待认领、编辑、发布和分享链路。
- 本轮发现并修复一个兼容问题：`link_article` 封面必须优先取链接 `coverUrl`，不能被企业微信媒体附件覆盖。
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：48 项通过。
- 下一步建议：
  1. 为 `SkillRun` 做持久化，记录导入时的 skillId、inputSnapshot、输出引用和失败原因。
  2. 为 `UserNote` / 笔记库建正式模型和接口。
  3. 小程序新增“我的笔记”基础管理页。
  4. 再把 `generatedCard` 逐步替换成 `UserNote` 到展示页/漫画图的后续流转。

## 2026-06-17 补充：P0/P1/P2 路线图已归档

- P0/P1/P2 实施路线图已新增：`docs/stage2-docs/09-p0-p2-roadmap.md`。
- 当前正式启动 P0 第一阶段：先把企业微信客服 `sync_msg` 作为过渡入口跑稳，不等待会话内容存档权限空转。
- 会话内容存档开通后进入 P0 第三阶段，并行新增 `wecom-archive-core`，不替换企业微信客服入口。
- 下一步优先做 `SkillRun` 持久化和导入失败日志，让 `content-to-note` 的每次执行可追踪、可排错、可计费。

## 2026-06-17 补充：工作区清理规则已更新

- 用户确认后续每次提交后尽量保持工作区干净。
- `docs/png/`、`docs/qa/当前项目_验收报告m1.md`、`miniprogram/project.config.json` 作为项目资料/配置纳入版本库。
- `miniprogram/project.private.config.json` 已加入 `.gitignore`，作为个人开发者工具配置保留本地。
- `backend/mock/runtime-state.json` 本地运行态改动已恢复，不提交测试运行数据。
- `docs/悦享互动宝 MVP 产品开发文档.md` 换行符扰动已恢复，不再污染后续 diff。

## 2026-06-17 补充：SkillRun 持久化和导入失败日志已完成

- 已新增 `SkillRun` 领域模型和仓储持久化，JSON / PostgreSQL 都支持。
- 企业微信导入成功时会保存 `content-to-note` 的成功 SkillRun，`outputRef` 指向当前兼容生成的 `Card`。
- 企业微信导入失败时会保存 failed SkillRun、失败导入批次和失败通知，失败可查询。
- 新增接口：
  - `GET /api/skills/runs`
  - `GET /api/wecom/import-failures`
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：50 项通过。
- 下一步建议：进入 P0 第二阶段前，先补强导入成功/失败通知口径和后台重试可视化；也可以直接开始正式 `UserNote` 模型和“我的笔记”基础接口。

## 2026-06-17 补充：导入通知口径和后台重试可视化已完成

- 导入通知文案已补强：
  - 成功：提示已整理完成，可去小程序认领、编辑和分类。
  - 成功但媒体未转存：提示媒体进入后台重试队列。
  - 失败：包含具体失败原因。
- 真实 `sync_msg` 导入通知 channel 使用 `wecom`，mock 导入继续使用 `mock`。
- 新增后台重试看板接口：`GET /api/wecom/retry-dashboard`。
- 新增失败导入重试接口：`POST /api/wecom/import-failures/retry?importBatchId=...`，需要 admin token。
- 失败导入重试按 `importBatchId` 重跑内容整理；媒体失败仍走 `media-retries/retry`，两类失败不要混用。
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：50 项通过。
- P0 第一阶段后端基础已基本收尾。下一步可以进入 P0 第二阶段：正式 `UserNote` 模型和“我的笔记”基础接口。

## 2026-06-17 补充：UserNote 模型和“我的笔记”基础接口已完成

- 已新增正式 `UserNote` 模型和仓储持久化，JSON / PostgreSQL 都支持。
- 企业微信导入成功后会双写：
  - `UserNote`：正式笔记库对象。
  - `Card`：当前小程序兼容草稿。
- `ImportBatch` 新增 `generatedNoteId`。
- `SkillRun.outputRef` 现在指向正式 `UserNote` ID。
- 认领导入时，note owner 会同步改为认领用户，状态从 `draft` 改为 `active`。
- 新增接口：
  - `GET /api/notes`
  - `GET /api/notes/{noteId}`
  - `PUT /api/notes/{noteId}`
  - `DELETE /api/notes/{noteId}`
- 笔记删除为软删除，不删除原始消息、导入批次或兼容卡片。
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：51 项通过。
- 下一步建议：小程序新增“我的笔记”基础页面，接 `/api/notes` 完成列表、搜索、详情、编辑和删除。

## 2026-06-17 补充：小程序“我的笔记”基础页面已完成

- 新增页面：
  - `miniprogram/pages/notes/index`
  - `miniprogram/pages/note-edit/index`
- 已接入 `/api/notes`：
  - 列表和搜索。
  - 详情查看。
  - 编辑保存。
  - 软删除。
- “我的”页和资源库快捷区已增加“我的笔记”入口。
- `services/api.js` 已支持 `fetchNotes`、`fetchNote`、`updateNote`、`deleteNote`，并归一化 note / generatedNote 媒体 URL。
- 最近验证：
  - 小程序所有 `.js` `node --check` 通过。
  - 小程序所有 `.json` 解析通过。
- 仍需微信开发者工具或真机人工验收页面渲染、输入、保存、删除和返回刷新。

## 2026-06-17 补充：会话内容存档配置与 wecom-archive-core 骨架已完成

- 用户已开通企业微信会话内容存档，后台页面为 `https://work.weixin.qq.com/wework_admin/frame#financial/corpEncryptData`。
- 本轮已生成 RSA 密钥对：
  - 私钥：`backend/secrets/wecom_archive_private.pem`
  - 公钥：`backend/secrets/wecom_archive_public.pem`
  - `*.pem` 被 `.gitignore` 忽略，不进入 Git。
- 配置文档已新增：`docs/stage2-docs/10-wecom-archive-config.md`。
- 后端新增会话存档配置项：
  - `WECOM_ARCHIVE_ENABLED`
  - `WECOM_ARCHIVE_SECRET`
  - `WECOM_ARCHIVE_PRIVATE_KEY_PATH`
  - `WECOM_ARCHIVE_PUBLIC_KEY_PATH`
  - `WECOM_ARCHIVE_SDK_LIB_PATH`
- 后端新增会话存档基础模型和仓储：
  - `WecomArchiveCursor`
  - `WecomArchiveMessage`
  - `wecom_archive_cursors`
  - `wecom_archive_messages`
- 新增接口：
  - `GET /api/wecom/archive/callback`
  - `POST /api/wecom/archive/callback`
  - `GET /api/wecom/archive/config-check`
  - `GET /api/wecom/archive/cursor`
  - `GET /api/wecom/archive/messages`
  - `POST /api/wecom/archive/mock-messages`
- 会话存档事件服务器当前默认复用 `WECOM_CALLBACK_TOKEN` 和 `WECOM_ENCODING_AES_KEY`；如后续拆独立配置，使用 `WECOM_ARCHIVE_CALLBACK_TOKEN` 和 `WECOM_ARCHIVE_ENCODING_AES_KEY`。
- 原始会话存档消息查询和样例写入需要 admin token。
- Codex 内置浏览器读取企业微信后台页面时，DOM/截图连续超时；本轮没有自动点击保存后台配置。后续应按配置文档人工粘贴公钥并保存，保存前确认页面是“会话内容存档”而不是“微信客服 API 接收消息”。
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive or wecom_config_check"`：7 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：57 项通过。
- 下一步建议：
  1. 生产已部署完成。公网 `/api/wecom/archive/config-check` 返回 `success=true`、`missing=[]`，公网 `/api/wecom/archive/callback?token=...&echostr=hello-archive` 返回 `hello-archive`。
  2. 企业微信后台“设置接收事件服务器”已保存成功。当前生产 archive 专用 Token / EncodingAESKey 已写入 `WECOM_ARCHIVE_CALLBACK_TOKEN` / `WECOM_ARCHIVE_ENCODING_AES_KEY`。
  3. 在企业微信后台会话内容存档页粘贴 `docs/stage2-docs/10-wecom-archive-config.md` 里的公钥并保存。
  4. 不要把真实 `WECOM_ARCHIVE_SECRET` 写入任何 Git 文档；真实值只留在生产 `backend/.env`。
  5. 接官方会话内容存档 SDK，拉取加密消息、解密、写入 `wecom_archive_messages` 并推进 `wecom_archive_cursors.seq`。
  6. 把解密消息 Adapter 到 `ContentObject -> content-to-note -> UserNote`。

## 2026-06-17 补充：会话存档回调已部署生产

- 用户提供生产 SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`。
- 已用 `rsync` 同步后端代码到服务器，原因是服务器 `git fetch origin` 长时间卡住。
- 同步前已备份服务器 `backend/app/api/routes_wecom.py` 本地 diff 到 `/home/ubuntu/teamBuy-deploy-backups/`。
- 已同步会话存档 RSA 密钥到服务器 `backend/secrets/`，并重建/重启 backend 容器。
- 生产 Docker 环境的会话存档密钥路径已修正为容器内绝对路径：
  - `/app/secrets/wecom_archive_private.pem`
  - `/app/secrets/wecom_archive_public.pem`
- 生产验证：
  - `/api/wecom/archive/config-check`：`success=true`，`missing=[]`。
  - `/api/wecom/archive/callback`：用生产 token 验证返回 `hello-archive`。
- 用户企业微信后台截图里填写的是本地 `backend/.env` 的 Token/AESKey；生产原 `WECOM_CALLBACK_TOKEN` / `WECOM_ENCODING_AES_KEY` 与本地不同。
- 为避免影响已跑通的微信客服回调，已将本地这组值写入生产 archive 专用配置：
  - `WECOM_ARCHIVE_CALLBACK_TOKEN`
  - `WECOM_ARCHIVE_ENCODING_AES_KEY`
- 重启后公网验证 `/api/wecom/archive/callback` 使用 archive 专用 token 返回 `archive-token-ok`。
- 用户确认企业微信后台“接收事件服务器”已保存成功。

## 2026-06-17 补充：P0 会话存档拉取与转笔记链路已实现

- 已新增真实会话存档拉取入口：
  - `POST /api/wecom/archive/pull`
  - 需要 admin token。
  - 从 `wecom_archive_cursors.seq` 继续拉取企业微信会话存档数据。
  - 拉取成功后写入 `wecom_archive_messages` 并推进游标。
  - SDK 或配置缺失时返回 502，并记录 failed 游标。
- 已新增归档消息处理入口：
  - `POST /api/wecom/archive/process`
  - 需要 admin token。
  - 将已解密归档消息转换为 `ContentObject -> content-to-note -> UserNote`。
  - 成功后在归档消息上记录 `generatedNoteId`、`generatedCardId`、`processedAt`，重复调用不会重复生成笔记。
  - 处理失败会写入 `processError`。
- 已新增官方 SDK 封装：
  - `backend/app/services/wecom_archive_client.py`
  - 调用 `GetChatData`、RSA 解密 `encrypt_random_key`、调用 `DecryptData`。
- 已补充配置项：
  - `WECOM_ARCHIVE_SDK_LIB_PATH`
  - `WECOM_ARCHIVE_PULL_LIMIT`
  - `WECOM_ARCHIVE_SDK_TIMEOUT_SECONDS`
  - `WECOM_ARCHIVE_PROXY`
  - `WECOM_ARCHIVE_PROXY_PASSWORD`
- 最近验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests` 通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：9 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：60 项通过。
- 仍需人工/生产验证：
  1. 将企业微信官方会话存档 Linux SDK 动态库放到生产容器可读路径。
  2. 设置生产 `WECOM_ARCHIVE_SDK_LIB_PATH` 为容器内绝对路径。
  3. 重启 backend 后确认 `/api/wecom/archive/config-check` 返回 `sdkConfigured=true`。
  4. 企业微信真实发一条测试消息。
  5. 调用 `/api/wecom/archive/pull`，确认 `savedCount>0` 或明确看到无新消息。
  6. 调用 `/api/wecom/archive/process`，确认生成 `UserNote`。
  7. 在小程序“我的笔记”中查看、编辑、删除该笔记。

## 2026-06-17 补充：P0 已部署生产，等待官方 SDK 动态库

- 生产已部署 commit：`5e104f0 feat: complete p0 wecom archive import`。
- 生产 `WECOM_ADMIN_TOKEN` 已补齐，值未写入文档。
- 生产公网验证：
  - `/api/wecom/archive/config-check`：`missing=[]`、`privateKeyReadable=true`、`sdkConfigured=false`。
  - `/api/wecom/archive/pull`：返回 502，错误明确为缺少 `WECOM_ARCHIVE_SDK_LIB_PATH`，并写入 failed cursor。
  - `/api/wecom/archive/process`：返回 200，当前 `processedCount=0`。
- 结论：
  - P0 后端链路已经部署。
  - 事件服务器已保存成功。
  - 真实会话内容拉取还不能人工通过，唯一阻塞是生产未安装/未配置企业微信官方会话存档 SDK 动态库。
- 下一步最自然顺序：
  1. 下载企业微信官方 Linux 会话存档 SDK 动态库。
  2. 放到服务器并让 Docker 容器可读。
  3. 设置 `WECOM_ARCHIVE_SDK_LIB_PATH=/app/secrets/<sdk动态库文件名>`。
  4. 重启 backend。
  5. 确认 `sdkConfigured=true`。
  6. 发真实企业微信测试消息。
  7. 调用 `pull -> process -> 小程序我的笔记验收`。

## 2026-06-17 补充：官方 SDK 已部署，真实拉取接口已跑通

- 用户下载了官方 Linux x86 v3.0 SDK：`sdk_x86_v3_20250205.tgz`。
- 已上传 `C_sdk/libWeWorkFinanceSdk_C.so` 到生产服务器 `backend/secrets/`。
- 已配置生产：
  - `WECOM_ARCHIVE_SDK_LIB_PATH=/app/secrets/libWeWorkFinanceSdk_C.so`
- 已修正 `docker-compose.yml`，让 backend 容器只读挂载 `./backend/secrets:/app/secrets:ro`。
- 生产公网验证：
  - `/api/wecom/archive/config-check`：`sdkConfigured=true`。
  - `/api/wecom/archive/pull`：返回 200，当前 `rawCount=0`、`savedCount=0`，说明 SDK 调用成功但没有新消息。
  - `/api/wecom/archive/process`：返回 200，当前 `processedCount=0`。
- 下一步人工验证只剩真实数据：
  1. 用已开启会话存档的成员和外部联系人产生一条新会话。
  2. 再调用 `/api/wecom/archive/pull`，预期 `rawCount` 或 `savedCount` 大于 0。
  3. 调用 `/api/wecom/archive/process`，预期生成 `UserNote`。
  4. 小程序“我的笔记”查看、编辑、删除该笔记。

## 2026-06-17 补充：21:57 测试消息暂未拉到

- 用户 21:57 发送“你好啊”后，已在 21:58 和 21:59 两次调用生产 `/api/wecom/archive/pull`。
- 两次均返回 200，但 `rawCount=0`、`savedCount=0`。
- `/api/wecom/archive/messages?limit=20` 仍为空数组。
- 后端日志无 SDK 报错，说明当前不是接口异常。
- 后续排查顺序：
  1. 确认发送该消息的企业微信成员正好在会话存档“开启范围”内。
  2. 确认这条消息是企业微信成员与微信外部联系人的会话，而不是普通内部会话、自己给自己发、或未纳入服务版范围的场景。
  3. 等待企业微信归档延迟后再拉取。
  4. 若持续为 0，再查看企业微信后台是否有“待同意/未授权/未生效”的范围提示。

## 2026-06-17 补充：客服通道目前被企业微信拒绝

- 生产客服配置检查通过：
  - `useMock=false`
  - `missing=[]`
  - `configured=true`
  - callback URL：`https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback`
- 手动触发生产 `/api/wecom/real-sync` 时，企业微信返回：
  - `errcode=48002`
  - `errmsg=api forbidden`
  - 来源 IP：`81.70.84.35`
- 最近后端日志没有看到企业微信访问 `/api/wecom/kf/teamBuy/callback`。
- 当前结论：
  - 后端客服通道配置已具备。
  - 企业微信后台客服 API 权限、可信 IP 或接收消息服务器配置仍需处理。
  - 现在还不能确认用户测试消息是否走了客服通道，因为客服 `sync_msg` 被企业微信拒绝。

## 2026-06-17 补充：会话存档真实链路已跑通

- 用户 23:41 发送测试消息后，企业微信会话存档开始返回真实数据。
- 本轮修复：
  - 修正 C SDK `DecryptData` ctypes 签名，多传 `sdk` 指针会导致 `10008`。
  - 增加归档 `msgtime` 毫秒时间戳归一化，避免 Pydantic 字符串校验失败。
- 生产验证结果：
  - `/api/wecom/archive/pull`：`rawCount=1`、`savedCount=1`、cursor `seq=1`。
  - 实际收到文本：`归档测试2218资料管理助手`。
  - `/api/wecom/archive/process`：`processedCount=1`、`failedCount=0`。
  - 生成笔记：`note_fc9f58783e`。
  - 生成兼容卡片：`card_ec1e041dde`。
- 当前结论：
  - P0 主链路已跑通：企业微信外部联系人消息 -> 会话存档 SDK -> 原始归档消息 -> `ContentObject -> content-to-note -> UserNote`。
- 下一步建议：
  1. 小程序“我的笔记”人工查看 `note_fc9f58783e` 是否可见。
  2. 验证编辑、删除、搜索。
  3. 再发一条更接近业务场景的客户资料长文本，验证摘要质量。

## 2026-06-18 补充：自动归档 worker 与新导入页已完成

- 后端自动归档 worker 已实现并部署生产。
- 生产配置：
  - `WECOM_ARCHIVE_WORKER_ENABLED=true`
  - `WECOM_ARCHIVE_WORKER_INTERVAL_SECONDS=60`
- 生产公网 `/api/wecom/archive/config-check` 已确认：
  - `sdkConfigured=true`
  - `workerEnabled=true`
  - `workerIntervalSeconds=60`
  - `missing=[]`
- 当前企业微信新消息会由 worker 自动执行 `pull -> process`，不再需要 Codex 手动调用。
- 小程序“待认领”页已改为“新导入资料”：
  - 默认展示标题和内容。
  - 支持通用 / 中介 / 团购模板按钮。
  - 认领后优先进入笔记编辑页。
  - 笔记编辑页显示模板字段提示。
- 仍然保留待认领原因：
  - `identity-core` 尚未实现。
  - 企业微信外部联系人和小程序用户还不能自动绑定。
  - 上线前应把“待认领”改成弱入口或异常入口。

## 2026-06-18 补充：微信笔记 note 解析与 5 秒聚合已部署

- 用户 03:39 发送房产类型微信笔记，企业微信归档为 `msgType=note`。
- 已支持解析 `note.info.items`：
  - 文本进入正文。
  - 位置进入 `locationText` 和正文。
  - 多张图片进入 media 引用。
- 已支持普通多消息 5 秒聚合：
  - 同一会话。
  - 同一发送人。
  - 相邻消息不超过 5 秒。
  - 非 `note` 类型。
- 生产验证：
  - 用 03:39 note 的 mock 副本生成 `note_da48e67e5e`。
  - 正文包含房源小区、户型、价格、商圈、备注、位置。
  - `mediaCount=5`。
- 注意：
  - 已经生成过的 `note_03cdd38ad5` 不会自动重处理。
  - 验证副本 `note_da48e67e5e` 会暂时出现在待认领列表。
  - 下一步仍建议做会话存档媒体下载转存，让图片真实显示。

## 2026-06-18 补充：图片不显示的原因与下一步收口

- 用户确认当前产品后续继续按“真实企业微信链路小范围生产联调，重要经验沉淀到文档”的思路推进。
- 当前图片不显示不是用户测试错误：
  - 企业微信归档图片已经作为 `sdkfileid` 引用进入 `UserNote.media`。
  - 但官方 SDK `GetMediaData` 下载媒体本体和服务端转存还未实现。
  - 因此小程序暂时没有可预览的 `media.url`。
- 下一步最自然开发：
  1. 实现会话存档媒体下载服务，支持通过 `sdkfileid` 调官方 SDK `GetMediaData`。
  2. 下载后进入现有媒体处理链路，图片转 WebP，先保存到服务器媒体目录，后续再换 COS/CDN。
  3. 将持久化 URL 写回 `UserNote.media.url` 和兼容 `Card.media.url`。
  4. 增加失败记录和后台重试，避免媒体失败阻断文字笔记。
  5. 用用户重新发送的一组“图片 + 文字 + 微信笔记”做人工验收。
- 已确认原则：
  - 小程序本地缓存只是展示优化，不能作为资料库正式图片存储。
  - 会话存档不负责回复用户；处理完成通知要后续单独接企业微信应用消息、微信客服消息或小程序订阅消息。
  - P0 阶段可继续在生产小范围联调，P1/P2 前建议拆 staging/test 环境。

## 2026-06-18 补充：会话存档媒体下载转存已实现

- 已实现会话存档媒体本体下载：
  - `backend/app/services/wecom_archive_client.py` 新增 `download_media()`。
  - 官方 SDK `GetMediaData` 按 `outindexbuf` 分片循环下载，直到 `is_finish`。
  - 二进制数据通过 `GetDataLen/GetData` 长度读取，避免字符串截断。
- 已接入归档处理：
  - `process_wecom_archive_messages(limit, archive_client)` 会在生成 `content-to-note` 前补齐 media URL。
  - 成功下载的图片进入现有媒体处理链路，转 WebP 后保存到 `/media`。
  - `UserNote.media.url`、兼容 `Card.coverUrl` 和 `Card.media.url` 会拿到正式媒体地址。
  - 下载失败不阻断文字笔记，会记录 `media_retry_jobs`，结果里返回 `media.failedCount`。
- worker 和手动接口都已传 archive client：
  - 自动 worker 每轮 `pull -> process` 会尝试下载媒体。
  - `POST /api/wecom/archive/process` 手动触发也会尝试下载媒体。
- 已验证：
  - compileall 通过。
  - `pytest backend/tests/test_app.py -q -k "wecom_archive"`：14 passed。
  - 相关后端测试：65 passed。
- 生产状态：
  - 已部署到 `https://teambuy.lifelove.top`。
  - `/api/wecom/archive/config-check` 确认 `sdkConfigured=true`、`workerEnabled=true`、`missing=[]`。
  - 手动 `/api/wecom/archive/process?limit=20` 返回 `processedCount=0`，当前没有未处理的新归档消息。
- 下一步建议：
  1. 用用户新发的“图片 + 文字 + 微信笔记”真实验证 `media.downloadedCount` 和小程序图片展示。
  2. 对已经生成但没有 URL 的旧图片笔记，后续可以补一个“历史媒体补下载/回填”脚本或后台按钮。

## 2026-06-18 补充：历史媒体补下载/回填已实现

- 新增后台接口：
  - `POST /api/wecom/archive/media-backfill`
  - admin token 保护。
  - `limit` 控制本次最多处理的缺失媒体数量。
- 回填范围：
  - 已有 `UserNote.media[]` 里 `mediaId` 存在、`url` 为空的媒体。
  - 不处理已经有 URL 的媒体，不覆盖用户已编辑内容。
- 回填结果：
  - 成功下载后写回 `UserNote.media.url`。
  - 若对应 `sourceCardId` 存在，会补齐 `Card.coverUrl` 和 `Card.media`，保证当前小程序旧卡片展示链路也能看到图片。
  - 下载失败写入 `media_retry_jobs`，继续处理下一条。
- 已验证：
  - archive 测试 15 passed。
  - 相关后端测试 66 passed。
- 下一步生产部署后可手动调用一次回填接口，补旧的 `note_f6cfe62264`、`note_866ce69346`、`note_da48e67e5e` 等历史无 URL 图片笔记。
- 生产首次回填已执行：
  - 成功回填 `note_da48e67e5e` 的 5 张图片，兼容卡片 `card_9af73ff8e0` 已更新。
  - 另有 2 个旧图片失败，原因是超长 `sdkfileid` 造成本地文件名过长。
  - 已修复媒体文件名规则：超长 media ID 截断并追加 hash，等待重新部署后再跑一次回填。
- 生产二次回填已执行：
  - 成功回填 `note_f6cfe62264` 和 `note_866ce69346`。
  - `downloadedCount=2`、`failedCount=0`。
  - 当前已知历史无 URL 图片笔记已补齐。

## 2026-06-18 补充：identity-core 第一版已实现

- 已新增“认领后绑定”：
  - 用户第一次认领导入后，保存 `wecom_external_user + externalUserId -> ownerUserId`。
  - 后续同来源企业微信客服导入和会话存档导入，会自动归属到该小程序用户。
  - 自动归属的 `ImportBatch.status=claimed`，不再进入“新导入资料/待认领”列表。
  - `UserNote.ownerUserId` 和兼容 `Card.ownerUserId` 会直接写成绑定用户。
- 新增模型/表：
  - `WecomIdentityBinding`
  - `wecom_identity_bindings`
- 已验证：
  - 认领后绑定。
  - 企业微信客服 mock 后续导入自动归属。
  - 会话存档后续导入自动归属。
  - 相关后端测试 68 passed。
- 当前边界：
  - 仍然是 mock 登录用户 ID。
  - 不是正式微信 code/openid/unionid 绑定。
  - 上线前仍需补正式微信登录和更清晰的绑定管理/解绑能力。
- 生产状态：
  - 已部署生产。
  - `/health` 正常。
  - PostgreSQL `wecom_identity_bindings` 表已确认存在。
  - 下一次用户从小程序认领某个来源后，同来源后续新消息应自动进入其笔记库。

## 2026-06-18 补充：URL 默认轻收藏已实现

- 产品口径：
  - 普通文章 URL 默认是轻收藏，但轻收藏不是通用笔记模板，而是文章收藏卡。
  - 第一层只展示原始链接、标题、封面、来源、收藏时间、基础标签、基础分类和一句话摘要。
  - 用户点击轻收藏卡片默认打开原文；公众号文章优先尝试小程序官方能力，普通网页降级复制链接。
  - 用户明确点企业微信快捷指令或输入 `整理链接` 等指令时，才做深度整理。
  - 小程序内可以从轻收藏手动升级为深度笔记。
- 已实现：
  - Skill Router 新增 `link_bookmark` 意图。
  - 普通 URL 规则路由到 `link-bookmark`。
  - `整理链接` 精确指令仍路由到 `content-to-note`。
  - 企业微信客服导入和会话存档导入已走统一判断。
  - 轻收藏后端字段已包含 `category/sourceName/sourceLabel/openAction/sourceUrl`。
  - 小程序“我的笔记”列表轻收藏已按文章卡片展示。
  - 小程序轻收藏详情页已从通用模板改成文章卡 + 基础信息 + 整理动作。
- 已验证：
  - compileall 通过。
  - 相关后端测试 70 passed。
  - 小程序 JS 静态检查通过。
  - 生产 `/health` 正常。
  - 生产路由验证：普通 URL 返回 `link_bookmark`，`整理链接` 返回 `content_to_note`。
  - 生产容器内 `run_link_bookmark()` 验证轻收藏字段已包含 `category/sourceName/sourceLabel/openAction/sourceUrl`。
- 当前边界：
  - 轻收藏第一版不抓取全文，只保存来源链接、标题、封面和简短描述。
  - 非公众号普通外链在微信小程序内不能保证直接打开，当前降级为复制链接。
  - “整理为笔记”第一版主要完成状态升级和编辑入口，后续可接入真正文章抓取、正文提取和大模型结构化摘要。
- 未提交/不应提交的本地文件仍需注意：
  - `miniprogram/project.config.json` 是微信开发者工具本地配置扰动，除非明确需要，不纳入功能提交。
  - `企业微信客服服务须知.pdf` 是本地参考文件，不纳入提交。

## 2026-06-18 补充：强标签、弱分类、专题聚合第一版已实现

- 架构文档：
  - `docs/stage2-docs/11-tag-topic-search-architecture.md`
- 产品口径：
  - 不做强制三级分类。
  - 来源类型对齐微信收藏基础类型。
  - `systemCategory` 是系统弱分类。
  - `tags/userTags/tagLevels` 是核心组织结构。
  - `topics/topicIds` 替代多级文件夹，承载场景集合。
- 已实现：
  - 轻收藏规则标签入库。
  - 标签建议接口。
  - 专题列表、创建、加入资料、移出资料接口。
  - 笔记列表按来源类型、标签、专题、排序筛选。
  - 小程序“我的笔记”筛选条。
  - 小程序轻收藏编辑页支持来源类型、弱分类、用户标签、专题。
  - 小程序新增“专题”页面和“我的”页入口。
- 已验证：
  - compileall 通过。
  - 相关后端测试 70 passed。
  - 小程序 JS 检查通过。
  - 小程序 JSON 解析通过。
  - 生产 `/health` 正常。
  - 生产 PostgreSQL 已确认存在 `topics` 表。
  - 生产专题接口路由与用户校验生效。
- 当前边界：
  - 暂未接 L2 轻模型和 L3 大模型。
  - 暂未做标签重命名、合并、批量打标。
  - 专题关系暂存在 `UserNote.visibilityConfig.topicIds`，不是最终表结构。

## 2026-06-19 补充：资料详情支持用户补传图片/视频

- 背景：
  - 用户确认贝壳等第三方小程序房源不应强依赖自动抓取完整图片/价格/字段。
  - 产品主链路应允许“保存原小程序入口 + 用户自己补字段/图片/视频 + 使用 SCRM/留资/预约/客户页”。
- 已实现：
  - `miniprogram/pages/note-edit/` 的“图片与视频”板块新增“添加”入口。
  - 支持添加图片和视频，复用现有 `api.uploadAsset()` / `POST /api/uploads/asset`。
  - 上传成功后自动保存当前资料，首张图片自动设为封面。
  - 媒体列表避免封面和同一张图片重复显示；删除封面媒体时会自动换下一张图片或清空封面。
  - 编辑页视频素材可直接播放。
  - `miniprogram/pages/note-preview/` 客户页预览新增“房源视频”区，补传视频会展示给客户。
- 已验证：
  - 小程序 JS 静态检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
- 当前边界：
  - 上传接口已存在，本次未改后端。
  - 视频第一版只做展示/播放，不做封面截帧、转码、压缩进度条或排序。
  - 需要用户在微信开发者工具重新编译预览后实测真机上传权限、视频播放和客户页展示。

## 2026-06-19 补充：房源轻 SCRM 支持按资料查看客户动作

- 背景：
  - `customer-action-plugin` 第一版已让客户页留资、预约持久化到 `customer_actions`，并投影到 `lead_reminders`。
  - 用户确认发布者更希望在房源资料详情里查看这套房源的客户动作，而不是只去全局线索列表搜索。
- 已实现：
  - 后端新增 `GET /api/notes/{note_id}/customer-actions?ownerUserId=...`，按 noteId 返回动作汇总、动作明细和已投影线索。
  - `miniprogram/pages/note-edit/` 的“轻 SCRM”板块显示客户动作、留资和待跟进数量。
  - “轻 SCRM”板块新增“查看客户动作 / 查看线索”入口，跳转 `pages/note-actions/index`。
  - 有待跟进线索时，轻 SCRM 标题和入口显示红点；红点绑定 `pending` 线索。
  - 新增 `miniprogram/pages/note-actions/`，展示当前资料的客户动作时间线和线索列表，可继续进入线索详情。
- 已验证：
  - 目标后端测试通过。
  - 新增小程序页面 JS 静态检查通过。
  - 小程序 JSON 解析检查通过。
- 当前边界：
  - 红点目前不是已读/未读事件表，而是待跟进线索提醒；线索状态改为已联系或归档后应消失。
  - 咨询点击等动作后续接入 `customer-action-plugin` 后，可继续复用当前 note 级入口展示。
  - 仍需微信开发者工具/真机验证页面跳转、红点视觉和线索处理后的刷新效果。

## 2026-06-19 补充：客户动作接口已部署生产并修复多端按钮适配

- 问题：
  - 用户在手机/iPad 上测试客户页留资和房源轻 SCRM 动作页时遇到 `Not Found`。
  - 资料详情顶部动作按钮和客户预览页浮动分享按钮在不同设备上样式不稳定。
- 根因：
  - 小程序 `apiBaseUrl` 指向生产域名，但生产后端还没有部署 `customer_actions` 新接口。
  - 部分按钮使用固定 `line-height`，不同屏宽渲染容易变形或过小。
- 已处理：
  - 已用 rsync 同步后端 `backend/app/` 和 `backend/mock/customer-actions.json` 到生产服务器。
  - 已重建并重启 `teambuy-backend` 容器。
  - 公网 `/health` 正常。
  - 公网 `/api/notes/note_not_exists/customer-actions?...`、`/customer-actions/config`、`POST /customer-actions/lead-contact` 已不再返回路由级 `Not Found`，而是业务级“笔记不存在”。
  - 小程序资料详情顶部三按钮、保存分享图、客户预览页好友/朋友圈和提交按钮已改为 rpx + flex 适配。
- 已验证：
  - 后端全量测试 98 passed。
  - 小程序 JS 静态检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。
- 下一步：
  - 需要在微信开发者工具重新编译，并上传/预览新版小程序前端，手机和 iPad 才能看到样式修复。

## 2026-06-19 补充：真机身份隔离、SCRM 红点已读和电话拨号

- 问题：
  - 两个不同微信真机测试看到同样数据。
  - 轻 SCRM 红点点开后不消失。
  - 待联系和 SCRM 线索页手机号旁缺少直接拨号入口。
- 根因：
  - 登录页仍走固定“本地测试用户”mock 身份，两个微信默认 nickname 一样时后端 openid 一样。
  - 红点绑定 pending 数量，不是“未读动作”。
- 已实现：
  - 后端新增 `POST /api/auth/wechat-login`，支持通过微信 code 换 openid。
  - 生产后端已部署该路由；当前服务器未配置 `WECHAT_MINIAPP_SECRET`，所以公网返回明确配置提示，不是 404。
  - 小程序登录优先走微信登录；正式登录未配置时使用设备级唯一 mock openid 兜底，避免串用户。
  - 小程序启动时清理旧 `openid_本地测试用户` 缓存。
  - 轻 SCRM 红点改成本机已读：点开“查看客户动作 / 查看线索”后红点立即消失。
  - 待联系列表、线索详情、房源客户动作页手机号旁增加“拨号”入口。
- 已验证：
  - 后端全量测试 99 passed。
  - 小程序 JS 静态检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。
- 下一步：
  - 生产服务器 `.env` 需要补 `WECHAT_MINIAPP_APPID=wxf43f7bc098d9858b` 和真实 `WECHAT_MINIAPP_SECRET`，再重启 backend，才是正式 openid 登录。
  - 目前设备级 mock 只用于未配置 AppSecret 的真机测试隔离，不等于正式登录体系。

## 2026-06-19 补充：已支持当前用户生成房源测试数据

- 背景：
  - 用户需要几组假数据在真机上测试房源详情、轻 SCRM、客户动作、红点和拨号。
- 已实现：
  - 后端新增 `POST /api/notes/demo-data?ownerUserId=...`。
  - 小程序“我的”页新增“生成测试房源数据”。
  - 每次会给当前登录用户生成 3 条房源资料、2 条线索、3 条客户动作。
  - 数据属于当前用户，可用于验证两个微信账号是否隔离。
  - 生产后端已部署并验证成功。
- 测试路径：
  - 重新编译/预览小程序。
  - 登录后进入“我的”。
  - 点击“生成测试房源数据”。
  - 到“我的笔记”看 3 条测试房源。
  - 进测试房源 A，看轻 SCRM 红点和“查看客户动作 / 查看线索”。
  - 到“待联系线索”测试手机号拨号。
- 已验证：
  - 后端全量测试 100 passed。
  - 小程序 JS/JSON 检查通过。
  - `git diff --check` 通过。

## 2026-06-19 补充：我的笔记卡片前置 SCRM 入口

- 用户反馈：
  - “我的笔记”搜索按钮太长太黑。
  - 房源 SCRM 入口藏在详情页下方太深，应该在房源笔记卡片直接进入。
  - 卡片有未读客户动作时要显示红点，点进 SCRM 后红点消失。
  - 资料详情顶部三按钮文字不居中，浮动“存”太小。
- 已处理：
  - 搜索按钮改短并使用主题蓝色。
  - 房源/团购笔记卡片加载后补取 note 级客户动作汇总。
  - 卡片右上显示未读红点，底部新增 `SCRM` 胶囊入口。
  - 点击卡片 `SCRM` 会写入本机已读时间并跳转客户动作页，红点立即消失。
  - 资料详情顶部三按钮改为专用 class + 内部 text + flex 居中。
  - 浮动保存按钮放大到 84rpx。
- 已验证：
  - 小程序 JS 静态检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。
- 注意：
  - 这是小程序前端改动，需要重新编译/预览/上传小程序才能在真机看到。

## 2026-06-19 补充：生产登录、归属和 chatrecord 解析已修复

- 生产状态：
  - `WECHAT_MINIAPP_APPID` / `WECHAT_MINIAPP_SECRET` 已配置到生产 `backend/.env`，backend 已重建重启。
  - 真机微信登录已成功创建真实用户 `user_25ec00a0f0`。
  - 企业微信外部联系人 `wmCSe7EwAAwsQd1LH-iNoA78ey4i0cXg` 已绑定到 `user_25ec00a0f0`。
  - 2026-06-19 当天 4 条误归属导入已迁移到该真实用户。
- 解析状态：
  - 新增注册式归档 parser：`backend/app/services/archive_message_parsers.py`。
  - `chatrecord` 已能解析 `ChatRecordText` 正文并识别鸡蛋团购商品。
  - 生产中两条旧 `chatrecord` 笔记已原地修复为“白凤乌鸡蛋 / groupbuy_product / 团购”。
- 前端状态：
  - 商品工作台重排为“商品信息 / 图片与视频 / 规格与价格 / 自提配送 / 团购接龙”。
  - 客户页商品卡先展示规格与价格；开启团购接龙后才显示提交入口。
  - 图片缩略图保持普通图片原样 `aspectFill`，封面角标只红字，不再额外铺背景。
- 验证：
  - 生产 `/health` 正常。
  - 生产当前用户笔记接口已返回“白凤乌鸡蛋 / groupbuy_product / 团购”。
  - 本地后端全量测试 103 passed。

## 2026-06-19 补充：商品下单 / 接龙名单出口

- 本轮结论：
  - 商品客户预览页默认必须有 SKU 点选和下单按钮。
  - 接龙开关只决定提交后叫“下单名单”还是“接龙名单”，不决定是否落库。
- 已实现：
  - 后端新增 `customer_actions.order-intent`。
  - `enableGroupRelay=false`：客户点“下单”写 `order-intent`。
  - `enableGroupRelay=true`：客户点“下单并接龙”写 `relay-intent`。
  - 两者都不投影到 `lead_reminders`，不进入 SCRM。
  - 客户预览页提交后显示已下单/已接龙的 SKU 和数量。
  - 团长资料详情页入口改为“查看下单 / 接龙名单”。
  - 我的笔记商品卡入口改为“下单 N / 下单名单”。
  - 客户动作页商品资料展示“商品下单名单 / 商品接龙名单”，支持复制汇总、复制单条、复制电话/微信和拨号。
- 生产确认：
  - 生产后端已同步并重启，`order-intent` 已生效。
  - 生产商品笔记 `enableGroupRelay=false` 时，客户动作配置返回 `order-intent / 下单`。
  - 生产商品笔记 `enableGroupRelay=true` 时，客户动作配置返回 `relay-intent / 下单并接龙`。
  - 客户预览页下单区域已移动到底部动作区后方。
- 已验证：
  - 使用 Codex Python 3.12 运行 `backend/tests/test_app.py`：66 passed。
  - 小程序 `note-preview`、`note-actions`、`note-edit`、`notes` JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。

## 2026-06-19 补充：轻订单中心和站内消息

- 本轮目标：
  - 商品轻订单补齐地址、电话、备注等履约信息。
  - 买家和商家都有订单中心。
  - 商品/房源/订单支持小程序内异步留言。
  - 我的页从单列表重构为业务分区。
- 已实现：
  - 后端新增订单接口：`GET /api/orders`、`GET /api/orders/{orderId}`、`PATCH /api/orders/{orderId}/status`。
  - 后端新增消息接口：线程列表、创建线程、消息列表、发送消息、标记已读。
  - 后端新增 `message_threads` / `message_records` 存储，mock JSON 和 Postgres schema 已同步。
  - 下单 payload 扩展 `receiverName / phone / address / wechat / remark`，电话和地址必填。
  - 小程序新增订单列表、订单详情、消息列表、消息会话页面。
  - 客户预览页商品下单区补齐地址/电话等字段，并新增“发消息”入口。
  - 商品下单/接龙名单每条记录新增“发消息”。
  - 资料详情和我的笔记卡片增加消息入口。
  - 我的页分为会员服务、笔记区域、线索/订单、消息专区、开发测试。
- 已验证：
  - 后端全量测试：66 passed。
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
- 注意：
  - 本轮没有做支付、库存扣减、物流、退款、核销。
  - 站内消息第一版是异步文本留言，没有 WebSocket、图片、语音。
  - 需要重新编译/预览/上传小程序，真机才能看到新增订单和消息页面。

## 2026-06-19 补充：消息入口已前端插件化

- 已实现：
  - `miniprogram/plugins/message-plugin/index.js`：统一封装打开会话、打开消息中心、获取未读数。
  - `miniprogram/components/message-entry`：统一入口组件，支持 thread / center 两种模式和 card / row / pill / text 样式。
  - 订单详情、商品名单、资料详情、我的笔记、我的页消息专区已接入组件。
  - 客户预览页动态“发消息”动作已改为调用 `messagePlugin.openMessageThread`。
- 后续约定：
  - 新增房源、商品、活动、课程等场景时，不在页面里直接调用 `api.createMessageThread`。
  - 有可见入口时优先使用 `message-entry`；只有动态动作列表这类场景才直接调用 `messagePlugin` 方法。
- 已验证：
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端全量测试：66 passed。
  - `git diff --check` 通过。

## 2026-06-20 补充：商品下单弹层和我的页宫格

- 已实现：
  - 商品客户预览页不再直接展开地址/电话/备注表单。
  - 点击“下单 / 下单并接龙”后打开底部弹层填写下单信息。
  - 我的页会员服务、笔记区域、线索/订单、开发测试改为 4 列图标宫格。
  - 订单中心空态区分“暂无购买订单 / 暂无收到的商品订单”。
  - 如果生产后端尚未部署 `/api/orders`，前端会显示中文提示，不再裸露英文 not found。
- 已验证：
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端全量测试：66 passed。
  - `git diff --check` 通过。

## 2026-06-20 补充：生产后端已部署订单和消息接口

- 已完成：
  - 生产后端已同步并重建 `teambuy-backend`。
  - `/api/orders`、`/api/orders/{orderId}`、`/api/messages/threads` 已在公网可用。
  - 订单中心的路由级 `Not Found` 已解决。
- 公网冒烟：
  - `/health` 正常。
  - `/api/orders?userId=user_test&role=buyer` 返回 200 空列表。
  - `/api/messages/threads?userId=user_test` 返回 200 空列表。
  - 真实用户 `user_25ec00a0f0` 可看到商品订单列表和订单详情。
- 未完成：
  - 小程序体验版上传未能由 Codex CLI 完成。本机微信开发者工具提示服务端口关闭，CLI 自动开启端口超时。
  - 需要人工在微信开发者工具打开“设置 -> 安全设置 -> 服务端口”，然后重新预览/上传小程序。
