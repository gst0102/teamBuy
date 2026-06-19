# teamBuy 阶段性交接归档 4

更新时间：2026-06-20
工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`
当前分支：`main...origin/main [ahead 8+]`
当前状态：后端能力和小程序体验已分组提交；仍有文档归档待提交，`miniprogram/project.config.json` 和未跟踪 PDF 不纳入当前业务提交。小程序上传由用户手动完成，Codex 默认不要尝试微信开发者工具 CLI 上传。

## 1. 项目背景与目标

teamBuy 当前产品方向是“资料整理助手”，面向微信私域里的房产中介和团购团长。

核心目标不是做完整 CRM、电商平台、支付、库存、分账或 PC 后台，而是跑通这条主链路：

```text
用户把微信笔记 / 小程序卡片 / 聊天记录 / 图片视频等素材发给企业微信客服
  -> 后端通过企业微信客服回调、sync_msg 或会话内容存档拉取消息
  -> 统一转成 ContentObject
  -> content-to-note 规则识别并生成 UserNote 资料卡
  -> 小程序端认领、编辑、整理、生成客户页
  -> 分享给客户查看
  -> 客户浏览、留电话/微信、预约、下单/接龙、站内留言
  -> 发布者在小程序查看线索、订单、消息、接龙名单和客户资料
