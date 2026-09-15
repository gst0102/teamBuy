# Project Memory

更新时间：2026-06-20

## 1. 产品定位

teamBuy 是一个面向微信群私域场景的小程序工具，核心能力是把用户发给企业微信客服的微信笔记、链接、图片、视频、位置等素材，自动聚合并生成可编辑的小程序卡片。

注意：企业微信客服导入发生在小程序外部的客服会话中。小程序内不提供“发给客服”操作入口；中间加号定位为“添加 / 快速入库”，`pages/imports/index` 仅作为外部导入后的“待认领”页面。

当前企业微信客服后端回调地址已配置成功，并以 `https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback` 为准；其它企业微信配置项以 `backend/.env` 为准。

企业微信会话内容存档已开通，进入 P0 第三阶段。配置清单固定在 `docs/stage2-docs/10-wecom-archive-config.md`；后端会话存档接口前缀为 `/api/wecom/archive`。会话内容存档使用独立 `WECOM_ARCHIVE_SECRET`、`WECOM_ARCHIVE_CALLBACK_TOKEN`、`WECOM_ARCHIVE_ENCODING_AES_KEY` 和 RSA 私钥，不复用微信客服 `WECOM_KF_SECRET` 或回调凭证。

长期架构计划以 `docs/stage2-docs/08-plugin-architecture.md` 为准：资料整理助手采用“企业微信稳定基座 + 混合驱动 Skill + 小程序笔记与展示页”。企业微信负责入口、消息和通知；通用基座负责会话存档、身份、合规、支付、笔记库和展示页基础能力；可变功能通过 Skill 扩展。

项目首版重点验证：

- 企业微信客服导入素材是否可跑通。
- 后端是否能通过回调和 `sync_msg` 拉取并聚合消息。
- 小程序是否能完成认领、编辑、分享、查看、接龙和复用闭环。
- 发起人是否能看到浏览统计、接龙名单和跟进状态。

## 2. 当前目标用户

第一优先用户：房产中介。

第二优先用户：团购团长。

当前产品不做“交易平台”，而是做“素材导入、卡片生成、查看统计、实名接龙与复用工具”。

## 3. 用户偏好

用户偏好：

- 简单直接的功能闭环。
- 优先本地开发和 mock 验证。
- 先跑通小程序端和后端，不急着做 PC 管理后台。
- 不做收款、订单、支付、分账这类资金链路。
- 不依赖聊天上下文，重要信息必须沉淀到仓库文档。
- 小步开发、小步验收，避免新窗口重新理解项目。
- 小程序体验版/上传/提交审核由用户在微信开发者工具中手动完成；Codex 默认不要反复尝试 CLI 上传，只做实现和自动化检查。

## 4. 技术偏好

