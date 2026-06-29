# teamBuy 阶段性交接归档 6

更新时间：2026-06-21

工作目录：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy`

当前分支：`main`

当前状态摘要：

- 本地分支显示 `main...origin/main [ahead 18]`。
- 当前工作区仍有大量未提交修改和未跟踪文件，不要擅自回滚。
- 后端最新逻辑已经部署到生产服务器 `https://teambuy.lifelove.top`。
- 小程序端最新 UI / 分享路径 / 经营看板前端改动需要用户在微信开发者工具重新上传体验版或正式版后，真机才会生效。
- 2026-06-21 后续补充：用户反馈真机分享回归多次未成功，本轮不继续盲改分享路径，已改为补齐代码侧 P0 边界测试；没有调用生产清理接口。

## 1. 项目背景与目标

teamBuy 当前正式产品方向是“资料整理助手”，服务微信私域/轻 SCRM 场景。

核心产品链路：

```text
用户把微信笔记、链接、图片、房源、商品、团购等资料整理进笔记库
  -> 小程序里形成可编辑的资料卡
  -> 多条资料组合成展示页
  -> 展示页发给客户
  -> 客户打开、看资料、电话咨询、复制微信、下单/接龙
  -> 发布者在经营看板、线索、订单、客户资料中查看效果并跟进
```

长期架构规则见：

- `AGENTS.md`
- `docs/project-memory.md`
- `docs/decisions.md`
- `docs/pitfalls.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- `docs/stage2-docs/08-plugin-architecture.md`

重要原则：

- 小程序微信 `openid` 是用户身份唯一锚点。
- `showcase-builder` 是小程序可视化配置工具，不是 AI 自动全权生成展示页。
- 展示页是给客户看的公开页，必须稳定、可信、低操作成本。
- 公开展示页必须读取发布快照，不允许每次客户打开都实时拼笔记资料。
- 有参考图的 UI 不能只交功能版，必须尽量贴近已确认的视觉结构。
- 按钮、标签、胶囊、底部操作条必须上下左右居中，不能靠 `line-height` 硬凑。

## 2. 当前阶段目标

当前阶段是“上线闭环与真实分享追踪 V1”。

对应开发文档：

- `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
- `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`
- `docs/qa/上线闭环与真实分享追踪V1_Codex自测报告.md`

阶段目标：

```text
用户创建展示页
  -> 发给客户
  -> 客户打开
  -> 客户看资料 / 咨询 / 下单 / 接龙
  -> 发布者能在展示页效果、经营看板、客户资料里反查
```

本次最后一次明确收口的 1-4 范围：

1. 扩展 `ShowcaseEvent` 数据字段和接口请求。
2. 修改展示页分享路径，生成并携带 `shareId`。
3. 公开展示页记录事件时带上分享来源。
4. analytics 和经营看板聚合分享来源。

## 3. 已完成的功能

### 3.1 展示页构建器 V1

已完成：

- 展示页后端模型、接口、发布、下架、删除。
- 小程序展示页列表页、编辑页、客户公开展示页。
- 四套模板：精选橱窗、朋友圈长页、清单目录、品牌名片。
- 新建展示页改成“模板 + 分类 + 默认全选该分类资料”的低操作流程。
- 展示页默认 `groupBy=tag`，不再给普通用户暴露复杂展示方式选择。
- 展示页列表右侧操作区减负：已发布主按钮为“发给客户”，低频操作进“更多”。
- 删除展示页使用 `POST /api/showcases/{id}/delete`，兼容部分环境不支持 `DELETE`。
- 展示页不再展示虚假的 `328+ 服务客户 / 128 成交案例 / 98% 好评率` 等营销数字。

### 3.2 展示页公开访问快照缓存

已完成：

- `ShowcasePage` 增加：
  - `publicSnapshot`
  - `snapshotVersion`
  - `snapshotCreatedAt`
- 发布展示页时生成公开快照。
- 客户公开接口优先返回 `publicSnapshot`。
- 老的已发布页没有快照时，首次公开访问自动补一份快照并保存。
- 重新发布展示页会刷新快照版本。
- 删除资料时同步修剪相关展示页快照，避免已删除资料继续外露。