```

第一优先用户：房产中介。
第二优先用户：团购团长。

当前不做收款、正式订单结算、库存扣减、物流、退款、核销、分账；商品下单是“轻订单/意向单”，底层复用 `customer_actions`。

## 2. 当前阶段目标

当前阶段目标是把房源和商品两条可用场景跑稳，并继续加固企业微信导入解析这条主链路。

已基本进入可真机回归的范围：

- 房源资料：导入、结构化、客户页、地图、留资、预约、轻 SCRM、站内消息。
- 商品资料：商品展示基座、SKU、多规格、下单/接龙、买家/商家订单中心、站内消息。
- 企业微信归档：`weapp` 小程序卡片、`chatrecord` 聊天记录解析已开始插件化。
- 小程序体验：我的页分区、消息专区、订单入口、资料详情工作台。

下一步建议不要先做 P2 商品能力，也不要急着做 OCR；优先推进：

1. 当前本地改动提交/部署/体验版上传。
2. 双账号真机回归消息、订单、商品 SKU、房源客户页。
3. 企业微信归档解析器插件化收口。
4. 类型识别可解释和中置信人工确认。
5. 后续再做 OCR 图片识别底层能力。

## 3. 已完成的功能

### 3.1 后端基础能力

- FastAPI 后端骨架。
- 本地 JSON/mock 仓储与 PostgreSQL 目标仓储适配。
- `/health` 健康检查。
- 企业微信客服回调 GET/POST 骨架。
- 企业微信 `sync_msg` 客户端、cursor、任务锁、任务日志、媒体转存抽象。
- 企业微信会话内容存档接口 `/api/wecom/archive`，拆成 pull/process 流程。
- 会话存档媒体下载转存链路已实现：`sdkfileid -> GetMediaData -> 服务端媒体处理/转存 -> UserNote.media.url`。
- 用户身份第一版：mock 登录、微信小程序登录接口、企业微信来源绑定到用户。
- 后端会使用 `WECHAT_MINIAPP_APPID / WECHAT_MINIAPP_SECRET` 通过 jscode2session 换 openid；生产环境此前已补过配置并验证真实微信登录。
- 资源卡片、访问统计、浏览记录、实名接龙、接龙跟进、客户资料库、线索跟进等旧能力仍保留。

### 3.2 企业微信导入与解析

- 统一 `ContentObject -> content-to-note -> UserNote` 主链路。
- `weapp` 小程序卡片不再生成空笔记；保存为 `miniapp_card / sourceType=miniapp`，结构化保留 `appid/pagePath/houseCode/cityId/username/displayName` 等。
- 贝壳小程序卡片只有外壳字段时只给“可能是房源”的中置信提示，不伪造价格、户型、图片、经纬度。
- `miniapp_card` 不从正文提取手机号，避免 pagepath 长数字污染电话字段。
- 小程序卡切换为房源字段卡时会保留 `structuredData.miniapp`，客户页可跳转贝壳原小程序。
- 已新增 `backend/app/services/archive_message_parsers.py`，归档消息解析开始拆为注册式 parser。
- `chatrecord` 已能解析 `ChatRecordText` 文本并过滤图片/视频占位，给商品/团购识别提供文本基础。

### 3.3 多类型资料卡

- `UserNote.visibilityConfig.cardType/cardState/structuredData/typeSuggestions` 承载 typed card 第一版。
- 已支持类型：
  - `property_listing`：房源字段卡。
  - `groupbuy_product`：商品展示/团购兼容类型。
  - `text_note`：普通文本资料。
  - `link / miniapp` 来源资料。
- 高置信房源/商品直接进入工作台；中置信资料写入 `typeSuggestions`，小程序提示用户确认；低置信保留普通笔记。
- 房源识别已增强：标题里的小区名可参与高置信判断；正文里的户型、价格、面积、地铁、商圈、服务费等作为组合信号。
- 商品识别已增强：商品名、规格、价格、团购/接龙/下单/自提/配送等作为组合信号。

### 3.4 房源场景

- 房源工作台：房源字段、图片/视频、功能组、轻 SCRM、标签专题。
- 主动作：分享文案、转发给好友、客户页预览；保存分享图为弱入口。
- 客户页：房源图片、地图定位、电话咨询、留下电话/微信、预约看房、微信咨询、站内留言。
- 地图定位：
  - 客户页不展示经纬度数字。
  - 有默认地址时先通过后端腾讯地图地理编码解析坐标。
  - `TENCENT_MAP_KEY` 只允许放后端。
  - 地理编码失败时保留微信原生选点兜底。
- 房源状态：推广中 / 已租 / 暂停推广；客户页按状态关闭新增转化动作。
- 小程序卡片房源：贝壳原房源入口通过 `wx.navigateToMiniProgram` 打开，失败时复制房源编码兜底。

### 3.5 商品展示 + 团购/轻订单

- 产品决策：商品展示是基座，团购只是可选接龙模式。
- `groupbuy_product` 继续作为兼容类型，前台统一叫“商品展示 / 商品”。
- 商品字段放在 `structuredData`，SKU 配置放在 `structuredData.skuConfig`。
- 截止时间选填；为空时客户页不展示。
- SKU 支持属性组、选项、组合 SKU、价格、说明、售罄状态。
- 新增 SKU 时属性/选项默认空值 + placeholder，不再要求用户先删除“选项3”。
- 有 SKU 时商品主价格按 SKU 价格区间展示；无 SKU 时使用单一价格兜底。
- 客户页商品 SKU 有属性组时按分组按钮展示；无属性组时保留组合 SKU 卡片。
- SKU 售罄逻辑：某个选项只要仍有任一未售罄组合就可点；点击后如果当前完整组合不可买，会自动切到同选项下第一个可买 SKU；后端仍做最终售罄校验。
- `conversionConfig.enableGroupRelay=false` 时提交 `order-intent`。
- `conversionConfig.enableGroupRelay=true` 时提交 `relay-intent`。
- `order-intent / relay-intent` 都写 `customer_actions`，不投影到 `lead_reminders`，不进入轻 SCRM。
- 商品下单必填：SKU、数量、电话、地址。
- 商品下单选填：收货人、微信号、备注。
- 客户再次进入商品页，配置接口返回 `submittedPayload`，前端恢复已提交 SKU、数量和联系方式。
- 团长名单支持地址、电话、微信、备注展示；支持复制汇总、复制单条、复制电话/微信、拨号、发消息。
- 团长名单支持按 SKU 筛选；筛选只影响展示和复制，不改变底层数据。
- 我的笔记商品卡有“下单 N / 接龙 N”入口。
- 已补本地 mock 商品数据和接龙样例。

### 3.6 轻订单中心

- 订单中心第一版不是正式订单表，读取 `customer_actions.order-intent / relay-intent`。
- 新增后端订单接口：
  - `GET /api/orders?userId=...&role=buyer|seller`
  - `GET /api/orders/{orderId}?userId=...`
  - `PATCH /api/orders/{orderId}/status`
- 状态第一版：`submitted / contacted / completed / cancelled`。
- 买家“我的订单”：看自己提交的商品意向。
- 商家“订单中心”：看自己资料收到的下单/接龙。
- 普通用户不能查看他人订单。
- 商家可更新订单状态；买家不能更新商家订单状态。

### 3.7 站内消息

- 第一版为异步文本留言，不做实时 IM / WebSocket。
- 后端新增 `message_threads` 和 `message_records`。
- 线程绑定 `noteId`，可选绑定 `orderActionId`。
- 新增消息接口：
  - `GET /api/messages/threads?userId=...`
  - `POST /api/messages/threads`
  - `GET /api/messages/threads/{threadId}/messages?userId=...`
  - `POST /api/messages/threads/{threadId}/messages`
  - `POST /api/messages/threads/{threadId}/read`
- 前端插件化：
  - `miniprogram/plugins/message-plugin/index.js`
  - `miniprogram/components/message-entry/*`
- 商品页、房源页、订单详情、资料详情、我的页都可以进入消息。
- 消息详情页已改成微信式对话：
  - 当前登录用户消息在右侧、绿色气泡、头像在右。
  - 对方消息在左侧、白色气泡、头像在左，显示对方昵称。
  - 逻辑按 `senderUserId === 当前登录 userId` 判断，不固定买家/团长方向。
- 后端线程行返回 `participants`，包含 owner/buyer 的角色、昵称、头像。

### 3.8 小程序页面与体验

- 我的页已按“会员服务 / 笔记区域 / 线索订单 / 消息专区 / 开发测试”重构。
- 我的页入口包括我的资源库、我的笔记、专题、访问记录、待联系线索、客户资料库、我的订单、商家订单中心、消息专区。
- 小程序上传约定已写入 `AGENTS.md`：小程序预览、上传体验版、提交审核由用户在微信开发者工具中手动完成；Codex 默认不尝试 CLI 上传。
- 登录页区分真实微信登录和本地 mock 登录；本地 mock 不伪装成真实微信登录。
- 当前小程序 `apiBaseUrl` 已恢复生产 `https://teambuy.lifelove.top`，本地 mock 只作辅助。

## 4. 已修改/新增的文件

### 4.1 当前已修改文件

```text
AGENTS.md
backend/app/core/schema.sql
backend/app/main.py
backend/app/models/domain.py
backend/app/services/app_service.py
backend/app/services/bootstrap.py
backend/app/services/content_object_adapter.py
backend/app/services/repository.py
backend/app/services/skill_router_service.py
backend/mock/customer-actions.json
backend/mock/runtime-state.json
backend/tests/test_app.py
docs/decisions.md
docs/dev-log.md
docs/handoff-latest.md
docs/pitfalls.md
docs/project-memory.md
miniprogram/app.js
miniprogram/app.json
miniprogram/pages/login/index.js
miniprogram/pages/login/index.wxml
miniprogram/pages/note-actions/index.js
miniprogram/pages/note-actions/index.json
miniprogram/pages/note-actions/index.wxml
miniprogram/pages/note-actions/index.wxss
miniprogram/pages/note-edit/index.js
miniprogram/pages/note-edit/index.json
miniprogram/pages/note-edit/index.wxml
miniprogram/pages/note-edit/index.wxss
miniprogram/pages/note-preview/index.js
miniprogram/pages/note-preview/index.wxml
miniprogram/pages/note-preview/index.wxss
miniprogram/pages/notes/index.js
miniprogram/pages/notes/index.json
miniprogram/pages/notes/index.wxml
miniprogram/pages/profile/index.js
miniprogram/pages/profile/index.json
miniprogram/pages/profile/index.wxml
miniprogram/pages/profile/index.wxss
miniprogram/project.config.json
miniprogram/services/api.js
```

### 4.2 当前新增未跟踪文件/目录

```text
backend/app/api/routes_messages.py
backend/app/api/routes_orders.py
backend/app/services/archive_message_parsers.py
backend/mock/message-records.json
backend/mock/message-threads.json
backend/mock/user-notes.json
miniprogram/components/message-entry/
miniprogram/pages/message-thread/
miniprogram/pages/messages/
miniprogram/pages/order-detail/
miniprogram/pages/orders/
miniprogram/plugins/
企业微信客服服务须知.pdf
```

注意：`企业微信客服服务须知.pdf` 是未跟踪本地文件，当前不是业务代码改动；不要误删，也不要默认提交，除非用户明确要求。

## 5. 当前代码状态

### 5.1 Git 状态

- 当前分支：`main...origin/main [ahead 8+]`
- 后端能力已提交为 `feat: add lightweight orders and messaging backend`。
- 小程序体验已提交为 `feat: add miniapp orders and messaging flows`。
- 文档归档仍在本轮收口中，待生产部署结果补齐后提交。
- `miniprogram/project.config.json` 为微信开发者工具自动配置变化，本轮暂不纳入提交。
- 未跟踪 PDF `企业微信客服服务须知.pdf` 不纳入提交。

### 5.2 最近验证结果

已通过：

```text
node --check miniprogram/pages/message-thread/index.js
find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check
python3 JSON 解析检查 miniprogram/**/*.json
/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest backend/tests/test_app.py -q
/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall backend/app backend/tests
git diff --check
```

最近后端测试结果：`66 passed`。

本轮收口新增全量测试结果：`backend/tests` 为 `103 passed`。

注意：项目根目录 `.venv` 是 Python 3.9.6，直接跑 pytest 会因 `dataclass(slots=True)` 报错。后续请使用 Codex runtime Python 3.12：

```text
/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