- 前端：原生微信小程序。
- 后端：FastAPI。
- 数据库：PostgreSQL 为目标，开发阶段可保留 JSON/SQLite/mock 兜底。
- 部署：Docker Compose，后端镜像构建使用清华 PyPI 源。
- 对象存储：后续接腾讯云 COS 或 S3-compatible 存储。
- 素材处理：图片/视频上传后先在后端压缩，再写入本地媒体目录或对象存储；图片通过 Pillow 转 WebP，视频通过 ffmpeg 转 H.264/AAC MP4，资料库保存压缩后的 URL。
- 前端资源状态：当前是原生微信小程序，不直接使用 Pinia；采用 `miniprogram/stores/resource-store.js` 承担 Pinia 类似的资源集中管理职责。
- 小程序 UI 硬规则：输入框 + 按钮、搜索框 + 按钮、卡片右侧操作区这类横向组合必须给父容器 `box-sizing: border-box`，给可伸缩列 `minmax(0, 1fr)` 或 `flex: 1; min-width: 0`，给按钮明确 `width/min-width/max-width`，并重置原生 `button` 的 `margin/padding/line-height/::after`，使用 flex 居中和 `white-space: nowrap`。不能只写 `grid-template-columns: 1fr 140rpx` 或只靠 `line-height`，真机会把按钮默认尺寸撑出屏幕。
- 线索状态：高意向访客的待联系 / 已联系 / 无效 / 暂不跟进 / 已完成 / 备注 / 跟进记录 / 下次跟进日期 / 归档原因 / 客户手机号 / 微信号 / 预算 / 意向等级 / 私有客户标签已升为后端持久化，不再存小程序本地 storage；待联系页按逾期、今日、未来、未设置、已完成组织待办，并有今日 / 逾期 / 未处理页内提醒；单条线索完整编辑在 `pages/lead-detail/index`，客户资料区置顶并支持复制完整档案；客户资料汇总在 `pages/customers/index`，支持意向筛选、搜索、手机号/微信号复制、排序、资料完整度快捷筛选、来源资料筛选、客户标签筛选、活跃/沉睡筛选、卡片快捷跟进、复制当前筛选客户摘要、复制当前筛选跟进清单、清空筛选和本地保存常用视图；客户卡片已按客户资料、跟进状态、来源资料和操作分区展示。
- 大模型：规则优先，大模型兜底；企业微信入口采用快捷指令 / 菜单优先、规则其次、AI 意图识别兜底的混合驱动模式。AI 不能直接执行业务动作，低置信度必须让用户点选确认。
- Skill 架构：文字类来源统一进入 `ContentObject -> content-to-note -> UserNote`。微信笔记、聊天记录、链接文章、手动文字和后续 OCR 都是不同 Input Adapter，不拆成多个重复 Skill；`note-to-comic-image` 独立负责漫画图/宣传图/长图；`showcase-builder` 是小程序可视化展示页构建器。
- 链接文章入口：普通 URL 默认先生成轻收藏 `link-bookmark`，第一层按文章收藏卡展示，只保存原始链接、标题、封面、来源、收藏时间、基础分类、基础标签和一句话摘要；用户点击卡片默认打开原文，普通网页受微信限制时降级复制链接；用户明确发送 `整理链接/文章总结/整理文章/做笔记` 或在小程序点击“整理为笔记”时，才升级为 `content-to-note` 深度整理。
- 小程序卡片入口：企业微信 `msgtype=weapp` 不再当普通空笔记处理，统一转成 `miniapp_card`，前台来源为 `miniapp`。正文只展示标题、来源、appid、houseCode；完整 `pagePath`、`cityId`、`username` 等保存在 `visibilityConfig.structuredData.miniapp`。贝壳小程序卡片只有外壳字段时只给“可能是房源”的中置信提示，不伪造价格、户型、图片、经纬度；用户确认成房源字段卡时必须保留 `miniapp` 元数据。客户页可用 `wx.navigateToMiniProgram` 跳转贝壳原房源，同时我们的客户页继续承载轻 SCRM、留资、预约、微信咨询和跟进能力。
- 资料组织方式：采用“强标签、弱分类、专题聚合”，不做强制三级分类。分类只做系统基础视图，标签是搜索和召回核心，专题替代多级文件夹承载场景集合。架构文档见 `docs/stage2-docs/11-tag-topic-search-architecture.md`。
- 多类型资料卡：资料整理助手不是单一笔记工具，而是多类型信息结构化系统。统一流程是“收藏 -> 编辑 -> 整理 -> 生成”，但 `cardType` 决定数据结构和行为能力。URL/公众号文章是链接卡/阅读卡，普通文字是文本卡，房源是字段卡，团购是商品卡，图片/截图后续是 OCR 卡。第一版不新建房源/团购表，继续用 `UserNote.visibilityConfig.cardType/cardState/structuredData/typeSuggestions` 兼容扩展；架构文档见 `docs/stage2-docs/12-typed-content-card-architecture.md`。
- 类型识别规则：`content-to-note` 会保存 `recognitionExplanation`，说明候选类型、分数、命中字段和可读信号；中置信 `typeSuggestions` 只是提示，用户确认类型必须调用后端 `POST /api/notes/{note_id}/confirm-type`，由后端统一重建结构并保留原文、图片和 `miniapp` 元数据。
- OCR 入口：第一版采用两段式。小程序“我的笔记”页先通过 `POST /api/ocr/images` 保存图片资料，编辑页再由用户点击“识别图片文字”调用 `POST /api/ocr/notes/{note_id}/recognize`。企业微信客服同步和会话归档的纯图片也走同一两段式：导入时只保存为 `image_ocr` 图片资料，`structuredData.ocr.status=pending`，不自动识别；图文混合仍走普通 `content-to-note`。识别成功后写入 `structuredData.ocr`，再统一进入 `ContentObject.sourceType=image_ocr -> content-to-note -> UserNote` 并更新原资料；兼容保留旧 `POST /api/ocr/image-to-note`。引擎通过 `OCR_PROVIDER=auto/paddle/tesseract/mock` 配置，未配置时图片仍会保存，用户可手动补文字和字段。当前生产已部署 PaddleOCR，`OCR_PROVIDER=paddle`，依赖固定为 `paddlepaddle==3.3.1`、`paddleocr==2.10.0`。
- 房源/团购小程序前台体验已从显性的 4 态流程收敛为“两层工作台”：高置信资料直接展示可分享、可留资、可预约/接龙、可跟进的结果工作台；用户只做板块级编辑、隐藏、恢复和功能组调整。4 态仅保留为后台生命周期语义，不再作为主 UI。中置信资料在普通卡片上轻提示确认类型，低置信资料直接当普通笔记。
- 房源地图定位规则：客户页不展示经纬度数字；房源默认地址优先通过后端腾讯地图地理编码解析为 `structuredData.mapLocation`，再在编辑页/客户页展示地图和小房子标记。地图 Key 只允许放后端 `TENCENT_MAP_KEY`，解析失败时用微信原生选点兜底，不伪造坐标。
- 商品展示规则：现有 `groupbuy_product` 暂作兼容类型，但产品口径是“商品展示基座 + 可选团购接龙”。商品字段放 `structuredData`，SKU 属性组和组合 SKU 放 `structuredData.skuConfig`，截止时间选填；`conversionConfig.enableGroupRelay` 只控制提交后叫下单名单还是接龙名单。商品轻订单复用 `customer_actions.order-intent / relay-intent`，电话和地址必填，买家/商家订单中心只是客户动作视图，不新增正式订单表；两者都不投影到 `lead_reminders`，不进入轻 SCRM。本阶段不做地图、支付、库存扣减、核销或分账，后续正式交易另起 `order-core`。
- 商品 P1 体验规则：客户页有 SKU 属性组时按分组按钮选择，组合 SKU 仍是提交和后端校验实体；已提交订单/接龙通过客户动作配置接口回显 `submittedPayload`，用于恢复客户已选 SKU、数量和联系方式；团长名单可按 SKU 筛选，筛选只影响展示和复制汇总。
- 站内消息规则：第一版是异步文本留言，不做实时 IM。会话写入 `message_threads`，消息写入 `message_records`，线程绑定 `noteId`，可选绑定商品轻订单 `orderActionId`；商品页、房源页、订单页、资料详情和我的页都可以进入消息专区，支持未读和已读。前端入口必须优先走 `miniprogram/plugins/message-plugin` 和 `components/message-entry`，后续新场景不要在业务页里重复手写 `createMessageThread`。
- 展示页构建器 V1 已进入 P1：展示页是小程序可视化配置工具，发布者从资料库选择多条 `UserNote`，配置店名、简介、banner、联系方式、排序后发布。后端模型为 `ShowcasePage/ShowcaseItem`，只保存 `noteId`、排序和配置，不复制资料正文；公开接口只允许访问 `published` 展示页，并实时读取资料摘要。
- 转化配置：房源/商品展示从编辑态到生成态需要保存 `conversionConfig`，用于控制是否展示联系电话、是否开启轻 SCRM、是否收集线索、房源预约看房/私聊咨询、商品团购接龙、分享图入口和下单按钮预留。该配置不属于房源/商品本体字段，不应混入 `structuredData`。
- 客户页动作持久化是下一阶段重点，并必须做成 `customer-action-plugin` 这类可复用插件。房源、团购、普通笔记只决定默认启用哪些动作；动作提交统一落通用记录，再投影到线索、预约、接龙和跟进。第一版已落地 `lead-contact` 和 `appointment`：客户页提交电话/微信或预约后会写入 `customer_actions`，并投影到 `lead_reminders`。发布者查看时，房源资料详情“轻 SCRM”板块是单房源客户动作主入口，可按 noteId 查看留资、预约和线索；全局线索列表保留为跨资料待办。长标题是房产中介主动展示卖点的方式，不拆字段、不改标题，只做排版容错。
- 房产场景继续围绕工作台效率优化：房源状态用 `structuredData.propertyStatus` 管理推广中 / 已租 / 暂停推广，客户页按状态关闭新增转化动作；图片/视频排序属于资料展示状态，调整后必须立即保存；电话拨号后应提示是否标记已联系，并写入跟进记录。
- 旧资源详情页策略：标准资料统一进入 `note-preview`，不再保留可访问的 `card-view` 页面。后端公开资料接口可将仍带有 `sourceNoteId` 的历史 Card ID 解析到对应 UserNote；没有标准来源的纯旧 Card 不再作为客户页主链路。
- 企业微信会话内容存档 P0：事件服务器已保存成功；真实归档链路拆成 `/api/wecom/archive/pull` 和 `/api/wecom/archive/process`。`pull` 负责官方 SDK 拉取/解密/原始消息入库，`process` 负责 `ContentObject -> content-to-note -> UserNote`，重复处理通过 `generatedNoteId` 幂等保护。当前生产已配置官方 SDK 动态库，自动 worker 已开启。会话存档媒体下载转存已实现：`sdkfileid -> GetMediaData -> 服务端媒体处理/转存 -> UserNote.media.url`，小程序本地缓存不能替代正式存储；仍需生产真实图片消息验证。
- identity-core P0 第一版采用收窄方案：小程序微信 `openid` 是唯一身份锚点，`userId` 只是后端内部主键。企业微信来源 `externalUserId/external_userid` 只做系统内部映射到 `ownerOpenid/ownerUserId`，第一次认领导入后，后续同来源企业微信客服导入和会话存档导入会自动进入该 `openid` 对应用户资料库。P0 不做面向用户的绑定管理、解绑或改绑功能；测试期误认领走后台数据修正。
- 小程序正式登录接口已新增：前端可调用 `wx.login`，后端 `POST /api/auth/wechat-login` 通过 jscode2session 换 openid 后创建/更新用户；服务器还需配置 `WECHAT_MINIAPP_APPID` 和 `WECHAT_MINIAPP_SECRET` 才能启用真实 openid。未配置前，小程序用设备级唯一 mock openid 兜底，避免两个真机共用“本地测试用户”。后续正式上线仍应把前端传 `ownerUserId` 升级为服务端 session/token 校验。
- 当前 P0 真实联调允许使用生产环境，因为企业微信会话存档和小程序体验版依赖公网 HTTPS 与合法域名；后续进入更稳定阶段应拆出 staging/test 环境，避免生产试错扩大风险。
- 会话内容存档只负责拉取与合规归档，不负责向微信用户回复“已完成”。导入完成通知后续走独立通道：企业微信应用消息、微信客服消息或小程序订阅消息。
- 当前不做完整 PC Web 管理端；客服侧边栏/H5 发卡片仅作为 P2 技术预研。

