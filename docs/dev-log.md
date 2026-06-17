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
