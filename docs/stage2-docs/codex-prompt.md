# Codex 阶段三启动任务说明

请阅读本阶段二文档包，并进入阶段三：代码落地执行。

## 1. 项目目标

按照文档实现 teamBuy v0.1 MVP 原型：

用户将微信笔记或链接发送给企业微信客服，系统通过后端聚合解析生成可编辑卡片，用户在小程序中认领、编辑、保存并分享到微信群。群用户可以查看卡片、拨打电话、复制字段、实名接龙。发起人可以查看浏览统计、接龙名单，并一键复用历史卡片。

## 2. 必读文档

请先读取：

- `AGENTS.md`
- `stage1-thinking/05-stage2-input-brief.md`
- `docs/stage2-docs/01-product-plan.md`
- `docs/stage2-docs/02-task-breakdown.md`
- `docs/stage2-docs/03-tech-spec.md`
- `docs/stage2-docs/04-acceptance.md`
- `docs/stage2-docs/05-resource-list.md`
- `docs/stage2-docs/06-data-structure.md`
- `skills/wecom-import-parser/SKILL.md`
- `skills/card-generation/SKILL.md`
- `skills/miniapp-flow/SKILL.md`
- `skills/qa-acceptance/SKILL.md`

## 3. 开发顺序

第一轮只实现项目骨架、mock 数据和核心数据结构。

第二轮实现后端导入聚合、规则解析、卡片草稿生成。

第三轮实现小程序登录、待认领导入、素材库、卡片编辑和查看。

第四轮实现浏览统计、实名接龙、团长管理、一键复用。

第五轮接入真实企业微信客服回调、小程序登录、对象存储和大模型兜底。

## 4. mock 和真实接入边界

开发阶段可以 mock：

- 企业微信真实回调
- `sync_msg` 返回数据
- media_id 下载结果
- 对象存储上传结果
- 大模型解析结果
- 微信登录 code 换 openid

必须真实实现：

- 消息聚合逻辑
- 卡片生成逻辑
- 认领逻辑
- 卡片编辑保存
- 浏览统计逻辑
- 接龙逻辑
- 一键复用逻辑
- 数据隔离规则

上线前必须真实接入：

- 企业微信回调 URL
- `sync_msg`
- 媒体下载和转存
- 小程序登录
- 线上数据库
- 线上对象存储

## 5. 技术要求

- 前端使用原生微信小程序。
- 后端使用 FastAPI。
- 不把密钥写入前端或 Git。
- 保留 `.env.example`，真实 `.env` 不提交。
- API 返回结构保持稳定。
- mock 数据要容易替换为真实接口。
- P0 测试项优先。

## 6. 不做范围

- 不做支付、订单、收款、分账。
- 不做库存、核销。
- 不做匿名接龙。
- 不做自动抓取微信聊天记录。
- 不做企业微信会话内容存档。
- 不做复杂 CRM。
- 不做多角色团队权限。

## 7. 完成后输出

每轮开发完成后必须输出：

1. 修改文件列表
2. 实现内容
3. 如何运行
4. 如何测试
5. 已通过测试项
6. 未覆盖测试项
7. 已知问题
8. 下一步建议

自测报告保存到：

```text
docs/qa/功能名称_Codex自测报告.md
```
