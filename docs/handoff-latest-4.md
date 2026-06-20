# teamBuy 阶段性交接归档 4

更新时间：2026-06-20

工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`

当前分支：`main...origin/main [ahead 14]`

## 1. 项目背景与目标

当前正式产品名是“资料整理助手”。项目面向微信私域里的房产中介和团购团长，目标不是做完整 CRM、电商平台或支付平台，而是跑通并产品化这条主链路：

```text
微信/企业微信素材
  -> 企业微信客服 sync_msg 或会话内容存档
  -> ContentObject
  -> content-to-note
  -> UserNote 资料卡
  -> 小程序编辑、整理、生成客户页
  -> 客户浏览、留资、预约、商品下单/接龙、站内留言
  -> 发布者查看线索、订单、消息和客户动作
```

第一优先用户是房产中介，第二优先用户是团购团长。当前不做正式交易平台，不做支付、库存扣减、物流、退款、核销、分账或复杂 PC 后台。商品“下单”目前是轻订单/意向单，底层复用 `customer_actions.order-intent / relay-intent`。

长期架构遵循 `docs/stage2-docs/08-plugin-architecture.md`：稳定基座负责企业微信通信、身份识别、会话管理、合规、支付权益、笔记库和展示页；可插拔 Skill 只负责内容处理能力。

## 2. 当前阶段目标

P0 主链路已经基本闭环，当前刚完成以下关键收口：

- OCR 两段式：先保存图片资料，用户再主动识别图片文字。
- 企业微信纯图片导入：无正文、无链接、仅图片且图片已转存时，先生成 `image_ocr` 图片资料，状态 `pending`。
- PaddleOCR 生产启用并隔离到子进程，避免 OCR native 依赖拖垮 Uvicorn 主进程。
- identity-core P0 收窄：小程序微信 `openid` 是唯一身份锚点；企业微信 `external_userid` 只做内部来源映射，不做用户侧解绑/改绑/绑定管理。
- 企业微信真实图片 OCR 闭环已跑通。
- Docker 开发期改为可挂载模式，减少反复 build 产生的缓存压力。

下一阶段建议进入 P1，优先做“展示页构建器 V1”，让用户从资料库勾选多条资料，配置店名/简介/banner/联系方式并生成可分享的小程序展示页。

## 3. 已完成的功能

### 3.1 企业微信导入主链路

- 企业微信客服回调和 `sync_msg` 过渡入口已接入。
- 会话内容存档已开通并接入 `/api/wecom/archive/pull` 和 `/api/wecom/archive/process`。
- 会话存档真实消息链路已跑通：拉取、解密、原始归档入库、`ContentObject -> content-to-note -> UserNote`。
- 会话存档媒体转存已实现：`sdkfileid -> GetMediaData -> 服务端媒体处理/转存 -> UserNote.media.url`。
- 归档 parser 已插件化初步收口，`archive_message_parsers.py` 有注册式 parser。
- `chatrecord` 已能解析 `ChatRecordText` 文本，过滤 `[图片]` / `[视频]` 占位，支持商品/团购内容识别。
- 企业微信 `weapp` 小程序卡片会保留 `structuredData.miniapp`，贝壳卡片只给中置信房源提示，不伪造字段。

### 3.2 资料卡和类型识别

- `UserNote` 已作为正式资料模型使用。
- `visibilityConfig.cardType/cardState/structuredData/typeSuggestions` 承载 typed card 第一版。
- 已支持：
  - `property_listing` 房源字段卡。
  - `groupbuy_product` 商品展示/团购兼容类型。
  - `text_note` 普通资料。
  - `image_ocr` 图片/OCR 资料。
  - `link` 链接收藏卡。
- 类型识别已可解释：`recognitionExplanation` 记录候选类型、分数、命中字段、信号和选择原因。
- 中置信人工确认接口已实现：`POST /api/notes/{note_id}/confirm-type`。

### 3.3 OCR 两段式与生产验证

- 新增两段式 OCR 接口：
  - `POST /api/ocr/images`：只保存图片资料，`structuredData.ocr.status=pending`。
  - `POST /api/ocr/notes/{note_id}/recognize`：对已有图片资料执行 OCR 并回写同一条资料。
  - 兼容保留旧 `POST /api/ocr/image-to-note`。
- 小程序“我的笔记”页入口从“图片识别”改为“保存图片”。
- 小程序资料编辑页新增 OCR 操作区，用户主动点击“识别图片文字”。
- OCR 未配置或识别为空时，图片仍保留，用户可手动补正文和字段。
- 生产已启用 PaddleOCR：
  - `OCR_PROVIDER=paddle`
  - `paddlepaddle==3.3.1`
  - `paddleocr==2.10.0`
- PaddleOCR 已改为子进程 worker：`backend/app/services/paddle_ocr_worker.py`。
- 生产真实图片闭环已完成：
  - 用户 2026-06-20 07:36 左右通过企业微信发送图片。
  - 归档消息 `seq=28`，`msgType=image`。
  - 生成资料 `note_f01130a526`。
  - 图片已转存为 `/media/...webp`。
  - 小程序触发 `POST /api/ocr/notes/note_f01130a526/recognize` 返回 200。
  - OCR 状态 `done`，provider `paddle`，confidence 约 `0.948`。
- 说明：当前 OCR 是识别图片里的文字，不是“看图识物”。普通照片没有明显文字时，可能返回空或低价值文本。

### 3.4 身份归属

- 小程序真实微信登录已实现：`POST /api/auth/wechat-login` 通过 jscode2session 换 `openid`。
- 生产已配置 `WECHAT_MINIAPP_APPID / WECHAT_MINIAPP_SECRET`，真实用户 `user_25ec00a0f0` 已创建。
- 用户确认 P0 身份方案收窄：
  - 小程序微信 `openid` 是唯一身份锚点。
  - `userId` 只是后端内部主键。
  - 企业微信 `external_userid` 只做系统内部来源映射到 `ownerOpenid/ownerUserId`。
  - 第一次认领导入后写入映射，后续同一企业微信来源自动进入该 `openid` 对应用户资料库。
  - P0 不做用户侧绑定管理、解绑或改绑。
- `WecomIdentityBinding` 已新增 `ownerOpenid`。
- 后续企业微信导入归属优先按 `ownerOpenid` 查用户，旧数据继续按 `ownerUserId` 兜底。
- `AGENTS.md` 已写入 openid 身份总规则。

### 3.5 房源、商品、订单和消息

- 房源资料支持结构化字段、客户页、地图、留资、预约、轻 SCRM、跟进状态。
- 商品资料支持 SKU、多规格、商品展示、下单/接龙名单。
- 商品下单不受 `enableGroupRelay` 是否开启影响：
  - `enableGroupRelay=false` 写 `order-intent`。
  - `enableGroupRelay=true` 写 `relay-intent`。
- 商品轻订单中心已实现：
  - 买家订单。
  - 商家订单。
  - 订单详情。
  - 商家更新状态。
- 站内消息已实现第一版：
  - `message_threads`
  - `message_records`
  - 线程列表、创建线程、消息列表、发送消息、标记已读。
- 前端消息入口已插件化：
  - `miniprogram/plugins/message-plugin/index.js`
  - `miniprogram/components/message-entry`

### 3.6 Docker 开发期挂载模式

- 用户确认当前 Docker 主要用于开发联调期，正式生产上线前可重新写干净的生产 Dockerfile/镜像发布流程。
- 新增 `backend/Dockerfile.dev`：只安装系统库和 Python 依赖，不 `COPY` 源码。
- 新增 `docker-compose.dev.yml`：挂载 `backend/app`、`backend/tests`、`backend/mock` 和只读 `backend/secrets`，启用 `uvicorn --reload`。
- 开发期启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend
```

