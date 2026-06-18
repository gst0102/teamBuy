# Project Memory

更新时间：2026-06-18

## 1. 产品定位

teamBuy 是一个面向微信群私域场景的小程序工具，核心能力是把用户发给企业微信客服的微信笔记、链接、图片、视频、位置等素材，自动聚合并生成可编辑的小程序卡片。

注意：企业微信客服导入发生在小程序外部的客服会话中。小程序内不提供“发给客服”操作入口；中间加号定位为“添加 / 快速入库”，`pages/imports/index` 仅作为外部导入后的“待认领”页面。

当前企业微信客服后端回调地址已配置成功，并以 `https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback` 为准；其它企业微信配置项以 `backend/.env` 为准。

企业微信会话内容存档已开通，进入 P0 第三阶段。配置清单固定在 `docs/stage2-docs/10-wecom-archive-config.md`；后端会话存档接口前缀为 `/api/wecom/archive`。会话内容存档使用独立 `WECOM_ARCHIVE_SECRET` 和 RSA 私钥，不复用微信客服 `WECOM_SECRET`。

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

## 4. 技术偏好

- 前端：原生微信小程序。
- 后端：FastAPI。
- 数据库：PostgreSQL 为目标，开发阶段可保留 JSON/SQLite/mock 兜底。
- 部署：Docker Compose，后端镜像构建使用清华 PyPI 源。
- 对象存储：后续接腾讯云 COS 或 S3-compatible 存储。
- 素材处理：图片/视频上传后先在后端压缩，再写入本地媒体目录或对象存储；图片通过 Pillow 转 WebP，视频通过 ffmpeg 转 H.264/AAC MP4，资料库保存压缩后的 URL。
- 前端资源状态：当前是原生微信小程序，不直接使用 Pinia；采用 `miniprogram/stores/resource-store.js` 承担 Pinia 类似的资源集中管理职责。
- 线索状态：高意向访客的待联系 / 已联系 / 无效 / 暂不跟进 / 已完成 / 备注 / 跟进记录 / 下次跟进日期 / 归档原因 / 客户手机号 / 微信号 / 预算 / 意向等级 / 私有客户标签已升为后端持久化，不再存小程序本地 storage；待联系页按逾期、今日、未来、未设置、已完成组织待办，并有今日 / 逾期 / 未处理页内提醒；单条线索完整编辑在 `pages/lead-detail/index`，客户资料区置顶并支持复制完整档案；客户资料汇总在 `pages/customers/index`，支持意向筛选、搜索、手机号/微信号复制、排序、资料完整度快捷筛选、来源资料筛选、客户标签筛选、活跃/沉睡筛选、卡片快捷跟进、复制当前筛选客户摘要、复制当前筛选跟进清单、清空筛选和本地保存常用视图；客户卡片已按客户资料、跟进状态、来源资料和操作分区展示。
- 大模型：规则优先，大模型兜底；企业微信入口采用快捷指令 / 菜单优先、规则其次、AI 意图识别兜底的混合驱动模式。AI 不能直接执行业务动作，低置信度必须让用户点选确认。
- Skill 架构：文字类来源统一进入 `ContentObject -> content-to-note -> UserNote`。微信笔记、聊天记录、链接文章、手动文字和后续 OCR 都是不同 Input Adapter，不拆成多个重复 Skill；`note-to-comic-image` 独立负责漫画图/宣传图/长图；`showcase-builder` 是小程序可视化展示页构建器。
- 链接文章入口：普通 URL 默认先生成轻收藏 `link-bookmark`，第一层按文章收藏卡展示，只保存原始链接、标题、封面、来源、收藏时间、基础分类、基础标签和一句话摘要；用户点击卡片默认打开原文，普通网页受微信限制时降级复制链接；用户明确发送 `整理链接/文章总结/整理文章/做笔记` 或在小程序点击“整理为笔记”时，才升级为 `content-to-note` 深度整理。
- 资料组织方式：采用“强标签、弱分类、专题聚合”，不做强制三级分类。分类只做系统基础视图，标签是搜索和召回核心，专题替代多级文件夹承载场景集合。架构文档见 `docs/stage2-docs/11-tag-topic-search-architecture.md`。
- 多类型资料卡：资料整理助手不是单一笔记工具，而是多类型信息结构化系统。统一流程是“收藏 -> 编辑 -> 整理 -> 生成”，但 `cardType` 决定数据结构和行为能力。URL/公众号文章是链接卡/阅读卡，普通文字是文本卡，房源是字段卡，团购是商品卡，图片/截图后续是 OCR 卡。第一版不新建房源/团购表，继续用 `UserNote.visibilityConfig.cardType/cardState/structuredData/typeSuggestions` 兼容扩展；架构文档见 `docs/stage2-docs/12-typed-content-card-architecture.md`。
- 转化配置：房源/团购从编辑态到生成态需要保存 `conversionConfig`，用于控制是否展示联系电话、是否开启轻 SCRM、是否收集线索、房源预约看房/私聊咨询、团购接龙、海报入口和下单按钮预留。该配置不属于房源/商品本体字段，不应混入 `structuredData`。
- 企业微信会话内容存档 P0：事件服务器已保存成功；真实归档链路拆成 `/api/wecom/archive/pull` 和 `/api/wecom/archive/process`。`pull` 负责官方 SDK 拉取/解密/原始消息入库，`process` 负责 `ContentObject -> content-to-note -> UserNote`，重复处理通过 `generatedNoteId` 幂等保护。当前生产已配置官方 SDK 动态库，自动 worker 已开启。会话存档媒体下载转存已实现：`sdkfileid -> GetMediaData -> 服务端媒体处理/转存 -> UserNote.media.url`，小程序本地缓存不能替代正式存储；仍需生产真实图片消息验证。
- identity-core P0 第一版已实现“认领后绑定”：用户第一次认领导入后，系统保存企业微信来源 `externalUserId -> ownerUserId`，后续同来源企业微信客服导入和会话存档导入会自动进入该用户笔记库，不再进入“新导入资料”。当前仍是 mock 登录用户 ID，不代表正式微信 openid/unionid 身份体系已经完成。
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
