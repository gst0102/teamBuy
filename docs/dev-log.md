# 2026-06-21

## 2026-06-29：企业群机器人群发消息 API 最小闭环

- 背景：
  - 用户希望先打通群发消息 API，后续试企业群日常运营消息效果。
  - 已有产品口径是企业群由机器人稳定播报，外部客户群仍由运营本人转化，不把机器人拉进外部群作为主链路。
- 已完成：
  - `backend/app/core/config.py` 新增 `WECOM_GROUP_BOT_WEBHOOKS` 配置解析，采用后端 JSON 白名单保存 `groupId -> 企业微信群机器人 webhook`。
  - `backend/.env.example` 补充 `WECOM_GROUP_BOT_WEBHOOKS` 示例，强调真实 webhook 只放后端环境。
  - `backend/app/api/routes_wecom.py` 新增 `GET /api/wecom/group-bot/config`，可查看已配置群 ID、脱敏 webhook 和内置模板。
  - `backend/app/api/routes_wecom.py` 新增 `POST /api/wecom/group-bot/broadcast`，支持一次发送多个 `groupId`，支持 `midday/afternoon/evening/custom` 模板，默认 `dryRun=true` 只预览，`dryRun=false` 才真正调用 webhook。
  - 新增后端测试覆盖管理员 Token、dryRun 模板渲染和真实发送调用。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "group_bot"`：3 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- 待下一步：
  - 生产环境配置真实 `WECOM_GROUP_BOT_WEBHOOKS` 后，可先用 `dryRun=true` 预览，再用 `dryRun=false` 给一个测试企业群发送。

## 2026-06-29：PC 后台新增群发渠道映射

- 背景：
  - 用户确认暂时不测试小程序 `config_id` 入群，优先用已打通的外部群机器人 webhook 做日报运营测试。
  - 需要在 PC 后台维护“群标识 -> 外部群 webhook -> 群类型/模板/发送时间”的映射，方便人工和 AI 查阅。
- 已完成：
  - `backend/app/services/ops_console_store.py` 新增 `GroupBotChannel`，保存群标识、群名称、webhook、群类型、人群、城市、日报模板、发送时间、负责人、备注、启停状态。
  - `backend/app/api/routes_ops_admin.py` 新增：
    - `GET /api/ops-admin/group-bot-channels`
    - `POST /api/ops-admin/group-bot-channels`
  - `backend/app/api/routes_wecom.py` 的群机器人配置和群发接口同时读取环境变量白名单与 PC 后台映射；PC 后台保存的 `groupId` 可直接用于群发。
  - `/ops` 新增 `群发渠道映射` Tab，可新增/更新群发渠道，列表展示时 webhook 自动脱敏。
  - `小程序加群配置` Tab 增加说明：当前只是“小程序按钮入群”用途，日报群发优先走群发渠道映射。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "group_bot or bot_channel"`：4 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
  - PC 后台内嵌脚本 `node --check`：通过。

## 2026-06-29：企业群机器人支持小程序卡片消息

- 背景：
  - 用户希望测试企业群机器人是否可以发“小程序卡片”，而不仅是文本里附小程序路径。
- 已完成：
  - 对 `resource_test` 测试群直接发送 `template_card/text_notice` 小程序卡片，企业微信返回 `errcode=0`。
  - `POST /api/wecom/group-bot/broadcast` 新增 `messageType=miniapp_card`。
  - 小程序卡片支持 `miniappAppId`、`miniappPath`、`cardTitle`、`cardDescription`。
  - 默认 `messageType=text` 不变，原文本日报链路不受影响。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "group_bot"`：6 passed。
  - `.venv312/bin/python -m pytest backend/tests -q`：171 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
  - `git diff --check`：通过。

## 2026-06-29：电子名片/服务方案工作台分享封面补齐

- 背景：
  - 用户真机反馈微信小程序分享卡片底部显示“未发布的小程序 开发版”，并要求检查资料、合集、名片等小卡片。
  - 代码层面确认：微信分享卡片底部类目/开发版标识由微信后台服务类目和版本状态决定，前端只能控制标题、路径和 `imageUrl`。
- 已完成：
  - `business-card-studio` 直接分享时，保存后预生成电子名片专属横版分享封面，不再优先退回头像/二维码。
  - `service-offer-studio` 直接分享时，保存后预生成服务方案专属横版分享封面，不再优先退回封面/头像。
  - 客户预览页、资料库列表、合集列表/预览原有分享封面逻辑已复查：均已提供标题、路径和封面兜底。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `.venv312/bin/python -m pytest backend/tests -q`：171 passed。
  - `git diff --check`：通过。
  - 后续如果效果稳定，再接定时任务和运营后台按钮。

## 2026-06-29：恢复资料/合集分享营销封面优先级

- 背景：
  - 用户真机反馈小程序分享卡片大图退回原始封面图，看不到“由资料整理助手生成 / 生成同款 / 打开完整资料”等营销钩子。
  - 复查确认：营销封面生成器仍在，问题是部分分享入口遇到 `coverUrl/bannerUrl` 时跳过生成或优先返回原图。
- 已完成：
  - 客户资料详情页：普通资料即使有封面图，也会生成标题营销封面。
  - 资料库列表：点击“发客户”时不再因有原始封面而跳过营销封面生成，分享时优先使用生成图。
  - 合集列表/合集详情：不再因已有 banner 或首图跳过标题营销封面，分享时优先使用生成图。
- 已验证：
  - `node --check`：`note-preview`、`library`、`showcases`、`showcase-view` 通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

## 2026-06-29：补齐我的笔记/编辑页直接分享封面

- 背景：
  - 用户继续真机反馈仍看到原生小程序卡片，说明不是客户预览页单点问题。
  - 复查发现“我的笔记”列表直接分享只给电子名片/服务方案提前生成封面，普通资料、房源、商品仍回退原始 `coverUrl`。
  - 笔记编辑页普通资料直接分享也没有生成标题营销封面。
- 已完成：
  - `pages/notes` 列表现在给所有可分享资料预生成分享封面：房源用房源封面生成器，名片/服务方案用专属生成器，普通资料/商品用标题营销封面。
  - 列表分享按钮在封面准备完成前临时禁用，避免用户点太快导致微信拿到原始封面。
  - `pages/note-edit` 普通资料直接分享也生成标题营销封面，并优先作为 `imageUrl`。
- 已验证：
  - `node --check`：`notes`、`note-edit`、`note-preview`、`library`、`showcases`、`showcase-view` 通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

## 2026-06-29：分享封面隐藏 canvas 真机稳定性修复

- 背景：
  - 用户继续反馈仍看到原始封面图，怀疑封面生成器挂掉或需要部署服务器。
  - 复查确认：分享封面是小程序端 canvas 临时图，不依赖服务器部署；但多个页面的隐藏 canvas 使用 `1px` 或远离屏幕的负坐标，真机可能不稳定导出。
- 已完成：
  - 统一资料详情、我的笔记、编辑页、资料库、合集列表、合集详情、电子名片工作台、服务方案工作台的分享 canvas 尺寸为 `750rpx x 600rpx`。
  - 分享 canvas 改为固定在页面后层透明渲染，避免 `canvasToTempFilePath` 因画布尺寸过小、完全隐藏或远离视口导致失败。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

## 2026-06-29：分享封面改为 HTTPS 素材并清理原图兜底

- 背景：
  - 用户真机连续反馈：房源版、有图普通版仍显示原始房源图/草莓图，而不是房源、无图、合集等营销封面。
  - 系统性复查发现：生成器返回的是本地临时图路径，微信分享在当前真机环境仍可能回退；同时多个入口保留了 `coverUrl/bannerUrl/avatarUrl` 兜底，失败时必然显示原图。
- 已完成：
  - `business-card-share.js` 统一导出分享 canvas 后，调用现有 `/api/uploads/asset` 上传成 HTTPS 素材 URL，再返回给 `imageUrl`。
  - 房源版、无图标题版、合集版、电子名片、服务方案共用同一套“生成 -> 上传 -> HTTPS 分享图”链路。
  - 清理分享入口里的原图兜底：`notes`、`note-edit`、`note-preview`、`library`、`showcases`、`showcase-view`、`showcase-edit`、`card-view`、`business-card-studio`、`service-offer-studio` 不再把原始封面图直接传给微信分享。
  - 删除本轮讨论时临时生成但未提交的机器人卡片 SVG 草稿，避免混入版本。
- 已验证：
  - 分享相关小程序 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

## 2026-06-29：PC 运营后台新增小程序加群配置生成入口

- 背景：
  - 手动创建企业微信外部客户群二维码适合扫码测试，但小程序按钮式入群需要企业微信返回的 `config_id/plugid`。
  - 如果后台手动创建入口不展示 `config_id`，更稳妥的方式是由后端调用企业微信服务端 API 创建“加入群聊”配置。
- 已完成：
  - `backend/app/services/wecom_client.py` 新增 `create_group_join_way()`，调用企业微信 `externalcontact/groupchat/add_join_way`。
  - `backend/app/api/routes_ops_admin.py` 新增：
    - `GET /api/ops-admin/wecom-group-join-ways`
    - `POST /api/ops-admin/wecom-group-join-ways`
  - `backend/app/services/ops_console_store.py` 新增 `wecomGroupJoinWays` 本地后台记录，保存生成过的 `configId/chatIdList/roomBaseName`。
  - `backend/app/static/ops-admin/index.html` 新增 `小程序加群配置` Tab，可填写客户群 `chat_id`、群名规则、渠道 state，预览后生成 `config_id`。
  - `backend/tests/test_app.py` 新增后台鉴权、dryRun、生成并保存 `config_id` 测试。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "join_way or group_join"`：3 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
  - PC 后台内嵌脚本 `node --check`：通过。
- 说明：
  - 手动建群仍然可用；PC 端生成的是“小程序点击加入群聊”需要的 `config_id`。
  - `chat_id` 不需要在企业微信后台手动找；PC 后台已支持拉取企业微信客户群列表，点击某个客户群即可填入。

## 2026-06-29：PC 后台补企业微信客户群列表拉取

- 背景：
  - 用户在企业微信外部群设置页找不到 `chat_id`，需要后台直接拉取客户群列表。
- 已完成：
  - `backend/app/services/wecom_client.py` 新增 `list_customer_groups()`，调用企业微信 `externalcontact/groupchat/list`。
  - `backend/app/api/routes_ops_admin.py` 新增 `GET /api/ops-admin/wecom-customer-groups`，返回 `chatId/name/owner/status/createTime`。
  - `/ops` 的 `小程序加群配置` Tab 新增 `企业微信客户群列表` 区块和 `拉取客户群` 按钮。
  - 点击客户群行会自动填入上方 `chat_id`，并把群名带入备注和群名规则。
  - `backend/tests/test_app.py` 新增客户群列表规范化测试。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "customer_groups or join_way or group_join"`：4 passed。
  - `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
  - PC 后台内嵌脚本 `node --check`：通过。

## 2026-06-28：企业资源搜索 V1（天眼查接入）策划沉淀

- 背景：
  - 用户计划申请天眼查 API Key，并希望把企业查询能力接入资源库，作为群资源库之外的第二类资源能力。
  - 讨论后确认第一版不应把 162 个工具全部暴露，而应收敛为“企业搜索 + 高频查询 + 保存企业资源卡”。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/28-tyc-enterprise-resource-search-v1.md`。
  - 新增测试清单 `docs/qa/企业资源搜索V1_测试清单与验收标准.md`。
  - 新增参考图 `docs/png/enterprise-resource-search-mockup.png`。
- 已确认口径：
  - 前台入口名为 `企业资源搜索`，放在资源库中。
  - 资源页入口建议采用九宫格，方便后续补行业黄页、商机线索等资源能力。
  - 第一版开放 6 个高频查询功能：基本信息、股东结构、司法风险、经营情况、历史变更、知识产权。
  - 搜索候选免费；基本信息低门槛；深度查询按功能扣积分。
  - API Key 只放后端服务器环境变量或密钥文件，前端只调自己的后端接口。
  - 同企业同功能 24 小时优先走缓存，避免重复扣分和浪费额度。
  - 查询结果可保存为企业资源卡；“导出企业摘要卡”作为后续能力，不在第一版强推。
- 本轮性质：
  - 仅做策划、参考图和 QA 文档，未开发接入。

## 2026-06-28：服务场景合集空态改为先去资料创建名片/方案

- 背景：
  - 用户指出服务场景下，名片和方案应属于“资料”里的单个资产，不应在“合集”页直接出现“先做名片 / 先做方案”。
- 已完成：
  - `miniprogram/pages/showcases`：服务场景空态取消 `先做名片`、`先做方案` 两个按钮，改为单个 `去资料里做名片/方案`。
  - 点击后切到资料 Tab，并带上服务场景筛选，保持“先有资料，再做合集”的心智。
- 已验证：
  - 待本轮 `node --check miniprogram/pages/showcases/index.js` 与 `git diff --check` 一并确认。

## 2026-06-28：首页非房源场景补企业微信助手入口

- 背景：
  - 用户指出除房源场景外，其他首页场景没有明显的“加企业微信”入口，导入主链路心智不完整。
- 已完成：
  - `miniprogram/pages/home`：助手区副标题从房源硬编码改为 `homeUi.assistantSub`，按当前场景展示对应说明。
  - `miniprogram/pages/home`：日常资料、团购、服务/商机场景补充完整卡片式 `加企业微信助手` 入口，复用现有微信客服插件。
  - 房源场景继续保留原主按钮 `添加房源助手`，不重复新增入口。
  - 移除首页 `后续可扩展 / 已预留` 这类内部规划文案。
  - 同步清理雷达页、合集页、资料编辑页、合集编辑页和标签管理页的 `预留 / 后续` 前台文案，改为用户可理解的功能表述。
  - 继续清理首页邀请提示、我的页帮助描述和资料编辑页能力状态，避免出现 `后续接入 / 后续开放 / 后续支持` 等内部口吻。
- 已验证：
  - 待本轮 `node --check miniprogram/pages/home/index.js` 与 `git diff --check` 一并确认。

## 2026-06-28：我的页顶卡与资料页副标题继续收口

- 背景：
  - 用户反馈“我的”页顶部仍不够精致，尤其是编辑提示重复、文案偏长，真机和模拟器观感差异不大。
  - 用户提供本地图标 `/Users/yiyi/Downloads/修改.svg`，希望直接替换现有文字型“改”提示。
  - 用户同时指出资料页副标题“房源继续保留关键判断信息，其他资料更轻更好发”语气偏硬、视觉上也太抢。
- 已完成：
  - `miniprogram/pages/profile`：移除头像上的重复“改”标记，只保留右上角单一编辑入口，并替换为 SVG 修改图标。
  - `miniprogram/pages/profile`：顶部副标题从品牌式表述改为“你的资料、资源和消息都在这里”，更直接强化页面职责。
  - `miniprogram/pages/library`：资料页副标题收为“房源保留重点信息，普通资料发起来更轻一点”，并同步收顺 AI 提示卡两枚说明标签。
  - 新增静态资源：`miniprogram/static/icons/edit-profile.svg`
- 已验证：
  - 待本轮 `git diff --check` 与 `node --check miniprogram/pages/profile/index.js` 一并确认。

## 2026-06-28：资料页 banner 改成全场景中性表达

- 背景：
  - 用户指出资料页会随场景切换，顶部 banner 继续写房源口径不合适。
  - 同时要求“发客户状态”筛选选中态不要再使用黑色，页面颜色要继续收敛到蓝白主基调。
- 已完成：
  - `miniprogram/pages/library` 顶部 kicker / subtitle 改为适配多场景的中性表达。
  - `miniprogram/pages/library` AI 提示卡首条标签同步去房源化，改成更通用的“关键信息”表达。
  - `miniprogram/pages/library` 发客户状态选中态由黑底改为蓝底。
  - 继续压短 banner 文案：kicker 改为 `资料直接发客户`，副标题改为 `按场景整理，客户一眼看懂。`，并限制副标题宽度，避免首屏横向拉太满。
- 已验证：
  - 待本轮 `git diff --check` 一并确认。

## 2026-06-28：我的页资源库次级入口文案继续去“半成品感”

- 背景：
  - 用户指出“行业通讯录”和“行业资源”这两个入口不应再写 `预留`，否则会显得像未完成占位。
  - 同时需要进一步明确两者语义：前者偏找人找渠道，后者偏找资料找机会。
- 已完成：
  - `miniprogram/pages/profile` 将 `行业通讯录` 和 `行业资源` 的状态标签统一改为 `近期开放`。
- 已验证：
  - 待本轮 `git diff --check` 一并确认。

## 2026-06-28：专题从资料主流程继续收口，资料详情补明显返回

- 背景：
  - 用户反馈资料页里的 `专题` 和 `合集` 容易混淆，而资料编辑页里的专题字段也缺少稳定存在感。
  - 用户同时指出资料详情页应当有明显的返回箭头。
- 已完成：
  - `miniprogram/pages/library`：从“更多工具”和主筛选区移除专题管理与专题筛选，避免和合集主心智冲突。
  - `miniprogram/pages/note-edit`：资料编辑页不再展示专题相关输入与操作，标签区只保留标签整理。
  - `miniprogram/pages/note-edit`：顶部导航开启返回箭头。
  - `miniprogram/components/custom-nav`：补强返回按钮的边框与阴影，让真机上更容易看见。
- 已验证：
  - 待本轮 `git diff --check` 与 `node --check miniprogram/pages/library/index.js miniprogram/pages/note-edit/index.js` 一并确认。

## 2026-06-28：资料列表非房源卡片改为顶部对齐，规避小屏重叠观感

- 背景：
  - 用户真机反馈日常资料列表中，左侧轻设计卡与右侧标题区在小屏上出现重叠观感。
  - 检查后确认：日常资料、名片、服务方案等非房源卡片共用同一套列表卡骨架，房源/团购因为信息块更重，症状相对不明显。
- 已完成：
  - 首轮曾尝试把列表卡改为顶部对齐，但用户确认观感方向不对。
  - `miniprogram/pages/library/index.wxss`：恢复列表卡垂直居中，只在左封面区和右正文区补左右安全边距，避免两块视觉挤在一起。
  - `miniprogram/pages/library/index.wxss`：标题继续保留 `word-break`，避免窄屏长词把布局顶坏。
  - 后续继续收紧：左侧轻设计卡宽高从 `144rpx` 收到 `128rpx`，列表卡列间距从 `16rpx` 拉到 `24rpx`，右侧正文区额外补左右边距，确保正文真正吃到右侧留白。
  - 再次按真机反馈微调：左侧轻设计卡加宽到 `138rpx`，同时收掉封面和正文的额外左右 margin，列间距调为 `20rpx`，让右侧正文获得更多实际宽度。
  - 继续修正：确认轻设计卡的 `padding` 未计入固定列宽导致实际盒子溢出，改为 `box-sizing: border-box` 并固定 `overflow: hidden`；左侧文字图改为居中排版，宽高调整为 `148rpx`，列间距 `22rpx`。
- 已验证：
  - 待本轮 `git diff --check` 一并确认。

## 2026-06-27：前四个 Tab 视觉收口第一轮落地

- 背景：
  - 用户确认先按最新参考稿落地前四个 Tab，优先把页面做得更漂亮、更酷、更统一。
  - 用户补充：房源页因价格、地铁等标签需要承担中转发判断，不能像普通资料那样过度压缩；我的页只先定风格，内部内容后续单独做。
- 已完成：
  - `miniprogram/pages/home`：移除图片 banner 依赖，改为代码化 hero，保留雷达图、口号、今日机会、房源助手入口，并补充导出方案书预留说明。
  - `miniprogram/pages/library`：补上资料页引导卡，收紧首页文案，统一卡片圆角、边框和阴影；继续保留房源资料高密度信息展示。
  - `miniprogram/pages/showcases`：新增合集顶部方案包引导区，强化“打开小程序查看完整合集 / 支持生成同款 / 方案书预留”心智，列表卡改为更强封面感和更稳的右侧操作区。
  - `miniprogram/pages/visits`：雷达页头部改为更短更强的 AI 跟进提示，补充轻量导出方案书预留表达，优化建议卡层级。
  - `miniprogram/pages/profile`：只收口为统一风格的个人工作台骨架，不改深层功能内容。
- 已验证：
  - `git diff --check -- miniprogram/pages/home/index.wxml miniprogram/pages/home/index.wxss miniprogram/pages/library/index.wxml miniprogram/pages/library/index.wxss miniprogram/pages/showcases/index.wxml miniprogram/pages/showcases/index.wxss miniprogram/pages/visits/index.wxml miniprogram/pages/visits/index.wxss miniprogram/pages/profile/index.wxml miniprogram/pages/profile/index.wxss`
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/library/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - `node --check miniprogram/pages/visits/index.js`
  - `node --check miniprogram/pages/profile/index.js`
- 待真机：
  - 需要在微信开发者工具和真机确认首页 hero、合集右侧按钮列、资料页长标题和雷达页顶部新层级是否有挤压或换行异常。
  - 需要确认我的页新头部在不同昵称长度下不会挤压按钮和场景徽标。

## 2026-06-28：雷达页首屏按效果稿方向继续重做

- 背景：
  - 用户真机截图反馈：雷达页虽然比之前整齐，但顶部 banner 仍不像效果稿，更像普通功能页，而不是“客户雷达工作台”。
- 已完成：
  - `miniprogram/pages/visits` 顶部从普通提示卡改为真正的雷达 hero：左侧口号与说明，右侧雷达图与三张机会信号卡。
  - hero 底部增加 `AI跟进建议` 和自动更新提示，让首屏更像智能助手而不是说明书。
  - summary 区补充软标签说明；“优先跟进队列”文案收为“今天优先跟进”，右侧增加新提醒 badge。
  - “最近行为轨迹”文案收为“最近动作”，和效果稿语义更一致。
- 已验证：
  - `git diff --check -- miniprogram/pages/visits/index.wxml miniprogram/pages/visits/index.wxss`
- 待真机：
  - 重点确认 hero 右侧雷达图与三张信号卡在真机上不重叠、不截断。
  - 确认长标题、badge 和 tabs 在小屏手机上不会顶出布局。

## 2026-06-27：群资源库 V1 策划与开发交接文档

- 背景：
  - 用户手里有大量商业微信群，且群置换是实际需求。
  - 讨论后确认第一版不要做重人工撮合，也不做充值或群资源交易，而是做轻量自助的“群资源库”。
  - 前期基础数据不多，产品应搜索优先，不做树形资源目录，避免显得空和重。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/24-group-resource-library-v1.md`。
  - 新增测试清单 `docs/qa/群资源库V1_测试清单与验收标准.md`。
  - 新增参考图：
    - `docs/png/group-resource-library-search-mockup.png`
    - `docs/png/group-resource-library-points-mockup.png`
- 已确认口径：
  - 新用户送 100 积分。
  - 查看一个群二维码消耗 30 积分。
  - 发布一个群资源奖励 20 积分。
  - 群被确认成功进群奖励 10 积分，单群确认奖励封顶。
  - 二维码 5 天内自然过期不扣分；超过 5 天且多人反馈失效才扣分。
  - 查看次数只算热度，不等于信用；成功进群确认才算有效信号。
  - 群类型和用途标签采用系统预设 + 用户自定义，避免金融、爱好者、细分行业等长尾群无法表达。
  - 上传流程采用“系统识别 + 用户点选 + 少量自定义”，系统识别二维码可读性/疑似微信/重复，城市、类型、用途、人数、活跃度和有效期尽量点选。
  - 每个群必须有有效期，默认 5 天，可点选 1/3/5/7 天。
  - 页面可展示真实的每日新增和确认可进数量，不能伪造运营数字。
  - 虚假群下架时追回该群发布/确认奖励，并按级别额外扣罚。
  - 有效举报可以给少量积分奖励，但举报不立即加分，必须确认有效。
  - 规则通知采用站内通知为底座，订阅消息用于重要结果提醒，微信客服用于咨询和申诉。
  - 第一版不做充值、人工撮合、公开二维码墙、企业通讯录和爬虫。
- 本轮性质：
  - 仅做策划文档、测试清单和参考图归档。
  - 未修改业务代码，未部署，未上传小程序。

## 2026-06-27：收费与会员策略草案沉淀

- 背景：
  - 用户讨论未来月费、免费额度、99 元经营版、支付系统和分销系统上线时机。
  - 当前判断：支付和分销不要抢在飞轮验证前上线，先跑通四工作台、群资源库、公开页传播和客户雷达回访。
- 已完成：
  - 新增策略文档 `docs/stage2-docs/25-pricing-membership-strategy-draft.md`。
- 已确认口径：
  - 当前不建议立刻开发正式支付系统和分销系统。
  - 第一阶段可以先不收费，观察 7-14 天真实使用数据。
  - 免费版建议先给较宽额度，例如 50 个资料资源、10 个合集/公开页、每月 3 个群资源、最近 7 天基础雷达。
  - 早期专业版可考虑 9.9/19.9/月内测价，正式后 19.9/29.9/月。
  - 99/月适合作为后续 `成交雷达 Pro / 经营增长版`，必须卖用户画像、高意向识别、客户轨迹、沉默复活、资料优化和跟进话术等结果感，不卖简单容量。
  - `去水印` 不作为当前核心说法，改用 `品牌展示增强 / 专属展示页 / 弱化平台标识`。
  - 分销系统应在真实付费和自然推荐成立后再做。
- 本轮性质：
  - 仅做收费策略归档，不代表当前进入支付或分销开发。

## 2026-06-27：平台运营群分发 SOP 与每日运营动作

- 背景：
  - 用户明确平台后续会维护大量真实行业群，难点不在聊天，而在从手机信息到微信群分发的重复劳动太重。
  - 进一步确认这属于平台内部运营需求，不是面向所有用户的前台能力。
  - 不做个人微信无人值守自动群发，转而采用“系统判断 + RPA 辅助准备 + 人工确认发送”的半自动方案。
- 已完成：
  - 新增内部运营 SOP：`docs/stage2-docs/26-semi-auto-group-distribution-sop.md`
  - 新增每日量化运营动作：`docs/stage2-docs/27-daily-growth-operations-playbook.md`
- 已确认口径：
  - Codex / 系统负责群台账、待分发内容池、推荐群列表、发送记录、复盘数据。
  - RPA 只负责打开清单、切群、打开内容、放到输入框待确认，不做自动发送。
  - 人工负责判断当下群是否适合发、最终发送、控频和处理反馈。
  - 平台飞轮表达固定为：`用资源找人，用样板打动人，用雷达留住人。`
- 本轮性质：
  - 仅做内部运营方法和节奏文档，不开发自动群发能力。

## 2026-06-27：成交辅助系统 V1 客户雷达与机会提醒

- 背景：
  - 用户确认产品应从“资料整理工具”升级为“成交辅助系统”：客户发出去的资料要能反向发现谁有意向、为什么有意向、下一步怎么跟。
  - 同时确认公开客户页和发布者后台必须隔离：客户只看资料，发布者才看客户雷达、意向判断、跟进建议和私密字段。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/21-conversion-assistant-opportunity-radar.md`。
  - 新增测试清单 `docs/qa/成交辅助系统V1_测试清单与验收标准.md`。
  - `ViewEvent` / `ShowcaseEvent` 增加 `sessionId/durationSeconds/maxScrollPercent/focusSections`，公开资料页和合集页可回传停留、滚动和重点板块。
  - 同一 `sessionId` 的单条资料访问和展示页打开会更新原事件，不重复增加 PV。
  - `/api/dashboard/business` 增加 `opportunitySummary/opportunityAlerts/radarProfiles/contentInsights/revivalAlerts`。
  - 新增规则引擎：基于咨询动作、多次打开、停留超过 90 秒、重点看价格/联系方式/FAQ、沉默后复活等生成高/中/低意向、解释、建议动作和跟进话术。
  - `get_public_note` 改为返回公开脱敏结构，过滤 `privateData/privateTags/analyticsData/opportunityAlerts/radarProfiles`，并对 `structuredData` 使用公开字段过滤。
  - 小程序 `pages/note-preview` 和 `pages/showcase-view` 只做公开展示与行为上报，不展示后台判断。
  - 首页房源模式的“今日概览”升级为“今日成交机会”，展示高意向、待跟进、今日访客、最热资料和 1-3 条机会提醒。
  - `pages/business-dashboard` 增加“客户雷达提醒”和“资料优化建议”，支持复制跟进话术。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：112 passed。
  - 专项测试覆盖同 session 更新不重复 PV、高意向规则、公开资料私密字段过滤、dashboard owner 校验。
  - `node --check` 覆盖 home、business-dashboard、showcase-view、note-preview、api。
  - 小程序 JSON 递归解析通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 上传体验版后确认首页机会卡、客户雷达卡、复制话术按钮在手机和 iPad 上不挤压、不错位。
  - 真机确认公开客户页不出现“高意向 / 雷达 / 被分析”等后台文案。
  - 真机确认客户打开资料后，发布者回首页/反馈页能看到机会提醒。

## 2026-06-26：房源助手首页入口与企业微信完成反馈闭环

- 背景：
  - 用户确认房源版主路径应优先走“企业微信房源助手接盘”，小程序首页只在原有结构上增加助手入口，不重排 banner、今日概览和常用入口。
  - 用户要求企业微信每次处理完成后给用户明确反馈，避免“发过去有没有处理”的不确定感。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/20-property-wecom-assistant-entry-feedback.md`。
  - 新增自测报告 `docs/qa/房源助手首页入口与企业微信反馈闭环_Codex自测报告.md`。
  - 新增小程序图标资源 `miniprogram/static/icons/wechat.svg`。
  - `miniprogram/utils/workspace-mode.js`：房源工作台描述收口为“群里房源发给助手”，常用入口第一项改为“添加房源助手”并引用微信图标。
  - `miniprogram/pages/home`：保留原首页结构，banner 内增加轻量“房源助手已准备好”入口；常用入口标题改为“常用入口”；点击助手入口优先打开企业微信客服，失败时复制提示文案。
  - `backend/app/models/domain.py`：`ImportNotification` 增加 `resultType/resultRefId/resultPath/actions/sendStatus/sendError/sentMessageAt`。
  - `backend/app/services/import_notification_service.py`：导入 `success/claimed` 都视为完成反馈，通知带小程序结果路径和动作。
  - `backend/app/services/wecom_client.py`：新增微信客服文本发送方法。
  - `backend/app/api/routes_wecom.py`：真实 `sync_msg` 导入完成后尝试通过企业微信客服发送文本反馈；发送失败只更新通知状态，不阻断资料生成。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/utils/workspace-mode.js`
  - `node --check miniprogram/services/api.js`
  - `home/index.wxml` 标签计数检查通过。
  - `.venv312/bin/python -m py_compile` 覆盖本轮后端关键文件通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：109 passed。
  - 本轮关键文件 `git diff --check` 通过。
- 待验证：
  - 需要真机确认首页 SVG 图标渲染、企业微信客服能否正常打开。
  - 需要生产环境真实向企业微信发送一条房源消息，确认完成反馈能发回用户。
- 生产部署：
  - 已部署后端到生产，备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260626-064103-property-wecom-feedback`。
  - 本轮同步后端文件：`routes_wecom.py`、`routes_notes.py`、`domain.py`、`notes.py`、`app_service.py`、`import_notification_service.py`、`wecom_client.py`。
  - 部署过程中首次重启发现线上缺少此前本地已有的 `PropertyBatch*` schema，导致短暂 502；已补同步 `backend/app/schemas/notes.py` 和 `backend/app/api/routes_notes.py` 后恢复。
  - 公网验证：`/health` 200；`/api/wecom/customer-service-config` 返回 `configured=true`；`/api/wecom/notifications` 返回 200。
  - 未触发真实 `sync_msg`，避免在未确认窗口内主动拉取并回复真实用户；真实完成反馈需要下一条用户发给企业微信助手的房源消息验证。

## 2026-06-25：房源中介首批推广与房源合集裂变策略讨论

- 背景：
  - 用户确认第一批客户优先选择房源中介和二房东，原因是该人群商业属性强、离佣金和付费更近，且用户已有十多个房源对盘群可做冷启动。
  - 推广场景从“泛资料整理助手”收口为“房源版”：在对盘群中用真实房源卡和房源合集自然种草，让中介看到展示效果后主动生成自己的房源卡/合集。
- 已确认方向：
  - 对外推广阶段聚焦房源工作台，不平均展示日常资料、团购/商品、服务三个工作台；其他工作台保留为长期架构，不删除。
  - 首批主推房源合集，而不只推单套房源卡；合集定位为中介自己的移动房源橱窗。
  - 第一批重点模板为“清单对比”和“精选橱窗”：
    - 清单对比用于对盘群和同行快速扫房源。
    - 精选橱窗用于客户和朋友圈视觉展示。
  - 微信群小程序卡片和房源/合集页面都应有轻量入口：`我是中介，也想生成这种合集`、`生成同款房源卡`。
  - 用户点击“我是中介”后进入“生成同款”引导页，再引导转发房源卡/合集给企业微信助手，或后续直接授权复制。
  - 生成同款时只复制公开房源内容、图片和展示结构；对外联系方式替换成当前用户自己的电话/微信。
  - A 中介私密保存的真实房东/二房东/渠道联系方式默认不继承给 B；B 的上游联系人默认可以是 A 中介，且 B 可以自行编辑自己的上游联系人。
  - 公开客户页不展示“隐藏了房东联系方式”；上游联系人私密保存只出现在发布者管理态或生成同款说明中。
  - 媒体资产应独立去重：图片/视频按原始 `sha256` 判断完全相同媒体，图片转 WebP，视频转 MP4 并生成 WebP 封面；房源卡和合集只保存引用。
- 产品卖点沉淀：
  - `群里看到好房源，转给助手，一键变成你的房源卡；客户看你的电话，上游电话你自己留着。`
  - `多套房源不好发？一键生成房源合集，客户点开自己看。`
- 本轮性质：
  - 仅做运营与产品策略讨论，并更新文档。
  - 未修改业务代码、未部署、未上传小程序。

### 2026-06-25 补充：房源中介对盘群增长 MVP 前端实现

- 背景：
  - 用户确认第一批以租房中介为主，先打同行对盘群，主联系方式是微信号，生成同款第一版可接受半自动。
  - 用户要求先整理开发文档，再落地开发；其他三个工作台代码隐藏但不删除。
- 已完成：
  - 新增 `docs/stage2-docs/19-property-agent-growth-mvp.md`。
  - 新增 `docs/qa/房源中介对盘群增长MVP_测试清单与验收标准.md`。
  - 新增 `docs/qa/房源中介对盘群增长MVP_Codex自测报告.md`。
  - `miniprogram/utils/workspace-mode.js` 新增房源增长模式开关，默认读取为 `property`，主动工作台选择只暴露房源模式；其他工作台配置仍保留。
  - 首页隐藏“切换工作台”入口，房源工作台文案改为“资料整理助手 · 房源版 / 租房对盘工作台”，快捷入口收口为发房源、生成同款、房源合集、客户反馈。
  - 新增 `pages/property-same` 生成同款确认页，支持填写微信号、电话、上游联系人；微信号/电话本地记忆；可复制给企业微信助手的整理指令。
  - 房源合集公开页新增“我是中介，也想生成这种合集 / 生成同款”入口，并把房源合集文案偏向租房对盘语境。
  - 单套房源客户页新增“我是中介，也想生成这张房源卡 / 生成同款”入口，仅房源卡显示。
- 规则边界：
  - A 中介私密保存的真实房东/二房东联系方式默认不继承给 B。
  - B 的上游联系人默认可为 A，但 B 可自行编辑。
  - 本轮只是前端半自动生成同款引导，不是后端完整克隆接口。
- 已验证：
  - `node --check`：workspace-mode、home、showcase-view、note-preview、property-same 均通过。
  - `app.json` 和 `property-same/index.json` JSON 解析通过。
  - WXML `view/button/text` 标签计数通过。
  - 本轮关键文件 `git diff --check` 通过。
- 未做：
  - 未上传小程序体验版。
  - 未做真机 UI 回归。
  - 未实现后端克隆接口和媒体资产 hash 去重落库。

### 2026-06-25 追加：房源版文案、资料筛选和后端识别提醒

- 用户补充：
  - 首页工作台标题不要叫“租房对盘工作台”，改回“房源工作台”。
  - 资料页房源筛选默认收起。
  - 后续后端开发必须打通企业微信接收我们自己的小程序房源卡/房源合集完整信息，不能只识别标题。
- 已完成：
  - `miniprogram/utils/workspace-mode.js`：房源版标题改回“房源工作台”。
  - `miniprogram/pages/library/index.js`：房源筛选面板默认收起，进入房源资料列表时不自动展开筛选细项。
  - `docs/stage2-docs/19-property-agent-growth-mvp.md`：补充后端必做项，要求识别我们小程序 `pagePath` 内部 ID 并回查完整公开结构；第三方贝壳卡仍按外壳信息处理。
  - `docs/handoff-latest.md`：同步交接提醒。

### 2026-06-25 追加：房源合集预览页按钮变形和非房源混入修复

- 背景：
  - 用户真机截图反馈展示页预览仍有按钮变形，“查看详情”按钮大面积压住房源内容；底部“生成同款”按钮超出屏幕。
  - 同时房源合集里混入普通“资料 / 图片资料”，导致房源清单对比显示不纯。
- 已完成：
  - `pages/showcase-view` 清单模板行改为三列布局：封面、内容、详情按钮。
  - “查看详情”和“生成同款”改为普通 `view` 轻按钮，不再使用原生 `button`，避免默认样式撑宽。
  - 底部联系条在只有一个联系方式时改为单列全宽，按钮使用 flex 居中并重置默认边框。
  - 房源合集展示层按 `displayConfig.activeCategory=房源/房产` 过滤，只展示 `property_listing` 条目；商品和服务合集也同步按场景过滤。
- 已验证：
  - `node --check miniprogram/pages/showcase-view/index.js`：通过。
  - `showcase-view/index.wxml` 的 `view/button/text` 标签计数：通过。
  - 本轮 `showcase-view` 关键文件 `git diff --check`：通过。

## 2026-06-25：普通笔记保存后进入资料库修复

- 背景：
  - 用户真机新增普通笔记后，能进入 `note-edit` 详情页，但资料库看不到新笔记。
  - 复查链路后确认：快速笔记保存为 `UserNote` note-only 资料；资料库读取 `/api/cards`，而 `/api/cards` 此前只额外合成 `business_card/service_offer` 两种 note-only 服务资料，普通 `text_note` 被漏掉。
- 已完成：
  - 后端 `list_cards` 合成范围从服务资料扩展为所有无旧 Card 承载、无 `sourceCardId` 的有效 `UserNote`。
  - 普通笔记、链接、图片 OCR 等基础 note-only 资料会以 `note_card_{noteId}` 形式进入资料库列表。
  - 普通笔记前台分类从旧 `待整理` 归一为 `普通笔记`；业务资料仍保留房源、团购、名片、服务等分类。
  - 补充回归测试，覆盖快速新增普通笔记、手动创建房源、手动创建团购商品后 `/api/cards` 能按 `sourceNoteId` 返回合成资料卡，同时保留服务资料合成能力。
  - 普通笔记详情页首屏收口为“标题 + 内容”；“摘要”不再默认作为普通笔记输入项展示，只有扩展为资料能力后才显示。
  - 普通笔记的能力扩展入口从顶部强提示下移到正文后，文案改为“需要时再添加能力”；留言、咨询、接龙等后续按插件接入，不在普通笔记默认启用。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "manual_note_draft_creates_property_from_pasted_text or manual_note_draft_creates_groupbuy_from_pasted_text or quick_capture_saves_plain_text_note or service_note_resources_are_listed_as_library_cards"`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：`100 passed`。
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node` 解析 `miniprogram/pages/note-edit/index.json`：通过。
  - `git diff --check` 覆盖本轮后端与普通笔记详情文件：通过。
- 说明：
  - 本轮只修复后端资料库列表口径，尚未部署生产。
  - 日常资料台产品方向同步确认：普通资料管理台不默认做 SCRM，只保留轻量分享反馈；房源、团购/商品、服务工作台继续承载客户动作和跟进能力。

## 2026-06-23：客户看板首屏优先级改造

- 背景：
  - 用户真机确认房源首页四指标、客户看房和房看客数据已经能对应上。
  - 继续讨论后确认：`待跟进 / 新访客 / 咨询预约` 都有价值，但在首屏并列展示会让用户感觉重复、信息多、处理优先级不清。
- 已完成：
  - `pages/business-dashboard` 的房源客户看板首屏从“分类并列”调整为“优先联系队列 + 客户动态”。
  - 顶部新增“今日要处理 / 优先联系”主视觉，只突出预约、留资、明确咨询和高意向访客。
  - 新增 `priorityContacts` 前端整理逻辑：优先展示待跟进动作，再补充多次查看、看多套、有咨询的新访客。
  - 新增 `customerDynamics` 前端整理逻辑：客户动态作为可观察行为记录，用于解释优先联系原因、复盘新访客、预约咨询、房源效果，不等同第二个待办列表。
  - 保留原有 `最近访客 / 房源效果 / 推荐包效果` Tab 和下钻能力，不新增后端接口。
- 已验证：
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `node -e` 解析 `miniprogram/pages/business-dashboard/index.json`：通过。
  - `git diff --check -- miniprogram/pages/business-dashboard/index.js miniprogram/pages/business-dashboard/index.wxml miniprogram/pages/business-dashboard/index.wxss`：通过。
- 待真机验收：
  - 用户重新上传体验版后确认：优先联系队列是否降低“重复和乱”的感觉，客户动态是否更像观察/复盘区，而不是新的待办压力。

## 2026-06-24：房源资料库卡片与详情页降噪优化

- 背景：
  - 用户真机确认客户看板优先级版本符合预期，下一步转向房源资料库卡片和房源详情页打磨。
  - 用户明确：房源标题中的表情符号和发布风格属于中介个人行为，不应由系统清洗或重写。
- 已完成：
  - 资料库房源卡保留用户原始标题，标题下方新增系统整理的房源关键信息行：价格 / 户型 / 区域 / 导入来源等。
  - 房源卡客户数据从“打开 / 访客 / 客户动态”平铺，调整为轻量信号：打开、访客、客户动态，以及预约 / 留资 / 咨询 / 待跟进等行动标签。
  - 房源卡主操作收成一个按钮：有客户动态时显示“看客户”，无客户动态时显示“分享”；编辑、合集、复制、删除收进“更多”。
  - 房源详情页上半部保留原始标题，房源分享操作收成“转发房源 / 客户页预览”两个主按钮，分享文案、分享图和客户话术下沉为轻操作。
  - 房源详情页“功能组”改为“客户功能”，默认只显示已启用功能标签，电话、留资、预约、微信咨询等开关放入“设置”展开区。
  - 房源详情页“轻 SCRM”前台改为“客户反馈”，入口文案改为“查看这套房的客户”。
  - 房源详情页“标签与专题”改为“资料归类”，房源场景默认弱化，只展示系统标签，需要时再点“调整”展开。
  - 房源微信转发标题优先使用用户原始标题，避免结构化小区名覆盖用户发布风格；封面仍使用当前房源封面。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - `node` 解析 `miniprogram/pages/library/index.json`、`miniprogram/pages/note-edit/index.json`：通过。
  - `git diff --check` 覆盖本轮关键文件：通过。
- 待真机验收：
  - 上传体验版后确认房源卡是否更清爽，主按钮是否符合“有客户看客户、没客户去分享”的直觉。
  - 真实转发一条房源，确认微信聊天卡片标题、封面和客户页主信息不变形、不串场。
  - 房源详情页确认“客户功能 / 客户反馈 / 资料归类”是否明显比原来的“功能组 / 轻 SCRM / 标签与专题”更自然。

### 2026-06-24 补充：房源分享常驻与合集按工作台归属

- 背景：
  - 用户真机确认房源卡整体方向可用，但指出：有“看客户”后分享按钮不应消失；租金和户型是客户最关心的信息，需要前置；合集页不应在房源工作台里同时展示四类工作台合集。
- 已完成：
  - 房源资料库卡新增 `租金 / 户型` 前置标签，保留用户原始标题不变。
  - 房源卡操作区改为：有客户动态时显示 `看客户 + 分享 + 更多`；无客户动态时显示 `分享 + 更多`。分享按钮始终存在。
  - 客户页预览新增同样的 `租金 / 户型` 前置标签。
  - 房源微信转发标题改为两行结构：第一行保留用户原始标题，第二行展示 `租金 · 户型`，不把结构化字段融进标题本体；当前封面仍使用房源封面图。
  - 房源微信转发新增专属分享封面图：用隐藏 canvas 动态生成横版卡片，封面图内固定展示原始标题、`租金 / 户型`、面积/位置和房源图片，降低微信标题折行不稳定带来的展示风险。
  - 资料库房源卡片把 `租金 / 户型` 从胶囊标签改成标题下方第二行，和微信转发卡片的信息层级保持一致。
  - 资料库房源卡新增旧导入数据兜底：如果列表接口暂未返回结构化租金/户型，会从标题、摘要、详情文本识别；仍识别不到时显示 `租金待补 / 户型待补`，避免房源关键字段在列表里静默消失。
  - 房源分享封面图先加入轻品牌署名 `由资料整理助手生成`；四个工作台的统一营销位、品牌话术和转化入口后续集中设计。
  - 客户页预览增加页面栈兜底：站内进入时显示返回箭头，从微信分享单独打开时在页面底部提供“回到首页”入口。
  - 合集页读取当前 `workspaceMode`，按工作台展示单一创建方向：房源工作台显示房源合集，团购工作台显示团购合集，服务工作台显示案例合集，日常资料台显示普通资料包。
  - 从合集页新建时把 `mode` 传给展示页编辑页，编辑页优先按当前工作台默认分类选资料。
- 说明：
  - 自动生成合集 / 一句话生成合集尚未实现。这个能力需要真正按价格、户型、标签、区域等筛选资料并生成展示页，不能先做一个假入口。
- 已验证：
  - `node --check` 覆盖资料库、客户页预览、详情页、合集页、展示页编辑页和 dashboard 工具：通过。
  - 小程序相关 JSON 解析：通过。
  - `git diff --check` 覆盖本轮关键文件：通过。
  - 2026-06-24 追加验证：`node --check miniprogram/pages/note-preview/index.js`、`node --check miniprogram/pages/note-edit/index.js`、`note-preview/note-edit` JSON 解析、预览页相关 `git diff --check` 均通过。

### 2026-06-24 补充：合集生成流程改为模板先行

- 背景：
  - 用户明确判断：合集概念对新用户偏抽象，应该先让用户看到具象化模板，再进入新建、生成方式、选房源、预览和发布。
- 已完成：
  - `pages/showcase-edit` 页面顺序调整为：`先选模板 -> 新建合集 -> 选择生成方式 -> 选择和确认房源 -> 预览和发布`。
  - 模板区文案改为“先看客户会看到什么”，让模板承担认知引导。
  - 新建合集区前置标题、说明、分享标题和封面图。
  - 新增生成方式选择：`从当前筛选生成` 和 `手动选择` 可用；`按条件筛选`、`按近期反馈推荐` 作为下一版入口展示，点击提示“下一版开放”，不做假生成。
  - `从当前筛选生成` 会按当前分类自动加入资料；`手动选择` 会清空候选并让用户自己勾选。
  - 发布 payload 中保存 `displayConfig.generationMethod`，便于后续分析和继续编辑。
  - 模板卡改为使用真实页面效果图，不再只有文字说明；四张图分别表达 `精选橱窗 / 朋友圈长页 / 清单目录 / 品牌名片`，让用户一眼知道模板用途。
  - 模板图以 WebP 形式放在生产服务器 `/media/showcase-templates/`，小程序只引用 HTTPS 远程图，不进入主包；当前单张约 59-75KB。
  - 资料选择区默认只显示 10 条，支持“再显示 10 条”，避免房源多时用户长距离下滑。
- 已验证：
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - `miniprogram/pages/showcase-edit/index.json` 解析：通过。
  - `git diff --check -- miniprogram/pages/showcase-edit/index.js miniprogram/pages/showcase-edit/index.wxml miniprogram/pages/showcase-edit/index.wxss`：通过。

## 2026-06-23：房源首页四指标与客户看板一期实现

- 背景：
  - 根据 `docs/stage2-docs/18-property-home-customer-dashboard-v1.md` 和测试清单，房源工作台首页需要从“房源 / 打开 / 访客 / 客户”收口为“房源 / 打开 / 访客 / 待跟进”，并把客户看板默认首屏调整为待跟进客户。
- 已完成：
  - `miniprogram/utils/workspace-mode.js` 中房源模式四指标改为“房源 / 打开 / 访客 / 待跟进”，房源工作台概览文案改为“今日概览”。
  - `miniprogram/pages/home` 中四个房源指标支持点击：房源进入资料页房源筛选，打开进入客户看板 `propertyEffect`，访客进入 `visitors`，待跟进入 `followup`。
  - `miniprogram/pages/business-dashboard` 支持 `mode=property` 与 `followup / visitors / propertyEffect / showcasePackage`，房源模式默认进入“待跟进”。
  - 原展示页能力在客户看板中保留为“推荐包效果”，文案强调“多套房源一起发给客户后的打开和点击”。
  - `miniprogram/pages/library` 支持首页传入房源入口筛选，默认用列表模式展示房源资料，并可清除筛选。
  - 已补充 `pages/visits` 和非房源模式看板路由，避免日常、团购、服务工作台误进入房源客户看板。
  - 新增 `docs/qa/房源首页四指标与客户看板一期_Codex自测报告.md` 和 `docs/qa/房源首页四指标与客户看板一期_验收报告.md`。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/visits/index.js`：通过。
  - `node --check miniprogram/utils/workspace-mode.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - 小程序 JSON 递归解析：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮未提交 Git、未部署生产、未上传小程序。
  - 仍需微信开发者工具或真机确认四指标点击、客户看板首屏、推荐包效果 Tab、资料页房源筛选和大屏列表可读性。
  - 2026-06-23 追加修正：资料卡“待跟进 / 客户动态”优先进入新资料客户动作页 `pages/note-actions`，有 `sourceNoteId` 但客户动作来自新资料时不再落到旧 `pages/manager` 访问详情，避免卡片显示待跟进但详情页无数据。
  - 资料页顶部四个统计暂定只做概览，不作为点击跳转入口；真正的客户处理入口放在单张资料卡的“待跟进 / 客户动态”上。

## 2026-06-23：房源首页四指标与客户看板一期方案

- 背景：
  - 用户确认“展示页”原本是多套房源一起发给客户的推荐页，不应被误当成客户看板本身。
  - 当前房源首页四个指标“房源 / 打开 / 访客 / 客户”里，“客户”不够明确，且现有经营看板默认偏展示页数据后台，不能第一时间回答“谁来了、看了什么、该联系谁”。
- 已完成：
  - 新增 `docs/stage2-docs/18-property-home-customer-dashboard-v1.md`。
  - 文档明确房源首页四指标建议为“房源 / 打开 / 访客 / 待跟进”，并定义每个指标的统计口径、用户理解和点击去向。
  - 文档明确客户看板一期默认进入“待跟进”，Tab 顺序建议为“待跟进 / 最近访客 / 房源效果 / 推荐包效果”。
  - 文档保留展示页能力，但在房源场景中前台解释为“房源推荐包”，承接多套房源一起发给客户后的打开、点击和咨询效果。
  - 文档补充资料页房源筛选、大屏列表/双列展示、客户卡片字段、空态、P0/P1/P2 验收标准和不做事项。
- 注意：
  - 本轮只做产品与开发文档沉淀，未修改业务代码。
  - 后续开发应优先闭环“看得懂、点得通、知道谁该跟进”，不要先做复杂 CRM 或 BI。

## 2026-06-23：客户痕迹首页与资料卡曝光优化

- 背景：
  - 用户反馈首页和资料卡片没有第一时间提示“来客户了”，浏览、访客、SCRM/留言不明显，且客户页反复点击后资料统计仍为 0。
  - 核心判断：现有首页/资料库主要读取旧 Card stats，而新资料客户页 `note-preview` 打开没有写入浏览事件，导致新资料的打开/访客长期为 0。
- 已完成：
  - 后端新增 `POST /api/notes/{note_id}/view`，客户打开新资料页时写入浏览事件；有 `sourceCardId` 的资料继续归到旧 Card 统计，无旧 Card 的资料按 note 自身统计。
  - `list_user_notes` 返回每条资料的 `stats` 和 `customerSummary`，包含打开、访客、登录访客、留资、预约、接龙/下单、待跟进和最新客户动作时间。
  - 旧 `list_cards` 在存在 `sourceNoteId` 时补充对应新资料的 `customerSummary`，方便资料库旧入口也露出客户动态。
  - 小程序客户页 `pages/note-preview` 加载成功后自动上报浏览；发布者自己预览不计入客户打开。
  - 首页四个统计口径调整为“资料/打开/访客/客户动态”，并新增“客户动态”列表，优先显示有浏览或客户动作的资料。
  - 资料库总览改为显示资料总数、当前筛选、访客、客户动态；资料卡片显示“打开 / 访客 / 客户动态”，有客户动作的卡片红点提示并自动靠前。
- 已验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q -k "note_preview_view_updates_note_list_stats or anonymous_and_logged_in_view_stats_are_isolated"`：`2 passed, 95 deselected`。
  - `python3 -m compileall backend/app`：通过。
  - `node --check`：首页、资料库、客户页、API、dashboard 工具、workspace-mode 均通过。
  - 小程序 JSON 递归解析：44 个通过。
  - `git diff --check`：通过。
- 注意：
  - 该改动包含后端新接口；生产真机要看到“点击后 stats 不再为 0”，需要部署后端。
  - 小程序首页和资料库视觉变化需要用户在微信开发者工具重新上传体验版。
  - 当前本地工作区存在大量未提交后端改动，本轮未擅自整包部署生产，避免带入无关改动。

### 生产部署补充

- 2026-06-23 16:20 左右已部署后端到生产。
- 部署前备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260623-162042-note-view-stats`。
- 本次同步文件：`backend/app/api/routes_notes.py`、`backend/app/api/routes_dashboard.py`、`backend/app/services/app_service.py`。
- 标准镜像构建卡在 Debian `apt-get update`，未中断线上旧服务；随后采用容器热补丁方式把 3 个文件复制到 `teambuy-backend-1:/app/app/...` 并重启后端容器。
- 公网验证：
  - `GET https://teambuy.lifelove.top/health` 返回 200。
  - `POST /api/notes/not_exist_deploy_probe/view` 返回业务级 404“笔记不存在”，证明新路由已上线。
  - `GET /api/notes?ownerUserId=user_25ec00a0f0` 已返回 `stats` 和 `customerSummary` 字段。
  - `GET /api/dashboard/business?ownerUserId=user_25ec00a0f0` 无 requester 返回 401；携带相同 `requesterUserId` 返回 200。
- 注意：
  - 容器热补丁已生效，服务器源码目录也已同步；但本次没有成功重建镜像。后续若重新构建镜像，需要确认服务器源码仍包含上述改动。

## 2026-06-23：首页工作台视觉与快捷入口小优化

- 背景：
  - 用户确认首页工作台基本结构可用，但单字图标如“资 / 团 / 服”和快捷入口文案仍偏占位，希望先把两字标签和各工作台普通笔记入口收口。
- 已完成：
  - “今日待处理”统计图标改为更明确的短词：日常为资料 / 打开 / 分享 / 资料包，房源为房源 / 打开 / 客户 / 预约，团购为商品 / 打开 / 接龙 / 买家，服务为名片 / 打开 / 咨询 / 预约。
  - 四个模式顶部右侧大方块从单字改为：资料 / 房源 / 团购 / 服务。
  - 快捷开始文案收口：
    - 日常：写笔记 / 存图片 / 存链接 / 建资料包。
    - 房源：新建房源 / 记需求 / 房源合集 / 我的名片。
    - 团购：新建商品 / 记素材 / 团购合集 / 查看接龙。
    - 服务：做名片 / 做方案 / 写笔记 / 案例合集。
  - 房源、团购、服务工作台均保留普通资料创建入口，分别用于记录客户需求、团购素材、服务素材。
  - 已新增并接入 4 张 240×240 首页工作台插画：`miniprogram/static/workspace/workspace-notes.png`、`workspace-property.png`、`workspace-groupbuy.png`、`workspace-service.png`，替代原顶部右侧大字方块。
  - 新增自测报告 `docs/qa/首页工作台视觉与快捷入口小优化_Codex自测报告.md`。
  - 新增验收报告 `docs/qa/首页工作台视觉与快捷入口小优化_验收报告.md`，结论为“需要人工确认”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js` 通过。
  - `node --check miniprogram/utils/workspace-mode.js` 通过。
  - 小程序 JSON 递归解析：44 个通过。
  - `git diff --check` 通过。
  - 4 张插画总大小约 240KB。
- 注意：
  - 当前先使用 240×240 PNG，未转 WebP；大小仍在前端包可接受范围内。
  - 仍需用户上传体验版后真机确认两字 / 三字图标是否居中、不截字，顶部插画是否清晰不破图，以及四个模式快捷入口点击是否符合预期。

## 2026-06-23：首页与 Tabbar 工作台模式一期复测与回归

- 背景：
  - 开发线程已根据 `docs/qa/首页与Tabbar工作台模式一期_Bug修复任务单.md` 修复两个 P0，并输出 `docs/qa/首页与Tabbar工作台模式一期_Bug修复报告.md`。
  - 原验收线程异常，新建复测线程后仍长时间未落盘；为避免 QA 流程卡住，本轮按 `skills/qa-acceptance/SKILL.md` 直接完成复测报告。
- 已完成：
  - 新增 `docs/qa/首页与Tabbar工作台模式一期_复测与回归报告.md`。
  - 复测结论为“需要人工确认”：P0 的代码和自动化证据已闭环，但缺微信开发者工具或真机体验版 UI 截图。
  - BUG-01 已核验：业务识别提示卡已有“继续当前工作台 / 切换到对应工作台”双选，切换只更新本地 `workspaceMode`，不改资料 owner、不删除资料、不强制改变身份。
  - BUG-02 已核验：工作台总看板、展示页效果、单条资料互动已有 owner / 非 owner / 匿名访客权限证据。
- 已验证：
  - `node --check miniprogram/pages/resource-create/index.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - 小程序 JSON 递归解析：44 个通过。
  - `git diff --check`：通过。
  - 权限/隐私专项测试：`7 passed, 89 deselected`。
  - 后端主测试：`96 passed`。
- 注意：
  - 可以进入最终人工确认。
  - 真机重点确认新增提示卡按钮是否出现、是否居中、不截字，以及切换后首页 / 工作台是否按新模式展示。
  - P1 的最近反馈筛选、资料页模式推荐、合集页动态推荐和 `workspaceMode` 后端持久化仍后置。

## 2026-06-23：首页与 Tabbar 工作台模式一期 P0 Bug 修复

- 背景：
  - 用户补充 `docs/qa/首页与Tabbar工作台模式一期_Bug修复任务单.md`，要求只按任务单修复，优先闭环 BUG-01 和 BUG-02 两个 P0。
  - 验收官此前结论为“不通过”，关键缺口是 P0-23 业务识别后缺少切换工作台专门提示，以及 P0-27 权限/隐私缺专项证据。
- 已完成：
  - `pages/resource-create` 的业务识别提示卡新增专门工作台切换区，提供“继续当前工作台 / 切换到对应工作台”两个选择。
  - 房源映射 `workspaceMode=property`，商品/团购映射 `groupbuy`，服务方案/电子名片映射 `service`。
  - 切换只保存小程序本地 `workspaceMode`，不修改资料 owner、不删除资料、不改变资料归属。
  - `GET /api/dashboard/business` 新增 `requesterUserId` 校验：owner 可读，非 owner 返回 403，匿名缺身份返回 401。
  - 小程序 `fetchBusinessDashboard` 已默认携带当前 owner 作为 requester。
  - 后端测试补充工作台总览、展示页效果、单条资料互动的 owner / 非 owner / 匿名访客权限证据。
  - 新增 `docs/qa/首页与Tabbar工作台模式一期_Bug修复报告.md`。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 递归解析：44 个通过。
  - `git diff --check`：通过。
  - 权限/隐私专项测试：`7 passed, 89 deselected`。
  - 后端主测试：`96 passed`。
- 注意：
  - P1 的最近反馈筛选、资料页模式推荐、合集页动态推荐未在本轮展开，已写入 Bug 修复报告。
  - `workspaceMode` 仍按一期决策仅本地保存，未做后端用户偏好持久化。
  - 真机仍需用户上传最新体验版后确认提示卡按钮、Tabbar、首页和工作台展示。

## 2026-06-23：工作台第一期重新自测报告

- 背景：
  - 验收官已输出 `docs/qa/工作台第一期_验收报告.md`，结论为“不通过”。
  - 主要原因是 P0-23 业务识别后的工作台切换提示未闭环、P0-27 权限/隐私缺专项回归证据，以及真机主链路仍未确认。
- 已完成：
  - 新增 `docs/qa/工作台第一期_Codex重新自测报告.md`。
  - 重新按验收官口径确认结论为“不通过”，不再把 P0-23 / P0-27 归为普通待确认。
  - 复核 `pages/resource-create` 的业务识别提示，确认当前只有“完善资料 / 先放笔记库”，缺少“切换对应工作台 / 继续当前工作台”的专门双选。
  - 复核 `GET /api/dashboard/business`，确认接口当前只接收 `ownerUserId`，缺少 requester 身份参数或鉴权证据，不能关闭 P0-27。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 递归解析：44 个通过。
  - `git diff --check`：通过。
  - 权限相关后端专项测试：`8 passed, 88 deselected`。
- 注意：
  - 后端专项测试只能证明旧链路中私有资料、展示页 analytics、单条资料 customer-actions 和旧资源统计脱敏没有明显倒退。
  - 工作台总看板接口仍需补 owner / 非 owner / 匿名访客专项权限测试和可能的接口鉴权修复。

## 2026-06-23：首页与 Tabbar 工作台模式一期测试清单

- 背景：
  - 用户要求根据 `docs/stage2-docs/17-home-tabbar-workspace-mode.md` 生成《首页与 Tabbar 工作台模式一期_测试清单与验收标准》。
  - 该阶段重点是首页、Tabbar 和常用工作台模式的信息架构重构，不是新增完整专题合集中心或 CRM。
- 已完成：
  - 新增 `docs/qa/首页与 Tabbar 工作台模式一期_测试清单与验收标准.md`。
  - 测试清单覆盖验收结论规则、测试范围、P0/P1/P2、自动化测试建议、真机回归清单、回归影响范围、Bug 修复任务单模板和上线前检查。
  - P0 明确覆盖 5 Tab、首次模式选择、`workspaceMode` 保存、首页按模式变化、工作台按模式变化、客户看板从“我的”迁出、资料库降噪、合集轻版入口、模式切换不删除资料、普通用户不暴露经营词。
  - `docs/decisions.md` 和 `docs/pitfalls.md` 已补充一期边界和风险。
- 注意：
  - 本轮只生成测试清单和文档沉淀，未实现首页/Tabbar 代码。
  - 后续开发完成后，需要按该清单进行自动化检查和真机回归。

## 2026-06-23：首页与 Tabbar 工作台模式一期实现

- 背景：
  - 用户确认一期按 `docs/stage2-docs/17-home-tabbar-workspace-mode.md` 的开发顺序执行，不新增复杂业务功能。
  - 目标是让普通用户默认只看到日常资料和分享效果，业务能力按工作台模式展示，客户看板从“我的”迁到“工作台反馈中心”。
- 已完成：
  - Tabbar 改为：首页 / 资料 / 合集 / 工作台 / 我的。
  - 新增 `miniprogram/utils/workspace-mode.js`，本地保存 `workspaceMode`，支持日常资料台、房源工作台、团购工作台、服务工作台。
  - 首页新增首次选择常用工作台；选择后保存偏好，后续按模式展示今日待处理、快捷开始、最近成果和最近反馈。
  - `pages/visits` 改为“工作台 / 反馈中心”，按模式显示分享效果、客户看板、接龙看板或咨询看板，并复用原访客 / 互动数据逻辑。
  - “我的”移除经营区域和经营看板入口，新增常用工作台设置。
  - 资料页降噪：默认只显示新增资料和更多工具；电子名片、服务方案、待认领、标签、我的笔记收进更多工具。
  - 合集页轻版化：前台命名改为“合集 / 资料包”，保留现有展示页接口和分享逻辑，新增四个创建方向提示。
- 已验证：
  - `node --check`：`workspace-mode`、首页、工作台、我的、资料、合集、经营看板、自定义导航均通过。
  - `miniprogram/app.json` 和 `pages/showcases/index.json` JSON 解析通过。
  - 路由扫描确认：没有 `switchTab` 到已移出 Tabbar 的 `resource-create`，没有页面内 `navigateTo` 到已成为 Tab 页的 `showcases`。
  - 本轮核心页面未新增 `px` 核心尺寸。
  - `git diff --check`：通过。
- 注意：
  - `workspaceMode` 一期先存本地，不新增后端用户偏好字段。
  - 合集页一期仍复用现有 `showcases` 能力，不做完整专题合集中心。
  - 小程序前端 Tabbar 变化需要用户重新上传体验版后真机确认。

## 2026-06-23：修正资料详情标签与专题的房产默认污染

- 背景：
  - 用户反馈“我的笔记资料详情”底部“标签与专题”默认出现房产相关标签和“万家丽”专题，这对非房源资料是不对的。
  - 该问题会让电子名片、服务方案或普通资料看起来被房产场景污染。
- 已完成：
  - `miniprogram/pages/note-edit` 增加按 `cardType` 过滤标签 / 专题的逻辑。
  - 非 `property_listing` 资料会过滤掉旧默认房产上下文标签和专题，例如“房产 / 房源 / 租房 / 万家丽 / 公寓”等。
  - 保留用户手动加入的标签：如果标签存在于 `userTags`，不会被误删。
  - 标签和专题输入提示改为通用场景，不再使用“万家丽 / 公寓 / 万家丽租房”作为默认示例。
  - `miniprogram/utils/note-display.js` 同步过滤资料库列表展示，避免详情页修正后列表仍显示旧房产默认标签。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/utils/note-display.js`：通过。
  - `node --check miniprogram/pages/notes/index.js`：通过。
  - 旧房产 placeholder 扫描：未命中。
  - `note-edit` 页面核心尺寸 `px` 扫描：未命中。
  - `git diff --check`：通过。
- 注意：
  - 房源资料本身仍会保留房产相关标签和专题建议；本次只清理非房源资料里的默认房产上下文。
  - 已经打开详情并点击保存的非房源旧资料，会把过滤后的标签 / 专题写回。

## 2026-06-23：新增项目专属运营策划 Skill

- 背景：
  - 用户要求先读完整项目，再为 teamBuy / 资料整理助手写一个专属运营策划 Skill，方便后续讨论未来运营方向。
  - 当前项目已经从单纯团购工具演进为“资料整理 + 销售页 + 客户动作回流 + 经营看板”的私域经营工具，运营讨论需要固定在真实产品阶段和仓库长期记忆上。
- 已完成：
  - 按项目启动规则读取 `AGENTS.md`、`docs/project-memory.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/dev-log.md`、`docs/handoff-latest.md`，并执行 `git status --short --branch` 与 `git diff --stat`。
  - 读取运营相关架构文档：插件化架构、多类型资料卡、客户动作插件、经营看板、电子名片与服务方案。
  - 新增 `skills/operation-planning/SKILL.md`，将运营策划固定为围绕“资料入库 -> 销售页/展示页 -> 客户动作 -> 跟进处理 -> 复用再发”的增长飞轮。
  - 新增 `skills/operation-planning/agents/openai.yaml`，用于 Codex UI 识别“运营策划”能力。
- 已验证：
  - 使用 `/tmp/teambuy-py312-test/bin/python` 运行 `quick_validate.py skills/operation-planning`：通过。
- 注意：
  - 本轮未修改后端和小程序业务代码。
  - 以后讨论运营、推广、增长、获客、转化、商业化、上线节奏或运营复盘时，应优先使用该 Skill。

## 2026-06-22：按参考图整块重做服务方案工作台

- 背景：
  - 用户提供新的服务方案参考图，明确要求“这块完全重做”，并指出上一版做到一半卡住。
  - 目标不再是修补白屏后的半成品，而是把模板选择、填写资料、确认详情页效果和保存分享做成完整工作台。
- 已完成：
  - 重写 `miniprogram/pages/service-offer-studio` 的 `index.js / index.wxml / index.wxss`。
  - 模板选择页改为 4 套模板清单 + 当前模板完整首屏预览，不再只是轻卡片列表。
  - 填资料页改为分组表单：基础信息、方案内容、联系方式、封面与案例图。
  - 确认页改为详情页视角预览，并保留模板切换。
  - 扩展 `miniprogram/utils/sales-page-templates.js` 中 4 套服务方案模板的预览元信息。
  - `pages/note-preview` 的 `service_offer` 客户页同步重做为模板化销售页结构，并补底部主动作条。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/note-preview/index.js`：通过。
  - `node --check miniprogram/utils/sales-page-templates.js`：通过。
  - `git diff --check` 针对本轮相关文件：通过。
- 注意：
  - 这轮是较大幅度的小程序前端重做，仍需用户重新上传体验版后真机确认布局、滚动、按钮点击区和分享效果。
  - 当前未补新的自动化小程序 UI 截图验证，主要依赖静态检查和后续真机回归。

## 2026-06-22：服务方案销售页 V1 独立工作台

- 背景：
  - 用户确认电子名片 P0 基本可继续，下一步进入“服务方案 / 非标服务销售页”开发。
  - 服务方案不另起 SCRM，也不做 SKU、订单或支付，继续复用现有 `service_offer + CustomerAction + LeadReminder` 基座。
- 已完成：
  - 新增小程序页面 `pages/service-offer-studio`，流程为“选风格 -> 填方案 -> 确认效果”，对齐电子名片工作台但文案和视觉按服务销售页重做。
  - 服务方案入口从“添加 -> 服务方案”直接进入独立工作台；旧 `sales-template-select` 里选择服务方案模板时也会转到新工作台。
  - 已有 `service_offer` 在笔记编辑页新增“设置方案样式”入口，可进入工作台实时切换模板，不需要重新填写内容。
  - 服务方案字段在前端拆成电话、微信、邮箱、公司网址 / 介绍链接，不再只用一个混合“联系方式”字段。
  - 工作台保存时写入 `service_offer`、模板元信息、结构化字段和默认转化配置：电话、微信、留资、预约、轻 SCRM、分享图入口；明确关闭团购接龙、支付预留。
  - 客户页 `service_offer` 新增专属详情结构，突出服务标题、卖点、适合人群、服务内容、流程 / 保障、报价说明、案例图片、联系与预约。
  - 4 个服务方案模板在工作台和客户页上有不同视觉气质：咨询预约、服务报价、案例背书、活动招募。
  - 服务方案客户页新增运行时分享封面生成，复用现有隐藏 canvas，不新增本地图片资源；微信好友 / 朋友圈分享优先使用服务方案封面。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 新增服务方案页面和客户页新增样式未发现独立 `px` 核心尺寸。
  - `git diff --check`：通过。
  - 后端服务方案 / 电子名片专项测试：`2 passed, 94 deselected`。
- 注意：
  - 这是小程序前端体验改动，需要用户重新上传体验版后真机查看。
  - 微信分享卡片仍只能控制标题、路径和图片；服务方案第一版复用现有隐藏 canvas 运行时生成模板化封面，不新增本地图片资源。

### 白屏修复补充

- 用户真机反馈服务方案工作台打开白屏。
- 已定位根因：
  - `defaultForm()` 初始化时误引用不存在的 `form`，导致页面加载阶段 JS 直接异常。
  - `buildPreview()` 使用 `images` 但未先定义，进入预览生成时也会异常。
- 已修复：
  - 移除 `defaultForm()` 中错误的 `form` 引用。
  - `buildPreview()` 内统一使用 `safeForm/safeTemplate` 并生成 `images/caseImages`。
  - 页面默认 `preview` 改为可用兜底对象，降低加载已有方案时的空对象风险。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 模拟小程序 `Page/getApp/wx` 环境加载 `service-offer-studio`：通过。
  - 小程序全量 JS 检查：通过。
  - 小程序 JSON 解析检查：通过。

## 2026-06-22：电子名片独立微信转发封面生成器

- 背景：
  - 用户真机转发电子名片后，微信聊天里看到的仍是普通小程序卡片/旧二维码卡片，不是已确认的精美电子名片效果。
  - 微信转发卡片不能直接复用客户页 WXML，必须单独提供 `imageUrl` 封面图。
- 已完成：
  - 新增 `miniprogram/utils/business-card-share.js`，作为电子名片专用微信转发封面生成器。
  - 生成器独立整理姓名、身份、公司/门店、服务范围、电话/微信和圆形头像，并用隐藏 canvas 绘制 750rpx 对应比例的横版名片封面。
  - 客户预览页 `pages/note-preview` 改为调用该生成器，微信好友和朋友圈分享都优先使用专用封面。
  - 编辑页 `pages/note-edit` 新增隐藏画布和封面预生成，电子名片从编辑页直接转发时也优先使用专用封面。
  - 资料库 `pages/notes` 新增隐藏画布和列表名片封面预生成，电子名片列表分享不再退回普通资料卡逻辑。
  - 分享标题统一为“姓名 · 身份 · 公司/门店”，视觉主体交给专用封面图承载。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 相关 WXSS 独立 `px` 扫描：通过，新增样式使用 `rpx`。
  - `git diff --check`：通过。
- 真机反馈修复：
  - 用户转发后微信聊天卡片已使用名片封面，但右侧内容被裁掉，原因是 750 设计坐标直接画到真机约屏宽的隐藏 canvas 上。
  - 已将生成器改为按 `windowWidth` 计算真实画布尺寸，绘制时整体缩放，导出时再生成 750×600 分享图，避免右半边被裁切。
- 注意：
  - 本轮是小程序前端改动，需要用户重新上传体验版后真机查看微信转发卡片。
  - 微信分享封面仍受微信平台缓存、体验版是否最新、头像下载域名白名单影响；头像下载失败时会用文字头像兜底。

## 2026-06-22：电子名片详情页独立重做

- 背景：
  - 用户对比参考图后确认：电子名片详情页不能继续复用此前“客户页预览 / 销售页”的通用结构。
  - 现有页面虽然有名片首屏，但后续动作区和内容区仍像普通资料销售页，和已确认的精美电子名片详情页不一致。
- 已完成：
  - `pages/note-preview` 中 `business_card` 单独走 `business-card-detail-page` 渲染分支。
  - 电子名片详情页改为：绿色名片首屏、圆形头像、姓名、身份胶囊、公司/门店、服务范围、电话/微信。
  - 名片首屏下新增四个圆形动作：电话咨询、微信咨询、留下电话/微信、预约沟通。
  - 保留原有留资和预约表单能力，但样式嵌入名片页，不再像普通销售动作网格。
  - 新增服务介绍、三列服务范围、联系与二维码/二维码占位、保存名片按钮。
  - 服务方案 `service_offer` 仍继续使用原销售页结构，房源/商品/普通资料不受影响。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 相关 WXSS 独立 `px` 扫描：通过。
  - `git diff --check`：通过。
- 注意：
  - 这是小程序前端页面改动，需要重新上传体验版后真机查看。
  - 当前二维码优先使用名片字段 `qrCodeUrl` 或可用图片，缺失时显示“二维码”占位，不伪造二维码。

## 2026-06-22：电子名片图片字段与 4 模板差异补齐

- 背景：
  - 用户反馈上传二维码后名片详情页没有显示。
  - 用户要求电话和微信设置后可以直接外呼/拨打或复制联系。
  - 用户要求新增公司网址选填介绍；头像和二维码不要在名片明细里显示 URL，而是直接显示图片。
  - 用户要求先画出 4 款名片卡片和对应详情页差异，因为当前 4 款看起来没有明显区别。
- 已完成：
  - 电子名片编辑页字段去掉“头像地址 / 二维码图片地址”普通 URL 输入，新增“公司网址”选填字段。
  - 电子名片编辑页新增头像和微信二维码图片区，直接显示当前图片；素材区图片新增“设头像 / 设二维码”操作。
  - 二维码显示逻辑兼容 `qrCodeUrl/qrcodeUrl/qrUrl/wechatQrCodeUrl/wechatQrUrl/qrCode`，并可从已上传图片中兜底选择。
  - 客户详情页电话咨询清理空格后优先拨号；微信咨询优先复制微信号；公司网址点击复制。
  - “保存名片”改为复制姓名、身份、公司、服务范围、电话、微信和网址的完整名片信息。
  - 电子名片详情页按模板 ID 拉开视觉差异：
    - 专业顾问：稳重顾问信任风。
    - 门店名片：绿色门店/预约风。
    - 专家介绍：紫色专业背书风。
    - 简洁微信风：头像居中、少字段轻名片。
  - 微信转发封面生成器已接收模板 ID，按模板色板生成不同气质的名片封面。
  - 新增 4 模板差异对照图：`docs/png/business-card-4-template-detail-comparison.svg`。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 相关 WXSS 独立 `px` 扫描：通过。
  - `git diff --check`：通过。
- 注意：
  - 已上传的二维码图片需要在素材区点“设二维码”，才能明确作为二维码显示；否则只能按图片兜底推断。
  - 公司网址第一版为复制，不直接打开网页；若后续要在小程序内打开，需要接 web-view 域名白名单。

## 2026-06-22：电子名片风格切换与联系方式动作修正

- 背景：
  - 用户要求电子名片填写完内容后，可以自由切换 4 款名片风格，不需要重新填写。
  - 用户认为电子名片里“预约沟通”不合适，应换成邮箱或按已填写联系方式动态显示。
  - 用户反馈电话和微信已填写但无法外呼或复制，需要把点击动作落到真实联系方式。
- 已完成：
  - 电子名片编辑页新增“名片风格”切换区，4 款模板可直接切换。
  - 切换模板只更新 `displayTemplate/displayTemplateName/displayTemplateScene/displayTemplateTone`，保留已填写的姓名、电话、微信、邮箱、网址、头像、二维码等内容。
  - 电子名片字段新增邮箱。
  - 电子名片详情页动作区改为动态联系方式：
    - 填了电话显示“电话咨询”，点击后清理空格/符号并调用拨号。
    - 填了微信显示“微信咨询”，点击复制微信号。
    - 填了邮箱显示“邮箱”，点击复制邮箱。
    - “留下电话/微信”保留为留资动作。
  - 电子名片详情页移除预约沟通动作和预约表单；服务方案仍保留预约沟通。
  - 点击电话/微信/邮箱后，页面会显示当前联系方式提示卡，明确用户刚点了哪个联系方式。
  - 编辑页功能组中，电子名片不再显示预约开关。
- 已验证：
  - 小程序相关 JS `node --check`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 相关 WXSS 独立 `px` 扫描：通过。
  - `git diff --check`：通过。

## 2026-06-22：电子名片与服务方案模板库 V1

- 背景：
  - 用户确认这两类资料的核心体验应从“填资料”变成“选模板，改内容，直接发客户”。
  - 现有接口和 SCRM 基座已经足够复用，本轮优先补模板结构、缩略预览和模板选择入口。
  - 用户真机反馈第一版仍像线框，模板看不出来；底部“使用模板”按钮变形；点击使用模板报“不支持的资料类型”。
- 已完成：
  - 新增 `miniprogram/utils/sales-page-templates.js`，定义 8 个销售页模板。
  - 电子名片 4 个模板：专业顾问、门店名片、专家介绍、简洁微信风。
  - 服务方案 4 个模板：咨询预约、服务报价、案例背书、活动招募。
  - 新增 `pages/sales-template-select` 模板选择页，支持电子名片 / 服务方案双 Tab、模板销售页预览、选中状态和底部“使用模板”。
  - 真机反馈后重做模板选择页：每个模板都有放大的手机页预览、中文卖点、中文功能点、场景标签和行动按钮预览，不再显示 `serviceHero` 等内部模块名。
  - 模板选择页 WXSS 已确认核心尺寸使用 `rpx`，底部按钮改为 `244rpx` 宽并 flex 居中，避免“使用模板”文字被截断。
  - 电子名片模板预览改为统一首屏名片视觉：圆形头像、姓名、身份胶囊、公司/门店、服务范围和电话/微信。
  - 资料库电子名片列表卡、编辑页电子名片首屏、客户页电子名片首屏均接入同一套名片视觉母版；模板选择页用样板信息，创建后自动替换为用户自己的信息。
  - 电子名片分享标题改为优先使用“姓名 · 职位 · 公司”，分享图片优先使用用户头像。
  - 客户页新增电子名片微信分享封面生成：页面加载后用隐藏 canvas 生成横版名片封面图，微信聊天卡片 `imageUrl` 优先使用该封面图；编辑页直接分享时标题和头像也按名片信息兜底。
  - “添加”页里的电子名片和服务方案入口改为先进入模板选择页，再创建资料卡。
  - 使用模板创建资料时会写入模板默认字段、模板名称、模板场景和模板 tone，并进入原有编辑页继续修改。
  - 编辑页顶部显示所选模板名，避免用户创建后丢失模板上下文。
  - 新增 8 模板总览图：`docs/png/business-card-service-offer-template-library.svg`。
  - `note-preview` 客户页已接入模板化销售页结构：电子名片突出头像、姓名、身份/公司、服务标签和客户动作；服务方案突出服务标题、卖点、适合人群、服务内容、流程、报价、案例和客户动作。
  - 客户页模板根据 `displayTemplate`、`displayTemplateName`、`displayTemplateScene` 和 tone 渲染；旧数据缺失或模板 ID 异常时按资料类型回退到默认模板。
  - 新增统一验收报告：`docs/qa/电子名片与服务方案统一验收报告.md`。
  - `docs/stage2-docs/16-business-card-service-offer.md` 已补模板库 V1 结构和后续增强方向。
  - 已部署生产后端，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-055345-business-card-service-offer`。
- 已验证：
  - 后端全量测试：`133 passed`。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 电子名片相关 WXSS `px` 扫描：通过，相关页面未发现 `px` 核心尺寸。
  - `git diff --check`：通过。
  - 公网 `/health` 正常。
  - 公网 `business_card` / `service_offer` 创建探针均已从“类型不支持”变为业务级“用户不存在”，说明生产后端已支持两类资料。
- 注意：
  - 生产后端已更新；小程序前端变化仍需要用户重新上传体验版后真机查看。

## 2026-06-22：电子名片与服务方案卡 V1

- 背景：
  - 当前资料库已有普通笔记、房源和商品/团购。
  - 用户确认还需要两类资料：非标准销售/服务销售，以及可接 SCRM 的个人电子名片。
  - 这两类和房源/商品的主要差异是前端展示和字段结构，客户动作与 SCRM 基座可以复用。
- 已完成：
  - 新增设计文档 `docs/stage2-docs/16-business-card-service-offer.md`。
  - 新增 4 张黑白线框原型 SVG：`business-card-edit-wireframe.svg`、`business-card-preview-wireframe.svg`、`service-offer-edit-wireframe.svg`、`service-offer-preview-wireframe.svg`。
  - 后端新增 `business_card` 和 `service_offer` 两种 `cardType`。
  - 电子名片空白创建时从用户资料带入昵称、头像和电话。
  - 服务方案默认启用咨询、留资、预约沟通和轻 SCRM，不启用商品 SKU、下单或接龙。
  - 小程序“添加”更多菜单新增“电子名片”和“服务方案”。
  - 资料库快捷筛选新增“电子名片 / 服务方案”，列表卡片显示“名片 / 服务”状态和客户信息入口。
  - `note-edit` 新增电子名片字段卡和服务方案字段卡，并复用功能组、轻 SCRM、图片/视频和客户页预览。
  - `note-preview` 新增名片/服务客户页展示，不显示商品 SKU、团购接龙或房源地图。
  - 新增自测报告：`docs/qa/电子名片与服务方案卡V1_Codex自测报告.md`。
- 已验证：
  - 后端全量测试：`133 passed`。
  - 新增/相关专项测试：`4 passed`。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端 compileall：通过。
  - `git diff --check`：通过。
- 注意：
  - 新类型第一版只通过明确入口创建，不加入自动识别。
  - 小程序前端变化需要用户重新上传体验版后真机验收。

## 2026-06-22：迁移链路小收口 V1

- 背景：
  - 用户确认先不要做大的“资料迁移工作台”，而是先做小的迁移链路收口。
  - 现有企业微信导入、手动添加、图片保存、OCR、房源/商品识别都已存在；本轮只让用户在资料库里看清“从哪来、现在什么状态、下一步做什么”。
- 已完成：
  - `miniprogram/utils/note-display.js` 新增迁移来源和状态计算。
  - `pages/notes` 顶部新增“最近迁入”轻概览，显示企业微信、手动/图片、图片待处理和候选确认数量。
  - 资料卡新增来源 + 状态小标签，例如“企业微信 / 已整理成房源”“图片资料 / 图片已保存”“手动文字 / 需要确认类型”。
  - “只看待处理”改为按前端计算出的 `migrationNeedsAction` 过滤，不再只依赖系统分类。
  - 顶部迁移卡新增“处理第一条”，有待处理资料时可直接进入下一条需要整理的资料详情。
  - 资料库普通笔记出现房源/商品候选时，支持直接点击“整理成房源 / 整理成商品”，复用后端 `confirm-type` 后进入对应详情工作台。
  - 普通 `text_note` 且无候选类型时，不再显示为“待整理”，资料卡状态改为“普通笔记”。
  - 普通笔记详情页默认收成轻量笔记器，只显示标题、摘要、正文；功能组、标签专题和候选整理放到“扩展为可运营资料”按钮之后。
  - 新增 QA 清单：`docs/qa/迁移链路小收口V1_测试清单与验收标准.md`。
- 注意：
  - 本轮没有新增独立迁移工作台页面，没有新增表，也没有改变企业微信导入和 OCR 主链路。

## 2026-06-22：展示页效果分享批次 P1 体验优化

- 背景：
  - 经营闭环 P0 已通过真机确认，进入 P1 收口后，需要让发布者更容易看懂“哪次发给客户带来了打开、看资料和咨询”。
- 已完成：
  - `pages/showcase-analytics` 的“分享批次”从短码列表改为业务化展示。
  - 每个批次显示“第 N 次发给客户”、状态标签“已发出 / 已打开 / 看过资料 / 已有咨询”、打开/看资料/咨询三项指标。
  - 保留批次尾号，便于和经营看板里的分享来源对照。
  - 资料点击排行和带资料的最近事件可点击进入对应 `note-actions` 客户动作页，看到某条资料带来的客户后能直接处理。
  - 展示页列表折叠效果面板里的资料点击排行也补齐“处理”入口，和单展示页效果页保持一致。
  - 展示页效果页的最近访客可直接进入客户库，并用访客昵称自动搜索。
  - 客户库、待联系和订单页支持通过 URL 参数带入来源、状态、日程或搜索关键词，跨页面跳转后不再掉回全量列表。
  - 客户库“当前筛选”卡新增“看待联系 / 看订单”，会把当前来源和阶段带到对应页面。
  - 展示页编辑保存时，对名称、简介、分享标题和联系文案增加分类默认兜底，避免空字段发布成半成品。
- 注意：
  - 本轮仅调整小程序前端展示，不新增接口和数据库表。

## 2026-06-22：经营闭环真机验收记录模板

- 背景：
  - 经营闭环代码侧和生产后端字段体检已完成，剩余阻塞点是用户上传最新小程序体验版后的真机 UI/交互确认。
- 已完成：
  - 新增 `docs/qa/经营闭环头像与处理链路_真机验收记录模板.md`。
  - 模板覆盖头像、经营看板四指标下钻、展示页/分享来源/资料排行筛选、具体客户处理卡、客户库、待联系、订单/接龙。
- 注意：
  - 该模板不是新功能，只用于下一次真机测试记录和判断 P0 是否可关闭。

## 2026-06-22：经营闭环头像与处理链路真机确认通过

- 背景：
  - 用户上传最新小程序后反馈：头像、经营看板下钻和客户详情信息“都能看到了”。
- 已确认：
  - 头像不再是白块，可看到真实头像或兜底头像。
  - 经营看板四个指标可以下钻到具体客户列表。
  - 客户详情卡可以看到头像、电话/微信、来源展示页、分享来源和看过资料。
- 已更新：
  - `docs/qa/经营闭环头像与处理链路_验收报告.md` 结论从“代码侧通过，真机侧需要人工确认”改为“通过”。
- 注意：
  - 该 P0 已可关闭；后续看板、客户库、待联系和订单/接龙的改动进入体验优化或下一阶段功能，不再作为本轮阻塞项。

## 2026-06-22：经营闭环头像测试断言对齐

- 背景：
  - 继续复核“头像白块 + 经营看板/客户库/待联系/订单落到具体人”目标时，专项测试通过后，后端全量测试发现旧断言仍要求空头像必须写入 `payload.avatarUrl/customerAvatarUrl`。
  - 当前真实产品规则已经改为：没有可用 HTTPS 头像时，不强行保存空头像字段，前端统一显示彩色文字兜底。
- 已完成：
  - 更新头像资料相关后端测试断言，和当前后端错误文案“头像地址必须是可访问的 HTTPS 地址”一致。
  - 更新商品接龙/轻订单测试断言，允许空头像在后端返回中为缺失或 `None`，由前端兜底显示。
- 已验证：
  - 经营闭环专项测试：8 passed。
  - 后端全量测试：131 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端 compileall：通过。
  - `git diff --check`：通过。
  - 生产 `/health`：`ok`，数据库为 PostgreSQL。
- 注意：
  - 本轮只对齐测试和文档，不改变后端业务行为。
  - 真机仍需上传最新小程序体验版后，按经营闭环真机清单确认头像兜底、外呼、复制微信和另一个微信打开分享后的访客记录。

## 2026-06-22：经营闭环验收报告与主客户头像补齐

- 背景：
  - 对照用户原始诉求做完成度审计时，发现经营看板“客户资料”主客户卡只显示文字头像，即使 `primaryCustomer.avatarUrl` 有真实头像也不会展示图片。
  - 继续核对后端字段来源时，发现经营看板 `latestActions` 没有返回客户动作里的 `avatarUrl`，导致主客户卡前端即使支持图片，也可能拿不到真实头像。
- 已完成：
  - `pages/business-dashboard` 的客户资料主客户卡改为优先展示真实 HTTPS 头像，缺失时显示彩色文字头像。
  - 后端经营看板聚合补齐 `latestActions.avatarUrl`，并在客户动作合并到 `visitorProfiles` 时保留 `payload.avatarUrl`。
  - 后端测试新增断言：带头像的客户动作必须出现在 `latestActions` 和 `visitorProfiles`。
  - 新增 `docs/qa/经营闭环头像与处理链路_验收报告.md`，按头像、经营看板下钻、后端数据口径、客户库、待联系、订单/接龙逐项说明代码侧证据和真机待确认项。
- 已验证：
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - 小程序 JSON 解析检查：通过。
  - 经营闭环相关后端专项测试：5 passed。
  - 后端全量测试：131 passed。
  - 小程序全量 JS 检查：通过。
  - 后端 compileall：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-015958-dashboard-avatar-flow`。
  - 注意：最初只同步宿主机文件并重启容器未生效，因为后端代码在 Docker 镜像内；随后已执行 `docker compose build backend && docker compose up -d backend` 重建镜像并重启。
  - 公网验证：`/health` 正常；生产容器内文件确认包含 `latestActions.avatarUrl`；真实账号 `user_25ec00a0f0` 的经营看板接口已全量返回 `latestActions.avatarUrl` key，且 `visitorProfiles` 含头像、联系方式、展示页、分享来源和资料点击下钻字段。
- 注意：
  - 后端头像字段补丁已生效；小程序主客户头像显示仍需用户重新上传体验版后真机可见。

## 2026-06-22：个人资料设置 V1 补齐头像白块问题

- 背景：
  - 用户真机反馈“已经登录，但用户头像都是白色”，并怀疑是否因为还没有设置中心。
  - 微信小程序登录只稳定提供 openid，不会天然返回可用头像；此前前端虽已做彩色首字兜底，但用户没有入口修正昵称、电话和头像信息。
- 已完成：
  - 后端新增 `PATCH /api/auth/users/{user_id}/profile`。
  - 请求字段支持 `nickname/avatarUrl/phone`，昵称不能为空；保留正常 emoji，过滤坏掉的半截 surrogate 字符。
  - 小程序“我的”页的“编辑资料”和“设置中心”改为打开个人资料弹窗。
  - 弹窗支持编辑昵称、手机号、头像链接，并支持微信 `chooseAvatar` 选择头像；头像为空时继续使用彩色首字兜底，避免白色头像。
  - 保存成功后同步更新后端、`app.globalData.currentUser` 和本地 `currentUser` 缓存。
- 已验证：
  - 个人资料专项后端测试：4 passed。
  - 后端全量测试：129 passed。
  - 后端 compileall：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-001727-profile-settings`。
  - 公网验证：`/health` 200；`PATCH /api/auth/users/user_missing_profile/profile` 返回业务级 404“用户不存在”，说明新路由已上线。
- 注意：
  - 小程序前端弹窗需要用户重新上传体验版后才能看到。
  - `chooseAvatar` 选择到的本地临时头像路径适合作本机展示；后续如需跨设备稳定头像，应补头像上传/托管能力。

## 2026-06-22：经营看板总数下钻到具体访客

- 背景：
  - 用户反馈“打开、访客、看资料、咨询”四个总数看得见，但不知道对应哪个展示页、哪次分享、哪个客户。
  - 之前展示页行和分享来源更像报表，不能直接把用户带到“这一路来的具体人”。
- 已完成：
  - 经营看板顶部四个指标改为下钻入口：
    - 打开：切到访客详情，只看打开过展示页的访客。
    - 访客：切到全部访客。
    - 看资料：切到看过资料的访客。
    - 咨询：切到咨询、留资或预约相关客户。
  - “按展示页拆解”每行点击后，切到该展示页带来的访客列表。
  - “分享来源”每行点击后，切到该分享批次带来的访客列表。
  - 访客详情页顶部新增“当前筛选”提示卡，明确当前是在看总访客、某个展示页、某次分享、看资料访客或咨询客户。
  - 访客详情页的小统计改为当前筛选下的客户数、看资料次数和咨询次数，下面列表只展示对应具体人。
- 已验证：
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮是小程序前端交互改动，不需要后端部署。
  - 需要重新上传体验版后真机确认：点四个总数、展示页行、分享来源行，是否都能筛到具体访客/客户。

## 2026-06-22：客户库和待联系补当前筛选提示

- 背景：
  - 用户指出客户库和待联系也需要从总看板递进到来源、阶段和具体客户。
  - 之前两页已有“来源资料 / 处理阶段 / 优先处理”等分组，但点完来源或筛选后，页面没有明显告诉用户“当前正在看哪一组人”。
- 已完成：
  - 客户库新增“当前筛选”提示卡：
    - 显示当前筛选组合，例如来源资料、处理阶段、意向等级、联系方式、活跃状态、标签和搜索关键词。
    - 显示当前结果人数。
    - 提供“全部客户”按钮一键清空筛选。
    - 所有筛选入口统一走 `commitCustomerView`，避免列表和提示不同步。
  - 待联系新增“当前筛选”提示卡：
    - 点今日、逾期、待联系、已联系、已归档、来源资料后，都会显示当前筛选条件和线索数量。
    - 来源资料筛选写入 `activeSourceFilter`，状态/时间筛选会继续尊重来源条件。
    - 提供“回到待联系”按钮，一键恢复默认待处理视图。
- 已验证：
  - `node --check miniprogram/pages/customers/index.js`：通过。
  - `node --check miniprogram/pages/leads/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮是小程序前端体验改动，不需要后端部署。
  - 需要重新上传体验版后真机确认客户库、待联系点击来源/阶段后的提示卡和列表是否一致。

## 2026-06-22：头像选择改为上传托管后再保存

- 背景：
  - 个人资料设置 V1 已能选择头像，但微信 `chooseAvatar` 可能返回 `wxfile://` 或本机临时路径。
  - 如果把临时路径直接保存到后端，换设备、重开小程序或别的页面读取时，仍可能出现白色头像。
- 已完成：
  - 小程序“我的 -> 编辑资料”保存时，如果头像是本机临时路径，会先调用已有 `/api/uploads/asset` 上传成生产可访问 URL，再保存用户资料。
  - 如果用户手动输入头像链接，必须是 `http/https`；否则前端提示“头像链接需以 https:// 开头”。
  - 后端 `PATCH /api/auth/users/{user_id}/profile` 增加保护：非 `http/https` 头像地址直接返回 400“头像地址必须是 HTTPS 地址”。
  - 经营看板、客户库、待联系、订单中心、我的页的头像兜底规则补充过滤 `wxfile/file/blob/tmp` 路径，避免旧脏数据导致白头像。
- 已验证：
  - 头像资料专项后端测试：3 passed。
  - 后端全量测试：130 passed。
  - 后端 compileall：通过。
  - 小程序相关页面 JS 检查：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-003526-profile-avatar-upload-guard`。
  - 公网验证：`/health` 200；真实测试用户传 `wxfile://tmp_avatar.jpg` 返回 400“头像地址必须是 HTTPS 地址”。
- 注意：
  - 小程序端自动上传头像属于前端变化，需要重新上传体验版后真机测试。
  - 后续如果需要裁剪头像或压缩策略更细，可继续复用 `/api/uploads/asset`。

## 2026-06-22：订单/接龙页补当前筛选提示

- 背景：
  - 用户要求最终落实到成交的人、问询的人、下单的具体人。
  - 商家订单中心已有状态分组和来源商品分组，但点来源商品后列表变化不够明确，容易不知道当前正在看哪组买家。
- 已完成：
  - 订单/接龙页新增 `activeSourceFilter` 和 `activeViewText`。
  - 状态筛选和来源商品筛选可叠加，列表只展示当前来源/状态下的具体买家。
  - 页面新增“当前筛选”提示卡，显示当前来源/状态和订单数量。
  - “来源商品”右侧“全部”可一键恢复全部订单。
- 已验证：
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮是小程序前端体验改动，不需要后端部署。
  - 需要重新上传体验版后真机确认：订单页点状态、来源商品后，提示卡和下面买家列表是否一致。

## 2026-06-22：经营看板动作流水跟随当前筛选

- 背景：
  - 经营看板“访客详情”已能按总数、展示页、分享来源筛具体访客。
  - 但动作流水仍显示全量客户动作，会让用户误以为当前筛选没有生效。
- 已完成：
  - 新增 `visibleLatestActions`，根据当前可见访客过滤客户动作。
  - 访客详情页的“动作流水”改为展示当前筛选下相关动作。
  - 笔记数据、客户资料等全局视图仍保留全量客户动作，不影响总览。
- 已验证：
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮是小程序前端体验改动，不需要后端部署。
  - 真机回归时需要在展示页/分享来源筛选后，看访客列表和动作流水是否同源。

## 2026-06-22：头像 URL 统一只接受 HTTPS

- 背景：
  - 上一轮后端错误提示写的是“头像地址必须是 HTTPS 地址”，但实际规则仍允许 `http://`。
  - 微信小程序真机对非 HTTPS 图片加载不稳定，继续允许 HTTP 头像会再次造成白头像。
- 已完成：
  - 后端 `PATCH /api/auth/users/{user_id}/profile` 改为只接受 `https://` 头像 URL。
  - 新增测试覆盖 `http://` 头像被拒绝。
  - 小程序“我的”、经营看板、客户库、待联系、订单中心的头像兜底也改为只认 `https://`，其它协议统一显示彩色首字头像。
- 已验证：
  - 头像资料专项后端测试：4 passed。
  - 后端全量测试：131 passed。
  - 后端 compileall：通过。
  - 小程序相关页面 JS 检查：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260622-004456-profile-avatar-https-only`。
  - 公网验证：`/health` 200；真实测试用户传 `http://cdn.example.test/avatar.png` 返回 400“头像地址必须是 HTTPS 地址”。

## P0 收口：另一个手机打开分享页前的代码侧检查

- 用户反馈“另一个手机打开”问题仍不确定，要求先把 P0 全部检查处理一遍，再重新真机测试。
- 已对照 `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md` 和 `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md` 做 P0 复核。
- 发现并修复两个前端打开风险：
  - 历史中转页 `pages/showcase-share/index` 文件存在但未注册到 `app.json`，若旧分享路径命中该页会直接打不开；已注册该页面。
  - 分享中转页 `pages/showcases/index` 同时承担后台列表和客户中转，未登录客户打开分享时存在被 `onShow` 登录检查抢先送去登录页的风险；已增加实例级 `openingSharedShowcase` 标记，确保分享中转先跳公开展示页。
- 本地验证：
  - 后端全量测试：126 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
- 生产接口检查：
  - `/health` 200。
  - `/api/auth/mock-login` 返回 403“测试登录已关闭”。
  - 不存在公开展示页返回业务 404“展示页不存在或未发布”。
  - 不存在展示页事件接口返回业务 404“展示页不存在或未发布”。
  - 不存在用户经营看板返回业务 404“用户不存在”。
- 生产正向闭环验证（独立演示用户 `user_836a4a8986`，不写真实用户数据）：
  - 已发布展示页公开接口 200，包含 4 条资料。
  - `share/view/note_click/phone_click/wechat_copy` 五类事件写入成功。
  - analytics 能按本次 `shareId` 聚合打开、资料点击和咨询。
  - 经营看板能看到同一 `shareId` 的分享来源聚合。
- 注意：
  - 本轮两个打开风险是小程序前端改动，必须重新上传/预览体验版后，另一个手机测试才会生效。
  - 若新版仍打不开，下一步优先看微信开发者工具生成的实际分享路径、体验成员权限和被分享手机打开时的页面报错，不再盲改后端。

## P0 修复：单条资料客户页分享到另一个手机打不开

- 用户提供真实分享路径：`pages/note-preview/index.html?id=note_730305fd2e`。
- 定位结论：
  - 这次不是展示页分享，而是单条资料客户页 `pages/note-preview/index?id=...`。
  - `note-preview` 旧逻辑在 `onShow` 中没有登录用户就 `wx.reLaunch("/pages/login/index")`。
  - 另一个手机打开分享通常没有发布者登录态，因此会被踢到登录页或无法显示资料。
  - 后端旧单条资料接口 `/api/notes/{id}?ownerUserId=...` 也只允许 owner 查看，不能给客户公开访问。
- 已修复：
  - 新增后端公开接口 `GET /api/notes/public/{note_id}`，允许读取 active 非删除资料。
  - 保留原 owner 私有接口权限：非 owner 访问 `/api/notes/{id}?ownerUserId=...` 仍返回 403。
  - `pages/note-preview` 改为：有登录用户时用 owner 私有接口；无登录用户时用公开接口。
  - `note-preview` 的留资、预约、下单/接龙支持匿名 `anonymousId` 提交；站内消息仍提示登录后使用。
  - 小程序 API 增加 `fetchPublicNote`。
  - 新增后端测试 `test_public_note_preview_does_not_require_owner`。
- 验证：
  - 专项测试：2 passed。
  - 后端全量测试：127 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
  - 已部署生产后端。
  - 公网验证：
    - `/api/notes/public/note_730305fd2e` 返回 200。
    - `/api/notes/note_730305fd2e?ownerUserId=user_not_owner_check` 返回 403，owner 权限仍有效。
    - `/api/notes/note_730305fd2e/customer-actions/config?anonymousId=...` 返回 200。
- 注意：
  - 后端公开接口已生效。
  - `note-preview` 前端免登录打开属于小程序代码变化，必须重新上传/预览体验版后，另一个手机才会看到修复效果。

## 补充：极简笔记入口方案 B 与图片只存图修正

- 用户确认底部“添加”应回到 flomo 式极简笔记器，而不是三步资料向导；普通笔记直接保存，业务资料用高置信/候选识别给强提示。
- 已调整 `pages/resource-create`：
  - 输入区下方显示方案 B 白色业务卡片，不再使用弹层遮罩，也不复用黑色“已保存”条。
  - 高置信房源/商品显示“已帮你整理成房源/商品草稿”，按钮进入对应 `note-edit` 工作台。
  - 中低置信但明显像房源/团购的内容显示“这条像房源资料 / 这条像商品团购”，用户点击后先确认类型再进工作台。
  - 普通笔记仍只显示轻量“已保存 / 查看详情”，保持极简入口。
- 已确认图片按钮不应触发 OCR：前端上传走 `/api/notes/image-capture`，只保存图片资料并进入编辑页；OCR 仍保留在图片资料编辑页由用户后续手动触发。
- 生产侧已处理图片上传失败的 Nginx 体积限制：`client_max_body_size 50M`，并用约 5.9MB 图片公网验证不再返回 HTML 413。
- 验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
- 注意：
  - 这次小程序页面变化必须在微信开发者工具重新上传/预览体验版后，真机才会看到。
  - 如果输入纯普通文本，不出现业务卡片是预期；只有识别为房源/团购或候选业务资料时才出现方案 B 提示。

## 修复：朋友圈口语房源文案漏判为普通笔记

- 用户提供两段真实房源文案：
  - `加州郡府 毛坯 小高层 双阳夹厅三居室 ... 126平米 88万 ...`
  - `龙悦和府 / 钢四小 / 乌兰小学 / 二十九中 / 网签即可入学 ...`
- 确认问题：
  - 原后端高置信房源规则偏向“字段: 值”格式，要求命中足够结构化字段。
  - 朋友圈房源文案常是口语串联，虽有面积、总价、楼盘、户型、装修、学校、入学、电话等强信号，但字段数不足时会降成普通笔记。
  - 前端本地兜底也漏了 `平米/万/小高层/阳台/入学/小学/中学/南北通透/独梯独户` 等信号。
- 已修复：
  - 后端 `content-to-note` 增加朋友圈口语房源强信号，房源信号足够密集时可高置信识别为 `property_listing`，不再死卡结构化字段数量。
  - 前端极简笔记入口补同类本地兜底识别，避免明显房源只出现“已保存”条。
  - 新增后端测试 `test_quick_capture_routes_informal_property_posts_as_high_confidence`，直接覆盖用户给的两段原文。
- 验证：
  - 专项 quick-capture 测试：4 passed。
  - 后端全量测试：124 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
  - 已部署生产后端；容器内规则验证两段文案均返回 `property_listing high score=10`，公网 `/health` 正常。
- 注意：
  - 生产后端识别规则已生效。
  - 小程序“方案 B 白色整理卡片”属于前端页面变化，需要重新上传/预览体验版后真机才会看到。

## 修复：图片资料入口与 OCR 按钮样式

- 用户反馈：
  - 图片资料详情页里的“识别图片文字”按钮太大，且深色大块不符合当前项目视觉。
  - 底部笔记入口上传图片后不应直接进入 OCR 资料详情页，应只保存图片。
- 已调整：
  - `pages/note-edit` 的 OCR 按钮改成小胶囊，文案缩短为“识别文字 / 重新识别”，颜色使用微信绿。
  - 图片识别状态文案从“OCR 引擎未配置”弱化为“识别服务未开启”，减少技术感。
  - `pages/resource-create` 上传图片后只显示“图片已保存”反馈，不再自动跳转到资料详情页。
  - `pages/notes` 的“保存图片”入口上传后刷新列表，不再自动进入 OCR 详情页。
- 验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
- 注意：
  - 图片资料仍可在资料详情页手动点击“识别文字”。
  - 该改动属于小程序前端，需要重新上传/预览体验版后真机可见。

## 修复：22:08 左右直接发文字保存失败

- 用户反馈 22:08 左右在笔记入口直接发送文字保存失败。
- 线上日志定位：
  - `/api/notes/quick-capture` 返回 500。
  - Postgres 写入时报 `UnicodeEncodeError: surrogates not allowed`。
  - 根因是输入文本里带了半截 emoji / Unicode surrogate（日志中为 `\ud83d`），这类字符不能被 UTF-8 正常写入数据库。
- 已修复：
  - 新增 `app/services/text_safety.py`，递归移除非法 Unicode surrogate。
  - `create_quick_note_capture` 和 `create_manual_note_draft` 在入口清洗 `rawText/title`，避免接口返回体继续携带非法字符。
  - Postgres `_upsert_payload` 入库前递归清洗 payload，防止其它来源同类字符把保存打崩。
  - JSON 本地仓库保存也做同样清洗。
  - 新增回归测试 `test_quick_capture_strips_invalid_unicode_surrogates`。
  - 补充 `test_quick_capture_keeps_valid_emoji`，确认完整 emoji（如 `🔥`、`☎️`）会原样保存，只有半截 surrogate 会被清理。
- 验证：
  - 专项测试：3 passed。
  - 后端全量测试：125 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序全量 JSON 解析：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，公网用带 `\uD83D` 的请求验证：返回业务级 404“用户不存在”，不再 500；生产日志无异常堆栈。

## 补充：分享追踪 V1 代码侧 P0 边界加固

- 用户反馈真机分享回归测试多次未成功，本轮不继续卡在真机分享链路，先向下推进代码侧收口。
- 已对照 `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md` 和 `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md` 复核范围。
- 已补后端回归：
  - `test_mock_login_can_be_disabled`：确认 `ALLOW_MOCK_LOGIN=false` 时 `/api/auth/mock-login` 返回 403 和“测试登录已关闭”。
  - `test_showcase_builder_create_publish_public_and_archive`：补充草稿展示页和下架展示页调用 `/events` 均返回“展示页不存在或未发布”。
  - `test_create_note_demo_data_for_owner`：补充同账号下非演示资料和非演示展示页在 `POST /api/notes/demo-data/cleanup` 后必须保留，防止正式上线前清理测试数据误删真实数据。
- 验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q -k 'create_note_demo_data_for_owner or mock_login_can_be_disabled or showcase_builder_create_publish_public_and_archive'`：3 passed。
  - `python3 -m compileall backend/app backend/tests -q`：通过。
  - `git diff --check`：通过。
- 注意：
  - 本轮没有继续修改小程序分享路径，也没有调用生产清理接口。
  - 真机分享问题仍留作后续人工/版本链路排查，不作为本轮继续开发的阻塞点。

## 补充：经营看板生产部署与服务器演示数据验证

- 用户提供腾讯云部署文档：`/Users/yiyi/Desktop/Desktop/myprojects/cloud_tencent/cloud_tencent.md`。
- 已把腾讯云生产部署约定写入 `AGENTS.md`：
  - 生产服务器：`ubuntu@81.70.84.35`
  - 项目目录：`/home/ubuntu/teamBuy`
  - 域名：`https://teambuy.lifelove.top`
  - SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`
- 已按该方式完成生产部署：
  - 部署前备份：`/home/ubuntu/teamBuy-deploy-backups/20260621-081845-dashboard-closeout`
  - 同步后端 `backend/app/`、`backend/tests/`、`backend/requirements.txt`、`backend/Dockerfile`
  - 完整重建并重启 `teambuy-backend`
- 公网验证：
  - `/health` 返回 200。
  - `/api/dashboard/business?ownerUserId=user_test` 返回业务级“用户不存在”，不再是路由级 404。
  - `/api/showcases?ownerUserId=user_test` 返回业务级“用户不存在”，不再是路由级 404。
  - `/api/orders?userId=user_test&role=seller` 返回 200 空列表。
- 演示数据说明：
  - 这不是前端 mock，而是通过服务器接口写入真实后端数据。
  - 已创建独立演示用户 `user_836a4a8986`，并通过 `POST /api/notes/demo-data` 写入 4 条资料、1 个展示页、5 条展示页事件、留资/预约和 1 条商品接龙。
  - 经营看板真实聚合返回：打开 2、访客 2、看资料 1、咨询 2、订单 1。
- 已新增复测报告：`docs/qa/客户数据看板_复测与回归报告.md`。
- 下一步：
  - 用户需要在微信开发者工具手动上传包含最新小程序代码的体验版。
  - 真机确认“访客线索 -> 经营看板”的视觉、Tab 切换和跳转。

## 补充：生产真实账号写入经营看板测试数据

- 用户确认生产库可写入假数据用于真机测试，正式上线前再清理。
- 已确认真实测试账号：
  - `userId`: `user_25ec00a0f0`
  - `openid`: `oPSh564GCACiIkZxFPV5VWVgdbds`
- 已通过后端接口 `POST /api/notes/demo-data?ownerUserId=user_25ec00a0f0` 写入服务器真实数据：
  - 4 条资料。
  - 1 个已发布演示展示页。
  - 5 条展示页行为事件。
  - 4 条客户动作，包含留资、预约和接龙。
- 写入后公网经营看板验证：
  - 展示页打开：2。
  - 访客：2。
  - 看资料：1。
  - 咨询：2。
  - 待联系线索：2。
  - 客户资料：4。
  - 订单/接龙：3。
  - 展示页总数：13，其中已发布 5。
- 注意：
  - 这批数据属于生产真实账号的测试假数据，正式上线前需要清理。

## 补充：经营看板 UI 对齐参考稿

- 用户反馈真机经营看板页面和参考图差异明显，缺少微信头像感，UI 也不是同一套视觉。
- 已确认原因：
  - 当前实现是“功能型看板”，没有按用户发的四张参考图做高保真结构。
  - 演示数据里的头像 URL 使用 `example.com` 测试域名，真机小程序通常不会加载，因此看起来没有头像。
- 已沉淀项目规则：
  - 已在 `AGENTS.md` 增加“UI 参考稿与实现一致性要求”。
  - 已在 `docs/pitfalls.md` 记录“不能把高保真参考图做成简化功能版”。
  - 已在 `docs/decisions.md` 明确“已有 UI 参考图必须作为验收标准”。
- 已调整 `miniprogram/pages/business-dashboard/`：
  - 四个 Tab 分别改成更接近参考图的页面结构：展示页效果、访客详情、笔记数据、客户资料。
  - 增加访客列表、资料点击排行、浏览轨迹、客户旅程、跟进记录等视觉模块。
  - 增加头像占位、电话脱敏、时间格式、状态文案等格式化。
  - 对 `example.com` 和默认测试头像做兜底，避免真机显示空白头像。
- 验证：
  - `node --check miniprogram/pages/business-dashboard/index.js` 通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。

## 补充：经营看板联系方式与按钮样式修正

- 用户反馈：
  - 访客详情底部“添加跟进 / 备注”按钮文字偏上，需要上下居中。
  - 经营看板是用户自己的 SCRM 工作台，手机号和微信号不应脱敏。
  - 所有展示手机号和微信号的位置都应提供外呼和复制按钮。
- 已调整：
  - `pages/business-dashboard/index.js` 去掉电话脱敏，改为完整展示 `displayPhone/displayWechat`。
  - 增加 `handleCallPhone` 和 `handleCopyWechat`。
  - `pages/business-dashboard/index.wxml` 在访客轨迹、笔记数据、客户资料、客户旅程、跟进记录等位置补充电话/微信展示和外呼/复制按钮。
  - `pages/business-dashboard/index.wxss` 修正底部按钮、复制/外呼按钮的 `display:flex`、`align-items:center`、`line-height` 和 `padding`，避免文字偏上。
- 已沉淀规则：
  - `docs/decisions.md` 增加“经营看板和 SCRM 自有客户视图不默认脱敏”。
  - `docs/pitfalls.md` 增加“自有 SCRM 视图不要给联系方式设障碍”。
- 验证：
  - `node --check miniprogram/pages/business-dashboard/index.js` 通过。
  - 小程序全量 JS 检查通过。
  - 小程序 JSON 解析通过。
  - `git diff --check` 通过。

## 本次收口：经营看板、线索闭环、商品轻订单和统一回归

背景：

- 用户确认把后续计划 1-4 一次收口：上线收口、P0 回归、线索闭环、商品/团购轻订单体验。
- 用户要求经营看板不要整块放在“我的”页，主入口放到“访客线索”，并统一测试。

完成内容：

- 生产状态复核：
  - 起初公网 `GET https://teambuy.lifelove.top/api/dashboard/business?ownerUserId=user_test` 返回路由级 `404 {"detail":"Not Found"}`，说明经营看板后端未部署。
  - 用户补充腾讯云 SSH key 后，已完成生产部署；当前该接口返回业务级“用户不存在”，不再是路由级 404。
- 经营看板入口收口：
  - “我的”页不再自动加载经营看板，不再展示整块经营看板。
  - 底部 Tab “访问记录”调整为“访客线索”，访客线索页顶部新增“经营看板”入口。
  - 经营看板最新客户动作支持点击：订单/接龙进入订单详情，留资/预约进入线索详情，其它动作进入笔记客户动作页。
  - 资料点击排行支持点击进入对应笔记客户动作页。
- 线索闭环收口：
  - 继续保持规则：匿名访客只统计，不强行进入客户库；只有留资/预约等真实动作才投影到 `LeadReminder`。
  - 经营看板最新动作返回 `targetType / leadReminderId / orderActionId`，让前端明确进入可处理页面。
- 商品/团购轻订单收口：
  - 后端订单列表新增 `summary`：全部、待处理、已联系、已完成、已取消、接龙、下单。
  - 订单行新增 `actionKindText/statusGroup`，区分“下单”和“接龙”，并按买家/商家显示状态文案。
  - 商家订单页新增状态筛选：全部、待处理、已联系、已完成、已取消。
  - 商品接龙/下单名单页新增状态处理按钮：已联系、已完成、取消；状态直接复用订单状态接口。
  - 订单详情页新增“类型”行，明确展示下单或接龙。
- 测试补齐：
  - 后端测试补充经营看板动作目标断言、订单汇总和状态变更断言。
  - 临时创建 `/tmp/teambuy-py312-test` Python 3.12 测试环境，安装不含 PaddleOCR 的后端测试必要依赖。

验证：

- `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q`：76 passed。
- `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q`：113 passed。
- 小程序全量 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend/app backend/tests`：通过。
- `git diff --check`：通过。

仍需人工/生产确认：

- 当前生产后端未部署新增 `/api/dashboard/business`，真机经营看板仍会显示空面板。
- 需要有服务器 SSH 权限的环境部署生产后端后，再重新上传小程序体验版并做真机 P0 回归。
- 小程序体验版上传仍按项目约定由用户在微信开发者工具手动完成。
- 已补上线执行文档：`docs/qa/客户数据看板_上线部署与回归清单.md`，包含生产部署范围、公网接口验证和真机回归清单。
- 已补服务器端部署命令模板：`docs/deploy/dashboard-closeout-server-commands.sh`，用于有 SSH 权限的环境执行备份、文件检查、重建重启和公网验证。

## 本次补充：客户数据关系文档与经营看板组件

背景：

- 用户确认真机展示页基础可用，下一步希望整理每个笔记、展示页、客户访客、下单/接龙和成交强数据之间的关系。
- 用户要求先把关系做成文档和组件化方案，再一次性开发并统一验收。
- 用户确认“行为强度分层”是内部判断概念，不要在用户 UI 中展示。

完成内容：

- 新增架构文档：`docs/stage2-docs/14-customer-data-dashboard-architecture.md`。
- 新增测试清单：`docs/qa/客户数据看板_测试清单与验收标准.md`。
- 新增自测报告：`docs/qa/客户数据看板_Codex自测报告.md`。
- 新增验收报告：`docs/qa/客户数据看板_验收报告.md`，结论为“需要人工确认”。
- 后端新增 `GET /api/dashboard/business?ownerUserId=xxx`：
  - 聚合展示页真实事件 `ShowcaseEvent`。
  - 聚合笔记客户动作 `CustomerAction`。
  - 聚合待联系客户 `LeadReminder`。
  - 商品下单/接龙继续复用 `order-intent / relay-intent`，不默认进入线索。
- 小程序新增可复用组件 `miniprogram/components/business-dashboard/`。
- 小程序新增经营看板详情页 `miniprogram/pages/business-dashboard/index`，包含 4 个看板 Tab：展示页效果、访客详情、笔记数据、客户资料。
- “我的”页不再展示整块经营看板，只在“访客线索”区域保留小入口。
- 底部 Tab 的“访问记录”调整为“访客线索”，页面顶部新增“经营看板”入口，点击进入经营看板详情页。
- 线索、订单/接龙、客户库、展示页管理保留为处理区入口，只在经营看板详情页内通过按钮进入。
- 新增后端测试代码 `test_business_dashboard_aggregates_real_customer_data`，覆盖 owner 隔离、匿名访客、展示页点击排行和商品接龙不污染线索。

验证：

- `python3 -m compileall backend/app backend/tests`：通过。
- 小程序全量 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `git diff --check`：通过。
- `python3 -m pytest backend/tests/test_app.py -q` 未执行成功：系统 Python 缺少 pytest。
- `./.venv/bin/python -m pytest backend/tests/test_app.py -q` 未执行成功：`.venv` 为 Python 3.9.6，不支持 `dataclass(slots=True)`。
- Codex Python 3.12 未执行成功：缺少 pytest；临时挂载 `.venv` site-packages 后 `pydantic_core` 二进制不兼容。

## 本次修复：我的页经营看板接口未部署导致整页加载失败

背景：

- 用户在 2026-06-21 07:20 左右真机测试时，“我的”页提示“我的数据加载失败”。
- 公网验证 `GET https://teambuy.lifelove.top/api/dashboard/business?ownerUserId=user_test` 返回路由级 `404 {"detail":"Not Found"}`。
- 小程序“我的”页此前使用 `Promise.all` 同时加载旧资源统计和新增经营看板，新经营看板接口失败会让整个页面进入失败分支。

完成内容：

- “我的”页基础资源统计、经营看板、消息未读改为分开加载。
- 基础资源统计失败时才提示“我的数据加载失败”。
- 经营看板接口失败时降级为空看板和默认入口，不影响原有“我的”页功能。
- 消息未读加载失败时降级为 0，不影响页面。

验证：

- 当时公网确认生产 `/api/dashboard/business` 为路由级 404，根因成立；后续已通过腾讯云部署修复，当前不再是路由级 404。
- 小程序全量 JS 静态检查：通过。
- 小程序 JSON 解析：通过。
- 后端 compileall：通过。
- `git diff --check`：通过。
- 生产 SSH 当时不可用；用户补充 key 后已完成后端部署。

## 本次补充：展示页真实效果追踪与轻量看板

背景：

- 用户真机测试展示页基础体验基本可用。
- 用户确认四模板多尺寸视觉回归、商品/房源混合资料模板表现需要真实上线反馈，当前无法拍板。
- 用户明确展示页真实浏览统计、谁看了、谁咨询了、展示页效果如何很重要，要求按此方向开发。

完成内容：

- 后端新增 `ShowcaseEvent` 事件模型，记录展示页真实事件：
  - `view`：客户打开展示页。
  - `note_click`：客户点击展示页内资料。
  - `phone_click`：客户点击电话咨询。
  - `wechat_copy`：客户复制微信。
  - `share`：客户触发展示页分享。
- 后端新增展示页事件存储能力，兼容本地 mock 和 PostgreSQL：
  - `showcase_events` 状态集合/表。
  - 按展示页、owner、事件类型、访客索引。
  - 删除展示页时同步删除展示页事件。
- 后端新增接口：
  - `POST /api/showcases/{id}/events`：客户页上报真实事件，只接受已发布展示页。
  - `GET /api/showcases/{id}/analytics?ownerUserId=xxx`：发布者查看展示页效果。
- 展示页列表接口返回轻量 `analytics`，列表可直接展示效果摘要。
- analytics 聚合内容：
  - 打开 PV。
  - 访客 UV，区分登录访客和匿名访客。
  - 资料点击数。
  - 电话点击数。
  - 微信复制数。
  - 分享数。
  - 咨询点击数 = 电话点击 + 微信复制。
  - 最近访客。
  - 最近动作。
  - 资料点击排行。
- 小程序客户展示页已接入埋点：
  - 发布者预览不记录。
  - 真实公开页打开记录 `view`。
  - 点资料记录 `note_click`。
  - 电话咨询记录 `phone_click`。
  - 复制微信记录 `wechat_copy`。
  - 触发分享记录 `share`。
- 小程序展示页列表增加轻量效果看板：
  - 卡片显示 `打开 X · 访客 Y · 咨询 Z`。
  - 已发布展示页的 `更多` 菜单新增 `效果`。
  - 展开后显示打开、访客、看资料、咨询四项指标。
  - 展示最近登录访客和匿名访客数量。
  - 展示资料点击排行。
- 开发文档和测试清单已更新：
  - 真实效果追踪列入本阶段 P1。
  - 四模板多尺寸视觉回归、商品/房源混合模板策略列为 P2 暂缓项，等真实上线反馈再开发。

验证：

- 小程序全量 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- 后端 Python 3.12 编译检查：通过。
- `git diff --check`：通过。
- 后端 pytest 未执行：当前 Codex runtime 缺少 `pytest`；项目 `.venv` 仍是 Python 3.9.6，无法运行使用 `dataclass(slots=True)` 的后端代码。

## 本次补充：展示页列表操作减负与客户页去假数据

背景：

- 用户真机截图反馈展示页列表仍然被按钮区挤压变形。
- 用户指出四套展示页模板里存在无法证明的营销数字和按钮，例如服务客户 `328+`、成交案例、好评率 `98%`，客户看到后可能产生质疑。
- 用户确认不希望为这些虚假数据再增加编辑功能，避免把展示页做复杂。

完成内容：

- 展示页列表卡片操作区改为一个主操作 + `更多`：
  - 已发布展示页主操作为 `发给客户`。
  - 草稿/下架展示页主操作为 `编辑`。
  - `预览 / 删除` 等低频操作进入 `更多` 操作菜单。
- 删除展示页继续保留确认弹窗，不再作为列表卡片上的大红按钮常驻展示。
- 列表按钮区宽度从双列大按钮收窄为单列轻按钮，减轻对标题、简介和状态行的挤压。
- 客户展示页移除虚假营销统计：
  - 不再用资料数量乘出 `128/328` 等假服务客户数。
  - 不再固定展示 `98%` 好评率。
  - 品牌名片不再展示虚构客户评价卡。
- 模板统计改为真实且无需用户配置的信息：
  - 精选资料/房源/好物数量。
  - 最近更新时间。
  - 咨询方式：电话/微信、电话咨询、微信咨询或可分享。
- 清单目录模板移除不可用的搜索按钮和筛选按钮，改为资料目录 + 数量提示；分类 tab 视觉改成静态标签。
- 橱窗和品牌模板的 `更多/查看更多` 改为 `共 X 条`，避免客户误认为有可点击入口。

验证：

- 小程序全量 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- 后端 Python 3.12 编译检查：通过。
- `git diff --check`：通过。

# 2026-06-20

## 本次补充：展示页按标签分组和编辑体验收口

背景：

- 用户反馈展示页卡片显示 4 个标签时会被挤压变形。
- 用户确认“展示方式”前期太复杂，展示页只保留默认按标签分组。
- 用户反馈删除展示页报“方法不允许”，以及电商/商品分类下自动生成信息仍出现房源标题。
- banner 图片配置不应要求用户输入图片地址，只需要看到缩略图并能换图。

完成内容：

- 客户展示页资料卡标签统一改为最多 4 个的等分网格：
  - 1 个标签占满一行。
  - 2 个标签两等分。
  - 3 个标签三等分。
  - 4 个标签四等分。
- 标签区统一预留 `padding/margin`，并针对精选橱窗、朋友圈长页、清单目录、品牌名片四种模板分别适配卡片宽度，避免文字挤压导致卡片变形。
- 编辑展示页删除“展示方式”配置入口，不再给用户暴露“不分组 / 按资料类型 / 按自定义分组”等选择；保存时固定写入 `displayConfig.groupBy=tag`。
- 自动生成信息跟随分类：
  - 房产/房源默认生成“我的房源精选”和房源说明。
  - 商品/团购/电商/好物默认生成“我的好物精选”和商品说明。
  - 其它分类生成“分类名精选”和通用资料说明。
  - 用户已经手动改过标题/简介时不强行覆盖。
- banner 配置区域只保留图片缩略图和“换图片”按钮，已移除“banner 图片地址”输入框。
- 删除展示页增加小程序友好的 `POST /api/showcases/{id}/delete` 接口；前端删除按钮改用 POST，兼容部分环境不允许 DELETE 方法的问题。
- 后端展示页测试同步改为覆盖 `POST /delete` 和固定标签分组。

验证：

- 小程序全量 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- 后端 Python 3.12 编译检查：通过。
- `git diff --check`：通过。
- 后端展示页 pytest 专项未执行：当前 Codex runtime 缺少 `pytest`；项目 `.venv` 仍是 Python 3.9.6，无法运行使用 `dataclass(slots=True)` 的后端代码。

## 本次补充：展示页模板化低操作流程

背景：

- 用户反馈展示页基本功能能实现，但操作工作量仍偏大。
- 用户明确建议：展示页直接内置 4 个标准模板；新建时先展示分类类型，再在分类笔记卡片上选择是否加入展示页；默认房产分类，默认该分类资料全部进入展示页；第一、第二个模板 banner 默认取分类第一条资料图；联系方式、微信头像、电话尽量从已有账号和笔记中自动带出。

完成内容：

- 新增模板配置工具：`miniprogram/utils/showcase-templates.js`。
- 内置 4 个标准模板，名称和副标题固定：
  - `精选橱窗`：适合日常发客户，主打精选、品质和快速联系。
  - `朋友圈长页`：像一篇漂亮分享页，适合讲合集故事、发朋友圈或客户群。
  - `清单目录`：适合资料很多时筛选、对比、快速点详情。
  - `品牌名片`：强调人和信任，适合中介、顾问、团长建立专业感。
- 展示页编辑页重构为低操作三步：
  - 选择展示模板。
  - 选择分类类型，默认优先 `房产`。
  - 在该分类笔记卡片上点 `加入 / 已加入`，新建时默认该分类全部加入展示页。
- 新建展示页会自动生成：
  - 展示页名称和分享标题。
  - 展示页简介，默认取模板副标题。
  - banner 图，默认取当前分类已选资料中的第一张图。
  - 联系电话，优先取当前用户手机号，再从已选笔记电话/联系字段推断。
- 联系方式自动填充补齐微信号：优先从已选笔记 `structuredData.wechat/contactWechat/weixin/wx` 推断。
- 新增可复用组件 `miniprogram/components/note-select-card/`，用于“笔记卡片 + 加入展示页”选择场景；展示页编辑页已改用该组件，后续专题、批量选择等场景可复用。
- 展示页发布时会保存发布者昵称和头像到 `contactConfig.ownerName/avatarUrl`，品牌名片模板可直接展示。
- 客户公开展示页已按模板产生不同视觉：
  - `精选橱窗`：偏橱窗精选。
  - `朋友圈长页`：大图长页叙事。
  - `清单目录`：紧凑列表。
  - `品牌名片`：顶部名片头像和信任感。
- 后端 `ShowcasePage.contactConfig` 允许保存 `ownerName/avatarUrl`。
- 生产后端已同步本次后端改动并重启，备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260620-221657-showcase-template-flow`；旧镜像备份标签：`teambuy-backend:before-showcase-template-flow-20260620`。

验证：

- 小程序相关 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- `git diff --check`：通过。
- 后端 Python 3.12 编译检查：通过。
- 生产公网 `/health`：通过。
- 生产公网展示页公开接口：仍为业务级 `展示页不存在或未发布`，说明路由在线。
- `.venv` 的 pytest 仍因 Python 3.9 不支持 `dataclass(slots=True)` 无法运行；本轮未完成 pytest 回归。

## 本次补充：修复展示页生产 Not Found 与自定义分组入口不清楚

背景：

- 用户反馈展示页显示 `no found`，并且不理解“展示方式”的四个选项；选择“自定义”后也没看到可编辑对象。
- 排查发现小程序当前 `apiBaseUrl` 指向生产 `https://teambuy.lifelove.top`，但生产 `/api/showcases` 仍返回路由级 `{"detail":"Not Found"}`，说明展示页后端接口尚未部署到生产。
- 自定义分组原本隐藏在每条已选资料下方的 `sectionTitle` 输入里，入口不够直观。

完成内容：

- 已将展示页后端代码同步到生产服务器，并重启生产 `teambuy-backend`。
- 生产完整 `docker compose build backend` 卡在 `apt-get update`，因此本次采用热修构建：先给旧镜像打备份标签 `teambuy-backend:before-showcases-20260620-1000`，再基于旧镜像叠加新的 `backend/app`、`backend/tests` 和 `requirements.txt` 生成新 `teambuy-backend` 镜像。
- 同步前生产备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260620-100050-showcases`。
- 公网复测：
  - `GET https://teambuy.lifelove.top/health` 返回 200。
  - `GET https://teambuy.lifelove.top/api/showcases?ownerUserId=user_test` 已从路由级 Not Found 变为业务级 `用户不存在`。
  - `GET https://teambuy.lifelove.top/api/showcases/public/test_showcase_not_exists` 已从路由级 Not Found 变为业务级 `展示页不存在或未发布`。
- 小程序构建页展示方式改为四个明确选项：
  - 不分组
  - 按资料类型
  - 按标签
  - 按自定义分组
- 当选择“按自定义分组”时，页面单独显示“自定义分组”编辑区，对象为已选入展示页的每条资料；每条资料可填写分组名称。
- 针对“展示页怎么给客户看 / 哪里发给客户”的反馈，已补显性分享入口：
  - 展示页列表中，已发布展示页显示“发给客户”。
  - 展示页编辑页发布后，底部显示“发给客户”。
  - 发布者预览展示页时，顶部显示“客户可见展示页 / 发给客户”。
- 分享路径统一为 `/pages/showcase-view/index?id=展示页ID`，客户打开后进入公开展示页，再从资料列表进入单条客户页。

验证：

- 小程序 `showcase-edit` JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- `git diff --check`：通过。
- 展示页后端专项测试：`3 passed`。
- 生产公网展示页路由验证：通过，已不再是接口未上线的 `Not Found`。
- 分享入口补充后再次验证：小程序全量 JS 静态检查通过，小程序 JSON 解析通过，`git diff --check` 通过。

## 本次补充：展示页构建器 V1 QA 验收

背景：

- 用户要求调用 AI 测试官 / 验收官 Skill，对展示页构建器 V1 基于开发文档、测试清单和 Codex 自测报告进行验收与回归。

完成内容：

- 已读取 `docs/stage2-docs/13-showcase-builder-v1.md`、`docs/qa/展示页构建器V1_测试清单与验收标准.md`、`docs/qa/展示页构建器V1_Codex自测报告.md`。
- 已复核展示页后端路由、service、schema、测试用例和小程序展示页相关页面。
- 新增验收报告：`docs/qa/当前项目_验收报告m2.md`。
- 验收结论为“需要人工确认”：后端与静态检查通过，但小程序构建页保存发布、客户页点击资料进入单条资料页尚未在微信开发者工具或真机中确认。
- 发现 1 个 P2 文档偏差：测试清单 P0-08 写 `note-preview?noteId=xxx`，实际实现和目标页使用 `id=xxx`；建议修正文档或兼容参数。

验证：

- 后端编译检查：通过。
- 小程序全量 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- `git diff --check`：通过。
- 后端全量测试：`112 passed`。

## 本次补充：P1 展示页构建器 V1

背景：

- P0 主链路基本闭环后，下一阶段优先进入“展示页构建器 V1”。
- 展示页目标是让发布者从资料库勾选多条资料，配置店名、简介、banner、联系方式并生成可分享的小程序展示页。

完成内容：

- 新增开发文档：`docs/stage2-docs/13-showcase-builder-v1.md`。
- 新增测试清单：`docs/qa/展示页构建器V1_测试清单与验收标准.md`。
- 新增自测报告：`docs/qa/展示页构建器V1_Codex自测报告.md`。
- 后端新增 `ShowcasePage` / `ShowcaseItem` 模型和仓储能力。
- 后端新增 `/api/showcases`：
  - owner 展示页列表。
  - 创建展示页草稿。
  - owner 查看详情。
  - 更新展示页。
  - 发布展示页。
  - 下架展示页。
  - 公开访问已发布展示页。
- 展示页只保存 noteId、排序和配置，不复制资料正文。
- 创建和更新时校验资料归属，禁止选择其他用户资料。
- 发布时要求至少一条有效资料。
- 公开接口只返回已发布展示页和资料摘要，草稿/下架不可访问。
- 小程序新增：
  - `pages/showcases/index` 展示页列表。
  - `pages/showcase-edit/index` 构建/编辑/发布页。
  - `pages/showcase-view/index` 客户展示页。
- “我的”页新增展示页入口。
- 构建页已支持 banner 图片上传、资料排序、隐藏、移除、展示标题和自定义分组标题。
- 公开页会过滤隐藏资料和已删除资料。

验证：

- 展示页专项后端测试：3 passed。
- 后端编译检查：通过。
- 小程序 JS 静态检查：通过。
- 小程序 JSON 解析检查：通过。
- `git diff --check`：通过。
- 后端全量测试：112 passed。

未做：

- 未尝试微信开发者工具 CLI 上传，符合项目约定。
- 真机分享、banner 裁切、电话拨号、复制微信号仍需人工确认。

## 本次补充：修复 PaddleOCR 识别接口 502

背景：

- 用户反馈 06:33 左右测试“识别图片文字”显示识别失败。
- 生产排查定位到：
  - 06:33:56 `POST /api/ocr/images` 保存图片成功，生成 `note_af53dd1a18`。
  - 06:34:06 `POST /api/ocr/notes/note_af53dd1a18/recognize` 返回 502。
  - Nginx 错误为 `upstream prematurely closed connection`，后端容器同秒重启。

原因：

- PaddleOCR 单独识别该图片成功，完整业务识别在一次性容器里也成功。
- 但 PaddleOCR 放在 Uvicorn Web 主进程内执行时，会让主进程直接退出，导致 Nginx 502。
- 该问题属于 native OCR 依赖与 Web 主进程同进程运行不稳定，不是图片丢失或路由未部署。

修复：

- 新增 `app.services.paddle_ocr_worker`，把 PaddleOCR 识别放到独立 Python 子进程中执行。
- `OcrService._try_paddle` 改为调用子进程并解析 JSON 结果。
- 子进程异常、超时或 native 崩溃时，只返回 OCR 未配置/失败原因，不再带崩主后端服务。

验证：

- 本地 `compileall backend/app backend/tests`：通过。
- 本地 `pytest backend/tests -q`：106 passed。
- 本地 PaddleOCR 子进程识别测试图：返回 `HELLO 123`。
- 生产已同步后端代码并重建/重启 `teambuy-backend`。
- 公网 `POST /api/ocr/notes/note_af53dd1a18/recognize`：返回 200。
- 生产容器 `RestartCount=0`，识别接口复测后未再重启。
- 该笔资料已更新为 OCR done，`provider=paddle`，`confidence≈0.94`，并给出“可能是商品”的中置信提示。

## 本次补充：OCR 生产部署与 PaddleOCR 启用

背景：

- 用户真机点击“保存图片”时报 `Not Found/no found`。
- 小程序 `apiBaseUrl` 指向生产 `https://teambuy.lifelove.top`，本地新增的 `/api/ocr/images` 尚未部署到生产。
- 用户确认 OCR 引擎优先安装 PaddleOCR。

完成内容：

- 已确认生产旧状态：
  - `GET https://teambuy.lifelove.top/api/ocr/images` 返回路由级 `{"detail":"Not Found"}`。
  - `POST /api/ocr/notes/test/recognize` 同样返回路由级 `Not Found`。
- 本机 Codex Python 运行时安装并验证：
  - `paddlepaddle==3.3.1`
  - `paddleocr==2.10.0`
  - `OcrService(provider="paddle")` 可识别测试图 `HELLO 123`。
- 后端依赖与镜像：
  - `backend/requirements.txt` 固定 PaddleOCR 依赖。
  - `backend/Dockerfile` 补 `libgomp1/libglib2.0-0/libxcb1`。
  - Docker 镜像内将图形版 OpenCV 替换为 `opencv-python-headless==4.13.0.92`，避免服务端依赖 `libGL` 大图形库。
- 生产部署：
  - 备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260620-040644`。
  - 已同步 `backend/app/`、`backend/tests/`、`backend/requirements.txt`、`backend/Dockerfile`、`backend/.env.example` 到生产。
  - 已将生产 `backend/.env` 的 `OCR_PROVIDER` 设置为 `paddle`。
  - 已重建并重启生产 `teambuy-backend` 容器。

验证：

- 生产 `/health`：返回 `status=ok`，Postgres configured。
- 生产 `GET /api/ocr/images`：返回 `405 Method Not Allowed`，说明路由已上线，不再是 404。
- 生产 `POST /api/ocr/notes/test/recognize`：返回业务级 `{"detail":"笔记不存在"}`，说明识别路由已上线。
- 生产 `POST /api/ocr/images` 上传测试图且使用不存在用户：返回业务级 `{"detail":"用户不存在"}`，说明保存图片接口已进入业务层。
- 生产容器内 `from paddleocr import PaddleOCR`：通过。
- 生产容器内 `OcrService(provider="paddle")` 识别测试图：返回 `text='HELLO 123'`、`configured=True`、`provider='paddle'`。
- 本地 `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：106 passed。
- `git diff --check`：通过。

## 本次补充：OCR 两段式保存与按需识别

背景：

- 用户确认 OCR 需要按实际意图拆开：有时只是保存图片，有时才需要识别图片文字。
- PaddleOCR / Tesseract 未配置时，图片资料也必须先保存，不能因为识别能力缺失而丢资料。

完成内容：

- 后端新增两段式接口：
  - `POST /api/ocr/images`：只保存图片资料，创建 `UserNote`，`cardType=image_ocr`，`sourceType=ocr`，`structuredData.ocr.status=pending`。
  - `POST /api/ocr/notes/{note_id}/recognize`：对已有图片资料执行 OCR；识别成功后进入 `ContentObject.sourceType=image_ocr -> content-to-note`，并更新原资料。
  - 兼容保留 `POST /api/ocr/image-to-note`，内部改为“保存图片 -> 识别图片”。
- OCR 状态写入 `visibilityConfig.structuredData.ocr`：
  - `pending`：图片已保存，等待用户主动识别。
  - `done`：已识别到文字，并进入资料整理链路。
  - `empty`：OCR 已配置但没有识别到文字。
  - `not_configured`：未配置 PaddleOCR / Tesseract / 其他 provider。
- 小程序“我的笔记”页入口从“图片识别”改为“保存图片”，上传后直接进入资料编辑页。
- 小程序 `note-edit` 新增图片资料 OCR 操作区，显示当前 OCR 状态、provider/原因，并提供“识别图片文字 / 重新识别图片文字”按钮。
- 未配置 OCR 或识别为空时，仍保留图片、封面和素材，用户可继续手动补正文和字段。

验证：

- `node --check miniprogram/pages/notes/index.js`：通过。
- `node --check miniprogram/pages/note-edit/index.js`：通过。
- `node --check miniprogram/services/api.js`：通过。
- `python3 -m compileall backend/app backend/tests`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q -k ocr`：2 passed。
- `find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check`：通过。
- `find miniprogram -name '*.json' -print0 | xargs -0 -n 1 python3 -m json.tool >/dev/null`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：106 passed。
- `git diff --check`：通过。

## 本次补充：OCR 图片识别入库第一版

背景：

- 用户确认 OCR 是重要入口能力，希望开始开发。
- 项目长期规则要求 OCR 作为 Input Adapter，不直接生成业务结果，而是统一进入 `ContentObject -> content-to-note -> UserNote`。

完成内容：

- 后端新增 `OcrService`：
  - `OCR_PROVIDER=auto` 默认优先尝试 PaddleOCR，再尝试 Tesseract。
  - 支持 `OCR_PROVIDER=paddle`、`OCR_PROVIDER=tesseract`、`OCR_PROVIDER=mock`。
  - 未安装 OCR 引擎时返回可解释结果，不阻断图片保存。
- 后端新增 `POST /api/ocr/image-to-note`：
  - 接收图片文件和 `ownerUserId`。
  - 复用现有图片压缩与存储链路保存图片。
  - 使用 OCR 识别图片文字。
  - 以 `ContentObject.sourceType=image_ocr` 进入 `content-to-note`。
  - 生成并保存 `UserNote`，同时记录 `SkillRun`。
  - 识别结果写入 `visibilityConfig.structuredData.ocr`，来源标记为 `sourceType=ocr`，标签包含 `图片识别`。
- 小程序“我的笔记”页新增“图片识别”入口：
  - 用户选择相册/拍照图片后上传识别。
  - 成功后直接跳转到新生成的资料编辑页。
  - 列表筛选新增“图片识别”来源。
- `backend/.env.example` 新增 OCR 配置项：`OCR_PROVIDER`、`OCR_LANGUAGE`、`OCR_TESSERACT_BIN`、`OCR_MOCK_TEXT`。

验证：

- `node --check miniprogram/pages/notes/index.js && node --check miniprogram/services/api.js`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q -k 'ocr_image_upload'`：1 passed。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：105 passed。
- `git diff --check`：通过。

## 本次补充：归档 parser 插件化、识别解释和中置信人工确认

背景：

- 用户要求把“企业微信归档 parser 插件化收口、类型识别可解释、中置信人工确认入口”一次完成。

完成内容：

- 企业微信会话归档 parser registry 收口：
  - 每个 archive parser 有稳定 `name` 和 `msg_types`。
  - `ArchiveMessageParserRegistry` 支持显式注册、重复 msgtype 拦截和 `supported_types()`。
  - 解析结果 metadata 自动写入 `archiveParser` 和 `archiveMsgType`，未知类型走 fallback 并记录 `unsupportedArchiveMsgType`。
- 类型识别可解释：
  - `content-to-note` 的 `visibilityConfig` 新增 `recognitionExplanation`。
  - 高置信和中/低置信都会记录候选类型、分数、命中字段、可读信号、parser hints 和摘要说明。
  - `typeSuggestions` 扩展 `score`、`matchedFields`、`signals` 和 `reason`，方便前端展示“为什么像房源/商品”。
- 中置信人工确认入口：
  - 后端新增 `POST /api/notes/{note_id}/confirm-type`。
  - 支持确认成 `property_listing`、`groupbuy_product` 或 `text_note`。
  - 确认时统一重建 `cardType/cardState/structuredData/conversionConfig`，清空 `typeSuggestions`，写入 `recognitionConfidence.level=manual` 和 `recognitionExplanation.manualConfirmation`。
  - 确认成房源/商品/普通笔记时会保留原始正文、图片和 `structuredData.miniapp`，避免贝壳原小程序入口丢失。
  - 小程序 `note-edit` 的中置信按钮改为调用后端确认接口，不再前端本地拼完整结构。
  - 中置信提示展示识别摘要、命中信号和置信度。

验证：

- `node --check miniprogram/pages/note-edit/index.js && node --check miniprogram/services/api.js`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q -k 'archive_parser_registry or miniapp_card'`：3 passed。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：104 passed。
- `git diff --check`：通过。

## 本次补充：当前改动分组提交与部署前验证

背景：

- 用户要求把当前建议顺序中的 1 到 5 一起执行：复核 diff、确认特殊文件、运行验证、分组提交、部署生产后端。

完成内容：

- 已复核当前 diff 范围，并确认未跟踪的 `企业微信客服服务须知.pdf` 不纳入提交。
- 已确认 `miniprogram/project.config.json` 主要是微信开发者工具自动补充配置与换行变化，本轮暂不纳入提交。
- 已将后端订单、消息、归档 parser、schema、测试和 mock 数据提交为 `feat: add lightweight orders and messaging backend`。
- 已将小程序订单、消息、消息入口组件、商品 SKU/名单体验、我的页和客户页体验提交为 `feat: add miniapp orders and messaging flows`。

验证：

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q`：66 passed。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：103 passed。
- `git diff --check`：通过。

部署：

- 已通过 SSH 访问生产服务器 `ubuntu@81.70.84.35`，生产目录为 `/home/ubuntu/teamBuy`。
- 同步前已备份生产 `backend/app`、`backend/tests`、`backend/mock` 和 `docker-compose.yml` 到 `/home/ubuntu/teamBuy-deploy-backups/20260620-031227`。
- 已用 `rsync` 同步本地 `backend/app/`、`backend/tests/`、`backend/mock/`、`backend/requirements.txt`、`backend/Dockerfile`、`backend/.env.example` 到生产，排除生产 `.env`、`secrets/`、媒体目录和 `backend/mock/runtime-state.json`。
- 已重建并重启生产 `teambuy-backend` 容器。

公网验证：

- `GET https://teambuy.lifelove.top/health`：返回 `status=ok`，Postgres configured。
- `GET https://teambuy.lifelove.top/api/orders?userId=user_test&role=buyer`：返回 200，空订单列表。
- `GET https://teambuy.lifelove.top/api/messages/threads?userId=user_test`：返回 200，空会话列表，`unreadTotal=0`。

## 本次补充：站内消息左右气泡

背景：

- 用户反馈站内消息里用户和团长头像/聊天气泡都在左侧，不像微信聊天。

完成内容：

- 后端消息线程返回 `participants`，包含发布者和买家的 userId、角色、昵称和头像。
- 小程序消息详情页按当前登录用户判断 `mine`：自己的消息在右侧，绿色气泡，头像在右；对方消息在左侧，白色气泡，头像在左，并显示对方昵称。
- 修正真机/平板上“我的消息仍贴左侧”的布局问题：不再使用 `row-reverse + justify-content:flex-end` 反转主轴，而是整行右对齐，只把我的头像单独排序到气泡右侧。
- 消息测试补充参与者信息断言，避免后续接口漏掉头像昵称。

验证：

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q`：66 passed。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
- `git diff --check`：通过。

## 本次补充：商品 P1 体验、名单筛选与小程序上传约定

背景：

- 用户确认小程序体验版/上传由自己在微信开发者工具完成，Codex 不要每次浪费 token 尝试 CLI 上传。
- 商品 P0 已基本跑通，需要把 P1 里工作量较小的体验补齐并统一测试。

完成内容：

- `AGENTS.md` 新增“小程序上传约定”：默认不再尝试微信开发者工具 CLI 预览/上传；Codex 只做实现、静态检查、JSON 校验和后端测试，上传由用户手动完成。
- 客户页商品 SKU 选择从单纯组合卡片增强为属性组按钮：有属性组时按口味、规格、配送方式等分组点选；无属性组时保留原组合 SKU 卡片兜底。
- SKU 选项售罄体验优化：某个选项只要仍有可买组合就不整体置灰，点击后自动切到可买组合；完全无可买组合才禁用。
- 客户再次进入商品客户页时，后端配置接口会回传 `submittedPayload`，前端恢复已提交的 SKU、数量、电话、地址、微信和备注。
- 团长 `note-actions` 商品下单/接龙名单增加 SKU 筛选；复制汇总、复制单条和发消息均按当前筛选列表执行。
- 后端测试补充已提交轻订单配置回显断言，覆盖 SKU、数量、电话和地址。

验证：

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q`：66 passed。
- `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
- `git diff --check`：通过。
- 未尝试微信开发者工具 CLI 上传，符合本轮新约定。

# 2026-06-19

## 本次补充：商品展示基座 + 团购 SKU 接龙

背景：

- 用户确认团购场景应先做成商品展示：团长配置商品字段和多 SKU，只有打开团购开关后客户页才出现接龙。
- 本轮不做 SCRM、地图、支付、订单、库存扣减、核销和分账；截止时间选填。

完成内容：

- 后端扩展 `relay-intent` 客户动作：写入 `customer_actions`，不投影到 `lead_reminders`。
- 后端新增商品 SKU 配置归一化，支持 `structuredData.skuConfig.attributeGroups/skus`，并在客户动作配置接口返回给客户页。
- 后端提交接龙时校验 `conversionConfig.enableGroupRelay`、SKU 是否售罄、同一客户同一商品是否已提交。
- 小程序商品工作台文案从“团购工作台”调整为“商品展示工作台”，并新增 SKU 属性组、选项和组合 SKU 编辑。
- 小程序商品主价格按 SKU 自动显示价格区间；截止时间为空时不展示。
- 客户页未开启团购时只展示商品；开启后显示 SKU 选择、数量、电话 / 微信、备注和提交按钮。
- 团长端 `note-actions` 针对商品展示为“接龙名单”，展示头像、昵称、SKU、数量、联系方式、备注和提交时间，并支持复制汇总、复制单条和电话拨号。
- 我的笔记商品卡轻 SCRM 摘要改为“接龙 N / 接龙名单”，避免把商品接龙误写成客户线索。
- 已补本地 mock 商品样例 `note_seed_groupbuy_product_001`：含 SKU 属性组、售罄 SKU、已提交接龙样例；运行态中 `lead_reminders=0`，可验证接龙不进入 SCRM。
- “我的”页生成测试数据入口已从 3 条房源扩展为 3 条房源 + 1 条商品，会生成到当前登录用户名下，避免 seed owner 和设备本地用户不一致导致看不到商品 mock。
- 接龙提交会把客户昵称和头像写入 `relay-intent` payload，团长名单可展示头像和昵称。
- 小程序主联调地址恢复为生产 `https://teambuy.lifelove.top`；本地 mock 只作为开发辅助，不作为企业微信客服生产链路验收口径。
- 商品接龙名单页面已按移动端 rpx 布局修正：头像 / 昵称 / 状态稳定排布，操作按钮改为小胶囊；商品工作台顶部动作支持窄屏换行，避免按钮文案被裁切。
- 本地 mock 环境下“微信登录”不再伪装成 mock 身份；真实微信登录需要线上 HTTPS 后端和 AppSecret，本地测试请使用“本地 mock 登录”。
- 商品工作台底部标签 / 专题输入在手机上改为上下布局，避免按钮溢出屏幕；iPad / 宽屏继续并排。
- SKU 新增属性和选项时不再把“属性 N / 选项 N”写入真实值，只作为输入提示；空选项会保留在编辑态，填写后才参与组合 SKU 生成。
- 商品“价格”从基础字段前置位置移出：有 SKU 时使用组合 SKU 的价格；未设置 SKU 属性时才显示“单一价格”兜底字段。
- 资料详情底部“删除 / 保存”改为 flex `space-between` 左右分布，清除小程序按钮默认 margin 避免真机错位。

验证：

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `pytest backend/tests -q`：102 项通过。
- `python -m compileall backend/app backend/tests`：通过。
- `git diff --check`：通过。
- 本地 `runtime-state.json` 已验证：1 条商品资料、1 条 `relay-intent`、0 条 `lead_reminders`。

## 本次补充：customer-action-plugin 第一版落地

背景：

- 用户确认下一阶段重点只做“客户页动作持久化”，并要求做成可复用插件，后续普通笔记、团购、活动等场景也能复用。
- 当前客户页 `note-preview` 的留联系方式和预约看房只是本地状态，刷新或发布者查看时无法形成真实线索闭环。

完成内容：

- 后端新增通用 `CustomerAction` 模型和 `customer_actions` 仓储 / PostgreSQL 表。
- 新增接口：
  - `GET /api/notes/{note_id}/customer-actions/config`
  - `POST /api/notes/{note_id}/customer-actions/{action_key}`
- 第一版接入两个动作插件：
  - `lead-contact`：客户留下电话 / 微信。
  - `appointment`：客户提交预约日期和时间。
- 两个动作都会先写通用动作记录，再投影到现有 `lead_reminders`。
- `lead-contact` 会写入客户手机号、微信号、备注和跟进日志。
- `appointment` 会复用同一条线索，写入预约时间为 `nextFollowUpAt`，并追加跟进日志。
- 线索列表补充 `sourceNoteId`，兼容新 `UserNote` 主链路和旧 `Card` 线索模型。
- 小程序 `pages/note-preview/index` 已把“提交联系方式”和“提交预约”从本地假提交改成真实 API 提交；刷新后会读取客户动作配置并恢复已提交状态。
- 新增 `backend/mock/customer-actions.json`，用于本地 JSON 仓储初始状态。

验证：

- `pytest backend/tests/test_app.py::test_import_creates_claimable_user_note_and_note_crud -q`：通过。
- `node --check miniprogram/pages/note-preview/index.js && node --check miniprogram/services/api.js`：通过。
- `python -m compileall backend/app backend/tests`：通过。

## 本次补充：客户页动作持久化收敛为插件化重点

背景：

- 用户确认房产长标题通常是中介有意把价格、地铁口、户型、亮点放在首屏，不应自动拆字段或改标题。
- 用户确认后续重点只做“客户页动作持久化”，且必须做成插件，因为其他笔记场景也会复用。

完成内容：

- 新增 `docs/stage2-docs/13-customer-action-plugin-architecture.md`。
- 固定 `customer-action-plugin` 方向：客户页动作由插件注册，房源 / 团购 / 普通笔记通过 `conversionConfig` 启用动作。
- 第一版插件清单包括 `lead-contact`、`appointment`、`relay-intent`、`consult-click`、`navigation-click`、`external-open`。
- 明确动作提交先落通用动作记录，再投影到 `lead_reminders`、预约、接龙和跟进。
- 明确不做标题拆字段、封面裁切焦点、三条亮点自动生成等旁支优化。

验证：

- 本次仅更新架构文档和长期记忆，无业务代码变更。

## 本次补充：房源详情主动作同排与分享图长标题防重叠

背景：

- 用户反馈房产资料详情顶部主动作排版不理想，希望“分享文案 / 转发给好友 / 客户页预览”放在同一排。
- 用户截图显示房源分享图在长标题场景下，标题、价格和补充信息可能互相挤压或重叠。

完成内容：

- `pages/note-edit/index` 房源 / 团购工作台顶部主动作调整为一行三列，顺序为“分享文案 / 转发给好友 / 客户页预览”。
- 主动作按钮补充 `margin: 0`、`min-width: 0` 和不换行约束，避免微信小程序默认按钮外边距导致三列排版挤压。
- `pages/note-poster/index` 分享图标题生成前会压平换行和多余空白。
- 分享图页面预览标题限制为最多 3 行；canvas 保存图片时同样限制标题区域高度，给价格和详情行保留空间。

验证：

- `node --check miniprogram/pages/note-poster/index.js`：通过。
- `node --check miniprogram/pages/note-edit/index.js`：通过。
- `git diff --check -- miniprogram/pages/note-edit/index.wxml miniprogram/pages/note-edit/index.wxss miniprogram/pages/note-poster/index.js miniprogram/pages/note-poster/index.wxss`：通过。

## 本次补充：企业微信小程序卡片归档不再生成空笔记

背景：

- 用户在 02:41 左右把贝壳房源小程序卡片发给企业微信，后端会话存档成功收到 `msgtype=weapp`，但小程序前端只能看到空资料。
- 生产排查确认企业微信实际下发的是小程序卡片外壳：标题、appid、username、displayname/description、pagepath，以及 pagepath 中的 `houseCode` / `cityId` / `source`；没有价格、户型、面积、图片和经纬度。

完成内容：

- `ContentObjectPayload` 新增 `metadata`，用于保留小程序 appid、pagepath、houseCode 等非正文元数据。
- `ContentObjectAdapter` 已支持会话存档 `weapp` 和客服 `sync_msg` `weapp`，入库时生成可见正文：小程序标题、来源、appid、房源编码。
- 小程序 pagepath 不直接展示在正文中，完整路径只保存到 `visibilityConfig.structuredData.miniapp.pagePath`，避免页面被长参数污染。
- `WecomMessageNormalizer`、`MessageAggregator` 和 `MessageType` 已补齐 `weapp`，普通客服同步链路也可导入小程序卡片。
- `SkillRouterService` 对小程序卡片写入 `sourceType=miniapp`、`systemCategory=小程序`、标签 `小程序/贝壳找房/房产`；贝壳卡片只给“可能是房源信息”的中置信提示，不自动当高置信房源。
- 修复 pagepath 长数字被手机号正则误识别的问题：`miniapp_card` 不从正文提取手机号，`showPhone=false`。
- 已将本地后端代码同步并重建生产后端。
- 已修复生产 02:41 的历史空笔记：
  - archive message：`wecom_archive_msg_04c9699da3`
  - note：`note_4ecff85fca`
  - card：`card_336b070ffc`
  - 标题：`三江尊园 全天采光 好楼层 拎包入住`
  - `houseCode=101137825091`、`cityId=150200`

验证：

- `python -m compileall backend/app backend/tests`：通过。
- `pytest backend/tests -q`：98 项通过。
- 生产 `https://teambuy.lifelove.top/health`：通过。
- 生产 `GET /api/notes/note_4ecff85fca?ownerUserId=user_08e8927ed8`：返回 `sourceType=miniapp`，正文不再为空，`phone=null`，`typeSuggestions` 含房源中置信提示。

## 本次补充：贝壳小程序原房源入口与 SCRM 组合

背景：

- 用户确认不需要强行爬取贝壳详情，贝壳小程序卡片可以在我们的房源块里显示为原小程序入口。
- 用户希望客户仍能通过我们的客户页使用轻 SCRM、留资、预约、咨询等能力。

完成内容：

- 小程序 `app.json` 增加贝壳 appid 的 `navigateToMiniProgramAppIdList`；地图选点仍只声明 `chooseLocation`。
- `pages/note-edit/index` 新增“原小程序房源”块：展示来源、标题、房源编码，并提供“查看贝壳原房源”和“客户页预览”。
- `pages/note-preview/index` 客户页新增“查看贝壳原房源”动作，点击后通过 `wx.navigateToMiniProgram` 跳转到贝壳小程序对应 `pagePath`；失败时复制标题、来源和房源编码兜底。
- 后端规则调整：贝壳这类 `miniapp_card` 房源候选默认开启轻 SCRM、留资、预约、微信咨询和海报入口，不开启电话展示。
- 后端会根据 `cityId + houseCode` 生成贝壳网页候选 URL；当前 `cityId=150200` 映射为 `baotou`，生成 `https://m.ke.com/baotou/ershoufang/101137825091.html`，并写入 `visibilityConfig.sourceUrl` 和 `structuredData.miniapp.webUrl`。
- 该网页 URL 可能被贝壳验证码拦截，不能作为稳定爬取来源；用途是备用打开、复制和人工核对。
- `buildStructuredDataForType` 已修复：用户把小程序卡切成房源字段卡时，会保留 `structuredData.miniapp`，不会丢失原贝壳入口。
- `pages/notes/index` 列表会把小程序资料显示为“小程序”，并展示来源和房源编码。
- 生产历史 note `note_4ecff85fca` 已恢复 `structuredData.miniapp`，当前为 `property_listing + sourceType=miniapp`，并已开启轻 SCRM、留资、预约和微信咨询。

验证：

- `pytest backend/tests -q`：98 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- 生产 `GET /api/notes/note_4ecff85fca?ownerUserId=user_08e8927ed8` 确认保留 `houseCode=101137825091`、`pagePath` 和 SCRM 配置。
- 生产同一接口确认已保留 `sourceUrl=https://m.ke.com/baotou/ershoufang/101137825091.html`。

## 本次补充：房源标题小区识别、默认城市定位和客户页动作文案

背景：

- 用户指出房产中介的标题里通常就带小区名，识别高置信时应把标题小区作为有效信号。
- 用户指出如果中介之前发过长沙房源，后续地址不带城市时也应默认补长沙，避免同名小区导致地图匹配失败。
- 用户反馈客户页里的“我要留资 / 私聊咨询”不够直白，需要换成客户能理解的动作。
- 用户要求预约看房默认今天/明天，并能用滚轮选择具体时间，精确到几点几分。

完成内容：

- 后端房源识别增强：当标题含小区名且正文有户型、面积、价格、位置等房源信号时，会把标题作为 `community` 参与高置信判断。
- 新增测试覆盖“标题是小区名，正文有房源字段”的高置信房源识别。
- 编辑页和客户页地图解析会记住最近一次房源城市，例如 `长沙市`；后续地址不含城市时，会用记住的城市补全后再调腾讯地图地理编码。
- 客户页动作文案调整：
  - `联系咨询` 改为 `电话咨询`。
  - `我要留资` 改为 `留下电话/微信`。
  - `私聊咨询` 改为 `微信咨询`。
  - `预约看房` 描述改为选择日期和时间。
- 客户页留资表单新增微信号字段，电话和微信二选一即可提交。
- 客户页预约看房改为页面内表单：默认今天 10:00，支持今天/明天快捷选择，也支持日期和时间选择器精确到分钟。

验证：

- `pytest backend/tests -q`：96 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

## 本次补充：分享入口、悬浮保存、手机号记忆和客户页图片/导航优化

背景：

- 用户认为“生成推广”不如“发给好友”直观，当前工作台应更强调结果分享。
- 用户希望长页面编辑时保存按钮能固定在页面左侧中部，减少滑到底保存的操作。
- 用户希望手机号填写后后续默认带入，减少重复输入。
- 用户确认客户页预览就是客户看到的详细页面，因此图片应在客户页完整展示。
- 用户希望地图定位点击后能尽量支持跳转导航 App，而不只是微信内置地图。

完成内容：

- 笔记列表房源/团购卡片动作文案统一改为“转发给好友”，并接入微信原生 `open-type="share"`。
- 房源/团购工作台顶部动作改为“分享文案 / 转发给好友 / 朋友圈海报”，其中“转发给好友”直接调起微信转发。
- `pages/note-edit/index` 增加浅绿色小尺寸悬浮保存按钮，默认吸附右侧中部，拖动松手后按左右距离吸附到最近侧；底部保存按钮仍保留。
- 发布者联系方式增加本地记忆：保存房源/团购联系方式后，下一条资料如果没有识别出联系方式，会自动带入上次手机号。
- 客户页留资手机号增加本地记忆：客户填写手机号并提交后，下次打开留资表单默认带入该手机号，仍可手动修改。
- 客户页新增房源图片横向图库，封面图继续作为分享卡片图片，其余图片在客户页内展示并支持预览。
- 客户页地图定位动作改为弹出“选择导航App / 微信内置地图 / 复制地址”；优先使用 `MapContext.openMapApp`，不支持时回退 `wx.openLocation`。
- 客户页正文内原“发给微信好友 / 发朋友圈”按钮已移除，改为右侧靠下固定的两个同尺寸小浮动按钮，避免和内容动作混淆。
- 修复补充：编辑页顶部恢复“客户页预览”独立入口，“转发给好友”保留为单独原生分享按钮，避免点击详情预览时误触发转发。
- 修复补充：我的笔记列表不再展示 `房源 · 编辑中` 这类内部生命周期状态，房源/团购卡片徽标只展示业务类型。

验证：

- `pytest backend/tests -q`：95 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

## 本次补充：客户页地图不显示经纬度，默认地址自动生成地图点

背景：

- 用户确认客户页地图可以显示，但不希望把经纬度数字直接展示给客户。
- 用户希望房源“默认地址”和地图位置默认对应，不能只有手动确认地图点后才显示地图。

完成内容：

- 客户页 `pages/note-preview/index` 的地图头部不再显示经纬度数字，改为“腾讯地图 / 正在匹配默认地址 / 按默认地址定位”。
- 客户页有地址但没有坐标时，会尝试通过后端地理编码接口把默认地址解析成腾讯地图坐标；成功后直接显示地图和小房子标记。
- 编辑页 `pages/note-edit/index` 加入同样的静默解析：房源有默认地址但没有 `mapLocation` 时，自动尝试生成坐标并保存到资料卡。
- 编辑页地址变更后会清掉不匹配的旧地图点，避免地址和地图小房子位置不一致。
- 新增后端 `GET /api/location/geocode`，由后端持有 `TENCENT_MAP_KEY` 调用腾讯地图地理编码，避免地图 Key 暴露到小程序前端。
- `backend/.env.example` 新增 `TENCENT_MAP_KEY` 和 `TENCENT_MAP_GEOCODER_URL` 配置说明。

验证：

- `pytest backend/tests/test_app.py -q`：59 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

生产配置补充：

- 已将腾讯地图 Key 配置到本地 `backend/.env` 和生产服务器 `/home/ubuntu/teamBuy/backend/.env`，未写入前端代码。
- 已同步 `routes_location.py`、`config.py`、`main.py` 到生产后端并重建 `teambuy-backend` 容器。
- 生产验证：`https://teambuy.lifelove.top/health` 正常，`/api/location/geocode` 返回 `configured=true` 且可解析测试地址坐标。

# 2026-06-18

## 本次补充：按用户参考图调整我的笔记列表和收藏态首屏

背景：

- 用户指出“我的笔记”页分类和标签不应横向滑动，应先展示常用项，再通过下拉展示全部。
- 用户要求笔记卡片底部“编辑字段”旁边展示上传时间，精确到年月日。
- 用户指出进入编辑页后的第一个 UI 状态与预期差距较大，应优先处理收藏态首屏，再继续处理其他三态。

完成内容：

- `pages/notes/index` 分类筛选改为默认展示“最近使用、笔记、下拉箭头”，点击后展示全部分类和“添加分类”入口。
- 标签筛选改为默认展示“最近使用、房产、户外、团购、添加标签”，可展开全部标签。
- 笔记卡片底部新增“上传时间 YYYY年M月D日”，放在“编辑字段”旁边。
- `pages/note-edit/index` 收藏态首屏去掉流程条和大状态头，改为先展示原始导入内容块、识别标签、图片预览，再展示“可能是房源资料”和“确认并编辑 / 直接整理”。
- “确认并编辑”会把状态持久化为 `editing`。

验证：

- `pytest backend/tests -q`：91 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

## 本次补充：按房产 4 态重构笔记编辑页

背景：

- 用户确认房产资料应按“收藏态、编辑态、整理态、生成态”推进。
- 现有 `note-edit` 虽然已有房源字段和功能配置，但视觉上仍像一个长表单，和预期的 4 态流程差距较大。

完成内容：

- 小程序 `pages/note-edit/index` 重构为 4 态流程：
  - 收藏态：展示企业微信导入的原始内容、识别标签、素材预览和“确认并编辑”入口。
  - 编辑态：突出房源/团购结构化字段表单，并把 `conversionConfig` 单独放在“转化功能配置”面板。
  - 整理态：展示整理摘要、字段审核、待确认项、生成建议和已启用动作。
  - 生成态：展示生成页管理预览、客户可用动作和轻 SCRM 数据占位。
- 页面顶部新增“收藏 -> 编辑 -> 整理 -> 生成”进度条和当前状态说明。
- “整理资料”现在会先保存当前字段，再调用整理接口，避免整理旧数据。
- 旧链接收藏卡逻辑保留，不受房源/团购 4 态重构影响。

验证：

- `pytest backend/tests -q`：91 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

## 本次补充：隐藏旧资源详情入口，强制优先走新资料卡链路

背景：

- 用户测试时发现房源/团购 typed card 已经生成，但从资源库、首页、线索或客户资料打开时仍进入旧 `card-view/card-edit` 资源卡页面。
- 根因是当前导入链路为了兼容旧小程序闭环仍双写 `UserNote` 和 `Card`，而部分前端入口仍以 `Card` 为主。

完成内容：

- 后端 `/api/cards` 和 `/api/cards/{card_id}` 响应新增 `sourceNoteId`，用于标识兼容旧 Card 对应的新 `UserNote`。
- 小程序新增 `utils/resource-navigation.js`，统一处理资源跳转：
  - 有 `sourceNoteId` 时进入 `/pages/note-edit/index`。
  - 没有 `sourceNoteId` 的纯旧资源卡才回退旧 `card-view/card-edit`。
- 资源库、首页热门资源、访问记录、客户资料库、待联系列表、线索详情、管理页的资源入口已接入统一跳转。
- 旧 `card-view` 和 `card-edit` 未删除；当资源拥有者直接打开带 `sourceNoteId` 的旧页面时，会自动重定向到新笔记编辑页。
- 客户分享访问旧 `card-view` 暂不强制拦截，避免在新的客户展示页完成前误伤外部查看链路。

验证：

- `python -m compileall backend/app backend/tests`：通过。
- `pytest backend/tests -q`：91 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

下一步：

- 在微信开发者工具里重新编译/预览，确认从资源库、首页、待联系、客户资料库打开已认领房源/团购资料时，进入新“笔记详情 / 功能配置 / 生成场景页”。
- 等新资料卡链路稳定后，再决定是否删除或改造旧 `card-view/card-edit`。

## 本次目标

实现“多类型资料卡与结构化业务信息”第一版：在现有 `UserNote` 上扩展 typed card，不把房源 / 团购继续当普通笔记处理。

## 完成内容

- 新增 `docs/stage2-docs/12-typed-content-card-architecture.md`，固定“统一流程、结构分型”的资料卡架构。
- `content-to-note` 规则版新增资料类型识别：
  - 普通 URL 仍默认进入链接卡。
  - 房源文本识别为 `property_listing`，提取小区、户型、价格、水电物业、商圈、地址、服务费、备注、联系方式、图片。
  - 团购文本识别为 `groupbuy_product`，提取商品名、价格、规格、截止时间、自提/配送、取货地点、库存备注、联系方式、图片。
  - 低置信内容保留为文本卡并写入 `typeSuggestions`。
- `UserNote.visibilityConfig` 兼容扩展 `cardType`、`cardState`、`structuredData`、`typeSuggestions`。
- “整理”动作按 `cardType` 分型：
  - 链接卡整理后进入文章/阅读卡口径。
  - 房源卡整理后补房源摘要和生成建议。
  - 团购卡整理后补商品摘要和生成建议。
- 笔记搜索现在会检索 `structuredData`，可以命中小区、商圈、商品规格等结构化字段。
- 小程序“我的笔记”列表按 `cardType` 展示链接卡、房源字段卡、团购商品卡和普通文本卡。
- 小程序笔记编辑页新增房源字段表单和团购商品字段表单，并保留来源类型、弱分类、用户标签、专题编辑。
- 校准 `test_import_flow_uses_single_import_artifact_transaction`：成功导入事务保存入口已在 `_process_import_batch`，静态测试不再误判外层方法。

## 迭代与错误记录

- 本机没有裸 `python` / `pytest` 命令，改用 Codex 工作区 Python；该运行时缺 pytest，于是安装 `backend/requirements.txt` 和 pytest 到运行时，不改仓库文件。
- 完整后端测试首次失败在旧静态断言：测试要求 `import_synced_messages` 直接包含 `save_import_artifacts`，但实际保存入口已委托到 `_process_import_batch`。已调整测试检查真实成功路径，并在 `docs/pitfalls.md` 记录。
- 小程序动态字段最初计划在 WXML 中直接用动态 key 读取，考虑兼容性后改为 JS 预计算字段列表，WXML 只渲染 `item.value`。

## 验证结果

- `python -m compileall backend/app backend/tests`：通过。
- `pytest backend/tests -q`：91 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。

## 下一步

- 用真实企业微信消息测试房源文本和团购文本入库，确认小程序列表和编辑页展示符合预期。
- 下一阶段可做“类型转换”：低置信文本卡允许用户手动转成房源卡或团购卡。
- 后续再接房源推广图、团购海报、微信群文案、客户话术等生成型 Skill。

## 后续补充：房源/团购生成态功能配置

- 后端新增 `visibilityConfig.conversionConfig` 标准配置，用于第二态编辑到第四态生成之间的转化能力控制。
- 房源默认开启：展示联系电话、轻 SCRM、线索收集、预约看房、私聊咨询、生成海报；不开启团购接龙和下单预留。
- 团购默认开启：展示联系电话、轻 SCRM、线索收集、团购接龙、生成海报；下单按钮只做预留且默认关闭。
- `POST /api/notes/{note_id}/generate` 新增轻量生成接口，当前把资料卡置为 `generated`，并把启用动作写入 `structuredData.generatedResult.enabledActions`。
- 小程序编辑页新增“功能配置”面板，房源/团购展示不同开关；新增“生成场景页”动作。
- 规则：房源/商品本体字段继续放 `structuredData`，行为/转化开关只放 `conversionConfig`。

验证：

- `python -m compileall backend/app backend/tests`：通过。
- 目标后端测试：房源/团购结构识别、配置保存、生成接口通过。
- 小程序 JS 静态检查通过。
- 小程序 JSON 解析通过。
- 生产部署：已同步 backend 到 `81.70.84.35:/home/ubuntu/teamBuy/backend/` 并重建 `teambuy-backend` 容器。
- 生产验证：`https://teambuy.lifelove.top/health` 返回 `status=ok`；`POST /api/notes/note_not_exists/generate?ownerUserId=user_not_exists` 返回“笔记不存在”，确认 generate 路由已上线。

# 2026-06-10

## 本次目标

推进资料库正式可用的第一阶段：明确正式持久化走 PostgreSQL 仓储，上传素材先压缩再存储，并用原生小程序 store/cache 模式集中管理资源与本机媒体缓存。

## 完成内容

- 新增后端媒体处理服务，手动上传和企微媒体转存都会先压缩：图片限制最大边长并转 JPEG，视频通过 ffmpeg 转 H.264/AAC MP4。
- 上传接口返回 `originalSize`、`storedSize`、`compressed`，用于确认压缩是否生效。
- 新增原生小程序 `stores/resource-store.js`，集中管理资源列表、分类、单卡片缓存和失效刷新。
- 新增 `utils/media-cache.js`，打开小程序后会把资源图片/视频下载并保存到手机，本地展示走 `coverDisplayUrl` / `media[].displayUrl`。
- 保留 `coverUrl` / `media[].url` 为后端正式 URL，避免保存时把本机缓存路径写回资料库。
- 更新依赖：后端增加 `Pillow` 用于图片压缩。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- `pytest backend\tests -q`：59 项通过。
- 小程序所有 `.js` 执行 `node --check`：通过，22 个文件。
- 小程序所有 `.json` 解析检查：通过，19 个文件。

## 下一步

建议继续做资料库持久化第二阶段：把高意向访客的“待联系 / 已联系 / 备注”从本地 storage 升级为后端持久化线索，并增加统一待联系列表。

# 2026-06-10

## 本次目标

修正小程序内“发给客服”入口逻辑，按用户确认口径改为：企业微信客服导入发生在小程序外部会话，小程序只负责待认领、编辑和资源库管理；中间加号作为快速入库入口。

## 完成内容

- tabBar 中间入口从“发给客服”改为“添加”，跳转到手动添加资源页。
- 首页、资源库、手动添加页移除了“发给客服 / 立即发给客服 / 去发给客服”用户操作文案。
- `pages/imports/index` 保留为“待认领导入”页，移除可见 mock 导入按钮，只展示外部导入结果和待认领草稿。
- 同步更新 UI 产品化文档、长期决策、坑点、项目记忆和交接文档。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析检查：通过。
- `pytest backend\tests\test_app.py -q`：34 项通过。
- 小程序残留文案扫描：`miniprogram` 内未命中“发给客服 / 立即发给客服 / 去发给客服 / 生成一条 mock 导入 / 企业微信客服”。
- 微信开发者工具人工复测通过：中间加号进入添加资源页，资源库“待认领”进入待认领导入页，小程序可见页面未发现旧的“发给客服”操作入口。

## 下一步

下一步建议优先清理当前提交范围并提交；提交后继续回到真实企业微信导入主链路或补齐后端持久化待联系提醒。

# Dev Log

## 2026-06-10

### 接龙名单显示与素材排序修复
- `relay-list` 组件内置接龙时间和跟进状态兜底格式化，资源详情页直接传原始 `relayEntries` 时不再显示 ISO 时间和 `pending` 原始值。
- 接龙时间显示为 `2024年1月15日 14:30` 这类年月日时分格式。
- 资源详情页的已接龙名单补齐 `标记已跟进` 和 `删除无效` 事件绑定，发布者可直接在资源页处理接龙。
- 卡片编辑页素材上移/下移后会重写 `sortOrder`，避免保存前又被旧排序排回原位。
- 素材上移、下移、删除操作改为更稳定的小按钮点击区。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

### 待联系提醒清理与完成状态

- 管理页高意向访客的本地待联系提醒从单一“已备注”扩展为 `pending / contacted` 两种状态。
- 点击“加入待联系”后，可继续“标记已联系”或“取消待联系”。
- 标记已联系后，访客卡片显示“已联系”，并支持“清除记录”。
- 本地 storage 仍按资源维度存储，key 为 `viewerReminders_{cardId}`。
- 旧版数组格式会自动兼容为 `pending` 状态，避免已有本地提醒丢失。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 高意向访客转待联系

- 管理页高意向访客卡片新增“复制昵称”动作。
- 管理页高意向访客卡片新增“加入待联系”动作。
- 待联系提醒按资源保存在小程序本地 storage，刷新后保留“已备注待联系”状态。
- 该能力当前用于发布者个人跟进节奏，不新增后端团队协作待办模型。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 管理页访客筛选与意向提示

- 后端 stats 的 `loggedInViewers` 增加 `viewCount`，同一登录用户重复访问会聚合为一条访客记录。
- 登录访客按最新访问时间排序，保留最近访问时间。
- 管理页访客区新增“高意向 / 最近 / 全部”切换。
- 重复访问且尚未接龙的访客标记为“高意向”并高亮展示。
- 已接龙访客标记为“已接龙”，避免发布者重复判断。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 管理页线索筛选分组

- 发布者管理页接龙名单改为单一线索面板，支持“待跟进 / 已跟进 / 全部”切换。
- 默认停留在“待跟进”，处理完的线索会从待跟进视图移出。
- 筛选项显示对应数量，便于发布者快速判断处理进度。
- 待跟进线索继续保留高亮卡片和快捷动作。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 发布者管理页线索操作效率

- `relay-list` 发布者视角新增线索快捷动作。
- 有电话的接龙线索支持“电话直拨”和“复制电话”。
- 有地址的接龙线索支持“复制地址”。
- 快捷动作只在 `isOwner=true` 时渲染，普通客户视角不会显示。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 发布者跟进后的客户侧状态

- 资源详情页客户接龙状态从单一“已提交”扩展为“已提交 / 已跟进”。
- 当 `currentUserRelay.followUpStatus === "followed"` 时，客户页显示“发布者已跟进”，并切换为蓝色状态卡。
- 当接龙仍为 `pending` 时，客户页继续显示“已提交接龙，发布者会尽快联系你”。
- 后端测试补充：发布者标记跟进后，客户再次请求 stats 时 `currentUserRelay.followUpStatus` 为 `followed`。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 客户提交接龙后的体验闭环

- 资源详情页会根据当前登录用户的接龙记录识别“已提交”状态。
- 客户提交接龙成功后，输入区切换为“已提交接龙，发布者会尽快联系你”，避免重复操作。
- 后端新增重复接龙保护，同一用户对同一卡片只能保留一条 active 接龙记录，重复提交返回 409。
- stats 返回 `currentUserRelay`，前端刷新后仍能识别当前用户是否已提交。
- 管理页新增“待跟进新线索”高亮区，pending 接龙优先展示；全部接龙名单继续保留完整列表。
- `relay-list` 支持 pending 线索高亮样式。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，34 项通过。

## 2026-06-10

### 普通客户视角资源页隐私收口

- 资源详情页客户视角不再展示 PV/UV/接龙数统计卡片，仅保留电话、复制、分享、提交接龙等客户动作。
- 资源详情页客户视角不再展示“已接龙名单”，避免普通查看用户看到其他人的参与信息。
- 发布者视角继续展示统计卡片、访问详情入口和完整接龙名单。
- `relay-list` 组件补充防御：只有 `isOwner=true` 时才渲染电话和地址字段。
- 后端新增回归测试，确认非发布者请求 stats 时接龙昵称脱敏、电话和地址为空；发布者仍可看到完整字段。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，33 项通过。

## 2026-06-10

### 编辑页继续上传素材与分享权限收口

- 资源编辑页新增“添加图片/视频”入口，发布后的资源可继续补充图片或视频素材，不必回到创建流程。
- 编辑页空素材状态会提示“首张图片作为资源封面，后续图片/视频进入详情”，降低多素材维护时的理解成本。
- 新上传素材会写入卡片 `media`，第一张图片可自动补为封面；保存修改后同步持久化。
- 资源详情页“分享资源”改为微信小程序原生 `open-type="share"`，直接调起微信分享面板。
- 资源详情页“访问详情”入口仅资源发布者可见，普通查看用户和接龙用户不展示团长管理入口。
- 静态检查：小程序所有 `.js` `node --check` 通过；小程序所有 `.json` 解析通过。
- 后端回归：`pytest backend\tests\test_app.py -q` 通过，32 项通过。

## 2026-06-09

### 本次目标

修正自定义导航标题与胶囊对齐问题，收口手动添加资源的上传说明、封面设置和预览发布链路。

### 完成内容

- `custom-nav` 改为按当前页面路由自动映射标题，避免 WXML 属性实体串直接显示。
- 胶囊占位宽度改为基于 `windowWidth - button.left` 计算，使标题与右上胶囊更接近同一视觉基线。
- 手动添加资源页移除“来源设置”区块。
- 上传区新增说明：首图默认封面，其他图片/视频/附件进入详情；支持手动“设为封面”。
- “预览资源页”改为真实创建并发布，再跳转资源详情页。
- 资源编辑页保存/发布 payload 统一由 `buildPayload()` 生成，减少字段结构不稳定导致的失败。

### 待验证

- 微信开发者工具里确认自定义导航标题不再显示 `&#x...` 实体文本。
- 确认手动添加资源页多图上传后，“设为封面”即时生效。
- 确认“保存到资源库”进入编辑页，“预览并发布”直接进入资源详情页。

### 后续修正

- 修复后端 `update_card()`：`payload.model_dump()` 后的 `relayConfig` 实际是 `dict`，旧代码继续调用 `value.model_dump()` 会触发 500。
- 新增 `test_update_card_flow_accepts_relay_config_payload` 回归测试，覆盖资源编辑保存链路。
- 删除首页、资源库、发给客服、访问记录、我的、登录页顶部重复出现的“资料整理助手”品牌条；资源创建页导航标题改为“手动添加资源”。

### 资源库补充

- 资源库第一排筛选明确为“分类筛选”，第二排明确为“标签筛选”。
- 第二排标签改为只展示真实自定义标签，不再混入“手动添加 / 客服接收 / 带链接 / 可接龙”等来源或能力标记。
- 新增资源删除能力：删除资源时同步移除其访问记录和接龙线索。

### 资源详情补充

- 卡片创建/更新接口正式支持 `media` 字段，手动上传的图片/视频不再只藏在 `detailText`。
- 手动添加资源页会把图片/视频作为 `media` 写入卡片，附件链接仍补充到文案里。
- 卡片编辑保存时会保留已有 `media`，避免保存后详情素材丢失。
- 资源详情页新增“详情素材”展示区，支持多图预览和视频播放。

### 编辑页操作文案修正

- 卡片编辑页底部按钮从“保存草稿 / 发布并预览”调整为“保存修改 / 发布并查看”。
- 手动添加页发布按钮从“预览并发布”调整为“发布并预览”。
- 明确产品语义：进入编辑页时资源已经在资料库中，“发布”会自动先保存当前修改。

### 编辑页素材管理

- 卡片编辑页新增“素材管理”区。
- 支持查看当前详情图片/视频的缩略图、类型和排序。
- 支持图片设为封面，设封面后同步更新 `coverUrl`。
- 支持详情素材上移、下移和删除，保存后写回卡片 `media`。

### 编辑页发布页式重构

- 资源编辑页改为接近用户发布页的视觉结构：顶部封面、标题、项目名和位置直接在预览区编辑。
- 移除“封面图片链接”输入框，不再向用户暴露技术字段。
- 详情素材区改为接近发布页展示效果，点击图片即可设为封面，其他图片/视频默认展示在详情区。
- 保留保存修改、发布并查看、标签、联系电话、来源链接、接龙设置等必要编辑能力。

本文件记录每次阶段性开发或文档整理的结果，供新 Codex 会话接手。

## 2026-06-08

### 本次目标

完成阶段一和阶段二项目规划，把团购想法收敛为可开发的 teamBuy MVP。

### 完成内容

- 生成 `stage1-thinking/` 阶段一交付物。
- 生成 `docs/stage2-docs/` 阶段二文档包。
- 生成 `docs/qa/MVP_测试清单与验收标准.md`。
- 生成本地构建与拉镜像部署方案。
- 新增项目级 Skills。
- 将客服侧边栏/H5 发卡片能力标记为 P2 技术预研。

### 修改文件

- `AGENTS.md`
- `stage1-thinking/*`
- `docs/stage2-docs/*`
- `docs/qa/*`
- `skills/*`

### 未完成

- 阶段三代码开发。
- 真实企业微信联调。
- 小程序人工验收。

### 下一步

按 `docs/stage2-docs/codex-prompt.md` 进入阶段三开发。

## 2026-06-09

### 本次目标

记录阶段三当前状态，生成交接文档，建立项目长期知识库。

### 完成内容

- 生成 `docs/handoff-latest.md`。
- 新增项目知识库文件：
  - `docs/project-memory.md`
  - `docs/decisions.md`
  - `docs/pitfalls.md`
  - `docs/dev-log.md`
  - `docs/prompts/codex-start.md`
  - `docs/prompts/codex-handoff.md`
- 在 `AGENTS.md` 中新增“项目知识库与 Codex 启动必读”规则。

### 当前观察

- 当前 HEAD 为 `c0a6f16 docs: record lifelove https callback readiness`。
- 远端 `main` 与本地 HEAD 同步。
- 工作区仍存在未提交的小程序 UI/产品化改动和未跟踪文件。
- 后端自测报告记录 `pytest` 48 项通过，但本轮未重新运行测试。

### 未完成

- 当前未提交 UI/产品化改动尚未整理提交。
- 企业微信真实 `sync_msg` 仍被 `48002 api forbidden` 阻塞。
- 小程序仍需微信开发者工具人工验收。

### 下一步

新会话先读取 `AGENTS.md` 和 `docs/handoff-latest.md`，检查当前工作区，再决定是否整理 UI 改动或继续企业微信真实联调。

## 2026-06-09

### 本次目标

完成「资料整理助手」v0.1 UI 产品化改版收尾，接入 tabBar 图标，修正文案边界并准备提交。

### 完成内容

- 小程序 tabBar 接入 `miniprogram/static/tab` 本地图标。
- 首页文案从“智能提醒”调整为“访问提醒”。
- 我的页会员占位文案从“智能整理权益”调整为“自动整理权益”。
- 访问记录页去掉“今日访问”表述，避免误导为真实分日统计。
- 访问记录页「全部记录 / 按资源 / 高意向」支持选中态，高意向筛选只展示高意向资源。
- 小程序前端静态检查通过。
- 小程序 JSON 解析检查通过。
- 后端 `pytest` 48 项通过。
- 后端 `python -m compileall app` 通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 真实企业微信 `sync_msg` 仍被 `48002 api forbidden` 阻塞。
- `docs/png/` 中存在较多设计参考大图，本轮不纳入提交范围。

### 下一步

优先用微信开发者工具验收小程序 UI 和 mock 旧链路；随后继续排查企业微信真实 `sync_msg` 权限配置。

## 2026-06-09

### 本次目标

在企业微信认证和 `sync_msg` 权限暂时无法继续推进时，先补齐资料库的手动添加资源能力。

### 完成内容

- 后端新增 `POST /api/cards`，用于手动创建资源卡片草稿。
- 新增 `CardCreateRequest`，创建草稿时校验用户存在和标题必填。
- 小程序新增 `pages/resource-create/index` 手动添加资源页。
- 资源库「手动添加」入口从占位提示改为进入手动添加页。
- 手动添加创建成功后进入现有卡片编辑页，继续复用保存、发布、查看、接龙、管理和一键复用链路。
- 新增后端测试覆盖手动创建卡片流程。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `cd backend && pytest`：49 项通过。
- `cd backend && python -m compileall app`：通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 真实企业微信 `sync_msg` 仍等待企业微信认证/官方沟通后继续排查。
- `docs/png/` 为页面参考图，不纳入 Git。

### 下一步

优先继续把参考图中的「标签管理 / 搜索筛选 / 资源详情动作」做成可用功能，同时保持不引入支付、提现、订单、CRM 等 v0.1 外能力。

## 2026-06-09

### 本次目标

继续按页面参考图补齐资源库真实筛选体验和资源详情动作。

### 完成内容

- 资源库搜索从后端标题搜索改为前端多字段筛选，覆盖标题、项目名、详情、来源链接、分类和标签。
- 分类 chip 由真实卡片数据聚合生成，不再依赖固定视觉列表。
- 标签 chip 由真实卡片标签聚合生成，支持点击筛选。
- 资源卡片操作改为「详情 / 访问 / 复制 / 编辑」。
- 卡片查看页新增复制信息、复制来源链接、分享占位和访问详情入口。
- 前端聚合工具新增 `enrichCard` / `inferTags`，统一生成分类和标签。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `cd backend && pytest`：49 项通过。
- `cd backend && python -m compileall app`：通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 标签仍为现有卡片数据聚合标签，不是完整自定义标签 CRUD。
- 分享为小程序原生分享入口和占位提示，未接入分享次数统计。

### 下一步

建议继续补卡片编辑页视觉和字段体验，尤其是封面、来源链接、接龙配置、保存/发布状态，让手动添加后的编辑链路更接近参考图。

## 2026-06-09

### 本次目标

把资源库标签管理从聚合展示推进为可新增、可删除、可绑定到卡片的轻量分类标签体系。

### 完成内容

- 后端新增分类标签接口：`GET /api/categories`、`POST /api/categories`、`DELETE /api/categories/{id}`。
- 新增 `CategoryCreateRequest`。
- JSON/PostgreSQL 仓储补充分类标签列表、读取、保存、删除能力。
- 删除标签时会从该用户所有卡片的 `categoryIds` 中移除，避免失效标签残留。
- 小程序新增 `pages/tag-manage/index` 标签管理页。
- 资源库「管理标签」进入标签管理页。
- 手动添加资源页可加载并选择自定义标签，创建卡片时写入 `categoryIds`。
- 资源库分类/标签筛选优先使用真实自定义标签，未设置标签的卡片继续使用前端推断分类兜底。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `cd backend && pytest`：50 项通过。
- `cd backend && python -m compileall app`：通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 标签管理目前是轻量新增/删除，尚未支持重命名、排序和批量给历史卡片打标签。
- `docs/png/` 为页面参考图，不纳入 Git。

### 下一步

继续补卡片编辑页的标签选择和资源详情视觉，让已创建的卡片后续也能调整分类标签。

## 2026-06-09

### 本次目标

补齐卡片编辑页标签选择能力，并按参考图方向优化编辑页视觉和字段结构。

### 完成内容

- 卡片编辑页加载当前用户自定义标签。
- 已创建卡片可在编辑页选择 / 取消标签，保存时写回 `categoryIds`。
- 编辑页拆分为预览头、分类标签、基础信息、联系来源、接龙设置、底部操作栏。
- 新增封面链接、来源链接、地址必填开关等更完整字段入口。
- 发布前会先保存草稿，保存失败时不继续发布。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `cd backend && pytest`：50 项通过。
- `cd backend && python -m compileall app`：通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 编辑页仍使用 URL 输入作为封面来源，尚未接入本地图片上传。
- 标签仍不支持重命名、排序和批量打标。

### 下一步

建议继续优化管理页/访问详情页视觉，把访客、接龙名单、跟进状态做成更接近参考图的线索管理界面。

## 2026-06-09

### 本次目标

优化管理页/访问详情页和卡片查看页视觉，让线索管理和分享资源页更接近参考图。

### 完成内容

- 管理页改为访问详情/线索管理结构。
- 管理页展示总访问、访客、匿名 PV、接龙数、待跟进数。
- 登录访客列表展示头像、昵称和相对访问时间。
- 接龙组件改为线索卡片样式，展示头像、跟进状态、电话、地址、标记已跟进和删除无效。
- 卡片查看页改为正式分享资源页结构，包含大封面、资源标题、关键动作、统计卡片、资源详情和实名接龙区。
- 新增状态文案工具，用于展示已跟进、待跟进、草稿、已发布等可读状态。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `cd backend && pytest`：50 项通过。
- `cd backend && python -m compileall app`：通过。

### 未完成

- 微信开发者工具人工验收尚未执行。
- 分享仍使用小程序原生分享入口和占位提示，未接入分享次数统计。
- 管理页未新增客户备注、跟进记录时间线等 CRM 功能。

### 下一步

建议进入微信开发者工具做完整人工验收，优先检查页面视觉、tabBar、手动添加链路、标签筛选、编辑发布、访问详情和接龙管理。

## 2026-06-09

### 本次目标

以 AI 测试官 / 验收官身份，对当前 teamBuy / 资料整理助手 v0.1 MVP 开发结果执行验收与回归，并输出团队可直接使用的 Markdown 验收报告。

### 完成内容

- 使用项目内 `skills/qa-acceptance/SKILL.md` 的验收规则。
- 读取 `docs/stage2-docs/`、MVP 测试清单、阶段三 Codex 自测报告、UI 产品化自测报告、企业微信真实联调记录。
- 执行自动化回归：
  - `cd backend && pytest`：50 passed。
  - `cd backend && python -m compileall app`：通过。
  - `miniprogram/**/*.js` 执行 `node --check`：通过。
  - `miniprogram/**/*.json` 执行 JSON 解析：通过。
  - 密钥关键词扫描：仅命中 `.env.example` 占位值和后端环境变量读取代码，未发现真实密钥硬编码。
- 新增验收报告：`docs/qa/当前项目_验收报告m1.md`。

### 验收结论

不通过。

主要原因：

- 真实企业微信 `sync_msg` 仍返回 `48002 api forbidden`，企业微信导入主链路未跑通。
- 小程序仍为 mock 登录，真实微信 code 换 openid 未形成上线闭环。
- 真实 media_id 下载与对象存储端到端未验收。
- 小程序拨号、复制、分享、接龙、管理、一键复用等 P0 交互尚未在微信开发者工具或真机完成系统人工验收。

### 下一步

优先修复企业微信 `sync_msg` 权限配置问题，并补齐真实微信登录、小程序人工验收和真实媒体转存验收；阻断项解决后再进入 AI 测试官复测与回归。
# 2026-06-09

## 本次目标

继续按参考图收口小程序 UI，统一自定义导航，修正资源库/我的按钮居中，并补齐手动添加资源页的真实上传能力。

## 完成内容

- 所有小程序页面 JSON 已补齐 `navigationStyle: "custom"`。
- 资源库搜索按钮和我的页“编辑资料”按钮已修正垂直居中和字号。
- 手动添加资源页已补齐上传区、来源设置、展示开关和底部双按钮。
- 新增后端上传接口 `POST /api/uploads/asset`。
- 小程序上传走 `wx.uploadFile`，首张图片会自动回填 `coverUrl`。
- 修复 `app.json` 和页面 JSON 的编码问题。

## 验证结果

- `miniprogram/**/*.js` 执行 `node --check`：通过。
- `miniprogram/**/*.json` 执行 JSON 解析检查：通过。
- `cd backend && pytest`：51 项通过。

## 下一步

优先在微信开发者工具里验收“手动添加资源 -> 上传图片/视频 -> 保存草稿 -> 编辑/发布 -> 资源页查看”链路，再补卡片编辑页的素材上传和替换能力。
# 2026-06-09

## 本次补充

- 新增小程序 `custom-nav` 组件，统一按胶囊按钮位置对齐自定义导航标题。
- `app.js` 启动时缓存胶囊位置信息，前端页面通过本地导航工具读取。
- 标签管理、手动添加资源、资源编辑等二级页已补返回箭头。
- 上传资源返回地址已改为前端绝对 URL，解决上传后图片不预览的问题。
- 资源编辑页保存/发布改为通过 `getCurrentUser()` 兜底读取用户，并输出更明确的失败提示。

# 2026-06-10

## 本次目标

执行线索持久化第二阶段，并按用户要求把图片压缩格式从 JPEG 改为 WebP。

## 完成内容

- 后端图片上传处理改为 ffmpeg 转 WebP，视频继续转 H.264/AAC MP4。
- mock 媒体图片占位扩展名同步改为 `.webp`。
- 新增后端 `LeadReminder` 持久化模型和 `lead_reminders` 仓储能力。
- 新增 `GET/POST/PUT/DELETE /api/lead-reminders`，支持待联系、已联系、备注、跨资源列表和删除。
- 管理页高意向访客的加入待联系、标记已联系、取消待联系、备注保存已改为调用后端。
- 新增小程序 `pages/leads/index` 统一“待联系”列表，支持待联系 / 已联系 / 全部筛选、备注保存、标记已联系、恢复待联系、清除。
- 我的页新增“待联系线索”入口。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests -q`：60 项通过。

## 本次继续开发

- 新增客户资料库页面 `pages/customers/index`。
- 客户资料库集中展示已沉淀手机号、微信号、预算或意向等级的线索。
- 支持按意向等级筛选：全部、高意向、中意向、低意向、待判断。
- “我的”页新增客户资料库入口。
- “待联系”页新增客户资料库快捷入口。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 后端 `LeadReminder` 新增 `customerTags`，并支持 `PUT /api/lead-reminders/{id}` 持久化发布者私有客户标签。
- 线索详情页客户资料区新增客户标签输入，支持用逗号、空格或顿号分隔。
- 复制单个客户档案时补充客户标签字段。
- 客户资料库新增来源资料筛选和客户标签筛选，筛选条件可与搜索、意向等级、资料完整度和排序叠加。
- 复制客户摘要时补充客户标签列。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- `pytest backend\tests\test_app.py -q`：36 项通过。

## 本次继续开发

- 客户资料库卡片新增“设为今日跟进”快捷动作，直接写入当天 `nextFollowUpAt`。
- 客户资料库卡片新增“添加跟进记录”快捷动作，通过弹窗输入并追加到 `followUpLogs`。
- 客户资料库卡片新增“标记已联系”快捷动作，直接把线索状态更新为 `contacted`。
- 客户资料库卡片展示下次跟进日期和最近一条跟进记录摘要。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests\test_app.py -q`：36 项通过。

## 本次继续开发

- 客户资料库卡片拆分为客户资料区、跟进状态区、来源资料条和操作区。
- 电话、微信、预算集中展示，电话/微信继续支持一键复制。
- 最近查看、最近跟进时间、下次跟进和最近跟进摘要集中到跟进状态区。
- “设为今日跟进 / 添加跟进记录 / 标记已联系”保留为主快捷动作。
- “查看客户 / 资源详情”降为次级操作，降低卡片视觉拥挤感。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests\test_app.py -q`：失败 1 项，`/health` 数据库 backend 当前返回 `postgresql`，测试期望 `postgres`；该失败来自当前工作区已有后端改动，不属于本次客户卡片 UI 调整范围。

## 本次继续开发

- 客户资料库新增“清空筛选”，重置搜索、意向、资料完整度、来源、标签、活跃度和排序。
- 客户资料库新增“保存常用视图”，可保存当前筛选组合。
- 常用视图以胶囊展示，点击恢复筛选组合，点击关闭按钮移除。
- 常用视图保存在小程序本地 storage，最多保留 8 个。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests\test_app.py -q`：36 项通过。

## 本次继续开发

- 客户资料库当前筛选结果区域新增“复制跟进清单”。
- 跟进清单基于当前筛选结果生成，不复制全量客户。
- 清单逐个客户输出姓名、意向等级、电话、微信、最近跟进、下次跟进和来源资料。
- 本阶段不接群发或企业微信自动触达接口。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests\test_app.py -q`：36 项通过。

## 本次继续开发

- 客户资料库新增“活跃筛选”胶囊：全部活跃、近 7 天查看、近 7 天跟进、14 天未跟进。
- 近 7 天查看基于客户 `lastViewedAt`。
- 近 7 天跟进和 14 天未跟进基于最近一条跟进记录时间。
- 14 天未跟进排除无效和已完成客户。
- 客户卡片补充展示最近查看和最近跟进时间。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests\test_app.py -q`：36 项通过。

## 本次继续开发

- 线索详情页客户资料区前移到页面上方。
- 客户资料区新增摘要卡，突出昵称、意向等级和联系方式。
- 新增“复制档案”，可复制单个客户完整档案。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 客户资料库新增“复制客户摘要”。
- 复制内容基于当前筛选结果，字段包括姓名、手机号、微信号、预算、意向等级、来源资料。
- 摘要使用制表符分隔，便于粘贴到表格。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 客户资料库新增排序模式：高意向优先、最近更新。
- 客户资料库新增快捷筛选：全部资料、有电话、有微信、有预算。
- 排序、意向等级筛选、快捷筛选和搜索可叠加使用。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 客户资料库新增搜索框，支持搜索昵称、手机号、微信号、预算和来源资料。
- 客户资料库手机号、微信号新增一键复制。
- 搜索结果和意向等级筛选可叠加使用。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- `LeadReminder` 新增客户手机号、微信号、预算、意向等级字段。
- 线索详情页新增“客户资料”面板。
- 支持保存客户手机号、微信号、预算和意向等级。
- 本阶段仍为发布者私有客户档案，不做团队 CRM。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests -q`：60 项通过。

## 本次继续开发

- 新增线索详情页 `pages/lead-detail/index`。
- 待联系列表页瘦身为摘要卡，只展示来源资料、状态、最近备注/跟进/归档原因和关键动作。
- 备注、跟进记录、下次跟进日期、归档原因、结论状态操作迁移到线索详情页。
- 后端新增单条线索详情接口 `GET /api/lead-reminders/{id}`，并校验发布者权限。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests -q`：60 项通过。

## 本次继续开发

- 待联系页新增时间筛选：全部时间、今日、逾期、未来、未设置。
- 待联系线索列表按跟进优先级排序：逾期、今日、未来、未设置、已完成。
- 每条线索展示跟进状态标签。
- 跟进记录区从“最近一条”扩展为最近 3 条记录，便于看到处理进度。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 后端线索状态扩展为 `pending / contacted / invalid / paused / completed`。
- `LeadReminder` 新增 `closedAt` 和 `conclusionReason`。
- 待联系页新增“已归档”筛选。
- 待联系页每条线索支持填写归档原因，并一键标记为无效、暂不跟进、已完成。
- 管理页高意向访客状态展示同步支持归档状态，不再把归档线索误显示为“已联系”。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests -q`：60 项通过。

## 本次继续开发

- 待联系页顶部新增提醒看板，突出“今日待跟进”和“已逾期”数量。
- 点击今日 / 逾期提醒卡片会直接切到对应筛选。
- 新增“一键只看未处理线索”，快速回到待联系线索列表，并按跟进优先级排序。
- 本阶段未接入微信订阅消息或后台推送。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 下一步

建议在微信开发者工具里复测管理页高意向访客备注、加入待联系、标记已联系、取消待联系，以及“我的 -> 待联系线索”统一列表的筛选和状态同步。

## 本次补充

- 资源详情页发布者入口从普通按钮改为更明显的“线索管理”提示条。
- 待联系页筛选项改为胶囊背景样式。
- 待联系线索卡片新增“来源资料”区域，点击可进入资源详情页。
- 待联系线索操作区拆分为“资源详情”和“线索管理”，避免只跳管理页造成理解混乱。

## 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。

## 本次继续开发

- 后端 `LeadReminder` 增加 `nextFollowUpAt` 和 `followUpLogs`。
- `PUT /api/lead-reminders/{id}` 支持保存下次跟进日期和追加跟进记录。
- 待联系页新增下次跟进日期选择、跟进记录输入和“保存跟进”胶囊按钮。
- 待联系页展示最近一条跟进记录。

## 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- `pytest backend\tests -q`：60 项通过。
## 2026-06-10

### 生产回调联调部署

- 已通过 MobaXterm 会话对应的 SSH key 登录 `ubuntu@81.70.84.35`。
- 已将生产后端回调路由同步到服务器 `/home/ubuntu/teamBuy`，并重建/重启 `backend` 容器。
- 生产公网新回调地址 `https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback?echostr=hello-teamBuy` 已返回 `"hello-teamBuy"`。
- 生产 `/api/wecom/config-check` 已返回新 `callbackUrl`。
- 生产 `backend/.env` 的 `WECOM_CALLBACK_TOKEN` 已同步为企业微信页面当前 Token；更新前已备份为 `backend/.env.callback-backup-20260610-1616`。
- 若企业微信后台保存仍失败，下一步优先核对完整 43 位 `WECOM_ENCODING_AES_KEY` 是否与企业微信页面一致。

## 2026-06-10

### 企业微信客服回调地址拆分

- 后端企业微信客服回调从通用 `/api/wecom/callback` 调整为专用 `/api/wecom/kf/teamBuy/callback`。
- `GET` 验证和 `POST` 事件接收都走新路径，便于后续为其他客服、应用或开放平台回调预留独立入口。
- `/api/wecom/config-check` 返回的 `callbackUrl` 已同步为新路径。
- README、企业微信客服配置清单、真实联调记录、MVP 测试清单和腾讯云部署文档已同步新地址。

### 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- `pytest backend\tests\test_app.py -q -k "wecom_callback or wecom_config_check"`：4 项通过。
- `pytest backend\tests\test_app.py -q`：35 项通过，1 项失败；失败项为 `test_health_reports_database_configuration`，当前环境读取到 `DATABASE_BACKEND=postgresql`，测试期望 `postgres`，与本次回调路径改动无关。

## 2026-06-10

### 企业微信回调验证响应格式修复与生产保存

- 修复 `GET /api/wecom/kf/teamBuy/callback` 的 URL 验证响应格式：成功验证时改为 `text/plain` 原样返回 `echostr`，避免 FastAPI 将字符串编码成 JSON 字符串。
- 已更新本地测试，检查 `response.text == "hello-teamBuy"` 和 `content-type: text/plain`。
- 已同步 `backend/app/api/routes_wecom.py` 到生产 `/home/ubuntu/teamBuy`，重建并重启 `backend` 容器。
- 生产公网验证：`https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback?token=...&echostr=hello-teamBuy` 返回 `200 text/plain`，正文为 `hello-teamBuy`。
- 已在企业微信后台 `API接收消息` 页面保存新 URL：`https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback`，页面提示“保存成功”。
- 生产日志确认企业微信请求命中新路径 `/api/wecom/kf/teamBuy/callback?...` 并返回 200。

### 验证结果

- `python -m compileall backend\app backend\tests`：通过。
- `pytest backend\tests\test_app.py -q -k "wecom_callback or wecom_config_check"`：4 项通过。

## 2026-06-15

### 企业微信真实收档媒体失败容错

- 为明天申请企业微信资料归档接口后的真实联调补强主链路：真实 `sync_msg` 中图片/视频 `media_id` 下载失败时，不再让整批 `real-sync` 返回 502。
- 媒体下载失败会写入 `media_retry_jobs` 补偿队列，文本、链接和其他可处理内容仍继续生成待认领草稿。
- 修复测试发现的二次问题：真实同步时如果 media 下载失败，导入阶段不能再走 mock 媒体存储兜底，否则会生成假的 `/mock-media/...` URL，让验收误判为转存成功。
- 新增 `allow_media_storage_fallback` 控制：mock 链路继续允许兜底，真实 `sync_msg` 链路只使用真实下载并处理成功后的媒体 URL。
- 更宽回归发现图片压缩在当前环境下不能依赖 ffmpeg，否则会回退原图并导致 WebP 压缩测试失败；已改为图片使用 Pillow 转 WebP，视频继续使用 ffmpeg。
- 验证结果：`python -m compileall backend/app backend/tests` 通过；`pytest backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q` 41 项通过。

## 2026-06-15

### 企业微信回调修复提交前整理与产品名修正

- 当前正式产品名按用户修正统一为“资料整理助手”，旧名不再作为当前产品名新增使用。
- 小程序分享兜底标题从旧名资源改为“资料整理助手资源”。
- 已整理当前未提交范围：企业微信回调新路径、`PlainTextResponse` 验证响应、测试和配套文档属于可提交范围。
- 已明确排除 `backend/mock/runtime-state.json`、`docs/png/`、微信开发者工具本地配置、未确认验收草稿和疑似换行符扰动的大文档。
- 验证时当前 shell 没有 `python` / `pytest` 命令；改用 Codex Python 3.12 运行时和临时虚拟环境完成测试。
- 系统 Python 3.9 跑 pytest 会因 `dataclass(slots=True)` 报错，本项目测试需使用 Python 3.10+。
- `backend/requirements.txt` 原 `Pillow==12.2.0` 在当前包源不可安装，已调整为可安装的 `Pillow==11.3.0`。
- 验证结果：`python -m compileall backend/app backend/tests` 通过；`pytest backend/tests/test_app.py -q -k "wecom_callback or wecom_config_check"` 4 项通过；小程序 `.js` `node --check` 通过。
- 本轮要求后续每次操作中遇到的错误、原因和修复迭代都写入 `docs/dev-log.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/handoff-latest.md` 中对应位置，避免新会话重复犯错。

## 2026-06-17

### 资料整理助手插件化架构 Phase 1 骨架

- 按用户确认的完整架构计划，新增 `docs/stage2-docs/08-plugin-architecture.md`，固定“企业微信基座 + 混合驱动 Skill + 小程序笔记与展示页”的完整边界。
- 后端新增 `skill-router` 第一版无状态骨架：
  - `/api/skills/commands` 返回快捷指令注册表。
  - `/api/skills/route` 先匹配快捷指令，再规则匹配，未知输入返回确认菜单。
  - `/api/skills/content-to-note/run` 将 `ContentObject` 转为规则版 `UserNoteDraft`，本轮暂不持久化。
- 新增统一内容类型和 Skill 类型：`ContentObject`、`SkillCommand`、`IntentResult`、`SkillRun`、`UserNoteDraft`。
- 本轮明确不把微信笔记、聊天记录、链接文章拆成三个 Skill，而是统一进入 `content-to-note`，输入差异由 Adapter 处理。
- 保留独立 `note-to-comic-image`，展示页使用 `showcase-builder` 可视化配置，不做 AI 全自动生成。
- 遇到一次补丁失败：`backend/app/api/dependencies.py` 已在前轮开发中改成 `build_repository()` 和 `WecomClient/WecomMockService` 装配方式，旧预期的导入片段不匹配。已按当前文件实际结构重贴补丁并继续。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：6 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：47 项通过。

## 2026-06-17

### 企业微信导入接入 ContentObject -> content-to-note

- 已将长期架构规则补入 `AGENTS.md`，明确完整架构文档入口、混合驱动策略、文字类来源统一进 `content-to-note`、漫画图和展示页的边界。
- 已更新 `docs/project-memory.md`，把“企业微信基座 + 混合驱动 Skill + 小程序笔记与展示页”作为长期项目记忆。
- 新增 `ContentObjectAdapter`，将现有企业微信 `RawMessage` 批次转换为 `ContentObject`：
  - 文本进入 `textBlocks`。
  - 图片/视频/file 进入 `media`。
  - 链接进入 `links`。
  - 位置消息追加为结构化前缀文本，供规则版笔记草稿提取。
- `import_synced_messages()` 已从旧的直接 `CardParserService.build_card_draft()` 改为：
  - `RawMessage` 批次
  - `ContentObject`
  - `content-to-note`
  - `UserNoteDraft`
  - 兼容映射为现有 `Card` 草稿
- 本轮保留旧 `generatedCard` 输出，不要求小程序立即改成正式 `UserNote`，避免破坏当前认领、编辑、发布链路。
- 迭代中发现链接导入兼容问题：链接同时存在 `thumbUrl` 和转存媒体时，新逻辑优先选了转存媒体，导致旧测试期望的文章封面不一致。已修正为 `link_article` 优先使用链接 `coverUrl`，普通微信笔记仍优先使用转存图片。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "mock_import or link_import or note_import or content_object or real_sync_records_media_retry or real_sync_downloads"`：7 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：48 项通过。

## 2026-06-17

### P0/P1/P2 路线图归档

- 已新增 `docs/stage2-docs/09-p0-p2-roadmap.md`，将 P0/P1/P2 从聊天结论沉淀为项目路线图。
- P0 拆成三阶段：
  - 第一阶段：企业微信客服 `sync_msg` 过渡入口跑稳。
  - 第二阶段：正式 `UserNote` 和小程序笔记库。
  - 第三阶段：用户开通企业微信会话内容存档后接入 `wecom-archive-core`。
- 明确企业微信客服和会话内容存档不是简单换接口；二者可共用后续 `ContentObject -> content-to-note -> UserNote`，但入口权限、游标、媒体、审计和合规处理不同。
- 下一步按 P0 第一阶段继续：优先补 `SkillRun` 持久化和导入失败日志。

## 2026-06-17

### 工作区脏文件归档与清理

- 用户确认项目整体资料不要长期悬在工作区，后续每次提交后应尽量保持干净。
- 已将 `docs/png/` 作为项目视觉参考资料准备纳入版本库归档。
- 已将 `docs/qa/当前项目_验收报告m1.md` 作为验收资料准备纳入版本库，并修正当前产品名为“资料整理助手”。
- 已将 `miniprogram/project.config.json` 作为小程序项目配置准备纳入版本库。
- 已将 `miniprogram/project.private.config.json` 加入 `.gitignore`，避免个人微信开发者工具配置污染提交。
- 已恢复 `backend/mock/runtime-state.json` 的本地运行态改动，避免把测试运行数据提交。
- 已恢复 `docs/悦享互动宝 MVP 产品开发文档.md` 的换行符扰动，避免无意义大 diff。

## 2026-06-17

### P0 第一阶段：SkillRun 持久化和导入失败日志

- 新增后端领域模型 `SkillRun`，并接入 JSON / PostgreSQL 仓储。
- `AppState` 新增 `skill_runs`，PostgreSQL 自动创建 `skill_runs` payload 表和常用索引。
- 企业微信导入成功时，`content-to-note` 的 `SkillRun` 会持久化，记录：
  - `skillId`
  - `status`
  - `inputSnapshot`
  - `outputRef`
  - `modelProvider`
  - `startedAt` / `endedAt`
- 企业微信导入中 `content-to-note` 失败时，不再只抛异常或静默中断：
  - 导入批次标记为 `failed`。
  - 失败通知写入 `import_notifications`。
  - 失败 `SkillRun` 写入 `skill_runs`。
  - 失败日志可通过接口查询。
- 新增查询接口：
  - `GET /api/skills/runs`
  - `GET /api/wecom/import-failures`
- 新增回归测试覆盖成功 SkillRun 持久化、失败 SkillRun 持久化和失败通知。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "skill_run or import_failure or content_object"`：3 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：50 项通过。

## 2026-06-17

### P0 第一阶段：导入通知口径和后台重试可视化

- 补强导入通知文案：
  - 成功通知改为“已整理完成，请打开小程序认领、编辑和分类”。
  - 成功但有媒体未转存时，会提示有媒体进入后台重试队列。
  - 失败通知会带失败原因，避免只提示“检查内容后重试”。
- 导入通知 channel 现在区分 `mock` 和 `wecom`，真实 `sync_msg` 导入使用 `wecom`。
- 新增失败重试看板接口：`GET /api/wecom/retry-dashboard`。
  - 汇总失败媒体数量、失败 SkillRun 数量、失败通知数量。
  - 返回媒体失败列表、SkillRun 失败列表、失败通知列表和可用重试接口。
- 新增失败导入重试接口：`POST /api/wecom/import-failures/retry?importBatchId=...`。
  - 需要 admin token。
  - 会读取失败批次原始消息，重新执行 `ContentObject -> content-to-note -> generatedCard`。
  - 重试成功后会生成新的成功通知和卡片草稿。
- 为 JSON / PostgreSQL 仓储补齐按导入批次读取原始消息能力，服务失败导入重试。
- 本轮没有新增小程序页面，只先把后台可视化和重试所需接口打通，方便后续后台/小程序接入。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "notification or import_failure or media_retry or mock_import"`：5 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：50 项通过。

## 2026-06-17

### P0 第二阶段：正式 UserNote 模型和“我的笔记”基础接口

- 新增正式 `UserNote` 领域模型，并接入 JSON / PostgreSQL 仓储。
- `ImportBatch` 新增 `generatedNoteId`，用于关联导入批次与正式笔记。
- 企业微信导入成功后同时生成：
  - `UserNote` 草稿，作为长期笔记库对象。
  - 兼容 `Card` 草稿，继续服务现有小程序待认领、编辑、发布链路。
- 认领导入时会同步把 `UserNote.ownerUserId` 改为认领用户，并把 note 状态从 `draft` 改为 `active`。
- `SkillRun.outputRef` 的长期口径调整为指向 `UserNote` ID；兼容 card 仍通过 `ImportBatch.generatedCardId` 关联。
- 新增“我的笔记”基础接口：
  - `GET /api/notes`
  - `GET /api/notes/{noteId}`
  - `PUT /api/notes/{noteId}`
  - `DELETE /api/notes/{noteId}`
- 删除笔记采用软删除 `status=deleted`，不删除原始企业微信消息、导入批次或兼容卡片。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "user_note or claim_import or note_crud"`：2 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：51 项通过。

## 2026-06-17

### P0 第二阶段：小程序“我的笔记”基础页面

- 新增小程序页面：
  - `pages/notes/index`：我的笔记列表、搜索、打开编辑、删除。
  - `pages/note-edit/index`：笔记详情、标题/摘要/正文/电话/位置编辑、保存、删除。
- `services/api.js` 新增笔记接口：
  - `fetchNotes`
  - `fetchNote`
  - `updateNote`
  - `deleteNote`
- 待认领导入前端 API 已同步归一化 `generatedNote`。
- “我的”页新增“我的笔记”入口；资源库快捷区新增“我的笔记”入口。
- 资源库快捷入口从 3 个增至 4 个后，已改为可换行的两列布局，避免移动端挤压。
- `app.json` 已注册两个新页面，并将全局标题修正为“资料整理助手”。
- WXML 展示兜底从 `||` 调整为三元表达式，降低小程序模板兼容风险。

### 验证结果

- 小程序所有 `.js` 执行 `node --check`：通过。
- 小程序所有 `.json` 解析：通过。
- 小程序内扫描 `悦享互动宝` / `悦享`：无残留。

## 2026-06-17

### P0 第三阶段：企业微信会话内容存档配置与 wecom-archive-core 骨架

- 企业微信会话内容存档功能已由用户开通，后台页面地址为 `https://work.weixin.qq.com/wework_admin/frame#financial/corpEncryptData`。
- 本轮生成会话内容存档 RSA 密钥对：
  - 私钥：`backend/secrets/wecom_archive_private.pem`
  - 公钥：`backend/secrets/wecom_archive_public.pem`
  - `*.pem` 已被 `.gitignore` 排除，不提交 Git。
- 新增配置文档：`docs/stage2-docs/10-wecom-archive-config.md`。
  - 已记录企业微信后台需要填写的 RSA Public Key。
  - 已记录 `WECOM_ARCHIVE_SECRET`、私钥路径、公钥路径和后续 SDK 路径。
- `backend/.env.example` 新增会话内容存档配置项。
- 新增会话内容存档领域模型：
  - `WecomArchiveCursor`
  - `WecomArchiveMessage`
- JSON / PostgreSQL 仓储已支持：
  - `wecom_archive_cursors`
  - `wecom_archive_messages`
- 新增接口：
  - `GET /api/wecom/archive/config-check`
  - `GET /api/wecom/archive/cursor`
  - `GET /api/wecom/archive/messages`
  - `POST /api/wecom/archive/mock-messages`
- 原始会话存档消息查询和样例写入均需要 admin token。
- 浏览器操作记录：
  - Codex 内置浏览器当前页确认为企业微信会话内容存档配置地址。
  - 页面 DOM/截图读取连续超时，未自动点击保存，避免误配置。
  - 后续建议用户按 `docs/stage2-docs/10-wecom-archive-config.md` 复制公钥到后台保存，保存后把 Secret 写入生产 `.env`。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive or wecom_config_check"`：4 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：54 项通过。

## 2026-06-17

### P0 第三阶段：会话存档事件服务器回调补齐

- 新增专用会话存档事件服务器接口：
  - `GET /api/wecom/archive/callback`
  - `POST /api/wecom/archive/callback`
- `GET` 验证成功时使用 `PlainTextResponse` 原样返回 `echostr`，用于企业微信后台保存 URL。
- archive callback 默认复用现有 `WECOM_CALLBACK_TOKEN` 和 `WECOM_ENCODING_AES_KEY`。
- 后续如需拆独立配置，可设置：
  - `WECOM_ARCHIVE_CALLBACK_TOKEN`
  - `WECOM_ARCHIVE_ENCODING_AES_KEY`
- `GET /api/wecom/archive/config-check` 已返回 `callbackUrl`、callback token 配置状态和 AESKey 配置状态。
- 用户曾把真实 `WECOM_ARCHIVE_SECRET` 写入配置文档；已从 `docs/stage2-docs/10-wecom-archive-config.md` 移除，保留占位符。真实 Secret 只能放 `.env`，不得写入 Git 文档。

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive or wecom_config_check"`：7 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：57 项通过。

### 部署结果

- 已提交并推送：`1b9cf52 feat: add wecom archive callback`。
- 尝试 SSH 部署生产：`ubuntu@81.70.84.35` 返回 `Permission denied (publickey)`，当前 Codex 本机没有可用服务器 SSH 权限。
- 公网验证：
  - `GET https://teambuy.lifelove.top/api/wecom/archive/callback?...` 当前返回 404。
  - `GET https://teambuy.lifelove.top/api/wecom/archive/config-check` 当前返回 404。
- 结论：代码已到 GitHub，生产尚未部署。需要提供服务器 SSH 权限，或在服务器手动执行部署命令。

### 生产部署补充

- 用户提供服务器 SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`。
- 已用该 key 登录 `ubuntu@81.70.84.35` 并完成生产部署。
- 服务器 `git fetch origin` 曾长时间卡住，改为：
  - 先备份服务器 `backend/app/api/routes_wecom.py` 本地 diff 到 `/home/ubuntu/teamBuy-deploy-backups/`。
  - 用 `rsync` 同步本地已验证的 `backend/app/`、`requirements.txt`、`.env.example` 到服务器。
  - 同步 `backend/secrets/wecom_archive_private.pem` 和 `backend/secrets/wecom_archive_public.pem` 到服务器。
- 生产 `backend/.env` 已配置会话存档项，并确认：
  - `WECOM_ARCHIVE_ENABLED` 已设置。
  - `WECOM_ARCHIVE_SECRET` 已设置，长度 43。
  - `WECOM_CALLBACK_TOKEN` 已设置，长度 28。
  - `WECOM_ENCODING_AES_KEY` 已设置，长度 43。
- 第一次生产 `config-check` 发现密钥路径被解析为 `/backend/secrets/...`，容器内实际路径应为 `/app/secrets/...`。已将生产 `.env` 修正为：
  - `WECOM_ARCHIVE_PRIVATE_KEY_PATH=/app/secrets/wecom_archive_private.pem`
  - `WECOM_ARCHIVE_PUBLIC_KEY_PATH=/app/secrets/wecom_archive_public.pem`
- 已重建并重启生产 backend 容器。
- 公网验证通过：
  - `GET https://teambuy.lifelove.top/api/wecom/archive/config-check` 返回 `success=true` 且 `missing=[]`。
  - `GET https://teambuy.lifelove.top/api/wecom/archive/callback?token=...&echostr=hello-archive` 返回 `hello-archive`。
- 操作中遇到一次脚本错误：远程 Python 状态打印脚本因 shell 引号和 f-string 嵌套导致 `NameError: name 'SET' is not defined`。已改为普通字符串拼接后验证通过。

### 生产 archive callback Token 修正

- 用户截图中填写的是本地 `backend/.env` 的 `WECOM_CALLBACK_TOKEN` / `WECOM_ENCODING_AES_KEY` 实际值。
- 核对发现本地 `.env` 与生产服务器 `.env` 中这两项不一致：
  - 本地 Token mask：`MB4rf...1ygTu`
  - 生产旧 Token mask：`mHJCN...FuUhL`
- 为避免破坏已跑通的微信客服回调，没有覆盖生产原 `WECOM_CALLBACK_TOKEN` / `WECOM_ENCODING_AES_KEY`。
- 已把本地这组值写入生产 archive 专用配置：
  - `WECOM_ARCHIVE_CALLBACK_TOKEN`
  - `WECOM_ARCHIVE_ENCODING_AES_KEY`
- 重启 backend 后，公网验证：
  - `GET /api/wecom/archive/callback?token=...&echostr=archive-token-ok` 返回 `archive-token-ok`。
- 容器重启瞬间 Nginx 曾短暂返回 502，等待后端启动完成后恢复正常。
- 用户确认企业微信后台“接收事件服务器”已保存成功。

## 2026-06-17

### P0 会话存档真实拉取与 content-to-note 入口

- 新增企业微信会话内容存档 SDK 客户端：
  - `backend/app/services/wecom_archive_client.py`
  - 支持检查 SDK 配置、调用 `GetChatData`、解密 `encrypt_random_key`、调用 `DecryptData`、输出解密后的消息对象。
- 新增会话存档拉取接口：
  - `POST /api/wecom/archive/pull`
  - 需要 admin token。
  - 从当前 `wecom_archive_cursors.seq` 开始拉取，写入 `wecom_archive_messages`，成功后推进游标。
  - SDK 缺失或拉取失败时写入 failed 游标，并返回 502，不伪装成成功。
- 新增会话存档处理接口：
  - `POST /api/wecom/archive/process`
  - 需要 admin token。
  - 将已解密、未处理的 `WecomArchiveMessage` 转成 `ContentObject`，正式进入 `content-to-note`，生成 `ImportBatch`、`Card`、`UserNote` 和 `SkillRun`。
  - 处理成功后在原始归档消息上记录 `generatedNoteId`、`generatedCardId`、`processedAt`，重复调用不会重复生成笔记。
  - 处理失败时在原始归档消息上记录 `processError`，方便后台排查。
- `ContentObjectAdapter` 新增 `from_wecom_archive_message`：
  - `text` 进入文本块。
  - `link` 进入链接对象。
  - `image` / `video` / `file` 先保存媒体引用，当前提示“媒体稍后转存”。
  - `location` 转为位置文本。
- 配置检查接口补充：
  - `sdkConfigured`
  - `pullLimit`
- `.env.example` 新增：
  - `WECOM_ARCHIVE_PULL_LIMIT`
  - `WECOM_ARCHIVE_SDK_TIMEOUT_SECONDS`
  - `WECOM_ARCHIVE_PROXY`
  - `WECOM_ARCHIVE_PROXY_PASSWORD`

### 验证结果

- `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：9 项通过。
- `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：60 项通过。

### 本轮迭代和错误记录

- 初始实现时需要确认 `encrypt_random_key` 的解码方式；最终按会话存档 SDK 返回值使用 base64 解码后再 RSA 私钥解密。
- 这轮没有安装官方 Linux SDK `.so` 文件，因此本地测试用 fake client 覆盖拉取成功/失败分支；生产真实拉取仍依赖服务器配置 `WECOM_ARCHIVE_SDK_LIB_PATH`。
- P0 当前代码链路已经完整，但真实企业微信数据验收必须等官方 SDK 库文件部署到服务器后执行。

### 生产部署与公网验证

- 已提交本地代码：`5e104f0 feat: complete p0 wecom archive import`。
- 已用 `rsync` 同步后端代码到生产服务器 `/home/ubuntu/teamBuy/backend/app/`，并同步 `backend/.env.example`、`backend/requirements.txt`。
- 已在生产 `backend/.env` 追加新增配置键：
  - `WECOM_ARCHIVE_PULL_LIMIT`
  - `WECOM_ARCHIVE_SDK_TIMEOUT_SECONDS`
  - `WECOM_ARCHIVE_PROXY`
  - `WECOM_ARCHIVE_PROXY_PASSWORD`
- 生产原本没有 `WECOM_ADMIN_TOKEN`，导致 `/api/wecom/archive/pull` 和 `/api/wecom/archive/process` 返回 403。已生成服务器专用 `WECOM_ADMIN_TOKEN` 写入生产 `.env`，只记录长度 43，不记录真实值。
- 已重建并重启生产 backend 容器。
- 公网验证：
  - `GET /api/wecom/archive/config-check`：`missing=[]`、`privateKeyReadable=true`、`sdkLibReadable=false`、`sdkConfigured=false`、`pullLimit=100`。
  - `POST /api/wecom/archive/pull`：带 admin token 调用返回 502，错误为 `会话内容存档 SDK 配置不完整: WECOM_ARCHIVE_SDK_LIB_PATH`，并写入 failed cursor。
  - `POST /api/wecom/archive/process`：带 admin token 调用返回 200，`processedCount=0`、`failedCount=0`。

### 部署中遇到的小错误

- 本机验证脚本第一次使用 `python`，当前环境没有该命令，返回 `zsh:1: command not found: python`；已改用 `python3`。
- 第一次生产管理接口验证假设 token 名为 `ADMIN_TOKEN`，实际配置项是 `WECOM_ADMIN_TOKEN`；已按代码配置项修正，并在生产补齐。

## 2026-06-17

### 会话存档官方 SDK 已部署生产

- 用户下载官方 Linux x86 v3.0 SDK：
  - 本机路径：`/Users/yiyi/Downloads/sdk_x86_v3_20250205.tgz`
  - 包内目标文件：`C_sdk/libWeWorkFinanceSdk_C.so`
- 已确认 SDK 文件为 Linux x86-64 动态库。
- 已上传到生产服务器：
  - 宿主机路径：`/home/ubuntu/teamBuy/backend/secrets/libWeWorkFinanceSdk_C.so`
  - 容器路径：`/app/secrets/libWeWorkFinanceSdk_C.so`
- 已设置生产 `.env`：
  - `WECOM_ARCHIVE_SDK_LIB_PATH=/app/secrets/libWeWorkFinanceSdk_C.so`
- 初次配置后 `config-check` 仍显示 `sdkLibReadable=false`，原因是 `docker-compose.yml` 没有把宿主机 `backend/secrets` 挂进容器，容器只能看到镜像构建时的旧 `/app/secrets`。
- 已修正 `docker-compose.yml`：
  - 增加只读挂载 `./backend/secrets:/app/secrets:ro`
- 重启 backend 后公网验证：
  - `GET /api/wecom/archive/config-check`：`missing=[]`、`sdkLibReadable=true`、`sdkConfigured=true`。
  - `POST /api/wecom/archive/pull`：返回 200，`rawCount=0`、`savedCount=0`，cursor 状态为 success。
  - `POST /api/wecom/archive/process`：返回 200，`processedCount=0`、`failedCount=0`。
- 结论：
  - 官方 SDK、Secret、私钥和网络调用已经跑通。
  - 当前企业微信没有新归档消息可拉取；下一步需要人工发一条真实会话消息，再执行 `pull -> process -> 小程序我的笔记` 验收。

### 21:57 真实消息拉取验证

- 用户反馈 2026-06-17 21:57 发送测试消息：“你好啊”。
- 生产服务器时间确认：`2026-06-17 21:59 +0800`。
- 两次调用生产 `POST /api/wecom/archive/pull`：
  - 21:58 左右：返回 200，`rawCount=0`、`savedCount=0`。
  - 21:59 左右：返回 200，`rawCount=0`、`savedCount=0`。
- `GET /api/wecom/archive/messages?limit=20` 返回空数组。
- 后端容器日志显示接口调用均为 200，没有 SDK 错误。
- 当前判断：后端 SDK 调用链路正常，但企业微信尚未返回该测试消息。下一步优先核对发送消息的成员是否在会话存档开启范围内、消息对象是否属于会话存档支持的外部联系人会话，以及是否需要等待企业微信归档延迟。

### 22:11 真实消息拉取验证

- 用户反馈 2026-06-17 22:11 发送测试消息：“今天天气怎么样”。
- 22:13 调用生产 `POST /api/wecom/archive/pull`：
  - 返回 200。
  - `rawCount=0`、`savedCount=0`。
  - cursor 仍为 `seq=0`、`status=success`。
- `GET /api/wecom/archive/messages?limit=50` 仍为空数组。
- `POST /api/wecom/archive/process` 返回 200，`processedCount=0`。
- 当前判断保持不变：SDK 调用链路通，但企业微信没有返回测试会话数据。优先排查会话存档开启范围、成员服务版生效状态、聊天对象是否为外部联系人，以及是否使用了企业微信客服通道而非普通外部联系人会话。

### 企业微信客服通道排查

- 用户确认会话存档开启范围、外部联系人会话和服务版生效状态无明显问题，要求排查是否走了企业微信客服通道。
- 生产 `GET /api/wecom/config-check`：
  - `useMock=false`
  - `missing=[]`
  - `configured=true`
  - callback URL 为 `https://teambuy.lifelove.top/api/wecom/kf/teamBuy/callback`
- 生产 `POST /api/wecom/real-sync` 调用企业微信客服 `sync_msg` 失败：
  - HTTP 502
  - 企业微信返回 `errcode=48002`
  - `errmsg=api forbidden`
  - 提示来源 IP：`81.70.84.35`
- 最近后端日志未看到企业微信访问 `/api/wecom/kf/teamBuy/callback`，只看到手动触发 `/api/wecom/real-sync` 后返回 502。
- 当前判断：
  - 客服通道在本系统侧配置项齐全。
  - 但企业微信客服 API 权限/可信 IP/后台接收服务器配置尚未完全打通，当前不能通过客服 `sync_msg` 验证用户消息是否进入客服通道。

### AgentId 对应关系排查

- 用户反馈企业微信后台有两个自建应用：
  - `AgentId=1000003`
  - `AgentId=1000004`
- 当前生产 `.env` 没有保存 `WECOM_AGENT_ID`，只有 `WECOM_SECRET`、`WECOM_ARCHIVE_SECRET`、`WECOM_OPEN_KFID`。
- 使用生产 `WECOM_SECRET` 调用 `gettoken` 成功：
  - `errcode=0`
  - `errmsg=ok`
- 继续调用 `agent/get` 查询 `1000003` 和 `1000004` 均失败：
  - `errcode=60020`
  - `errmsg=not allow to access from your ip`
  - 来源 IP：`81.70.84.35`
- 当前无法从 API 侧确认当前 `WECOM_SECRET` 对应哪个 AgentId。需要在企业微信后台给对应自建应用加入可信 IP `81.70.84.35` 后，再查 `agent/get`。

### 22:36 唯一文本归档验证

- 用户反馈 2026-06-17 22:36 发送测试消息：“归档测试 2218 资料整理助手”。
- 调用生产 `POST /api/wecom/archive/pull`：
  - 返回 200。
  - `rawCount=0`、`savedCount=0`。
  - cursor 仍为 `seq=0`、`status=success`。
- `GET /api/wecom/archive/messages?limit=100` 返回空数组。
- 唯一文本“归档测试 2218 资料整理助手”命中数为 0。
- `POST /api/wecom/archive/process` 返回 200，`processedCount=0`。
- 当前结论进一步收敛：官方 SDK 调用成功但企业微信持续返回 0 条数据，问题不在后端保存/处理链路，优先回到企业微信后台确认会话存档是否已产生可拉取数据。

### 23:41 归档消息拉取成功与修复记录

- 用户反馈 2026-06-17 23:41 再次发送测试消息：“归档测试 2218 资料整理助手”。
- 第一次拉取出现新错误：
  - 企业微信 `GetChatData` 已返回 1 条数据。
  - `DecryptData` 返回 `10008`。
  - 根因：`backend/app/services/wecom_archive_client.py` 绑定官方 C SDK `DecryptData` 时错误传入了 `sdk` 指针。
  - 官方头文件实际签名为 `int DecryptData(const char *encrypt_key, const char *encrypt_msg, Slice_t *msg)`。
  - 已修正 ctypes 绑定和调用参数。
- 修正后第二次拉取出现落库错误：
  - 企业微信 `msgtime` 返回毫秒时间戳整数 `1781710904435`。
  - `WecomArchiveMessage.msgTime` 模型要求字符串。
  - 已在 `AppService.save_wecom_archive_messages` 增加 `_normalize_archive_msg_time`，兼容秒/毫秒时间戳和字符串。
- 验证结果：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：9 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：60 项通过。
- 生产重新部署后验证成功：
  - `POST /api/wecom/archive/pull`：`rawCount=1`、`savedCount=1`、cursor 推进到 `seq=1`。
  - 实际收到文本：`归档测试2218资料管理助手`。
  - `msgTime` 归一化为 `2026-06-17T23:41:44.435000+08:00`。
  - `POST /api/wecom/archive/process`：`processedCount=1`、`failedCount=0`。
  - 生成 `UserNote`：`note_fc9f58783e`。
  - 生成兼容 `Card`：`card_ec1e041dde`。
- 结论：
  - P0 会话内容存档真实链路已跑通：企业微信外部联系人消息 -> SDK 拉取解密 -> 原始归档入库 -> content-to-note -> UserNote。

## 2026-06-18

### 小程序上传 sitemap 修复

- 用户在微信开发者工具点击“上传”时报错：
  - `Error: 系统错误，错误码：-80055`
  - `Invalid SiteMap, sitemap错误，缺少rules字段`
- 检查发现 `miniprogram/sitemap.json` 原本为 `{"rules":[]}`。
- 部分微信开发者工具版本会把空 `rules` 视为无效 sitemap。
- 已改为明确允许所有页面：
  - `{"action":"allow","page":"*"}`
- 同时临时将小程序 `apiBaseUrl` 指向生产后端，方便测试真实会话存档生成的笔记。
- 验证：
  - 小程序 JS `node --check` 通过。
  - `app.json`、`project.config.json`、`sitemap.json` JSON 校验通过。

### 小程序首页补充待认领入口

- 用户登录后首页没有“导入/待认领”入口，导致真实企业微信归档生成的 `import_f077fcf5a3` 无法被自然发现。
- 已在首页快捷区新增“待认领”入口，跳转到 `/pages/imports/index`。
- 快捷区改为可换行三列布局，避免 5 个入口挤在一行。
- 验证：
  - 小程序 JS `node --check` 通过。
  - `app.json`、`project.config.json`、`sitemap.json` JSON 校验通过。

### 自动归档 worker 与新导入页简化

- 后端新增轻量自动归档 worker：
  - `backend/app/services/wecom_archive_worker.py`
  - 启动后循环执行 `pull_wecom_archive_messages -> process_wecom_archive_messages`。
  - worker 默认关闭，通过 `WECOM_ARCHIVE_WORKER_ENABLED=true` 开启。
  - 间隔由 `WECOM_ARCHIVE_WORKER_INTERVAL_SECONDS` 控制，生产当前为 60 秒。
- `GET /api/wecom/archive/config-check` 新增：
  - `workerEnabled`
  - `workerIntervalSeconds`
- 生产已打开：
  - `WECOM_ARCHIVE_WORKER_ENABLED=true`
  - `WECOM_ARCHIVE_WORKER_INTERVAL_SECONDS=60`
- 生产公网验证：
  - `sdkConfigured=true`
  - `workerEnabled=true`
  - `workerIntervalSeconds=60`
  - `missing=[]`
- 小程序“待认领”页改为“新导入资料”：
  - 默认只展示标题、内容和来源信息。
  - 增加模板按钮：通用 / 中介 / 团购。
  - 选择模板后展示建议补充字段。
  - 认领后优先进入笔记编辑页，不再进入旧卡片编辑页。
  - 笔记编辑页顶部显示当前模板字段提示。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive or worker"`：10 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：61 项通过。
  - 小程序 JS `node --check` 通过。
  - 小程序 JSON 校验通过。
- 本轮部署中出现一次 rsync 目标路径错误：
  - 误把文件同步到服务器 `/home/ubuntu/teamBuy/backend/app/PLACEHOLDER/`。
  - 已逐个删除误建的 `config.py`、`main.py`，再移除空目录。

### 03:30 图片归档 worker 验证

- 用户反馈 2026-06-18 03:30 左右发送两个图片和一条文字。
- 生产 worker 状态：
  - `workerEnabled=true`
  - `workerIntervalSeconds=60`
  - cursor 已推进到 `seq=4`
  - `lastSyncedAt=2026-06-18T03:31:40+08:00`
- 归档消息结果：
  - `seq=3`：`msgType=image`，`msgTime=2026-06-18T03:31:26.537+08:00`，包含 `sdkfileid`、`md5sum`、`filesize`，已生成 `note_f6cfe62264`。
  - `seq=4`：`msgType=image`，`msgTime=2026-06-18T03:31:27.713+08:00`，包含 `sdkfileid`、`md5sum`、`filesize`，已生成 `note_866ce69346`。
  - 03:30 附近未看到新文本消息；最近文本是 `seq=2`，内容为“高士图 13024199490  明天出去玩”，时间 `2026-06-18T03:04:41+08:00`。
- 两条图片目前进入“新导入资料”，标题/正文为“收到image素材，媒体稍后转存。”，各自 `noteMediaCount=1`。
- 当前结论：
  - 自动 worker 已能拉取并处理图片消息。
  - 会话存档图片本体下载/转存尚未实现，当前只保存 `sdkfileid` 引用，下一步应实现 `GetMediaData -> storage -> media.url`。

### 03:31 文本归档补查

- 用户纠正 03:30 左右发送的文本为“今天天气很好啊”。
- 手动补查生产 `/api/wecom/archive/messages?limit=50` 后确认：
  - `seq=5`
  - `msgType=text`
  - `msgTime=2026-06-18T03:31:36.779+08:00`
  - `text=今天天气很好啊`
  - `generatedNoteId=note_8bbadcfa3d`
- cursor 已推进到 `seq=5`。
- 本轮前一次排查只看到了 `seq=3/4` 图片和 `seq=2` 旧文本，漏看了后续 `seq=5` 文本。后续排查多消息场景时，必须先按 seq 倒序完整列出最近消息，再下结论。

### 03:39 房产微信笔记解析与 5 秒聚合

- 用户 2026-06-18 03:39 发送一个房产类型微信笔记。
- 生产归档消息形态：
  - `seq=6`
  - `msgType=note`
  - `msgTime=2026-06-18T03:39:11.786+08:00`
  - `info.items` 内包含 text、location、text `[视频]`、5 个 image。
- 原实现不识别 `note`，生成内容为“企业微信note归档 / 暂无正文”。
- 已实现：
  - `ContentObjectAdapter` 支持 `msgType=note`。
  - 解析 `info.items[].content` JSON。
  - text 进入正文，location 转为 `位置：...`，image/video/file 进入 media 引用。
  - 忽略 `[图片]` / `[视频]` / `[文件]` 这类占位文本。
- 已实现 5 秒聚合：
  - 同一会话。
  - 同一发送人。
  - 非 `note` 类型。
  - 相邻消息时间差不超过 5 秒。
  - 合并为一个 `ContentObject -> UserNote`。
  - 原始归档消息仍逐条保存，业务产物合并生成。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：12 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：63 项通过。
- 生产部署后用同一条 note 的 mock 副本验证：
  - `corpId=ww_archive_verify`
  - `seq=9001`
  - 生成 `note_da48e67e5e`
  - 正文包含小区、户型、价格、商圈、备注、位置。
  - `mediaCount=5`
  - `locationText=湖南省长沙市雨花区嘉雨路碧桂园城市之光`
- 注意：
  - 生产验证副本会出现在待认领列表中，标题为“🍓小区：碧桂园城市之光1栋1210...”。

### 会话存档图片展示原因确认与后续开发原则记录

- 用户反馈：微信笔记进入后，小程序里没有看到图片。
- 当前确认：
  - 归档消息中的图片已经进入系统，`note` 解析和普通图片消息都会保存 `sdkfileid/md5sum/filesize` 等 media 引用。
  - 但会话存档图片本体下载/转存尚未实现，所以小程序目前没有可展示的图片 URL。
  - 重新发送同类图片只能再次生成 media 引用，不能自动解决图片不显示。
- 已记录后续原则：
  - 企业微信会话存档媒体必须走服务端 `GetMediaData -> 媒体处理/转存 -> UserNote.media.url`。
  - 小程序本地缓存只用于已转存 URL 的展示加速，不能作为资料库长期存储。
  - 当前 P0 真实企业微信链路允许生产小范围联调，但 P1/P2 前应拆 staging/test 环境。
  - 会话存档不能直接回复用户“已完成”，通知后续独立走企业微信应用消息、微信客服消息或小程序订阅消息。
- 本轮未改业务代码，仅更新长期记忆文档。

### 会话存档媒体下载转存实现

- 已实现 `sdkfileid -> GetMediaData -> 媒体处理/转存 -> UserNote.media.url`：
  - `WecomArchiveClient.download_media()` 调用官方 C SDK `GetMediaData`。
  - `_FinanceSdk.get_media_data()` 按 `outindexbuf/is_finish` 循环下载分片，并用长度读取二进制数据。
  - `process_wecom_archive_messages()` 在生成 `content-to-note` 前先补齐媒体 URL。
  - 下载成功后复用现有 `MediaProcessingService` 和 `MediaStorageService`，图片会转 WebP 并存到 `/media`。
  - 成功 URL 写入 `UserNote.media.url`，并通过现有草稿构建同步进入兼容 `Card.coverUrl/Card.media.url`。
  - 下载失败不阻断文字笔记生成，会写入 `media_retry_jobs`，处理结果返回 `failedCount`。
- 后台 worker 和手动 `POST /api/wecom/archive/process` 都已传入 archive client，因此自动处理和手动处理都会尝试下载媒体。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：14 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：65 项通过。
- 生产部署：
  - 已同步后端代码到服务器并重建/重启 backend 容器。
  - 公网 `/api/wecom/archive/config-check` 确认 `sdkConfigured=true`、`workerEnabled=true`、`missing=[]`。
  - 手动 `POST /api/wecom/archive/process?limit=20` 返回 200，当前 `processedCount=0`，表示没有未处理的新归档消息。
  - 真实图片本体下载仍需用户重新发送一条新图片/微信笔记触发验证；已处理过的旧图片不会自动重跑。

### 历史会话存档媒体补下载/回填

- 已新增后台接口：
  - `POST /api/wecom/archive/media-backfill`
  - 需要 `X-Admin-Token`。
  - 参数 `limit` 控制本次最多处理多少个缺失 URL 的媒体。
- 回填规则：
  - 扫描已有 `UserNote`，只处理 `mediaId` 存在且 `url` 为空的媒体。
  - 优先复用已经成功下载过的媒体 URL。
  - 无成功记录时通过会话存档 SDK `GetMediaData` 下载，再进入现有媒体压缩/存储链路。
  - 成功后回写 `UserNote.media.url`，并同步补齐兼容 `Card.coverUrl` / `Card.media`。
  - 下载失败继续写入 `media_retry_jobs`，不影响其他历史笔记回填。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：15 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：66 项通过。
- 生产首次回填结果：
  - `checkedNoteCount=3`。
  - `downloadedCount=5`，成功回填 `note_da48e67e5e` 的 5 张图并更新兼容卡片。
  - `failedCount=2`，失败原因是超长 `sdkfileid` 原样拼进文件名导致 `[Errno 36] File name too long`。
- 已迭代修复：
  - 媒体文件名生成对超长 media ID 做截断并追加 `sha256` 短 hash。
  - 新增超长 media ID 存储测试。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：67 项通过。
- 生产二次回填结果：
  - `checkedNoteCount=2`。
  - `downloadedCount=2`、`failedCount=0`。
  - 成功回填 `note_f6cfe62264`、`note_866ce69346`，并更新对应兼容卡片。

### identity-core 第一版：认领后自动绑定归属

- 新增身份绑定模型和仓储：
  - `WecomIdentityBinding`
  - PostgreSQL 表：`wecom_identity_bindings`
  - 绑定键：`sourceType=wecom_external_user` + `externalUserId`
- 认领流程增强：
  - 用户认领导入后，保存企业微信来源身份与小程序用户的绑定。
  - `/api/imports/{id}/claim` 返回 `identityBinding`。
- 后续导入自动归属：
  - 企业微信客服 `sync_msg` 导入处理时先查绑定。
  - 企业微信会话存档 `process` 处理时先查绑定。
  - 命中绑定后，`UserNote.ownerUserId` 和兼容 `Card.ownerUserId` 直接指向该用户。
  - `ImportBatch.status=claimed`，不会再进入“新导入资料/待认领”列表。
- 当前边界：
  - 仍是 mock 登录用户 ID，不是正式微信 code/openid/unionid 绑定。
  - 未做企业微信成员和小程序用户的管理后台绑定。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "claim_import or wecom_archive_process_auto_assigns_bound_external_user"`：2 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_app.py -q -k "wecom_archive"`：16 项通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：68 项通过。
- 生产部署：
  - 已同步后端代码并重建/重启 backend。
  - `/health` 返回 ok。
  - PostgreSQL 已确认存在 `wecom_identity_bindings` 表。
  - 首次查表时 shell/SQL 引号写复杂导致 `syntax error`，已改用简单 `information_schema.tables` 查询确认。

### URL 轻收藏与深度整理升级入口

- 已按最新产品口径实现：
  - 普通文章 URL 默认生成轻收藏笔记。
  - 轻收藏标记 `visibilityConfig.contentMode=bookmark`，默认标签为“文章 / 链接 / 未整理”。
  - 企业微信明确指令 `整理链接` 仍走 `content-to-note` 深度整理，不进入轻收藏。
  - 小程序笔记编辑页在轻收藏状态下展示“整理为笔记”，用户点击后升级为深度笔记状态。
- 后端改动：
  - Skill Router 新增 `link_bookmark` 意图和 `link-bookmark` 轻收藏运行路径。
  - 企业微信客服导入和会话存档导入统一通过路由判断，避免绕过轻收藏策略。
  - `POST /api/notes/{note_id}/organize` 支持把轻收藏升级为深度笔记状态。
- 小程序改动：
  - 笔记编辑页识别轻收藏状态，并提供“整理为笔记”操作。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：70 项通过。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
- 迭代记录：
  - 初次回归时旧测试仍断言“URL 文本必须路由到 content-to-note”，已改为“普通 URL 默认 link-bookmark，明确整理指令才 content-to-note”。
- 生产部署：
  - 已同步后端代码到服务器并重建/重启 backend 容器。
  - `https://teambuy.lifelove.top/health` 返回 ok。
  - 生产 `POST /api/skills/route` 验证：
    - `我收藏一下 https://example.com/a` 返回 `intent=link_bookmark`、`skillId=link-bookmark`。
    - `整理链接` 返回 `intent=content_to_note`、`skillId=content-to-note`、`source=exact_command`。
  - 小程序端“整理为笔记”按钮需要通过微信开发者工具重新上传/预览后才能在体验版看到。

### URL 轻收藏 UI 修正：从通用笔记改为文章收藏卡

- 用户反馈：
  - 上一版轻收藏点进去仍像通用模板，不符合“轻收藏”的第一层体验。
  - 轻收藏应像微信公众号文章卡：标题、封面、来源、收藏时间、分类、标签、一句话摘要和原始链接。
- 已修正：
  - 后端 `link-bookmark` 增加 `visibilityConfig.category/sourceName/sourceLabel/openAction`。
  - 小程序“我的笔记”列表中，轻收藏显示为文章收藏卡。
  - 点击轻收藏卡片默认打开原文；公众号文章优先尝试 `wx.openOfficialAccountArticle`，普通网页按微信限制降级复制链接。
  - “整理 / 编辑”和“删除”变成卡片底部次级动作。
  - 轻收藏详情页先展示文章卡、来源、收藏时间、基础分类和标签，不再先显示通用资料模板。
  - 轻收藏详情页只暴露标题和一句话摘要基础编辑，点击“整理为笔记”后再进入深度笔记字段。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：70 项通过。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
- 迭代记录：
  - “轻收藏”不能只作为 `UserNote` 的一个状态塞进通用编辑页；它需要独立的文章收藏卡展示形态。
  - 生产验证时首次误打 `content-to-note/run` 深度整理接口，该接口不会返回轻收藏字段；已改用容器内 `run_link_bookmark()` 做无写库验证。
- 生产部署：
  - 已同步后端代码到服务器并重建/重启 backend 容器。
  - `https://teambuy.lifelove.top/health` 返回 ok。
  - 生产容器内验证 `run_link_bookmark()` 返回：
    - `intent=link_bookmark`
    - `category=文章收藏`
    - `sourceName=example.com`
    - `sourceLabel=网页链接`
    - `openAction=copy_link`
  - 小程序文章卡片 UI 需要通过微信开发者工具重新预览/上传后才能看到。

### 强标签、弱分类、专题聚合第一版

- 新增架构文档：
  - `docs/stage2-docs/11-tag-topic-search-architecture.md`
- 后端实现：
  - `UserNote.visibilityConfig` 兼容扩展 `sourceType/systemCategory/tags/userTags/tagLevels/topicIds/topics/tagStatus`。
  - `link-bookmark` 入库时生成 L1 规则标签，不调用大模型，不阻塞收藏。
  - 新增标签建议接口：`GET /api/notes/tag-suggestions`。
  - 新增专题接口：`GET/POST /api/notes/topics`、`POST/DELETE /api/notes/{note_id}/topics/{topic_id}`。
  - 笔记列表支持按 `sourceType/tag/topicId/sort` 筛选。
- 小程序实现：
  - “我的笔记”新增来源类型筛选、标签筛选、专题筛选和收藏时间/更新时间排序。
  - 轻收藏编辑页支持调整来源类型、系统弱分类、用户标签和专题。
  - 新增“专题”页面，可创建专题并按专题进入资料库。
  - “我的”页面新增专题入口。
- 验证：
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests/test_skill_router.py backend/tests/test_app.py backend/tests/test_media_processing_service.py backend/tests/test_media_storage_service.py -q`：70 项通过。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：25 个文件通过。
- 当前边界：
  - L2 轻模型标签和 L3 大模型深度标签暂未接入。
  - 专题关系第一版保存在 `UserNote.visibilityConfig.topicIds`，后续稳定后再拆 `topic_items`。
- 生产部署：
  - 已同步后端代码到服务器并重建/重启 backend 容器。
  - `https://teambuy.lifelove.top/health` 返回 ok。
  - PostgreSQL 已确认存在 `topics` 表。
  - 生产 `GET /api/notes/topics?ownerUserId=nonexistent` 返回 404 `用户不存在`，说明新接口路由与用户校验生效。

### 轻量资料库与两层工作台改造

- 产品收敛：
  - 不再把“收藏 -> 编辑 -> 整理 -> 生成”四态作为用户主 UI 卖点。
  - 用户主体验调整为两层：自动生成结果工作台 + 板块级轻编辑。
  - 高置信房源/团购直接进入工作台；中置信普通资料卡给“可能是房源 / 团购”确认；低置信普通笔记不打扰。
- 后端实现：
  - `content-to-note` 增加 `recognitionConfidence`，房源/团购高置信写入 `level=high`。
  - 房源识别增强：支持 emoji 字段标签，增加面积字段，要求价格、位置和房型/面积等组合信号。
  - 团购识别增强：要求商品、价格和配送/自提/截止/规格等组合信号。
  - 高置信房源/团购默认 `cardState=generated`，直接进入可用工作台。
  - 中置信保留 `text_note` 并写入 `typeSuggestions`。
  - 笔记搜索新增宽松模糊索引：标题、摘要、正文、结构化字段、标签、专题、来源、上传日期和数字归一化日期。
- 小程序实现：
  - `pages/note-edit` 从 4 态流程 UI 改为工作台 UI。
  - 房源/团购展示顶部工作台、房源/商品卡、媒体、功能组、轻 SCRM、基础信息、标签与专题。
  - 房源默认功能组：分享/海报、轻 CRM、留资、预约看房、私聊咨询。
  - 团购默认功能组：分享/海报、轻 CRM、留资、团购接龙。
  - 每个核心板块支持隐藏/恢复；普通笔记支持添加轻 CRM、留资表单、预约、接龙功能组。
  - `pages/notes` 保持默认按上传/导入时间倒序，并保留每个卡片的上传时间。
  - 资料库新增“未整理”轻入口，专题继续作为轻文件夹，标签仍负责多维搜索筛选。
  - 普通笔记列表展示中置信提示，例如“可能是：房源 / 团购”。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：92 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 两层工作台编辑体验细化

- 用户反馈：
  - 字段输入框和背景颜色太接近，编辑感不清晰。
  - 海报入口、客户页入口还只是预留提示。
  - 价格识别对“价格 1300 + 服务费 200 + 面积 42 平”等混合数字不够稳。
  - 户型、水电、服务费、自提方式这类字段希望更轻，不想纯手打。
  - 图片需要支持编辑和删除。
- 已调整：
  - 字段区改为浅色信息块 + 白底描边输入框，拉开层次。
  - 常见字段增加快捷项：户型、水电物业、服务费、自提/配送、库存备注等。
  - 图片区改成素材卡，显示封面/图片/视频标记，支持设为封面和从当前资料卡删除。
  - “客户页”入口新增 `pages/note-preview/index`，用于 owner 侧预览客户可见内容与动作。
  - “海报入口”新增 `pages/note-poster/index`，用于预览海报草稿和复制发群文案。
  - 价格识别优先读取带价格关键词的行，忽略服务费行，避免面积、楼栋号、服务费数字抢占价格。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 客户页动作、海报配色与地图定位完善

- 用户反馈：
  - 海报入口深蓝背景太深，文字不清楚。
  - 需要明确海报与客户页的作用边界。
  - 客户页按钮视觉和功能都需要更完整。
  - 房源需要腾讯地图定位，方便客户点击查看位置。
  - 标签和专题也应像户型快捷项一样，默认给出可点选项，减少手动输入。
- 已调整：
  - 海报页改为浅色海报卡，提供 5 个主流强调色可切换：墨绿、青绿、湖蓝、玫红、暖黄。
  - 客户页新增原生分享按钮，并实现 `onShareAppMessage` / `onShareTimeline`。
  - 客户页动作按钮改为两列动作卡，支持联系咨询、留资表单、预约看房、私聊咨询、地图定位、团购接龙等交互。
  - 房源编辑页地址字段增加“选择地图位置”，通过微信原生腾讯地图选点，保存到 `structuredData.mapLocation`。
  - 客户页有经纬度时调用 `wx.openLocation` 打开腾讯地图；无经纬度但有地址时复制地址。
  - `app.json` 增加 `scope.userLocation` 授权说明。
  - 标签区展示系统默认标签并可删除，同时给出推荐标签快捷项。
  - 专题区给出推荐专题快捷项，点击后自动创建或加入已有专题。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests`：通过。
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 字段推荐与标签展示降噪

- 用户反馈：
  - 商圈字段也需要像户型一样给默认点选。
  - 地理位置不应只藏在“选择地图位置”按钮里，有默认地址就应该直接显示。
  - `未整理`、`待跟进` 和过长标签不要在前台展示。
  - 标签和专题推荐只显示高置信、高价值项。
- 已调整：
  - 房源商圈 / 区域字段新增快捷项：万家丽、高桥北、汽车东站、袁隆平地铁口、高桥。
  - 商圈识别值会按顿号、逗号等拆分成可点快捷项。
  - 地址字段有地址时显示默认地址预览；用户选过地图点后显示真实小地图预览。
  - `未整理` 保留为资料库筛选概念，不再作为标签/专题推荐显示。
  - `待整理`、`未整理`、`待跟进`、过长标签从编辑页和资料列表前台展示中过滤。
  - 推荐标签和推荐专题只保留短、明确、重复价值高的项。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 专题移除、地图预览与分享按钮细化

- 用户反馈：
  - 点击默认专题后删不了。
  - 默认地址不应只显示文字，要有腾讯地图经纬度定位。
  - 客户页“发给微信好友”按钮背景过深。
  - 需要有可提示发朋友圈的入口。
- 已调整：
  - 编辑页已加入当前资料的专题不再因名称过长被隐藏，都会显示为可点 `×` 的胶囊，便于从当前资料移除。
  - 资料库列表页专题只做筛选，不做删除；专题筛选改为横向胶囊并提供“全部”清除筛选。
  - 列表页专题只展示短、高价值专题，避免长专题堆叠。
  - 地址字段不再显示纯地址文字预览；有经纬度时显示腾讯地图，没经纬度时显示“生成腾讯地图定位”入口。
  - 客户页“发给微信好友”按钮改为浅绿色；新增“发朋友圈”提示入口，朋友圈分享配置继续走 `onShareTimeline`。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 客户页地图经纬度与房源标记

- 用户反馈：
  - 客户页地图看不明白，不确定是否能显示经纬度。
  - 希望地图上有小房子标记。
- 已调整：
  - 客户页有经纬度时直接展示腾讯地图卡片。
  - 地图卡片顶部显示经纬度。
  - 地图 marker 增加 `🏠` label 和 `🏠 房源位置` callout。
  - 编辑页地图预览 marker 同步增加房源标记。
  - 没有经纬度时仍提示先在编辑页选择腾讯地图位置，不伪造定位。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 地图选点权限与保存体验修正

- 用户反馈：
  - 点击生成/保存经纬度时直接退回，不让选。
  - 不要求精确到门牌号，能定位到小区即可。
- 已调整：
  - `app.json` 增加 `requiredPrivateInfos: ["chooseLocation"]`，避免微信隐私接口未声明导致选点直接失败；`wx.openLocation` 不写入 `requiredPrivateInfos`。
  - 选择地图位置成功后自动保存 `structuredData.mapLocation`，不需要再手动点保存。
  - 地图选点失败时改为弹窗说明：确认位置权限，并在腾讯地图中搜索小区名称即可。
  - 保存定位时优先使用地图返回地址，无法精确门牌时允许用小区/商圈作为地址兜底。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：93 passed。
  - `find miniprogram -name '*.js' -print0 | xargs -0 -n1 node --check`：通过。
  - 小程序 JSON 解析检查：通过。

### 资料详情支持用户补传图片/视频

- 用户反馈：
  - 微信笔记导入过来的图片可以删除，但资料详情里没有新增入口。
  - 贝壳等小程序房源无法稳定拿到详情图和视频时，需要允许用户保留标题/原小程序链接，再自行补充图片、视频和字段。
- 已调整：
  - `miniprogram/pages/note-edit/` 的“图片与视频”板块新增“添加”入口。
  - 支持从相册/相机添加图片，支持从相册/相机添加视频。
  - 上传继续复用现有 `POST /api/uploads/asset` 接口，不新增后端接口。
  - 上传成功后自动写回当前资料并保存；首张图片会自动作为封面。
  - 媒体列表避免封面图重复显示，同一张图若是封面则只显示一次并标记“封面”。
  - 编辑页视频素材改为可直接播放。
  - 客户页预览新增“房源视频”展示区，用户补传的视频可以在客户页看到。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 分享图路径弱化与保存海报

- 用户反馈：
  - 当前“海报”概念不清楚，用户不明白它和客户页链接的区别。
  - 朋友圈更适合发客户页链接，海报应只是辅助图片素材。
- 已调整：
  - 资料详情顶部工作台主动作移除“朋友圈海报”按钮，只保留“分享文案 / 客户页预览 / 转发给好友”。
  - 分享图入口改为弱链接“保存分享图”。
  - `pages/note-poster/index` 标题从“海报入口”改为“分享图”。
  - 分享图页面新增“保存海报”按钮，使用 canvas 生成静态图片并保存到相册。
  - 分享图页面保留“客户页”和“复制文案”次级动作。
  - 功能组文案从“生成海报”改为“保存分享图”，避免和客户页分享混淆。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 房源轻 SCRM 增加按资料查看客户动作入口

- 用户反馈：
  - 客户页动作持久化后，发布者不应只去全局线索列表里找。
  - 房源资料详情的“轻 SCRM”板块应能直接查看这条房源的留资、预约、咨询动作。
  - 有待跟进线索时，房源卡片应像微信未读一样有红点提醒。
- 已调整：
  - 后端新增 `GET /api/notes/{note_id}/customer-actions?ownerUserId=...`，按 noteId 返回客户动作汇总、动作明细和已投影线索。
  - 房源/团购资料详情的轻 SCRM 板块显示“客户动作 / 留资 / 待跟进”数量。
  - 轻 SCRM 板块新增“查看客户动作 / 查看线索”入口，跳转到 `pages/note-actions/index`。
  - 有 `pending` 线索时，轻 SCRM 标题和入口显示红点；线索处理后红点可随状态消失。
  - 新增 `pages/note-actions/index`，按当前 noteId 展示客户动作时间线和线索列表，并可进入线索详情。
- 验证：
  - 目标后端测试 `test_import_creates_claimable_user_note_and_note_crud`：通过。
  - 新增小程序页面 JS 静态检查：通过。
  - 小程序页面 JSON 解析检查：通过。

### 客户动作生产 404 与多端按钮适配修复

- 用户反馈：
  - 手机/iPad 测试客户页提交“留下电话/微信”时报 `Not Found`。
  - 房源资料详情进入“查看客户动作 / 查看线索”也报 `Not Found`。
  - 资料详情顶部“分享文案 / 转发给好友 / 客户页预览”在手机和平板上样式变形。
  - 客户预览页右下角“好友 / 朋友圈”和提交按钮在不同设备上尺寸不稳定。
- 根因：
  - 小程序当前 `apiBaseUrl` 指向生产 `https://teambuy.lifelove.top`，但生产后端尚未部署 `customer_actions` 新接口。
  - 部分按钮依赖固定 `line-height`，在不同屏宽/设备渲染时容易挤压或显得过小。
- 已调整：
  - 已同步后端代码到生产服务器并重建 `teambuy-backend` 容器。
  - 公网验证新接口已从路由级 `{"detail":"Not Found"}` 变为业务级 `{"detail":"笔记不存在"}`，确认路由已上线。
  - 资料详情顶部动作按钮改为 flex 居中和 rpx 尺寸，窄屏降低间距与字体。
  - “保存分享图”弱入口改为稳定 rpx 胶囊样式。
  - 客户预览页浮动“好友 / 朋友圈”和留资/预约提交按钮改为 rpx + flex 布局，增加安全区底部间距。
- 验证：
  - 生产 `/health` 正常。
  - 生产 `GET /api/notes/note_not_exists/customer-actions?ownerUserId=user_test` 返回“笔记不存在”，不再是路由级 `Not Found`。
  - 生产 customer action config 和 lead-contact POST 路由同样已上线。
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：98 passed。
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 真机身份隔离、红点已读和线索拨号入口

- 用户反馈：
  - 两个不同微信真机测试看到同样资料数据，应该按 openid 隔离，非分享场景不能看其他人的笔记。
  - 房源轻 SCRM 红点点开后应取消。
  - 待联系页面和从轻 SCRM 进入的客户页面，电话旁边必须有拨号入口，同时保留编辑修改功能。
- 根因：
  - 登录页仍使用默认“本地测试用户”mock 登录；后端 mock 登录默认 `openid = openid_昵称`，两个微信默认昵称一致时会复用同一用户。
  - 红点之前绑定 pending 线索数量，点开查看不会改变 pending，所以不会消失。
- 已调整：
  - 后端新增 `POST /api/auth/wechat-login`，用小程序 `wx.login` code 通过后端换 openid 后创建/更新用户。
  - 后端新增 `WECHAT_MINIAPP_APPID`、`WECHAT_MINIAPP_SECRET`、`WECHAT_JSCODE2SESSION_URL` 配置项；Secret 只允许放后端。
  - 小程序登录页优先走微信登录；生产未配置 AppSecret 时，兜底为“本机唯一测试身份”，避免不同手机继续共用默认用户。
  - 小程序启动时清理旧的 `openid_本地测试用户` 缓存，避免旧真机预览继续串数据。
  - 轻 SCRM 红点改为本机已读模型：最新客户动作时间大于本机已读时间才显示，点击“查看客户动作 / 查看线索”后立即取消红点。
  - 待联系列表、线索详情、房源客户动作页均在手机号旁增加“拨号”入口，调用 `wx.makePhoneCall`，原有编辑/保存功能保留。
  - 已部署后端登录接口到生产；公网验证 `/api/auth/wechat-login` 已不是 404，当前因服务器未配置 AppSecret 返回明确配置提示。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：99 passed。
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 当前用户一键生成房源测试数据

- 用户反馈：
  - 需要 mock 几组假数据，否则真机无法完整测试房源资料详情、轻 SCRM、客户动作和拨号。
- 已调整：
  - 后端新增 `POST /api/notes/demo-data?ownerUserId=...`。
  - 生成 3 条当前用户自己的房源资料：
    - 测试房源 A：有留资、预约、待跟进线索，可测红点、客户动作页和预约投影。
    - 测试房源 B：有已联系线索，可测线索列表和拨号入口。
    - 测试房源 C：无客户动作，可测空状态。
  - 每次生成的数据归属当前登录用户，用于验证两个微信账号数据隔离。
  - 小程序“我的”页新增“生成测试房源数据”入口。
  - 生产后端已部署该接口，并用临时测试用户验证成功生成 3 条房源、2 条线索、3 条客户动作。
- 验证：
  - `/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests -q`：100 passed。
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 我的笔记卡片增加 SCRM 快捷入口与按钮适配

- 用户反馈：
  - “我的笔记”搜索按钮太长太黑，应改短并使用小程序主题蓝色。
  - 房源 SCRM 入口藏在资料详情下面太深，应该在房源笔记卡片上直接显示 SCRM 按钮和红点。
  - 点开 SCRM 后卡片红点应消失。
  - 资料详情顶部“分享文案 / 转发给好友 / 客户页预览”文字没有居中，浮动“存”按钮太小。
- 已调整：
  - “我的笔记”搜索按钮改为短蓝色按钮。
  - 房源/团购笔记卡片加载后会补取当前 noteId 的客户动作汇总。
  - 卡片右上角显示未读红点；底部新增 `SCRM` 胶囊入口，待跟进时显示数量。
  - 点击卡片 `SCRM` 后写入本机已读时间并跳转 `pages/note-actions/index`，红点立即消失。
  - 资料详情顶部三按钮改为专用 `hero-action-btn`，按钮内加 `text` 并用 flex 居中。
  - 浮动保存按钮从 60rpx 放大到 84rpx，文字同步放大。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 我的笔记搜索栏与客户信息入口微调

- 用户反馈：
  - 搜索输入框太短，搜索按钮太长，不应一行各占一半。
  - 卡片上的 `SCRM` 文案偏技术，应改成“客户信息”。
  - 有未读/待处理时客户信息入口颜色稍红；点开处理/查看后恢复当前蓝色。
- 已调整：
  - 搜索区改为 `输入框 + 92rpx 搜索按钮`，输入框占主要空间。
  - 房源/团购卡片入口文案改为“客户信息”，待跟进时显示数量。
  - 未读态客户信息入口使用淡红底和红字，已读态恢复蓝色。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 资料详情图片删除与设封面持久化修复

- 用户反馈：
  - 上传两张图片后删除一张，刷新/返回后又恢复成两张。
  - 图片无法稳定设置为封面。
- 根因：
  - 删除和设封面只更新了本地 `form` 展示状态，没有立即保存到后端。
  - 素材数量按 `coverUrl + media.length` 计算，会把同一张封面重复计数。
- 已调整：
  - 删除图片/视频后立即保存当前资料。
  - 设置封面后立即保存当前资料。
  - 保存失败时重新加载服务端资料，避免前端停留在错误状态。
  - 素材数量改为按实际展示的 `mediaItems.length` 计算，避免封面重复计数。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 封面角标视觉区分

- 用户反馈：
  - 设置成封面后，“封面”字样应更明显，不要继续用白字深色底，否则和普通图片不容易区分。
- 已调整：
  - 封面角标单独使用淡红底和红字。
  - 封面角标字号略放大，普通“图片/视频”角标保持原样。
- 验证：
  - 小程序 JS 静态检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 房产场景 5 项体验补强

- 用户确认：
  - 标题保持原样，不做自动拆字段提示。
  - 重点继续放在房源客户动作持久化和房源工作台体验。
- 已调整：
  - 我的笔记房源卡片增加房源状态 chip：推广中 / 已租 / 暂停推广。
  - 卡片“客户信息”文案更直观：有待跟进显示“待跟进 N”，有线索显示“客户 N”。
  - 房源资料详情顶部增加“复制客户话术”，保留“保存分享图”为弱入口。
  - 房源资料详情增加“房源状态”快捷切换；状态会立即保存。
  - 客户页预览识别已租 / 暂停推广后，关闭电话咨询、留资、预约、私聊、接龙等新增转化动作，只保留原房源 / 地图等信息入口。
  - 图片与视频素材支持上移 / 下移排序，并立即保存排序结果。
  - 房源客户动作页改成分层展示：新线索/待跟进、预约看房、已联系/已归档、全部客户动作。
  - 客户动作页、全局线索页、线索详情页拨号成功后，提示是否标记已联系；确认后写入跟进记录并刷新列表。
- 验证：
  - `find miniprogram -name '*.js' -not -path '*/miniprogram_npm/*' -print0 | xargs -0 -n 1 node --check`：通过。
  - `python3 -m json.tool` 检查相关小程序页面 JSON：通过。
  - `git diff --check`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `/tmp/teambuy-pytest-venv312/bin/python -m pytest backend/tests -q`：100 passed。
  - 直接运行项目根目录 `.venv/bin/python -m pytest` 会因该虚拟环境 Python 版本较低触发 `dataclass(slots=True)` 报错，本轮已改用 Python 3.12 测试环境完成回归。

### 2026-06-19：生产微信登录与 chatrecord 商品解析修复

- 生产处理：
  - 服务器 `backend/.env` 已补 `WECHAT_MINIAPP_APPID` / `WECHAT_MINIAPP_SECRET`，后端已重建并重启。
  - 真机微信登录已能通过 `/api/auth/wechat-login` 换取真实 openid；当前生产用户为 `user_25ec00a0f0`。
  - 企业微信外部联系人绑定已从旧本地测试用户 `user_08e8927ed8` 迁到真实用户 `user_25ec00a0f0`。
  - 2026-06-19 当天误归属的 4 条企业微信导入已迁移到真实用户。
- 解析器处理：
  - 新增 `archive_message_parsers.py`，把企业微信归档消息解析拆成注册式 parser。
  - 新增 `ChatRecordArchiveParser`，支持解析 `chatrecord.item[]` 中的 `ChatRecordText`，过滤 `[图片]` / `[视频]` 占位。
  - 对商品/团购聊天记录写入 `parserHints=["groupbuy_product"]`，后续由 `content-to-note` 生成商品卡。
  - 商品团购识别支持无价格但有商品、活动、规格/数量等信号的聊天记录；可提取 `白凤乌鸡蛋`、`4斤，约40多个`。
  - 生产已原地修复两条旧 `chatrecord` 笔记：标题为“白凤乌鸡蛋”，类型为 `groupbuy_product / 团购`。
- 小程序体验：
  - 商品工作台重排为“商品信息 / 图片与视频 / 规格与价格 / 自提配送 / 团购接龙”。
  - 客户页商品卡先展示规格与价格；开启团购接龙后才显示提交入口。
  - 图片缩略图保持普通图片原样 `aspectFill`，封面角标只改红色文字，不再使用额外背景。
- 验证：
  - 生产 `/health` 正常。
  - 生产 `GET /api/notes?ownerUserId=user_25ec00a0f0&sort=collected` 已返回“白凤乌鸡蛋 / groupbuy_product / 团购”。
  - 本地后端全量测试：103 passed。
  - 小程序相关 JS 语法检查通过。
  - `git diff --check` 通过。

### 2026-06-19：商品下单意向出口补齐

- 用户确认：
  - 商品/团购客户预览页不管是否开启接龙，都必须默认有 SKU 点选和下单按钮。
  - 客户提交后，客户自己和团长都必须有明确出口查看下单情况。
- 已调整：
  - 后端新增 `order-intent` 客户动作，用于未开启接龙时的商品下单意向。
  - 开启接龙时继续使用 `relay-intent`；关闭接龙时使用 `order-intent`。
  - 两种动作都写入 `customer_actions`，都不投影到 `lead_reminders`，不进入 SCRM。
  - 同一客户同一商品只允许提交一条商品下单/接龙意向，防止重复刷名单。
  - 客户预览页默认展示 SKU 点选、数量和“下单 / 下单并接龙”按钮；提交后显示已下单的 SKU 和数量状态。
  - 团长在资料详情页可通过“查看下单 / 接龙名单”进入明细。
  - 团长在“我的笔记”商品卡可看到“下单 N”入口。
  - 客户动作页对商品资料展示“商品下单名单 / 商品接龙名单”，支持复制汇总、复制单条、复制电话/微信和拨号。
- 2026-06-19 追加：
  - 生产后端已同步 `order-intent` 相关代码并重建重启。
  - 生产商品笔记已确认返回 `order-intent / 下单` 或 `relay-intent / 下单并接龙`。
  - 客户预览页下单区域已下移到页面底部动作区后方，即“电话咨询 / 留下电话微信”下面。
- 验证：
  - 后端全量测试：66 passed。
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
  - 生产 `/health` 正常。

### 2026-06-19：商品轻订单中心 + 站内消息 + 我的页重构

- 用户确认：
  - 第一版只做轻订单，不做支付、库存扣减、物流、退款、核销。
  - 商品下单必须补齐地址、电话、数量、SKU；微信号和备注可选。
  - 买家和商家都需要订单中心；双方都需要小程序内异步留言入口。
- 已调整：
  - 后端新增轻订单查询接口：买家看自己的下单，商家看自己资料收到的下单，商家可更新状态。
  - 轻订单继续复用 `customer_actions.order-intent / relay-intent`，不新增正式订单表。
  - 下单 payload 扩展 `receiverName / phone / address / wechat / remark`，其中电话和地址为必填。
  - 后端新增 `message_threads` / `message_records`，支持 note 级、订单级站内文本留言、未读数和已读。
  - 小程序新增“我的订单 / 商家订单中心 / 订单详情 / 消息专区 / 站内消息”页面。
  - 客户预览页商品下单区固定在底部动作区后，展示数量、电话、地址、微信和备注。
  - 商品/房源客户页增加“发消息”；商品名单页每条下单增加“发消息”。
  - 资料详情商品区/房源区增加“消息中心”；我的笔记房源/商品卡增加“消息”入口。
  - 我的页按“会员服务 / 笔记区域 / 线索订单 / 消息专区 / 开发测试”重构。
- 验证：
  - 后端全量测试：66 passed。
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。

### 2026-06-19：站内消息前端插件化

- 用户确认：
  - 趁当前代码还不复杂，先把消息入口插件化，避免后续新场景重复改页面。
- 已调整：
  - 新增 `miniprogram/plugins/message-plugin/index.js`，统一封装打开会话、打开消息中心、读取未读数。
  - 新增 `miniprogram/components/message-entry`，统一渲染“发消息 / 消息中心 / 未读数”入口。
  - 订单详情、商品下单/接龙名单、资料详情、我的笔记卡片、我的页消息专区改用统一组件。
  - 客户预览页动态动作继续调用同一个 `messagePlugin.openMessageThread`，不再手写创建会话和跳转。
- 验证：
  - 小程序消息插件、消息入口组件和相关页面 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端全量测试：66 passed。
  - `git diff --check` 通过。

### 2026-06-20：客户预览下单弹层与我的页宫格优化

- 用户反馈：
  - 商品客户预览页地址、电话、备注都铺在同一页，页面太长。
  - 我的页会员服务、笔记区域、线索/订单用单行列表展示，页面太长也不好看。
  - 我的订单 / 商家订单中心在未部署接口时显示英文 not found，不够清楚。
- 已调整：
  - 商品客户预览页正文只保留 SKU 和下单入口；点击下单后弹出底部表单填写数量、电话、地址、微信、备注。
  - 我的页会员服务、笔记区域、线索/订单、测试入口改成 4 列图标宫格，超过 4 个自动换行。
  - 订单中心增加中文空态和错误态；后端订单接口未部署时提示“订单接口还没有更新到当前后端”。
- 验证：
  - 小程序相关 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端全量测试：66 passed。
  - `git diff --check` 通过。

### 2026-06-20：订单与消息后端生产部署

- 已部署：
  - 已用 rsync 同步 `backend/` 到生产服务器 `/home/ubuntu/teamBuy/backend/`，排除生产 `.env`、`secrets/` 和媒体目录。
  - 同步前已在生产服务器备份 `backend/app`、`backend/tests`、`backend/mock`、`docker-compose.yml` 到 `/home/ubuntu/teamBuy-deploy-backups/`。
  - 已重建并重启生产 `teambuy-backend` 容器。
- 公网验证：
  - `GET /health`：200，Postgres configured。
  - `GET /api/orders?userId=user_test&role=buyer`：200，返回空订单列表，不再是路由级 Not Found。
  - `GET /api/messages/threads?userId=user_test`：200，返回空会话列表。
  - `GET /api/notes/note_not_exists/customer-actions?ownerUserId=user_test`：返回业务级“笔记不存在”，客户动作路由正常。
  - 真实生产用户 `user_25ec00a0f0` 可返回商品笔记、买家订单、商家订单和订单详情。
- 注意：
  - 生产中少量旧测试订单在电话/地址必填上线前创建，可能显示空电话或空地址；新提交会被后端强校验。
  - 小程序上传未完成：本机微信开发者工具 CLI 被“服务端口关闭”安全设置拦截，需要在开发者工具 GUI 里打开“设置 -> 安全设置 -> 服务端口”后再上传/预览。

### 2026-06-20：企业微信纯图片导入接入两段式 OCR

- 已调整：
  - 后端统一导入层新增纯图片分流：企业微信客服同步、会话归档处理遇到“无正文、无链接、仅图片且图片已转存”的内容时，先保存为图片资料，不自动 OCR。
  - 保存后的资料使用 `cardType=image_ocr`、`sourceType=ocr`、`structuredData.ocr.status=pending`，小程序编辑页继续由用户点击“识别图片文字”触发 OCR。
  - 图文混合导入保持原有 `content-to-note` 整理逻辑；图片下载失败时仍保留原导入和媒体重试行为，不伪装成可识别图片资料。
- 验证：
  - 新增客服同步纯图片、会话归档纯图片测试。
  - 后端全量测试：108 passed。
  - `compileall backend/app backend/tests` 通过。
  - `git diff --check` 通过。

### 2026-06-20：identity-core P0 收窄为 openid 唯一身份锚点

- 用户确认：
  - P0 不做企业微信来源绑定管理、解绑或改绑页面。
  - 小程序微信 `openid` 是多途径来源进入系统后的唯一身份信息。
  - 企业微信 `external_userid` 只做系统内部来源映射。
- 已调整：
  - `WecomIdentityBinding` 增加 `ownerOpenid`。
  - 新认领导入写入 `external_userid -> ownerOpenid/ownerUserId`。
  - 后续企业微信导入解析归属时优先按 `ownerOpenid` 查找用户，旧数据仍按 `ownerUserId` 兜底。
  - `AGENTS.md` 写入 openid 身份总规则。
- 验证：
  - 新增 openid 优先归属测试。
  - 身份相关回归：3 passed。
  - 后端全量测试：109 passed。

### 2026-06-20：生产部署 identity + OCR 纯图片导入

- 已部署：
  - 生产同步前备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260620-072737`。
  - 已同步 `backend/app/`、`backend/tests/`、`backend/requirements.txt`、`backend/Dockerfile`、`backend/.env.example` 到生产。
  - 已重建并重启 `teambuy-backend` 容器。
- 公网/生产验证：
  - `GET /health`：200，Postgres configured。
  - `GET /api/ocr/images`：405，说明 OCR 保存图片路由已上线，不是 404。
  - `POST /api/ocr/notes/not_exists/recognize`：业务级“笔记不存在”，说明 OCR 识别路由进入业务层。
  - Postgres `wecom_identity_bindings.owner_openid` 列已存在。
  - 生产镜像内确认 `WecomIdentityBinding.ownerOpenid`、纯图片导入分流和 PaddleOCR worker 可用。
  - 生产容器内 PaddleOCR 识别测试图返回 `HELLO 123`，`configured=True`。
  - 生产容器重启次数为 0。
- 企业微信真实拉取：
  - 手动触发 `/api/wecom/archive/pull?limit=20` 成功，当前 `rawCount=0`，没有新真实归档消息。
  - 手动触发 `/api/wecom/archive/process?limit=20` 成功，`processedCount=0`。
- 待人工配合：
  - 需要用户从企业微信真实发送一张纯图片，再触发 `pull -> process` 验证“企业微信纯图片 -> 图片资料 pending OCR -> 小程序点识别”闭环。

### 2026-06-20：企业微信真实图片 OCR 闭环验证

- 用户在 2026-06-20 07:36 左右通过企业微信发送一张图片。
- 生产会话存档已保存并处理：
  - 归档消息：`seq=28`，`msgType=image`。
  - 生成资料：`note_f01130a526`。
  - 图片已转存到 `/media/...webp`。
- 小程序端已触发 OCR：
  - `POST /api/ocr/notes/note_f01130a526/recognize` 返回 200。
  - OCR 状态：`done`。
  - Provider：`paddle`。
  - Confidence：约 `0.948`。
  - 识别内容为聊天截图里的时间、群名、联系人和聊天文字。
- 结论：
  - “企业微信图片 -> 归档拉取/处理 -> 图片资料 -> 用户点击 OCR -> PaddleOCR 回写同一条资料”闭环已跑通。
  - 普通照片如果没有可见文字，OCR 可能返回空或低价值文本；当前 OCR 不是图片内容理解/看图识物。

### 2026-06-20：开发期 Docker 挂载模式与构建缓存清理约定

- 用户确认：
  - 当前 Docker 方案主要服务开发联调期，真正生产上线前可以另写干净的生产 Dockerfile/镜像发布流程。
  - 服务器每天清理 Docker build cache 可以接受，以降低磁盘压力。
- 已调整：
  - 新增 `backend/Dockerfile.dev`：只安装系统库和 Python 依赖，不 `COPY` 源码。
  - 新增 `docker-compose.dev.yml`：挂载 `backend/app`、`backend/tests`、`backend/mock` 和只读 `backend/secrets`，并使用 `uvicorn --reload`。
  - `backend/README.md` 增加开发期挂载启动方式和安全清理命令。
- 建议清理命令：
  - `docker builder prune -af --filter "until=24h"`
  - `docker image prune -f`
  - 不建议日常使用 `docker system prune -af --volumes`，避免误伤数据卷。
- 验证：
  - `docker-compose.dev.yml` YAML 解析通过。
  - `git diff --check` 通过。

### 2026-06-20：展示页四套标准模板参考稿与笔记展示复用

- 已补四套展示页标准模板视觉参考稿，保存到 `docs/png/`：
  - `showcase-template-01-featured-window.png`：精选橱窗，适合少量主推房源/商品快速发客户。
  - `showcase-template-02-moments-story.png`：朋友圈长页，适合讲推荐逻辑和客户群转发。
  - `showcase-template-03-catalog-list.png`：清单目录，适合资料多时筛选、对比和快速浏览。
  - `showcase-template-04-brand-card.png`：品牌名片，适合突出顾问/团长本人和信任背书。
  - `showcase-template-00-all.png` 为四套总览图，`showcase-template-mockups.html` 为参考稿源文件。
- 已新增 `miniprogram/utils/note-display.js`，把“我的笔记”列表里的资料类型、标签、摘要、徽标、上传时间、房源/商品主副信息等展示计算抽成共用工具。
- `pages/notes/index.js` 改为使用 `decorateNoteForList`，页面结构和交互保持不变。
- `pages/showcase-edit/index.js` 改为使用 `decorateNoteForShowcasePicker` 和 `decorateSelectedShowcaseItem`，展示页选资料时能复用笔记页同一套类型识别和字段展示逻辑。
- 后端和开发文档里的展示页默认模板已从旧 `classic_grid` 调整为四套标准模板首项 `featured_window`。
- 展示页联系方式默认值继续优先取登录用户；若用户头像/昵称缺失，会从已选笔记结构字段 `contactName/ownerName/agentName/contactPerson` 和 `contactAvatarUrl/ownerAvatarUrl/avatarUrl` 兜底。
- 验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `compileall backend/app backend/tests` 通过。
  - `git diff --check` 通过。
  - `pytest backend/tests/test_app.py -q -k showcase` 未在当前环境跑通：Codex runtime Python 缺少 pytest；项目 `.venv` 是 Python 3.9.6，导入时因 `dataclass(slots=True)` 失败。

### 2026-06-20：展示页模板视觉重排与双列卡片布局

- 按用户反馈补齐“列表 / 双列卡片”布局切换：
  - `pages/notes/index` 增加 `viewMode`，我的笔记可在列表和双列卡片之间切换。
  - `pages/showcase-edit/index` 增加 `noteViewMode`，新建展示页选择资料时也可在列表和双列卡片之间切换。
  - `components/note-select-card` 新增 `mode=list/grid`，同一个选择组件可服务后续更多资料选择场景。
- 客户展示页不再只是四个模板共用一套列表结构换色，已按四套标准稿分别重排：
  - `featured_window`：大图 hero、顾问/店铺卡、三项数据、联系按钮、双列主推卡片。
  - `moments_story`：生活长页 hero、服务导航、本周故事、分组故事流。
  - `catalog_list`：搜索栏、分类 tabs、筛选行、紧凑清单行、底部联系条。
  - `brand_card`：深色品牌头图、头像和背书数据、联系卡、横向案例、评价和信任条。
- 后端公开展示项增加 `badge/primaryText/secondaryText/priceText`，客户页模板可直接展示价格、主信息和标签，不再只能展示标题和摘要。
- 验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `compileall backend/app backend/tests` 通过。
  - `git diff --check` 通过。

### 2026-06-20：展示页分类文案、折叠编辑和删除入口修正

- 修正四套客户展示模板里的硬编码房源文案：
  - 展示页保存时把当前分类写入 `displayConfig.activeCategory`。
  - 客户展示页优先按 `activeCategory`，再按资料 `cardType` 推断展示上下文。
  - 当分类是商品/团购时，模板文案切换为“精选好物 / 成交订单 / 好物推荐 / 搜索好物”等，不再显示“精选房源 / 好房推荐 / 找到理想的家”。
- 编辑展示页的资料选择区：
  - 标题从“某分类资料”改为“笔记资料”。
  - 增加“隐藏 / 展示”按钮，隐藏后保留已选数量摘要，避免笔记过多时必须长滚动才能看到后续设置。
- 展示页删除：
  - 后端新增 `DELETE /api/showcases/{showcase_id}?ownerUserId=...`，仅 owner 可删除。
  - 小程序展示页列表每条都显性显示“编辑 / 预览 / 删除”，已发布页额外显示“发给客户”。
  - 编辑页底部对已有展示页显示“删除”。
- 用户反馈“有的只有预览功能”的原因：
  - 旧列表页草稿/下架只显示“预览”按钮，编辑入口隐藏在整行点击里，发给客户只在已发布状态展示。
  - 已改为显性按钮，草稿也能直接点“编辑”和“删除”。
- 验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `compileall backend/app backend/tests` 通过。
  - `git diff --check` 通过。

### 2026-06-21：经营看板与展示页数据闭环收口

- 已按用户要求把本轮 1-7 项统一收口：
  - 经营看板改为独立页面入口，不再占用“我的”页大区域。
  - 经营看板四个页签按参考图补齐：展示页效果、访客详情、笔记数据、客户资料。
  - 访客详情和客户资料中展示真实手机号/微信，不做脱敏；所有可联系位置补“外呼 / 复制微信”操作。
  - 访客详情底部“添加跟进 / 备注”按钮修正为上下居中，并接入跟进记录更新。
  - 展示页列表新增单个展示页“效果”入口，可查看该展示页打开、访客、看资料、咨询、最近访客和资料点击排行。
  - 行为数据只在内部按强度排序，不把“行为强度分层”概念展示给用户。
  - 增加生产测试数据清理能力：后端提供清理接口，小程序“我的 -> 开发/测试”提供“清理测试”按钮。
- 生产环境调整：
  - 生产后端已部署本轮改动，部署前备份为 `/home/ubuntu/teamBuy-deploy-backups/20260621-094814-dashboard-scrm-closeout`。
  - 生产 `.env` 已设置 `ALLOW_MOCK_LOGIN=false`，公网 mock 登录返回 403，避免真实上线后继续使用测试登录。
  - 用户真实账号 `openid=oPSh564GCACiIkZxFPV5VWVgdbds` 下保留演示数据，方便真机继续测试；上线前可一键清理。
- 统一验证：
  - 后端核心测试：76 passed。
  - 后端全量测试：113 passed。
  - `compileall backend/app backend/tests` 通过。
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
  - 公网 `/health` 正常，数据库连接正常，`teambuy-backend-1` 容器运行正常。

### 2026-06-21：上线闭环与真实分享追踪 V1 启动并完成 P0 第一刀

- 已新增开发文档和测试清单：
  - `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
  - `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`
- 已实现：
  - 展示页事件扩展 `shareId/shareFromUserId/scene/referrer`。
  - 展示页列表分享会生成 `shareId`，分享路径携带 `sid/from/scene`，并记录 `share` 事件。
  - 展示页公开页读取 `sid/from/scene/ref`，客户打开、点击资料、电话咨询、复制微信都会携带同一分享来源。
  - 展示页 analytics 增加 `shareSourceCount/topShares`。
  - 单展示页效果页增加“分享批次”，展示每次分享带来的打开、看资料和咨询。
- 已验证：
  - 后端核心测试：76 passed。
  - 后端全量测试：113 passed。
  - Postgres 仓储字段/index 测试：3 passed。
  - `compileall backend/app backend/tests` 通过。
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。
- 待人工确认：
  - 需要上传/预览新版小程序后，用真机走“发给客户 -> 客户打开 -> 点击资料 -> 电话/复制微信 -> 看效果页分享批次”。
- 生产部署：
  - 生产后端已部署，备份目录：`/home/ubuntu/teamBuy-deploy-backups/20260621-104718-launch-share-tracking-v1`。
  - 公网 `/health` 正常，生产 mock 登录仍返回 403。
  - 已用真实测试账号 `user_25ec00a0f0` 的已发布展示页写入一条冒烟事件 `share_prod_smoke_20260621`，analytics 已返回 `shareSourceCount=1` 和对应 `topShares`。

### 2026-06-21：修正预览态展示页误分享导致客户页面不存在

- 用户反馈：
  - 自己点击展示页没问题，转发给微信好友后，对方点击显示页面不存在。
- 排查结论：
  - 生产已发布展示页公开接口可正常访问，后端公开展示页不是整体故障。
  - 高概率原因是预览态/草稿态页面被分享给客户：发布者自己走 owner 预览接口能看，客户走公开接口只能打开已发布页。
  - 另一个需要人工确认的因素：如果当前小程序仍是体验版，未加入体验成员的微信好友也可能无法打开。
- 已修复：
  - 未发布预览页隐藏“发给客户”按钮。
  - 未发布预览页隐藏右上角分享菜单。
  - 编辑页发布态分享统一生成 `shareId`，分享路径携带 `sid/from/scene`。
- 已验证：
  - 相关小程序 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端展示页测试：1 passed。
  - `git diff --check` 通过。

### 2026-06-21：补充 UI 居中硬规则和展示页分享兜底

- 用户反馈：
  - 按钮和标签文字上下/左右不居中问题反复出现，希望写入文档硬规则。
  - 管理员账号接收分享仍然打不开。
- 已调整：
  - `AGENTS.md` 新增 UI 文本居中与按钮排版硬规则。
  - `miniprogram/app.wxss` 新增全局交互控件基线，统一处理常用按钮、标签、胶囊、状态标签的上下左右居中。
  - 展示页列表按钮改为 flex 居中，重置原生 button 默认内边距/line-height。
  - 展示页状态标签加 `inline-flex`、`white-space: nowrap` 和最小宽度，避免“已发布”拆行。
  - 展示页列表分享按钮增加 `prepareShare`，分享前先锁定当前展示页 id，避免真机上 `open-type=share` dataset 丢失导致分享路径 id 为空。

### 2026-06-21：排查演示展示页空白并修复分享路径和列表按钮布局

- 用户指定问题展示页：
  - 标题：`演示展示页：房源和好物精选`
  - 线上 ID：`showcase_627fc56634`
- 后台排查：
  - 该展示页状态为 `published`。
  - 公开接口 `/api/showcases/public/showcase_627fc56634` 正常返回。
  - 返回 4 条资料：3 条测试房源 + 1 条测试商品。
  - 事件接口可写入，说明后端公开页和统计接口不是故障源。
- 已修复：
  - 分享路径同时携带 `id` 和 `showcaseId`，避免真机分享路径丢 id 后空白。
  - 展示页公开页无 id 或接口失败时显示明确错误，不再空白页。
  - 分享来源参数由 `scene` 改为 `src`，减少和微信小程序系统 scene 语义混淆。
  - 展示页列表右侧操作区改为紧凑横排：主按钮小宽度，更多按钮轻量宽度，不再两个按钮占半张卡。
- 已验证：
  - 相关小程序 JS 语法检查通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。

### 2026-06-21：展示页分享改为首页中转，绕开深层页打开异常

- 用户继续反馈：
  - 12:00 左右继续测试 `演示展示页：房源和好物精选`，好友打开仍显示页面不存在。
- 再次排查：
  - 该展示页 ID `showcase_627fc56634` 后台状态为 `published`。
  - 公网公开接口返回 200，包含 4 条资料。
  - analytics 已有 `pv=5`、`shareCount=3`，事件接口能写入。
  - 判断故障不在展示页数据或后端公开接口，而在微信分享卡片打开深层页面这一层。
- 已修复：
  - 展示页列表、编辑页、公开展示页的分享路径统一改为 `pages/home/index?shareTarget=showcase&showcaseId=...`。
  - 首页 `pages/home/index` 新增分享落地处理：识别展示页分享参数后，在登录拦截前跳转公开展示页。
  - 公开展示页继续兼容直接 `id/showcaseId` 打开。
- 已验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - `git diff --check` 通过。

### 2026-06-21：展示页分享改为专用落地页，避免首页数据加载失败

- 用户反馈：
  - 12:40 测试后，另一台手机打开分享显示“首页数据加载失败”，没有进入展示页。
- 结论：
  - 首页作为 tab 页中转不可靠，分享参数和页面生命周期可能没有按预期进入中转逻辑，导致执行了首页自己的数据加载。
- 已修复：
  - 新增 `pages/showcase-share/index`，作为专用展示页分享落地页。
  - 所有展示页分享路径统一改为 `pages/showcase-share/index?showcaseId=...`。
  - 落地页不加载首页数据、不要求登录，只负责跳转公开展示页。
  - 移除首页中的展示页分享中转逻辑，避免再次触发“首页数据加载失败”。
- 已验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - 分享路径检查确认只走 `pages/showcase-share/index`。
  - `git diff --check` 通过。

### 2026-06-21：展示页分享落地改用已有 showcases 页面

- 继续收口：
  - 为避免新增 `showcase-share` 页面未进入体验版导致“页面不存在”，分享落地不再使用新增页面。
  - 展示页分享路径改为已有页面 `pages/showcases/index?shareTarget=showcase&showcaseId=...`。
  - `pages/showcases/index` 在 `onLoad` 中识别分享参数后，先跳公开展示页，不走登录检查和列表加载。
  - `app.json` 移除 `pages/showcase-share/index` 注册。
- 已验证：
  - 小程序全量 JS `node --check` 通过。
  - 小程序 JSON 解析检查通过。
  - 分享路径检查确认不再走首页和深层展示页直达。
  - `git diff --check` 通过。
### 2026-06-21：展示页公开访问改为发布快照缓存

- 用户反馈：
  - 展示页“发给客户”后公开页不应该每次都重新拉服务器资料并动态拼页面，客户打开量增加会造成服务器压力。
- 已修复：
  - `ShowcasePage` 增加 `publicSnapshot/snapshotVersion/snapshotCreatedAt`。
  - 发布展示页时生成公开快照，客户公开接口优先返回快照。
  - 老的已发布展示页没有快照时，第一次公开访问自动补一份快照并保存。
  - 重新发布展示页会刷新快照版本。
  - 删除资料时同步修剪相关展示页快照，避免已删除资料继续出现在客户页。
- 已验证：
  - 展示页后端测试：3 passed。
  - 后端全量测试：113 passed。
  - 后端代码编译检查通过。
  - 小程序 JS 全量语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 已部署到 `https://teambuy.lifelove.top` 后端。
  - 线上 `/health` 正常。
  - 线上展示页 `showcase_627fc56634` 连续两次公开访问均返回 `snapshotVersion=1`、同一个 `snapshotCreatedAt`，确认第二次读的是发布快照。

### 2026-06-21：上线闭环 1-4 经营看板分享来源收口

- 范围核准：
  - 对照 `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`，本次“1-4”对应：扩展事件字段、分享路径携带 `shareId`、公开页记录来源事件、analytics 和经营看板聚合分享来源。
- 已补齐：
  - 经营看板后端增加 `summary.shareSourceCount` 和 `topShares` 聚合。
  - 经营看板详情页增加“分享来源”模块。
  - 经营看板复用组件增加“分享来源”模块。
  - 后端测试补充经营看板 `shareId` 聚合断言。
  - 开发文档和测试清单同步当前真机稳定分享路径：`pages/showcases/index?shareTarget=showcase&showcaseId=...&sid=...&from=...&src=...`。
- 已验证：
  - 后端全量测试：113 passed。
  - 小程序 JS 全量语法检查通过。
  - 小程序 JSON 解析检查通过。
  - 后端代码编译检查通过。
  - `git diff --check` 通过。
  - 已部署线上后端。
  - 线上 `/health` 正常。
  - 线上经营看板 `user_25ec00a0f0` 返回 `shareSourceCount=11`、`topSharesLength=6`。

### 2026-06-21：小程序“添加资料”手动新建快速向导 V1

- 背景：
  - 用户确认继续向下推进新功能：房源/商品团购除了企业微信、微信笔记、图片 OCR 迁移，也需要小程序内手动新建入口。
  - 首版不做复杂多页表单，不新增房源表/商品表，统一创建 `UserNote` 后进入现有 `note-edit` 工作台精修。
- 已完成：
  - 后端新增 `POST /api/notes/manual-draft`。
  - 支持 `cardType=property_listing/groupbuy_product/text_note`。
  - 支持 `inputMode=paste_text/blank`。
  - 粘贴文案构造成 `ContentObject(sourceType=manual_text)`，复用 `content-to-note` 规则提取字段，再按用户选择类型做人工确认。
  - 空白房源/商品默认创建结构化资料卡，并写入对应默认转化配置；普通笔记不启用转化能力。
  - 小程序底部 Tab 的 `pages/resource-create/index` 改为“添加资料”轻向导：选类型、选输入、创建草稿。
  - 图片资料入口保留为“保存图片资料”，继续复用现有 OCR 图片保存接口，成功后进入 `note-edit`。
  - 前端新增 `api.createManualNoteDraft`。
  - 后端测试补齐粘贴房源、粘贴团购、空白房源/商品、非法类型/方式和不存在用户。
- 已验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q`：118 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `python3 -m compileall backend/app backend/tests -q`：通过。
  - `git diff --check`：通过。

### 2026-06-21：手动草稿接口部署到生产

- 用户反馈：
  - 小程序新建资料时报 `Method Not Allowed`。
- 线上确认：
  - `POST https://teambuy.lifelove.top/api/notes/manual-draft` 返回 `405 Allow: GET`，说明生产后端还没有新接口。
- 已处理：
  - 备份生产服务器 `/home/ubuntu/teamBuy` 中的 `routes_notes.py`、`notes.py`、`app_service.py`。
  - 同步本地已通过测试的后端接口文件到生产服务器。
  - 重新构建并启动 `teambuy-backend-1`。
- 已验证：
  - 线上 `/health` 返回 200。
  - `POST /api/notes/manual-draft` 已不再返回 405；使用不存在用户验证时返回业务层 `404 用户不存在`。

### 2026-06-21：添加页改为方案 A 极简随手记入口

- 背景：
  - 用户确认原“添加资料”三步选择页不再作为主形态，底部中间“添加”应像 flomo 一样成为极简随手记入口。
  - 房源/团购不再要求用户先选类型；高置信内容由系统自动整理成对应资料草稿。
- 已完成：
  - 新增后端 `POST /api/notes/quick-capture`。
  - 快速记录构造 `ContentObject(sourceType=manual_text, entryMode=quick_note)`，复用 `content-to-note` 规则识别。
  - 高置信房源/商品自动保存为 `property_listing/groupbuy_product`；普通内容保存为 `text_note`。
  - 团购高置信草稿补齐 `skuConfig` 兼容结构。
  - 小程序 `pages/resource-create/index` 改为方案 A：标题“放进笔记库”、大输入框、轻工具栏、绿色发送按钮。
  - 普通笔记保存后留在当前页，显示“已保存 / 查看详情”小条。
  - 高置信房源/商品保存后弹业务化提示，引导“完善房源/完善商品”；取消时仍保留业务草稿在笔记库。
  - `...` 更多里保留空白房源、空白商品、图片资料；图片按钮继续复用 OCR 图片资料入口。
- 已验证：
  - 后端全量测试：122 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端编译检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，线上 `/health` 返回 200。
  - 线上 `POST /api/notes/quick-capture` 已进入业务层；使用不存在用户验证时返回 `404 用户不存在`。

### 2026-06-21：添加页高置信分流提示改为方案 B

- 用户反馈：
  - 方案 A 太像普通笔记，高置信识别后如果提示不明显，会弱化本产品和普通笔记工具的差异。
- 已调整：
  - 保留“放进笔记库”极简输入器作为主入口。
  - 高置信房源/商品不再用原生系统弹窗，改为页面内业务提示层。
  - 房源提示文案：`已帮你整理成房源草稿`，引导补图片、电话和展示按钮。
  - 商品提示文案：`已帮你整理成商品草稿`，引导补规格、取货方式和接龙按钮。
  - 操作按钮为“完善房源/完善商品”和“先放笔记库”。
- 已验证：
  - 小程序全量 JS 语法检查：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-21：笔记器图片按钮改为保存图片资料，不走 OCR 命名

- 用户反馈：
  - 笔记器上传图片显示“图片保存返回解析失败”。
  - 产品心智上这里不应该叫 OCR，图片按钮只是保存图片资料，文字识别应在详情页主动触发。
- 根因确认：
  - 线上 `teambuy.lifelove.top` Nginx 未设置 `client_max_body_size`，2MB 图片会被 Nginx 返回 HTML `413 Request Entity Too Large`，小程序 JSON 解析失败。
- 已修复：
  - 生产 Nginx `teambuy.conf` 增加 `client_max_body_size 50M` 并 reload。
  - 新增 `POST /api/notes/image-capture`，调用现有保存图片资料逻辑，只保存图片并标记等待主动识别。
  - 小程序 `uploadImageNote` 改为调用 `/api/notes/image-capture`，不再从笔记器打 `/api/ocr/images`。
  - 非 JSON 上传错误提示改为可读错误，413 时显示“图片太大，请换一张较小的图片”。
  - “我的笔记”页图片保存失败文案从“识别失败”改为“保存失败”。
- 已验证：
  - 图片保存相关后端测试：3 passed。
  - 后端全量测试：123 passed。
  - 小程序 JS 全量语法检查：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端编译检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端。
  - 线上 `POST /api/notes/image-capture` 使用 5.9MB PNG 验证，已返回业务层 JSON `404 用户不存在`，不再被 Nginx 拦成 HTML 413。

### 2026-06-21：22:53 真机分享打不开日志核对

- 用户提供测试路径：
  - `pages/note-preview/index.html?id=note_f114f85595`
  - `pages/showcase-view/index.html?sid=share_showcase_627fc56634_1782053566523_88269&from=user_25ec00a0f0&id=showcase_627fc56634&showcaseId=showcase_627fc56634&src=showcase_list_share`
- 线上日志核对：
  - 22:53:18/22:53:35，笔记详情请求仍是 `GET /api/notes/note_f114f85595?ownerUserId=user_25ec00a0f0` 和 `customer-actions/config?viewerUserId=user_25ec00a0f0`，没有看到真机走新版匿名公开接口 `/api/notes/public/note_f114f85595`。
  - 22:53:42，展示页请求已走 `GET /api/showcases/public/showcase_627fc56634`，并写入 `POST /api/showcases/showcase_627fc56634/events`，两者均为 200。
  - 本地直接请求生产 `GET /api/notes/public/note_f114f85595` 返回 200；`GET /api/showcases/public/showcase_627fc56634` 返回 200。
- 当前判断：
  - 笔记分享问题主要指向小程序前端体验版未更新到当前 `note-preview` 匿名公开接口逻辑，或测试手机仍在使用旧包。
  - 展示页公开接口后端已经正常返回；如果真机仍显示打不开，下一步应查小程序端页面渲染错误、旧包、体验成员/版本，而不是先改后端公开接口。
  - 用户粘贴路径里的 `.html` 更像微信开发者工具 page-frame 内部显示；当前代码生成的分享路径不带 `.html`。

### 2026-06-21：23:02 真机分享复测与 note-preview 接口收口

- 用户再次提供测试路径：
  - 笔记：`pages/note-preview/index.html?id=note_f114f85595`
  - 展示页：`pages/showcase-view/index.html?from=user_25ec00a0f0&showcaseId=showcase_21cb92837c&src=showcase_edit_share&id=showcase_21cb92837c&sid=share_showcase_21cb92837c_1782054127312_44205`
- 线上日志核对：
  - 23:02:32，笔记仍请求 `/api/notes/note_f114f85595?ownerUserId=user_25ec00a0f0` 和 `customer-actions/config?viewerUserId=user_25ec00a0f0`，说明当前真机包仍走私有接口。
  - 23:02:43，展示页已请求 `/api/showcases/public/showcase_21cb92837c`，并记录事件，均 200。
  - 生产公开接口手动验证：`/api/notes/public/note_f114f85595` 200，`/api/showcases/public/showcase_21cb92837c` 200。
- 已调整：
  - `pages/note-preview/index.js` 的资料加载固定使用 `api.fetchPublicNote(noteId)`。
  - 登录用户信息只用于客户动作配置和后续留资/接龙身份，不再决定客户预览页是否能加载资料。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：服务方案工作台白屏修复

- 背景：
  - 用户真机反馈服务方案工作台打开后白屏。
- 原因：
  - `service-offer-studio` 页面初始化时默认表单错误引用未定义变量，预览构建阶段也缺少图片数组兜底，导致页面 JS 运行时异常。
- 已完成：
  - 修复默认表单和预览构建逻辑，补齐安全默认模板、默认表单和默认预览数据。
  - 页面初始化增加可见错误卡片，登录缺失、模板加载失败或读取已有方案失败时显示“重试/去登录”，避免再次纯白屏。
  - 阶段区块和底部操作条在错误态下隐藏，避免半初始化页面继续触发异常。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 服务方案页面模拟加载：有用户时加载 4 套模板；无用户时显示登录提示，不白屏。
  - `git diff --check -- miniprogram/pages/service-offer-studio/index.js miniprogram/pages/service-offer-studio/index.wxml miniprogram/pages/service-offer-studio/index.wxss`：通过。

### 2026-06-22：电子名片独立三步式工作台

- 背景：
  - 用户明确要求电子名片不要继续藏在“我的笔记”或输入笔记器里，而是在资料库增加独立入口。
  - 电子名片核心体验应从“填资料”升级为“选一张好看的名片风格，改内容，直接发客户”。
- 已完成：
  - 新增 `pages/business-card-studio` 独立页面，流程为“选风格 -> 填资料 -> 确认效果”。
  - 4 款风格按用户参考图复刻方向实现：专业顾问风、门店名片风、专家个人品牌风、简洁微信风。
  - 同一份资料可自由切换 4 款风格，切换不清空姓名、头像、电话、微信、邮箱、二维码、介绍等内容。
  - 填写页支持头像和二维码图片上传，头像/二维码在页面中直接显示图片，不展示 URL。
  - 确认页同时展示“微信转发卡片封面效果”和“点开后的详情页效果”。
  - 保存仍复用 `UserNote + structuredData + conversionConfig` 基座，生成 `business_card` 资料卡。
  - 资料库快捷入口新增“电子名片”，旧添加页里的“电子名片”入口也改到新工作台。
- 已验证：
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - 小程序 `app.json` 与新页面 `index.json` JSON 解析检查：通过。
  - 新增/触达 WXSS 未发现核心独立 `px` 单位。
  - `git diff --check` 针对本轮触达文件：通过。
- 待用户验收：
  - 上传体验版后，从“资料库 -> 电子名片”进入，检查是否为独立三步式流程。
  - 在第一步确认 4 款风格差异明显；在第二步填写一份资料后，回到第一步切换风格，确认内容不丢。
  - 上传头像和二维码后，在确认页、保存后的客户详情页、微信转发卡片中检查图片显示。
  - 真机验证电话拨号、复制微信、复制邮箱和留资入口。

### 2026-06-22：电子名片模板选择页体验修正

- 背景：
  - 用户反馈 4 个模板预览只有单字头像，显得粗糙。
  - 双列模板在手机屏幕上会压缩横向名片比例，看起来像变形。
  - 需要确认制作预览、保存后的详情页和微信转发卡片读取同一套数据。
- 已完成：
  - 4 款模板预览改为两男两女职业头像样板，不再只显示首字。
  - 4 款模板补充更完整的默认姓名、身份、机构、联系方式和服务标签。
  - 模板选择页新增“列表 / 双列”切换，默认列表卡片，双列作为快速浏览模式。
  - 微信转发卡片生成器调色与 4 款模板对齐，并移除“预约沟通”文案。
  - 核对保存链路：制作页写入 `displayTemplate` 与 `structuredData`，详情页和转发封面均从同一套字段读取。
- 已验证：
  - `node --check` 检查电子名片工作台、模板库、分享封面生成器：通过。
  - 小程序 JSON 解析检查：通过。
  - 电子名片工作台 WXSS 未发现核心独立 `px`。
  - 本轮触达文件 `git diff --check`：通过。

### 2026-06-22：电子名片模板头像改为本地写真头像

- 背景：
  - 用户希望 4 款模板头像从 CSS/文字样板升级为更真实的写真美女和男生头像。
- 已完成：
  - 生成 2 男 2 女超现实写真风头像素材。
  - 曾短暂切分为本地小程序资源；后因主包超过 2MB，已迁移为服务器 WebP，前端不再保留本地头像图片。
  - 模板预览优先显示服务器 WebP 写真头像，保留 CSS/首字兜底。
- 已验证：
  - 原始头像素材可正常裁切；当前有效资源以服务器 WebP 为准。
  - `node --check` 检查电子名片工作台和模板库：通过。
  - 电子名片工作台 WXSS 未发现核心独立 `px`。
  - 本轮触达文件 `git diff --check`：通过。

### 2026-06-22：电子名片写真头像迁移到服务器 WebP

- 背景：
  - 真机调试报错 `source size 2200KB exceed max limit 2MB`。
  - 原因是 4 张写真 PNG 放入小程序前端包后，主包从约 1.5MB 增至约 2.9MB，超过微信小程序 2MB 主包限制。
- 已完成：
  - 4 张头像通过线上上传接口转存为服务器 WebP，前端不再携带头像图片文件。
  - 模板头像改为 HTTPS WebP 地址：
    - `https://teambuy.lifelove.top/media/media_a535beaccd-manual_asset_0afb19f5db.webp`
    - `https://teambuy.lifelove.top/media/media_35b3a047fc-manual_asset_25ae3bb5b2.webp`
    - `https://teambuy.lifelove.top/media/media_c8b9458757-manual_asset_b208951151.webp`
    - `https://teambuy.lifelove.top/media/media_94ec97ee72-manual_asset_744c2c96ca.webp`
  - 后端补 `image/webp` MIME 映射并已部署生产，避免 `/media/*.webp` 返回 `text/plain`。
  - 前端包里的 PNG/JPG 写真头像文件已移除，小程序目录体积降至约 1.5MB。
- 已验证：
  - 生产 `/health` 正常。
  - 4 个 WebP 公网访问返回 `200` 且 `content-type: image/webp`。
  - `node --check miniprogram/utils/sales-page-templates.js`：通过。
  - `python3 -m py_compile backend/app/main.py`：通过。
  - 本轮触达文件 `git diff --check`：通过。

### 2026-06-22：电子名片写真头像重新裁切

- 背景：
  - 用户真机截图显示部分模板头像仍是 4 人拼图或裁切错位。
  - 原因是首次用 `sips --cropOffset` 裁切时偏移理解错误，导致个别头像没有按 2x2 原图正确裁切。
- 已完成：
  - 改用系统图像库按像素坐标重切：左上男、右上女、左下女、右下男。
  - 重新上传为服务器 WebP，并替换模板 URL。
  - 新头像均为单人 320x320 源图转 WebP。
- 已验证：
  - 本地目视确认 4 张重切头像均为单人头像。
  - 4 个新 WebP 公网访问返回 `200` 且 `content-type: image/webp`。
  - `node --check miniprogram/utils/sales-page-templates.js`：通过。

### 2026-06-22：已有电子名片迁入工作台换风格

- 背景：
  - 用户希望已经做好的电子名片，可以从“我的笔记/编辑名片”进入电子名片工作台，实时切换风格，查看卡片预览和详情预览，并保存/分享。
  - 用户同时要求“我的笔记”的编辑名片页不再直接放“选名片风格”区域，因为那里看不到完整视觉效果。
- 已完成：
  - `business-card-studio` 支持 `?id=noteId` 读取已有 `business_card` 名片。
  - 工作台顶部新增“已做好的名片”区域，显示当前名片标题/摘要，并提供编辑资料、客户页入口。
  - 确认页改为“卡片预览 / 详情预览”切换。
  - 确认页底部新增 4 款模板缩略图，切换后实时刷新预览。
  - 切换风格后标记为未保存，保存后才显示客户页预览和分享按钮，避免分享旧模板。
  - 保存时保留已有 `conversionConfig`，不覆盖编辑页配置过的 SCRM/转化能力。
  - `note-edit` 电子名片字段区移除风格网格，改为“设置名片风格”按钮，跳转电子名片工作台。
- 已验证：
  - `node --check` 检查电子名片工作台、我的笔记编辑页、模板库：通过。
  - 本轮触达 WXSS 未发现核心独立 `px`。
  - 本轮触达文件 `git diff --check`：通过。
- 后续真机测试要求：
  - 必须重新上传最新小程序体验版/正式版。
  - 客户手机必须使用已加入体验成员的另一个微信号，或等待正式版发布后用普通微信测试。
  - 新版笔记客户页打开时应命中 `/api/notes/public/{noteId}`。

### 2026-06-21：经营看板从总数看板改为可递进处理台

- 用户反馈：
  - 上传新版小程序后分享打开问题已解决。
  - 经营看板“打开、访客、看资料、咨询”能看到总数，但不知道是哪一个展示页的数据，也无法点击处理。
  - 分享来源和访客详情只有报表感，没有递进到具体客户、手机号、微信、线索、订单或资料动作。
  - 登录后头像仍是白色，怀疑是否因为还没有设置中心。
- 已处理：
  - 后端 `/api/dashboard/business` 保留原有字段，并新增：
    - `showcaseBreakdown`：按每个展示页返回打开、访客、看资料、咨询、分享来源、状态和最近事件时间。
    - `visitorProfiles`：按访客聚合展示页事件、客户动作、线索资料、订单入口、电话、微信、来源展示页和看过的资料。
    - `topShares` 补充 `visitorNames/visitorCount`，让分享来源能看到该批次带来的访客。
  - 小程序 `pages/business-dashboard` 改造：
    - 顶部四个数字明确为“全部展示页汇总”。
    - 新增“按展示页拆解”列表，每行可进入对应展示页效果页。
    - 分享来源展示访客名和数据，并可进入对应展示页效果页。
    - 最近客户/访客详情改为客户卡片，显示来源、动作、电话、微信和“处理线索/查看订单/查看动作”入口。
    - 去掉“白色情人”“周末草莓团购”等硬编码演示文案，避免误导数据归属。
  - 头像处理：
    - 经营看板继续过滤 `example.com/avatar-demo` 等无效头像，并显示彩色首字兜底。
    - “我的”页头像如果没有真实头像地址，改为彩色首字兜底，不再显示空白图片。
- 已验证：
  - 后端全量测试：127 passed。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，公网 `/api/dashboard/business?ownerUserId=user_25ec00a0f0` 返回 `showcaseBreakdown=14`、`visitorProfiles=20`、`topShares=6`。
- 后续仍需继续：
  - 小程序需要用户重新上传体验版，才能看到新的经营看板页面。
  - 头像真实上传/修改仍需要后续“设置中心/资料设置”能力；微信登录只给 openid，不会自动给头像昵称。
  - 客户库和待联系页面还需要按同一思路继续重构：总看板 -> 分来源列表 -> 具体客户/动作/成交或下单处理。

### 2026-06-21：客户库和待联系改为递进处理视图

- 背景：
  - 用户指出客户库和待联系也不能只做列表或总看板，需要从总数递进到来源、具体客户和处理动作。
- 已完成：
  - 客户库：
    - 新增“处理阶段”分组：待处理、今日跟进、已联系、已归档。
    - 新增“来源资料”分组：按资料来源展示客户数、高意向、待处理数量，点击后筛到具体客户。
    - 客户卡片增加头像兜底、状态、下一步动作、外呼、复制、来源资料、今日跟进、跟进记录和标记联系。
    - 筛选体系补 `activeStageFilter`，常用视图也会保存处理阶段。
  - 待联系：
    - 新增“优先处理”区，优先展示逾期、今日和待联系线索。
    - 新增“按来源资料拆解”，点击来源后只看该资料带来的线索。
    - 线索卡片增加头像兜底、微信复制入口，并保留拨号后标记已联系。
- 已验证：
  - `node --check miniprogram/pages/customers/index.js`：通过。
  - `node --check miniprogram/pages/leads/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 后续：
  - 需要用户重新上传体验版，真机确认客户库和待联系页面的分组、按钮居中、头像兜底和外呼/复制交互。
  - 下一步可继续补“成交/订单结果”维度，把客户库与商家订单页、订单详情进一步串起来。

### 2026-06-22：订单/接龙接入客户处理链路

- 背景：
  - 用户要求看板、客户库、待联系最终都能落到成交的人、问询的人、下单的人身上。
- 已完成：
  - 客户库：
    - 加载商家订单数据，并按联系方式/昵称与客户资料做轻匹配。
    - 新增“下单 / 成交”面板，展示待处理、已联系、已成交、已取消，以及最近下单客户。
    - 客户卡片显示最新订单状态，主操作会优先进入订单详情。
  - 商家订单中心：
    - 新增“订单状态”分组：待处理、已联系、已完成、已取消。
    - 新增“来源商品”分组：按商品/团购资料展示总单、待处理、成交、接龙。
    - 订单列表从商品视角调整为买家处理视角，显示买家头像兜底、买家名、商品来源、规格、电话/微信操作。
  - 订单详情：
    - 商家侧补“复制微信”按钮，和拨号、复制地址一起形成处理动作。
- 已验证：
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - `node --check miniprogram/pages/order-detail/index.js`：通过。
  - `node --check miniprogram/pages/customers/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。
- 后续：
  - 需要上传小程序体验版真机确认商家订单中心、客户库下单面板、订单详情复制微信。
  - 后续可进一步补“客户成交漏斗”独立视图，但当前已能从客户库/订单中心进入具体下单人。

### 2026-06-22：资料点击排行下钻到具体访客

- 背景：
  - 经营看板顶部“看资料”已经能筛出所有看过资料的人，但“资料点击排行”单条资料仍只是跳动作页，不能直接回答“这条资料是谁点的”。
- 已完成：
  - 后端 `/api/dashboard/business` 的 `visitorProfiles` 新增 `noteIds`，记录每个访客点过的资料 ID。
  - 小程序经营看板点击“资料点击排行”单条资料时，直接切到访客详情，并只显示点过该资料的访客和动作流水。
  - 动作流水筛选兼容 `noteIds`，避免同一个客户点过多条资料时筛选不准。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端 Python 3.12 编译检查：通过。
  - `git diff --check`：通过。
  - 已部署生产后端，公网 `/api/dashboard/business?ownerUserId=user_25ec00a0f0` 返回 `visitorProfiles` 中包含 `noteIds`。
- 未覆盖：
  - 本机后端 pytest 受本地 Python 3.9 虚拟环境限制未跑；此前后端全量测试已通过，线上部署后健康检查通过。

### 2026-06-22：经营看板访客详情处理卡

- 背景：
  - 访客列表虽然能跳转到线索、订单或资料动作，但点击后会直接离开看板，用户还没确认“这个人是谁、从哪里来、看过什么、联系方式是什么”。
- 已完成：
  - 经营看板点击访客后先打开页内客户详情处理卡。
  - 详情卡展示头像/兜底头像、来源、打开/看资料/咨询次数、电话、微信、来源展示页、看过资料和分享批次。
  - 详情卡内保留外呼、复制微信、回到列表和进入业务处理入口。
- 已验证：
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：客户库补客户详情处理卡

- 背景：
  - 客户库卡片已经有外呼、复制、订单和跟进按钮，但操作散在卡片里，新用户仍可能不知道这个客户的完整上下文和下一步。
- 已完成：
  - 客户库点击客户头像/姓名区域后，先打开页内客户详情处理卡。
  - 详情卡集中展示客户阶段、意向、电话、微信、来源资料、最近查看、最近跟进、订单状态和客户标签。
  - 详情卡内保留查看客户、来源资料和下一步处理主按钮；原卡片上的快操作不变。
- 已验证：
  - `node --check miniprogram/pages/customers/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：待联系补线索详情处理卡

- 背景：
  - 待联系页已经有来源、电话、微信和处理按钮，但缺少一个先看完整线索再处理的入口，和经营看板/客户库心智不完全一致。
- 已完成：
  - 待联系页点击线索头像/姓名区域后，打开页内线索详情处理卡。
  - 详情卡集中展示状态、跟进时间、电话、微信、来源资料、查看次数、最近查看、备注、最近跟进和归档原因。
  - 详情卡内保留拨号、复制微信、查看线索、来源资料和立即处理主按钮。
- 已验证：
  - `node --check miniprogram/pages/leads/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：订单/接龙补买家处理卡

- 背景：
  - 订单中心已经按状态和来源商品拆解，但点击订单卡会直接进入订单详情，列表页缺少“先确认买家和来源，再处理”的轻路径。
- 已完成：
  - 订单/接龙列表点击订单卡后，先打开页内买家订单处理卡。
  - 处理卡展示买家头像/兜底头像、订单状态、下单时间、来源商品、规格/数量、接龙或下单类型、备注、地址和联系方式。
  - 商家侧可在处理卡内直接外呼、复制微信、查看订单或立即处理。
- 已验证：
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：头像白块兜底扩大覆盖

- 背景：
  - 用户真机测试反馈登录后头像仍可能白色。原因不是只缺设置中心，还包括旧 mock 登录、旧统计事件和旧资源链路里会保存或渲染 `example.com/avatar-default`、临时路径等不可用头像。
- 已完成：
  - 小程序 `utils/dashboard` 新增统一 `safeAvatarUrl/avatarText`，首页、访客线索、资源管理页、展示页列表和展示页统计页复用清洗。
  - 首页“谁看过我”、访客线索、资源管理页访客、接龙组件、资料动作页、展示页公开页、展示页列表和站内消息都补头像兜底或头像清洗。
  - 登录页默认头像从 `example.com` 改为空，避免继续写入无效头像。
  - 后端登录、mock 登录和接龙默认头像改为空；用户资料更新时拒绝 `example.com/avatar-default/wxfile/tmp` 等无效头像。
  - 已部署生产后端，公网验证无效头像更新返回 `400 头像地址必须是可访问的 HTTPS 地址`。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - 后端 Python 3.12 编译检查：通过。
  - 生产 `/health`：通过。
  - `git diff --check`：通过。
- 待用户验收：
  - 需要重新上传小程序体验版。
  - 真机重点看首页访客、访客线索、经营看板、客户库、待联系、订单中心、展示页列表和资料动作页是否还有白头像。

### 2026-06-22：头像与下钻完成度审计补漏

- 审计结果：
  - 经营看板、客户库、待联系、订单/接龙已经覆盖“总览/来源/状态 -> 具体人 -> 处理卡 -> 外呼/复制/业务详情”。
  - 头像直渲染剩余风险主要在旧 `business-dashboard` 组件和部分旧资源统计链路。
- 已完成：
  - 旧 `components/business-dashboard` 组件内部增加头像 URL 清洗和文字兜底。
  - 旧组件模板改为读取清洗后的 `displayDashboard`。
- 已验证：
  - `node --check miniprogram/components/business-dashboard/index.js`：通过。
  - 小程序全量 JS 检查：通过。
  - 小程序 JSON 检查：通过。
  - 后端 Python 3.12 编译检查：通过。
  - `git diff --check`：通过。

### 2026-06-22：我的笔记与我的页小优化收口

- 背景：
  - 用户真机反馈“我的笔记”需要更清楚地区分普通笔记，迁入待处理筛选态不够明显，顶部保存图片入口不应留在笔记列表。
  - “我的”页底部退出按钮和编辑资料按钮在真机上有变形风险，访客线索/待联系入口与经营看板心智重复。
- 已完成：
  - “我的笔记”分类快捷项改为“全部 / 普通笔记 / 房源 / 商品团购”，普通笔记按 `text_note` 且无业务候选本地筛选。
  - “最近迁入”点击待处理后，迁入卡和按钮增加绿色选中背景，列表条数变化和筛选态同步可见。
  - 删除“我的笔记”顶部“保存图片”入口；图片保存继续从笔记器/添加入口走。
  - 笔记数量蓝色胶囊显式使用 `rpx` 字号并用 flex 居中，减少 iPad/大屏显示差异。
  - “我的”页编辑资料和退出登录移到头像昵称下方，去掉底部退出按钮；编辑资料弹窗去掉“头像链接”输入。
  - “我的”页移除访客线索、待联系和客户库主入口，保留经营看板作为经营主入口；客户库/待联系底层页面暂不删除，避免影响看板下钻和历史链路。
  - `AGENTS.md` 新增小程序尺寸单位硬规则：核心布局、统计数字、头像、按钮和宫格默认使用 `rpx`。
- 已验证：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 JSON 解析检查：通过。
  - `git diff --check`：通过。

### 2026-06-23：服务方案工作台横向重排与资源库入口补齐

- 背景：
  - 用户反馈服务方案工作台纵向过长，手机里同时看不到步骤心智和模板参考。
  - “服务报价 / 案例背书”缺少有质感的默认图，像半成品。
  - 服务方案入口不能只藏在“笔记器/快速入库”里，需要在资源库与“电子名片”并列出现。
- 已完成：
  - `pages/service-offer-studio/index` 将“选模板 / 填资料 / 确认效果”改为横向步骤条。
  - 模板选择区改为横向卡片滑动，点击即联动下方详情预览。
  - 为“服务报价”接入装修空间默认图，为“案例背书”接入案例主图和 3 张案例缩略图。
  - 工作台表单预览、确认预览、客户详情页预览和分享图统一支持模板默认图兜底。
  - 资料库在“电子名片”旁边新增“服务方案”独立入口，保留原“快速入库”入口不删。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/note-preview/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/utils/sales-page-templates.js`：通过。
  - `node --check miniprogram/utils/business-card-share.js`：通过。
  - `git diff --check`：通过。

### 2026-06-23：服务方案工作台真机变形修正

- 背景：
  - 用户真机截图反馈服务方案工作台在手机/iPad 上标题、步骤、模板卡和图片都出现撑宽、裁切粗糙或变形。
  - 用户要求参考“我的笔记 / 电子名片”的稳定样式，副标题自动换行，并继续坚持核心尺寸使用 `rpx`。
- 已完成：
  - 服务方案顶部步骤条改为电子名片同款三列布局，不再用横向滚动撑开页面。
  - 页面壳、标题、副标题、阶段说明、模板卡标题和摘要补齐宽度约束与自动换行。
  - 模板选择卡去掉缩略图，只保留模板名称、标签和适合场景说明，减少首屏拥挤和横向溢出。
  - 将低分辨率裁图替换为 v2 高分辨率源图，并通过后端上传接口压缩转存为服务器 WebP：报价空间、案例成果、材料细节。
  - 清空小程序 `miniprogram/static/service-offer` 中的图片文件，避免 6.5MB 资源进入前端代码包。
  - 预览大图和案例小图继续使用 `aspectFill`，并固定 rpx 高度，避免图片被拉伸。
  - 选择模板横向滚动区补齐 `2rpx` 安全内边距、`box-sizing` 和宽度约束，避免右侧撑出整页。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/utils/sales-page-templates.js`：通过。
  - 服务方案工作台相关 WXSS/WXML 未发现非 `rpx` 的核心 `px` 尺寸。
  - 新 v2 源图尺寸为 `1774x887`，后端 WebP 资源公网返回 `200` 且 `content-type: image/webp`。
  - `miniprogram/static/service-offer` 已移除，前端不再保留服务方案默认图片文件。
  - `git diff --check`：通过。

### 2026-06-23：服务方案工作台三步页面手机溢出补修

- 背景：
  - 用户继续反馈服务方案工作台中，模板选择卡下方预览、填写资料页底部按钮、确认效果页在手机端仍有横向溢出。
- 已完成：
  - 服务方案工作台主阶段卡、预览卡、表单卡、确认页客户预览统一补齐 `width: 100%` / `max-width: 100%` / `min-width: 0` 约束。
  - 内层关键卡片采用 `calc(100% - 4rpx)` 并保留左右 `2rpx` 安全留白，避免贴边和撑出屏幕。
  - 缩小详情预览内英雄图、头像、左右边距和标题字号，减少手机宽度下的挤压。
  - 确认页底部 4 个客户动作从一行 4 列改成 2 列，防止文字和格子挤压。
  - 工作台底部操作条从固定 grid 列改为 flex，可随“返回 / 确认效果 / 保存并使用 / 预览 / 分享”自动收缩。
  - “下一步：确认效果”按钮文案缩短为“确认效果”，避免文字超出蓝色按钮背景。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 服务方案工作台相关 WXSS/WXML 未发现非 `rpx` 的核心 `px` 尺寸。
  - 前端未重新引入 `/static/service-offer` 图片引用。
  - `miniprogram/static` 未发现超过 200KB 的静态图片文件。

### 2026-06-23：服务方案底部遮挡与转发封面一致性修正

- 背景：
  - 用户真机反馈服务方案工作台底部“返回 / 使用这个模板”等按钮会挡住模板和上方预览区域。
  - 用户要求服务方案微信转发卡片、模板预览和“我的笔记”列表展示像电子名片一样保持完整一致，不要退回默认小程序卡片。
- 已完成：
  - 服务方案工作台增加底部真实 spacer，并把 sticky 底部操作条更贴近安全区，三步页面底部内容不再被按钮压住。
  - “我的笔记”服务方案列表卡改为专属销售方案预览卡，展示模板名、方案标题、卖点、标签和封面图。
  - `note-display` 增加 `serviceOfferPreview`，优先使用用户封面，缺省时使用模板默认图。
  - “我的笔记”列表分享图预生成从只支持电子名片扩展为电子名片 + 服务方案。
  - 服务方案分享优先使用 `generateServiceOfferShareImage` 生成的横版模板封面，标题使用服务方案标题和卖点。
- 已验证：
  - `node --check miniprogram/pages/notes/index.js`：通过。
  - `node --check miniprogram/pages/note-preview/index.js`：通过。
  - `node --check miniprogram/utils/note-display.js`：通过。
  - `node --check miniprogram/utils/business-card-share.js`：通过。
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 服务方案工作台与我的笔记相关 WXML/WXSS 未发现核心布局 `px`。
  - `miniprogram/static` 仍为约 `88K`，未发现超过 200KB 的静态文件。
  - `git diff --check`：通过。

### 2026-06-23：电子名片与服务方案 P0/P1 统一收口

- 背景：
  - 用户确认当前测试没有问题，要求把剩余 P0/P1 代码侧事项统一处理，体验版上传由用户负责。
- 已完成：
  - “我的笔记”服务方案双列卡片新增专属迷你方案预览，和列表卡、模板预览保持一致。
  - 电子名片 / 服务方案分享按钮增加封面生成中状态：封面生成前显示“封面准备中”，生成完成或失败后恢复“发名片 / 发方案”。
  - 服务方案列表、双列卡片、分享封面共用 `serviceOfferPreview` 预览数据，避免不同入口展示割裂。
  - 确认生产 mock 登录关闭能力已有后端开关和自动化测试覆盖。
  - 新增 `docs/qa/电子名片与服务方案P0P1收口_Codex自测报告.md`。
- 已验证：
  - 相关小程序 JS 语法检查通过。
  - 工作台 / 我的笔记相关 WXML/WXSS 未发现核心布局 `px`。
  - 小程序前端密钥关键词扫描仅命中登录页提示文案，未发现真实密钥。
  - `miniprogram/static` 约 `88K`，未发现超过 200KB 静态文件。
  - `git diff --check`：通过。
  - 后端 `test_mock_login_can_be_disabled` 用例存在；本轮本机 Python/pytest 环境不匹配，未能实际执行。

### 2026-06-23：首页与 Tabbar 工作台模式一期验收

- 背景：
  - 用户要求基于 `首页Tabbar工作台模式一期_Codex自测报告.md` 和 `首页与 Tabbar 工作台模式一期_测试清单与验收标准.md` 输出验收报告。
- 已完成：
  - 新增 `docs/qa/工作台第一期_验收报告.md`。
  - 验收结论为“不通过”：P0 未全部闭环，不能进入上线确认。
  - 明确 P0-23 业务识别后缺少“切换对应工作台 / 继续当前工作台”专门提示。
  - 明确 P0-27 权限和隐私缺少专项真机或接口回归证据。
  - 输出 5 个 Bug 单、P0/P1 回归清单和上线前检查事项。
- 后续：
  - 开发 Codex 先修复 P0-23，并补齐 P0-27 权限回归证据。
  - 最新体验版上传后，再按报告第 6 节做真机 P0 回归。

### 2026-06-23：资料库列表/双列展示与客户入口修正

- 背景：
  - 用户真机反馈企业微信纯文字、微信笔记、链接均能进入资料库，但资料区域只显示左半边，SCRM/留言入口不明显。
- 已完成：
  - `pages/library` 新增“列表 / 双列”切换，默认列表展示，双列用于快速浏览。
  - 资料库卡片补齐 `list-mode/grid-mode` 页面级样式，覆盖全局半宽卡片规则，避免只占左半屏。
  - 资料卡固定显示“客户/SCRM”和“留言”入口；“客户/SCRM”进入线索/访问管理，“留言”进入消息中心。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check -- miniprogram/pages/library/index.js miniprogram/pages/library/index.wxml miniprogram/pages/library/index.wxss`：通过。
- 待真机验收：
  - 重新上传体验版后，确认资料库列表模式不再半屏显示，双列模式左右两列都能正常铺满。

### 2026-06-23：Python 3.12 环境与房源客户看板口径收口

- 背景：
  - 用户明确指出客户痕迹/待跟进是产品付费核心，不能只复用旧经营看板接口，也不能让房源看板混入非房源数据。
  - 本地后端验证此前受 Python 版本影响，决定统一使用 Python 3.12。
- 已完成：
  - 新建本地 `.venv312`，Python 版本为 `3.12.13`，并安装 `backend/requirements.txt` 全量依赖。
  - `.gitignore` 增加 `.venv312/`，后续本地虚拟环境不进入仓库。
  - `GET /api/dashboard/business` 增加 `mode` 参数。
  - `mode=property` 时后端走房源专属客户看板聚合：只统计房源资料、房源推荐包、房源客户动作和房源待跟进线索。
  - 房源模式的推荐包拆解、访客画像和资料排行过滤非房源 `note_click`，避免服务/普通资料点击混入房源看板。
  - 首页房源四指标优先使用后端房源看板汇总：房源数、打开、访客、待跟进。
  - 资料库房源卡片如存在 note 级客户动作，客户入口优先进入 `pages/note-actions`，不再误进旧 `manager` 导致待跟进数据看不到。
  - 新增后端用例 `test_property_business_dashboard_only_counts_property_customer_data`，覆盖房源看板隔离边界。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - `node --check` 覆盖首页、客户看板、资料页和 API 文件：通过。
  - `git diff --check` 覆盖本轮关键文件：通过。
- 待真机验收：
  - 用户上传体验版后，实际从房源首页点击 `打开 / 访客 / 待跟进`，确认进入客户看板对应 Tab。
  - 用一条真实房源产生浏览/预约后，确认首页数字、客户看板和单条资料客户动作页三处口径一致。

### 2026-06-23：房源首页今日/累计口径拆分

- 背景：
  - 用户指出首页标题为“今日概览”，但实际显示的是历史累计数据，会误导用户。
  - 用户要求点击“今日访客”后能看到今天具体是谁来了、看了哪些房源、如何联系。
- 已完成：
  - 房源看板后端返回 `summary` 和 `todaySummary` 两套口径。
  - `summary` 保持累计：当前房源总数、历史打开、历史访客、当前待跟进。
  - `todaySummary` 新增今日口径：今日新增房源、今日打开、今日访客、今日新增待跟进。
  - 单条房源浏览事件合并进客户看板 `visitorProfiles`，不再只显示推荐包访客。
  - 访客画像、最近访客和客户动作增加 `isToday` / 日期字段，前端可按今日真实过滤。
  - 首页房源概览增加“今日 / 累计”切换，默认展示今日。
  - 从首页今日 `打开 / 访客 / 待跟进` 进入客户看板时携带 `range=today`，客户看板只显示今日访客和今日动作。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - `node --check` 覆盖首页、客户看板和 API 文件：通过。
  - 关键文件 `git diff --check`：通过。

### 2026-06-23：房源待跟进数字与列表对齐

- 背景：
  - 用户反馈首页 `待跟进` 显示 1，但点击进入客户看板没有看到待跟进记录。
  - 核对后确认：数字统计来自 `LeadReminder`，但客户看板待跟进列表只来自 `CustomerAction`，旧访问详情/旧线索可能没有对应客户动作。
- 已完成：
  - 房源客户看板 `latestActions` 合并 pending `LeadReminder`。
  - 对没有 `CustomerAction` 的待跟进线索，生成 `lead-followup` 行，保留电话、微信、客户名、房源标题和 `leadReminderId`。
  - 单条房源排行的 `followupCount/todayFollowupCount` 同时按 action projection 和 `lead.cardId` 归因。
  - 补测试覆盖“有待跟进线索但没有客户动作”的场景。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `.venv312/bin/python -m compileall backend/app`：通过。
  - 关键文件 `git diff --check`：通过。
- 2026-06-23 19:30 后端补齐房源客户看板 propertyBreakdown 输出，并在待跟进动作中用 LeadReminder 反填客户姓名、电话、微信，避免首页“待跟进 1”进入看板后只显示空客户/空动作名。
- 2026-06-23 19:40 线上复验通过：/api/dashboard/business?mode=property 返回 todaySummary.pendingLeadCount=1；今日待跟进列表包含 高先生 / 预约看房 / 新世界广场B-938 / lead_1073169e12；propertyBreakdown=12。
- 2026-06-23 19:50 新增阶段性交接归档 `docs/handoff-策划运营.md`，汇总项目背景、阶段目标、已完成功能、关键文件、代码状态、风险、用户确认决策、下一步顺序和新 Codex 接手提示词。

### 2026-06-24：房源合集与资料库细节收口

- 背景：
  - 用户确认合集功能展示暂时可用，但反馈每次点合集都显示“正在读取”，担心频繁拉库给服务器压力。
  - 房源资料库卡片在客户状态已更新后仍显示红点。
  - 资料库“更多工具”中混入电子名片、服务方案，和当前房源资料库场景不一致。
  - 合集新建和分享层级偏深，需要先做轻量入口优化。
- 已完成：
  - `pages/showcases` 增加本地合集列表缓存，按用户和工作台模式缓存 5 分钟；有缓存时先显示本地数据，过期后后台同步最新数据。
  - 合集首页增加“分享最近”按钮，直接分享最近一个已发布合集；合集方向卡也可直接进入新建。
  - 资料库红点口径调整为只代表 `hasUnread` 或 `pending`，历史客户动态不再让红点常驻。
  - 资料库更多工具收口为资料相关入口：待认领、管理标签、我的笔记；电子名片和服务方案不再放在资料库工具区。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
- 待真机验收：
  - 第二次进入合集页应优先显示手机缓存，不再出现明显等待感。
  - 已处理客户状态后，房源卡红点应消失，但“客户动态 1 / 看客户”仍可用于复盘。
  - 资料库更多工具不再出现服务方案和电子名片。

### 2026-06-24：资料详情客户功能压缩与标签解释补齐

- 背景：
  - 用户反馈资料详情页“客户功能”展开后 6 行过长，希望改成两列减少页面长度。
  - 用户询问“管理标签”的作用，以及用户如何知道并使用。
- 已完成：
  - 资料详情页客户功能展开区改为两列卡片式开关，保留说明文字但将高度压缩到约 3 行。
  - 资料库入口文案从“管理标签”改为“标签设置”，减少管理后台感。
  - 标签管理页新增用途说明：快速筛选、自动归类、生成合集；新增标签示例改为房源语境。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/pages/tag-manage/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。

### 2026-06-24：房源筛选增强与详情页分层调整

- 背景：
  - 用户确认房源库需要加强价格、户型、地铁、电梯、状态等专门筛选，并要求价格支持两个区间输入。
  - 用户希望房源详情页继续分层，减少低频配置对主工作流的干扰。
  - 用户反馈标签按钮样式偏窄。
- 已完成：
  - 资料库在房源模式下新增“房源筛选”面板。
  - 支持最低价/最高价两个价格输入，并提供常用价格区间快捷筛选。
  - 支持户型、位置/地铁、电梯/楼梯、状态筛选。
  - 房源详情页调整层级：顶部动作后优先展示“客户反馈”，再展示“房源卡”，低频“客户功能”设置继续折叠/两列展示。
  - 标签管理页添加/删除按钮加宽加高，说明卡片提高最小高度。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/pages/tag-manage/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。

### 2026-06-24：房源筛选入口前置与合集条件筛选开放

- 背景：
  - 用户反馈资料库页面没有看到“分类筛选”，说明房源筛选入口依赖分类区过于隐性。
  - 用户询问合集里的“按条件筛选”是否可以打开。
- 已完成：
  - 资料库只要存在房源资料，就在“新增资料 / 更多工具”下方显示“房源筛选”面板，不再依赖用户先找到分类筛选。
  - 房源筛选默认不影响普通资料列表；只有输入价格或选择户型/地铁/电梯/状态等条件后，才按房源条件收窄列表。
  - 合集编辑页“按条件筛选”已启用，展示价格、户型、地铁、电梯/楼梯、状态条件面板。
  - 合集条件变化后自动重新计算候选房源并加入合集，用户仍可在下一步删减和调整顺序。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - 本轮相关文件 `git diff --check`：通过。

### 2026-06-24：房源工作台小闭环集中打磨

- 背景：
  - 用户认为前面建议的房源卡状态、筛选生成合集、详情页分层、客户反馈闭环和分享效果复盘都属于小优化，希望按顺序一起做完后统一验收。
- 已完成：
  - 房源卡新增状态分层：待处理、已跟进、有浏览、待分享。
  - 客户反馈页待跟进线索新增快捷处理：已联系、暂不合适、已完成、重点跟进。
  - 资料库房源筛选面板新增“用当前筛选生成合集”，会把当前价格/户型/地铁/电梯/状态条件带到合集编辑页。
  - 合集编辑页接收资料库条件，并启用“按条件筛选”，自动筛出符合条件的房源加入合集。
  - 合集效果页新增“客户看房轨迹”，基于最近事件展示客户、动作、房源和时间，可下钻处理对应房源。
  - 房源详情页新增“发客户 / 编辑资料”切换，默认进入发客户视角，编辑项放到“编辑资料”里。
- 已验证：
  - `node --check` 覆盖 `pages/library`、`pages/showcase-edit`、`pages/note-actions`、`pages/showcase-analytics`、`pages/note-edit`、`utils/dashboard`：通过。
  - 本轮相关文件 `git diff --check`：通过。
- 待真机验收：
  - 房源卡状态文案是否准确。
  - 客户反馈页四个处理按钮是否能正确刷新待跟进/已归档。
  - 资料库当前筛选生成合集后，合集条件和候选房源是否一致。
  - 合集效果页客户看房轨迹是否能解释“客户看了哪些房源”。
  - 房源详情默认“发客户”视角是否比长表单更清楚。

### 2026-06-24：标签设置到单房源展示链路补齐与系统校验

- 背景：
  - 用户测试后反馈：在标签设置里添加了几个标签，但看不到这些标签如何在每个房源上体现。
  - 用户要求系统再跑一轮校验。
- 已完成：
  - 资料库房源卡标签读取补齐：除旧 `categoryIds` 外，也读取资料 `visibilityConfig.userTags/tags`。
  - 房源详情页“编辑资料 -> 资料归类”新增“常用标签”，展示标签设置页创建的全局标签；点击后应用到当前房源，保存后回到资料库可显示和筛选。
  - 常用标签按钮加宽加高，避免过窄。
- 已验证：
  - 小程序关键脚本 `node --check` 覆盖资料库、合集编辑、客户反馈、合集效果、资料详情、标签管理和 dashboard 工具：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。

### 2026-06-24：房源系统标签自动补齐

- 背景：
  - 用户明确系统标签不应由用户点选，应该根据房源信息默认补齐，后续筛选和选房依赖这些标签。
- 已完成：
  - 房源保存时自动生成 `systemTags`，并合并进可筛选 `tags`。
  - 第一批系统标签覆盖：租金区间（1300以下、1300-1800、1800-2500、2500以上）、公寓/一房/两房/三房、地铁口/地铁、电梯房/楼梯房、可租/已租/暂停推广、待确认。
  - 用户手动标签保留在 `userTags`，不会被系统标签覆盖或删除。
  - 修正价格区间标签长度规则，避免 `1300-1800`、`1800-2500` 被过滤。
  - 租金区间只根据明确租金/价格字段生成，避免把标题编号误识别为租金。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - 房源工作台相关关键脚本 `node --check`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-24：房源工作台发客户前打磨

- 背景：
  - 用户确认房源工作台下一阶段先优化：客户视角预览、房源卡跟进闭环、合集发送前检查、筛选和系统标签继续补强。
- 已完成：
  - 房源详情“发客户”页签新增客户视角预览卡，展示封面、标题、位置、租金、户型、面积、押付、入住和客户可用动作。
  - 房源详情新增发布前检查：封面、租金、户型、位置、联系方式、已租/暂停状态。
  - 房源字段新增面积、楼层/电梯、押付方式、入住时间。
  - 系统标签补强：面积区间、小户型、押一付一/押一付三、随时入住/本周可住。
  - 资料库和合集条件筛选同步新增面积、押付方式、入住时间。
  - 房源卡状态增加下一步提示，例如待处理提示优先看客户，有浏览提示可再发客户。
  - 合集编辑页新增发布前检查，并在发布时对缺项弹窗确认。
- 已验证：
  - `node --check` 覆盖资料详情、资料库、合集编辑、dashboard、note-display：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。

### 2026-06-24：团购/商品工作台首页一期收口

- 背景：
  - 房源工作台已基本收口，用户希望按同样经验打磨团购场景。
  - 讨论后确认：主入口不叫单纯“商品工作台”，避免落入普通商品管理竞品心智；也不只叫“团购工作台”，避免限制商品展示、商品合集和访客反馈。
- 已完成：
  - 首页模式名称改为“团购/商品工作台”，说明文案改为“整理商品，发到群里，管理接龙和买家反馈”。
  - 团购/商品首页四指标改为“商品 / 待处理 / 今日接龙 / 访客”。
  - 首页团购/商品统计不再直接使用全量资料：商品数和访客数按 `groupbuy_product` 商品资料过滤，待处理和今日接龙使用现有卖家订单/接龙接口汇总。
  - 四指标点击路径收口：商品进入资料页商品筛选，待处理进入待处理名单，今日接龙进入今日名单，访客进入团购看板访客页。
  - 资料页新增 `groupbuy_product` 入口筛选，从首页进入时显示“当前只看商品资料”。
  - 接龙/买家名单新增 `date=today` 前端筛选参数，首页“今日接龙”可以落到今日名单。
  - 卖家侧订单页标题从“商家订单中心”收口为“接龙/买家名单”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - `node --check miniprogram/utils/workspace-mode.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机验收：
  - 上传体验版后确认首页四指标文字是否居中、不截断。
  - 确认四个指标点击是否符合直觉，尤其“今日接龙”是否只显示今天的接龙/买家。
  - 后续再进入商品资料卡片和接龙看板，不在本轮扩展完整电商能力。

### 2026-06-24：团购/商品资料库卡片一期打磨

- 背景：
  - 参考房源工作台推进逻辑，首页收口后继续让资料库里的业务卡片能直接回答“这条商品现在该做什么”。
  - 商品卡不能继续停留在普通资料卡形态，否则团长需要点进详情才能看到接龙、待处理、访客和规格价格。
- 已完成：
  - `utils/dashboard.js` 为 `groupbuy_product` 增加商品卡展示字段：价格/规格/自提/截止高亮信息、商品说明、接龙/下单/待处理/访客标签和下一步状态。
  - 资料库商品卡新增状态行：待处理 / 有接龙 / 有下单 / 有访客 / 待发布。
  - 商品卡第二行前置价格、规格、提货方式、截止时间，延续房源卡“标题下方先放关键决策信息”的经验。
  - 商品卡新增接龙/下单信号行，待处理时高亮。
  - 商品卡主操作改为：有接龙/下单/访客动态时显示“处理接龙 + 分享 + 更多”，无动态时显示“分享 + 更多”。
  - “处理接龙”优先进入 `pages/note-actions` 的商品接龙/下单名单，即使当前为空也展示该商品名单空态。
  - 商品详情页顶部工作台名称同步为“团购/商品工作台”。
- 已验证：
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `miniprogram/pages/library/index.json`、`miniprogram/pages/note-edit/index.json` 解析：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机验收：
  - 商品卡价格/规格/截止时间在小屏是否拥挤。
  - “处理接龙 / 分享 / 更多”按钮是否居中、不挤压标题。
  - 商品卡空态、待处理、有访客、有接龙四种状态是否符合团长直觉。

### 2026-06-24：团购/商品单品详情页发群前打磨

- 背景：
  - 用户建议继续按房源工作台推进逻辑打磨“单商品详情页”，让商品详情也分成高频运营和低频编辑，而不是长表单。
- 已完成：
  - 商品详情页新增“发群 / 编辑商品”双页签，默认先进入发群视角。
  - “发群”页签新增客户视角预览，展示商品图、标题、取货地点、价格/规格/取货方式/截止时间和客户可用动作。
  - “发群”页签新增发群前检查，覆盖商品图片、商品名称、价格/规格、取货方式、联系方式和 SKU 库存。
  - “发群”页签新增“接龙 / 买家反馈”区，聚合下单、接龙、待处理和消息中心入口。
  - “编辑商品”页签保留商品信息、图片/视频、规格与价格、取货与下单、资料归类等低频编辑项。
  - 商品标题、电话、快捷字段、SKU、素材和下单开关变化后，客户预览和发群前检查会实时刷新。
- 已验证：
  - `node --check miniprogram/pages/note-edit/index.js`：通过。
  - `miniprogram/pages/note-edit/index.json` 解析：通过。
  - 本轮详情页相关文件 `git diff --check`：通过。
- 待真机验收：
  - “发群 / 编辑商品”切换是否比长页面更顺手。
  - 客户视角预览在小屏下商品图、标题、标签是否拥挤。
  - 发群前检查是否提示准确、不过度焦虑。
  - 接龙/买家反馈入口是否符合团长处理名单的直觉。

### 2026-06-24：团购/商品合集发群前打磨

- 背景：
  - 单商品详情页已经形成“发群 / 编辑商品”结构，下一步按房源合集经验打磨“多个商品一起发群”的商品合集链路。
- 已完成：
  - 团购/商品工作台首页“商品合集”入口直接进入商品合集编辑页。
  - 资料库商品卡“加入合集”进入商品合集编辑页，不再只跳普通合集列表。
  - 合集编辑页根据当前分类切换文案：商品分类下显示发群、商品合集、商品条件、已选商品等语境。
  - 商品合集新增条件筛选：价格区间、取货方式、截止时间。
  - 商品合集发布前检查改为发群前检查，覆盖合集名称、已选商品、合集封面、联系入口、价格完整度、取货信息。
  - 商品合集条件面板使用团购/商品橙色选中态，与商品详情页保持一致。
- 已验证：
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/utils/note-display.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 待真机验收：
  - 从首页“商品合集”和资料库商品卡“加入合集”进入路径是否符合直觉。
  - 商品条件筛选是否能稳定筛出价格、取货和截止时间匹配的商品。
  - 发群前检查是否准确提示缺价格、缺取货信息。
  - 商品合集编辑页是否还残留容易误解的房源文案。

### 2026-06-24：团购/商品工作台 P0 代码侧补齐

- 背景：
  - 用户要求把团购/商品工作台 P0 全部补上，涉及人工测试的项目后置。
- 已完成：
  - 后端订单列表新增 `noteId` 过滤参数，卖家/买家都可按具体商品资料过滤订单/接龙，避免同名商品串单。
  - 小程序订单接口 `fetchOrders` 支持传 `noteId`。
  - 卖家“接龙/买家名单”页优先用 `noteId` 作为来源分组 key，展示仍使用商品名。
  - 从单商品入口进入名单时，“清除状态”不会跳出当前商品范围。
  - 后端测试新增同名商品场景，确认按 `noteId` 过滤时不会混入另一条同名商品订单。
  - 商品合集发群前价格识别收紧，避免把“3斤装”等规格数字误判为价格。
  - 复核客户下单/接龙链路：已有自动化覆盖售罄 SKU 阻止、重复提交阻止、团长可见、买家不可改状态、消息线程、订单状态更新。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `python3 -m py_compile backend/app/api/routes_orders.py backend/app/services/app_service.py`：通过。
  - `node --check` 覆盖订单页、商品合集页、首页、资料库、商品详情、API：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 后置人工测试：
  - 微信开发者工具/真机验证页面是否顺手、按钮是否居中、转发是否可打开。
  - 体验版上传和群内真实分享验证。

### 2026-06-24：团购/商品工作台 P1 代码侧补齐

- 背景：
  - 用户要求 P1 也直接开发完，之后统一进行测试。
- 已完成：
  - 商品合集客户侧卡片增强：正式发布快照和预览都携带商品规格、取货方式、取货地点、截止时间和“查看详情/接龙”提示。
  - 资料库新增商品筛选面板，支持价格区间、取货方式、截止时间、有接龙、有访客、待补价格、待补取货。
  - 资料库商品筛选可一键生成商品合集，并把当前价格/取货/截止条件带入合集编辑页。
  - 商品保存时自动生成系统标签：团购、商品、自提/配送/快递、今日截止/本周截止、有 SKU、已售罄、待补价格、待补取货。
  - 接龙/买家名单页新增“全部日期 / 今日新增”切换。
  - 商品资料新增“复用成新商品”：复制当前商品为新商品草稿，保留字段、图片和 SKU，不复制客户动作、订单或统计。
  - 后端新增 note 复制接口 `/api/notes/{note_id}/duplicate`。
  - 后端测试覆盖商品复制不复制客户动作、商品合集正式发布快照带商品 meta。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：98 passed。
  - `python3 -m py_compile` 覆盖订单、笔记路由和服务：通过。
  - `node --check` 覆盖资料库、商品合集客户页、商品合集编辑、订单页、商品详情、API：通过。
  - 页面 JSON 解析：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 后置人工测试：
  - 商品筛选面板小屏高度和按钮居中。
  - 商品合集客户页三种模板下价格/取货标签是否拥挤。
  - 复用成新商品后字段是否符合团长预期。
  - 今日新增切换在真实订单数据下是否符合直觉。

### 2026-06-24：工作台模式资料隔离修正

- 背景：
  - 用户反馈切换到团购/商品工作台后，资料页和工作台仍会显示房源信息。
- 已完成：
  - 资料库 Tab 直接进入时读取当前工作台模式；房源模式默认只看房源，团购/商品模式默认只看商品。
  - 资料库统计、分类、标签按当前模式后的资料集合重新计算，避免列表和数字不一致。
  - 底部工作台页按当前模式过滤资料后再计算概览和反馈列表。
  - 后端团购看板按团购/商品资料过滤笔记、相关合集、客户动作和线索，避免商品看板混入房源排行。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/visits/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
- 未完成：
  - 本机系统 Python 未安装 `pytest`，`python3 -m pytest backend/tests/test_app.py -q` 未能运行。
  - 仍需微信开发者工具/真机确认切换工作台后资料页、工作台页、团购看板均不混入房源。

### 2026-06-24：企业微信团购笔记未进团购工作台排查与修正

- 背景：
  - 用户反馈 16:14 左右通过企业微信发送团购微信笔记，但没有进入团购/商品工作台；同时非房源工作台仍显示房源筛选标签。
- 排查结论：
  - 线上 2026-06-24 16:13:51 收到企业微信会话存档回调。
  - 16:14:14 已生成 `note_ec9fc09893`，标题为“白凤乌鸡蛋”，`user_notes` 中类型为 `groupbuy_product / 团购`。
  - 未显示在团购工作台的原因是 `/api/cards` 返回的来源卡片没有透出来源资料的 `cardType/systemCategory/visibilityConfig`，前端只能靠标题关键词猜；“白凤乌鸡蛋”标题不含团购/商品关键词，导致被过滤掉。
- 已完成：
  - `/api/cards` 列表返回时附带来源 note 的 `cardType`、`systemCategory` 和 `visibilityConfig`。
  - 资料库房源筛选面板只在房源模式显示；商品筛选面板只在团购/商品模式显示。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - `git diff --check` 覆盖本轮关键文件：通过。
  - 本地模拟确认补出 `cardType=groupbuy_product` 后，“白凤乌鸡蛋”会被识别为商品。
- 未完成：
  - 本机系统 Python 未安装 `pytest`，完整后端测试未运行。
  - 需部署后端并上传/预览小程序后，在真机确认“白凤乌鸡蛋”进入团购/商品工作台。

### 2026-06-24：生产后端临时部署工作台类型透传

- 背景：
  - 用户要求先部署后端，以便继续测试前端团购/商品工作台。
- 已执行：
  - 生产服务器 `/home/ubuntu/teamBuy/backend/app` 已备份到 `/home/ubuntu/teamBuy_deploy_backups/backend_app_20260624_162457.tar.gz`。
  - 已同步本地 `backend/app` 到生产服务器。
  - 尝试 `docker compose build backend` 时卡在 `apt-get update`，旧后端容器保持运行。
  - 为了先让线上接口生效，已将服务器 `backend/app` 复制进当前 `teambuy-backend-1` 容器并重启容器。
- 已验证：
  - `https://teambuy.lifelove.top/health`：200，数据库正常。
  - `/api/cards?ownerUserId=user_25ec00a0f0` 中“白凤乌鸡蛋”已返回 `cardType=groupbuy_product`、`systemCategory=团购`、`sourceNoteId=note_ec9fc09893`。
- 注意：
  - 这次是容器内代码热替换，未完成镜像重建；如果后续强制重建镜像，应重新确认构建成功并验证接口。
  - 小程序前端仍需用户在微信开发者工具中预览/上传后，才能验证房源筛选面板显示逻辑。

### 2026-06-24：团购资料样式挤压与封面兜底修正

- 背景：
  - 用户真机反馈团购资料列表按钮堆叠、横向溢出；展示页编辑的已选商品区域也被操作按钮挤压。
  - 用户设置的封面在微信转发可见，但资料页团购卡片仍显示“资料”占位。
- 已完成：
  - 团购资料卡片动作区改为两行/两列布局：有接龙时“处理接龙”独占一行，“分享/更多”下一行平分；无接龙时“分享/更多”平分。
  - 团购资料卡片按钮补齐 flex 居中、最小宽度和文本不换行约束，避免真机上按钮撑破卡片。
  - 展示页编辑的已选商品行改为“封面+正文”在上、“上移/下移/隐藏/删除”操作在下，避免正文被四个小按钮挤压。
  - 后端 `/api/cards` 列表在卡片自身没有封面时，兜底返回来源资料的封面或第一张图片。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/showcase-edit/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
  - 生产 `https://teambuy.lifelove.top/health` 正常。
  - 生产 `/api/cards?ownerUserId=user_25ec00a0f0` 中“白凤乌鸡蛋”已返回线上 `coverUrl`。
- 注意：
  - 后端封面兜底已热更新到线上容器；镜像仍未完成重建。
  - 前端样式需要微信开发者工具重新预览/上传后，真机才能看到。

### 2026-06-24：资料卡片操作按钮改为内容宽度

- 背景：
  - 用户真机反馈资料卡片底部操作按钮背景仍然过长，分享/更多像长条一样横向占满。
- 已完成：
  - 资料卡片操作区从等分网格改为可换行 flex 胶囊布局。
  - “看客 / 分享 / 更多 / 处理接龙”等按钮按文字内容和最小可点宽度显示，不再平分整行。
  - 房源和团购商品资料卡片共用该规则，避免两个工作台重复出现长按钮。
- 已验证：
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `git diff --check -- miniprogram/pages/library/index.wxss`：通过。

### 2026-06-24：客户资料提交文案改为留言

- 背景：
  - 用户反馈原客户资料提交术语偏运营内部表达，普通用户不容易理解。
- 已完成：
  - 小程序可见文案统一改成“留言”相关表达，覆盖资料详情、客户动作页、客户看板、工作台配置、电子名片/服务方案和分享图文案。
  - 后端演示数据文案同步改成“留言”。
  - 保留内部字段名和 action key 不变，避免影响已有数据结构和统计逻辑。
- 已验证：
  - `rg -n "留资" miniprogram backend/app backend/mock`：无结果。
  - 相关小程序 JS 语法检查通过。
  - `python3 -m py_compile backend/app/services/app_service.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-24：客户看板命名与创建时间展示

- 背景：
  - 用户认可第四个 Tab 可叫“客户看板”，并希望资料库和合集卡片下方显示创建时间。
- 已完成：
  - 底部第四个 Tab 从“工作台”改为“客户看板”，客户看板页面标题同步调整。
  - 首页和我的页跳转第四个 Tab 的入口文案改为“去客户看板”。
  - 资料库卡片新增“创建于 …”时间行。
  - 合集列表卡片新增“创建于 …”时间行。
- 已验证：
  - `node -c` 覆盖资料库、合集列表和时间格式化工具：通过。
  - `miniprogram/app.json` JSON 解析：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-24：团购/商品 P1 体验收口

- 背景：
  - 用户确认团购/商品主链路基本没问题，希望优先处理 P1 中客户看板团购化、商品复用体验和空态引导。
- 已确认：
  - 团购高置信识别不是只看标题，而是用全文和结构化字段综合判断：商品信号、价格/解析提示、取货/规格/截止信号、团购分数高于房源分数等。
- 已完成：
  - 客户看板在团购模式下改为“待处理 / 买家/访客 / 商品效果 / 发群效果”，首屏文案和空态切到接龙、下单、买家、商品点击语境。
  - 商品“复用成新商品”增加确认说明：复制文案、图片、规格和取货设置，不复制旧接龙、订单、访客和统计；成功后进入新商品编辑页。
  - 团购资料库空态新增“新建商品 / 商品合集”入口。
  - 团购合集空态新增“先建一个商品”入口。
  - 首页团购模式空态提示发群后会更新打开、访客和接龙动态。
- 已验证：
  - `node -c` 覆盖客户看板、资料库、合集页、首页：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-24：电子名片/服务工作台一期优化启动

- 背景：
  - 用户开始推进电子名片/服务工作台，希望参考房源和团购工作台经验优化首页和场景能力。
- 当前判断：
  - 服务工作台已有首页皮肤和入口，但还需要从“换皮”推进到“独立场景”：名片/服务方案资料隔离、咨询看板语境、服务合集和空态引导。
- 已完成：
  - 服务工作台首页统计按电子名片和服务方案过滤，不再用全量资料计算。
  - 首页“看资料”和统计卡进入资料库时，自动切到“名片/服务方案”视图。
  - 资料库支持 `service_workspace` 入口过滤，只显示电子名片和服务方案。
  - 客户看板服务模式 Tab 改为“待咨询 / 访客 / 方案效果 / 案例合集”，首屏和效果页文案切到咨询、方案、案例合集语境。
  - 首页服务模式空态提示先做名片、再补服务介绍页；咨询反馈空态提示名片/方案发出后回流。
- 已验证：
  - `node -c miniprogram/pages/home/index.js`：通过。
  - `node -c miniprogram/pages/library/index.js`：通过。
  - `node -c miniprogram/pages/business-dashboard/index.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-24：电子名片/服务工作台 P0 闭环补强

- 背景：
  - 用户确认先做服务工作台 P0，希望按房源和团购工作台经验继续推进。
- 已完成：
  - 服务工作台首页统计修正：资源数统计电子名片 + 服务方案，咨询数只统计真实客户互动，不再用服务方案数量兜底。
  - 后端客户看板支持 `mode=service` 数据隔离，只聚合电子名片和服务方案相关资料、合集、客户动作和线索。
  - 电子名片工作台新增发给客户前检查，覆盖身份、联系方式、个人介绍、头像/二维码。
  - 服务方案工作台新增发给客户前检查，覆盖服务名称、服务内容、留言/预约、联系方式、封面/案例图。
  - 电子名片和服务方案在未保存或有未保存改动时隐藏右上角分享菜单；保存后才允许分享，避免误发编辑器页。
  - 两个工作台确认页底部主按钮改为“保存并预览”，保存后直接进入客户页确认效果。
  - 服务客户看板默认文案按模式切换，不再在服务模式下出现“预约看房 / 看房源 / 房源资料”兜底。
  - 新增后端服务看板隔离回归用例，覆盖名片、服务方案和团购商品混合时只统计服务资料。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py`：通过。
  - 本轮关键文件 `git diff --check`：通过。
- 未完成验证：
  - `python3 -m pytest ...` 未运行成功，本机 Python 环境缺少 `pytest`。
  - 小程序真机需要用户重新预览/上传体验版后验证分享菜单、保存并预览、客户页留言/预约回流。

### 2026-06-24：电子名片/服务工作台 P1 收口与后端部署

- 背景：
  - 用户要求 P1 一起做，并部署后端以便测试前端。
- 已完成：
  - 资料库服务模式卡片新增“复用”入口，支持电子名片/服务方案复制成新资料，且不复制访客、留言、预约和统计。
  - 资料库服务卡片“编辑”进入对应专属工作台：电子名片进名片工作台，服务方案进服务方案工作台。
  - 资料库服务空态增加“做名片 / 做方案”入口。
  - 服务卡片加入合集时直接进入案例合集编辑。
  - 案例合集空态增加“先做名片 / 先做方案”入口。
  - 服务客户看板空态文案继续服务化，覆盖咨询动态、分享来源、客户明细和方案效果。
- 已验证：
  - `node --check` 覆盖首页、资料库、合集、名片工作台、服务方案工作台、客户看板和资源跳转工具：通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_service_business_dashboard_only_counts_service_customer_data backend/tests/test_app.py::test_property_business_dashboard_only_counts_property_customer_data -q`：2 passed。
  - 本轮关键文件 `git diff --check`：通过。
- 后端部署：
  - 服务器部署前已备份：`/home/ubuntu/teamBuy/backups/backend-code-before-service-p1-20260624233925.tgz`。
  - 已同步后端代码到 `/home/ubuntu/teamBuy/backend`，未覆盖生产 `.env`、`backend/secrets/` 和运行态 mock 数据。
  - 已执行 `docker compose build backend && docker compose up -d backend`。
  - `teambuy-backend-1` 已重建并启动。
  - 内网 `http://127.0.0.1:8002/health`：200 OK。
  - 公网 `https://teambuy.lifelove.top/health`：200 OK。
  - 部署后根分区约 64% 使用率，剩余约 21G。
- 注意：
  - 后端已经线上生效；小程序前端仍需要用户在微信开发者工具重新预览/上传体验版后才能测试新前端。

### 2026-06-25：电子名片/服务方案资料库与模板一致性修复

- 背景：
  - 用户反馈电子名片和服务方案转发后，回到工作台资料库看不到对应资料。
  - 用户反馈服务方案“展示模板”和“确认详情页效果”在未编辑内容时仍出现文案不一致，其他服务模板也有类似问题。
- 已确认原因：
  - 电子名片/服务方案保存为 `user_notes`，但资料库仍主要读取 `/api/cards`，没有把无旧版 card 的服务 note 合并进列表。
  - 服务方案模板预览使用 `template.preview` 示例文案，确认页使用表单默认文案；默认表单非空导致模板 `defaults` 没有覆盖，造成“选了模板但最终页还是通用内容”。
- 已完成：
  - `backend/app/services/app_service.py`：`/api/cards` 在指定 owner 时合并 `business_card/service_offer` note-only 资料，返回 `sourceNoteId/cardType/categoryName/stats/customerSummary`，资料库可直接展示。
  - `backend/tests/test_app.py`：新增回归测试，覆盖服务方案保存后能在 `/api/cards` 资料库列表出现。
  - `miniprogram/utils/resource-navigation.js`：资料库“查看”服务资料进入客户预览页，“编辑”进入名片/服务方案专属工作台。
  - `miniprogram/pages/library/index.js`：note-only 服务资料删除时调用删除 note，不再误调删除旧版 card。
  - `miniprogram/pages/service-offer-studio/index.js`：模板切换会在用户未手动改写时应用当前模板 defaults；模板小预览与确认效果共用实际表单服务内容和统计项。
  - `miniprogram/pages/business-card-studio/index.js`：电子名片模板切换同样在未手动改写时应用模板 defaults。
- 已验证：
  - `node --check` 覆盖服务方案工作台、电子名片工作台、资料库和资源跳转工具：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：100 passed。
- 部署结果：
  - 部署前备份：`/home/ubuntu/teamBuy/backups/backend-code-before-service-library-template-202606250026.tgz`。
  - 已同步后端代码，未覆盖生产 `.env`、`backend/secrets/`、媒体目录和运行态 mock 数据。
  - 已执行 `docker compose build backend && docker compose up -d backend`。
  - 内网 `http://127.0.0.1:8002/health`：200 OK。
  - 公网 `https://teambuy.lifelove.top/health`：200 OK。
- 待验证：
  - 小程序前端仍需用户在微信开发者工具重新预览/上传体验版后验证模板一致性和资料库查看/编辑路径。

### 2026-06-25：电子名片/服务方案确认页所见即所得编辑

- 背景：
  - 用户体验后认为模板和最终效果仍有差异感，提出参考 Codex 浏览器备注修改：在预览页面上点击内容进行修改，保存后替换成自己的内容。
- 产品判断：
  - 先做“半所见即所得”：保留选模板、填资料、确认效果三步，但在确认效果页支持点击关键内容直接编辑。
  - 这样不会推翻已有保存/分享链路，又能让用户看到哪里不合适就改哪里。
- 已完成：
  - `miniprogram/pages/service-offer-studio/`：确认效果页支持点击服务名称、一句话卖点、适合人群、服务内容、流程/报价/案例、联系方式和预约说明，底部弹出编辑面板，保存后即时刷新预览。
  - `miniprogram/pages/business-card-studio/`：名片卡片预览和详情预览支持点击姓名、身份、公司/门店、一句话介绍、服务介绍、服务范围和联系方式即时编辑。
  - 两个工作台的点选编辑仅更新当前页面表单和预览；最终仍通过底部“保存并预览”写入后端，避免频繁保存和误发未保存内容。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - WXML view 标签配对检查：服务方案 258/258，电子名片 166/166。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 微信开发者工具重新预览/上传体验版后，真机检查点击编辑区域、底部编辑面板、保存后即时刷新预览、底部“保存并预览”持久化。

### 2026-06-25：电子名片第二模板浅色背景编辑角标修复

- 背景：
  - 用户测试确认点选编辑整体可用，但电子名片第二个模板背景偏浅，编辑角标沿用白色样式导致看不清。
- 已完成：
  - `miniprogram/pages/business-card-studio/index.wxss`：针对 `store_sales_card` 模板单独覆写点选编辑边框、底色和“编辑”角标颜色，浅色背景下改为绿色文字和浅绿底。
- 已验证：
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-25：服务工作台 P1 统一收口

- 背景：
  - 用户确认服务工作台主链路测试基本没问题，要求把剩余 P1 统一补齐。
- 已完成：
  - `miniprogram/pages/service-offer-studio/`：
    - 确认页支持点击封面、头像占位、案例图直接替换图片。
    - 联系与预约区在电话、微信、邮箱、网址缺失时显示“补电话/补微信/补邮箱/补网址”。
    - 底部电话/微信按钮文案支持点选编辑，并保存到结构化数据。
    - 切换模板时，如果已有未保存改动，会让用户选择“保留我的内容 / 套用模板文案”。
  - `miniprogram/pages/business-card-studio/`：
    - 卡片预览和详情预览支持点击头像、二维码直接替换图片。
    - 联系方式区缺失字段支持直接补齐。
    - 切换模板时同样提供“保留我的内容 / 套用模板文案”选择。
  - `miniprogram/pages/note-preview/`：
    - 服务方案客户页使用自定义按钮文案展示电话/微信咨询按钮。
    - 服务方案留言和预约表单占位文案改成“咨询问题、预算、期望服务方式”等服务语境。
- 已验证：
  - `node --check miniprogram/pages/service-offer-studio/index.js`：通过。
  - `node --check miniprogram/pages/business-card-studio/index.js`：通过。
  - `node --check miniprogram/pages/note-preview/index.js`：通过。
  - WXML view 标签配对检查：服务方案 263/263，电子名片 172/172，客户页 176/176。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 重新上传体验版后检查：点图替换、补联系方式、切模板选择、按钮文案保存后客户页展示。

### 2026-06-25：团购/商品工作台首页访客改订单

- 背景：
  - 用户复查团购/商品工作台首页后认为“访客”对普通商品经营价值不如订单明确，建议第四项改为订单详情入口。
- 已完成：
  - `miniprogram/utils/workspace-mode.js`：团购/商品工作台概览文案和第四个统计项从“访客”调整为“订单”。
  - `miniprogram/pages/home/index.js`：首页第四格统计改用订单/接龙总数，点击进入卖家订单列表；待处理仍进入待处理订单，今日接龙仍进入今日过滤订单。
  - `miniprogram/pages/home/index.wxml`：团购空态文案从访客动态改为订单和接龙动态。
  - `miniprogram/utils/dashboard.js` 和 `miniprogram/pages/library/`：商品卡有接龙时显示“处理接龙”，只有普通下单时显示“处理订单”；资料库团购筛选从“有访客”改为“有订单”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/orders/index.js`：通过。
  - `node --check miniprogram/utils/dashboard.js`：通过。
  - `node --check miniprogram/utils/workspace-mode.js`：通过。
  - WXML view 标签配对：首页 72/72，资料库 104/104。
  - 本轮关键文件 `git diff --check`：通过。
- 待用户验证：
  - 重新上传体验版后检查团购/商品首页第四格显示“订单”，点击进入全部订单；商品卡普通下单显示“处理订单”，接龙商品显示“处理接龙”。

### 2026-06-25：日常资料台反馈命名、真实待整理与普通资料整理

- 背景：
  - 用户确认日常资料台不默认走 SCRM/客户看板，要求继续改首页和底部 Tab 命名，并把“待整理任务”做成真实数据。
- 已完成：
  - 底部 Tab `pages/visits` 从“客户看板”改为“反馈”，反馈页标题同步改为“反馈”。
  - 首页反馈面板按模式展示：日常资料台为“分享反馈 / 看反馈”，团购为“买家动态 / 去接龙看板”，服务为“咨询动态 / 去咨询看板”，房源仍保留客户看板语义。
  - 日常资料台首页“待整理任务”改为真实任务卡：
    - 待认领：来自 `/api/imports/pending`。
    - 待整理：来自资料卡 `typeSuggestions`、图片待处理、待整理分类或草稿状态。
    - 待识别图片：来自 `image_ocr / ocr / image_capture` 且 OCR 未成功的资料。
    - 未完成资料包：来自 `/api/showcases` 中非 published/archived/deleted 的资料包。
  - `pages/notes` 支持从首页任务卡带筛选进入：`sourceType=ocr`、`migrationPending=1`、`plain=1`、`systemCategory`。
  - 普通笔记详情增加“一键整理”和“加入资料包”入口；“添加能力”继续只作为后续留言、咨询、接龙等插件能力入口。
  - 资料包编辑页支持 `noteId` 直达预选，普通资料场景不再默认使用房源文案和租金完整度校验。
  - 后端普通资料 `organize` 补充轻量 `organizeResult`，返回“资料包 / 分享摘要 / 标签归类”生成选项。
- 已验证：
  - `node --check`：home、notes、visits、note-edit、showcase-edit 均通过。
  - `miniprogram/app.json` JSON 解析通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：100 passed。
  - `git diff --check`：通过。
- 未做：
  - 本轮按用户要求未部署、未上传小程序体验版。

### 2026-06-25：资料库与反馈页按当前工作台收口

- 背景：
  - 用户 3:02 左右点击资料库后仍看到其他工作台资料；反馈页虽然 Tab 改为“反馈”，但页面内仍显示四个工作台切换，非中介用户会看到房源、服务等突兀入口。
- 已完成：
  - `miniprogram/pages/library/index.js`：日常资料台进入资料库时自动应用 `notes_workspace` 范围，只看非房源、非团购、非名片/服务方案的日常资料。
  - `miniprogram/pages/visits/index.js/.wxml`：反馈页按当前工作台过滤资料；日常、房源、团购、服务各自只看自己的反馈数据。
  - 反馈页移除页面内四工作台切换 Tab，避免日常资料用户直接看到房源/团购/服务入口。
  - 日常反馈页统计图标和筛选项改为中性表达；“进入/分享记录”不再跳业务看板，改去资料包。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/visits/index.js`：通过。
  - `git diff --check`：通过。
- 追加自测补强：
  - 新增短普通笔记自动测试，覆盖 `rawText="a da g g"` 保存后进入 `/api/cards`，并以 `text_note / 普通笔记 / note_card_{note.id}` 暴露给资料库。
  - 追加小程序资料库日常范围过滤脚本检查：普通笔记保留，房源和服务资料排除。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：101 passed。
- 待用户验证：
  - 重新预览后在日常资料台点击资料库，确认不再混入房源、团购、服务资料。
  - 进入“反馈”页，确认不再看到四个工作台切换，且列表内容只属于当前工作台。

### 2026-06-25：生产热修普通笔记进入资料库

- 背景：
  - 用户 3:29 新建普通笔记后，生产小程序资料库仍看不到。
  - 排查确认小程序连接 `https://teambuy.lifelove.top` 生产后端；本地测试通过但生产后端仍是旧 `_service_note_card_rows` 逻辑。
- 生产只读排查：
  - 线上数据库存在 `note_f03a120b21`，标题“改革规划”，`cardType=text_note`，`source_card_id` 为空。
  - 部署前线上 `/api/cards?ownerUserId=user_25ec00a0f0` 返回 14 条，未包含 `note_f03a120b21`。
- 已部署：
  - 服务器路径 `/home/ubuntu/teamBuy/backend/app/services/app_service.py` 做最小补丁。
  - 备份文件：`backend/app/services/app_service.py.bak.20260625033613`。
  - 将 `list_cards` 从只合成服务/名片 note-only，改为合成所有有效 note-only 资料，并按类型映射 `普通笔记/链接/图片/房源/团购/名片/服务`。
  - 执行 `docker compose up -d --build backend` 重建并重启后端。
- 已验证：
  - `https://teambuy.lifelove.top/health`：200 OK。
  - 线上 `/api/cards?ownerUserId=user_25ec00a0f0` 返回 27 条。
  - `note_f03a120b21` 已返回为 `note_card_note_f03a120b21`，`cardType=text_note`，`categoryName=普通笔记`。
  - 前端日常资料库过滤模拟：27 条中日常资料 7 条，`note_f03a120b21` 保留。

### 2026-06-25：资料库补充专题筛选

- 背景：
  - 用户确认 4 个工作台都有“专题”，但资料库目前没有可见的专题检索入口；专题与资料包心智需要区分。
- 已完成：
  - `miniprogram/pages/library/index.js`：加载资料库时同步读取用户专题，并按当前工作台范围内的资料统计专题数量。
  - 资料库筛选逻辑新增 `activeTopicId`，支持分类、标签、关键词和专题组合筛选。
  - 关键词搜索同时纳入资料所属专题名。
  - `miniprogram/pages/library/index.wxml/.wxss`：在分类和标签之间新增“专题筛选”胶囊，只有当前范围内存在专题资料时展示。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `git diff --check -- miniprogram/pages/library/index.js miniprogram/pages/library/index.wxml miniprogram/pages/library/index.wxss`：通过。
- 未做：
  - 本轮未部署、未上传小程序体验版。

### 2026-06-25：资料工作台 P0 收口补强

- 背景：
  - 用户确认“专题=内部整理检索，资料包=外部分享集合”后，要求把剩余 P0 全部开发。
- 已完成：
  - 资料库专题筛选命中后新增“建资料包”入口，并在页面文案里说明专题用于内部整理和检索、资料包用于分享。
  - `pages/showcase-edit` 支持 `topicId/topicName` 参数：从专题建资料包时只读取该专题下的资料，并默认全选加入。
  - 资料包编辑页显示“来自专题”提示条，明确专题和资料包心智区别。
  - 普通资料在资料库卡片点击“合集”时，直接进入资料包编辑页并预选当前资料；不再只是跳到资料包列表。
  - 普通资料包空封面提示改为“默认取第一条资料图”，避免日常资料包继续出现房源语境。
- 已验证：
  - `node --check miniprogram/pages/library/index.js`：通过。
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - `miniprogram/pages/library/index.wxml` view 标签配对：110/110。
  - `miniprogram/pages/showcase-edit/index.wxml` view 标签配对：86/86。
  - 本轮关键文件 `git diff --check`：通过。
- 未做：
  - 未部署后端；本轮只改小程序前端。
  - 未上传小程序体验版。

### 2026-06-25：前台命名统一为“专题 / 合集”

- 背景：
  - 用户明确不要创造过多名词，要求内部统一叫“专题”，外部统一叫“合集”；四个工作台分别叫日常合集、房源合集、商品合集、案例合集。
- 已完成：
  - `pages/showcase-edit`：普通资料外部集合统一改为“日常合集”，服务模式改为“案例合集”，团购模式改为“商品合集”。
  - `pages/showcases`：入口卡、空态、删除确认、分享兜底统一去掉“资料包 / 团购合集”旧词。
  - `pages/library`：专题筛选后的外部生成入口改为“建合集”，解释为“专题内部整理，合集对外分享”。
  - `pages/note-edit`：普通资料详情动作改为“加入合集”，标签专题说明改成“专题和合集归类”。
  - 首页、反馈、工作台配置、业务看板中日常模式旧“资料包”文案改为“日常合集”。
- 已验证：
  - 小程序前端 `rg "资料包|团购合集|服务资料包|普通资料包|建资料包|加入资料包|资料包效果|专辑"`：无结果。
  - `node --check`：showcase-edit、showcases、library、home、workspace-mode 通过。
  - WXML view 标签配对：资料库 110/110；合集编辑 86/86；合集列表 47/47；首页 78/78；业务看板 285/285。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-25：资料工作台 P1 统一收口

- 背景：
  - 用户要求把剩余 P1 一次收口，并统一测试。
- 已完成：
  - 专题页增强：
    - 增加“专题内部整理 / 合集对外分享”的心智说明。
    - 每个专题支持直接“建合集”，进入日常合集编辑并自动带入该专题资料。
    - 支持删除专题；删除只移除资料上的专题关联，不删除资料。
  - 日常合集编辑增强：
    - 日常/服务场景生成方式不再沿用房源推荐包、租金、户型等文案。
    - 日常合集的条件生成先作为“按专题/标签生成”后续能力，不误展示房源筛选面板。
  - 普通资料插件入口：
    - “添加能力”改为插件占位面板，展示留言、咨询、接龙为后续插件能力。
    - 普通笔记不再因为点“添加能力”直接进入运营配置；仍可选择先补摘要、标签和专题。
  - 标签设置页文案改为通用资料语境，不再只举房源标签例子。
  - 后端普通资料一键整理选项从“资料包”改为“日常合集”，并补专题删除接口和测试。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：101 passed。
  - `python3 -m compileall -q backend/app`：通过。
  - `node --check`：topics、note-edit、showcase-edit、showcases、api、tag-manage、library、home、workspace-mode 通过。
  - 小程序 JSON 递归解析：通过。
  - WXML view 标签配对：topics 19/19，note-edit 313/313，showcase-edit 86/86，tag-manage 24/24。
  - 前端/后端旧词扫描：`资料包|团购合集|服务资料包|普通资料包|建资料包|加入资料包|资料包效果|专辑` 无结果。
  - 本轮关键文件 `git diff --check`：通过。
- 后端部署：
  - 2026-06-25 04:36 已备份生产后端文件到 `/home/ubuntu/teamBuy/backups/backend-topic-delete-20260625-043627`。
  - 已同步 `backend/app/services/app_service.py` 和 `backend/app/api/routes_notes.py`。
  - 标准 `docker compose up -d --build backend` 在服务器上长时间无输出；随后重启 Docker 恢复服务，并采用容器热补丁复制两处代码后重启 `teambuy-backend-1`。
  - 公网 `https://teambuy.lifelove.top/health` 返回 200。
  - 线上创建并删除探针专题通过：`topic_9ddae95120`、`topic_20314ec7e3` 均已删除。
- 小程序上传：
  - 已检查到本机微信开发者工具 CLI，但用户确认小程序体验版自行上传，本轮不再代传。
- 待真机回归：
  - 新增普通笔记后资料库可见。
  - 资料库按专题筛选。
  - 专题筛选后建日常合集。
  - 普通资料卡点“合集”进入并预选当前资料。
  - 日常合集发布/分享。
  - 反馈页数据按当前工作台正常展示。

### 2026-06-25：专题管理入口与四工作台入口出口收口

- 背景：
  - 用户反馈“没看到新增删减专题功能，只有资料详情下面有删减”，确认问题是专题管理页入口藏在“我的”里，资料库主路径不可见。
  - 用户要求补完专题管理入口，并检查四个工作台每一项的入口和出口。
- 已完成：
  - 资料库“更多工具”新增“专题管理”入口，直接进入专题页，可新建、删除专题和从专题建合集。
  - 资料库出现专题筛选时，标题右侧新增“管理专题”，避免用户只能筛选但找不到管理入口。
  - 资料库“新增资料”按当前工作台进入正确新建路径：日常资料、房源、商品、服务分别进入对应创建入口。
  - 资料库卡片“更多”菜单拆分普通资料和房源资料，不再让日常资料显示“编辑房源”。
  - 首页最近成果和反馈数据改为按当前工作台范围计算，避免四个工作台看到相同内容。
  - 合集页按当前工作台真实过滤合集：日常合集、房源合集、商品合集、案例合集不再混在同一列表。
  - 合集编辑页把“日常资料”作为真实范围，日常合集候选不再使用“全部资料”把房源、商品和服务带进去。
  - 团购/商品工作台“商品合集”快捷入口改为进入合集列表，与其他工作台一致。
- 四工作台入口出口检查结论：
  - 日常资料台：首页待整理任务 -> 导入/笔记/图片/日常合集；资料库 -> 日常资料范围；合集 -> 日常合集；反馈 -> 分享效果。
  - 房源工作台：首页统计 -> 房源资料/房源效果/访客/待跟进；快捷入口 -> 新建房源/记需求/房源合集/名片；资料库和合集均按房源范围。
  - 团购/商品工作台：首页统计 -> 商品资料/待处理订单/今日接龙/订单；快捷入口 -> 新建商品/记素材/商品合集/处理接龙；资料库和合集均按商品范围。
  - 服务工作台：首页统计 -> 名片和服务方案/打开/访客/咨询；快捷入口 -> 做名片/做方案/写笔记/案例合集；资料库和合集均按服务范围。
- 已验证：
  - `node --check`：library、home、showcases、showcase-edit、visits、workspace-mode 通过。
  - 小程序 JSON 递归解析：通过。
  - 前端/后端旧词扫描：`资料包|团购合集|服务资料包|普通资料包|建资料包|加入资料包|资料包效果|专辑` 无结果。
  - 本轮关键文件 `git diff --check`：通过。
- 未做：
  - 本轮未部署后端；改动均为小程序前端。
  - 未上传小程序体验版，需用户在微信开发者工具上传后真机查看。

### 2026-06-25：专题页新建栏按钮溢出修复

- 背景：
  - 用户真机反馈专题页“新建”按钮被横向撑出屏幕。
- 根因：
  - `input + button` 横向布局只写了 `grid-template-columns: 1fr 140rpx`，没有给可伸缩输入框 `min-width: 0`，也没有固定并重置原生 `button` 默认尺寸。
- 已完成：
  - `miniprogram/pages/topics/index.wxss`：新建栏改为 `minmax(0, 1fr) 140rpx`。
  - 输入框补 `min-width: 0`。
  - 新建按钮补固定宽度、`margin/padding/line-height` 重置、flex 居中、`white-space: nowrap` 和 `button::after` 边框清除。
  - `docs/project-memory.md` 记录“小程序横向输入框 + 按钮布局硬规则”。
  - `docs/pitfalls.md` 记录本次坑点和同类区域检查清单。
- 已验证：
  - `node --check miniprogram/pages/topics/index.js`：通过。
  - `miniprogram/pages/topics/index.wxml` 标签计数：view 19/19，button 3/3，text 4/4。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-25：房源合集展示一列/双列与微信助手入口修正

- 背景：
  - 用户真机反馈展示页仍有按钮变形，并希望所有模板和展示页都能选择一列/双列，默认一列。
  - 用户点击微信助手时只看到复制，期望能自动进入添加/联系企业微信客服。
- 已完成：
  - `pages/showcase-edit` 新增“房源排列：一列 / 双列”选择，默认一列，并保存到 `displayConfig.layoutMode`。
  - `pages/showcase-view` 四类模板都读取 `layoutMode` 渲染，一列为默认，双列为紧凑浏览模式。
  - `miniprogram/app.wxss` 增加原生 `button` 全局 reset 和常用按钮/标签居中基线，减少真机文字偏移和按钮撑宽。
  - 新增后端 `/api/wecom/customer-service-config`，复用现有整理助手企业微信客服 `WECOM_CORP_ID / WECOM_OPEN_KFID`，生成小程序打开客服所需参数。
  - 生成同款页优先请求后端客服配置并调用 `wx.openCustomerServiceChat`；后端未部署、参数缺失或调用失败时复制整理指令兜底。
- 注意：
  - `miniprogram/config/customer-service.js` 只保留离线兜底，不作为主配置来源，也不放密钥。
- 待验证：
  - 重新上传体验版后，真机检查精选橱窗、清单对比、朋友圈长页、名片型展示的一列/双列切换和按钮居中。

### 2026-06-25：企业微信助手配置与自有小程序卡后端识别

- 背景：
  - 用户更正“企业微信客服”就是当前归纳整理助手，不是另一个客服号。
  - 今天讨论的后端点包括：复用现有企业微信助手配置、企业微信收到我们自己的房源卡/合集时不能只识别标题、生成同款不能泄露原发布者私密上游联系人。
- 已完成：
  - 后端新增 `GET /api/wecom/customer-service-config`，由现有 `WECOM_CORP_ID / WECOM_OPEN_KFID` 生成小程序 `wx.openCustomerServiceChat` 所需 `corpId/extInfoUrl`。
  - 企业微信 `weapp` 解析补充自有小程序 `noteId/showcaseId` 识别，兼容 `id/sourceNoteId/showcaseId` 等 query 参数。
  - 企业微信同步和会话归档进入 `content-to-note` 前，会对自有小程序房源卡/合集回查公开结构并写入 `structuredData.internalMiniapp`。
  - 自有房源卡公开结构会过滤 `contact/phone/wechat/landlord/upstream/channel/rawText` 等可能夹带私密联系人或上游来源的字段。
  - 展示页后端 `displayConfig` 保留 `layoutMode=list/grid`，避免前端发布的一列/双列设置被后端归一化丢弃。
  - 小程序生成同款页优先请求后端客服配置，后端未部署或调用失败时继续复制整理指令兜底。
- 已验证：
  - `python3 -m compileall -q backend/app`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：104 passed。
  - 关键文件 `git diff --check`：通过。
- 生产部署：
  - 2026-06-25 已备份生产后端文件到 `/home/ubuntu/teamBuy/backups/backend-property-agent-20260625-073636`。
  - 已同步并热补丁到 `teambuy-backend-1`，随后重启后端容器。
  - 生产 `/health` 返回 200。
  - 生产 `/api/wecom/customer-service-config` 返回 `configured=true`，`corpId=ww9c4d57d8c6ab4d48`，`openKfid=kfc5d3f0baa1f359b6d`。
  - 容器内 `python -m compileall -q /app/app` 通过。
- 待真机验证：
  - 小程序重新上传体验版后真机测试“打开微信助手”直达归纳整理助手。

### 2026-06-25：生成同款后端克隆与媒体资产 hash 去重底座

- 背景：
  - 用户确认当前还缺两个基础能力：完整后端克隆接口还没有把 A 的公开房源/合集一键生成 B 名下正式房源卡/合集；媒体资产 hash 去重仍停留在文档方向，没有落库实现。
- 已完成：
  - 新增 `MediaAsset` / `MediaAssetRef` 模型和 PostgreSQL/JSON 仓储能力。
  - 新增 `media_assets`、`media_asset_refs` 表，按 `media_type + original_sha256` 和 `media_type + storage_sha256` 做索引与唯一约束。
  - `process_and_store_media` 改为保存前计算原始 hash，图片继续转 WebP、视频继续转 MP4，处理后再计算存储 hash；命中已有资产时复用 URL，只补引用。
  - OCR 图片上传路径保留本地落文件行为，同时接入同一套 hash 去重和资产引用。
  - 新增 `POST /api/notes/property-same/clone`：
    - `sourceType=note`：复制公开房源字段和媒体引用，生成 B 名下新 `UserNote`。
    - `sourceType=showcase`：复制公开合集中的每条房源为 B 名下新房源卡，再生成 B 名下新 `ShowcasePage`。
    - B 的电话/微信会写入公开联系方式；上游联系人写入 `visibilityConfig.privateData.upstreamContact`，默认取 A 的公开联系方式或身份，且不继承 A 的私有 `privateData`。
  - 公开字段过滤增强为大小写无关，避免 `contactPhone/contactWechat` 这类字段漏出。
- 已验证：
  - 本地后端全量测试：`../.venv312/bin/pytest tests -q`，144 passed。
  - 生产 `/health` 返回 200。
  - 生产新增接口无副作用验证：
    - 缺用户返回 `用户不存在`。
    - 已存在用户 + 缺源返回 `公开房源卡不存在`，确认路由和业务逻辑已生效。
  - 生产 PostgreSQL 已存在 `media_assets`、`media_asset_refs` 两张表。
- 生产部署：
  - 备份目录：`/home/ubuntu/teamBuy/backups/backend-clone-media-20260625-075259`。
  - 已同步宿主机文件，并热补丁到 `teambuy-backend-1` 容器内，随后重启后端容器。
- 仍需后续：
  - 小程序“生成同款”页需要从复制给助手升级为直接调用 `POST /api/notes/property-same/clone`。（2026-06-25 已完成前端接入，见下一条）
  - 历史已上传媒体没有原始 hash，需另做离线回填任务才可纳入资产去重索引。

### 2026-06-25：生成同款小程序前端接入后端克隆接口

- 背景：
  - 后端克隆接口已部署，用户要求 `pages/property-same` 优先直接生成 B 的正式房源卡/合集，企业微信助手只作为失败兜底。
- 已完成：
  - `miniprogram/services/api.js` 新增 `clonePropertySame`，调用 `POST /api/notes/property-same/clone`。
  - `pages/property-same` 主按钮改为“生成同款”：
    - 有 `sourceType=note/showcase` 和 `sourceId` 时，优先调用后端克隆接口。
    - 成功生成房源卡后跳转 `/pages/note-edit/index?id=新noteId`。
    - 成功生成房源合集后跳转 `/pages/showcase-edit/index?id=新showcaseId&mode=property`。
    - 缺少来源或接口失败时，自动复制整理指令并打开企业微信助手兜底。
  - 页面保留“打开助手”次按钮，方便用户主动走半自动整理。
- 已验证：
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - `node --check miniprogram/services/api.js`：通过。
  - 小程序 JSON 递归解析：通过。
  - 关键文件 `git diff --check`：通过。
- 待真机：
  - 上传体验版后，从房源卡/房源合集公开页点击“生成同款”，确认成功后分别进入新房源卡编辑页/新合集编辑页。

### 2026-06-26：生成同款登录页与一键生成落点优化

- 背景：
  - 真机测试显示“生成同款”能直接生成，但首次未登录会进入登录页；旧登录页像测试表单，键盘容易顶起页面，按钮视觉也不稳定。
  - 生成成功后进入编辑/操作页，会让“一键生成”显得还需要二次点选。
- 已完成：
  - `pages/property-same` 未登录时带 `returnUrl` 跳登录页，登录成功后自动回到原生成同款页面。
  - 回到生成同款页后带 `autoGenerate=1`，自动继续调用克隆接口，减少首次用户二次操作。
  - 生成成功后的落点改为客户预览页：
    - 房源卡 -> `/pages/note-preview/index?id=新noteId`
    - 房源合集 -> `/pages/showcase-view/index?id=新showcaseId`
  - 房源合集克隆前端传 `publishShowcase=true`，确保生成后能直接打开客户可见合集。
  - 登录页重做为房源场景入口页，去掉昵称输入表单，主按钮为“微信一键登录”，保留本地测试登录仅在本地后端显示。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - 小程序 JSON 递归解析：通过。

### 2026-06-26：登录页文案图片与 iPad 底部按钮适配

- 背景：
  - 真机反馈登录页 `openid 隔离` 过于技术化，应改成用户能理解的“微信官方隔离”。
  - 登录页预览卡需要使用真实房源图。
  - iPad 上房源详情/合集详情底部生成同款、联系按钮仍有变形或横向裁切。
  - 讨论是否登录时强制获取头像昵称。
  - 登录说明里“不展示给其他中介”容易放大中介对资料外泄的担心，需要改成更短、更正向的归属说明。
- 已完成：
  - 登录页预览卡文案改为“微信官方隔离”。
  - 登录区文案改为“登录后保存到你的账号 / 用于生成同款、查看线索，下次打开还能继续管理。”，避免让用户误解平台会讨论或展示他的房源给同行。
  - 使用用户提供的房源图压缩为 `miniprogram/static/workspace/login-room.jpg`，预览卡左图改为真实房源图。
  - `note-preview` 生成同款卡片改为最大宽度居中，窄屏自动上下布局。
  - `showcase-view` 底部联系按钮、固定分享按钮、生成同款卡片增加最大宽度居中和自适应列宽，减少 iPad 横屏/分栏下裁切。
  - 登录策略暂定：首登继续一键登录，不在第一步强制头像昵称；头像昵称放到后续资料/名片/个人页补全，避免看房客户和中介首次转化被打断。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `node --check miniprogram/pages/property-same/index.js`：通过。
  - 小程序 JSON 递归解析：通过。

### 2026-06-26：合集模板切换发布态与朋友圈长页适配

- 背景：
  - 真机反馈：编辑页切换模板后，再转发给客户仍像是上一个模板。
  - iPad 上“朋友圈长页”模板仍出现内容横向拉伸、底部按钮漂移/裁切。
- 已完成：
  - `showcase-edit` 新增 `unpublishedChanges` 状态：已发布合集只要修改模板、排列、标题、封面、联系方式、筛选条件或已选资料，就标记为“新版未发布”。
  - 已发布但有新版未发布时，顶部和底部不再直接展示分享按钮，改为“发布新版”，避免客户继续打开旧模板。
  - 分享兜底增加校验：如果存在新版未发布，会提示“先发布新版再分享”。
  - `showcase-view` 四个模板主体统一最大宽度居中，减少 iPad 宽屏/分栏下把移动端模板拉满屏。
  - “朋友圈长页”模板的首屏、故事卡、列表行、服务条和标签改为可收缩网格列，避免长标题和图片列把布局撑坏。
- 已验证：
  - `node --check miniprogram/pages/showcase-edit/index.js`：通过。
  - `showcase-edit/showcase-view` JSON 解析：通过。
  - `showcase-edit/showcase-view` WXML 标签配对：通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-26：品牌名片模板、微信优先联系与合集排序修复

- 背景：
  - 真机反馈第四个“品牌名片”模板仍在 iPad 上变形。
  - 用户再次确认房源场景微信联系比电话联系更重要，四个模板都应体现微信优先。
  - 重新保存并发布新版后，用户预期该合集应回到列表靠前位置。
- 已完成：
  - `showcase-view` 联系按钮顺序改为微信优先：有微信时先显示“微信联系”，电话咨询放后；统计位只要有微信就显示“微信咨询”。
  - 品牌名片模板重排：
    - 主体继续限制 720rpx 居中。
    - 头部不再负 margin 拉满。
    - 列表卡片固定图片列和内容列，长标题最多两行，摘要单行省略。
    - 标签改为两列，避免四标签在 iPad 分栏下挤爆。
    - 无封面时补兜底封面，避免网格错位。
  - `showcase-edit` 发布新版后清理合集列表本地缓存。
  - `showcases` 列表读取缓存和接口数据时都按 `updatedAt/createdAt` 倒序，确保刚发布新版的合集靠前。
- 已验证：
  - `node --check`：`showcase-edit`、`showcase-view`、`showcases` 通过。
  - `showcase-edit/showcase-view/showcases` JSON 解析和 WXML 标签配对通过。
  - 本轮关键文件 `git diff --check`：通过。

### 2026-06-26：品牌名片房源卡结构性修复

- 背景：
  - 真机继续反馈第四模板按钮仍被截断，房源缩略图和卡片内容明显变形，整体不具备“想用下去”的视觉吸引力。
  - 复查确认品牌名片模板中的房源卡缺少内容容器，图片、标题、摘要、标签、价格作为同级 grid 子项自动排布，导致摘要/标签/价格窜到图片列或下一行。
- 已完成：
  - `showcase-view` 品牌名片房源卡 WXML 增加 `brand-case-body` 内容容器，把标题、摘要、标签和价格包成右侧完整内容区。
  - 品牌名片列表卡固定为 `188rpx + 内容区` 两列，封面图和无图兜底都固定 `188rpx` 正方形，避免高度被内容撑变。
  - 标题两行截断、摘要单行截断、标签两列居中、价格固定在内容区底部。
  - 固定分享按钮 `.sticky-share` 改为 flex 居中，不再依赖 `line-height` 硬撑。
  - 房源模板固定分享按钮文案从长句缩短为“发给客户”，避免 iPad 分栏下文字被裁切。
- 已验证：
  - `node --check miniprogram/pages/showcase-view/index.js`：通过。
  - `showcase-view` JSON 解析和 WXML 标签配对通过。
  - `showcase-view` 关键文件 `git diff --check`：通过。

### 2026-06-26：登录页房源卡合并小地图导航卖点

- 背景：
  - 用户希望在生成同款登录页增加“客户可直接导航带看”的营销点，但不要额外堆一张大地图卡。
  - 讨论后确认：利用房源预览卡右侧空白位放小地图更紧凑。
- 已完成：
  - `pages/login` 预览房源卡改为三列：房源图 / 房源信息 / 小地图导航。
  - 删除“图片已复用”文案，只保留“近地铁 / 可带看”。
  - 小地图用 WXSS 绘制道路、定位点和“导航”胶囊，不新增图片资源。
  - 原三步能力点改为四个短标签：房源卡、房源合集、查看客户线索、位置导航。
  - 更新效果图 `docs/png/login-map-navigation-mockup.svg` 为合并版本。
- 已验证：
  - `node --check miniprogram/pages/login/index.js`：通过。
  - `login` JSON 解析和 WXML 标签配对通过。
  - 登录页和效果图 `git diff --check`：通过。

### 2026-06-26：房东长文本批量拆房源与上游信息隔离

- 背景：
  - 用户提供真实房东群发文案：一条消息可能包含多套房源，且混有中介费、密码锁、看房电话、微信、朋友圈照片视频、禁宠等信息。
  - 确认“禁宠”属于客户可见公开标签；上游电话、微信、中介费和带看协作信息只能给中介自己看。
- 已完成：
  - 后端新增 `POST /api/notes/property-batch/parse` 和 `POST /api/notes/property-batch/create`。
  - 批量解析能把同一条房东长文本拆成多套 `property_listing` 候选，并支持勾选生成。
  - 公开标签写入房源结构和 `tags`，包含禁宠、可办居住证、可落户、可办停车位、可开发票、燃气、卫生间带窗、干湿分离、已空等。
  - 上游电话、微信、中介费、密码锁、红包、朋友圈有照片视频和带看限制写入 `visibilityConfig.privateData/privateTags`，不进入客户可见联系方式。
  - 小程序 `resource-create` 粘贴多套房源时先展示“房源批量识别”确认卡，用户可勾选生成多张房源卡，也可按普通资料保存。
- 已验证：
  - `pytest backend/tests/test_app.py -k property_batch_parse_and_create_keeps_upstream_private`：通过。
  - `pytest backend/tests/test_app.py -k manual_note_draft_creates_property_from_pasted_text`：通过。
  - 后端相关文件 `py_compile`：通过。
  - `node --check miniprogram/services/api.js`、`node --check miniprogram/pages/resource-create/index.js`：通过。

### 2026-06-26：访客身份分层与疑似中介隔离

- 背景：
  - 用户确认：中介生成同款后也会进入访客/反馈链路，但不能混进“租客客户线索”，否则发布者会误判。
  - 讨论后决定不丢数据，而是给疑似中介/上游打身份标签，并在反馈页分组展示。
- 已完成：
  - 后端在 `clone_property_same` 成功后，为原发布者写入一条 `生成同款` 客户动作，身份标记为 `peer_agent / 疑似中介`。
  - 该动作只进入同行传播和访客看板，不投射成 `LeadReminder`，不会增加“待联系客户”。
  - 看板 `visitorProfiles/latestActions` 增加 `visitorIdentityType/visitorIdentityLabel/visitorIdentityGroup`。
  - 小程序 `business-dashboard` 最近访客页新增 `客户 / 同行 / 上游 / 全部` 分组筛选；默认展示客户线索。
  - 列表、动作流水和访客详情均显示身份标签，客户绿色、同行橙色、上游蓝紫色。
- 已验证：
  - `pytest backend/tests/test_app.py -k property_same_clone_note_creates_b_owned_note_with_replaced_contact`：通过，确认生成同款记录为疑似中介且不增加待联系线索。
  - `py_compile backend/app/services/app_service.py`：通过。
  - `node --check miniprogram/pages/business-dashboard/index.js`：通过。

### 2026-06-26：首页房源助手改用企业微信「联系我」插件

- 背景：
  - 真机确认 `wx.openCustomerServiceChat` 打开的是微信客服会话，不能像企业微信成员好友一样置顶。
  - 用户需要的是添加企业微信成员后的长期会话入口，用于置顶并持续发送群里房源。
- 已完成：
  - 小程序 `app.json` 接入企业微信「联系我」插件 `wx104a1a20c3f81ec2`，版本按官方文档使用 `1.4.7`。
  - 首页声明 `cell: plugin://contactPlugin/cell` 组件，并使用用户在企业微信后台生成的配置 ID：`3bf7435f594f0d6ca83a9a185ea201e5`。
  - 首页 banner 内的房源助手入口从“打开微信客服”改为官方「联系我」按钮组件，使用 `styleType=2 / blockStyle=button`。
  - 常用入口里的“添加房源助手”不再调用旧客服接口，改为提示用户点击顶部联系我入口。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - 小程序 `app.json` 和 `pages/home/index.json` JSON 解析通过。
- 待真机：
  - 小程序后台需先在 `设置 -> 第三方服务 -> 添加插件` 添加插件 ID `wx104a1a20c3f81ec2`。
  - 上传体验版后确认点击首页「联系我」能进入企业微信成员添加流程，而不是微信客服会话。

### 2026-06-26：首页房源助手插件按钮排版修复

- 背景：
  - 真机反馈 banner 内企业微信「联系我」按钮被裁切，只露出半截“系”，常用入口按钮也被上下线压住。
- 已完成：
  - banner 内“添加房源助手”卡片由三列改为上下结构：上方图标和文案，下方独立放官方插件按钮。
  - 常用入口里的插件按钮区域增加最小高度并居中，避免按钮视觉被裁切。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - 小程序 `app.json` 和 `pages/home/index.json` JSON 解析通过。
  - 首页相关文件 `git diff --check`：通过。

### 2026-06-26：企业微信成员好友自动回消息真实测试

- 背景：
  - 用户在 20:40 左右用个人微信向企业微信成员发消息，希望验证后端能否自动回文字、图片和小程序卡片。
- 已确认：
  - 线上会话存档表已收到该消息，对应外部联系人 `external_userid` 已识别。
  - 使用现有微信客服 `kf/send_msg` 尝试给该外部联系人发文本，企业微信返回 `48002 api forbidden`，说明该成员好友会话不能直接复用微信客服发送接口。
  - 使用客户联系 `externalcontact/add_msg_template` 尝试创建单人文本发送任务，企业微信返回 `60020 not allow to access from your ip`，调用服务器 IP 为 `81.70.84.35`。
- 结论：
  - 目前不是“文字/图片/小程序一定不能发”，而是客户联系接口需要先把生产服务器公网 IP 加到对应企业微信应用的“企业可信 IP”。
  - 在可信 IP 配置完成前，图片和小程序卡片测试会被同一 IP 白名单拦截，暂不具备有效测试条件。
- 下一步：
  - 用户在企业微信后台对应自建应用/客户联系能力处添加可信 IP：`81.70.84.35`。
  - 配置生效后重测 `externalcontact/add_msg_template` 的文本、图片、小程序卡片三种消息。

### 2026-06-26：客户联系文本与图片触达重测通过

- 背景：
  - 用户在企业微信后台补齐客户联系 API 可调用应用后，要求继续验证外部联系人文本、图片和小程序卡片。
- 已完成：
  - `externalcontact/get` 成功返回外部联系人资料，确认当前 access token 具备客户联系读取权限。
  - `externalcontact/add_msg_template` 文本发送任务创建成功，返回 `errcode=0` 和 `msgid`。
  - `media/uploadimg` 成功返回图片 URL，并用该 URL 创建图片发送任务成功。
  - 小程序卡片仍未通过：临时素材 `media/upload` 的 `media_id` 被判 `40007 invalid media_id`；无封面卡片返回 `41006 media_id missing`；永久素材接口 `material/add_material` 当前返回 `48002 api forbidden`。
- 结论：
  - 企业微信客户联系链路已可创建文本和图片触达任务。
  - 小程序卡片还需补齐可用于 `pic_media_id` 的素材权限，或寻找客户联系小程序卡片要求的正确封面素材上传方式。

### 2026-06-26：external_userid 到小程序用户绑定链路确认

- 背景：
  - 用户要求先建立 `external_userid -> openid/userId` 的绑定，确保房源助手收到的后续消息能自动进入对应小程序账号。
- 已确认：
  - 后端已有 `wecom_identity_bindings` 表，唯一键为 `source_type + external_user_id`。
  - `claim_import` 认领导入时会写入 `sourceType=wecom_external_user`、`externalUserId`、`ownerUserId`、`ownerOpenid`。
  - 后续企业微信/会话存档消息处理会先按 `external_userid` 查绑定；命中后直接把生成的资料归属到该用户，不再进入待认领。
- 本轮已完成：
  - 小程序待认领导入页文案改为“第一次认领会绑定房源助手，后续发来的资料自动进你的账号”。
  - 按钮从“认领并编辑”改为“认领并绑定”。
  - 未登录点击认领时先跳登录页。
  - 认领成功后提示“已绑定房源助手”，再进入编辑页。
  - 认领页按钮改为 flex 居中，避免真机按钮文字偏移。
  - 后端测试补充断言：认领导入返回的 `identityBinding.ownerOpenid` 必须等于当前登录用户 openid。
- 已验证：
  - `node --check miniprogram/pages/imports/index.js`：通过。
  - `python3 -m py_compile backend/app/services/app_service.py backend/tests/test_app.py`：通过。
- 未完成：
  - 本机当前 Python 环境缺少 `pytest`，三条目标后端测试未能运行；需在具备后端依赖的环境执行。

### 2026-06-27：首页收口为企业微信成员好友主入口

- 背景：
  - 用户明确暂时不考虑“企业微信给用户发小程序”，也不要继续在首页混入微信客服入口。
  - 当前主链路收口为：中介添加企业微信房源助手，置顶后把群里的房源/微信笔记转发给它；后端通过会话存档收消息并整理，小程序内查看新导入资料和房源合集。
- 已完成：
  - 首页 banner 删除“发房源给助手 / 打开微信客服 / 整理完回小程序”的口径。
  - 首页 banner 只保留企业微信「联系我」插件作为唯一主入口，文案改为“添加房源助手 / 加企业微信后置顶，把群里房源转发给它”。
  - 常用入口不再嵌第二个联系插件，点击“添加房源助手”只滚动回顶部并提示点顶部按钮，减少页面混乱。
  - `pages/home` 移除 `wx.openCustomerServiceChat` 调用和微信客服配置读取。
  - `pages/property-same` 兜底不再打开微信客服，只复制助手指令并提示发给企业微信助手。
  - 删除小程序前端 `miniprogram/config/customer-service.js`，并从 `services/api.js` 移除未使用的微信客服配置接口包装。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/property-same/index.js`
  - `node --check miniprogram/utils/workspace-mode.js`
  - `node --check miniprogram/services/api.js`
  - 小程序 JSON 递归解析通过。
  - `home/index.wxml` 基础标签计数通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 上传体验版后确认首页 banner 只出现一个企业微信添加入口，没有白屏按钮和微信客服授权页。
  - 点击常用入口“添加房源助手”应回到顶部提示，不打开微信客服。

### 2026-06-27：WorkBuddy“企业微信单聊回复”方案评估

- 背景：
  - 用户提供 `/Users/yiyi/WorkBuddy/2026-06-26-18-42-00/单独回复`，要求评估“直播蜂鸟走企业微信单聊回复功能”的文档和代码是否满足房源助手需求。
- 已检查：
  - `企业微信单聊回复_发送小程序卡片.md`
  - `企业微信发送小程序给微信用户_技术实现.md`
  - `wecom-miniprogram-bot` 与 `wecom-miniprogram-bot 2`，两份代码内容一致。
- 测试结果：
  - `python3 -m py_compile` 可通过。
  - 实际调用 `WecomClient._api()` 会在拼 URL 时直接报 `NameError: name 'cgi' is not defined`，因为代码写成了 `https://qyapi.weixin.qq.com{cgi-bin}{endpoint}`。
  - 代码发送文本和小程序卡片都依赖 `/cgi-bin/externalcontact/message/send`。
- 官方文档核对：
  - 官方能对上的客户联系能力包括 `externalcontact/add_msg_template`、`externalcontact/send_welcome_msg` 和微信客服 `kf/send_msg`。
  - 暂未在官方文档中确认普通企业微信外部联系人单聊可通过 `/externalcontact/message/send` 自由实时发送文本/小程序卡片。
- 当前结论：
  - WorkBuddy 代码不能直接并入，也不能证明“企业微信成员好友单聊可由后端自由回小程序卡片”。
  - 它最多提供了回调解密和异步处理的 demo 结构，但不满足 teamBuy 的房源导入、入库、绑定、通知和合规边界。
  - 房源助手主入口仍应坚持企业微信成员好友/会话存档收消息；发送结果卡片需要继续验证官方可用通道，不能默认采用 WorkBuddy 的 `externalcontact/message/send`。

### 2026-06-26：房源助手点击小程序链接即绑定

- 背景：
  - 用户指出竞品不是让用户进“待认领”手动找结果，而是处理完成后由企业微信自动发回小程序链接，用户点击即可进入结果。
- 已完成：
  - 后端新增 HMAC 签名的导入认领 token，默认 7 天有效。
  - 新增 `POST /api/imports/claim-by-token`，小程序登录后可通过 token 直接认领导入并写入 `external_userid -> ownerUserId/ownerOpenid` 绑定。
  - 新增 `AppService.build_import_claim_link(import_id)`，后续企业微信发送小程序卡片时可直接使用返回的 `pagePath`：`pages/import-claim/index?token=...`。
  - 新增小程序页面 `pages/import-claim/index`：用户点击企业微信发回的小程序链接后，未登录先登录，登录回来自动认领、绑定并跳编辑页。
  - `claim_import` 增加保护：导入已被其他账号认领时，不能被再次抢绑。
  - `miniprogram/app.json` 注册 `pages/import-claim/index`。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_claim_import_and_publish_flow backend/tests/test_app.py::test_claim_import_by_token_binds_external_user backend/tests/test_app.py::test_wecom_archive_process_auto_assigns_bound_external_user backend/tests/test_app.py::test_wecom_identity_mapping_resolves_owner_by_openid`：4 passed。
  - `node --check miniprogram/pages/import-claim/index.js`、`node --check miniprogram/pages/imports/index.js`、`node --check miniprogram/services/api.js`：通过。
  - `miniprogram/app.json` 和 `pages/import-claim/index.json` JSON 解析通过。

### 2026-06-26：会话存档处理完成后补自动通知

- 背景：
  - 用户 10:19 左右把微信笔记发给企业微信成员后，小程序没有收到企业微信回传的小程序链接。
- 已确认：
  - 线上会话存档已收到该条 `note` 消息，并生成导入批次 `import_0437e0a14e` 与资料 `note_de667374ee`。
  - 根因不是会话存档没进来，而是 archive 处理链路生成导入后没有创建 `ImportNotification`，因此不会进入发送队列。
- 已完成：
  - `process_wecom_archive_messages` 处理成功后会创建完成通知，并把结果入口改为 `pages/import-claim/index?token=...`。
  - archive worker 增加通知发送回调，处理完成后会尝试把通知发回企业微信。
  - 新增后台补发接口 `POST /api/wecom/notifications/send-pending`，用于补发待发送通知。
  - 已热更新生产后端并重启。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_wecom_archive_process_creates_user_note_and_is_idempotent backend/tests/test_app.py::test_real_sync_sends_wecom_completion_feedback backend/tests/test_app.py::test_claim_import_by_token_binds_external_user`：3 passed。
  - 生产路由已生效，错误 admin token 返回 403。
- 当前阻塞：
  - 对 10:19 这条历史导入手动补通知并试发时，企业微信返回 `48002 api forbidden`。
  - 说明当前发送实现仍走微信客服 `kf/send_msg`，不能给企业微信成员外部联系人会话直接发消息。
- 下一步：
  - 保留通知生成和失败落库。
  - 发送通道需要从微信客服发送接口切换为更合适的企业微信客户联系/群发/欢迎语/小程序内提醒链路。

### 2026-06-26：微信客服官方链路权限打通，但测试消息仍发到企微成员好友

- 背景：
  - 用户确认微信客服已开启，并把小程序开发者 ID 绑定到微信客服；随后补充配置“可调用接口的应用”后要求重测。
- 已确认：
  - 生产 `WECOM_SECRET` 获取 token 成功。
  - `kf/account/list` 已从 `48002 api forbidden` 变为成功，返回真正可用的客服账号：
    - `open_kfid=wkCSe7EwAAtY1p65p2bXVj3gTbWWzcKg`
  - 生产 `backend/.env` 已把 `WECOM_OPEN_KFID` 从旧值 `kfc5d3f0baa1f359b6d` 改为新值 `wkCSe7EwAAtY1p65p2bXVj3gTbWWzcKg`，并重建后端容器使环境变量生效。
  - `POST /api/wecom/real-sync` 现在可成功调用 `kf/sync_msg`，不再报 `48002`。
- 16:38 测试结果：
  - 用户 16:38 发来的文字没有进入微信客服 `sync_msg`。
  - 线上日志显示该消息进入的是会话内容存档 `archive/callback`。
  - archive 表已保存消息并生成 `note_23816dbffa` 与导入通知 `notice_f7c4c04efe`。
  - 对该 archive 外部联系人 ID 直接调用 `kf/send_msg` 返回 `95018 session status invalid`。
- 结论：
  - 微信客服官方 API 权限已经打通。
  - 16:38 这条仍是发给企业微信成员好友，不是通过 `wx.openCustomerServiceChat` 打开的微信客服会话。
  - 只有用户从微信客服入口进入并发送消息，`kf/sync_msg + kf/send_msg` 才可能自动回小程序卡片。
- 部署注意：
  - 本轮为刷新 `WECOM_OPEN_KFID` 执行过 `docker compose up -d --force-recreate --no-deps backend`，随后重新热同步了近期后端文件。
  - 后续最好做一次正式后端镜像构建，避免热补丁与镜像文件再次不一致。

### 2026-06-26：首页房源助手入口改为微信客服优先

- 背景：
  - 用户确认产品应该把两层功能叠起来：前端像“找企业微信助手”，底层实际走微信客服 API 收发。
- 已完成：
  - 首页 banner 房源助手主卡文案改为“发房源给助手”。
  - 主按钮“立即发送房源”调用 `wx.openCustomerServiceChat`。
  - 企业微信「联系我」插件保留为二级入口，文案为“长期联系可再添加企业微信”。
  - 常用入口中“发房源给助手”点击卡片本身直接打开微信客服，不再只是滚动到顶部。
  - 常用入口内仍保留“加企业微信”插件按钮，作为长期联系转化。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`：通过。
  - `node --check miniprogram/utils/workspace-mode.js`：通过。
  - `miniprogram/app.json`、`miniprogram/pages/home/index.json` JSON 解析通过。
  - `home/index.wxml` 基础标签计数通过。
  - 本轮关键文件 `git diff --check` 通过。
- 待真机：
  - 上传体验版后，点击“立即发送房源”应进入微信客服会话，而不是企业微信成员好友。
  - 在该客服会话里发房源后，再触发 `real-sync` 验证是否进入 `kf/sync_msg`。

### 2026-06-27：6:44 真机客户行为与雷达未出现排查

- 背景：
  - 用户 6:44 左右用两个微信测试客户打开房源/推荐包，并反馈客户看板未出现雷达，同时手机端“好友/朋友圈”按钮遮挡“生成同款”区域。
- 线上只读排查：
  - 生产数据库已记录 6:45-6:46 的客户行为：`user_5fd8d56c26` 打开 `showcase_3f537b64ed`，并点击 `note_d00ca2b3bd`、`note_730305fd2e`、`note_ea2607e9d8` 等房源。
  - 生产 `/api/dashboard/business` 当前返回旧版 `data.summary/recentVisitors/topNotes/visitorProfiles` 结构，没有 `opportunitySummary`、`opportunityAlerts`、`radarProfiles`、`contentInsights`、`revivalAlerts` 字段。
  - 结论：真机事件进了后台，但本地新增的成交雷达后端尚未部署到生产，所以没有生成雷达提醒。
  - 当前线上小程序上报事件缺少 `durationSeconds`、`maxScrollPercent`、`focusSections`，因此即使上线新版前端前，也无法产生“停留 2 分钟、重点看价格/联系方式”的解释。
- 小程序已修：
  - `pages/note-preview` 手机端默认把“好友/朋友圈”分享按钮从固定悬浮改为行内按钮，避免遮挡成交卡片。
  - `property-same-card` 默认手机单列，大屏再切回左右布局；`生成同款`按钮保持 flex 居中。
- 已验证：
  - `node --check miniprogram/pages/note-preview/index.js` 通过。
  - `git diff --check -- miniprogram/pages/note-preview/index.wxss` 通过。

### 2026-06-27：首页与客户雷达 UI 收敛

- 背景：
  - 用户指出首页功能都在，但视觉太乱，客户显示位置太多，不知道应该看哪个入口。
  - 讨论后确定首页应优先展示“今日成交机会”，客户相关统一进入“客户雷达”。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/22-home-radar-ui-consolidation.md`。
  - 首页重构为四块：
    - 今日成交机会。
    - 把房源发给助手。
    - 客户雷达统一入口。
    - 最近成果。
  - 首页移除旧的“客户动态/反馈”分散模块，只保留客户雷达入口。
  - 底部 tab 文案从“反馈”改为“雷达”。
  - `pages/visits` 从旧反馈页重构为客户雷达页，包含：
    - 待跟进。
    - 访客。
    - 资料优化。
  - 雷达页客户卡展示：意向、原因、标签、建议动作、复制话术、标记已联系。
  - 雷达页资料优化区展示资料建议，并预留“生成对比建议”动作。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`、`node --check miniprogram/pages/visits/index.js`、`node --check miniprogram/pages/business-dashboard/index.js` 通过。
  - `miniprogram/app.json`、首页/雷达页 JSON 解析通过。
  - 首页、雷达页、客户看板 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：首页首屏视觉对齐效果图

- 背景：
  - 用户指出实际首页与效果图差距较大，右侧雷达 banner 过于简化。
  - 用户指出空机会卡里的黑色“去雷达”按钮含义不清。
  - 用户指出“添加房源助手”不应额外显示插件默认的“立即联系”标签按钮。
- 已完成：
  - 首页右侧雷达图改为 CSS 绘制的客户卡 + 雷达圆环组合，更接近效果图。
  - 空机会卡不再显示黑色“去雷达”按钮，只保留提示文案。
  - 有真实机会提醒时才显示“复制话术”按钮。
  - “添加房源助手”卡片保留干净视觉，企业微信联系插件透明覆盖整张卡，避免露出默认“立即联系”样式。
- 已验证：
  - `node --check miniprogram/pages/home/index.js` 通过。
  - 首页 WXML 标签检查通过。
  - `git diff --check -- miniprogram/pages/home/index.wxml miniprogram/pages/home/index.wxss` 通过。

### 2026-06-27：释放其他工作台入口并按场景切换首页/雷达文案

- 背景：
  - 用户确认产品对外先主推房源，但未来客户也可能成为用户，全社会很多销售场景都可复用成交雷达能力。
  - 需要把服务、团购、日常资料三个工作台逻辑梳理清楚，并让 UI 能按对应工作台切换。
- 已完成：
  - `miniprogram/utils/workspace-mode.js` 取消强制房源锁定，默认仍为房源工作台。
  - 首页 banner、主动作、空状态、最热内容指标按工作台切换：
    - 房源：房源成交助手 / 今日成交机会 / 添加房源助手 / 整理房源合集。
    - 服务：服务成交助手 / 今日咨询机会 / 做服务方案 / 做个人名片。
    - 团购：团购成交助手 / 今日成单机会 / 新建商品 / 商品合集。
    - 日常：资料分享助手 / 今日分享反馈 / 写笔记 / 日常合集。
  - 首页 banner 增加轻量工作台切换入口，默认仍显示房源。
  - 雷达页按工作台切换空状态、资料名词、对比建议：
    - 房源对比合集。
    - 商品对比建议。
    - 服务方案对比。
    - 日常资料合集。
  - 服务、团购也会尝试拉取对应 `business-dashboard` 数据；日常资料继续使用本地分享反馈。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/pages/visits/index.js && node --check miniprogram/utils/workspace-mode.js` 通过。
  - 首页和雷达页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：首页白屏排查与稳定性修复

- 背景：
  - 用户反馈新版首页打不开、白屏，并怀疑是否有些请求走服务器、有些走本地后端。
- 排查结论：
  - `miniprogram/app.js` 当前统一使用 `https://teambuy.lifelove.top`，未发现首页链路混用本地后端地址。
  - 线上 `/api/dashboard/business` 和 `/api/notes` 可访问，测试用不存在用户返回 404，说明不是域名或网关不可达。
  - 首页脚本模拟加载通过，但 WXML 里存在 `||` 和三元表达式等复杂模板表达式，真机基础库下有兼容风险。
  - 线上模式会清理本地 mock 登录态；如果手机仍保留旧本地测试用户，会跳到登录页，需要重新微信登录。
- 已修复：
  - 首页 WXML 移除复杂表达式，改为 JS 预先准备 `modeSwitchLabel`、`statusClass`、`valueClass`、`activeClass`。
  - 首页未登录跳转登录页时带上 `returnUrl`，便于识别登录态问题。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/utils/workspace-mode.js && node --check miniprogram/pages/login/index.js && node --check miniprogram/app.js` 通过。
  - 首页、登录页、雷达页 WXML 标签检查通过。
  - 首页 WXML 表达式检查已无 `||`、`&&`、三元和相等判断。

### 2026-06-27：服务工作台补充“商机/合作信息”能力

- 背景：
  - 用户提供保险出单、海参工厂批发、城市群管理员招募、进口清关代理等群消息样例。
  - 讨论后确认这些内容不是普通服务方案，而是高频 B2B 商机/合作信息。
- 已完成：
  - 新增开发文档 `docs/stage2-docs/23-business-opportunity-service-card.md`。
  - 服务工作台不新增第五个大工作台，继续复用 `service` + `service_offer`。
  - 新增服务页模板 `service_business_opportunity`，用于保险、清关、招募、批发、代理、货源合作等内容。
  - 首页服务模式主入口改为“做服务/商机页”。
  - 服务工作台 quick action 新增“商机合作”。
  - 后端 `SkillRouterService` 新增商机/合作识别规则，高置信时自动生成 `service_offer` 并带 `displayTemplate=service_business_opportunity`。
- 样例验证：
  - 保险出单、海参工厂批发、城市群管理员招募、进口清关代理四条样例均识别为 `service_offer + service_business_opportunity`。
- 已验证：
  - `node --check miniprogram/utils/sales-page-templates.js && node --check miniprogram/pages/service-offer-studio/index.js && node --check miniprogram/pages/home/index.js && node --check miniprogram/utils/workspace-mode.js` 通过。
  - `PYTHONPATH=backend ... python3 -m py_compile backend/app/services/skill_router_service.py` 通过。
  - 服务方案页和首页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：我的页工作台文案收敛

- 背景：
  - 用户在“我的页 / 常用工作台”只看到“服务”，未看到“商机合作”。
  - 用户指出“只影响首页和工作台展示，不会删除资料”文案过长，且“工作台”含义不清。
- 已完成：
  - 服务工作台在常用工作台区显示为“服务商机”，名称为“服务/商机工作台”。
  - 常用工作台说明改为“只影响首页和雷达展示。”。
  - 按钮从“去客户看板”改为“去雷达”。
- 已验证：
  - `node --check miniprogram/utils/workspace-mode.js && node --check miniprogram/pages/profile/index.js` 通过。
  - 我的页和首页 WXML 标签检查通过。

### 2026-06-27：首页 V2：资料机会雷达

- 背景：
  - 用户确认产品主表达应升级为“资料发出去，机会看得见”。
  - 房源仍是默认推广尖刀，但首页不能只框死房源，也不能把四个工作台做成功能超市。
- 新增文档：
  - `docs/stage2-docs/24-home-opportunity-radar-generalized.md`
- 已完成：
  - 首页 banner 主心智改为：
    - 小标题：资料机会雷达。
    - 主标题：资料发出去，机会看得见。
    - 副标题：谁看了、谁感兴趣、下一步怎么跟，这里帮你整理好。
  - 场景切换从大入口收敛为轻胶囊：`当前：房源场景`。
  - 今日机会独立成数据面板，指标为：高意向、新打开、待跟进、待处理。
  - 移除首页单独“客户雷达”大卡，今日机会数字和提醒进入雷达。
  - 默认房源场景继续保留“把房源发给助手”第一动作。
  - “最近成果”改为“最近有反馈的资料”。
  - 底部新增轻入口：“也可以用于商品、服务商机和资料包 · 切换场景”。
- 已验证：
  - `node --check miniprogram/pages/home/index.js && node --check miniprogram/utils/workspace-mode.js` 通过。
  - 首页 WXML 标签检查通过，复杂表达式检查通过。
  - 首页模拟加载通过，默认房源场景和四个今日机会指标正常。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：首页 banner 视觉资产化

- 背景：
  - 用户反馈效果图漂亮，但前端 DOM 版本少了质感。
  - 当前 banner 的雷达图、人物卡和标题排版由 WXML/WXSS 绘制，容易受小程序字体、rpx 和容器压缩影响。
- 已完成：
  - 从用户确认的首页效果图中裁出纯 banner 卡片，保存为 `miniprogram/static/workspace/home-opportunity-radar-banner.png`。
  - 首页首屏 banner 改为图片资产展示。
  - 保留“当前：房源场景”区域的点击热区，用于打开场景切换。
  - 今日机会、房源助手、最近有反馈的资料仍继续走真实数据和 DOM 渲染。
- 取舍：
  - banner 视觉更接近效果图。
  - banner 内文案暂为静态图，当前适合房源默认主推场景；后续若要多场景动态文案，需要分别出多张场景 banner 或重新做高保真 DOM。
- 已验证：
  - 首页 JS 语法检查通过。
  - 首页 WXML 标签检查通过。
  - 首页 WXML 复杂表达式检查通过。
  - banner 图片资源存在，关键文件 `git diff --check` 通过。

### 2026-06-27：前台“工作台”文案改为“场景”

- 背景：
  - 用户指出切换弹层兜底按钮字号过大，并质疑是否还要叫“工作台”。
- 已完成：
  - 首页切换弹层小标签从“常用工作台”改为“使用场景”。
  - 兜底按钮从“还不确定，先用日常资料台”改为“先用日常资料”，字号和宽高收小。
  - 我的页“常用工作台”改为“常用场景”。
  - 前台模式名改为“房源场景 / 团购/商品场景 / 服务/商机场景 / 日常资料场景”。
  - 测试数据提示从“去工作台查看”改为“去雷达查看”。
- 已验证：
  - 首页、我的页和工作台配置 JS 语法检查通过。
  - 首页和我的页 WXML 标签检查通过。
  - 前台相关文件已无“工作台 / 日常资料台 / 常用工作台”残留。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料、合集、雷达销售助理闭环 V1

- 背景：
  - 用户坚持底部 tab 继续叫“资料”。
  - 讨论确认资料和合集都是可发客户的内容载体，雷达负责客户反馈和机会判断。
  - 用户认可“发客户后的状态追踪”可以用浅色条和文字呈现。
- 新增文档：
  - `docs/stage2-docs/25-material-collection-radar-sales-assistant-loop.md`
- 已完成：
  - 资料页顶部定位改为“管理单条资料，直接发客户”。
  - 资料卡新增发出状态追踪条：等待客户打开、客户已打开、客户重复查看、建议跟进。
  - 资料页主按钮从“分享”改为“发客户”，有客户动作入口改为“去雷达”。
  - 合集页顶部定位改为“把多条资料打包发客户”。
  - 合集卡新增发出状态追踪条，已发布合集主按钮改为“发客户”。
  - 雷达页顶部新增定位文案：“看客户反馈和跟进建议”。
  - `enrichCard` 统一输出 `deliveryStatus`，后续其他页面可复用。
- 已验证：
  - `node --check miniprogram/utils/dashboard.js && node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/visits/index.js` 通过。
  - 资料页、合集页、雷达页 WXML 标签检查通过。
  - 状态规则模拟通过：等待客户打开 / 客户已打开 / 客户重复查看 / 建议跟进。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料/合集/雷达 P1 酷功能规则版收口

- 背景：
  - 用户要求先把 P1 收口并全部实现。
  - P1 目标是让三页更像销售助理，而不是普通资料管理工具。
- 已完成：
  - 资料页新增发前体检：
    - 缺联系方式、价格不清、缺图片、标题偏短、体检通过。
  - 资料页新增发客户状态筛选：
    - 全部、待整理、已发客户、有反馈。
  - 合集页新增状态筛选：
    - 全部、草稿、已发布、有反馈。
  - 雷达画像标签增强：
    - 价格敏感、位置优先、联系意向、关注保障、需要信任、沉默复活、反复查看、正在比较、有咨询动作、疑似同行、疑似上游、多次触达。
  - 雷达下一句话建议增强：
    - 根据价格、位置、联系方式、案例、保障、沉默复活、正在比较等标签生成不同话术。
  - 雷达客户卡新增“打开来源”。
  - 资料优化建议按钮可跳回来源资料。
  - “生成对比合集建议”改为跳转合集创建页，并带 `method=radar_compare` 和来源 `noteId`。
  - 合集创建页新增“来自雷达建议”提示卡。
  - 开发文档 `docs/stage2-docs/25-material-collection-radar-sales-assistant-loop.md` 补充 P1 已落地清单和仍未完成的 P0 真实发送闭环。
- 已验证：
  - `node --check miniprogram/utils/dashboard.js && node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/visits/index.js && node --check miniprogram/pages/showcase-edit/index.js` 通过。
  - 资料页、合集页、雷达页、合集创建页 WXML 标签检查通过。
  - 发前体检和状态规则模拟通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：P0 发客户真实链路收口

- 背景：
  - 用户要求 P0 也全部实现并继续收口。
  - P0 关键是把“发客户”从按钮文案变成真实可追踪业务动作。
- 已完成：
  - 后端：
    - `RecordViewRequest` 新增 `eventType/shareId/shareFromUserId/scene/referrer`。
    - `ViewEvent` 新增 `shareId/shareFromUserId/scene/referrer`。
    - `ViewType` 增加 `share`。
    - `view_events` 表新增 `share_id/share_from_user_id/scene/referrer`。
    - 新增 `idx_view_events_share`。
    - `record_note_view` 和 `record_view` 支持 `eventType=share`。
    - share 事件不计入 PV/UV。
    - 资料统计新增 `shareCount/latestShareAt/topShareId`。
    - owner 自己打开资料不入库、不计客户机会。
    - owner 自己打开合集事件后端兜底忽略。
  - 小程序：
    - 资料页卡片“发客户”改成真实分享按钮。
    - 资料页直接发客户时生成 `shareId` 并记录 share 事件。
    - 单条资料分享路径携带 `sid/from/src/ref`。
    - 客户打开单条资料时回传 `shareId/shareFromUserId/scene/referrer`。
    - 资料卡状态支持 `shareCount`，已发未打开显示“已发出，等待打开”。
  - 测试：
    - Postgres repository schema 测试补充 view_events share 字段和索引。
    - 资料浏览测试覆盖 share 不计 PV/UV、owner 打开不计 PV/UV、客户打开后计 PV/UV。
    - 合集发布测试补充 owner 打开合集不记录。
- 已验证：
  - `.venv312/bin/python -m pytest backend/tests/test_postgres_repository_schema.py backend/tests/test_app.py::test_note_preview_view_updates_note_list_stats -q` 通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py::test_showcase_builder_create_publish_public_and_archive -q` 通过。
  - 后端关键文件 `py_compile` 通过。
  - 前端相关 JS `node --check` 通过。
  - 资料页、资料预览页、合集页、合集公开页 WXML 标签检查通过。
  - 状态规则模拟通过：等待客户打开 / 已发出，等待打开 / 客户已打开。

### 2026-06-27：P0/P1 分享体验与裂变补强

- 背景：
  - 用户要求把 P0/P1 一起补强。
  - 用户补充：每个资源或合集的转发卡片下方要有“生成同款”等营销语句，方便裂变。
- 已完成：
  - 资料页点“发客户”后，本地资料卡即时切换为“已发出，等待打开”。
  - 合集页点“发客户”后，本地合集卡即时切换为“已发出，等待打开”。
  - 资料卡和合集卡下方新增裂变提示：“发给客户后可看反馈；对方也能生成同款，帮你带来更多传播。”
  - 资料页“发前体检”提示支持点击直达编辑。
  - 资料公开页、合集公开页和列表分享标题统一为客户友好口径：“xxx｜点开查看完整资料”。
  - 保持“生成同款”主要在公开页和列表提示里承接，避免客户收到的分享标题过度营销。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/note-preview/index.js && node --check miniprogram/pages/showcase-view/index.js` 通过。
  - 资料页、合集页 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：小程序前端图片转 WebP 降包体

- 背景：
  - 用户反馈小程序前端超过 2MB，无法测试。
  - 首页雷达 banner 和工作台场景图占用较大。
- 已完成：
  - 将 `miniprogram/static/workspace/` 下 6 张大图转为 WebP：
    - `home-opportunity-radar-banner.webp`
    - `login-room.webp`
    - `workspace-groupbuy.webp`
    - `workspace-service.webp`
    - `workspace-property.webp`
    - `workspace-notes.webp`
  - 首页、登录页和工作台配置引用改为 WebP。
  - 删除已替换的 PNG/JPG 原图。
  - 删除 `miniprogram/.DS_Store` 和 `miniprogram/static/.DS_Store`。
- 体积结果：
  - 小程序目录真实文件字节约 `1,697,712 bytes`。
  - 图片总字节约 `149,917 bytes`。
  - 旧 workspace 大图引用已清空。
- 已验证：
  - `node --check miniprogram/utils/workspace-mode.js` 通过。
  - 首页、登录页 WXML 标签检查通过。

### 2026-06-27：前四个 tab 闭环感补强

- 背景：
  - 用户希望继续打磨前 4 个 tab，让“首页、资料、合集、雷达”更稳、更酷。
  - 目标是不再堆功能，而是强化“整理资料 -> 发客户 -> 看雷达 -> 做合集继续跟”的闭环。
- 已完成：
  - 首页：
    - 日常资料场景下，今日机会数字可带用户进入雷达对应 tab。
    - 新打开/访客进入雷达相关页，待跟进/高意向进入待跟进。
  - 资料页：
    - 每条资料新增阶段提示：待补强、可发送、已发出、已打开、建议跟进。
    - 阶段提示与发前体检、发客户状态并列，让资料更像销售素材。
  - 合集页：
    - 每个合集新增用途标签：推荐包、对比包、商品包、方案包、资料包、复访包。
    - 用途标签说明适合发给哪类客户或场景。
  - 雷达页：
    - 客户卡新增“下一步动作”：发对比合集、补附近方案、立即轻触达、发案例保障、发最新情况、先观察等。
    - 下一步动作根据客户标签和建议动作前端规则生成。
- 已验证：
  - `node --check miniprogram/utils/dashboard.js && node --check miniprogram/pages/home/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/visits/index.js && node --check miniprogram/pages/library/index.js` 通过。
  - 首页、资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料/合集卡片高度与雷达动作位置修正

- 背景：
  - 用户反馈资料和合集每个卡片不是字太长，而是卡片太高、不美观。
  - 讨论确认“下一步动作”更适合放在雷达待跟进页，因为它是针对某个客户的跟进动作；资料优化页只保留资料修补和对比合集建议。
- 已完成：
  - 资料列表卡左侧封面从 `178rpx` 降为 `132rpx`，行距、状态胶囊和按钮高度同步收紧。
  - 没有客户动态时不再显示“暂无客户动态”空胶囊。
  - 资料卡把“发前体检 / 资料阶段 / 发客户状态”从三条竖向说明压缩成一行状态胶囊。
  - 资料卡裂变提示压缩为“可追踪反馈 · 支持生成同款”。
  - 合集卡封面从 `112rpx` 降为 `96rpx`，右侧操作区收窄。
  - 合集卡把“用途标签 / 发客户状态”压缩成一行状态胶囊。
  - 合集卡裂变提示改为单行省略。
  - 撤回资料优化 tab 的“下一步动作”模块，避免与待跟进客户动作混淆。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/visits/index.js` 通过。
  - 资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料卡高度二次压缩、合集顶部紧凑化、待跟进动作按钮化

- 背景：
  - 用户认可“下一步动作属于待跟进页”的产品判断，并提醒后续需要坚持正确观点，不要只顺着用户话走。
  - 用户反馈资料卡仍然偏高，合集顶部 banner 过高。
  - 用户反馈雷达待跟进页仍没有明显的“下一步动作”按钮。
- 已完成：
  - 资料页：
    - 列表封面继续从 `132rpx` 降到 `112rpx`。
    - 创建时间并入统计行，不再单独占一行。
    - 状态胶囊减少为“阶段 + 发前问题”，不再重复显示“等待客户打开”。
    - 裂变提示只在已发出、已打开或有客户动态时显示。
    - 资料卡按钮高度进一步收紧。
  - 合集页：
    - 顶部从高 banner 调整为紧凑工具卡。
    - 方向入口改为一行紧凑卡，标题和说明压缩。
    - 顶部主按钮高度收紧。
  - 雷达页：
    - 待跟进客户卡中的“下一步动作”改为明确按钮。
    - 对比类动作跳转生成对比合集，其余动作复制跟进话术。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/visits/index.js` 通过。
  - 资料、合集、雷达 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料缩略图权重恢复与合集无效 banner 删除

- 背景：
  - 用户反馈资料缩略图太小、太靠上靠左，且按钮区右侧有空白。
  - 用户判断合集顶部 banner 没有实际作用，建议删除。
- 已完成：
  - 资料页：
    - 列表缩略图从 `112rpx` 调整为 `144rpx`。
    - 资料卡改为垂直居中对齐，缩略图不再贴上。
    - 无客户动态时按钮区改为两列，不再留下第三列空白。
  - 合集页：
    - 删除顶部大 banner 和方向卡。
    - 改为轻量操作栏：场景标签、合集类型、新建按钮。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js` 通过。
  - 资料、合集 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料搜索按钮收窄与合集 Hero 样式统一

- 背景：
  - 用户反馈资料页搜索按钮背景太长，只需要比文字稍宽。
  - 用户反馈合集顶部如果暂时没有更好方案，就统一为资料页 banner 样式。
- 已完成：
  - 资料页搜索按钮从固定 `128rpx` 改为内容自适应，保留最小宽度和左右内边距。
  - 合集页顶部改为与资料页一致的 hero 样式：
    - 左侧文案。
    - 右侧视觉字块。
    - 下方轻操作栏保留场景和新建按钮。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js` 通过。
  - 资料、合集 WXML 标签检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：合集页按参考效果图重做比例

- 背景：
  - 用户反馈合集页前端实现与效果图比例仍有差距，效果图的顶部开场、右侧视觉块、主动作和列表卡比例更舒服。
- 已完成：
  - 合集页恢复页面内“合集”视觉锚点，形成与参考图一致的开场节奏。
  - 顶部 Hero 调整为大标题 + 右侧“合”视觉块，不再使用前一版紧凑工具条。
  - 场景标签和“新建房源合集”等主按钮放在 Hero 下方同一行，强化“打包发客户”的主动作。
  - 筛选胶囊直接承接主动作区，减少中间干扰。
  - 合集列表卡片重新收紧比例：封面、标题、简介、创建时间、状态标签和操作按钮重新分配空间。
  - 合集状态从多行说明压缩为一行胶囊，保持卡片轻量。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js` 通过。
  - 合集 WXML 小程序模板适配检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：修正合集页重复标题和首屏空白

- 背景：
  - 用户真机截图反馈合集页“完全不能看”，与效果图差距明显。
  - 主要问题是页面出现多个“合集”标题，且顶部空白过大，Hero 文案被挤到首屏下半部分。
- 已完成：
  - 删除自定义导航下额外的 `body-title`，避免重复显示“合集”。
  - 收紧合集 Hero 的顶部留白和最小高度，让“把多条资料打包发客户 / 房源合集 / 右侧合视觉块”回到首屏主位置。
  - 保留场景标签、新建合集按钮和筛选胶囊的顺序。
- 已验证：
  - `node --check miniprogram/pages/showcases/index.js` 通过。
  - 合集 WXML 小程序模板适配检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：修复合集页原生导航与 custom-nav 双标题

- 背景：
  - 用户反馈删除正文标题后仍然还有两个“合集”。
  - 排查发现合集页用了 `<custom-nav title="合集" />`，但 `miniprogram/pages/showcases/index.json` 未设置 `navigationStyle: "custom"`，导致原生导航标题和自定义导航标题同时显示。
- 已完成：
  - `miniprogram/pages/showcases/index.json` 增加 `navigationStyle: "custom"`。
  - 文档补充 custom-nav 页面必须关闭原生导航的坑。
- 已验证：
  - 合集 JS、JSON、WXML 检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：资料页与合集页卡片风格统一

- 背景：
  - 用户确认如果合集页比例通过，下一步应让“资料页”和“合集页”的卡片风格统一，看起来像同一个产品体系。
- 已完成：
  - 资料列表卡改为与合集卡一致的白底、细边框、`8rpx` 圆角和轻阴影。
  - 资料卡标题字号、颜色、状态胶囊、裂变提示和底部按钮节奏向合集卡靠齐。
  - 普通资料卡外露操作从“发客户 / 编辑 / 合集 / 复用 / 复制 / 删除”等多入口，收口为“发客户 / 编辑 / 更多”。
  - “更多”复用已有操作弹层，保留加入合集、复制文案、删除资料等功能。
  - 资料缩略图保留较大识别尺寸，不强行压到合集封面尺寸。
- 已验证：
  - `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js` 通过。
  - 资料、合集 WXML 检查通过。
  - 资料、合集 JSON 检查通过。
  - 本轮关键文件 `git diff --check` 通过。

### 2026-06-27：雷达页销售助理收口

- 背景：
  - 用户要求把“待跟进客户卡、下一步动作、客户画像标签、资料/合集联动、助理式空状态”5 个点一起做完。
- 已完成：
  - 雷达待跟进卡升级为销售助理结构：销售助理判断、看过什么、为什么值得跟、画像标签、下一步动作、复制话术、生成对比、打开来源、标记已联系。
  - 客户画像标签扩展到价格敏感、位置优先、反复看联系方式、关注保障、需要信任、沉默复活、正在比较、疑似同行、疑似上游等。
  - 疑似同行和疑似上游不进入待跟进主池，仍可在访客画像中观察。
  - 资料页“去雷达”会带来源筛选，只看这条资料带来的客户反馈。
  - 合集页已发布合集的“更多”菜单新增“雷达”，可带合集来源进入客户雷达。
  - 雷达页新增来源筛选条，可一键恢复看全部。
  - 雷达空状态改为助理口吻：“先发出 3 条资料，我会帮你找出谁反复看、谁关注价格、谁适合马上跟。”
- 已验证：
  - `node --check miniprogram/pages/visits/index.js && node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/showcases/index.js` 通过。
  - 资料、合集、雷达 WXML 检查通过。
  - 资料、合集、雷达 JSON 检查通过。
  - 本轮关键文件 `git diff --check` 通过。
## 2026-06-27：前四个 Tab 二次收口

- 背景：
  - 用户确认首页、资料、合集、雷达四个 Tab 的主链路方向对了，但希望“更稳、更酷”，尤其要减少蓝白单调感、减少解释文字，并增强 AI 助理感。
- 已完成：
  - 首页“今日机会”和“最近有反馈的资料”副文案进一步收短，改成结果导向，不再提示用户怎么点。
  - 资料页把“发客户状态”前置为默认主筛选；分类、专题、标签下沉到展开工具区，降低首屏后台感。
  - 资料卡主状态从 `materialStage` 收口为更直接的 `deliveryStatus`，首屏优先告诉用户这条资料现在是待发送、已打开、客户重复查看还是建议跟进。
  - `miniprogram/utils/dashboard.js` 将未分享资料的默认状态文案从“等待客户打开”改为“待发送”，让资料页阶段感更清楚。
  - 合集卡把 `purpose` 提前为主信息块，先告诉用户这是推荐包、对比包、商品包、方案包还是资料包，以及适合什么场景。
  - 雷达页顶部提示压缩为一句短说明，客户卡标签改成“AI判断”；卡片动作从并列 4 个按钮收口为“复制话术 + 更多”。
  - 雷达统计卡补充暖橙、绿色、淡紫等轻色层次，避免首页/雷达继续只有蓝白两色。
- 已验证：
  - `node --check miniprogram/pages/home/index.js`
  - `node --check miniprogram/pages/library/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - `node --check miniprogram/pages/visits/index.js`
  - `node --check miniprogram/utils/dashboard.js`
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27：无图资料改为标题封面卡

- 背景：
  - 用户提出很多转发微信群、展示页和资料列表里的内容没有图片，当前只显示“资料 / 房源 / 合集”等占位字，识别度和美观度都不够。
- 已完成：
  - 新增通用工具 `miniprogram/utils/title-cover.js`，从标题中提取不超过 8 个字的重点内容，生成两行标题封面信息和轻色调。
  - 资料列表、首页最近反馈、合集列表在无图时统一改成“小标签 + 重点标题”的轻封面卡，而不是单字占位。
  - 展示页 `featured_window / moments_story / catalog_list / brand_card` 的无图卡片同步改成标题封面卡。
  - `note-preview` 新增普通资料无图分享图兜底；`showcase-view` 新增无 banner / 无首图时的分享图兜底，优先生成标题封面图。
- 已验证：
  - `node --check miniprogram/utils/title-cover.js`
  - `node --check miniprogram/utils/dashboard.js`
  - `node --check miniprogram/utils/business-card-share.js`
  - `node --check miniprogram/pages/note-preview/index.js`
  - `node --check miniprogram/pages/showcase-view/index.js`
  - `node --check miniprogram/pages/showcases/index.js`
  - 本轮关键文件 `git diff --check` 通过。

## 2026-06-27：无图分享卡补回主打开引导和轻同款入口

- 背景：
  - 用户确认无图卡方向可以，但明确要求“打开小程序查看完整内容”必须是主承接。
  - “我也想做同款”要保留，但只适合做一行更小的次级提示，不能抢掉资料本身。
- 已完成：
  - `miniprogram/utils/business-card-share.js`
    - 通用无图分享卡改为双层承接：主按钮显示“打开小程序查看完整资料/合集”，底部再加一行小字“我也想做同款”。
  - `miniprogram/pages/note-preview/index.js`
    - 普通资料无图分享兜底图主文案改为“打开小程序查看完整资料”。
  - `miniprogram/pages/showcase-view/index.js`
    - 合集无图分享兜底图主文案改为“打开小程序查看完整合集”。
  - `miniprogram/pages/library/index.{js,wxml,wxss}`
    - 列表直接“发客户”时，无封面资料会预生成无图分享图，尽量避免群发时没有分享图。
  - `miniprogram/pages/showcases/index.{js,wxml,wxss}`
    - 列表直接“发客户”时，无 banner 合集会预生成无图分享图，保持和公开页一致的分享语言。
## 2026-06-28 前四个 Tab 视觉收口真机清单

- 新增 [docs/qa/前四个Tab视觉收口_真机回归清单.md](/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/qa/前四个Tab视觉收口_真机回归清单.md)。
- 这份清单用于本轮首页、资料、合集、雷达四个 Tab 的真机收边，重点覆盖：
  - 视觉统一
  - 文本密度
  - 居中与排版
  - 无图卡兜底
  - 首页 / 资料 / 合集 / 雷达逐页验收标准
- 本轮没有继续改业务代码，先把“怎么验、先修哪里”固定下来，避免后续反复凭感觉收口。

## 2026-06-28 前四个 Tab 第一轮页面收边

- 首页：
  - 压缩了 hero 副文案。
  - 压缩了“把房源发给助手”区域说明和底部预留文案。
- 资料页：
  - 压缩了顶部说明区。
  - 把说明性长文案改成两个短胶囊。
  - 非房源/非商品无图卡切到“轻设计卡”布局。
  - 卡片底部统一补回“打开小程序看完整资料 / 输入同款继续问”类传播引导。
- 合集页：
  - 压缩了首屏说明。
  - 无图合集卡切到同风格“轻设计合集卡”。
  - 合集卡底部保留“打开小程序看完整合集 / 输入同款继续问 / 导出方案书预留”引导。
- 本轮没有修改路由和业务逻辑，只做视觉收口和文案密度控制。

## 2026-06-28 前四个 Tab 第二轮统一收边

- 本轮把首页、资料、合集、雷达作为一组统一继续收边，不再拆开单独修。
- 首页：
  - 最近反馈区的无图卡也切到轻封面样式，和资料页、合集页保持一致。
- 雷达页：
  - hero 副文案和 AI 提示继续压短。
  - hero 三张信号卡补了更明确的辅助色区分。
  - 摘要区明确露出“同行已过滤”胶囊，避免业务信息被视觉优化吞掉。
  - 跟进卡、时间线卡、建议卡统一补成更轻的渐变白底和描边层次。
- 现在前四个 Tab 已基本收成同一套浅底、轻阴影、短文案、轻胶囊、轻封面卡的语言。

## 2026-06-28 场景说明字再减一轮

- 用户反馈“AI会按打开、停留、咨询和重点查看...”这类说明字会让人不舒服。
- 已从首页 hero 和雷达 hero 里直接删掉这类系统说明文本，只保留核心口号、场景胶囊和关键业务信息。

## 2026-06-28 我的页收口落地

- 我的页重做为更克制的个人工作台结构：
  - 顶部身份卡
  - 资源库入口
  - 当前使用场景
  - 我的内容
  - 设置与帮助
- 删除了原来的会员服务、笔记/专题堆叠、消息专区重复入口、开发测试入口等杂项。
- 顶部身份卡改成“默认一键登录身份 + 明确可编辑”：
  - 头像角标
  - 编辑资料按钮
  - 微信号/手机号完善状态
- 资源库区域改为扁平重点入口，当前主打 `群资源库`，同时为 `行业通讯录` 和后续行业资源预留位置。
- 场景切换只保留一处，并与“完善资料，方便客户主动联系你”绑定。
- 我的内容只保留 `资料 / 合集 / 消息`。
- 设置与帮助暂时只保留 `个人资料 / 帮助与反馈 / 退出登录`。
- 个人资料编辑层补上了 `微信号` 字段，前后端已一起接通保存。

## 2026-06-28 我的页顶部再减一轮

- 顶部身份卡右侧不再保留长胶囊 `编辑` 按钮，改为更小的圆形修改提示，减少 banner 横向占用。
- 资源库右上角明确改成 `100 积分`，不再只写抽象的“积分入口”。

## 2026-06-28 五个 Tab 首屏心智与名片入口收口

- 本轮按用户要求继续收口五个 Tab，不扩会员、PDF、专题、行业通讯录、行业资源等新功能。
- 五个 Tab 顶部心智已分别收成：
  - 首页：`今天先做什么`
  - 资料：`适合发客户的资料`
  - 合集：`多条资料打包成一页`
  - 雷达：`谁值得跟进`
  - 我的：`资料、资源、消息和个人资料入口`
- 服务场景下新增 `我的名片` 显性入口：
  - 我的页身份卡下方显示紧凑名片入口，点击进入资料页并只看电子名片。
  - 首页服务场景的次动作从 `做个人名片` 改成 `我的名片`，点击进入资料页名片筛选。
  - 资料页支持 `business_card` 和 `service_offer` 两个细分入口筛选，空态分别引导做名片或做服务方案。
- 资料页“新增资料”在名片筛选下直接打开名片编辑，在服务方案筛选下打开服务方案编辑，避免名片/方案入口再次混杂。
- 本轮验证：
  - `node --check` 已覆盖首页、资料、我的、合集、雷达五个 Tab 的 JS 文件。
  - `git diff --check` 已覆盖本轮修改的 WXML/WXSS/JS 文件。

## 2026-06-28 群资源库添加微信群前端 MVP

- 资源库当前无继续收口阻塞，本轮把我的页 `群资源库` 从提示态改为真实页面入口。
- 新增小程序页面 `pages/group-resource-library/index`：
  - 顶部显示 `群资源库`、积分胶囊和搜索框。
  - 支持热词搜索：房源对盘、团购宝妈、老板资源、本地商家、供应链、行业交流。
  - 支持 `添加微信群`：上传群二维码、填写城市、选择群类型、用途、人数、活跃度、入群备注。
  - 发布成功本地奖励 `+20 积分`。
  - 新用户首次进入本地初始化 `100 积分`。
  - 查看二维码消耗 `30 积分`；同一个群再次查看不重复扣分。
  - 群列表展示城市、类型、人数、活跃度、用途标签、查看次数和确认数。
- 本轮只做前端本地 MVP：
  - 数据暂存在本机小程序 storage。
  - 未接后端持久化、审核、二维码识别、跨用户共享、积分明细和举报处理。
  - 后续正式 V1 仍需按 `docs/stage2-docs/24-group-resource-library-v1.md` 接后端。
- 已验证：
  - `node --check miniprogram/pages/group-resource-library/index.js`
  - `node --check miniprogram/pages/profile/index.js`
  - `node --check miniprogram/components/custom-nav/index.js`
  - `app.json` 和页面 `index.json` 可解析。
  - `git diff --check` 覆盖本轮修改文件。

### 群资源库首屏小修

- 搜索区按钮缩短并固定在卡片内，避免真机上按钮背景和文字溢出页面。
- `添加微信群` 卡片右侧按钮改短，只保留 `添加/收起`。
- 空态按钮从 `添加微信群` 改为 `去添加`，减少横向占用。
- 积分胶囊下方新增 `积分规则` 入口，弹层展示首次进入 `+100`、发布微信群 `+20`、查看二维码 `-30`。

### 群资源库发布流程按四步稿重做

- 用户反馈原先没有看到参考图里的发布流程，且搜索仍有溢出。
- 已把 `添加微信群` 从首页内联表单改为四步发布流程：
  - 第 1 步：上传识别，展示二维码上传区和识别结果。
  - 第 2 步：点选信息，按城市/区域、群类型、用途、人数区间、活跃度、自定义标签点选。
  - 第 3 步：有效期确认，支持 1 天、3 天、5 天、7 天，5 天为推荐。
  - 第 4 步：发布成功，展示获得 20 积分、群卡片、后续动作。
- 搜索框改成一个完整胶囊：输入区 + 内部搜索按钮，避免右侧按钮再溢出屏幕。
- 统计位置保留，但不使用效果稿里的假数字，改为真实本地数据 `当前新增 X 个群 · Y 个确认可进`。

### 群资源库积分与删除规则修正

- 用户指出：发布群后未确认前不应直接给积分，应该按规则等待两人加入确认或后台确认。
- 已把发布奖励从“直接到账”改为“冻结 20 积分”：
  - 顶部显示可用积分和冻结积分。
  - 列表卡片显示该群冻结积分。
  - 发布成功页改为 `冻结 20 积分`，并说明 `2 人确认成功进群或后台确认后，冻结积分会转为可用积分`。
  - 旧本地测试数据如果已经把发布积分直接加到账户，会在加载时迁移为冻结积分并扣回一次。
- 已给自己发布的群资源增加 `删除` 按钮：
  - 删除前二次确认。
  - 删除后不再展示，也不会获得该群确认积分。
- 积分规则弹层补充惩罚与退分机制：
  - 确认失效后退还查看者 30 积分。
  - 虚假/风险群下架会扣回并罚分。
  - 超过 5 天多人反馈失效扣 20 积分。
- 补充群信息页城市选择改为更明确的城市选项：长沙、全国、广州、深圳、上海、北京、其他，并增加提示“点选一个城市；其他城市先选其他”。

### 群资源库列表卡与城市选择修正

- 用户反馈最近可查看卡片底部统计被按钮挤压成竖排，真机观感变形。
- 已把群卡片底部改成两行：
  - 第一行展示 `查看 / 确认可进 / 冻结积分`。
  - 第二行展示 `删除 / 查看二维码` 操作按钮，避免按钮挤压统计文字。
- 补充群信息页城市选择从自定义城市按钮改为微信小程序原生 `picker mode="region"`：
  - 保留 `全国` 快捷选项。
  - 默认使用当前 MVP 的城市位 `长沙市`。
  - 后续如需真实自动定位到用户所在城市，需要再接定位反查城市服务。

### 企业资源搜索前端收口

- 我的页资源工具文案进一步统一：
  - 群资源库：找渠道。
  - 企业资源搜索：找客户 / 合作方。
  - 行业黄页：找名单，近期开放。
  - 商机线索：找机会，近期开放。
- 企业资源搜索页补充结果感和规则说明：
  - 搜索结果标题增加 `先看状态和风险`。
  - 未搜索和无结果分别展示轻空态。
  - 企业详情页新增建议条：先看司法风险和历史变更，再决定是否保存。
  - 增加积分规则弹层，说明候选免费、基本信息 -10、深度查询 -20、24 小时缓存不重复扣、保存资源卡免费。
  - 保存成功文案改为 `已加入你的企业资源池`，强化资源沉淀心智。
- 本轮仍是前端流程版：
  - 未接真实 Tianyancha MCP。
  - 未接后端企业资源保存、真实积分、后端缓存和频控。

### 我的页资源工具右上角积分与四宫格压缩

- 用户反馈资源工具占用首屏空间过大，且积分展示应更接近效果图。
- 已把我的页资源工具改为一行 4 个紧凑入口：
  - 群资源库
  - 企业资源搜索
  - 行业黄页
  - 商机线索
- 右上角改为积分区：
  - `100` 数字放大显示。
  - 有冻结积分时显示 `冻结 X`。
  - `积分规则` 放在右上角同一区域。
- 我的页新增资源积分规则弹层：
  - 查看群资源 -30
  - 发布群冻结 +20
  - 企业基本信息 -10
  - 企业深度查询 -20
  - 24 小时缓存不重复扣

### 帮助与反馈共创中心前端版

- 用户确认公司名和核心心智是“就互动”，希望更凸显用户能动性：愿意接受反馈，并对有效 Bug 和建议给足够多奖励。
- 新增小程序页面 `pages/help-feedback/index`：
  - 顶部强调 `就互动共创奖励`。
  - 明确有效 Bug 和被采纳建议奖励 `100-1000 积分`。
  - 支持提交四类反馈：问题反馈、功能建议、使用咨询、积分申诉。
  - 表单包含标题、详细描述、关联页面、联系方式和最多 3 张截图。
  - 提交后进入 `我的反馈`，展示状态、时间、反馈类型和预估奖励。
  - 我的页 `帮助与反馈` 入口改为真实页面跳转，并在入口文案中提示采纳奖励。
- 当前是前端本地闭环：
  - 反馈记录暂存小程序本地 storage。
  - 未接后端反馈表、管理端处理、站内消息通知和统一积分账本。
  - 后续真实奖励必须由后端积分流水发放，不能只靠前端展示。

### 部署前文字减负收口

- 首页、资料、合集、雷达、我的页按“少解释、强动作”统一压缩文案：
  - 首页强调 `谁动了，我先知`、`先盯谁，再跟谁`。
  - 资料页去掉大段 AI 说明，改为轻提示条，保留“发客户前，先看状态”。
  - 合集页强调 `多条资料，一页发客户`。
  - 雷达页强调 `先看谁值得跟`、`高意向排前面`。
  - 我的页身份、资源工具和场景区文案压短，保留帮助与反馈的奖励心智。
- 企业资源搜索页压成工具语气：
  - 顶部改为 `先搜企业，再看风险`。
  - 详情建议改为 `先看风险，再保存`。
  - 重复的底部积分说明删除，统一放进积分规则弹层。
- 帮助与反馈奖励卡副文案改为 `被采纳，就给奖励`，保留 `100-1000 积分` 的共创激励。

### 部署前自测与前端文案卫生

- 上线前复扫小程序前端展示文案，清理用户不该看到的开发态表达：
  - `后端未更新，请先部署新版后端` 改为 `服务正在更新，请稍后再试`。
  - 订单、客户看板错误提示改为用户可理解的服务更新提示。
  - 企业资源搜索保存页移除 `生成企业摘要卡（后续）` 按钮，数据来源文案去掉 `API Key`。
  - 登录页本地调试按钮文案从 `本地测试登录` 改为 `便捷登录`。
  - 若干 `后续` 类非必要前端提示改为 `之后 / 稍后 / 更多`。
- 验证结果：
  - 小程序全量 JS `node --check`：通过。
  - 小程序 49 个 JSON 文件解析：通过。
  - 前端敏感文案复扫：只剩内部变量判断 `openid_本地测试用户`，不会展示到用户界面。
  - `git diff --check` 覆盖小程序和本轮文档：通过。
  - `.venv312/bin/python -m compileall backend/app backend/tests`：通过。
  - `.venv312/bin/python -m pytest backend/tests/test_app.py -q`：112 passed。
  - `.venv312/bin/python -m pytest backend/tests -q`：149 passed。

### 2026-06-28 生产后端稳妥部署

- 本次没有在服务器执行 `git pull`，采用本地已验证代码定向同步到生产服务器。
- 部署前服务器状态：
  - `/dev/vda2` 使用率约 61%，可用约 23G。
  - `teambuy-postgres-1` 运行且 healthy。
  - 旧 `teambuy-backend-1` 本地 `/health` 正常。
- 生产备份：
  - 备份目录：`/home/ubuntu/teamBuy/backups/pre-deploy-20260628-062157`
  - 已备份 `docker-compose.yml`、`backend/app`、`backend/tests`、`backend/requirements.txt`、`backend/Dockerfile`、生产 `backend/.env` 和 `backend/secrets`。
- 同步范围：
  - `backend/app/`
  - `backend/tests/`
  - `backend/requirements.txt`
  - `backend/Dockerfile`
  - `backend/.env.example`
  - `docker-compose.yml`
  - `backend/mock/` 中除 `media/` 和 `runtime-state.json` 外的文件
- 未覆盖：
  - 生产 `backend/.env`
  - 生产 `backend/secrets/`
  - Docker volumes
  - 媒体目录
  - 运行态数据
- 回滚镜像：
  - 已给旧镜像打标签 `teambuy-backend:before-deploy-20260628-062238`。
- 构建和重启：
  - `docker compose build backend` 成功。
  - `docker compose up -d backend` 成功。
- 验证：
  - 服务器本地 `http://127.0.0.1:8002/health` 正常。
  - 公网 `https://teambuy.lifelove.top/health` 正常。
  - 公网 `/api/wecom/config-check` 正常，企业微信客服配置 ready。
  - 公网 `/api/wecom/customer-service-config` 正常。
  - `/api/wecom/archive/config-check` 在服务器本地正常，会话存档配置 ready。
  - 管理接口错误 token 返回 403，符合预期。
  - 重启后等待一个周期，容器仍稳定，日志未见异常堆栈。
- 部署后服务器状态：
  - 根盘使用率约 69%，可用约 18G。
  - 当前新镜像 `teambuy-backend:latest` 约 2.8GB。
  - 未执行 Docker 大清理，保留旧镜像用于回滚。

注意：

- 本次只部署生产后端；小程序仍需用户在微信开发者工具里上传体验版/提交审核。
- 小程序订阅消息主动推送尚未落地，当前是站内反馈、客户看板、雷达提醒和企业微信导入完成文本通知。

## 2026-06-28 PC 运营后台 V1 已落地

本轮新增：

- 新增开发文档：
  - `docs/stage2-docs/29-pc-ops-console-v1.md`
  - `docs/qa/PC运营后台V1_测试清单与验收标准.md`
- 新增 PC 端运营后台入口：
  - `GET /ops`
- 新增后台接口：
  - `GET /api/ops-admin/overview`
  - `GET /api/ops-admin/user-leaderboard`
  - `GET /api/ops-admin/content-leaderboard`
  - `GET /api/ops-admin/system-queue`
  - `POST /api/ops-admin/group-upload/preview`
  - `POST /api/ops-admin/group-upload/batches`
  - `GET /api/ops-admin/group-upload/batches`
  - `GET /api/ops-admin/feedback`
  - `POST /api/ops-admin/feedback`
  - `PATCH /api/ops-admin/feedback/{ticketId}`
- 新增轻量运营存储：
  - `backend/app/services/ops_console_store.py`
  - 当前承接“群二维码批量上传批次”和“反馈工单”两类 PC 端数据。
- 新增后台静态页面：
  - `backend/app/static/ops-admin/index.html`

实现范围：

- 总览日报：今日新增用户、资料、合集、客户动作、展示页打开、通知、异常。
- 用户排行：按资料数、合集数、客户动作、打开数计算活跃分。
- 内容排行：合集排行 + 资料排行。
- 系统待处理：导入失败、待发送通知、媒体失败、同步失败。
- 群二维码批量上传：支持预览解析和保存批次。
- 反馈工单：支持创建、查看、回复、状态更新。

明确保留边界：

- 群资源库积分、企业资源搜索积分、帮助反馈前台提交，目前仍主要在小程序本地存储。
- 因此本次后台没有实现“真实全局积分余额修改”和“资源积分全局排行”。
- 页面已明确标注这些模块为待后端化，避免误导运营。

验证结果：

- `python3 -m compileall backend/app`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -k "ops_admin" -q`：4 passed。

## 2026-06-28 新增群二维码服务器上传交接文档

本轮补充：

- 新增 `docs/stage2-docs/30-group-qr-server-upload-handoff.md`
- 新增 `docs/prompts/group-qr-upload-codex-prompt.md`

文档用途：

- 让后续新开的 Codex 会话能直接接手“读取一批微信群二维码图片 -> 上传服务器 -> 生成图片 URL -> 整理成模板”的执行任务。
- 明确区分：
  - 二维码内容
  - 二维码图片 URL
- 提供一段可直接复制的标准提示词。

## 2026-06-28 小程序真机 UI 细节收口

本轮按真机截图修正三个影响观感的问题：

- 群资源库空态按钮：
  - `去添加` 改为短胶囊按钮，并强制居中。
  - 群资源库顶部不再重复展示 `100 积分 / 积分规则`。
- 资源积分展示：
  - 企业资源搜索顶部和详情页不再重复展示积分和积分规则。
  - 企业资源搜索扣分 key 改为复用群资源库同一资源积分 key，避免前端出现三套积分的错觉。
  - 积分总入口保留在 `我的页 -> 资源工具`。
- 雷达 / 首页按钮：
  - 雷达客户卡删除底部重复的 `复制话术 / 更多` 操作层，只保留 `下一步动作` 里的主按钮。
  - 首页机会卡删除黑色 `复制话术` 按钮。
  - 首页 `待发现` 空态去掉重复的 `先发一份资料` 第二行，只保留一句提示。

验证：

- `node --check miniprogram/pages/home/index.js`：通过。
- `node --check miniprogram/pages/visits/index.js`：通过。
- `node --check miniprogram/pages/group-resource-library/index.js`：通过。
- `node --check miniprogram/pages/enterprise-resource-search/index.js`：通过。
- `git diff --check` 针对本轮小程序文件：通过。

注意：

- 本轮是小程序前端代码调整，线上用户需要重新在微信开发者工具上传体验版/提交审核后才能看到。

## 2026-06-28 雷达动作与天眼查企业搜索修正

本轮修正：

- 雷达页客户卡：
  - 默认下一步动作从 `复制话术` 改为 `看详情`。
  - 点击客户卡或 `看详情` 进入客户看板访客页，用于查看浏览痕迹、客户动态和联系方式。
  - 保留 `发对比合集` 等明确业务动作；普通跟进不再强推复制话术。
- 我的页资源工具：
  - 积分规则新增 `冻结积分：确认可进后到账`。
  - 冻结积分继续显示在资源积分旁边，作为同一个资源积分体系的一部分。
- 企业资源搜索：
  - 新增后端代理接口 `GET /api/enterprise-resources/search`。
  - 小程序企业搜索页改为优先调用后端企业搜索接口，失败时再保留本地兜底。
  - 天眼查接入确认走 MCP 通道：`search_companies` 工具可用。
  - 天眼查 OpenAPI REST `searchV2` 用当前 key 返回 `无权限访问此api`，不能作为当前接入通道。

部署：

- 已在生产服务器 `backend/.env` 配置天眼查 MCP key 和 `TYC_MCP_URL`。
- 已同步并重建生产后端。
- 公网 `https://teambuy.lifelove.top/health` 正常。
- 公网 `https://teambuy.lifelove.top/api/enterprise-resources/search?keyword=长沙装饰&page_size=2` 已返回真实企业候选。

验证：

- `node --check miniprogram/services/api.js`：通过。
- `node --check miniprogram/pages/enterprise-resource-search/index.js`：通过。
- `node --check miniprogram/pages/visits/index.js`：通过。
- `python3 -m compileall backend/app/api/routes_enterprise_resources.py backend/app/main.py backend/app/core/config.py`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -k "enterprise_resource_search or location_geocode" -q`：4 passed。

## 2026-06-28 企业资源搜索积分减负

本轮根据真机测试反馈调整企业资源搜索扣分体验：

- 企业候选搜索继续免费。
- 企业基本信息、股东结构、司法风险、经营情况、历史变更、知识产权统一调整为 `5 分/项`。
- 企业详情页查询卡展示同步改为 `5分`。
- 我的页资源工具积分规则同步改为 `企业查询：-5/项`。
- 24 小时缓存仍然不重复扣分。

原因：

- 冷启动阶段需要让用户先体验到企业查询价值，同时让“查询会消耗积分”的心智足够清楚。
- 积分体系应鼓励试用和沉淀资源，深度查询可以轻扣，真正高价值能力后续再按会员/套餐承接。

验证：

- `node --check miniprogram/pages/enterprise-resource-search/index.js`：通过。
- `git diff --check` 针对企业资源搜索页和我的页规则文件：通过。

## 2026-06-29 企业微信智能机器人权限网关 MVP

本轮新增后端机器人权限网关骨架：

- 新增接口 `POST /api/robot/query`。
- 新增配置 `ROBOT_GATEWAY_TOKEN`，机器人入口调用后端必须带 `Authorization: Bearer <token>`。
- 网关把请求分成三类权限：
  - `public`：天气、帮助、产品说明等公开问题。
  - `self`：我的资料、我的合集、我的资源等个人数据，必须先绑定企微身份和小程序用户。
  - `room`：群日报、广告识别等群数据，必须带当前群 `roomId`。
- `self` 查询复用已有 `wecom_identity_bindings`：
  - `externalUserId/fromUserId -> ownerUserId`。
  - 查资料和合集时只使用绑定后的 `ownerUserId`。
  - 机器人请求不能直接指定任意用户 ID。
- 群里询问个人数据时返回 `private_required`，提示转私聊处理，避免把个人数据发到群里。
- 返回结果包含小程序路径：
  - 资料：`/pages/note-preview/index?id=...`
  - 合集：`/pages/showcase-view/index?id=...`
- 兼容 WorkBuddy API 插件的发送人识别：
  - Body 里没有 `externalUserId/fromUserId` 时，后端会读取请求头 `userid` 作为提问人身份。
  - WorkBuddy 参数配置可以只暴露 `text/chatType/roomId/limit`，避免让模型伪造或误填用户身份。
- 兼容 WorkBuddy 调试器的输出展示：
  - 返回体保留 `data` 结构，同时在顶层输出 `text/result/answer/content`。
  - 方便平台输出参数直接映射 `result` 或 `text`，避免调试器只显示空白。

验证：

- `python3 -m compileall backend/app/api/routes_robot.py backend/app/main.py backend/app/core/config.py`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -k "robot_gateway" -q`：3 passed。
- 生产接口用 `userid` 请求头、不传 Body 用户 ID 验证通过。
- 生产接口返回顶层 `result/answer/content/text` 验证通过。
## 2026-06-29 企业群日常运营内容方案文档

本轮新增：

- `docs/stage2-docs/31-enterprise-group-daily-operations-v1.md`

本轮明确：

- 企业群不再承担“继续分群”的动作。
- 企业群固定为 3 类消息：
  - 中午更新
  - 下午入口
  - 晚间总结
- 企业群里的重点动作变成：
  - 看更新
  - 提交资源
  - 生成同款
  - 必要时私聊运营者

文档用途：

- 作为企业群机器人运营播报的交接文档。
- 作为后续产品承接页和群消息模板的统一口径。
## 2026-06-29 企业群机器人消息模板文档

本轮新增：

- `docs/stage2-docs/32-enterprise-group-bot-message-templates-v1.md`

本轮补充：

- 明确机器人当前实现边界是通过 API 按不同 `groupId` 下发不同模板消息。
- 外部群仍由运营本人手动转化，机器人不参与。
- 企业群模板按 4 类群配置：
  - 房源资源群
  - 商家合作 / 资源合作群
  - 企业资源 / 企业查询群
  - 内测反馈群