- 每天可安全清理 Docker build cache：

```bash
docker builder prune -af --filter "until=24h"
docker image prune -f
```

- 不建议日常使用 `docker system prune -af --volumes`，避免误删 Postgres 或媒体数据卷。

## 4. 已修改/新增的文件

### 后端

- `backend/Dockerfile`
  - 增加 PaddleOCR 运行所需系统库。
  - 使用 headless OpenCV。
- `backend/Dockerfile.dev`
  - 新增开发期 Dockerfile，不复制源码，配合挂载和 reload。
- `backend/README.md`
  - 增加开发期挂载模式、启动方式和 Docker build cache 安全清理建议。
- `backend/requirements.txt`
  - 增加 `paddlepaddle==3.3.1`、`paddleocr==2.10.0`。
- `backend/app/api/routes_ocr.py`
  - 新增保存图片、识别已有图片资料的 OCR API。
- `backend/app/models/domain.py`
  - `WecomIdentityBinding` 增加 `ownerOpenid`。
- `backend/app/services/app_service.py`
  - OCR 两段式保存与识别逻辑。
  - 企业微信纯图片导入分流为 `image_ocr` 图片资料。
  - 企业微信身份映射优先按 `ownerOpenid` 解析归属。
- `backend/app/services/ocr_service.py`
  - PaddleOCR 改为子进程 worker 调用，避免 Uvicorn 主进程崩溃。
- `backend/app/services/paddle_ocr_worker.py`
  - 新增 PaddleOCR 子进程 worker。
- `backend/app/services/repository.py`
  - Postgres 字段映射增加 `owner_openid`。
- `backend/tests/test_app.py`
  - 新增 OCR 两段式测试。
  - 新增 OCR 未配置仍保留图片测试。
  - 新增企业微信客服同步纯图片生成 pending OCR 资料测试。
  - 新增会话归档纯图片生成 pending OCR 资料测试。
  - 新增 openid 优先归属测试。

