# teamBuy 阶段性交接归档

更新时间：2026-06-09  
工作目录：`d:\Desktop\myprojects\teamBuy`  
当前分支：`main`  
当前 HEAD：本轮已提交 `feat: productize yuexiang miniapp ui`  
远端状态：本地 `main` 已完成小程序 UI 产品化改版提交，尚未推送到 `origin/main`。

## 1. 项目背景与目标

teamBuy 是一个面向微信群私域场景的小程序工具，核心目标是把用户发给企业微信客服的微信笔记、链接、图片、视频、位置等素材，自动聚合并生成可编辑的小程序卡片。

项目首版不做收款、订单、支付、分账、库存和核销。当前核心闭环是：

```text
企业微信客服导入素材
  -> 后端回调 / sync_msg 拉取消息
  -> 消息聚合与卡片草稿生成
  -> 小程序认领、编辑、保存、分享
  -> 群用户查看、拨号、复制、实名接龙
  -> 团长查看浏览统计、接龙名单、跟进状态
  -> 素材库一键复用
```

第一批目标用户是房产中介，第二批目标用户是团购团长。产品定位已经从“团购交易系统”收敛为“素材导入、卡片生成、查看统计、实名接龙与复用工具”。

## 2. 当前阶段目标

当前已经进入阶段三代码落地阶段。

阶段三目标是实现 v0.1 MVP：

- 后端 FastAPI 服务可本地运行、Docker 构建、服务器部署。
- 企业微信客服回调和 `sync_msg` 主链路具备真实接入能力。
- 本地 mock 链路可验证导入、聚合、解析、认领、卡片、浏览、接龙、复用。
- 小程序端具备登录、待认领、素材库、卡片编辑、卡片查看、团长管理等基础页面。
- 后续继续完成真实企业微信权限配置和小程序人工验收。

## 3. 已完成的功能

以下内容已在 Git 提交历史或现有文档中体现。

### 3.1 阶段一与阶段二文档

- 已完成 `stage1-thinking/` 阶段一交付物。
- 已完成 `docs/stage2-docs/` 阶段二开发文档包。
- 已完成 `docs/qa/MVP_测试清单与验收标准.md`。
- 已完成本地构建与拉镜像部署方案。
- 已补充 Docker 使用清华 PyPI 源的要求。
- 已补充企业微信客服侧边栏/H5 发送小程序卡片作为 P2 技术预研，不进入 v0.1 P0。
- 已补充企业微信文档 `92455`、`101463` 作为后续技术预研参考。

### 3.2 后端已实现能力

根据 `docs/qa/阶段三MVP_Codex自测报告.md` 与提交历史，后端已实现：

- FastAPI 后端骨架。
- `/health` 与数据库健康检查。
- JSON 本地持久化与 PostgreSQL 过渡仓储。
- 企业微信回调 GET/POST 入口。
- 企业微信回调签名校验/解密入口。
- `sync_msg` 客户端骨架。
- mock 企业微信导入。
- 微信笔记 60 秒聚合。
- 文本、图片、链接、视频、位置消息标准化适配。
- 卡片草稿生成。
- 导入认领、卡片编辑、发布、一键复用。
- 浏览统计、匿名浏览隔离。
- 实名接龙、团长删除无效接龙、标记已跟进。
- 导入成功/失败通知抽象和查询接口。
- 真实 `sync_msg` 主链路 normalizer -> 幂等过滤 -> 事务写入导入产物。
- `sync_cursor` 持久化和分页推进。
- real-sync 手动触发锁、锁超时恢复、管理令牌 unlock。
- media_id 下载/转存抽象。
- 本地 `/media/...` 转存 URL。
- COS/S3-compatible 对象存储适配层。
- 媒体转存失败补偿队列。
- callback 触发后台 real-sync 任务。
- PostgreSQL 持久化任务队列 `sync_tasks` / `sync_task_logs`。

### 3.3 小程序已实现能力

根据文件结构和自测报告，已存在：