线上验证：

- 生产域名：`https://teambuy.lifelove.top`
- 指定展示页：`showcase_627fc56634`
- 连续两次公开访问都返回 `snapshotVersion=1`。
- 两次 `snapshotCreatedAt` 一致：`2026-06-21T14:50:04.334312+08:00`。
- 说明第二次已经读取缓存快照，不再实时拼资料。

### 3.3 展示页真实分享追踪

已完成：

- `ShowcaseEvent` 支持：
  - `shareId`
  - `shareFromUserId`
  - `scene`
  - `referrer`
- 事件类型支持：
  - `share`
  - `view`
  - `note_click`
  - `phone_click`
  - `wechat_copy`
- 小程序展示页列表、编辑页、公开展示页分享都会生成 `shareId`。
- 分享路径统一落到已有页面 `pages/showcases/index` 中转，再跳公开展示页。
- 当前分享路径格式：

```text
pages/showcases/index?shareTarget=showcase&showcaseId={showcaseId}&sid={shareId}&from={ownerUserId}&src={scene}&ref={previousShareId}
```

- 公开展示页兼容 `id/showcaseId` 和旧 `scene` 参数。
- 公开展示页打开记录 `view`。
- 点击资料记录 `note_click`。
- 电话记录 `phone_click`。
- 复制微信记录 `wechat_copy`。
- 同一分享批次下的打开、看资料、咨询能进入 analytics。

### 3.4 单展示页效果 analytics

已完成：

- 新增 `GET /api/showcases/{id}/analytics?ownerUserId=xxx`。
- 只有 owner 能看 analytics，非 owner 返回 403。
- analytics 返回：
  - `summary.pv`
  - `summary.uv`
  - `summary.noteClickCount`
  - `summary.phoneClickCount`
  - `summary.wechatCopyCount`
  - `summary.consultClickCount`
  - `summary.shareCount`
  - `summary.shareSourceCount`
  - `recentViewers`
  - `recentEvents`
  - `topNotes`
  - `topShares`
- 小程序 `pages/showcase-analytics/` 已提供展示页效果页。
- 展示页列表卡片会展示轻量效果摘要。

### 3.5 经营看板与分享来源

已完成：

- 新增后端 `GET /api/dashboard/business?ownerUserId=xxx`。
- 经营看板聚合：
  - 展示页打开
  - 访客
  - 看资料
  - 咨询
  - 分享次数
  - 分享批次数
  - 待联系线索
  - 客户资料
  - 商品下单/接龙
  - 最近访客
  - 资料点击排行
  - 最近客户动作
  - 分享来源排行 `topShares`
- 小程序新增 `pages/business-dashboard/index`，包含四个 Tab：
  - 展示页效果
  - 访客详情
  - 笔记数据
  - 客户资料
- 经营看板详情页新增“分享来源”模块。
- 复用组件 `components/business-dashboard` 也新增“分享来源”模块。
- owner 视角手机号和微信不脱敏，提供外呼和复制按钮。
- 页面不展示“行为强度分层”等内部概念。

线上验证：

- `/health` 返回正常。
- 线上经营看板 `user_25ec00a0f0` 返回：
  - `shareSourceCount=11`
  - `topSharesLength=6`

### 3.6 商品/团购轻订单与客户动作

已完成：

- 商品/团购下单和接龙继续复用 `CustomerAction`：
  - `order-intent`
  - `relay-intent`
- 商品轻订单不默认进入房源轻 SCRM 线索，避免污染房源客户资料。
- 订单/接龙页面支持待处理、已联系、已完成、已取消等轻量状态。
- 经营看板可看到订单/接龙数量和待处理数量。

### 3.7 文档和规则沉淀

已完成：

- `AGENTS.md` 增加 UI 文本居中与参考图一致性规则。
- `AGENTS.md` 增加腾讯云生产部署约定。
- `docs/decisions.md` 增加：
  - 公开展示页必须读取发布快照。
  - 展示页真实追踪只记录真实事件。
  - 展示页不展示虚假营销数字。
  - 经营看板是独立入口，不铺在“我的”页首页。
