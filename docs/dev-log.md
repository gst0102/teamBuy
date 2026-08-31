# 2026-06-21

## 2026-09-01：积分核心与互帮互助订阅模板已部署生产

### 本轮部署

- 按腾讯云真实同步文档完成生产备份：`/home/ubuntu/teambuy-backups/20260901-073641-mutual-points-subscription/`；生产 API、后台 Worker、归档 Worker 当前镜像均保留 `rollback-20260901-073641` 标签。
- 将本地 `a605373` 中积分核心和互帮互助订阅配置所需的后端文件逐个同步到生产，并分别注入 API、后台 Worker、归档 Worker 热修复镜像；没有执行 Docker 网络构建。
- 生产环境仅追加互帮互助专用的模板 ID、字段映射和跳转页配置；原客户查看/留言提醒模板变量未替换，生产 `.env` 权限仍为 `600`、`root:root`。
- PostgreSQL 启动迁移已补齐积分核心所需的 `account_type`、幂等键、来源字段和索引；没有创建生产测试充值订单，没有调用 `test-confirm`。

### 验证与边界

- API、后台 Worker、归档 Worker、PostgreSQL 均 healthy；`8004 -> 8000`、本机 `/health`、`/health/db` 和公网 `https://teambuy.lifelove.top/health` 均通过。
- 容器已确认加载 `PointsCoreService`、互帮互助订阅模板配置和互助积分/订阅路由；目标后端文件的本地、生产 staging、三个新镜像哈希一致。
- 本次仅部署后端；小程序“我的”入口、订阅授权调用和其他互帮互助页面仍需用户在微信开发者工具重新编译、真机预览并手动上传体验版。
- 互帮互助任务、提交、验收、羊毛、评论、打赏和正式跨用户积分结算仍是本地演示边界，不能把本次部署描述为完整任务系统上线。

## 2026-09-01：任务短链接报错与原生分享入口收口（本地完成，待体验版验收）

### 本轮完成

- 修复三个任务发布入口的短链接体验：发布时会自动收纳输入框里已经粘贴的有效链接，不再因为用户忘记点击“添加入口”而误报“请添加小程序短链接”；手动添加入口仍保留去重、类型和数量校验。
- 发布页将案例提示放到输入框下方的常驻说明中：打开目标页面，点击右上角“…”→“复制链接”，粘贴后点击“添加入口”。placeholder 只保留格式示例，不承担关键操作提示。
- 发布成功后进入发布者任务管理详情；任务分享图准备成功后显示绿色“分享任务到微信群”按钮。任务管理卡片分享按钮同步改为微信绿，任务分享图片继续保持互帮互助暖风配色。
- 发布者管理详情和执行者任务详情都挂载任务分享 Canvas、`enableShareAppMessage` 和任务专用 `onShareAppMessage`；回调继续只返回当前任务详情路径和已登记的任务分享图。
- 为当前实际编译路由补齐页面级 `enableShareAppMessage`；首页、客户雷达、我的工具和互帮互助首页使用安全的产品封面，资料/名片/合集/商机/回应包等页面沿用各自已有的快照回调。编辑、支付、登录、客户隐私详情等没有稳定公开目标的页面不强行开放分享。

### 验证与边界

- 已通过全量小程序 JavaScript `node --check`、79 个小程序 JSON 解析、发布短链接收纳/校验 smoke、活动路由分享回调与页面配置一致性检查，以及 `git diff --check`。
- 本轮未部署生产、未上传微信体验版、未创建生产测试充值订单、未调用 `test-confirm`。生产后端、数据库、媒体目录和环境配置未修改。
- 真实微信开发者工具仍需人工确认：短链接只粘贴不点“添加入口”可正常发布、三种任务发布后均能看到分享按钮、右上角“…”可转发并能复制链接，最终聊天卡包含正确 `imageUrl` 和任务详情 `path`。

## 2026-08-31：互帮互助任务支持小程序与网页多入口（本地完成，待后端/真机验收）

### 本轮完成

- 新增统一 `taskLinks` 模型和解析器：兼容历史 `shortLink`，识别微信小程序短链接与 HTTPS 网页链接；普通任务可以同时挂小程序和网页入口。
- 发布页改为“任务入口”编辑区，支持入口标题、添加/删除和最多 6 个入口；小程序任务仍要求至少一个小程序入口。
- 执行者详情和发布者管理详情统一展示入口卡片：小程序使用 `wx.navigateToMiniProgram`；已配置业务域名的 HTTPS 进入专用 `web-view`；其他 HTTPS 复制链接并提示使用手机浏览器。
- 任务大厅和任务管理卡片增加入口摘要；任务专用分享图的内容源同步带入口类型摘要，最终分享回调仍要求真实专用 `imageUrl` 和任务详情 `path`。

### 验证与边界

- 通过互帮互助 JS `node --check`、JSON/路由检查、WXML 结构检查、任务入口解析 smoke、分享回调反例检查和 `git diff --check`。
- 当前 `web-view` 白名单只包含 `teambuy.lifelove.top`。第三方域名不能仅靠代码加入，须逐个完成微信业务域名配置、HTTPS 和真机兼容验证；未配置站点统一走手机浏览器复制兜底。
- 本轮未修改生产环境、未部署、未上传微信体验版；任务、分享快照和积分仍是本地演示数据，好友跨设备访问需下一阶段后端接口与公开分享 token。

## 2026-08-31：任务大厅首页布局与可见范围修正（本地完成）

- 重排首页积分卡：积分信息留在左侧，“规则”和“首页排序”固定在右上操作区，不再因为弹性布局跑到卡片中间。
- 任务大厅默认布局改为 `2x` 双列；布局存储键升级为 v2，旧设备不会继续沿用之前的 1x 默认值，用户仍可切换回 1x。
- 移除任务大厅对 `ownerUserId` 的过滤，用户自己发布的任务也会显示并可以自行点击完成；已完成任务仍按当前用户的提交状态从可执行列表中移除。
- 同步更新架构、决策、避坑和交接文档；本轮未部署生产、未上传微信体验版。

## 2026-08-31：互帮互助任务详情按角色拆分设计（仅设计，未改业务代码）

- 复核微信好友分享截图：当前分享卡已经生成，但因为互帮互助任务的 `onShareAppMessage` 只返回标题和路径、没有任务专用 `imageUrl`，微信使用了详情页默认截图，因此出现长页面缩略图，不是任务分享卡渲染失败。
- 按第一性原理将详情页拆成两个目标：执行者页面负责“看懂并完成”，发布者页面负责“查看提交并验收管理”。两者共享 `MutualTask` 数据，但不共享操作区。
- 新增角色页面设计文档和视觉稿：`docs/stage2-docs/45-mutual-help-task-role-pages-v2.md`、`docs/stage2-docs/visuals/my-tools-mutual-help-role-pages-v2.svg`。
- 设计决策：好友分享链接默认进入执行者任务详情；发布者从“我的”进入任务管理。目标小程序卡仍是详情页内的本项目 UI，点击后调用 `wx.navigateToMiniProgram`，不伪造目标小程序原生分享卡。
- 本轮不修改业务代码、不部署生产、不上传微信体验版；后续实现前必须先接入服务端任务查询、角色权限、任务分享快照和跨用户图片链路。

## 2026-08-31：互帮互助任务分享入口与发布后直达详情（本地完成，待后端与真机验收）

- 积分卡的“规则”固定在卡片右上角，字号调整为更易读的 24rpx，保持按钮固定宽高和上下左右居中；深色模式同步适配。
- 发布任务成功后不再先回任务大厅，而是直接进入刚发布任务的详情页；详情页增加“分享给好友”原生分享按钮，并由 `onShareAppMessage` 返回当前任务详情路径。
- 分享给好友的对象是“资料整理助手任务详情卡”。好友打开后先查看任务说明和验收标准，再点击详情里的目标小程序卡片，由 `wx.navigateToMiniProgram({ shortLink })` 进入发布者提供的小程序；不能由本小程序伪造目标小程序的原生分享卡。
- `getTask(taskId)` 对带 ID 的深链只接受精确匹配，不再把未知分享 ID 静默替换为第一条演示任务，避免好友看到错误任务。
- 当前仍未接入互帮互助后端任务接口、分享快照和跨用户媒体；本地分享只能验证回调对象和同设备详情链路，不能宣称跨设备任务分享已经完成。
- 本轮未部署生产、未上传微信体验版；目标小程序跳转和微信好友真实聊天卡仍需用户在真机/开发者工具中验收。

## 2026-08-28：分享与列表链路收口修复（本地完成，待人工验收）

- 修复资料库和合集“发出后不置顶”：最近排序现在使用最新发送/编辑/创建活动时间，发送成功后立即重排并更新本地缓存。
- 修复新资料被旧资料库元数据缓存遮挡：资料创建、图片入库、编辑、发布、快照保存等 API 统一失效 `resourceStore` 卡片缓存；资料刷新请求增加 owner generation，旧响应不能回写。
- 修复合集编辑页清理错误缓存键，同时清理旧键和 `v2` 环境隔离键。
- 加强统一分享插件：无明确目标 path 或目标为资料库路径时直接拒绝，避免任何遗漏调用回退到错误页面截图。
- 自测：全量小程序 JS 语法、JSON、Python 编译、`git diff --check`、资料缓存失效 smoke、旧刷新响应 generation smoke、分享路径门禁 smoke 均通过。当前环境没有 pytest 和 Docker，未虚报后端全量测试；历史后端结果保留在之前交接记录中。
- 本轮未部署生产、未上传微信体验版；需要用户按交付清单重新编译上传后人工验证真实聊天卡片和列表返回状态。

## 2026-08-28 最新：名片与合集模板接入旧资料和新资料

- 共享 `share-snapshot` 新增模板 revision 指纹：名片和合集的当前 v10 模板变化会让历史 v10 JPG 进入 stale 状态，旧资料在下一次发送前重新生成。
- 合集列表、编辑和公开展示统一使用同一个来源构造器；按可见资料顺序选第一张有效图片，服务端 owner/public payload 同步补齐媒体首图。
- 公共合集响应新增分享图 fingerprint；资料详情页和合集详情页均先完成当前指纹门禁，再开放原生分享，避免旧图或缺少 `imageUrl` 时被微信截取资料列表。
- 本轮未部署生产后端、未上传微信体验版；部署后仍需清缓存、重新编译，并分别验证旧资料重发、新资料、无图资料、有图资料、名片和合集。

## 2026-08-28 14:31：生产已切换分享图 v10 后端

- 生产 API、后台 worker、归档 worker 已全部切换到 `share_card_v10`；本次没有执行 Docker 网络构建，只基于当前生产镜像注入经过核对的 `app_service.py` 单行版本变更。
- 切换前已备份 Compose 和 v9/v10 源码：`/home/ubuntu/teambuy-backups/20260828T063111Z-share-v10`；三个旧镜像均保留 `rollback-20260828T063111Z` 回滚标签。
- 三个容器内 `app_service.py` 哈希均为 `d4b33d68a5b631f23615202027b1d8970a2a76af8db521f37e531ad9fa095090`，且均确认 `SHARE_SNAPSHOT_STYLE_ID = "share_card_v10"`。
- `8004 -> 8000` 端口、PostgreSQL、本机和公网 `/health`、`/health/db` 均通过；worker 保持运行，归档 worker 最近日志无错误。
- 本次只部署后端，未上传微信体验版。前端仍需清缓存、重新编译并上传 `20260828-share-card-v10`，再用新消息验证真实微信卡片。

## 2026-08-28 最新：分享图 v10 改为有图大图优先/无图信息版式（本地开发）

- 非名片资料和合集现在按真实主图分成两个展示族：有图进入 `image_first`，主图占固定 750×600（5:4）JPG 卡片主体；无图进入 `info_first`，只绘制类型、标题、摘要和业务字段，不伪造图片。
- 图片资料采用保留完整画面的模式，房源、商品、服务、链接和合集采用大图封面模式；所有文字继续按固定行数和 Canvas 实际宽度截断，避免卡片变形。
- 分享样式版本升级为 `share_card_v10`，客户端构建标识升级为 `20260828-share-card-v10`。旧 v9 快照不再被当前分享入口复用，重新进入发送入口后按当前资料版本生成 JPG。
- 仍保留电子名片的 `identity_first` 专用布局；历史资料、历史快照和历史微信消息不删除、不改写，只清理当前运行时不再使用的小图渲染函数。
- 本轮已完成代码实现，尚未部署生产后端，也尚未上传微信体验版；下一步先完成本地定向测试和分享回调对抗式审查，再部署后端 v10 并由用户重新编译上传体验版。

## 2026-08-28 最新：分享图改为“真实主图优先 + 固定 5:4 JPG 模板”

- 非名片资料不再只显示类型图标：文字资料、图片资料、房源、商品、服务、链接和合集有可用主图时，先把主图下载到 Canvas 的固定图片区域，再叠加类型、标题、摘要和最多三个字段；无图时仍使用对应类型的信息模板。
- 主图采用固定区域 `aspectFill` 裁切，不直接把原图交给微信，非名片继续导出 750×600 JPG，避免原图比例不一致导致卡片变形或微信截图资料列表。
- 服务端已有 `/api/uploads/share-snapshot` 和 `share_card_v9` 后端无需新增部署；主图被纳入分享指纹，旧 v9 无图快照会在下一次准备分享时自动失效并重新生成。
- 合集列表和合集编辑页同步选择第一条资料主图或 banner；名片分享 key 改为包含完整快照指纹，旧名片不需要重建，重新进入“我的”页即可重新准备当前 v9 快照。
- 本地验证：全部小程序 JS `node --check`、JSON 校验、分享模型 smoke、Canvas JPG smoke、分享链路对抗式 smoke、后端分享/媒体定向测试 `6 passed`、`git diff --check` 通过。
- 本轮只修改小程序分享源与渲染链路，没有重新部署后端，也没有上传微信体验版；需要在开发者工具重新编译上传后，用一条有图资料、一条无图资料和名片各发送一条新消息验收。

## 2026-08-28 12:39：生产已部署分享 JPG 上传与 v9 快照后端

- 按生产热修复路径完成部署，未执行 Docker 网络构建；备份目录为 `/home/ubuntu/teambuy-backups/20260828T043920Z-share-v9`，未覆盖生产 `.env`、密钥、媒体目录或数据库卷。
- API、`backend-worker`、`archive-worker` 已同步切换到 `share-v9-20260828T043920Z` 镜像；三个旧镜像分别保留 `rollback-20260828T043920Z` 标签。
- 运行态确认 `/api/uploads/share-snapshot` 已注册，`process_share_image()` 可用，服务端样式为 `share_card_v9`；容器内 4 个部署文件哈希与本地 staging 完全一致。
- 8004 端口、PostgreSQL、本机 `/health`、`/health/db` 和公网 `/health` 全部通过；容器内实际 PNG→JPG 处理 smoke 通过。未执行真实账号上传，公网未登录请求返回 401，符合认证门禁。
- 小程序体验版尚未由本轮自动上传。下一步在微信开发者工具清缓存并重新编译当前前端，刷新资料后点击“重试分享图”，按钮成功生成后应恢复为“发客户”，再发送新消息验收 JPG 卡片。

## 2026-08-28 11:57：所有资料显示“重试分享图”，确认生产未部署 JPG 上传链路

- 真机截图中资料列表的“重试分享图”表示新分享图准备失败，不是按钮样式丢失；新链路在快照未 ready 时会隐藏“发客户”，避免微信再次把资料列表截图当封面。
- 线上只读核对确认 `teambuy-backend-1` 仍为 2026-08-27 21:17 创建的旧镜像；容器 `/app/app` 中没有 `/api/uploads/share-snapshot`、`process_share_image` 或 `share_card_v9`。生产健康检查正常，但分享图上传/处理代码尚未进入容器。
- 因此当前失败点是前后端版本不一致：小程序已调用新 JPG 上传接口，生产后端仍是旧接口。雷达 count-only 已部署，所以雷达变快与本次分享失败是两条独立链路。
- 下一步必须按部署文档备份并部署后端新代码，部署后先用已登录请求验证分享上传返回 `image/jpeg`，再重新编译上传小程序并新发消息；历史聊天卡片不会自动改变。

## 2026-08-28：全量分享链路收口为固定模板 JPG（本地完成，待部署与体验版验收）

- 资料、图片资料、链接、房源、商品、服务方案、电子名片和合集现在都只走 `miniprogram/plugins/share-snapshot/index.js`；非名片统一使用固定 750×600（5:4）信息模板，名片使用固定 600×480（同为 5:4），不再按“有主图”直接复用原图。
- Canvas 导出固定为 JPG，并通过新增后端 `/api/uploads/share-snapshot` 处理为 `image/jpeg` 后再保存快照；普通资料/附件上传接口仍保持原来的 WebP 策略。分享图上传跳过普通媒体的原始哈希命中，避免把旧 WebP 当成分享图返回。
- 已删除运行代码中的 `shareDirect`、`original_media` 和 note-edit 页面原图兜底；旧 `universal-share` 模块此前已删除。未就绪时仍阻止原生分享，不返回资料库/首页截图路径。
- 本次收尾又移除了名片 `share_card_v4`、图片资料专用旧快照校验、`resource_default` 旧别名和列表按钮未使用的封面参数；公开合集命中旧缓存快照时也会清空旧分享图字段。运行代码只保留 v9 固定模板链路。
- `share_card_v9` 已作为新样式版本，旧 v7/v8 快照会被判定为过期并重新生成。定向分享 smoke、后端分享图测试 4 项、全量后端测试 301 项、69 个 JSON 和全部小程序 JS 静态检查通过。
- 本轮尚未部署生产后端，也未上传微信体验版；必须先部署后端新上传接口，再清缓存、重新编译并上传小程序，用全新消息验证真实聊天卡片。

## 2026-08-28 06:28：v8 分享仍退回资料库截图，发现 WebP 兼容风险

- 生产 06:27（北京时间）的 `library_send_customer` 事件对应 `note_11a9ec9b67`，数据库当前快照已是 `share_card_v8 / ready`；但聊天截图仍是资料库页面，截图中的“你是”对应另一条资料 `note_cda9ab4d89`。
- 直接下载生产 v8 `imageUrl` 验证为 600×480、`Content-Type: image/webp`；当前后端上传入口会把图片统一处理为 WebP。分享事件已写入不等于微信最终采用了 `imageUrl`，当前优先怀疑原生分享图格式兼容性，下一步应为分享快照提供 PNG/JPG 输出并再次真机验证。
- 全量页面、分包和运行时扫描未发现第二份 `pages/library/index`、`universal-share` 或旧列表兜底回调；本轮只完成排查和文档记录，未修改后端、未部署、未上传体验版。

## 2026-08-28 06:01：分享图比例与旧快照复用复核

- 生产 06:02（北京时间）`library_send_customer` 记录对应 `note_6dee30f9ad`，服务端保存的是 `share_card_v7 / ready`、750×460 WebP；URL 返回 200，但 750×460 不是微信聊天分享卡常用的 5:4 长卡比例，微信展示时会裁掉右侧内容。
- 当前资料库列表和客户页源码没有继续返回资料列表路径作为分享图；旧文案“资料分享图准备中，请稍后再试”也不在当前运行源码。截图中的资料列表卡仍应按历史消息/旧体验包/旧回调分开判断，不能用当前 v7 图片是否可访问替代最终回调取证。
- 无图信息卡统一升级为固定 750×600（5:4）画布，标题和摘要最多两行、超长字段按绘制宽度使用 `...`，内容区增加裁剪边界；分享样式版本从 `share_card_v7` 升为 `share_card_v8`，使所有旧 v7 无图快照失效并按当前 revision 重新生成。
- 本轮只修改小程序分享渲染与版本校验，没有修改后端、没有部署生产、没有上传体验版。客户端构建标识更新为 `20260828-share-card-v8`；体验版必须清缓存、重新编译后，先等待 v8 分享图准备完成，再新发一条消息验收。

## 2026-08-28 05:50：分享卡片后台记录复核

- 生产日志确认 05:44、05:51 的 `note_6dee30f9ad` 分享事件均从 `library_send_customer` 写入；生产资料快照为 `share_card_v7 / ready`，不是旧 v5/v6。
- “雪花肥牛”和“你是”对应的 v7 `imageUrl` 均为本站 HTTPS WebP，公网返回 200；下载检查后的图片是新固定模板，不是资料列表截图。
- 05:50 附近没有新的 `PATCH /api/notes/*/share-snapshot`，因为这两条资料已经有可复用的 v7 快照；当前服务器没有重新生成旧分享图。
- 截图中的“资料分享图准备中，请稍后再试”不在当前小程序源码、`HEAD` 或后端运行代码中，当前阶段不再继续改后端分享快照；需要核对微信最终使用的体验包/历史消息和实际 `onShareAppMessage` 返回值。

## 2026-08-28 05:44：部署后复核分享旧文案

- 用户截图仍出现“资料分享图准备中，请稍后再试”；该完整旧文案在当前小程序源码、`HEAD` 和后端运行代码中均不存在，当前资料库回调使用“资料分享图正在准备，请稍后再发”并在无图时返回 `null`。
- 因此该截图不能证明当前源码仍保留旧逻辑，优先指向体验版未使用 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram` 这份工程、上传的不是最新构建，或截图中包含此前已经发送的历史消息。
- 生产后端已于本日 05:14 切换 count-only 版本；本次复核未再次修改代码或服务器。

## 2026-08-28 05:14：生产部署 count-only 雷达投影

- 已按 `docs/deploy/tencent-cloud-real-sync.md` 的范围热修复策略部署 `schema.sql`、`domain.py`、`repository.py` 和 `app_service.py`，未执行 Docker 构建，未覆盖生产 `.env`、密钥、媒体目录或数据库卷。
- API、`backend-worker`、`archive-worker` 已切换到同一批 hotfix 镜像，并保留 `rollback-20260827T211415Z` 回滚标签；本地、宿主机 staging、三个运行镜像的源码哈希一致。
- 生产数据库已自动创建 `customer_radar_summaries` 表，当前 0 行；该实现按用户首次摘要请求懒生成，后续请求才命中持久化 count-only 投影，首个冷请求仍可能慢。
- 本机和公网 `/health`、`/health/db` 均通过，8004 端口保持不变；本轮未上传小程序体验版，分享旧样式仍需重新编译上传 `20260828-share-radar-v2` 前端包后验收。

## 2026-08-28：全量迁移旧通用分享链路并删除旧模块

- 已将供需/商机/回应包 10 个页面从 `utils/universal-share.js` 迁移到 `plugins/share-snapshot/index.js` 的统一通用入口。
- 统一入口现在负责固定 Canvas、文本归一化、无图信息卡生成、分享菜单就绪门控、合法 `imageUrl` 校验和异步 generation 防旧结果覆盖。
- 旧 `miniprogram/utils/universal-share.js` 已删除；10 个页面的 canvas id/class 已统一为 `shareCardCanvas` / `.share-card-canvas`，回应包 demo 分支也补齐分享图准备。
- 历史日志中的 `universal-share` 只保留为历史事实；当前运行代码已无该模块引用。未部署生产、未上传体验版。

## 2026-08-28：生产与体验版版本不一致复核（本轮未部署）

- 复核生产 `teambuy-backend-1`：Python 3.12.14；生产 `app_service.py` 哈希为 `f0dc2a30c4026e46c0d0014907f874f4f878cf452550c842d29338227ca5d1b7`，本地最新文件哈希为 `b2f828fada4754f3fc5bb93cf80ee94ca87d30fa7ad5a1a32ba216169ec9c2`，两者不一致。
- 生产容器虽然已注册 `/api/scrm/customer-intelligence/summary`，但没有本地新增的 `CustomerRadarSummary/customer_radar_summaries` 计数投影；因此线上摘要仍会读取资料、动作和历史事件重算，四个数字慢的原因是后端版本未部署。
- 截图中的“资料分享图准备中，请稍后再试”与资料库列表截图对应旧前端无图回调；当前本地 `HEAD` 已把异常路径改到客户详情，但 4:05 测试包显然没有包含当前提交。客户端构建标识已更新为 `20260828-share-radar-v2`，用于下一次体验版确认。
- 活跃分享兼容链路仍包括 `share-snapshot`、`universal-share`、合集和供需/商机页面；没有发现可以只凭文件名安全删除的旧页面或插件。本轮未删除、未部署、未上传体验版。

## 2026-08-28：资料分享封面与雷达首屏性能排查（仅排查，未开发）

- 用户截图中的分享标题“资料分享图准备中，请稍后再试”与 `miniprogram/pages/library/index.js` 的无图回调分支一致；该分支返回 `/pages/library/index` 且不返回 `imageUrl`，微信因此可能使用资料库页面截图作为小程序分享卡封面。
- 当前确实使用微信原生 `open-type="share"` + `onShareAppMessage`，但封面图不是微信自动生成的产品卡片，而是应用生成/登记后通过 `imageUrl` 交给微信。没有有效 `imageUrl` 时，原生分享仍会继续，不能视为“已生成分享卡”。
- 已静态审查普通文字、图片、房源、商品、服务方案、电子名片、合集、供需/商机/回应包等入口：有真实主图的资料可直出主图；无主图的文字/业务卡依赖 Canvas 生成、上传和快照落库；多个回调仍存在“未就绪也返回分享对象”的兜底，均有出现列表截图或默认截图的风险。
- 雷达客户端已经有用户隔离的进程内摘要缓存、并发请求合并和跟进动作失效；但冷启动的服务端摘要仍读取资料、动作和历史事件，并执行三组客户画像投影，不是真正的 count-only 查询。缓存只能改善命中后的返回，不能解决首次计算慢。
- 生产只读核对：API/worker 容器使用 Python 3.12.14，宿主机 Python 3.10.12；生产 `app_service.py` 与本地不同，生产容器没有本地最新 `list_view_events_for_cards` 批量方法。当前本轮未部署、未上传体验版。
- 下一步最小方案：统一分享回调的“有效 `imageUrl` + 客户页 `path`”契约，未就绪时阻止原生分享；雷达增加真正的 count-only/预计算摘要并保持进程内缓存。上述方案本轮未实现。

## 2026-08-27：客户雷达跟进状态回退排查与前端竞态修复

- 生产排查结论：北京时间 11:33 的跟进操作请求均返回 200；对应 `lead_reminders` 已持久化为 `paused/following`，线上实时投影也返回 `following=2、abandoned=7`，没有数据库回滚或后端投影回退。
- 根因收敛为小程序端读取竞态：雷达旧请求可能在放弃/恢复操作之后返回，并用旧快照再次 `setData`；操作成功后也没有立即做一次服务端权威校准，因此页面会出现“过一会恢复原状”。
- 已修复：跟进操作开始前提升雷达请求代际并清理客户智能/详情内存缓存；旧响应自动丢弃；服务端操作成功后保留即时乐观反馈，并后台强制重读；连续操作失败回滚时按操作代际保护，不覆盖后续操作。
- 新增小程序构建标识 `20260827-radar-consistency-1`，请求通过 `X-TeamBuy-Client-Build` 传递；后端代码会回显并记录 SCRM 请求构建标识，便于确认体验版是否真正包含本轮代码。
- 已通过小程序相关 JS `node --check`、后端编译检查、`git diff --check` 和 `backend/tests/test_sales_scrm.py`（17 passed）。本轮前端修复仍需用户在微信开发者工具重新编译并上传体验版；生产后端当前数据投影已正确。

## 2026-08-25：修复资料页绑定消息被清空

- 根因：资料页调用 `/api/auth/wecom-bind-intent` 后，将返回的 `data.bindMessage` 错误重置为空字符串，导致弹窗只有步骤说明，没有消息区域和复制按钮。
- 已改为保留接口返回的当前用户专属完整绑定消息；首页原逻辑不变。
- 已通过两个页面的 `node --check` 和 `git diff --check`；小程序需重新编译上传体验版。

## 2026-08-25：绑定消息文案改为可直接理解的完整请求

- 绑定消息改为“我刚添加了资料整理助手，请帮我把我的微信账号和资料库绑定起来。绑定口令：TB-XXXXXX。绑定完成后，我发给你的图片、文件和链接会自动整理到我的小程序资料库。”
- 保留 `TB-XXXXXX` 作为唯一机器识别片段，用户复制的是完整消息，不再只看到一串难以理解的口令。
- 首页和资料库按钮文案统一为“复制绑定消息”，步骤说明明确要求整段复制发送。
- 已验证绑定口令、归档绑定测试通过；小程序首页和资料库 JS 检查通过。

## 2026-08-25：资料助手绑定回到复制动态口令方案（本地，待体验版上传）

- 根据真实企业微信链路限制，停止依赖添加客户事件发送动态小程序卡片；保留会话存档作为绑定确认通道。
- 首页和资料库打开“资料助手”时改为调用 `/api/auth/wecom-bind-intent`，生成当前用户专属的 `绑定资料助手 TB-XXXXXX` 口令。
- 引导弹层改为“添加企业微信 → 复制口令 → 粘贴发送给资料助手”；移除“点击绑定卡片”的文案和操作。
- 后端原有口令识别、一次性有效期和 `externalUserId -> openid` 绑定逻辑未改动；不会修改会话存档配置、生产 secrets 或 Petlove 项目。
- 已验证：绑定口令相关 pytest 通过，首页/资料库 JS `node --check` 通过，`git diff --check` 通过。
- 小程序需要用户在微信开发者工具重新编译并上传体验版后，人工测试真实添加和口令发送。

## 2026-08-25：拆分微信客服与会话存档环境变量

- 将客服 / 外部联系人回调变量改为 `WECOM_KF_CALLBACK_TOKEN`、`WECOM_KF_ENCODING_AES_KEY`，客服 API Secret 改为 `WECOM_KF_SECRET`。
- 会话存档只读取 `WECOM_ARCHIVE_CALLBACK_TOKEN`、`WECOM_ARCHIVE_ENCODING_AES_KEY`，取消对客服回调变量的复用。
- 更新 `.env.example`、客服配置清单、归档配置说明、部署迁移文档和相关测试；企业微信客服测试 54 passed。
- 已部署生产：生产 `.env` 已补充新变量，备份目录为 `/home/ubuntu/teamBuy/.deploy-backups/wecom-kf-callback-20260825011733/`；API 与同步 worker 已重启，健康检查 200。
- 公网签名联调通过：`GET /api/wecom/kf/teamBuy/callback` 返回 200，AES 解密响应与验证明文一致；用户现在可以在企业微信后台点击“保存”。
- 企业微信后台已成功保存回调并配置可信 IP；生产日志显示后台验证请求返回 200。
- 生产原有客服 Secret 已迁移到 `WECOM_KF_SECRET`，容器内实际获取 `access_token` 成功；下一步测试当前 `WECOM_OPEN_KFID` 对应客服账号的真实消息同步。

## 2026-08-24：客户详情改为后端定向读取并部署

- 根因：此前只有客户雷达聚合接口，详情页在多个聚合数组中由前端反查客户身份；不同投影使用 `user:xxx`、原始 ID、线索 ID 时会误报找不到客户。
- 新增后端 `/api/scrm/customer-detail`，沿用客户信息链开关、会员门禁和 owner/requester 校验，只返回单条 `customer + timeline + lead` 投影；服务端统一处理身份别名并校验线索归属。
- 前端客户详情页先校验会员状态，再调用定向接口；支付关闭时直接读取，支付开启且非会员仍进入会员页，支付开启且会员直接读取详情。
- 对抗式审查覆盖跨账号请求、收费非会员锁定、支付关闭放行、错误 `leadId/customerId` 串线和未知客户 404；相关 pytest 16 passed。
- 生产已备份并部署后端：`/home/ubuntu/teamBuy/.deploy-backups/customer-detail-20260824023638/`；API 容器重启后健康检查和路由注册正常，未修改数据库、开关、worker 或生产 secrets。
- 小程序前端尚未上传体验版；需要用户在微信开发者工具重新编译、上传后人工验收真实客户详情。

## 2026-08-20：运营后台一级导航收敛为分组入口

- 根因：运营后台把 14 个页面全部平铺在左侧，用户每天真正高频使用的“总览”和“客户经营”与低频配置、审核、系统处理没有层级区分。
- 已改为保留“总览、客户经营”两个一级入口；用户/内容排行归入“数据分析”，群二维码/群发渠道/加群配置归入“群运营”，商机/供给审核/回应包/积分归入“业务工作台”，系统待处理/反馈/规则样本归入“系统与反馈”。
- 分组入口使用可展开的二级标签，原有 `data-tab`、接口和页面内容不变，避免导航收敛演变成业务路由改造。
- 本地完整页面可在 `http://127.0.0.1:8000/ops` 查看；生产已同步后端应用与页面，公网地址为 `https://teambuy.lifelove.top/ops`。
- 客户经营接口已和页面成组发布：客户信息链配置、客户运营指标、总览扩展接口均返回 200；线上开关初始为关闭，保持安全默认。
- API、后台 worker、归档 worker 已重启；数据库、媒体目录、生产 `.env` 和 secrets 未覆盖。
- 本次生产应用备份为 `/home/ubuntu/teambuy-backups/teambuy-customer-ops-20260820-235617/`；健康检查返回 200。

## 2026-08-15：我的页名片入口改为直接发客户

- 根因：`我的 → 我的名片` 原先无条件进入电子名片编辑器，编辑页“发客户”又只是发布后跳资料库，实际分享按钮隐藏在资料库卡片中。
- 已改为：已发布名片在“我的”页直接显示原生“发名片”分享按钮；没有名片或名片未完善时显示“制作名片/完善名片”并进入编辑器。
- 分享回调复用客户页 `/pages/note-preview/index`、分享归因和默认封面兜底；没有新增后端接口。
- 未部署、未上传体验版；需微信开发者工具重新编译后验证无名片、未完善、已发布、已停止分享四种状态。

## 2026-08-15：隐私权限与高风险链路接手审查

- 检查 `miniprogram/app.json`：代码只使用 `wx.chooseLocation`，没有 `wx.getLocation`；移除未使用的 `permission.scope.userLocation`，保留 `requiredPrivateInfos: ["chooseLocation"]`，避免把选点误申报为实时定位。
- 复核剪贴板、选中文件、选中照片/视频、相册写入和选中位置的调用与隐私申报范围；`wx.setClipboardData` 属于剪贴板使用场景。
- 对客户智能缓存、会员门禁、客户联系方式脱敏、发布/发客户状态、分享封面、旧路由引用、无客户信号时的会员推广入口和生产 API 配置做静态审查，未发现新的 P0。
- 相关 JS `node --check`、小程序 68 个 JSON 解析、`git diff --check` 通过；后端测试 `228 passed`。
- 未部署生产、未上传微信体验版；需用户在微信公众平台确认隐私指引，并在微信开发者工具重新编译后验证 `uploadFile` 授权和真实分享卡封面。

## 2026-08-14：电子名片入口读取改为本地缓存优先

- 电子名片编辑页之前会先请求一次完整资料列表查找名片，读取名片后又再次请求资料列表加载精选资料，导致首次打开出现连续等待。
- 现在优先使用名片 `noteId` 本地缓存和资料列表缓存；页面先完成名片身份区渲染，精选资料在后续异步补齐。
- 名片保存/发现已有名片后会缓存 `businessCardNoteId`，后续从入口进入直接读取已缓存的名片详情。
- 头像预览调整为 148rpx，二维码预览调整为 184rpx；“更换/添加”按钮分别收窄到 64rpx，减少中间说明文字被挤压。

## 2026-08-14：五类编辑器底部操作栏与名片二维码入口收边

- 电子名片联系方式中的二维码预览区从 90rpx 放大到 124rpx，二维码“添加/更换”按钮单独收窄，头像按钮保持原尺寸。
- 房源、商品、服务、普通文字、链接编辑器的底部双操作统一为等宽两列，按钮内容用 flex 居中，保留左浅色/右蓝色语义。
- 未部署、未上传；需在微信开发者工具重新编译后检查安全区、长文案和小屏宽度。

## 2026-07-05 项目收口：整理迁移配置与 GitHub 上传准备

本轮处理：

- 按项目规则重新读取：
  - `AGENTS.md`
  - `docs/project-memory.md`
  - `docs/decisions.md`
  - `docs/pitfalls.md`
  - `docs/dev-log.md`
  - `docs/handoff-latest.md`
- 检查当前工作区：
  - 分支：`codex/version-protection-20260629`
  - 远程：`git@github.com:gst0102/teamBuy.git`
  - 当前分支相对远端 `ahead 1`
  - 工作区存在大量未提交二期改动，包含后端、H5、小程序、文档
- 补项目收口文档：
  - 新增 `docs/project-closeout-20260705.md`
  - 新增 `docs/config-migration-reference.md`
- 新增收口规则：
  - `.gitignore` 增加 `artifacts/`
  - 本地部署比对目录不再参与 GitHub 上传

本轮结论：

- 当前仓库更适合做“阶段归档 + 新项目复用底座”。
- 当前前端默认配置仍是测试环境：
  - `apiBaseUrl=https://teambuy.lifelove.top`
  - `apiRoutePrefix=/test-api`
  - `mediaRoutePrefix=/test-media`
  - `environmentName=test`
- 可迁移重点已整理进 `docs/config-migration-reference.md`：
  - 域名 / 服务器
  - 小程序 AppID
  - H5 `web-view + ticket` 模式
  - 后端环境变量骨架

验证：

- 文档与 `.gitignore` 改动已落盘。
- 后续准备在提交前再统一执行一次 `git diff --check`。

补充：

- 新增可直接交给新项目开发的执行文档：
  - `docs/new-project-migration-checklist.md`
- 文档内容包括：
  - 哪些文件可直接复制
  - 哪些配置必须重配
  - 哪些旧业务代码不要带
  - 新项目建议落地顺序

## 2026-07-03 资源工具 H5：补本地预览模式，并强化首页雷达感 / 我的发布控制台感

本轮完成：

- 资源工具 H5 增加本地预览模式：
  - 在 `file://`、`localhost`、`127.0.0.1` 直接打开时，不再因为缺少 ticket 只显示“登录状态已过期”。
  - 预览模式会注入示例用户、示例机会、示例供需、示例资料、示例回应包。
  - 保存、申请合作、提交审核、保存订阅、下架等动作在预览模式下只做前端模拟提示，不调用真实接口。
- 首页继续按“更酷一点”的方向打磨：
  - 增加实时刷新胶囊、扫描条感、信号柱动效和更明显的匹配分区域。
  - 加入“本地预览模式”小胶囊，便于区分真数据和视觉预览。
  - 维持首屏紧凑布局，继续突出“去找需求 / 去盯资源”两个主动作。
- 我的发布页继续产品化：
  - 增加最近动态、优先处理、建议动作三块控制台信息。
  - 修正 `＋ 新建发布 / 查看历史` 按钮的默认边框问题，改为统一 CTA 样式。
  - 补统一焦点态、按下态，去掉浏览器默认橙边/黑边带来的未完成感。

验证：

- H5 内联脚本语法通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 本地浏览器预览已确认：首页可直接进入示例雷达页，“我的发布”可直接进入控制台页。
- 已同步测试后端并重启 `teambuy-test-backend-test-1`。
- 公网 `https://teambuy.lifelove.top/test-health` 正常。
- 公网 `https://teambuy.lifelove.top/test-api/h5/resource-tools/` 已确认包含：
  - `preview-banner`
  - `isLocalPreviewHost`
  - `buildPreviewPackage`
  - `mine-console-strip`
  - `lead-live-pill`
- 远端 H5 内联脚本解析通过。

追加打磨：

- 首页机会卡继续压层级：
  - 标题字号稍提，摘要和元信息间距重排。
  - 城市、行业改为轻胶囊，时间单独收在右侧。
  - 按钮前增加轻分隔线，让卡片结构更清楚。
- 我的发布单卡改为专用发布卡骨架：
  - 头像方块改成更像序号/状态入口的 index 角标。
  - 标题、摘要限制行数，避免长内容撑乱卡片。
  - 城市 / 行业 / 类型 / 状态改成四格指标块。
  - 操作区改为主按钮 + 紧凑次按钮，更像控制台卡片。

补充验证：

- H5 内联脚本再次通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 已再次同步测试后端，公网测试页已包含：
  - `lead-meta-pill`
  - `lead-card-divider`
  - `mine-publish-card`
  - `mine-publish-title`
  - `mine-publish-metrics`
  - `mine-publish-actions`

继续打磨：

- 首页顶部统计区增加轻量“扫描面板”节点：
  - 扫描状态
  - 重点城市
  - 当前热点
  - 并补脉冲点，让顶部更像实时面板。
- “我的发布”里的“收到申请”改为控制台语言：
  - 新增工单式申请卡
  - 展示申请人 / 渠道意向 / 建议动作三格信息
  - 文案从“普通合作信息”改为“优先处理的申请任务”

补充验证：

- H5 内联脚本再次通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 已同步测试后端，公网测试页已包含：
  - `lead-panel-strip`
  - `lead-panel-node`
  - `lead-panel-dot`
  - `mine-application-card`
  - `mine-application-grid`
  - `mine-application-actions`

补修正：

- 用户反馈“看不到扫描面板”和“收到申请这些 DOM 没反应”。
- 已确认原因不是样式缺失，而是：
  - 用户打开的是 `?page=opportunities` 的“我的机会”页，不是首页首屏。
  - 预览模式下“我的发布”原先没有喂申请 mock 数据。
  - `通过 / 拒绝` 在预览模式下原先没有模拟反馈。
- 已修正：
  - 在“我的机会”页顶部也显示一版扫描面板，并明确提示“机会页同步显示”。
  - 预览模式下为“我的发布”补充收到申请和我申请的合作 mock 数据。
  - 预览模式下 `通过 / 拒绝` 已可弹出模拟反馈。

再次验证：

- H5 内联脚本通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 已同步测试后端，公网测试页已包含：
  - `previewReceivedApplications`
  - `previewMyApplications`
  - `机会页同步显示`
  - `预览：已模拟通过申请`

继续打磨：

- “我申请的合作”已统一成控制台申请卡语言：
  - 改为蓝色申请卡视角
  - 增加申请去向 / 当前状态 / 建议动作三格信息
  - 增加 `查看原需求 / 继续找资源` 两个动作
- 供需广场顶部改成一个完整产品面板：
  - 新增 `market-top-panel`
  - hero、统计、筛选合并在同一块面板里
  - 筛选区新增轻量运行摘要：重点城市 / 当前热点 / 筛选方式

再次验证：

- H5 内联脚本通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 已同步测试后端，公网测试页已包含：
  - `market-top-panel`
  - `market-filter-panel`
  - `market-panel-head`
  - `market-scan-row`
  - `mine-application-card applied`
  - `继续找资源`

## 2026-07-03 资源工具 H5：补“发布历史”、需求详情和供需搜索

本轮完成：

- “我的发布”补历史入口，新增历史页面用于查看已下架/历史供需。
- 供需详情拆出需求详情样式，`cardType=demand` 时不再复用普通供给详情卡。
- 发布供需页资料选择卡改为紧凑卡片，长标题最多显示两行，并补“查看详情”按钮。
- 供给预览页“会员可查看 / 对方可申请联系”改为可点击 DOM 按钮，点击后可回到发布页继续编辑。
- 供需广场补真搜索框和搜索按钮，支持输入关键词后刷新当前列表。
- 供需广场卡片第二操作改为“申请合作 / 立即联系”，避免误走机会保存链路。
- 订阅页上方配置与下方“正在为你盯”改为实时联动。
- 发布供需新增草稿缓存，解决预览页提交时读不到标题和联系方式的问题。
- 顶部工具栏改为横向可滑动，`发布`、`我的` 不再隐藏。
- 资源工具导航重新收敛：
  - 顶部只保留 `我的机会 / 需求广场 / 已保存 / 订阅` 四个主入口。
  - `发布供需 / 我的发布` 改成独立一排胶囊按钮。
  - 首页内部重复 tab 和底部重复导航移除。
- 发布供需表单不再默认塞满内容，改为“空值 + 示例占位”；编辑旧内容时才回填。
- 发布保存时仍保留草稿链路，避免预览页提交时再次丢标题。
- 首页首屏进一步压缩信息密度，并增加“去找需求 / 去盯资源”两个快捷入口。
- 我的发布页补强为更完整页面，增加 `＋ 新建发布 / 查看历史` 两个明显按钮。

验证：

- H5 内联脚本语法通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。

## 2026-07-03 资源工具 H5：按 34 号参考图完成 9 页视觉骨架

本轮完成：

- 继续上一轮 systemError 中断点，不从头重做，只补完“我的发布”页。
- 已按 `docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md` 的 3 张参考图完成 9 个 H5 页面视觉骨架：
  - 商机线索首页
  - 我的机会
  - 线索详情
  - 订阅雷达
  - 已保存
  - 供需广场
  - 发布供给
  - 供给预览
  - 我的发布
- “我的发布”从旧版通用卡片替换为参考图风格：统计卡、展示中/待处理/收到申请状态、发布卡片、合作申请区、再发布入口。
- 发布供给“下一步”补齐 `preview-supply` 动作，能进入供给预览页。

验证：

- H5 内联脚本语法解析通过。
- H5 页面标记检查通过：`lead-summary-card`、`match-overview-card`、`lead-detail-page`、`subscription-like-page`、`saved-like-page`、`market-like-page`、`publish-progress`、`preview-page`、`mine-page`。
- `.venv312/bin/python -m compileall -q backend/app` 通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html docs/dev-log.md docs/decisions.md docs/pitfalls.md docs/handoff-latest.md` 通过。
- 已同步测试后端并重启 `teambuy-test-backend-test-1`。
- 公网 `https://teambuy.lifelove.top/test-health` 返回正常。
- 公网 `https://teambuy.lifelove.top/test-api/h5/resource-tools/` 已确认包含 9 个页面结构标记，远端内联脚本解析通过。

注意：

- 本轮只同步测试环境，未改生产环境。
- 当前为 H5 视觉骨架和主链路按钮补齐，真机仍需继续按截图微调间距、字体和卡片高度。

## 2026-07-02 资源工具 H5：体验打磨与筛选排序

本轮完成：

- 顶部功能导航从固定 6 列改为横向滑动胶囊，避免手机窄屏挤压。
- 机会/供需列表新增城市、行业、类型、排序筛选胶囊。
- 筛选条件会带到接口请求，同时前端保留兜底过滤；接口暂时不识别参数时，页面仍能按当前返回数据筛选。
- 排序支持“推荐优先 / 最新优先”。
- 发布供需页不再展示 `supply/demand` 内部值，改为“我能提供 / 我在寻找”中文胶囊。
- 发布供需页城市、行业、类型、联系要求改为“自定义输入 + 常用胶囊”组合，用户可以点选也可以自己输入。
- H5 操作按钮补充居中和最小宽度约束，降低按钮文本变形概率。

验证：

- H5 内联脚本语法解析通过。
- `.venv312/bin/python -m compileall -q backend/app` 通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。
- 已同步测试后端并重启 `teambuy-test-backend-test-1`，未碰生产。
- 公网 `https://teambuy.lifelove.top/test-health` 返回正常。
- 公网 `https://teambuy.lifelove.top/test-api/h5/resource-tools/` 已包含筛选、中文发布方向和新页面脚本。

注意：

- 当前筛选接口参数属于兼容增强，后端如果后续要做数据库级精准筛选，可继续在对应列表接口里消费 `city/industry/demandType`。
- 小程序前端配置当前仍为测试环境：`/test-api`、`/test-media`。

追加修正：

- 用户反馈“之前里面 4 个页面，现在像一个页面，没法验收”。
- 已将 H5 默认首屏改成资源工具入口页：
  - 4 个主入口卡片：机会雷达、供需广场、已保存、订阅雷达。
  - 发布供需、我的发布作为常用动作入口放在下方。
  - 默认不再直接进入机会列表，也不默认展开搜索和筛选。
  - 顶部导航固定为 4 个主页面 + 刷新，不再把发布/我的挤进主导航。
  - 页面标题会随模块切换：首页是资源工具，进入模块后再显示对应模块名。
- 已同步测试后端并重启 `teambuy-test-backend-test-1`。
- 公网页面确认包含 `module-card`、机会雷达、供需广场、已保存、订阅雷达等新入口。

再次修正：

- 用户反馈 H5 与之前原生页面差别仍然很大，要求尽量 1:1 还原原样式和效果。
- 已按原生小程序页面重新还原 H5 的 4 个核心页视觉骨架：
  - 机会雷达：恢复“我的机会”hero、匹配度圆形、主动推荐、雷达图、主推机会卡、更多机会卡。
  - 供需广场：恢复公开线索池 hero、发布按钮、四格统计、分类筛选面板、线索列表卡。
  - 已保存：恢复轻量跟进台 hero、四个状态统计、回应包筛选、跟进卡。
  - 订阅雷达：恢复配置分组、标签选择、关键词、提醒节奏、正在为你盯、保存按钮。
- 这次不再使用“简化卡片列表”作为主要页面，而是让 H5 页面结构尽量贴近原生 WXML/WXSS。
- 已再次同步测试后端并重启 `teambuy-test-backend-test-1`。
- 公网页面确认包含 `radar-visual`、`stats-grid`、`已保存线索`、`正在为你盯` 等还原后的模块。

首页专项微调：

- 用户确认先只碰第一页，并要求按 34 号文档三张参考图逐项还原，不要随意变化。
- 已先按第一张参考图左一“商机线索首页”重做 H5 默认首屏：
  - 隐藏 H5 自带大 hero、工具 tab 和状态条。
  - 默认首屏改为绿色统计卡：今日机会、高匹配、可联系、今日新增。
  - 恢复四个首页 tab：我的机会、需求广场、订阅、已保存。
  - 恢复首页线索卡：标签、标题、摘要、城市/行业/时间、查看详情/保存按钮。
  - 恢复底部四项导航视觉：线索、广场、订阅、我的。
  - 测试库无机会数据时提供只用于视觉验收的预览卡，点击详情/保存不会请求不存在的后端数据。
- 已同步测试后端并重启 `teambuy-test-backend-test-1`。
- 公网页面确认包含 `lead-summary-card`、`今日为你筛出`、`lead-bottom-nav` 等首页模块。

## 2026-07-02 资源工具 H5 化最小闭环

本轮完成：

- 后端新增 H5 短期登录票据：
  - `POST /api/auth/h5-ticket`：小程序用当前 `userId` 换取短期签名票据。
  - `GET /api/auth/h5-session`：H5 用票据校验并换取当前用户信息。
  - 票据为 HMAC 签名，默认 10 分钟有效，不建表，不直接信任前端裸传 `userId`。
- 后端新增 H5 静态入口：
  - `/h5/resource-tools/` 返回资源工具 H5 首屏。
  - H5 首屏支持校验登录态、读取机会列表、读取供需列表、关键词搜索和刷新。
- 小程序新增 `pages/resource-tools-webview/index` 通用 web-view 容器。
- “我的”页资源工具/商机雷达入口改为先签发 H5 票据，再打开 H5；失败时回退原生商机雷达页。
- 原生商机/供需/回应包页面全部保留，当前 H5 只是最小闭环入口，不替换完整业务能力。

已验证：

- `node --check miniprogram/pages/resource-tools-webview/index.js miniprogram/pages/profile/index.js miniprogram/services/api.js`：通过。
- `.venv312/bin/python -m compileall -q backend/app`：通过。
- 小程序 `app.json` 和 H5 web-view 页面 JSON 校验：通过。
- 后端 TestClient 烟测通过：mock 登录、签发 H5 票据、校验 H5 session、访问 `/h5/resource-tools/`。
- `git diff --check`：通过。

注意：

- 本轮未部署测试后端、未部署生产、未上传小程序。
- 真机 web-view 访问需要微信小程序后台配置 H5 业务域名，域名应为 `https://teambuy.lifelove.top`。
- 当前 H5 详情和保存按钮只提示“下一步迁移”，还未接原生详情/保存完整动作。

测试环境部署：

- 已只同步测试后端，未碰生产后端。
- 测试端备份：`/home/ubuntu/teamBuy-deploy-backups/20260702-145729-h5-resource-tools-test`。
- 同步方式：`rsync backend/app/` 到测试服务器，再 `docker cp backend/app/. teambuy-test-backend-test-1:/app/app/`，重启测试容器。
- 由于测试 Nginx 只把 `/test-api` 转发到测试容器，H5 测试路径使用 `/test-api/h5/resource-tools/`；生产路径仍预留 `/h5/resource-tools/`。
- 公网验证：
  - `https://teambuy.lifelove.top/test-health`：200。
  - `https://teambuy.lifelove.top/test-api/h5/resource-tools/`：200。
  - `POST /test-api/auth/h5-ticket`：200。
  - `GET /test-api/auth/h5-session`：200。
  - `/test-api/opportunity-leads?userId=...`：200。
  - `/test-api/supply-demand/cards`：200。

提交审核前文案清理：

- 已清理资源工具用户侧展示文案中的 `H5`、`最小闭环`、`原生小程序页面` 等开发字眼。
- 小程序异常 toast 改为产品文案：`资源工具地址无效`、`资源工具升级中，已打开旧版`。
- 测试环境已同步最新文案，公网页面确认不再包含用户可见的 H5 开发文案。

## 2026-07-02 资源工具 H5：详情和基础动作

本轮完成：

- 资源工具 H5 列表卡片支持进入详情：
  - 机会详情：展示标题、摘要、城市、行业、需求类型、联系方式状态和行动建议。
  - 供需详情：展示标题、摘要、城市、行业、类型、联系要求和标签。
- 机会详情支持基础动作：
  - 保存机会，调用 `/api/opportunity-leads/{id}/save`。
  - 查看联系方式，调用 `/api/opportunity-leads/{id}/unlock-contact`，扣分和 24 小时免重复由后端资源钱包规则控制。
- 供需详情支持申请合作，调用 `/api/supply-demand/cards/{id}/applications`。
- 列表页“先保存 / 申请合作”已直接接真实接口，不再只提示升级中。

已验证：

- H5 内联脚本语法解析通过。
- 后端 compileall 通过。
- 本地 TestClient 验证 H5 页面、签票和验票通过。
- `git diff --check` 通过。
- 已同步测试后端，公网 `https://teambuy.lifelove.top/test-api/h5/resource-tools/` 已包含新动作文案。

注意：

- 当前没有额外造测试数据；如果测试库没有已发布机会或供需卡，页面仍会显示空列表。
- 回应包、订阅雷达、发布供需、我的发布/申请列表还未迁入 H5。

## 2026-07-02 资源工具 H5：已保存、订阅和回应包基础闭环

本轮完成：

- 顶部入口扩展为四个模块：机会、供需、已保存、订阅。
- 已保存跟进台：
  - 接 `/api/opportunity-leads/saved`。
  - 展示已保存线索、状态、回应包状态。
  - 支持进入机会详情。
  - 支持生成或打开回应包。
- 订阅雷达：
  - 接 `/api/opportunity-subscriptions/me` 读取现有订阅。
  - 表单支持订阅方向、我在找、我能提供、城市、关键词、联系方式要求。
  - 接 `/api/opportunity-subscriptions` 保存订阅。
- 回应包基础显示：
  - 从机会详情或已保存线索生成回应包。
  - 接 `/api/opportunity-leads/{id}/response-packages`。
  - 接 `/api/response-packages/{id}` 打开已生成回应包。
  - 展示需求摘要、回应话术、推荐资料、跟进建议。
  - 支持复制回应内容。

已验证：

- H5 内联脚本语法解析通过。
- 后端 compileall 通过。
- 本地 TestClient 覆盖订阅保存、订阅读取、已保存列表和 H5 页面关键词检查。
- `git diff --check` 通过。
- 已同步测试后端，公网确认新增模块文案存在。
- 公网 `/test-api/opportunity-subscriptions/me` 和 `/test-api/opportunity-leads/saved` 返回 200。

注意：

- 当前仍未迁移发布供需、我的发布/我的申请、回应包反馈雷达。
- 如果测试库为空，已保存和订阅可以显示空态或表单，但机会/供需列表没有卡片可点。

## 2026-07-02 资源工具 H5：发布供需、我的发布/申请、回应包反馈

本轮完成：

- 顶部入口继续扩展：新增 `发布`、`我的`。
- 发布供需：
  - 支持填写供给/需求方向、标题、摘要、城市、行业、类型、联系要求、标签。
  - 支持保存草稿和提交审核。
  - 接 `/api/supply-demand/cards` 和 `/api/supply-demand/cards/{id}/submit`。
- 我的发布/申请：
  - 接 `/api/supply-demand/cards/me` 展示我的发布。
  - 接 `/api/supply-demand/cards/applications?role=owner` 展示收到的合作申请。
  - 接 `/api/supply-demand/cards/applications?role=applicant` 展示我申请的合作。
  - 收到的申请支持通过/拒绝，接 `/api/supply-demand/cards/applications/{id}/review`。
- 回应包反馈雷达：
  - 回应包详情新增“查看反馈”。
  - 接 `/api/response-packages/{id}/radar`。
  - 展示打开、复制、联系、最近反馈和事件记录。

已验证：

- H5 内联脚本语法解析通过。
- 后端 compileall 通过。
- 本地 TestClient 覆盖供需发布、提交审核、我的发布接口和 H5 页面关键词检查。
- `git diff --check` 通过。
- 已同步测试后端。
- 公网确认 H5 新入口文案存在，`/test-api/supply-demand/cards/me` 和 `/test-api/supply-demand/cards/applications` 返回 200。

注意：

- 发布供需 H5 当前先做基础字段，关联资料/合集选择器还未迁入。
- 我的发布 H5 当前支持提交审核和查看详情，编辑回填、下架等细节后续再补。

## 2026-07-02 资源工具 H5：发布关联、编辑回填、下架与反馈埋点

本轮完成：

- 发布供需关联资料/合集选择器：
  - 打开发布页时读取 `/api/notes?ownerUserId=...` 和 `/api/showcases?ownerUserId=...`。
  - 可在发布表单里选择一条资料或合集作为关联资源。
  - 保存时写入 `linkedResourceType/linkedResourceId`，兼容资料时写入 `linkedNoteId`。
- 我的发布编辑回填：
  - “我的发布”卡片新增编辑按钮。
  - 点击编辑读取 `/api/supply-demand/cards/{id}?userId=...` 并回填发布表单。
  - 编辑保存时走 `PUT /api/supply-demand/cards/{id}`。
- 我的发布下架：
  - “我的发布”卡片新增下架按钮。
  - 下架先读取详情，再用 `PUT /api/supply-demand/cards/{id}` 更新为 `archived`。
- 回应包反馈事件埋点：
  - 复制回应内容时调用 `/api/response-packages/{id}/events` 写入 `copy` 事件。
  - 回应包反馈雷达可统计复制行为。

已验证：

- H5 内联脚本语法解析通过。
- 后端 compileall 通过。
- 本地 TestClient 覆盖供需关联字段保存、编辑更新为下架和 H5 页面关键词检查。
- `git diff --check` 通过。
- 已同步测试后端。
- 公网确认 H5 页面包含关联资料/合集、编辑、下架和反馈事件埋点逻辑。
- 公网 `/test-api/notes`、`/test-api/showcases` 返回 200。

## 2026-07-02 商机雷达真机反馈修复：保存提示、发布供需、筛选输入

本轮完成：

- 我的雷达保存失败排查与前端兜底：
  - 保存前检查登录用户是否有 `user.id`。
  - 只对真实 `opp_*` 商机线索调用保存接口，非商机内容提示去供需详情申请。
  - 保存失败时展示后端返回的具体原因；如果是登录态失效，会清除本地用户，避免继续拿旧用户请求。
- 发布供需页：
  - “我能提供 / 我在寻找”改为稳定 `view` 胶囊，不再使用原生 `button` 撑变形。
  - 删除“绑定资料 ID”输入，改为从用户自己的资料库和合集列表中选择关联资料。
  - 供需卡新增并保存 `linkedResourceType/linkedResourceId`，兼容旧 `linkedNoteId`。
  - 城市、行业、类型支持自定义输入，同时保留常用标签快捷选择。
- 供需广场筛选：
  - 城市、行业、需求类型新增自定义输入框。
  - 常用标签仍可快捷点选，输入确认后按真实接口参数筛选。

已验证：

- `node --check miniprogram/pages/supply-demand-publish/index.js miniprogram/pages/opportunity-market/index.js miniprogram/pages/opportunity-radar/index.js miniprogram/services/api.js`：通过。
- 小程序 `app.json`、发布供需页、供需广场页 JSON 校验：通过。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-bugfix-radar-supply.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q`：1 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-bugfix-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"`：13 passed。
- 后端 compileall：通过。
- `git diff --check`：通过。

注意：

- 本轮未部署生产，也未上传小程序。
- 如果用户当前真机仍连接旧测试后端，保存接口可能仍失败；需要上传包含本轮前端的新体验版并保证测试后端有对应接口。

## 2026-07-01 商机雷达 P1：订阅、解锁、反馈、供给发布与后台审核

本轮完成：

- 完成 P1 1-5：
  - 订阅雷达真实保存：新增 `opportunity_subscriptions` 数据模型、JSON/Postgres 仓储、后端接口和小程序订阅页保存/回填。
  - 联系方式解锁：新增线索联系方式解锁接口，按资源积分扣减，重复解锁不重复扣分，返回完整联系方式并写跟进记录。
  - 回应包雷达反馈页：新增回应包反馈接口和小程序反馈页，聚合打开、联系、保存等事件，给出下一步建议。
  - 我的发布 / 发布供给：新增供需卡模型、公开列表、我的发布列表、发布供给页、提交审核流程。
  - 供给审核后台：PC 运营后台新增供给审核入口，支持筛选、通过、驳回。
- 小程序供需广场改为混合展示官方商机线索和已发布供需卡。
- 小程序“我的机会”接入用户订阅匹配结果，不再只展示固定 mock。
- 小程序线索详情“查看联系方式”接入真实解锁接口；demo 数据仍本地成功，避免 mock id 打真实 API 报错。
- 新增 P1 闭环回归测试，覆盖订阅保存、匹配线索、解锁联系方式、回应包反馈、供给提交审核和公开展示。

已验证：

- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-test2.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q`：1 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"`：13 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-compile.json .venv312/bin/python -m compileall -q backend/app`：通过。
- `node --check` 覆盖 `miniprogram/services/api.js`、商机雷达、线索详情、供需广场、回应包、回应包反馈、供给发布、我的发布页面：通过。
- 小程序 `app.json` 和新增页面 JSON 校验：通过。
- `git diff --check`：通过。

注意：

- 本轮未部署生产，也未上传小程序；当前只是本地代码和测试环境可验证状态。
- 供给发布里的关联资料当前先用 `linkedNoteId` 手动输入，后续 P2 可改成资料选择器。
- 供需广场里供给卡的“保存/联系”后续还需要设计成申请合作或回应包流程；本轮 P1 先完成发布、审核和展示闭环。

## 2026-07-01 商机雷达 P1 体验补强：跟进台、订阅推荐、资料勾选、广场筛选

本轮完成：

- 已保存跟进台完善：
  - 后端已保存列表支持按跟进状态、关键词、回应包状态筛选。
  - 已保存列表返回 `responsePackage/packageStatus/latestFollowup/followupCount`，用于展示回应包状态和最近动作。
  - 小程序已保存页支持切换回应包筛选、编辑跟进状态、快捷设置提醒时间、打开已生成回应包。
- 订阅匹配结果：
  - `/api/opportunity-leads?userId=...` 改为按用户 active 订阅生成“今日推荐机会”，按匹配分排序并返回推荐规则和生成时间。
  - 支持城市、行业、需求类型、联系方式状态筛选，不再只是展示全部线索。
- 回应包可选资料：
  - 回应包预览请求支持 `selectedAssetIds`。
  - 后端返回 `assetOptions/selectedAssetIds`，用户可在小程序里勾选或替换资料后再生成回应包。
  - 生成回应包会按用户勾选资料写入 `ResponsePackageItem`。
- 供需广场筛选：
  - 供需广场后端支持城市、行业、需求类型、需求/供给方向、联系方式状态筛选。
  - 小程序供需广场筛选胶囊接真实接口参数，筛选后重新拉取数据。

已验证：

- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-test.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q`：1 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"`：13 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-enhance-compile.json .venv312/bin/python -m compileall -q backend/app`：通过。
- `node --check` 覆盖 `services/api.js`、已保存、回应包、供需广场、我的机会页面：通过。
- 小程序相关 JSON 校验：通过。
- `git diff --check`：通过。

注意：

- 本轮仍未部署生产，也未上传小程序。
- 供需卡详情页还未单独开发；供需广场点击非商机线索卡时先提示“供需卡详情后续开放”。

## 2026-07-01 商机雷达 P1 延伸：供需详情、合作申请、站内主动推荐

本轮完成：

- 供需卡独立详情页：
  - 新增后端 `GET /api/supply-demand/cards/{card_id}`。
  - 新增小程序 `pages/supply-demand-detail/index`。
  - 供需广场点击 `sd_*` 等非商机线索卡时进入供需详情页，不再误跳商机详情。
- 合作申请：
  - 新增 `SupplyDemandApplication` 模型和 JSON/Postgres 仓储。
  - 新增申请、申请列表、处理申请接口。
  - 供需详情页支持填写留言并申请合作。
  - 我的发布页展示收到的合作申请，支持通过/拒绝。
- 主动推送：
  - 新增 `OpportunityPushDigest` 模型和 JSON/Postgres 仓储。
  - 新增站内推荐摘要接口：生成、列表、标记已读。
  - 我的机会页新增“主动推荐”模块，可生成今日推荐摘要并标记已读。
  - 当前不外发微信模板消息或企业微信消息，只做站内待推送/推荐摘要记录。

已验证：

- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-test.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q`：1 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-regression.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"`：13 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-next-compile.json .venv312/bin/python -m compileall -q backend/app`：通过。
- `node --check` 覆盖 `services/api.js`、供需详情、我的发布、我的机会、供需广场页面：通过。
- 小程序 `app.json` 与新增页面 JSON 校验：通过。
- `git diff --check`：通过。

注意：

- 本轮未部署生产，也未上传小程序。
- 主动推送当前是站内摘要，不是微信/企微外发；后续如要外发，需要单独确认授权、触达频率和退订机制。

## 2026-07-01 商机雷达 P1 尾巴：编辑回填、我申请的列表、后台触发站内推荐

本轮完成：

- 我的发布编辑回填：
  - 供需发布页支持 `id` 参数进入编辑模式。
  - 进入编辑时通过供需详情接口回填标题、摘要、城市、行业、类型、联系方式要求、关联资料和标签。
  - 保存草稿和提交审核时会带原卡片 `id`，不再重复新建。
  - 供需详情接口允许 owner 查看自己的草稿、待审、驳回和已发布卡；非 owner 只能查看已发布卡。
- 我申请的合作列表：
  - “我的发布”页新增“我申请的合作”区块。
  - 调用现有 applicant 视角申请接口，展示自己发出的申请状态和卡片信息。
- 站内推荐自动生成接口/后台触发：
  - 后端新增 `generate_opportunity_push_digests_for_active_subscriptions`，遍历 active 订阅用户批量生成站内推荐摘要。
  - PC 后台供给审核页新增“生成站内推荐摘要”按钮，调用 `/api/ops/opportunity-push-digests/generate`。
  - 仍然不外发微信/企微消息。

已验证：

- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-test3.json .venv312/bin/python -m pytest backend/tests/test_app.py::test_p1_subscription_unlock_supply_and_response_radar -q`：1 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-regression2.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "p1_subscription or response_package or opportunity_lead or resource_wallet or ops_opportunity_dashboard"`：13 passed。
- `PYTHONPATH=backend DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-p1-tail-compile.json .venv312/bin/python -m compileall -q backend/app`：通过。
- `node --check` 覆盖 `services/api.js`、供需发布、我的发布、供需详情、我的机会页面：通过。
- 小程序 JSON 校验和 `git diff --check`：通过。

注意：

- 本轮未部署生产，也未上传小程序。
- 站内推荐摘要可由用户手动生成，也可由 PC 后台触发批量生成；没有定时任务和外部消息发送。

## 2026-07-01 房源公开联系方式与上游联系方式分离

本轮完成：

- 生成房源卡时，公开联系方式默认使用发布者“我的”资料里的手机号和微信。
- 房源原文中识别到的电话、微信和上游备注继续写入 `visibilityConfig.privateData/privateTags`，不再作为公开联系电话。
- 公开客户页过滤 `privateData/privateTags` 后，会补入发布者自己的 `phone/wechat`，并把公开 `body` 替换为安全房源摘要，避免原文上游电话泄露。
- 批量房源、手动粘贴、快捷记录、普通笔记确认成房源都会走同一套 owner 联系方式补齐逻辑。
- 已热更新生产和测试后端，最新备份：`/home/ubuntu/teamBuy/backend/backups/codex-20260701-141141-owner-contact-empty-field-fix/`。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：14 passed。
- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "owner_contact or upstream_private or property_note_uses"`：2 passed。
- `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- 生产健康检查正常。
- 生产容器内验证：owner 手机 `13900001111` 和微信 `agent-yiyi` 自动进入公开字段；上游电话 `18501775740` 仅在 `privateData.upstreamPhones`，公开 payload 中不存在。

## 2026-07-01 测试环境房源识别与旧普通笔记候选兜底

本轮完成：

- 排查用户 13:44 上传 `开福区天健一期H栋1205` 仍显示普通笔记且没有“整理成房源”按钮的问题。
- 确认根因：生产 `/api` 已是新规则，但测试 `/test-api` 仍是旧 `skill_router_service.py`，同一段文案在测试后端返回 `text_note`、房源分 1、`typeSuggestions=[]`。
- 已把 `backend/app/services/skill_router_service.py` 同步热更新到测试容器 `teambuy-test-backend-test-1` 和生产容器 `teambuy-backend-1`。
- 小程序房源编辑页增加前端兜底：旧普通笔记即使后端没有 `typeSuggestions`，只要标题/正文命中明显租房信号，也展示“整理成房源”候选按钮。
- 后端确认类型逻辑补充回归：普通笔记确认成房源时，优先复用识别器重新抽取租金、押付、水电等字段。

已验证：

- 生产 `https://teambuy.lifelove.top/health` 正常。
- 测试 `/test-api/skills/content-to-note/run` 对该文案返回 `cardType=property_listing`、`level=high`、`price=1500`、`paymentMethod=押一付三`、`utilities=民水民电`。
- `.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：14 passed。
- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "quick_capture or confirm_plain_rental_note or manual_draft"`：9 passed。
- `node --check miniprogram/pages/note-edit/index.js`：通过。
- 小程序 JSON 校验：通过。

注意：

- 旧体验版如果仍连 `/test-api`，必须重新上传包含前端兜底按钮的新版本，页面上才会出现候选按钮。
- 本轮曾短暂误传本地混有未上线商机线索依赖的 `app_service.py`，导致容器启动失败；已立即恢复线上备份，并改为使用干净线上版本做最小补丁后重新部署。

## 2026-07-01 上游备注常驻输入与日常资料默认 SCRM

本轮完成：

- 房源编辑页“仅自己可见：上游备注”改为常驻输入区，不再要求已有 `privateData` 才显示。
- 支持手动填写上游电话、上游微信、上游联系人、中介费、密码锁、看房备注、上游备注。
- 手动填写内容保存到 `visibilityConfig.privateData`，继续不进入客户页、公开分享页和生成同款公开资料。
- 小程序默认转化配置调整：房源、团购、服务卡、日常普通资料默认 `enableLightScrm=true`。
- 后端普通 `text_note` 默认 `conversionConfig.enableLightScrm=true`，与前端默认口径一致。
- 已热更新生产后端 `backend/app/services/skill_router_service.py`，备份到 `/home/ubuntu/teamBuy/backend/backups/codex-20260701-134651-scrm-upstream-defaults/skill_router_service.py`。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：14 passed。
- `node --check miniprogram/pages/note-edit/index.js`：通过。
- `node --check miniprogram/app.js`：通过。
- 小程序 JSON 校验：通过。
- `git diff --check`：通过。
- 生产 `https://teambuy.lifelove.top/health` 正常。
- 生产普通文本卡验证返回 `cardType=text_note` 且 `conversionConfig.enableLightScrm=true`。

## 2026-07-01 单条房源识别生产热更新与小程序切生产

本轮完成：

- 已将 `backend/app/services/skill_router_service.py` 热更新到生产服务器 `/home/ubuntu/teamBuy`。
- 生产原文件已备份到 `/home/ubuntu/teamBuy/backend/backups/codex-20260701-133204-skill-router/skill_router_service.py`。
- 已重启生产容器 `teambuy-backend-1`。
- 小程序全局配置 `miniprogram/app.js` 已从测试环境切回生产环境：`apiRoutePrefix=""`、`mediaRoutePrefix=""`、`environmentName="production"`。

已验证：

- `https://teambuy.lifelove.top/health` 返回 `status=ok`。
- 生产 `POST /api/skills/content-to-note/run` 使用典型租房微信笔记验证，返回 `cardType=property_listing`、`recognitionConfidence.level=high`。
- `node --check miniprogram/app.js`：通过。
- 小程序 JSON 校验：通过。
- `git diff --check`：通过。

## 2026-07-01 单条微信笔记房源识别与房源编辑单位输入修复

本轮完成：

- 修正单条微信笔记房源识别规则，补齐真实租房口语信号：押付、民水民电、独门独户、禁宠、密码锁、底价、租客、空置/搬空、看房、房屋配置等。
- 支持 `【租金】1980`、`【面积】40` 这类微信笔记括号字段。
- 房源字段生成时，面积和租金统一保存为数字值，例如 `40`、`1980`，单位由前端展示。
- 房源编辑页把“租金”和“面积”改为数字输入，右侧固定单位：`元/月`、`㎡`。
- 增加回归测试覆盖 `珠江好世界B5栋5083` 完整单套微信笔记，以及 `开福区天健一期H栋1205 / 底价1500 / 押一付三 / 民水民电 / 不养宠物 / 密码锁` 短租房笔记。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：14 passed。
- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property or wecom_archive_process"`：18 passed。
- `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- `node --check miniprogram/pages/note-edit/index.js`：通过。
- 小程序 JSON 校验：通过。
- `git diff --check`：通过。

## 2026-07-01 商机雷达 P0：小程序静态 UI

本轮完成：

- 按 `docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md` 和参考图要求，先做商机线索静态 UI，不接接口。
- 新增页面：
  - `pages/opportunity-radar/index`
  - `pages/opportunity-market/index`
  - `pages/opportunity-detail/index`
  - `pages/opportunity-saved/index`
  - `pages/opportunity-subscription/index`
- `我的` 页资源工具里的 `商机线索` 从近期开放改为可点击入口。
- 我的机会页包含雷达图、匹配度、最高匹配机会、匹配原因、建议动作和 `生成回应包 / 查看联系方式 / 保存`。
- 供需广场包含统计、筛选、需求卡、供给卡和发布入口。
- 详情页包含结构化摘要、行动建议和跟进状态。
- 已保存页按跟进状态分组，订阅页用标签点选配置雷达订阅。

已验证：

- 新增 5 个页面和 `profile/index.js` 的 `node --check`：通过。
- 小程序 `app.json` 和新增页面 JSON 解析：通过。
- `git diff --check`：通过。
- 自测报告：`docs/qa/商机线索静态UI_Codex自测报告.md`。

## 2026-07-01 商机雷达 P0：商机线索数据模型和后台录入

本轮完成：

- 按 P0 第二步实现商机线索基础数据模型和后台录入。
- 新增后端模型：商机线索、线索来源、线索联系人、线索匹配、用户保存、用户跟进。
- 新增运营接口：
  - `GET /api/ops/opportunity-leads`
  - `GET /api/ops/opportunity-leads/{lead_id}`
  - `POST /api/ops/opportunity-leads`
- 新增小程序预留接口：
  - `GET /api/opportunity-leads`
  - `GET /api/opportunity-leads/{lead_id}`
  - `GET /api/opportunity-leads/saved`
  - `POST /api/opportunity-leads/{lead_id}/save`
  - `POST /api/opportunity-leads/{lead_id}/followups`
- PC 运营后台新增 `商机线索` 标签页，可人工录入标题、摘要、城市、行业、内容、来源和联系方式。
- 前台接口默认只展示 `官方收录`，不展示具体第三方来源，不返回完整联系方式。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "opportunity_lead or resource_wallet"`：8 passed。
- `.venv312/bin/python -m pytest backend/tests -q`：189 passed。
- `.venv312/bin/python -m compileall -q backend/app`：通过。
- PC 后台内嵌脚本语法检查：通过。
- `git diff --check`：通过。

## 2026-07-01 房源编辑页上游备注前端展示

本轮完成：

- 小程序房源编辑页新增“仅自己可见：上游备注”信息块。
- 该信息块只在 `房源工作台 -> 编辑资料` 且存在 `visibilityConfig.privateData/privateTags` 时展示。
- 支持展示上游电话、上游微信、上游联系人、中介费、密码锁、看房备注、红包备注、租客限制、来源房源和私密标签。
- 增加“复制全部”和单项“复制”按钮，方便用户查到上游电话后直接使用。
- 明确提示这些内容只在当前账号查看，客户页、公开分享页和生成同款公开资料不展示。
- 本轮只改小程序前端展示，不改后端归档解析、存储结构和客户公开接口。

已验证：

- `node --check miniprogram/pages/note-edit/index.js`：通过。
- 小程序 JSON 校验：通过。
- `git diff --check`：通过。

## 2026-07-01 商机雷达 P0：后端积分账本底座

本轮完成：

- 按 `docs/stage2-docs/36-opportunity-radar-phase2-dev-checklist.md` 的 P0 顺序，先实现资源工具积分账本底座。
- 新增后端模型：用户积分钱包、积分流水、免费额度、解锁记录。
- 新增接口：
  - `GET /api/resource-wallet/me`
  - `GET /api/resource-wallet/ledger`
  - `POST /api/resource-wallet/consume`
  - `POST /api/ops/resource-wallet/adjust`
- 后端消费规则已覆盖：
  - 用户首次进入自动创建钱包并发放初始积分。
  - 同一用户、同一对象、同一动作 24 小时内不重复扣积分。
  - 免费额度优先于积分扣减。
  - 运营后台可用管理员口令调整积分，并写入流水。
  - 用户之间钱包和流水隔离。
- 本轮没有做支付、会员、保证金、双向收费、自动联系。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "resource_wallet"`：5 passed。
- `.venv312/bin/python -m pytest backend/tests -q`：186 passed。
- `.venv312/bin/python -m compileall -q backend/app`：通过。
- `git diff --check`：通过。

## 2026-07-01 批量房源自动生成合集 P0

本轮实现：

- 手动批量房源创建 `POST /api/notes/property-batch/create` 在生成多条 `property_listing` 后，会同步生成一个展示页合集。
- 企业微信客服同步批量房源导入命中拆分后，会同步生成一个展示页合集。
- 企业微信会话归档批量房源导入命中拆分后，会同步生成一个展示页合集。
- 自动合集使用 `templateId=property_batch_collection`，默认 `draft` 状态，不自动发布。
- 自动合集包含本次导入的全部房源资料，默认名称类似 `xx房源合集 N套` 或 `批量房源合集 N套`。
- 自动合集联系方式默认不展示电话/微信，继续避免把上游电话公开给客户。
- 手动批量创建返回值新增 `showcaseId/showcase`，小程序生成成功提示改为“房源卡和合集”。
- 归档处理返回值新增 `showcaseId`，通知动作增加“查看房源合集”。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_batch"`：3 passed。
- `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- `node --check miniprogram/pages/resource-create/index.js`：通过。

## 2026-07-01 批量房源合集筛选 P1

本轮实现：

- 自动生成的批量房源合集会按本次房源生成筛选配置：
  - 区域：优先取 `businessArea/address/community`。
  - 户型：归一为一房/单间、次卧、主卧、一室一厅、两房、三房、Loft/复式等。
  - 价格：归一为 `1000以下 / 1000-1500 / 1500-2000 / 2000-3000 / 3000以上`。
- 公开展示页房源摘要新增 `propertyMeta`，客户页可用它做筛选。
- 小程序展示页在房源合集里展示区域/户型/价格筛选胶囊，点击后即时过滤当前房源列表。
- 筛选后统计数量同步变化；筛选无结果时展示空态提示。
- 本地预览态也按同样规则生成 `propertyMeta`，避免发布前预览筛选失效。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_batch"`：3 passed。
- `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- `node --check miniprogram/pages/showcase-view/index.js`：通过。
- 小程序 JSON 校验：通过。

## 2026-07-01 OCR 图片房源批量入库 P2

本轮实现：

- 图片资料点击“识别图片文字”后，如果 OCR 结果命中批量房源规则，会直接生成多套 `property_listing`。
- OCR 批量房源会同步生成草稿合集，并继承 P1 的区域/户型/价格筛选能力。
- 原图片资料仍保留为 `image_ocr`，并记录 OCR 状态和识别文本，不被改成第一套房源。
- OCR 批量生成的房源标记 `sourceType=ocr_property_batch`，并保存 `ocrSourceNoteId`，方便追溯原图。
- OCR 批量生成的房源会继承原图片封面/媒体，便于后续单套房源补图和客户展示。
- 小程序资料编辑页识别成功后，如果生成了批量房源，会提示“已生成 N 套房源和合集”。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "ocr"`：5 passed。
- `node --check miniprogram/pages/note-edit/index.js`：通过。

## 2026-07-01 批量房源功能生产临时部署

本轮部署：

- 用户确认本次作为 Bug 修复直接在生产环境验证，不再先切测试环境。
- 部署前本地全量后端测试通过：`.venv312/bin/python -m pytest backend/tests -q`：180 passed。
- 已确认小程序当前 `apiBaseUrl` 指向生产域名 `https://teambuy.lifelove.top`。
- 生产服务器部署前检查：磁盘 `/dev/vda2` 使用 65%，`teambuy-postgres-1` healthy，`teambuy-backend-1` running。
- 已备份生产后端文件到 `/home/ubuntu/teamBuy/backend/backups/codex-20260701-102308`。
- 已把 `backend/app/services/app_service.py` 同步到生产服务器源码目录，并热更新到正在运行的后端容器。
- 生产容器内确认：
  - `AppService._create_property_batch_showcase` 已存在。
  - OCR 识别流程已包含 `ocr_property_batch` 批量房源逻辑。
- 公网健康检查 `https://teambuy.lifelove.top/health` 返回正常。

注意事项：

- 本次 Docker 镜像重新构建卡在系统包更新阶段，未完成新镜像构建；为了让用户立即测试，采用容器内热更新并重启后端。
- 生产源码目录已同步新代码，后续镜像构建成功后会包含该逻辑。
- 如果生产后端容器在镜像未重建前被删除并重新创建，本次容器热更新可能丢失，需要重新构建或再次同步。
- 小程序前端代码已在本地改好且配置为生产域名，但仍需用户用微信开发者工具预览/上传体验版后，真机才能看到前端提示和筛选 UI。

## 2026-07-01 短挂牌房源整体要素识别修复

本轮修复：

- 用户反馈 10:48 会话归档文本整体包含门牌、户型、价格、联系方式、中介费和看房信息，但系统只生成普通文本资料。
- 原因确认：规则过度依赖单行户型关键词，未覆盖 `南次一室户`、`北一室一厅`，且批量判断没有从整篇文本做要素评分。
- 已调整批量房源入口判断：整篇文本出现房源上下文、编号、门牌/房号、价格、联系方式、中介费/看房/空置/视频等组合信号时，进入批量房源解析。
- 已补充户型规则：支持 `次一室户`、`一室一厅`、`南次一室户`、`北一室一厅` 等短挂牌写法。
- 已调整解析优先级：完整房源行优先独立识别；只有当前行缺少小区/门牌信号时，才沿用上一行小区作为子房间底座，避免误挂。
- 已新增回归测试：`test_property_batch_parse_short_listing_by_whole_text_elements`。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_batch"`：5 passed。
- `.venv312/bin/python -m pytest backend/tests -q`：181 passed。
- `.venv312/bin/python -m compileall -q backend/app backend/tests`：通过。
- `git diff --check`：通过。
- 已部署生产后端热更新，备份路径 `/home/ubuntu/teamBuy/backend/backups/codex-20260701-105746-property-rule`。
- 生产只解析接口验证同一段文本返回 2 套候选：
  - `玉兰286弄10号601室 · 南次一室户 2500元/月`
  - `玉兰四期73号202室 · 北一室一厅 3800元/月`
  - 私密信息识别：上游电话 2 个、中介费 `%50`、朋友圈视频标签。

## 2026-07-01 合集分享封面与资源操作胶囊修复

本轮修复：

- 用户反馈房源卡分享封面正常，但房源合集分享没有等待封面渲染完成，导致微信使用页面截图式封面，且没有底部“由资料整理助手生成 · 点击生成同款”引流钩子。
- 合集详情页 `showcase-view` 增加分享封面状态：进入页面后生成分享图，未生成完成前分享按钮显示“封面准备中”并禁用。
- 合集列表页 `showcases` 改为预生成已发布合集分享图，按钮未准备好时禁用，避免点“发客户”时异步生成还没完成。
- 合集分享仍统一调用 `generateTitleShareImage`，底部引流钩子沿用单条资料/房源卡的分享图生成逻辑。
- 资料库日常资料卡操作区收口为“发客户 + 更多”两枚等宽胶囊，移除列表卡片里的单独“编辑”按钮，编辑仍通过点击卡片主体进入。
- 我的笔记里名片/服务方案操作区统一按钮宽度、高度和字号，避免“发客户/更多”比例偏小或不居中。

覆盖场景：

- 日常资料资源：资料库列表按钮已调整。
- 房源资源：沿用已有房源卡“发客户 + 更多”胶囊。
- 商品团购资源：沿用已有商品卡“发客户 + 更多”胶囊。
- 服务/名片资源：资料库与我的笔记列表按钮已调整。
- 日常/房源/商品/服务合集：合集详情页和合集列表页分享封面等待逻辑统一。

已验证：

- `node --check miniprogram/pages/showcase-view/index.js`：通过。
- `node --check miniprogram/pages/showcases/index.js`：通过。
- `node --check miniprogram/pages/notes/index.js`：通过。
- `node --check miniprogram/pages/library/index.js`：通过。
- 小程序相关 JSON 解析：通过。
- `git diff --check`：通过。

## 2026-07-01 第二期开发前前端切测试环境

本轮处理：

- 用户确认第一期当前测试没问题，准备进入第二期开发。
- 小程序前端已从生产接口切到测试接口：
  - `apiBaseUrl=https://teambuy.lifelove.top`
  - `apiRoutePrefix=/test-api`
  - `mediaRoutePrefix=/test-media`
  - `environmentName=test`
- 请求封装 `miniprogram/utils/request.js` 新增测试路由前缀处理：小程序里的 `/api/...` 会转换成 `/test-api/...`。
- 上传接口改为走同一套 URL 构造，避免出现 `/test-api/api/...` 双前缀。
- 媒体相对路径 `/media/...` 在测试环境下会显示为 `/test-media/...`，避免测试数据读取生产媒体入口。
- 登录缓存增加 `apiRoutePrefix/environmentName` 标记，环境变化时会清掉旧登录态，避免生产登录缓存混入测试环境。

已验证：

- 测试后端容器 `teambuy-test` 正常运行，`https://teambuy.lifelove.top/test-health` 正常。
- `POST https://teambuy.lifelove.top/test-api/auth/mock-login` 返回测试环境业务响应，证明 `/test-api/...` 路由命中测试后端。
- `POST https://teambuy.lifelove.top/test-api/api/auth/mock-login` 返回 404，证明不能使用双 `/api` 前缀。
- `node --check` 覆盖 `app.js/request.js/api.js/login/profile/showcase-view/showcases/library/notes`：通过。
- 小程序相关 JSON 解析：通过。

## 2026-06-29：分享封面收回原生卡片比例

- 背景：
  - 用户确认上一版分享封面过度设计，视觉不如微信原生小程序卡片。
  - 新规则要求在原版卡片基础上做轻增强：标题一行，有图时图片占主体，无图时只显示 8 字以内标题重点，底部统一放“由资料整理助手生成 · 点击生成同款”。
- 已完成：
  - `business-card-share.js` 将房源、普通资料、合集、电子名片、服务方案分享封面统一收口为 `750 x 420` 原生比例。
  - 有图资料/房源/名片/服务方案直接用业务图片铺满 `imageUrl` 主体，不再在封面图内重复绘制标题，标题只交给微信外层卡片显示。
  - 分享封面图片铺满改为按原图宽高居中裁切，等同 `aspectFill`，避免名片/房源图被横向或纵向拉伸变形。
  - 无图资料只画标题重点，不再额外解释“无图资料”。
  - 底部钩子改为直接画在封面图主体图片底部白条内，避免微信只展示 `imageUrl` 中间图时看不到“由资料整理助手生成 · 点击生成同款”。
  - 合集分享封面标题自动补“合集”，主体图强制优先使用第一条资料首图，其次才用合集 banner；列表页和详情页均接入首图。
  - 分享入口撤掉原始封面图兜底：生成图未准备好时提示稍后再发，不再静默退回原图。
  - 资料库和我的笔记里的名片/服务卡底部动作收口为“发客户 + 更多”两列等宽胶囊，中间保留间距。
  - 资料库列表改为页面加载/筛选后预生成可见卡片分享图，按钮准备好后才显示可发，避免 `open-type=share` 触发时等不到异步渲染。
  - 清理 `note-preview` 里已废弃的本地分享画图函数，避免后续误接旧逻辑。
- 已验证：
  - 分享相关小程序 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

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

## 2026-06-29：移除误显示在页面上的分享 canvas

- 背景：
  - 用户真机反馈资料页/合集页顶部 banner 变成了分享卡片样式。
  - 原因是上一轮为了保证 canvas 参与渲染，把分享 canvas 放在 `left:0/top:0` 并用透明度隐藏；小程序真机 canvas 原生组件对透明度/层级不可靠，导致分享画布直接覆盖页面。
- 已完成：
  - 分享封面已改为上传 HTTPS 图片，不再需要把 canvas 放在可视区域。
  - 8 个分享画布统一恢复到屏幕外 `-9999rpx`，保留 `750rpx x 600rpx` 尺寸，不再设置 `opacity` 和 `z-index`。
- 已验证：
  - 分享相关小程序 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `git diff --check`：通过。

## 2026-06-29：重收口分享卡片有图/无图/合集规则

- 背景：
  - 用户反馈有图资料分享卡片显示成当前资料库页面截图，说明空 `imageUrl` 触发了微信默认截屏。
  - 用户确认原资料有图片时，分享卡片必须保留资料图片，不能只画纯标题卡。
- 已完成：
  - 普通资料标题营销封面支持 `coverUrl`，有图资料改为“真实资料图 + 标题摘要 + 打开完整资料 / 我也想做同款”。
  - 分享入口恢复安全兜底：营销图未准备好时使用资料原图/合集 banner/名片头像/服务封面，绝不返回空 `imageUrl` 让微信截当前页面。
  - 资料库和合集列表的 `pendingShare.imageUrl` 初始值恢复为原资料图，生成成功后再替换成营销图。
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
  - 服务方案入口从“添加 -> 服务方案”直接进入独立工作台；旧模板选择入口已由新工作台承接。
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
  - 曾新增电子名片 / 服务方案双 Tab 模板选择页；后续已由两个独立工作台直接承接模板选择。
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

## 2026-06-29 电子名片分享封面二次修正

本轮修正：

- 电子名片分享封面不再把头像或封面图铺满整张小程序卡片。
- 新增名片专属 canvas 封面：在固定横版分享图里绘制一张模板化电子名片，保留头像、姓名、职位、公司、联系方式、服务标签和“由资料整理助手生成 · 点击生成同款”。
- 名片封面按 4 类模板区分视觉：
  - 专业顾问：深蓝 + 金色。
  - 门店名片：浅绿门店风。
  - 专家介绍：黑金风。
  - 简洁微信风：白底轻量风。
- 客户页里的名片详情同步强化模板差异，避免“4 个名片模板点进去像同一个模板”。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 电子名片资料库入口补漏

本轮修正：

- 资料库 / 名片列表的“发客户”入口此前仍使用通用资料封面生成，导致用户从资料库分享名片时仍看到大图封面。
- `miniprogram/pages/library/index.js` 已改为：
  - 电子名片走 `generateBusinessCardShareImage`。
  - 服务方案走 `generateServiceOfferShareImage`。
  - 普通资料才走 `generateTitleShareImage`。
- 资料库里的名片 / 服务卡片按钮已改为复用房源卡片的按钮结构和尺寸。
- 资料列表里的名片 / 服务卡片按钮尺寸同步收窄为房源同款视觉。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 电子名片分享图比例修正

本轮修正：

- 电子名片分享图从 750x420 横图改为名片专用 600x480，适配微信聊天卡片更接近 5:4 的展示裁切。
- 混合分享 canvas 高度扩到 600rpx，兼容普通资料 750x420 和名片 600x480 两种导出。
- 名片头像绘制改为先下载并通过 `getImageInfo` 校验，拿可绘制本地 path 画头像；失败时走首字占位，避免头像位置空白。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 电子名片分享图改为 5:4 模板卡

本轮修正：

- 电子名片分享图不再把横向名片缩成小条，改为 5:4 卡片内的模板卡结构。
- 白色外卡占主要区域，上半部分展示完整名片视觉，下半部分展示模板名称、适用说明和查看入口。
- 名片内部头像、姓名、职位、模板标签、公司/联系方式、服务标签和二维码占位重新排布，避免内容挤压变形。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 电子名片分享图内容精简与头像兜底

本轮修正：

- 删除名片内部 3 个服务胶囊，避免遮挡手机号。
- 公司和联系方式下移，名片内部只保留头像、姓名、身份、模板标签、公司、联系方式和二维码占位。
- 头像兜底改为：
  - 优先使用名片数据里的头像。
  - 没有头像时使用所选名片模板自带头像。
  - 仍不可绘制时显示浅色首字占位，避免黑色空头像。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 电子名片分享头像可见性修正

本轮修正：

- 头像绘制增加白色圆形底座、主题色描边和内层白边。
- 头像图片缩进绘制，避免深色头像和深色模板重合、浅色头像和浅色背景重合。
- 无头像时仍使用浅色首字占位。

验证：

- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-29 生产后端与 PC 运营后台部署

本轮完成：

- 本地重新跑上线前检查：
  - 小程序全部 JS `node --check`：通过。
  - 小程序 JSON 解析：通过。
  - `python3 -m compileall backend`：通过。
  - `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。
- 生产服务器检查：
  - 根分区 `/dev/vda2` 使用率约 68%，本轮无需清理 Docker。
  - `teambuy-postgres-1` 健康，`teambuy-backend-1` 已重建启动。
- 部署方式：
  - 先备份线上代码到 `/home/ubuntu/teamBuy-backups/teamBuy-code-20260629-215329.tar.gz`。
  - 使用 rsync 同步本地 `backend/` 和 `docker-compose.yml`。
  - 排除 `backend/.env`、`backend/secrets/`、`backend/mock/media/` 等生产配置和运行态数据。
  - 执行 `docker compose build backend` 和 `docker compose up -d backend`。
- PC 运营后台公网入口：
  - Nginx 新增 `/ops` 和 `/ops/` 代理到 `127.0.0.1:8002`。
  - Nginx 配置已备份到 `/etc/nginx/conf.d/teambuy.conf.bak-20260629-220842`。

线上验证：

- `https://teambuy.lifelove.top/health`：200，数据库 postgres 已配置。
- `https://teambuy.lifelove.top/ops`：200，返回 PC 运营后台 HTML。
- `https://teambuy.lifelove.top/api/ops-admin/overview` 不带管理口令返回 403，说明公网 API 路由已到后端且鉴权生效。

## 2026-06-29 小程序地图接口权限修正

本轮修正：

- 移除 `app.json` 中未获权限的 `requiredPrivateInfos: ["chooseLocation"]`。
- 移除房源编辑页 `wx.chooseLocation` 调用和“手动选择地图”入口。
- 保留 `map` 组件和 `markers` 展示已有经纬度的小房子标记；该展示方式不需要腾讯地图 Key，也不需要 `chooseLocation` 权限。
- 未匹配到默认地址时提示用户补充完整地址。

验证：

- 全项目已无 `chooseLocation` / `requiredPrivateInfos` / `scope.userLocation` 引用。
- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：134 passed。

## 2026-06-30 生产 / 测试环境隔离完成

本轮完成：

- 新增 `docker-compose.test.yml`，用于在同一台腾讯云服务器上启动隔离测试环境。
- 服务器 `/home/ubuntu/teamBuy/backend/.env.test` 已由生产 `.env` 派生生成，但强制覆盖：
  - `APP_ENV=test`
  - `APP_PORT=8003`
  - `WECOM_USE_MOCK=true`
  - `WECOM_ARCHIVE_WORKER_ENABLED=false`
  - `WECOM_GROUP_BOT_WEBHOOKS={}`
  - 测试媒体目录和媒体路径。
- 启动测试容器：
  - `teambuy-test-postgres-test-1`
  - `teambuy-test-backend-test-1`
- Nginx 新增测试入口：
  - `https://teambuy.lifelove.top/test-api/`
  - `https://teambuy.lifelove.top/test-ops`
  - `https://teambuy.lifelove.top/test-health`
  - `https://teambuy.lifelove.top/test-media/`
- Nginx 改动前已备份：
  - `/etc/nginx/conf.d/teambuy.conf.bak-20260630-004042-before-test-env`
- `/test-ops` 页面通过 Nginx `sub_filter` 把后台请求从 `/api/` 改到 `/test-api/`，避免测试后台误操作生产 API。
- 新增环境隔离文档：
  - `docs/deploy-env-isolation.md`

验证：

- `https://teambuy.lifelove.top/health`：正常，生产未受影响。
- `https://teambuy.lifelove.top/test-health`：正常，测试后端和测试数据库已配置。
- `https://teambuy.lifelove.top/test-api/ops-admin/overview` 不带口令返回 403，说明测试 API 路由和鉴权生效。
- `https://teambuy.lifelove.top/test-ops` 页面里的后台请求已替换为 `/test-api/...`。

后续使用：

- 生产环境只用于小程序审核、正式用户、正式数据和正式运营入口。
- 测试环境用于群机器人运营卡片生成器、每日运营内容、测试群 webhook、资源上架实验、爬取实验、支付分销实验。

## 2026-06-30 企业微信助手首次导入自动绑定

本轮修正：

- 后端新增 `POST /api/auth/wecom-bind-intent`。
- 小程序首页点击“添加企业微信助手”时，先为当前登录用户创建短期绑定意图。
- 企业微信客服导入和会话归档导入解析未绑定 `external_userid` 时：
  - 已有绑定：直接归属到对应用户。
  - 没有绑定但存在唯一有效绑定意图：自动建立绑定，资料直接进入该用户账号。
  - 多个有效绑定意图并存：不自动绑定，继续进入待认领，避免串用户。
  - 可选自营测试默认归属：`WECOM_UNCLAIMED_DEFAULT_OWNER_USER_ID`，默认空。
- 保留原来的认领链接 / 待认领兜底链路。

验证：

- 新增自动绑定测试和多意图防误绑测试。
- 小程序全部 JS `node --check`：通过。
- 小程序 JSON 解析：通过。
- `python3 -m compileall backend/app`：通过。
- `./.venv312/bin/python -m pytest backend/tests/test_app.py -q`：136 passed。
## 2026-06-30 资源工具与商机雷达产品方案

本轮新增：

- `docs/stage2-docs/33-resource-tools-opportunity-radar-v1.md`

本轮明确：

- 资源工具不是工具集合，而是“小生意人的机会雷达入口”。
- 商机线索不应只是普通需求广场，应拆成：
  - 需求广场
  - 我的机会
  - 订阅
  - 已保存
- 前台不强调微博、小红书等第三方来源，可统一表达为“官方收录 / 公开线索”；后台必须保留完整来源用于去重、风控和追溯。
- 与四个工作台打通的含义不是替用户发布第三方线索，而是用户看到机会后，可用自己的房源、商品、服务、名片和合集生成回应资料。
- 现有资源积分仍是小程序本地缓存，适合演示，不适合正式上线，后续需要后端化账本。
## 2026-06-30 商机线索页面 UI 规格与验收标准

本轮新增：

- `docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md`

本轮明确：

- UI 规格文档不能替代真机验收。
- 商机线索页面必须按“静态 UI 截图验收 -> mock 数据 -> 接口联调 -> 真机截图复验”的流程开发。
- 关键不得简化项：
  - 我的机会页不能删除雷达图。
  - 线索详情页必须突出“生成回应资料”。
  - 已保存页不能做成普通收藏夹，必须体现跟进状态。
- 开发交付必须说明当前是否为参考图版本，并提供真机截图。
## 2026-06-30 供需广场与用户发布供给卡方案

本轮补充：

- `docs/stage2-docs/33-resource-tools-opportunity-radar-v1.md`
- `docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md`

新增关键产品点：

- 需求广场可升级为供需广场。
- 用户不仅能看官方收录的需求，也可以把自己整理好的资料、服务页、房源合集、商品合集、电子名片发布为“我能提供”的供给卡。
- 发布供给优先选择已有资料，而不是重新填写长表单。
- 供给卡进入广场后，别人可查看资料、保存、申请联系；发布者可在“我的发布”里查看展示、保存和雷达反馈。

该点把资料整理能力从“发给客户”升级为“被需求方发现”。

## 2026-06-30 回应包与双向收费方案

本轮新增：

- `docs/stage2-docs/35-response-package-monetization-v1.md`

同步补充：

- `docs/stage2-docs/33-resource-tools-opportunity-radar-v1.md`
- `docs/stage2-docs/34-opportunity-leads-ui-spec-v1.md`

核心明确：

- 回应包不是普通 AI 文案，而是“资料推荐 + 首次话术 + 追踪链接 + 跟进建议”的成交资料包。
- 回应包主要服务供给方回应具体需求，系统不自动替用户联系对方。
- 免费额度可先给新用户 5 次 / 普通用户每月 3 次，后续再接积分、会员和供给方收费。
- 双向收费后置，前期优先收供给方，因为供给方成交动机更强。
- 保证金用于服务可信认证和违规约束，不表达为平台担保成交。

## 2026-06-30 商机线索二期开发清单

本轮新增：

- `docs/stage2-docs/36-opportunity-radar-phase2-dev-checklist.md`

核心拆解：

- P0 先做后端积分账本，避免用户退出重登或换设备后积分重置。
- 商机线索先做数据模型、后台录入、小程序静态 UI、真实接口、回应包 P0、PC 后台增强。
- 支付、会员、保证金、双向收费、自动爬虫和自动联系全部后置。
- 二期完成标准是用户链路和运营链路都跑通。

## 2026-06-30 企业微信助手绑定码方案

本轮实现：

- 后端 `POST /api/auth/wecom-bind-intent` 返回 `bindCode` 和 `bindMessage`。
- 小程序首页企业微信助手入口会创建绑定意图，并复制 `绑定资料助手 TB-XXXXXX`。
- 后端客服同步消息导入前会识别绑定码消息，完成绑定后不生成资料。
- 后端会话归档处理前会识别绑定码消息，完成绑定后标记该归档消息已处理。
- 后续同一 `external_userid` 的资料自动归属到对应小程序用户。

已验证：

- 绑定码客服消息只绑定不入库。
- 绑定后再发 mock 房源资料可自动归属到用户。
- 会话归档先发绑定码、再发房源资料可自动归属到用户。
- 小程序首页 JS 静态检查通过。

## 2026-06-30 企业微信批量房源导入修复

本轮修复：

- 批量房源解析器补充编号清理规则，支持 `1）`、`4)` 等编号。
- 补充 `朝南次卧`、`次卧`、`主卧`、`大厅一室户` 等房型识别。
- 企业微信客服同步和会话归档导入已绑定用户时，先尝试批量房源拆分。
- 命中批量房源后，自动生成多条 `property_listing` 资料，不再只生成一条普通资料。
- 批量房源 note 标记 `recognitionConfidence.level = high`，来源为 `property_batch_parser`。

已验证：

- 用户提供的挂牌清单可拆出 7 条房源。
- 会话归档导入同样可自动拆出 7 条房源。
- 绑定码相关测试仍通过。
- 后端完整测试 140 条通过。

## 2026-06-30 小程序添加资料助手引导层

本轮优化：

- 首页点击“添加房源助手 / 加企业微信助手”后，不再只弹系统提示。
- 绑定码生成并复制成功后，打开自定义引导层。
- 引导层展示绑定话术、三步操作说明、重新复制和“我去发送”按钮。
- 明确提示小程序不能替用户自动发送消息，需要用户在企业微信聊天里手动发送一次。

已验证：

- 首页 JS 静态检查通过。
- 小程序 JSON 校验通过。

## 2026-07-01 添加资料助手二维码位与短胶囊按钮

本轮优化：

- 添加资料助手引导层补充二维码区域。
- 绑定话术仍在打开弹层时自动复制，用户添加企业微信后可直接粘贴发送。
- 底部按钮改为居中的短胶囊，避免铺满整行或互相挤压。

- 企业微信资料助手真实二维码已接入 `miniprogram/static/wecom/assistant-qrcode.png`。

## 2026-07-01 企业微信绑定码复用与已绑定提示

本轮修复：

- 同一个小程序用户已有有效绑定码时，重复点击添加助手返回同一个绑定码，不再每次生成新码。
- 用户已经绑定企业微信外部联系人后，后端返回 `status=bound`，不再返回绑定话术。
- 小程序收到已绑定状态后，只提示“资料助手已绑定，可以直接转发资料”，不再展示二维码和绑定码。

已验证：

- 相关绑定码测试 5 条通过。
- 后端完整测试 142 条通过。
- 小程序首页 JS 静态检查通过。

## 2026-07-01 资料列表发客户不再等待分享图

本轮优化：

- 资料列表“发客户”按钮不再依赖 canvas 分享图生成完成。
- 有首图的资料直接使用首图作为微信分享图，避免等待隐藏 canvas 绘制和上传。
- 没有首图的资料也允许先发客户，只是不带自定义分享图。
- 只有缺少 `sourceNoteId`、无法打开客户页的资料才禁用按钮，并显示“先编辑”。

已验证：

- `node --check miniprogram/pages/library/index.js` 通过。

## 2026-07-01 房源编辑封面、复制和商圈候选修正

本轮优化：

- 房源编辑页切换封面时，同步更新 `structuredData.coverUrl` 和图片列表，客户预览/房源卡片会跟随新封面。
- 资料列表卡片封面增加兜底：没有 `coverUrl` 时直接使用第一张图片媒体作为缩略图。
- 上游备注“复制全部”改为从页面状态读取，不再把整段文本塞进 DOM dataset。
- “复制全部”和单项“复制”增加按压变深效果，并补充复制失败提示。
- 商圈/区域快捷候选去掉本地写死项，改为从原文、标题、备注、地址和已识别字段提取；固定兜底只保留“人民广场 / 五一广场”。

已验证：

- `node --check miniprogram/pages/note-edit/index.js` 通过。
- `node --check miniprogram/services/api.js` 通过。
- `node --check miniprogram/utils/note-display.js` 通过。
- `git diff --check` 通过。

## 2026-07-01 二期测试前端切回测试环境

本轮调整：

- 小程序全局配置 `miniprogram/app.js` 切为测试环境：
  - `apiBaseUrl=https://teambuy.lifelove.top`
  - `apiRoutePrefix=/test-api`
  - `mediaRoutePrefix=/test-media`
  - `environmentName=test`
- 环境切换后会清理旧登录缓存，避免生产登录态混入测试环境。

已验证：

- `node --check miniprogram/app.js` 通过。
- URL 拼接：`/api/cards` -> `https://teambuy.lifelove.top/test-api/cards`。
- `GET https://teambuy.lifelove.top/test-api/cards` 返回 200。

## 2026-07-01 表格式多套房源归档拆分规则

本轮修复：

- 批量房源入口先归一化 keycap emoji 数字，例如 `1️⃣2️⃣5️⃣0️⃣` -> `1250`。
- 批量房源识别补充“区域标题 / 楼栋行 / 房号价格行”表格式规则。
- 支持类似“新时代广场... / 1925南栋 / 2号房一1250”的多套公寓房源表拆分。
- “微信同号”会把识别到的手机号同步写入上游微信私密字段。
- 上游电话、微信同号、佣金仍进入私密数据；客户页不公开展示。

已验证：

- `pytest backend/tests/test_app.py -q -k "property_batch"` 通过，6 条批量房源相关测试全部通过。

补充验证：

- 重新读取 `/Users/yiyi/Desktop/房源样本.docx`。
- 文字样本 001-006 已全部通过本地解析稳定性检查：
  - 样本 001：预期 13，实际 13，归档入口命中。
  - 样本 002：预期 12，实际 12，归档入口命中。
  - 样本 003：预期 6，实际 6，归档入口命中。
  - 样本 004：预期 4，实际 4，归档入口命中。
  - 样本 005：预期 5，实际 5，归档入口命中。
  - 样本 006：预期 8，实际 8，归档入口命中。
- 新增回归覆盖字段块房源、元/月清单、地址后接房号价格、价格区间、空置尾缀等真实格式。
- 图片样本 007 属于 OCR 链路，本轮未用文字解析器直接验收。

已验证：

- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "property_batch"` 通过，7 条批量房源相关测试全部通过。
- 原始 docx 文字样本复测 `ALL_OK=True`。

部署：

- 已备份服务器当前后端文件：`/home/ubuntu/teamBuy/backend/backups/codex-20260701-162139-property-batch-text/app_service.py`。
- 已将批量房源文字规则最小补丁同步到测试容器 `teambuy-test-backend-test-1` 和生产容器 `teambuy-backend-1`。
- 两个容器均已重启，并在容器内验证 15:39 样本 + docx 001-006 全部通过。
- 公网验证：
  - `https://teambuy.lifelove.top/health` 返回 200。
  - `https://teambuy.lifelove.top/test-api/cards` 返回 200。
  - `https://teambuy.lifelove.top/api/cards` 返回 200。

## 2026-07-01 图片样本 007 OCR 验证与防误拆

本轮验证：

- 从 `/Users/yiyi/Desktop/房源样本.docx` 抽取图片样本 007：`/tmp/property_docx_media/image1.png`。
- 测试环境真实 OCR 配置为 `OCR_PROVIDER=paddle`。
- 直接识别原图结果：
  - OCR configured=true。
  - confidence 约 0.816。
  - 只识别出 26 行。
  - 表格大量小字、房号、价格串行或漏识别。
  - 当前解析器只能从低质 OCR 文本中误拆 4 条，不满足“太多套”预期。
- 尝试 2x/3x 切块增强后，Paddle 同步识别耗时过长，不适合直接阻塞用户请求。

本轮修复：

- OCR 批量房源新增防误拆保护：当 OCR 文本明显是表格式房源图，但只解析出少量候选时，不自动创建房源合集。
- 这样 007 当前不会误生成 4 条错误房源，而是保留 OCR 笔记，等待后续 OCR 表格后处理。

已验证：

- 本地 `pytest backend/tests/test_app.py -q -k "ocr_recognized_property_batch or ocr_table_like_low_yield or property_batch"`：8 passed。
- 已同步测试后端和生产后端。
- 容器内验证：
  - 15:39 文字样本仍拆 8 套。
  - 007 低质 OCR 文本解析出 4 条，但触发 manual review 防误拆。
- 公网 `/health`、`/test-api/cards`、`/api/cards` 均返回 200。

补充专项实验：

- 使用 OpenCV 对 007 原图做表格线检测，能稳定检测到 5 个业务列：区域、商圈、房源地址、户型、月租。
- 横线可切出约 163 个行区间。
- 改为“单行裁剪 + 4 倍放大 + 单进程 PaddleOCR”后，全表 OCR 约 51 秒完成。
- 全表得到 159 行有效 OCR 文本，头尾数据均可读，例如：
  - `芙蓉区 人民东路 碧桂园城市之光5号1016 1室1厅1卫 1,400.00`
  - `雨花区 高桥 正荣悦玺1号2207B 1室1厅1卫 1,100.00`
- 对 OCR 行文本做规则解析后，159 行中 156 行可结构化为房源候选。
- 失败样式主要是：
  - 区域/商圈顺序错位，例如 `金盆岭 天心区 ...`。
  - `星沙` 这类非“区”结尾区域和路名地址边界需要专项规则。
  - 极少数行价格漏识别。

结论：

- 007 可以做，但不能走当前整图 OCR。
- 可行路线是新增“表格房源图片 OCR”专项 worker：检测网格 -> 按行裁剪 -> 单进程 OCR -> 行文本结构化 -> 生成批量房源候选。
- 该链路耗时约 50 秒，应设计为后台任务或明确等待态，不适合阻塞普通上传请求。

## 2026-07-01 OCR 后台任务架构本地改造

本轮改造：

- 新增 `BackgroundTaskWorker`，可按任务名从 `SyncTaskQueue` 拉取待执行任务。
- `SyncTaskQueue` 增加 `auto_schedule`、任务名过滤、`max_running` 和 `max_to_schedule`，用于 API 入队但不立即执行。
- 图片上传/识别相关接口改为：保存图片资料 -> 创建 `ocr-recognize-note` 任务 -> 标记 OCR `queued` -> 返回 `syncTask`。
- 新增 `mark_ocr_note_queued`，让前端可直接展示“识别中”而不是卡在请求等待。
- 新增 `backend/app/worker.py`，作为后台 worker 入口。
- `docker-compose.yml` 拆分：
  - `backend`：API 进程，关闭 OCR/归档后台任务。
  - `backend-worker`：OCR 队列 worker，默认 `OCR_TASK_CONCURRENCY=1`。
  - `archive-worker`：企业微信会话归档 worker。
- 预留 `property-table-ocr` 任务名，但当前仍复用普通 OCR handler；007 表格检测、切行和结构化算法尚未接入正式 worker。

已验证：

- `.venv312/bin/python -m compileall -q backend/app backend/tests` 通过。
- `.venv312/bin/python -m pytest backend/tests/test_app.py backend/tests/test_sync_task_queue.py -q -k "ocr or image_capture or property_batch or archive_worker or sync_task"`：19 passed。
- `git diff --check` 通过。

## 2026-07-01 007 表格 OCR 专项 worker 接入

本轮改造：

- 新增 `PropertyTableOcrService` 和 `property_table_ocr_worker`。
- 普通 OCR 后台任务会先做表格线检测；命中表格图时自动转入专项表格 OCR，不需要前端额外按钮。
- `property-table-ocr` 队列任务已注册到 `recognize_property_table_ocr_note_image`，不再复用普通 OCR handler。
- 表格 OCR 流程为：OpenCV 检测表格线 -> 按行裁剪 -> 单进程 PaddleOCR -> 行文本结构化 -> 批量生成房源候选。
- 表格行解析支持 `1,400.00`、`1, 600. 00` 这类 OCR 价格格式，统一归一为 `1400元/月`。
- 生成的批量房源使用 `sourceType=ocr_property_table`，源 OCR note 记录 `ocrSourceNoteId`。

真实 007 验证：

- 使用 `/tmp/property_docx_media/image1.png` 对应的 `/Users/yiyi/Desktop/房源样本.docx` 图片样本。
- 生产 worker 容器表格检测结果：
  - `tableLike=true`
  - 检测到竖线 `[0, 136, 330, 636, 765, 893]`
  - 检测到约 167 个行区间。
- 生产 worker 完整 OCR：
  - `configured=true`
  - confidence 约 `0.989`
  - 有效文本 163 行。
- 生产解析器结构化结果：
  - 从真实 OCR 文本中解析出 159 套房源候选。
  - 示例：`碧桂园城市之光5号1016 · 1室1厅1卫 · 1400元/月`。
  - 尾部示例：`正荣悦玺1号2207B · 1室1厅1卫 · 1100元/月`。

部署：

- 已部署生产后端三进程架构。
- 新增文件已同步生产：
  - `backend/app/services/property_table_ocr_service.py`
  - `backend/app/services/property_table_ocr_worker.py`
- 对生产 `app_service.py` 和 `dependencies.py` 采用最小补丁，没有整文件覆盖。
- 服务器备份目录：`backend/backups/codex-20260701-*-property-table-ocr`。

验证：

- 本地 `.venv312/bin/python -m compileall -q backend/app backend/tests` 通过。
- 本地 `.venv312/bin/python -m pytest backend/tests/test_app.py backend/tests/test_sync_task_queue.py -q -k "ocr or image_capture or property_batch or archive_worker or sync_task"`：20 passed。
- `git diff --check` 通过。
- 公网 `https://teambuy.lifelove.top/health` 返回 200。
- 生产容器 `backend`、`backend-worker`、`archive-worker` 均 Up。

注意：

- 为避免污染生产账号，本轮没有通过公网 API 直接上传 007 并生成 159 条测试房源；已在生产容器内分别验证表格检测、完整 OCR 和结构化解析。
- 后续真机上传 007 时，会由普通 OCR 任务自动检测表格图并进入专项流程。

待上线动作：

- 已于 2026-07-01 20:52 部署到生产服务器。
- 服务器备份目录：`/home/ubuntu/teamBuy/backend/backups/codex-20260701-203506-ocr-worker-arch`。
- 当前生产容器：
  - `teambuy-backend-1`：API。
  - `teambuy-backend-worker-1`：OCR 后台队列 worker。
  - `teambuy-archive-worker-1`：企业微信会话归档 worker。
- `docker compose config --services` 已确认包含 `postgres/backend/backend-worker/archive-worker`。
- 已补 `DATABASE_REQUIRE_POSTGRES=true`，生产 Postgres 连接失败时不再静默 fallback 到 JSON。
- 已补 `pg_advisory_xact_lock(81207008435)`，避免三个进程同时启动执行 schema 初始化时互相 deadlock。
- 公网验证：
  - `https://teambuy.lifelove.top/health` 返回 200。
  - `/api/ocr/images` 上传测试图立即返回 `ocr.status=queued` 和 `syncTask`。
  - OCR worker 约 10 秒后消费任务，测试任务 `sync_task_aaa9d6e9c2ff4556b20177ac14eaa60a` 状态为 `success`。
  - 对应测试 note `note_5ba04883aa` 从 `queued` 更新为 `empty`，provider 为 `paddle`。

部署中发现并修复：

- API 进程曾因 Postgres 初始化异常静默 fallback 到 `/backend/mock/runtime-state.json`，导致 API 能看到 note、worker/Postgres 看不到 task；已通过 `DATABASE_REQUIRE_POSTGRES=true` 防止生产再次分裂。
- 三个进程同时 `init_schema()` 时曾出现 Postgres DDL deadlock；已通过 advisory lock 串行化 schema 初始化。
- 曾误将本地完整 `repository.py` 拷贝到服务器，带入未上线的商机模型导入导致服务启动失败；已恢复服务器线上系 repository，并只补最小 patch。

本地验证：

- `.venv312/bin/python -m compileall -q backend/app backend/tests` 通过。
- `.venv312/bin/python -m pytest backend/tests/test_app.py backend/tests/test_sync_task_queue.py -q -k "ocr or image_capture or property_batch or archive_worker or sync_task"`：19 passed。
- `git diff --check` 通过。

## 2026-07-01 商机线索 P0 第 4/5 片：小程序接接口与回应包 P0

本轮改造：

- 后端新增回应包 P0 链路：
  - `POST /api/opportunity-leads/{id}/response-packages/preview`
  - `POST /api/opportunity-leads/{id}/response-packages`
  - `GET /api/response-packages/{id}`
  - `POST /api/response-packages/{id}/events`
- 回应包内容包括：商机摘要、推荐资料、首次联系话术、跟进建议和小程序追踪路径。
- 预览不扣积分；正式生成先用每月免费额度，再按 20 积分消耗。
- 同一用户对同一商机重复生成回应包，返回已有回应包，不重复扣积分。
- 生成回应包后自动把商机保存为“跟进中”，并写入一条跟进记录。
- 小程序商机页由静态数据改为真实接口优先、mock 兜底：
  - 我的机会
  - 供需广场
  - 线索详情
  - 已保存线索
  - 新增回应包页

已验证：

- `node --check` 覆盖 `miniprogram/services/api.js` 和商机/回应包相关页面 JS，全部通过。
- 小程序 `app.json` 和相关页面 JSON 解析通过。
- `DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-response-package.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "response_package or opportunity_lead or resource_wallet"`：11 passed。
- `DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-response-package.json .venv312/bin/python -m compileall -q backend/app` 通过。
- `git diff --check` 通过。

全量测试说明：

- 使用本地 JSON 测试库跑全量后端测试：198 passed、1 failed。
- 失败项为 `test_health_reports_database_configuration` 固定断言数据库 backend 是 `postgres`，而本次为避开本机 Postgres 密码问题使用了 `DATABASE_BACKEND=json`。
- 本次新增和改动相关的商机、回应包、资源积分测试全部通过。

待确认：

- 后端接口仍需部署到测试环境后，小程序真实接口才能拿到最新 P0 回应包数据。
- 小程序体验版需要用户在微信开发者工具中重新预览/上传。

## 2026-07-01 商机线索 P0 第 6 片：PC 后台增强

本轮改造：

- PC 运营后台新增二期能力：
  - 商机线索看板：今日资源工具人数、今日积分消耗、今日回应包、线索状态统计。
  - 商机线索列表新增回应包数量和快捷下架。
  - 新增“积分账本”Tab：用户积分列表、余额/发放/消耗/流水、人工调整积分。
  - 新增“回应包记录”Tab：查看回应包、所属用户、关联商机、资料数、积分消耗、最近打开。
- 后端新增运营接口：
  - `GET /api/ops/opportunity-dashboard`
  - `POST /api/ops/opportunity-leads/{lead_id}/offline`
  - `GET /api/ops/resource-wallet/users`
  - `POST /api/ops/resource-wallet/users/{user_id}/adjust`
  - `GET /api/ops/response-packages`
- 所有新增运营接口继续使用 `X-Admin-Token` 鉴权。

已验证：

- `DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-ops-pc.json .venv312/bin/python -m pytest backend/tests/test_app.py -q -k "ops_opportunity_dashboard or response_package or opportunity_lead or resource_wallet"`：12 passed。
- `DATABASE_BACKEND=json DATABASE_URL= DATA_FILE=/tmp/teambuy-test-ops-pc.json .venv312/bin/python -m compileall -q backend/app` 通过。
- 提取 `backend/app/static/ops-admin/index.html` 内 `<script>` 后用 Node `new Function(...)` 检查通过。

待确认：

- 需要部署测试后端后，在 `/ops` 页面用管理员 Token 真机/浏览器确认表格和操作。
- 供给卡审核仍未做独立模型和审核流，当前 P0 先覆盖商机、积分、回应包和反馈工单。

## 2026-07-02 商机 P1 真机测试：测试后端未同步导致订阅/发布保存 404

现象：

- 小程序当前仍连接测试环境：`apiBaseUrl=https://teambuy.lifelove.top`、`apiRoutePrefix=/test-api`。
- 真机进入“订阅雷达”提示“订阅读取失败”，保存失败。
- 真机进入“发布供需”点击保存/提交返回 `Not Found`。

排查：

- 本地 FastAPI 已注册：
  - `GET/POST /api/opportunity-subscriptions`
  - `GET/POST/PUT /api/supply-demand/cards`
  - `POST /api/supply-demand/cards/{card_id}/submit`
- 公网测试环境仍返回 404：
  - `https://teambuy.lifelove.top/test-api/opportunity-subscriptions/me?userId=route_check` -> 404 `{"detail":"Not Found"}`
  - `https://teambuy.lifelove.top/test-api/supply-demand/cards` -> 404 `{"detail":"Not Found"}`

处理：

- 前端已把这类 404 的 toast 优化为“测试后端未同步接口”，避免继续显示英文 `Not Found`。
- 本轮未部署生产，也未部署测试后端。

下一步：

- 需要只部署测试环境后端，使 `/test-api/opportunity-subscriptions/*` 和 `/test-api/supply-demand/cards/*` 生效。
- 部署后再用真机回归：订阅读取、订阅保存、发布供需保存草稿、提交审核、我的发布编辑回填。

## 2026-07-02 资料库分享封面勾子统一

本轮改造：

- 资料库发客户不再把原首图裸用作 `imageUrl`。
- 所有可发客户的资料卡都走分享图生成：
  - 有封面：用首图按比例裁切，并叠加底部“由资料整理助手生成 · 点击生成同款”。
  - 无封面：生成标题图，并叠加同样底部勾子。
- 分享图未准备好时，按钮显示“封面准备中”，点击时提示稍后再发，避免发出没有勾子的默认卡片。

验证：

- `node --check miniprogram/pages/library/index.js && node --check miniprogram/utils/business-card-share.js && node --check miniprogram/pages/showcases/index.js && node --check miniprogram/pages/showcase-view/index.js && node --check miniprogram/pages/note-preview/index.js` 通过。
- `git diff --check` 通过。

## 2026-07-02 二期页面统一分享 imageUrl 层

本轮改造：

- 新增 `miniprogram/utils/universal-share.js`：
  - 统一生成带底部勾子的分享图。
  - 有封面时复用首图裁切，无图时走标题图。
  - 统一返回 `title/path/imageUrl`。
- 新增全局隐藏 canvas 样式 `.universal-share-canvas`。
- 二期 10 个页面接入 `onShareAppMessage`：
  - `opportunity-radar`
  - `opportunity-market`
  - `opportunity-detail`
  - `opportunity-saved`
  - `opportunity-subscription`
  - `response-package`
  - `response-package-radar`
  - `supply-demand-detail`
  - `supply-demand-my`
  - `supply-demand-publish`

验证：

- 10 个二期页面 JS + `utils/universal-share.js` `node --check` 通过。
- 10 个二期页面 WXML 均包含 `canvas-id="universalShareCanvas"`。
- `git diff --check` 通过。

未做：

- 未部署测试后端，未部署生产，未上传小程序。
- 分享图真机显示仍需用户上传/预览小程序后验证。

## 2026-07-02 测试后端同步商机 P1 路由

本轮处理：

- 只处理测试环境，不碰生产环境。
- 服务器备份路径：`/home/ubuntu/teamBuy-deploy-backups/20260702-103933-p1-test-routes`。
- 标准测试 compose build 卡在系统依赖阶段，已中止；旧测试容器保持运行。
- 修正同步路径后，将本地 `backend/app` 热同步到测试容器真实加载目录 `/app/app/`，并重启 `teambuy-test-backend-test-1`。

验证：

- 测试容器路由表已包含商机 P1 路由。
- `GET https://teambuy.lifelove.top/test-health` 返回 200，数据库为 postgres。
- `GET https://teambuy.lifelove.top/test-api/opportunity-subscriptions/me?userId=user_a732f38f21` 返回 200。
- `POST https://teambuy.lifelove.top/test-api/opportunity-subscriptions` 返回 200。
- `GET https://teambuy.lifelove.top/test-api/supply-demand/cards` 返回 200。
- `POST https://teambuy.lifelove.top/test-api/supply-demand/cards` 返回 200。
- `GET https://teambuy.lifelove.top/test-api/opportunity-leads?userId=user_a732f38f21` 返回 200。

清理：

- 探测创建的订阅 `opp_sub_e863a027c7` 已 DELETE，状态为 deleted。
- 探测创建的供需卡 `sd_17ca6283ba` 已 PUT 为 archived。

注意：

- 因为 `GET /api/supply-demand/cards/me` 当前会返回 archived 记录，真机“我的发布”如果看到“测试供需发布”，它是已归档的探测数据。
- 本轮未部署生产，未上传小程序。
# 2026-07-02 资料详情胶囊、个人头像交互与前端缓存

本轮处理：

- 个人资料弹窗：
  - 删除独立“选择头像”按钮。
  - 改为点击头像本身触发微信 `chooseAvatar`。
  - 头像居中展示。
- 资料详情页胶囊：
  - 统一候选类型、功能组、快捷选项、状态标签、预览标签和媒体角标的胶囊尺寸。
  - 胶囊字体、背景块高度、内边距缩小，横向间距加大。
  - 保持 flex 居中和不换行。
- 前端缓存：
  - `miniprogram/services/api.js` 新增用户级 note 列表/详情缓存。
  - 缓存 key 按环境、API 前缀、用户、查询条件隔离。
  - 资料详情页先读缓存再拉后端。
  - 旧“我的笔记”列表先读缓存再刷新。
  - 资料库页不再强制绕过 `resource-store` 缓存。
  - `resource-store` 支持从本地 storage 直接返回卡片/分类缓存。

验证：

- `node --check` 覆盖 profile、note-edit、notes、library、api、resource-store，全部通过。
- 小程序相关 JSON 校验通过。
- `git diff --check` 通过。

注意：

- 后端缓存本轮未直接实现，避免 OCR/归档 worker 写入后读旧数据；后续建议用 ETag/短 TTL/写入失效。
- 前端缓存需要重新上传小程序后才生效。

# 2026-07-02 商机/服务纠错入口与规则样本池

本轮处理：

- 小程序资料详情页普通笔记候选规则新增商机/服务兜底：
  - 建站、推广、落地页、独立站、官网商城、小程序开发、服务器、CDN、源码交付、返点、联系电话等信号会出现“商机合作”候选。
- 调整资料详情页候选按钮和功能按钮：
  - 候选按钮改为两列，间距更大。
  - 胶囊高度、字体和背景视觉减小，避免真机上显得过重。
- 后端确认类型接口记录规则学习样本：
  - 用户把资料从普通笔记切到房源/商品/商机/服务时，写入 `OpsConsoleStore.ruleLearningSamples`。
  - 记录原类型、选择类型、原文、识别解释和标签。
- PC 运营后台新增“规则样本池”：
  - 支持按状态和类型筛选。
  - 支持将样本标记为确认或拒绝。
  - 第一版不自动发布全局规则。

验证：

- `node --check miniprogram/pages/login/index.js` 通过。
- `node --check miniprogram/pages/note-edit/index.js` 通过。
- PC 后台内联脚本 `node --check` 通过。
- `PYTHONPATH=backend .venv312/bin/python` 验证规则样本池存取通过。
- `.venv312/bin/python -m compileall -q backend/app backend/tests` 通过。
- `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "confirm_plain_rental_note or quick_capture or owner_contact"`：10 passed。
- `git diff --check` 通过。

注意：

- 本轮未部署生产，未上传小程序。
- PC 后台“确认样本”只是审核样本，不会自动改变全局识别规则；后续需要做“规则配置发布 + 历史样本回归”。

# 2026-07-02 登录页缩略图真机稳定性修复

本轮处理：

- 将登录页左侧房源缩略图从 `login-room.webp` 转为 `login-room.jpg`。
- 新图尺寸为 360x270，体积约 21KB。
- 登录页引用改为 `/static/workspace/login-room.jpg`。
- 图片加载失败时展示“房”字兜底，避免真机出现空白块。

验证：

- 已确认生成的 JPG 文件存在，格式为 JPEG，尺寸 360x270。
- 后续仍需用户在微信开发者工具重新上传体验版后真机确认。

# 2026-07-02 生产热修基线归档与二期合并准备

本轮处理：

- 已从生产服务器 `/home/ubuntu/teamBuy` 拉取当前线上关键文件，归档到 `artifacts/prod-baseline-20260702-ocr-property/`。
- 归档范围包括：
  - `docker-compose.yml`
  - `backend/app/api/dependencies.py`
  - `backend/app/worker.py`
  - `backend/app/services/app_service.py`
  - `backend/app/services/repository.py`
  - `backend/app/services/sync_task_queue.py`
  - `backend/app/services/background_task_worker.py`
  - `backend/app/services/property_table_ocr_service.py`
  - `backend/app/services/property_table_ocr_worker.py`
- 已确认生产容器当前状态：
  - `teambuy-backend-1` Up
  - `teambuy-backend-worker-1` Up
  - `teambuy-archive-worker-1` Up
  - `teambuy-postgres-1` healthy
- 已新增合并计划文档：`docs/stage2-docs/37-production-hotfix-merge-plan.md`。

合并判断：

- 本地和生产一致的重点文件：`docker-compose.yml`、`dependencies.py`、`worker.py`、`sync_task_queue.py`、`background_task_worker.py`、`property_table_ocr_service.py`、`property_table_ocr_worker.py`。
- 高风险人工合并文件：`app_service.py`、`repository.py`。
- 原因：本地这两个文件已经包含二期商机/资源钱包/供需能力，生产版本包含已上线 OCR/房源热修，二期上线前必须统一合并。

下一步：

- 将生产热修整理为独立 commit 或基线分支。
- 将二期后端代码合入该基线。
- 在统一分支上完成 OCR、007 表格 OCR、批量房源、单条房源识别、会话归档 worker 回归。

# 2026-07-02 个人资料弹层交互微调

本轮处理：

- 个人资料弹层关闭按钮改为右上角透明点击区，去掉浅色胶囊背景。
- 头像选择改为点击头像本身，去掉头像背后的浅色背景。
- 弹层遮罩空白处继续支持点击关闭，弹层内部点击不误关闭。
- 字段顺序调整为昵称、手机号、微信号。
- 微信号处新增“手机微信同号”，点击后把手机号填入微信号。
- 头像继续使用微信原生 `open-type="chooseAvatar"`，昵称输入框继续使用 `type="nickname"`。

验证：

- `node --check miniprogram/pages/profile/index.js` 通过。
- `python3 -m json.tool miniprogram/pages/profile/index.json >/dev/null` 通过。

# 2026-07-02 规则样本池部署到测试后端

本轮处理：

- 只同步测试后端，未碰生产后端。
- 服务器备份：`/home/ubuntu/teamBuy-deploy-backups/20260702-140814-rule-learning-test`。
- 同步本地 `backend/app` 到测试服务器 `/home/ubuntu/teamBuy/backend/app`。
- 热同步到测试容器：`docker cp backend/app/. teambuy-test-backend-test-1:/app/app/`。
- 重启测试容器：`teambuy-test-backend-test-1`。

验证：

- 本地 `.venv312/bin/python -m compileall -q backend/app backend/tests` 通过。
- 本地 `.venv312/bin/python -m pytest backend/tests/test_app.py -q -k "confirm_plain_rental_note or quick_capture or owner_contact or rule"`：10 passed。
- 本地 `.venv312/bin/python -m pytest backend/tests/test_skill_router.py -q`：14 passed。
- 公网 `https://teambuy.lifelove.top/test-health` 返回 200。
- 公网 `/test-api/ops-admin/rule-learning-samples` 无 Token 返回 403，确认不是 404。
- 公网带测试管理员 Token 请求 `/test-api/ops-admin/rule-learning-samples?cardType=service_offer` 返回 200。
- 用测试账号创建临时笔记并确认类型为 `service_offer` 后，样本池生成 `rule_sample_7582ffaf54`；随后已将该验证样本标记为 `rejected`，并删除临时笔记 `note_8a82e792af`。

注意：

- 当前部署完成的是“用户纠错/确认类型 -> 进入规则样本池 -> PC 后台人工审核”的收集闭环。
- “审核通过后自动发布为全局规则并影响后续高置信分类”仍未完成，需要后续继续开发。

补充：

- 修复 PC 测试后台 `/test-ops` 页面接口前缀：
  - 生产 `/ops` 继续请求 `/api/...`。
  - 测试 `/test-ops` 自动请求 `/test-api/...`。
- 已同步更新后的 `backend/app/static/ops-admin/index.html` 到测试后端容器。

# 2026-07-02 资料库统一入口实验版

本轮处理：

- 底部 Tab 的 `pages/library` 改为统一资料库：
  - 默认展示全部资料，不再按当前工作场景自动过滤。
  - 新增类型筛选：全部、房源、商机、服务、商品、日常。
  - 类型筛选在前端本地完成，减少切换等待。
  - 房源/商品筛选面板在选择对应类型时展示。
- `pages/notes` 也同步改成统一资料库文案和本地类型筛选：
  - 后端只按搜索/来源/标签/专题取数。
  - 房源、商机、服务、商品、日常、待确认在前端本地切换。

验证：

- `node --check miniprogram/pages/library/index.js` 通过。
- `node --check miniprogram/pages/notes/index.js` 通过。
- `python3 -m json.tool miniprogram/pages/library/index.json >/dev/null` 通过。
- `python3 -m json.tool miniprogram/pages/notes/index.json >/dev/null` 通过。
- `git diff --check` 通过。

注意：

- 本轮只改小程序前端和文档，未部署后端。
- 首页/雷达仍保留工作场景概念；本轮先验证“资料库统一入口”的体验。

补充：

- 首页 `pages/home` 也改为统一入口版：
  - 移除首屏“四场景选择”弹窗。
  - 移除顶部“当前场景 / 切换场景”入口。
  - 首页标题改为“今天收到的资料”。
  - 首屏固定三个主入口：添加资料、查看资料库、客户雷达。
  - 房源、商机、服务、商品、合集改成“快捷工具”，不再作为全局模式切换。
  - 首页统计按全部资料口径展示，不再按当前工作场景过滤。

验证补充：

- `node --check miniprogram/pages/home/index.js` 通过。
- `python3 -m json.tool miniprogram/pages/home/index.json >/dev/null` 通过。

# 2026-07-02 资料库按钮与登录页统一文案收口

本轮处理：

- 修复 `pages/library` “新增资料”点击无反应：
  - 原因是统一资料库改造时移除了 `readWorkspaceMode` import，但 `handleManualAdd` 仍引用该函数，真机点击会触发运行时错误。
  - 现改为根据 `entryFilter` 和 `activeLibraryType` 决定跳转目标。
- 修正资料库商品/服务空态按钮：
  - “新建商品 / 商品合集”“做名片 / 做方案”“做服务方案”等空态按钮统一改成小胶囊、flex 居中、限宽居中。
  - “用当前筛选生成合集 / 用当前筛选生成商品合集”和“重置筛选”改为 54rpx 高、21rpx 字号、限宽居中。
- 登录页文案从“房源工作台 / 一键生成房源卡”改成 SCRM 获客口径：
  - 首屏标题：“把资料变成你的客户 SCRM”。
  - 强调客户打开、咨询、留资和跟进状态沉淀到账号。
  - 功能点改为资料获客、客户雷达、线索跟进、成交复盘。

验证：

- `node --check miniprogram/pages/library/index.js && node --check miniprogram/pages/home/index.js && node --check miniprogram/pages/login/index.js` 通过。
- `miniprogram/pages/library/index.json`、`home/index.json`、`login/index.json` JSON 解析通过。
- `git diff --check -- miniprogram/pages/library/index.js miniprogram/pages/library/index.wxss miniprogram/pages/login/index.wxml miniprogram/pages/login/index.js` 通过。

注意：

- 本轮只改小程序前端，不需要部署后端。
- 真机看到登录页仍是旧“房源工作台”，通常说明小程序体验版还没有重新上传最新前端。

# 2026-07-02 小程序前端切回生产环境

本轮处理：

- `miniprogram/app.js` 切回生产配置：
  - `apiBaseUrl`: `https://teambuy.lifelove.top`
  - `apiRoutePrefix`: 空字符串，直接请求 `/api/...`
  - `mediaRoutePrefix`: 空字符串，直接请求 `/media/...`
  - `environmentName`: `production`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- 本地验证 `buildApiUrl('/api/health')` 输出 `https://teambuy.lifelove.top/api/health`。
- 本地验证 `buildApiUrl('/media/example.jpg')` 输出 `https://teambuy.lifelove.top/media/example.jpg`。

注意：

- 这是前端环境配置切换，不涉及后端部署。
- 因 `currentUser` 存储里会记录旧环境信息，切到生产后旧测试登录态会被自动清理，需要重新微信登录。

# 2026-07-02 生产后端部署前检查：本轮不部署后端

检查结论：

- 本地后端仍有大量未提交/未统一合并改动，包含二期商机、供需、资源钱包、H5、规则样本池等，不适合直接整包部署生产。
- 生产环境当前已经运行 OCR worker、archive worker 和 Postgres，不需要为了本轮前端文案/生产配置切换重新部署后端。

线上检查：

- `https://teambuy.lifelove.top/health` 返回 `status=ok`，数据库后端为 `postgres`。
- 服务器 `docker compose ps` 显示：
  - `teambuy-backend-1` Up
  - `teambuy-backend-worker-1` Up
  - `teambuy-archive-worker-1` Up
  - `teambuy-postgres-1` Up healthy

注意：

- `/api/health` 返回 404 是因为健康检查路由在根路径 `/health`，不是生产故障。
- 当前建议只上传小程序前端；后端二期功能必须走统一分支、测试通过后再生产部署。

# 2026-07-02 小程序前端切回测试环境

本轮处理：

- 用户已提交生产前端后，将 `miniprogram/app.js` 切回二期开发测试环境：
  - `apiBaseUrl`: `https://teambuy.lifelove.top`
  - `apiRoutePrefix`: `/test-api`
  - `mediaRoutePrefix`: `/test-media`
  - `environmentName`: `test`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- 本地验证 `buildApiUrl('/api/health')` 输出 `https://teambuy.lifelove.top/test-api/health`。

注意：

- 本轮只切前端开发配置，不涉及后端部署。
- 切回测试后，真机二期开发会读取测试后端和测试库；不要用它判断生产归档数据是否存在。

# 2026-07-02 登录与头像点击反馈修补

本轮处理：

- 按用户要求重新把 `miniprogram/app.js` 切回生产前端配置：
  - `apiRoutePrefix`: 空字符串
  - `mediaRoutePrefix`: 空字符串
  - `environmentName`: `production`
- `pages/login/index.js`：
  - 微信登录点击后立即显示 `登录中` loading，成功/失败都会关闭，避免真机误判为按钮没反应。
- `pages/profile/index.*`：
  - 头像按钮增加 `bindtap` 兜底检测，旧微信版本不支持 `chooseAvatar` 时提示“当前微信版本不支持头像选择”。
  - 头像按钮明确 `position/z-index/flex` 点击热区，头像图片设置 `pointer-events: none`，点击统一落到原生 button 上。

验证：

- `node --check miniprogram/app.js && node --check miniprogram/pages/login/index.js && node --check miniprogram/pages/profile/index.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- `miniprogram/pages/login/index.json`、`profile/index.json` JSON 解析通过。
- 本地验证生产 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/api/auth/wechat-login`。
- 公网探测生产登录路由：无效 code 返回 400 `invalid code`，证明不是路由 404。
- `git diff --check -- miniprogram/app.js miniprogram/pages/login/index.js miniprogram/pages/profile/index.js miniprogram/pages/profile/index.wxml miniprogram/pages/profile/index.wxss` 通过。

注意：

- `chooseAvatar` 必须在真机微信环境和支持的基础库中触发；开发者工具或旧微信版本可能不会弹系统头像选择。
- 生产前端配置已打开，当前工作区不再是测试配置。

# 2026-07-02 安卓头像选择兜底

本轮处理：

- 用户反馈 iOS 真机可以调起头像/昵称，安卓真机调不起来。
- `pages/profile/index.*` 增加安卓平台识别：
  - iOS/非安卓继续使用微信官方 `button open-type="chooseAvatar"`。
  - 安卓改为普通头像点击区，点击后走“从相册选择头像”兜底。
  - 选择到的本地图片继续复用原保存逻辑，保存时上传为头像资源。

说明：

- 微信昵称不是后端接口，也不是可强制弹出的授权窗；当前只能通过 `input type="nickname"` 获取微信系统建议。
- 安卓微信不弹昵称建议时，用户仍可直接手动输入昵称并保存。

验证：

- `node --check miniprogram/pages/profile/index.js` 通过。
- `miniprogram/pages/profile/index.json` JSON 解析通过。
- `git diff --check -- miniprogram/pages/profile/index.js miniprogram/pages/profile/index.wxml miniprogram/pages/profile/index.wxss miniprogram/app.js` 通过。

补充修复：

- 安卓相册兜底从优先 `wx.chooseMedia` 改为优先 `wx.chooseImage`。
- 原因：用户真机出现微信内部 `received error code -3 on sync-*`，能点到入口但系统相册未打开，疑似安卓微信/基础库对 `chooseMedia` 调相册链路不稳定。
- 失败时弹窗展示系统 `errMsg`，便于继续定位是否为微信相册权限、系统权限或基础库问题。

# 2026-07-02 小程序前端再次切回测试环境

本轮处理：

- 用户已提交生产前端后，将 `miniprogram/app.js` 切回测试环境：
  - `apiRoutePrefix`: `/test-api`
  - `mediaRoutePrefix`: `/test-media`
  - `environmentName`: `test`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- 本地验证 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/test-api/auth/wechat-login`。

状态：

- 当前工作区适合继续二期测试开发。

# 2026-08-12 恢复小程序测试登录与隔离测试后端

本轮处理：

- 确认资料整理助手小程序 AppID 为 `wxf43f7bc098d9858b`。
- 从用户指定的本地 RTF 配置文档读取 AppID / AppSecret，密钥未输出到日志或提交 Git。
- 新建 Git 忽略的 `backend/.env.test`，配置真实微信小程序登录和独立 H5 ticket 密钥。
- 发现服务器旧 `/home/ubuntu/teamBuy` 目录和测试容器已不存在，但 Nginx 仍将 `/test-api` 代理到 `127.0.0.1:8003`，因此此前登录返回 502。
- 在 `/srv/teambuy-test/teamBuy` 重建隔离测试环境，Compose 项目名为 `teambuy-test`，启动：
  - `teambuy-test-postgres-test-1`
  - `teambuy-test-backend-test-1`
- 增加 `backend/Dockerfile.test`。测试镜像暂不安装 `paddlepaddle` / `paddleocr`，避免首次恢复被大体积 OCR 依赖阻塞；其他 API 依赖保留。

验证：

- `https://teambuy.lifelove.top/test-health` 返回 200，PostgreSQL 已配置。
- 测试容器确认 AppID、AppSecret 均已读取，AppID 与项目配置一致。
- 使用无效诊断 code 请求 `/test-api/auth/wechat-login` 返回微信侧 `invalid code`，证明 Nginx、后端配置和 `jscode2session` 链路已接通，不再是 502 或未配置。

注意：

- 本轮只恢复测试环境 `8003`，未改生产 `/api` 和其他项目容器。
- 测试镜像当前不覆盖 PaddleOCR 真实识别验收；需要 OCR 时再构建完整镜像。

# 2026-07-12 会话归档 / 机器人 / 建群资料整理

本轮处理：

- 新增独立参考文档：`docs/wecom-archive-robot-group-reference.md`
- 将以下能力的资料、配置、接口、部署信息和迁移注意事项集中整理到一处：
  - 企业微信客服回调
  - 企业微信会话内容存档
  - 智能机器人查询网关
  - 企业微信群机器人群发
  - 企业微信群入群方式 / 建群承接
  - 群二维码上传
- 文档内已补充：
  - 关键代码入口索引
  - `.env` 配置参数分组
  - 关键公网地址与生产部署信息
  - 常见混淆点与迁移建议

状态：

- 本轮只整理文档与交接信息，未改业务代码，未触碰生产环境。

# 2026-07-03 H5 资源工具：我的页拆成可直达二级路径

本轮处理：

- `backend/app/static/h5/resource-tools/index.html`
  - 将“我的发布”拆成四个可直达子路径：
    - `?page=mine`
    - `?page=mine-received`
    - `?page=my-applications`
    - `?page=mine-history`
  - `mine` 主页不再把“收到申请 / 我申请的合作 / 历史”全堆在一张长页面中，而是用明显的二级 tab 切换。
  - 保留统一的总览统计卡和控制台条，但下方主体区按子路径只展示一个核心模块，减少滑动查找。
  - “历史”不再走 detail 临时页，改成和 `mine` 同级的可刷新列表页。

验证：

- `node -e "new Function(...)"` 解析 `index.html` 内联脚本通过。
- `git diff --check -- backend/app/static/h5/resource-tools/index.html` 通过。

状态：

- 这轮只改 H5 测试链路，不碰生产环境。
- 下次提交生产前端前，需要再次切回生产配置。

# 2026-07-03 头像选择统一走相册

本轮处理：

- 用户反馈生产版本安卓可以通过相册选头像，iOS 又不行。
- 为避免 `button open-type="chooseAvatar"` 在 iOS/安卓、微信版本和基础库之间表现不一致，`pages/profile` 头像入口统一改为：
  - 点击头像；
  - 打开“从相册选择头像”；
  - 使用 `wx.chooseImage` 优先选择图片；
  - 保存时复用现有上传头像逻辑。
- 移除我的页头像入口里的 `open-type="chooseAvatar"`、平台判断 `isAndroid` 和相关回调。

说明：

- 昵称仍使用普通输入框并保留 `type="nickname"`，微信昵称建议不作为强依赖。
- 头像统一相册后，只依赖“选中的照片或视频信息”隐私声明，不再依赖微信头像弹窗。

验证：

- `node --check miniprogram/pages/profile/index.js` 通过。
- `miniprogram/pages/profile/index.json` JSON 解析通过。
- `rg chooseAvatar/isAndroid` 确认我的页不再使用官方头像弹窗逻辑。
- `git diff --check -- miniprogram/pages/profile/index.js miniprogram/pages/profile/index.wxml miniprogram/pages/profile/index.wxss` 通过。

# 2026-07-03 小程序前端切回生产环境

本轮处理：

- 为提交头像兼容修复，将 `miniprogram/app.js` 切回生产配置：
  - `apiRoutePrefix`: 空字符串
  - `mediaRoutePrefix`: 空字符串
  - `environmentName`: `production`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js && node --check miniprogram/pages/profile/index.js` 通过。
- 本地验证 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/api/auth/wechat-login`。
- 本地验证 `buildApiUrl('/media/example.jpg')` 输出 `https://teambuy.lifelove.top/media/example.jpg`。
- `git diff --check -- miniprogram/app.js miniprogram/pages/profile/index.js miniprogram/pages/profile/index.wxml miniprogram/pages/profile/index.wxss` 通过。

状态：

- 当前工作区小程序配置为生产前端配置，可用于提交/上传。

# 2026-07-03 小程序前端切回测试环境

本轮处理：

- 用户已提交生产前端后，将 `miniprogram/app.js` 切回测试环境：
  - `apiRoutePrefix`: `/test-api`
  - `mediaRoutePrefix`: `/test-media`
  - `environmentName`: `test`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- 本地验证 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/test-api/auth/wechat-login`。

状态：

- 当前工作区适合继续二期测试开发。

# 2026-08-12 销售型 SCRM 五阶段开发与统一对抗式审查

本轮完成：

- 阶段一：首页收口为“先做内容、再看反馈”，资料库增加全部/最近/常发/高反馈/待完善快捷筛选，复杂条件默认收起；我的页新增会员和推广入口，资源工具原区块未改。
- 阶段二：新增客户信息链接口。免费返回真实数量和脱敏信号，会员返回客户身份、联系方式、跨资料看板和时间线。
- 阶段三：新增 19.9 元月会员订单、权益、续费顺延、退款回退和非生产测试支付适配器。
- 阶段四：生成同款支持“用这份信息”和“用我的资料”两种模式；新 ID、独立统计，不复制客户、私密备注、上游信息或原统计。
- 阶段五：一级直接邀请每笔有效订单奖励 50%（995 分），不做二级 5%；包含唯一归因、续费奖励、退款撤销、提现申请状态。
- 完成统一对抗式审查并修复旧接口绕付费墙、私密正文复制、长链循环邀请、退款撞提现、归因状态丢失、静态 schema 缺表等问题。

验证：

- `python -m compileall -q backend/app` 通过。
- 相关小程序 JS `node --check` 通过，新增 JSON 解析通过。
- `pytest backend/tests/test_app.py backend/tests/test_sales_scrm.py -q`：171 passed。
- `git diff --check` 通过。

未做：

- 未部署测试或生产；未触碰生产 `/api`。
- 未接微信真实支付、自动续费和企业付款。
- 未在微信开发者工具/真机完成视觉、分享卡和交互验收。

# 2026-07-03 用户协议与隐私政策合规补齐

本轮处理：

- 新增小程序协议页面：
  - `pages/legal/terms/index`：资料整理助手用户服务协议。
  - `pages/legal/privacy/index`：资料整理助手隐私政策。
- 协议主体统一为：湖南悦享互动科技有限公司。
- 登录页新增“我已阅读并同意《用户服务协议》和《隐私政策》”：
  - 不勾选时禁止微信登录和本地便捷登录。
  - 协议名称可点击进入对应页面。
- 我的页个人资料弹窗新增协议勾选：
  - 保存昵称、头像、手机号、微信号前必须勾选同意。
  - 协议名称可点击进入对应页面。
- 隐私政策内容覆盖当前真实场景：
  - 微信登录标识、昵称、头像。
  - 手机号、微信号。
  - 选中的照片或视频信息。
  - 资料图片、资料内容、客户线索、浏览/咨询/留资/跟进状态。
  - 位置展示、导航和地图标记。
  - 上游联系方式、私密备注默认不在客户页展示。

验证：

- `node --check` 已覆盖 `login/index.js`、`profile/index.js`、`legal/terms/index.js`、`legal/privacy/index.js`。
- `miniprogram/app.json`、登录页、我的页、两个协议页 JSON 解析通过。
- `git diff --check` 已覆盖协议相关页面和入口改动。

注意：

- 这是前端合规补齐，不涉及后端部署。
- 当前工作区仍为测试环境配置；提交生产前端前需要切回生产配置。

# 2026-07-03 小程序前端切回生产环境用于重新上传

本轮处理：

- 将 `miniprogram/app.js` 切回生产配置：
  - `apiRoutePrefix`: 空字符串
  - `mediaRoutePrefix`: 空字符串
  - `environmentName`: `production`

验证：

- `node --check` 已覆盖 `app.js`、`utils/request.js`、`services/api.js`、登录页、我的页和两个协议页。
- 本地验证 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/api/auth/wechat-login`。
- 本地验证 `buildApiUrl('/media/example.jpg')` 输出 `https://teambuy.lifelove.top/media/example.jpg`。
- `git diff --check -- miniprogram/app.js miniprogram/app.json miniprogram/pages/login miniprogram/pages/profile miniprogram/pages/legal` 通过。

状态：

- 当前工作区小程序配置为生产前端配置，可用于重新上传。

# 2026-07-03 小程序前端切回测试环境

本轮处理：

- 用户完成生产上传后，将 `miniprogram/app.js` 切回测试配置：
  - `apiRoutePrefix`: `/test-api`
  - `mediaRoutePrefix`: `/test-media`
  - `environmentName`: `test`

验证：

- `node --check miniprogram/app.js && node --check miniprogram/utils/request.js && node --check miniprogram/services/api.js` 通过。
- 本地验证 `buildApiUrl('/api/auth/wechat-login')` 输出 `https://teambuy.lifelove.top/test-api/auth/wechat-login`。

状态：

- 当前工作区适合继续二期测试开发。
# 2026-08-12 首页按销售任务流完成 UI 重构

本轮处理：

- 首页从“功能展板”重构为单一销售行动流：今天该做什么 -> 发出/打开/跟进 -> 最近常用 -> 快速创建。
- 首屏主卡根据空资料、待发送、已发送、已有反馈、待跟进五类状态切换主文案和唯一主动作。
- 删除首页常驻四宫格统计、重复机会空态、六宫格工具入口和无信号时的会员售卖卡。
- 会员入口只在已经产生客户信号且信息链锁定时出现；资料制作、分享和生成同款保持免费表达。
- 最近常用最多显示三份资料；快速开始只保留资料助手、新建资料、生成同款。
- 修正空状态进度语义：没有实际发送时不点亮“发出”，发出数量不再使用资料总数冒充。

验证：

- `node --check miniprogram/pages/home/index.js` 通过。
- 首页相关文件 `git diff --check` 通过。
- 已在微信开发者工具用 AppID `wxf43f7bc098d9858b` 重新编译并目视检查 iPhone 12/13 Pro 模拟器首屏；新版结构和样式已实际生效。

未做：

- 未部署、未上传、未修改生产环境。
- 当前测试后端请求客户情报接口仍返回 404，空资料状态可降级显示；真实资料、反馈、付费状态仍需后续联调验收。
# 2026-08-13 首页动态客户处理与四 Tab 前端收口

本轮处理：

- 首页 Banner 右侧加入动态客户雷达，高意向、待跟进、复活机会取现有雷达汇总数据，点击进入雷达。
- 文案“分享到群里”改为“分享到客户”。
- 原流程节点改为三张浅色可点击反馈卡：发出进入资料页已发筛选，打开进入雷达访客，跟进进入雷达待办。
- 新增最高优先级客户卡：免费态展示脱敏信号和会员解锁；付费态展示客户名、来源资料、跟进建议及轨迹/跟进入口。
- 删除首页快速开始和无上下文生成同款入口。
- 底部 Tab 从五个改为四个：`首页 / 资料 / 雷达 / 我的`。
- 合集迁入资料页操作区，并将现有合集入口从 `switchTab` 改为 `navigateTo`，保留业务页面和分享链路。

验证：

- 首页、资料、我的、业务看板 JS 语法检查通过；`app.json` 解析通过；相关文件 `git diff --check` 通过。
- 微信开发者工具重新打开项目后编译成功；iPhone 12/13 Pro 模拟器确认新 Banner 雷达、可点击反馈卡、移除快速开始及四 Tab 已生效。
- 资料页确认出现“我的合集”入口。

未做：

- 未部署、未上传、未修改生产环境。
- 当前测试接口缺少客户情报路由时只能验收空数据状态；优先客户付费/免费两种真实数据状态仍需联调。
# 2026-08-13 资料页双状态 UI 重构

- 按已确认高保真稿重构 `pages/library/index`：有资料态保留搜索、最近/常发/高反馈/待完善、紧凑资料卡、发客户和固定新建/资料助手入口；零资料态隐藏搜索和筛选，展示首次建库 CTA、资料助手和合集数量。
- 本轮未开发合集和新建资料二级页面，只复用现有导航入口。
- 资料卡继续使用真实分类、标签、分享、打开、访客和客户信号数据；未修改数据库结构。
- 完成对抗式审查并修复：最近筛选误隐藏旧资料、筛选空态误判首次空态、接口失败误判零数据、分享次数摘要不同步、入口筛选计数污染等问题。
- 微信开发者工具 iPhone 12/13 Pro 模拟器已完成零数据态编译和视觉验收；有数据态仍需真实资料账号补真机截图。
- 详细报告：`docs/qa/资料页UI重构_对抗式审查与自测报告.md`。
# 2026-08-13 合集一级页重构

- 按销售 SCRM 主循环重构 `pages/showcases/index`，将合集定义为“把多份资料组合后发客户”的一级管理页。
- 页面与资料页统一为“资料 / 合集”切换，保留搜索、最近/常发/高反馈/草稿、状态与类型筛选、紧凑卡片及固定新建入口。
- 已发布、草稿、已下架分别提供发客户、继续编辑、重新发布；客户反馈统一进入雷达，不在列表展开访客详情。
- 移除原一级页大型宣传 Banner、生成同款/导出方案书说明和内嵌分析面板。
- 本轮未修改新建合集、编辑合集和预览二级页面，未修改后端与数据库，未部署环境。
- 状态脚本和微信开发者工具零数据视觉验收通过；详见 `docs/qa/合集一级页重构_数据逻辑自测报告.md`。

# 2026-08-13 内容编辑器产品讨论收口（未开发）

- 完成通用编辑器、文字/图片/文章链接三类展示和房源深度编辑器的第一性原理讨论。
- 确认分享封面与客户页保留轻量生成同款、删除阅读中段提示，分享确认页保留原作者分佣利益提示。
- 确认房源租售单选、腾讯地图公共位置导航、精确地址与上游信息私密保存。
- 新增长期规格：`docs/stage2-docs/39-content-editor-product-design-decisions.md`。
- 本阶段只记录产品结论，未修改业务代码、未部署测试或生产环境。

# 2026-08-13 商品 / 团购深度编辑器产品讨论（未开发）

- 已确认商品展示与团购接龙共用一个轻量编辑器，销售方式单选。
- 已确认简单多规格、配送/自提、腾讯地图、接龙设置和私密进货管理的页面结构。
- 已确认第一版不做商品在线支付和复杂电商后台能力，接龙数据需关联客户雷达。
- 用户认可高保真效果稿，可作为后续 UI 验收参考；产品结论已写入 `docs/stage2-docs/39-content-editor-product-design-decisions.md`。
- 本阶段未修改业务代码、未部署。

# 2026-08-13 服务 / 合作与电子名片讨论收口（未开发）

- 将服务方案收敛为跨行业通用“服务/合作”资料，支持文字、图片、PDF 和外部链接，废弃复杂交付型服务稿。
- 完成电子名片第一性原理设计和资料库卡、客户主页、微信分享封面三场景高保真稿。
- 确认电子名片提供 4 个纯视觉轻样式，样式切换不得修改用户内容或新建资料。
- 结论已写入 `docs/stage2-docs/39-content-editor-product-design-decisions.md`；尚未开发、未部署。

# 2026-08-13 五类编辑器开发规格与交接材料

- 新增 `docs/stage2-docs/40-five-editor-data-route-attachment-spec.md`，锁定统一 UserNote、各类型字段、附件、事件、路由、生成同款和身份模型。
- 新增 `docs/qa/五类内容编辑器_测试清单与验收标准.md`，覆盖P0权限、附件、路由、五类页面、SCRM、生成同款和UI验收。
- 新增 `docs/prompts/five-editors-development-codex-prompt.md`，可直接复制到新窗口开始开发。
- 将7张已认可高保真参考图保存到 `docs/png/editor-design/`；复杂专业服务旧稿未纳入并明确废弃。
- 核对发现当前 `mediaType=file` 上传仍按图片路径处理，PDF真实存储和点击事件为下一窗口P0，不得只做UI占位。
- 本阶段只新增和更新文档/参考图，未修改业务代码、未部署。

# 2026-08-13 五类内容编辑器一次性开发完成

- 按 `docs/prompts/five-editors-development-codex-prompt.md` 一次完成通用、房源、商品、服务/合作、电子名片五类编辑器及共同基础能力。
- 通用文字/图片/链接继续复用 `note-edit`；新增独立房源、商品编辑页；服务与名片 studio 改为共享轻量字段编辑器。
- `UserNote.media` 统一承接图片、PDF、HTTPS 链接；PDF 上传校验大小、MIME、扩展名和 `%PDF-` 文件头，公开附件使用稳定 ID。
- 新增 `cardType -> editor route` 唯一路由，并接入资料列表、创建、认领、旧卡页和服务模板等主要入口。
- 个人销售资料成为名片身份与联系方式真源；名片支持商务蓝、深色质感、暖色亲和、清新自然四套纯视觉样式。
- 客户页新增统一附件区、同款入口和图片/PDF/链接/联系/电话/地图事件；同款清空原作者身份、私密字段、客户、统计和来源链路。
- 完成统一对抗式审查，修复稳定附件 ID、远程 PDF 打开方式、名片同款入口和公开文本残留上游联系方式 4 个确认风险。
- 验证：小程序全部 JS 语法、全部 JSON、后端编译、`git diff --check` 通过；`backend/tests/test_app.py + test_sales_scrm.py` 共 175 项通过。
- 未部署生产，未上传体验版；真机 UI 和合法域名仍需用户在微信开发者工具人工确认。
- 报告：`docs/qa/五类内容编辑器_Codex自测报告.md`、`docs/qa/五类内容编辑器_对抗式审查与修复报告.md`。

# 2026-08-13 五类编辑器真机有数据态回归修正

- 根据旧房源、合集和筛选弹层真机截图，修复资料/合集卡片、筛选底栏、编辑器固定底栏和新建资料识别卡的横向越界。
- 房源、商品、服务编辑器恢复为渐进字段结构；预览去重并限制长正文，私密与更多字段按已有值自动展开。
- 客户页空封面不再占据大块空间，本人预览隐藏咨询与生成同款；通用编辑器移除浮动保存按钮。
- 完成追加对抗式审查与一轮针对性重试；相关 JS 语法和 `git diff --check` 通过。
- 未部署、未上传；真实有数据态仍需用户重新编译后复截图。

# 2026-08-13 新建资料第一屏按效果图逐项回归

- 将 `resource-create` 第一屏从自定义的“四种来源卡 + 大表单”收回效果图结构：单一内容框、添加图片/链接、整理成资料、四个空白场景。
- PDF 和电子名片不再占据本页一级入口；普通资料只作为无法归入房源/商品/服务时的通用空白起点。
- “添加图片”改为给当前待整理内容暂存附件，不再立即另建图片资料并跳页；文字与图片可一起生成同一 `noteId`。
- JS 语法、页面 JSON 和 `git diff --check` 通过；未部署、未上传。

- 修复第一屏两个附件按钮无可见反馈：添加图片现在打开相册/相机并显示缩略图，兼容不支持 `chooseMedia` 的基础库；添加链接现在弹出 HTTPS 链接输入面板，加入后显示可删除的链接卡片。纯图片、纯链接或图文混合都可继续整理。
- 安卓真机相册回归：恢复项目既有的 `wx.chooseImage` 优先策略，`chooseMedia` 只作兜底；失败弹窗显示真实 `errMsg`，并单独识别微信后台隐私 scope 未声明。该能力不需要申请小程序类目，但必须在用户隐私保护指引声明“选中的照片或视频信息”。

# 2026-08-13 手工链接解析与链接卡路由修复

- 确认原链路只把手工 URL 保存为普通附件，后端没有主动抓取网页标题、摘要和封面的接口，因此整理后错误落入普通笔记。
- 新增受 SSRF 约束的 HTTPS 网页元信息读取：限制公开地址、跳转次数、HTML 类型和响应体大小，解析 `og:*`、description、title 与封面。
- 新增 `/api/notes/link-capture`，纯链接直接生成 `cardType=link/contentMode=bookmark`；外站拒绝抓取时保留 URL 并标记 `fetch_failed`，不再降级成普通笔记。
- 小程序新建页纯链接提交改走链接接口；图文混合仍作为普通资料的链接附件。
- 验证：2 条链接定向回归通过；后端编译、小程序 JS 语法和 `git diff --check` 通过。未部署、未上传。

# 2026-08-13 手工链接对抗式审查与测试环境部署

- 对抗式审查发现初版响应大小限制发生在完整下载之后，无法真正限制内存；已改为流式读取，读取前检查 Content-Length，读取中执行 2MB 硬限额，并复核连接对端 IP。
- 全量本地回归 175 项通过，1 项失败为 JSON 测试模式与用例硬要求 PostgreSQL 的环境断言；链接定向回归 2 项全部通过，全部小程序 JS/JSON 与 diff 检查通过。
- 部署前确认测试环境独立运行、根盘剩余 9.4GB；已备份测试后端代码到 `/srv/teambuy-test/backups/20260813-link-before/backend-code.tgz`。
- 仅更新并重启 `teambuy-test-backend-test-1`，未修改生产 `/api`、数据库卷、媒体卷、`.env.test` 或 secrets。
- 公网 `/test-api/notes/link-capture` 实测 `https://example.com/` 返回 `title=Example Domain`、`cardType=link`、`contentMode=bookmark`、`parseStatus=meta_done`；测试资料随后删除。
- 小程序前端仍需用户在微信开发者工具重新编译/预览或上传体验版，手机旧版本不会自动获得本地前端改动。

# 2026-08-13 17:05 真机链接确认页回归修复

- 从测试日志确认 17:04:57 手工公众号链接创建接口返回 200，但之后没有读取该 note 的请求；根因是创建页成功后只清空输入并显示底部“已保存”，没有进入第二步解析结果页。
- 纯链接创建成功后改为立即 `navigateToNoteEditor(note)`；`link/bookmark` 将命中链接确认 DOM，显示来源、标题、摘要、封面、打开原文和整理为笔记。
- 同一公众号链接初次为 `fetch_failed`，原因是微信 HTML 超过 2MB 时被整体拒绝；改为流式最多读取前 2MB 后停止，既限制内存又能取得页面头部元信息。
- 测试容器真实解析该链接得到标题“WPS悄悄上线AI原生Agent，他们这是要革PPT的命？”、摘要“有点东西！”及封面；已将用户 17:05 生成的 `note_125214a272` 补全为 `meta_done`。
- 前端跳转修复仍需微信开发者工具重新编译/预览或重新上传体验版；后端公众号解析已在测试环境生效。

# 2026-08-13 17:13 链接旧编辑器替换

- 真机截图确认解析数据虽然正确，但 `link/bookmark` 仍复用旧 `note-edit`，点击整理后变为 `article/deep_note`，暴露附件管理、轻 CRM、预约、接龙和基础信息等不属于确认阶段的 DOM。
- 新增独立 `pages/link-confirm`：只显示识别类型、网页封面、标题、摘要、来源、标签、隐私说明、打开原文、“生成资料”和“保存原文，不整理”。
- 新建纯链接与资料库中未整理链接统一路由到确认页；已整理 `article` 路由到资料预览，不再回旧通用编辑器。
- 将用户截图对应的 `note_ec0685f41d` 从误转的 `article/deep_note` 恢复为 `link/bookmark`，重新编译后可直接打开验证新确认页。
- 新页面 JS/JSON、路由 JS、app.json 和 `git diff --check` 通过；前端仍需微信开发者工具重新编译/上传体验版。

# 2026-08-13 所有资料入口确认流程审计

- 审计所有创建、认领、资料库、旧卡、客户/雷达和生成同款入口，确认不能把所有资料都机械导向“链接确认”；统一的是识别确认阶段，页面内容必须随资料类型变化。
- 粘贴文字、选择图片、图文混合、添加链接、上传 PDF、房源批量弹层中“保留为文字资料”、企业微信/助手认领统一进入 `link-confirm`（后续名称可再改为通用 confirm）。
- 确认页新增普通资料、图片资料、图文资料、PDF资料、文章链接以及识别出的房源/商品等类型展示；链接保留元信息和原文动作，其他类型显示素材数量及隐私提示。
- 用户明确选择空白房源、商品、服务/合作或电子名片时直接进对应编辑器；已存在且已确认的资料从资料库进入对应编辑器/预览，不重复确认。
- 统一路由审计后，全部小程序 JS/JSON 和 `git diff --check` 通过；仍需重新编译/上传体验版做真机逐入口验证。

# 2026-08-13 17:39 编辑器排版、朋友圈说明与资料库刷新修复

- 房源、商品及共享结构化编辑器的 input/textarea 原为 `28rpx + 22rpx padding`，真机字体度量导致 placeholder 超出单行高度；统一为单行 `80rpx/26rpx`、placeholder `24rpx/40rpx`，多行输入明确 `40rpx` 行高。
- 微信小程序不能由页面按钮直接拉起朋友圈发布器，`onShareTimeline` 只配置微信右上角朋友圈分享；将按钮改为“发朋友圈方法”，弹层明确微信限制并提示可保存分享图后发布。
- 17:39 新建的房源、商品、服务和普通资料均已存在测试数据库且为 active；公网 `/test-api/cards` 也全部返回。资料库未显示是 `resourceStore` 优先返回旧内存/本地缓存，`onShow` 无新 `/api/cards` 请求。
- 资料库 `loadCards` 改为每次页面显示时对 cards 使用 `{force:true}` 拉取，分类仍可缓存；公网验证 5 个对应 noteId 全部出现在 cards 列表。
- 全部小程序 JS/JSON 和 `git diff --check` 通过；后端无需再次部署，前端需重新编译/上传体验版。

# 2026-08-13 深度编辑器补充资料渐进展示

- 确认图片、PDF、外链作为房源、商品、服务/合作和名片的补充资料能力合理，但空附件区不应常驻占据核心字段后的大块页面。
- 四类共享编辑器默认只显示紧凑“补充资料”入口及已有数量；点击展开后才显示附件列表与添加按钮，再点击添加才弹出图片/PDF/外链选择。已有附件自动展开。
- 图片预览、PDF下载打开、链接复制打开和删除事件均保留；不是视觉占位。
- 补齐前端边界：图片9张、PDF5份、链接5条、总计12个，重复链接拒绝；图片选择优先 `wx.chooseImage`，`chooseMedia` 仅兜底。
- 四个编辑器确认共用该模板；全部小程序 JS/JSON 与 `git diff --check` 通过。

# 2026-08-13 新建资料入口与资料页真机偏差修正

- 根据真机截图确认 `pages/resource-create` 仍残留旧版“随手记 / 发送 / 工作台切换”结构；本轮将入口层完整替换为已定稿的“文字、图片、链接、PDF 来源 + 继续整理 + 四类空白场景”结构。
- 复用现有 quick-capture、类型识别和唯一编辑器路由；去除入口页发送语义及工作台切换，避免创建与分享混为一步。
- 图片创建成功后直接进入对应编辑器；PDF 先完成真实附件上传，再创建同一条资料并进入通用编辑器，上传失败不再遗留空草稿。
- 资料页卡片更多按钮下移并增强可见性；固定“新建资料 / 资料助手”改为等宽布局。
- JS 语法、页面 JSON 与 `git diff --check` 通过；未部署、未上传，需在微信开发者工具重新编译后做真机视觉验收。

# 2026-08-13 房源编辑器按高保真稿独立重构

- 资料卡操作区按效果图调整为“更多在右上、发客户/完善在右下”，不再上下顺序颠倒。
- 房源页不再复用通用结构化模板，改为独立编辑器：客户效果预览、主图/多图、核心信息、亮点、更多信息、公开位置、私密管理依次展示。
- 房源图片前置，第一张作为封面；支持上传、预览、删除，长按任意缩略图可移到第一张并设为封面。
- 出租/出售改为单一 `listingMode` 与单一 `price` 字段；界面只渲染当前模式的标签和单位，保存时移除旧 `rentPrice/salePrice/dealType` 分叉字段。
- 客户预览与资料卡兼容 `listingMode`：出租显示“租金/元/月”，出售显示“售价/万元”；旧含单位价格载入时先归一为数值，避免重复单位。
- PDF/外链能力保留在“更多房源信息”的渐进区域，不再常驻抢占图片和核心字段。
- 房源页、资料库、客户预览及公共导航组件的 JS/JSON 静态检查与 `git diff --check` 通过；未部署、未上传小程序，仍需微信开发者工具重新编译做真机视觉验收。

# 2026-08-13 资料卡主行为、租售互斥与时间语义修正

- 按第一性原理重新确认：资料库属于作者工作区，整张资料卡的主点击必须进入编辑；客户预览与分享只能由明确次级动作触发。
- 整张资料卡绑定编辑路由，“发客户 / 更多 / 雷达”改为阻止冒泡，避免点击次级按钮又同时进入编辑。
- 修复统一路由中 `article` 被硬编码到客户预览的问题，已整理文章现在从资料库进入 `note-edit`。
- 客户页分享按钮由“发朋友圈方法”缩短为“朋友圈”，说明仍在点击后的微信限制弹层内。
- 房源编辑器移除同时常驻的“出租 / 出售”双选项，只显示当前交易类型标签；点击标签后再选择切换，价格表单仍只有一个。
- 资料卡新增动作时间：最近发送晚于最近编辑时显示“最近发送”，否则显示“最近编辑”，并继续显示发送次数和打开次数。
- 已验证资料卡事件拦截、房源互斥 DOM、唯一价格输入、相关 JS 语法及 `git diff --check`；未部署、未上传。

# 2026-08-13 URL 链接资料独立编辑与客户阅读闭环修复

- 回读任务 `019ff5bc-7486-76c3-8ab3-4bd0bda41d19` 原始讨论，确认链接资料应为“文章元信息 + 销售推荐语 + 简介 + 查看原文 + 原文点击信号”，不是旧普通笔记插件页。
- 新增 `pages/link-editor` 独立作者编辑页，只包含客户效果、封面、标题、来源、原文链接、销售推荐语、内容简介和隐私说明。
- `link-confirm` 仍只承担解析确认；生成后进入 `link-editor`。`article` 从资料库也统一进入 `link-editor`，不再进入旧 `note-edit`。
- `note-preview` 为 `article` 新增独立客户阅读 DOM：文章封面、来源、标题、推荐语、简介、“查看原文”、按字段出现的咨询发布者和轻量生成同款。
- 后端新增 `source_open/source-open` 互动事件，无需伪造附件 ID；点击原文单独去重、忽略作者本人预览，并进入客户行为记录。
- 新增测试覆盖文章原文点击记录、去重与作者预览忽略；链接定向测试 2 项通过。新增静态否定验收，链接编辑页禁止出现轻 CRM、留言表单、预约、接龙、基础信息和通用附件大区。
- 未部署、未上传小程序。

## 2026-08-13 编辑器类型路由防回归与旧页退役盘点

- 盘点结果：URL、房源、商品、服务、名片已有独立路由；文字、图片 OCR/图文、PDF 仍使用 `note-edit`。
- 将路由从“未知类型兜底到 `note-edit`”改为显式白名单，未知类型改进类型确认页。
- `note-edit.applyLoadedNote()` 增加同样的白名单守卫，直接 URL 也不会渲染错误类型 DOM。
- 移除普通资料的“添加功能/能力插件”交互 DOM，保留一键整理和加入合集。
- 明确 `note-edit` 暂不能整页删除；需先迁移其四种合法通用内容模式。

## 2026-08-13 资料库分享封面、缓存与10条分页修复

- 修复首次进入页面立即发客户时 canvas 未就绪、微信改用当前页截图的回归；现在同步使用原图或固定封面，canvas 成功后再替换。
- 资料页不再在每次 `onShow` 用 `force:true` 绕过 `resourceStore`；先显示内存/本地缓存，再后台刷新首页。
- `fetchNote` 接入已有 5 分钟 item cache，URL、房源、商品、服务、名片和普通资料的重复点击都可命中。
- `/api/cards` 增加 `limit/offset`，资料库首批 10 条，页面触底每次再加载 10 条。
- 后端增加 20 秒合并列表缓存，并在主要 note/card 新建、修改、删除链路主动失效。
- 验证：相关小程序 JS 静态检查、后端 compileall、`git diff --check` 通过；分页/缓存失效与 URL 原文点击测试 `2 passed`。
# 2026-08-14 商品编辑器按高保真结构重做

- 将 `pages/product-editor` 从共享结构化模板改为独立商品编辑器。
- 完成客户实时预览、1～9 张商品图、咨询/接龙单选、整数分简单规格、亮点与说明、履约方式、自提地图、条件接龙设置、私密进货管理及保存预览。
- 新页面读取旧 `price/spec/skuConfig/pickupMethod/deadline`，保存后写入 `salesMode/variants/fulfillment/relayConfig`。
- 客户预览补新商品契约读取，咨询模式不再展示下单面板，接龙模式显示“参加接龙”。
- 分享封面共同兜底补到资料库、旧笔记列表、详情页和旧编辑页，旧列表仅预生成前 10 项。
- 前端 JS、JSON 和 diff 静态检查通过；后端定向 pytest 被本机 Python 3.9 与 `dataclass(slots=True)` 不兼容阻断。
- 未部署生产，未上传小程序。
- 2026-08-14 补充：商品空白草稿的名称、规格、说明等不再写入实体占位值；编辑器加载旧草稿时只清理精确系统占位词。销售方式 `inquiry` 在编辑器显示为“商品”。

# 2026-08-14 服务/合作编辑器按设计稿重做

- 将 `pages/service-offer-studio` 从旧销售模板/三步模板选择页改为独立轻量编辑器：客户效果、基本信息、真实图片与文件、其他信息、保存并预览。
- 名称、介绍、详细说明、服务范围和价格/合作条件均为空值 + placeholder；新建草稿不再持久化“未命名服务方案”“手动创建”等系统提示。
- 历史 `serviceContent/targetAudience/serviceProcess/caseHighlights/appointmentNote` 只在读取时合并到 `detailText`，保存后使用六字段新契约。
- 客户预览移除适合人群、指标卡、流程、案例、联系与预约等旧 DOM，改为封面、服务名称、介绍、发布者身份、咨询详情及按值出现的补充信息；公共附件继续支持图片/PDF/链接行为记录。
- 服务默认关闭预约动作，主咨询点击记录 `contact_click`；资料卡摘要同步读取新字段。
- 验证：相关 3 个小程序 JS 语法、Python 编译、diff whitespace 检查和旧 DOM 反向扫描通过；后端定向测试 `2 passed`。未部署、未上传小程序。

# 2026-08-14 普通手动文字资料按设计稿重做

- `note-edit` 新增 `text_note` 顶层独立分支，页面收敛为客户效果、标题、正文、按需整理、折叠补充资料和保存并预览。
- 移除普通文字分支中的旧资料详情头图、摘要输入、整理归档卡、加入合集、标签运营区和巨大附件空态。
- 空白文字草稿不再保存“未命名笔记”“手动创建”等实体占位；加载历史草稿时只清理精确系统占位词。
- 普通文字客户页新增专业阅读分支，展示标题、系统摘要、发布者和正文，客户底部可咨询或生成同款。
- 图片入口优先使用 `wx.chooseImage`，已有图片/PDF/链接自动展开并支持预览、打开和删除。
- 验证：前端语法、WXML 标签配平、Python 编译、diff 检查通过；空白结构化资料测试 `1 passed`。未部署、未上传小程序。

# 2026-08-14 合集页面与资料卡动作收口

- 后端新增场景/模板白名单：`property`、`groupbuy`、`service`、`notes`、`business_card`、`mixed`；保存、更新和公开快照均由服务端归一化模板。
- 合集编辑页改为“合集信息 / 已加入资料 / 客户页效果 / 发布检查”四段式；模板选项按场景过滤，旧“先选模板 + 生成方式”旧 DOM 不再展示。
- 资料卡“加入合集”改为同场景合集选择页；选中已有合集后以 `addNoteId` 打开编辑器，保存时才写入合集。
- 三个点支持停止分享与重新发布；新增资料撤回接口，撤回会失效关联公开合集快照。
- 验证：后端 `./.venv312/bin/pytest -q backend/tests` → 224 passed；新增场景映射、越界拒绝、撤回/重发和快照失效测试；小程序核心 JS `node --check` 通过；旧 `sales-template-select` 路由引用搜索无结果。未部署生产。

# 2026-08-14 合集编辑器默认选择与客户页预览修正

- 新建合集默认改为“手动选择”，不再因为默认分类或历史 `filter` 值把当前分类全部资料静默加入；只有显式传入筛选/条件模式，或用户主动切换到批量生成时才批量加入。
- 房源等场景的模板白名单没有丢失；合集编辑页现在使用模板的 `previewImage`，图片加载失败时回退到带场景色和“客户页预览”的可见占位，不再显示空白色块。
- 复核发现原远程模板预览地址返回 404；已将四张设计稿预览图缩放为 220px 宽 JPEG 纳入小程序 `static/showcase/`，避免依赖尚未部署的媒体目录，同时显著降低体验版源码包体积。
- “资料排列”改为固定标签列 + 等宽双按钮网格，避免小程序真机把标签拆成竖排、按钮撑满或互相覆盖。
- 客户页列表、故事行、目录行和品牌卡增加最小宽度、行数截断和紧凑图片/操作尺寸，长标题与摘要不再把卡片撑变形。
- 验证：合集编辑/客户页 JS `node --check`、`git diff --check` 通过；未部署、未上传体验版，待全部功能完成后统一真机人工验收。

# 2026-08-14 小程序源码包体积优化

- 真机上传报 `80051 source size 2956KB exceed max limit 2MB` 的直接诱因是合集模板四张 780×1688 PNG 预览图；已改为 220px 宽 JPEG，四张合计约 50KB。
- 模板预览路径同步为 `/static/showcase/*.jpg`；继续保留加载失败回退，不依赖远程媒体。
- 移出未被 `app.json` 或代码引用的重复资料 tab 图标和旧 `templates/structured-editor` 文件，避免它们进入小程序源码包。
- 当前 `miniprogram` 非 Git 源码文件约 2.19MB，压缩包约 0.8MB；上传前仍需以微信开发者工具实际编译结果为准。
# 2026-08-14 电子名片按三场景设计稿重做

- 将 `pages/business-card-studio` 从共享结构化模板改为独立编辑器：实时客户效果、统一个人身份、名片表达、独立二维码、最多3份精选资料及4种轻样式。
- 新建资料页下方空白入口由4项改为一行5项，新增“电子名片”；名片入口会优先查找并打开当前用户已有主名片。
- 新名片草稿不再复制姓名、电话、头像等身份字段进 `structuredData`，也不写“你好，我是…”等实体默认文案；旧名片加载时可迁移历史身份字段到统一个人资料。
- 客户页移除旧服务模板模块和虚构兜底内容，改为按值展示“我能提供、关于我、精选资料、更多联系方式”；二维码不再从附件图片猜测。
- 公开接口新增精选资料安全投影，只返回同一拥有者且未删除的最多3份资料；打开精选资料新增独立 `featured_note_open` 事件。
- 资料库名片卡优先读取当前用户 `salesProfile` 的头像、姓名、职位、公司和一句话介绍；分享封面四种轻样式与客户页使用相同 styleId。
- 验证：电子名片3项后端定向测试通过（`3 passed, 167 deselected`）；相关小程序 JS、Python 编译和 `git diff --check` 通过。未部署、未上传小程序；微信开发者工具编译和真机视觉仍需人工确认。
# 2026-08-14 资料库筛选模型与入口视觉重做

- 资料库筛选面板按三层模型重做：资料类型、客户进度、标签；移除重复“分类”维度。
- 资料类型补齐房源、商品、服务方案、电子名片、链接和普通资料；客户进度改为未发送、已发送、已打开、有反馈。
- 标签区改为搜索、热门标签和展开全部标签；底部“重置 / 完成（数量）”等宽对称布局。
- 搜索旁筛选入口放大为图标 + “筛选”文字；资料库 tab 使用裁切放大的资源图标，提升视觉识别度。
- 验证：小程序 JS 语法、app.json JSON 和 `git diff --check` 通过；未部署、未上传，仍需开发者工具编译及真机核对筛选面板滚动和 tab 图标尺寸。

# 2026-08-14 资料入库后端生命周期、幂等与公开门禁

- 新建、快速采集、链接采集、图片/OCR、房源批量、企业微信认领、复制资料统一落为私有草稿；新增 `shareState/intakeId/idempotencyKey/revision` 字段。
- 增加 `POST /api/notes/{note_id}/publish`，公开资料、客户动作、浏览和互动接口统一要求已发布；编辑已发布资料自动退回私有并递增 revision。
- 创建入口按用户 + 幂等键返回原结果，房源批量同时复用原合集；PostgreSQL 增加 user_notes/showcase_pages 的条件唯一索引。
- 发布前检查公开投影中的敏感标记和未确认手机号；名片精选资料只挂载同一用户、未删除且已发布的资料；展示页发布时同步生成公开快照。
- 回归验证：`./.venv312/bin/pytest -q backend/tests`，220 passed；`python3 -m compileall -q backend/app` 和 `git diff --check` 通过。
- 本轮只收口后端约束，未部署生产、未上传小程序。前端后续必须传入幂等键并在保存后显式发布，否则资料会正确保持私有。
- 对抗式复查补齐旁路编辑门禁：整理、确认类型、生成场景、OCR、附件回填、专题归档和认领不会绕过版本递增与私有化。
- 2026-08-14 资料卡分享状态回归：资料库统一从 `shareState`、`sourceNoteShareState`、`visibilityConfig.shareState` 和历史 `sharePublished` 解析当前分享态；异步分享封面不再覆盖私有/撤回状态；停止分享和重新发布后强制刷新首批资料；`resourceStore` 缓存升到 v2，避免旧版卡片字段继续复现。未部署生产、未上传体验版。

# 2026-08-14 资料保存后状态误显示“完善”修复

- 根因：后端按约束将保存和公开发布分开，编辑器保存后资料保持 `shareState=private`；资料库却把所有非 `published` 资料都当成“完善”，导致已完成的微信文章/链接资料被误判为半成品。
- `pages/library` 新增统一内容完成度和动作状态判断：资料未完成显示“完善”，已保存但未公开显示“发布”，已发布显示“发客户”，撤回显示“已停止分享”。“发布”按钮和三个点菜单共用发布接口，成功后强制刷新资料库。
- 链接、商品、房源、服务/合作、电子名片和普通资料编辑器主操作统一改为“保存并发布”；完整预览仍为只保存的私有预览入口，发布失败不会误标为已发布。
- `api.publishNote` 补齐资料项缓存写入和列表缓存失效，避免发布成功后旧缓存继续显示错误动作。
- 验证：相关小程序 JS `node --check`、`git diff --check`、后端 `./.venv312/bin/pytest -q backend/tests` → 224 passed。未部署、未上传体验版。

# 2026-08-14 资料发客户链路根因修复与对抗式复查

- 根因：企业微信/历史导入资料可能保留 `status=draft`；编辑器保存只更新内容和 `shareState`，未把资料推进到可用生命周期，随后调用发布接口会稳定返回“资料尚未完成”。
- 后端在资料保存和统一内容编辑门禁中将已被拥有者编辑的遗留 draft 推进为 `active`；发布接口兼容已有完整内容的遗留 draft，并仍由公开安全检查决定是否允许客户读取。
- 资料库新增 `sourceNoteStatus` 投影用于诊断和迁移；完成度只判断真实标题 + 正文/封面，不再把 `status=draft` 或 `cardState=draft` 当成内容不完整，避免误伤已经保存的微信文章/链接资料。
- 用户界面收回内部“发布”措辞：五类编辑器和资料卡统一显示“发客户”；“完善”只表示内容确实缺少必要信息。私有资料首次点卡片“发客户”先完成公开准备，原生分享入口只对已发布资料开放，避免异步发布与微信 `open-type=share` 竞态。
- 对抗式复查补齐快速连续分享保护：`onShareAppMessage` 只接受当前卡片的待分享封面，不能复用上一张卡片的 canvas 图。
- 验证：`./.venv312/bin/pytest -q backend/tests` → 225 passed；五类编辑器及资料库 JS `node --check` 通过；`git diff --check` 通过。未部署生产、未上传体验版。

# 2026-08-14 发客户旁路复查补充

- 发现旧 `pages/notes` 仍把原生分享按钮直接放在所有资料行上，绕过资料库的私有/已发布判断；已改为只有 `shareState=published` 才渲染原生分享，私有完成资料先走“发客户”准备，不完整资料进入编辑。
- `pages/notes.onShareAppMessage` 增加状态校验，避免深链或快速触发时误生成客户路径。
- 完成度的唯一前端依据是有效标题 + 正文/摘要/封面，不再把内部 `status=draft` 当成“完善”。
- 新增遗留 draft 直接发布回归测试；后端全量 226 passed，相关小程序 JS、diff 检查通过。未部署、未上传体验版。
- 历史 `card-view` 资源详情也收回分享门禁：只有 `Card.status=published` 才显示“发客户”，旧草稿深链不会再出现无条件分享按钮。

# 2026-08-14 资料卡“发客户”无效路径与三个点菜单收口

- 只读检查当前小程序配置确认它请求 `https://teambuy.lifelove.top/test-api`；该测试地址的公开资料接口存在，但当前部署版本对 `POST /notes/{id}/publish` 返回英文 `Not Found`，说明体验包和本地后端版本未同步，点击“发客户”不能完成公开准备。
- 资料卡三个点移除重复的“发客户”。主按钮是唯一发送入口；三个点只保留编辑、加入合集、类型相关复用、复制文案、已发布时停止分享、已撤回时重新发布和删除。
- 资料库分享回调现在只接受当前卡片的 `sourceNoteId` 与 `shareState=published`，并拒绝过期/串卡的 `data-note-id`；状态变化时回退资料库，不再生成必然 404 的客户页路径。
- 验证：`node --check miniprogram/pages/library/index.js` 通过；远端测试地址只读检查记录为 `publish` 路由未同步。未部署、未上传体验版。

# 2026-08-14 合集分享封面兜底修复

- 根因：合集编辑页分享回调直接返回 `bannerUrl`，为空时微信会截取当前“编辑合集”页面；合集列表页则在 Canvas 封面异步生成完成前仍暴露 `open-type=share`，会把空 `imageUrl` 送入微信分享。
- 列表页现在只有 `shareImageReady` 时才渲染原生“发客户”按钮；生成中显示不可点击的“封面生成中”，生成失败显示“重试封面”，重试按钮不再触发原生分享竞态。
- 编辑页新增统一 Canvas 分享封面，发布后和打开已发布合集后自动生成；编辑已发布合集会清空旧封面并要求重新发布，生成完成前不会显示分享按钮。
- 图片上传失败时仍保留本地临时文件作为分享图兜底；后端部署只影响远程上传/发布接口，不再是避免页面截图的唯一条件。
- 验证：合集列表/编辑器 JS `node --check`、分享链路 `git diff --check` 通过；未部署生产、未上传体验版，需开发者工具重新编译后真机验证封面生成和微信分享卡。

# 2026-08-14 合集模板与筛选底栏回归修正

- 客户页目录模板的大段留白根因是 `.tpl-page` 的 `min-height:100vh` 让双列 CSS Grid 自动行拉伸；改为内容决定高度，并给目录网格 `align-content:start`，不再把空白分摊到搜索区和筛选区之间。
- 模板渲染增加前端按 `sceneType` 的白名单归一化：异常或旧快照模板按当前场景回退，不再把所有异常值一律落到精选橱窗；本地缩略预览仍保留失败回退。
- 合集三个点收敛为“客户反馈 / 编辑 / 停止分享 / 删除”（草稿为继续编辑、预览、删除；下架为编辑、预览、重新发布、删除），移除重复的“效果 / 雷达 / 预览”混合入口；发客户继续是卡片唯一主动作。
- 新增全局 `.bottom-two-actions` 等宽双按钮基线，合集筛选底栏与客户页联系方式均使用 `repeat(2,minmax(0,1fr))`，避免按钮文案长度造成比例变形。
- 验证：合集列表/客户页/模板工具 JS `node --check`、相关 JSON 解析、`git diff --check` 通过；未部署生产、未上传体验版，仍需微信开发者工具重新编译后人工核对真机间距与模板点击。

# 2026-08-14 客户展示页首屏导航与模板入口收口

- 客户展示页已经有微信原生导航标题“展示页”，页面内容不再重复挂载自定义 `custom-nav`；移除重复导航后，首屏不会再为“资料整理助手”额外预留一整段垂直空间。
- “资料整理助手”属于产品壳层标识，不属于客户要看的合集内容，因此不再出现在客户展示页；编辑合集页仍保留明确的编辑导航。
- 模板卡只在合集编辑页出现，承担“选择客户页样式”的作者操作；客户公开页只渲染选中的实际内容，不暴露模板选择器。编辑页补充“点选样式，预览客户页查看真实内容”提示，完整预览统一走“预览客户页”。
- 验证：客户页/合集编辑页 JS `node --check`、展示页 JSON 解析、`git diff --check` 通过；未部署生产、未上传体验版。

# 2026-08-14 客户雷达第一性原理重构

- 重新定义雷达职责：不做访问数据看板，只回答“谁值得现在跟、依据是什么、下一步做什么”。页面收敛为今日摘要、待跟进优先队列、访客事实、资料优化三块内容。
- 移除装饰性轨道、重复时间线、虚假的“导出跟进方案”和未持久化的“标记已联系”入口；每条队列只保留来源、行为证据、排序原因和两个等宽动作（查看资料/复制话术，比较场景可生成对比）。
- 会员锁定、接口失败和加载中拆成三种独立状态；网络错误不再误显示成会员墙，匿名访客继续以匿名身份展示。
- 雷达不再在每次 `onShow` 强制刷新资料库；优先读取客户智能接口，资料库仅作为同步缓存回退，30 秒内同一场景/资料筛选不重复请求。
- 验证：雷达 JS `node --check`、资源存储 JS `node --check`、相关 `git diff --check` 通过。未部署生产、未上传体验版，需开发者工具重新编译后人工核对真机布局与接口状态。

# 2026-08-14 会员页第二版：推广收益与规则说明

- 会员页按确认效果稿重构：客户行为信号主卡、四项会员权益、推广收益卡、脱敏访客示例和数据保留说明。
- 新增可展开的“会员说明”和“推广奖励规则”，规则使用当前 SCRM 契约：一级直接邀请、有效首购/续费按实付金额 50%、退款或异常交易撤销/冻结、当前提现手续费 0，不展示旧二级分佣口径。
- 推广收益卡与会员页规则按钮均可进入推广中心；推广中心补充邀请码用途、奖励比例、邀请层级、异常处理和提现说明。
- 验证：会员页与推广中心 JS `node --check`、JSON 解析、`git diff --check` 通过。未部署、未上传体验版，需开发者工具重新编译后人工核对真机视觉和会员/推广点击链路。

# 2026-08-14 分享链接自动归因与会员资格收口

- 分享商品、资料或合集时沿用现有 `from` 分享者参数，打开公开资料/合集后由前端异步调用 `/api/scrm/referrals/share-bind`，不再要求用户复制或填写邀请码；旧邀请码接口仅保留兼容，不再出现在推广中心主流程。
- 自动归因采用首次触达且幂等：已有其他推广人的关系不会被覆盖，也不会阻塞资料打开；匿名访问暂不建立关系，用户登录后再次进入页面会补绑定。
- 归因和分佣拆成两个时点：关系建立时不要求推广人付费；好友会员订单确认时检查推广人当前会员是否有效。推广人到期期间不产生该笔奖励，之后续费不追补错过的月份；有效时按实付金额 50% 生成一级奖励。
- note-preview、showcase-view 和历史 card-view 分享路径统一传递分享者 ID；会员页与推广中心规则同步改为“分享链接自动归因、有效会员才享受分佣”。
- 验证：`backend/tests/test_sales_scrm.py` 10 项通过；后端 Python 编译、相关小程序 JS `node --check` 与 `git diff --check` 通过。未部署生产、未上传体验版。

# 2026-08-14 客户雷达快捷筛选与资料优化入口

- 四个首屏指标改为可点击快捷筛选：待跟进/高意向切换待跟进队列，访客/有动作切换访客列表；高意向和有动作实际过滤对应列表。
- 新增当前快捷筛选提示和清除按钮；手动切换 Tab 会恢复完整数据集，不遗留上一次指标筛选。
- 资料优化卡片按钮改为“编辑资料”，通过资料类型导航进入对应编辑器；客户详情/轨迹入口暂缓，等详情字段方案确认后再接入。
- 验证：雷达 JS `node --check`、相关页面 `git diff --check` 通过。未部署生产、未上传体验版。

# 2026-08-14 客户详情页：从雷达信号进入行动页

- 新增 `miniprogram/pages/customer-detail/`，页面按已确认的效果稿收敛为：客户身份、现在该做什么、相关资料、重点标签、最近动态、底部跟进行动。
- 雷达卡片仅将稳定身份区域设为可点击，携带 `customerId`、`leadId` 和当前业务场景；不再用昵称或 noteId 猜客户身份。缺少稳定 ID 时保持不可点击并给出解释。
- 详情页复用已有会员门禁的客户智能接口，会员锁定进入会员页；同行/上游身份不展示联系方式且操作按钮为“继续观察”。相关资料、复制话术、生成对比、记录跟进、联系客户均有明确动作或安全提示。
- 后端补充客户稳定字段、联系方式、跟进档案和证据字段，告警与资料画像保持同一客户 ID 契约。
- 验证：详情页/雷达 JS `node --check`、后端 `py_compile`、JSON 解析、相关 `git diff --check` 通过；`.venv312/bin/pytest -q backend/tests/test_sales_scrm.py` 10 项通过，后端运行时导入通过。未部署生产、未上传体验版。

# 2026-08-14 雷达与合集编辑页交互收口

- 合集编辑页移除重复的自定义“编辑合集”导航，只保留微信原生导航，压缩重复导航造成的顶部留白；同时清理页面未使用的 `custom-nav` 声明。
- 雷达待跟进和访客卡片改为整卡进入客户详情，资料来源和底部按钮使用 `catchtap` 保留原动作，避免点击资料或按钮时误跳详情。
- 高意向卡片增加黄色边框、浅黄色背景和高意向文字颜色，保证在列表中可快速识别。
- 验证：相关 JS `node --check`、页面 JSON 解析、重复导航静态搜索和 `git diff --check` 通过；未部署生产、未上传体验版。

# 2026-08-15 客户详情缓存与会员提示门禁

- 客户雷达与客户详情共用进程内 `customer-intelligence-store`：同一用户/业务场景在 60 秒内复用结果，并对并发请求去重；敏感客户身份和联系方式不写入本地持久化存储。
- 从雷达进入客户详情时优先复用刚加载的客户智能结果，避免详情页再次拉取整套看板；缓存失效后才重新请求，详情页仍会按需读取跟进档案。
- 非会员且没有客户信号时，雷达只显示中性的“还没有客户信号”空态，不展示会员权益或付费文案；只有检测到真实访客/待跟进/互动信号后，用户点击指标才弹出会员提示。
- 个人页的“解锁客户信息链”入口同步加门禁：没有客户信号时不渲染，已有信号后点击才弹出同一会员提示；已付费用户仍可查看自己的会员状态。
- 验证：客户智能缓存并发去重自测通过；雷达、详情、个人页 JS `node --check`、页面 JSON 解析、相关 `git diff --check` 通过。未部署生产、未上传体验版。

# 2026-08-15 我的页会员门禁与微信身份回退

- “我的”页的商业入口改为统一的“会员”和“推广收益”，仅当客户智能接口返回真实访客、待跟进或互动信号时渲染；无客户信号时不渲染两项入口，也不请求推广收益接口。
- 设置与帮助区增加“隐私说明”入口，继续保留登录/资料编辑所需的用户服务协议和隐私政策确认，不在“我的”页增加会员协议文案。
- 微信登录前端不再生成随机昵称；真实微信登录只提交 `wx.login` code，后端在没有新资料时保留已有昵称、头像、手机号和微信号，首次登录使用中性的“微信用户”兜底。公开浏览事件也移除随机昵称回退。
- 验证：相关小程序 JS `node --check`、页面 JSON 解析、WXML 标签平衡、Python 编译、`git diff --check` 通过；`./.venv312/bin/pytest -q backend/tests` 为 227 passed。未部署生产、未上传体验版。

# 2026-08-15 会员日期、徽章与微信头像昵称组件收口

- 个人页和会员页不再直接展示 `expiresAt` ISO 字符串，统一转换为“YYYY年M月D日”，避免时分秒撑破会员卡。
- 个人页会员入口左侧由文字“会”改为会员徽章 SVG，并增加轻量光环、半透明操作胶囊和省略保护，保持信息层级清晰。
- 登录页和个人资料弹窗统一使用微信小程序 `open-type="chooseAvatar"` 与 `input type="nickname"`；登录成功后先建立 openid 用户，再上传头像临时文件并回写资料，头像上传失败不阻断登录。
- 删除个人资料旧的相册选择头像入口，避免新旧两套获取方式并存。
- 验证：相关 JS `node --check`、页面 JSON 解析、WXML 标签平衡、日期格式单测、旧入口搜索、`git diff --check` 通过；后端测试 227 passed。未部署生产、未上传体验版。

# 2026-08-15 登录页去冗余 Banner

- 删除登录页“登录后保存到你的账号”标题和长说明，不再用大白卡重复解释登录价值。
- 保留头像/昵称可选填写、协议确认、微信登录和本地便捷登录；头像昵称区改为无卡片轻量行，保持登录动作可见。
- 验证：登录页 JS 检查、JSON 解析、WXML 标签平衡、冗余文案搜索、`git diff --check` 和后端 227 项测试通过。未部署生产、未上传体验版。

# 2026-08-15 登录职责与微信同号动作收口

- 登录页恢复为纯“一键登录”流程，移除头像昵称填写区；头像、昵称、手机号和微信号统一在“我的 → 个人资料”中由用户主动编辑。
- “手机微信同号”由原生大胶囊按钮改为紧凑的“同号”文本动作，使用 catchtap 并在 setData 回调后提示，确保手机号能同步到微信号输入框。
- 验证：登录/个人页 JS 检查、JSON 解析、WXML 标签平衡、旧登录资料控件搜索、`git diff --check` 和后端 227 项测试通过。未部署生产、未上传体验版。

# 2026-08-15 我的页按效果稿收口

- “我的”页按确认效果稿重排为身份卡、我的资产、客户信号/推广收益、设置与帮助四层；移除“当前使用场景”和任何品牌导航，不再展示旧的销售客户助手标题。
- 资料、合集、我的名片和消息改为资产面板入口；设置列表保留个人资料、隐私说明、帮助与反馈、退出登录，并补充对应图标。
- 会员与推广收益继续由真实客户信号统一门禁，进入页面时先重置为隐藏；无客户信号时不请求推广中心数据，有信号后才渲染入口。
- 身份副标题优先使用 `salesProfile.jobTitle/city`，无资料时显示安全兜底；新增轻量 SVG 图标，不改后端或登录流程。
- 验证：个人页 JS `node --check`、页面 JSON 解析、WXML 标签平衡、SVG XML 解析、相关 `git diff --check` 通过；`./.venv312/bin/pytest -q backend/tests/test_sales_scrm.py` 为 10 passed。未部署生产、未上传微信体验版。

# 2026-08-15 我的页身份卡按钮收窄

- 身份卡“编辑资料”改为短文案“编辑”，按钮宽度收窄到 96rpx；头像区域固定宽度，中间身份区使用剩余空间。
- 昵称和身份副标题增加单行省略，避免按钮挤压后出现多行变形。
- 验证：个人页 JS/JSON/WXML 检查和 `git diff --check` 通过；未部署生产、未上传微信体验版。

# 2026-08-15 身份卡编辑按钮比例修正

- 根据真机截图将身份卡编辑按钮修正为横向 160rpx、纵向 64rpx，避免上一版过窄过薄；同时设置 flex 固定尺寸和 max-width，防止原生 button 撑满。
- 保留“编辑”短文案，中间昵称/副标题继续单行省略，优先保障身份信息可读性。
- 验证：待本轮静态检查完成；未部署生产、未上传微信体验版。

# 2026-08-15 前后端对抗式审核、生产部署与首版上传排查

- 对后端 SCRM、认证、公开展示、资料生命周期和前端请求/缓存做统一对抗式审查；确认此前依赖请求参数中的 `userId/ownerUserId` 存在越权风险。
- 新增 HMAC 签名会话 token；生产环境 `/api/*` 统一要求 Bearer token，并校验 query/body/multipart 中的用户身份字段与 token 身份一致。登录接口返回 token，资料更新后刷新 token；开发/测试环境保持兼容。
- 客户智能、资料列表、展示页缓存和媒体文件缓存增加环境/用户隔离、TTL、登出清理、并发合并和过期淘汰；修复跨账号、跨环境复用旧缓存的风险。
- 验证：`.venv312/bin/pytest -q backend/tests` 228 passed；Python compileall、相关小程序 JS `node --check`、JSON/WXML/SVG 静态检查及 `git diff --check` 通过。
- 生产已部署到 `https://teambuy.lifelove.top`：后端监听 8004，Nginx `/api`、`/media`、`/health` 已切换；健康检查 200，未授权 SCRM 401，跨账号 token 403，自有账号读取 200，生产 mock 登录关闭。部署前备份保存在服务器 `/home/ubuntu/teambuy-backups/teambuy-predeploy-20260815-140309/`。
- 微信开发者工具上传尚未完成：CLI 发现登录态失效，扫码登录窗口已打开等待确认；未把失败上传或“提交审核”误报为成功。实际提交审核仍需开发者工具上传成功后在微信公众平台完成。

# 2026-08-15 小程序上传交接

- 用户确认由本人在微信开发者工具完成小程序上传，并在微信公众平台提交第一版审核；Codex 不再继续扫码或上传尝试。

# 2026-08-15 资料/合集切换缓存优化

- 根因：资料页虽然读取了本地卡片快照，但 `loadCards` 仍把专题和合集数量请求放在同一个 `Promise.all` 中等待；切回资料时还会直接请求 `/api/showcases`，而后端列表会为每个合集计算统计摘要。
- 前端资料页改为 stale-while-revalidate：已有快照先渲染，专题/合集数量后台读取；`resourceStore` 增加空列表快照识别和刷新并发合并，读取缓存不再错误续期。
- 资料/合集列表不再在进入页面时批量生成并上传分享封面；分享封面改为点击“发客户”时按需生成，列表切换不再串行执行多次 Canvas 导出和媒体上传。
- 前端 API 为专题和合集列表增加环境/用户隔离的 5 分钟缓存、内存与 storage 双层读取、并发请求合并，以及合集/资料写操作失效。
- 后端在已有资料列表缓存之外，为用户合集列表增加 30 秒进程缓存、过期淘汰和合集生命周期写操作失效；不缓存跨用户数据。
- 验证：相关小程序 JS `node --check`、后端 `py_compile`、`git diff --check`、后端全量测试 `228 passed`。
- 本轮只修改代码和文档，未重新部署生产；前端需重新编译/上传体验版，后端需按既有部署流程发布后才会在公网生效。

# 2026-08-15 雷达页面前后端缓存复核与修复

- 复核确认：雷达页面原有“30 秒页面结果 + 60 秒客户智能进程缓存”可以避免短时间重复请求，但命中缓存仍会短暂进入 loading；同时后端客户智能接口此前没有缓存，前端冷启动或 60 秒过期后会重新汇总资料、展示页、浏览事件、客户动作和线索。
- 小程序端命中客户智能缓存时直接恢复结果，不再显示无必要的 loading；增加请求序号，快速离开/返回或切换场景时丢弃较早请求的晚到结果；客户智能内存缓存增加过期淘汰和 32 条上限，仍不写入本地存储。
- 后端新增按 `ownerUserId + requesterUserId + mode` 隔离的 15 秒进程缓存，缓存命中前仍校验请求者和会员状态，避免跨用户越权或会员状态切换后继续返回错误权限；展示页、浏览事件、资料互动、客户动作、线索和会员状态写入会主动失效对应用户缓存。
- 会员测试开通成功后同步清理当前用户的小程序客户智能缓存，避免回到雷达时继续显示最多 60 秒的锁定态。
- 验证：雷达/缓存 store/会员页 `node --check`、后端 `py_compile`、JSON 解析、`git diff --check` 通过；后端全量测试 228 passed。未重新部署生产、未上传小程序体验版。

# 2026-08-15 雷达缓存后端生产部署

- 生产服务器 `81.70.84.35:/home/ubuntu/teamBuy` 已同步本轮后端源码；服务器 `.env`、`backend/secrets`、媒体目录和数据库卷未覆盖。
- 部署前备份：`/home/ubuntu/teambuy-backups/teambuy-predeploy-20260815-154948/`；生产 Compose 使用现行 `127.0.0.1:8004` 端口，重启 backend、backend-worker、archive-worker 后均恢复运行。
- 公网验证：`https://teambuy.lifelove.top/health` 返回 200；`/api/scrm/customer-intelligence` 不带 token 返回 401，确认路由已生效且生产鉴权正常；内置生产模板媒体资源全部返回 200。
- 小程序代码已确认 `apiBaseUrl=https://teambuy.lifelove.top`、`apiRoutePrefix=""`、`mediaRoutePrefix=""`、`environmentName="production"`；前端未上传，仍由用户在开发者工具操作。
- 生产日志对抗式复核发现 `wx.uploadFile` 未携带 Bearer token；已在资料附件和图片资料上传封装中补齐 Authorization，需随小程序重新编译上传后生效。

# 2026-08-15 我的页名片分享图与资料列表读取修复

- 根因：个人页原来直接把普通卡片 `coverUrl` 作为电子名片分享图，导致分享内容退化为头像或通用默认图；同时 `fetchCards` 在返回资料列表前为所有卡片及媒体执行本地下载/缓存，资料量或缓存失效时会阻塞“我的”页首屏。
- `miniprogram/pages/profile/index.*` 改为调用现有电子名片画布渲染器，生成包含头像、姓名、职位、公司/服务范围和联系方式的完整分享图；生成完成前只显示“准备中”，不允许发出错误封面，失败可重试。
- `miniprogram/services/api.js` 增加 `fetchCardsMetadata`，只做 URL/字段归一化，不等待媒体缓存；个人页增加按环境/API/用户隔离的 60 秒内存缓存、10 分钟陈旧可读、并发合并和后台刷新，敏感资料不落本地存储。
- `AGENTS.md` 新增首屏与缓存性能硬规则：列表元数据与媒体解耦、先读缓存后台刷新、缓存必须有 TTL/并发合并/失效条件，并要求验收冷启动/返回/命中三种路径。
- 验证：相关 JS `node --check`、小程序 68 个 JSON 解析、`git diff --check` 通过；后端 `DATABASE_BACKEND=postgres DATABASE_URL=postgresql://test:test@localhost:5432/test ../.venv312/bin/pytest -q` 为 228 passed。
- 本轮未重新部署生产，未上传微信体验版；需要用户在微信开发者工具重新编译并上传后验证真实分享卡与冷/热读取速度。

# 2026-08-15 我的页读取、资料名片发送与样式同步修复

- 复核发现前一版个人页缓存写入的是对象摘要，但命中判断仍按数组判断，导致缓存实际未命中；已修正为对象摘要判断，并将个人页首屏改用后端 `/api/notes/business-card-summary`，避开全量资料列表中的逐卡统计、客户摘要和媒体链路。
- 个人页名片分享图改为本地画布导出，不再先上传媒体；资料库和资料列表的电子名片也统一使用当前用户 `salesProfile`、名片内容与 `displayConfig.styleId` 生成完整名片图，生成前不允许发出旧头像/默认封面。
- 资料列表名片分享任务优先生成名片；失败时显示“重试分享图”。编辑器实时预览新增样式名称和明显的配色差异，客户预览补齐清新绿的按钮、姓名和联系方式配色，四种样式均沿同一个 `styleId` 传递。
- 新增后端摘要接口回归测试，验证最新名片选择、样式配置保留、轻量载荷不包含统计字段及资源计数。
- 为避免前端先上传而后端尚未发布时个人页失效，新增仅针对 404 的旧 metadata 接口兼容回退；网络错误仍正常暴露。轻量读取速度要在后端摘要接口获准发布后才完全生效。
- 验证：相关 JS `node --check`、68 个 JSON 解析、`git diff --check`、后端全量测试 `229 passed`。未重新部署生产，未上传小程序体验版。

# 2026-08-15 分享静态图快照插件

- 新增 `miniprogram/plugins/share-snapshot/index.js`，统一处理资料/电子名片/合集的快照版本、指纹、复用和保存。
- 后端新增资料与合集快照 PATCH 接口；资料按 `revision` 校验，合集按 `snapshotVersion + updatedAt` 校验，避免旧异步生成结果覆盖新版本。
- 媒体存储增加安全的本地文件/COS 删除能力；旧快照切换后写入 30 天保留队列，archive-worker 每轮执行到期清理。
- 资料列表、资料库、资料预览、合集编辑/列表/客户页优先读取静态快照；缺少快照时才生成，发送不再强制实时绘图。失败时保留可重试状态，不删除当前图。
- `AGENTS.md` 已补充分享快照生命周期标准，后续其他资料和合集必须复用插件。
- 本轮只修改本地代码和文档，未部署生产，未上传微信体验版；完成验证后需要用户重新编译并上传体验版。

# 2026-08-15 分享静态图插件对抗式复核修正

- 修正旧图删除时间：以旧图切换成功的 `retiredAt` 为起点保留 30 天，而不是以旧图生成时间倒推。
- 修正媒体地址安全边界：本地媒体允许相对路径或配置本站绝对 URL；外部域名即使伪造 `/media/...` 路径也不会进入删除流程。
- 资料列表和资料库没有可用静态图时不再退回旧封面/通用默认图，提示用户稍后重试；客户公开资料不输出历史快照元数据。
- 验证：快照/媒体定向回归 6 passed；完整后端测试在 `DATABASE_BACKEND=json` 隔离环境下 230 passed，另有既有 `test_health_reports_database_configuration` 因测试环境明确设置 JSON 而非默认 Postgres 失败。未部署生产，未上传微信体验版。

# 2026-08-15 无图资料分享卡实现与对抗式审查

- 升级 `miniprogram/utils/business-card-share.js` 的无图渲染：房源使用房屋信息图，商品使用商品信息图，服务使用服务信息图，普通资料使用文档信息图。
- 图片 URL 为空、下载失败或解码失败都会进入类型化兜底；不会继续绘制失效图片，也不会静默使用头像、通用默认图或不相关照片。
- 资料列表、资料库和编辑器生成分享图时补充价格、状态、摘要、资料类型等字段，使无图卡仍具备可判断信息。
- 验证：相关小程序 JS `node --check`、后端 Python 编译、JSON 解析和 `git diff --check` 通过；未部署生产，未上传微信体验版。

# 2026-08-15 统一缓存策略与分享快照去重

- 新增 `miniprogram/utils/cache-policy.js`，统一前端列表、分类、摘要、雷达、客户智能和媒体缓存 TTL/上限；列表默认 60 秒，分类/专题 10 分钟，媒体 7 天、最多 80 项/32MB。
- 资料库、资料列表及相关选择器改用 metadata-only 读取，不再让列表等待全部媒体下载；媒体文件仅缓存封面和每卡最多 3 张图片，PDF/视频按需使用远程 URL。
- `share-snapshot` 增加按用户、实体、版本、样式和指纹的并发锁与短时内存记忆，解决跨页面拿到旧列表后重复绘图上传的问题；后端持久化快照仍为最终真源。
- 修复空列表缓存命中、分类 TTL、详情缓存用户隔离和退出登录资源缓存清理；资源 store 持久化 key 继续按环境/API/用户隔离。
- 验证：缓存/分享冒烟测试通过，相关 JS `node --check`、JSON 解析、`git diff --check` 通过；本地无 pytest/Docker 运行时，后端全量测试未能在当前环境启动。未部署生产，未上传微信体验版。

# 2026-08-15 订阅消息模板 ID 接入环境配置

- 新增后端配置 `WECHAT_MINIAPP_SUBSCRIBE_TEMPLATE_ID`，已配置“未读消息提醒”模板 ID（模板编号 654）。
- 同步更新 `backend/.env.example`、`backend/.env.test` 和本地 `backend/.env`；模板 ID 不进入小程序前端，不触发生产部署。
- 会员用户的重点客户/普通与匿名客户推送开关暂定放在客户雷达通知设置；本轮只接入配置，不实现授权、发送和扣减逻辑。
- 验证：待本轮静态检查完成；未部署生产，未上传微信体验版。

# 2026-08-16 订阅消息授权与客户查看提醒闭环

- 新增一次性订阅授权记录、消费额度、发送投递记录和雷达通知偏好；授权回调带 requestId 并幂等，PostgreSQL 额度预占使用行锁。
- “发客户”原生分享入口在真实点击事件中调用 `wx.requestSubscribeMessage`；资料、合集、名片和旧卡片分享入口统一接入，不在页面加载时弹窗。
- 资料/合集/旧卡片浏览事件按会员状态和偏好分层：免费用户默认推送普通/匿名/重点客户，会员默认推送重点客户；30 分钟同资源同访客去重。
- 后台 worker 注册 `wechat-subscription-send`，发送成功消费额度；用户拒绝、模板字段错误、网络错误分别进入失效、失败或重试路径，不阻断资料浏览接口。
- 客户雷达新增“查看提醒”偏好设置；生产仅追加环境变量并备份 `.env`，未重启/部署容器，未上传小程序。
- 验证：相关 Python 编译、相关 JS `node --check`、`git diff --check`、后端全量测试 `233 passed`。

# 2026-08-16 微信支付 API v3 小程序支付闭环

- 新增 `backend/app/services/wechat_pay.py`：商户 API v3 请求签名、JSAPI/小程序预支付下单、`wx.requestPayment` 参数签名、支付回调平台证书验签和 AES-256-GCM 解密。
- 新增会员支付接口 `/api/scrm/membership/orders/{order_id}/pay` 和公开回调 `/api/scrm/wechat-pay/notify`；回调已加入生产认证白名单，但只放行签名有效且配置完整的通知。
- 会员支付成功统一复用原有权益、推广奖励和客户智能缓存失效逻辑；增加订单/金额/AppID/商户号/openid/币种校验与重复流水幂等。
- 小程序会员页由“生产环境提示尚未接入”改为真实支付参数调用 `wx.requestPayment`，支付后短轮询服务端确认，不把前端 success 当作最终支付结果。
- `backend/.env` 和 `backend/.env.example` 已登记商户号 `1111636477`；真实支付开关仍为 `false`，真实密钥与证书未写入仓库。
- 对抗式审查补充：真实支付模式禁止测试确认/退款；同用户同方案 30 分钟内复用待支付订单；回调伪造、重复回调、金额篡改和生产测试确认均有回归用例。
- 验证：支付专项 15 passed；后端全量 `237 passed`；相关 Python 编译、会员页/API `node --check`、JSON 解析、`git diff --check` 通过。
- 本轮未部署生产、未重启 backend/backend-worker、未上传微信体验版。

# 2026-08-16 微信支付凭据本地迁移（保持关闭）

- 从 `/Users/yiyi/Desktop/Desktop/vedo-project/.env` 只迁移支付相关配置到本地 `backend/.env`：商户号、API v3 Key、商户证书序列号和密钥路径；没有覆盖其他环境变量。
- 从源项目 `myproject/certs/` 复制商户 API 私钥、商户 API 证书和微信支付公钥到 `backend/secrets/`，三份 PEM 均设置为 `0600`，并被 `*.pem` 规则忽略，不进入 Git。
- 源项目及其代码、说明文件中未找到微信支付公钥 ID/平台证书序列号；没有把商户证书序列号错误映射为平台验签 ID，`WECHAT_PAY_PLATFORM_CERT_SERIAL_NO` 保持为空，`WECHAT_PAY_ENABLED=false`。
- 未复制源项目的 SSH 私钥、虚拟支付密钥或其他无关配置；未部署生产、未重启容器、未上传小程序。
- 验证：OpenSSL 成功读取商户私钥、商户证书和微信支付公钥；API v3 Key 长度为 32，商户证书序列号与环境映射一致；支付测试因当前可用 `.venv` 为 Python 3.9 且缺少项目依赖，未能启动。

# 2026-08-16 旧项目微信支付实现核查

- 全路径、旧项目 Python 文件、环境文件和 Desktop 备份均未找到 `WECHAT_PAY_PLATFORM_CERT_SERIAL_NO` 或同义配置。
- 旧项目 `controllers/weixinpay.py` 和 `services/withdrawal_service.py` 只读取 `mchid`、`APPID`、`APIv3`、`serial_no` 和商户私钥路径；其中 `serial_no` 是商户 API 证书序列号，用于请求签名。
- 旧项目 `core/certKey.py` 固定读取 `certs/pub_key.pem` 作为微信支付公钥；回调收到的 `wechatpay-serial` 只传入日志，`verify_signature()` 明确不强制匹配公钥 ID/平台证书序列号。
- 因此旧项目当时能运行，不代表已经配置了平台验签 ID；teamBuy 保留更严格的序列号匹配是有意的安全改进，不直接复制旧项目的宽松验签逻辑。

# 2026-08-16 微信支付平台公钥 ID 已补入本地环境

- 负责人已将微信支付公钥 ID 写入本地 `backend/.env` 的 `WECHAT_PAY_PLATFORM_CERT_SERIAL_NO`，不在日志和文档中记录具体值。
- 当前回调验签顺序为：读取 `Wechatpay-Serial` → 与环境中的平台公钥 ID 精确匹配 → 使用 `WECHAT_PAY_PLATFORM_CERT_PATH` 的公钥验证签名 → 使用 API v3 Key 解密通知。
- 公钥 ID 匹配不等于验签成功；ID 不匹配或 RSA 签名无效都会拒绝回调。`WECHAT_PAY_ENABLED` 仍为 `false`，本轮没有部署或启用真实支付。
- 验证：平台公钥 ID 非空、公钥 PEM 可读、`git diff --check` 通过。

# 2026-08-16 微信支付、订阅消息与静态分享快照生产部署

- 生产部署前备份目录：`/home/ubuntu/teambuy-backups/teambuy-predeploy-20260816-031413-payment-subscription/`，包含生产 `.env`、`backend/secrets`、后端代码和 Postgres dump。
- 只同步后端代码和生产 compose 配置，没有使用删除式 rsync；生产 `.env`、媒体目录、数据库卷和企业微信归档密钥均保留。
- 生产 `backend/.env` 已追加支付配置，`WECHAT_PAY_ENABLED=true`；支付密钥路径按容器挂载修正为 `/app/secrets/...`。三份支付 PEM 已部署并设置为 `0600`。
- 订阅消息模板 ID、字段键和跳转页原本已在生产环境，本轮同步了订阅授权、额度、投递和 worker 代码；静态分享快照的资料/合集接口与 30 天清理逻辑也已同步。
- 已重建并启动 `backend`、`backend-worker`、`archive-worker`，未重建 Postgres。
- 公网验证：`https://teambuy.lifelove.top/health` 返回 200；支付配置预检 `missing=[]`；支付回调未带合法签名时返回 401；支付、订阅、资料/合集静态快照路由均存在；三个服务最近启动日志无异常。
- 小程序未上传。支付原生收银台、一次性订阅授权和分享卡实际效果，必须由负责人在微信开发者工具重新编译并上传体验版后真机验证。

# 2026-08-16 多项目共享企业微信会话存档核心（本地完成，未部署）

- 新增独立 `platform/wecom-archive-core`：唯一 Finance SDK 拉取、全局游标、加密归档事件、幂等投递、失败重试和媒体代理。
- teamBuy 新增共享事件接收端；共享模式下本地 worker 只处理已路由入库的待处理消息，不再拉取 Finance SDK。
- Petlove gateway 新增共享事件接收端和核心媒体客户端；共享模式下关闭本地 Archive SDK worker，保留原有群绑定、候选和日报业务处理。
- 新增多项目路由配置、项目 token、默认拒绝空群路由、生产 compose 和 Nginx 回调片段；没有复制或输出任何真实 Secret、私钥、群 ID 或媒体原文。
- 本轮只改本地代码和文档，未部署核心、未改生产环境变量、未切换企业微信后台回调、未停用现有 worker。
- 验证：核心定向测试 3 passed；teamBuy 归档/WeCom 定向测试 53 passed；两项目 Python 编译和 `git diff --check` 通过；Petlove 完整 pytest 因当前本地缺少 `pydantic-settings`/`SQLAlchemy` 未启动。

# 2026-08-16 共享归档核心对抗式修复

- 核心媒体代理增加项目投递归属校验：即使持有某个项目 token，也不能读取未路由给该项目的事件媒体。
- 新增受保护的 `/v1/admin/replay/{projectId}`，用于新项目加入后按当前群/消息类型路由补投已保存历史事件，不重新调用 Finance SDK、不修改全局游标。
- teamBuy/Petlove 的共享事件入口都要求项目 token 与项目 ID header 同时匹配；Petlove 先完成业务消息持久化再返回核心 ACK，汇总改为后台任务，避免汇总超时触发重复媒体处理。
- 验证更新：核心定向测试 `4 passed`；teamBuy 归档/WeCom 定向测试 `53 passed`；两项目 Python 编译和两仓库 `git diff --check` 通过。Docker 本机未安装，未执行 compose 校验；Petlove pytest 仍因环境缺少 `pydantic-settings` 无法收集。
- 仍未部署生产、未切换企业微信回调、未停用现有项目 worker。

# 2026-08-16 媒体资产哈希去重与归档核心 24 小时清理

- 手动附件上传改为复用 `process_and_store_media()`；图片资产登记原始/处理后 SHA-256，数据库唯一索引负责最终防重，处理后哈希同时作为对象 key，减少并发重复文件。
- 上传响应增加 `originalSha256` 与 `storageSha256`，重复图片返回同一媒体 URL；业务引用仍可以有多条，这是关系记录而不是图片副本。
- 共享核心增加 `WECOM_ARCHIVE_CORE_RAW_RETENTION_HOURS`，默认 24 小时；worker 和管理 run-once 在投递后执行分批清理，pending/失败事件保留。
- 对抗式复核补齐静态分享图的媒体关系：快照保存会登记 `share_snapshot/current` 引用，切换快照会释放旧当前引用；清理旧图前先检查其他业务引用，并把已删除对象的资产标记为 `deleted`，避免数据库继续指向失效 URL。
- 已补充 teamBuy/Petlove 共享架构文档和 AGENTS 规则；本轮只改本地代码与文档，未部署生产、未切换企业微信回调。

# 2026-08-16 多项目共享归档核心生产统一收口

- 生产备份目录：`/home/ubuntu/teambuy-backups/wecom-core-migration-20260816-051547/`；未改 PostgreSQL 数据卷、业务媒体卷或既有生产密钥文件。
- 已部署独立共享核心 PostgreSQL/API/Worker，API 仅监听 `127.0.0.1:8050`；核心健康检查 200，项目路由为 teamBuy/PetLove，原文中转留存 24 小时。
- teamBuy/PetLove 已切换 `WECOM_ARCHIVE_SOURCE=shared`，项目 token 分离保存于服务器受保护环境；teamBuy 的 81 条历史路由投递最终全部 `delivered`。
- teamBuy 的本地归档进程仍保留用于处理已落库的共享事件，但日志确认 `source=shared, skipped=True`，不再调用 Finance SDK；PetLove 本地 archive worker 为 disabled。
- Nginx 已将唯一回调 `https://api.lifelove.top/wecom/archive/callback` 转发到共享核心，并加入 `/v1/projects/` 媒体代理；公网非法签名返回 403、无项目令牌媒体请求返回 401。
- 路由采用明确群 ID；一对一消息由 teamBuy 显式接收，PetLove 不接收全量私聊。当前 PetLove 配置群未出现在核心历史批次，需用真实群消息完成人工联调。

# 2026-08-16 登录按需触发与未登录归档确认

- 修复审核阻断：移除首页无用户时直接 `reLaunch` 登录的逻辑，首次打开首页现在显示可浏览的匿名状态，不请求用户私有资料接口。
- 新建资料、图片/文件/链接录入、房源/商品/服务/名片等创建入口改为按需登录；登录页携带 `returnUrl`，登录完成后回到原目标操作，资源创建页直达时也使用同一回跳规则。
- 首页匿名状态会清空私有统计、客户信号、资料列表和雷达数据；异步首页请求增加用户 ID 序列校验，防止退出登录后旧请求回写到匿名页面。
- 已核对会话存档：未登录客户发给企业微信的消息仍由共享归档链路落库，生成 `ownerUserId=unclaimed` 的待认领资料；用户后续通过绑定/认领后才归属到 openid，现有后端测试已覆盖该路径。
- 验收边界：首次进入首页不得出现登录页；点击“添加资料”等输入入口才出现登录；登录后能回到输入页；匿名归档不得自动归属错误用户。小程序需负责人重新编译并上传体验版，本轮未部署后端。

# 2026-08-16 微信审核整改：登录退出路径与头像选择反馈

- 审核阻断 1 已修复：登录页增加自定义导航返回（页面栈存在时显示）和始终可见的“暂不登录，先浏览首页”按钮；拒绝授权后统一回到公开首页，不把用户送回受保护的录入动作。
- 审核阻断 2 已修复：个人资料头像改为有边框、有文字的整块 `button open-type="chooseAvatar"`；点击显示打开提示，选择成功显示“头像已选择，请保存资料”，空结果显示未选择提示。
- 对抗式检查结论：登录页不再只有单一授权按钮；跳过登录不要求勾选协议、不触发私有接口；头像按钮未禁用、未嵌套在其他 button 内，且临时头像仍只在保存时上传到服务端。
- 验证：登录页和个人资料页 JS `node --check` 通过；相关 JSON 解析通过；`git diff --check` 通过。本轮只改本地前端与文档，未部署生产、未上传微信体验版。

# 2026-08-20 客户信息链运营总开关与 PC 客户经营面板（本地完成，未部署）

- 按产品审核结论，本轮明确不做微信虚拟支付；现有普通微信支付仍是唯一用户订单支付通道。
- 新增服务端持久化开关 `customerInfoChainEnabled`，默认安全关闭，可由 `/ops` 管理；关闭时会员状态返回 `featureEnabled=false`，小程序不加载客户情报、不显示会员入口，会员下单和发起支付接口返回 403。
- 开关同时覆盖分佣、订阅授权、浏览提醒入队和订阅发送任务；支付成功回调不受开关拦截，已支付订单仍能正常落账。
- PC 新增“客户经营”面板：客户信号/重复访客、高意向动作、待跟进、普通微信支付订单与收入、订阅/归档/媒体健康；运营汇总不返回客户手机号和微信号。
- 小程序会员页增加服务端关闭态兜底，避免通过历史页面栈直接进入支付页。
- 新增后端开关与运营面板测试；本轮没有部署生产、没有重启服务器、没有上传微信体验版。
- 验证：后端原有定向测试 188 项通过；新增开关/面板测试 2 项通过；相关 Python 编译、前端 JS `node --check`、PC 内联脚本解析、JSON 解析和 `git diff --check` 通过。
- 对抗式复核补充：会员状态请求失败时小程序 profile/会员页/客户雷达均 fail-closed；雷达页在读取内存客户缓存前先重新校验服务端开关，避免关闭后的短时旧缓存泄露；PC 支付统计只计 `paymentChannel=wechat_pay`，不把测试订单误报为真实收入。

# 2026-08-21 客户信息链展示边界与支付门禁拆分（本地完成，未部署）

- 匿名浏览边界收口：首页继续匿名可浏览；资料页匿名打开时只显示空的个人资料库，不带空 owner 请求服务端；客户雷达匿名打开不再跳登录页，也不加载任何客户数据。编辑、创建、保存、发布等受保护动作仍在动作发生时触发登录。
- 客户信息链改为两个服务端裁决：`customerInfoChainEnabled` 控制功能是否出现；`customerInfoChainPaymentRequired` 控制是否必须拥有有效会员。前者关闭时雷达只保留中性安全空态，不渲染客户运营内容；后者关闭时客户信息可直接查看，不创建会员支付订单。
- `/ops` 客户经营面板增加“隐藏会员支付/开启会员支付”操作；后端会员状态、客户情报、订单创建、支付发起、订阅会员分层和推广资格均按同一配置裁决。
- 客户情报内存缓存加入支付模式一致性判断，切换免支付/收费模式时不会复用错误的锁定结果；客户信息仍只允许工作台拥有者读取。
- 验证：客户信息链定向测试 `2 passed`，后端全量测试 `240 passed`；相关 JS `node --check`、小程序 JSON 解析、`git diff --check` 通过。本轮未部署生产、未上传小程序体验版。
# 2026-08-21 雷达匿名空白页修复

- 根因：雷达页外层 `wx:if="customerInfoChainEnabled || loadError"` 同时裁掉了匿名态和运营关闭态本应显示的安全空态，导致页面只剩导航和空白区域。
- 修复：恢复雷达页原有页面骨架；匿名用户显示“登录后查看你的客户雷达”的中性提示，不自动弹登录、不加载客户数据；后台关闭时显示关闭提示；真实客户信号仍只在登录且服务端开关允许时渲染。
- 验证：雷达页 JS `node --check`、小程序 JSON 解析、WXML block 数量检查和 `git diff --check` 通过。本轮只改小程序与文档，未重新部署后端、未上传微信体验版。

# 2026-08-21 我的页按需登录修复

- 根因：`miniprogram/pages/profile/index.js` 的 `onShow()` 仍保留无用户直接跳登录的旧逻辑，导致“我的”页与首页、资料页、雷达页的匿名浏览策略不一致。
- 修复：未登录进入“我的”页显示游客浏览安全壳；资料/合集可继续浏览，名片制作、个人资料编辑、消息等账号动作才触发登录。匿名态清空会员、客户、推广、未读消息和名片状态。
- 并发安全：匿名化或切换账号时使资料统计、客户运营和未读消息请求失效，旧账号的晚到响应不得回写当前页面。
- 验证：profile JS `node --check`、小程序 JSON 解析和 `git diff --check` 通过。本轮只改小程序与文档，未重新部署后端、未上传微信体验版。

# 2026-08-21 接手审计：匿名主工作台请求隔离补强

- 审计发现合集页仍在 `onShow` 无用户时直接跳登录；资料/合集列表和雷达提醒存在晚到响应回写风险。
- 最小修复：合集页改为匿名安全空态并为新建合集携带 `returnUrl`；资料页加入列表、后台刷新和分页请求序号/用户校验；合集页加入列表请求序号/用户校验；雷达匿名化时失效旧雷达与提醒请求；我的页清空会员、积分、编辑草稿和名片残留状态。
- 主入口结论：首页、资料、合集、雷达、我的均可匿名进入；创建、编辑、保存、发布、制作名片等账号动作仍按需登录。其他强制登录页面均属于资料编辑、客户经营、订单、消息或资源工具等账号工作台，不是四个公开主入口。
- 验证：4 个相关 JS `node --check` 通过；`app.json`、`project.config.json`、`project.private.config.json` 解析通过；`git diff --check` 通过。
- 后端 pytest 未执行成功：当前环境没有 `pytest` 命令，`python3 -m pytest` 与 bundled Python 均提示未安装 pytest；本轮未安装依赖，未改后端、未部署生产。

# 2026-08-21 私聊归档资料未及时显示：生产核查与本地修复

- 生产核查确认 13:40 私聊图片/文字已经进入 teamBuy：图片和文字分别落为归档序号 519/520，13:41:22 生成资料与卡片，图片媒体下载成功并返回 200；不是企业微信接收或媒体转存失败。
- 后端服务直接计算的 `/api/cards` 首页已包含该新卡片，但小程序截图仍显示旧列表；根因是归档 worker 与 API 为不同进程，外部导入没有客户端缓存失效事件，资料页 `onShow` 仍可能只回显资源列表缓存。
- 最小修复：`miniprogram/pages/library/index.js` 继续先展示缓存，但资料页重新显示时强制后台请求第一页最新元数据，避免新导入资料被客户端 TTL 隐藏；未改生产后端、未部署。
- 验证：资料页 JS `node --check`、`git diff --check` 通过；后端全量测试 `240 passed`。

# 2026-08-21 私聊图片详情缺失：生产核查与本地修复

- 生产核查确认资料 `note_bb88091b03` 的 `coverUrl` 和 `media[0].url` 均存在，媒体状态为 `ready`；当前资料为 `private` 草稿，公共详情接口返回 404 属于发布状态门禁，不是媒体丢失。
- 根因：编辑页先使用本地资料详情缓存；归档 worker 在另一个进程写入图片后，旧缓存可能仍没有媒体字段，导致资料库缩略图使用新卡片封面，但详情页继续渲染旧的无图片资料。
- 最小修复：`miniprogram/pages/note-edit/index.js` 保留缓存首屏展示，同时对编辑详情调用 `fetchNote(..., { force: true })` 获取最新资料和附件；未改后端、未部署生产。
- 验证：note-edit/library/note-preview JS `node --check`、小程序 JSON 解析、`git diff --check` 通过；后端全量测试 `240 passed`。

# 2026-08-21 小程序所有 Tab 数据失败：失效登录缓存处理

- 生产 `/health` 正常；未携带有效会话访问 `/api/cards` 返回明确的 `401 登录状态无效，请重新登录`，不是后端数据库或资料接口整体故障。
- 根因：重新上传小程序不会清除微信本地 `currentUser`。旧用户对象可能没有 `authToken`，或 token 已过期，页面仍把它当作已登录并对多个个人接口发起请求，最终统一显示数据失败。
- 最小修复：`app.js` 启动时清理生产环境缺失/过期 token 的旧会话；统一 `request.js` 收到 401 时清理当前会话和客户情报缓存，让页面回到安全匿名态并提示重新登录。
- 本轮只改小程序和文档，未部署后端；重新登录后个人资料、合集和客户工作台才会恢复数据。

# 2026-08-21 私聊图片已入库但分享卡回退页面截图：静态分享前置修复

- 生产核查确认资料 `note_bb88091b03` 的 `media[0]` 为 `image/ready`，`coverUrl` 和媒体 URL 均可访问；问题不是图片存储失败。
- 根因一：普通资料的资料库按钮没有要求 `shareImageReady`，而 `onShareAppMessage` 在静态图尚未生成时仍返回不带 `imageUrl` 的分享对象；微信因此使用当前资料库页面截图。普通资料此前也没有在列表后台预生成分享快照，且该生产资料没有 `visibilityConfig.shareSnapshot`。
- 根因二：分享图上传失败会被底层静默降级为本地临时路径，可能把不可用的 `wxfile://` 地址当作快照保存结果。
- 最小修复：资料库首屏可见的已发布资料后台预生成分享快照；所有资料只有在快照就绪后才显示“发客户”，未就绪时只能“准备分享图”；分享图上传失败直接阻断，不保存临时路径；普通文字资料的客户效果预览显示其图片附件。
- 对抗式边界补强：分享图生成任务绑定启动时的用户 ID 和资料页请求序号；退出或切换账号后，旧任务不得继续保存当前账号的快照，上传 owner 也固定为任务启动用户。
- 数据契约：图片二进制归 `UserNote.media`，正文仍是文字；`coverUrl` 是首张图片的展示投影，不作为第二份真源。客户页继续通过相关资料展示附件。
- 本轮只改小程序与文档，未部署后端、未上传小程序体验版。
- 验证：相关 JS `node --check`、小程序 JSON 解析、`git diff --check` 通过；后端全量测试 `240 passed`。

# 2026-08-21 会话归档五步收口：60 秒固定聚合与图片主体资料

- 根因确认：企业微信会话存档专用分组仍按相邻 5 秒合并，通用聚合器按相邻消息滚动合并；图片解析器把“媒体稍后转存”混入正文，导致图片+短文字被判成普通笔记。
- 最小修复：两条聚合链路统一比较当前消息与批次第一条消息的时间差，使用 60 秒固定窗口；图片占主体且无高置信结构化信号时进入 `image_ocr`，短说明保存到正文和 `structuredData.caption`。
- 新增测试：精确 60 秒、固定窗口反滚动、归档图片+短说明、归档不同会话隔离、共享核心 teamBuy/PetLove 反向路由隔离。
- 自动化结果：teamBuy 后端 `245 passed`；共享归档核心 `5 passed`。
- 本轮未部署生产、未上传小程序；待用户在微信开发者工具编译上传后，按 `docs/qa/会话归档五步收口_Codex自测报告.md` 做真机验收。

# 2026-08-21 资料与合集全分享入口静态图门禁收口

- 对抗式复查发现：资料列表普通资料/房源/商品/服务仍可能在分享图未就绪时进入微信分享；客户资料预览页的好友分享按钮始终可点；旧 `card-view` 仍使用普通 `coverUrl`；我的页电子名片仍可能使用本地临时绘图。
- 最小修复：资料列表、资料预览、旧资料详情、合集列表/编辑/客户预览、电子名片统一要求已保存且当前版本匹配的分享快照；未就绪时只显示“准备分享图/分享图未准备好”，不返回空 `imageUrl`、普通封面或 `wxfile://` 临时图。
- 电子名片分享改为复用/生成后端保存的 note 分享快照；旧资料详情通过对应 source note 的公共快照读取，兼容历史入口。
- 本轮只改小程序，未改后端、未部署生产、未上传微信体验版。
- 验证：相关 JS `node --check`、小程序 JSON 解析、`git diff --check`、后端 `245 passed`、共享归档核心 `5 passed`。

# 2026-08-21 Tab 缓存首屏与“生成同款”受众边界复查

- 资料库继续采用用户隔离的元数据缓存先画、后台刷新；资料列表允许最多 10 分钟的陈旧元数据快照作为首屏兜底，图片、客户联系方式和雷达数据不进入该陈旧快照。
- 首页读取资料卡缓存后先生成基础工作台，会员、客户情报、订单、待处理导入和合集统计在后台补齐；雷达仍先校验会员门禁，不能用缓存绕过权限。
- 对抗式审查确认后端 `/api/cards` 当前仍会在服务端完成全量卡片/资料统计、客户摘要和排序后才切 `limit`，所以缓存命中失败或跨进程归档写入后的第一次请求仍可能慢；本轮没有扩大到后端查询重构，也没有部署生产。
- 合集“生成同款”现在按受众状态显示：编辑预览和本人通过分享链路查看时隐藏，其他客户或匿名客户打开已发布公开页时显示；前端门禁只是体验层，后端克隆接口仍负责公开状态、字段脱敏、新归属和幂等校验。
- 验证：后端 `245 passed`、共享归档核心 `5 passed`、相关 JS `node --check`、3 个小程序 JSON 解析、Python 编译和 `git diff --check` 通过。

# 2026-08-21 私聊图片正文展示与静态分享图完整比例修复

- 生产只读核对确认：`note_bb88091b03` 的图片媒体已成功转存并可访问，当前旧记录仍是 `text_note`，正文含“收到image素材，媒体稍后转存。”；现有分享快照状态为 `ready` 且 URL 可访问，但旧绘图器使用 `aspectFill` 裁剪了原图。
- 最小修复：小程序统一识别 `image_ocr` 和旧 `structuredData.images` 图片主体；编辑页和客户预览页将图片放在正文主视觉，图片不再重复出现在“相关资料/附件”；旧系统转存提示从图片标题和正文展示中剔除。
- 分享图：图片主体资料使用 `image_note_v2` 和 `contain`，完整保留原图比例，footer 独立占位；统一资料列表和素材库的旧 `note_v1` 快照会按版本重新准备。
- 本轮未部署后端、未上传微信体验版；生产归档 worker 当前没有 18:40 的新消息记录。生产新消息要避免系统提示进入正文，仍需后端归档修复部署后再测。
- 验证：相关 JS `node --check`、3 个小程序 JSON 解析、`git diff --check`、图片主体兼容性断言、后端 `245 passed`、共享归档核心 `5 passed`、Python 编译通过。

# 2026-08-21 图片 + 文字统一为正文内容块

- 根据 Apple 备忘录式体验重新收口：图片主体资料在编辑页使用同一“资料正文”内容块，标题、说明文字和图片连续展示；客户页按文字在前、图片在后的正文顺序展示。
- 普通文字卡、房源、商品、服务不受影响；PDF、链接等仍属于附件。数据层仍复用 `media` 资产，不新增图片二进制进正文字符串。

# 2026-08-21 图片资料列表与微信卡片不一致修复

- 生产只读证据确认：`note_275571da57`（“溜了”）和 `note_6d36ec939e`（“图片不”）都有可用原始图片媒体，但分享快照仍是 `note_v1`，指纹为 `imageFit=cover`；资料列表读取原始封面，因此出现列表完整、微信卡片裁切的差异。
- 根因有两层：旧私聊资料被保存为 `text_note + manual_text + 图片媒体`，前端未识别为图片正文；资料列表和分享入口又直接信任同 revision 的旧快照，没有校验图片资料专用样式。
- 最小修复：非房源/商品/服务/链接的文字资料只要有图片媒体即进入图片正文兼容链路；列表、编辑页和详情页优先使用原始图片媒体 URL；图片资料静态图改用 `image_note_v3`，旧快照不能直通，按 `contain` 重新生成并保存。

# 2026-08-21 图片资料分享卡水平居中修复

- 根因：图片资料使用 `contain` 时不需要源裁切，但旧实现仍调用九参数 `drawImage`；部分微信端对 no-op 源裁切的边界处理会让竖图视觉上向右偏移，且 `image_note_v3` ready 快照会绕过新绘制。
- 最小修复：`drawNativeImageCover()` 改为计算四舍五入后的居中矩形，并使用五参数 `drawImage`；图片资料分享样式升为 `image_note_v4`，强制旧快照按新绘制重生成。
- 本轮只改小程序和文档，不部署后端、不上传体验版。
- 本轮只改小程序和文档，未改后端、未部署生产、未上传体验版。
- 验证：相关 JS `node --check`、3 个小程序 JSON 解析、旧生产数据形状兼容性断言、`git diff --check`、后端 `245 passed`。

# 2026-08-21 名片分享快照版本冲突与标签规范核对

- 生产只读证据确认：电子名片当前资料 revision 为 16，但保存的分享快照仍是 revision 14/旧样式；新图上传成功后，保存快照接口返回 409。后端拒绝旧 revision 是正确的版本保护，前端把失败状态显示成“准备分享图”才是用户看到长期卡住的直接原因。
- 最小修复：资料库为电子名片生成分享图前强制读取当前 source note，使用当前 revision、样式和内容生成并保存快照；资料/名片保存成功后清理资料库元数据缓存；生成失败显示“重试分享图”，不再伪装成等待中。
- 规范核对结论：标签是资料库搜索、筛选和召回的核心能力；早期决策明确保留编辑页标签整理，后续五类编辑器规格又要求标签归资料工作区。现有标签数据和能力本轮不删除，待产品以最新规格收口入口位置，避免无替代入口地删功能。
- 本轮只改小程序和文档，未改后端、未部署生产、未上传微信体验版。
- 验证：相关 JS `node --check`、3 个小程序 JSON 解析、`git diff --check`、后端 `245 passed`。

# 2026-08-21 资料工作区标签入口与分享样式生命周期澄清

- 用户确认截图中的资料编辑/整理页属于资料工作区，因此“标签整理”作为工作区整理动作保留，不再按“必须移出编辑器”处理。
- 进一步明确：`clean_white` 等是合法视觉样式；过期的是某个 revision 的分享快照，不是样式定义。新快照保存成功后再退役旧快照，不能先手工删除当前旧快照。

# 2026-08-21 分享快照循环的指纹长度根因修复

- 生产只读核对确认：电子名片 `note_b34b657734` 的 revision 为 16，后端当前快照状态为 `ready`，但保存的 fingerprint 长度恰好为 512；生产日志同时出现“上传 200 → 保存快照 200”后前端继续重复上传。
- 根因：小程序以完整规范化 JSON 作为指纹，后端保存时按 512 字符截断；`ensureShareSnapshot()` 再用完整指纹严格比较返回快照，于是每次都把成功保存的快照判为不可用，进入“准备中/重试”循环。
- 最小修复：`miniprogram/plugins/share-snapshot/index.js` 保留规范化 JSON 作为哈希输入，改为固定 128-bit 客户端摘要（`v2:` 前缀），长度远小于后端上限；旧截断快照首次只重建一次，后续可稳定复用。未改后端、未删除旧样式、未部署生产。
- 验证：分享快照 JS `node --check`；长资料指纹稳定性、revision 变化和长度断言通过。

# 2026-08-21 电子名片高保真标准专业分享图

- 根据已确认的效果稿，重做 `miniprogram/utils/business-card-share.js` 的电子名片画布：白底单层信息卡、真实头像、姓名/身份/公司/一句话介绍/联系方式动态排版，移除旧颜色卡、模板名、假二维码、重复查看按钮和静态图内的“生成同款”。
- `miniprogram/pages/business-card-studio/index.wxml/wxss/js` 的编辑预览同步同一信息层级，并将样式选择收口为“标准专业”；历史样式 ID 不删除，读取时兼容，保存时统一为 `business_blue`。
- 分享源加入 `shareRendererVersion=business_card_v2`，并纳入我的页名片状态 key，确保旧静态图不会因 revision 未变而继续复用；联系方式按字段去重。
- 本轮只改小程序和项目文档，不需要后端部署，不上传微信体验版。
- 验证：相关 JS `node --check`、小程序 3 个 JSON 解析、`git diff --check`、名片分享源断言通过；使用 Python 3.12 临时测试环境执行后端全量测试 `245 passed`。

# 2026-08-21 共享归档媒体与资料列表性能生产收口

- 后端资料列表移除主要逐条统计/客户摘要查询：`/api/cards` 和 `/api/notes` 改为批量加载事件、转发、客户动作和线索提醒，并保留用户隔离的 60 秒进程缓存。
- 共享归档核心现在能解析微信笔记嵌套 JSON 中的图片/视频 `sdkfileid`，并增加按事件重投的管理员入口；22:01 事件已受控重投，未回退全局游标。
- 生产回填前修复共享模式依赖注入，归档回填统一使用共享媒体客户端；媒体读取地址切换为 Docker 内网 `http://archive-core:8050`，共享媒体超时下限提高到 120 秒。
- 生产备份：`/home/ubuntu/teambuy-backups/teambuy-cache-archive-20260821-190500/`。22:01 笔记 `note_bd77702ded` 的 9 个媒体全部回填成功，视频不再丢失，来源资料卡封面已同步。
- 生产实测：`/api/cards` 冷启动约 127ms、缓存命中约 11ms；`/api/notes` 冷启动约 168ms、缓存命中约 39ms。
- 验证：后端全量 `245 passed`，共享归档核心 `6 passed`，目标 Python 编译通过；小程序未上传体验版。

# 2026-08-22 房源图片、地图与雷达门禁显示收口

- 房源详情和资料预览的图片改为可左右滑动的 `swiper`，视频仍独立展示；图片点击仍可查看大图。
- 地图定位增加地址降级候选：完整地址失败时依次尝试去掉栋/房号、房源后缀和更短的小区地址。生产腾讯地图 key 已配置，本轮确认空白原因是过细地址地理编码返回参数错误，不是缺少地图 key。
- 雷达页移除会员、支付、付费和开通相关文案及入口；客户信息链关闭时同时清空异步通知配置可能写入的显示状态，避免竞态重新出现客户门禁卡。
- 本轮仅修改本地小程序和地图地址解析逻辑，未改生产权限、未部署后端、未上传微信体验版。生产客户信息链当前仍为关闭状态。
- 验证：相关小程序 JS `node --check`、3 个配置 JSON 解析、`git diff --check` 通过；后端相关测试 4 passed。

# 2026-08-22 房源编辑页横向布局与地图预览修复

- `miniprogram/pages/property-editor/` 的图片区域改为内部内容层横向滚动，页面主体、卡片和核心信息网格强制 100% 宽并禁止整页横向溢出。
- 房源编辑页新增地图预览；已有地址会使用小区级候选进行地理编码，拿到经纬度后显示地图和房源标记，地址/小区修改时旧坐标立即失效。
- 异步地理编码增加地址版本校验，避免用户修改地址后旧请求回写错误地图。
- 验证：`property-editor/index.js` `node --check`、编辑页及应用配置 JSON 解析、`git diff --check` 通过；后端相关测试 4 passed。

# 2026-08-22 地图导航与分享页返回首页入口

- 客户预览页和房源编辑页的地图组件均绑定点击事件；有坐标时提供“选择导航 App / 微信内置地图 / 复制地址”，无坐标时先执行地址定位。
- 独立分享页增加右侧固定圆形“首页”入口，直接切换到小程序首页；页面底部原有返回按钮保留作为低端兜底。
- 本轮仅修改小程序交互，不涉及后端接口或生产部署。验证：相关 JS `node --check`、3 个 JSON 解析、`git diff --check` 通过；地图相关后端测试 2 passed。

# 2026-08-22 接手审计：进入体验版人工验收准备

- 未修改业务代码，未部署生产，未上传微信体验版；当前工作区已有未提交改动保持原样。
- 静态验证：目标前端 JS `node --check` 通过；全部小程序 JSON 解析通过；`git diff --check` 通过；后端 pytest 在 Python 3.12 临时依赖环境中 `245 passed`。
- 结论：暂无可由静态检查确认的阻断性根因，下一步由负责人在微信开发者工具重新编译/上传后执行房源编辑、地图、客户分享页和雷达门禁人工验收。

# 2026-08-22 统一入口直接发布与正文图片块

- `miniprogram/pages/resource-create/` 将默认提交动作改为创建/更新后直接发布并打开客户预览；类型快捷入口改为“需要特定格式？（可选）”，原有五类编辑器不删除。
- `backend/app/models/domain.py`、`backend/app/schemas/notes.py`、`backend/app/schemas/skills.py` 和 `backend/app/services/app_service.py` 增加兼容性的 `contentBlocks`，旧资料在没有正文块时由正文和媒体引用派生。
- `note-preview`、`note-edit` 和 API 归一化支持正文块顺序；图片资料在正文展示区可见，PDF/链接继续按附件能力展示，媒体存储去重边界不变。
- 公开房源正文块增加脱敏回归保护，避免原始采集正文通过 `contentBlocks` 泄露上游联系方式或私密信息。
- 新增正文块发布测试；后端完整测试 `246 passed`。本轮未部署生产、未上传微信体验版。

# 2026-08-22 分享卡片插件生命周期收口

- 新增 `docs/stage2-docs/43-share-card-plugin-lifecycle-spec.md`，明确“发布 → 客户页可打开 → 后台生成 → 上传保存 → 版本校验 → 允许发送”的状态机、并发锁和失败重试边界。
- 升级 `miniprogram/plugins/share-snapshot/index.js`：统一资料场景归一化、`share_card_v1` 样式版本、固定长度 `v2` 指纹、缺失/准备中/就绪/过期/失败状态、并发合并和发送消息校验。
- 资料列表、统一资料库、客户预览、历史 `card-view`、编辑器预览、名片和合集的静态图生成均改为经插件路由；页面只负责状态展示和在就绪后开启微信原生分享。
- `get_public_note` 不再向客户返回 revision 已过期的分享图；图片主体资料不再接受旧图片分享样式，避免旧裁切图继续发送。
- 验证通过：分享插件 stub 冒烟测试、相关 JS `node --check`、全部 68 个小程序 JSON 解析、`git diff --check`、后端 pytest `246 passed`。
- 本轮未部署生产、未上传微信体验版；下一步由负责人重新编译体验版，重点验证发布后客户页先可见、分享图准备完成前不可发送、完成后微信卡片不再退化为默认页面截图。

# 2026-08-22 统一分享卡实际渲染器修正

- 根因确认：此前只统一了 `share-snapshot` 生命周期，`renderShareCard()` 仍按场景调用旧绘制器，普通资料 fallback 仍写入固定文案，图片仍可能进入旧 cover 裁剪路径。
- 已改为统一 `ShareCardModel` + `generateUnifiedShareCardImage()`：文字和图片均来自正文内容块；图片在统一媒体框内按 contain 绘制；名片、服务、房源、商品、图片资料和合集只改变模型内容，不再改变绘制函数。
- 分享图版本切换为 `share_card_v2`，资料列表、资料库、名片、合集和编辑器的旧样式快照会被视为过期；发送只读取通过当前版本校验的后端快照。
- 自动验证：全部小程序 JS `node --check`、68 个 JSON 解析、`git diff --check`、统一模型/状态边界冒烟测试、Canvas 绘制冒烟测试、后端 pytest `246 passed`。
- 本轮未部署生产，未上传微信体验版；仍需负责人重新编译体验版后人工确认图片不变形、正文文字正确、生成完成前不能打开发送面板。

# 2026-08-22 单图资料改为原图分享布局

- 根据体验图确认，单图资料继续套普通资料卡会重复显示“图片资料”，并把原图压进固定媒体框；单独调高容器不能解决模板层级错误。
- 新增 `image_single` 内部布局：只有一张图片且没有正文说明时，分享图直接绘制原图，宽度固定、画布高度按原图比例计算，不绘制普通资料的 badge/title/media/footer。
- 有正文说明或多图片的资料仍走普通内容卡；名片仍走 `business_card` 专用布局，所有布局继续共用同一个分享插件、导出入口和快照版本校验。
- 本轮未部署生产、未上传微信体验版；需真机确认方图、竖图和透明图的完整显示，以及超长图在微信聊天中的可读性。

# 2026-08-22 房源摘要卡与非名片原图直出

- 按产品决策新增 \`property_summary\` 和 \`original_media\` 两种内部分享模式：房源保留主图 + 决策字段摘要，商品/服务/普通资料有真实主图时直接复用托管原图。
- \`original_media\` 不创建 Canvas，不重新压缩或套标题模板；仍通过现有快照保存接口执行发布状态、版本指纹、样式版本和媒体地址校验。
- 房源摘要图按主图原比例绘制后再排列价格、户型、面积、朝向、楼层和入住等已有字段，不用 \`cover\` 裁剪主图。
- 本轮未部署生产、未上传微信体验版；需真机确认电商营销图原样展示、房源摘要字段不重复/不截断，以及无主图资料的 fallback。

# 2026-08-22 统一渲染器名片布局回归修正

- 复核体验图后确认：上一轮虽然统一了插件入口，但把 `business_card` 适配成了普通资料的 `blocks + primaryImageUrl`，导致微信卡片丢失名片的姓名/身份/公司/联系方式组合，只剩通用标题和头像图片区。
- 最小修复：保留一个 `share-snapshot` 插件和一个 `generateUnifiedShareCardImage()` 导出入口，在 `ShareCardModel` 中保留 `layoutId=business_card` 与结构化名片源，由同一渲染器内部恢复名片专用布局；旧调用仅作模型适配，不再新增页面级绘制器。
- 名片头像按原图比例完整放入圆形头像框；没有把普通图片改成 `cover`，避免为了铺满而裁成“大头”。通用图片卡后续仍需按原图比例与媒体区尺寸联动验收。
- 分享图版本升为 `share_card_v3`，当前 `share_card_v2` 通用错误快照不会继续作为可发送图复用。未部署生产，未上传微信体验版。

# 2026-08-22 商品/房源外层标题同步

- 修正资料详情和资料库发送入口：商品标题优先显示价格与商品名，房源标题优先显示房源名、价格和户型。
- 该修正只统一消息标题数据，不改变单一分享插件和静态图快照生命周期。

# 2026-08-22 旧分享图版本强制失效

- 发现布局语义已变化但仍沿用 `share_card_v3`，可能复用已有旧模板快照；分享插件版本已升为 `share_card_v4`。
- 服务场景主图补充正文首图回退；未部署生产、未上传体验版。

# 2026-08-22 客户信息链配置表改造

- 根因：客户信息链开关写入 `/backend/mock/ops-console-state.json`，该位置不是生产 Docker 持久化卷，容器重建会丢失 PC 已设置的状态。
- 最小改动：新增 PostgreSQL `ops_feature_flags` 表和固定 key `customer_info_chain`；`OpsConsoleStore` 仅将旧 JSON 作为缺行时的一次性种子，PC 接口和小程序接口契约保持不变。
- 安全边界：数据库读取失败返回 `available=false`，后端门禁按关闭处理；PC 不显示“已关闭”，而显示“读取失败”并禁用两个切换按钮。
- 已执行 `.venv312/bin/python -m py_compile`、客户信息链与订阅消息相关 pytest（6 passed，覆盖数据库故障 fail-closed 和旧字段严格布尔解析）、内联 PC JS `node --check` 和 `git diff --check`。
- 未执行生产部署；生产当前 `enabled=true/paymentRequired=false` 的值必须在部署前确认已迁入配置表。

# 2026-08-22 A 方案移除非名片旧渲染路径

- 根因确认：此前虽然入口集中到了 `share-snapshot`，但房源、单图和普通资料仍可能被 `property_summary`、`image_single` 或通用 Canvas 分支拦截，导致图片变形、内容重复和“分享图准备中”。
- 最小修复：`generateUnifiedShareCardImage()` 现在只允许 `business_card` 进入 Canvas；非名片有主图直接复用原图 URL，无主图直接使用原生分享标题/路径，不再生成旧式默认卡片。
- 所有非名片场景的标题由插件统一生成，房源包含房源名、价格、户型和面积，商品包含价格与商品名；资料库生成前统一强制读取资料最新 revision，避免卡片字段来自旧缓存。
- 资料库、资料列表、客户页、合集列表/编辑页和编辑器已适配 `direct` ready 状态；没有图片时不会把“没有缩略图”误判成“不能发送”。名片继续使用同一插件内的专用 Canvas。
- 分享样式版本升为 `share_card_v5`，旧版本快照自动进入过期判断，不再发送旧布局。本轮未部署生产、未上传微信体验版。

# 2026-08-22 分享链路对抗式审查规则沉淀

- 本轮复盘确认：普通静态检查和后端 pytest 通过，不能证明小程序最终分享正确；必须测试 `onShareAppMessage` 的真实返回对象。
- 新增长期门禁：非名片有图时验证“原图 `imageUrl` + 资料详情 `path`”；无图时验证产品约定的无图行为；任何“无 `imageUrl` + 资料库/首页 path”都判定为 P0。
- 后续每次分享功能开发必须覆盖状态矩阵、失败反例、快速连续点击、旧 revision、未发布和非当前用户，并在交付报告中分别标记静态检查、回调测试和真机验收状态。

# 2026-08-22 修复非名片有图仍显示分享图准备中

- 根因：`isDirectSharePlan()` 之前只把“没有主图的非名片”判为直出；有主图资料仍等待已废弃的非名片 Canvas 快照，且部分发送入口没有把原图传入 `imageUrl`。
- 修复：统一插件将所有非名片标记为 `direct`，新增统一的 `getShareImageUrlFromState()`；房源、商品、服务、普通资料、图片资料的发送入口均从该状态直接返回托管原图，名片保持专用快照流程。
- 对抗式回归已通过：房源、有主图、无快照时，资料库 `onShareAppMessage()` 返回原图 `imageUrl` 和资料详情页 `path`；不会返回资料库路径或“资料分享图准备中”。
- 已执行：相关 JS `node --check`、定向 Node 回调反例测试、`git diff --check`。未修改后端，因此本轮无对应后端 pytest；未部署生产、未上传微信体验版。

# 2026-08-22 生产分享链接失效后的发送门禁与客户页提示

- 生产日志确认：资料 `note_58b97f641f` 在编辑 `PUT` 后回到 `private`，随后旧分享链接访问 `/api/notes/public/...` 得到 404；后端的发布边界行为正确，问题是前端旧列表状态仍可能把该资料当成可发送。
- 修复 `miniprogram/pages/library/index.js`：分享准备前强制以最新资料的 `shareState` 为准；最新状态不是 `published` 时清除旧直出/快照状态、撤销发送资格，并回到重新发布路径；校验进行中立即清除旧 `shareImageReady`，堵住异步校验窗口的发送竞态。
- 修复 `miniprogram/pages/note-preview/`：404/未发布链接显示“资料已停止分享，请让发布者重新发布后再发送”，网络故障才显示可重试的客户页加载失败；增加请求序列保护，避免旧请求覆盖新资料页状态。
- 对抗式回归通过：编辑后 private 卡片不可发送、校验未返回时旧 ready 立即清除、旧公开链接进入明确失效态；后端相关 3 项用例通过。
- 静态验证通过：目标 JS `node --check`、68 个小程序 JSON 解析、`git diff --check`。未部署生产、未上传微信体验版。

# 2026-08-22 客户信息链配置表生产部署

- 已将本轮 PostgreSQL 配置表改造的最小后端补丁部署到生产，仅同步 `ops_console_store.py`、`repository.py`、`dependencies.py` 和 PC 运营页 `index.html`；未覆盖生产 `.env`、secrets、媒体目录或其他本地未提交改动。
- 已备份线上原文件到 `/home/ubuntu/teamBuy/.deploy-backups/customer-info-chain-20260822191532/`；已重建 `teambuy-backend-1`、`teambuy-backend-worker-1`、`teambuy-archive-worker-1`，未重启 PostgreSQL。
- 生产接口验证通过：本机健康检查与 `https://teambuy.lifelove.top/health` 均返回 `status=ok`；运营接口从 `ops_feature_flags.customer_info_chain` 读取到 `enabled=true`、`paymentRequired=false`、`updatedBy=ops`。
- 对抗式部署复核通过：表内已有行优先、旧 JSON 不参与覆盖、数据库值与运营接口一致；生产仍未开启/修改客户信息链，只验证当前既有状态。
- 发现归档 worker 处理已有历史任务时仍有独立错误：`SkillRouterService` 缺少 `is_image_primary_import`；该错误不影响本次 API 启动、健康检查和配置表读取，已留作单独问题，不在本次范围内扩大修改。

# 2026-08-22 会员支付待支付订单复用与倒计时

- 已实现同一用户/同一会员方案在 30 分钟内复用同一笔 pending 业务订单；取消微信支付只保留订单，不创建新订单。
- 后端在读取会员状态、创建订单和发起支付时都会惰性关闭超时订单；超时旧订单不能再次发起支付，下一次支付才创建新订单。
- 会员状态接口返回 pendingOrder.expiresAt 和 pendingOrder.secondsRemaining；小程序会员页按服务端到期时间每秒倒计时，显示“订单将在倒计时结束后关闭”，支付取消会提示 30 分钟内可继续。
- 已保留支付回调的资金安全边界：经过微信验签、金额、商户和用户校验的晚到成功回调，即使本地订单刚被关闭，也会完成该笔已实际支付订单，不把已收款误判为失败。
- 对抗式验证通过：同订单复用、30 分钟后关闭并生成新订单、旧订单号支付被拒、倒计时冒烟测试；项目后端测试 250 passed。本轮未部署生产，需重新编译体验版后人工验证取消支付、返回会员页和倒计时结束三个真机路径。

# 2026-08-22 订阅消息 SOP 对抗式修复（待与支付改动合并部署）

- 修复生产公开浏览身份边界：有效 Authorization 会话由服务端推导 `viewerUserId`；无会话即使请求体伪造实名 ID 也只能记为匿名，昵称和头像不再信任请求体。
- 匿名浏览仍可进入统计/雷达，但不再消耗发布者的一次性订阅额度，阻止轮换 `anonymousId` 刷掉额度和制造虚假订阅提醒。
- 补齐额度/投递失败闭环：队列入列失败标记投递失败并释放额度；微信可重试错误达到 3 次后释放 `reserved`；`reserved` 超过 15 分钟由 worker 和业务动作回收。
- 小程序订阅入口等待后端配置；授权成功但记录接口失败时保存同一 `requestId/status` 重试；拒绝授权记录 24 小时冷却，避免反复弹窗。
- 对抗式测试新增并通过：生产身份伪造、匿名不耗额度、连续 3 次发送失败、投递入列失败可重试、过期预占回收；订阅专项 6 passed，支付专项仍需与全量回归一起复核。
- 本轮仍未部署生产；完成全量后端回归、JS/JSON/差异检查和部署前生产只读检查后，与会员支付待支付订单改动一次性部署。生产客户信息链保持当前关闭状态。

# 2026-08-22 订阅消息 SOP 与会员支付改动合并生产部署

- 按计划一次性同步订阅消息身份/额度回收修复与会员支付待支付订单复用改动；只同步后端代码文件，未覆盖生产 `.env`、secrets、媒体目录或 PostgreSQL 数据卷。
- 部署前备份目录：`/home/ubuntu/teamBuy/.deploy-backups/subscription-payment-20260822201302/`；重建 `backend` 和 `backend-worker`，未重启 PostgreSQL 与 archive-worker。
- 公网 `/health` 返回数据库已配置且 `status=ok`；backend、backend-worker 均正常启动。线上目标文件 SHA-256 与本地部署文件逐一匹配。
- 对抗式部署探针确认公开 view/events 路由已加载；不存在资料返回业务 404/参数 422，而不是路由不存在。生产配置表复核仍为 `enabled=false`、`paymentRequired=true`，本轮没有开启客户信息链。
- 小程序前端未上传体验版；订阅入口的配置等待、授权失败重试和拒绝冷却需要负责人在微信开发者工具重新编译上传后人工验证。

# 2026-08-22 归档 Worker 修复与企业微信自动回复通道复核

- 根因确认：生产 `AppService` 已调用 `SkillRouterService.is_image_primary_import`，但归档 Worker 运行时加载的 `skill_router_service.py` 仍是旧版本，导致归档消息只入库、不生成资料。
- 最小修复：只同步 `backend/app/services/skill_router_service.py` 到生产宿主机；部署前备份线上原文件到 `/tmp/teamBuy-skill_router_service.py.before-fix-20260822`，重启三个后端相关容器，未修改 `.env`、secrets、数据库和媒体目录。
- 生产复核：21:46 的 `seq=538` 已生成 `note_87f5a9f411`，不再出现 `is_image_primary_import` 缺失；Worker 还处理了 9 组历史积压。
- 自动回复复核：资料生成成功，但对该消息调用微信客服 `kf/send_msg` 返回 `95018 session status invalid`。原因是该消息来自企业微信成员好友的会话存档，不是 `wx.openCustomerServiceChat` 产生的微信客服会话；客服发送 API 不能作为成员好友私聊回发接口。
- 验证：后端全量 `255 passed`；相关 JS `node --check`、68 个小程序 JSON、`git diff --check` 通过。
- 本轮结论：归档整理已恢复；成员好友消息自动回卡片仍不成立。要验证客服自动回复，必须从微信客服入口发送一条新消息；不擅自改变当前“添加企业微信助手/绑定口令”为主入口的产品决策。
# 2026-08-23 联系我插件与一次性绑定卡片（本地实现，未部署）

- 已确认配置 ID `df29f3fd3ddc95bfec70e60cef93730c` 用于联系我插件；插件添加完成不等于绑定完成。
- 已实现企业微信添加客户事件 -> 同步欢迎小程序卡片 -> 用户点击卡片 -> 当前小程序 openid 绑定的链路，首页与资料库共用。
- 已加入短期单次 token、重复回调去重、跨用户抢占保护，并将重复失败/已处理 welcome code 视为已处理，避免重复发送和唯一索引冲突。
- 已通过相关后端测试 194 passed、Python 编译、相关 JS node --check、JSON 解析和 git diff --check。
- 本轮未部署生产；仍需外部配置欢迎卡片 media_id、企业微信事件回调 Token/AES，并由负责人重新编译上传小程序后人工验证。
# 2026-08-23 企业微信应用回调密钥同步生产

- 用户在“资料整理助手”应用详情页的“接收消息 -> 设置API接收”中配置回调；本地重新生成并保存了新的 Token/AES。
- 只读核对确认：截图中的旧 Token 与本地旧 `.env` 一致，但生产 Token/AES 不同，导致企业微信保存 URL 校验失败。
- 已备份生产 `.env` 到 `/home/ubuntu/teamBuy/.deploy-backups/wecom-callback-20260823005716/backend.env.before`，只同步 `WECOM_CALLBACK_TOKEN`、`WECOM_ENCODING_AES_KEY`，未覆盖整份配置。
- 已使用 `docker-compose.production-runtime.yml` 重建 `backend`；容器内 Token/AES 哈希与本地一致，生产 `/health` 和公网 callback 路径可访问。
- 当前待人工动作：回到企业微信回调配置页面点击“保存”；绑定欢迎卡片的 `WECOM_BIND_CARD_PIC_MEDIA_ID` 仍未配置。

# 2026-08-23 绑定欢迎卡片素材正式生命周期（本地实现，未部署）

- 根因：此前发送链路只读取 `WECOM_BIND_CARD_PIC_MEDIA_ID`，没有源图片、上传接口、过期时间和失败保留机制；临时 media_id 过期后会重新出现卡片发送失败。
- 最小实现：新增 `WecomBindCardAsset` 持久化记录；企业微信素材上传客户端；PC 后台上传/状态/立即刷新接口；发送欢迎卡片前的有效期检查和自动刷新。
- 安全边界：完整 media_id、企业凭证和源图片不进入小程序；PC 状态只返回状态、有效期、源文件名和 media_id 尾部；旧素材只有在新素材上传并入库后才退休。
- 失败策略：上传失败记录失败原因并保留当前 active 素材；刷新失败但旧素材未过期时继续使用旧素材；没有可用素材时明确返回失败，不发送不完整卡片。
- 验证：后端全量 `262 passed`；素材服务覆盖上传持久化、过期刷新、替换失败保留旧素材；PC 管理页脚本 `node --check`、JSON 解析、`git diff --check` 通过。
- 待人工/部署：上传一张绑定封面图到 PC 后台；部署后在生产 PC 后台确认状态为“自动刷新已启用”，再测试“添加企业微信 -> 收到卡片 -> 点击绑定”。本轮未部署生产，也未上传小程序体验版。

# 2026-08-23 企业微信绑定卡片正式方案部署生产

- 已按最小范围同步绑定卡片服务、企业微信上传客户端、运营后台路由、PC 静态页面及其依赖文件；生产 `.env`、`secrets`、数据库卷和媒体卷未覆盖。
- 生产原文件已备份到 `/home/ubuntu/teamBuy/.deploy-backups/wecom-bind-card-pc-20260823-014025`。
- API、普通 worker、归档 worker 已重启；`wecom_bind_card_assets` 通过现有 `init_schema()` 自动创建，未执行删除或数据迁移。
- 生产 `/health` 返回正常，公网 `/ops` 已包含“企业微信绑定卡片”，生产 `WECOM_USE_MOCK=false`。
- 待人工验收：进入生产 PC 后台上传 PNG/JPEG/WebP 封面，再用新客户测试“添加企业微信 -> 自动收到卡片 -> 点击绑定”。

# 2026-08-23 小程序主包超限分包优化

- 根因：小程序把 58 个页面全部放在主包，源代码资源约 2.47MB；图片资源不是主要超限来源。
- 最小修改：新增 `miniprogram/subpackages/workbench`，迁移编辑器、发布器、展示页编辑和经营看板共 15 个页面；首页、四个 Tab、公开详情/分享页继续留在主包，避免历史分享路径失效。
- 所有内部跳转和编辑器映射已改为 `/subpackages/workbench/...`，分包页面对主包公共组件和服务的相对引用已调整。
- 结果：主包静态体积估算约 1.25MiB，工作台分包约 719KiB；不是删除功能，也没有压缩或替换业务图片。
- 验证：87 个 JS `node --check` 通过、69 个 JSON 解析通过、58 个配置页面路径存在、旧编辑器路径无残留、`git diff --check` 通过。
- 待人工动作：微信开发者工具重新编译，确认主包低于 1.8MB 后上传体验版；重点回归新建资料、房源/商品/名片编辑、展示页编辑、经营看板和历史分享页。

# 2026-08-23 小程序失效会话恢复与游客访问修复（本地，待体验版上传）

- 现象判断：删除小程序后恢复，最符合本地 `currentUser` 中旧/失效登录态触发受保护接口 401；没有证据表明生产后端或缓存发生跨用户冲突。
- 最小修复：`app.js` 清理失效用户、资料列表/合集/专题缓存和客户雷达内存缓存；`request.js` 区分认证失效、未登录、网络失败、403 和 5xx；带有效旧 token 的 401 只触发一次登录恢复，登录页保留原目标路径。
- 游客规则：启动和首页不强制登录；无登录态时继续浏览公开首页/公开内容，只有记录笔记、保存、发布、工作台等受保护动作才进入登录门槛。无 token 的 401 只清理脏会话，不跳转登录。
- 并发保护：清理用户缓存时递增列表缓存代次，旧的 topics/showcases 请求不能在新会话中回写缓存，旧请求也不能删除新请求的 in-flight 记录。
- 验证：相关 JS `node --check`、小程序 JSON 解析、`git diff --check` 通过；后端 `backend/tests` 为 `262 passed`；请求层游客/失效 token/网络超时反例通过。
- 本轮未修改后端、未部署生产、未上传微信体验版；待负责人在微信开发者工具重新编译上传并人工验证游客浏览、登录恢复和重新登录后的个人数据隔离。

# 2026-08-23 客户留言订阅消息与会话深链（本地，未部署）

- 复用现有订阅消息模板和一次性额度，不新增模板；仅客户/买家向资料发布者发送留言时入队通知，发布者回复不触发通知。
- 留言通知按同一会话 30 分钟去重；当普通浏览通知仍在排队时，只释放一条排队浏览通知的额度给留言通知，其他浏览通知保留。已经发送或正在发送的微信通知无法被平台额度回收。
- 订阅消息点击进入 `/pages/message-thread/index?id=...`；会话页只对发布者显示“查看客户雷达”。进入雷达时只携带受权限保护的 `threadId`，雷达页先读取并校验会话归属，再加载客户信息，避免把客户身份或联系方式拼进 URL。
- 模板留言预览会脱敏手机号、邮箱和微信号；完整留言仍只在有权限的会话内查看。访客浏览、未授权和无订阅额度不会被强制登录或伪造为已发送通知。
- 对抗式回归覆盖：客户留言入队、发布者回复不通知、同时间窗去重、普通浏览额度让位、入队失败回滚、跨用户会话 403、敏感内容不进入模板；订阅专项 10 passed，后端全量 266 passed，相关 JS、69 个 JSON、Python 编译和 `git diff --check` 通过。
- 本轮未部署生产、未上传微信体验版；负责人需在微信开发者工具重新编译上传后，人工验证订阅授权、通知点击、会话留言、客户雷达会员门禁和失效登录回跳。

# 2026-08-23 分享卡片客户侧“客户页加载失败”根因调查（未改代码）

- 页面文案来源已确认：不是客户雷达页，而是 `miniprogram/pages/note-preview/index.js` 捕获公开资料请求异常后显示的通用标题。
- 公开分享链路为：分享路径 `/pages/note-preview/index?id=...` -> `api.fetchPublicNote()` -> `GET /api/notes/public/{noteId}`。`note-preview` 保留在主包，旧分享路径未迁移。
- 生产验证：无 Authorization 访问已发布资料返回 200；带伪造/失效 Bearer token 访问同一公开接口返回 401。当前 `miniprogram/utils/request.js` 会给所有请求附带本地 `currentUser.authToken`，这是可复现的失败链路：客户手机残留失效会话 -> 公开资料请求被生产鉴权中间件拦截 -> 前端显示“客户页加载失败”。
- 16:28 服务器访问日志未出现客户侧 `/api/notes/public/{noteId}` 请求，只有微信开发者工具访问发布者自己的接口；因此该次具体点击还存在“客户侧请求在发出前失败/客户使用旧版本或网络未到达”的不确定性，但公开接口、发布状态和生产数据未显示跨用户缓存冲突。
- 本轮未修改代码、未部署后端；建议最小修复先让公开资料 GET 不携带失效 token，并保留客户动作/浏览上报的登录鉴权；随后用有旧 token、无 token、有效 token、已撤回资料和旧分享链接分别验收。

# 2026-08-23 客户留言订阅后端最小范围部署

- 生产只同步本功能所需的 `backend/app/api/routes_messages.py`、`backend/app/models/domain.py`、`backend/app/services/app_service.py`；未同步本地其他企业微信绑定、支付、资料编辑或小程序改动。
- 部署前备份：`/home/ubuntu/teamBuy/.deploy-backups/message-subscription-20260823130659/`；未修改生产 `.env`、secrets、PostgreSQL 数据卷和媒体卷。
- 使用生产 `docker-compose.production-runtime.yml` 重建 `backend`、`backend-worker`、`archive-worker`；由于生产 `.env` 权限为 root-only，使用现有 sudo 提权方式完成重建。
- 验证通过：3 个容器运行，容器内代码加载确认，内网/公网 `/health` 返回 `status=ok` 且 PostgreSQL 正常；未登录访问消息路由返回 401，生产鉴权仍生效。
- 小程序前端仍未上传体验版；负责人下一步在微信开发者工具重新编译上传，再做真实订阅授权、客户留言、通知点击、会话和客户雷达人工验收。

# 2026-08-23 订阅消息模板字段映射修复并重启生产

- 17:45–17:48 生产日志确认分享页浏览和客户留言均成功到达后端，worker 也调用了微信发送接口；两条投递均被微信以 `47003` 拒绝，原因是 `data.thing13.value` 为空。
- 通过线上模板列表接口确认“未读消息提醒”实际字段：`thing13` 消息名称、`thing16` 客户名称、`thing14` 项目名称、`thing3` 消息内容、`time11` 提醒时间。生产旧配置错用了 `thing1/thing2/thing3/thing4/time5`。
- 已备份并修改生产 `/home/ubuntu/teamBuy/backend/.env`，重建 `backend` 与 `backend-worker`；容器内确认新配置已加载，公网 `/health` 通过。
- 已同步 `backend/.env.example`、`backend/app/core/config.py` 默认配置和订阅测试断言，避免环境变量缺失或测试默认值再次回退到旧字段。
- 对抗式结论：匿名打开分享卡片仍按设计不发送通知；旧失败投递不会因重启自动重试；修复后的验收必须由已授权、已登录客户产生新的浏览或留言事件，并检查微信 JSON `errcode=0` 与数据库 `status=sent`。

# 2026-08-23 小程序登录初始化时序补丁（本地，待体验版上传）

- 现象：生产前端在 16:15 左右点击微信登录提示 `undefined is not an object (evaluating 'a.globalData')`；页面能打开，删除小程序后暂时恢复，说明不是后端登录接口本身报错。
- 根因：`miniprogram/utils/request.js` 在模块顶层执行 `getApp()`，登录页加载 `services/api` 时可能早于小程序 `App()` 初始化，导致请求层在真正发起微信登录前访问不存在的 `globalData`。
- 最小修复：请求层改为调用时惰性读取 App；App 尚未完成初始化或 API 地址不可用时返回可重试的 `app_init` 错误，不调用 `wx.request`。登录页的 onLoad、微信登录、保存登录用户和 returnUrl 解码均增加安全保护。
- 业务边界：游客仍可浏览首页和公开内容，不会因启动保护被强制登录；带 token 的 401 仍清理失效会话并恢复登录，无 token 的 401 只清理脏状态、不跳转登录。
- 对抗式验证：全量小程序 JS `node --check`、69 个 JSON 解析、`git diff --check` 通过；Node 模拟 App 未初始化、正常游客请求、游客 401、登录用户 401、`getApp()` 抛错均通过。后端未修改、未重新部署。
- 待人工动作：微信开发者工具重新编译并清理编译缓存后，冷启动点击微信登录、选择“暂不登录”、失效 token 恢复和登录后回到原目标页；确认无误后再上传体验版。

# 2026-08-23 留言登录回跳、头像上传与浏览历史（本地，待小程序上传）

- 根因：公开资料页的留言入口未登录时只显示提示，没有保存原资料路径；头像选择没有在登录页形成“选择临时头像 -> 登录后上传 -> 保存 HTTPS 地址”的完整闭环；浏览记录不应依赖会被删除小程序清掉的本地缓存。
- 最小实现：留言入口通过 `returnUrl` 带回资料页、分享上下文和 `action=message`，登录成功后回到原资料并自动打开消息会话；登录页和个人资料页使用微信 `chooseAvatar` 与 `type="nickname"`，头像上传失败不会清空旧头像；新增前端 `/static/images/avatar-default.png` 作为未设置头像的展示兜底。
- 浏览历史使用现有 `view_events`，新增前端 `/api/view-history`；只返回仍公开的标题、封面和查看时间，服务端过滤自己的资料、私密/撤回/删除资料，不返回手机号、微信号、客户身份或雷达信息。
- 对抗式修正：撤回资料不会再回退到旧关联卡片；生产模式下历史接口由 Authorization 和 `userId` 双重约束；游客仍可浏览，只有主动留言才进入登录门槛。
- 验证：相关后端 `185 passed`（`test_app.py` 与 PostgreSQL schema 测试）；全量小程序 JS `node --check`、69 个 JSON 解析、`git diff --check` 通过。
- 本轮未部署后端、未修改生产客户信息链或支付开关、未上传微信体验版；负责人需在微信开发者工具重新编译上传后人工验收登录回跳、iOS/Android 头像、跨设备历史和公开资料撤回边界。

# 2026-08-23 最近看过改为单条预览与独立列表（本地，待小程序上传）

- 产品调整：我的页面不再直接铺开多条浏览记录，只展示最新 1 条；存在更多记录时显示“查看全部浏览记录”。
- 新增主包页面 `miniprogram/pages/view-history/index`，复用现有 `/api/view-history`，读取后端允许的公开记录，点击后按 note/card 类型回到对应公开页面。
- 游客访问独立历史页不会被强制登录；未登录时只显示可选登录入口。浏览记录请求失败与“没有记录”在我的页面和独立页均分开处理。
- 未改后端数据结构、客户信息链、会员支付或生产配置；默认头像仍只是列表展示兜底，不写入用户头像字段。
- 验证：全量小程序 JS `node --check`、70 个 JSON 解析、后端 `tests/test_app.py tests/test_postgres_repository_schema.py` 共 `185 passed`、`git diff --check` 通过。
- 本轮未部署后端、未上传微信体验版；需在微信开发者工具重新编译后人工验收我的页面高度、最新 1 条、查看全部、下架资料过滤和游客路径。

# 2026-08-23 小程序主包头像资源压缩（本地，待体验版上传）

- 生产上传错误明确为主包超限：微信报告 `main package source size 3089KB exceed max limit 2048KB`，不是网络请求故障。
- 根因：`miniprogram/static/images/avatar-default.png` 原始尺寸为 1254×1254，单文件约 1.5MB；它只是展示层默认头像，不需要保留原始分辨率。
- 最小修复：保持原文件名和所有引用路径不变，将其压缩为 256×256 PNG，文件大小降至 75.7KB；没有迁移业务页面，没有修改 `app.json` 路由和公开分享路径。
- 当前按项目文件精确字节估算的主包源码约 1851.1KB，低于微信 2048KB 上限，保留约 196.9KB 余量。
- 验证：默认头像可正常读取；59 个配置页面的 JS/JSON/WXML/WXSS 文件均存在；全量 JS `node --check`、70 个 JSON、后端 `185 passed`、`git diff --check` 和主包估算检查通过。
- 本轮未部署后端；需在微信开发者工具重新编译并重新上传体验版，再确认工具显示的主包大小低于 2MB。

# 2026-08-23 最近看过空状态文案修正（本地，待体验版上传）

- 将“我的”页真正空记录状态从“你浏览过的公开资料会显示在这里”改为“暂时没有最近的记录”。
- 保留网络/API 失败状态“最近看过暂时无法读取，点击重试”，避免把接口失败误报成没有记录。
- 验证：相关 JS `node --check`、页面 JSON 解析、浏览历史专项后端 `2 passed`、`git diff --check` 通过；本轮未改后端、未部署生产。

# 2026-08-23 生产浏览记录接口未部署（只读核查）

- 真机仍显示失败文案后，生产 `/health` 返回 200，但已登录用户请求 `/api/view-history?userId=user_5fd8d56c26&limit=30` 在 20:14–20:24 多次返回 404。
- 生产容器和服务器代码目录均未找到 `view-history` 路由；无 Token 探针返回 401，说明生产鉴权正常，404 是后端版本缺少接口，不是缓存或前端空数据。
- 本地已有实现位于 `backend/app/api/routes_cards.py`、`backend/app/services/app_service.py`、`backend/app/services/repository.py`，但尚未部署生产。
- 当前未部署；真正修复只需备份后同步这三个后端文件并重建 backend，随后验证带有效会话的接口返回 200。不要用前端把 404 转成空数组。

# 2026-08-23 浏览记录接口最小生产部署

- 已按用户明确要求部署浏览记录后端补丁；部署前备份：`/home/ubuntu/teamBuy/.deploy-backups/view-history-20260823203926/`。
- 只修改生产 `backend/app/api/routes_cards.py`、`backend/app/services/app_service.py`、`backend/app/services/repository.py`；没有同步本地脏工作区，没有修改生产 `.env`、secrets、客户信息链、支付开关、PostgreSQL 数据或媒体卷。
- 生产运行时通过 `./backend:/app:ro` 挂载源码，因此采用目标文件补丁并仅重启 `teambuy-backend-1`；没有重启归档 worker，也没有重建数据库或执行清理命令。
- 中途一次无上下文补丁在远端 dry-run 后暴露出插入位置风险，未重启线上服务；已用线上备份恢复 3 个文件，改用带上下文补丁重新部署。最终选定文件差异仅包含新增浏览记录路由、按 viewer 查询和服务层公开状态过滤。
- 验证通过：容器内三个目标文件源码编译、`/api/view-history` 路由导入、`viewer_user_id/card_id/viewed_at` 数据库字段存在、服务层不存在用户返回空数组；后端重启后公网 `/health=200`，无凭证和伪造 Bearer 访问浏览记录均为 `401`，不再是原来的 `404`。
- 对抗式检查：历史查询按 `viewer_user_id` 过滤；生产路由同时校验认证用户与 `userId`；自己的资料、私密/撤回/删除资料不会进入结果；输出不包含手机号、微信号或客户雷达字段；撤回资料不会回退到旧关联卡片。
- 尚未用真实用户会话直接验证“有记录返回 200”，因为当前没有从客户端取用用户认证令牌；需要负责人重新打开小程序后人工确认“最近看过”能显示最新记录，以及空记录显示“暂时没有最近的记录”。

# 2026-08-23 企业客户服务插件升级到 1.4.8（本地，待上传）

- 通过微信开发者工具插件详情确认 `wx104a1a20c3f81ec2` 的最新版本为 `1.4.8`，更新日志为“鸿蒙系统适配”；项目原配置仍为 `1.4.3`。
- 已将 `miniprogram/app.json` 中 `contactPlugin.version` 从 `1.4.3` 更新为 `1.4.8`，provider、组件路径和企业微信配置 ID 均未修改。
- 验证通过：首页/资料页 JS `node --check`、相关 JSON 解析、插件 provider/version 断言、`git diff --check`。
- 本轮只改前端插件版本配置，未部署后端、未修改企业微信绑定卡片链、客户信息链或支付开关；需负责人在微信开发者工具重新编译、上传体验版并验收首页和资料页联系我按钮。

# 2026-08-23 首页今日雷达与待跟进视觉区分（本地，待体验版上传）

- 首页 banner 雷达三圈改为今日口径：外围显示今日已分享，中圈显示今日打开访客，内圈显示今日待跟进；数据复用客户信息链已有 `todaySummary`，没有新增接口或改变累计统计。
- 对 `backend/app/services/app_service.py` 做最小统计补齐：资料预览直接分享产生的 `viewType=share` 纳入今日/累计分享数，同时不再把分享动作算成打开访客；资料级今日打开和访客明细同步排除分享动作。
- 首页雷达不再显示高意向、复活等混合指标，避免把历史/当前状态和今日行为混在同一张图里；首页待处理文案同步改为“当前有”，不再把当前待办误称为今日新增。
- 客户雷达“待跟进”页的队列卡片增加浅绿色背景和“待跟进”标识；高意向待跟进保留浅黄色强调，访客页和资料优化页不套用该背景。
- 开始请求客户数据时先清空上一次页面实例的首页雷达数字，避免切换用户或刷新期间短暂展示上一位用户的客户信号。
- 验证：相关 JS `node --check`、70 个 JSON 解析、`git diff --check`、客户信息链后端专项 `2 passed`；本轮未部署后端、未上传微信体验版。

# 2026-08-23 首页今日雷达统计补丁生产部署

- 用户已明确要求部署；只部署生产 `backend/app/services/app_service.py` 的最小统计补丁，没有同步本地脏工作区。
- 生产补丁将资料预览 `viewType=share` 纳入累计/今日分享数，并从累计/今日打开访客及资料级今日明细中排除，避免一次分享被同时统计为分享和打开。
- 部署前检查生产根盘可用约 33G（43% 使用率），`teambuy-backend-1` 使用 `/home/ubuntu/teamBuy/backend:/app:ro` 挂载；目标文件已备份到 `/home/ubuntu/teamBuy/.deploy-backups/radar-share-20260823224129/`。
- 仅重启 `teambuy-backend-1`，没有修改 `.env`、secrets、数据库数据、媒体卷、客户信息链开关、会员支付开关或 worker。
- 验证：远端 `py_compile` 通过，容器重启后 `/health` 和公网 `https://teambuy.lifelove.top/health` 均返回 200，数据库状态正常；重启窗口首次探活的连接重置后复核通过。

# 2026-08-23 首页漏斗时间筛选补齐（前端本地完成，后端已部署，待前端上传）

- 后端 `rangeSummaries` 已以最小补丁部署生产，备份位于 `/home/ubuntu/teamBuy/.deploy-backups/radar-range-20260823231400/`；只重启 API，未同步本地脏工作区或修改生产配置、数据、客户信息链、会员支付和 worker。

- 本轮按参考图收紧首页反馈区：删除“查看反馈”，保留“发出去以后”标题和副标题，将“今日 / 近7日 / 累计”做成紧凑分段控件，说明文案缩短，三列统计卡高度和间距同步收紧。

- 根据最新参考图进一步调整为左右同排：标题改为“客户反馈”，左侧放说明，右侧放三个周期；下方显示动态“今日数据 / 近7日数据 / 累计数据”，卡片文案改为“已分享 / 打开访客 / 待跟进”。


- 发现此前只实现了首页雷达三圈的“今日”显示，`overviewRange` 虽存在但页面没有渲染筛选控件，后端也没有近 7 日汇总字段。
- 最小实现：在“发出去以后”区块增加“今日 / 近7日 / 累计”，默认“累计”；首页雷达三圈继续固定今日，不受漏斗筛选影响。
- 后端客户信息链新增 `rangeSummaries.today/last7/total`，近 7 日按上海时区自然日包含今天共 7 天；分享、打开访客、咨询动作和仍待处理线索按同一时间窗口统计。
- 跟进口径明确为“该时间段产生、目前仍待处理的线索”，不会因为切换筛选或点击页面而清零；历史累计仍保留。
- 防错：后端未返回 `last7` 字段时，前端不显示筛选控件，避免把累计数冒充近 7 日；切换筛选只更新漏斗数字，不改变首页主行动卡。
- 验证：相关 JS `node --check`、70 个 JSON 解析、`git diff --check`、客户看板专项 `2 passed`；后端已部署，前端仍未由 Codex 上传微信体验版。

# 2026-08-23 接手核验：首页漏斗与雷达 UI 保持现状

- 复核首页三文件：默认累计；三组 `today/last7/total` 齐全才显示筛选；反馈区标题/说明与周期控件同排；三列卡片横排；待跟进使用浅绿色；雷达三圈固定今日口径。
- 对抗式检查覆盖缓存缺组、用户切换异步回写、会员锁定/联系方式边界、漏斗切换污染今日雷达；未发现需要修改的明确问题。
- 本轮没有修改业务代码、没有部署生产、没有上传微信体验版。验证：全量小程序 88 个 JS `node --check`、70 个 JSON 解析、`git diff --check`；`.venv312` 下定向 pytest `15 passed`。
- 剩余事项由负责人在微信开发者工具重新编译上传体验版后人工验收首页布局、周期数字、雷达今日口径、切换账号隔离和真实登录态接口。

# 2026-08-24 客户信息免支付/收费门禁与错误态收口（本地，待体验版上传）

- 新增 `miniprogram/utils/customer-access.js`，统一区分 `disabled`、`payment_required`、`allowed` 和空响应 `unknown`；不再把 `membership.active` 单独当作客户信息访问条件。
- 免支付模式（客户信息链开启且 `paymentRequired=false`）直接放行雷达、客户详情、客户资料库、线索详情和工作台客户数据；收费模式下非会员统一进入 `/pages/membership/index`。
- 雷达移除“发现客户信号 / 知道了”无行动弹窗；收费锁定状态提供“去支付”，免支付状态不显示支付提示。客户详情将功能关闭、会员门禁、记录已刷新、真实接口失败拆成不同标题和按钮。
- 收费非会员进入雷达前清理当前用户/模式的客户情报缓存；缓存清理提升代次，阻止旧 in-flight 解锁响应回写。
- 本轮未修改后端、客户信息链开关、会员支付开关、生产配置或生产数据；未部署生产，未上传微信体验版。
- 验证通过：相关 JS `node --check`、客户访问状态与缓存竞态 smoke test、70 个 JSON 解析、`git diff --check`、客户信息链/销售 SCRM pytest `15 passed`。
- 对抗式审查覆盖免支付直达、收费支付跳转、空会员响应 fail-closed、关闭功能、旧记录、网络异常、缓存权限切换；未发现新的明确 P0。
- 待负责人在微信开发者工具人工验收免支付账号直达详情、收费非会员支付、支付成功后恢复、功能关闭中性空态和跨账号联系方式隔离。

# 2026-08-24 客户信息链状态复核与雷达详情匹配修正（本地，待体验版上传）

- 根据真机截图确认两个前端问题：雷达页停留期间运营开关变化后，旧支付门禁仍可把用户带到功能关闭的会员页；详情页只查画像数组，雷达告警卡来源不一致时误显示“这条客户信号已更新”。
- 支付入口在跳转前重新读取会员/功能状态：功能关闭回到中性态，免支付模式刷新雷达直接放行，收费非会员才进入 `/pages/membership/index`。
- 客户详情统一在 `radarProfiles`、`visitorProfiles`、`opportunityAlerts` 三类服务端数据中按客户身份别名匹配；会员状态判断仍先于客户情报读取，未扩大联系方式权限。
- 本轮未修改后端、运营开关、支付实现、生产配置或客户数据；未部署生产，未上传微信体验版。
- 验证通过：全量小程序 JS `node --check`、87 个 JSON 解析、`git diff --check`、客户信息链/销售 SCRM pytest `15 passed`。
- 待负责人在微信开发者工具重新编译上传后，按“功能开+支付开”“功能开+支付关”“功能关”三组状态人工复测；仅打开支付而未打开客户信息链时，后端仍会按功能关闭处理。

# 2026-08-24 客户信息链门禁文案去支付化（本地，待体验版上传）

- 删除功能关闭态“会员支付入口”、免支付态“关闭会员支付”和雷达锁定态“需要先完成会员支付/去支付”等用户可见文案。
- 非会员仍由状态门禁直接跳转会员开通页；真正开通页中的订单和交易流程文案保留，不改变支付能力。
- 验证重点：客户信息链相关中性/锁定状态不出现支付字眼；收费非会员点击查看仍直接进入会员页；免支付模式直接查看详情。

# 2026-08-24 客户详情身份键兼容修正（本地，待体验版上传）

- 真机仍显示“这条客户信号已更新”后，确认详情页进入的是“接口已解锁但目标身份未匹配”保护分支，不是会员门禁或功能关闭。
- 详情匹配现在同时归一化 `user:xxx`/`xxx`、`anon:xxx`/`xxx` 两种身份键，并把 `customerTimelines` 作为候选来源，兼容旧/新雷达投影。
- 未找到真实记录时仍保留安全错误态，不根据 URL 参数伪造客户资料；后端联系方式权限和按 owner 鉴权未改变。
- 验证：详情身份别名 smoke test、相关 JS `node --check`、客户信息链/销售 SCRM pytest `15 passed`；待完成全量 JSON 和 `git diff --check`。

# 2026-08-24 客户资料门禁简化与详情强制刷新（本地，待体验版上传）

- 按最终业务规则收敛前端门禁：支付开启且非会员才跳 `/pages/membership/index`；支付开启且已是会员、支付关闭且无论会员状态，均直接读取客户信息。
- 移除客户雷达、客户列表、线索列表、线索详情和客户详情对 `featureEnabled` 的前端分支；保留会员响应缺失时的 fail-closed 重试态和后端 owner/联系方式权限校验。
- 客户详情不再优先复用客户情报缓存，首次进入直接读取当前接口结果；移除“这条客户信号已更新”误导性错误文案，真正找不到记录统一显示可重试态。
- 本轮未修改后端、客户信息链开关、会员支付开关、生产配置或生产数据；未部署生产，未上传微信体验版。
- 验证：全量小程序 JS `node --check`、87 个 JSON 解析、`git diff --check`、客户信息链/销售 SCRM pytest `15 passed`；支付门禁四种组合 smoke test 通过。

# 2026-08-24 客户雷达匿名身份与定向详情修复（本地，待体验版上传）

- 根因确认：旧雷达在匿名标识缺失时使用事件 ID 做临时客户 ID，详情又从聚合画像反查，导致同一客户卡可能出现“客户详情不存在”。
- 新增 owner-scoped `visitorIdentityId`：匿名浏览使用 owner + 客户端匿名 ID 的不可逆摘要；旧事件无匿名 ID 时使用持久化事件 ID，避免错误合并访客。
- 雷达告警、画像、时间线和客户详情统一使用该身份；详情接口先执行原有 owner/会员门禁，再按原始浏览事件、展示页事件、客户动作和跟进线索定向解析，不根据 URL 伪造客户资料。
- 统一联系方式：已授权的登录用户电话/微信/销售资料邮箱，以及客户动作/跟进线索中的电话、微信、邮箱进入详情；跨 owner 请求仍拒绝，锁定响应不返回联系方式。
- 小程序公开资料、展示页和卡片浏览共用本地匿名 ID，兼容旧匿名 key；未改变客户信息链开关、支付开关、生产配置或生产数据。
- 验证：相关 JS `node --check`、相关 JSON 解析、`git diff --check`；`.venv312` 下 `test_app.py`、销售 SCRM 和客户信息链专项共 `199 passed`。本轮未部署后端、未上传微信体验版。

# 2026-08-24 客户详情后端生产部署

- 按用户明确授权，将稳定访客身份、定向客户详情和联系方式汇总的最小后端补丁部署到生产；仅更新 `backend/app/services/app_service.py`、`backend/app/models/domain.py`、`backend/app/schemas/cards.py`，未同步本地脏工作区。
- 生产备份：`/home/ubuntu/teamBuy/.deploy-backups/customer-identity-20260824033921/`；二次兼容补丁备份：`/home/ubuntu/teamBuy/.deploy-backups/customer-detail-encoding-20260824034241/`。未修改 `.env`、secrets、数据库数据、媒体目录、客户信息链开关、会员支付开关或 worker。
- 发现并修复旧前端详情参数重复 URL 编码（`%253A`）导致身份匹配失败的问题；详情接口在既有 owner/会员门禁之后仅归一化残留编码层，不改变授权边界。
- 验证：本地相关 pytest `199 passed`、全量小程序 JS `node --check`、70 个 JSON、后端 AST、`git diff --check`；容器导入和部署标记通过，生产 `/health` 和公网 `/health` 正常，生产容器无最近严重错误日志。
- 前端仍需负责人在微信开发者工具清缓存、重新编译并上传体验版；本轮没有上传小程序。

# 2026-08-24 待跟进客户建档与联系方式区域（本地，待后端部署/体验版上传）

- 新增 `POST /api/scrm/customer-followups/ensure`：服务端按 owner-scoped `visitorIdentityId` 幂等创建或复用跟进档案；前端“开始跟进”成功后进入已有线索详情页，不再要求客户先从资料页建立档案。
- 修复展示页事件没有 `noteId` 时的详情断链：客户详情会从已匹配的展示页条目回溯 owner 自有资料，保证来源资料、跟进建档和详情页面使用同一条数据链。
- 客户详情联系方式区域统一显示已授权的电话、微信号、邮箱；电话支持拨打/复制，微信号和邮箱支持逐项复制；联系方式仅存在于当前页面内存，不写入小程序持久化缓存。
- 详情页去掉重复会员预检，改为一次服务端详情请求；服务端返回收费门禁时才跳会员页，免支付或已开通直接展示，减少一次无效网络请求。
- 客户情报缓存继续使用环境 + owner + mode 隔离、短 TTL、in-flight 合并；建立/复用跟进档案后只失效当前 owner/mode，防止旧待跟进计数回写。
- 验证：全量小程序 JS `node --check`、JSON 解析、后端编译、`git diff --check`；`test_sales_scrm.py` 与客户信息链专项 `17 passed`，`test_app.py` `182 passed`。本轮未部署生产后端、未上传微信体验版。

# 2026-08-24 缓存策略收敛与雷达重复请求削减（本地，待部署/体验版上传）

- 前端资料/合集/资源列表 TTL 调整为 30 分钟，专题/分类为 2 小时，客户情报为 10 分钟；会员状态和提醒配置使用 5 分钟用户隔离内存缓存，并合并 in-flight 请求。
- `miniprogram/pages/visits/index.js` 不再每次返回都向服务端重复读取会员状态；雷达使用缓存门禁，缓存过期或显式重试才访问网络，最终客户情报响应仍复核服务端返回的支付状态。
- `miniprogram/services/api.js` 的资料列表改为真正缓存命中；资料写入/发布/撤销/复制/整理/生成/类型确认/专题变更会主动失效，支付确认轮询强制刷新会员状态。
- 后端列表缓存改为 30 分钟、客户情报缓存改为 10 分钟；普通浏览/分享不再清空整份客户情报或卡片列表缓存，高价值联系方式动作仍立即失效情报缓存。
- 对抗式审查覆盖账号隔离、会员过期/支付成功、被动事件高频失效和资料写入旧缓存回显；发现并修正支付轮询误用会员缓存、被动浏览清空列表缓存、订阅配置重复请求三个风险。
- 验证：相关 JS `node --check`、全量小程序 JSON 解析、`git diff --check`、SCRM/客户信息链 pytest `17 passed`。本地后端编译通过。

# 2026-08-24 缓存后端定向生产部署

- 按用户明确授权，仅将生产 `backend/app/services/app_service.py` 的缓存 TTL、被动事件失效范围和高价值联系方式事件失效规则上线；未同步本地其他脏改动，未修改客户信息链开关、会员支付开关、`.env`、secrets、数据库或媒体数据。
- 生产缓存口径：资料/卡片/合集列表 30 分钟，客户情报 10 分钟；普通浏览、分享和附件查看不再清空全量列表或情报缓存，资料写入和高价值客户动作仍主动失效。
- 生产备份：`/home/ubuntu/teamBuy/.deploy-backups/cache-policy-20260824053318/app_service.py.before`。API、后台任务和归档任务已重启，数据库未重启。
- 验证：生产文件差异核验仅包含预期缓存改动；生产 `py_compile`、本地定向 pytest `17 passed`、本地 `git diff --check`、生产本机 `/health` 与公网 `/health` 均通过。
- 前端仍未上传体验版，下一步由负责人在微信开发者工具清缓存、重新编译并上传后人工验收冷启动、页面返回、缓存命中、资料更新立即刷新、支付门禁和切换账号隔离。

# 2026-08-24 开始跟进接口缺失修复并部署

- 根因：生产 `routes_scrm.py` 和 `schemas/scrm.py` 仍是旧版本，`POST /api/scrm/customer-followups/ensure` 未注册；5:37 左右生产日志连续记录该接口 404。生产已有客户详情及稳定身份代码，但缺少建档方法。
- 仅部署三个最小片段：`app_service.py` 补幂等建档方法，`routes_scrm.py` 注册接口，`schemas/scrm.py` 补请求模型；未覆盖其他客户链、支付、配置或数据改动。
- 生产备份：`/home/ubuntu/teamBuy/.deploy-backups/customer-followup-20260824054119/`。API、后台任务、归档任务已重启，数据库未重启。
- 对抗式检查：未登录公网请求由 404 变为 401；本地锁定、跨 owner、重复复用、匿名稳定身份专项测试通过；本地 pytest `17 passed`，公网 `/health` 正常。

# 2026-08-24 客户详情合并跟进与旧线索页下线

- 客户详情页现在承载客户联系方式、客户资料、跟进记录、下次跟进时间和最近跟进日志；不再跳转独立的旧线索详情页。
- 已删除 `miniprogram/pages/lead-detail/` 四个页面文件，并从 `app.json`、导航标题及业务入口清理旧路由引用。
- 资料卡和合集卡片的“三个点”新增“线索详情”，进入带资源来源过滤的客户雷达；点击具体客户后统一进入客户详情页。合集原有“资料运营”入口保留。
- 资料来源过滤写入当前用户 owner 标识并在读取时校验，避免切换账号误打开上一用户的客户来源；客户详情在 owner 变化时清空旧状态并重新加载。
- 对抗式审查补正了微信 `showActionSheet` 最多六项限制，以及优先处理列表在筛选后找不到客户的问题。
- 本地前端尚未上传体验版，生产后端本轮未变更。

# 2026-08-24 后端部署核对与安全清理边界

- 按负责人要求核对生产后端；运行中的 `teambuy-backend-1` 已包含客户详情、客户跟进建档、跟进保存、客户情报缓存和 SCRM 路由，相关源码哈希与生产主机一致，公网接口未登录返回 401，`/health` 返回 200。
- 本次没有重建或覆盖生产后端：本地 `app_service.py` 虽有其他未提交差异，但当前功能所需方法与生产一致，整文件部署会带入无关模块风险。
- 已确认旧 `lead-detail` 运行时目录和路由引用均不存在。没有执行 `git clean`；预览结果显示其会删除当前客户详情、会员、缓存、分包和 SCRM 测试等未跟踪内容，不能视为无关内容。

# 2026-08-24 资料运营页补齐并移除旧线索详情入口

- 新增 `miniprogram/subpackages/workbench/resource-analytics/` 资料级运营页，读取资料卡统计和资料客户动作，展示发送、打开、访客、客户动作、联系方式状态和最近动作，并可直接进入统一客户详情。
- 资料卡“三个点”改为“资料运营”，合集卡片保留“资料运营”；资料反馈提示和资料详情/待联系入口均改到运营页，不再跳客户雷达。
- 删除 `miniprogram/pages/manager/` 旧资源级“线索详情”页面，移除 app 路由和导航标题注册；客户动作按钮统一称为“客户详情”。
- 补齐 `getCustomerAccessState` 导出，修复合集运营页和客户动作页引用不存在函数导致的运行时错误；访问状态仍按功能关闭、会员门禁和服务端结果处理。
- 本轮没有新增后端接口，复用现有资料卡、资料客户动作和会员状态接口；客户联系方式不写入小程序持久化缓存。

# 2026-08-24 合集分享入口与头像选择修正（本地，待体验版上传）

- 合集卡片操作顺序与资料卡统一为“三个点”在上、“发客户/继续编辑/重新发布”在下；没有改动分享快照必须就绪后才能触发原生分享的门禁。
- 合集分享准备状态不再向用户暴露“准备封面”“重试封面”等实现文案，改为“准备发送”“正在准备”“重新准备”；未准备完成时按钮保持普通准备动作，准备成功后才变为“发客户”。
- 登录页和“我的 → 编辑个人资料”的头像主入口改为仅打开本地相册；选择成功后沿用已有 `uploadAsset` 上传，保存前不把临时文件路径写入用户资料。微信 `chooseAvatar` 保留为明确的备用入口。
- 取消选图不会清空现有头像，选择失败有明确反馈；不修改后端、支付开关、客户信息链或生产环境。
- 合集列表、合集预览和合集编辑的分享路径及异常兜底统一指向当前合集详情页，不再把当前合集分享回合集列表。
- 验证：相关 JS `node --check`、页面 JSON 解析、`git diff --check`、SCRM pytest `13 passed`，并完成分享状态、头像取消/上传、入口顺序的对抗式静态断言。

# 2026-08-24 资料运营页按参考图重做（本地，待体验版上传）

- 将资料级资料运营页调整为参考图结构：资料摘要卡、查看/编辑操作、总访问/访客/分享三项统计、访问趋势、单条高意向访客、来源与动作、接龙未启用状态；移除绿色运营提示、四项客户动作卡和长客户动作列表。
- 复用现有卡片统计、资料客户动作和统一客户详情入口；后端统计响应本地补充 `trend.last7` 与 `trend.today`，本轮未部署生产后端。
- 资料运营请求先校验卡片 `ownerUserId` 与当前用户一致，再请求统计和客户动作，避免通过手工 URL 读取其他用户运营数据。
- 验证：资料运营 JS 与 API JS `node --check`、页面 JSON 解析、结构顺序/旧文案静态断言、`git diff --check`、卡片统计 pytest `3 passed`、SCRM pytest `13 passed`。

# 2026-08-24 头像入口收敛与合集资料运营统一（本地，待体验版上传）

- 登录页和个人资料弹窗移除微信 `open-type="chooseAvatar"` 按钮、事件函数及相关样式，只保留相册选图；继续复用已有临时文件上传和保存链路。
- 合集卡片操作区改为与资料卡相同的 `space-between` 纵向布局，拉开发客户按钮和三个点的距离。
- 资料卡和合集卡片的“资料运营”统一进入 `resource-analytics`；统一页根据实体类型显示“查看资料/编辑资料”或“查看合集/编辑合集”，旧 `showcase-analytics` 仅保留兼容跳转壳。
- 未修改后端、支付开关、客户信息链或生产环境。
- 验证：登录/个人资料/合集/资料运营相关 JS `node --check`、JSON 解析、头像/路由/间距结构断言、`git diff --check`、SCRM pytest `13 passed`、统计隔离 pytest `2 passed`。

# 2026-08-24 合集页自定义底部 Tab 接手验收（仅检查）

- 复核 `miniprogram/pages/showcases/index.wxml/js/wxss`：底部 Tab 位于加载中、首屏空态、正常列表和筛选面板分支之外；“资料”固定使用蓝色选中态，四入口分别指向原生 `tabBar` 的首页、资料、雷达和我的。
- 新建合集固定操作条位于 Tab 上方，`bottom: calc(116rpx + env(safe-area-inset-bottom))`；Tab 自身使用 `height: calc(112rpx + env(safe-area-inset-bottom))` 和安全区内边距。筛选遮罩打开时会按 modal 规则覆盖 Tab，节点仍存在且背景不可交互。
- 本轮未修改业务代码、未新增后端接口、未部署生产、未上传微信体验版；静态断言覆盖 4 条路由和 4 种页面状态，相关后端合集场景测试 `4 passed`。

# 2026-08-24 暂存推广奖励与供需发布功能（本地保留，未提交）

- 保留 `referral-center`、`supply-demand-publish`、`supply-demand-my`、`supply-demand-detail` 页面源码和后端能力，但从 `miniprogram/app.json` 移除路由，暂不随小程序提交。
- 移除个人页、会员页的推广奖励入口和推广规则入口；移除商机/供需广场的发布入口，并从商机 Tab 中隐藏供需广场入口。
- 个人页不再因客户信号请求推广中心数据，避免暂存功能继续产生无效接口请求。
- 本轮不删除本地页面文件、不修改后端、不部署生产；重新提交前需在微信开发者工具清缓存并重新编译确认页面不可达。

# 2026-08-24 自动化控制面第一段（本地，未部署）

- 按已确认的硬件形态建模为“一台 Android 手机 + 一个 ESP32 HID + 两个微信账号”，任务通过 `targetWechatAccountId` 串行领取；不假设两台手机并行执行。
- 新增 `backend/app/api/routes_automation.py`、`backend/app/schemas/automation.py`、`backend/app/services/automation_control_service.py`，以及设备、任务、群候选的领域模型和 JSON/PostgreSQL 持久化。
- PC 操作端可创建/查看任务；设备端可心跳、按当前微信账号领取任务、成功/失败回传；群候选只保存二维码引用、群名、保存时间、加入状态和是否可发送等最小字段。
- 操作令牌与设备令牌分离；任务有幂等键、单设备并发限制、租约和账号上下文校验。当前没有连接手机、执行真实加群/群发或部署生产。
- 验证：自动化控制 pytest `4 passed`、Python compileall、`git diff --check` 通过。全量后端测试为 `273 passed, 1 failed`；唯一失败是既有资料分享统计测试的 `shareCount` 仍为 0，与本轮自动化代码无调用关系。

# 2026-08-24 AScript + ESP32 真实设备入口联调

- 已完整核对 `/Users/yiyi/Downloads/AScript_ESP32_Android自动化架构设计方案.md`：AScript 负责感知、Selector/OCR/业务判断，ESP32 BLE HID 负责最终输入；当前测试严格停留在应用入口和账号选择，不执行搜索、加群、聊天或群发。
- 设备已通过局域网连接：nubia NX711J、Android 15、1080×2310，AScript 4.0.03；运行模式为 `HID控件模式`，辅助功能、录屏和悬浮窗已开启，`wechat_launcher` 工程可运行。
- 现有 launcher 的微信入口调用 `open_app("com.tencent.mm")` 后会弹出系统双开选择器；两个微信入口都显示“微信”，左侧和右侧均可由控件树读取，不能仅凭文本区分真实账号。
- 左侧微信入口按临时约定作为微信 1，右侧带双开标记的入口作为微信 2；两次均成功进入 `com.tencent.mm` 前台并读取到“通讯录/发现”等首页节点。微信 2 截图正常显示首页和群列表，微信 1 启动初期截图出现黑屏但控件树已加载，不能只用截图黑屏判断启动失败。
- 现有 launcher 的小红书入口同样弹出两个“小红书”实例；左侧小红书按“固定采集账号”临时选择，进入 `com.xingin.xhs` 后能读取“首页/发现/消息/我”，未执行搜索。
- 语义节点父点击在系统双开面板上未产生状态变化，才按实时观察到的卡片矩形降级使用一次 HID 坐标点击；自绘 WebWindow 本身无可用 Android 节点，入口卡片也只使用已观察位置。
- `get_device_status` 显示 AScript 蓝牙权限为未授予，AScript API 检索也没有发现 ESP32/Bluetooth 调用；本轮证明了 HID 动作能使手机入口状态变化，但没有把“ESP32 物理链路已连接”伪装成可由 AScript API 单独证明的事实。
- 本轮没有修改 teamBuy 业务代码、没有调用自动化后端、没有部署生产、没有上传微信体验版；测试结束时手机已恢复到 AScript 工具箱。

# 2026-08-24 双开微信账号身份探针第一段

- 新增 `automation/ascript/wechat_account_identity/__init__.py`，只读取两个双开微信实例的登录昵称并生成内部 `accountId`；本段不搜索小红书、不加群、不读聊天、不发营销消息。
- 账号身份以微信“我”页实际读到的昵称为准，不把左/右位置写成永久账号身份；当前设备实测右侧实例为 `leo`，生成 `wechat-nickname-6b621ed98e7fc3d77703`。左侧实例本轮启动后保持黑屏，45 秒内未出现微信页面，因此结果明确为 `degraded`，没有伪造左侧账号。
- 通过已连接的 ESP32 `BleDevice.home/click` 执行系统级返回和入口点击；双开选择器在设备侧 Selector 不稳定时保留 OCR 兜底。OCR 兼容微信号的全角/半角冒号，并拒绝装饰点等非昵称候选。
- AScript 可选向 `/api/automation/devices/heartbeat` 上报昵称元数据；当前 `BACKEND_URL` 和 `DEVICE_TOKEN` 留空，未发送网络请求。只要账号不完整或昵称重复，设备状态上报为 `degraded`，不会进入 `ready`。
- PC 端新增受操作令牌保护的 `GET /api/automation/devices`，可查看设备最新账号元数据；设备令牌不能读取设备列表。自动化控制测试 `5 passed`，Python compileall 与 `git diff --check` 通过。
- 对抗式审查结论：已验证令牌分权、部分账号不冒充 ready、重复昵称会阻断、未配置后端不联网；剩余阻塞是左侧微信实例在当前设备上的黑屏启动，需先人工恢复/确认该实例可正常打开，再继续做账号切换和加群动作。
- 对抗式审查补正：发现后端心跳模型未接受 AScript 的 `degraded` 状态；已同步更新领域状态和请求模型，并用自动化控制测试验证部分账号状态可以安全落库。

# 2026-08-24 生产新建资料 500 事故定位

- 21:00:39、21:00:46、21:01:21、21:01:25、21:01:47（北京时间）生产 `POST /api/notes/quick-capture` 均返回 500；健康检查仍为 200，故障集中在纯文字快速新建链路。
- 后端异常为 `AttributeError: 'UserNoteDraftPayload' object has no attribute 'contentBlocks'`。线上 `app_service.py` 已读取 `note_draft.contentBlocks`，但线上 `backend/app/schemas/skills.py` 的同名 Pydantic 模型没有该字段，属于部署代码契约不一致。
- 异常发生在 `repo.save_user_note()` 之前；本轮只读排查，未修改生产、未重启容器、未部署修复。后续需先对齐 schema/service，再做单接口回归和生产部署。

# 2026-08-24 生产新建资料 500 修复与对抗式审查

- 已在生产备份 `/home/ubuntu/teamBuy-backups/quick-capture-schema-fix-20260824-211437/` 后，只修改 `backend/app/schemas/skills.py` 的 `UserNoteDraftPayload.contentBlocks`，并将 `_build_user_note_from_note_draft()` 改为兼容读取缺失字段；未修改 `.env`、secrets、数据库或媒体目录。
- API、backend-worker、archive-worker 已重启；公网 `/health` 返回 200，未登录调用创建接口返回预期 401，重启后没有新的 5xx/Traceback。容器内无写入 dry-run 验证新 schema 和旧模型兼容路径均通过。
- 本地资料创建/编辑/发布相关回归 `9 passed`；完整后端测试 `274 passed, 1 failed`，唯一失败是既有 `shareCount` 统计测试，与本次修复无关。
- 对抗式审查确认：生产 backup 与当前文件差异仅为预期两处；ContentMediaPayload 元数据字段已在线上存在；分享回调文件未被本次修复修改，未把分享链路静态检查冒充为微信人工验收。

# 2026-08-24 生产新建资料 500 二段链路修复

- 用户复测证明第一处修复后，`POST /api/notes/quick-capture` 已返回 200，但前端紧接着的 `PUT /api/notes/{noteId}` 仍返回 500。
- 新堆栈定位为 `UserNoteUpdateRequest` 缺少 `contentBlocks`，`AppService.update_user_note()` 直接读取该字段；这是同一 schema/service 漂移在自动保存阶段的第二个暴露点。
- 已备份 `/home/ubuntu/teamBuy-backups/quick-capture-update-fix-20260824-212459/`，补齐生产 `UserNoteUpdateRequest.contentBlocks`，并让更新服务兼容读取缺失字段；未修改生产 `.env`、secrets、数据库或媒体目录。
- 已重启 API、backend-worker、archive-worker。重启后生产日志连续出现 quick-capture 200 及对应 PUT 200，错误扫描未发现新的 500/502/Traceback。
- 本地创建/编辑/发布回归仍为 `9 passed`，`git diff --check` 通过。真实登录用户的最终验收仍需用户再次操作一次。

# 2026-08-24 22:10 另一台手机点击后未收到订阅消息

- 生产日志确认另一台手机已打开资料：`GET /api/notes/public/note_5f6772f69f`、`POST /api/notes/note_5f6772f69f/view` 均为 200。
- 数据库中的访问事件为 `viewType=anonymous`、`anonymousId=visitor_1787580610629_58451`，`viewerUserId` 为空；22:00–22:20 没有对应的 `wechat_subscription_deliveries` 或 `wechat-subscription-send` 任务。
- 根因不是微信发送接口报错，而是当前业务规则明确拒绝匿名访问消耗订阅额度（返回原因 `anonymous_no_subscription_quota`）。另一台手机未登录小程序账号，点击不会触发发布者订阅消息。
- 正确验收方式：发布者先在分享入口同意订阅；另一台手机登录不同的小程序账号后再打开同一资料。若希望匿名点击也推送，需要另行调整隐私、频控和订阅额度规则，本次未改代码。

# 2026-08-24 匿名资料访问订阅消息规则调整

- 根据业务确认，匿名访问也属于有价值的浏览信号；已移除匿名访问不入队的限制。
- 匿名消息只使用“匿名访客”标签和资料标题，不传播访客身份或联系方式；同一发布者/资料/30 分钟窗口内的匿名访问统一去重，防止轮换 anonymousId 消耗多个订阅额度。
- 未设置偏好的会员用户默认开启普通/匿名浏览提醒；显式关闭的 `ordinaryAnonymousViewEnabled=false` 仍然生效。
- 本地订阅通知回归 `10 passed`，JS 语法检查和 `git diff --check` 通过；生产已备份并重启 API、backend-worker、archive-worker，AST、健康检查和 worker 启动日志通过。
- 生产真实匿名点击尚待用户再次触发完成最终微信送达验收；本次没有用诊断请求消耗生产订阅额度。

# 2026-08-24 xhs.find_group 只读垂直切片完成（本地与真机验证）

- 新增 `automation/ascript/xhs_find_group/__init__.py`：固定使用已验证可用的小红书右侧实例槽位，PC 配置了任务时领取 `xhs.find_group`，未配置后端时使用本地关键词 `微信群`；不打开笔记、不保存图片、不加群、不发消息。
- 真机通过 ESP32 HID 打开小红书双开选择器、选择右侧实例、进入搜索结果；AScript `Ocr.find_all()` 全量识别“群聊：群名”，`CodeScanner.scan()` 在同一屏幕快照上解码微信群邀请引用。
- 真机输出已验证至少一条稳定候选：`后来的我们`，二维码为已登记的 `https://weixin.qq.com/g/...` 引用；此前同一结果页还观察到 `资源共享群`。结果流会动态刷新，脚本现在要求搜索词和群聊标签同时存在，并在同一截图上配对群名与二维码，避免跨帧错配。
- 后端修正了账号无关任务的领取边界：`xhs.find_group` 以 `activeWechatAccountId=null` 领取时不再被最近微信昵称阻塞，完成任务也不会清空设备最近一次微信账号身份；目标微信账号任务仍由 `targetWechatAccountId` 校验。
- 设备测试结束已恢复 `wechat_launcher`；`BACKEND_URL` 和 `DEVICE_TOKEN` 仍为空，没有发送真实心跳、任务回传或群候选写入，也没有生产部署和微信体验版上传。
- 验证：AScript 入口完整部署运行成功；本地 AScript 文件 `py_compile` 通过；自动化控制 pytest `6 passed`；backend/app 与 backend/tests `compileall`、`git diff --check` 通过。
- 对抗式审查：固定小红书槽位顺序变化、结果流刷新、二维码无法解码、关键词不一致、未配置后端和左侧微信黑屏均不会被伪装成可执行加群状态。

# 2026-08-24 订阅消息进入消息页后的首页回流优化

- 发现订阅消息深链进入 `pages/message-thread/index` 后，消息页没有明确的首页入口，发送成功后也不会回到首页。
- 消息订阅深链现在携带 `source=subscription&autoHome=1`；消息页对订阅入口发送成功后显示成功反馈，并在短暂提示后 `wx.switchTab({ url: '/pages/home/index' })`，失败时用 `reLaunch` 兜底。
- 消息页始终显示“回到首页”按钮，并启用可用时的返回箭头；普通站内消息页不自动跳转，避免打断正常对话。
- 本地消息订阅回归 `10 passed`、消息页 JS/JSON 检查通过；生产后端已备份 `/home/ubuntu/teamBuy-backups/subscription-message-home-path-20260824-223908` 并重启 backend 与 worker，AST、健康检查 200 和源码深链检查通过。
- 小程序前端尚未由 Codex 上传体验版，需用户在微信开发者工具上传后进行真机验收。

# 2026-08-24 生成同款链路性能优化

- 根因确认：`POST /api/scrm/same-style/generate` 不调用 AI、OCR、分享图生成或媒体转码，但旧实现为检查幂等和保存生成记录，先后两次读取并整体保存 PostgreSQL `AppState`。生产当前约 4,571 行、11.7 MB，末次整体保存还会逐表删除再重插，与轻量配置动作不匹配。
- 后端改为按表读取/写入 `same_style_generations` 和 `referral_relations`；同款生成不再触发完整 `AppState` load/save。源用户重复读取也收敛为一次，保持公开内容净化、联系方式替换、裂变关系和幂等语义不变。
- 生产部署前检查磁盘可用 32 GB、Docker 可回收空间未执行清理；备份目录为 `/home/ubuntu/teamBuy-backups/same-style-performance-20260824-225504/`。部署时发现本地脏工作区的完整 `repository.py` 包含生产尚未同步的 Automation 模型，导致短暂启动失败；已立即用备份恢复并改为只在生产基线文件上补 4 个方法，健康检查恢复 200。
- 最终将生成记录与裂变关系合并为单事务写入，二次部署前的生产基线备份为 `/home/ubuntu/teamBuy-backups/same-style-performance-atomic-20260824-230235/repository.py`。
- 追加把源用户对象复用到三段联系方式净化逻辑，生产备份为 `/home/ubuntu/teamBuy-backups/same-style-profile-read-20260824-230555/app_service.py`；重启后健康检查和幂等耗时验证仍通过。
- 线上已有幂等请求耗时从部署前约 `0.468s` 降至 `0.031–0.049s`，约提升 90%；测试只读已有记录，`same_style_generations=4`、`user_notes=1336` 未变化。
- 本地 `backend/tests/test_sales_scrm.py -k same_style` 为 `3 passed`，Python 编译、`git diff --check` 通过；本次只改后端，无需重新上传小程序体验版。

# 2026-08-24 微信原生群扫描并入 PC 群候选库（只读切片）

- 后端群候选记录新增 `source=wechat_native`、可空 `groupQRCode`、`remark` 与 `lastSeenAt`；原生微信群不要求二维码，首次发现视为已加入，`canSend` 初始保持未知。小红书来源仍必须带二维码，避免放宽原有加群门禁。
- 新增 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/automation/ascript/wechat_group_inventory/__init__.py`：串行读取同一安卓手机上的两个微信实例，按真实昵称建立账号标识，进入“通讯录 → 群聊”，滚动收集原生群名，并可通过 PC API 写入统一候选库。
- 真机当前账号的原生微信群列表读取到 10 个群；脚本严格只读，不打开群、不加群、不发消息。由于设备脚本中的 `BACKEND_URL` 与 `DEVICE_TOKEN` 仍为空，本轮只证明了设备侧读取，未宣称 PC 实际写入成功。
- 重扫时保留人工审核的 `remark` 与 `canSend`，`savedAt` 保持首次入库时间，`lastSeenAt` 更新；同一微信账号下暂以群名去重，后续若能从详情页取得稳定群 ID 再升级键值。
- 验证：`backend/tests/test_automation_control.py` 为 `8 passed`；AScript 入口本地 `py_compile` 通过；`git diff --check` 通过。未部署生产后端，未上传微信体验版。

# 2026-08-24 微信会话列表补充扫描（双账号真机回归）

- 根据真机事实补充第二来源：微信“通讯录 → 群聊”不是完整群集合；微信首页会话列表中存在未保存到通讯录的群。扫描现在先读取通讯录群聊，再读取首页会话列表并向下滚动，只读合并去重。
- 会话列表群识别采用“多头像网格视觉证据 + 群名语义提示”双重策略，明确排除“服务号、公众号、微信团队”；不会打开任何会话或读取聊天内容。
- 真机最终回归：微信实例 `高士腾` 读取通讯录 39 个、会话列表 7 个，合并 46 个；微信实例 `leo` 读取通讯录 10 个、会话列表 110 个，合并 111 个；两个实例均无脚本错误。
- 回传结果语义已修正：未配置 `BACKEND_URL`/`DEVICE_TOKEN` 时输出 `preparedCount`，`postedCount=0`、`backendWriteConfirmed=false`，不再把本地候选准备数量误称为 PC 已入库。
- 修复 AScript ESP32 调用：当前官方插件方法为 `BleDevice.slide()`，不是 `swipe()`；最终真机回归 HID 插件加载成功并运行完成。
- 仍有边界：会话扫描最多 180 次滑动并在连续 3 次无变化时停止，当前证明的是“可滚动发现更多群”，不是已经穷尽微信全部 12,000+ 会话；会话列表候选仍必须经过 PC 人工确认后才能进入营销范围。
- 验证：AScript 最终真机双账号运行成功；本地 `py_compile`、自动化控制 pytest `8 passed`、`git diff --check` 均通过；未部署生产后端，未上传体验版。

# 2026-08-24 生成同款复用与排序优化

- 同一用户再次复用同一公开资料/合集时，后端按 `ownerUserId + mode + sourceNoteId/sourceShowcaseId` 查找最近一次有效生成结果；目标资料仍归属当前用户且未删除时直接复用，不再创建重复资料。原有幂等键仍保留，`use_own_content` 因未持久化所选资料集合暂不做语义去重。
- 资料库和合集列表新增 `isSameStyle`、`sameStyleLabel`、`sameStyleGeneratedAt`、`sameStyleSourceId` 元数据；同款按生成时间置顶，普通资料继续按原来的更新时间/收藏时间排序，未修改资料 `updatedAt`。
- 小程序资料库与合集列表显示“同款”标签；公开资料页改用稳定幂等键，生成同款成功后统一清理资料/合集客户端列表缓存，确保返回列表立即看到置顶结果。
- 本地验证：`backend/tests/test_sales_scrm.py -k same_style` 为 `3 passed`；Python 编译、4 个相关 JS `node --check`、`git diff --check` 通过。
- 生产部署前检查磁盘可用 32 GB、未执行 Docker 清理；备份目录为 `/home/ubuntu/teamBuy-backups/same-style-reuse-sort-20260824-232549/`。仅更新后端 `app_service.py` 和生产基线补丁版 `repository.py`，未覆盖生产 `.env`、secrets、数据库或媒体目录。
- 生产 `/health` 返回 200；使用线上已有同款记录做只读语义复用验证，结果为 `duplicate=true/reused=true`，资料和同款记录数量前后均为 `37/1`；线上列表首项为同款资料并带“同款”标签。小程序前端仍需用户上传体验版后真机验收。

# 2026-08-24 资料助手绑定接口同步部署

- 生产点击“资料助手”时，前端调用 `GET /api/auth/wecom-bind-status`，但生产旧路由只注册了 `wecom-bind-intent`，接口实际返回 404；前端 catch 原先把所有错误显示为“登录状态异常”。
- 已备份并同步生产 `backend/app/api/routes_auth.py` 与 `backend/app/schemas/auth.py`，补齐 `wecom-bind-status`、`wecom-bind-card` 及 `WecomBindCardRequest`；线上 `AppService` 对应服务方法原本已存在，未覆盖整套后端代码。
- 生产备份目录为 `/home/ubuntu/teamBuy-backups/wecom-bind-routes-20260824-233812/`；未修改 `.env`、secrets、数据库或媒体目录。API 与 backend-worker 已重启。
- 验证：公网 `/health` 返回 200；生产路由清单已出现两个绑定接口；带真实签名会话的绑定状态只读请求返回 `success=true、status=unbound`；无效绑定卡请求返回预期 400，未写入数据。
- 小程序本地入口错误文案已区分 401、404 和其他错误；该文案需随体验版上传后生效，后端接口修复不依赖重新上传即可解除当前 404。

# 2026-08-24 PC 群自动化运营页与审核入库链路

- 运营后台左侧“群运营”分组新增“群自动化运营”页面，读取自动化设备心跳和统一群候选库，展示微信账号、来源、最近发现、营销状态和备注。
- 新增运营令牌保护的 `PATCH /api/automation/group-candidates/{candidate_id}`，PC 可明确设置“允许营销/暂不营销”和备注；设备令牌不能调用该审核接口。
- 群候选继续由设备接口幂等写入；设备重扫传入 `canSend=null` 或不传备注时，会保留 PC 已审核的 `canSend/remark`。自动化运营令牌仅存当前浏览器会话的 `sessionStorage`。
- AScript 会话列表扫描改为每次滑动后比较可见会话名称及上下位置；连续两次无位移才标记 `bottom_stable`，`MAX_CHAT_SCROLLS` 只作为防卡死上限，并在结果中回传停止原因和实际滑动次数。
- 当前仍未填写设备侧 `BACKEND_URL/DEVICE_TOKEN`，因此尚未宣称真机已写入 PC；本轮只完成接口、页面和权限链路，未部署生产、未上传体验版。
- 验证：自动化控制 pytest `9 passed`；Python 编译、PC 内嵌脚本 `node --check`、`git diff --check` 通过。

# 2026-08-25 运营后台旧 HTML 缓存排查

- 用户截图中的“群运营”只有 3 个子项，但当前源码已包含第 4 项“群自动化运营”；根因是浏览器/旧后端服务返回了旧版 HTML，不是页面功能未写入。
- `/ops` 的 `FileResponse` 增加 `Cache-Control: no-store, max-age=0`，后端重载后不再复用旧菜单 HTML。
- 本地源码菜单、PC 内嵌 JavaScript、Python 编译和 `git diff --check` 通过；未部署生产。组合回归发现 1 个与本次无关的既有资料分享统计失败，自动化控制测试保持 `9 passed`。

# 2026-08-25 群自动化运营页面与后端控制面生产部署

- 已备份并部署生产 `/home/ubuntu/teamBuy` 的运营后台 HTML、`/ops` 防缓存响应，以及自动化设备/群候选控制面相关代码；生产采用 bind mount，未重建镜像，只重启 `teambuy-backend-1`。
- 生产公网 `https://teambuy.lifelove.top/ops` 已验证返回“群自动化运营”和 `Cache-Control: no-store, max-age=0`；`/health` 返回数据库正常。
- `/api/automation/devices` 未携带令牌返回 403，说明自动化运营鉴权已生效；生产 `.env` 未写入新令牌，尚未开放真实设备回传。
- 备份目录：`/home/ubuntu/teamBuy/.deploy-backups/ops-automation-page-20260825-0009`、`/home/ubuntu/teamBuy/.deploy-backups/automation-api-20260825-0013`。
- 本次没有部署小程序、没有改生产数据库数据、没有执行营销动作；页面已上线，真实群入库还需要单独配置运营令牌/设备令牌后验收。

# 2026-08-25 企业微信动态欢迎语后端接入

- 后端客户添加回调现在发送“欢迎文字 + 动态小程序卡片”；文字默认说明资料助手用途，卡片标题改为“开启我的资料库”，卡片页面继续使用每个客户独立的一次性 token。
- 回调解析失败增加不打印密钥和消息正文的结构化异常日志，用于定位企业微信回调 400 的签名、解密或格式问题。
- 本地验证：`./.venv313/bin/pytest -q backend/tests/test_wecom_contact_binding.py` 为 `5 passed`；Python 编译和 `git diff --check` 通过。
- 生产已备份目标代码与 `.env` 到 `/home/ubuntu/teamBuy-backups/wecom-dynamic-welcome-20260825-001935/`，同步后重启 `teambuy-backend-1`；生产 `/health` 返回 200，运行时已加载新的欢迎文字和卡片标题。
- 生产 Docker 镜像构建因 Debian 软件源安装阶段无输出而停止；生产采用 backend bind mount，源码同步并重启已使改动生效，未改数据库、媒体、secrets 或生产 `.env`。
- 待人工验证：必须使用尚未添加过资料助手的企业微信客户重新添加，确认收到欢迎文字和动态小程序卡片；若仍失败，读取本轮新增的回调解析异常日志。

# 2026-08-25 动态欢迎语首次真实测试失败定位

- 用户在 12:32 左右重新添加资料助手；生产日志确认 POST 回调已到达，但连续返回 400。
- 新增日志已定位为 `企业微信回调签名验证失败`，失败发生在 `parse_callback_body`，早于 `WelcomeCode` 提取和 `send_welcome_msg` 调用；因此本次没有发送欢迎文字或动态卡片。
- 当前最小阻塞是企业微信“客户联系 → 客户 → API → 接收事件服务器”的 Token 与生产 `WECOM_CALLBACK_TOKEN` 不一致；需要同时核对 URL、Token、EncodingAESKey，且不要把固定欢迎语页面当成动态绑定配置。
- 本轮没有绕过签名校验，也没有把密钥打印到日志或聊天；待企业微信后台配置修正后，用新客户再次添加验证。

# 2026-08-25 独立令牌配置与真机群库入库验收

- 已生成并配置独立的运营令牌与设备令牌；令牌保存在本机受保护的 `tmp/automation-secrets-20260825.txt`，未写入 Git、聊天或生产日志。
- 生产 `backend/.env` 先备份到 `/home/ubuntu/teamBuy/.deploy-backups/automation-tokens-20260825-002428/backend.env`，再仅追加两项自动化令牌；后端使用 `--force-recreate backend` 重新读取 env，`/health` 返回 `ok/postgres`。
- 鉴权验收通过：无令牌请求 `/api/automation/devices` 返回 403；正确运营令牌读取设备和群候选接口均返回 200。
- AScript 工程新增被忽略的本地 `local_config.py`，当前只配置第一个微信实例，上传后脚本启动；真机屏幕处于锁屏/面部验证页，未进入微信，因此没有产生设备心跳或群候选写入。
- 已主动停止真机脚本，未执行加群、打开群聊、发消息或营销动作；静态配置检查、自动化控制测试 `9 passed`、`git diff --check` 通过。

# 2026-08-25 真机双微信群库入库验收完成

- 解锁手机后重新清理旧运行状态并启动单账号扫描；高士腾账号首次回传 47 条，PC API 按账号核对为 47 条，来源全部为 `wechat_native`。
- 恢复双账号配置后完成只读扫描：高士腾本轮 46 条、leo 102 条，两个账号均 `backendWriteConfirmed=true` 且 `postErrors=[]`；会话列表均以连续两次滑动后可见内容和底部位置不再变化为停止条件。
- PC API 当前实际记录 149 条：高士腾 47 条、leo 102 条，全部 `canSend=unset`，没有任何群被自动批准发送；设备心跳已回传，能力标记为 `ascript/double-wechat/wechat-native-group-inventory`。
- 高士腾本轮扫描比前一次少 1 条，但入库采用幂等 upsert、不会因一次扫描未看到就删除历史记录；该差异保留给后续 `lastSeenAt`/失联复核流程处理，避免误删真实群记录。
- 本轮没有加群、打开群聊、读取聊天内容、发消息或营销；生产页面和接口未新增改动。
- 扫描结束后已通过设备令牌将 `android-01` 心跳恢复为 `ready`，PC 端实际状态核对为 `ready`；后续应把结束心跳写入 AScript，避免依赖人工收尾。

# 2026-08-25 PC 自动化运营改为复用管理员 Token

- 根据唯一管理员使用场景，PC 群自动化运营页已删除重复的自动化运营 Token 输入框，直接复用顶部管理员 Token；AScript 设备回传仍使用独立设备令牌，避免手机端获得管理员权限。
- 自动化 operator 鉴权现在兼容 `X-Admin-Token` 和原有 `X-Automation-Operator-Token`；无 Token 仍返回 403，设备 Token 访问 PC 读接口仍返回 403。
- 生产已备份并部署 `routes_automation.py`、`ops-admin/index.html`，重启 `teambuy-backend-1`；公网页面已验证不再包含旧输入框，管理员 Token 读取群库返回 149 条，账号分布为高士腾 47、leo 102。
- 对抗式检查通过：旧 operator Token 仍可读 149 条、管理员 Token 可读 149 条、设备 Token 不能读群库，生产最近日志无启动错误。

# 2026-08-25 群库审核改为行内“可以/不可以”

- 运营后台“群自动化运营”页移除右侧独立人工审核表单，微信群库每一行直接显示“可以营销”和“不可以营销”两个按钮；当前状态按钮高亮，点击后立即保存并更新该行与统计。
- 行内审核仍调用原有 `PATCH /api/automation/group-candidates/{id}`，不新增后端接口、不创建营销任务、不触发 AScript 发消息；已有备注会随请求原样保留。
- 已完成对抗式审查：未审核 `canSend=null` 仍不计入允许营销；审核按钮只改 `canSend`；设备 Token 仍不能修改审核；请求期间同一行两个按钮禁用，避免连续点击重复提交。
- 本地验证：运营后台内联 JS `node --check`、`git diff --check`、`./.venv313/bin/pytest -q backend/tests/test_automation_control.py` 为 `10 passed`。
- 生产已备份并部署页面到 `/home/ubuntu/teamBuy/.deploy-backups/ops-inline-review-20260825-011531/`，重启 `teambuy-backend-1`；公网 `/ops` 已验证包含新按钮文案、旧审核表单已消失，`/health` 正常。
- 营销卡片关联暂不直接绑死在群记录上，确定采用“群标签/性质 → 营销策略 → 卡片或合集池 → 时间窗口发送任务”；`canSend=true` 只是群级总开关，未审核/不允许营销/无匹配策略/卡片未发布均不得生成发送任务。

# 2026-08-25 群画像与实际发送资格第一版

- `AutomationGroupCandidate` 增加主题、地域、允许内容类型、成员状态、最近活跃时间和最近检查时间；新字段随现有 payload JSON 保存，不新增数据库表或迁移。
- PC 群库增加“保存群画像”，可以直接填写“房产/宠物/AI工具”等主题、上海/长沙等地域、允许内容类型和成员状态；最近活跃与最近检查时间暂由后续手机状态检查回传，页面不会伪造这些时间。
- 服务端新增只读 `sendEligibility` 计算：管理员许可不等于当前可发送；未确认成员状态、没有近三天活跃记录、近三天无活跃、缺少主题地域或尚未配置卡片策略时均不会放行。
- `canSend` 语义已收紧：设备候选上报即使携带该字段也不能修改管理员许可；新群保持待确认，重扫只保留已有管理员结果。设备 Token 线上 PATCH 验证返回 403。
- 本地验证：自动化控制测试 `11 passed`、运营后台内联 JS `node --check`、`git diff --check` 通过；生产 `/health` 正常，群库返回资格字段和画像字段，页面已显示新编辑控件，生产日志无启动错误。
- 生产备份目录：`/home/ubuntu/teamBuy/.deploy-backups/group-profile-20260825-013732/`。
- 本轮仍未读取聊天正文、未创建营销任务、未发送微信消息；下一阶段增加手机端只读群状态检查，回传“是否仍在群内、最近活跃时间、检查时间”。

# 2026-08-25 群库账号昵称与布局优化

- 群库不再把长 `wechatAccountId` 作为表格列展示；顶部账号筛选改为显示微信昵称，群名称下方只显示短昵称，内部 ID 继续仅用于筛选和接口请求。
- 后端增加 `wechatAccountName` 和设备双账号昵称映射；AScript 本地代码已补充昵称回传字段，尚未上传手机执行。历史 149 条记录已按已确认身份补齐：高士腾 47 条、leo 102 条。
- 群画像编辑区改为紧凑布局，发送资格单独展示；“群主题”明确作为内容路由条件，与地域和允许内容类型共同决定匹配卡片，不是普通备注。
- 生产已部署页面和账号映射代码，备份目录为 `/home/ubuntu/teamBuy/.deploy-backups/account-label-layout-20260825-014947/`；昵称元数据容错补丁备份于 `/home/ubuntu/teamBuy/.deploy-backups/account-label-guard-20260825-015329/`。
- 生产验证：健康检查正常，群库仍为 149 条且昵称分布为高士腾 47、leo 102，运营后台源码已包含顶部账号筛选和紧凑画像布局；本地自动化测试 `11 passed`、AScript Python 语法、内联 JS 和 `git diff --check` 均通过。

# 2026-08-25 群库分页与营销卡片内容落地边界

- 群自动化运营页的微信群库改为前端每页 10 条，增加“上一页/下一页”和“第 N / M 页 · 共 X 个群”；账号筛选或刷新后回到第 1 页，行内审核和群画像保存保持当前页，不新增后端接口。
- 分页复用现有最多读取 500 条群候选的接口，当前 149 条记录可完整分页展示；如果群库未来超过 500 条，再单独把接口改为服务端分页，不在本轮扩大范围。
- 发送卡片不直接填写在每个群库行里。群行的“允许内容”只保存内容类型白名单；实际内容来自已发布的资料/合集卡片，策略按群主题、地域、内容类型和目标群范围进行匹配，再生成发送任务。
- 发送任务至少引用 `candidateId`、`cardId`、卡片版本和当前分享快照；AScript 只领取明确任务并回传结果，不在手机端临时决定发什么，也不拼装卡片内容。没有精确匹配的卡片时不生成任务。
- 本轮只部署运营后台 HTML，备份目录为 `/home/ubuntu/teamBuy/.deploy-backups/group-pagination-20260825-022812`；生产 `/health` 正常、页面包含分页标记，未改数据库、未上传小程序、未执行微信发送。
- 验证：运营后台内嵌 JS `node --check`、`git diff --check`、自动化控制 pytest `11 passed`；生产 backend 重启后无启动错误。
# 2026-08-25 小程序营销路由与单群单卡任务第一版

- 小程序通用资料编辑页增加“微信群营销匹配”字段：主题、地域、内容类型；字段写入现有 `UserNote.visibilityConfig.marketingRoute`，不复制正文，也不影响普通客户分享。
- 房源、团购、服务等专用卡片没有重复增加一套表单；自动化卡片目录按卡片类型提供安全默认主题/内容类型，并从已存在的结构化城市字段推导地域，通用资料可人工选择。
- 自动化控制面新增 `GET /api/automation/marketing-cards`，只返回已发布资料卡的标题、类型、路由和分享快照状态，不返回正文、私密字段或联系方式。
- 新增 `POST /api/automation/marketing-card-tasks`，PC 只支持“指定群 + 指定已发布卡片 + 指定设备”的单次测试任务。服务端再次校验管理员许可、仍在群内、近三天活跃、主题/地域/允许内容匹配、分享图为当前 revision 后才创建待执行任务。
- 任务固定为 `wechat.send_miniapp_card`，只进入 AScript 队列；本轮没有实现 AScript 发送执行器，不会因点击 PC 按钮直接发微信消息。
- 本地验证：小程序 JS、运营后台内嵌 JS、Python 编译、JSON 解析和 `git diff --check` 通过；自动化、资料发布/分享相关 pytest 共 `17 passed`。
- 生产已备份并部署 4 个后端/运营文件，备份目录为 `/home/ubuntu/teamBuy/.deploy-backups/marketing-card-route-20260825-025730`；`/health`、`/ops` 页面标记和带管理员鉴权的卡片目录接口均已验证。未上传小程序体验版，未执行营销任务。

## 2026-08-25 佛山宠物交流群1 单群单卡预检

- 生产群库精确找到 `佛山宠物交流群1`，候选为 `group_candidate_a4b7f6a5b4`，账号显示为 `leo`，设备为 `android-01`，管理员允许进入策略，主题为宠物、地域为佛山、允许内容为寻猫。
- AScript 实时截图和 OCR 已确认手机当前打开同名群页面；本轮没有点击发送、没有创建生产任务。
- 当前最相关的已发布资料卡为“刚流浪几个月的蓝猫”（`note_d9743da89b`，revision 3），但没有宠物/佛山/寻猫营销路由，也没有当前 revision 的分享图，服务端按既定门禁拒绝发送。
- 设备端 `esp32` 插件导入报 `bad magic number`；按官方插件版本重新加载仍未恢复，暂不能把 ESP32 HID 视为已验证的发送通道。
- 下一步是先补齐测试卡路由和分享快照、确认群内近三天活跃与当前账号，再实现 AScript `wechat.send_miniapp_card` 的单次执行和结果回传；未满足任一项都不创建任务。

## 2026-08-25 PC 运营总览时间范围切换

- 总览新增“今日 / 近 7 日 / 近 30 日”切换；服务端 `overview` 和 `customer-operations` 接口接受同一 `period` 参数。
- 时间范围同步影响匿名独立访客、新增用户/资料/合集、展示页打开、客户动作、高意向动作、通知、支付收入、漏斗分支和趋势；当前待办与会员状态保留当前快照并在页面标明“当前”。
- 漏斗包含匿名访客、注册、首次创建内容、首次发布、分享和客户信号，并保留首次新建资料/合集分支；匿名 ID 无法和后续注册稳定归因时只展示参考比例。
- 本地验证：Python 编译、运营后台内嵌 JS `node --check`、`git diff --check`、相关定向测试通过；完整后端测试 `282 passed, 1 failed`，失败为既有资料分享统计测试，与本次运营总览改动无关。

## 2026-08-25 PC 运营总览时间范围生产发布

- 生产采用 backend bind-mount，本次未重建镜像，只备份并同步 `routes_ops_admin.py` 和 `ops-admin/index.html`，随后重启 `teambuy-backend-1`。
- 生产备份目录：`/home/ubuntu/teamBuy/.deploy-backups/ops-period-switch-20260825-122445/`；未修改生产 `.env`、secrets、媒体目录或数据库数据。
- 生产验证：`/health` 返回数据库正常；带管理员鉴权的 overview/customer-operations 接口分别通过 today、7d、30d；公网 `/ops` 返回新时间切换按钮。

## 2026-08-25 佛山宠物交流群1 设备与小程序复核

- 通过手机实时打开目标群，当前微信实例已确认昵称为 `leo`，生产群记录 `membershipStatus=active`，并写入 `lastVerifiedAt=2026-08-25T12:23:16+08:00`。
- 目标群当前仍为 `activity_check_required`：截图只能证明群页面已打开，不能证明近三天有消息；本轮没有伪造 `lastActivityAt`。
- 手机端重新进入“资料整理助手”后处于游客态，资料页为空，不能替卡片所有者编辑“刚流浪几个月的蓝猫”、发布或生成分享图；没有触发登录或授权。
- ESP32 插件仍为 `plug.load=true`、`import=false`，设备端报 `bad magic number`，`ashid` 未激活；真实发送器继续拒绝使用未验证 HID 通道。
- 任务队列保持为空，未创建任务、未发送微信消息；下一步需要管理员登录卡片所有者账号完成路由/发布/分享图，再修复设备插件并补做近三天活跃核验。

## 2026-08-25 佛山宠物交流群1 活跃确认与卡片权限复核

- 按管理员确认“刚发了消息”，已将目标群 `lastActivityAt` 记录为 `2026-08-25T05:02:26.993509+00:00`；生产发送资格已进入 `card_route_required`，不再阻塞于近三天活跃。
- 当前手机已重新打开资料整理助手，但“我的”页明确显示“游客浏览”和“登录”，资料数量为空；因此不能通过当前会话替卡片所有者改生产资料。
- 生产卡片“刚流浪几个月的蓝猫”仍为主题“其他”、地域空、内容类型“普通资料”、revision 3、无分享快照；没有写入未经授权的路由或发布状态。
- ESP32 复测仍为 `plug.load=true`、导入失败 `bad magic number`，与手机当前蓝牙/系统状态不能混为一谈；真实 HID 发送仍未放行。

## 2026-08-25 ESP32 插件错误定位

- AScript 设备实测运行时为 Python 3.8.16，官方插件目录显示 `esp32` 最新版本为 4.7.0；`plug.load("esp32:4.7.0")` 返回成功，但 `from esp32 import BleDevice` 失败。
- 设备实际加载的 `/data/user/0/com.aojoy.airscript/files/line_plug/esp32/__init__.pyc` 文件头为 `48 38 74 58`（ASCII `H8tX`），不是当前 Python 可识别的字节码头，因此报 `bad magic number`；`BleDevice` 和 `ashid` 尚未进入可执行阶段。
- 该故障发生在 AScript 手机插件包/运行时兼容层，不是 `idf.py` 固件编译或烧录错误；本轮没有刷写 ESP32 固件，也没有用普通坐标点击冒充 HID。
- 最小修复方向是更新/重启兼容的 AScript Android 运行时，并在设备端清理后重新下载官方 4.7.0 插件；完成导入后再检查蓝牙权限和 HID 连接。

## 2026-08-25 ESP32 USB 只读识别

- Mac 发现串口 `/dev/cu.usbmodem211NTXR6V3782`，已使用本机 `esptool.py v4.7.0 chip_id` 做只读识别。
- 当前返回 `No serial data received`，没有执行任何 `write_flash`；优先判断为未进入下载模式、线材/端口问题或设备未正确复位。
- 进入下载模式并识别芯片型号后，才能从安卓蓝牙固件目录选择对应的 C3/S2/S3/Pico32 固件；刷固件也不能替代 AScript Python 插件包修复。

## 2026-08-25 ESP32 串口归属复核

- `/dev/cu.usbmodem211NTXR6V3782` 对应的是 LG 显示器 USB 控制设备，USB 序列号为 `211NTXR6V378`，不是 ESP32 开发板。
- 因此此前 `esptool chip_id` 的无响应不能作为 ESP32 芯片或固件故障证据；本轮仍未执行 `write_flash`。
- 下一步需把 ESP32 通过真正的数据线直接接入 Mac，确认出现新的串口后再做 `chip_id` 和型号匹配。

## 2026-08-25 ESP32-C3 固件刷写与手机插件复测

- 直连后发现新串口 `/dev/cu.usbmodem101`，USB 设备为 Espressif USB JTAG/serial debug unit，MAC 为 `10:20:BA:DC:5D:90`。
- 只读识别确认芯片为 `ESP32-C3`；按芯片匹配刷写 `/Users/yiyi/Downloads/AS-esp32固件烧录/安卓蓝牙固件/esp32-c3/firmware` 的 bootloader、partitions 和 firmware。
- `esptool.py v4.7.0` 三段写入均完成，三段均 `Hash of data verified`，随后已通过 RTS 硬复位；没有使用 `idf.py`。
- 刷写后重新连接 Android-237 并执行 `plug.load('esp32:4.7.0')` 与 `from esp32 import BleDevice`；仍为 `load=true`、`import=false`，报错仍是 `bad magic number in 'esp32': b'H8tX'`。
- 结论：ESP32-C3 固件刷写链路已通过，但手机端 AScript ESP32 插件仍是坏的/不兼容 `.pyc`，问题尚未进入蓝牙通信层；真实 HID 发送继续禁止。

### 下一步最小执行顺序

1. 在 AScript Android 端清理并重新下载兼容的官方 `esp32:4.7.0` 插件，重新验证 `BleDevice` 导入。
2. 导入成功后再验证蓝牙权限、设备发现和 HID 激活状态。
3. 通过硬件通道预检后，回到小程序卡片路由/分享图，再执行单群单卡测试。

## 2026-08-25 商家转账最小开发测试

- 已按负责人确认的商家转账场景 `1005` 增加独立服务器配置：`WECHAT_TRANSFER_ENABLED`、`WECHAT_TRANSFER_SCENE_ID`、`WECHAT_TRANSFER_NOTIFY_URL`；本地和示例环境均保持 `WECHAT_TRANSFER_ENABLED=false`，生产环境未改动。
- `WechatPayClient` 已增加创建商家转账单的最小适配器，使用现有商户私钥和 API v3 签名配置，构造金额（分）、OpenID、场景报备信息和 HTTPS 回调地址；当前未接入佣金提现业务状态机，也未触发真实付款。
- 新增 mock 测试覆盖：1005 请求体、商户请求签名、关闭开关保护、微信失败时不自动换商户单号重试；`backend/tests/test_wechat_pay.py` 定向测试 9 项通过。

## 2026-08-25 佣金提现金额与审核回调闭环

- 提现最低金额按环境读取：开发/测试 `WECHAT_TRANSFER_TEST_MIN_AMOUNT_FEN=10`（¥0.10），生产 `WECHAT_TRANSFER_MIN_AMOUNT_FEN=1000`（¥10.00）；小程序推广中心会展示当前环境门槛并在提交前提示。
- 增加运营后台提现列表和审核发起接口；审核通过后创建稳定的微信商户单号，状态进入 `waiting_user_confirm`/`processing`，转账成功回调后奖励从 `reserved` 结算为 `withdrawn`。
- 微信转账 2xx 响应、异步回调均做签名/金额/OpenID校验；重复成功回调不会重复结算，失败/撤销会释放奖励预占。当前生产转账开关仍关闭，未部署、未发生真实付款。
- 佣金和微信支付针对性回归测试共 `25 passed`；Python 编译、前端 JS 语法和 `git diff --check` 均通过。

## 2026-08-25 提现规则与转账异常处理闭环

- 推广中心新增独立“提现规则”区块，明确可提现门槛、每日最多 1 次、北京时间可申请时段、平台审核、提现手续费、到账时间和失败/撤销处理；到账文案明确为“以微信实际到账时间为准，用户确认后基本秒到”。
- 小程序接入 `wx.requestMerchantTransfer`，仅在提现记录为 `waiting_user_confirm` 且存在 `packageInfo` 时拉起微信确认页；前端不把拉起成功误显示为已到账，最终状态仍以微信回调/查单为准。
- 后端增加微信商户单号查单、撤销接口及运营后台 `query`/`cancel` 人工处理入口；撤销受理后保持 `CANCELING`，只有查单或回调到 `CANCELLED` 才释放冻结佣金。
- 增加每日提现次数服务端限制配置 `WECHAT_TRANSFER_DAILY_WITHDRAWAL_LIMIT=1`；定向回归测试 `26 passed`，Python 编译、前端 JS 语法和 `git diff --check` 通过。生产未部署、转账开关仍关闭。

## 2026-08-25 提现页注册为可直接测试页面

- 已将 `pages/referral-center/index` 注册到 `miniprogram/app.json`；此前页面代码存在但未进入小程序路由，开发者工具无法直接编译打开。
- 当前页面可通过开发者工具“编译模式”直接打开；小程序 `app.js` 仍指向生产 API，本轮未部署后端，真实提交前需要先确认体验版使用的后端版本。

## 2026-08-25 我的页增加推广奖励入口

- 在“我的”页增加“推广奖励”入口，点击进入 `pages/referral-center/index`；入口对已登录用户可见，位置在客户信号卡片和设置区域之间。
- 复用现有推广图标和小程序 `rpx` 对齐样式，页面入口和提现页面均通过 JS/JSON/diff 检查。

## 2026-08-25 线上敏锐生意人提现测试奖励

- 在线上 PostgreSQL 为最近更新的 `敏锐生意人` 账号 `user_ce567d897f` 增加一笔可提现测试奖励 `20` 分（¥0.20），测试来源单号为 `test_withdrawal_user_ce567d897f_20fen_v1`。
- 写入前确认该账号没有既有佣金记录，写入后复核状态为 `available`、金额为 `20` 分；记录可幂等识别，不会重复追加同一测试来源单号。
- `WECHAT_TRANSFER_ENABLED` 未打开，不会自动向微信付款；用户点击申请后只会产生提现申请记录，仍需后台审核。

## 2026-08-25 生产提现状态与页面重构

- 核对线上 `withdrawal_bd00988073`：提现为 `pending`、奖励为 `reserved`，没有微信商户单号；根据负责人确认的实际到账结果，调用新增的运营人工收敛接口，记录已变为 `paid`，奖励已变为 `withdrawn`，并保存 `settlementSource=manual` 和核实备注。
- 生产后端已部署并重启 API、OCR worker、会话存档 worker；生产配置已补齐商家转账开关、场景 `1005`、回调地址、正式最低 `1000` 分和每日 1 次。健康检查、运行配置和运营提现列表均验证通过。
- 小程序推广中心已按“余额 → 规则 → 金额选择 → 提现记录”的任务顺序重排，增加最低 ¥10、¥10/¥50/¥200 选项，余额不足项置灰，提现/奖励时间统一格式化为中文年月日和时分，并放大规则、金额和记录字号。
- 本地定向回归 `28 passed`；Python 编译、前端 JS 语法、`app.json` JSON 解析和 `git diff --check` 通过。小程序体验版仍需负责人在微信开发者工具手动上传编译。

## 2026-08-25 AScript 本地小程序合并为统一九宫格

- 新增统一入口 `automation/ascript/__init__.py` 和 `res/ui/launcher.html`，将小红书找群、加群、扫描微信群、微信群库、群营销、微信账号、设备状态、任务日志、设置收敛到一个九宫格入口。
- 通过 AScript 官方项目管理接口逐个删除了诊断探针和重复正式项目；手机端当前只保留 `资料整理助手` 这一项目入口，以及原有的 `test`、`kuaishou_assistant` 两个非本项目工程。
- “资料整理助手”项目已核对包含九宫格页面和已合并的功能模块；本轮没有发送微信消息、没有部署后端，也没有上传小程序体验版。
- 自动 `deploy_and_run` 时 WebWindow 未能在当前微信前台画面中被截图确认，因此九宫格仍需用户从 AScript“本地小程序”手动打开并确认视觉和点击链路。

## 2026-08-25 AScript 九宫格前台启动问题定位

- 在 nubia NX711J / Android 15 / AScript 4.0.03 上验证：`WebWindow` 的 `mode(3)`、`mode(-1)`、`Dialog.alert` 和 `Canvas` 在“本地小程序”后台启动上下文中都不能把 UI 带到前台；脚本接口返回成功不等于用户看得到窗口。
- 同一设备用默认 Activity 模式 `mode(0)` 加已确认存在的 HTML 资源路径可以显示九宫格，证明 HTML 内容和设备权限不是根因；但通过 `run_project` 从 AScript 宿主启动时仍停留在宿主页面，根因是本地后台运行上下文不提供前台 Activity。
- 统一入口已改为 Activity 模式，页面桥接改用官方 `window.airscript.call(...)`；资源路径保留官方 `R.ui/R.res` 优先和当前设备路径兜底，便于后续独立 APK 打包。未发送微信消息、未部署后端、未上传小程序体验版。
- 已删除一个确认属于正式项目的 URL 编码重复工程；当前设备本地项目为 `资料整理助手`、`test`、`kuaishou_assistant`，后两者未改动。

## 2026-08-26 AScript 单项目九宫格前台调试继续

- 用户确认最终形态是“一个 AScript 本地小程序 + 一个九宫格 UI”，九个宫格分别进入一个功能；本轮不打包 APK，也不拆成多个 teamBuy 小程序。
- 复核发现固定 `WebWindow(id=10301)` 会在 AScript 4.0.03 重用历史窗口状态，导致入口脚本运行但宿主列表仍在前台。入口已改为每次启动生成短生命周期窗口 ID，并使用已验证存在的设备 HTML 路径优先。
- 通过设备主进程直接启动同一份 `__init__.py` 已显示完整九宫格；通过同一 `WebWindow` 实例和 `WebSelector` 点击“微信群库”已收到 `feature=wechat_group_library` 回调，证明 HTML 和点击桥可用。
- `run_project` 接口仍只证明脚本进入运行态，当前 AScript 本地项目列表启动上下文仍停留在宿主页面；尚未把该接口结果当作视觉验收通过。没有发送微信消息、没有部署后端、没有上传小程序体验版。

### 下一步最小执行顺序

1. 用户在 AScript“本地小程序”中手动点 `资料整理助手` 的绿色运行按钮，确认九宫格前台出现；如仍停留列表，回传截图，继续定位宿主版本的前台切换。
2. 九宫格出现后，先点击“微信群库”做无副作用安全验收，再逐个核对九个入口的文案和返回行为。
3. 入口验收通过后，再继续群扫描/PC 入库和佛山宠物群单群单卡发送，不提前触发真实微信发送。

- 对抗式复核补齐了页面关闭释放：`pagehide` 回传 `window_closed`，设备状态入口也统一在后台线程完成后释放等待；避免返回桌面后留下无感后台脚本。
- 本轮静态检查通过，后端定向自动化控制测试使用 Python 3.13 环境为 `12 passed`；系统默认 Python 过低导致的旧虚拟环境导入错误未作为代码问题处理。

## 2026-08-26 AScript 九宫格功能加载与返回修复

- 用户截图中的 `No module named xhs_find_group` 根因是统一入口使用顶层模块名加载项目子目录；AScript 运行时没有把功能目录注册为顶层 import 路径。
- 入口改为按当前项目目录用 `importlib.util.spec_from_file_location()` 加载合成功能包，保留子模块搜索路径，兼容功能目录内的相对导入。
- 功能 WebWindow 关闭后，入口现在区分“为执行功能主动关闭”和“用户返回关闭”；功能结束或异常提示关闭后会重新显示九宫格，不再把用户留在 Android 桌面。
- 已上传统一入口文件到手机；设备回归确认“微信群库”提示关闭后能回到九宫格，“小红书找群”不再报模块不存在。由于 ESP32 插件仍报 `bad magic number`，本轮未执行真实小红书搜索、入群或群消息发送。

## 2026-08-26 AScript 运行模式说明与九宫格退出修复

- 核对当前微信模块：群扫描和账号识别会优先尝试 ESP32，插件失败时只读流程可 fallback 到 AScript 输入；群营销发送不允许 fallback。
- 明确 AScript 页面“运行模式：HID 控件模式”不是 ESP32 插件成功证明；当前仍以 `BleDevice` 导入和连接结果作为 ESP32 实际使用标准。
- 统一入口增加“退出九宫格”按钮，并在收到退出事件后主动关闭 WebWindow。设备实测点击按钮后已退出九宫格回到系统界面。

## 2026-08-26 暂停 ESP32，统一切换 AScript 原生输入

- 按负责人决定，当前开发主链路不再加载 ESP32 插件；小红书找群、双微信账号识别和微信群只读扫描统一使用 AScript 的控件树、OCR、`action.click`、`action.swipe`、`action.input` 和原生按键。
- 统一九宫格的“设备状态”改为展示当前输入模式，不再尝试导入 `esp32:4.7.0`；设备心跳改为记录 `inputMode=ascript_native`，不再伪报 ESP32 HID 设备。
- 群营销任务不再因 ESP32 插件缺失而提前退出，但实际小程序卡片发送仍保留“发送 UI 尚未完成设备验收”门禁，不会因为切换输入方式而误报成功或执行群发。
- 本轮只改输入适配和状态元数据，没有新增后端接口、没有部署后端、没有发送微信消息、没有上传小程序体验版。

## 2026-08-26 客户雷达支付入口按最新状态路由

- 生产环境核对结果：客户信息链 `enabled=true`，微信支付开关 `paymentRequired=true`；用户截图中的“客户信息暂时无法读取，请重试”不是预期的支付引导，而是雷达页在加载期间被页面旧状态拦截。
- 小程序 `miniprogram/pages/visits/index.js` 已调整：雷达指标、锁定态按钮和客户卡片点击时强制读取最新会员/运营开关；收费模式进入 `/pages/membership/index`，免支付模式刷新客户雷达，具体卡片再进入客户详情，客户信息链关闭时显示明确的未开启状态。
- `miniprogram/pages/visits/index.wxml` 已补齐“客户信息链暂未开启”状态，并把锁定态按钮改为按状态显示“去支付查看/继续查看”，不再因为加载中的本地状态提示“请重试”。
- 验证：`node --check miniprogram/pages/visits/index.js`、小程序 JSON 解析、`git diff --check` 通过；相关后端回归共 `32 passed`。本轮未改后端，不需要重启生产服务；待用户在微信开发者工具上传体验版后做真机验收。

## 2026-08-26 运营总览指标详情与时间标签

- PC 运营总览的指标卡已改为可点击卡片：周期指标显示“今日 / 近 7 日 / 近 30 日”，实时队列指标显示“当前”，并在总览标题旁显示精确统计区间。
- 新增管理员接口 `/api/ops-admin/overview-detail?metric=...&period=...`，返回指标定义、统计区间、总数和最多 100 条明细；用户、资料、合集、客户动作、展示页打开、匿名访客、通知、会员和支付收入均可展开查看时间、对象、具体数据与状态。
- 匿名访客明细继续只显示“匿名访客”，不返回匿名标识；接口沿用 `X-Admin-Token` 校验。
- 验证：运营后台内嵌 JavaScript 语法、Python 编译、`git diff --check` 通过；运营总览、客户信息链和明细接口测试 `5 passed`。已部署生产并重启 backend；备份位于服务器 `/home/ubuntu/teamBuy-deploy-backups/20260826-122159-ops-overview-details/`，公网 `/health`、`/ops` 和明细接口验证通过。

## 2026-08-26 运营明细补充登录身份与昵称状态

- 新增用户明细不再把默认昵称“微信用户”当作真实用户名：有主动设置的昵称时显示昵称，没有设置时显示“微信用户（未设置昵称）”，并在具体数据中标注“登录身份：已登录”和用户 ID。
- 客户动作、展示页打开等访客明细区分“匿名访客（未登录）”与已登录用户；匿名事件没有可安全反查的真实用户名，不根据匿名标识或昵称相似度猜测身份。
- 已通过相关后端测试 `5 passed`、Python 编译和 `git diff --check`；已部署生产并重建 backend，公网验证新增用户接口返回“微信用户（未设置昵称）/已登录/未设置昵称”。
- 本轮生产备份位于 `/home/ubuntu/teamBuy-deploy-backups/20260826-123458-ops-identity-labels/`，未修改生产 `.env`、secrets、媒体或数据库。

## 2026-08-26 资料编辑进入运营更新明细

- 根因确认：资料保存接口会更新 `UserNote.updatedAt`，但运营总览原先只有“新增资料”，统计和明细均按 `createdAt`，历史资料编辑后不会进入当天明细，也不会排到第一行。
- 新增独立“资料更新”指标，只有 `updatedAt > createdAt` 的资料才计入，按 `updatedAt` 倒序；“新增资料”继续保持 `createdAt` 口径，避免把编辑误算成新建。
- 生产验证通过：`/api/ops-admin/overview-detail?metric=updatedNotes&period=today` 返回 5 条，第一条时间为最新编辑时间，运营页面已出现“资料更新”卡片。
- 本地相关测试 `5 passed`，后台 JavaScript 语法检查、Python 编译和 `git diff --check` 通过；生产备份位于 `/home/ubuntu/teamBuy-deploy-backups/20260826-125950-ops-note-updates/`。

## 2026-08-26 用户端与微信群运营边界拆分

- 移除小程序 `note-edit` 中的“微信群营销匹配”面板、主题/地域/内容字段和对应输入处理；用户端仍保留资料编辑、发布、分享和用户自己的资料运营分析。
- 用户端 `/api/notes` 相关响应不再返回 `marketingRoute`；用户保存资料时不会创建或修改运营路由，后端会保留已有 PC 路由。
- PC 群自动化运营页新增管理员专用卡片路由保存接口和配置区：`PATCH /api/automation/marketing-cards/{note_id}/route`。卡片正文/分享图仍来自资料端，营销路由只在 PC 运营端维护。
- 审查确认小程序没有调用 `/api/automation/*`；微信群资源库是独立的用户资源功能，资料运营是用户自己的数据分析入口，均未误删。
- 验证：AScript/小程序相关 JS、运营后台内嵌 JS、Python、JSON 和 `git diff --check` 通过；自动化控制测试 `12 passed`。`test_app.py` 其余测试通过，但分享统计测试 `test_note_preview_view_updates_note_list_stats` 单独失败，目前未能证明由本次字段隔离引入，需后续单独定位。

## 2026-08-26 统一客户页沟通区与服务页改造

- 小程序客户预览页新增统一“方便沟通”区，覆盖服务/合作、房源、商品、文章、图文、图片和文字资料；电话、微信、站内留言、留下需求、预约和邮箱按当前资料能力展示。
- 服务/合作页改为“主张—发布者—服务对象/范围/合作方式—详细内容—图片资料—沟通”的结构；保留场景化字段，不再为行业拆分独立系统。
- 房源保留相册、房源字段、地图定位和预约看房；统一沟通区负责基础联系，地图等场景动作继续独立展示。
- 预约时间动作已收敛为房源专属“预约看房”；服务/合作和普通资料不再默认出现预约入口。商品编辑器保存旧资料时会补齐电话、轻 CRM、留资和微信咨询四项基础沟通能力。
- 普通资料的新默认转换配置开启电话、微信、留言和线索入口；后台公开资料读取时先补齐稀疏配置，避免旧资料因缺少默认配置而没有客户入口。
- 验证：三个小程序 JS、两个后端 Python 文件语法检查通过，WXML 标签嵌套检查通过，统一动作生成检查通过，`git diff --check` 通过。当前机器的 `pytest` 虚拟环境为 Python 3.9，而项目使用 `dataclass(slots=True)`，后端测试无法启动；未部署生产、未上传微信体验版。

## 2026-08-26 统一客户页后端生产部署

- 生产服务器 `/home/ubuntu/teamBuy` 已同步 `backend/app/services/app_service.py` 和 `backend/app/services/skill_router_service.py`，用于开放普通资料基础沟通默认配置并支持历史商品保存后的统一沟通能力。
- 生产使用 `docker-compose.production-runtime.yml` 的源码挂载模式，本轮未重建镜像；API、OCR worker、归档 worker 已全部重启，Postgres、`.env`、secrets、媒体目录和数据库未修改。
- 部署前备份位于 `/home/ubuntu/teamBuy-deploy-backups/20260826-142054-customer-page/`。
- 验证：两个文件生产 SHA256 与本地一致，三个容器运行正常，worker 无导入/数据库错误，公网 `/health` 返回 200。小程序前端仍需用户上传当前体验版。

## 2026-08-26 服务资料保存清理旧正文块

- 根因确认：服务/合作编辑器此前只更新 `body`，没有覆盖 `contentBlocks`；发布安全校验仍会扫描旧导入正文中的手机号，因此即使编辑框里删除号码，仍可能提示“资料正文含有未确认的手机号”。
- 服务编辑器现在显式提交当前正文和媒体 `contentBlocks`，并增加可单独执行的“保存”按钮；后端对 `service_offer` 未传 `contentBlocks` 时也按当前正文重建，作为兼容兜底。
- 第二次生产备份位于 `/home/ubuntu/teamBuy-deploy-backups/20260826-143541-service-contentblocks-fix/`；生产 backend、backend-worker、archive-worker 已重启，公网 `/health` 返回 200。
- 本地静态检查通过：服务编辑器 JS、后端 Python、服务编辑器 WXML 标签嵌套和 `git diff --check`。

## 2026-08-26 旧资源详情入口统一跳转客户页

- 复查发现历史记录、旧分享链接和部分旧资源入口仍可能进入 `pages/card-view`；该页是旧版资源详情模板，因此文字/图文资料会看起来没有更新。
- 该阶段先用旧页面转发到统一的 `pages/note-preview/index`，作为删除前的过渡验证；旧资源详情页再次分享时也改用 `note-preview` 路径。

## 2026-08-26 删除旧 card-view 页面并解析历史卡片 ID

- 按负责人决定删除 `miniprogram/pages/card-view/`，从 `app.json` 移除页面，不再让旧资源详情页作为可访问路由。
- 所有小程序入口已改为 `note-preview`；导入通知的结果路径、历史记录、资料运营和旧卡片编辑发布后的查看路径不再生成 `card-view`。
- 后端 `get_public_note` 支持把历史 Card ID 解析为对应的已发布 Note，承接旧链接但不恢复旧页面。
- 本地小程序 JS、后端 Python、`app.json` 和 `git diff --check` 已通过；后端需部署后再做公网旧 Card ID 验证。

## 2026-08-26 资料页主体点击改为客户预览

- 复查发现“资料”页卡片主体的 `handleView` 实际调用编辑路由，用户点击文字/图片资料时会进入编辑器，容易误判为客户页仍是旧代码；右侧“完善”按钮已经承担编辑职责。
- 资料页卡片主体现在调用 `navigateToResourceView`，标准资料进入统一 `pages/note-preview/index`；编辑入口仍由“完善”或编辑字段操作负责。
- 该阶段的兼容页已删除；无标准来源的纯旧 Card 不再进入客户页主链路。

## 2026-08-26 修复资料页预览函数未引入

- 资料页主体改用 `navigateToResourceView` 后发现顶部解构遗漏该函数；真机点击会因函数未定义而无法跳转。
- 已补齐引入并通过 Node 语法检查；本次仍只需重新上传小程序，后端无需部署。

## 2026-08-26 清理资源导航旧路由兜底

- 复查通用资源导航后发现，虽然显式入口已改为客户页，但无 `sourceNoteId` 的历史 Card 仍可能通过动态兜底拼出旧详情地址。
- 查看兜底现在统一进入 `/pages/note-preview/index`，编辑兜底统一进入工作台 `card-edit`；不再生成旧资源详情路由。
- 已完成小程序 JS 语法、`app.json` 路由和差异检查；后端公开接口仍需随本轮部署后验证历史 Card ID。

## 2026-08-26 体验版仍显示旧客户页的根因确认

- 用户截图实际进入的是 `note-preview`，不是已删除的 `card-view`；但截图中的“咨询这份资料”不在当前源码中，当前源码对应的是“方便沟通”区。
- 因此问题不是生产后端或路由删除未生效，而是微信端仍运行旧体验包/缓存版本；后端部署不能替换小程序 WXML/WXSS。
- 已确认唯一工程根目录为 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram`，并通过源码标记和旧路由搜索检查；需在微信开发者工具重新编译、上传并选择最新体验版。

## 2026-08-26 客户页留下需求表单与沟通区层级调整

- 根因确认：文字、图片、服务等新客户页分支只有“留下需求”动作卡，没有对应表单节点；点击会切换状态但页面没有可显示内容。
- 现在由客户页统一渲染留下需求表单，包含称呼、手机号、微信号和需求备注；点击入口后自动滚动到表单，提交成功后收起并显示结果。
- 统一沟通区改为“标题 → 两列入口 → 底部立即咨询”，适用于服务、文章、图文、图片、文字、房源和商品等公开资料。
- 验证：预览页 JS 语法、WXML 标签嵌套、`git diff --check` 已通过；小程序前端需重新上传体验版后真机验收。

## 2026-08-26 修复无主图资料发送时截取资料库页面

- 根因确认：资料库对无主图非名片资料使用 `direct` 状态，但最终分享对象没有 `imageUrl`；微信因此自动截取当前资料库页面作为聊天卡片缩略图。
- 分享插件现在只对有真实主图的非名片使用原图直出；无主图资料统一进入插件内部 `resource_default` 信息卡，绘制真实资料类型、标题、摘要和字段并保存当前版本快照。
- 所有资料发送仍共用 `share-snapshot` 插件和客户页路径；页面不新增 Canvas 绘制逻辑。分享样式版本升级为 `share_card_v6`，旧快照不再作为当前版本复用。
- 同步修正通用分享入口的无封面分支，避免其他资料分享流程也返回无图原生卡片。本轮未部署后端，需重新上传小程序体验版。
- 验证：分享插件、统一渲染器、资料库、客户预览页和通用分享 JS 语法检查通过；无主图状态回归、WXML 标签检查和 `git diff --check` 通过，仍需微信真机验证最终缩略图。

## 2026-08-26 留下需求表单视觉层级优化

- 表单改为浅草绿色渐变信息卡，使用深绿色标题、联系信息提示条和带标签的输入区域，解决原先白色表单与页面背景边界不清的问题。
- 手机号与微信号继续保持“至少填写一项”的业务校验；新增“仅用于本次联系，不会公开展示”提示，不改变提交接口和数据规则。
- 提交按钮改为绿色，与蓝色“立即咨询”形成动作层级区分；本轮只修改小程序客户预览页 WXML/WXSS，未部署后端。
- 验证：预览页 JS、WXML 相关结构、后端 Python、资源导航 JS 和 `git diff --check` 通过；仍需重新上传体验版并在真机检查颜色、字号和输入状态。

## 2026-08-26 复制内容手机号分拣与发布入口修复

- 根因确认：复制/导入的正文可能同时包含发布者电话、上游电话和第三方电话；原逻辑只有后端发布安全拦截，没有候选识别、归属选择和正文清理界面，所以服务编辑页与资料库都只能弹出“未确认的手机号”。
- 新增共享 `miniprogram/utils/contact-review.js`：提取多个手机号、脱敏展示、保留未处理状态，并支持从公开字段移出号码。
- 服务/合作编辑器和普通文字资料编辑器新增手机号分拣面板：每个号码可选择“公开电话”“仅自己保存”“移出正文”；未处理号码允许保存草稿，但发布前会定位到处理面板并阻止发布。
- 资料库“发客户/重新发布”遇到该安全拦截时，改为显示可解释的“去处理”确认并进入对应编辑器，不再只显示无行动路径的 toast。
- 服务资料保存不再固定发送 `phone: null` 或清空 `privateData`；已确认公开电话写入 `note.phone`，私密号码写入私密配置，公开正文只保留已确认内容。
- 验证：手机号工具行为回归、相关小程序 JS 语法检查和 `git diff --check` 通过；尚未在微信开发者工具/真机上验证按钮点击与最终发布，需要重新上传体验版。

## 2026-08-26 名片与合集接入统一客户沟通组件

- 新增 `miniprogram/components/customer-communication/`，把电话、微信、留言、留需求、邮箱和分享的展示结构收敛为一个可复用组件，资料详情页的八类分支统一引用。
- 名片移除旧的独立动作栏，接入电话、微信、邮箱、留言、留需求和分享；名片编辑保存与后端默认配置开启 `collectLeads`，并对历史名片做客户页展示兼容。
- 合集页移除各模板重复的电话/微信按钮，统一放到模板内容之后；合集层只承担有明确归属的电话、微信、分享，留言和留需求引导到具体资料详情页。
- 验证：相关 JS、JSON、Python 编译、目标结构断言和名片/客户动作回归 5 passed；后端仍需部署，小程序仍需重新上传体验版后做真机验收。

## 2026-08-26 客户详情页动作层级与暂不跟进

- 根因确认：客户详情页的联系方式采用可收缩主区域加自然宽度按钮，窄屏下按钮挤压了手机号，导致号码逐字竖排；中段和固定底部还重复提供“联系客户”，造成动作区拥挤和视觉层级混乱。
- 客户详情页调整为“身份判断 → 可联系渠道 → 下一步判断 → 跟进记录/资料证据”的顺序；中段只保留复制话术和资料对比，联系客户统一收口到固定底部主按钮。
- 固定底部改为两个等宽主动作“记录跟进/联系客户”，下方增加低强调“暂不跟进”；该动作复用后端已有 `paused` 状态，保留客户资料、浏览记录和操作记录，不直接物理删除。已暂停、无效或完成的记录可从同一位置恢复到待跟进。
- 无跟进记录时，“暂不跟进”会先建立当前客户的跟进档案，再立即标记为暂停，保证用户的放弃决定可追溯；本轮不需要后端部署。
- 验证：客户详情页 JS/API 语法、JSON 解析和 `git diff --check` 通过；仍需重新上传小程序体验版并在真机检查底部安全区、手机号横向显示及暂停/恢复交互。

## 2026-08-26 客户详情页直接放弃跟进

- 按用户确认，固定底部改为两个等宽动作：“记录跟进/开始跟进”和浅橙色“放弃跟进”；不再展示“联系客户”，也不弹确认框。
- 点击“放弃跟进”复用现有跟进接口，将记录置为 `paused`，写入“放弃跟进”和操作日志，保留客户详情、浏览轨迹和跟进记录；成功后返回客户雷达，因此该客户不会继续出现在当前待跟进页。
- 后端雷达组装增加关闭状态过滤：`paused`、`invalid`、`completed` 的客户从画像、机会提醒、内容洞察中移除，但不从客户详情和历史记录中删除；恢复操作仍可把记录置回 `pending`。
- 同步修正客户详情接口的暂停状态文案为“已放弃跟进”。
- 验证：`test_sales_scrm.py` 16 passed，线索状态回归 1 passed，客户详情 JS 语法和后端 Python 编译通过；仍需重新上传小程序体验版做真机点击验收。

## 2026-08-26 客户详情放弃跟进后端部署

- 已将当前 `backend/app` 同步到生产 `/home/ubuntu/teamBuy/backend/app`，未覆盖生产 `backend/.env`、`backend/secrets/`、数据库和媒体卷。
- 生产实际使用 `docker-compose.production-runtime.yml`，后端监听 `127.0.0.1:8004`，由 `teambuy.lifelove.top` 的 `/api/` 转发；API、OCR worker、归档 worker 已重启并正常运行。
- 已验证本地与生产 `app_service.py` SHA256 一致，公网 `/health` 返回 Postgres 已配置且正常；业务接口未携带生产登录令牌时返回 401，未继续读取生产会话。
- 部署前备份：`/home/ubuntu/teamBuy/.deploy-backups/customer-detail-abandon-20260826-213938/backend-app.tar.gz`。

## 2026-08-26 客户详情仍显示旧“联系客户”的根因确认

- 复查当前工程后确认，客户详情唯一正式路由是 `/pages/customer-detail/index`；雷达、客户列表、线索列表、消息和运营入口均已指向该路由，`lead-detail` 与 `card-view` 均不存在于当前 `app.json` 路由。
- 当前客户详情 WXML 底部只有“记录跟进/开始跟进”和“放弃跟进”，没有“联系客户”按钮；本次仅清理了客户详情中未使用的旧联系方法和相关旧提示文案。
- 用户在 21:48 看到的“联系客户”来自微信端尚未上传本轮小程序前端的旧体验包，不是生产后端路由或当前源码仍在兜底。后端部署不能替换已安装的 WXML/WXSS/JS。

## 2026-08-26 修复放弃跟进后的雷达返回

- 根因确认：`/pages/visits/index` 是 TabBar 页面，放弃成功后错误使用 `wx.redirectTo`，导致状态已保存但仍停留在客户详情。
- 已将放弃成功后的跳转改为 `wx.switchTab({ url: "/pages/visits/index" })`，并同步修正客户详情错误页的“返回客户雷达”入口；放弃成功后直接离开详情页。
- 本轮只修改小程序前端，不需要重新部署后端；需要重新编译上传体验版才能验证真机行为。

## 2026-08-26：雷达客户处理动作统一出队与单请求优化

- 根因确认：原“开始/继续跟进”只建立 `pending` 档案，因此客户仍留在待跟进和访客列表；原“放弃跟进”在无档案客户上需要先 ensure 再 update，两次请求造成明显等待。
- 现在“开始/继续跟进”写入 `contacted`，“放弃跟进”写入 `paused`；两种动作都保留客户详情、来源资料、联系方式和历史，仅从雷达两个工作列表移除。
- 新增 `/api/scrm/customer-followups/action`，首次动作可直接创建目标状态，已有档案在同一请求内完成状态迁移；小程序成功后清理雷达缓存并用 `wx.switchTab` 返回雷达。
- 雷达前端不再用本地资料缓存的旧访客拼 fallback 卡片；工作列表只使用服务端已经过滤过的 `radarProfiles`/`opportunityAlerts`，避免已处理客户被旧缓存重新显示。
- 生产已同步 `backend/app` 并重启 API、OCR worker、归档 worker；备份为 `/home/ubuntu/teamBuy/.deploy-backups/customer-followup-inbox-20260826-223420/backend-app.tar.gz`。
- 验证：SCRM 回归 `16 passed`，客户信息链回归 `1 passed`；全量后端 `290 passed, 1 failed`，唯一失败为既有资料分享统计测试，与本次无关。公网 `/health` 正常，新动作接口未授权请求返回 `401`，说明生产鉴权链已生效。

## 2026-08-26：客户雷达高保真工作台 V3

- 雷达页按“待跟进 / 活跃访客 / 已放弃”重排，顶部三项数字直接由当前三组客户卡派生；处理状态不再和资料优化混在同一套页签里。
- 客户卡统一展示客户身份、最近行为、客户实际看到的内容和原资料入口；移除“查看资料 / 复制首句”等低价值动作，保留“处理情况 / 放弃跟进”两个主操作。
- 后端增加 `abandonedProfiles` 和 `restore` 动作；“清空删除”改为 `deleted` tombstone，既不占用回收站，也不会因历史浏览事件重新召回客户。
- 小程序采用内存快照优先渲染和乐观出队，放弃、恢复、清空不等待整页刷新；本页不再预加载未使用的提醒配置。
- 本轮尚未部署生产或上传体验版；高保真效果验收需重新编译 `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram` 后在微信开发者工具真机检查。

## 2026-08-27：客户详情页按高保真稿重构

- 客户详情页展示顺序调整为“客户身份 → 客户刚刚看了什么 → 下一步怎么做 → 可联系渠道 → 最近动态 / 相关资料”。
- 客户刚刚看了什么使用详情接口返回的首条真实资料，来源标题、查看次数和资料跳转不再固定到某个房源；如果资料有封面则按需展示，没有封面使用资料类型占位。
- 最近动态和相关资料改为同一卡片内的两个默认折叠行，点击标题行展开；箭头只做方向反馈，不对首屏发起额外请求。
- 移除详情页首屏的跟进表单、重点标签和完整资料列表，保留原有处理逻辑；底部统一为左侧浅橙色“放弃跟进”、右侧蓝色“开始/继续跟进”。
- 联系渠道按钮按语义区分：电话可拨打和复制，微信号只复制微信号；固定宽度和 nowrap 防止手机号再次竖排变形。
- 本轮未部署生产；等待客户详情页与雷达页一起完成体验版真机验收。

## 2026-08-27：雷达来源资料与客户详情性能修复

- 根因确认：雷达卡片展示的是客户实际看过的 canonical `noteId`，但原“原资料”入口复用了 Card 导航，先请求 `/api/cards/<noteId>`，因此资料 ID 被误判为 Card ID 而打不开。
- 雷达和客户详情的来源资料入口现在统一调用 `navigateToNoteView(noteId)`，直接进入 `/pages/note-preview/index`；雷达画像不再把 `resourceId` 或 `showcaseId` 误作为资料预览 ID。
- 客户详情新增短时进程内 `customer-detail-store`：优先复用雷达已经读取的客户画像、来源资料、行为时间和联系方式，先绘制详情，再后台请求服务端校准；不写 `wx` 持久化存储，缓存按环境、拥有者、场景、客户和线索隔离，会员快照过期立即丢弃。
- 客户详情加载增加请求序列和卸载保护，旧客户、旧账号或晚到的后台刷新不能覆盖当前页面；跟进动作成功后同时清理雷达和详情缓存。
- “开始/继续跟进”允许只有 `leadId` 的客户详情入口继续执行，不再无提示地提前返回；执行成功后有反馈并返回雷达。详情页和雷达卡片的放弃/恢复动作均统一为右侧按钮。
- 雷达回到前台时，如果情报缓存已因跟进动作失效，先清掉旧卡片再刷新，避免已处理客户短暂复现。
- 验证：小程序相关 JS 语法、页面 JSON、`git diff --check`、资源路由/缓存隔离/按钮顺序断言通过；`backend/tests/test_sales_scrm.py` 为 16 passed。本轮未部署生产，仍需重新上传体验版做真机冷启动、热路径和实际资料点击验收。

## 2026-08-27：全链路缓存审计、修复与生产后端部署

- 审计范围：资料/合集/专题/资源列表、客户雷达和客户详情、手机号与微信号草稿、匿名访客标识、媒体文件缓存，以及后端 API/媒体响应缓存。
- 客户端修复：列表元数据 TTL 统一为 60 秒（分类 10 分钟），内存缓存优先、后台刷新并合并重复请求；wx 持久化写入改为异步，退出登录和会话过期会清理用户资源、媒体和接口缓存。
- 敏感数据边界：客户详情、手机号、微信号、客户身份和雷达详情继续只允许短时进程内缓存，不写入 wx 持久化存储；联系方式草稿改为内存变量，房源城市等非敏感偏好才按用户/环境隔离保存。
- 媒体缓存修复：缓存键包含环境、API 地址、媒体前缀和用户身份；只缓存 HTTPS 图片，PDF/视频不落本地媒体缓存；增加 7 天 TTL、80 个文件、32 MB 总量、单资料最多 3 张，以及账号切换时的代际保护和清理。
- 服务端修复：资料/合集相关列表缓存 TTL 降为 60 秒；发布、复制、删除分类、浏览/互动记录写入后失效相关列表缓存；API 和健康检查返回 no-store，媒体地址返回版本化长期缓存头。
- 生产部署：仅部署 backend/app/main.py 和 backend/app/services/app_service.py，先完成磁盘、Docker 空间和运行容器检查，备份保存于服务器 /home/ubuntu/teambuy-backups/cache-audit-20260827-050322；后端与 worker 重启后健康检查、公网响应头和源码 SHA256 校验通过。
- 验证：小程序相关 JS node --check、Python compileall、后端全量测试 293 passed、缓存契约测试包含在全量结果内、客户端缓存行为脚本通过；全仓 pytest 仍受历史 platform/wecom-archive-core/tests/test_engine.py 的 app.codec 导入问题阻塞。
- 发布边界：本轮生产只更新后端；小程序缓存逻辑需用户在微信开发者工具清缓存、重新编译并上传体验版后才会进入体验包。当前后端仍是进程内缓存，未来扩容多 API 进程时需补共享失效总线或 Redis。

## 2026-08-27：跟进状态与已放弃列表修复

- 生产兼容修复：`LeadReminderStatus` 和服务层状态白名单保留 `deleted`，已清空线索继续作为 tombstone 参与身份过滤，避免旧生产数据反序列化或状态更新时触发 500。
- 已放弃投影修复：`abandonedProfiles` 只允许与真实存在的 `paused` 线索档案按 `leadReminderId` 对齐，单独的历史浏览事件不会再伪造已放弃客户。
- 跟进状态落地：开始跟进将 `pending` 转为 `following`；继续跟进保持 `following`（兼容既有 `contacted`），每次动作追加明确的“已开始跟进/已继续跟进”记录。
- 雷达增加独立“跟进中”状态和动态数量；开始/继续跟进后客户从待跟进、访客工作列表移出，进入跟进中列表；详情页原地更新，不再误跳雷达。
- 雷达和详情的跟进摘要携带最近 5 条跟进记录，缓存首屏与后台刷新使用同一状态；放弃、恢复和跟进动作继续清理相关内存缓存。
- 验证：SCRM 与客户信息链回归 `20 passed`；Python 编译、相关小程序 JS 语法和 `git diff --check` 均通过。本轮未部署生产或上传体验版。

## 2026-08-27：跟进状态后端生产部署

- 生产部署内容：`domain.py`、`app_service.py`、`routes_ops_admin.py`、`routes_scrm.py`，未覆盖线上 `.env`、`secrets/`、媒体目录和数据库卷。
- 部署前检查：根分区可用约 31GB，Postgres healthy，Docker 空间正常；线上代码备份为 `/home/ubuntu/teambuy-backups/follow-up-status-20260827-063235`。
- 部署结果：API 绑定线上原端口 `8004`，backend、backend-worker、archive-worker 全部运行；本机和公网 `/health` 均返回 200，SCRM 业务路由探测返回 401（路由存在且鉴权生效）。
- 过程纠偏：首次使用 `sudo compose` 未显式传入原 `APP_PORT`，短暂绑定到 8000 并造成 Nginx 502；已立即用 `APP_PORT=8004` 重建 API 映射并确认公网恢复，后续部署必须显式保留该参数。
- 小程序前端未随本次后端部署更新；用户仍需清缓存、重新编译并上传体验版，才能看到“跟进中”页签和客户详情原地反馈。

## 2026-08-27：跟进状态、详情缓存与留言链路统一收口

- 跟进动作改为服务端原子提交：`operationId` 防重复，`expectedVersion` 防并发覆盖，提交后回读确认；雷达提醒卡片也携带 `leadVersion` 和最近跟进日志。
- 雷达、跟进中、已放弃的动作请求统一带线索版本；客户端乐观出队只做即时反馈，超时或未知结果不使用旧列表复活客户。
- 情报缓存补齐真正的 stale-while-revalidate；强制刷新会绕过缓存，旧请求不能清理新请求或覆盖新结果。
- 客户详情带 `leadId` 时走轻量详情热路径，浏览/动作只读取当前身份最近 50 条；留言摘要只做精确登录身份关联，匿名访客不自动串线。
- 本轮完成后端全量 293 项、SCRM 16 项、JS/JSON/差异检查和页面对象级连续点击、超时、冷启动、重进回归。
- 本轮未部署生产、未上传微信体验版；真实微信网络、真机截图和生产 Postgres 并发烟测仍需人工完成。

详细报告：`docs/qa/客户跟进状态与客户详情_Codex自测报告.md`、`docs/qa/客户跟进状态与客户详情_对抗式审查报告.md`、`docs/qa/客户跟进状态与客户详情_复测与回归报告.md`。

## 2026-08-27：统一收口版本重新部署生产

- 发布前确认线上实际运行的 Compose 配置为 `/home/ubuntu/teamBuy/docker-compose.yml`，容器未绑定本地源码；因此采用重建镜像并只重建 `backend`、`backend-worker`、`archive-worker` 的方式使代码生效。
- 发布前检查根分区可用约 27GB，未执行任何清理；线上 `.env`、`secrets/`、数据库和媒体卷未覆盖。
- 线上源码备份：`/home/ubuntu/teambuy-backups/followup-unified-20260827-104106/backend/app/`；更新的 5 个后端文件已与本地 SHA256 对齐。
- 发布结果：`backend`、`backend-worker`、`archive-worker` 新容器正常运行，Postgres healthy，API 保持 `8004` 端口映射；容器内定向 `py_compile` 通过。
- 公网验证：本机和 `https://teambuy.lifelove.top/health` 返回 200；`/api/scrm/customer-intelligence` 未登录返回 401，路由存在且鉴权生效；启动日志无导入错误。
- 体验版边界：本次只重新部署后端，微信体验版仍需在开发者工具清缓存、重新编译并上传最新 `miniprogram/`，否则仍会运行旧前端包。

## 2026-08-27：体验版状态不一致的生产诊断

- 用户反馈体验版测试后仍显示错误、怀疑跟进数据未进入数据库。
- 生产证据：重建容器后 Postgres 中仍存在最新 `following` 和 `paused` 线索；对应接口日志显示 `POST /api/scrm/customer-followups/action` 返回 200，说明服务端原子写入链路已执行并持久化。
- 当前最小解释：后端发布不会替换微信体验包；若体验版未重新清缓存、编译、上传，仍会执行旧前端逻辑，可能不发送新动作接口或继续读取旧投影。若重新上传后仍异常，再按测试时间核对请求中的 `ownerUserId/customerId/leadId/expectedVersion` 与数据库记录。
- 本次未修改数据库、不做数据修复；下一次人工复测必须先确认体验包上传时间和版本号，再验证动作请求与页面重进结果。

## 2026-08-27：房源雷达状态投影修复并重新部署

- 根因：房源模式的雷达看板只用 `note.id` 匹配 `LeadReminder.cardId`，而导入资料的线索保存的是资料的 `sourceCardId`；数据库中的 `following/paused` 已正确写入，但看板组装阶段把这些线索过滤掉，所以顶部数字和状态页签回退。
- 修复：房源雷达和客户详情统一使用“资料 ID + `sourceCardId`”作为来源匹配集合；新增回归用例覆盖无 `CustomerAction` 投影、仅凭来源卡片 ID仍能进入“跟进中/已放弃”的情况。
- 本地验证：房源来源卡片回归、房源看板和客户雷达相关测试通过；`backend/tests/test_sales_scrm.py` 全部 17 项通过，定向语法检查和 `git diff --check` 通过。
- 生产发布：线上备份为 `/home/ubuntu/teambuy-backups/property-radar-source-20260827-112556/backend/app/services/app_service.py`；重建 `backend`、`backend-worker`、`archive-worker`，未修改生产 `.env`、密钥、Postgres 或媒体数据。容器内源码 SHA256 为 `f6eeabad771e4150a2faf86ef142996d9ebf123a623b9d6c14581726ed4def74`。
- 线上验证：三个服务正常运行，Postgres healthy，本机和公网 `/health` 均 200，SCRM 情报接口未登录按预期返回 401，容器内 `py_compile` 通过。

## 2026-08-27：清理雷达待跟进旧兜底

- 11:53/11:55 真机截图中的“待跟进 5”不是数据库状态回退：生产情报接口当时 `opportunityAlerts=0`，但小程序仍执行 `alerts.length ? alerts : profiles.slice(0, 5)`，把普通活跃访客画像伪装成待跟进卡片。
- 已删除该旧兜底。雷达“待跟进”现在只渲染服务端明确生成的 `opportunityAlerts`；没有可处理信号时显示空态，不再从 `radarProfiles` 补卡。
- 未删除 `/api/scrm/customer-intelligence` 或其路由；该接口仍负责返回当前四类投影、状态和客户详情所需数据，删除它会破坏新雷达链路。
- 本轮验证：`node --check miniprogram/pages/visits/index.js`、`git diff --check` 通过。该修复属于小程序前端，需重新清缓存、编译并上传体验版后才会在微信端生效。

## 2026-08-27：客户详情跟进表单与动作回雷达热路径

- 客户详情补回实际跟进区：展示系统识别标签、可选跟进标签、备注、下次跟进日期和最近 5 条跟进记录；标签通过已有 `LeadReminder.customerTags` 保存，不新增重复数据模型。
- 雷达“跟进中”卡片补显示标签；待跟进、访客、跟进中进入详情时显式携带来源页签，详情动作成功后写入轻量页签偏好并返回原页签。
- 开始/继续/放弃动作只等待一次服务端原子接口；服务端成功确认后清理情报/详情缓存并立即切回雷达，不再在详情页二次读取完整客户投影。未知结果仍只走一次对账读取，避免误报成功。
- 雷达已有解锁情报缓存时直接标记访问允许，避免点击详情时重复等待会员检查；会员和详情接口仍是最终权限边界。
- 本地验证：客户详情与雷达 JS `node --check`、后端 `test_sales_scrm.py`（17 passed）、`git diff --check` 通过。仍需微信开发者工具清缓存、重新编译并上传体验版做真机动作、页签和表单保存验收。

## 2026-08-27：生产跟进中 500 与访客状态重复修复

- 线上 500 的直接原因已确认：生产 PostgreSQL 的 `view_events` 缺少当前详情热路径查询所需的 `visitor_identity_id` 字段；不是客户详情页本身的路由或跟进标签问题。
- 后端补齐正式 schema、动态初始化字段和查询索引，生产重启时执行 `ADD COLUMN IF NOT EXISTS`，不改动 `.env`、密钥、媒体或业务数据。
- 访客列表不再把通用 `radarProfiles` 全量当成访客；只有没有 `leadReminderId` 的身份才属于访客投影。开始跟进、继续跟进和放弃后，客户只能出现在各自的服务端状态页签。
- 本地定向回归：Postgres schema 与 SCRM 测试共 20 项通过，相关 JS 语法和 `git diff --check` 通过。生产发布后还需重新验证跟进中详情和状态页签。

### 生产执行记录

- 生产 schema 与 repository 文件已备份到 `/home/ubuntu/teambuy-backups/customer-radar-db-schema-20260827-125309`，并同步到服务器源码目录；线上环境变量、密钥、数据库卷和媒体目录未覆盖。
- 镜像重建因基础镜像 `apt-get update` 长时间无输出而中止，旧容器未被切换；为先解除线上 500，已直接在生产 Postgres 执行同一正式迁移：`visitor_identity_id text` 和 `idx_view_events_visitor_identity`。
- 迁移结果已只读核验，API 本机与 `https://teambuy.lifelove.top/health` 均返回 200。生产镜像仍需在基础镜像网络恢复后按正常流程重建，使动态迁移代码进入镜像。

## 2026-08-27：客户详情跟进动作身份键与标签布局修复

- 根因：详情页和雷达卡片在已有 `leadId` 时仍同时提交旧的 `customerId` 别名；两者不一致会被服务端安全校验正确拒绝为“客户与跟进档案不匹配”，前端随后进入慢速对账路径，造成点击慢和旧列表短暂回显。
- 修复：已有跟进档案时，详情读取、开始/继续/放弃/恢复动作和雷达对账统一只提交 `leadId`；只有首次没有 `leadId` 的访客才提交 `customerId` 建档。未放宽后端身份校验，也未删除正式接口。
- UI：客户详情“本次跟进标签”改为兼容小程序的固定两列，按钮宽度均分、文字保持单行居中。
- 验证：客户详情与雷达 JS `node --check`、SCRM/schema 定向测试 20 passed、`git diff --check` 通过。该轮仅修改小程序前端，需重新清缓存、编译并上传体验版后真机验证。

## 2026-08-27：对抗式审查补齐客户身份唯一入口

- 审查发现客户列表、销售线索、资源分析等非雷达入口仍可能把 `leadId` 和历史 `customerId` 同时拼到详情路由；这虽被详情页忽略，但会留下后续回归风险。
- 修复：`miniprogram/services/api.js` 在详情读取和跟进动作 API 边界统一执行 canonical identity 规则；有 `leadId` 自动不发送 `customerId`。已知导航入口同步改为有线索 ID 时只传 `leadId`。
- 保留首次访客建档路径：没有 `leadId` 时仍发送 `customerId`，不能为了清除旧混用而误删新访客建档能力。
- 对抗式结果：访客、跟进中、已放弃及其他客户入口的 lead-based 请求均通过静态检查；两列标签样式仍为固定 50% 宽度，未发现新的单列 CSS 覆盖。

## 2026-08-27：17:17 放弃访客后人数回弹修复

- 生产证据：17:18:11 写入了一条 paused 线索，版本为 16；来源资料类型为 groupbuy_product。因此“放弃没有落库”不是事实，真实问题是房源模式只按当前场景重建事件，而没有用所有场景的已处理线索做身份屏蔽。
- 修复：机会雷达的状态列表继续按当前场景展示，但待处理/活跃访客的身份屏蔽改为读取该拥有者全部 following/contacted/paused/deleted 线索；同时顶层 summary.visitorCount 与过滤后的活跃访客投影统一。
- 生产已同步 app_service.py、routes_scrm.py、repository.py 和 schema.sql，重启时补齐 lead_reminders.visitor_identity_id/version、customer_actions.visitor_identity_id；线上健康检查 200，直接重算房源雷达为活跃访客 4 人，17:18 那条已放弃身份不在雷达中，客户详情热路径不再 500。
- 本地回归：schema 与 SCRM 测试 21 项通过，Python/JS 定向语法检查和 git diff --check 通过。Docker 基础镜像的 apt-get update 下载曾长时间阻塞，本次为先恢复线上服务采用容器内热替换；宿主机源码已同步，后续应在依赖网络恢复后重建正式镜像。
- 小程序体验包仍需用户在微信开发者工具重新编译、上传；未上传新包时，手机仍可能使用不带 refresh=1 和新列表分流的旧前端。

### 18:38 复核

- 对照生产日志，17:18:11 的放弃请求为 HTTP 200，数据库写入没有丢失；该次真机操作早于本轮修复上线。
- 修复后的 API 容器和两个 worker 已统一核对源码 SHA，健康检查通过；新旧业务看板接口重算出的房源活跃访客均为 4 人，已处理身份不会重新进入访客投影。
- 后续真机验收必须先重新编译并上传体验包，再复测“放弃一人 → 返回雷达 → 重新进入访客 → 等待 30 秒/重进页面”。

## 2026-08-27：清理雷达页旧样式与无效视图构造

- 已确认当前 `pages/visits/index.wxml` 只使用 `radar-workbench-*` 页面链路；删除同一 WXSS 文件中未被当前 WXML 使用的旧 `radar-*`、`radar-v2-*`、旧摘要/时间线/付费墙样式。
- 删除雷达 JS 中已无调用方的旧 `buildTimeline`、`buildSummaryView`、`buildAssistantBrief`，避免后续把旧视图误接回新状态投影。
- 保留首次访客建档所需的 `customerId` 分支，以及当前唯一的 `customerIntelligence`、`customer-detail` 和 `note-preview` 路由；没有删除正式新接口或当前页面。
- 验证重点：页面 WXML 与 WXSS 仅剩当前前缀；相关 JS 语法、身份请求静态不变量、后端 SCRM/schema 回归继续通过。
- 真机仍需用户在微信开发者工具清缓存、重新编译并上传体验版；仓库清理不会替换已经安装的旧体验包。

## 2026-08-27：跟进记录两列与动作热路径优化

- 客户详情“本次跟进标签”改为显式固定两列布局：使用 `flex` 两列宽度、按钮内容双向居中、标签文案单行显示，避免小程序端 `gap`/原生 button 默认样式造成退化为单列或文字偏移。
- 详情页开始/继续跟进成功后，把服务端返回的线索 ID、状态和版本放入雷达页的进程内短时 mutation 队列；返回雷达时先从四个本地列表移除旧卡并放入目标状态列表，命中则跳过完整雷达重算。放弃、恢复沿用同一机制。
- 首次访客动作新增紧凑卡片投影参数，后端可直接按“拥有者 + 访客身份 + 来源资料 ID”建档，不再先构造完整客户详情；同时修正 compact 分支残留旧 `detail` 变量导致首次动作异常的问题。
- 动作接口继续是唯一持久化真源：服务端原子写入后返回线索和四类跟进计数；下次页面正常刷新再从服务端完整投影校准，未把客户身份或联系方式写入 `wx` 持久化缓存。
- 本地验证：`backend/tests/test_sales_scrm.py` 与 `backend/tests/test_postgres_repository_schema.py` 共 22 项通过；相关 Python/JS 语法检查及 `git diff --check` 通过。生产后端和微信体验包本轮尚未发布。

## 2026-08-27：跟进记录结构化与雷达轻量投影

- `LeadFollowUpLog` 现在把 `action/actionLabel`、本次标签 `tags`、备注 `note`、下次跟进时间 `nextFollowUpAt` 与 `createdAt` 绑定为同一条历史记录；旧文本记录仍可读取。
- 跟进表单即使只选择标签或只设置下次日期，也会落一条可审计记录；当前客户标签/下次日期仍保留在 `LeadReminder`，分别作为当前状态字段和雷达卡片摘要。
- 雷达 `radarProfiles`、`followingProfiles`、`abandonedProfiles` 和机会提醒不再下发 `followUpLogs/latestFollowUp`，只下发当前状态、版本和最新下次跟进时间；完整历史只由客户详情读取。
- 客户详情的内存雷达快照明确不伪造历史，后台详情请求返回真实历史；日期选择器使用 `YYYY-MM-DD`，历史行仍显示完整创建时间。
- 本地验证：`backend/tests/test_sales_scrm.py` 19 passed；客户详情/雷达 JS `node --check` 通过；`git diff --check` 通过。生产后端和微信体验包本轮未发布。

## 2026-08-27：21:53 跟进历史标签渲染复核

- 复核确认设计与数据模型一致：每条最近记录由 `action/actionLabel`、标签快照、备注、下次跟进日期和 `createdAt` 组成；不能只显示手动输入文字。
- 详情页历史记录模板改用显式 `record/tag` 循环变量，避免小程序 WXML 内外层都使用隐式 `item` 导致标签字段在真机渲染时丢失。
- 小程序构建标识更新为 `20260827-followup-records-1`，便于确认体验版是否真正包含本轮代码。
- 旧体验包或旧记录仍可能只显示文字：旧前端保存时没有发送标签，数据库无法事后推断；必须用新体验包新保存一条记录验证标签展示。

## 2026-08-27：待跟进转跟进中同步修复

- 根因：详情页从雷达卡片打开后，已有 `leadId` 时路由不再携带旧 `customerId`；动作成功后，前端 mutation 只使用详情页暂时为空的客户 ID/旧身份进行匹配，部分卡片因此无法从待跟进集合移走，且返回时仍默认停留在待跟进标签。
- 修复：mutation 以动作接口返回的 `lead.visitorIdentityId/viewerUserId` 和 `lead.id` 作为唯一同步身份，跨待跟进、访客、跟进中、已放弃四个集合先移除旧卡，再放入目标状态；开始/继续跟进成功后直接返回“跟进中”，放弃后返回“已放弃”，不再依赖旧客户别名。
- store 仍只保留当前页面返回所需的短时内存身份键、线索 ID、状态、版本和下次日期，不写手机号/微信号到持久化缓存；服务端动作响应仍是最终持久化真源。
- 本轮待验证：首次访客无 `leadId` 开始跟进、已有待跟进档案开始跟进、跟进中继续跟进、放弃/恢复，以及冷启动和手动刷新后的四类计数。
- 客户端构建标识更新为 `20260827-followup-routing-1`，用于确认体验包是否包含本轮雷达移动修复。

## 2026-08-28：跟进链路与雷达首屏统一收口

- 客户详情移除旧的“保存本次跟进”写入路径；底部唯一主按钮现在一次提交当前标签、备注、下次跟进时间和开始/继续跟进动作，并在服务端成功后自动返回雷达目标页签。
- 新动作接口在服务端原子更新 `LeadReminder` 并新增一条结构化 `LeadFollowUpLog`，历史记录同一条绑定 `action/actionLabel`、标签快照、备注、下次时间和创建时间；请求幂等和版本冲突不会回退旧状态。
- 雷达首屏增加轻量摘要投影，先返回状态计数，完整卡片后台补齐；未完成加载不再显示假数字 0，使用 `—`。客户端仅使用环境/用户隔离的进程内缓存，敏感客户数据不进入 wx 持久化缓存。
- 前端客户详情不再调用旧保存/兜底接口；后端保留的 `ensure_customer_followup` 和旧更新路由仅作为内部首次建档/其他旧页面兼容，不属于当前详情页调用链。
- 验证结果：销售 SCRM 定向测试 21 passed；全量后端测试 298 passed；Python 编译、Node 语法检查和 `git diff --check` 通过。
- 本轮未部署生产，也未上传小程序体验版；人工验收前仍需开发者工具清缓存、重新编译并上传最新体验包。

## 2026-08-27：跟进链路旧兜底清理

- 当前客户详情不再使用 `log.customerTags` 兼容字段补标签，保存和恢复也不再用页面内旧 `followUpLogs` 作为接口响应兜底。
- `LeadReminderUpdateRequest` 不再接受旧的 `customerTags` 跟进写入方式；当前表单唯一写入字段是 `followUpTags`。
- 保留旧历史记录的只读可见性，但不再让旧记录字段参与新记录写入或新标签渲染；旧记录没有标签时不会凭空补造标签。

## 2026-08-27：22:21 跟进记录标签再次核对

- 线上容器 `teambuy-backend-1` 的实际源码仍是旧版本：`LeadReminderUpdateRequest` 仍有 `customerTags`，服务端更新方法仍只处理 `payload.customerTags`，没有 `followUpTags` 的结构化写入。
- 因此 22:21 的文字“下周”可以落库，但新客户端提交的标签会被旧后端忽略；这不是历史数据渲染问题，而是线上前后端版本不一致。
- 本地前端增加结构化响应契约校验：保存后必须收到新建记录及 `action/tags` 字段；旧接口不再被静默当成成功，直接提示重新部署后端并上传最新体验版。
- 本轮未部署生产；部署后必须新建一条测试记录验证“标签、备注、下次日期、时间”在同一条最近记录中出现。

## 2026-08-27：22:32 跟进标签后端发布

- 生产发布前已检查根分区和 Docker 占用，磁盘可用约 28G；线上 `.env`、secrets、数据库卷和媒体目录未覆盖。
- 常规 Compose 构建卡在基础镜像 `apt-get update`，未切换半成品；随后以现有生产镜像为基础，仅覆盖 `domain.py`、`cards.py`、`app_service.py` 构建热修复镜像，并保留旧 API/worker 镜像标签用于回滚。
- API、backend-worker、archive-worker 已使用新镜像；生产 API 按 Nginx 既有约定映射到 `8004:8000`，公网 `/health`、`/health/db` 均正常。
- 容器内只读核对到 `followUpTags` schema 和结构化持久化分支；受保护的 `config-check` 返回 401，说明路由可达且鉴权仍生效。
- 小程序构建标识更新为 `20260827-followup-records-2`；仍需微信开发者工具重新编译、清缓存并上传体验版，手机端才会使用结构化响应校验。
## 2026-08-28：客户详情底部唯一动作收口复核

- 复核发现交接所述“唯一按钮”与本地 WXML 不一致：详情底部仍有独立放弃/恢复按钮和 handler。
- 已移除该详情专属状态按钮、handler、状态锁及样式；固定底部改为单按钮 100% 宽度，并保留雷达页的放弃/恢复入口。
- 静态核对：详情无旧保存/`ensure`/`updateLeadReminder` 调用；统一动作仍提交标签、备注、下次跟进时间、`operationId` 和 `expectedVersion`。
- 验证：SCRM 21、Postgres schema 3、全量后端 298；Python/Node/JSON/`git diff --check` 均通过。
- 未部署生产、未上传体验版；人工需在微信开发者工具清缓存并重新编译上传，检查详情只剩一个底部按钮及雷达动作、标签、记录。
## 2026-08-28：生产客户跟进字段版本已落地

- 生产预检：根分区可用约 28G；Postgres healthy；teamBuy 端口为 `8004 -> 8000`，未修改生产 `.env`、secrets、数据库卷或 Nginx。
- 已备份 Compose 和原三份源码到 `/home/ubuntu/teambuy-backups/20260828-011239/`，并为 API、两个 worker 的旧镜像保留 `rollback-20260828-011239` 标签。
- 常规构建在 `apt-get update` 阶段无响应，已停止本次构建进程；随后基于现有镜像仅覆盖客户跟进三份源码，生成并切换热修复镜像，三套容器均正常运行。
- 生产容器 hash 与本地 staging hash 一致；容器内 schema 包含 `followUpTags`、`logContent`、`nextFollowUpAt`，service 包含对应参数，OpenAPI 暴露新字段和动作路由。
- 本机 `/health`、`/health/db` 与公网 `/health` 均通过。无认证动作探针被登录中间件拦截，未产生数据库写入，因此真实业务写入仍待体验版登录后验证。
- 后端已部署；小程序尚未通过微信开发者工具重新编译上传。

## 2026-08-28：详情状态按钮与雷达计数显示修复

- 根据真机截图复核，详情页上一轮“底部唯一按钮”收口误删了状态操作；已恢复第二个底部按钮：活动客户显示“放弃跟进”，已放弃客户显示“恢复跟进”。两个按钮均复用原子 action API，并携带当前标签、备注和下次跟进时间。
- 无 lead 的访客详情也显示跟进表单，保证“保存并开始跟进”不是只有按钮而没有可编辑字段。
- 雷达页下方四个页签全部显示对应计数，加载中显示 `—`；缓存 dashboard 先派生四类列表和计数，轻量摘要独立返回后立即刷新，不再出现列表已经显示而顶部/页签数字缺失的状态。
- 固定底部双按钮改为 flex 两列、明确宽度和单行居中；保留原项目的 rpx 和小程序按钮排版约定。
- 同步修订生产部署主手册、腾讯云总运维手册、客户看板上线清单和旧部署脚本：当前默认使用范围明确的当前镜像热修复，完整构建必须显式 `ALLOW_NETWORK_BUILD=1`，并固定使用 `APP_PORT=8004` 无构建切换。
- 本轮未上传微信体验版；仍需开发者工具清缓存、重新编译并上传后进行真机验收。

## 2026-08-28：四个主 Tab 读取性能与稳定性专项

- 客户雷达完整读取改为批量加载资料事件、客户动作和合集事件；客户画像在一次请求内复用同一访客的联系方式查询，消除按事件重复查用户的 N+1 路径。
- “我的”页判断客户入口改读雷达摘要，不再为一个入口等待完整客户画像；雷达摘要增加环境/用户/场景隔离的进程内缓存和并发请求合并，动作成功后主动失效。
- 资料库和首页先展示卡片元数据，再补齐分类、专题、合集、订单和客户画像，避免无关请求拖住首屏；浏览历史源事件在数据库侧限量。
- 清理审查确认：`message-plugin`、`share-snapshot` 均仍被现有页面/组件引用；`app.json` 中的旧页面以及 workbench 子包页面仍有路由用途，本轮没有证据充分的可安全删除项，未做批量删除。
- 本轮未部署生产，也未上传微信体验版；需在本地完成测试后，再由用户按需安排体验版验证。

## 2026-08-28：类型化分享卡固定模板与雷达计数投影

- 分享插件样式版本升为 `share_card_v7`，接入 `text_note`、`image_ocr`、`link`、`property_listing`、`groupbuy_product`、`service_offer`、`business_card` 七种资料类型；无主图资料使用固定信息卡，标题/摘要限制两行、字段最多三项并按绘制宽度省略，真实 HTTPS 主图继续原图直发。
- 合集分享源补齐 `showcase_info` 无封面模板；修复合集列表和编辑页把“无封面”误判为 direct、从而允许空 `imageUrl` 原生分享的问题。所有合集分享回调在无图时都阻止发送并提示准备中。
- 雷达新增 `customer_radar_summaries` count-only 投影表，按 owner + mode 保存八项计数；热路径只读一行干净计数，资料/事件/客户全量扫描仅在首次或被业务变更标脏时重建，且不保存客户身份或联系方式。
- 已补充 Json/Postgres repository、schema、索引和雷达回归测试；未发现可安全删除的未引用插件，`message-plugin` 与 `share-snapshot` 仍被多个页面/组件使用。
- 本轮未部署生产、未上传体验版；需要在微信开发者工具清缓存、重新编译后人工检查七种资料和四个场景的分享缩略图及合集无封面发送状态。

## 2026-08-28：分享回调兜底与雷达并行读取复核

- 资料列表和资料库分享图未就绪时，回调兜底路径改为对应资料详情页，不再返回资料列表页，避免微信在缺少 `imageUrl` 时截取错误列表画面。
- 雷达权限确认后，count-only 摘要和完整客户卡片请求并行等待；摘要被标脏重建时不再额外阻塞客户内容展示。
- 对抗式冒烟覆盖七种无图资料、HTTPS 主图直发、HTTP 图片降级、合集固定模板以及空图回调目标路径；未进行微信开发者工具真机验收。

## 2026-08-28：资料库发送卡片回调消费已生成快照

- 定位到“详情页发送正常、返回资料库发送变成列表截图”的具体断点：资料库预热流程将完整资料生成的 JPG 写入 `shareImages`，但最终回调之前没有消费这份映射，而是重新用精简列表卡片计算 fingerprint。
- 精简列表卡片不包含完整 `contentBlocks`，与详情页的快照 fingerprint 不一致；最终回调因此返回 `null`，微信便截取当前资料库页面，形成列表截图。这不是旧模板 JPG，也不是后端保存失败。
- 资料库现在优先消费按卡片 ID、资料 ID、revision 校验过的 `shareImages` JPG；没有有效匹配时才使用列表状态的严格校验结果，仍禁止返回资料列表路径或空图原生分享。
- 冒烟验证覆盖有效预热快照、错误 revision、缺图三种回调结果；本轮未重新部署生产，也未上传体验版，仍需开发者工具清缓存、重新编译后真机验证资料库按钮。

## 2026-08-28：分享 JPG 去除重复的内部打开引导

- 根据真机截图核对，分享卡的“外层微信标题/卡片文案”和 JPG 内部的“打开小程序查看完整资料”不是两层页面，而是同一张 JPG 内部多画了一条兜底引导。
- 已从统一绘图层和共享 `share-snapshot` 入口移除该内部兜底文案；保留真实资料摘要、底部品牌 footer“资料整理助手 · 点击查看完整资料”和外层微信分享标题，避免删除真正的分享入口。
- 同步将 `SHARE_CARD_TEMPLATE_REVISION` 从 v2 升到 v3，使已经保存的旧 JPG 快照不再被复用；下一次进入发送准备时会按新模板重新生成。
- 当前修改只影响前端分享图绘制，不需要后端部署；必须重新编译并上传体验版后，新的 JPG 才会在微信端生效。已发出的历史微信卡片不会被改写。
- 验证：分享绘图模块和资料库回调 Node 语法检查、`git diff --check` 通过；完整真机分享矩阵仍待人工验收。

## 2026-08-28：商品分享图补齐规格价格并保留商品全图

- 定位到商品编辑器已经将价格写入 `structuredData.variants[].priceFen`，而分享计划仍只读取已废弃的扁平 `data.price`，导致商品 JPG 没有价格标签。
- 商品分享现在优先取可售规格中的最低 `priceFen`，无可售规格时取全部规格；同时兼容旧 `skuConfig.skus[].price` 和旧 `data.price`，价格作为第一个 facts 标签。
- 商品主图改用 `contain`，在固定 5:4 JPG 内保留完整图片；图片资料和商品拼图都不再因 `cover` 放大而裁掉内容，房源/服务照片继续使用铺满视觉。
- 分享模板 revision 升到 v4，已有 v3 快照不会继续复用；本轮未部署后端，需重新编译上传体验版后重新生成商品分享图。
- 七类资料数值字段复核后，合集编辑页商品价格筛选也补上 `variants[].priceFen`，避免新商品在合集条件筛选中继续走旧 SKU 字段。

## 2026-08-28：全系统性能稳定性专项实现与对抗式审查

- 后端 PostgreSQL 主仓储和运维功能开关仓储统一改为有限连接池并复用连接；应用退出时显式关闭连接池。会员状态读取改为用户范围查询，不再为一次状态判断扫描并重写全量状态。
- 客户详情/雷达/资料库的高频读取改为批量事件、动作和资料查询；未筛选的资料库分页只读取当前窗口所需数据，保留关键词/分类的完整过滤语义。
- 上传入口、OCR 图片入口、运维文件入口增加大小上限；CPU/磁盘媒体处理移出异步 API 事件循环。企业微信、共享会话存档和 OCR 远程图片改为限量流式读取，统一媒体处理入口再次兜底拒绝超限内容。
- 小程序请求增加 15 秒超时；资料/分类持久化缓存的可用陈旧时间明确受 TTL 限制，修复陈旧分类恢复时错误刷新时间戳的问题。同步保留雷达 generation、并发合并和主动失效机制。
- Compose 增加 API 数据库健康检查和 worker 进程探活；延迟任务调度增加去重，避免同一任务被重复创建 sleeper。
- 对抗式审查覆盖缓存过期、分页边界、迟到响应、跨用户查询、上传超限、远程媒体超大响应、连接池关闭和延迟任务重复调度；未发现新的确定性业务回归。
- 验证：全量后端 `303 passed`，Python 编译、Node 语法、Compose YAML 解析、`git diff --check` 通过；本机无 Docker CLI，未进行真实 PostgreSQL/容器启动验证。
- 本轮未部署生产、未上传微信体验版。由于新增 `psycopg-pool` 运行依赖，生产发布必须重新构建包含新依赖的镜像并按健康检查切换，不能采用只覆盖源码的旧镜像热修复。

## 2026-08-28：性能专项生产部署与真实 PostgreSQL 验证

- 已将性能专项提交 `3aaaf17`（`perf: harden tab loading and production runtime`）部署到腾讯云生产；部署前检查磁盘、Docker 占用、端口和健康状态，并备份到 `/home/ubuntu/teambuy-backups/20260828-205848-perf-runtime`。
- 标准 Compose 完整构建在 Debian `apt-get update` 阶段两次出现长时间无进展，均已停止，旧容器未因此被长期占用。由于本次新增 `psycopg-pool`，没有采用只覆盖源码的热修复；改用已存在生产镜像作为基础，注入经过 SHA-256 校验的 `psycopg_pool-3.2.6-py3-none-any.whl` 和已同步源码，制作依赖完整的发布镜像。
- 首个临时镜像 smoke test 暴露了制镜容器的 `sleep` 启动命令和连接池默认 `row_factory=None` 两个问题；已回滚旧镜像恢复服务，修复连接池默认使用 `tuple_row` 并补充回归测试，再制作 r2 镜像。该过程证明切换前必须检查镜像 `CMD`，并用真实 PostgreSQL 网络启动临时容器。
- 最终运行镜像：`teambuy-backend:deploy-3aaaf17-r2`（`73769cd56f0e`）、`teambuy-backend-worker:deploy-3aaaf17-r2`（`44858b4dfc88`）、`teambuy-archive-worker:deploy-3aaaf17-r2`（`965517eaac58`）；三个服务均已运行并 healthy。旧镜像仍保留为 `rollback-20260828-205848`。
- 上线验证：生产 PostgreSQL 初始化 smoke test 通过；API、两个 worker 均正常启动；`127.0.0.1:8004/health`、`/health/db` 和公网 `https://teambuy.lifelove.top/health` 全部通过；日志未见启动异常。数据库卷、媒体卷、`backend/.env` 和 `backend/secrets/` 未覆盖。
- 代码验证：连接池定向回归 `8 passed`；部署前全量后端测试 `303 passed`。小程序仍未清缓存、重新编译或上传体验版，前端性能和分享卡必须由用户在微信开发者工具中人工验收。
## 2026-08-29：推广奖励/提现页状态与审查可用性优化

- 重构 `miniprogram/pages/referral-center` 首屏：先展示加载态，首次请求失败提供重试，已加载页面刷新失败保留旧数据并提示，不再把接口尚未返回误显示为真实的 ¥0。
- 将当前余额、最低提现金额、进度、未达门槛原因和“去资料库分享赚奖励”放到首屏；只有服务端规则完整且余额达到门槛时才显示提现金额选项和提交按钮。
- 对服务端响应中的余额字段增加有效性判断；接口成功但余额缺失/非法时显示“余额不可用”，不把异常响应伪装成真实的 ¥0。
- 删除前端按环境猜最低提现额的兜底；最低金额、每日次数、申请时段和手续费均以服务端返回为准。提现选项会自动包含服务端最低金额，避免规则调整后刚好达标却无可选项。
- 提现提交增加规则可用、余额、金额和重复操作保护；加载请求使用请求序号，迟到响应不能覆盖较新的页面状态。详细提现规则和分佣规则默认收起，减少首屏信息密度。
- 本轮只修改小程序前端，没有修改后端、数据库或生产配置；不需要后端部署，但需要微信开发者工具清缓存、重新编译并上传体验版。

### 验证

- `node --check miniprogram/pages/referral-center/index.js` 通过。
- Node 状态断言覆盖：余额为 0、刚好达到最低金额、固定金额部分可用、服务端最低金额变更、规则缺失、迟到响应保护，均通过。
- `python3 -m json.tool miniprogram/app.json`、`git diff --check` 通过。
- `.venv312/bin/pytest -q backend/tests/test_sales_scrm.py -k referral`：5 passed；`.venv312/bin/pytest -q backend/tests/test_wechat_pay.py -k referral`：1 passed。
- 已完成一次针对规则缺失、最低金额变化、重复提交和迟到响应的对抗式审查；未进行微信开发者工具视觉和真实提现验收。

## 2026-08-29：登录页游客入口可见性调整

- 将“游客模式 · 先浏览首页”置于微信一键登录按钮上方，并提升为与登录按钮同高的全宽入口，使用浅绿色高可见样式和 flex 居中，避免游客路径被埋在登录操作之后。
- 游客入口继续直接进入公开首页，不触发登录协议确认；需要账号归属的操作仍由业务动作按需触发登录。
- 本轮仅修改小程序登录页 WXML/WXSS，未修改后端、数据库或生产配置，也未上传体验版。

## 2026-08-29：正式环境最低提现金额调整为 ¥0.10

- 将正式环境 `WECHAT_TRANSFER_MIN_AMOUNT_FEN` 默认/示例配置从 `1000` 分调整为 `10` 分；服务端规则接口、创建提现校验和运营审核校验继续共用同一门槛函数。
- 小程序前端原有的服务端门槛读取逻辑无需改动：正式环境会显示 ¥0.10，并保留 ¥10、¥50、¥200 等可选金额。
- 增加正式环境恰好 10 分可创建提现、低于 10 分被拒绝的回归覆盖。本轮需要重新构建并部署后端，不能只上传小程序代码。

### 生产发布结果

- 已备份生产 Compose、`backend/.env` 和后端配置到 `/home/ubuntu/teambuy-backups/20260829-171728-withdrawal-minimum/`。
- 标准 `docker compose build` 在 Debian 基础镜像 `apt-get update` 阶段超过 180 秒无进展，已终止且未影响旧容器；本次无新增依赖，采用现有已验证镜像 + 显式生产环境变量的受控发布路径。
- 已将生产 `WECHAT_TRANSFER_MIN_AMOUNT_FEN` 更新为 `10`，并强制重建 API、OCR worker、归档 worker 容器；三个容器均 healthy，容器内配置为 `production / 10`。
- 线上运营规则接口返回 `minimumWithdrawalFen=10`；本机 `/health`、`/health/db` 和公网 `/health`、`/health/db` 均通过。旧业务数据、数据库卷、媒体卷和其他密钥未改动。

## 2026-08-30：推广中心改版为概览页 + 收益与推广详情页

- `referral-center` 改为暖色调推广中心概览：可提现金额与“去提现”并列，移除用户不可理解的“待结算”；已邀请、已开通、累计收益三个指标可点击，分享入口回到现有资料库，继续使用资料/名片/合集的既有分享归因链路。
- 新增 `referral-detail` 页面，使用“收益记录 / 推广好友”页签承载收益、提现记录和直接推广好友；提现规则在页面内直接展示，不使用抽屉，提现提交和微信收款确认逻辑沿用原流程。
- 推广规则文案继续使用当前服务端/既有页面约定：分享自动归因、会员资格、实际支付金额的 50%、仅一级直接推广、退款/刷单/异常交易处理；提现门槛、次数、时段、手续费和到账说明继续读取服务端规则。
- 服务端推广中心响应新增脱敏的 `directReferrals` 和收益记录中的 `inviteeNickname`，用于好友页和收益明细显示；未改变奖励计算、一级归属或提现校验。

### 验证与发布边界

- `backend/tests/test_sales_scrm.py` 与 `backend/tests/test_wechat_pay.py`：`33 passed`；推广定向回归：`5 passed`。
- 小程序 JS 语法、页面 JSON、`git diff --check` 通过；已检查推广页面不存在“待结算”文案和旧提现事件引用。
- 已完成静态边界/对抗式检查：服务端规则缺失、余额缺失、最低金额、重复提交、迟到刷新、直接好友脱敏和支付状态映射均由现有保护链路约束。
- 本轮未部署生产、未修改生产运行配置、未上传微信体验版；真机页面视觉和提现交互仍需开发者工具人工验收。

## 2026-08-30：PC 用户使用汇总改为独立数据分析子页面

- 根据运营反馈，恢复总览和客户经营页的原有展示，包括待跟进客户表；用户使用数据不再嵌入总览或替换客户经营内容。
- 在“数据分析”导航组新增“用户使用数据”子页面，复用既有汇总接口，页面打开时按需加载今日/近 7 日/总量、10 行分页和四字段排序。
- 本次只调整 PC 页面信息架构和加载时机，未修改用户汇总接口的统计口径。

### 验证与发布边界

- 已检查总览、客户经营、用户排行、内容排行及新增子页面的 tab/DOM 对应关系；PC 内嵌 JavaScript 静态检查和相关后端回归已通过。
- 本轮尚未部署生产、未修改生产配置、未上传微信体验版。

## 2026-08-30：PC 运营总览增加用户使用数据汇总

- 根据运营关注点，PC 总览不再渲染待跟进客户的逐条明细；客户经营页也移除同一张待跟进列表，避免把预约跟进时间当成主要经营数据。待跟进总数指标和其他指标详情保持兼容。
- 新增 \`/api/ops-admin/user-activity-summary\`：按用户返回资料数、分享次数、匿名访客去重数、注册访客去重数，支持今日/近 7 日/总量、关键词兼容、10 行分页和四个数值字段的升降序排序。时间窗口由服务端 \`Asia/Shanghai\` 计算。
- 总览新增独立“用户使用数据”表；匿名访客跨资料/合集事件合并去重，注册访客按登录用户 ID 去重；点击“待跟进客户”指标会定位到该表，不再读取客户逐条详情。

### 验证与发布边界

- \`PYTHONPATH=backend .venv312/bin/pytest -q backend/tests/test_app.py -k 'ops_admin_overview_and_leaderboards or ops_admin_user_activity_summary'\`：\`2 passed\`。
- 运维后台内嵌 JavaScript \`node --check\`、Python \`compileall\`、\`git diff --check\` 通过；接口测试覆盖今日/近 7 日/总量、跨来源匿名去重、注册访客去重、分享统计、10 行分页、四个排序字段和非法排序。
- 本轮只修改本地后端接口、PC 运维页面和测试/文档；未部署生产，未修改生产配置，未上传微信体验版。PC 页面仍需在真实浏览器中人工确认表格视觉和点击交互。

## 2026-08-30：用户使用数据子页面部署生产

- 按范围明确的无构建热修复路径发布 \`backend/app/api/routes_ops_admin.py\` 和 \`backend/app/static/ops-admin/index.html\`；本次没有新增运行依赖，未覆盖生产 \`backend/.env\`、\`backend/secrets/\`、媒体目录或数据库卷。
- 部署备份：\`/home/ubuntu/teambuy-backups/20260830-072815-user-activity/\`。回滚标签：\`teambuy-backend:rollback-20260830-072815-user-activity\`、\`teambuy-backend-worker:rollback-20260830-072815-user-activity\`、\`teambuy-archive-worker:rollback-20260830-072815-user-activity\`。
- 当前发布镜像：\`teambuy-backend:deploy-20260830-072815-user-activity\`（\`06cdaf76c918\`）、\`teambuy-backend-worker:deploy-20260830-072815-user-activity\`（沿用 \`44858b4dfc88\`）、\`teambuy-archive-worker:deploy-20260830-072815-user-activity\`（沿用 \`965517eaac58\`）；三项均同步到 Compose 使用的 \`latest\` 标签。
- 切换时显式保留 \`APP_PORT=8004\`。API、backend-worker、archive-worker、PostgreSQL 均 healthy；本机和公网 \`/health\`、\`/health/db\` 通过。新汇总接口无 Token 返回预期 \`403\`，带服务器内部管理员 Token 返回 \`200\` 且 payload 标记完整，运营页面包含新入口和原客户明细 DOM。
- 本轮未上传微信体验版。PC 运营后台仍需用户在真实浏览器中人工检查视觉、导航、用户使用数据时间切换、排序和分页。

## 2026-08-30：用户使用数据补充稳定 ID 与首次注册时间

- 生产只读核对显示用户使用数据总量为 38，接口按系统用户记录汇总；分页 10 行对应 4 页。这个数字包含当前用户表中的测试/Mock 记录可能性，不作为真实微信用户数承诺。
- 用户使用汇总接口新增返回用户 \`createdAt\`；PC 页面把稳定 \`userId\` 放在用户单元格主行，昵称放次行，并新增“首次注册”列。该时间采用服务端创建记录时的东八区 ISO 时间，含义是本产品首次进入时间。
- 定向运营测试：\`1 passed\`；内嵌 PC JavaScript 检查和 \`git diff --check\` 通过。本次尚未重新部署生产，需用户确认后再发布。
- 定向运营测试：\`1 passed\`；内嵌 PC JavaScript 检查和 \`git diff --check\` 通过。本次已完成生产部署并通过线上验证。
- 新生产镜像：\`teambuy-backend:deploy-20260830-075602-user-activity-created-at\`（\`4ac8733c742e\`）；API、两个 Worker 和 PostgreSQL 均 healthy，端口保持 \`8004\`。备份目录：\`/home/ubuntu/teambuy-backups/20260830-075602-user-activity-created-at/\`。
- 线上汇总接口返回 38 条用户记录且每条包含 \`createdAt\`；公网 \`/health\`、\`/health/db\`、\`/ops\` 页面标记和无 Token 鉴权检查均通过。未上传微信体验版。

## 2026-08-30：PC 二维码活码工作台（本地已完成，未部署）

- 新增独立页面 `backend/app/static/live-qr/index.html`，入口为 `/ops/live-qr`；支持管理员 Token 登录、创建活码、复制/下载固定入口二维码、更新目标、暂停和恢复。
- 新增 `LiveQrCode` 主仓储实体和 `live_qr_codes` PostgreSQL/JSON 持久化；公开入口 `/live-qr/{code}` 记录访问次数后 302 到当前目标，目标更新不改变 code；`/live-qr/{code}.png` 生成真实 PNG 二维码。
- 新增 qrcode 运行依赖（版本 8.2）；因此后续生产发布必须按新增依赖流程重新构建包含依赖的镜像，不得只覆盖源码热修复。

### 验证与发布边界

- 活码定向回归：2 passed；全量后端测试：307 passed。
- Python compileall、独立页面 JavaScript node --check、HTML 标记检查和 `git diff --check` 通过。
- 已覆盖未授权后台接口、无效目标、PNG 输出、首次访问计数、更新目标后 code 不变、暂停不计数、恢复后跳转新目标。
- 本轮未部署生产、未修改生产配置、未上传微信体验版；需要真实浏览器检查页面视觉，并用真实手机扫码验证小红书/微信环境能打开目标链接。

## 2026-08-30：活码纳入群运营并增加分页、7 天到期和换码操作

- 运营后台新增“群运营 → 二维码活码”子页面；原有群自动化、群二维码批量上传、群发渠道映射和小程序加群配置保持不变。
- 活码列表改为服务端分页，默认每页 10 条；每行展示外层二维码、固定编号、当前目标、目标有效期、访问次数、最近访问、状态，并提供更换二维码、复制入口、下载图片、暂停/恢复。
- `LiveQrCode` 增加 `targetExpiresAt`；新建默认 7 天，更换目标默认重新计算 7 天；目标过期或暂停时固定入口返回 410，避免继续使用失效目标。
- 目标更新仍只改变服务端跳转目标，不重新生成外层二维码；当前版本的换码操作要求填写可访问的 http/https 目标地址。

### 验证与发布边界

- 活码定向测试：3 passed；相关运维/仓储测试：13 passed；全量后端测试：308 passed。
- Python compileall、运营后台内嵌 JavaScript node --check、页面结构/视觉人工检查和 `git diff --check` 通过。
- 已覆盖分页返回、默认 7 天有效期、目标更新后固定 code 不变、同目标延长有效期、过期入口 410、暂停/恢复、PNG 输出和原有无 Token 鉴权。
- 本轮未部署生产、未修改生产配置、未上传微信体验版；生产仍需在依赖完整的镜像中发布后再做公网和真实手机扫码验收。

## 2026-08-30：活码投放卡片增加虚拟头像和群名（未部署）

### 本轮完成

- 运营后台和兼容的 /ops/live-qr 页面，活码列表预览改为自动合成竖版投放卡片。
- 卡片包含 6 个系统绘制的虚拟头像、展示群名、原始固定外层二维码，以及“扫码进入最新群入口 / 外层入口不变，群码更新后无需重新发布”提示。
- 默认下载动作改为“下载投放卡片”；原始二维码下载入口保留，方便技术排查和特殊投放。
- 按需求移除卡片中的群有效期文字；当前目标的 7 天有效期、PC 列表到期提醒、过期入口 410 和换目标逻辑均未改变。
- 投放卡片在浏览器端用 Canvas 合成，使用本机系统字体绘制中文群名，避免服务端 slim 镜像缺少中文字体导致图片文字异常。

### 验证与发布边界

- 活码定向测试：3 passed；两处页面内嵌 JavaScript 均通过 node --check；git diff --check 通过。
- 本地 FastAPI + JSON 状态验证了真实 QR 图片加载、卡片 Canvas 生成（900×1200）、群名与虚拟头像预览以及“下载投放卡片”按钮可见。
- 本轮未部署生产、未修改生产配置、未上传微信体验版；生产仍需后续按新增 qrcode 依赖的完整镜像流程发布。

### 真实风险

- 浏览器端 Canvas 会受操作系统字体和 Emoji 字体影响，群名中文字形或星号样式可能有轻微差异，但不影响二维码识别。
- 小红书已发布的旧图片不会自动替换；换目标后需要重新下载并重新发布卡片，旧卡片仍可通过固定入口进入当前目标。
- 卡片生成依赖浏览器成功加载原始二维码；如果管理页被拦截或 QR 图片加载失败，下载动作会明确失败，不会静默下载错误图片。

## 2026-08-30：群运营活码已部署生产并补齐公网入口

### 发布内容

- 生产已发布“群运营 → 二维码活码”子页面、兼容页面 /ops/live-qr、活码 API、PostgreSQL live_qr_codes 表结构和 qrcode==8.2 运行依赖。
- API、backend-worker、archive-worker 均基于当前生产镜像制作依赖完整发布镜像，运行服务保持 8004 -> 8000；生产 backend/.env、backend/secrets/、媒体目录和数据库卷未覆盖。
- 常规 Compose 构建在 Debian apt-get update 阶段无进展后按部署约定停止；随后使用已校验的 qrcode-8.2-py3-none-any.whl 和明确源码制作受控发布镜像。
- 因公网 Nginx 原先对未列出的路径统一返回 404，已备份并仅新增 /live-qr/ -> 127.0.0.1:8004/live-qr/ 代理，nginx -t 通过后 reload。

### 生产记录

- 应用备份：/home/ubuntu/teambuy-backups/20260830-182429-group-live-qr。
- Nginx 备份：/etc/nginx/conf.d/teambuy.conf.bak-20260830-182429-group-live-qr。
- 发布镜像标签：teambuy-backend:deploy-20260830-182429-group-live-qr-final2、teambuy-backend-worker:deploy-20260830-182429-group-live-qr-final2、teambuy-archive-worker:deploy-20260830-182429-group-live-qr-final2。
- 三个业务容器和 PostgreSQL 均 healthy；/health、/health/db、公网 /health 通过；活码未授权 API 返回 403，未知活码公网入口返回 410。

### 发布后的人工验收

- 需要在真实浏览器硬刷新生产 /ops，展开“群运营”确认出现“二维码活码”，输入管理员 Token 后创建长期 HTTPS 目标。
- 需要下载投放卡片并用真实手机扫码；再执行更换目标、暂停/恢复和到期状态检查，确认固定外层入口不变。
- 本轮未上传微信体验版；未修改小程序分享链路。

## 2026-08-30：活码支持上传群二维码解析与目标到期筛选（本地完成，未部署）

### 本轮完成

- 活码创建/编辑表单新增“上传图片并解析”：后台临时读取上传图片，使用 `zxing-cpp==3.1.1` 优先解码二维码，OpenCV `QRCodeDetector` 兜底；解析成功后只把完整 http/https 链接回填表单，不保存原图片、不自动创建或更新活码。
- 保留手动粘贴链接作为兜底；无法读取二维码、图片损坏、二维码内容不是完整 http/https 地址时，页面给出明确错误，不会写入目标。
- 活码接口新增目标有效期筛选和汇总：`expired`、`1d`、`2d`、`3d`，每个指标统计当前全部活码（包含暂停记录），列表仍按服务端分页，每页 10 条。
- “群运营 → 二维码活码”页面和 `/ops/live-qr` 兼容页面均新增“已过期 / 剩 1 天 / 剩 2 天 / 剩 3 天”指标卡；点击指标或下拉筛选后，列表直接展示对应活码，列表内“更换二维码”可进入编辑。
- 到期天数沿用既有规则：按目标剩余秒数向上取整；因此页面的“剩 1/2/3 天”是目标有效期桶，不是自然日日期承诺。

### 验证与发布边界

- 活码定向测试：5 passed；全量后端测试：310 passed。
- 两处页面内嵌 JavaScript 均通过 `node --check`，Python 编译检查和 `git diff --check` 通过。
- 本地真实浏览器验证了指标渲染、指标点击筛选、下拉筛选、分页/编辑入口和图片上传回填；用实际参考微信群二维码截图验证后台成功解析出微信链接。
- 本轮新增后端依赖 `zxing-cpp==3.1.1`，尚未部署生产；后续发布必须按新增依赖的完整镜像流程同步 API/Worker，并保留 Nginx `/live-qr/` 代理。
- 本轮未上传微信体验版，未修改小程序 `onShareAppMessage` 分享链路。

## 2026-08-30：活码上传解析与到期筛选已部署生产

### 发布内容

- 生产已切换活码上传解析接口、到期汇总/筛选分页接口，以及 `/ops` 和 `/ops/live-qr` 两处页面。
- `zxing-cpp==3.1.1` 已通过 Linux x86_64 wheel 安装进 API、backend-worker、archive-worker 三个运行镜像；生产 PostgreSQL、`.env`、secrets、媒体目录和数据库卷未覆盖。
- 由于生产基础镜像的 Debian 构建网络风险，本次按受控例外路径基于当前线上镜像制作依赖完整发布镜像，并保留原服务启动命令和 8004 端口映射。

### 生产记录与验证

- 生产备份：`/home/ubuntu/teambuy-backups/20260830-202319-live-qr-decode`。
- 发布镜像：`teambuy-backend:deploy-20260830-202319-live-qr-decode`、`teambuy-backend-worker:deploy-20260830-202319-live-qr-decode`、`teambuy-archive-worker:deploy-20260830-202319-live-qr-decode`。
- `zxing_cpp-3.1.1` wheel SHA-256：`9cf67341949946307d086b302cefd453fb47bc6d6ddc7d088839e9481982757b`。
- 三个应用容器和 PostgreSQL 均为 `healthy`；本机 `/health`、`/health/db` 与公网 `https://teambuy.lifelove.top/health`、`/health/db` 通过。
- 生产 `/ops/live-qr` 可访问；未知活码返回 `410`；带文件但无管理员令牌的解析请求返回 `403`；使用测试二维码完成生产解析闭环并正确返回目标链接。

### 发布边界

- 本轮未上传微信体验版，未修改小程序分享链路；真实浏览器页面视觉、真实群二维码投放和真实手机扫码仍需人工验收。

## 2026-08-30：活码扫码问题诊断与真实群头像卡片（本地完成，未部署）

### 本轮完成

- 复核生产现有活码：固定外层入口可正常返回 302，但当前保存的群二维码目标在跟随跳转后返回 404；问题在目标链接本身无效或已失效，不是外层 `/live-qr/{code}` 路由或二维码图案生成失败。
- 活码创建/编辑新增真实群头像上传，使用现有媒体资产处理和去重链路保存 `groupAvatarUrl`；不把原图转 Base64 写入活码记录，也不再绘制虚拟人形头像。
- 投放卡片顶部改为裁切显示运营人员上传的真实微信群头像拼图，未上传时只显示明确的“未上传群头像”提示；头像加载异常不会阻断二维码卡片生成。
- `/ops` 群运营子页面和 `/ops/live-qr` 兼容页面均同步了表单、预览、下载卡片和文案。

### 验证与发布边界

- 活码定向测试：6 passed；全量后端测试：311 passed。
- 两处页面内嵌 JavaScript 分别通过 `node --check`，Python 编译检查和 `git diff --check` 通过。
- 本轮未部署生产；生产当前仍是无真实群头像字段展示的上一版镜像。部署后还需用新鲜的有效群二维码和真实手机微信验收。

### 真实风险

- 活码只能固定跳转到保存的目标地址，不能修复目标地址自身返回 404、过期或被微信限制访问的问题；运营人员需要在列表点击“更换二维码”，上传新的有效群二维码图片并保存。
- 上传二维码图片只能解析链接，不能证明链接长期有效；上传群头像是独立操作，系统无法从二维码内容反推出微信群头像。

## 2026-08-30：真实群头像活码改动已部署生产

### 发布记录

- 生产已切换活码路由、`LiveQrCode.groupAvatarUrl`、运营后台 `/ops` 页面和兼容页 `/ops/live-qr`；上传二维码解析、到期筛选和固定公网入口保持不变。
- 本轮无新增 Python/系统依赖，按既有无构建热修复流程从当前生产镜像制作三个发布镜像；PostgreSQL、生产 `backend/.env`、secrets、媒体目录和数据库卷未覆盖。
- 生产备份：`/home/ubuntu/teambuy-backups/20260830-211240-live-qr-avatar`。
- 发布镜像：`teambuy-backend:deploy-20260830-211240-live-qr-avatar`、`teambuy-backend-worker:deploy-20260830-211240-live-qr-avatar`、`teambuy-archive-worker:deploy-20260830-211240-live-qr-avatar`。
- 回滚标签：对应三个 `rollback-20260830-211240-live-qr-avatar` 镜像标签。

### 生产验证

- API、backend-worker、archive-worker、PostgreSQL 均 healthy；生产端口仍为 `8004 -> 8000`。
- 本机和公网 `/health`、`/health/db` 通过；`/ops` 和 `/ops/live-qr` 已包含真实群头像功能文案。
- 运行中容器文件 SHA-256 与本地上传文件一致；生产活码管理返回 `groupAvatarUrl` 字段，固定入口返回 302。
- 未在生产上传真实群头像或替换现有群二维码，避免替用户改变当前投放数据；需运营人员在页面中手动完成。

## 2026-08-30：重新上传后的活码仍打不开，确认故障在目标链接

- 生产现有新活码 `qr_g2mrjltbw5e` 的外层二维码已解码为 `https://teambuy.lifelove.top/live-qr/qr_g2mrjltbw5e`，固定入口实际返回 302，说明卡片二维码生成、域名和 Nginx 路由均正常。
- 新旧两个活码记录当前都指向同一个 `c.weixin.com/g/...` 群链接；目标有效期字段仍在未来，但从服务端跟随访问、普通浏览器 User-Agent 和微信 User-Agent 检查均返回 404。
- 因此重新生成外层二维码、延长后台 7 天或修改头像都不能修复本次打不开；需要确认原始微信群二维码在微信中直接扫描是否有效。若原始群码也打不开，应从微信群重新生成并上传；若原始群码能打开而外层不能，再改为“落地页展示当前群码/微信内二次识别”的方案。

## 2026-08-30：临时验证落地页二次识别方案（未修改仓库代码）

- 使用用户提供的内层微信群二维码创建临时活码：`qr_fsokeazode`，名称为“临时测试-二次识别-20260830-214405”。
- 在生产媒体卷中放置临时落地页：`/media/live-qr-test-20260830-214405.html`；页面展示内层二维码，并提示在微信中长按选择“识别图中二维码”。
- 临时内层图片通过现有媒体资产接口上传，公网图片和页面均返回 HTTP 200；外层固定入口 `https://teambuy.lifelove.top/live-qr/qr_fsokeazode` 返回 HTTP 302 到临时落地页。
- 外层 QR 图片已下载到本机 `/tmp/teamBuy-live-qr-outer-20260830-214405.png`，供用户用真实微信扫码验证。
- 本轮没有修改仓库源码、Docker 镜像或小程序；临时页面和活码记录属于生产测试数据，验证结束后应暂停或按运营决定处理。

## 2026-08-30：活码列表删除与群人数提醒已部署生产

### 实现内容

- `/ops` 群运营页和 `/ops/live-qr` 兼容页的活码列表在“暂停/恢复”旁新增“删除”；删除前二次确认，删除后固定外层入口立即失效，同时解除当前群头像媒体引用，不立即删除媒体二进制。
- 活码记录新增最近一次群人数与检查时间；提供 `180–199 人` 黄色提醒、`200 人及以上` 红色换群提醒、`人数未检查` 状态和筛选，顶部数字只统计 active 活码，暂停记录不产生换群提醒。
- PC 页面每天按服务器日期对当前 180 人以上记录做一次页内提醒；这不是浏览器/操作系统推送，必须打开该页面才能看到。
- 当前群人数由活码编辑时人工录入，旧记录显示“人数未检查”；现有 Android 群扫描链路尚未回传真实群人数，因此没有把未知人数当作 0。

### 验证与发布

- 活码定向测试：7 passed；backend 全量后端测试：312 passed。
- 两处页面内嵌 JavaScript 通过 Node 语法检查，Python import smoke test 和 `git diff --check` 通过。
- 生产备份：`/home/ubuntu/teambuy-backups/20260830-222226-live-qr-member-reminder`。
- 发布镜像：`teambuy-backend:20260830-222226-live-qr-member-reminder`、`teambuy-backend-worker:20260830-222226-live-qr-member-reminder`、`teambuy-archive-worker:20260830-222226-live-qr-member-reminder`，并切换到三个服务的 `latest` 标签。
- 三个旧镜像保留对应 `rollback-20260830-222226-live-qr-member-reminder` 标签；生产端口保持 `8004 -> 8000`，PostgreSQL、`.env`、secrets、媒体目录和数据库卷未覆盖。
- 生产 `/health`、`/health/db`、公网 `/health` 通过；活码列表鉴权 200、未授权 403、删除不存在记录 404；线上页面已包含新按钮和人数提醒内容。

## 2026-08-30：活码改为落地页二次识别，并接入 7 天默认有效期与自动人数任务（本地完成，待部署）

### 本轮完成

- 外层 `/live-qr/{code}` 已改为固定落地页 `200 HTML`，不再 302 到 `c.weixin.com` 或其他微信群目标。页面展示当前内层群二维码，明确提示用户在微信中长按并选择“识别图中二维码”。
- 活码表单改为上传内层群二维码图片；后台自动解析链接用于校验和诊断，同时用原图像素保存当前二维码供落地页展示。上传/更换成功时服务端强制按当前时间自动设置 7 天有效期，页面移除手动有效期输入。
- 活码列表和兼容页继续保留分页、到期筛选、删除、暂停/恢复、真实群头像和投放卡片；人数不再由 PC 手工录入，旧手工来源显示“未检测”。
- backend-worker 增加每天 08:00（Asia/Shanghai）后的活码群人数任务调度，任务按活码和服务器日期幂等；AScript 群扫描模块可从通讯录或微信会话列表定位群聊，在“聊天信息”页读取人数并通过设备鉴权回传。
- 人数状态继续使用 180–199 黄色提醒、200+ 红色建议换群；未知和过期检测不会按 0 处理。

### 验证与边界

- 活码和自动化定向回归、后端全量测试：`314 passed`。
- 两处 PC 页面内嵌 JavaScript `node --check` 通过；变更 Python `py_compile`、AScript Python 语法检查、`git diff --check` 通过。
- 已完成 JSON/HTML/接口级检查，覆盖 200 落地页无 Location、原图上传、上传后 7 天重置、分页与筛选、人数任务幂等、设备/账号/群名绑定校验。
- AScript 本机设备扫描未发现可连接设备，因此本轮没有真实安卓 UI、OCR、微信扫码或 AScript 任务运行验收；这些必须在设备和微信开发者/真机环境补做。
- 本轮尚未部署生产；生产部署必须将 API、backend-worker、archive-worker 一起切换，并保留旧镜像回滚标签。生产旧活码若未上传内层二维码，部署后会显示“当前群二维码暂未上传”，不会继续使用旧 302 目标。

### 生产发布结果

- 已按受控无构建热修复流程切换 API、backend-worker、archive-worker 三个服务；本轮没有新增依赖，未覆盖生产 `backend/.env`、`backend/secrets/`、媒体目录或数据库卷。
- 备份目录：`/home/ubuntu/teambuy-backups/20260830-233358-live-qr-auto-member/`；三个旧镜像均保留对应 `rollback-20260830-233358-live-qr-auto-member` 标签。
- 当前发布镜像：`teambuy-backend:deploy-20260830-233358-live-qr-auto-member`、`teambuy-backend-worker:deploy-20260830-233358-live-qr-auto-member`、`teambuy-archive-worker:deploy-20260830-233358-live-qr-auto-member`，并已同步到 Compose 使用的 `latest` 标签。
- API、两个 Worker 和 PostgreSQL 均 healthy，端口保持 `8004 -> 8000`；本机 `/health`、`/health/db` 和公网 `/health` 通过。
- 公网固定入口 `https://teambuy.lifelove.top/live-qr/qr_ndejoqudeo8` 返回 `200 text/html` 且无 `Location`；页面包含落地页文案。该旧记录尚未上传当前内层二维码，因此显示未上传提示，不再暴露旧 302 目标。
- 公网 `/ops` 已包含活码新文案，未授权活码管理 API 返回 `403`，未知入口返回 `410`；三个运行容器中的关键源码 SHA-256 与本地上传文件一致。
- AScript 本机没有可连接设备，本轮仍未完成真实安卓 OCR/任务闭环和真实微信二次识别；未上传微信小程序体验版。

## 2026-08-30：暂停无 AScript 条件下的群人数检测，并精简活码落地页（本地修改，待部署）

- 新增 `LIVE_QR_MEMBER_COUNT_AUTOMATION_ENABLED` 配置，默认 `false`；未接入并验证 AScript 前，backend-worker 不创建活码人数检测任务，设备端也不能领取该类旧任务。
- 保留人数数据字段、回传接口和 AScript 扫描代码，未来完成真实设备验收后再显式开启，不把未知人数当作 0。
- 正式 `/live-qr/{code}` 仍返回 200 HTML 且不走 302；有内层二维码时页面只渲染该原图，移除群头像、群名、标题和操作说明；无图时保留未上传提示。
- 已同步更新活码测试、配置示例和 AScript 工具文案；定向活码/自动化测试 22 passed，后端全量测试 315 passed，Python 编译、页面内嵌 JavaScript 语法和 `git diff --check` 均通过。本轮只改本地代码和项目文档，未部署生产。

## 2026-08-31：暂停群人数检测与纯内层二维码落地页已部署生产

- 已按受控无构建热修复流程切换 API、backend-worker、archive-worker；PostgreSQL 保持原容器和数据卷不变，生产 `.env`、secrets、媒体目录未覆盖。
- 生产备份目录：`/home/ubuntu/teambuy-backups/20260831-000348-live-qr-no-ascript/`。
- 发布镜像：`teambuy-backend:20260831-000348-live-qr-no-ascript`、`teambuy-backend-worker:20260831-000348-live-qr-no-ascript`、`teambuy-archive-worker:20260831-000348-live-qr-no-ascript`，并同步为 Compose 使用的 `latest` 标签；旧版本保留 `rollback-20260831-000348-live-qr-no-ascript` 标签。
- 生产三个应用容器和 PostgreSQL 均 healthy，端口保持 `8004 -> 8000`；`/health`、`/health/db`、公网 `/health` 通过。
- 公网活码 `qr_3zi4ilfiwk` 返回 200、无 `Location`，页面无群名/头像/说明，仅展示内层二维码图片；内层图片公网返回 200，未授权活码管理 API 返回 403。
- 三个运行容器的群人数开关均为 `False`，关键文件 SHA-256 与本地一致；最近日志未发现 API 或 backend-worker 的 ERROR/Traceback。

## 2026-08-31：互帮互助统一积分架构与首版页面视觉稿（讨论稿）

### 本轮完成

- 新增架构讨论稿 `docs/stage2-docs/44-my-tools-mutual-help-architecture-v1.md`，将互帮互助收敛为单一 `mutualPoints`：初始 100 分、任务消耗、执行收入、首页排序和 PC 规则配置均围绕这一字段展开。
- 明确首页默认按发布者当前互助积分倒序，支持切换为执行者可获得赏金倒序；服务端排序并保证分页稳定，不新增独立信誉分。
- 明确小程序任务采用用户指定的 `shortLink` 跳转；返回后反馈文字和图片均可选。普通任务保留标题、内容、交付标准、材料类型、奖励等最小字段。
- 明确连续三名不同执行者有效提交被拒绝时暂停任务、降级发布者，并优先从冻结额度返还执行者积分；保留拒绝理由、处罚和申诉记录。
- 新增五屏 SVG 视觉稿 `docs/stage2-docs/visuals/my-tools-mutual-help-v1.svg`，用于先确认首页、任务详情/提交、发布任务和我的工具的页面方向；本轮没有修改业务代码、数据库、生产配置或微信体验版。

### 验证与边界

- 已读取并遵守项目接手文档、部署文档和现有工作区状态；没有执行 reset、checkout、删除或生产操作。
- 已通过 XML 结构检查和 `git diff --check` 验证本轮新增文档/视觉稿；视觉稿只代表讨论方向，不代表小程序真机适配完成。

## 2026-08-31：互帮互助视觉稿按反馈调整为顶部 Tab（讨论稿）

### 本轮完成

- 任务卡片的 `+4 分` / `+8 分` 已移动到卡片右上角，发布者积分继续放在卡片信息区。
- 移除五个画面内的底部 TabBar，增加互帮互助模块顶部的 `首页 / 发布 / 任务 / 我的` 四个 Tab；详情/提交页高亮“任务”。
- 在架构文档补充第一性原理检查：以“找任务 → 看懂标准 → 完成提交 → 验收结算”为唯一首版闭环，并补充冻结积分、幂等、防重复结算、超时验收、补交/申诉和任务终态等最小规则。

### 验证与边界

- SVG XML 解析、PNG 重新导出和 `git diff --check` 通过；已打开 PNG 人工检查顶部 Tab、奖励位置和 CTA 与底部安全空间。
- 本轮仍只修改架构/设计资产和项目记录，没有修改业务代码、数据库、生产配置或微信体验版。

## 2026-08-31：普通任务增加可选任务次数（讨论稿）

### 本轮完成

- 根据用户反馈，普通任务发布表单新增“任务次数（可选）”，支持设置 3 次、5 次等成功验收上限；留空表示次数不限。
- 达到任务次数后，任务自动显示为“已完成/已下架”，前端不再允许点击完成，服务端也要拒绝超额完成请求；成功次数按验收结算数量计算。
- 按用户意见移除“发布时预冻结积分”作为第一期规则：任务发布不扣、不冻结积分；每次结算前检查余额，余额不足以支付下一笔时任务暂停/下架，积分不扣成负数。
- 第 4 屏视觉稿改为“普通任务发布”状态，展示任务内容、交付标准、任务次数（可选）和奖励积分。

### 验证与边界

- SVG XML、PNG 重新导出和 `git diff --check` 通过；本轮没有修改业务代码、数据库、生产配置或微信体验版。

## 2026-08-31：任务图片预览与本地演示结算规则补齐

### 本轮完成

- 任务管理卡片不再把原始长截图作为矮框封面；优先使用已经生成的固定 5:4 任务分享图，保持比例并提示“点击任务查看完整图片”。详情页继续用 `widthFix` 原比例展示，支持微信放大滑动和保存相册。
- 互帮互助首页移除重复的“我的工具”眉标题，并补充说明：任务大厅只展示其他用户可完成的任务，用户自己发布的任务在“任务”Tab管理。
- 本地演示提交记录改为可按任务聚合，普通任务提交后进入发布者管理详情的待验收列表；发布者通过验收后扣发布者积分、给执行者发放 0.8 倍积分。
- 小程序任务在执行者成功打开目标小程序并明确点击“提交完成”后立即结算；普通任务提交后 5×24 小时发布者未处理时自动通过。结算操作具备本地幂等保护，余额不足不扣成负数。

### 验证与边界

- 相关 JavaScript `node --check`、互帮互助 JSON 解析、结算流程 mock（普通任务人工验收、小程序即时结算、5 天自动通过）、`git diff --check` 通过。
- 本轮未修改后端、生产配置、数据库、活码链路，未部署生产，未上传微信体验版。
- 任务和积分仍是本地演示存储，跨设备任务大厅、服务端原子次数、真实积分流水和生产媒体 URL 仍需后端实现。

## 2026-08-31：互帮互助页面第二轮视觉与交互调整

### 本轮完成

- 互帮互助首页顶栏去掉重叠的“互帮互助 / 我的工具”右侧标题；其他模块页也移除会挤压标题的 `rightText`，保留各自页面标题。
- 本地演示积分命名空间升级为 v2，旧测试产生的 0 分不会覆盖约定的首次 100 分；真实生产积分仍未接入。
- 四个互帮互助页面顶部新增浅色 / 深色主题切换，主题选择写入本地演示偏好；深色模式同步处理页面、卡片、表单、占位提示和返回按钮对比度。
- 任务大厅新增可记忆的 `1x / 2x` 卡片布局；2x 使用双列网格并收紧卡片信息密度，默认仍为 1x。
- 普通任务分类扩展为下载 App、注册/登录体验、页面/功能体验、问卷/反馈、图片/视频标注、文本校对、资料整理、商品信息核对和其他；普通任务卡片显示实际分类。

### 验证与边界

- JavaScript 语法、JSON、WXML 标签栈、互帮互助路由与主题/布局静态接线检查，以及 `git diff --check` 通过。
- 本轮只修改小程序页面、共享演示适配器、公共自定义导航和项目记录；未修改后端、生产配置、数据库或微信体验版。

## 2026-08-31：互帮互助发布表单改为有序图文内容段

### 本轮完成

- 普通任务的“任务内容”和“验收标准”从“单独文字框 + 图片列表”改为有序内容段编辑，可按“文字段 → 图片段 → 文字段”添加和展示。
- 文字段支持单独编辑，图片段支持预览和删除；不强制每个任务都拆成步骤，发布者需要流程说明时可在文字段中自行写“步骤1、步骤2”。
- “添加图片”由高大的方形按钮改为紧凑的横向按钮，发布表单和提交材料区域共用样式。
- 演示积分增加一次性种子版本标记：旧演示缓存中的 0 分首次读取会初始化为 100 分；后续保存的 0 分仍可保留，真实生产必须改用服务端积分流水。
- 首页积分卡改为“余额主信息 + 排序提示 + 规则按钮”的结构，规则按钮固定为小尺寸，避免空白和按钮比例失衡。

### 验证与边界

- 相关 JavaScript 语法、四个 WXML 标签结构、内容块顺序和演示积分初始化检查通过；未部署生产、未修改后端、未上传微信体验版。
- 当前图片仍是本地演示路径；真实发布前必须接入媒体资产登记和受控 URL，不能把临时 `wxfile` 路径写入生产任务。

## 2026-08-31：任务详情图片改为原比例预览并支持保存相册

### 本轮完成

- 发布页图片段缩略图改用 `aspectFit`，保留完整图片内容，不再使用方形裁切。
- 任务详情页内容图和验收图改为 `widthFix` 原比例展示，移除固定最大高度，避免长图被压缩或截断。
- 点击详情图片调用微信原生 `wx.previewImage`，支持放大和左右滑动浏览该任务全部内容图片。
- 图片下增加“保存到相册”；远程图片先通过 `wx.downloadFile` 转为本地临时文件，再调用 `wx.saveImageToPhotosAlbum`，相册权限拒绝时可进入设置。
- 提交材料缩略图也改为等比完整显示。

### 验证与边界

- 相关 JavaScript、WXML 结构、图片预览图库组装和远程图片保存调用模拟检查通过；未部署生产、未上传微信体验版。
- 真机仍需验证超长图片滚动高度、下载域名白名单、相册授权弹窗和不同图片格式的保存结果。

## 2026-08-31：小程序任务增加卡片式目标入口

### 本轮完成

- 小程序任务详情页增加卡片式目标入口，展示任务标题、进入说明和箭头；卡片点击与底部“打开小程序”按钮共用目标跳转逻辑。
- 目标仍使用发布者提供的微信小程序分享短链接，通过 `wx.navigateToMiniProgram({ shortLink })` 打开；返回后才允许提交完成。
- 明确卡片是当前小程序自己的 UI，不是把另一个小程序嵌入当前页面，也不能伪造目标小程序的微信原生分享卡片。
- 详情页卡片同步适配深色模式，保留目标跳转失败和任务已结束的反馈。

### 验证与边界

- JavaScript 语法、WXML 结构和卡片跳转入口静态检查通过；未执行微信开发者工具真机跳转。
- 真实验收需使用有效目标短链接，确认跳转成功、返回当前任务页、状态变为可提交；模拟器结果不作为最终结论。

## 2026-08-31：互帮互助按发布者/执行者拆分任务页面

### 本轮完成

- 顶部“任务”入口改为发布者任务管理列表；发布者只看到自己发布的任务，支持全部、进行中、已暂停和已结束筛选。
- 发布任务成功后进入对应的发布者管理详情，不再误进入执行者提交页面；管理详情展示发布进度、待验收数量、任务内容和验收标准，并提供分享、预览执行者页面和暂停/恢复发布入口。
- 分享路径和任务大厅仍进入执行者任务详情；执行者详情移除模块内四 Tab，只保留完成任务所需信息。发布者打开执行者页时显示只读预览，不能打开目标或提交自己的任务。
- 任务大厅按当前用户过滤已提交、已结束和自己发布的任务，避免执行者完成后只因本地状态变化造成错误的全局删除假象。
- 公共互帮互助样式的主要卡片、表单字段和区块分隔线调整为 `2rpx`，管理页新增进度卡、状态标签和待验收空态，并同步适配深色模式。

### 验证与边界

- 相关 JavaScript 通过 `node --check`；`app.json` 和新增页面 JSON 解析通过；6 个互帮互助 WXML 标签结构检查通过；路由、角色页、发布后跳转、任务大厅过滤和 2rpx 分隔线静态检查通过；`git diff --check` 通过。
- 本轮未修改后端、生产配置、数据库或活码链路，未上传微信体验版。
- 任务管理待验收列表、跨设备任务查询、真实积分结算和任务专用分享图 `imageUrl` 仍需后端接口与真机验收；当前不能把本地演示状态当成生产结果。

## 2026-08-31：任务发布支持图文内容，并确定我的工具分包方向（讨论稿）

### 本轮完成

- 架构文档补充：普通任务的任务内容和验收标准均支持文字、图片或图文混合，允许只上传一张说明图/流程图；内容使用有序 `text/image` 内容块表达。
- 明确图片仍必须复用现有媒体资产登记、哈希去重和受控访问链路；第一期不做复杂富文本编辑器。
- 根据当前 `miniprogram/app.json` 已有 `subpackages.workbench` 的事实，确定“我的工具”后续按业务域使用普通分包；互帮互助和未来微信群原则上分开，不使用独立分包。

### 验证与边界

- 本轮只更新架构、视觉稿和项目记录，没有迁移页面、修改业务代码、数据库、生产配置或微信体验版。
- 分包边界仍需在开发阶段结合微信开发者工具的实际包体积、依赖分析和冷启动耗时确认；当前结论是架构方向，不代表已经完成分包迁移。

## 2026-08-31：实现我的工具与互帮互助页面（页面交互阶段）

### 本轮完成

- 在 `miniprogram/subpackages/my-tools` 新增“我的工具”入口页，当前展示互帮互助和未来微信群工具占位。
- 在 `miniprogram/subpackages/my-tools-mutual-help` 新增首页、任务详情/提交、发布任务、我的工具四个页面；四个入口固定在页面顶部，不触碰全局底部 TabBar。
- 发布普通任务支持任务分类、任务次数、最低 5 分奖励、任务内容和验收标准的文字/图片/图文混合输入；详情页支持普通任务文字/图片提交。
- “我的”页新增进入“我的工具”入口。

### 验证与边界

- JavaScript 语法、JSON、路由文件齐全、WXML 标签结构和 `git diff --check` 通过。
- 当前使用本地演示适配器，没有新增后端接口；真实任务共享、媒体资产登记、积分流水和微信真机验收待下一阶段。

## 2026-08-31：接入互帮互助任务专用分享图

### 本轮完成

- 修复任务分享回调只返回标题和路径、未返回 `imageUrl` 的核心缺口；新增 `task-share.js`，统一为任务详情生成固定 `750×600` 的专用 JPG 分享图。
- 复用现有 `share-snapshot` 插件和 `/api/uploads/share-snapshot` 上传接口；任务源可携带任务类型、奖励、剩余次数、截止信息，普通任务有内容图片时使用图片优先卡片。
- 发布者管理详情和执行者详情均挂载隐藏 Canvas，图片上传成功前分享按钮保持禁用；`onShareAppMessage` 没有可用专用图片时返回 `null`，不会再让微信截取默认长页面。
- 任务快照带样式版本、源版本和指纹，并保存到本地演示任务，避免同一设备重复生成未变化的分享图。

### 验证与边界

- `node --check`、任务分享源/回调 mock、WXML 标签结构和 `git diff --check` 通过。
- 未执行微信开发者工具真实编译、真实聊天转发、跨设备打开或生产部署；当前本地任务仍未接入服务端 `MutualTask`，跨设备好友打开详情仍需后端任务查询和分享 token。

## 2026-08-31：补充任务类型与验收标准字段（讨论稿）

### 本轮完成

- 根据讨论补充“验收标准”字段：普通任务发布时必填，使用多行文本说明提交材料、通过条件和补交方式；详情和提交页展示原文。
- 明确不使用标题猜任务类型：顶部 `小程序任务 / 普通任务` 切换直接写入必填 `taskKind`，普通任务另外使用轻量 `taskCategory` 分类选择，不增加重复的任务类型输入框。
- 小程序任务的验收标准采用有效打开、返回和停留条件；反馈文字和图片仍可选，不能以可选反馈替代完成条件。
- 第 4 屏普通任务发布稿增加“分类：文本校对”，并将“交付标准”统一改为“验收标准”。

### 验证与边界

- SVG XML、PNG 重新导出和 `git diff --check` 通过；本轮没有修改业务代码、数据库、生产配置或微信体验版。
## 2026-08-31：任务管理列表外部分享、删除与目标小程序预览修复

### 本轮完成

- 任务管理 Tab 的任务卡改为接近微信 5:4 分享卡的信息层级：类型标签、执行者奖励、资料整理助手标识、图片/任务图标预览、标题、摘要、次数与验收进度。
- 分享入口移到每张任务卡外部的独立操作区；详情页不再放分享按钮。列表后台按任务逐个预热任务专用分享图，按钮只有在该任务的 `imageUrl` 准备完成后才可点击。
- `onShareAppMessage` 从分享按钮 `dataset.id` 精确选择任务，并返回该任务自己的详情路径和静态 `imageUrl`，不会复用另一条任务的分享图，也不会退回详情页截图。
- 任务删除采用本地演示阶段的软删除：状态标记为 `deleted`，从任务管理列表和任务大厅隐藏，但不改写已有记录；修复删除全部任务后演示任务自动复活的问题。
- 目标小程序入口对所有用户开放。发布者管理详情的目标小程序卡片可点击，执行者详情不再因 `isOwner` 被拦截；发布者仍不能在执行者页面提交或结算。
- 跳转失败回调保留真实错误日志，并区分用户取消与目标小程序不可打开。

### 验证与边界

- 已通过互帮互助 JavaScript 语法检查、分享消息按任务 ID 的模拟检查、无 `imageUrl` 阻断检查、删除空数组持久化检查、WXML 分享/删除/目标入口结构检查和 `git diff --check`。
- 本轮未部署生产、未上传微信体验版；任务仍是本地演示适配器，跨设备任务查询、后端任务删除/分享权限、提交验收和积分流水仍未接入。
- 目标小程序跳转仍使用发布者提供的微信短链接；真实跳转必须用已发布目标在微信真机验收。

## 2026-08-31：互帮互助第一期接入羊毛任务与评论交互

### 本轮完成

- 将“羊毛”接入共用任务模型：新增 taskKind=wool，复用普通任务的标题、分类、任务次数、文字/图片内容段、验收标准和多任务入口，不另造一套任务详情结构。
- 发布页新增羊毛策略：免费查看或一次性付积分解锁、可选固定完成奖励、完成后可自愿打赏发布者；固定奖励为 0 时不误显示为普通任务的最低奖励。
- 羊毛详情页新增解锁卡片、一次性解锁扣分、评论摘要与“值得做/一般/不建议”标签、评论举报、失效任务退款申请和完成后打赏入口。评论和举报记录采用本地演示存储，退款申请状态已为后续 PC 端处理预留。
- 普通任务与羊毛任务共用评论展示和评论发布入口；羊毛未解锁时可看评论，但完整内容、任务入口、验收标准和提交入口保持隐藏。
- 首页任务大厅新增“羊毛”筛选；用户自己发布的未删除任务仍显示在大厅，即使因余额不足暂停，也不被前端用任务可执行状态误隐藏。
- 任务专用分享图源增加羊毛语义：展示“免费查看/解锁 N 分”“完成奖励/可自愿打赏”和剩余次数，仍由专用 imageUrl 发送，不回退微信默认页面截图。

### 验证与边界

- 互帮互助目录 JavaScript 通过 node --check；小程序 JSON 解析、WXML 标签结构、git diff --check 通过。
- 本地 mock 已验证：羊毛一次性解锁幂等、解锁积分转移、评论摘要、重复举报幂等、打赏积分转移和退款申请去重；分享源能输出羊毛专用事实字段。
- 当前仍是本地演示适配器，没有新增后端任务、评论、举报、退款或积分流水接口；PC 端退款/举报审核页面尚未实现。
- 本轮未部署生产、未修改生产数据库和活码链路、未上传微信体验版；真实跨用户共享、服务端原子扣分、媒体资产登记和微信真机验收待下一阶段。

## 2026-08-31：修订羊毛任务为非验收型福利入口

### 本轮完成

- 发布页按三种任务类型显示不同的首次理解文案、标题示例、入口名称、内容提示、分类和结算说明。
- 羊毛不再要求验收标准；发布数据使用空的 acceptanceCriteriaBlocks 兼容旧结构，但不再生成固定完成奖励。
- 羊毛详情改为“摘要/评论 → 解锁 → 福利说明/使用入口 → 可选打赏”，隐藏提交材料、验收和 5 天自动通过路径。
- 羊毛解锁、评论、举报、退款和打赏能力保留；免费羊毛不显示解锁退款入口。普通任务和小程序任务原有提交/结算流程保持不变。
- 羊毛和普通任务使用更清晰的分类；任务管理页对羊毛显示解锁和评论信息，不再显示待验收数量。
- 羊毛填写可选次数时按查看/解锁名额处理：首次进入免费羊毛或首次付费解锁消耗一次，重复操作不重复消耗。

### 验证与边界

- 相关 JavaScript 通过 node --check，互帮互助目录 JSON 解析通过，git diff --check 通过。
- 已用本地 mock 验证：羊毛策略不再暴露固定完成奖励；羊毛空验收内容可以通过发布校验；普通任务仍要求验收内容。
- 当前仍是单设备本地演示，尚未接入服务端任务、评论、解锁、退款和统一积分流水；未部署生产、未上传微信体验版。

## 2026-09-01：互助积分充值与 PC 业务工作台上线准备

### 本轮完成

- 增加互助积分账户、积分流水、充值订单和业务活动事件的服务端模型及 PostgreSQL 表；首次访问账户自动发放 100 分，并以流水记录作为来源。
- 接入充值订单、微信支付 JSAPI 预支付和微信支付回调；开发/测试模式保留显式 test-confirm，生产环境不允许测试确认冒充真实支付。
- 小程序“我的”增加充值入口和充值页；当前充值默认开启并显示，提现默认关闭且隐藏。后续提现规则固定为保留 300 分，当前只展示规则，不开放提现。
- PC 业务工作台增加“互助积分”子 Tab，显示今日、近 7 日和总量的发布任务、完成任务、充值笔数，并提供充值/提现的“启用”和“显示”开关。
- 管理接口复用现有单管理员认证，不新增互助功能专用 token；开关配置写入已有 `ops_feature_flags`，数据库异常时按关闭/不可用处理。
- 任务发布和完成事件已向服务端活动统计上报，使用幂等键避免重复计数；未上传微信小程序体验版，活码 200 HTML 与 AScript 关闭配置未改动。

### 验证与边界

- `backend/tests` 全量通过：317 passed；互助积分专项测试 2 passed；Python 编译、相关小程序 JavaScript 语法、JSON 解析和 `git diff --check` 通过。
- 当前服务端充值账户和统计已经具备生产接口，但互助任务本身仍是本地演示任务引擎；发布者/执行者的跨设备任务、扣分、加分、验收、羊毛解锁及评论等尚未全部迁移为服务端统一账本。
- 因此本轮不能把“任务完成后真实积分结算”描述为已上线能力；当前上线范围是充值账户链路、配置开关和统计事件链路，正式任务结算仍需下一阶段公共任务引擎。

### 生产部署结果

- 已按腾讯云真实同步文档完成精确备份：`/home/ubuntu/teambuy-backups/20260901-015500-mutual-recharge/`。
- 已部署 API 镜像 `teambuy-backend:20260901-015500-mutual-recharge-api2`、任务 Worker 镜像 `teambuy-backend-worker:20260901-015500-mutual-recharge`、归档 Worker 镜像 `teambuy-archive-worker:20260901-015500-mutual-recharge`，并同步为 Compose 使用的 `latest` 服务标签。
- 生产 API、两个 Worker、PostgreSQL 均 healthy；`127.0.0.1:8004` 与公网 `https://teambuy.lifelove.top/health` 正常，互助新表已创建，PC 管理 Tab 与开关接口已验证。
- 生产固定活码回归通过：当前入口 HTTP 200、无 `Location`，页面内层二维码图片 HTTP 200；AScript 人数检测仍关闭。

## 2026-09-01：互帮互助文案收口、分享卡口径和大厅行为修正

### 本轮完成

- 清理互帮互助首页、任务详情、任务管理、发布、充值和“我的”中的内部解释性文案；移除大厅下方关于排序机制和“自己的任务如何展示”的说明，保留完成任务所必需的操作提示。
- 分享卡不再把 `#小程序://...` 或网页地址当作任务摘要；无自然摘要时按任务类型生成简短说明，任务类型标签统一为“小程序任务 / 羊毛 / 普通任务”，底部统一为“点开任务，完成后赚积分”。
- 分享卡营销语“互助赚积分，让别人帮你完成”在无图信息卡中上移到标题区；互帮互助任务使用独立的 `mutual_task_share_v2` 快照版本，旧任务图会按版本重新生成，不影响资料/名片/合集继续使用生产兼容的 `share_card_v10`。
- 大厅排序改为优先读取发布者当前互助积分；没有用户归属的演示种子任务继续使用种子积分。自己的任务保留在大厅，详情页允许发布者以普通执行流程自行完成，完成后从当前可执行列表移除。

### 验证与边界

- 互帮互助 JavaScript、分享插件和渲染器 `node --check` 通过；小程序全量 JSON 解析和 `git diff --check` 通过。
- 分享源已验证原始小程序短链不会进入卡片摘要；最终 `onShareAppMessage` 复核确认正常快照返回任务详情 `path` 和 HTTPS `imageUrl`，旧样式快照、结束任务和未准备快照均阻断分享；当前积分排序和自助完成行为 smoke 通过。
- 本轮只修改小程序文案、任务列表/详情行为和分享卡渲染；未修改后端、数据库、生产配置或生产镜像，未上传微信体验版。
- 需要重新生成分享快照后，才能在微信聊天卡片中看到新文案；微信分享气泡底部的“未发布的小程序 / 开发版”属于微信开发者工具状态，不由卡片代码控制。
- 互帮互助任务、评论、羊毛和积分结算仍主要是本地演示逻辑；“发布者自己完成自己的任务”当前也只在本地演示账本中生效，正式开放前需确认服务端是否允许同一用户同时作为发布者和执行者。

## 2026-09-01：互帮互助三处营销提示暖色统一

### 本轮完成

- 根据用户对视觉稿的反馈，确认互帮互助沿用原有暖风，而不是前一版效果图的蓝色主导风格。
- 任务大厅积分卡下方新增统一营销提示区：`互助赚积分，让别人帮你完成`，并用暖米白、陶土橙和焦糖色表达“完成别人任务 → 获取积分 → 发布自己的需求”。
- 任务详情新增同款营销提示区；普通/小程序任务额外把 `+N 分` 作为奖励主信息展示，羊毛任务继续保留独立的解锁语义。
- 任务专用分享图新增营销语字段；仅 `templateKind=mutual_task` 使用暖色分享卡调色板，文字信息卡和有图信息卡均保持 5:4 固定尺寸，其他资料/名片/合集分享模板不变。

### 验证与边界

- 互帮互助目录全部 JavaScript、分享插件和分享渲染器均通过 `node --check`。
- 小程序全部 JSON 解析通过；任务分享源 smoke 验证营销语和 `+4 分` 事实字段；目标文件无尾随空格，`git diff --check` 通过。
- 本轮未修改后端、数据库、生产配置或生产镜像，未创建生产充值订单，未调用 test-confirm，未上传微信体验版。
- 当前任务和积分仍主要是本地演示数据；需要用户在微信开发者工具清缓存、重新编译并手动预览/上传后，人工确认三处真机效果和分享卡最终图片。

## 2026-09-01：积分核心可扩展化与 Git 安全检查点

### 本轮完成

- 在开始实现前，已将当前包含多轮既有前端、后端、活码、互帮互助和积分充值改动的工作区完整提交为 Git 检查点：`93688f6 chore: checkpoint before extensible points core`。没有执行 reset、checkout、删除或批量清理。
- 新增 `backend/app/services/points_core.py`，统一提供积分账户初始化、发放、消耗、双边转移和流水查询；通过 `accountType` 支持后续工具复用同一账户体系，并通过来源字段和幂等键追踪业务动作。
- 互助积分首次 100 分和充值入账已切换到积分核心；充值流水带有 `recharge:<orderId>` 幂等键和充值订单来源信息。互助积分状态接口补充最近流水，并增加 `/api/scrm/mutual-help/ledger` 查询接口。
- PostgreSQL 兼容字段增加账户类型、来源类型和来源 ID，并增加用户/账户类型约束索引；保留原有互助积分表和接口，未进行生产迁移。

### 验证与边界

- `./.venv312/bin/pytest -q backend/tests/test_mutual_help_points.py backend/tests/test_points_core.py`：4 passed。
- `./.venv312/bin/python -m compileall -q backend/app backend/tests/test_mutual_help_points.py backend/tests/test_points_core.py` 通过；`git diff --check` 通过。
- 本轮没有部署生产、没有创建生产充值订单、没有调用 test-confirm、没有上传微信体验版；互帮互助任务前端仍是本地演示，尚未调用该核心完成正式任务结算。
- 当前实现的跨用户转账在应用层保持单次操作语义；正式接入多副本生产任务前仍需增加 PostgreSQL 行锁/事务级并发验证。

## 2026-09-01：我的工具入口收回我的页

### 本轮完成

- 将“我的”页的“我的工具”从单行大卡改为三列自适应宫格，与“我的资产”的入口密度保持一致。
- 互帮互助入口改为直接进入互帮互助首页，减少重复目录页和内部解释文案。
- 暂未开放的“微信群工具”保留为禁用宫格项，显示“即将上线”，点击只给出轻量提示，不伪造功能可用状态。
- 旧的 `subpackages/my-tools` 页面和路由文件保留，作为兼容路径，不再作为“我的”页的标准入口。

### 验证与边界

- 小程序页面 JavaScript `node --check`、79 个小程序 JSON 解析、旧个人页工具样式引用检查和 `git diff --check` 均通过。
- 本轮只修改小程序“我的”页入口及项目文档，没有后端、数据库、生产配置或生产镜像变更。
- 小程序不能通过服务器部署生效；需要用户在微信开发者工具中重新编译、真机预览并手动上传体验版。本轮不自动上传。

## 2026-09-01：隐藏已上线状态并核对互帮互助订阅消息

### 本轮完成

- 从“我的”页互帮互助宫格移除“已上线”状态，只保留入口名称；兼容旧“我的工具”页面同步不显示可用工具的上线状态。
- 只读核对生产容器：当前生产为互助积分/充值版本，完整互帮互助任务服务端仍未部署。
- 核对现有订阅消息链路：生产已有订阅消息环境配置、`/api/scrm/notification-config`、授权记录接口和发送 Worker，但业务范围是客户查看/留言提醒，尚未接入互帮互助任务状态通知。

### 订阅消息待办与边界

- 不替换现有“未读消息提醒”模板；建议在微信后台另申请任务进度/处理结果类模板，拿到模板 ID 和字段详情后再新增独立配置。
- 首期订阅通知建议覆盖发布者的“新提交待处理”和执行者的“审核结果”，并分别在发布/提交等用户点击动作中请求一次性授权。
- 本轮未修改订阅消息后端、未修改生产配置、未创建生产测试订单、未部署服务器；小程序仍需用户手动重新编译和上传体验版。

## 2026-09-01：接入互帮互助任务进度订阅模板配置

### 本轮完成

- 接入用户提供的“任务进度更新通知”模板：`thing1` 任务名称、`phrase2` 任务进度、`time3` 更新时间、`thing4` 执行人、`thing5` 发起人。
- 新增互帮互助专用环境配置 `WECHAT_MINIAPP_MUTUAL_HELP_SUBSCRIBE_TEMPLATE_ID`、字段映射和跳转页；本地 `.env` 已写入用户提供的模板 ID，生产 `.env` 未修改。
- `/api/scrm/notification-config` 增加 `mutualHelp` 模板配置；订阅授权记录增加 `purpose=mutual_help_task`，不再要求客户信息链路开关才能记录互助模板授权。
- 小程序订阅服务增加互帮互助用途选择和独立并发键，保留原有客户提醒调用方式不变。
- 当前没有把授权弹窗接到本地任务发布/提交按钮，也没有伪造任务通知发送；待服务端任务引擎接入后再连接两类真实事件。

### 验证与边界

- `backend/tests/test_subscription_notifications.py`：11 passed；Python 编译、小程序 JavaScript 语法、79 个 JSON 解析和 `git diff --check` 均通过。
- 本轮没有部署服务器、没有修改生产 `.env`、没有创建生产测试订单、没有调用 `test-confirm`、没有上传微信体验版。
- 模板配置已在本地代码和本地环境就绪；生产要生效仍需按部署文档备份后同步配置与代码，并在真实任务后端可发送时人工验收。