- `miniprogram/` 原生微信小程序骨架。
- 登录页。
- 待认领导入页。
- 素材库页。
- 卡片编辑页。
- 卡片查看页。
- 管理页。
- 悦享互动宝首页。
- 访问记录页。
- 我的页。
- 组件：`card-preview`、`field-copy-row`、`relay-list`。
- API 服务封装。
- 前端数据聚合工具：`miniprogram/utils/dashboard.js`。
- tabBar：首页、资源库、发给客服、访问记录、我的，并接入 `miniprogram/static/tab` 图标。
- 手动添加资源页：`miniprogram/pages/resource-create/index`。
- 后端手动创建卡片接口：`POST /api/cards`。
- 资源库支持基于真实卡片数据的搜索、分类筛选和标签筛选。
- 卡片查看页支持复制信息、复制来源链接、分享占位和访问详情入口。
- 标签管理页：`miniprogram/pages/tag-manage/index`。
- 后端分类标签接口：`GET /api/categories`、`POST /api/categories`、`DELETE /api/categories/{id}`。
- 手动添加资源时可选择自定义标签并写入卡片 `categoryIds`。

### 3.4 部署与真实联调

根据 `docs/qa/企业微信真实联调记录.md`：

- 代码已推送到 GitHub `main`。
- 腾讯云服务器 `81.70.84.35` 已克隆仓库到 `/home/ubuntu/teamBuy`。
- Docker Compose 已启动 `postgres` 和 `backend`。
- 后端宿主机端口使用 `8002`。
- Compose 构建确认使用清华 PyPI 源。
- PostgreSQL 仅暴露在 Docker 内部网络。
- 公网域名确认为 `teambuy.lifelove.top`。
- DNS A 记录已生效：`teambuy.lifelove.top -> 81.70.84.35`。
- 已使用 certbot 签发并部署 HTTPS 证书。
- 公网 HTTPS 健康检查已通过：
  - `GET https://teambuy.lifelove.top/health -> 200`
  - `GET https://teambuy.lifelove.top/api/wecom/config-check -> success=true`
  - `GET https://teambuy.lifelove.top/api/wecom/callback?echostr=hello-teamBuy -> "hello-teamBuy"`

## 4. 已修改/新增的文件

### 4.1 已提交到 Git 的核心文件

阶段文档与规则：

- `AGENTS.md`
- `stage1-thinking/*`
- `docs/stage2-docs/*`
- `docs/qa/MVP_测试清单与验收标准.md`
- `docs/qa/2026-06-08_teamBuy_本地构建与拉镜像部署方案.md`
- `docs/qa/阶段三MVP_Codex自测报告.md`
- `docs/qa/企业微信客服配置清单.md`
- `docs/qa/企业微信真实联调记录.md`
- `docs/deploy/tencent-cloud-real-sync.md`

后端：

- `backend/.env.example`
- `backend/Dockerfile`
- `backend/README.md`
- `backend/requirements.txt`
- `backend/app/main.py`
- `backend/app/api/*`
- `backend/app/core/*`
- `backend/app/models/domain.py`
- `backend/app/schemas/*`
- `backend/app/services/*`
- `backend/mock/*`
- `backend/tests/*`

小程序：

- `miniprogram/README.md`
- `miniprogram/app.js`
- `miniprogram/app.json`
- `miniprogram/app.wxss`
- `miniprogram/services/api.js`
- `miniprogram/utils/request.js`
- `miniprogram/pages/login/*`
- `miniprogram/pages/imports/*`
- `miniprogram/pages/library/*`
- `miniprogram/pages/card-edit/*`
- `miniprogram/pages/card-view/*`
- `miniprogram/pages/manager/*`
- `miniprogram/components/card-preview/*`
- `miniprogram/components/field-copy-row/*`
- `miniprogram/components/relay-list/*`

部署：

- `docker-compose.yml`
- `backend/.dockerignore`

### 4.2 当前工作区未提交改动

当前 `git status --short --branch` 显示以下已跟踪文件被修改但未提交：