## 5. 项目策略

1. 先完成 v0.1 MVP 闭环。
2. 不过早做复杂分销、支付、会员、团队权限、CRM。
3. 企业微信真实联调优先处理权限和配置问题，不盲目改代码。
4. 小程序功能必须在微信开发者工具或真机环境人工验收。
5. 后端核心逻辑必须有自动化测试。
6. 每轮开发结束必须更新 `docs/dev-log.md` 和 `docs/handoff-latest.md`。

## 6. 必读文档分层

永久规则：

- `AGENTS.md`

长期记忆：

- `docs/project-memory.md`
- `docs/decisions.md`
- `docs/pitfalls.md`

当前状态：

- `docs/dev-log.md`
- `docs/handoff-latest.md`

开发文档：

- `docs/stage2-docs/`
- `docs/stage2-docs/08-plugin-architecture.md`
- `docs/stage2-docs/09-p0-p2-roadmap.md`
- `docs/qa/MVP_测试清单与验收标准.md`

## 2026-08-16：媒体哈希去重与共享归档 24 小时中转留存

- teamBuy 的图片/媒体业务上传统一走 `AppService.process_and_store_media()`；`MediaAsset` 保存原始内容哈希 `originalSha256` 与处理后存储哈希 `storageSha256`，按 `mediaType + hash` 复用资产，`MediaAssetRef` 只记录业务引用关系。
- 手动 `/api/uploads/asset` 已接入同一套资产登记和去重链路，并返回两个哈希字段；存储对象 key 使用处理后哈希，避免并发重复上传产生不同物理文件。
- 共享企业微信核心 `WECOM_ARCHIVE_CORE_RAW_RETENTION_HOURS` 默认 24 小时；只有所有项目投递完成后才清理，项目业务库中已经持久化的数据不受影响。