- `docs/pitfalls.md` 增加：
  - 公开展示页不能每次打开都实时拼资料。
  - 小程序分享不要走 tab 首页或新增未验证页面作为入口。
  - 小程序按钮和标签不能靠 `line-height` 假居中。
  - 参考图不能实现成简化功能版。
- `docs/dev-log.md` 和 `docs/handoff-latest.md` 已记录阶段收口。

## 4. 已修改/新增的文件

### 后端主要修改

- `backend/app/models/domain.py`
  - 新增/扩展 `ShowcasePage` 快照字段。
  - 新增/扩展 `ShowcaseEvent`。
- `backend/app/schemas/showcases.py`
  - 新增 `ShowcaseEventRequest` 分享来源字段。
- `backend/app/api/routes_showcases.py`
  - 新增展示页事件和 analytics 路由。
  - 新增 POST 删除兜底。
- `backend/app/api/routes_dashboard.py`
  - 新增经营看板接口。
- `backend/app/main.py`
  - 挂载 dashboard 路由。
- `backend/app/services/app_service.py`
  - 展示页发布快照。
  - 公开展示页读快照。
  - 事件记录。
  - analytics 聚合。
  - 经营看板聚合。
  - 演示数据写入。
  - 删除资料时修剪展示页快照。
- `backend/app/services/repository.py`
  - `showcase_events` 存取和索引字段映射。
- `backend/app/core/schema.sql`
  - 新增 `showcase_events` 表和索引。
- `backend/app/core/config.py`
  - 增加生产关闭 mock 登录相关配置。
- `backend/tests/test_app.py`
  - 展示页、分享追踪、经营看板、快照缓存相关测试。
- `backend/tests/test_postgres_repository_schema.py`
  - 校验 `showcase_events` 字段和索引。

### 小程序主要修改/新增

- `miniprogram/app.json`
  - 新增/调整展示页、经营看板、订单相关页面注册。
- `miniprogram/app.wxss`
  - 增加全局按钮/标签/胶囊居中基线。
- `miniprogram/services/api.js`
  - 新增展示页、事件、analytics、经营看板 API。
- `miniprogram/pages/showcases/`
  - 展示页列表、分享中转、效果摘要、主操作与更多菜单。
- `miniprogram/pages/showcase-edit/`
  - 模板 + 分类 + 默认全选流程。
  - 分享、发布、删除、banner 缩略图。
- `miniprogram/pages/showcase-view/`
  - 四模板客户公开页。
  - 打开/点击/电话/微信复制事件记录。
  - 公开页分享与来源传递。
- `miniprogram/pages/showcase-analytics/`
  - 单展示页效果页，含分享来源。
- `miniprogram/pages/business-dashboard/`
  - 经营看板四 Tab 详情页。
  - 分享来源、访客、资料点击排行、客户动作、外呼/复制。
- `miniprogram/components/business-dashboard/`
  - 可复用经营看板组件。
- `miniprogram/components/note-select-card/`
  - 资料选择卡片组件。
- `miniprogram/utils/note-display.js`
  - 我的笔记和展示页选资料共用的笔记展示逻辑。
- `miniprogram/utils/showcase-templates.js`
  - 四套展示页模板配置。
- `miniprogram/pages/notes/`
  - 复用笔记展示逻辑，增加列表/双列展示。
- `miniprogram/pages/visits/`
  - “访客线索”入口调整。
- `miniprogram/pages/orders/`、`miniprogram/pages/order-detail/`
  - 商品/团购轻订单状态和详情体验。
- `miniprogram/pages/note-actions/`
  - 笔记客户动作/数据入口。

### 文档新增/修改