- `AGENTS.md`
- `miniprogram/app.json`
- `miniprogram/app.wxss`
- `miniprogram/pages/imports/index.js`
- `miniprogram/pages/imports/index.wxml`
- `miniprogram/pages/imports/index.wxss`
- `miniprogram/pages/library/index.js`
- `miniprogram/pages/library/index.wxml`
- `miniprogram/pages/library/index.wxss`
- `miniprogram/pages/login/index.js`
- `miniprogram/pages/login/index.wxml`
- `miniprogram/pages/login/index.wxss`

当前还存在以下未跟踪文件或目录：

- `docs/png/`
- `docs/qa/悦享互动宝_v0.1_UI产品化改版_Codex自测报告.md`
- `docs/stage2-docs/07-yuexiang-ui-productization-v0.1.md`
- `docs/悦享互动宝 MVP 产品开发文档.md`
- `miniprogram/pages/home/`
- `miniprogram/pages/profile/`
- `miniprogram/pages/visits/`
- `miniprogram/utils/dashboard.js`

这些内容属于小程序 UI/产品化改版方向，准备作为正式提交归档。`docs/png/` 中存在较多设计参考大图，本轮不纳入提交范围。

## 5. 当前代码状态

### 5.1 Git 状态

最近远端同步状态：

```text
## main...origin/main
```

但工作区不干净，存在已修改和未跟踪文件。

当前 HEAD：

```text
feat: productize yuexiang miniapp ui
```

最近提交包括：

```text
本轮提交：feat: productize yuexiang miniapp ui
c0a6f16 docs: record lifelove https callback readiness
12c7898 docs: update wecom real sync domain
fe30c7c docs: record wecom real sync deployment check
dbac2a7 fix: keep postgres internal in compose
b8fae13 docs: prepare docker compose real sync deploy
d8bd796 feat: persist real sync task queue
a3e49ca feat: queue real sync from callback
e9b3d07 feat: trigger real sync from wecom callback
```

### 5.2 后端测试状态

`docs/qa/阶段三MVP_Codex自测报告.md` 记录：

- 已执行：`cd backend && pytest`
- 当前结果：48 项通过
- 已执行：`cd backend && python -m compileall app`

本 handoff 生成时未重新运行测试。

本轮 UI 产品化收尾已重新执行：

- 小程序所有 `.js`：`node --check` 通过。
- 小程序所有 `.json`：JSON 解析通过。
- `cd backend && pytest`：50 项通过。
- `cd backend && python -m compileall app`：通过。

### 5.3 真实联调状态

HTTPS 域名和后端健康检查已经可用。

当前主要阻塞是真实 `sync_msg` 返回：

```text
errcode=48002
errmsg=api forbidden
from ip=81.70.84.35
```

初步判断代码已经请求到企业微信接口，但企业微信后台权限或配置未完全满足。下一轮应检查 Secret、API 管理模式、客服账号权限、可信 IP/白名单和微信客服 API 权限。

## 6. 已知问题和风险

- 当前工作区存在未提交的小程序 UI 改动和新增文档/图片资源，新会话不要盲目提交或删除。
- 真实企业微信 `sync_msg` 仍被 `48002 api forbidden` 阻塞。
- 回调验签和解密入口已实现，但真实 XML 字段映射仍需企业微信账号实测。
- 小程序尚未完成微信开发者工具中的系统性人工验收。
- 电话拨号、字段复制、接龙管理等小程序能力需要在微信开发者工具或真机环境确认。
- 未接入真实微信登录 code 换 openid。
- 未完成真实对象存储端到端验证。
- PostgreSQL 仓储当前仍有 JSONB 过渡结构，后续可按热点查询继续拆表和优化索引。
- 分类能力目前以查询过滤为主，独立分类管理 API 仍可增强。
- 当前全局 Python 环境曾出现 `sse-starlette` 与 `starlette` 版本约束冲突，后续建议使用项目虚拟环境。
- PC Web 管理端未纳入 v0.1；客服侧边栏/H5 发送卡片仅作为 P2 技术预研。

## 7. 用户已经确认过的产品/技术决策