- 会话存档普通消息的业务聚合统一采用“同一发送人、同一会话、首条消息起 60 秒固定窗口”；`note` 消息天然原子。图片加短说明以图片为主体，说明文字仍保留在资料正文。

## 2026-08-22：分享发送链路必须做对抗式审查

这次分享图问题的长期记忆：统一渲染器、跳过 Canvas、快照状态通过，并不等于微信最终分享正确。必须沿着“点击发客户 -> `onShareAppMessage` -> 返回对象 -> 微信卡片”验证最终结果。

- 非名片有原图时，若产品决策是 A 方案，最终返回对象必须带当前登记原图 `imageUrl`；不能因为 `shareSnapshot` 尚未完成就返回“准备中”标题或资料库路径。
- 微信原生分享没有 `imageUrl` 时可能截取当前页面；因此“无 `imageUrl` + `/pages/library/index` 或首页 path”是阻断性错误，不是可接受降级。
- `direct` 必须表示最终发送动作可立即完成且带有真实主图 `imageUrl`，不得只表示“没有进入 Canvas”。无图资料必须走插件的 `resource_default` 信息卡快照；名片继续走专用 Canvas。
- 每次开发前必须写出至少一个能击穿方案的反例，开发后必须验证名片、房源、商品、普通资料、图片资料、合集、无图、缺图、旧版本、失败重试和快速连续点击。
- `node --check`、JSON 解析、后端 pytest 只能证明基础代码/接口没有明显错误，不能替代小程序发送回调测试和微信开发者工具真机验收。

