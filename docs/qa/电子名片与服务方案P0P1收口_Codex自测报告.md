# 电子名片与服务方案 P0/P1 收口 Codex 自测报告

日期：2026-06-23

## 范围

- 服务方案工作台底部操作条遮挡修正。
- 服务方案微信转发封面与电子名片保持同级体验。
- “我的笔记”列表和双列卡片中的服务方案展示。
- 分享封面生成中的按钮状态兜底。
- 前端包体和密钥泄露基础检查。

## P0 收口

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 工作台三步页面不被底部按钮遮挡 | 已处理 | `service-offer-studio` 增加底部 spacer，sticky 操作条贴近安全区。 |
| 服务方案微信转发不退回默认卡片 | 已处理 | “我的笔记”和客户页分享优先使用 `generateServiceOfferShareImage` 生成横版封面。 |
| 服务方案列表与模板预览保持一致 | 已处理 | “我的笔记”列表使用专属方案预览卡，展示模板名、标题、卖点、标签和封面。 |
| 默认图不进入前端包 | 通过 | `miniprogram/static` 约 88K，未发现超过 200KB 的静态文件。 |
| 前端不包含真实密钥 | 通过 | 小程序目录关键词扫描仅命中登录页提示文案，未发现真实密钥值。 |
| mock 登录生产关闭能力 | 已覆盖 | 后端已有 `ALLOW_MOCK_LOGIN` 开关和 `test_mock_login_can_be_disabled` 自动化测试。本机 Python/pytest 环境不匹配，未在本轮实际执行该测试。 |

## P1 收口

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 分享封面生成中兜底 | 已处理 | 电子名片/服务方案在封面生成前按钮显示“封面准备中”，生成完成或失败后恢复“发名片/发方案”。 |
| 双列卡片服务方案专属预览 | 已处理 | 双列卡片新增服务方案迷你预览，不再只使用普通封面卡。 |
| 多模板色调适配 | 已处理 | 列表和双列卡片按服务方案 tone 区分蓝/绿/暖/紫色调。 |
| 统一资料预览数据 | 已处理 | `note-display` 增加 `serviceOfferPreview`，列表、双列卡片和分享共用同一份预览信息。 |

## 已运行检查

- `node --check miniprogram/pages/notes/index.js`
- `node --check miniprogram/pages/note-preview/index.js`
- `node --check miniprogram/utils/note-display.js`
- `node --check miniprogram/utils/business-card-share.js`
- `node --check miniprogram/pages/service-offer-studio/index.js`
- 服务方案工作台 / 我的笔记相关 WXML/WXSS 核心布局 `px` 扫描：未发现。
- `miniprogram/static` 包体检查：约 88K，未发现超过 200KB 静态文件。
- `git diff --check`：通过。

未运行项：

- 后端定向 pytest：本机 `python3` 和项目 `.venv` 均为 Python 3.9，无法加载项目里的 `dataclass(slots=True)`；内置 Python 3 可用但未安装 pytest。

## 需要用户上传体验版后确认

- 从服务方案工作台三步页面滚到底部，确认按钮不再挡住最后一屏内容。
- 从“我的笔记”列表和双列卡片查看服务方案，确认展示与模板预览一致。
- 从“我的笔记”点“发方案”，确认微信聊天卡片显示完整横版方案封面。
- 打开被分享的服务方案客户页，确认电话、微信、留资、预约动作可用。