- `docs/stage2-docs/13-showcase-builder-v1.md`
- `docs/stage2-docs/14-customer-data-dashboard-architecture.md`
- `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
- `docs/qa/展示页构建器V1_测试清单与验收标准.md`
- `docs/qa/展示页构建器V1_Codex自测报告.md`
- `docs/qa/当前项目_验收报告m2.md`
- `docs/qa/客户数据看板_测试清单与验收标准.md`
- `docs/qa/客户数据看板_Codex自测报告.md`
- `docs/qa/客户数据看板_验收报告.md`
- `docs/qa/客户数据看板_复测与回归报告.md`
- `docs/qa/客户数据看板_上线部署与回归清单.md`
- `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`
- `docs/qa/上线闭环与真实分享追踪V1_Codex自测报告.md`
- `docs/deploy/dashboard-closeout-server-commands.sh`
- `docs/png/showcase-template-00-all.png`
- `docs/png/showcase-template-01-featured-window.png`
- `docs/png/showcase-template-02-moments-story.png`
- `docs/png/showcase-template-03-catalog-list.png`
- `docs/png/showcase-template-04-brand-card.png`
- `docs/png/showcase-template-mockups.html`
- `docs/decisions.md`
- `docs/pitfalls.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`
- 本文件：`docs/handoff-latest-6.md`

### 当前未跟踪但存在的文件

当前 `git status` 显示仍有若干未跟踪文件，包括：

- `backend/app/api/routes_dashboard.py`
- `docs/stage2-docs/14-customer-data-dashboard-architecture.md`
- `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`
- `miniprogram/components/business-dashboard/`
- `miniprogram/components/note-select-card/`
- `miniprogram/pages/business-dashboard/`
- `miniprogram/pages/showcase-analytics/`
- `miniprogram/pages/showcase-share/`
- `miniprogram/utils/note-display.js`
- `miniprogram/utils/showcase-templates.js`
- 多个 QA 文档和展示页模板图片。
- `企业微信客服服务须知.pdf`

注意：

- `miniprogram/pages/showcase-share/` 文件存在但当前已不作为分享落地页使用，`app.json` 中已移除注册。不要误以为它是当前主链路。
- 未跟踪 PDF 可能是用户资料，不要删除。

## 4.1 2026-06-21 补充：分享追踪 V1 代码侧边界加固

- 背景：
  - 用户真机反复测试“发给客户 / 好友打开 / 分享来源回流”未成功，要求不再继续卡住真机分享，直接向下开发。
- 本轮处理：
  - 未继续修改小程序分享路径。
  - 补后端测试 `test_mock_login_can_be_disabled`，覆盖 `ALLOW_MOCK_LOGIN=false` 时 mock 登录返回 403。
  - 补 `test_showcase_builder_create_publish_public_and_archive`，覆盖草稿和下架展示页调用事件接口均返回“展示页不存在或未发布”。
  - 补 `test_create_note_demo_data_for_owner`，覆盖清理演示数据时同账号真实资料和真实展示页必须保留。
- 验证：
  - `/tmp/teambuy-py312-test/bin/python -m pytest backend/tests/test_app.py -q -k 'create_note_demo_data_for_owner or mock_login_can_be_disabled or showcase_builder_create_publish_public_and_archive'`：3 passed。
  - `python3 -m compileall backend/app backend/tests -q`：通过。
  - `git diff --check`：通过。
- 后续注意：
  - 真机分享失败后续仍按版本、体验成员、分享路径参数和公开接口 200 顺序排查，不建议没有新证据时继续换落地页。

## 5. 当前代码状态

### Git 状态

最近一次检查：

```text
## main...origin/main [ahead 18]
```

工作区有大量 modified 和 untracked 文件，尚未提交。

不要执行：

- `git reset --hard`
- `git checkout --`
- `rm -rf`
- 任何批量删除或批量回滚

除非用户明确要求。

### 自动化验证状态

最近统一测试结果：

```text
/tmp/teambuy-py312-test/bin/python -m pytest backend/tests -q
113 passed

find miniprogram -name '*.js' -print0 | xargs -0 -n 1 node --check
通过

小程序 JSON 解析检查
通过

python3 -m compileall backend/app -q
通过

git diff --check
通过
```

### 生产部署状态

生产信息：

- 服务器：`ubuntu@81.70.84.35`
- SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`
- 服务器目录：`/home/ubuntu/teamBuy`
- 域名：`https://teambuy.lifelove.top`
- 容器：`teambuy-backend-1`
- 数据库：Postgres 容器

已部署到生产的后端能力：