### 小程序

- `miniprogram/services/api.js`
  - 新增保存图片资料和识别已有图片资料 API。
- `miniprogram/pages/notes/index.js`
  - “保存图片”入口调用新 OCR 保存接口。
- `miniprogram/pages/notes/index.wxml`
  - 文案从图片识别改为保存图片。
- `miniprogram/pages/note-edit/index.js`
  - 新增 OCR 状态构建、识别动作和回写逻辑。
- `miniprogram/pages/note-edit/index.wxml`
  - 新增 OCR 操作面板。
- `miniprogram/pages/note-edit/index.wxss`
  - 新增 OCR 面板样式。
- `miniprogram/project.config.json`
  - 微信开发者工具自动改动，当前不应默认纳入业务提交，除非用户确认。

### 文档

- `AGENTS.md`
  - 写入 openid 是唯一身份锚点的项目级规则。
- `docker-compose.dev.yml`
  - 新增开发期挂载 compose。
- `docs/decisions.md`
  - 记录 OCR 两段式、企业微信纯图片导入、openid 身份锚点等决策。
- `docs/dev-log.md`
  - 记录本轮开发、部署、生产验证、真实图片 OCR 闭环和 Docker 开发期挂载。
- `docs/handoff-latest.md`
  - 更新最新交接状态。
- `docs/handoff-latest-4.md`
  - 本文件。
- `docs/pitfalls.md`
  - 记录 PaddleOCR 子进程隔离、Docker slim 依赖、归档图片占位文字、openid 身份规则等坑。
- `docs/project-memory.md`
  - 更新长期记忆中的 OCR 和 identity-core 规则。

### 未跟踪/不应默认提交

- `企业微信客服服务须知.pdf`
  - 未跟踪文件，不属于本轮业务代码。

## 5. 当前代码状态

当前 `git status --short --branch`：

```text
## main...origin/main [ahead 14]
 M AGENTS.md
 M backend/Dockerfile
 M backend/README.md
 M backend/app/api/routes_ocr.py
 M backend/app/models/domain.py
 M backend/app/services/app_service.py
 M backend/app/services/ocr_service.py
 M backend/app/services/repository.py
 M backend/requirements.txt
 M backend/tests/test_app.py
 M docs/decisions.md
 M docs/dev-log.md
 M docs/handoff-latest.md
 M docs/pitfalls.md
 M docs/project-memory.md
 M miniprogram/pages/note-edit/index.js
 M miniprogram/pages/note-edit/index.wxml
 M miniprogram/pages/note-edit/index.wxss
 M miniprogram/pages/notes/index.js
 M miniprogram/pages/notes/index.wxml
 M miniprogram/project.config.json
 M miniprogram/services/api.js
?? backend/Dockerfile.dev
?? backend/app/services/paddle_ocr_worker.py
?? docker-compose.dev.yml
?? 企业微信客服服务须知.pdf
```

当前 `git diff --stat` 约为：

```text
22 files changed, 1150 insertions(+), 129 deletions(-)
```

最近验证：

- 后端全量测试：`109 passed`。
- `compileall backend/app backend/tests`：通过。
- `git diff --check`：通过。
- `docker-compose.dev.yml`：本机无 Docker CLI，未执行 `docker compose config`；已用 Ruby YAML 解析校验。
- 生产 `/health` 正常。
- 生产 PaddleOCR 容器内测试图识别 `HELLO 123`。
- 生产容器重启次数为 0。
- 企业微信真实图片 OCR 闭环已完成。

生产部署状态：

- 最新生产同步前备份：`/home/ubuntu/teamBuy-deploy-backups/20260620-072737`。
- 已同步后端 `app/tests/requirements/Dockerfile` 并重建 `teambuy-backend`。
- 生产数据库已补 `wecom_identity_bindings.owner_openid`。
- 公网 `/api/ocr/images` 已上线，GET 返回 405，说明不是路由级 404。
- 公网 OCR 识别路由对不存在笔记返回业务级“笔记不存在”。

## 6. 已知问题和风险

- 小程序体验版上传仍需用户在微信开发者工具中手动完成。Codex 不要默认反复尝试微信开发者工具 CLI 上传。
- `miniprogram/project.config.json` 是微信开发者工具自动改动，提交前需要用户确认是否纳入。
- 未跟踪 PDF `企业微信客服服务须知.pdf` 不属于本轮代码。
- 当前很多接口仍依赖前端传 `ownerUserId`，P1 应逐步升级为服务端 session/token 校验。
- 当前媒体仍主要使用生产服务器本地 `/media`，P1 应接 COS/S3 或其他对象存储，避免服务器磁盘长期承压。
- Docker 开发期可以清 build cache，但不要日常使用带 `--volumes` 的全量清理。
- OCR 是文字识别，不是图片内容理解。普通照片没有明显文字时，识别为空或低价值文本是正常现象。
- PaddleOCR 不要直接在 Uvicorn 主进程内执行，必须保持子进程/worker 隔离。
- 当前生产小范围联调可继续，但进入更稳定 P1/P2 前建议拆 staging/test 环境，减少生产试错。
- P1 展示页构建器尚未实现。
- 支付和权益基础尚未实现。

