# teamBuy 阶段性交接归档

更新时间：2026-06-10  
工作目录：`d:\Desktop\myprojects\teamBuy`  
当前分支：`main`  
当前最新提交：`feat: persist lead reminders and webp media`  
本地状态：`main` 领先 `origin/main` 多个提交，尚未推送。本轮线索持久化第二阶段和 WebP 压缩改动准备提交。

上一轮已提交修复：
- `relay-list` 组件已增加接龙时间和跟进状态兜底格式化，资源详情页不再直接显示 ISO 时间或 `pending`。
- 资源详情页已绑定已接龙名单的 `标记已跟进` 和 `删除无效` 操作。
- 卡片编辑页素材上移/下移已修复旧 `sortOrder` 导致排序回弹的问题。
- 小程序内“发给客服”入口已改为“添加 / 快速入库”：中间 tab 指向手动添加资源页，`pages/imports/index` 仅作为外部导入后的“待认领导入”页。
- 小程序可见页面已移除“发给客服 / 立即发给客服 / 去发给客服”和可见 mock 导入按钮。
- 已验证：小程序 JS 静态检查通过，小程序 JSON 解析通过，`pytest backend\tests\test_app.py -q` 34 项通过。

本轮改动：
- 后端上传接口和企微媒体转存已接入媒体处理服务，图片通过 ffmpeg 转 WebP，视频通过 ffmpeg 转 H.264/AAC MP4。
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
- 已验证：`python -m compileall backend\app backend\tests` 通过，`pytest backend\tests -q` 60 项通过，小程序 JS/JSON 检查通过。

## 1. 项目背景与目标

teamBuy 是一个面向微信私域场景的小程序工具。当前产品名和 UI 方向为“悦享互动宝”。

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
- 禁止批量删除文件或目录，严格遵守 AGENTS.md。
```