- 展示页接口。
- 经营看板接口。
- 展示页分享追踪事件。
- 展示页公开访问快照缓存。
- 经营看板分享来源聚合。

最近线上验证：

- `/health` 正常。
- `showcase_627fc56634` 连续公开访问读取相同快照。
- `GET /api/dashboard/business?ownerUserId=user_25ec00a0f0` 返回 `shareSourceCount=11`、`topSharesLength=6`。

## 6. 已知问题和风险

1. 小程序端还需要用户重新上传体验版或正式版。
   - 后端已部署，但小程序前端改动只有上传后真机才会生效。
   - 包括最新分享路径、经营看板“分享来源”模块、按钮居中和展示页 UI 修正。

2. 真实微信好友打开分享页仍需上线环境确认。
   - 之前用户多次反馈“页面不存在 / 首页数据加载失败”。
   - 代码已改为 `pages/showcases/index` 中转，避免直达深层页或 tab 首页。
   - 但如果小程序体验版未上传或好友不是体验成员，仍可能打不开。

3. 生产库已有测试假数据。
   - 用户确认可以在生产库写测试假数据，正式上线前会删除。
   - 重点测试用户包括：
     - `user_25ec00a0f0`
     - openid `oPSh564GCACiIkZxFPV5VWVgdbds`
   - 旧演示用户 `user_836a4a8986` / `openid_dashboard_demo_prod_20260621` 是系统生成测试身份，不是微信官方 openid。

4. `docs/stage2-docs/13-showcase-builder-v1.md` 中早期“资料更新后展示页公开接口读取最新资料摘要”的描述已被快照决策取代。
   - 当前正式规则是：客户公开页读发布快照；资料编辑后需要重新发布才更新客户页。
   - 以 `docs/decisions.md` 的“公开展示页必须读取发布快照”和 `docs/pitfalls.md` 的缓存规则为准。

5. `miniprogram/project.config.json` 有改动。
   - 可能包含微信开发者工具自动改动。
   - 提交前需要人工判断是否保留。

6. 工作区很脏。
   - 有大量历史阶段改动和未跟踪文件。
   - 新 Codex 接手时必须先读状态，不要只看最终回复。

7. 小程序真机 UI 仍可能需要微调。
   - 用户对按钮文字居中、列表右侧按钮占宽、参考图落差非常敏感。
   - 新功能交付前必须用真机或截图对照。

## 7. 用户已经确认过的产品/技术决策

已确认决策：

- 展示页是给客户看的，不是复杂装修器。
- 展示页 V1 固定四套模板，不继续扩大自定义装修能力。
- 新建展示页要降低操作成本，走模板、分类、默认全选。
- 展示页不展示虚假营销数字，如服务客户、好评率、成交案例。
- 展示页列表不要堆满按钮，主操作 + 更多即可。
- 展示方式选择删掉，前期默认按标签分组。
- 自动生成信息必须跟分类标签和资料类型走，不能商品页还写房源文案。
- banner 不让用户手输图片 URL，只显示缩略图和换图片。
- 公开展示页必须加缓存/发布快照，不能每次打开都重新拉服务器拼资料。
- 经营看板不铺在“我的”页首页，放到“访客线索 / 经营看板”单独页面。
- 经营看板展示事实，不展示“行为强度分层”等内部概念。
- owner 自己的 SCRM/经营看板里手机号和微信不脱敏，必须可外呼、可复制。
- 商品/团购轻订单需要处理状态，但不默认污染房源线索。
- 手动新建房源/商品/普通笔记统一走“添加资料”快速向导，创建 `UserNote` 后进入 `note-edit`，不回到旧资源库 Card 主路径。
- 手动粘贴文案复用 `content-to-note` 规则，用户选择的房源/商品/普通笔记类型视为人工确认类型。
- 底部中间“添加”最终主形态已经改为极简随手记入口 + 方案 B 高置信业务提示层：打开就是“放进笔记库”大输入框，高置信房源/团购自动保存为业务草稿，再强提示完善详情。
- 小程序按钮、标签、胶囊、底部操作条必须上下左右居中。
- 有参考图时，不能规划得很好，最后实际做成完全不同的功能版。
- 小程序预览、上传体验版和提交审核默认由用户在微信开发者工具手动完成。
- 腾讯云部署方式已经写入 `AGENTS.md`，可按该方式部署后端。