### 5.3 部署状态

- 生产后端此前已部署过订单/消息相关能力，公网 `/health` 曾验证通过。
- 但当前本地最新改动包含后续 P1、消息参与者、聊天左右气泡等补丁，不能假设已经全部部署到生产。
- 小程序体验版/上传由用户手动在微信开发者工具完成；Codex 默认不要尝试 CLI 上传。

## 6. 已知问题和风险

### 6.1 当前未完成 / 不应编造完成

- OCR 图片识别尚未开发，只是讨论了后续技术方向：优先 PaddleOCR 自部署，腾讯云 OCR 可作为低置信兜底。
- 商品 P2 未开发，包括 SKU 图片、库存数字展示、批量导出、截止后自动关闭接龙、咨询点击记录、外链打开记录、正式 `order-core`。
- 正式支付、正式订单、退款、物流、核销、分账均未开发。
- 实时 IM / WebSocket 未开发，站内消息只是异步文本留言。
- 完整 PC 管理后台未开发。
- 小程序 CLI 上传不再默认尝试，需用户手动上传。

### 6.2 真实联调风险

- 企业微信真实导入是产品核心，不要把本地 mock 或手动添加当作最终上线通过。
- 企业微信 `weapp/chatrecord` 解析已增强，但更多企业微信消息形态仍可能需要 parser 扩展。
- 会话存档媒体真实图片/视频消息仍需生产真实验证。
- 小程序真机登录必须依赖后端 `WECHAT_MINIAPP_APPID / WECHAT_MINIAPP_SECRET`，不要把 mock 登录用户当成真实 openid 身份体系。
- 同一条消息在不同手机上左右方向相反是正确行为：当前登录用户在右，对方在左。只有两台手机使用同一个账号/mock user 时，显示才会不符合真实双人对话。

