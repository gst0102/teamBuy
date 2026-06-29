# teamBuy 阶段性交接归档

## 2026-06-29 本轮交接：PC 后台可生成小程序加群 config_id

- 用户确认：企业微信后台手动创建外部群二维码后，可能找不到小程序插件需要的 `config_id/plugid`，因此需要系统通过 API 生成。
- 本轮已改：
  - `backend/app/services/wecom_client.py`
  - `backend/app/schemas/ops_admin.py`
  - `backend/app/services/ops_console_store.py`
  - `backend/app/api/routes_ops_admin.py`
  - `backend/app/static/ops-admin/index.html`
  - `backend/tests/test_app.py`
  - `docs/dev-log.md`
  - `docs/decisions.md`
  - `docs/pitfalls.md`
- 新增后端能力：
  - `WecomClient.create_group_join_way()`
  - 调用企业微信 `externalcontact/groupchat/add_join_way`
  - 企业微信成功时返回 `config_id`
- 新增 PC 运营后台接口：
  - `GET /api/ops-admin/wecom-group-join-ways`
  - `POST /api/ops-admin/wecom-group-join-ways`
  - 都要求 `X-Admin-Token: <WECOM_ADMIN_TOKEN>`
- 新增 PC 页面：
  - `/ops` 左侧新增 `小程序加群配置`
  - 可填写客户群 `chat_id`、备注、群名规则、群序号、是否群满自动建群、渠道 state。
  - 支持预览配置和生成 `config_id`。
  - 生成历史保存在 `ops-console-state.json` 的 `wecomGroupJoinWays`。
- 重要边界：
  - 以后不是只能系统建群。手动建群、手动二维码仍然可用。
  - 只有“小程序按钮式加入群聊”这条链路，建议走 PC 后台 API 生成 `config_id`。
  - 第一版需要人工填客户群 `chat_id`；后续可补客户群列表查询。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "join_way or group_join"`：3 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
  - PC 后台内嵌脚本 `node --check`：通过。

## 2026-06-29 本轮交接：企业群机器人群发消息 API 已打通

- 用户要求先把群发消息 API 打通，后续试企业群日常运营效果。
- 本轮已改：
  - `backend/app/core/config.py`
  - `backend/.env.example`
  - `backend/app/api/routes_wecom.py`
  - `backend/tests/test_app.py`
  - `docs/dev-log.md`
  - `docs/decisions.md`
  - `docs/pitfalls.md`
- 新增配置：
  - `WECOM_GROUP_BOT_WEBHOOKS`
  - 格式示例：`{"property":"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"}`
  - 真实 webhook 只能放后端环境变量或生产 `.env`，不要写入前端或提交 Git。
- 新增接口：
  - `GET /api/wecom/group-bot/config`
  - `POST /api/wecom/group-bot/broadcast`
- 接口规则：
  - 必须带 `X-Admin-Token: <WECOM_ADMIN_TOKEN>`。
  - `broadcast` 支持 `groupId` 或 `groupIds`。
  - `template` 支持 `midday / afternoon / evening / custom`。
  - 默认 `dryRun=true`，只返回预览内容和目标群，不调用 webhook。
  - 只有显式传 `dryRun=false` 才真实发送。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "group_bot"`：3 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- 重要边界：
  - 这次打通的是“平台自有企业群机器人 webhook 播报”，不是外部客户群自动群发。
  - 外部群仍由运营本人判断和发送；机器人可生成内容和建议，但不作为外部群直接自动运营主链路。

## 2026-06-28 本轮交接：企业资源搜索 V1（天眼查接入）策划

- 用户计划申请天眼查 API Key，并希望在资源库中增加第二类资源能力：企业资源搜索。
- 已新增文档：
  - `docs/stage2-docs/28-tyc-enterprise-resource-search-v1.md`
  - `docs/qa/企业资源搜索V1_测试清单与验收标准.md`
  - `docs/png/enterprise-resource-search-mockup.png`
- 当前口径：
  - 前台入口名为 `企业资源搜索`，放在资源库中，与群资源库并列。
  - 资源页入口建议采用九宫格，方便后续继续扩 `行业黄页`、`商机线索` 等资源能力。
  - 第一版不暴露天眼查 162 个工具，而是收敛为：企业搜索 + 企业卡 + 6 个高频查询功能。
  - 6 个功能为：基本信息、股东结构、司法风险、经营情况、历史变更、知识产权。
  - 搜索候选免费；基本信息低门槛；深度查询按功能扣积分。
  - 查询结果可保存为企业资源卡；“导出企业摘要卡”放后续。
  - Tianyancha API Key 只记录在服务器环境变量或密钥文件中，前端只调用自家后端接口。
  - 同企业同功能 24 小时优先走缓存，避免重复扣分和浪费额度。

## 2026-06-28 本轮交接：服务场景合集空态改为去资料创建

- 用户最新反馈：
  - 服务场景下，名片和方案应该在资料里，不应该在合集页里出现为创建入口。
- 本轮已改：
  - `miniprogram/pages/showcases/index.wxml`
  - `miniprogram/pages/showcases/index.js`
  - `miniprogram/pages/showcases/index.wxss`
- 本轮重点：
  - 合集页服务空态只保留合集创建主动作。
  - 次动作改为 `去资料里做名片/方案`，跳转资料 Tab 并带上服务场景筛选。
  - 统一心智：资料是单个资产，合集是多个资料的打包页。

## 2026-06-28 本轮交接：首页非房源场景补企业微信助手入口

- 用户最新反馈：
  - 除房源外，其他首页场景好像没有写加企业微信入口。
- 本轮已改：
  - `miniprogram/pages/home/index.js`
  - `miniprogram/pages/home/index.wxml`
  - `miniprogram/pages/home/index.wxss`
- 本轮重点：
  - 助手区副标题改为按场景读取，不再硬写房源说明。
  - 日常资料、团购、服务/商机场景补充完整卡片式 `加企业微信助手` 入口。
  - 房源场景继续使用原来的 `添加房源助手` 主按钮，不重复展示。
  - 首页移除 `后续可扩展 / 已预留` 内部规划文案。
  - 雷达页、合集页、资料编辑页、合集编辑页和标签管理页同步去掉 `预留 / 后续` 这类前台表达。
  - 首页邀请提示、我的页帮助描述和资料编辑页能力状态也同步改为用户视角文案。

## 2026-06-28 本轮交接：我的页顶卡和资料页副标题继续精修

- 用户最新反馈：
  - “我的”页顶部编辑提示仍显得长、丑、重复，真机观感和之前差别不够大。
  - 资料页副标题“房源继续保留关键判断信息，其他资料更轻更好发”太硬，不够顺。
- 本轮已改：
  - `miniprogram/pages/profile/index.wxml`
  - `miniprogram/pages/profile/index.wxss`
  - `miniprogram/pages/library/index.wxml`
  - `miniprogram/static/icons/edit-profile.svg`
- 本轮重点：
  - 顶部身份卡移除头像角标，只保留右上角单个 SVG 修改图标，减少重复编辑提示。
  - 我的页副标题改成“你的资料、资源和消息都在这里”，强化页面心智而不是重复产品名。
  - 资料页副标题和 AI 提示标签改得更软一些，继续保留“房源信息可稍重、普通资料更轻”的产品口径。
- 接下来建议：
  - 真机重点看“我的”页顶部是否终于有明显收口感。
  - 如果还嫌重，下一步优先继续压“当前使用场景”整块，而不是再回头调顶部一句话。

## 2026-06-28 本轮交接：资料页 banner 去房源化，状态筛选改蓝色

- 用户最新反馈：
  - 资料页支持场景切换，顶部 banner 不该继续写房源口径。
  - “发客户状态”选中态不要黑色，整页不需要那么多主色。
- 本轮已改：
  - `miniprogram/pages/library/index.wxml`
  - `miniprogram/pages/library/index.wxss`
- 本轮重点：
  - 顶部 banner 改成更短的“资料直接发客户 / 按场景整理，客户一眼看懂”。
  - AI 提示卡首条标签同步改成通用的“重点资料会保留关键信息”。
  - 发客户状态选中态从黑底改成蓝底，和页面主色统一。

## 2026-06-28 本轮交接：我的页资源库入口去掉“预留”字样

- 用户最新反馈：
  - `行业通讯录` 和 `行业资源` 不应再显示 `预留`，可以改成 `近期开放` 这类更自然的口径。
  - 两者语义要区分：一个更像黄页/找人渠道，一个更像行业资料与机会入口。
- 本轮已改：
  - `miniprogram/pages/profile/index.wxml`
- 本轮重点：
  - `行业通讯录` 和 `行业资源` 的标签都统一为 `近期开放`。

## 2026-06-28 本轮交接：专题从资料主流程收掉，资料详情补返回箭头

- 用户最新反馈：
  - 资料页“更多工具”里的 `专题` 和 `合集` 容易混淆。
  - 资料编辑页里的专题字段存在感也不稳定，如果意义不大应先收掉。
  - 资料详情页需要明确的返回箭头。
- 本轮已改：
  - `miniprogram/pages/library/index.wxml`
  - `miniprogram/pages/note-edit/index.wxml`
  - `miniprogram/components/custom-nav/index.wxss`
- 本轮重点：
  - 资料页去掉 `专题管理` 入口与专题筛选。
  - 资料编辑页标签区只保留标签，不再展示专题相关输入。
  - 资料详情页导航开启返回，且返回按钮视觉更明确。

## 2026-06-28 本轮交接：资料列表轻卡在小屏下改为顶部对齐

- 用户最新反馈：
  - 日常资料列表里，左侧轻设计卡与右侧标题区在真机上出现重叠观感。
- 二次修正：
  - 用户明确要求不要改成顶部对齐，应恢复居中，只给左右两个区域增加安全边距。
- 本轮已改：
  - `miniprogram/pages/library/index.wxss`
- 本轮重点：
  - 列表卡恢复垂直居中。
  - 左封面区和右正文区增加左右 margin，把两块视觉拉开。
  - 标题继续保留断词能力，降低长标题顶坏布局的风险。
  - 进一步把左封面区宽高收小、列间距拉大，让右侧正文不再被虚耗空间挤压。
  - 继续按真机反馈把左封面区加宽到 `138rpx`，并收掉额外 margin，避免可用宽度被 margin 吃掉。
  - 最新修正：轻设计卡 `padding` 改为计入固定盒子，左侧文字图居中，封面固定为 `148rpx`，避免实际盒子溢出到右侧文字区域。

## 2026-06-27 本轮交接：收费与会员策略草案

## 2026-06-27 本轮交接：前四个 Tab 视觉收口第一轮已落代码

- 用户最新确认：
  - 四个 Tab 先按最新效果稿统一风格落地。
  - 我的页只先确定风格，里面 UI 内容和功能后续再单独做。
  - PDF 方案书现在只预留入口心智，不进入当前主功能。
- 本轮已改：
  - `miniprogram/pages/home`：hero 改为代码化 banner，保留雷达图和口号；今日机会、房源助手入口、最近有反馈资料保持不删，只收紧文案和层级。
  - `miniprogram/pages/library`：新增资料页说明卡，统一顶部和列表卡的视觉语言；继续保留房源页信息密度，不做过度压缩。
  - `miniprogram/pages/showcases`：新增合集方案包引导卡，强调“打开小程序查看完整合集 / 支持生成同款 / 导出方案书预留”；合集列表卡改为更稳的右侧操作列。
  - `miniprogram/pages/visits`：雷达页头部收为更短的 AI 提示，加入轻量预留入口语义，建议卡层级更清楚。
  - `miniprogram/pages/profile`：只做风格骨架统一，未重排深层功能。
- 已验证：
  - `git diff --check` 已覆盖上述 10 个前端页面文件并通过。
  - `node --check` 已覆盖 home、library、showcases、visits、profile 五个页面 JS 并通过。
- 接下来建议：
  - 先上传体验版做真机截图，对照这轮参考稿看四个 Tab 的字号、间距、长标题和按钮是否需要二次微调。
  - 如果真机观感过关，再进入下一轮更细的“首页 / 资料 / 雷达”局部打磨，不要先扩大到 PDF 或我的页功能。

## 2026-06-28 本轮交接：雷达页已按效果稿方向单独重做首屏

- 用户指出上一版雷达页与效果稿差距仍大，尤其顶部 banner 不像效果稿。
- 已继续改动：
  - `miniprogram/pages/visits/index.wxml`
  - `miniprogram/pages/visits/index.wxss`
- 本轮重点：
  - 顶部改成真正的雷达 hero，而不是普通说明卡。
  - 左侧是“先看信号，再决定怎么跟”的首屏口号；右侧是雷达图和高意向 / 待跟进 / 复活机会三张信号卡。
  - hero 下方增加 AI 跟进建议提示条。
  - 中部 summary 保留“今天优先跟进”结构，并加软标签；队列区标题和右侧 badge 更接近效果稿。
- 已验证：
  - `git diff --check` 已覆盖雷达页两份文件并通过。
- 还需要：
  - 用户重新在开发者工具/真机看一眼雷达页首屏，如果层级和气质到位，再继续做细调；如果仍偏差，就继续只打磨雷达页，不分散到别页。

- 用户讨论未来是否收月费、免费额度是否给 50 个资源/10 个合集、99 元/月是否可行，以及支付/分销上线时机。
- 已新增策略文档：`docs/stage2-docs/25-pricing-membership-strategy-draft.md`。
- 当前口径：
  - 暂不建议马上开发正式支付系统和分销系统。
  - 先验证四工作台、群资源库、公开页传播、生成同款和客户雷达回访。
  - 免费版早期可以给较宽额度：50 个资料资源、10 个合集/公开页、每月 3 个群资源、最近 7 天基础雷达。
  - 专业版可先用 9.9/19.9 元/月内测价验证付费动作，后续正式价可考虑 19.9/29.9 元/月。
  - 99 元/月适合作为后续 `成交雷达 Pro / 经营增长版`，前提是用户已经感受到高意向识别、用户画像、客户轨迹、沉默复活、资料优化和跟进话术的结果价值。
  - 不建议现在把 `去水印` 当核心收费点，改用 `品牌展示增强 / 专属展示页 / 弱化平台标识`。
  - 分销系统等真实付费和自然推荐成立后再做。
- 注意：
  - 这只是收费策略草案，不是当前支付/分销开发任务。

## 2026-06-27 本轮交接：平台运营群分发 SOP 与每日量化动作

- 用户进一步澄清：群运营难点不在聊天，而在大量群和大量内容之间的低效匹配，以及从手机信息到微信群分发的重复劳动。
- 已确认这是平台内部运营需求，不是面向所有用户的前台功能。
- 已新增文档：
  - `docs/stage2-docs/26-semi-auto-group-distribution-sop.md`
  - `docs/stage2-docs/27-daily-growth-operations-playbook.md`
- 当前口径：
  - 不做个人微信无人值守自动群发。
  - 采用半自动方案：系统/Codex 负责群台账、待分发内容池、推荐群列表、发送记录和复盘；RPA 只做打开清单、切群、打开内容和输入框待确认；人工负责最终判断和发送。
  - 平台运营飞轮表达固定为：`用资源找人，用样板打动人，用雷达留住人。`
  - 每日量化动作围绕 3 件事：补资源、做样板、投渠道，并在晚上做复盘。

## 2026-06-27 本轮交接：群资源库 V1 策划交接

- 用户提出群置换需求：用户手里的商业微信群本身是资源，平台希望以轻量自助方式沉淀群资源池，同时方便进入更多精准商业群做小程序推广。
- 已确认产品方向：
  - 做 `群资源库`，放在“我的”或资源入口，不抢首页成交机会主心智。
  - 搜索优先，不做树形资源目录；前期数据少时用搜索、热词、最近可查看和空结果提交需求承接。
  - 用积分交换代替人工撮合：新用户送 100 分，看一个群二维码扣 30 分，贡献一个群加 20 分，成功进群确认继续加分。
  - 查看次数只代表热度，不代表信用；成功进群确认才是有效信号。
  - 二维码 5 天内自然过期不扣分；超过 5 天且多人反馈失效才扣轻罚。
  - 群类型/用途标签必须支持系统预设 + 用户自定义，避免金融、爱好者群、细分行业等长尾场景被分类卡死。
  - 上传页必须遵循“系统能识别就识别、能点选就点选、尽量少手填”的原则；系统识别二维码可读性/疑似微信/重复，城市、类型、用途、人数、活跃度和有效期尽量点选。
  - 每个群必须设置有效期，默认 5 天，可点选 1/3/5/7 天；页面可展示真实的 `今日新增 X 个群 · Y 个确认可进`。
  - 虚假群下架时追回该群发布/确认奖励，再按级别额外扣罚。
  - 举报不立即奖励，必须确认有效后才给少量积分；恶意举报要限制反馈能力。
  - 规则通知采用站内通知兜底，订阅消息用于重要结果提醒，微信客服用于咨询和申诉解释。
  - 第一版不做充值、不做公开二维码墙、不做人工撮合、不做企业通讯录/爬虫。
- 已新增文档：
  - `docs/stage2-docs/24-group-resource-library-v1.md`
  - `docs/qa/群资源库V1_测试清单与验收标准.md`
- 已归档参考图：
  - `docs/png/group-resource-library-search-mockup.png`
  - `docs/png/group-resource-library-points-mockup.png`
- 后续开发 Codex 接手建议：
  - 先读 `docs/stage2-docs/24-group-resource-library-v1.md` 和 QA 清单。
  - 先做搜索、发布、查看扣分、积分明细、反馈和退分/扣分闭环。
  - 不要扩大到充值、企业通讯录、复杂推荐或群交易。

## 2026-06-27 本轮交接：成交辅助系统 V1 客户雷达与机会提醒

- 用户要求实现“成交辅助系统”方向：不只是资料整理，而是通过客户行为识别成交机会、提醒跟进并提供酷的销售助理感。
- 已新增：
  - `docs/stage2-docs/21-conversion-assistant-opportunity-radar.md`
  - `docs/qa/成交辅助系统V1_测试清单与验收标准.md`
- 后端已完成：
  - `ViewEvent` / `ShowcaseEvent` 增加 `sessionId/durationSeconds/maxScrollPercent/focusSections`。
  - 单条资料和展示页访问支持同 `sessionId` 更新，避免回填停留时间时重复增加 PV。
  - `/api/dashboard/business` 返回 `opportunitySummary/opportunityAlerts/radarProfiles/contentInsights/revivalAlerts`。
  - 规则引擎按咨询动作、多次打开、停留、重点板块、复活访问生成高/中/低意向、解释、建议动作和跟进话术。
  - `get_public_note` 已改为公开脱敏 dict，过滤 `privateData/privateTags/analyticsData/opportunityAlerts/radarProfiles`。
- 小程序已完成：
  - `pages/note-preview` 和 `pages/showcase-view` 生成访问 `sessionId`，进入记录打开，离开回填停留、滚动和重点板块；客户页不显示任何后台判断。
  - `pages/home` 房源模式“今日概览”改为“今日成交机会”，接入机会提醒。
  - `pages/business-dashboard` 增加“客户雷达提醒”和“资料优化建议”，支持复制跟进话术。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：112 passed。
  - 小程序关键 JS `node --check` 通过。
  - 小程序 JSON 递归解析通过。
  - 本轮关键文件 `git diff --check` 通过。
- 注意：
  - 还未上传体验版，客户雷达卡、首页机会卡和公开页行为上报需要真机确认。
  - 由于 `miniprogram/pages/business-dashboard/` 当前仍是未跟踪目录，普通 `git diff --stat` 不显示该目录内本轮改动；提交或交接时要特别检查。

## 2026-06-27 本轮交接：首页企业微信主入口收口

- 用户明确：暂时不考虑企业微信给用户发小程序；小程序里添加微信客服相关入口先删掉，首页现在太乱。
- 本轮小程序已改：
  - `pages/home` banner 删除微信客服主入口，改为单一“添加房源助手”。
  - banner 文案收口为“加企业微信后置顶，把群里房源转发给它”；不再写“打开微信客服，整理完回小程序”。
  - 首页只保留一个企业微信「联系我」插件入口。
  - 常用入口“添加房源助手”不再嵌第二个插件按钮，只滚动回顶部并提示点击顶部按钮。
  - `pages/home` 移除 `wx.openCustomerServiceChat` 调用。
  - `pages/property-same` 的助手兜底改为复制指令并提示“发给企业微信助手”，不再打开微信客服。
  - 删除 `miniprogram/config/customer-service.js`，并移除 `services/api.js` 里未使用的微信客服配置接口包装。
- 当前产品口径：
  - 主入口：企业微信成员好友。
  - 收消息：会话存档。
  - 看结果：小程序内新导入资料、自动归属和房源合集。
  - 暂不承诺：企业微信成员好友整理完成后主动回小程序卡片。
- 已验证：
  - `node --check` 覆盖 home、property-same、workspace-mode、api。
  - 小程序 JSON 递归解析通过。
  - 首页 WXML 基础标签计数通过。
  - 关键文件 `git diff --check` 通过。
- 待真机：
  - 上传体验版后确认首页没有微信客服授权页/白屏按钮。
  - 点击顶部企业微信插件应进入“联系我/添加企业微信”流程。

## 2026-06-27 本轮交接：WorkBuddy 企业微信单聊回复方案评估

- 用户提供 `/Users/yiyi/WorkBuddy/2026-06-26-18-42-00/单独回复`，要求验证其“企业微信单聊回复发送小程序卡片”是否可满足房源助手需求。
- 已读文件：
  - `企业微信单聊回复_发送小程序卡片.md`
  - `企业微信发送小程序给微信用户_技术实现.md`
  - `wecom-miniprogram-bot` 全部源码；`wecom-miniprogram-bot 2` 与前者内容一致。
- 已测：
  - `python3 -m py_compile` 通过。
  - 运行 `WecomClient._api()` 会报 `NameError: name 'cgi' is not defined`，代码无法真正发送。
- 核心问题：
  - 方案依赖 `/cgi-bin/externalcontact/message/send`，但本轮官方文档核对未确认其为普通企业微信外部联系人单聊实时回复接口。
  - 官方可确认的能力仍是微信客服 `kf/send_msg`、客户联系群发 `externalcontact/add_msg_template`、新客户欢迎语 `externalcontact/send_welcome_msg` 等，各自有限制。
- 当前结论：
  - WorkBuddy 代码不能直接并入，也不能证明“企业微信成员好友单聊可后端自由回小程序卡片”。
  - 房源助手主入口继续按用户最新判断：企业微信成员好友/会话存档收消息是自然入口；微信客服不适合作为推广主入口。
  - 发送结果卡片仍需单独找并验证官方可用通道，不能用未确认接口硬上。

## 2026-06-26 本轮交接：房源助手首页入口与企业微信完成反馈

- 用户要求：按刚才讨论，把首页添加房源助手入口和企业微信完成反馈闭环整理成文档并开发，开发完部署服务器。
- 已新增开发文档：`docs/stage2-docs/20-property-wecom-assistant-entry-feedback.md`。
- 已新增自测报告：`docs/qa/房源助手首页入口与企业微信反馈闭环_Codex自测报告.md`。
- 小程序：
  - 新增 `miniprogram/static/icons/wechat.svg`。
  - `miniprogram/utils/workspace-mode.js` 房源工作台首个常用入口改为“添加房源助手”，描述收口为“群里房源发给助手”。
  - `miniprogram/pages/home` 保留原首页结构，banner 内增加“房源助手已准备好”轻入口；常用入口标题改为“常用入口”；点击助手入口优先打开企业微信客服，失败时复制提示文案。
- 后端：
  - `ImportNotification` 增加结果路径、动作和发送状态字段。
  - 导入状态 `success/claimed` 都视为完成反馈。
  - 企业微信真实 `sync_msg` 导入完成后尝试用微信客服接口发文本反馈；发送失败不阻断资料生成。
- 已验证：
  - 小程序关键 JS 检查通过。
  - `home/index.wxml` 标签计数通过。
  - 后端关键文件 py_compile 通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：109 passed。
  - 本轮关键文件 `git diff --check` 通过。
- 待继续：
  - 部署生产后验证 `/health`、`/api/wecom/customer-service-config`、`/api/wecom/notifications`。
  - 需要用户上传小程序体验版后，真机确认微信图标、首页入口和客服打开效果。
- 生产部署已完成：
  - 备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260626-064103-property-wecom-feedback`。
  - 已热更新容器并重启后端。
  - 首次重启因生产缺少此前本地已有的 `PropertyBatch*` schema 短暂 502，已补同步 `backend/app/schemas/notes.py` 和 `backend/app/api/routes_notes.py` 后恢复。
  - 公网 `/health` 200；`/api/wecom/customer-service-config` 200 且 `configured=true`；`/api/wecom/notifications` 200。
  - 还未触发真实企业微信消息回传；下一步需用户发一条房源给助手验证文本完成反馈。

## 2026-06-26 本轮交接：访客身份分层

- 用户确认：中介生成同款后应该被记录，但不能混进租客客户线索。
- 已落地“访客身份分层”底座：客户、疑似中介、疑似上游。
- 后端 `clone_property_same` 成功后，会给原发布者写入一条 `生成同款` 动作，`visitorIdentityType=peer_agent`，`visitorIdentityLabel=疑似中介`。
- 该动作不会投射为 `LeadReminder`，因此不会增加“待联系客户”和优先联系队列。
- `business-dashboard` 最近访客页已新增 `客户 / 同行 / 上游 / 全部` 筛选，默认显示客户；列表、动作流水、访客详情都展示身份标签。
- 设计口径：这是未来可插件化的“访客身份分层”能力，后续团购/服务/名片也可以复用。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_same_clone_note_creates_b_owned_note_with_replaced_contact"` 通过。
  - `.venv312/bin/python -m py_compile backend/app/services/app_service.py` 通过。
  - `node --check miniprogram/pages/business-dashboard/index.js` 通过。