## 7. 用户已经确认过的产品/技术决策

- 产品名和方向：资料整理助手。
- 首版不做完整交易平台，不做支付、库存扣减、物流、退款、核销、分账。
- 商品是“商品展示基座 + 可选团购接龙”，`groupbuy_product` 作为兼容类型。
- 商品下单是轻订单/意向单，复用 `customer_actions.order-intent / relay-intent`。
- 电话和地址是商品下单必填字段。
- 站内消息第一版是异步文本留言，不做实时 IM、图片、语音。
- 前端消息入口必须走 `message-plugin` 和 `message-entry`，不要在业务页重复手写创建会话逻辑。
- OCR 采用两段式：先保存图片，用户再主动识别。
- 未配置 OCR 时图片仍然保存，用户可手动补正文和字段。
- OCR provider 第一版使用 PaddleOCR，生产已启用。
- 企业微信纯图片导入只保存为 pending OCR 图片资料，不自动识别。
- 小程序微信 `openid` 是唯一身份锚点；企业微信 `external_userid` 只做内部映射，不做用户侧绑定管理、解绑或改绑。
- P0 阶段测试期误认领走后台数据修正，不做正式产品功能。
- 小程序上传/预览/提交审核默认由用户在微信开发者工具中手动完成。
- 当前 Docker 方案主要服务开发联调期；真正生产上线前可以重新设计独立生产 Dockerfile/镜像发布流程。
- 开发期可每天清理 Docker build cache，但不要清 volume。

## 8. 下一步建议执行顺序

### 第一优先：整理提交范围

1. 确认是否提交 `miniprogram/project.config.json`。
2. 确认是否忽略或移走未跟踪 PDF `企业微信客服服务须知.pdf`。
3. 把本轮 OCR、identity、Docker 开发期挂载、文档归档分成清晰提交。

### 第二优先：P1 展示页构建器 V1

建议作为下一轮开发主线：

1. 先生成开发文档和测试清单。
2. 后端增加展示页配置模型和接口：
   - 店名
   - 简介
   - banner
   - 联系方式
   - 选中的 noteIds
   - 分类/标签展示配置
   - 发布状态
3. 小程序增加展示页构建入口：
   - 从资料库勾选资料
   - 配置展示页基础信息
   - 预览
   - 发布/分享
4. 客户端展示页：
   - 展示店铺信息
   - 按分类/标签展示资料
   - 可进入单条客户页
   - 可发消息/留资

### 第三优先：运维和存储

1. 失败任务/运维看板：
   - 企业微信导入失败
   - 媒体下载失败
   - OCR 失败
   - SkillRun 失败
   - 支持查看原因和手动重试
2. 对象存储正式化：
   - COS/S3 配置生产化
   - 图片、视频、OCR 图片统一存储
3. session/token 身份升级：
   - 当前 `openid` 仍是身份锚点
   - 逐步减少接口从前端直接传 `ownerUserId`

### 第四优先：权益基础

1. 免费额度。
2. OCR 次数。
3. 展示页数量。
4. 图片/资料容量。
5. 先做权益计数，不急着做微信支付。

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

请先不要改代码。先输出：

1. 你理解的项目目标
2. 当前代码状态
3. 已确认的重要决策
4. 当前风险
5. 下一步建议执行顺序

特别注意：

- 小程序微信 openid 是唯一身份锚点，userId 只是内部主键。
- 企业微信 external_userid 只做内部映射，不做用户侧解绑/改绑管理。
- OCR 是两段式：先保存图片，用户再主动识别。
- 企业微信纯图片导入应先生成 pending OCR 图片资料，不自动识别。
- PaddleOCR 必须通过子进程/worker 隔离，不要跑在 Uvicorn 主进程内。
- 小程序上传由用户手动在微信开发者工具完成，Codex 默认不要反复调用 CLI 上传。
- 开发期 Docker 可以用 docker-compose.dev.yml 挂载代码；生产上线前另写生产 Dockerfile。
- 不要提交真实密钥、backend/.env、backend/secrets、媒体目录、未确认的 project.config.json 或未跟踪 PDF。

如果继续 P1 开发，请优先从“展示页构建器 V1”开始，先补开发文档和测试清单，再实现后端模型/API 和小程序构建/预览/发布页面。
```