## 8. 下一步建议执行顺序

建议新会话按以下顺序推进：

1. 启动必读和状态确认。
   - 读取 `AGENTS.md`。
   - 读取 `docs/project-memory.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/dev-log.md`、`docs/handoff-latest.md`、本文件。
   - 执行 `git status --short --branch` 和 `git diff --stat`。

2. 不急着写新功能，先做当前收口核验。
   - 对照 `docs/stage2-docs/15-launch-closed-loop-share-tracking-v1.md`。
   - 对照 `docs/qa/上线闭环与真实分享追踪V1_测试清单与验收标准.md`。
   - 确认 1-4 已经代码完成且测试通过。

3. 等用户上传新版小程序后，做真机回归。
   - 展示页列表点击“发给客户”。
   - 另一个微信打开分享页。
   - 打开展示页后看经营看板“打开 / 访客”是否增加。
   - 点击资料后看“看资料”和资料点击排行。
   - 点击电话或复制微信后看“咨询”是否增加。
   - 看经营看板“分享来源”是否出现该 `shareId` 批次。
   - 看客户资料页是否能外呼、复制微信、添加跟进、备注。

4. 如果真机分享仍打不开，优先排查版本和身份，不要先乱改后端。
   - 是否已上传最新体验版/正式版。
   - 好友是否体验成员。
   - 分享路径是否是 `pages/showcases/index?...`。
   - 是否带 `showcaseId/sid/from/src`。
   - 后端公开接口是否 200。

5. 正式上线前清理生产测试数据。
   - 用户已经允许生产库写测试假数据，但正式上线前必须删除。
   - 清理时不要批量删除未知数据，只清理带明确演示标记的数据。

6. 提交前做变更分组。
   - 当前工作区包含多阶段修改，不建议一口气无脑提交。
   - 至少分为：展示页构建器、经营看板、上线闭环分享追踪、文档/QA。
   - `miniprogram/project.config.json` 和 PDF 需要单独确认。

7. 之后可考虑的下一阶段。
   - 方案 A 极简添加页真机验收：底部“添加”打开即聚焦输入；普通内容保存后留在当前页；房源/团购高置信后提示完善详情；图片按钮仍能进入 OCR 资料页。
   - 真实微信登录与 openid 稳定性回归。
   - 展示页分享真实线上链路验收。
   - 生产测试数据清理工具。
   - 经营看板 UI 真机细节打磨。
   - 企业微信导入主链路继续联调。

## 9. 新 Codex 会话接手时的第一条提示词

建议复制以下提示词给新 Codex 窗口：

```text
请接手 teamBuy 项目，工作目录是 /Users/yiyi/Desktop/Desktop/myprojects/teamBuy。

先不要改代码。请严格按 AGENTS.md 启动规则读取：
- AGENTS.md
- docs/project-memory.md
- docs/decisions.md
- docs/pitfalls.md
- docs/dev-log.md
- docs/handoff-latest.md
- docs/handoff-latest-6.md

然后执行：
- git status --short --branch
- git diff --stat

请先输出接手理解，必须包含：
1. 项目目标
2. 当前阶段目标
3. 当前代码状态
4. 已确认的重要产品/技术决策
5. 当前风险
6. 下一步建议执行顺序

当前重点不是新增大功能，而是继续“上线闭环与真实分享追踪 V1”的真机回归和收口：
- 展示页分享路径已经改为 pages/showcases/index 中转，并携带 showcaseId/sid/from/src/ref。
- 公开展示页已经改成发布快照缓存 publicSnapshot，不能再每次打开实时拼笔记资料。
- 经营看板已经返回 shareSourceCount/topShares，并在小程序页面展示“分享来源”。
- 后端已部署到 https://teambuy.lifelove.top，最近后端全量测试 122 passed。
- 小程序端仍需要用户重新上传体验版/正式版后才能真机看到最新前端改动。

请不要回滚用户未提交改动，不要删除未跟踪文件，不要使用 destructive git 命令。
```