更新时间：2026-06-23
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`
当前分支：`main`
当前最新提交：以 `git log -1 --oneline` 为准。
本地状态：P1 展示页构建器 V1 已实现并完成 AI 测试官验收报告，但尚未提交；仍需排除微信开发者工具自动改动 `miniprogram/project.config.json` 和未跟踪 PDF `企业微信客服服务须知.pdf`。

最新补充：
- 2026-06-25 用户真机截图反馈 `pages/showcase-view` 展示页预览按钮仍变形：清单模板“查看详情”按钮大面积压住内容，底部“生成同款”按钮超出屏幕，同时房源合集混入普通图片资料。已修复：清单行改为三列 grid（封面 / 内容 / 详情按钮）；“查看详情”和“生成同款”改成普通 `view` 轻按钮，避免原生 button 默认样式撑宽；底部联系条单联系方式时改为单列全宽；展示层按 `displayConfig.activeCategory` 过滤，房源合集只展示 `property_listing`，商品/服务合集也按各自类型过滤。验证：`node --check miniprogram/pages/showcase-view/index.js`、WXML `view/button/text` 计数和 `git diff --check` 均通过。仍需用户重新上传体验版后真机确认。
- 2026-06-25 用户补充三点并已处理：`租房对盘工作台` 前台标题改回 `房源工作台`；资料库房源筛选面板默认收起，用户需要时点“展开”；后续开发后端时必须打通“企业微信接收我们自己的小程序房源卡/房源合集”的完整识别链路。具体要求已写入 `docs/stage2-docs/19-property-agent-growth-mvp.md`：收到我们自己的小程序卡不能像贝壳第三方卡一样只拿标题，必须从 `pagePath` 中识别内部 `noteId/showcaseId/sourceNoteId` 等标识并回查完整公开结构，用于生成同款；但仍不能继承原发布者私密保存的真实房东/二房东/渠道联系方式。
- 2026-06-25 已完成“房源中介对盘群增长 MVP”前端第一版。新增开发文档 `docs/stage2-docs/19-property-agent-growth-mvp.md`、测试清单 `docs/qa/房源中介对盘群增长MVP_测试清单与验收标准.md` 和自测报告 `docs/qa/房源中介对盘群增长MVP_Codex自测报告.md`。小程序现在通过 `miniprogram/utils/workspace-mode.js` 的房源增长模式开关默认进入 `property`，首页不再主动弹四工作台选择，也隐藏“切换工作台”入口；其他日常、团购/商品、服务工作台代码和配置均保留未删除。首页文案已收为“资料整理助手 · 房源版 / 租房对盘工作台”，快捷入口为发房源、生成同款、房源合集、客户反馈。
- 2026-06-25 已新增 `miniprogram/pages/property-same` 生成同款确认页。入口来自首页、房源合集公开页和单套房源客户页。页面支持填写微信号、电话和上游联系人，微信号/电话本地记忆；从 A 发布者进入时，B 的上游联系人默认可带 A 的公开联系方式，但 B 可自行修改。主动作是“复制给企业微信助手”，剪贴板内容包含生成类型、来源编号、来源标题、原发布者、我的微信、我的电话、我的上游联系人和隐私规则。注意：本轮是前端半自动引导，不是后端完整克隆接口。
- 2026-06-25 房源合集公开页 `pages/showcase-view` 已增加“我是中介，也想生成这种合集 / 生成同款”入口，并把房源合集文案偏向租房对盘：清单、租房、微信联系、持续更新。单套房源客户页 `pages/note-preview` 已增加“我是中介，也想生成这张房源卡 / 生成同款”入口，仅 `property_listing` 显示。公开客户页仍不展示“隐藏了房东联系方式”等敏感提示。
- 2026-06-25 本轮验证：`node --check` 覆盖 `workspace-mode`、`home`、`showcase-view`、`note-preview`、`property-same` 均通过；`app.json` 和 `property-same/index.json` JSON 解析通过；WXML `view/button/text` 标签计数通过；关键文件 `git diff --check` 通过。未上传体验版，未真机回归，未实现后端克隆接口和媒体资产 hash 去重落库。
- 2026-06-25 已进入“专门营销细节”讨论，并确认首批推广聚焦房源中介/二房东，不再平均推广四个工作台。对外中介版本建议包装为“资料整理助手 · 房源版”，默认展示房源工作台，隐藏日常资料、团购/商品、服务三个主动切换入口，但保留长期架构。首批主打法是利用用户已有十多个房源对盘群，发真实房源卡和房源合集自然种草；重点不是泛讲 AI/SCRM，而是让中介看到“房源卡/合集比普通群消息更专业，且能换成自己的联系方式再发客户”。第一批主推合集模板定为“清单对比”和“精选橱窗”：前者服务对盘群同行快速扫房，后者服务客户和朋友圈视觉展示。房源合集页和单房源页都应有轻量入口“我是中介，也想生成这种合集 / 生成同款房源卡”，点击后进入生成同款引导页。
- 2026-06-25 已确认“生成同款”隐私边界：A 中介发布的房源卡/合集被 B 中介转发给助手或点击生成同款时，B 只复制公开房源内容、图片和展示结构；B 的对外联系方式替换为 B 自己；B 的上游联系人默认可记录为 A 中介，并允许 B 自行编辑。A 私密保存的真实房东/二房东/渠道联系方式默认不继承给 B，除非后续 A 主动开启明确合作共享。公开客户页不展示“隐藏了房东联系方式”；上游联系人私密保存只出现在发布者管理态或生成同款说明中。这个边界非常关键，否则 A 不敢用系统发房源。
- 2026-06-25 已确认媒体资产去重方向：图片和视频应作为独立 MediaAsset，房源卡和合集只保存引用。上传/转存时先算原始 `sha256`，hash 一样就认为是同一个原始媒体，不重复存储；图片统一压缩转 WebP，视频统一转 H.264/AAC MP4 并生成 WebP 封面；同时保存 `originalSha256` 和 `storageSha256`。第一版先做 sha256 完全去重，相似图片/截图/微信压缩后二次识别以后再考虑 perceptual hash。这个能力既省存储，也能支撑营销卖点“同行转来的房源，不用重新传图，一键生成你的版本”。
- 2026-06-25 已修复“快速新增普通笔记后资料库看不到”的后端口径问题。根因是快速笔记保存为 `UserNote` note-only，而资料库读取 `/api/cards`；此前 `/api/cards` 只额外合成 `business_card/service_offer`，普通 `text_note` 未合成。本轮把 owner 场景下无旧 Card 承载、无 `sourceCardId` 的有效 `UserNote` 都合成为 `note_card_{noteId}` 进入资料库，并将普通笔记、链接、图片 OCR 等基础资料分类归一为自然词。房源 `property_listing`、团购商品 `groupbuy_product`、普通笔记 `text_note` 和服务资料 `service_offer` 均已有 `/api/cards` 合成回归测试。普通笔记详情首屏也已收口为“标题 + 内容”，摘要只在扩展为可运营资料后展示。已验证 `.venv312/bin/python -m pytest backend/tests/test_app.py -q` 为 `100 passed`，`node --check miniprogram/pages/note-edit/index.js` 通过。本轮未部署生产，小程序真机要看到新笔记入库仍需部署后端。
- 2026-06-25 产品方向同步确认：日常资料台是资料管理底座，不默认 SCRM 化；普通资料只保留轻量分享反馈。房源、团购/商品、服务工作台继续承载客户动作、访客、留言、预约、接龙、订单和跟进能力。后续首页和底部 Tab 文案应避免让普通资料用户默认看到“客户看板 / SCRM / 高意向”等业务词。
- 2026-06-24 已继续按房源工作台推进逻辑打磨“团购/商品资料库卡片一期”：`groupbuy_product` 资料卡现在不再只是普通资料卡，而是展示商品状态、价格/规格/提货/截止、接龙/下单/待处理/访客信号，并按状态给出下一步提示。商品卡操作区收口为有动态时“处理接龙 + 分享 + 更多”，无动态时“分享 + 更多”；“处理接龙”优先进入单商品 `pages/note-actions` 接龙/下单名单，即使当前为空也显示该商品名单空态。商品详情顶部工作台名称同步为“团购/商品工作台”。本轮验证通过 `node --check`、JSON 解析和关键文件 `git diff --check`；仍需真机确认商品卡小屏布局、按钮居中和各状态文案。
- 2026-06-24 已完成“团购/商品工作台首页一期收口”：前台名称从“团购工作台”调整为“团购/商品工作台”，避免落入普通商品后台或单一接龙名单心智。首页四指标改为“商品 / 待处理 / 今日接龙 / 访客”；商品数和访客数按 `groupbuy_product` 资料过滤，待处理和今日接龙接入现有卖家订单/接龙接口汇总。四指标点击路径已收口：商品进入资料页商品筛选，待处理进入待处理名单，今日接龙进入 `date=today` 今日名单，访客进入团购看板访客页。资料页新增商品入口筛选，卖家侧订单页标题收为“接龙/买家名单”。本轮只做首页入口层和轻筛选，不扩库存、支付、核销或完整电商后台；仍需真机确认首页指标居中、点击路径和今日接龙筛选是否符合直觉。
- 2026-06-24 用户确认合集新建流程应“模板先行”：先选模板帮助用户具象化理解合集，再新建合集、选择生成方式、选择和确认房源、预览、发布。`pages/showcase-edit` 已按该顺序改造；模板卡已改用既有展示页模板参考图，参考图上传到生产服务器 `/media/showcase-templates/*.webp`，单张约 6-8KB，小程序只引用远程 HTTPS 地址，不放主包。第一版真实支持 `从当前筛选生成` 和 `手动选择`，后续能力改为更贴近房源业务的 `按条件筛选`、`按近期反馈推荐`，暂时只提示下一版开放，不做假入口。资料选择区默认 10 条一批，支持“再显示 10 条”。发布 payload 已保存 `displayConfig.generationMethod`。
- 2026-06-24 继续按用户真机反馈修正房源资料库：房源卡现在 `分享` 常驻，有客户动态时显示 `看客户 + 分享 + 更多`，无客户动态时显示 `分享 + 更多`；资料库房源卡和客户页预览前置 `租金 / 户型`，资料库卡片已改成标题下方第二行，不再是普通胶囊标签。针对旧 Card 列表未带完整 structuredData 的情况，前端已从标题/摘要/详情文本兜底识别租金和户型，识别不到时显示待补。微信转发标题改为两行心智：第一行原始标题，第二行 `租金 · 户型`，不融成一个新标题；同时新增房源专属 canvas 分享封面图，图内固定展示原始标题、租金、户型、面积/位置和房源图，降低微信标题渲染不稳定风险，并先放轻品牌署名 `由资料整理助手生成`。客户页预览从站内进入时显示返回箭头；从微信分享单独打开时，因为没有上一页页面栈，底部提供“回到首页”兜底。合集页已读取当前 `workspaceMode`，房源工作台只突出房源合集，团购突出团购合集，服务突出案例合集，日常突出普通资料包；从合集页新建时会把 mode 传到展示页编辑页，编辑页优先按工作台分类选择资料。自动生成合集 / 一句话生成合集尚未实现，应作为下一阶段核心能力单独设计，不要先做假入口。
- 2026-06-24 用户确认客户看板优先级版本符合预期后，继续打磨房源资料库和详情页。已调整：房源卡保留用户原始标题，不清洗标题里的表情；标题下方由系统整理价格/户型/区域/来源和客户信号；房源卡主操作改为有客户动态时“看客户”、无客户动态时“分享”，编辑/合集/复制/删除收进“更多”。房源详情页上半部主动作收成“转发房源 / 客户页预览”，功能组改为“客户功能”并默认折叠开关，`轻 SCRM` 前台改为“客户反馈”，标签专题下沉为“资料归类”。房源微信转发标题优先使用用户原始标题，保持资料库卡、详情页和微信卡片口径一致。仍需体验版真机确认房源卡视觉和微信转发卡片是否不变形。
- 2026-06-23 用户真机确认房源首页四指标、客户看房和房看客数据已经能对应；随后继续改造 `pages/business-dashboard` 首屏：从 `待跟进 / 新访客 / 咨询预约 / 热门房源` 并列，调整为“优先联系队列 + 客户动态”。优先队列只抬预约、留资、明确咨询和高意向访客；客户动态定位为观察与复盘，用来解释为什么优先、今天谁有动静、哪套房被看得多，不作为第二个待办列表。本轮验证通过 `node --check miniprogram/pages/business-dashboard/index.js`、客户看板 JSON 解析和关键文件 `git diff --check`，仍需用户上传体验版真机确认信息是否更清楚。
- 2026-06-23 已完成“房源首页四指标与客户看板一期”小程序前端实现，未提交、未部署、未上传小程序。
- 房源工作台首页四指标已改为“房源 / 打开 / 访客 / 待跟进”，四个指标可点击：房源进入资料 Tab 的房源筛选，打开进入 `pages/business-dashboard/index?mode=property&tab=propertyEffect`，访客进入 `tab=visitors`，待跟进入 `tab=followup`。
- 客户看板 `pages/business-dashboard` 房源模式默认进入“待跟进”，Tab 为“待跟进 / 最近访客 / 房源效果 / 推荐包效果”；旧 `showcases/notes/customers` 参数已做兼容映射，展示页能力保留为“推荐包效果”。
- 资料页 `pages/library` 已支持房源入口筛选；由于资料页是 tabBar 页面，首页先写入一次性本地筛选再 `switchTab`，资料页读取后默认列表模式展示房源资料，并提供“全部”清除筛选。
- 已补充 `pages/visits` 和非房源模式看板路由，避免日常、团购、服务工作台误进入房源客户看板。
- 新增自测和验收报告：`docs/qa/房源首页四指标与客户看板一期_Codex自测报告.md`、`docs/qa/房源首页四指标与客户看板一期_验收报告.md`，验收结论为“需要人工确认”。
- 本轮验证通过：`node --check miniprogram/pages/home/index.js`、`node --check miniprogram/pages/business-dashboard/index.js`、`node --check miniprogram/pages/library/index.js`、`node --check miniprogram/pages/visits/index.js`、`node --check miniprogram/utils/workspace-mode.js`、`node --check miniprogram/services/api.js`、小程序 JSON 递归解析、`git diff --check`。
- 仍需真机确认：四指标点击路径、客户看板首屏是否显示待跟进或明确空态、匿名访客文案、推荐包效果是否能找到原展示页数据、资料页房源筛选和大屏列表可读性。
- 2026-06-23 追加修正：资料页卡片上的“待跟进 / 客户动态”如果来自新资料 `sourceNoteId` 的客户动作，优先跳转 `pages/note-actions/index?id=sourceNoteId`，不再进入旧 `pages/manager` 访问详情，避免“卡片有待跟进，详情无数据”。
- 资料页顶部四个统计“资料总数 / 当前筛选 / 访客 / 客户动态”暂时只作为概览，不做点击跳转；资料页内的处理入口以单张资料卡的客户动态为准。
- 2026-06-23 已新增 `docs/stage2-docs/18-property-home-customer-dashboard-v1.md`，专门沉淀“房源首页四指标与客户看板一期方案”。
- 该方案明确：展示页在房源场景中仍是“多套房源一起发给客户”的推荐包，不是客户看板本身；客户看板默认应服务“谁来了、看了什么、该联系谁”。
- 房源首页四指标建议为“房源 / 打开 / 访客 / 待跟进”，并要求四个指标都可点击：房源进入资料筛选，打开进入房源效果，访客进入最近访客，待跟进入客户看板默认页。
- 客户看板一期 Tab 建议为“待跟进 / 最近访客 / 房源效果 / 推荐包效果”，默认进入“待跟进”；前台避免使用 SCRM，改用客户看板、客户动态、待跟进、推荐包效果等自然词。
- 下一步开发若做客户看板，应先闭环“看得懂、点得通、知道谁该跟进”，不要优先扩展复杂 CRM、BI、客户画像或企业微信自动推送。
- 2026-06-23 已完成“客户痕迹首页与资料卡曝光优化”：解决新资料客户页打开后首页/资料库统计仍为 0、SCRM/留言只能进详情页才明显的问题。
- 后端新增 `POST /api/notes/{note_id}/view`，客户打开 `pages/note-preview` 后会写入浏览事件；有 `sourceCardId` 的资料归入旧 Card 统计，无旧 Card 的资料按 note 自身统计。发布者自己预览不计入客户打开。
- `list_user_notes` 现在返回每条资料的 `stats` 与 `customerSummary`；旧 `list_cards` 在存在 `sourceNoteId` 时补充新资料客户摘要。
- 首页统计口径调整为“资料 / 打开 / 访客 / 客户动态”，客户动态聚合留资、预约、接龙/下单、咨询等动作；首页“客户动态”列表会优先显示有浏览或客户动作的资料。
- 资料库总览改为资料总数、当前筛选、访客、客户动态；资料卡直接显示“打开 / 访客 / 客户动态”，有待跟进或客户动作时红点/高亮并自动靠前。
- 验证通过：后端专项 `2 passed, 95 deselected`，后端 compileall，小程序关键 JS 检查，小程序 JSON 44 个解析，`git diff --check`。
- 注意：该改动包含后端新接口，生产真机验证需要部署后端；小程序首页/资料库视觉变化需要用户重新上传体验版。当前本地工作区有大量未提交后端改动，本轮未擅自整包部署生产。
- 生产部署补充：2026-06-23 16:20 左右已把后端改动部署到生产。备份目录为 `/home/ubuntu/teamBuy-deploy-backups/20260623-162042-note-view-stats`。标准 `docker compose build backend` 卡在 Debian `apt-get update`，未影响线上旧服务；随后采用容器热补丁方式复制 3 个文件到 `teambuy-backend-1:/app/app/...` 并重启容器。公网 `/health` 200，`POST /api/notes/not_exist_deploy_probe/view` 返回业务级“笔记不存在”，`/api/notes?ownerUserId=user_25ec00a0f0` 已带 `stats/customerSummary`，工作台接口 requester 校验生效。
- 2026-06-23 已完成首页工作台视觉与快捷入口小优化，并新增 `docs/qa/首页工作台视觉与快捷入口小优化_Codex自测报告.md` 和 `docs/qa/首页工作台视觉与快捷入口小优化_验收报告.md`。
- 本轮把首页“今日待处理”统计图标从单字改为短词：日常为资料 / 打开 / 分享 / 资料包，房源为房源 / 打开 / 客户 / 预约，团购为商品 / 打开 / 接龙 / 买家，服务为名片 / 打开 / 咨询 / 预约。
- 快捷开始入口已收口：日常为写笔记 / 存图片 / 存链接 / 建资料包；房源为新建房源 / 记需求 / 房源合集 / 我的名片；团购为新建商品 / 记素材 / 团购合集 / 查看接龙；服务为做名片 / 做方案 / 写笔记 / 案例合集。
- 房源、团购、服务均保留普通资料创建入口；顶部右侧已接入 4 张 240×240 本地 PNG 插画，路径为 `miniprogram/static/workspace/`，总大小约 240KB。验收结论为“需要人工确认”，需用户上传体验版后确认两字 / 三字标签居中、不截字、插画不破图和点击路径。
- 2026-06-23 已新增 `docs/qa/首页与Tabbar工作台模式一期_复测与回归报告.md`，结论为“需要人工确认”：P0 代码和自动化证据已闭环，但缺微信开发者工具 / 真机体验版 UI 截图，不能直接判定通过。
- 复测已确认 BUG-01 / BUG-02 在代码与自动化层面闭环；复测命令通过：关键 JS 检查、44 个小程序 JSON 解析、`git diff --check`、权限专项 `7 passed, 89 deselected`、后端主测试 `96 passed`。
- 当前可以进入最终人工确认；真机重点看业务识别提示卡两个按钮是否出现并居中、点击切换后首页 / 工作台是否按新模式展示，以及五个 Tab 是否无白屏。
- 2026-06-23 已按 `docs/qa/首页与Tabbar工作台模式一期_Bug修复任务单.md` 优先修复两个 P0，并新增 `docs/qa/首页与Tabbar工作台模式一期_Bug修复报告.md`。
- BUG-01 已闭环：`pages/resource-create` 的业务识别提示卡新增“继续当前工作台 / 切换到对应工作台”双选；房源映射 `property`，商品/团购映射 `groupbuy`，服务方案/电子名片映射 `service`；切换只保存本地 `workspaceMode`，不改资料 owner、不删除资料。
- BUG-02 已闭环：`GET /api/dashboard/business` 新增 `requesterUserId` 校验，owner 可读，非 owner 返回 403，匿名缺身份返回 401；小程序 `fetchBusinessDashboard` 默认携带当前 owner 作为 requester。
- 权限专项证据已补：工作台总览、展示页效果、单条资料互动均覆盖 owner / 非 owner / 匿名访客；专项测试 `7 passed, 89 deselected`，后端主测试 `96 passed`。
- 本轮验证已通过：小程序全量 JS 检查、JSON 递归解析 44 个、`git diff --check`。
- P1 未本轮展开：最近反馈按类型筛选、资料页按 `workspaceMode` 推荐、合集页动态推荐、`workspaceMode` 后端持久化；已在 Bug 修复报告说明原因。
- 2026-06-23 验收官已输出 `docs/qa/工作台第一期_验收报告.md`，结论为“不通过”；Codex 已重新自测并新增 `docs/qa/工作台第一期_Codex重新自测报告.md`。
- 重新自测报告当时结论同为“不通过”；随后本轮已修复 P0-23 和 P0-27，真机主链路仍需上传体验版后确认。
- 已补充证据：小程序全量 JS 检查通过、JSON 递归解析 44 个通过、`git diff --check` 通过、后端权限相关专项测试 `8 passed, 88 deselected`。
- 原关键风险已修复：`GET /api/dashboard/business` 已新增 `requesterUserId` 校验，不能再只靠前端入口隐藏保护权限。
- 2026-06-23 已根据 `docs/stage2-docs/17-home-tabbar-workspace-mode.md` 新增 `docs/qa/首页与 Tabbar 工作台模式一期_测试清单与验收标准.md`。
- 该清单覆盖 5 个 Tab、首次选择常用工作台、`workspaceMode` 保存和切换、首页按模式变化、工作台按模式变化、客户看板从“我的”迁出、资料库降噪、合集页轻版入口和空态、模式切换不删除资料、普通用户不暴露经营词等 P0。
- 2026-06-23 已完成首页 / Tabbar / 工作台模式一期代码实现：Tabbar 为：首页 / 资料 / 合集 / 工作台 / 我的。
- 新增 `miniprogram/utils/workspace-mode.js`，本地保存 `workspaceMode`，支持日常资料台、房源工作台、团购工作台、服务工作台。
- 首页首次进入显示“你想先整理哪类资料？”，选择后按模式展示今日待处理、快捷开始、最近成果和最近反馈。
- `pages/visits` 已归位为“工作台 / 反馈中心”，普通资料台显示分享效果，业务模式显示客户看板、接龙看板或咨询看板，并复用原访客 / 互动数据。
- “我的”已移除经营区域和经营看板入口，新增常用工作台设置；`pages/showcases` 已作为“合集”Tab，前台叫资料包 / 合集。
- 本轮自测报告：`docs/qa/首页Tabbar工作台模式一期_Codex自测报告.md`。仍需用户重新上传体验版后真机确认 Tabbar 和首次模式选择。
- 2026-06-23 已修正“我的笔记资料详情”底部标签与专题默认房产化问题：非房源资料会过滤“房产 / 房源 / 租房 / 万家丽 / 公寓”等旧默认上下文，标签和专题输入示例改为通用客户资料场景。
- 该修正涉及 `miniprogram/pages/note-edit/index.js`、`miniprogram/pages/note-edit/index.wxml` 和 `miniprogram/utils/note-display.js`；房源资料仍保留房产标签 / 专题建议，用户手动添加的标签通过 `userTags` 保留。
- 验证已通过：`node --check` 针对 `note-edit`、`note-display`、`notes`，旧房产 placeholder 扫描，`note-edit` 核心 `px` 扫描，以及 `git diff --check`。
- 2026-06-23 已新增项目专属运营策划 Skill：`skills/operation-planning/SKILL.md`，并生成 `skills/operation-planning/agents/openai.yaml`。
- 该 Skill 用于后续讨论资料整理助手的运营方向、目标用户、冷启动、私域推广、销售页转化、商业化包装、上线节奏和运营复盘。
- 运营策划的核心飞轮已固定为：资料入库 -> 结构化成资料卡 -> 生成销售页/展示页 -> 发给客户/群 -> 客户打开、咨询、留资、预约、接龙 -> 发布者处理跟进 -> 复用资料、模板和话术再次发出。
- 后续任何运营建议都必须先校准当前产品阶段和真实可用能力；不要把演示数据、mock 链路或未真机验收页面包装成稳定上线能力。
- 本轮未修改后端和小程序业务代码；Skill 校验已通过：`/tmp/teambuy-py312-test/bin/python /Users/yiyi/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/operation-planning`。
- 2026-06-22 用户基于新的服务方案参考图要求“整块重做”，本轮已不再沿旧半成品页面补丁式迭代，而是直接重写 `miniprogram/pages/service-offer-studio/index.js`、`index.wxml`、`index.wxss`。
- 服务方案工作台现在按 3 段主链路组织：模板选择、资料填写、详情页效果确认；模板选择页改成 4 套模板清单 + 当前模板完整首屏预览，确认页改成客户详情页主视角预览。
- `miniprogram/utils/sales-page-templates.js` 已补 4 套服务方案模板的预览元信息，服务方案模板不再只有标题和几条标签。
- `pages/note-preview` 中 `service_offer` 客户页已同步重做：咨询预约 / 服务报价 / 案例背书 / 活动招募四类模板按不同首屏和内容结构展示，并新增底部主动作条（电话、微信、预约、留资）；邮箱和站内消息下沉到联系区。
- 代码侧静态检查已通过：`node --check miniprogram/pages/service-offer-studio/index.js`、`node --check miniprogram/pages/note-preview/index.js`、`node --check miniprogram/utils/sales-page-templates.js`、`git diff --check`。
- 尚未完成：用户重新上传体验版后的真机验收，重点看模板选择页布局、咨询/报价/案例/活动 4 套模板视觉差异、详情页底部动作条、案例图滚动和分享卡片。
- 2026-06-22 已新增服务方案销售页 V1 独立工作台：`miniprogram/pages/service-offer-studio`，流程为选风格、填方案、确认效果、保存分享。
- “添加 -> 服务方案”现在直接进入服务方案工作台；旧模板页里选择服务方案模板也会跳转到新工作台；已有 `service_offer` 在笔记编辑页通过“设置方案样式”进入，不再把模板预览塞进笔记编辑页。
- 服务方案工作台复用现有 4 个模板：咨询预约、服务报价、案例背书、活动招募；同一份服务内容可切换风格，不清空字段。
- 服务方案字段已拆成电话、微信、邮箱、公司网址 / 介绍链接；保存时继续写入 `UserNote.visibilityConfig.structuredData` 和 `conversionConfig`，默认启用电话、微信、留资、预约、轻 SCRM，关闭团购接龙和支付预留。
- `pages/note-preview` 中 `service_offer` 已新增专属客户页结构，突出服务标题、卖点、适合人群、服务内容、流程 / 保障、报价说明、案例图片、联系与预约，不再套普通销售页。
- 服务方案分享卡新增运行时 canvas 封面生成，复用 `business-card-share.js` 的隐藏画布能力，不新增本地图片资源；无上传封面时也能生成模板化服务方案分享图。
- 本轮验证：小程序相关 JS 检查、全量 JS 检查、小程序 JSON 解析、`git diff --check` 通过；后端服务方案 / 电子名片专项测试 `2 passed, 94 deselected`。前端效果仍需用户重新上传体验版后真机确认。
- 2026-06-22 已新增电子名片与服务方案模板库 V1：`miniprogram/utils/sales-page-templates.js` 定义 8 个模板，电子名片包括专业顾问、门店名片、专家介绍、简洁微信风；服务方案包括咨询预约、服务报价、案例背书、活动招募。
- 新增小程序页面 `pages/sales-template-select`，支持电子名片 / 服务方案双 Tab、模板销售页预览、选中状态和“使用模板”；“添加”页里的电子名片和服务方案入口现在先进入模板选择页，再创建并进入编辑页。
- 用户真机反馈第一版模板选择页太像线框、看不到模板、底部按钮变形；已重做为 8 套放大的中文销售页预览，去掉 `serviceHero` 等内部模块名，按钮宽度和文字居中均使用 `rpx + flex` 控制。
- 用户进一步确认电子名片首屏应像参考图一样精美，模板预览、资料库名片卡、编辑页首屏、客户页首屏应保持一致；已统一为“圆形头像 + 姓名 + 身份胶囊 + 公司/门店 + 服务范围 + 电话/微信”的名片母版。模板选择页显示样板信息，创建后自动换成用户自己的信息。
- 微信聊天里的小程序分享卡片不是客户页 WXML，已单独补电子名片分享封面：客户页加载后用隐藏 canvas 生成横版名片封面图，`onShareAppMessage.imageUrl` 优先使用该封面；编辑页直接分享时标题和头像也按名片信息兜底。
- 使用模板创建时会写入模板默认字段、模板名称、模板场景和模板 tone；编辑页顶部显示所选模板名。
- `note-preview` 客户页已接入模板化销售页：电子名片突出人、身份、服务标签和联系方式；服务方案突出服务标题、卖点、适合人群、流程、报价、案例和行动按钮；两类均不显示商品 SKU、接龙下单或房源地图模块。
- 新增 8 模板总览图：`docs/png/business-card-service-offer-template-library.svg`。
- 生产后端已部署新版，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-055345-business-card-service-offer`；公网 `business_card` / `service_offer` 创建探针均已从“类型不支持”变为业务级“用户不存在”。
- 新增统一验收报告：`docs/qa/电子名片与服务方案统一验收报告.md`。本轮验证：后端全量测试 133 passed，小程序全量 JS 检查、小程序 JSON 检查、`git diff --check` 和公网 `/health` 均通过。
- 2026-06-22 已新增电子名片与服务方案卡 V1：后端支持 `business_card` 和 `service_offer`，小程序添加入口可创建“电子名片 / 服务方案”，资料库可筛选和展示，编辑页和客户页已分型渲染；两类默认复用咨询、留资、预约沟通、站内留言和轻 SCRM，不启用商品 SKU、下单、接龙或支付。
- 本轮新增设计说明 `docs/stage2-docs/16-business-card-service-offer.md`，以及 4 张黑白线框原型 SVG：`docs/png/business-card-edit-wireframe.svg`、`docs/png/business-card-preview-wireframe.svg`、`docs/png/service-offer-edit-wireframe.svg`、`docs/png/service-offer-preview-wireframe.svg`。
- 本轮新增自测报告 `docs/qa/电子名片与服务方案卡V1_Codex自测报告.md`。验证结果：后端全量测试 133 passed，小程序全量 JS 检查、小程序 JSON 检查、后端编译检查和 `git diff --check` 均通过。
- 待用户上传最新小程序体验版后，真机验收创建电子名片/服务方案、客户页分享、电话咨询、微信咨询、留资、预约沟通，以及经营看板/待联系回流。
- 2026-06-22 开始“迁移链路小收口 V1”：不做大型工作台，只在“我的笔记”补顶部“最近迁入”概览和单条资料来源/状态标签；顶部迁移卡新增“处理第一条”；普通笔记无业务候选时显示“普通笔记”且不计入待处理，详情页默认是轻量笔记器；有房源/商品候选时，可直接“整理成房源 / 整理成商品”，复用后端 `confirm-type` 进入对应工作台；新增 `docs/qa/迁移链路小收口V1_测试清单与验收标准.md`。
- 2026-06-22 P1 展示页效果页已优化“分享批次”展示：每个批次显示“第 N 次发给客户”、状态标签“已发出 / 已打开 / 看过资料 / 已有咨询”、打开/看资料/咨询三项指标，并保留批次尾号方便和经营看板对照；单展示页效果页和展示页列表折叠效果面板里的资料点击排行，可直接进入对应资料客户动作页；最近访客可进入客户库自动搜索。
- 2026-06-22 P1 小优化一次性收口：客户库、待联系、订单页支持 URL 带入来源/状态/搜索筛选；客户库“当前筛选”可跳到同来源待联系或订单；展示页编辑保存增加名称、简介、分享标题和联系文案兜底。
- 2026-06-22 用户真机确认经营闭环 P0 通过：头像、经营看板下钻和客户详情信息“都能看到了”。`docs/qa/经营闭环头像与处理链路_验收报告.md` 已改为通过；该 P0 可关闭。
- 2026-06-22 已新增真机验收记录模板：`docs/qa/经营闭环头像与处理链路_真机验收记录模板.md`。下一次用户上传最新体验版后，可直接按模板记录头像、经营看板下钻、客户处理卡、客户库、待联系、订单/接龙的通过/不通过结果。
- 2026-06-22 已补后端经营看板头像字段来源：`latestActions` 返回 `avatarUrl`，客户动作合并到 `visitorProfiles` 时保留 `payload.avatarUrl`，并新增测试断言保证客户动作头像能进入看板。
- 已部署该后端补丁到生产，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-015958-dashboard-avatar-flow`；注意后端代码在 Docker 镜像内，单纯 `scp + restart` 不生效，已执行 `docker compose build backend && docker compose up -d backend` 重建镜像。
- 公网 `/health` 正常；生产容器内文件已确认包含 `latestActions.avatarUrl`；真实账号 `user_25ec00a0f0` 字段体检通过：`latestActions` 全量带 `avatarUrl` key，`visitorProfiles` 全量带头像字段，并含联系方式、展示页、分享来源、资料点击下钻字段。
- 本次补充验证更新：后端全量测试 131 passed，小程序全量 JS 检查、小程序 JSON 解析、后端 compileall、`git diff --check` 均通过。
- 2026-06-22 对经营闭环目标做完成度审计时，补齐经营看板“客户资料”主客户卡真实头像展示：有 `primaryCustomer.avatarUrl` 时显示图片，无头像时显示彩色文字兜底。
- 新增验收报告 `docs/qa/经营闭环头像与处理链路_验收报告.md`，结论为代码侧通过、真机侧需要人工确认。
- 本次补充验证：经营闭环相关后端专项测试 5 passed，`node --check miniprogram/pages/business-dashboard/index.js` 通过，小程序 JSON 解析通过，`git diff --check` 通过。
- 2026-06-22 继续复核经营闭环目标时，后端全量测试发现旧头像断言与当前规则不一致：空头像不再强行写入 `payload.avatarUrl/customerAvatarUrl`，前端统一彩色文字兜底；已更新测试断言和文档。
- 最新验证：经营闭环专项测试 8 passed，后端全量测试 131 passed，小程序全量 JS 检查、小程序 JSON 解析、后端 compileall、`git diff --check` 均通过；生产 `/health` 正常。
- 2026-06-22 已补个人资料设置 V1：后端新增 `PATCH /api/auth/users/{user_id}/profile`，小程序“我的 -> 编辑资料 / 设置中心”可编辑昵称、手机号、头像链接，并支持微信 `chooseAvatar`。
- 该能力用于解决真机登录后头像白块问题：没有真实头像时仍显示彩色首字兜底，保存后同步后端、本地缓存和 `app.globalData.currentUser`。
- 资料设置后端已部署生产，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-001727-profile-settings`；公网 `/health` 200，新接口用不存在用户验证返回业务级 404“用户不存在”。
- 本轮验证：个人资料专项后端测试 4 passed，后端全量测试 129 passed，后端 compileall、小程序全量 JS 检查、小程序 JSON 解析、`git diff --check` 均通过。
- 2026-06-22 已补头像上传托管保护：`chooseAvatar` 返回本机临时路径时，保存资料前先调用 `/api/uploads/asset` 上传成生产 URL；后端拒绝保存 `wxfile/file/blob/tmp` 等非 HTTP 头像路径。生产备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-003526-profile-avatar-upload-guard`；公网已验证真实测试用户传 `wxfile://tmp_avatar.jpg` 返回 400“头像地址必须是 HTTPS 地址”。
- 2026-06-22 已进一步收紧头像规则：后端和小程序头像展示均只接受 `https://`，`http://` 会被拒绝或前端兜底为彩色首字头像。生产备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-004456-profile-avatar-https-only`；公网已验证真实测试用户传 `http://cdn.example.test/avatar.png` 返回 400。
- 注意：小程序资料编辑弹窗和头像上传托管属于前端变化，仍需用户在微信开发者工具重新上传体验版后才能真机看到。
- 2026-06-22 已补经营看板下钻体验：顶部“打开 / 访客 / 看资料 / 咨询”四个总数现在会切到访客详情并带筛选；“按展示页拆解”和“分享来源”每行点击也会筛出该展示页或该分享批次带来的具体访客。
- 访客详情页新增“当前筛选”提示卡和当前筛选下的小统计，避免用户看不懂当前列表来自哪个来源。该改动为小程序前端，无需后端部署，但需要重新上传体验版。
- 2026-06-22 已补经营看板动作流水跟随筛选：访客详情页的“动作流水”现在使用当前筛选下的相关客户动作，不再在筛选某展示页/分享来源时混入全量动作。
- 2026-06-22 已补客户库和待联系的“当前筛选”提示：客户库显示当前来源/阶段/意向/标签/搜索组合和客户数量，并可一键回全部；待联系显示当前来源/状态/时间组合和线索数量，并可一键回待联系。该改动同样只需重新上传小程序体验版。
- 2026-06-22 已补订单/接龙页“当前筛选”提示：商家订单中心点状态或来源商品后，会显示当前来源/状态和订单数量，列表落实到具体买家；来源商品右侧“全部”可恢复全部订单。该改动为小程序前端，无需后端部署。
- 2026-06-21 已按 `/Users/yiyi/Desktop/Desktop/myprojects/cloud_tencent/cloud_tencent.md` 完成经营看板生产后端部署，`AGENTS.md` 已补腾讯云生产部署约定。
- 生产部署信息：服务器 `ubuntu@81.70.84.35`，目录 `/home/ubuntu/teamBuy`，域名 `https://teambuy.lifelove.top`，SSH key `/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`。
- 部署前备份：`/home/ubuntu/teamBuy-deploy-backups/20260621-081845-dashboard-closeout`。已完整重建并重启 `teambuy-backend`。
- 公网验证：`/health` 200；`/api/dashboard/business?ownerUserId=user_test` 已变为业务级“用户不存在”，不再是路由级 404；`/api/orders?userId=user_test&role=seller` 返回 200 空列表。
- 已在服务器写入独立演示用户真实数据：`user_836a4a8986`。该数据不是前端 mock，而是通过后端接口写入真实数据库，包含 4 条资料、1 个已发布展示页、5 条展示页事件、留资/预约和 1 条待处理接龙。
- 演示用户经营看板验证结果：打开 2、访客 2、看资料 1、咨询 2、订单 1；展示页 analytics 和订单列表均可返回。
- 用户随后确认可在生产库真实账号写入测试假数据，正式上线前再清理；已向 `user_25ec00a0f0` / openid `oPSh564GCACiIkZxFPV5VWVgdbds` 写入一组经营看板演示数据。
- 真实账号写入后验证：展示页打开 2、访客 2、看资料 1、咨询 2、待联系线索 2、客户资料 4、订单/接龙 3、展示页总数 13，其中已发布 5。
- 用户反馈真机经营看板 UI 与参考图差异明显；已将 `pages/business-dashboard` 从功能型看板改为更接近参考图的四个页面结构，并对测试头像域名做前端兜底，避免显示空白头像。该改动需要重新上传小程序体验版后才能在真机看到。
- 已把本次教训写入项目规则：`AGENTS.md` 新增“UI 参考稿与实现一致性要求”，`docs/pitfalls.md` 新增“不能把高保真参考图做成简化功能版”，`docs/decisions.md` 明确 UI 参考图必须作为验收标准。后续有参考图的页面，不能只交功能版。
- 用户反馈经营看板 owner 视角不应脱敏手机号/微信号，且需要外呼和复制按钮；已在 `pages/business-dashboard` 去掉电话脱敏，并在访客轨迹、笔记数据、客户资料、客户旅程、跟进记录等位置加外呼/复制微信按钮，同时修正“添加跟进 / 备注”按钮文字上下居中。
- 新增复测报告：`docs/qa/客户数据看板_复测与回归报告.md`。原 P0“生产后端未部署经营看板接口”已解决；剩余事项是小程序体验版上传和真机确认。
- 2026-06-21 用户要求把后续计划 1-4 一次收口：上线收口、P0 回归、线索闭环、商品/团购轻订单体验。
- 本轮已完成代码侧收口：经营看板最新客户动作可点击进入线索详情/订单详情/笔记客户动作页，资料点击排行可进入笔记客户动作页；商品/团购订单页新增汇总和状态筛选；商品接龙/下单名单页可直接标记已联系、已完成或取消；订单详情显示“类型”区分下单/接龙。
- 已新增生产部署与真机回归清单：`docs/qa/客户数据看板_上线部署与回归清单.md`。有服务器权限的环境可按该清单部署后端并执行公网/真机回归。
- 已新增服务器端命令模板：`docs/deploy/dashboard-closeout-server-commands.sh`。该脚本不负责从本机同步代码，假设新代码已在服务器 `/home/ubuntu/teamBuy`，然后执行备份、文件检查、重建重启和公网验证。
- 本轮验证通过：`/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q` 为 76 passed；`/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q` 为 113 passed；小程序全量 JS 检查、小程序 JSON 解析、后端 compileall、`git diff --check` 均通过。
- 生产部署已完成：公网 `/api/dashboard/business` 不再是路由级 404。真机若仍为空面板，优先确认小程序是否已上传最新体验版，以及当前登录用户是否已有真实展示页/访客/订单数据。
- 2026-06-21 07:20 左右真机“我的数据加载失败”已定位：当时生产 `https://teambuy.lifelove.top/api/dashboard/business?ownerUserId=user_test` 返回路由级 404，说明新增经营看板后端接口尚未部署到生产；旧前端用 `Promise.all` 导致新增接口失败拖垮“我的”页整体加载。该生产接口问题现已通过部署修复。
- 已调整小程序端入口：`pages/profile/index.js` 不再自动加载经营看板，只加载基础资源统计和消息未读；经营看板主要入口放到“访客线索”页。
- 本轮验证通过：小程序全量 JS 检查、小程序 JSON 解析、后端 compileall、`git diff --check`。
- 当前已可按 `AGENTS.md` 的腾讯云生产部署约定登录服务器；经营看板后端已部署。若真机仍异常，优先检查体验版是否已更新。
- 2026-06-21 客户数据关系与经营看板已开发：新增文档 `docs/stage2-docs/14-customer-data-dashboard-architecture.md`，明确 `ShowcaseEvent / CustomerAction / LeadReminder / 商品轻订单` 的关系。
- 新增后端 `GET /api/dashboard/business?ownerUserId=xxx`，统一聚合展示页打开、访客、资料点击、咨询、待联系线索、商品下单/接龙、最近访客、资料点击排行和最近客户动作。
- 新增小程序复用组件 `miniprogram/components/business-dashboard/`，当前保留为后续嵌入式看板备用，不再放在“我的”页头像下方。
- 新增 `miniprogram/pages/business-dashboard/index` 经营看板详情页，包含展示页效果、访客详情、笔记数据、客户资料四个 Tab；底部 Tab 的“访问记录”已调整为“访客线索”，页面顶部进入经营看板，线索、订单/接龙、客户库、展示页管理只作为详情页内处理按钮。
- 看板 UI 不展示“行为强度分层”等内部概念，只展示真实事实；匿名访客只显示匿名，不包装成实名客户。
- 新增 QA 文档：`docs/qa/客户数据看板_测试清单与验收标准.md`、`docs/qa/客户数据看板_Codex自测报告.md`、`docs/qa/客户数据看板_验收报告.md`；验收结论为“需要人工确认”。
- 新增后端测试代码 `test_business_dashboard_aggregates_real_customer_data`，但当前本机无法实际跑 pytest：系统 Python 缺少 pytest，`.venv` Python 3.9 会因 `dataclass(slots=True)` 失败；Codex Python 3.12 缺少 pytest，挂载 `.venv` 依赖会因 `pydantic_core` 二进制不兼容失败。
- 本轮验证：后端 compileall 通过、小程序全量 JS 检查通过、小程序 JSON 解析通过、`git diff --check` 通过。
- 2026-06-21 展示页真实效果追踪已开发：新增 `showcase_events`，记录 `view / note_click / phone_click / wechat_copy / share` 五类真实事件；发布者预览不记录，公开客户页才记录。
- 后端新增 `POST /api/showcases/{id}/events` 和 `GET /api/showcases/{id}/analytics?ownerUserId=xxx`；analytics 只允许 owner 查看，匿名访客只统计数量。
- 展示页列表接口已返回轻量 `analytics`；小程序展示页列表卡片显示 `打开 X · 访客 Y · 咨询 Z`，已发布项的 `更多` 菜单新增 `效果`，展开后可看打开、访客、看资料、咨询、最近访客和资料点击排行。
- 展示页开发文档和 QA 清单已更新：真实效果追踪列入本阶段 P1；四模板多尺寸视觉回归、商品/房源混合资料模板策略列为 P2 暂缓，等真实上线反馈再开发。
- 本轮验证：小程序全量 JS 检查通过、小程序 JSON 解析通过、后端 Python 3.12 编译通过、`git diff --check` 通过；pytest 未执行，当前 Codex runtime 缺少 pytest。
- 2026-06-21 展示页列表卡片操作区已减负：已发布只常驻 `发给客户 + 更多`，草稿/下架只常驻 `编辑 + 更多`，`预览 / 删除` 放入更多菜单，删除仍二次确认；右侧按钮区收窄，避免继续挤压标题和简介。
- 客户展示页已去掉虚假营销数字：不再展示 `328+ 服务客户`、`128+ 成交案例`、`98% 好评率`，改为真实可解释的 `资料数量 / 最近更新 / 咨询方式`。
- 品牌名片模板已移除虚构客户评价卡；清单目录模板移除不可用的搜索/筛选按钮；橱窗和品牌模板的 `更多/查看更多` 改为 `共 X 条`。
- 本轮验证：小程序全量 JS 检查通过、小程序 JSON 解析通过、后端 Python 3.12 编译通过、`git diff --check` 通过。
- 2026-06-20 根据用户最新反馈收口展示页编辑体验：展示方式入口已删除，保存时固定 `displayConfig.groupBy=tag`，前期只给用户默认按标签分组。
- 展示页客户页资料卡标签已改为等分网格，最多展示 4 个标签；1/2/3/4 个标签都会自动铺满卡片宽度并保留间距，避免 4 标签挤压变形。
- 自动生成信息已跟随分类语义：房产/房源生成房源标题和说明，商品/团购/电商/好物生成商品标题和说明，用户手动改过的文案不会被强行覆盖。
- banner 配置区已移除图片地址输入框，只显示图片缩略图和“换图片”按钮。
- 删除展示页新增 `POST /api/showcases/{id}/delete`，小程序删除按钮改用 POST，避免 DELETE 在部分环境报“方法不允许”；后端仍保留 DELETE 兼容。
- 本轮验证：小程序全量 JS 检查通过、小程序 JSON 解析通过、后端 Python 3.12 编译通过、`git diff --check` 通过；pytest 未执行，当前 Codex runtime 缺少 pytest，项目 `.venv` 为 Python 3.9.6 会因 `dataclass(slots=True)` 失败。
- 2026-06-20 修正展示页模板硬编码房源文案：展示页保存 `displayConfig.activeCategory`，客户页按分类/资料类型切换为房源、好物或资料文案；商品/团购页不再显示“精选房源、好房推荐、找到理想的家”等房产词。
- 编辑展示页资料选择区已改名“笔记资料”，并增加“隐藏 / 展示”按钮，避免笔记很多时长滚动影响后续配置。
- 展示页新增删除能力：后端 `DELETE /api/showcases/{id}?ownerUserId=...`，列表页和编辑页均有删除按钮；列表页草稿/下架也显性显示“编辑 / 预览 / 删除”，解决用户看到“有的只有预览功能”的问题。
- 2026-06-20 根据用户截图反馈继续修正展示页：我的笔记和新建展示页资料选择区已增加“列表 / 双列卡片”切换；新建展示页复用 `note-select-card mode=list/grid`。
- 客户展示页已重排为四套真实不同结构，不再只是同一套列表换颜色：精选橱窗=大图+顾问卡+双列主推，朋友圈长页=生活故事流，清单目录=搜索筛选+紧凑清单，品牌名片=深色顾问品牌页+横向案例。
- 后端公开展示项已补 `badge/primaryText/secondaryText/priceText`，用于四套模板展示价格、主信息和标签。
- 2026-06-20 已补四张展示页标准模板参考图，保存到 `docs/png/showcase-template-01-featured-window.png`、`docs/png/showcase-template-02-moments-story.png`、`docs/png/showcase-template-03-catalog-list.png`、`docs/png/showcase-template-04-brand-card.png`；`showcase-template-00-all.png` 为总览，`showcase-template-mockups.html` 为源文件。
- 2026-06-20 已新增 `miniprogram/utils/note-display.js`，把“我的笔记”里的资料类型、标签、摘要、徽标、上传时间、房源/商品主副字段等展示计算抽成共用工具。
- `pages/notes/index.js` 已改为使用 `decorateNoteForList`；`pages/showcase-edit/index.js` 已改为使用 `decorateNoteForShowcasePicker` 和 `decorateSelectedShowcaseItem`，展示页选资料不再维护一套孤立的笔记卡片逻辑。
- 后端 schema/model/service 和开发文档里的展示页默认模板已统一为 `featured_window`，不再使用旧 `classic_grid` 默认值。
- 展示页联系方式默认值继续优先取登录用户；用户昵称/头像缺失时，会从已选笔记的联系人姓名和头像结构字段兜底。
- 本轮验证：小程序全量 JS 检查通过、小程序 JSON 解析通过、后端 Python 3.12 编译通过、`git diff --check` 通过；后续仍需用户在微信开发者工具真机预览四套模板、发布分享和客户打开效果。当前 Codex runtime 缺少 pytest，项目 `.venv` 为 Python 3.9.6，会因 `dataclass(slots=True)` 无法跑后端 pytest。
- 2026-06-20 展示页新建流程已重构为“模板 + 分类 + 默认全选”低操作版本：先选四个标准模板，再选分类，默认优先房产分类，分类内笔记卡片显示 `加入 / 已加入`，新建时默认该分类全部加入展示页。
- 四个标准模板固定为：`精选橱窗 / 朋友圈长页 / 清单目录 / 品牌名片`，模板名称和副标题集中在 `miniprogram/utils/showcase-templates.js`。
- 新建展示页会自动生成名称、分享标题、简介、banner 和电话；banner 默认取当前分类已选资料第一张图，电话优先取当前用户手机号，再从已选笔记电话/联系字段推断。
- 微信号也会从已选笔记结构字段 `wechat/contactWechat/weixin/wx` 自动推断；发布者昵称和头像保存到展示页 `contactConfig`。
- 新增 `miniprogram/components/note-select-card/`，展示页编辑页已用它渲染分类内笔记选择卡片，后续资料选择场景可复用。
- 客户公开展示页已按 `templateId` 呈现不同视觉：橱窗精选、长页叙事、紧凑目录、品牌名片。
- 展示页 `contactConfig` 已支持保存 `ownerName/avatarUrl`，品牌名片可展示发布者昵称和头像；生产后端已同步并重启，备份路径 `/home/ubuntu/teamBuy-deploy-backups/20260620-221657-showcase-template-flow`，旧镜像标签 `teambuy-backend:before-showcase-template-flow-20260620`。
- 本轮验证：小程序相关 JS 静态检查通过、小程序 JSON 解析通过、`git diff --check` 通过、后端 Python 3.12 编译通过、生产 `/health` 正常；`.venv` pytest 因 Python 3.9 不支持 `dataclass(slots=True)` 未跑通。
- 2026-06-20 修复用户反馈的展示页 `no found`：生产 `/api/showcases` 原本返回路由级 `{"detail":"Not Found"}`，说明展示页接口未部署；已同步后端到生产并重启 `teambuy-backend`。
- 生产部署备注：完整 `docker compose build backend` 卡在 `apt-get update`，本轮使用热修镜像方式上线；旧镜像标签为 `teambuy-backend:before-showcases-20260620-1000`，生产备份路径为 `/home/ubuntu/teamBuy-deploy-backups/20260620-100050-showcases`。
- 公网复测：`/health` 200；`/api/showcases?ownerUserId=user_test` 已变为业务级“用户不存在”；`/api/showcases/public/test_showcase_not_exists` 已变为业务级“展示页不存在或未发布”，不再是路由未上线。
- 小程序展示页构建页已优化“展示方式”：四个选项明确为“不分组 / 按资料类型 / 按标签 / 按自定义分组”；选择自定义分组时，单独显示已选资料的分组名称编辑区。
- 已补展示页显性分享入口：列表已发布项、编辑页发布后底部、发布者预览页顶部均有“发给客户”；分享路径为 `/pages/showcase-view/index?id=展示页ID`。
- 本轮验证：小程序 `showcase-edit` JS 检查通过；小程序 JSON 解析通过；`git diff --check` 通过；展示页后端专项测试 `3 passed`。
- 2026-06-20 完成展示页构建器 V1 QA 验收，报告保存为 `docs/qa/当前项目_验收报告m2.md`；结论为“需要人工确认”。
- 本轮 QA 回归通过：后端编译、小程序 JS 静态检查、小程序 JSON 解析、`git diff --check`、后端全量测试 `112 passed`。
- 展示页后端 P0 自动化项已覆盖：创建草稿、越权资料拒绝、空资料发布失败、发布后公开访问、草稿/下架不可公开、公开接口只返回可见资料摘要。
- 仍需人工确认：小程序构建页真实保存发布、客户展示页点击资料进入单条资料页、真机分享、banner 裁切、电话拨号和微信号复制。
- QA 发现 1 个 P2 文档偏差：测试清单写 `pages/note-preview/index?noteId=xxx`，现有实现和目标页使用 `id=xxx`；建议修正文档或兼容参数。
- 2026-06-20 进入 P1 展示页构建器 V1：已先补开发文档 `docs/stage2-docs/13-showcase-builder-v1.md` 和测试清单 `docs/qa/展示页构建器V1_测试清单与验收标准.md`。
- 后端新增 `ShowcasePage/ShowcaseItem` 和 `/api/showcases`：支持展示页列表、创建草稿、owner 详情、更新、发布、下架和公开访问已发布展示页。
- 展示页只保存 `noteId`、排序和配置，不复制资料正文；公开接口实时读取 active `UserNote` 摘要，草稿和下架页不可公开访问。
- 后端已覆盖展示页创建、越权资料拒绝、空资料发布拒绝、发布后公开访问、下架后不可访问、资料更新后读取最新摘要。
- 小程序新增 `pages/showcases/index`、`pages/showcase-edit/index`、`pages/showcase-view/index`，并在“我的”页增加展示页入口；构建页支持 banner 上传、资料排序、隐藏、移除、展示标题和自定义分组标题。
- 本轮验证：后端编译通过，小程序全量 JS 检查通过，小程序 JSON 解析通过，`git diff --check` 通过，后端全量测试 `112 passed`。
- 小程序体验版仍由用户在微信开发者工具中手动上传；真机分享、banner 裁切、电话拨号、复制微信号需要人工确认。
- 2026-06-20 修复 PaddleOCR 识别接口 502：06:33 测试图片保存成功，但识别请求让 Uvicorn 主进程退出，Nginx 返回 502；已改为 PaddleOCR 子进程隔离执行。
- 生产公网 `POST /api/ocr/notes/note_af53dd1a18/recognize` 已复测 200，后端容器未再重启；该笔资料 OCR 已完成，置信度约 0.94，并给出“可能是商品”的中置信提示。
- 2026-06-20 已部署 OCR 两段式接口到生产，并启用 PaddleOCR：生产 `OCR_PROVIDER=paddle`，依赖为 `paddlepaddle==3.3.1`、`paddleocr==2.10.0`。
- 真机“保存图片”此前报 `Not Found` 的原因是生产尚未部署 `/api/ocr/images`；当前公网 `GET /api/ocr/images` 已变为 `405 Method Not Allowed`，上传接口用不存在用户测试返回业务级“用户不存在”，说明路由已上线。
- 生产容器内 PaddleOCR 已验证可识别测试图 `HELLO 123`；首次真实 OCR 时若模型缓存不存在，会有一次模型下载/初始化开销。
- 2026-06-20 OCR 改为两段式：小程序“我的笔记”页先 `POST /api/ocr/images` 保存图片资料，资料编辑页再由用户点“识别图片文字”调用 `POST /api/ocr/notes/{note_id}/recognize`。
- OCR 只作为图片 Input Adapter：识别文字写入 `structuredData.ocr` 后，再统一走 `ContentObject.sourceType=image_ocr -> content-to-note -> UserNote`，并更新原图片资料；兼容保留旧 `POST /api/ocr/image-to-note`。
- OCR provider 可配置为 `auto/paddle/tesseract/mock`；未配置时 `structuredData.ocr.status=not_configured`，图片仍会保存，用户可手动补正文和字段。
- 2026-06-20 新增归档 parser 插件化收口：archive parser 现在有稳定 `name/msg_types`，registry 显式注册并给解析结果 metadata 写入 `archiveParser/archiveMsgType`。
- 2026-06-20 新增类型识别可解释：`visibilityConfig.recognitionExplanation` 记录候选类型、分数、命中字段、可读信号、parser hints 和摘要；`typeSuggestions` 也带 `score/matchedFields/signals/reason`。
- 2026-06-20 新增中置信人工确认接口：`POST /api/notes/{note_id}/confirm-type`，支持确认成房源、商品或普通笔记；确认后清空 `typeSuggestions`，写入 manual 识别记录，并保留原文、图片和 `structuredData.miniapp`。
- 小程序 `note-edit` 中置信按钮已改为调用后端确认接口，并展示识别摘要和命中信号，不再前端本地拼完整类型转换结构。
- 2026-06-20 收口：已完成当前大 diff 复核，未跟踪 PDF 不纳入提交，`miniprogram/project.config.json` 暂不纳入提交。
- 已提交后端能力：`feat: add lightweight orders and messaging backend`，包含订单接口、消息接口、消息模型、归档 parser、schema、测试和 mock 数据。
- 已提交小程序体验：`feat: add miniapp orders and messaging flows`，包含订单页、消息页、消息入口组件、商品 SKU/名单体验、客户页和我的页入口。
- 本轮收口验证：小程序全量 JS 检查通过；小程序 JSON 解析通过；Python 3.12 `compileall` 通过；`pytest backend/tests/test_app.py -q` 为 66 passed；`pytest backend/tests -q` 为 103 passed；`git diff --check` 通过。
- 生产后端已部署：同步前备份到 `/home/ubuntu/teamBuy-deploy-backups/20260620-031227`，已重建并重启 `teambuy-backend`。
- 公网验证通过：`/health` 正常；`/api/orders?userId=user_test&role=buyer` 返回 200 空列表；`/api/messages/threads?userId=user_test` 返回 200 空会话列表。
- 小程序体验版仍由用户在微信开发者工具中手动上传。
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

## 2026-06-20 补充：企业微信纯图片已接入 OCR 两段式

- 已完成：
  - 统一导入层会识别“无正文、无链接、仅图片且图片已转存”的企业微信内容。
  - 企业微信客服同步纯图片、会话归档纯图片现在先生成 `image_ocr` 图片资料，OCR 状态为 `pending`。
  - 用户仍需在小程序编辑页点击“识别图片文字”才会调用 OCR；未配置 OCR 时仍可手动补文字和字段。
  - 图文混合资料仍走原 `content-to-note`；媒体下载失败仍走媒体重试，不生成无图的 OCR 资料。
- 已验证：
  - 新增 `test_real_sync_pure_image_saves_pending_ocr_note`。
  - 新增 `test_wecom_archive_pure_image_saves_pending_ocr_note`。
  - 后端全量测试：108 passed。
  - `compileall backend/app backend/tests` 通过。
  - `git diff --check` 通过。
- 下一步建议：
  - 用企业微信真实发一张纯图片到生产，确认小程序资料库出现“图片资料 / 待识别”。
  - 在真机小程序点“识别图片文字”，确认 PaddleOCR 识别结果能回写同一条资料。

## 2026-06-20 补充：identity-core P0 收窄为 openid 唯一身份

- 用户确认：
  - 小程序微信 `openid` 是多途径来源进入系统后的唯一身份锚点。
  - 企业微信 `external_userid` 只做系统内部来源映射，不做用户侧绑定管理、解绑或改绑。
- 已完成：
  - `AGENTS.md` 已写入 openid 身份总规则。
  - `WecomIdentityBinding` 增加 `ownerOpenid`。
  - 认领导入时写入 `external_userid -> ownerOpenid/ownerUserId`。
  - 企业微信后续导入归属优先按 `ownerOpenid` 找用户，旧映射继续按 `ownerUserId` 兜底。
- 已验证：
  - 新增 openid 优先归属测试。
  - 身份相关回归：3 passed。
  - 后端全量测试：109 passed。
- 注意：
  - P0 不新增解绑/改绑接口和小程序页面。
  - 测试期如发生误认领，先由后台数据修正，不作为正式用户功能。

## 2026-06-20 补充：identity + OCR 纯图片导入已部署生产

- 已完成：
  - 生产同步前备份：`/home/ubuntu/teamBuy-deploy-backups/20260620-072737`。
  - 已同步后端 app/tests/requirements/Dockerfile，并重建重启 `teambuy-backend`。
  - 生产数据库已补 `wecom_identity_bindings.owner_openid` 列。
- 已验证：
  - 公网 `/health` 正常。
  - 公网 `/api/ocr/images` 已上线，GET 返回 405，不再是路由级 404。
  - 公网 OCR 识别路由对不存在笔记返回业务级“笔记不存在”。
  - 生产容器内 `ownerOpenid` 字段、纯图片导入分流、PaddleOCR worker 均可导入。
  - 生产容器内 PaddleOCR 测试图识别为 `HELLO 123`。
  - 容器重启次数为 0。
- 企业微信真实消息状态：
  - 已手动触发会话存档 `pull -> process`。
  - 当前 `rawCount=0`、`processedCount=0`，说明生产没有新的真实归档消息可处理。
  - 下一步需要用户从企业微信真实发送一张纯图片，然后再次触发 `pull -> process` 验证图片资料 pending OCR 闭环。

## 2026-06-20 补充：企业微信真实图片 OCR 已闭环

- 用户 07:36 左右通过企业微信发送图片。
- 生产已处理该真实图片：
  - 归档消息 `seq=28`，`msgType=image`。
  - 生成资料 `note_f01130a526`。
  - 图片已转存为 `/media/...webp`。
- OCR 已由小程序端触发并成功：
  - `POST /api/ocr/notes/note_f01130a526/recognize` 返回 200。
  - `structuredData.ocr.status=done`。
  - `provider=paddle`，`confidence≈0.948`。
  - 识别文本为聊天截图中的时间、群名、联系人和聊天内容。
- 结论：
  - 企业微信真实图片归档、转存、图片资料生成、用户主动 OCR、结果回写同一条资料均已跑通。
  - 普通照片如果没有可见文字，OCR 不会做“看图识物”，可能返回空或很少文字。

## 2026-06-20 补充：开发期 Docker 改为可挂载模式

- 背景：
  - 当前 Docker 主要用于开发联调期，反复 `docker compose build backend` 会堆积 build cache。
  - 生产正式上线前可以另写生产专用 Dockerfile/镜像发布流程。
- 已新增：
  - `backend/Dockerfile.dev`：只装系统库和 Python 依赖，不复制源码。
  - `docker-compose.dev.yml`：挂载 `backend/app`、`backend/tests`、`backend/mock`、`backend/secrets`，并启用 `uvicorn --reload`。
- 开发期启动：
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend`
- 安全清理建议：
  - 每天可清 Docker build cache：`docker builder prune -af --filter "until=24h"`。
  - 可顺手清悬空镜像：`docker image prune -f`。
  - 不要日常使用带 `--volumes` 的全量清理，避免误删 Postgres 或媒体数据卷。
- 验证：
  - 本机无 Docker CLI，未执行 `docker compose config`。
  - 已用 Ruby YAML 解析校验 `docker-compose.dev.yml`。
  - `git diff --check` 通过。

## 2026-06-21 补充：经营看板 / 展示页数据闭环已统一收口

- 本轮已完成：
  - 经营看板改为独立入口，保留展示页效果、访客详情、笔记数据、客户资料四个视图。
  - 访客和客户资料中的手机号/微信不脱敏，并补齐外呼、复制微信操作。
  - 访客详情底部“添加跟进 / 备注”按钮已修正垂直居中，并接入跟进记录更新。
  - 展示页列表新增单个展示页“效果”入口，进入后查看该展示页打开、访客、看资料、咨询、最近访客、资料点击排行。
  - 后端客户行为按业务强度排序，但小程序不展示“行为强度分层”字样。
  - 增加演示数据清理能力：后端清理接口 + 小程序“我的 -> 开发/测试 -> 清理测试”按钮。
- 生产状态：
  - 生产后端已部署，备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260621-094814-dashboard-scrm-closeout`。
  - 生产已设置 `ALLOW_MOCK_LOGIN=false`，公网 mock 登录返回 403。
  - 真实测试账号 `openid=oPSh564GCACiIkZxFPV5VWVgdbds` 当前保留演示数据，方便继续真机看板测试；上线前可一键清理。
- 已验证：
  - 后端核心测试：76 passed。
  - 后端全量测试：113 passed。
  - `compileall backend/app backend/tests` 通过。
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
  - 公网 `/health` 正常，生产容器 `teambuy-backend-1` 正常运行。
- 下一步：
  - 需要用户在微信开发者工具手动上传/预览新版小程序，才能在真机看到最新前端页面。
  - 真机重点回归：经营看板四个页签、手机号外呼、微信复制、添加跟进、备注、单展示页效果页、清理测试按钮。
  - 上线前确认是否执行“清理测试”，删除生产库中的演示数据。

## 2026-06-21 补充：上线闭环与真实分享追踪 V1 已完成 P0 第一刀

- 新增文档：
  - `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
  - `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`
  - `docs/qa/上线闭环与真实分享追踪V1_Codex自测报告.md`
- 已完成代码：
  - `ShowcaseEvent` 增加 `shareId/shareFromUserId/scene/referrer`。
  - `POST /api/showcases/{id}/events` 接收并保存分享来源。
  - analytics 增加 `shareSourceCount/topShares`。
  - 展示页列表和展示页预览/公开页分享路径携带 `sid/from/scene/ref`。
  - 客户打开展示页、点击资料、电话咨询、复制微信都携带分享来源。
  - 单展示页效果页展示“分享批次”。
- 已验证：
  - 后端核心测试：76 passed。
  - 后端全量测试：113 passed。
  - Postgres 仓储字段/index 测试：3 passed。
  - Python 编译、小程序 JS、小程序 JSON、`git diff --check` 均通过。
- 生产部署：
  - 已部署生产后端。
  - 部署前备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260621-104718-launch-share-tracking-v1`。
  - 公网 `/health` 正常，生产 mock 登录返回 403。
  - 已写入一条生产冒烟事件 `share_prod_smoke_20260621`，analytics 可返回 `shareSourceCount/topShares`。
- 未完成：
  - 小程序需要用户手动上传新版后才能真机验收分享路径。
- 下一步建议：
  - 部署生产后端，验证新字段自动补列和事件接口。
  - 用户上传小程序体验版后，真机验证分享批次链路。

## 2026-06-21 补充：展示页好友打开“页面不存在”已修预览误分享

- 用户反馈：
  - 自己点展示页正常，转发给微信好友后好友点击显示页面不存在。
- 排查：
  - 生产已发布展示页公开接口可正常访问。
  - 预览态/草稿态会让 owner 自己能看，但客户公开访问返回不存在。
  - 如果小程序仍是体验版，未加入体验成员的好友也可能打不开。
- 已修：
  - `pages/showcase-view` 未发布预览隐藏分享按钮和右上角分享菜单。
  - `pages/showcase-edit` 发布态分享统一携带 `sid/from/scene` 并记录 `share` 事件。
- 已验证：
  - 相关小程序 JS 检查通过。
  - 小程序 JSON 解析通过。
  - 展示页后端相关测试通过。
  - `git diff --check` 通过。
- 仍需人工确认：
  - 重新上传/预览新版小程序。
  - 确认用于测试的微信好友是体验成员；如果不是体验成员，需要发布正式版或先加入体验成员。

## 2026-06-21 补充：UI 居中规则已写入文档，展示页分享增加 id 兜底

- 已写入：
  - `AGENTS.md` 新增“UI 文本居中与按钮排版硬规则”。
  - `miniprogram/app.wxss` 新增全局交互控件基线。
  - `docs/pitfalls.md` 记录原生 button 不能靠 `line-height` 假居中。
- 已修展示页列表：
  - 按钮统一 flex 居中。
  - 状态标签不换行，避免“已发布”拆行。
  - 分享按钮 `bindtap=prepareShare`，分享前锁定展示页 id/title/banner，`onShareAppMessage` 再兜底读取。
- 仍需用户上传新版小程序后真机验证。

## 2026-06-21 补充：指定演示展示页公开接口正常，已修分享路径空白兜底

- 用户指定展示页：
  - `演示展示页：房源和好物精选`
  - ID：`showcase_627fc56634`
- 后台确认：
  - 状态为已发布。
  - 公开接口能返回 4 条资料。
  - 事件接口可写入。
- 已修：
  - 分享路径同时带 `id/showcaseId`。
  - 展示页公开页缺 id 或接口失败时显示明确错误，不再空白。
  - 分享来源查询参数改用 `src`，继续兼容旧 `scene`。
  - 展示页列表右侧操作改紧凑横排，避免“发给客户 / 更多”占半张卡。
- 已验证：
  - 相关 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 仍需：
  - 用户重新上传/预览新版小程序后，再用管理员账号和好友账号测试同一条展示页分享。

## 2026-06-21 补充：展示页分享已改为首页中转

- 背景：
  - 指定展示页 `showcase_627fc56634` 后台和公开接口正常，但好友打开分享仍显示页面不存在。
  - 判断问题发生在微信打开分享路径阶段。
- 已改：
  - 展示页相关分享统一使用 `pages/home/index?shareTarget=showcase&showcaseId=...`。
  - 首页识别参数后，在登录判断前跳转 `/pages/showcase-view/index?...`。
  - 客户未登录也能通过首页中转打开公开展示页。
- 验证：
  - 小程序 JS 全量检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 真机验证：
  - 必须重新上传新版小程序后再测试。
  - 测试路径：展示页列表第二条 `演示展示页：房源和好物精选` -> 发给客户 -> 管理员账号/好友账号打开。

## 2026-06-21 补充：首页中转失败，已改为专用展示页分享落地页

- 用户反馈：
  - 12:40 另一台手机打开分享进入首页并显示“首页数据加载失败”。
- 已修：
  - 新增 `pages/showcase-share/index`。
  - 展示页列表、编辑页、公开展示页的分享路径全部改为 `pages/showcase-share/index?showcaseId=...`。
  - 落地页不登录、不加载首页数据，只跳转 `pages/showcase-view/index`。
  - 移除首页 `shareTarget=showcase` 中转逻辑。
- 已验证：
  - 小程序 JS 全量检查通过。
  - 小程序 JSON 检查通过。
  - 分享路径静态检查通过。
  - `git diff --check` 通过。
- 真机验证：
  - 必须重新上传新版小程序，因为新增了页面 `pages/showcase-share/index`。

## 2026-06-21 补充：分享落地最终改用已有 showcases 页面

- 再次调整：
  - 不再使用新增 `pages/showcase-share/index` 作为分享入口。
  - 分享路径统一改为已有 `pages/showcases/index?shareTarget=showcase&showcaseId=...`。
  - `pages/showcases/index` 在登录检查前识别分享参数并跳转公开展示页。
  - `app.json` 已移除 `pages/showcase-share/index` 注册，降低“新增页面未进体验版”风险。
- 已验证：
  - 小程序 JS 全量检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
## 2026-06-21 补充：展示页公开页已改为发布快照缓存

- 背景：
  - 用户明确要求展示页公开访问必须加缓存，不能让每次客户打开都重新拉资料拼页面。
- 当前实现：
  - 展示页发布时写入 `publicSnapshot`。
  - 公开接口 `/api/showcases/public/{id}` 优先返回快照。
  - 老的已发布页没有快照时，首次公开访问自动补快照。
  - 重新发布刷新快照版本。
  - 删除资料时同步修剪相关展示页快照。
- 验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q -k "showcase"`：3 passed。
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q`：113 passed。
  - `python3 -m compileall backend/app -q`：通过。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 已部署线上后端。
  - 线上 `/health` 返回正常。
  - 线上 `showcase_627fc56634` 连续两次公开访问均返回 `snapshotVersion=1`，且 `snapshotCreatedAt=2026-06-21T14:50:04.334312+08:00` 未变化。
- 后续注意：
  - 客户公开页不要再改回实时逐条读取笔记拼装。
  - 展示页内容变更后，用户需要重新发布才刷新客户看到的快照。

## 2026-06-21 补充：上线闭环 1-4 已统一收口

- 本次核准范围：
  - 1. 扩展 ShowcaseEvent 数据字段和接口请求。
  - 2. 修改展示页分享路径，生成并携带 `shareId`。
  - 3. 公开展示页记录事件时带上分享来源。
  - 4. analytics 和经营看板聚合分享来源。
- 当前实现：
  - 后端 `ShowcaseEventRequest/ShowcaseEvent` 支持 `shareId/shareFromUserId/scene/referrer`。
  - 小程序展示页列表、编辑页、公开页分享都会生成 `shareId`，并通过 `pages/showcases/index` 中转携带 `sid/from/src/ref`。
  - 公开展示页打开、点击资料、电话、复制微信都会记录事件并携带分享来源。
  - 单展示页 analytics 返回 `shareCount/shareSourceCount/topShares/recentEvents.shareId`。
  - 经营看板返回 `summary.shareCount/summary.shareSourceCount/topShares`，详情页和复用组件已展示“分享来源”。
- 验证：
  - 后端全量测试：113 passed。
  - 小程序 JS 全量语法检查：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端编译检查：通过。
  - `git diff --check`：通过。
  - 已部署线上后端，线上 `/health` 正常。
  - 线上经营看板 `user_25ec00a0f0` 已返回 `shareSourceCount=11`、`topSharesLength=6`。
- 后续注意：
  - 小程序端变更需要用户重新上传体验版/正式版才能在真机看到“分享来源”模块和最新分享路径。

## 2026-06-21 补充：分享追踪 V1 代码侧 P0 边界加固

- 用户反馈真机分享回归测试多次未成功，本轮按用户要求不再继续卡住真机分享，转为向下推进代码侧收口。
- 已补测试：
  - `test_mock_login_can_be_disabled`：`ALLOW_MOCK_LOGIN=false` 时 mock 登录返回 403。
  - `test_showcase_builder_create_publish_public_and_archive`：草稿和下架展示页调用事件接口均返回“展示页不存在或未发布”。
  - `test_create_note_demo_data_for_owner`：同账号真实资料和真实展示页在清理演示数据后仍保留。
- 验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q -k 'create_note_demo_data_for_owner or mock_login_can_be_disabled or showcase_builder_create_publish_public_and_archive'`：3 passed。
  - `python3 -m compileall backend/app backend/tests -q`：通过。
  - `git diff --check`：通过。
- 本轮没有继续改小程序分享路径，也没有调用生产清理接口。

## 2026-06-21 补充：手动新建房源/商品快速向导 V1 已实现

- 范围：
  - 底部 Tab 现有 `pages/resource-create/index` 已从旧资源创建页改为“添加资料”快速向导。
  - 房源、商品团购、普通笔记统一通过 `POST /api/notes/manual-draft` 创建 `UserNote` 草稿。
  - 创建后跳转 `/pages/note-edit/index?id=...`，不新增房源表或商品表。
  - 图片资料继续复用现有 OCR 图片保存接口，成功后进入 `note-edit`。
- 后端规则：
  - `cardType` 只允许 `property_listing/groupbuy_product/text_note`。
  - `inputMode` 只允许 `paste_text/blank`。
  - 粘贴文案走 `ContentObject(sourceType=manual_text)` 和 `content-to-note` 规则，再按用户选择类型人工确认。
  - 空白房源/商品生成结构化壳和默认转化配置；普通笔记不启用转化能力。
- 验证：
  - 后端全量测试：118 passed。
  - 小程序 JS 全量语法检查：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端编译检查：通过。
  - `git diff --check`：通过。
- 后续真机验收：
  - 底部“添加”进入新向导。
  - 粘贴房源文案后进入房源工作台。
  - 粘贴商品文案后进入商品展示工作台。
  - 空白创建能进入详情页继续补字段。
  - 图片资料入口仍能保存图片并进入 OCR 资料页。

## 2026-06-21 补充：添加页方案 A 极简随手记入口已实现

- 用户最终选择：
  - 使用方案 A，不再保留三步类型选择页作为主形态。
  - 底部中间“添加”打开后直接进入“放进笔记库”输入器。
- 当前实现：
  - 新增 `POST /api/notes/quick-capture`。
  - 普通内容保存为普通笔记，保存后停留当前页，并显示“已保存 / 查看详情”。
  - 高置信房源/团购直接保存成对应业务草稿，再用方案 B 页面内业务提示层引导“完善房源/完善商品”。
  - 用户点“先放笔记库”时，仍保留业务草稿类型，不降级成普通笔记。
  - 图片按钮继续走 OCR 图片资料入口。
  - `...` 更多入口保留空白房源、空白商品、图片资料。
- 已验证：
  - 后端全量测试：122 passed。
  - 小程序 JS 全量语法检查：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端编译检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，线上 `/health` 返回 200。
  - 线上 `POST /api/notes/quick-capture` 已进入业务层；不存在用户验证返回 `404 用户不存在`。
- 后续注意：
  - 小程序端需要用户重新上传体验版/正式版才能看到新添加页。
  - 小程序上传后即可调用线上 `quick-capture`；Codex 不负责自动上传小程序。

## 2026-06-21 补充：22:53 分享打不开日志结论

- 用户测试：
  - 笔记：`note_f114f85595`
  - 展示页：`showcase_627fc56634`，分享 id `share_showcase_627fc56634_1782053566523_88269`
- 生产日志：
  - 笔记在 22:53 仍请求旧的登录/本人接口：`/api/notes/note_f114f85595?ownerUserId=user_25ec00a0f0`，没有走新版匿名公开接口 `/api/notes/public/note_f114f85595`。
  - 展示页在 22:53:42 已请求 `/api/showcases/public/showcase_627fc56634`，并记录访问事件，均 200。
  - 手动请求生产公开接口确认：笔记公开接口 200，展示页公开接口 200。
- 下一步优先级：
  - 先让用户重新上传/切换到最新小程序体验版，再复测笔记分享；新版应出现 `/api/notes/public/{id}` 请求。
  - 展示页如果仍无法显示，重点看真机/开发者工具页面报错和渲染状态；后端公开接口不是当前阻断点。
  - 不要因为本次 22:53 反馈优先乱改后端展示页公开接口。

## 2026-06-21 补充：23:02 分享复测与笔记客户页收口

- 用户 23:02 再测：
  - 笔记 `note_f114f85595`
  - 展示页 `showcase_21cb92837c`
- 日志结论：
  - 笔记仍走 `/api/notes/note_f114f85595?ownerUserId=user_25ec00a0f0`，没有走公开接口。
  - 展示页已走 `/api/showcases/public/showcase_21cb92837c` 并记录事件，后端返回 200。
- 新修复：
  - `miniprogram/pages/note-preview/index.js` 固定用 `api.fetchPublicNote(noteId)` 加载客户预览页。
  - 这能避免客户手机有登录态时被误导到 owner 私有接口。
- 验证：
  - 小程序 JS 检查、JSON 检查、`git diff --check` 均通过。
- 待用户操作：
  - 重新上传最新小程序体验版。
  - 用另一个已加入体验成员的微信号打开分享卡片；打开笔记时后台应看到 `/api/notes/public/note_f114f85595`。

## 2026-06-21 补充：经营看板递进处理台第一版

- 用户确认旧体验版问题后，继续反馈：
  - 经营看板只有“打开、访客、看资料、咨询”总数，不知道属于哪个展示页，也无法点击处理。
  - 分享来源、访客详情、客户库、待联系都需要从总数递进到具体来源、具体客户和具体成交/问询/下单动作。
  - 用户头像登录后仍白色。
- 本轮已完成：
  - 后端 `/api/dashboard/business` 新增 `showcaseBreakdown`、`visitorProfiles`，并给 `topShares` 增加访客预览字段。
  - 经营看板展示页效果页改为“全部展示页汇总 -> 按展示页拆解 -> 分享来源 -> 最近客户”。
  - 访客详情页改为优先显示可处理客户列表，客户卡片可跳线索详情、订单详情或资料动作页。
  - “我的”页没有头像时显示彩色首字兜底；经营看板继续过滤无效示例头像并兜底。
- 生产状态：
  - 已备份生产 `backend/app/services/app_service.py` 到 `backups/20260621-235421-dashboard-drilldown/`。
  - 已同步后端并重建启动 `teambuy-backend-1`。
  - 公网验证 `user_25ec00a0f0` 返回 `showcaseBreakdown=14`、`visitorProfiles=20`、`topShares=6`。
- 已验证：
  - 后端全量测试：127 passed。
  - 小程序全量 JS 检查、JSON 检查、`git diff --check` 通过。
- 还未完成：
  - 需要用户重新上传小程序体验版后真机看新经营看板。
  - 真实头像需要后续做设置中心/资料设置；微信登录不会自动返回头像。
  - 客户库和待联系还需要继续按“总数 -> 来源 -> 具体客户 -> 处理动作”重构。

## 2026-06-21 补充：客户库 / 待联系递进处理视图

- 本轮继续补齐用户提出的同一类问题：
  - 客户库和待联系也要能从总数递进到来源、具体客户和处理动作。
- 已完成：
  - 客户库新增处理阶段分组、来源资料分组，客户卡片显示头像兜底、电话外呼、微信复制、下一步动作、来源资料、跟进入口。
  - 客户库筛选新增 `activeStageFilter`，保存常用视图时会带上处理阶段。
  - 待联系新增优先处理区和按来源资料拆解区，线索卡片显示头像兜底、电话、微信、来源和处理入口。
- 已验证：
  - 客户库/待联系 JS 语法检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传小程序体验版后检查客户库和待联系页面是否符合“总览 -> 分来源/分状态 -> 具体人 -> 处理动作”的心智。
  - 真机确认外呼、复制微信、头像兜底、按钮居中和长标题不挤压。

## 2026-06-22 补充：订单/接龙落实到具体下单人

- 本轮继续补“成交的人、下单的人”：
  - 客户库加载商家订单，新增“下单 / 成交”面板，并在客户卡片显示最新订单状态。
  - 商家订单中心新增状态分组、来源商品分组，订单列表改成买家处理视角。
  - 订单详情新增复制微信。
- 验证：
  - 订单页、订单详情、客户库 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后检查订单中心是否能从总数进入状态/来源，再到具体买家。
  - 检查客户库下单/成交面板是否能进入订单详情。
  - 真机确认外呼、复制微信、复制地址。

## 2026-06-22 补充：资料点击排行可下钻到访客

- 本轮继续收口经营看板：
  - 后端 `visitorProfiles` 增加 `noteIds`，记录访客点过哪些资料。
  - 小程序经营看板点击“资料点击排行”单条资料时，切到访客详情并只看点过该资料的人。
  - 当前筛选下的动作流水同步过滤，不再混入其他资料动作。
- 生产状态：
  - 已备份生产 `backend/app/services/app_service.py` 到 `/home/ubuntu/teamBuy-deploy-backups/20260622-dashboard-note-drilldown/`。
  - 已同步后端并重建启动 `teambuy-backend-1`。
  - 公网验证 `/health` 200，`/api/dashboard/business?ownerUserId=user_25ec00a0f0` 返回的 `visitorProfiles` 已包含 `noteIds`。
- 验证：
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 后端 Python 3.12 编译检查通过。
  - `git diff --check` 通过。
  - 本机后端 pytest 因本地虚拟环境 Python 3.9 不支持项目当前 `dataclass(slots=True)` 未跑。
- 待用户验收：
  - 上传体验版后，在经营看板点“资料点击排行”某条资料，确认下面只出现看过这条资料的访客。

## 2026-06-22 补充：经营看板访客详情处理卡

- 本轮继续改善“看得云里雾里”的问题：
  - 访客列表点击后先打开页内客户详情处理卡，不再直接跳走。
  - 详情卡展示头像、来源、打开/看资料/咨询次数、电话、微信、来源展示页、看过资料和分享批次。
  - 详情卡内可直接外呼、复制微信、回到列表，或进入线索/订单/资料动作处理。
- 验证：
  - 经营看板 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后，在经营看板点任意客户行，确认先出现客户详情处理卡。
  - 真机确认弹层不挡底部按钮、外呼/复制微信按钮居中并可点击。

## 2026-06-22 补充：客户库客户详情处理卡

- 本轮继续把客户库从“卡片列表”收口到“具体人处理”：
  - 点击客户头像/姓名区域先打开页内客户详情处理卡。
  - 详情卡展示阶段、意向、电话、微信、来源资料、最近查看、最近跟进、订单状态和客户标签。
  - 原有外呼、复制、订单、跟进等快操作保留。
- 验证：
  - 客户库 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后，在客户库点客户头像/姓名区域，确认先看到客户详情处理卡。
  - 真机确认“下一步处理”会按订单/电话/微信/客户详情正确执行。

## 2026-06-22 补充：待联系线索详情处理卡

- 本轮继续统一“先看人，再处理”：
  - 待联系页点击线索头像/姓名区域后，先打开页内线索详情处理卡。
  - 详情卡展示状态、跟进时间、电话、微信、来源资料、查看次数、最近查看、备注、最近跟进和归档原因。
  - 原有拨号、复制微信、查看线索、资源详情、标记已联系等快操作保留。
- 验证：
  - 待联系 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后，在待联系页点线索头像/姓名区域，确认先看到线索详情处理卡。
  - 真机确认“立即处理”会优先拨号，其次复制微信，没有联系方式时进入线索详情。

## 2026-06-22 补充：订单/接龙买家处理卡

# 2026-06-22 补充：电子名片微信转发封面独立生成器

- 本轮按用户反馈修正电子名片分享：
  - 新增 `miniprogram/utils/business-card-share.js`，作为电子名片专用微信转发封面生成器。
  - 封面独立绘制，不复用普通资料分享图，也不依赖客户页截图。
  - 封面包含圆形头像、姓名、身份、公司/门店、服务范围、电话/微信和打开名片行动提示。
  - `pages/note-preview` 客户预览页分享已改为调用专用生成器。
  - `pages/note-edit` 编辑页新增隐藏 canvas，电子名片直接转发时优先使用专用封面。
  - `pages/notes` 资料库列表新增隐藏 canvas，电子名片列表分享也优先使用专用封面。
- 真机反馈后继续修复：
  - 用户截图显示微信卡片已经用上名片封面，但右半边被裁切，只露出左侧头像和局部文字。
  - 已修复生成器的画布尺寸逻辑：按真机 `windowWidth` 缩放绘制，再导出 750×600 分享图，避免半张图裁切。
- 验证：
  - 小程序相关 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 新增样式未发现独立 `px`，使用 `rpx`。
  - `git diff --check` 通过。
- 待用户验收：
  - 重新上传体验版后，从电子名片客户预览页、编辑页、资料库列表分别转发给微信好友。
  - 微信聊天里应看到精美横版名片封面，而不是普通小程序二维码卡片。
  - 如果头像没有显示，先确认头像是否为 HTTPS 且在小程序下载域名白名单内；否则应显示文字头像兜底。

# 2026-06-22 补充：电子名片详情页独立重做

- 本轮按用户参考图继续修正电子名片详情页：
  - `pages/note-preview` 中 `business_card` 已从通用客户预览 / 销售页结构中拆出。
  - 新详情页使用绿色名片风格首屏：圆形头像、姓名、身份胶囊、公司/门店、服务范围、电话/微信。
  - 首屏下方四个圆形动作：电话咨询、微信咨询、留下电话/微信、预约沟通。
  - 下方内容改为服务介绍、三列服务范围、联系与二维码/占位、保存名片。
  - `service_offer` 仍使用服务销售页结构；房源、商品、普通资料不受影响。
- 验证：
  - 小程序相关 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 相关 WXSS 未发现独立 `px`。
  - `git diff --check` 通过。
- 待用户验收：
  - 重新上传体验版后打开电子名片客户详情页，确认不再是蓝色普通客户预览页。
  - 对照参考图检查：名片首屏、动作区、服务介绍、服务范围、联系与二维码是否都在。

# 2026-06-22 补充：电子名片图片字段与模板差异

- 本轮继续按用户反馈修正电子名片：
  - 编辑页名片字段去掉头像 URL 和二维码 URL 输入。
  - 新增头像/二维码图片区，直接显示图片。
  - 素材区图片新增“设头像 / 设二维码”，上传二维码后需要点“设二维码”明确指定。
  - 新增公司网址选填字段，详情页展示后点击复制。
  - 详情页电话咨询会清理空格后拨号；微信咨询复制微信号。
  - 保存名片按钮复制完整名片信息。
  - 二维码显示兼容多种历史字段名，并从图片素材兜底。
  - 4 款电子名片详情页已按模板 ID 拉开视觉差异。
  - 微信转发封面已按模板 ID 使用不同色板。
  - 新增 4 模板差异图：`docs/png/business-card-4-template-detail-comparison.svg`。
- 验证：
  - 小程序相关 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 相关 WXSS 未发现独立 `px`。
  - `git diff --check` 通过。
- 待用户验收：
  - 重新上传体验版。
  - 在电子名片编辑页上传二维码图片后，点素材区“设二维码”，保存并打开客户详情页确认二维码出现。
  - 分别创建/切换 4 款电子名片模板，确认卡片封面和详情页风格有差异。

# 2026-06-22 补充：电子名片风格切换与动态联系方式

- 本轮继续修正电子名片核心体验：
  - 编辑页新增 4 款“名片风格”切换区。
  - 用户填完一张名片后，可直接切换专业顾问、门店名片、专家介绍、简洁微信风，不需要重新填写。
  - 切换风格只保存模板元信息，不覆盖已填内容。
  - 电子名片新增邮箱字段。
  - 电子名片详情页移除“预约沟通”，动作区改为按字段动态显示电话、微信、邮箱、留下电话/微信。
  - 电话点击后拨号；微信点击复制微信；邮箱点击复制邮箱。
  - 点击联系方式后，页面出现联系方式提示卡，明确当前点击的是哪个联系方式。
  - 电子名片编辑页功能组不再显示预约开关；服务方案仍保留预约。
- 验证：
  - 小程序相关 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 相关 WXSS 未发现独立 `px`。
  - `git diff --check` 通过。
- 待用户验收：
  - 重新上传体验版后，先填写一张电子名片，再在编辑页切换 4 款风格，确认内容不丢。
  - 分别只填电话/电话+微信/电话+微信+邮箱，确认详情页动作区自动变为 2/3/4 个并居中。
  - 点击电话、微信、邮箱，确认能拨号或复制，并在页面看到对应联系方式提示。

- 本轮继续补“下单的具体人”：
  - 订单/接龙列表点击订单卡后，先打开页内买家订单处理卡。
  - 处理卡展示买家、状态、下单时间、来源商品、规格/数量、订单类型、备注、地址和联系方式。
  - 商家侧可直接外呼、复制微信、查看订单或立即处理。
- 验证：
  - 订单页 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后，在商家订单中心点任意订单卡，确认先看到买家订单处理卡。
  - 真机确认“立即处理”优先外呼，其次复制微信，没有联系方式时进入订单详情。

## 2026-06-22 补充：头像白块兜底扩大覆盖

- 本轮继续处理用户反馈的白头像问题：
  - 小程序统一头像清洗：非 HTTPS、`example.com`、`avatar-default`、`wxfile/file/blob`、`/tmp` 都不渲染图片。
  - 首页访客、访客线索、资源管理页访客、接龙组件、资料动作页、展示页公开页、展示页列表、展示页统计和站内消息补头像兜底或清洗。
  - 登录页默认头像改为空，不再写入 `example.com/avatar-local.png`。
  - 后端登录默认头像改为空，资料更新拒绝无效头像地址。
- 生产状态：
  - 已备份生产文件到 `/home/ubuntu/teamBuy-deploy-backups/20260622-avatar-sanitize-wide/`。
  - 已同步并重建启动后端。
  - 公网 `/health` 正常；PATCH `https://example.com/avatar-default.png` 返回 400。
- 验证：
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 后端 Python 3.12 编译检查通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 重新上传体验版后，真机重点检查首页访客、访客线索、经营看板、客户库、待联系、订单中心、展示页列表和资料动作页头像区域。

## 2026-06-22 补充：完成度审计补漏

- 本轮做了一次代码侧审计：
  - 经营看板、客户库、待联系、订单/接龙的下钻路径已覆盖到具体人处理卡。
  - 头像直渲染剩余风险主要在旧组件和旧资源统计链路。
- 已补：
  - 旧 `components/business-dashboard` 组件内部清洗 `recentVisitors.avatarUrl`，并生成 `avatarText`。
  - 组件模板改读 `displayDashboard`，避免未来复用时把无效头像直接渲染成白块。
- 验证：
  - 旧经营看板组件 JS 检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 后端编译检查通过。
  - `git diff --check` 通过。
- 剩余：
  - 代码侧可验证项已收口；是否完全解决需要用户上传最新体验版后真机回归。

## 2026-06-22 补充：真机回归清单

- 已新增回归清单：
  - `docs/qa/经营闭环头像与处理链路_真机回归清单.md`
- 覆盖：
  - 头像兜底。
  - 经营看板总数/展示页/分享来源/资料排行到具体访客。
  - 客户库来源/状态到具体客户。
  - 待联系来源/状态到具体线索。
  - 订单/接龙来源商品/状态到具体买家。
- 下一步：
  - 用户上传最新体验版后，按清单真机回归。
  - 若仍出现白头像，优先记录页面名、用户/客户名称、是否真实头像、是否从旧分享进入，再查对应接口返回。

## 2026-06-22 补充：Codex 自测报告

- 已新增自测报告：
  - `docs/qa/经营闭环头像与处理链路_Codex自测报告.md`
- 结论：
  - 代码侧自测通过。
  - 生产后端已部署头像入库保护。
  - 真机拨号、复制微信、体验版是否最新、头像域名白名单和另一个微信打开分享后的新记录仍需人工确认。
- 本轮最终检查：
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 检查通过。
  - 后端 Python 3.12 编译检查通过。
  - `git diff --check` 通过。
  - 生产 `/health` 正常。

## 2026-06-22 补充：我的笔记/我的页小优化

- 本轮按用户反馈做了 UI 收口：
  - “我的笔记”快捷分类新增“普通笔记”，并把快捷项调整为“全部 / 普通笔记 / 房源 / 商品团购”。
  - 普通笔记筛选为本地过滤：`text_note` 且没有房源/团购候选，不新增后端参数。
  - “最近迁入”待处理筛选增加整卡绿色选中态，避免只看到列表条数变化。
  - 删除“我的笔记”顶部“保存图片”按钮；图片保存不再从列表页进入。
  - 笔记数量蓝色胶囊显式使用 `rpx` 字号和 flex 居中。
  - “我的”页编辑资料和退出登录移到头像昵称下方；底部退出按钮删除；编辑资料弹窗去掉“头像链接”输入。
  - “我的”页去掉访客线索、待联系、客户库主入口，保留经营看板和订单入口。
- 判断：
  - 客户库暂不物理删除。它仍可作为客户档案沉淀页，并且经营看板/历史链路可能还会依赖。
  - 待联系底层页面也暂不物理删除。若后续确认废弃，需要单独扫描看板下钻、客户库跳转、历史路径和 tab 配置再清理。
- 项目规则：
  - `AGENTS.md` 新增小程序尺寸单位硬规则，要求核心尺寸、统计数字、头像、按钮和宫格默认使用 `rpx`。
- 验证：
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。
- 待用户验收：
  - 上传体验版后检查“我的笔记”普通笔记筛选、迁入筛选绿色态、顶部保存图片按钮是否消失。
  - 真机检查“我的”页头部编辑资料/退出登录按钮是否不变形，编辑资料里是否不再显示头像链接。

## 2026-06-22 补充：电子名片独立工作台

- 用户最新确认：
  - 按其提供的流程图和 4 款风格图开发。
  - 电子名片单独开页面，不放在“我的笔记”或输入笔记器里。
  - 资料库增加“电子名片”按钮。
  - 4 款风格尽量复原参考图，差异必须明显。
- 本轮实现：
  - 新增 `miniprogram/pages/business-card-studio/`：
    - 第一步：4 款名片风格预览。
    - 第二步：填写名片信息，含头像、二维码、姓名、职位、公司/门店、电话、微信、邮箱、网址、城市、地址、服务范围、服务介绍。
    - 第三步：同时预览微信转发卡片和客户详情页。
  - `miniprogram/app.json` 注册新页面。
  - `miniprogram/pages/library/` 新增“电子名片”快捷入口。
  - `miniprogram/pages/resource-create/index.js` 旧“电子名片”入口改跳新工作台。
  - 保存仍创建/更新 `business_card` 类型 `UserNote`，不新增后端系统。
- 验证：
  - `node --check miniprogram/pages/business-card-studio/index.js` 通过。
  - `miniprogram/app.json` 和新页面 JSON 解析通过。
  - 新页面和资料库触达 WXSS 未发现核心独立 `px`。
  - 本轮触达文件 `git diff --check` 通过。
- 后续建议：
  - 用户上传体验版后真机检查资料库入口、4 款模板视觉差异、资料切换不丢、头像/二维码显示。
  - 若用户认可独立工作台体验，再把已有电子名片的“编辑”入口也逐步迁到该工作台的编辑模式。

## 2026-06-22 补充：电子名片模板选择体验修正

- 用户反馈：
  - 模板头像不能只是一个字，4 款模板要两男两女。
  - 双列在手机上会把横向名片挤压变形，需要列表/双列选择，默认列表。
  - 需要核对制作预览、微信转发卡片、点击后的详情页是否一致。
- 本轮处理：
  - `miniprogram/utils/sales-page-templates.js`：4 款电子名片模板补完整默认人物信息，并标记头像样式。
  - `miniprogram/pages/business-card-studio/`：模板选择页新增列表/双列切换，默认 `list`；模板头像改为两男两女职业头像样板。
  - `miniprogram/utils/business-card-share.js`：转发封面调色对齐 4 款模板，CTA 去掉“预约沟通”。
- 核对结论：
  - 制作页保存 `displayTemplate`、`displayTemplateName`、`displayTemplateTone`、`structuredData`。
  - 客户详情页通过 `displayTemplate` 解析模板并渲染对应详情样式。
  - 微信转发封面通过同一套 `businessCardHero` 数据生成图片。
  - 编辑页保留 SCRM/转化配置是合理的；新制作工作台隐藏复杂配置，但保存时仍保留轻 SCRM 与留资能力。

## 2026-06-22 补充：电子名片模板写真头像

- 用户反馈：
  - 模板头像希望换成超现实写真美女和男生头像。
- 本轮处理：
  - 生成一组 2 男 2 女写真头像。
  - 曾短暂切分到 `miniprogram/static/business-card/`；后因主包超过 2MB，已改为服务器 WebP。
  - 4 款电子名片模板的 `preview.avatarUrl` 当前指向服务器 WebP。
  - 模板选择页优先渲染头像图片，图片不可用时才回落到 CSS 样板/首字兜底。

## 2026-06-22 补充：头像资源迁移到服务器 WebP

- 用户反馈：
  - 真机调试报错 `source size 2200KB exceed max limit 2MB`。
  - 要求图片不要再放前端包，放入服务器并改成 WebP。
- 本轮处理：
  - 4 张模板头像通过线上上传接口转为服务器 WebP。
  - `miniprogram/utils/sales-page-templates.js` 改为引用 HTTPS WebP 地址。
  - 删除前端包内的写真头像 PNG/JPG 文件，小程序目录约 1.5MB，低于 2MB 主包限制。
  - `backend/app/main.py` 增加 `mimetypes.add_type("image/webp", ".webp")`，并已部署生产后端。
- 线上头像 URL：
  - `https://teambuy.lifelove.top/media/media_a535beaccd-manual_asset_0afb19f5db.webp`
  - `https://teambuy.lifelove.top/media/media_35b3a047fc-manual_asset_25ae3bb5b2.webp`
  - `https://teambuy.lifelove.top/media/media_c8b9458757-manual_asset_b208951151.webp`
  - `https://teambuy.lifelove.top/media/media_94ec97ee72-manual_asset_744c2c96ca.webp`
- 生产验证：
  - `https://teambuy.lifelove.top/health` 正常。
  - 4 个 WebP 均返回 `content-type: image/webp`。

## 2026-06-22 补充：电子名片头像裁切修正

- 用户反馈：
  - 真机中部分头像显示为 4 人拼图或裁切错误。
- 本轮处理：
  - 从原始 2x2 头像图重新按像素坐标切出 4 张单人头像。
  - 重新上传服务器 WebP，替换 `sales-page-templates.js` 中 4 个模板头像 URL。
- 当前正确头像 URL：
  - 专业顾问男：`https://teambuy.lifelove.top/media/media_a535beaccd-manual_asset_0afb19f5db.webp`
  - 门店名片女：`https://teambuy.lifelove.top/media/media_35b3a047fc-manual_asset_25ae3bb5b2.webp`
  - 专家品牌女：`https://teambuy.lifelove.top/media/media_c8b9458757-manual_asset_b208951151.webp`
  - 简洁微信男：`https://teambuy.lifelove.top/media/media_94ec97ee72-manual_asset_744c2c96ca.webp`

## 2026-06-22 补充：已有名片进入电子名片工作台

- 用户反馈：
  - 电子名片工作台前面需要有“已做好的名片”区域。
  - 已有名片应从“我的笔记/编辑名片”进入工作台，在工作台实时切换风格，看卡片预览和详情预览，再保存和分享。
  - “我的笔记”的编辑名片页不要再放风格选择网格。
- 本轮处理：
  - `pages/business-card-studio/index` 支持 `?id=noteId` 加载已有名片。
  - 工作台顶部新增“已做好的名片”提示区。
  - 确认页增加“卡片预览 / 详情预览”切换和 4 款模板缩略图。
  - 切换风格后标记未保存，保存后才显示“预览 / 分享”，避免分享旧版本。
  - 保存时合并保留已有 `conversionConfig`，不清掉编辑页配置过的 SCRM 能力。
  - `pages/note-edit/index` 电子名片区移除原“名片风格”网格，新增“设置名片风格”按钮跳转工作台。

## 2026-06-22 补充：服务方案工作台白屏修复

- 用户反馈：
  - 服务方案页面打开白屏。
- 本轮处理：
  - 修复 `pages/service-offer-studio/index` 默认表单引用未定义变量的问题。
  - 修复服务方案预览构建时图片列表没有兜底的问题。
  - 为页面补充默认模板、默认表单和默认预览，避免首屏初始化阶段空数据触发运行时异常。
  - 增加页面可见错误态：未登录、模板加载失败、读取已有方案失败时显示提示和“重试/去登录”，不再纯白屏。
- 验证：
  - 服务方案页面 JS 语法检查通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 解析检查通过。
  - 模拟有用户加载：4 套服务方案模板正常出现。
  - 模拟无用户加载：显示登录提示，不白屏。
- 待用户验收：
  - 需要重新上传小程序体验版后，在真机从资料库“服务方案”入口打开工作台确认。

## 2026-06-23 补充：服务方案工作台第二轮重做已继续推进

- 用户新增要求：
  - 工作台不要再纵向拖太长，顶部“选模板 / 填资料 / 确认效果”改成横向。
  - 模板方案区也改为横向排列，点击一个模板，下方预览立即跟着变化。
  - “服务报价 / 案例背书”需要真实默认图，不要白块占位。
  - 资源库里在“电子名片”旁边新增“服务方案”独立入口，原笔记器/快速入库入口保留。
- 本轮已做：
  - `pages/service-offer-studio/index` 步骤条与模板条改成横向滑动结构。
  - `sales-page-templates.js` 为报价型与案例型补入服务器 WebP 默认参考图。
  - `pages/note-preview/index` 与 `utils/business-card-share.js` 支持服务方案模板服务器图片兜底，避免详情页和分享图掉图。
  - `pages/library/index` 新增“服务方案”独立入口，位置与“电子名片”并列。
- 已验证：
  - 服务方案工作台、客户详情页、资源库入口相关 JS 语法检查通过。
  - `git diff --check` 通过。
- 下一步建议：
  - 用户重新上传体验版后，真机重点看服务方案工作台首屏长度、模板横滑手感、案例图展示和资源库入口位置是否符合参考图预期。

## 2026-06-23 续更：服务方案工作台真机变形已继续修

- 用户最新反馈：
  - 服务方案工作台和“我的笔记 / 电子名片”几乎同类，应直接参考电子名片稳定样式。
  - 当前截图中标题、步骤、模板卡和预览图片在手机/iPad 上都有撑宽或变形。
  - 副标题一行放不下必须自动换行；核心尺寸必须继续用 `rpx`。
- 本轮已做：
  - `pages/service-offer-studio/index.wxml` 去掉步骤区横向滚动结构，改成三列固定步骤。
  - `pages/service-offer-studio/index.wxss` 增加页面宽度约束、文本换行、模板卡纯文字布局、预览图固定 rpx 高度和图片铺满规则。
  - `utils/sales-page-templates.js` 切换到 v2 高分辨率源图转存后的服务器 WebP 资源。
  - 当前后端图片：
    - `https://teambuy.lifelove.top/media/media_aa4adc7919-manual_asset_5d2328325f.webp`
    - `https://teambuy.lifelove.top/media/media_3463380142-manual_asset_1dd9a72074.webp`
    - `https://teambuy.lifelove.top/media/media_9ff631d3e1-manual_asset_6a708c50d6.webp`
  - 已删除小程序前端 `miniprogram/static/service-offer` 图片文件，避免默认图进入 2MB 代码包。
  - 选择模板卡去掉缩略图，只展示模板名称、标签和适合场景；横向滚动区增加 `2rpx` 安全内边距和宽度约束。
- 已验证：
  - 服务方案 JS 与模板配置 JS 语法检查通过。
  - 服务方案工作台相关 WXSS/WXML 未发现非 `rpx` 核心 `px` 尺寸。
  - 前端不再存在 `/static/service-offer` 代码引用；后端 WebP 图片公网返回 `200`。
  - `git diff --check` 通过。
- 待真机验收：
  - iPhone 普通屏、小屏和 iPad 上确认页面不再横向撑开，副标题能换行，模板选择区不再出现缩略图，预览图铺满且不变形。

## 2026-06-23 再续：服务方案三步页面手机溢出补修

- 用户最新反馈：
  - “选模板 / 填资料 / 确认效果”顶部三步和模板横滑区基本正常。
  - 4 个类型的样板卡片、下方预览、填写资料页底部按钮、确认效果页在手机端仍有溢出。
  - 要求页面宽度 100%，但保留 rpx 留白。
- 本轮已做：
  - `pages/service-offer-studio/index.wxss` 对阶段卡、样板预览、表单卡、确认页预览补齐 `width/max-width/min-width` 约束。
  - 关键内层卡片改为 `calc(100% - 4rpx)`，左右保留 `2rpx` 安全留白。
  - 缩小手机端容易挤压的详情预览头像、英雄区边距和标题字号。
  - 确认页 4 个客户动作由一行 4 列改成 2 列，减少文字挤压。
  - 底部操作条由固定 grid 改为 flex，按钮可收缩；“下一步：确认效果”文案缩短为“确认效果”。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js` 通过。
  - 服务方案工作台相关 WXSS/WXML 未发现非 `rpx` 的核心 `px` 尺寸。
  - 前端未重新引入 `/static/service-offer` 图片引用。
  - `miniprogram/static` 未发现超过 200KB 的静态图片文件。
- 待真机验收：
  - 重新上传体验版后，用普通手机重点看三个步骤页是否还有横向滚动：模板预览区、填写资料底部按钮、确认效果客户预览页。

## 2026-06-23 三续：服务方案底部遮挡与微信转发封面

- 用户最新反馈：
  - 工作台三步页面底部“返回 / 使用这个模板”等按钮会挡住模板和上方预览内容，需要留白并向下。
  - 服务方案微信转发不能使用默认小程序卡片，应像电子名片一样保持模板、转发卡片和“我的笔记”列表的完整一致。
- 本轮已做：
  - `pages/service-offer-studio` 增加底部 spacer，sticky 操作条更贴近安全区，减少遮挡。
  - `utils/note-display.js` 增加 `serviceOfferPreview`，从服务方案结构化数据和模板默认图构建列表/分享预览。
  - `pages/notes/index` 将服务方案纳入列表分享图预生成，调用 `generateServiceOfferShareImage`。
  - “我的笔记”服务方案列表从普通左图右文卡改为专属方案预览卡，展示模板名、服务标题、卖点、标签和封面。
  - 列表页分享服务方案时使用专属横版模板封面和服务方案标题，不再优先退回默认小程序卡片。
- 已验证：
  - `node --check` 已覆盖 `pages/notes/index.js`、`pages/note-preview/index.js`、`utils/note-display.js`、`utils/business-card-share.js`、`pages/service-offer-studio/index.js`。
  - 工作台与我的笔记相关 WXML/WXSS 没发现核心布局使用 `px`。
  - `miniprogram/static` 仍约 `88K`，没有新增前端大图。
  - `git diff --check` 通过。
- 待真机验收：
  - 重新上传体验版后，验证工作台底部按钮是否还遮挡最后一屏内容。
  - 从“我的笔记”服务方案点击“发方案”，看微信聊天里的卡片是否显示完整服务方案横版封面。

## 2026-06-23 四续：P0/P1 代码侧统一收口

- 用户确认当前测试没有问题，要求 Codex 统一处理剩余 P0/P1 开发操作，体验版上传由用户处理。
- 本轮已做：
  - 服务方案双列卡片新增专属迷你方案预览，避免双列模式退回普通封面卡。
  - 电子名片 / 服务方案分享按钮新增“封面准备中”状态，封面生成完成或失败后恢复“发名片 / 发方案”。
  - `note-display` 的 `serviceOfferPreview` 继续作为服务方案列表、双列卡片、分享封面的统一数据源。
  - 新增自测报告：`docs/qa/电子名片与服务方案P0P1收口_Codex自测报告.md`。
  - 确认生产 mock 登录关闭能力已有 `ALLOW_MOCK_LOGIN` 开关和自动化测试。
- 已验证：
  - `node --check` 覆盖 `pages/notes`、`pages/note-preview`、`utils/note-display`、`utils/business-card-share`、`pages/service-offer-studio`。
  - 工作台 / 我的笔记相关 WXML/WXSS 未发现核心布局 `px`。
  - 小程序前端密钥关键词扫描只命中登录页提示文案，未发现真实密钥。
  - `miniprogram/static` 约 `88K`，没有新增前端大图。
  - `git diff --check` 通过。
  - 后端 mock 登录关闭已有用例，但本机 Python/pytest 环境不匹配，本轮未实际执行。
- 待用户体验版确认：
  - 分享按钮封面准备状态是否自然。
  - 双列卡片服务方案是否符合模板感。
  - 微信聊天卡片是否稳定显示完整横版封面。

## 2026-06-23 五续：首页与 Tabbar 工作台模式一期验收

- 用户要求：
  - 基于 `docs/qa/首页Tabbar工作台模式一期_Codex自测报告.md` 和 `docs/qa/首页与 Tabbar 工作台模式一期_测试清单与验收标准.md` 输出验收报告。
- 本轮已做：
  - 新增 `docs/qa/工作台第一期_验收报告.md`。
  - 验收结论为“不通过”。
  - 主要原因：P0 未全部闭环，P0-23 业务识别提示仅部分覆盖，P0-27 权限和隐私缺专项回归证据，真机主链路仍待确认。
  - 报告已包含未覆盖/异常项、开发 Bug 单、P0/P1 回归清单和上线前检查事项。
- 新会话接手建议：
  - 如果继续开发，优先修复 P0-23：识别房源/商品/服务资料后，提示用户“切换到对应工作台”或“继续当前工作台”。
  - 同步补 P0-27 权限回归证据：owner、非 owner、匿名访客三类身份访问工作台/看板/展示页效果。
  - 修复后重新输出 Codex 修复报告，再让 AI 测试官做复测与回归。

## 2026-06-23 六续：资料库展示与客户入口修正

- 用户最新反馈：
  - 15:34 左右测试纯文字、微信笔记、链接均能进入资料库。
  - 资料库列表区域只显示左半边，疑似双列卡片布局没有铺满。
  - SCRM 和留言入口不明显，需要恢复/露出。
- 本轮已做：
  - `miniprogram/pages/library/index` 增加 `viewMode`，资料库默认“列表”展示，并提供“双列”切换。
  - 资料库页面新增页面级 `.card-grid.list-mode` / `.card-grid.grid-mode`，覆盖全局 `.resource-card { width: calc(50% - 10rpx) }`，修复半屏卡片。
  - 每张资料卡新增“客户/SCRM”和“留言”入口；客户入口跳 `manager`，留言入口打开消息中心。
- 已验证：
  - `node --check miniprogram/pages/library/index.js` 通过。
  - 小程序 JSON 解析通过。
  - 资料库相关文件 `git diff --check` 通过。
- 待用户体验版确认：
  - 上传体验版后查看资料库默认列表是否铺满宽度。
  - 切换“双列”后是否能左右两列正常展示。
  - 点击“客户/SCRM”和“留言”是否符合预期。

## 2026-06-23 七续：房源客户看板专属口径与 Python 3.12

- 用户最新反馈：
  - 现在还没上线，客户痕迹/待跟进是核心付费价值，不能因为一期想简单就退让。
  - Python 版本问题不能每次影响后端验证，要求统一升级到 3.12。
- 本轮已做：
  - 创建 `.venv312`，当前 Python 为 `3.12.13`，已安装后端完整依赖。
  - `.gitignore` 增加 `.venv312/`。
  - 后端 `GET /api/dashboard/business` 支持 `mode` 参数。
  - 新增 `mode=property` 专属房源客户看板聚合：房源数、打开、访客、待跟进、房源效果、推荐包效果、最近访客、客户动作和访客画像。
  - 房源模式过滤非房源客户动作和非房源 `note_click`，避免服务/普通资料污染房源看板。
  - 首页房源四指标优先使用后端房源看板汇总。
  - 资料库卡片如有 note 级客户动作，客户入口优先进入 `pages/note-actions/index?id=...`。
  - 新增后端回归用例：`test_property_business_dashboard_only_counts_property_customer_data`。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - 关键文件 `git diff --check`：通过。
- 新会话接手建议：
  - 真机/开发者工具上传体验版后，优先验证房源首页四指标是否和客户看板数字一致。
  - 用企业微信发一条真实房源，打开/预约/留资后检查：首页 `待跟进`、客户看板 `待跟进`、单条资料客户动作页是否三处一致。
  - 如果继续优化 UI，先优化客户看板首屏“待跟进客户”列表，不要先扩展复杂 CRM。

## 2026-06-23 八续：房源首页今日/累计切换

- 用户最新反馈：
  - 当前首页数字应是历史累计，却写成“今日概览”，口径不对。
  - 希望首页能同时显示今日和历史累计，并且点击今日访客后能看到今天具体谁来了、看了哪些、如何联系。
- 本轮已做：
  - 后端房源看板返回 `summary`（累计）和 `todaySummary`（今日）。
  - 今日口径覆盖：今日新增房源、今日打开、今日访客、今日新增待跟进。
  - 访客画像、最近访客、客户动作增加今日标记。
  - 单条房源浏览合并进 `visitorProfiles`，今日访客不再只依赖推荐包。
  - 首页房源概览新增“今日 / 累计”切换，默认今日。
  - 首页进入客户看板时，今日口径携带 `range=today`；客户看板筛选今日访客和今日动作。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - 关键文件 `git diff --check`：通过。
- 新会话接手建议：
  - 真机验证首页“今日/累计”切换是否清楚，特别是今日新房源为 0 时用户是否能理解。
  - 点击今日访客进入客户看板后，确认只出现今天的访客；历史访客只能在累计入口或清空筛选后看到。

## 2026-06-23 九续：待跟进数字与列表不一致修复

- 用户最新反馈：
  - 首页待跟进显示 1，但点击进入客户看板没有看到待跟进记录。
- 本轮已做：
  - 核对确认为 `LeadReminder` 和 `CustomerAction` 两套来源不一致。
  - 房源客户看板 `latestActions` 现在会合并 pending `LeadReminder`。
  - 无客户动作的旧线索会生成 `lead-followup` 行，点击后可进入线索详情。
  - 房源排行的待跟进数也按 `lead.cardId` 归因，不再只看 action projection。
  - 测试补充旧线索场景，防止再次出现“有数无列表”。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - 关键文件 `git diff --check`：通过。
## 2026-06-23 19:30 房源客户看板线上修正

- 线上后端已准备部署：补 propertyBreakdown；待跟进动作用 LeadReminder 反填姓名/联系方式；旧动作名为空时按 CUSTOMER_ACTION_LABELS 兜底。
- 本地验证：backend/tests/test_app.py 98 passed；backend/app compileall 通过。
- 2026-06-23 19:40 线上已部署并复验：房源客户看板今日待跟进 1 可下钻到具体客户，高先生 / 预约看房 / 新世界广场B-938；后端容器 teambuy-backend-1 正常运行。

## 2026-06-23 19:50 阶段性交接归档

- 已新增 `docs/handoff-策划运营.md`。
- 文档覆盖：项目背景与目标、当前阶段目标、已完成功能、已修改/新增文件、当前代码状态、已知问题和风险、用户已确认的产品/技术决策、下一步建议执行顺序、新 Codex 会话第一条提示词。
- 新会话如果继续做运营策划，必须同时读取 `skills/operation-planning/SKILL.md` 和 `docs/handoff-策划运营.md`。

## 2026-06-24 一续：合集缓存、红点口径与资料库工具收口

- 用户最新反馈：
  - 合集页每次点击都显示正在读取，希望缓存到用户手机，降低服务器压力。
  - 房源资料库卡片红点在客户状态更新后仍存在。
  - 资料库工具区中服务方案、电子名片等入口和当前资料库场景不清晰。
  - 合集新建和分享层级偏深，希望优化。
- 本轮已做：
  - `miniprogram/pages/showcases/index.js` 增加 `userId + mode` 维度本地缓存，缓存 5 分钟；有缓存时先展示，过期再后台同步。
  - 合集首页增加 `latestPublished` 和“分享最近”，降低已发布合集再次转发的层级。
  - 合集方向卡可直接点击进入新建，减少用户必须点右上按钮的路径。
  - `miniprogram/utils/dashboard.js` 将 `hasHotCustomerSignal` 调整为只看未读和待跟进，历史客户动态不再触发红点。
  - `miniprogram/pages/library/index.wxml` 从“更多工具”移除电子名片和服务方案，只保留待认领、管理标签、我的笔记。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
- 待真机验证：
  - 第一次进入合集无缓存时仍会加载；第二次进入应优先显示缓存。
  - 处理客户状态后红点应消失，但客户动态和看客户入口仍保留。
  - 分享最近按钮在有已发布合集时出现，并能正常触发微信分享。

## 2026-06-24 二续：标签解释与客户功能两列设置

- 用户最新反馈：
  - 不清楚“管理标签”对普通用户有什么用、如何让用户知道并使用。
  - 房源资料详情页“客户功能”展开后过长，希望直接两列显示，避免 6 行拉长页面。
- 本轮已做：
  - 资料库入口“管理标签”改为“标签设置”。
  - 标签管理页增加业务说明：快速筛选、自动归类、生成合集；输入示例改为房源场景。
  - 资料详情页客户功能展开区改为两列卡片式开关，约 5-6 个功能压缩到 3 行左右。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/pages/tag-manage/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。
- 待真机验证：
  - 客户功能两列在手机端是否文字不挤、不溢出。
  - 标签设置页说明是否能让用户理解标签和筛选/合集的关系。

## 2026-06-24 三续：房源筛选增强与详情页分层

- 用户最新反馈：
  - 房源库筛选需要加强，增加价格、户型、地铁、电梯、状态等专门筛选；价格需要两个区间输入。
  - 房源详情页继续分层，先按 Codex 判断做一版。
  - 标签设置后如何使用仍不清晰，且标签按钮样式偏窄。
- 本轮已做：
  - 房源资料库在房源模式下新增“房源筛选”面板。
  - 支持最低价/最高价输入；提供不限、1300 以下、1300-1800、1800-2500、2500 以上快捷按钮。
  - 支持户型、地铁/近地铁、电梯/楼梯、状态筛选。
  - 房源详情页分层调整：顶部发客户动作后，先展示客户反馈，再展示房源卡，低频客户功能设置继续折叠和两列展示。
  - 标签管理页按钮加宽加高。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/pages/tag-manage/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。
- 待真机验证：
  - 房源筛选面板在手机端是否高度可接受。
  - 价格上下限筛选是否符合用户预期。
  - 详情页先客户反馈、再房源卡、再低频设置的顺序是否更顺。

## 2026-06-24 四续：房源筛选入口前置与合集条件筛选开放

- 用户最新反馈：
  - 资料库页面根本没看到“分类筛选”，无法理解房源筛选在哪里。
  - 希望合集里的“按条件筛选”也可以打开。
- 本轮已做：
  - 资料库中只要存在房源资料，就在“新增资料 / 更多工具”下方直接显示“房源筛选”面板。
  - 默认不影响普通资料；当用户设置价格、户型、地铁、电梯、状态后，列表会按房源条件收窄。
  - 合集编辑页启用“按条件筛选”，可按价格、户型、地铁、电梯/楼梯、状态自动筛出房源并加入合集。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。
- 待真机验证：
  - 资料库顶部是否能直接看到“房源筛选”面板。
  - 合集里点“按条件筛选”后，条件变化是否会自动更新候选和已加入房源。

## 2026-06-24 五续：房源工作台小闭环集中打磨

- 用户最新要求：
  - 将房源卡状态、筛选生成合集、详情页分层、客户反馈处理和合集效果复盘这些小优化一起完成，再统一验收打磨。
- 本轮已做：
  - `utils/dashboard.js`：房源卡新增 `propertyFollowStatus`，支持待处理、已跟进、有浏览、待分享。
  - `pages/note-actions`：待跟进线索增加已联系、暂不合适、已完成、重点跟进四个快捷处理按钮。
  - `pages/library`：房源筛选面板新增“用当前筛选生成合集”，通过本地缓存把条件传给合集编辑页。
  - `pages/showcase-edit`：启用“按条件筛选”，支持价格、户型、地铁、电梯/楼梯、状态，并自动加入符合条件的房源。
  - `pages/showcase-analytics`：新增“客户看房轨迹”，展示客户、动作、房源和时间，可下钻到房源客户反馈。
  - `pages/note-edit`：房源详情页增加“发客户 / 编辑资料”切换，默认发客户视角。
- 已验证：
  - `node --check` 覆盖本轮关键 JS：通过。
  - 本轮相关文件 `git diff --check`：通过。
- 待真机验证：
  - 房源卡状态是否准确、不过度打扰。
  - 客户反馈快捷处理后，待处理红点/待跟进数字是否刷新。
  - 当前筛选生成合集是否能复用条件并自动选中房源。
  - 合集效果页轨迹是否能看出客户浏览路径。
  - 房源详情“发客户 / 编辑资料”是否降低长页面压力。

## 2026-06-24 六续：标签设置使用链路补齐与系统校验

- 用户最新反馈：
  - 标签设置里添加标签后，不知道如何在每个房源上体现。
  - 要求系统再跑一轮校验。
- 本轮已做：
  - `utils/dashboard.js`：资料库房源卡标签来源从仅 `categoryIds` 扩展为 `categoryIds + visibilityConfig.userTags/tags`。
  - `pages/note-edit`：房源详情“编辑资料 -> 资料归类”新增“常用标签”，展示标签设置页创建的标签，可一键应用到当前房源。
  - 常用标签按钮样式加宽加高。
- 标签使用路径：
  - `资料库 -> 更多工具 -> 标签设置` 创建常用标签。
  - 进入某套房源详情，切到 `编辑资料`。
  - 在 `资料归类` 中点 `常用标签`，保存。
  - 返回资料库，该房源卡片会显示标签，并可在标签筛选里使用。
- 已验证：
  - 小程序关键脚本 `node --check`：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。

## 2026-06-24 七续：房源系统标签自动补齐

- 用户最新确认：
  - 系统标签应根据房源信息默认补齐，不让用户点选；后续按标签选房和生成合集依赖这些标签。
  - 第一批重要标签包括电梯/楼梯、租金区间、公寓、地铁口等。
- 本轮已做：
  - `pages/note-edit` 保存房源时自动生成 `systemTags`。
  - 自动标签覆盖：租金区间、户型/公寓、地铁口/地铁、电梯房/楼梯房、状态、待确认。
  - `systemTags` 合并进 `tags` 参与筛选；`userTags` 保留用户个人判断，不被覆盖。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。

## 2026-06-24 八续：房源工作台发客户前打磨

- 用户最新要求：
  - 先把客户视角预览、房源卡跟进闭环、合集发送前检查、筛选和系统标签继续补强一起做完。
- 本轮已做：
  - `pages/note-edit`：房源详情“发客户”页签新增客户视角预览卡和单套房源发布前检查。
  - `pages/note-edit`：房源字段新增面积、楼层/电梯、押付方式、入住时间。
  - `pages/note-edit`：系统标签补强面积区间、小户型、押一付一/押一付三、随时入住/本周可住。
  - `pages/library`：房源筛选新增面积、押付、入住条件；筛选状态更新后再刷新列表。
  - `pages/showcase-edit`：合集条件筛选同步新增面积、押付、入住；发布前新增检查项，存在缺项时弹窗确认。
  - `utils/dashboard`：房源卡状态新增下一步提示。
  - `utils/note-display`：合集已选行展示房源主信息，发布检查可判断租金完整度。
- 已验证：
  - `node --check` 覆盖资料详情、资料库、合集编辑、dashboard、note-display：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
- 待真机验证：
  - 房源详情客户视角预览是否比直接跳客户页更直观。
  - 单套房源检查项文案是否会造成过度焦虑。
  - 资料库/合集新增筛选条件是否好找、好用。
  - 合集发布前弹窗是否只提醒、不打断工作。

## 2026-06-24 九续：团购/商品工作台与单品详情页打磨

- 用户最新方向：
  - 房源工作台基本处理完后，按房源推进逻辑继续打磨团购/商品工作台。
  - 主入口名称确定为“团购/商品工作台”，不要退化成普通商品后台。
  - 单商品详情页要像房源详情一样分成“发群 / 编辑商品”，并加客户视角预览和发群前检查。
- 本轮已做：
  - 首页团购/商品模式改名并收口四指标：商品、待处理、今日接龙、访客。
  - 首页指标点击路径分别进入商品资料、待处理名单、今日接龙名单和访客看板。
  - 资料库商品卡增强价格/规格/取货/截止时间、接龙/下单信号、待处理状态和“处理接龙”入口。
  - 单商品详情页新增“发群 / 编辑商品”双页签。
  - “发群”页签新增客户视角预览、发群前检查和接龙/买家反馈。
  - “编辑商品”页签保留商品信息、图片/视频、SKU、取货与下单、资料归类。
  - 商品标题、电话、快捷字段、SKU、素材和下单开关变化后，会同步刷新发群预览和检查项。
- 已验证：
  - `node --check` 覆盖首页、资料库、订单页、工作台模式、dashboard、商品详情页：通过。
  - 相关页面 JSON 解析：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机验证：
  - 团购/商品首页四指标是否好理解、点击路径是否顺手。
  - 商品资料卡小屏是否拥挤，按钮是否居中。
  - 商品详情“发群 / 编辑商品”是否降低长页面压力。
  - 发群前检查是否提示准确、不过度焦虑。
  - 接龙/买家反馈入口是否符合团长处理名单的直觉。

## 2026-06-24 十续：商品合集发群前链路

- 用户最新指令：
  - 继续下一阶段开发。
  - 按房源工作台推进逻辑继续打磨团购/商品工作台。
- 本轮已做：
  - 首页团购/商品工作台“商品合集”快捷入口直接进入 `pages/showcase-edit/index?mode=groupbuy`。
  - 资料库商品卡“加入合集”进入商品合集编辑页。
  - 合集编辑页按当前分类生成场景文案：商品分类下使用发群、商品合集、商品条件、已选商品等表达。
  - 商品合集新增条件筛选：价格区间、取货方式、截止时间。
  - 商品合集发群前检查覆盖合集名称、已选商品、合集封面、联系入口、价格完整度、取货信息。
  - 发布按钮仍只发布；发布后通过“发到群里”转发，避免误导为自动发群。
- 已验证：
  - `node --check` 覆盖 `showcase-edit`、首页、资料库、`note-display`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机验证：
  - 商品合集入口路径是否顺手。
  - 商品条件筛选是否符合团长快速组团的直觉。
  - 商品合集页面是否仍有不该出现的房源文案。
  - 发群前检查是否准确、不过度打断。

## 2026-06-24 十一续：团购/商品工作台 P0 代码侧补齐

- 用户最新要求：
  - 把团购/商品工作台 P0 全部补上。
  - 涉及人工测试的内容后置。
- 本轮已做：
  - 后端 `/api/orders` 增加 `noteId` 过滤参数。
  - 小程序 `fetchOrders` 支持 `noteId`。
  - 卖家“接龙/买家名单”页用 `noteId` 做来源分组和过滤，展示名仍用商品名。
  - 单商品范围内清除筛选时不跳出当前商品。
  - 后端新增同名商品订单过滤测试，避免标题相同导致串单。
  - 商品合集价格识别收紧，避免规格数字误判为价格。
  - 已复核客户接龙/下单自动化覆盖：售罄 SKU、重复提交、团长可见、买家不可改状态、消息线程、订单状态更新。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - 后端订单相关文件 Python 编译：通过。
  - 小程序相关 JS `node --check`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 剩余后置：
  - 微信开发者工具/真机人工验收。
  - 体验版上传、真实微信群转发打开验证。
  - 页面视觉细节：按钮居中、文案是否拥挤、商品合集是否残留房源语境。

## 2026-06-24 十二续：团购/商品工作台 P1 代码侧补齐

- 用户最新要求：
  - P1 也直接全部开发，之后统一测试。
- 本轮已做：
  - 商品合集客户侧展示增强，商品卡展示规格、取货方式、取货地点、截止时间和“查看详情/接龙”提示。
  - 后端发布快照同步输出商品 meta，确保正式分享页和预览一致。
  - 资料库新增商品筛选：价格、取货方式、截止时间、有接龙、有访客、待补价格、待补取货。
  - 资料库“用当前筛选生成商品合集”会把商品筛选条件带入合集编辑页。
  - 商品保存自动生成系统标签：自提/配送/快递、今日/本周截止、有 SKU、已售罄、待补价格、待补取货。
  - 接龙/买家名单新增“今日新增”切换。
  - 商品资料支持“复用成新商品”，只复制内容，不复制订单/接龙/统计/消息。
  - 后端新增 `/api/notes/{note_id}/duplicate`。
- 已验证：
  - 后端完整测试 98 passed。
  - 后端相关文件编译通过。
  - 小程序相关 JS 检查通过。
  - 页面 JSON 解析通过。
  - 本轮关键文件 `git diff --check` 通过。
- 剩余后置：
  - 真机看商品筛选面板高度、商品合集客户卡片是否拥挤。
  - 真机验证“复用成新商品”后的字段和图片是否符合预期。
  - 真实数据下看“今日新增”切换是否清楚。

## 2026-06-24 十三续：工作台模式资料隔离修正

- 用户最新反馈：
  - 工作台之间已经可以切换，但资料信息没有随工作台切换隔离；房源仍会在团购/商品工作台里显示。
- 本轮已做：
  - `miniprogram/pages/library/index.js`：资料库 Tab 直接进入时读取当前工作台模式，房源模式默认只看房源，团购/商品模式默认只看商品；统计、分类、标签也按过滤后的资料计算。
  - `miniprogram/pages/visits/index.js`：底部工作台页按当前模式过滤资料后再生成概览和反馈列表。
  - `backend/app/services/app_service.py`：团购看板按团购/商品资料过滤笔记、相关合集、客户动作和线索，避免后端返回房源排行。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/visits/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
- 未验证：
  - 当前本机系统 Python 没有安装 `pytest`，`python3 -m pytest backend/tests/test_app.py -q` 无法运行。
  - 需要微信开发者工具/真机确认：首页切到团购/商品 -> 点底部“资料”和“工作台” -> 不再显示房源。

## 2026-06-24 十四续：16:14 企业微信团购笔记未进工作台

- 用户最新反馈：
  - 16:14 左右通过企业微信发送团购微信笔记，但没有进入团购/商品工作台。
  - 房源筛选标签只应在房源工作台显示，不应出现在其他工作台。
- 排查结论：
  - 线上 Nginx 记录显示 2026-06-24 16:13:51 收到 `/api/wecom/archive/callback`。
  - 数据库中 `wecom_archive_messages` 新增 seq=37，`import_batches` 新增 `import_6a739cb1df`。
  - 对应资料 `note_ec9fc09893` 已生成并归属 `user_25ec00a0f0`，类型是 `groupbuy_product / 团购`，标题“白凤乌鸡蛋”。
  - 问题原因：`/api/cards` 返回的 card 没有携带来源 note 的类型，前端按标题关键词判断时，“白凤乌鸡蛋”没有团购关键词，导致被团购工作台过滤掉。
- 本轮已做：
  - `backend/app/services/app_service.py`：`list_cards` 返回来源 note 的 `cardType/systemCategory/visibilityConfig`。
  - `miniprogram/pages/library/index.wxml`：房源筛选面板改为只在 `showPropertyFilters` 时显示；商品筛选面板只在 `showGroupbuyFilters` 时显示。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - 本地模拟：补出 `cardType=groupbuy_product` 后，“白凤乌鸡蛋”会被 `isGroupbuyCard` 识别。
- 未验证/待办：
  - 本机系统 Python 缺少 `pytest`，完整后端测试未运行。
  - 当前修正尚未部署到生产；部署后端并上传/预览小程序后，需要真机验证该商品进入团购/商品工作台。

## 2026-06-24 十五续：后端已临时部署到生产

- 用户最新要求：
  - 先部署后端，便于测试前端。
- 本轮已执行：
  - 检查生产磁盘和 Docker 状态：根分区约 60%，空间足够；后端和 Postgres 容器正常。
  - 备份生产 `/home/ubuntu/teamBuy/backend/app` 到 `/home/ubuntu/teamBuy_deploy_backups/backend_app_20260624_162457.tar.gz`。
  - 同步本地 `backend/app` 到生产服务器。
  - 尝试重建后端镜像，但 `docker compose build backend` 卡在 `apt-get update`；未中断旧服务。
  - 停止卡住的构建后，将生产服务器 `backend/app` 复制进运行中的 `teambuy-backend-1:/app/app` 并重启容器。
- 已验证：
  - `https://teambuy.lifelove.top/health` 返回 200，数据库正常。
  - 生产 `/api/cards?ownerUserId=user_25ec00a0f0` 已返回“白凤乌鸡蛋”的 `cardType=groupbuy_product`、`systemCategory=团购`、`sourceNoteId=note_ec9fc09893`。
  - 生产团购看板接口 `/api/dashboard/business?...&mode=groupbuy` 返回 200。
- 注意：
  - 当前后端修复已在线上容器生效，但镜像本身未重建成功；如果后续容器被强制重建，需要重新构建或再次确认代码已进入镜像。
  - 前端筛选面板逻辑仍需要微信开发者工具预览/上传小程序后才会生效。

## 2026-06-24 十六续：团购样式堆叠与封面不显示

- 用户最新反馈：
  - 团购资料页真机上按钮和内容堆叠，商品卡片“更多”按钮横向溢出。
  - 编辑展示页“已选商品顺序”区域封面、正文和排序/隐藏/删除按钮挤在一起。
  - 设置封面后，微信转发可显示，但资料页团购卡片仍显示占位。
- 本轮已做：
  - `miniprogram/pages/library/index.wxss`：团购商品卡片动作区改为两列布局；有客户/接龙时主操作独占一行，分享和更多下一行平分；按钮补齐 flex 居中、最小宽度和不换行规则。
  - `miniprogram/pages/showcase-edit/index.wxss`：已选商品行改为上方封面+正文、下方四个操作按钮，底部固定操作按钮补齐 flex 居中和不换行。
  - `backend/app/services/app_service.py`：`list_cards` 在 card 无封面时兜底返回来源 note 的封面或第一张图片。
- 已部署：
  - 已同步 `backend/app` 到生产服务器，并复制进运行中的 `teambuy-backend-1` 容器后重启。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/showcase-edit/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - 生产健康接口正常。
  - 生产 `/api/cards?ownerUserId=user_25ec00a0f0` 中“白凤乌鸡蛋”已返回 `coverUrl=https://teambuy.lifelove.top/media/media_44020dedaf-manual_asset_0c176188a5.webp`。
- 待用户验证：
  - 在微信开发者工具重新预览/上传小程序后，真机检查团购资料列表和展示页编辑页是否还堆叠。
  - 刷新资料页确认团购商品卡片显示封面，不再显示“资料”占位。

## 2026-06-24 十七续：资料卡片按钮背景过长

- 用户最新反馈：
  - 真机截图中房源和团购资料卡片底部按钮背景仍然过长，没有必要占满整行。
- 本轮已做：
  - `miniprogram/pages/library/index.wxss`：资料卡片操作区从等分网格改为可换行 flex 胶囊布局。
  - “看客 / 分享 / 更多 / 处理接龙”等按钮改为按内容宽度显示，只保留最小可点宽度，不再拉伸成整条背景。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `git diff --check -- miniprogram/pages/library/index.wxss`：通过。
- 待用户验证：
  - 微信开发者工具重新预览/上传后，真机确认房源和团购资料卡片底部按钮不再横向过长。

## 2026-06-24 十八续：客户资料提交文案改为留言

- 用户最新反馈：
  - 原客户资料提交术语很多人看不懂，希望统一改成“留言”。
  - 同时询问底部第四个“工作台”与首页、我的里切换工作台的区别和意义。
- 本轮已做：
  - 小程序可见文案统一改为“留言”，覆盖资料详情、客户动作页、客户看板、工作台配置、电子名片/服务方案、分享图和演示数据。
  - 后端演示文案同步改为“留言”。
  - 内部字段名、action key 和统计结构保持不变。
- 已验证：
  - `rg -n "留资" miniprogram backend/app backend/mock`：无结果。
  - `node -c` 覆盖 `dashboard.js`、`workspace-mode.js`、`note-edit`、`note-actions`、`business-dashboard`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 产品判断：
  - 首页里的工作台切换更像“选择当前业务场景 + 快速开始”。
  - 我的里的工作台切换更像“账号默认设置”。
  - 底部第四个 Tab 当前实际是经营反馈页，展示访客、客户动态、高意向和待处理事项；它不应主要承担切换工作台的心智。
  - 后续更建议把第四个 Tab 命名和定位收敛为“看板”或“反馈”，工作台切换只保留为顶部筛选或入口辅助。

## 2026-06-24 十九续：客户看板命名与卡片创建时间

- 用户最新反馈：
  - 第四个 Tab 可以叫“客户看板”。
  - 希望每个资料库卡片和合集卡片下面都显示创建时间。
- 本轮已做：
  - `miniprogram/app.json`：第四个 Tab 文案改为“客户看板”。
  - `miniprogram/pages/visits/index.wxml`：页面标题改为“客户看板”。
  - 首页和我的页跳转入口改为“去客户看板”。
  - `miniprogram/utils/dashboard.js`：资料卡片增加 `createdText`。
  - `miniprogram/pages/library/index.wxml/.wxss`：资料卡片下方展示创建时间。
  - `miniprogram/pages/showcases/index.js/.wxml/.wxss`：合集卡片下方展示创建时间。
- 已验证：
  - `node -c miniprogram/utils/dashboard.js`：通过。
  - `node -c miniprogram/pages/showcases/index.js`：通过。
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `miniprogram/app.json` JSON 解析：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 微信开发者工具重新预览/上传后，确认底部 Tab 显示“客户看板”。
  - 真机确认资料库卡片、合集卡片创建时间位置不挤压按钮。

## 2026-06-24 二十续：团购/商品 P1 体验收口

- 用户最新问题：
  - P0 企业微信团购笔记识别的“高置信”逻辑是什么，是否还是只看标题。
  - P1 中客户看板团购化、商品复用体验、空态引导可以优先处理。
- 识别逻辑确认：
  - 后端 `skill_router_service.py` 高置信团购识别基于全文和结构化字段，不是只看标题。
  - 高置信条件包含：团购分数 `score >= 5`、团购分数高于房源分数、命中商品信号、命中价格或解析器 hint、命中取货/规格/截止/接龙等交付信号，并且字段数量足够。
  - 不满足高置信时会降为普通资料或给人工确认建议，不直接强行进团购。
- 本轮已做：
  - `miniprogram/pages/business-dashboard/`：团购模式下 Tab 改为“待处理 / 买家/访客 / 商品效果 / 发群效果”，首屏和空态切到接龙、下单、买家、商品点击语境。
  - `miniprogram/pages/library/index.js`：商品复用前增加确认，说明不会复制旧接龙、订单、访客和统计。
  - `miniprogram/pages/library/index.wxml/.wxss`：团购资料空态增加“新建商品 / 商品合集”入口。
  - `miniprogram/pages/showcases/index.js/.wxml/.wxss`：团购合集空态增加“先建一个商品”入口。
  - `miniprogram/pages/home/index.wxml`：团购模式空态提示新建商品、企业微信导入和发群后接龙反馈。
- 已验证：
  - `node -c miniprogram/pages/business-dashboard/index.js`：通过。
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/showcases/index.js`：通过。
  - `node -c miniprogram/pages/home/index.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 真机检查团购客户看板文案是否更像商品/接龙场景。
  - 复用商品弹窗文案是否足够清楚。
  - 团购资料库和商品合集空态入口是否顺手。

## 2026-06-24 二十一续：电子名片/服务工作台一期优化启动

- 用户最新要求：
  - 开始做电子名片/服务工作台，并基于房源和团购工作台经验看首页如何优化。
- 当前理解：
  - 这个工作台的核心不是“资料整理”，而是让服务型用户先做名片、服务方案，再看咨询客户和方案效果。
  - 首页已经有服务工作台视觉，但数据范围和看板语境还需要独立。
- 本轮已做：
  - `miniprogram/pages/home/index.js`：服务工作台首页统计只按 `business_card/service_offer` 计算。
  - `miniprogram/pages/home/index.js`：服务模式“看资料”和统计卡跳转资料库时写入 `service_workspace` 入口过滤。
  - `miniprogram/pages/home/index.wxml`：服务模式空态提示先做名片、再补服务介绍页；咨询反馈空态改为名片/方案发出后回流。
  - `miniprogram/pages/library/index.js/.wxml`：资料库支持服务工作台入口过滤，只看名片/服务方案，并展示对应说明。
  - `miniprogram/pages/business-dashboard/index.js/.wxml`：服务模式客户看板 Tab 改为“待咨询 / 访客 / 方案效果 / 案例合集”，首屏与效果页文案切到咨询、方案和案例合集语境。
- 已验证：
  - `node -c miniprogram/pages/home/index.js`：通过。
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/business-dashboard/index.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 下一步建议：
  - 继续打磨服务工作台 P0/P1：名片详情页、服务方案详情页、客户视角预览、发布前检查、咨询/预约回流。
  - 真机检查首页服务模式的统计、快捷入口、资料库隔离和客户看板文案。

## 2026-06-24 二十二续：电子名片/服务工作台 P0 闭环补强

- 用户最新要求：
  - “可以。先做 p0。”
- 本轮已做：
  - `miniprogram/pages/home/index.js`：服务工作台资源数改为电子名片 + 服务方案；咨询数只取真实客户互动，不再用服务方案数量兜底。
  - `backend/app/services/app_service.py`：客户看板 `mode=service` 只聚合电子名片和服务方案；合集、点击事件、客户动作和线索同步按服务资料范围收窄。
  - `backend/tests/test_app.py`：新增服务看板隔离用例，验证名片/服务方案/团购商品混合时，服务看板不统计团购订单和团购资料。
  - `miniprogram/pages/business-card-studio/`：新增发给客户前检查；未保存或有未保存改动时隐藏分享菜单；保存后分享路径指向客户页；底部主动作改为“保存并预览”。
  - `miniprogram/pages/service-offer-studio/`：新增服务方案发前检查；未保存或有未保存改动时隐藏分享菜单；保存后分享路径指向客户页；底部主动作改为“保存并预览”。
  - `miniprogram/pages/business-dashboard/index.js`：服务模式下待咨询、访客、方案效果等兜底文案不再出现“预约看房 / 看房源 / 房源资料”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 未跑通：
  - `python3 -m pytest backend/tests/test_app.py::test_service_business_dashboard_only_counts_service_customer_data ...` 未执行成功，原因是当前系统 Python 缺少 `pytest`。
- 待用户验证：
  - 微信开发者工具重新预览/上传体验版后，真机确认名片/方案编辑页未保存时不显示分享、保存并预览能打开客户页。
  - 客户页留言/预约提交后，服务客户看板只显示服务咨询，不混入房源和团购。
- 下一步建议：
  - 如果 P0 真机通过，再做 P1：服务案例合集空态/模板、名片与服务方案复用、服务工作台首页最近咨询卡片更精细化。

## 2026-06-24 二十三续：电子名片/服务工作台 P1 收口与后端部署

- 用户最新要求：
  - “p1 也一起做了，然后在部署后端，我测试前端。”
- 本轮已做：
  - `miniprogram/pages/library/index.js/.wxml`：服务资料卡新增复用入口；复用电子名片进入名片工作台，复用服务方案进入服务方案工作台；复用说明明确不复制访客、留言、预约和统计。
  - `miniprogram/utils/resource-navigation.js`：电子名片和服务方案点击编辑时进入对应专属工作台，不再回通用编辑页。
  - `miniprogram/pages/library/index.wxml`：服务资料库空态增加“做名片 / 做方案”。
  - `miniprogram/pages/showcases/index.js/.wxml/.wxss`：案例合集空态增加“先做名片 / 先做方案”。
  - `miniprogram/pages/business-dashboard/index.wxml`：服务客户看板空态继续服务化，覆盖咨询动态、服务分享来源、咨询客户明细和方案效果。
- 已验证：
  - `node --check` 覆盖首页、资料库、合集、名片工作台、服务方案工作台、客户看板和资源跳转工具：通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_service_business_dashboard_only_counts_service_customer_data backend/tests/test_app.py::test_property_business_dashboard_only_counts_property_customer_data -q`：2 passed。
  - 本轮关键文件 `git diff --check`：通过。
- 后端部署结果：
  - 部署前备份：`/home/ubuntu/teamBuy/backups/backend-code-before-service-p1-20260624233925.tgz`。
  - 已同步本地后端代码到服务器，未覆盖 `.env`、`backend/secrets/`、媒体目录或运行态 mock 数据。
  - 已执行 `docker compose build backend && docker compose up -d backend`。
  - `teambuy-backend-1` 当前运行正常。
  - `http://127.0.0.1:8002/health`：200 OK。
  - `https://teambuy.lifelove.top/health`：200 OK。
  - 容器内确认存在 `_is_service_note` 和 `mode == "service"` 看板过滤逻辑。
  - 部署后服务器根分区约 64%，剩余约 21G。
- 用户测试前注意：
  - 后端已生效。
  - 小程序前端仍需要在微信开发者工具重新预览或上传体验版，才能看到 P1 前端改动。
- 建议测试顺序：
  - 服务工作台首页：确认统计、空态和入口。
  - 资料库服务视图：确认编辑进入专属工作台、复用生成新名片/方案、加入案例合集。
  - 名片/方案工作台：确认保存并预览、未保存不分享、保存后可分享。
  - 客户页：提交留言/预约。
  - 咨询看板：确认只出现服务咨询，不混房源/团购。

## 2026-06-25 零点续：电子名片/服务方案资料库和模板一致性修复

- 用户最新反馈：
  - 点击/转发“方案”和“电子名片”后，回到工作台资料库看不到对应资料。
  - 服务方案“展示模板”和“确认详情页效果”未编辑也显示不同内容，其他服务模板也类似。
- 根因确认：
  - 名片/方案保存为 `user_notes`，资料库读 `/api/cards`，旧接口未合并没有 backing card 的服务 note。
  - 服务方案模板小预览读 `template.preview` 示例内容，确认效果读表单默认内容；默认表单非空导致模板 defaults 未覆盖。
- 本轮已做：
  - `backend/app/services/app_service.py`：`list_cards` 合并 note-only 的 `business_card/service_offer` 资料，返回 `note_card_{noteId}`、`sourceNoteId`、`cardType`、`categoryName`、统计和客户摘要。
  - `backend/tests/test_app.py`：新增 `test_service_note_resources_are_listed_as_library_cards`，覆盖服务方案保存后能进入资料库列表。
  - `miniprogram/utils/resource-navigation.js`：资料库查看服务资料打开客户预览页，编辑才进入专属工作台。
  - `miniprogram/pages/library/index.js`：note-only 服务资料删除改为删除来源 note。
  - `miniprogram/pages/service-offer-studio/index.js`：模板 defaults 在未手动改写字段时生效；小预览的服务内容和统计项改为使用实际表单内容。
  - `miniprogram/pages/business-card-studio/index.js`：名片模板 defaults 同步采用同样规则。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/utils/resource-navigation.js`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：100 passed。
- 待继续：
  - 后端已部署，线上 `/api/cards` 已包含服务 note-only 资料合并逻辑。
  - 用户需重新上传/预览小程序体验版，才能验证前端模板一致性、资料库查看/编辑/删除路径。
- 部署结果：
  - 部署前备份：`/home/ubuntu/teamBuy/backups/backend-code-before-service-library-template-202606250026.tgz`。
  - 已同步后端代码，未覆盖生产 `.env`、`backend/secrets/`、媒体目录和运行态 mock 数据。
  - 已执行 `docker compose build backend && docker compose up -d backend`。
  - `teambuy-backend-1` 已重建并启动。
  - 内网 `http://127.0.0.1:8002/health`：200 OK。
  - 公网 `https://teambuy.lifelove.top/health`：200 OK。
  - 容器内确认存在 `_service_note_card_rows`。
  - 部署前服务器根分区约 65%，剩余约 21G。

## 2026-06-25 续：电子名片/服务方案确认页点选编辑

- 用户最新要求：
  - 参考 Codex 浏览器网页上的备注修改方式，在模板/效果页上点击内容进行修改，保存后替换成用户自己的内容。
- 本轮方案：
  - 先做“半所见即所得”：不推翻当前三步流程，在确认效果页增加点选编辑。
  - 点选编辑只更新当前页面表单和预览，最终仍通过“保存并预览”写入后端。
- 本轮已做：
  - `miniprogram/pages/service-offer-studio/index.js/.wxml/.wxss`：
    - 确认效果页支持点击服务名称、一句话卖点、适合人群、服务内容、流程/报价/案例、联系方式、预约说明。
    - 点击后底部弹出编辑面板，保存修改后即时刷新预览，并标记为未保存。
  - `miniprogram/pages/business-card-studio/index.js/.wxml/.wxss`：
    - 名片卡片预览和详情预览支持点击姓名、身份、公司/门店、一句话介绍、服务介绍、服务范围、联系方式。
    - 逻辑同样只回写当前表单，最终由“保存并预览”持久化。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - WXML view 标签配对：服务方案 258/258；电子名片 166/166。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 微信开发者工具重新预览/上传体验版。
  - 服务方案：点击标题、人群、服务内容、流程/报价/案例、联系方式，确认底部编辑面板和即时刷新。
  - 电子名片：在卡片预览和详情预览分别点击内容修改，确认预览刷新。
  - 修改后未保存时分享仍不可用；点击“保存并预览”后客户页展示修改后的内容。

## 2026-06-25 续二：电子名片浅色模板编辑角标修复

- 用户最新反馈：
  - 电子名片第二个模板背景偏浅，点选编辑角标使用白色导致不清晰。
- 本轮已做：
  - `miniprogram/pages/business-card-studio/index.wxss`：为 `store_sales_card` 模板单独设置点选编辑边框、背景和角标颜色，浅色背景下改为绿色角标。
- 已验证：
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 重新上传体验版后，确认第二个名片模板卡片预览和详情预览的“编辑”角标可读。

## 2026-06-25 续三：服务工作台 P1 统一收口

- 用户最新要求：
  - 服务工作台整体测试无大问题，把剩余 P1 统一补上。
- 本轮已做：
  - 服务方案工作台：
    - 确认页点封面、头像占位、案例图可直接替换图片。
    - 联系方式缺失时显示“补电话/补微信/补邮箱/补网址”。
    - 底部电话/微信按钮文案可点选编辑，并写入 `structuredData.primaryAction/secondaryAction`。
    - 切模板时若已有未保存改动，弹出“保留我的内容 / 套用模板文案”。
  - 电子名片工作台：
    - 卡片预览/详情预览点头像和二维码可直接替换。
    - 联系方式缺失时可直接补齐。
    - 切模板时同样提供“保留我的内容 / 套用模板文案”。
  - 客户页：
    - 服务方案电话/微信咨询按钮使用编辑器里保存的按钮文案。
    - 服务方案留言/预约表单占位文案切成咨询问题、预算、期望服务方式语境。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/note-preview/index.js`：通过。
  - WXML view 标签配对：服务方案 263/263；电子名片 172/172；客户页 176/176。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 重新上传体验版后，验证点图替换、补联系方式、切模板选择、按钮文案保存后客户页展示。

## 2026-06-25 续四：团购/商品首页访客改订单

- 用户最新要求：
  - 团购/商品工作台首页“今日待处理”第四项不再放访客，改成订单；普通商品更应该展示订单详情。
- 本轮已做：
  - 首页团购/商品四格改为“商品 / 待处理 / 今日接龙 / 订单”。
  - “订单”统计使用订单/接龙总数，点击进入 `/pages/orders/index?role=seller`。
  - “待处理”继续进入待处理订单，“今日接龙”继续进入今日过滤订单。
  - 商品资料卡主按钮：有接龙显示“处理接龙”，只有普通下单显示“处理订单”，只有访客不再显示处理按钮。
  - 团购资料库筛选从“有访客”改为“有订单”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - `node --check miniprogram/utils/workspace-mode.js`：通过。
  - WXML view 标签配对：首页 72/72；资料库 104/104。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 重新上传体验版后，检查团购/商品首页第四格、点击跳转、资料库商品卡按钮文案和筛选项。

## 2026-06-25 续五：日常资料台反馈命名、真实待整理与普通资料整理

- 用户最新要求：
  - 继续改首页和底部 Tab 的“客户看板”命名。
  - 做待整理任务真实化。
  - 做普通资料的一键整理和资料包增强。
- 本轮已做：
  - 底部 Tab `pages/visits` 改名为“反馈”，反馈页标题同步改为“反馈”。
  - 首页反馈面板按模式切文案：日常资料台为“分享反馈 / 看反馈”，团购为买家动态，服务为咨询动态，房源仍保留客户看板。
  - 首页日常资料台“待整理任务”改为真实任务卡：待认领、待整理、待识别图片、未完成资料包。
  - `pages/notes` 支持首页任务跳转筛选：`sourceType=ocr`、`migrationPending=1`、`plain=1`、`systemCategory`。
  - 普通笔记详情增加“一键整理”“加入资料包”“添加能力”三类入口；添加能力仍保留为后续插件方向。
  - 资料包编辑页支持 `noteId` 直达预选，普通资料包不再套房源合集文案和租金校验。
  - 后端普通资料 `organize` 增加轻量 `organizeResult`，用于资料包、分享摘要、标签归类。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/notes/index.js`
  - `node --check miniprogram/pages/visits/index.js`
  - `node --check miniprogram/pages/note-edit/index.js`
  - `node --check miniprogram/pages/showcase-edit/index.js`
  - `miniprogram/app.json` JSON 解析通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：100 passed。
  - `git diff --check`：通过。
- 未做：
  - 按用户要求未部署、未上传小程序体验版。
- 待用户验证：
  - 重新预览后检查：首页待整理任务数字和跳转是否符合实际数据；普通笔记详情按钮是否不挤、不误导；普通资料加入资料包后是否只预选当前资料。

## 2026-06-25 续六：资料库和反馈页按当前工作台隔离

- 用户最新反馈：
  - 3:02 左右点击资料库，日常资料台疑似仍看到其他工作台资料。
  - “反馈”Tab 内仍显示四个工作台切换，日常用户看到房源/服务会突兀。
- 本轮已做：
  - 资料库新增 `notes_workspace` 范围：当前工作台是日常资料台时，默认排除房源、团购、名片/服务方案，只显示普通资料、链接、图片、笔记等日常资料。
  - 反馈页数据过滤补齐：日常只看日常资料，房源只看房源，团购只看商品，服务只看名片/服务方案。
  - 反馈页移除四工作台切换 Tab，避免底部一级页自动暴露所有业务场景。
  - 日常反馈页统计图标/筛选项改为中性表达，“进入/分享记录”改去资料包，不再跳业务看板。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/visits/index.js`：通过。
  - `git diff --check`：通过。
- 待用户验证：
  - 重新预览后在日常资料台点“资料”，确认看不到房源/团购/服务资料。
  - 点“反馈”，确认没有四个工作台切换，列表只显示当前工作台资料反馈。

## 2026-06-25 续七：资料库专题筛选

- 用户最新要求：
  - 先做资料库专题筛选。
- 本轮已做：
  - 资料库加载时同步读取用户专题。
  - 专题列表按当前工作台范围内的资料统计，只展示真实有关联资料的专题。
  - 资料库新增“专题筛选”胶囊，可与分类、标签、关键词组合筛选。
  - 关键词搜索纳入专题名，用户可直接搜专题相关资料。
  - 文档确认：专题是内部组织和检索维度，资料包是外部分享集合。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `git diff --check -- miniprogram/pages/library/index.js miniprogram/pages/library/index.wxml miniprogram/pages/library/index.wxss`：通过。
- 未做：
  - 本轮未部署、未上传小程序体验版。
- 待用户验证：
  - 在任一工作台下进入资料库，确认有专题的资料会出现“专题筛选”。
  - 点击专题后，列表只剩该专题资料；切回“全部”恢复当前工作台资料范围。

## 2026-06-25 续八：资料工作台 P0 收口

- 用户最新要求：
  - 确认“专题=内部整理检索，资料包=外部分享集合”后，要求把剩余 P0 全部开发。
- 本轮已做：
  - 资料库选中专题后出现“建资料包”入口。
  - 入口文案明确：专题用于内部整理和检索；资料包用于整理成可分享页面。
  - 资料包编辑页支持 `topicId/topicName`，从专题进入时只读取该专题资料并默认加入。
  - 资料包编辑页展示“来自专题”说明，继续强化专题/资料包心智。
  - 普通资料卡点“合集”时直接进入资料包编辑页并预选当前资料。
  - 普通资料包空封面提示改为资料语境，不再残留房源图提示。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - WXML view 标签配对：资料库 110/110；资料包编辑 86/86。
  - 本轮关键文件 `git diff --check`：通过。
- 未做：
  - 本轮未部署、未上传小程序体验版。
- 待用户验证：
  - 资料库选专题后点“建资料包”，确认资料包里只自动加入该专题资料。
  - 资料库普通资料卡点“合集”，确认资料包里只预选当前资料。
  - 普通资料包页面不再出现房源化文案。

## 2026-06-25 续九：专题 / 合集命名统一

- 用户最新要求：
  - 不再创造过多名词。内部统一叫“专题”；外部统一叫“合集”。
  - 四个工作台外部集合命名固定为：日常合集、房源合集、商品合集、案例合集。
- 本轮已做：
  - 小程序前端去掉“资料包 / 团购合集 / 专辑”等旧口径。
  - 资料库专题筛选后的入口改为“建合集”，说明“专题用于内部整理和检索，合集用于分享”。
  - 普通资料详情按钮改为“加入合集”。
  - 日常工作台、首页任务、反馈页、业务看板旧“资料包”改为“日常合集”。
  - 合集新建页按场景显示：日常合集、房源合集、商品合集、案例合集。
- 已验证：
  - 前端 `rg "资料包|团购合集|服务资料包|普通资料包|建资料包|加入资料包|资料包效果|专辑"`：无结果。
  - `node --check`：showcase-edit、showcases、library、home、workspace-mode 通过。
  - WXML view 标签配对通过。
  - 本轮关键文件 `git diff --check`：通过。
- 未做：
  - 未部署、未上传小程序体验版。

## 2026-06-25 续十：资料工作台 P1 统一收口

- 用户最新要求：
  - 把剩余 P1 全部做一下，并统一测试。
- 本轮已做：
  - 专题页：
    - 增加专题/合集心智说明。
    - 支持从专题直接建日常合集。
    - 支持删除专题，删除只移除资料上的专题关联，不删除资料。
  - 日常合集编辑页：
    - 日常/服务场景不再沿用房源推荐包、租金、户型等文案。
    - 日常“按条件筛选”改为后续“按专题/标签生成”能力，不误展示房源筛选面板。
  - 普通资料详情：
    - “添加能力”改为插件占位面板，留言、咨询、接龙均作为后续插件能力展示。
    - 不再一键打开运营配置，保留“先补摘要、标签和专题”的轻量整理入口。
  - 标签设置页：
    - 文案从房源示例改为通用资料、专题、合集语境。
  - 后端：
    - 普通资料一键整理生成选项改为“日常合集 / 分享摘要 / 标签归类”。
    - 新增删除专题接口，并回归删除后资料专题关联清理。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：101 passed。
  - `python3 -m compileall -q backend/app`：通过。
  - 小程序关键 JS `node --check`：通过。
  - 小程序 JSON 递归解析：通过。
  - WXML view 标签配对通过。
  - 旧词扫描无结果。
  - 本轮关键文件 `git diff --check`：通过。
- 后端部署：
  - 生产后端已部署删除专题接口。
  - 部署前备份目录：`/home/ubuntu/teamBuy/backups/backend-topic-delete-20260625-043627`。
  - 标准镜像构建长时间无输出，已改用容器热补丁方式复制 `app_service.py`、`routes_notes.py` 并重启 `teambuy-backend-1`。
  - 公网 `/health` 200；线上创建后删除探针专题验证通过，探针专题已清理。
- 小程序上传：
  - 本机已确认微信开发者工具 CLI 存在，但用户明确小程序体验版自行上传，本轮不再代传。
- 下一步真机回归：
  - 新增普通笔记 -> 资料库可见。
  - 资料库专题筛选。
  - 专题筛选后建日常合集。
  - 普通资料加入合集。
  - 日常合集发布/分享。
  - 反馈页数据按当前工作台隔离正常。

## 2026-06-25 续十一：专题管理入口与工作台入口出口检查

- 用户最新要求：
  - 补充完专题管理入口。
  - 检查四个工作台每一项的逻辑、入口和出口。
  - 没问题后开始讨论专门营销细节。
- 本轮已做：
  - `pages/library`：
    - “更多工具”新增“专题管理”，可直达专题页。
    - 专题筛选标题右侧新增“管理专题”。
    - “新增资料”按工作台进入对应新建路径：日常、房源、商品、服务不再混用。
    - 卡片“更多”菜单区分普通资料与房源资料，日常资料不再显示“编辑房源”。
  - `pages/home`：
    - 首页最近成果、反馈列表改为按当前工作台过滤，不再用全量资料导致四个工作台看起来相同。
    - 团购/商品“商品合集”入口改为进入合集列表，与日常、房源、服务保持一致。
  - `pages/showcases`：
    - 合集列表按当前工作台过滤：日常合集、房源合集、商品合集、案例合集分开展示。
    - 缓存读取路径也做过滤，避免旧缓存继续串台。
  - `pages/showcase-edit`：
    - 日常合集候选资料改为真实“日常资料”范围，不再用“全部”把房源、商品、服务资料带进去。
    - 分类统计对“资料/房源/商品/服务”等场景词做去重，避免计数虚高。
- 四工作台检查结论：
  - 日常资料台：入口和出口围绕资料入库、专题、日常合集、分享反馈。
  - 房源工作台：入口和出口围绕房源创建、房源资料、房源合集、客户看板。
  - 团购/商品工作台：入口和出口围绕商品创建、商品资料、商品合集、订单/接龙。
  - 服务工作台：入口和出口围绕名片、服务方案、案例合集、咨询反馈。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - `node --check miniprogram/pages/showcase-edit/index.js`
  - `node --check miniprogram/pages/visits/index.js`
  - `node --check miniprogram/utils/workspace-mode.js`
  - 小程序 JSON 递归解析通过。
  - 旧词扫描无结果。
  - 本轮关键文件 `git diff --check` 通过。
- 待用户操作：
  - 本轮是小程序前端改动，需用户上传体验版后真机查看。
  - 真机重点看：资料库“更多工具 -> 专题管理”、专题筛选右侧“管理专题”、四个工作台首页/资料/合集/反馈是否不再串台。

## 2026-06-25 续十二：第四期工作台优化阶段性交接归档

- 用户最新要求：
  - 进入“专门营销细节”前，先做一次阶段性交接归档。
  - 生成 `docs/第四期工作台优化.md`，适合直接给新 Codex 窗口继续执行。
- 本轮已做：
  - 新增 `docs/第四期工作台优化.md`。
  - 文档覆盖项目背景与目标、当前阶段目标、已完成功能、已修改/新增文件、当前代码状态、已知问题和风险、已确认产品/技术决策、下一步建议执行顺序、新会话第一条提示词。
  - 明确区分已完成、已部署、未上传体验版、仍需真机确认和下一阶段营销建议。
- 已验证：
  - `git diff --check -- docs/第四期工作台优化.md`：通过。
  - 文档尾部提示词代码块完整。
- 下一步：
  - 不建议继续大规模开发工作台功能。
  - 建议开始讨论第一批用户、首个打穿场景、产品一句话定位、销售路径和演示脚本。

## 2026-06-25 续十三：房源合集展示排列与微信助手入口

- 用户最新反馈：
  - 所有模板和展示页都应支持一列/双列，默认一列。
  - 按钮样式问题反复出现，应把按钮基线抽到主样式文件。
  - 手机点击“微信助手”只显示复制，想知道为什么不能自动添加微信客服。
- 本轮已做：
  - `pages/showcase-edit` 增加“一列 / 双列”展示排列选择，默认一列，保存到 `displayConfig.layoutMode`。
  - `pages/showcase-view` 四类模板按 `layoutMode` 渲染，一列默认，双列作为用户主动选择。
  - `miniprogram/app.wxss` 补原生 `button` 全局 reset 和常用按钮/标签居中基线。
  - 后端新增 `/api/wecom/customer-service-config`，复用现有整理助手企业微信客服配置，按 `WECOM_CORP_ID / WECOM_OPEN_KFID` 生成小程序打开客服所需参数。
  - `pages/property-same` 主按钮改为“打开微信助手”，优先请求后端配置并调用 `wx.openCustomerServiceChat`，失败或后端未部署时复制整理指令兜底。
  - `miniprogram/config/customer-service.js` 只保留离线兜底，不放密钥，也不是主配置来源。
- 重要说明：
  - 小程序不能凭微信号直接自动添加客服，必须走微信官方企业微信客服能力。
  - 当前项目已有归纳整理用企业微信客服，主路径应复用后端 env，不需要前端另配一套。
- 待验证：
  - 用户重新上传体验版后，检查展示页默认一列是否稳定，切双列是否不挤压按钮。
  - 后端部署新接口后验证“打开微信助手”是否直达归纳整理助手的企业微信客服会话。

## 2026-06-25 续十四：后端承接企业微信助手与自有小程序卡

- 本轮已做：
  - 后端新增 `/api/wecom/customer-service-config`，复用现有归纳整理助手 `WECOM_CORP_ID / WECOM_OPEN_KFID`，不要求前端另配客服。
  - 企业微信 `weapp` 小程序卡解析补充 `noteId/showcaseId/sourceNoteId/id` 识别。
  - 自有小程序房源卡/房源合集进入企业微信后，后端会回查公开结构，写入生成草稿的 `visibilityConfig.structuredData.internalMiniapp`。
  - 公开结构过滤私密上游/房东/渠道/电话/微信/rawText 等字段，避免 B 中介生成同款时继承 A 的私密联系人。
  - 后端展示页配置保留 `layoutMode=list/grid`。
- 已验证：
  - 后端全量测试 104 passed。
  - 后端编译通过。
- 已部署生产：
  - 备份目录：`/home/ubuntu/teamBuy/backups/backend-property-agent-20260625-073636`。
  - 已同步并热补丁后端文件到 `teambuy-backend-1`，容器已重启。
  - `https://teambuy.lifelove.top/health` 返回 200。
  - `https://teambuy.lifelove.top/api/wecom/customer-service-config` 返回 `configured=true`。
  - 容器内后端编译通过。
- 仍需用户侧：
  - 小程序体验版更新后，“打开微信助手”优先直达归纳整理助手；失败才复制兜底。

## 2026-06-25 续十五：生成同款克隆接口与媒体资产 hash 去重底座

- 用户最新要求：
  - 优先补齐两个基础底座：
    - 完整后端克隆接口：A 的公开房源卡/合集一键生成 B 名下正式房源卡/合集，并替换联系方式。
    - 媒体资产 hash 去重：图片 WebP hash、视频 hash、MediaAsset 引用表落库。
- 本轮已做：
  - 后端新增 `MediaAsset` / `MediaAssetRef` 模型。
  - 后端新增 `media_assets`、`media_asset_refs` 两张表及索引/唯一约束。
  - `process_and_store_media` 改为：
    - 计算原始 hash。
    - 图片转 WebP / 视频转 MP4。
    - 计算处理后 hash。
    - 命中已有资产时复用 URL，只新增引用。
  - OCR 图片上传也接入 hash 去重，仍保留真实本地落文件行为。
  - 新增 `POST /api/notes/property-same/clone`：
    - `sourceType=note`：生成 B 名下新房源卡。
    - `sourceType=showcase`：逐条复制公开房源为 B 名下新房源卡，再生成 B 名下新合集。
  - 克隆隐私边界：
    - 公开字段过滤 `contact/phone/wechat/landlord/upstream/channel/rawText` 等敏感字段。
    - B 的电话/微信替换进公开联系方式。
    - B 的上游联系人写入 `visibilityConfig.privateData.upstreamContact`，默认取 A 的公开联系方式或身份。
    - 不继承 A 的 `privateData`。
- 已验证：
  - 本地后端全量测试：144 passed。
  - 生产 `/health` 200。
  - 生产新接口已命中业务逻辑：
    - 缺用户返回 `用户不存在`。
    - 真实用户 + 缺源返回 `公开房源卡不存在`。
  - 生产 PostgreSQL 已存在 `media_assets`、`media_asset_refs`。
- 已部署生产：
  - 备份目录：`/home/ubuntu/teamBuy/backups/backend-clone-media-20260625-075259`。
  - 注意：本项目生产后端热补丁必须同时同步宿主机文件和 `docker cp` 到 `teambuy-backend-1:/app/app/...`；本轮已完成并重启容器。
- 下一步建议：
  - 小程序 `pages/property-same` 从“复制给企业微信助手”升级为优先调用 `POST /api/notes/property-same/clone`。（2026-06-25 续十六已完成）
  - 调用成功后根据返回 `type=note/showcase` 跳转到新房源卡或新合集编辑/预览页。（2026-06-25 续十六已完成）
  - 保留企业微信助手作为接口失败或用户想半自动整理时的兜底。
  - 后续单独做历史媒体 hash 回填任务。

## 2026-06-25 续十六：生成同款页接入后端克隆接口

- 用户最新要求：
  - 做小程序前端接入：`pages/property-same` 优先直接调用后端克隆接口，成功后跳到 B 的新房源卡/新合集；企业微信助手保留失败兜底。
- 本轮已做：
  - `miniprogram/services/api.js` 新增 `clonePropertySame(payload)`。
  - `miniprogram/pages/property-same/index.js`：
    - 新增 `handleGenerateSame`。
    - 有来源 ID 时调用 `POST /api/notes/property-same/clone`。
    - 缺来源或接口失败时自动走原有 `handleOpenAssistant`，复制整理指令并打开企业微信助手。
    - 成功生成 `note` 后跳 `/pages/note-edit/index?id=...`。
    - 成功生成 `showcase` 后跳 `/pages/showcase-edit/index?id=...&mode=property`。
  - `miniprogram/pages/property-same/index.wxml`：
    - 主按钮改为“生成同款”。
    - 次按钮保留“打开助手”。
    - 增加失败兜底提示。
  - `miniprogram/pages/property-same/index.wxss`：
    - 增加兜底提示样式和主按钮 disabled 状态。
- 已验证：
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - 小程序 JSON 递归解析：通过。
  - 关键文件 `git diff --check`：通过。
- 待用户操作：
  - 需要在微信开发者工具上传体验版后真机测试。
  - 重点路径：房源卡公开页 -> 生成同款 -> 新房源卡编辑页；房源合集公开页 -> 生成同款 -> 新合集编辑页。

## 2026-06-26 续十七：生成同款首次登录与预览落点优化

- 用户最新反馈：
  - 生成同款已经能一键生成，问题不大。
  - 首次点击会进入登录页，旧登录页视觉粗糙，键盘顶起页面。
  - 生成成功后进入操作/编辑页，观感不像“一键生成”，还像需要继续点选操作。
- 本轮已做：
  - `pages/property-same` 未登录跳转登录页时带 `returnUrl`，保留原 `sourceType/sourceId/sourceTitle/publisherName/upstreamContact`。
  - 登录成功后回到原生成同款页面，并通过 `autoGenerate=1` 自动继续生成。
  - 生成成功后不再跳编辑页：
    - 房源卡跳 `/pages/note-preview/index?id=...`。
    - 房源合集跳 `/pages/showcase-view/index?id=...`。
  - 前端克隆合集时传 `publishShowcase=true`，保证生成后可以直接打开客户可见合集。
  - 登录页重做：
    - 删除昵称输入框，避免键盘首屏干扰。
    - 强化“房源工作台 / 一键生成你的房源卡”首屏。
    - 增加房源卡预览感模块和三步价值点。
    - 主按钮为“微信一键登录”，本地 mock 登录仅本地后端显示。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - 小程序 JSON 递归解析：通过。
- 待真机：
  - 未登录用户从房源卡/合集点“生成同款” -> 登录 -> 自动回跳并生成 -> 直接进入新预览页。

## 2026-06-26 续十八：登录页文案图片与 iPad 底部按钮修复

- 用户最新反馈：
  - 登录页 `openid 隔离` 改为“微信官方隔离”。
  - 登录页一键登录区域要有真实房源图片，使用用户给的第二张图片。
  - iPad 点击房源详情、合集详情后，底部按钮仍有变形/裁切。
  - 继续思考登录页是否应该获取微信昵称头像。
  - 登录说明“不展示给其他中介”容易让中介产生误会，文案需要更短。
- 本轮已做：
  - 新增压缩图片 `miniprogram/static/workspace/login-room.jpg`，约 93KB。
  - `pages/login` 预览卡使用真实房源图，隔离标签改为“微信官方隔离”。
  - `pages/login` 登录区改为“登录后保存到你的账号 / 用于生成同款、查看线索，下次打开还能继续管理。”，减少隐私说明带来的反向提醒。
  - `pages/note-preview`：
    - 生成同款卡片增加最大宽度居中。
    - iPad 宽屏下分享浮层跟随内容区域右侧。
    - 窄屏下生成同款卡片自动上下布局。
  - `pages/showcase-view`：
    - 底部联系按钮最大宽度居中。
    - 固定分享按钮最大宽度居中。
    - 生成同款卡片最大宽度居中，窄屏自动上下布局。
- 登录策略当前建议：
  - 当下继续使用“微信一键登录”，只确认身份和归属，降低首次生成同款阻力。
  - 不在登录第一步强制头像昵称；头像昵称更适合放到“我的资料/名片/发布资料前补全”。
  - 原因：登录用户不一定是中介，也可能是租客/客户；强制填头像昵称会影响他们查看房源。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - 小程序 JSON 递归解析：通过。

## 2026-06-26 续十九：合集模板发布态与朋友圈长页修复

- 用户最新反馈：
  - 换了合集模板后，转发给客户仍看到上一个模板。
  - 四个模板需要再检查，当前“朋友圈长页”在 iPad 上仍然变形。
- 本轮已做：
  - `pages/showcase-edit` 新增 `unpublishedChanges`：
    - 已发布合集修改模板、排列、标题、封面、联系方式、筛选和已选资料后，标记为新版未发布。
    - 顶部和底部分享按钮在新版未发布时改成“发布新版”。
    - `onShareAppMessage` 遇到新版未发布时提示“先发布新版再分享”，避免误发旧版客户页。
  - `pages/showcase-view`：
    - 四个模板主体统一 `max-width: 720rpx` 居中。
    - “朋友圈长页”首屏、故事卡、列表行、服务条和标签使用可收缩列，降低 iPad 宽屏/分栏下横向撑开风险。
- 已验证：
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - `showcase-edit/showcase-view` JSON 解析通过。
  - `showcase-edit/showcase-view` WXML 标签配对通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机：
  - 已发布合集 -> 切换模板 -> 底部应显示“发布新版”，发布后再分享客户应看到新模板。
  - 逐个切换 `精选橱窗 / 朋友圈长页 / 清单目录 / 品牌名片`，在 iPad 和手机确认主体不再横向拉满或按钮裁切。

## 2026-06-26 续二十：品牌名片、微信优先和发布排序

- 用户最新反馈：
  - 第四个“品牌名片”模板仍然变形。
  - 房源合集不应电话优先，微信联系更重要，几个模板都需要改。
  - 重新保存并发布新版后，应当算最近更新，合集列表应靠前。
- 本轮已做：
  - `pages/showcase-view`：
    - 精选橱窗、清单目录、品牌名片的联系按钮改为微信优先。
    - 统计位只要有微信就显示“微信咨询”，不再优先显示“电话咨询”。
    - 品牌名片模板头部去掉负 margin，列表卡片加固定列、两行标题、单行摘要、两列标签和无图兜底。
  - `pages/showcase-edit`：
    - 发布新版成功后清理 `teambuy_showcases_{userId}_{mode}` 本地缓存。
  - `pages/showcases`：
    - 缓存和接口数据都按 `updatedAt/createdAt` 倒序展示，配合后端发布时刷新 `updatedAt`，让新版合集靠前。
- 已验证：
  - `node --check miniprogram/pages/showcase-edit/index.js`
  - `node --check miniprogram/pages/showcase-view/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - 三个页面 JSON 解析和 WXML 标签配对通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机：
  - 品牌名片模板在 iPad 上确认头部、统计卡、联系区、房源列表、固定分享按钮不再裁切。
  - 有微信号的合集确认各模板先展示“微信联系”；没有微信号时才只展示电话。
  - 发布新版后返回合集列表，确认该合集靠前。

## 2026-06-26 续二十一：品牌名片房源卡结构修复

- 用户最新反馈：
  - 第四模板按钮仍然变形，缩略图也变形。
  - 房源布局整体缺少验收感，不能给中介“很酷、想用”的冲动。
- 本轮已做：
  - `pages/showcase-view` 品牌名片模板的房源卡新增 `brand-case-body`，让封面和内容区成为明确两列结构。
  - 封面图/无图兜底固定 `188rpx` 正方形，不再被标题、标签或价格高度挤压。
  - 内容区内部固定层级：标题两行、摘要一行、标签两列、价格底部。
  - `.sticky-share` 改为 flex 居中，房源模板分享按钮文案缩短为“发给客户”，避免按钮在 iPad 分栏下裁切。
- 已验证：
  - `node --check miniprogram/pages/showcase-view/index.js`：通过。
  - `showcase-view` JSON 解析和 WXML 标签配对通过。
  - `showcase-view` 关键文件 `git diff --check`：通过。
- 仍需真机确认：
  - 第四模板在 iPad 上的封面比例、右侧内容、标签和底部分享按钮是否稳定。
  - 如果还有“酷感不足”，下一步应做模板视觉重设计，而不是继续只修错位。

## 2026-06-26 续二十二：登录页小地图导航卖点合并

- 用户最新反馈：
  - 登录页“生成同款后”区域可加小地图，但应和房源预览卡合并一行。
  - 删除“图片已复用”，只保留“近地铁 / 可带看”。
- 本轮已做：
  - `pages/login` 预览卡改为三列布局：房源图、房源信息、小地图导航。
  - 小地图用 WXSS 画道路、定位点和“导航”胶囊，不增加图片资源。
  - 能力点从 3 个带数字卡改为 4 个短标签：房源卡、房源合集、查看客户线索、位置导航。
  - 更新 `docs/png/login-map-navigation-mockup.svg` 为合并版本。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `login` JSON 解析和 WXML 标签配对通过。
  - 登录页和效果图 `git diff --check`：通过。
- 待真机：
  - 上传体验版后确认小地图在普通手机/iPad 分栏下不挤压房源标题和微信联系文案。
## 2026-06-26 本轮交接：房东长文本批量拆房源

- 用户确认：房东群发信息里 `禁宠` 属于公开标签，可以展示给客户；但上游电话、微信、中介费、密码锁、红包、朋友圈照片视频和带看协作限制必须只给中介自己看。
- 后端已新增：
  - `POST /api/notes/property-batch/parse`
  - `POST /api/notes/property-batch/create`
- 解析规则已支持一条房东长文本拆多套房源；无图房源也能生成 `property_listing`，后续可补图。
- 生成的房源卡公开结构包含：标题、小区/楼室、单元/房间、户型、租金、公开标签和公开卖点。
- 私密结构写入 `visibilityConfig.privateData/privateTags`，包含上游电话、微信、中介费、密码锁、红包、朋友圈照片视频和带看限制；客户公开页不得展示。
- 小程序 `pages/resource-create` 已接入：粘贴多套房源时先出现“房源批量识别”确认卡，可勾选生成多张房源卡，也可“按普通资料保存”。
- 已补测试 `test_property_batch_parse_and_create_keeps_upstream_private`，覆盖 `禁宠` 公开和上游信息私密隔离。
- 本地已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_batch_parse_and_create_keeps_upstream_private or manual_note_draft_creates_property_from_pasted_text"` 通过。
  - `.venv312/bin/python -m py_compile backend/app/services/app_service.py backend/app/schemas/notes.py backend/app/api/routes_notes.py` 通过。
  - `node --check miniprogram/services/api.js` 和 `node --check miniprogram/pages/resource-create/index.js` 通过。

## 2026-06-26 本轮交接：房源助手入口改为企业微信「联系我」

- 背景：
  - 用户确认微信客服会话不能置顶，不是目标路径；目标是添加企业微信成员，形成可置顶的长期会话。
- 本轮已改：
  - `miniprogram/app.json` 新增插件：
    - provider：`wx104a1a20c3f81ec2`
    - alias：`contactPlugin`
  - `miniprogram/pages/home/index.json` 新增组件：
    - `cell: plugin://contactPlugin/cell`
  - `miniprogram/pages/home/index.js` 新增配置 ID：
    - `propertyContactPluginId = 3bf7435f594f0d6ca83a9a185ea201e5`
  - 首页 banner 房源助手入口改为官方按钮模式 `<cell plugid="{{propertyContactPluginId}}" styleType="{{2}}" blockStyle="button" />`。
  - 常用入口里的 `openAssistant` 不再调用 `wx.openCustomerServiceChat`，改为滚动到顶部并提示点官方联系入口。
  - 真机反馈按钮被裁切后，banner 助手卡已改为上下结构，官方插件按钮独占一行；常用入口按钮区域也加高居中。
- 已验证：
  - `node --check miniprogram/pages/home/index.js` 通过。
  - `miniprogram/app.json`、`miniprogram/pages/home/index.json` JSON 解析通过。
- 用户/真机待做：
  - 在小程序后台 `设置 -> 第三方服务 -> 添加插件` 搜索并添加插件 ID `wx104a1a20c3f81ec2`。
  - 上传体验版后确认点击首页插件入口进入企业微信成员添加流程，而不是微信客服会话。
  - 如果开发者工具提示插件不可用，先确认小程序后台已添加插件 `wx104a1a20c3f81ec2`，再确认 `cell` 组件路径和插件版本 `1.4.7`。

## 2026-06-26 本轮交接：外部联系人自动回消息测试

- 用户已在企业微信后台添加生产服务器可信 IP：`81.70.84.35`。
- 已用 2026-06-26 08:40 左右个人微信发给企业微信成员的真实会话记录定位到外部联系人 `external_userid`。
- 测试结果：
  - `kf/send_msg` 微信客服发送文本：返回 `48002 api forbidden`，成员好友会话不能复用微信客服发送接口。
  - `media/upload` 上传测试图片：成功返回 `media_id`，说明服务器 IP 可信配置已生效。
  - `externalcontact/add_msg_template` 文本、图片、小程序卡片：均返回 `48002 api forbidden`。
  - `externalcontact/get` 获取客户详情：返回 `48002 api forbidden`。
- 当前结论：
  - 用户已在企业微信后台补充客户联系 API 权限后，`externalcontact/get` 成功，文本发送任务创建成功。
  - `media/uploadimg` 成功并可用于 `externalcontact/add_msg_template` 的图片附件，图片发送任务创建成功。
  - 小程序卡片目前失败：普通临时素材 `media/upload` 返回的 `media_id` 会被 `add_msg_template` 判为 `40007 invalid media_id`；无封面卡片返回 `41006 media_id missing`；永久素材 `material/add_material` 当前返回 `48002 api forbidden`。
- 新结论：
  - 外部联系人客户联系链路已能创建文本和图片发送任务。
  - 小程序卡片还需要补齐可用于 `pic_media_id` 的素材权限或换用可产生合法卡片封面的上传方式。

## 2026-06-26 本轮交接：房源助手 external_userid 绑定

- 当前方案：
  - 首次使用房源助手时，企业微信/会话存档消息先生成“新导入资料”。
  - 用户打开小程序并登录，用“新导入资料”页点击“认领并绑定”。
  - 后端在 `wecom_identity_bindings` 保存 `externalUserId -> ownerUserId/ownerOpenid`。
  - 之后同一个企业微信外部联系人发来的资料，会自动进入该小程序账号，不再走待认领。
- 已有后端链路：
  - `AppService.claim_import` 会调用 `_save_wecom_identity_binding`。
  - `_resolve_owner_user_id_for_external` 会按 `wecom_external_user + external_userid` 查绑定，并优先用 `ownerOpenid` 找用户。
  - 会话存档处理和 mock sync 已有测试覆盖自动归属。
- 本轮小程序优化：
  - `miniprogram/pages/imports/index.wxml` 文案改为“第一次认领会绑定房源助手，后续发来的资料自动进你的账号”。
  - 认领按钮改为“认领并绑定”。
  - 未登录时点击认领跳转登录页。
  - 认领成功提示“已绑定房源助手”后进入编辑页。
  - `miniprogram/pages/imports/index.wxss` 的模板按钮和认领按钮改为 flex 居中。
- 用户真机流程：
  - 个人微信先添加企业微信成员“高士腾/房源助手”。
  - 给这个企微发一条房源文本或图片。
  - 等后台会话存档处理生成导入后，打开小程序首页进入“资料/待认领/新导入资料”。
  - 点击该条资料的“认领并绑定”。
  - 之后再发给同一个企微成员的房源，会自动归属到当前小程序账号。
- 验证：
  - `node --check miniprogram/pages/imports/index.js` 通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py` 通过。
  - 当前本机缺少 `pytest`，未能运行完整目标 pytest；后续可在有依赖的 `.venv312` 或服务器测试环境补跑。

## 2026-06-26 本轮交接：点击小程序链接自动绑定

- 用户反馈：
  - 竞品体验是：用户把链接/视频发给企业微信，企业微信处理完成后自动回小程序链接，用户点击即可进入下载/结果页；不是让用户去待认领列表找。
- 本轮新增主链路：
  - 后端可调用 `AppService.build_import_claim_link(import_id)` 生成：
    - `token`
    - `pagePath = pages/import-claim/index?token=...`
    - `title`
  - 小程序新增 `pages/import-claim/index`。
  - 用户点击企业微信发回的小程序链接后：
    - 未登录：跳登录页。
    - 登录后：自动调用 `POST /api/imports/claim-by-token`。
    - 后端：认领导入、写入 `external_userid -> ownerUserId/ownerOpenid` 绑定。
    - 小程序：进入资料编辑页。
- 安全规则：
  - token 使用 HMAC 签名并带 7 天过期时间。
  - 已被其他账号认领的导入不能被再次抢绑。
  - 待认领仍保留为兜底，不作为第一推荐用户路径。
- 仍待接入：
  - 企业微信处理完成后的“回小程序卡片/链接”发送动作还需要接到通知发送服务上。
  - 发送内容应使用 `pagePath`，而不是让用户自己进入“新导入资料”。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_claim_import_and_publish_flow backend/tests/test_app.py::test_claim_import_by_token_binds_external_user backend/tests/test_app.py::test_wecom_archive_process_auto_assigns_bound_external_user backend/tests/test_app.py::test_wecom_identity_mapping_resolves_owner_by_openid`：4 passed。
  - `node --check miniprogram/pages/import-claim/index.js`、`node --check miniprogram/pages/imports/index.js`、`node --check miniprogram/services/api.js`：通过。

## 2026-06-26 本轮交接：会话存档完成通知补齐与发送阻塞

- 用户 10:19 左右给企业微信成员发送微信笔记后，没有收到小程序回传链接。
- 线上排查确认：
  - 会话存档已收到 `note` 消息。
  - 已生成导入批次 `import_0437e0a14e`。
  - 已生成资料 `note_de667374ee`。
  - 当时没有生成 `ImportNotification`，所以不会发送完成提示。
- 本轮已补：
  - archive 处理成功后自动创建完成通知。
  - 完成通知的结果入口使用 `pages/import-claim/index?token=...`，用户点击后可登录、认领、绑定并进入结果。
  - archive worker 支持处理后立即调用通知发送器。
  - 新增后台补发接口 `POST /api/wecom/notifications/send-pending`。
  - 已热更新生产后端。
- 生产验证结果：
  - 对 10:19 历史导入手动创建通知后，调用补发接口可进入发送流程。
  - 企业微信返回 `48002 api forbidden`，错误内容为 `send customer service text failed`。
- 当前结论：
  - 资料生成和通知生成已经补齐。
  - 主动回消息仍阻塞在发送通道：当前代码使用微信客服 `kf/send_msg`，不能给企业微信成员外部联系人会话直接发消息。
- 下一步建议：
  - 不再把 `kf/send_msg` 当成企业微信成员好友私聊通道。
  - 继续验证客户联系可用触达方式：欢迎语、客户群发、群发任务、客户群触达，或改为小程序内消息中心/首页待认领作为稳定反馈。
  - 如果要继续做“整理完成自动私聊回卡片”，必须先找到企业微信允许服务端对该外部联系人发送的正式接口，并确认文本、图片、小程序卡片三类能力。

## 2026-06-26 本轮交接：微信客服 API 权限已通，仍需用户从客服入口发消息

- 用户补齐微信客服「可调用接口的应用」后，生产验证结果：
  - `kf/account/list` 成功。
  - 返回可用客服账号 `wkCSe7EwAAtY1p65p2bXVj3gTbWWzcKg`。
  - 生产 `backend/.env` 已更新 `WECOM_OPEN_KFID` 为该值。
  - 后端容器已 force recreate 以刷新环境变量，公网 `/api/wecom/customer-service-config` 返回新客服号。
  - `POST /api/wecom/real-sync` 成功，不再 `48002`。
- 重要踩坑：
  - force recreate 后旧镜像丢失了之前容器内热补丁，本轮已重新 `docker cp` 同步 `routes_wecom.py`、`routes_imports.py`、`dependencies.py`、`schemas/imports.py`、`services/app_service.py`、`services/wecom_archive_worker.py`、`services/wecom_client.py`、`models/domain.py`、`services/repository.py`、`core/schema.sql`、`services/import_notification_service.py`、`schemas/notes.py`、`api/routes_notes.py` 等文件，后端已恢复。
  - 后续应尽快做正式镜像构建，避免再次因重建容器丢热补丁。
- 16:38 用户测试：
  - 用户说 16:38 发了一段文字房源。
  - `real-sync` 没有拉到新客服消息。
  - 日志显示收到的是 `/api/wecom/archive/callback`。
  - archive 表最新消息 `wecom_archive_msg_d463844610`，`msgType=text`，已生成 `note_23816dbffa`。
  - 对该外部联系人调用 `kf/send_msg` 返回 `95018 session status invalid`。
- 当前结论：
  - 微信客服官方链路权限已经打通。
  - 16:38 这条不是从微信客服入口发的，而是发给了企业微信成员好友，所以进入会话存档。
  - 下一次必须从小程序的 `wx.openCustomerServiceChat` 入口打开微信客服会话后发送房源，才能测试 `sync_msg -> 整理 -> kf/send_msg 回小程序卡片`。

## 2026-06-26 本轮交接：首页入口改为微信客服主链路

- 用户确认产品逻辑：
  - 前端交互看起来像“发给企业微信助手”。
  - 底层收发消息必须走微信客服 API。
  - 会话里再引导添加企业微信好友，形成长期联系。
- 小程序已改：
  - 首页 banner 主卡标题从“添加房源助手”改为“发房源给助手”。
  - 主按钮“立即发送房源”调用 `openPropertyAssistant`，也就是 `wx.openCustomerServiceChat`。
  - banner 内「联系我」插件降级为二级入口，文案“长期联系可再添加企业微信”。
  - 常用入口的“发房源给助手”点击卡片本身直接打开微信客服。
  - 常用入口内保留“加企业微信”插件按钮，作为转化入口。
- 验证：
  - `node --check miniprogram/pages/home/index.js` 通过。
  - `node --check miniprogram/utils/workspace-mode.js` 通过。
  - JSON 解析和 WXML 标签计数通过。
- 下一步：
  - 用户上传体验版。
  - 真机点“立即发送房源”，确认打开的是微信客服会话。
  - 在该会话发房源后，再触发 `POST /api/wecom/real-sync` 验证 `kf/sync_msg` 是否收到。

## 2026-06-27 本轮交接：成交雷达真机数据与手机按钮遮挡

- 用户反馈：
  - 6:44 左右用两个微信测试客户访问，但客户看板没有看到雷达生成。
  - 手机端房源详情页“好友/朋友圈”浮层遮挡“生成同款”区域，质疑全局样式为何没有一次解决。
- 线上只读排查：
  - 生产服务运行在 `teambuy-backend-1`，PostgreSQL 正常。
  - 生产数据库已记录北京时间 6:45-6:46 的事件：
    - `showcase_3f537b64ed` 被 `user_5fd8d56c26` 打开。
    - 同一用户点击了多套房源，包括 `note_d00ca2b3bd`、`note_730305fd2e`、`note_ea2607e9d8`。
  - 生产 `/api/dashboard/business?ownerUserId=user_25ec00a0f0&requesterUserId=user_25ec00a0f0&mode=property` 仍返回旧版 `data.summary/recentVisitors/topNotes/visitorProfiles` 结构。
  - 生产接口没有返回 `opportunitySummary`、`opportunityAlerts`、`radarProfiles`、`contentInsights`、`revivalAlerts`。
- 结论：
  - 这次真机测试数据进后台了，但生产后端未部署本地新增的成交雷达规则，因此没有生成雷达提醒。
  - 线上事件也没有 `durationSeconds/maxScrollPercent/focusSections`，说明新版小程序行为上报尚未在真机体验版生效。
- 本轮本地修复：
  - `miniprogram/pages/note-preview/index.wxss`：手机端默认把分享按钮改成行内，不再固定悬浮遮挡业务卡片。
  - `property-same-card` 手机默认单列，大屏再变双列；`生成同款`按钮继续 flex 居中。
- 已验证：
  - `node --check miniprogram/pages/note-preview/index.js` 通过。
  - `git diff --check -- miniprogram/pages/note-preview/index.wxss` 通过。
- 下一步建议：
  - 先正式部署后端成交雷达代码。
  - 再上传小程序体验版。
  - 真机用非 owner 微信打开推荐包，停留、滚动、查看价格/联系方式并触发一次咨询/预约，回 owner 客户看板验证 `客户雷达提醒 + 复制话术 + 资料优化建议`。

## 2026-06-27 本轮交接：首页与客户雷达 UI 收敛

- 用户反馈：
  - 首页做了多轮后功能都有，但视觉不好，客户相关展示位置太多，用户不知道看哪个。
  - 希望先按效果图方向重构首页和雷达页。
- 新增文档：
  - `docs/stage2-docs/22-home-radar-ui-consolidation.md`
- 本轮已改：
  - `miniprogram/pages/home/index`：
    - 首页改为“今日成交机会”优先。
    - 保留“把房源发给助手”工作入口。
    - 新增“客户雷达”统一入口。
    - 移除旧首页分散的客户动态/反馈模块。
  - `miniprogram/pages/visits/index`：
    - 从旧“反馈”页重构为“客户雷达”页。
    - 三个 tab：待跟进、访客、资料优化。
    - 待跟进卡展示意向、原因、标签、建议动作、复制话术、标记已联系。
    - 资料优化页展示建议，并预留生成对比建议。
  - `miniprogram/app.json`：
    - 底部 tab 文案从“反馈”改为“雷达”。
- 重要产品决策：
  - 客户相关主入口以后统一叫“雷达”。
  - 首页不再堆多个客户入口，只展示今日机会摘要和雷达入口。
  - 旧客户看板 `pages/business-dashboard` 继续作为明细/兼容页，不再作为首页主心智。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/pages/visits/index.js && node --check miniprogram/pages/business-dashboard/index.js` 通过。
  - `miniprogram/app.json`、首页/雷达页 JSON 解析通过。
  - 首页、雷达页、客户看板 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 微信开发者工具重新编译后检查首页首屏是否不再拥挤。
  - 检查底部 tab 是否显示“雷达”。
  - 手机和 iPad 检查首页机会卡、雷达入口、雷达客户卡按钮是否居中且不挤压。

## 2026-06-27 本轮交接：其他工作台释放与 UI 文案切换

- 用户判断：
  - 产品对外先做房源，但销售场景很多，用户的客户未来也可能成为用户。
  - 需要把服务、团购、日常资料三个工作台逻辑梳理清楚，符合基座 + 插件架构。
- 本轮已改：
  - `miniprogram/utils/workspace-mode.js`
    - 取消 `PROPERTY_GROWTH_MODE_ENABLED` 强制锁房源。
    - 默认工作台仍为 `property`。
  - `miniprogram/pages/home/index.js/wxml`
    - 新增 `HOME_UI_BY_MODE`。
    - 首页 banner、主动作、空状态和最热指标按 `property/service/groupbuy/notes` 切换。
    - banner 增加轻量工作台切换 chip。
    - 服务/团购也尝试拉取对应 `business-dashboard`。
  - `miniprogram/pages/visits/index.js/wxml`
    - 雷达页按工作台切换资料名词、空状态和对比建议。
    - 房源显示房源对比合集；团购显示商品对比；服务显示服务方案对比；日常显示资料合集。
- 当前代码可继续优化点：
  - `isPropertyCard/isGroupbuyCard/isServiceCard` 在首页、雷达、资料库等页面重复，建议抽到统一 `workspace-mode` 或 `note-display` 工具。
  - 首页与雷达页已有工作台文案配置，但 `business-dashboard` 明细页仍有较多房源文案，需要继续统一。
  - 服务/团购的雷达规则可复用后端机会引擎，但后续应补场景化标签：服务看案例/报价/保障，团购看规格/价格/取货/接龙。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/pages/visits/index.js && node --check miniprogram/utils/workspace-mode.js` 通过。
  - 首页和雷达页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：首页白屏排查

- 用户反馈：
  - 首页打不开、白屏，怀疑是否有些请求走服务器、有些走本地后端。
- 排查结果：
  - 当前小程序接口基址统一为 `https://teambuy.lifelove.top`，未发现首页链路混入 `localhost/127.0.0.1`。
  - 线上接口可达，不存在用户返回 404，说明不是网关不可达。
  - 首页 JS 可模拟加载；主要风险在 WXML 复杂表达式和旧本地 mock 登录态。
- 本轮已改：
  - `miniprogram/pages/home/index.wxml`：移除 `||`、三元和相等判断表达式。
  - `miniprogram/pages/home/index.js`：新增 `modeSwitchLabel`，机会卡和统计卡 class 由 JS 预处理。
  - `miniprogram/utils/workspace-mode.js`：工作台选项增加 `activeClass`。
  - 首页未登录跳转登录页时携带 `returnUrl`。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/utils/workspace-mode.js && node --check miniprogram/pages/login/index.js && node --check miniprogram/app.js` 通过。
  - 首页、登录页、雷达页 WXML 标签检查通过。
  - 首页 WXML 表达式检查通过。
- 真机建议：
  - 微信开发者工具先清缓存并重新编译。
  - 如果之前用本地 mock 登录，线上模式会清掉该登录态，需要重新微信登录。
  - 若仍白屏，优先看开发者工具 Console 第一条报错。

## 2026-06-27 本轮交接：商机/合作信息能力

- 用户输入：
  - 提供真实群消息样例：保险出单、海参工厂批发、城市群管理员招募、进口清关代理。
- 产品判断：
  - 这些不是普通服务方案，而是“商机/合作信息”。
  - 暂不新增第五个工作台，归入服务工作台。
- 本轮已改：
  - `docs/stage2-docs/23-business-opportunity-service-card.md`：新增开发文档。
  - `miniprogram/utils/sales-page-templates.js`：新增 `service_business_opportunity` 模板。
  - `miniprogram/pages/service-offer-studio/index.js/wxss`：商机模板指标和主题色。
  - `miniprogram/pages/home/index.js`：服务模式入口改为“做服务/商机页”，并可跳转商机模板。
  - `miniprogram/utils/workspace-mode.js`：服务工作台新增“商机合作”快捷入口。
  - `backend/app/services/skill_router_service.py`：新增商机/合作规则识别，高置信自动生成 `service_offer + service_business_opportunity`。
- 样例验证：
  - 保险出单 -> `service_offer / service_business_opportunity`。
  - 海参工厂批发 -> `service_offer / service_business_opportunity`。
  - 城市群管理员招募 -> `service_offer / service_business_opportunity`。
  - 进口清关代理 -> `service_offer / service_business_opportunity`。
- 已验证：
  - 前端相关 JS `node --check` 通过。
  - 后端 `skill_router_service.py` 编译通过。
  - 服务方案页和首页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 服务工作台点击“商机合作”，检查模板卡和预览是否出现。
  - 把四条样例通过导入/手动粘贴走一遍，确认进入服务工作台并能打开客户页。

## 2026-06-27 本轮交接：我的页工作台文案

- 用户反馈：
  - “我的页 / 常用工作台”只看到服务，没有看到商机合作。
  - “只影响首页和工作台展示，不会删除资料”应简化。
  - “工作台”是否指雷达不清晰。
- 本轮已改：
  - `miniprogram/utils/workspace-mode.js`：服务工作台显示为“服务/商机工作台”，短名“服务商机”，图标“商机”。
  - `miniprogram/pages/profile/index.wxml`：说明改为“只影响首页和雷达展示。”。
  - `miniprogram/pages/profile/index.wxml`：按钮改为“去雷达”。
  - 我的页选中态改用 `activeClass`，减少 WXML 判断。
- 已验证：
  - `node --check miniprogram/utils/workspace-mode.js && node --check miniprogram/pages/profile/index.js` 通过。
  - 我的页和首页 WXML 标签检查通过。

## 2026-06-27 本轮交接：首页 V2 资料机会雷达

- 用户确认：
  - 产品主心智升级为“资料发出去，机会看得见”。
  - 不希望产品被房源完全框死，但房源仍作为默认推广尖刀。
  - 四工作台不能做成首页四个大按钮，避免退回功能超市。
  - 雷达 banner 是强心智资产，需要继续放在首页首屏。
- 新增文档：
  - `docs/stage2-docs/24-home-opportunity-radar-generalized.md`
- 本轮已改：
  - `miniprogram/pages/home/index.wxml`
    - banner 改为“资料机会雷达 / 资料发出去，机会看得见”。
    - 场景切换收敛为“当前：房源场景”轻胶囊。
    - 今日机会独立成数据面板。
    - 移除单独“客户雷达”大卡。
    - “最近成果”改为“最近有反馈的资料”。
  - `miniprogram/pages/home/index.js`
    - 今日机会指标统一为高意向、新打开、待跟进、待处理。
    - 待处理/待跟进按场景进入对应雷达或订单处理入口。
  - `miniprogram/pages/home/index.wxss`
    - 新增今日机会面板样式。
    - 优化场景胶囊、banner 文案和底部弱切换入口。
- 已验证：
  - 首页 JS 语法检查通过。
  - 首页 WXML 标签检查通过。
  - 首页 WXML 复杂表达式检查通过。
  - 首页模拟加载通过，默认房源场景和四个今日机会指标正常。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机确认：
  - 微信开发者工具重新编译首页，确认 banner 雷达图、今日机会卡、房源助手第一动作与参考方向一致。
  - 在 iPhone 和 iPad 检查“当前：房源场景”胶囊、今日机会数字和底部弱入口不挤压。

## 2026-06-27 本轮交接：首页 banner 视觉资产化

- 用户反馈：
  - 效果图很漂亮，但前端 DOM 版本差点意思。
  - 询问 banner 是否为 DOM，并建议实在不行直接使用效果图。
- 本轮已改：
  - `miniprogram/static/workspace/home-opportunity-radar-banner.png`
    - 从用户确认的整页效果图中裁出首页 banner 卡片。
  - `miniprogram/pages/home/index.wxml`
    - 首页 banner 改为本地图片资产。
    - 保留场景切换点击热区。
  - `miniprogram/pages/home/index.wxss`
    - 移除 banner 外层重复边框、背景和阴影。
    - 图片宽度自适应首页内容区。
- 注意：
  - banner 内的“当前：房源场景”是图片文案，不再随工作台动态变化。
  - 这是为了优先拿到高质感首屏；若后续要动态支持商品/服务/资料，需要补多张 banner 或重做高保真 DOM。
- 已验证：
  - 首页 JS 语法检查通过。
  - 首页 WXML 标签检查通过。
  - 首页 WXML 复杂表达式检查通过。
  - banner 图片资源存在，关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：资料、合集、雷达销售助理闭环 V1

- 用户确认：
  - 底部 tab 继续叫“资料”。
  - 资料和合集都要能发客户，不是所有资料都必须先做合集。
  - 主按钮更适合叫“发客户”，而不是普通“分享”。
  - 发客户后的状态追踪可以用浅色条和文字呈现。
- 新增文档：
  - `docs/stage2-docs/25-material-collection-radar-sales-assistant-loop.md`
- 本轮已改：
  - `miniprogram/utils/dashboard.js`
    - `enrichCard` 新增 `deliveryStatus`。
    - 根据打开、访客、客户动作输出等待客户打开、客户已打开、客户重复查看、建议跟进。
  - `miniprogram/pages/library/index.wxml/wxss`
    - 顶部定位改为“管理单条资料，直接发客户”。
    - 资料卡新增状态追踪条。
    - 主按钮改为“发客户”，客户入口改为“去雷达”。
  - `miniprogram/pages/showcases/index.js/wxml/wxss`
    - 顶部定位改为“把多条资料打包发客户”。
    - 合集卡新增状态追踪条。
    - 已发布合集主按钮改为“发客户”。
  - `miniprogram/pages/visits/index.wxml/wxss`
    - 顶部新增“看客户反馈和跟进建议”的定位卡。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集、雷达 WXML 标签检查通过。
  - 状态规则模拟通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机确认：
  - 资料页不同卡片状态条是否换行自然。
  - 合集页“发客户/更多”按钮是否在手机和 iPad 上不挤压。
  - 雷达页新增定位卡是否不会把首屏内容推得太低。

## 2026-06-27 本轮交接：资料/合集/雷达 P1 酷功能规则版

- 用户要求：
  - 先把 P1 收口，全部实现。
- 本轮已改：
  - `miniprogram/utils/dashboard.js`
    - `enrichCard` 新增 `salesCheck`。
    - 发前体检规则：缺联系方式、价格不清、缺图片、标题偏短、体检通过。
  - `miniprogram/pages/library/index.js/wxml/wxss`
    - 新增发客户状态筛选：全部、待整理、已发客户、有反馈。
    - 资料卡显示发前体检提示。
  - `miniprogram/pages/showcases/index.js/wxml/wxss`
    - 新增合集状态筛选：全部、草稿、已发布、有反馈。
  - `miniprogram/pages/visits/index.js/wxml`
    - 雷达画像标签增强。
    - 下一句话建议按标签生成。
    - 客户卡新增“打开来源”。
    - 资料优化建议可跳回来源资料。
    - 生成对比合集建议跳到合集创建页。
  - `miniprogram/pages/showcase-edit/index.js/wxml/wxss`
    - 支持 `method=radar_compare`。
    - 新增“来自雷达建议”提示卡。
  - `docs/stage2-docs/25-material-collection-radar-sales-assistant-loop.md`
    - 补充 P1 已落地清单和未完成的 P0 真实发送闭环。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集、雷达、合集创建页 WXML 标签检查通过。
  - 发前体检和状态规则模拟通过。
  - 本轮关键文件 `git diff --check` 通过。
- 重要边界：
  - 这是规则版 P1，可见体验已收口。
  - 真实 P0 发送闭环已在下一段补齐；如果继续增强，可再做独立发送记录表和按 shareId 下钻。

## 2026-06-27 本轮交接：P0 发客户真实链路

- 用户要求：
  - P0 也要全部实现，继续收口。
- 本轮已改：
  - `backend/app/schemas/cards.py`
    - `RecordViewRequest` 增加 `eventType/shareId/shareFromUserId/scene/referrer`。
  - `backend/app/models/domain.py`
    - `ViewType` 增加 `share`。
    - `ViewEvent` 增加分享归因字段。
  - `backend/app/core/schema.sql`
    - `view_events` 增加 `share_id/share_from_user_id/scene/referrer`。
    - 新增 `idx_view_events_share`。
  - `backend/app/services/repository.py`
    - Postgres 映射和索引补充 view_events 分享字段。
  - `backend/app/services/app_service.py`
    - `record_note_view/record_view` 支持 `eventType=share`。
    - share 事件不计入 PV/UV，只计 `shareCount/latestShareAt/topShareId`。
    - owner 自己打开资料不入库。
    - owner 自己打开合集事件返回 `recorded:false`。
  - `miniprogram/pages/library/index.js/wxml/wxss`
    - 资料卡“发客户”变成真实 `open-type=share`。
    - 分享时生成 `shareId`，记录 share 事件，并带归因参数。
  - `miniprogram/pages/note-preview/index.js`
    - 接收 `sid/from/src/ref`。
    - 记录客户打开时回传分享归因。
    - 预览页再次分享也生成新 `shareId` 并记录。
  - `miniprogram/utils/dashboard.js`
    - `normalizeStats` 保留 `shareCount/latestShareAt/topShareId`。
    - `deliveryStatus` 支持“已发出，等待打开”。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_postgres_repository_schema.py backend/tests/test_app.py::test_note_preview_view_updates_note_list_stats -q` 通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_showcase_builder_create_publish_public_and_archive -q` 通过。
  - 后端关键文件编译通过。
  - 前端相关 JS 检查通过。
  - 资料页、资料预览页、合集页、合集公开页 WXML 标签检查通过。
- 待真机：
  - 在资料页点“发客户”，确认直接弹微信分享。
  - 客户微信打开后，资料状态从“已发出，等待打开”变为“客户已打开”。
  - 发布者自己打开分享链接不应让 PV/UV 增加。
  - 合集 owner 自己打开不应进入访客统计。

## 2026-06-27 本轮交接：P0/P1 分享体验与裂变补强

- 用户要求：
  - P0/P1 一起补强。
  - 每个资源或合集下面的转发卡片下方加入“生成同款”等营销语句，方便裂变。
- 本轮已改：
  - `miniprogram/pages/library/index.js/wxml/wxss`
    - 点“发客户”后即时把本地卡片状态改为“已发出，等待打开”。
    - 卡片下方新增裂变提示。
    - “发前体检”提示可点击直达编辑。
    - 分享标题改为“xxx｜点开查看完整资料”。
  - `miniprogram/pages/showcases/index.js/wxml/wxss`
    - 点“发客户”后即时把本地合集状态改为“已发出，等待打开”。
    - 合集卡下方新增裂变提示。
    - 分享标题改为“xxx｜点开查看完整资料”。
  - `miniprogram/pages/note-preview/index.js`
    - 资料公开页二次转发标题改为客户友好口径。
  - `miniprogram/pages/showcase-view/index.js`
    - 合集公开页二次转发标题改为客户友好口径。
  - `docs/stage2-docs/25-material-collection-radar-sales-assistant-loop.md`
    - P0/P1 补强完成项已更新。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料页、合集页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 点资料/合集“发客户”后，确认微信分享面板出现，同时列表状态即时变化。
  - 检查裂变提示在手机和 iPad 上不挤压主按钮。
  - 客户打开公开页后，继续确认底部“生成同款”入口可见但不干扰看资料。

## 2026-06-27 本轮交接：小程序图片转 WebP 降包体

- 用户要求：
  - 前端图片改成 WebP，因为小程序前端超过 2MB，当前测试不了。
- 本轮已改：
  - `miniprogram/pages/home/index.wxml`
    - 首页雷达 banner 改用 `/static/workspace/home-opportunity-radar-banner.webp`。
  - `miniprogram/pages/login/index.wxml`
    - 登录页图片改用 `/static/workspace/login-room.webp`。
  - `miniprogram/utils/workspace-mode.js`
    - 四个工作台场景图改为 WebP。
  - `miniprogram/static/workspace/`
    - 新增 6 张 WebP。
    - 删除已替换的 PNG/JPG 原图。
  - 清理：
    - 删除 `miniprogram/.DS_Store`。
    - 删除 `miniprogram/static/.DS_Store`。
- 体积结果：
  - `miniprogram` 真实文件字节约 `1,697,712 bytes`。
  - 图片真实字节约 `149,917 bytes`。
  - `du` 显示约 `2172 KB block usage`，这是磁盘块占用，不等同微信上传体积。
- 已验证：
  - 旧 PNG/JPG 路径引用检查为空。
  - `node --check miniprogram/utils/workspace-mode.js` 通过。
  - 首页、登录页 WXML 标签检查通过。
- 待真机：
  - 首页 WebP banner 是否正常显示。
  - 登录页图片是否正常显示。
  - 四个场景图是否正常显示。

## 2026-06-27 本轮交接：前四个 tab 闭环感补强

- 用户要求：
  - 继续先打磨，不部署。
  - 先把前 4 个 tab 中“更稳、更酷”的点加上。
- 本轮已改：
  - `miniprogram/pages/home/index.js`
    - 新增雷达目标 tab 缓存。
    - 日常资料场景下，今日机会数字可进入雷达对应 tab。
  - `miniprogram/pages/visits/index.js`
    - 读取首页带来的雷达目标 tab。
    - 客户卡新增 `nextStep` 规则。
  - `miniprogram/pages/visits/index.wxml/wxss`
    - 客户卡展示“下一步动作”。
  - `miniprogram/utils/dashboard.js`
    - `enrichCard` 新增 `materialStage`。
  - `miniprogram/pages/library/index.wxml/wxss`
    - 资料卡新增阶段提示：待补强、可发送、已发出、已打开、建议跟进。
  - `miniprogram/pages/showcases/index.js/wxml/wxss`
    - 合集卡新增用途标签：推荐包、对比包、商品包、方案包、资料包、复访包。
- 已验证：
  - 相关 JS 语法检查通过。
  - 首页、资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 资料卡新增阶段条是否挤压内容。
  - 合集用途标签在小屏是否换行自然。
  - 雷达客户卡“下一步动作”是否让首屏过长。

## 2026-06-27 本轮交接：资料/合集卡片高度与雷达动作位置修正

- 用户反馈：
  - 资料和合集卡片不是字太长，而是卡片太高、不美观。
  - 用户追问“下一步动作”最合理应该在哪个页面。
- 本轮已改：
  - `miniprogram/pages/library/index.wxml/wxss`
    - 列表封面降为 `132rpx`，整体间距和按钮高度收紧。
    - 无客户动态时不再展示空胶囊。
    - 三条状态说明合并成一行状态胶囊。
    - 裂变提示缩短为“可追踪反馈 · 支持生成同款”。
  - `miniprogram/pages/showcases/index.wxml/wxss`
    - 封面降为 `96rpx`，右侧操作区收窄。
    - 用途标签和发客户状态合并成一行状态胶囊。
    - 裂变提示单行省略。
  - `miniprogram/pages/visits/index.wxml/wxss`
    - 撤回资料优化 tab 的“下一步动作”模块。
    - 产品判断：客户“下一步动作”属于待跟进页；资料优化页只保留资料修补和生成对比合集建议。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 资料卡、合集卡高度是否更协调。
  - 待跟进客户卡里的“下一步动作”是否清晰。

## 2026-06-27 本轮交接：资料卡二次压缩、合集顶部紧凑化、待跟进动作按钮化

- 用户反馈：
  - 要坚持产品判断，不要只是顺着用户说。
  - “下一步动作”应该在雷达待跟进页，需要补得更明显。
  - 资料卡仍偏高。
  - 合集顶部 banner 过高，需要重新设计。
- 本轮已改：
  - `miniprogram/pages/library/index.wxml/wxss`
    - 封面降到 `112rpx`。
    - 创建时间并入统计行。
    - 状态胶囊减少为阶段和发前问题。
    - 裂变提示仅在已发出、已打开或有客户动态时显示。
    - 按钮高度继续收紧。
  - `miniprogram/pages/showcases/index.wxss`
    - 顶部大 banner 改为紧凑工具卡。
    - 方向入口改成一行紧凑卡。
    - 顶部按钮和说明文字尺寸收紧。
  - `miniprogram/pages/visits/index.js/wxml/wxss`
    - 待跟进客户卡里的“下一步动作”改为可点击按钮。
    - 对比/合集动作跳生成对比合集，其余动作复制话术。
- 产品判断：
  - 客户“下一步动作”只放在雷达待跟进页。
  - 资料优化页不叫下一步动作，只放资料优化和生成对比合集建议。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：资料缩略图权重恢复与合集无效 banner 删除

- 用户反馈：
  - 资料缩略图太小、太靠上靠左，需要居中。
  - 资料卡右侧按钮区有多余空白。
  - 合集顶部 banner 没有作用就不要保留。
- 本轮已改：
  - `miniprogram/pages/library/index.wxss`
    - 列表缩略图调整为 `144rpx`。
    - 列表卡改为垂直居中。
    - 无客户动态时操作按钮改为两列，消除右侧空白。
  - `miniprogram/pages/showcases/index.wxml/wxss`
    - 删除顶部大 banner。
    - 删除方向卡。
    - 改为轻量操作栏：场景标签、合集类型、新建按钮。
- 产品判断：
  - 合集页是工具页，不应该用无效 banner 占首屏。
  - 资料缩略图需要保留识别价值，不能为了压高度压得过小。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：资料搜索按钮收窄与合集 Hero 样式统一

- 用户反馈：
  - 资料搜索按钮背景太长。
  - 合集顶部如果没有更好方案，就跟资料页 banner 一样。
- 本轮已改：
  - `miniprogram/pages/library/index.wxss`
    - 搜索按钮改为自适应宽度，保留 `min-width` 和左右内边距。
  - `miniprogram/pages/showcases/index.wxml/wxss`
    - 合集顶部改为和资料页一致的 hero 样式。
    - 下方保留轻操作栏：场景标签和新建按钮。
- 已验证：
  - 相关 JS 语法检查通过。
  - 资料、合集 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：合集页按参考效果图重做比例

- 用户反馈：
  - 之前生成的合集页效果图比例比当前前端好很多。
  - 可以按效果图重新做合集页。
- 本轮已改：
  - `miniprogram/pages/showcases/index.wxml`
    - 在自定义导航下新增页面内“合集”视觉锚点。
    - 合集卡状态改成一行胶囊：发布状态、资料数量、用途、发客户状态。
  - `miniprogram/pages/showcases/index.wxss`
    - 页面外边距、Hero 高度、标题、右侧“合”视觉块和主按钮比例按参考图重排。
    - 场景标签和新建合集按钮组成清晰主动作区。
    - 筛选胶囊、列表卡、封面、按钮和标签整体收紧，避免卡片继续显高。
- 产品判断：
  - 合集页可以有任务型 Hero，但必须服务“把多条资料打包发客户”。
  - 客户画像和下一步动作仍留在雷达，不进入合集页。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js` 通过。
  - 合集 WXML 小程序模板适配检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：修正合集页重复标题和空白过大

- 用户反馈：
  - 真机截图中合集页出现多个“合集”，顶部空白过大，视觉上完全不像参考图。
- 本轮已改：
  - `miniprogram/pages/showcases/index.wxml`
    - 删除额外的 `body-title`。
  - `miniprogram/pages/showcases/index.wxss`
    - 收紧 Hero 顶部留白和最小高度。
    - 让文案和右侧“合”视觉块回到首屏主位置。
- 产品判断：
  - 参考图要复刻视觉重心，不应机械复刻大段留白。
  - 自定义导航已有页面标题时，正文不要再重复放同名标题。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js` 通过。
  - 合集 WXML 小程序模板适配检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：修复合集页双导航标题

- 用户反馈：
  - 删除一个“合集”后，真机仍然还有两个“合集”。
- 根因：
  - 合集页 WXML 使用了 `<custom-nav title="合集" />`。
  - 但 `miniprogram/pages/showcases/index.json` 仍未设置 `navigationStyle: "custom"`。
  - 微信原生导航标题和自定义导航标题同时出现。
- 本轮已改：
  - `miniprogram/pages/showcases/index.json` 增加 `navigationStyle: "custom"`。
  - `docs/pitfalls.md` 记录：custom-nav 页面必须同步关闭原生导航。
- 已验证：
  - 合集 JS、JSON、WXML 检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：资料与合集卡片风格统一

- 用户要求：
  - 如果合集页比例通过，继续把资料页和合集页卡片风格统一，让两个原材料页面像同一个产品体系。
- 本轮已改：
  - `miniprogram/pages/library/index.wxml`
    - 普通资料卡外露操作收口为“发客户 / 编辑 / 更多”。
    - 更多入口复用已有 `handleMoreCardActions`，保留加入合集、复制文案、删除等低频功能。
  - `miniprogram/pages/library/index.wxss`
    - 资料卡改为与合集卡一致的白底、细边框、`8rpx` 圆角和轻阴影。
    - 资料卡标题、状态胶囊、裂变提示和按钮高度向合集卡靠齐。
    - 保留资料缩略图较大尺寸，避免降低单条资料识别度。
- 产品判断：
  - 统一卡片语言，不强行统一所有尺寸。
  - 资料页重点是识别单条资料，合集页重点是打包发客户。
- 已验证：
  - 资料、合集 JS 检查通过。
  - 资料、合集 WXML/JSON 检查通过。
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：雷达页销售助理 5 项收口

- 用户要求：
  - 直接把 5 个点都做了：待跟进客户卡、下一步动作、客户画像标签、资料/合集联动、助理式空状态。
- 本轮已改：
  - `miniprogram/pages/visits/index.js`
    - 新增来源筛选状态 `teambuy:radarSourceFilter`。
    - 读取资料/合集入口状态后，雷达只展示当前来源相关反馈。
    - 客户标签扩展到价格敏感、位置优先、反复看联系方式、关注保障、需要信任、沉默复活、正在比较、疑似同行、疑似上游等。
    - 待跟进主池过滤疑似同行和疑似上游。
    - 来源筛选时顶部统计按当前来源重算。
  - `miniprogram/pages/visits/index.wxml/wxss`
    - 新增来源筛选条。
    - 待跟进卡改为销售助理结构：看过什么、为什么值得跟、画像标签、下一步动作、复制话术、生成对比、打开来源、标记已联系。
    - 4 个动作按钮使用两列布局，避免挤压变形。
    - 空状态改为助理口吻，并提供生成对比合集入口。
  - `miniprogram/pages/library/index.js`
    - 有客户反馈的资料点击“去雷达”时写入来源筛选并切到雷达。
  - `miniprogram/pages/showcases/index.js`
    - 已发布合集“更多”菜单新增“雷达”入口，带合集来源进入雷达。
- 产品判断：
  - 资料/合集只负责“发出去”和“带来源进雷达”；客户动作统一在雷达处理。
  - 同行和上游不进入待跟进主池，但保留在访客画像里观察。
- 已验证：
  - 资料、合集、雷达 JS 检查通过。
  - 资料、合集、雷达 WXML/JSON 检查通过。
  - 本轮关键文件 `git diff --check` 通过。
## 2026-06-27 本轮交接：前四个 Tab 二次收口

- 用户要求：
  - 首页、资料、合集、雷达整体方向可用，但要继续收口，减少蓝白单调和说明文字，增强 AI 助理感。
- 本轮已改：
  - `miniprogram/pages/home/index.wxml`
    - 首页“今日机会”和“最近有反馈的资料”副文案改短，转成结果导向。
  - `miniprogram/utils/dashboard.js`
    - 未分享资料默认状态从“等待客户打开”改成“待发送”。
  - `miniprogram/pages/library/index.wxml/.wxss`
    - “发客户状态”前置为默认主筛选。
    - 分类、专题、标签收进展开工具区，减轻首屏后台感。
    - 资料卡首屏状态改为优先显示 `deliveryStatus`。
  - `miniprogram/pages/showcases/index.wxml/.wxss`
    - 合集卡把 `purpose` 提前为主信息块，先告诉用户这是推荐包、对比包、商品包、方案包还是资料包。
  - `miniprogram/pages/visits/index.wxml/.wxss/.js`
    - 雷达顶部说明压缩为一句短提示。
    - 客户卡标签改为“AI判断”。
    - 客户卡动作从 4 个并列按钮收口为“复制话术 + 更多”。
    - 雷达统计卡加入暖橙、绿、淡紫等轻状态色，降低蓝白单调感。
- 当前产品口径：
  - 首页：今天先做什么。
  - 资料：单条资料现在处于哪个发送阶段。
  - 合集：这份包适合发给谁。
  - 雷达：谁值得跟、为什么跟、下一句怎么说。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/library/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - `node --check miniprogram/pages/visits/index.js`
  - `node --check miniprogram/utils/dashboard.js`
  - 本轮关键文件 `git diff --check` 通过。
- 待真机确认：
  - 资料页高级筛选折叠后，首屏节奏是否更舒服。
  - 合集用途块是否比之前更容易让用户理解“这个包适合谁”。
  - 雷达统计卡新颜色在手机和 iPad 上是否足够清楚，但不过度花。
  - 雷达卡按钮收口后，用户是否更容易先执行主动作。

## 2026-06-27 本轮交接：无图资料标题封面卡

- 用户问题：
  - 许多微信群转发、展示页和资料卡没有图片，当前只显示“资料 / 房源 / 合集”这类占位字，不够好看也不够好认。
- 本轮已改：
  - 新增 `miniprogram/utils/title-cover.js`
    - 从标题中提取不超过 8 个字的重点内容，生成两行标题封面数据和轻色调。
  - `miniprogram/utils/dashboard.js`
    - 资料卡统一补 `titleCover`，供首页、资料页等无图卡片复用。
  - `miniprogram/pages/library/index.wxml/.wxss`
    - 无图资料卡改为“标签 + 标题重点词”封面卡。
  - `miniprogram/pages/home/index.wxml/.wxss`
    - 首页最近反馈无图卡同步改成标题封面卡。
  - `miniprogram/pages/showcases/index.js/.wxml/.wxss`
    - 无图合集卡改成标题封面卡。
  - `miniprogram/pages/showcase-view/index.js/.wxml/.wxss`
    - 展示页内无图 Hero、无图卡片同步改成标题封面卡。
    - 新增 `showcaseShareCanvas`，无 banner / 无首图时可生成分享封面。
  - `miniprogram/utils/business-card-share.js`
    - 新增 `generateTitleShareImage` 通用标题封面图。
  - `miniprogram/pages/note-preview/index.js`
    - 普通资料无图分享时，优先生成标题封面图。
- 当前边界：
  - 资料库/合集列表直接点“发客户”的分享 `imageUrl` 仍优先走已有图片。
  - 但无图资料和无图合集现在会在点击分享时预生成标题封面图，再作为分享兜底图使用。
- 已验证：
  - `node --check miniprogram/utils/title-cover.js`
  - `node --check miniprogram/utils/dashboard.js`
  - `node --check miniprogram/utils/business-card-share.js`
  - `node --check miniprogram/pages/note-preview/index.js`
  - `node --check miniprogram/pages/showcase-view/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27 本轮交接：无图分享卡 CTA 再收口

- 用户补充：
  - “我也想做同款”最好只是一行字，字体更小，不要占主要视觉。
- 本轮已改：
  - `miniprogram/utils/business-card-share.js`
    - 通用无图分享卡改成双层 CTA：主按钮固定承接“打开小程序查看完整资料/合集”，底部一行小字承接“我也想做同款”。
  - `miniprogram/pages/note-preview/index.js`
    - 普通资料无图分享图改用“打开小程序查看完整资料”主文案。
  - `miniprogram/pages/showcase-view/index.js`
    - 合集无图分享图改用“打开小程序查看完整合集”主文案。
  - `miniprogram/pages/library/index.{js,wxml,wxss}`
    - 无图资料从列表直接点“发客户”时，会先预生成标题分享图。
  - `miniprogram/pages/showcases/index.{js,wxml,wxss}`
    - 无图合集从列表直接点“发客户”时，会先预生成标题分享图。
- 待真机确认：
  - 分享面板弹起前，预生成无图分享图的速度是否足够稳定。
  - 微信实际分享预览里，小字版“我也想做同款”是否清楚但不抢视觉。
## 2026-06-28 前四个 Tab 真机收边补充

当前新增：

- [docs/qa/前四个Tab视觉收口_真机回归清单.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/qa/前四个Tab视觉收口_真机回归清单.md)

说明：

- 这是接在“首页 / 资料 / 合集 / 雷达第一轮视觉落地”和“雷达页 banner 二次收口”之后的补充动作。
- 目的不是继续改代码，而是先把真机验收标准钉住，避免下一轮收口时方向发散。
- 清单已经明确当前保留原则：
  - 首页保留 `banner + 机会面板 + 发给助手`
  - 雷达页保留 `同行过滤` 等业务必要模块
  - 房源卡高密度，非房源卡可继续压缩

建议下一步：

1. 用户上传体验版。
2. 按清单截首屏和关键卡片。
3. 只挑阻断体验的问题修第一轮。

## 2026-06-28 前四个 Tab 第一轮收边已落地

本轮已改：

- [miniprogram/pages/home/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.wxml)
- [miniprogram/pages/home/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.wxss)
- [miniprogram/pages/library/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.wxml)
- [miniprogram/pages/library/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.wxss)
- [miniprogram/pages/showcases/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/showcases/index.wxml)
- [miniprogram/pages/showcases/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/showcases/index.wxss)

已完成内容：

- 首页首屏文案压短，减少 banner 和助手区的重复说明。
- 资料页顶部说明压缩，并把一段长解释改成两个短胶囊。
- 资料页无图卡改成更明显的“轻设计卡”呈现。
- 资料卡底部重新补强“打开小程序 / 输入同款”传播引导。
- 合集页首屏说明压缩，无图合集卡同步切到轻设计风格。
- 合集卡底部保留“打开小程序看完整合集 / 输入同款继续问 / 导出方案书预留”一行引导。

仍未完成：

- 未做微信开发者工具截图验证。
- 未做真机验收，因此这轮只能算“第一轮视觉落地”，还不是最终收边完成版。

## 2026-06-28 前四个 Tab 统一收边完成到当前阶段

继续补的内容：

- [miniprogram/pages/visits/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/visits/index.wxml)
- [miniprogram/pages/visits/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/visits/index.wxss)
- [miniprogram/pages/home/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.wxml)
- [miniprogram/pages/home/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.wxss)

本轮补齐后，前四个 Tab 当前状态：

- 首页、资料、合集、雷达都已统一到同一套轻量工作台风格。
- 首页最近反馈卡、资料卡、合集卡都已有无图轻封面兜底。
- 雷达页 hero、摘要区、跟进卡、建议卡、时间线卡已收成同一层次体系。
- “同行过滤”已在雷达摘要区显式保留。

当前建议：

- 前四个 Tab 可以先视为“收边到可继续推进其他模块”的状态。
- 后续如果还有 UI 微调，优先走真机截图驱动的小修，不再回到大范围重做。

## 2026-06-28 说明字删除补充

- 首页删除了 hero 底部 `AI会按打开、停留、咨询和重点查看自动整理机会`。
- 雷达页删除了 hero 底部 `AI跟进建议 / 会按打开、停留、咨询和重点查看自动更新`。
- 这一轮是纯减法，目标是避免用户看到“系统解释文字”产生不适感。

## 2026-06-28 我的页已按收口版落地

已改文件：

- [miniprogram/pages/profile/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.wxml)
- [miniprogram/pages/profile/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.wxss)
- [miniprogram/pages/profile/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js)
- [backend/app/models/domain.py](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/models/domain.py)
- [backend/app/schemas/auth.py](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/schemas/auth.py)
- [backend/app/services/app_service.py](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/services/app_service.py)

当前结构：

- 顶部身份卡：默认头像/昵称、可编辑、微信号/手机号状态
- 资源库：群资源库主入口，行业通讯录与行业资源预留
- 当前使用场景：唯一场景切换入口，绑定“完善资料”
- 我的内容：资料 / 合集 / 消息
- 设置与帮助：个人资料 / 帮助与反馈 / 退出登录

额外说明：

- 个人资料编辑层已补上 `微信号`，不再只有手机号。
- 群资源库和帮助反馈当前先用轻提示占位，后续功能落地时可直接接真实页面。

## 2026-06-28 我的页顶部小收边

- 顶部右侧长条 `编辑` 已改成更小的圆形修改提示。
- 资源库右上角已明确展示 `100 积分`。

## 2026-06-28 五个 Tab 心智与名片入口收口

本轮已改文件：

- [miniprogram/pages/home/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.wxml)
- [miniprogram/pages/home/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/home/index.js)
- [miniprogram/pages/library/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.wxml)
- [miniprogram/pages/library/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/library/index.js)
- [miniprogram/pages/profile/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.wxml)
- [miniprogram/pages/profile/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js)
- [miniprogram/pages/profile/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.wxss)
- [miniprogram/pages/showcases/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/showcases/index.wxml)
- [miniprogram/pages/visits/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/visits/index.wxml)

当前状态：

- 五个 Tab 顶部心智已分别收成：首页 `今天先做什么`、资料 `适合发客户的资料`、合集 `多条资料打包成一页`、雷达 `谁值得跟进`、我的 `资料、资源、消息和个人资料入口`。
- 服务场景下，`我的名片` 已从合集创建逻辑里抽出来：我的页显示独立名片入口，首页服务场景次动作进入名片筛选，资料页支持只看名片和只看服务方案。
- 本轮没有扩会员、PDF、专题、行业通讯录、行业资源。

已验证：

- `node --check miniprogram/pages/home/index.js`
- `node --check miniprogram/pages/library/index.js`
- `node --check miniprogram/pages/profile/index.js`
- `node --check miniprogram/pages/showcases/index.js`
- `node --check miniprogram/pages/visits/index.js`
- `git diff --check` 覆盖本轮修改文件。

仍需人工真机看：

- iPhone 小屏下五个 Tab 首屏是否不堵。
- 日常资料、名片、服务方案三类无图卡是否左侧文字图居中且不压右侧标题。
- 底部 Tabbar 是否挡住列表最后一张卡。

## 2026-06-28 群资源库添加微信群前端 MVP

本轮已改文件：

- [miniprogram/app.json](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/app.json)
- [miniprogram/components/custom-nav/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/components/custom-nav/index.js)
- [miniprogram/pages/profile/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js)
- [miniprogram/pages/group-resource-library/index.json](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/group-resource-library/index.json)
- [miniprogram/pages/group-resource-library/index.wxml](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/group-resource-library/index.wxml)
- [miniprogram/pages/group-resource-library/index.js](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/group-resource-library/index.js)
- [miniprogram/pages/group-resource-library/index.wxss](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/group-resource-library/index.wxss)

当前能力：

- 我的页 `群资源库` 已跳转到新页面。
- 新页面支持搜索、热词、积分胶囊、添加微信群、上传二维码、填写城市和标签、发布奖励积分、查看二维码扣积分。
- 本轮是前端本地 MVP，数据存本机 storage。

未完成：

- 未接后端持久化。
- 未做二维码内容识别、重复校验、真实微信群判断。
- 未做积分明细、举报反馈、审核下架、退分扣分。
- 未做跨用户资源共享。

已验证：

- `node --check miniprogram/pages/group-resource-library/index.js`
- `node --check miniprogram/pages/profile/index.js`
- `node --check miniprogram/components/custom-nav/index.js`
- `app.json` 和页面 `index.json` JSON 解析通过。
- `git diff --check` 覆盖本轮修改文件。

补充小修：

- 搜索按钮已收进搜索卡片内，避免右侧溢出。
- 添加微信群按钮已改短。
- 已新增 `积分规则` 入口和弹层。

再次补充：

- 群资源库 `添加微信群` 已从内联表单重做为四步发布流程：
  - 上传识别
  - 点选信息
  - 有效期确认
  - 发布成功
- 搜索框已改为胶囊内部按钮布局，避免按钮和背景溢出屏幕。
- 效果稿中的新增/确认数字没有写死，当前用本地真实数据展示。

规则修正：

- 发布群不再直接到账积分，改为冻结 20 积分；2 人确认可进或后台确认后才应转可用积分。
- 当前前端本地 MVP 只展示冻结状态，不提供用户自己确认到账的按钮，避免自刷。
- 自己发布的群资源卡片新增 `删除`。
- 积分规则弹层已补充退分和惩罚机制。
- 城市选择已改为微信小程序原生地区选择器，保留 `全国` 快捷选项；当前 MVP 默认城市位为 `长沙市`，真实自动定位城市后续需接定位反查服务。
- 最近可查看群卡片底部已拆成统计行和按钮行，避免 `查看 / 确认可进 / 冻结积分` 被按钮挤压成竖排。

## 2026-06-28 部署前文字减负收口

本轮已完成：

- 首页、资料、合集、雷达、我的页首屏文案进一步压短。
- 资料页采用 B 方案：大块 AI 提示卡改为轻提示条。
- 企业资源搜索页工具语气收口，重复积分说明移出主页面。
- 帮助与反馈页保留奖励主心智，奖励卡副文案压为 `被采纳，就给奖励`。

已验证：

- `node --check` 覆盖首页、合集、雷达、我的、企业资源搜索、帮助与反馈 JS。
- `git diff --check` 覆盖本轮修改文件。

仍需人工真机看：

- 小屏首屏文字是否明显减负。
- 资料页轻提示是否足够解释“为什么列表会这样排序”。
- 企业资源搜索积分规则弹层里的规则是否和后端正式积分账本一致。

## 2026-06-28 部署前自测结果

本轮额外收口：

- 清理小程序前端展示文案里的开发态表达，避免用户看到 `后端 / 部署 / API Key / 本地测试 / 后续按钮` 这类不成熟措辞。
- 企业资源搜索保存页移除未实现的摘要卡按钮。
- 登录页本地调试入口在本地环境仍可用，但展示文案改为 `便捷登录`。

已验证：

- 小程序全量 JS `node --check`：通过。
- 小程序 49 个 JSON 文件解析：通过。
- `git diff --check`：通过。
- 后端编译：`.venv312/bin/python -m compileall backend/app backend/tests` 通过。
- 后端主测试：`.venv312/bin/python -m pytest backend/tests/test_app.py -q`，112 passed。
- 后端完整测试：`.venv312/bin/python -m pytest backend/tests -q`，149 passed。

部署前仍建议人工确认：

- 微信开发者工具真机预览五个 Tab 首屏。
- 资料无图卡、群资源库卡片、我的页资源工具四宫格在小屏手机上不挤压。
- 生产后端部署前备份 `.env`、`secrets/`、媒体目录和运行态数据。

## 2026-06-28 生产后端已部署

部署方式：

- 未使用服务器 `git pull`。
- 采用本地已验证代码定向 `rsync` 到生产。
- 排除生产 `.env`、`secrets/`、媒体目录、Docker volume 和运行态数据。

备份与回滚：

- 生产备份目录：`/home/ubuntu/teamBuy/backups/pre-deploy-20260628-062157`
- 旧后端镜像回滚标签：`teambuy-backend:before-deploy-20260628-062238`

已验证：

- `docker compose build backend` 成功。
- `docker compose up -d backend` 成功。
- 服务器本地 `/health` 正常。
- 公网 `https://teambuy.lifelove.top/health` 正常。
- 公网 `/api/wecom/config-check` 正常。
- 公网 `/api/wecom/customer-service-config` 正常。
- 服务器本地 `/api/wecom/archive/config-check` 正常。
- 管理接口错误 token 返回 403。
- 重启后等待一个 worker 周期，容器稳定，日志无异常堆栈。

待人工继续：

- 在微信开发者工具上传小程序体验版。
- 真机扫五个 Tab、资料分享页、企业微信助手入口。
- 后续版本稳定后整理 GitHub release，避免本地和服务器都出问题时无法恢复。

## 2026-06-28 最新交接：PC 运营后台 V1

本轮完成：

- 新增 PC 运营后台文档：
  - `docs/stage2-docs/29-pc-ops-console-v1.md`
  - `docs/qa/PC运营后台V1_测试清单与验收标准.md`
- 新增后台页面：
  - `GET /ops`
- 新增后台接口：
  - 总览 / 用户排行 / 内容排行 / 系统待处理
  - 群二维码批量上传预览、保存、列表
  - 反馈工单创建、列表、更新
- 新增后台轻量存储：
  - `backend/app/services/ops_console_store.py`
- 新增静态后台页面：
  - `backend/app/static/ops-admin/index.html`

已确认现状：

- 这版 PC 后台已经能做：
  - 每日运营总览
  - 用户活跃排行
  - 合集 / 资料排行
  - 导入 / 通知 / 媒体 / 同步异常聚合
  - 群二维码批量录入批次
  - 反馈工单处理
- 这版 PC 后台还不能做：
  - 真实全局资源积分余额调整
  - 群资源库 / 企业资源搜索的全局积分统计
  - 小程序帮助反馈前台自动汇入后台

为什么不能直接做积分管理：

- 群资源库积分、企业资源搜索积分、帮助反馈，目前主要仍在小程序本地 storage。
- 如果现在硬加“改别人积分”按钮，会出现后台已改、前台不生效的错觉。
- 因此本轮只在总览页明确标记这些模块“待后端化”。

测试结果：

- `python3 -m compileall backend/app`：通过
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -k "ops_admin" -q`：4 passed

下个 Codex 接手建议顺序：

1. 先把资源积分和帮助反馈迁到后端真实存储。
2. 再补“用户积分调整、冻结积分、积分流水、排行”。
3. 再把群二维码批次正式接入群资源库前台审核 / 发布链路。

## 2026-06-28 新增二维码服务器上传提示词文档

已新增：

- `docs/stage2-docs/30-group-qr-server-upload-handoff.md`
- `docs/prompts/group-qr-upload-codex-prompt.md`

用途：

- 给后续新会话的 Codex 一套稳定提示词，用于处理：
  - 读取本地微信群二维码图片
  - 上传到生产服务器 media 目录
  - 生成公网图片 URL
  - 整理成 CSV / XLSX 模板

重要口径：

- 批量模板里的 `二维码链接` 是图片 URL，不是扫码后的微信内部数据。

## 2026-06-28 最新交接：小程序真机 UI 细节收口

本轮完成：

- 群资源库空态 `去添加` 改成短胶囊并居中。
- 群资源库顶部移除重复的 `100 积分 / 积分规则`。
- 企业资源搜索顶部和详情页移除重复积分展示，只保留资源工具里的总积分入口。
- 企业资源搜索本地扣分 key 改为复用群资源库同一个资源积分 key。
- 雷达客户卡删掉底部重复 `复制话术 / 更多` 操作层。
- 首页机会卡删掉黑色 `复制话术` 按钮。
- 首页 `待发现` 空态去掉重复文案，压成一条提示。

已验证：

- 相关小程序页面 JS 语法检查通过。
- 本轮小程序文件 `git diff --check` 通过。

待人工继续：

- 微信开发者工具重新上传体验版。
- 真机重点复看：
  - 群资源库空态按钮是否居中、是否足够短。
  - 雷达客户卡 `下一步动作` 按钮是否不挤压文案。
  - 首页 `待发现` 是否只显示一条 `先发一份资料。`。
  - 我的页资源工具是否成为唯一积分总入口。

## 2026-06-28 最新交接：雷达动作与企业搜索真实接入

本轮完成：

- 雷达页客户卡默认动作改为 `看详情`，点击进入客户看板访客页。
- 删除“普通客户下一步默认复制话术”的心智，复制话术不再作为雷达主动作。
- 我的页资源积分规则补充冻结积分说明。
- 新增后端企业资源搜索接口：
  - `GET /api/enterprise-resources/search`
- 小程序企业搜索页优先调用后端接口。
- 生产后端已部署并验证：
  - `/health` 正常。
  - `/api/enterprise-resources/search?keyword=长沙装饰&page_size=2` 返回真实天眼查 MCP 候选。

重要注意：

- 当前天眼查 key 是 MCP 权限，REST OpenAPI `searchV2` 返回“无权限访问此api”。
- 后端已走 MCP `search_companies`，不要再切回 REST 搜索接口。
- 小程序前端改动仍需微信开发者工具上传体验版后才能在手机看到。
- 企业搜索“深度查询”当前仍主要是本地模拟结果；本轮先把企业候选搜索接到真实天眼查，后续再把风险/股东/变更等功能逐个接 MCP 工具。

## 2026-06-28 最新交接：企业资源搜索积分减负

本轮根据真机测试反馈调整：

- 企业候选搜索免费。
- 企业基本信息和深度查询统一改为 `5 分/项`。
- 查询卡片上的 `10分 / 20分` 已同步改为 `5分`。
- 我的页资源工具积分规则已同步为 `企业查询：-5/项`。
- 24 小时缓存仍然不重复扣分。

注意：

- 当前这是小程序本地资源积分策略调整，测试号此前已扣掉的本地积分不会自动恢复。
- 正式版资源积分仍需后端化，必须补余额、冻结、流水、缓存、退分、补偿和异常申诉。

验证：

- `node --check miniprogram/pages/enterprise-resource-search/index.js`：通过。
- `git diff --check` 针对企业资源搜索页和我的页规则文件：通过。

## 2026-06-29 最新交接：企业微信智能机器人权限网关 MVP

本轮完成：

- 新增后端路由 `backend/app/api/routes_robot.py`。
- `backend/app/main.py` 已挂载机器人路由。
- `backend/app/core/config.py` 新增 `robot_gateway_token`。
- `backend/.env.example` 新增 `ROBOT_GATEWAY_TOKEN` 说明。
- 新增接口：
  - `POST /api/robot/query`
- 调用要求：
  - Header: `Authorization: Bearer <ROBOT_GATEWAY_TOKEN>`
- 请求核心字段：
  - `chatType`: `private` / `group`
  - `externalUserId` 或 `fromUserId`；WorkBuddy API 插件也可不传，后端会读取请求头 `userid`
  - `roomId`
  - `text`
  - `limit`
- 返回核心字段：
  - 顶层 `result/text/answer/content` 都是机器人回复内容，优先给 WorkBuddy 输出参数映射 `result`。
  - `data` 内保留完整结构，供后端或小程序后续继续使用。
- 权限模型：
  - `public`：天气、帮助等公开问题。
  - `self`：查用户自己的资料/合集，必须通过 `wecom_identity_bindings` 映射到 `ownerUserId`。
  - `room`：群日报/广告识别，需要 `roomId`。
- 已实现：
  - 未配置或 token 错误时拒绝访问。
  - 未绑定企微身份时返回 `bind_required`。
  - 绑定后只查当前绑定用户自己的资料。
  - 群里问个人数据时返回 `private_required`。
  - 资料结果返回 `/pages/note-preview/index?id=...`。
  - 合集结果返回 `/pages/showcase-view/index?id=...`。

验证：

- `python3 -m compileall backend/app/api/routes_robot.py backend/app/main.py backend/app/core/config.py`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -k "robot_gateway" -q`：3 passed。

待接 WorkBuddy 前确认：

- WorkBuddy API 插件参数建议只配置 `text/chatType/roomId/limit`，发送人身份优先从请求头 `userid` 读取。
- WorkBuddy 输出参数如果调试面板空白，必须显式配置输出字段 `result`，来源路径填顶层 `result`。
- 第一版机器人只调用网关，不直接连接数据库。
## 2026-06-29 企业群日常运营方案已补

已新增文档：

- `docs/stage2-docs/31-enterprise-group-daily-operations-v1.md`

后续如要继续推进，建议按这份文档往下拆：

- 企业群机器人消息模板配置
- 企业群消息对应的小程序承接页
- 不同群类型的模板差异化

当前已确定的企业群口径：

- 不是继续分群场
- 是持续更新和内容承接场
- 固定 3 类消息：
  - 中午更新
  - 下午入口
  - 晚间总结
## 2026-06-29 企业群机器人消息模板已补

已新增文档：

- `docs/stage2-docs/32-enterprise-group-bot-message-templates-v1.md`

这份文档适合下一步继续拆给：

- 开发配置群机器人模板
- 运营配置不同 `groupId` 的文案
- 产品确认不同群类型的小程序承接页
