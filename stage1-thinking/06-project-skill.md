# 项目 Skill 规划

## 1. 总体要求

开发本项目时，应优先在项目根目录创建 `skills/` 文件夹，并为关键工作流生成项目专属 Skill。

Skill 的目标是让不同 Codex 或 AI 角色在后续阶段能稳定读取同一套规则，不依赖聊天上下文。

## 2. 建议 Skill 列表

| Skill | 用途 | 优先级 |
|---|---|---|
| `skills/wecom-import-parser/SKILL.md` | 企业微信客服回调、sync_msg、微信笔记聚合、媒体转存、导入失败处理 | P0 |
| `skills/card-generation/SKILL.md` | 卡片字段生成、规则解析、大模型兜底、卡片编辑和复用规则 | P0 |
| `skills/miniapp-flow/SKILL.md` | 原生微信小程序页面、登录、分享、查看、拨号、字段复制 | P0 |
| `skills/qa-acceptance/SKILL.md` | 测试清单、验收标准、Bug 单、复测和回归 | P0 |
| `skills/privacy-compliance/SKILL.md` | 登录用户展示、匿名浏览统计、昵称脱敏、手机号和地址处理 | P1 |
| `skills/growth-copy/SKILL.md` | 后续商业化、邀请、付费文案和用户引导文案 | P2 |

## 3. `wecom-import-parser` Skill 要点

该 Skill 必须说明：

- 企业微信客服必须配置回调 URL
- 必须开启 API 管理模式
- 使用回调事件触发后端处理
- 使用 sync_msg 拉取消息
- 微信笔记没有专门消息类型
- 需要按同一用户、同一会话、60 秒窗口聚合消息
- media_id 必须及时下载转存
- 导入成功或失败必须由企业微信客服回发通知

## 4. `card-generation` Skill 要点

该 Skill 必须说明：

- 卡片字段是通用可选字段
- 第一段文本优先作为标题候选
- 第一张图片优先作为封面候选
- 其余图片进入图集
- 链接保留来源 URL、标题、描述、缩略图
- 手机号、位置、视频作为候选字段
- 规则优先解析
- 大模型只做文本清洗和字段补全
- 一键复用是复制整张历史卡片重新发起

## 5. `qa-acceptance` Skill 要点

该 Skill 必须覆盖：

- 微信笔记导入成功率
- 链接导入成功率
- 导入失败通知
- 待认领导入
- 卡片编辑保存
- 群分享查看
- 电话拨号
- 字段复制
- 登录浏览用户统计
- 匿名浏览统计
- 实名接龙
- 接龙名单管理
- 一键复用
- 数据隔离和回归测试

## 6. 参考来源

可参考旧项目：

- `d:\Desktop\vedo-project\skills`
- `d:\Desktop\vedo-project\AGENTS.md`

参考时只继承“角色分工、测试官流程、Bug 修复流程、验收报告格式”，不要照搬积分、小游戏、广告、提现等旧业务规则。
