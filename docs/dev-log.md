# Dev Log

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

完成「悦享互动宝」v0.1 UI 产品化改版收尾，接入 tabBar 图标，修正文案边界并准备提交。

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
