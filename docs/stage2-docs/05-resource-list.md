# 资源清单

## 1. 缺失资源

以下资源在阶段三真实接入前必须补齐：

- 微信小程序 AppID
- 企业微信主体和客服账号
- 企业微信回调 Token、EncodingAESKey、Secret
- 企业微信 API 凭证
- 腾讯云服务器
- 对象存储配置
- 数据库配置
- 大模型 API Key

## 2. 资源落地表

| 资源类型 | 资源名称 | 文件名建议 | 所属模块 | 规格要求 | MVP 必须 | mock 方案 | 验收标准 |
|---|---|---|---|---|---|---|---|
| 配置 | 后端环境变量模板 | `.env.example` | 后端 | 不含真实密钥 | 是 | 使用占位值 | 字段完整且不泄密 |
| 配置 | 小程序配置 | `miniprogram/app.json` | 小程序 | 页面路径完整 | 是 | 基础页面配置 | 可被微信开发者工具识别 |
| 图片 | 默认卡片封面 | `assets/images/default-cover.png` | 卡片 | 750x420，压缩后小于 300KB | 是 | 纯色占位图 | 无封面时可展示 |
| 图片 | 空素材库插图 | `assets/images/empty-library.png` | 素材库 | 300x300，压缩后小于 150KB | 否 | 文案空状态 | 空列表不突兀 |
| 图标 | 电话图标 | `assets/icons/phone.png` | 查看页 | 48x48 | 是 | 使用文字按钮 | 可识别拨号动作 |
| 图标 | 复制图标 | `assets/icons/copy.png` | 查看页 | 48x48 | 是 | 使用文字按钮 | 可识别复制动作 |
| 图标 | 接龙图标 | `assets/icons/relay.png` | 接龙 | 48x48 | 否 | 使用文字按钮 | 可识别接龙入口 |
| 文案 | 导入成功文案 | `copy/import-success.md` | 企业微信客服 | 带标题候选 | 是 | 固定文案 | 用户知道导入成功 |
| 文案 | 导入失败文案 | `copy/import-failed.md` | 企业微信客服 | 带失败原因候选 | 是 | 固定文案 | 用户知道如何重试 |
| 文案 | 认领提示文案 | `copy/claim-guide.md` | 小程序 | 简短明确 | 是 | 页面静态文案 | 用户知道如何认领 |
| mock 数据 | 微信笔记消息样例 | `mock/wecom-note-messages.json` | 后端 | 包含文本、图片、链接 | 是 | 手写 JSON | 可用于聚合测试 |
| mock 数据 | 链接消息样例 | `mock/wecom-link-messages.json` | 后端 | 小程序/公众号/网页各一条 | 是 | 手写 JSON | 可用于链接解析测试 |
| mock 数据 | 卡片样例 | `mock/cards.json` | 前后端 | 覆盖全部字段 | 是 | 手写 JSON | 可用于页面开发 |
| mock 数据 | 浏览记录样例 | `mock/view-events.json` | 统计 | 登录和匿名都覆盖 | 是 | 手写 JSON | 可用于统计测试 |
| mock 数据 | 接龙记录样例 | `mock/relays.json` | 接龙 | 含手机号、地址、跟进状态 | 是 | 手写 JSON | 可用于管理页测试 |

## 3. 官方文档资源

| 文档 | 链接 | 用途 |
|---|---|---|
| 微信客服入门指南 | https://developer.work.weixin.qq.com/document/path/94638 | 确认接入方式 |
| 小程序接入微信客服 | https://work.weixin.qq.com/nl/act/p/a733314375294bdd | 小程序端客服入口 |
| 接收事件 - 配置回调服务器 | https://developer.work.weixin.qq.com/document/path/90968 | 配置回调 URL |
| 接收消息和事件 | https://developer.work.weixin.qq.com/document/path/94670 | 回调、sync_msg、消息类型 |
| 获取临时素材 | https://developer.work.weixin.qq.com/document/path/94674 | media_id 下载 |

## 4. 资源标准

- 所有真实密钥只放环境变量，不进 Git。
- 图片资源必须压缩。
- mock 数据必须覆盖 P0 正常流程和异常流程。
- 文案必须避免承诺收益、收款、支付、交易保障。
- 资源文件命名使用小写字母、数字和短横线。