## 2026-08-26：无主图资料禁止退回微信当前页面截图

- 资料库、资料列表、客户页和通用分享入口都必须通过 `share-snapshot` 统一得到有效缩略图；没有真实主图时由插件生成 `resource_default` 信息卡并上传保存。
- 最终 `onShareAppMessage` 必须返回有效托管 `imageUrl` 和客户页 `path`；空 `imageUrl` 会让微信截取当前页面，属于阻断性分享错误。

## 2026-08-22：运营开关必须使用数据库配置表

- 客户信息链开关不是 PC 前端状态，也不能继续依赖 Docker 容器内的 `ops-console-state.json`；生产唯一真源是 PostgreSQL `ops_feature_flags` 的 `customer_info_chain` 行。
- 旧 JSON 仅允许在配置表缺行时一次性迁移；已有数据库行优先，旧文件删除或变化都不能覆盖线上开关。
- 数据库不可读时，后端必须 fail closed；PC 必须显示“读取失败”并禁止切换，不能把故障显示为“已关闭”或误开放客户身份、联系方式和会员门禁。
- 任何迁移发布前都要核对当前生产开关值已经写入表中；不能只部署代码后再假设旧容器文件会继续存在。

## 2026-08-22：生产客户页加载失败的长期规避规则

这次真实生产复现证明：不能把“原生分享面板打开了”当作“客户一定能打开”。资料编辑后会进入新的 revision 并撤销 published 状态，旧分享链接返回 404 是预期的安全边界；真正的前端缺口是旧列表状态在异步最新版本校验完成前仍可触发分享。

- 资料库分享准备必须先读取最新 owner note，以最新 `shareState` 和 `revision` 覆盖缓存值；只要不是 `published`，立即清除旧 `shareImageReady`/直出状态，进入重新发布路径。
- 异步校验开始时先撤销发送按钮资格，不能保留旧 ready 状态等待请求返回；否则会产生“发送成功、客户页 404”的竞态。
- 客户页必须区分“资料已停止分享/未发布”和“网络加载失败”，前者提供重新发布后重新发送的行动提示，后者提供重试。
- 对抗式验收必须至少构造：已发布后编辑、校验请求慢/失败、旧 404 分享链接、正常 published 分享、页面请求竞态；并同时检查资料库状态、`onShareAppMessage` 返回对象和客户页最终可见状态。

## 2026-08-22：客户信息链配置表生产落地

- 客户信息链开关已在生产切换为 PostgreSQL `ops_feature_flags` 的 `customer_info_chain` 行；本轮部署后接口实际读取 `enabled=true`、`paymentRequired=false`，没有改变这两个值。
- 配置表部署采用线上文件基线的最小补丁和显式备份，后端相关容器可重建，但不得重建 PostgreSQL 或覆盖生产 `.env`、secrets、媒体数据。
- 生产验证必须同时检查公网健康接口、运营接口返回值和数据库行；PC 的显示状态只能作为界面结果，不能作为持久化证据。
## 2026-08-22：会员支付待支付订单生命周期

- 会员支付同一用户/同一方案的业务订单在 30 分钟内复用；取消微信支付只保留 pending，不生成第二笔订单。
- pendingOrder.expiresAt 和 pendingOrder.secondsRemaining 由后端返回；小程序只按到期时间展示 mm:ss，不能只依赖本地倒计时决定能否支付。
- 会员状态、创建订单、发起支付都必须执行超时关闭；旧订单号在超时后不能重新发起支付，超过窗口才允许创建新订单。
- 已验签且金额/商户/用户一致的微信成功回调，即使本地订单因超时变为 closed，仍需完成该真实支付，避免扣款和权益不一致。