### 6.3 技术/代码风险

- 当前 worktree 很脏，提交前必须分组复核，避免把无关文件、`project.config.json` 自动改动、未跟踪 PDF 混入提交。
- `backend/mock/runtime-state.json` 改动很大，提交前需确认是否应纳入。
- `.venv` Python 版本过低，不适合跑后端测试。
- 旧 `Card/card-view/card-edit` 仍保留兼容，不要误删。
- 旧资源详情页不是 typed card 主流程，新资料应优先走 `UserNote` 和 `pages/note-edit/index`。
- `project.config.json` 可能被微信开发者工具自动改动，提交前需特别看 diff。

## 7. 用户已经确认过的产品/技术决策

- 产品名和方向：资料整理助手，不是交易平台。
- 第一优先房产中介，第二优先团购团长。
- 企业微信导入主链路是核心；小程序内不提供“发给客服”的主入口。
- 小程序上传、体验版、审核由用户手动完成；Codex 默认不要反复尝试开发者工具 CLI 上传。
- 长期架构：稳定基座 + 可插拔 Skill；企业微信入口采用快捷指令/菜单优先、规则其次、AI 兜底。
- 文字来源统一进入 `ContentObject -> content-to-note`；微信笔记、聊天记录、链接文章、手动文字、后续 OCR 都是 Input Adapter，不拆重复 Skill。
- 多类型资料卡：统一“收藏 -> 编辑 -> 整理 -> 生成”生命周期，但数据结构分型。
- 高置信自动进模板，中置信让用户确认，低置信保留普通笔记。
- 房源长标题通常是中介主动展示卖点，不自动拆标题、不改标题，只做排版容错。
- 贝壳小程序卡片只含外壳字段时，不伪造成完整房源；保留原小程序入口。
- 客户页链接是主分享路径，分享图只是辅助素材。
- 客户页动作使用客户语言，不用“留资”等内部术语。
- 商品展示是基座，团购接龙只是可选模块。
- `groupbuy_product` 暂时继续作为兼容类型，但前台叫“商品展示/商品”。
- 商品轻订单复用 `customer_actions.order-intent / relay-intent`，不新增正式订单表。
- 商品下单/接龙不进入房产 SCRM，不投影 `lead_reminders`。
- 商品下单电话和地址必填；微信号、收货人、备注可选。
- 商品/团购当前不做支付、库存扣减、核销、分账。
- 站内消息先做异步文本留言，不做实时 IM。
- 前端消息入口必须走 `message-plugin` 和 `message-entry`，后续新场景不要重复手写消息创建逻辑。
- 商品 P2 暂不急做；先推进主链路和解析稳定化。
- OCR 是后续图片识别底层能力，不是当前必须马上开发的业务场景；技术倾向首选 PaddleOCR 自部署，腾讯云 OCR 后续可作兜底。