- 首版主产品形态是“小程序端 + FastAPI 后端”，不是 PC 管理后台。
- 不做收款、订单、支付、分账。
- 第一批目标用户是房产中介，第二批是团购团长。
- 主链路是企业微信客服导入微信笔记/链接，生成小程序卡片。
- 微信笔记必须支持；小程序链接尽量支持，优先级高于公众号链接和普通网页链接。
- 卡片字段采用通用可选字段，不写死房产或团购专用字段。
- 接龙必须登录，不允许匿名。
- 默认接龙使用头像和微信昵称。
- 手机号、地址是首版接龙可选附加字段。
- 浏览用户列表只展示已登录用户；匿名用户只计入总浏览量。
- 一键复用定义为复制整张历史卡片重新发起，新旧卡片数据独立。
- 技术栈使用原生微信小程序 + FastAPI。
- 后端 Docker 构建使用清华 PyPI 源，并支持 `PIP_INDEX_URL` 覆盖。
- 前期以本地开发为主，AppID、服务器、真实企业微信配置等由用户在测试完整后提供。
- 后续客服侧边栏/H5 发送小程序卡片可作为 P2 预研，不影响 v0.1 主链路。
- 企业微信文档 `92455` 适合 P2 小程序端企业微信能力预研。
- 企业微信文档 `101463` 仅作为机器人/消息能力预研，不替代 v0.1 微信客服回调 + `sync_msg` 主链路。

## 8. 下一步建议执行顺序

1. 先把当前小程序在微信开发者工具中跑起来，完成登录、tabBar、首页、资源库、发给客服、访问记录、我的页、手动添加页人工验收。
2. 重点验收标签管理：新增标签 -> 手动添加资源选择标签 -> 资源库按标签筛选 -> 删除标签后筛选恢复。
3. 重点验收资源库搜索、分类 chip、标签 chip、资源卡片「详情 / 访问 / 复制 / 编辑」入口。
4. 继续验收本地可跑链路：手动添加资源 -> 编辑 -> 发布查看 -> 拨号/复制/实名接龙 -> 管理页 -> 一键复用。
5. 继续验收 mock 企业微信链路：发给客服 mock 导入 -> 待认领 -> 认领编辑 -> 发布查看。
6. 企业微信认证问题解决后，优先排查真实 `sync_msg` 的 `48002 api forbidden`：
   - 确认 `WECOM_SECRET` 是微信客服对应 Secret。
   - 确认企业微信后台已开启“微信客服 - 通过 API 管理微信客服帐号”。
   - 确认 `WECOM_OPEN_KFID` 对应客服账号允许 API 管理。
   - 检查企业微信可信 IP/白名单是否包含 `81.70.84.35`。
   - 检查当前企业/应用是否具备微信客服相关 API 权限。
7. 真实发送文本消息后检查：

```text
/api/wecom/sync-tasks
/api/imports/pending
/api/wecom/media-retries
```

8. 继续测试真实链接、图片、视频、位置和微信笔记。
9. 真实链路跑通后，再补充 QA 验收报告，不要提前标记上线通过。

## 9. 新 Codex 会话接手时的第一条提示词

```text
请接手 d:\Desktop\myprojects\teamBuy 项目。

先不要继续开发新功能。请先读取：
1. AGENTS.md
2. docs/handoff-latest.md
3. docs/stage2-docs/codex-prompt.md
4. docs/qa/MVP_测试清单与验收标准.md
5. docs/qa/阶段三MVP_Codex自测报告.md
6. docs/qa/企业微信真实联调记录.md

然后执行：
1. 检查 git status，明确当前已提交、未提交、未跟踪文件。
2. 不要删除或覆盖未提交的小程序 UI/产品化改动。
3. 总结当前代码状态和风险。
4. 优先处理当前工作区归档与验收：小程序微信开发者工具人工验收、后端 pytest/compileall 复跑。
5. 如果继续真实联调，优先排查企业微信 sync_msg 返回 48002 api forbidden 的权限配置问题。

请先输出你的接手理解、当前风险、第一轮只做什么、不会做什么，然后再开始执行。
```
