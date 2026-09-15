# 资料整理助手：五类内容编辑器开发启动提示词

请接手“资料整理助手”五类内容编辑器开发。

项目路径：

```text
/Users/yiyi/Desktop/Desktop/myprojects/teamBuy
```

开始前必须依次完整读取：

```text
1. AGENTS.md
2. docs/project-memory.md
3. docs/decisions.md
4. docs/pitfalls.md
5. docs/dev-log.md
6. docs/handoff-latest.md
7. docs/stage2-docs/39-content-editor-product-design-decisions.md
8. docs/stage2-docs/40-five-editor-data-route-attachment-spec.md
9. docs/qa/五类内容编辑器_测试清单与验收标准.md
```

然后执行：

```bash
git status --short --branch
git diff --stat
```

先不要直接改代码。先输出：

1. 对五类编辑器目标和产品边界的理解。
2. 当前数据模型、路由、附件上传、客户事件和生成同款的差距。
3. 已有未提交改动中，本轮可能重叠的文件及归属判断。
4. 按依赖关系拆分的开发顺序。
5. 将执行的最小验证和最终对抗式审查范围。

## 本轮目标

一次完成以下五类编辑器及共同基础能力，全部完成后统一做一次对抗式审查：

```text
1. 通用编辑器：文字、图片、文章链接
2. 房源编辑器
3. 商品 / 团购编辑器
4. 服务 / 合作编辑器
5. 电子名片编辑器与4个轻样式
```

共同基础能力包括：

- 统一 `UserNote` 数据契约与旧数据兼容。
- 统一编辑器路由解析器。
- 图片/PDF/链接真实附件模型。
- PDF真实上传、微信预览和附件点击事件。
- 统一客户页、分享封面、基础SCRM信号。
- 通用生成同款净化、邀请与分佣归因。
- “我的”销售身份与名片/各资料联系方式单一数据源。

## 必须遵守的产品边界

- 内容创建、卡片、分享和生成同款免费；身份、完整轨迹、客户档案与跟进为会员权益。
- 编辑器不显示SCRM开关、客户反馈、消息中心、标签后台或复杂工作流。
- 服务/合作是跨行业轻资料，只做名称、介绍、图片/PDF/链接、选填范围和合作条件；不要恢复复杂专业服务稿。
- 商品不做在线支付、退款、物流、优惠券和复杂SKU。
- 房源公开地图只导航到小区/楼盘公共位置，精确地址必须私密。
- 电子名片第一版每人一张；4种样式只改视觉，不得覆盖用户内容。
- 生成同款必须剥离私密数据、客户数据、统计和原作者身份；名片必须固定清空个人身份与精选资料。

## UI验收参考

必须逐项对照：

```text
docs/png/editor-design/01-text-three-scenes.png
docs/png/editor-design/02-image-three-scenes.png
docs/png/editor-design/03-link-three-scenes.png
docs/png/editor-design/04-property-editor.png
docs/png/editor-design/05-product-editor.png
docs/png/editor-design/06-service-collaboration-editor.png
docs/png/editor-design/07-business-card-three-scenes.png
```

复杂专业服务方案旧稿已废弃，不得使用。

## 开发要求

- 开发前先按测试文档补齐必要测试，不要最后才补验收条件。
- 优先实现P0，严格按依赖顺序推进，但本轮要求五类全部完成后再统一审查。
- 使用现有架构和API，做能解决根因的最小生产改动；不要建立平行内容系统。
- 修改前确认工作区现有改动归属，不回滚或覆盖已有改动。
- 所有导航入口必须通过统一 `cardType -> editor route` 解析器。
- 更新资料必须保持原 `noteId`，除非明确执行生成同款。
- 公共净化与生成同款必须复用同一套安全策略。
- PDF不能只做前端图标；必须验证真实文件字节、MIME、公开访问和微信预览。
- UI完成后必须对照参考图检查模块、文案、居中、rpx、安全区和空态。

## 安全和环境

- 不部署生产，不修改生产 `/api`，除非用户之后单独明确要求。
- 当前小程序测试环境：`/test-api`、`/test-media`、`environmentName=test`。
- 测试域名：`https://teambuy.lifelove.top`。
- 测试健康检查：`https://teambuy.lifelove.top/test-health`。
- 测试服务器目录：`/srv/teambuy-test/teamBuy`，但本轮没有明确部署授权时不要部署。
- 不覆盖任何 `.env`、secrets、数据库、媒体目录或运行态数据。
- AppSecret、企业微信Secret、Token、私钥不得出现在聊天、日志、文档或Git。
- 当前工作区已有大量未提交改动，禁止 `git reset --hard`、`git checkout --`、批量删除或覆盖用户改动。
- 旧服务器目录 `/home/ubuntu/teamBuy` 已不存在，不要使用。
- 小程序上传和体验版提交由用户在微信开发者工具手动完成。

## 阶段交付

开发完成后必须：

1. 运行 `docs/qa/五类内容编辑器_测试清单与验收标准.md` 中的相关检查。
2. 一次性执行对抗式审查，重点攻击数据隔离、附件安全、重复创建、旧数据兼容、生成同款剥离、样式切换和事件污染。
3. 修复确认问题后再做一次针对性回归。
4. 输出自测与对抗式审查报告到 `docs/qa/`。
5. 更新 `docs/dev-log.md`、`docs/decisions.md`、`docs/pitfalls.md`、`docs/handoff-latest.md`。
6. 明确列出自动验证通过项、需要微信开发者工具/真机人工确认项和剩余风险。

达到P0通过且参考图结构一致前，不要宣称全部完成。