## 8. 下一步建议执行顺序

### 8.1 立即收口当前改动

1. 重新做完整 diff 复核，按范围确认提交：
   - 后端能力：订单、消息、parser、schema、tests。
   - 小程序体验：商品 SKU、订单中心、消息、我的页、客户页。
   - 文档归档：AGENTS、project-memory、decisions、pitfalls、dev-log、handoff。
   - 本地杂项：`project.config.json`、mock runtime、未跟踪 PDF。
2. 跑验证：
   - 小程序全量 `node --check`。
   - 小程序 JSON 解析。
   - Python 3.12 `pytest backend/tests/test_app.py -q`。
   - Python 3.12 `compileall backend/app backend/tests`。
   - `git diff --check`。
3. 分组提交。建议至少三组：
   - 后端能力。
   - 小程序体验。
   - 文档归档。
4. 生产后端部署当前最新代码。
5. 用户手动上传小程序体验版。
6. 双账号真机回归：
   - 买家下单/接龙。
   - 商家订单中心。
   - 买家订单中心。
   - 双方站内消息，确认当前登录用户始终右侧。
   - 商品 SKU 售罄和筛选。
   - 房源客户页留电话/预约/消息。

### 8.2 下一阶段功能建议

1. 企业微信归档 parser 插件化收口：
   - 明确 parser registry。
   - `text/weapp/chatrecord/image/video` 归一输出。
   - parser 只负责 ContentObject，不直接写业务库。
2. 类型识别可解释：
   - 记录为什么判成房源/商品。
   - 返回命中信号、置信度、候选类型。
   - 方便用户测试时不再黑盒猜。
3. 中置信人工确认入口：
   - 普通资料卡上提示“像房源/商品/普通笔记”。
   - 用户一键切换模板。
   - 切换时保留 miniapp 元数据和原始内容。
4. 再考虑 OCR：
   - 第一版建议 PaddleOCR 自部署。
   - 只把 OCR 结果转为 ContentObject，不直接生成业务结果。
   - 低置信仍让用户确认。

## 9. 新 Codex 会话接手时的第一条提示词

```text
请先读取以下文件：

- AGENTS.md
- docs/project-memory.md
- docs/decisions.md
- docs/pitfalls.md
- docs/dev-log.md
- docs/handoff-latest.md
- docs/handoff-latest-4.md

然后执行：

- git status --short --branch
- git diff --stat

注意：

1. 小程序上传、体验版、提交审核由用户在微信开发者工具中手动完成；不要默认尝试微信开发者工具 CLI 上传。
2. 当前本地有大量未提交改动，请先完整 diff 复核，不要直接改代码。
3. 不要把未跟踪的“企业微信客服服务须知.pdf”默认纳入提交。
4. 项目根目录 .venv 是 Python 3.9.6，后端测试请使用：
   /Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
5. 当前重要主线是：先收口/提交/部署现有房源+商品+订单+站内消息能力，再推进企业微信归档解析器插件化、类型识别可解释和中置信确认。

请先输出：

1. 你理解的项目目标
2. 当前代码状态
3. 已确认的重要决策
4. 当前风险
5. 下一步建议执行顺序
```
