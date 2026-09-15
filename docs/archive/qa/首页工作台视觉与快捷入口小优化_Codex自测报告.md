# 首页工作台视觉与快捷入口小优化_Codex自测报告

更新时间：2026-06-23

## 1. 修改结论

已完成首页工作台小优化：

- “今日待处理”统计图标从单字占位改为更明确的两字 / 短词标签。
- 四个工作台的“快捷开始”文案已按当前产品讨论收口。
- 房源、团购、服务工作台均保留普通笔记入口，避免业务模式下无法随手记录。
- 顶部右侧大方块由单字改为两字模式标签：资料、房源、团购、服务。
- 顶部右侧视觉已接入 4 张 240×240 本地 PNG 插画，替代原大字方块；如果图片缺失则保留文字兜底。

## 2. 涉及文件

- `miniprogram/utils/workspace-mode.js`
- `miniprogram/pages/home/index.js`
- `miniprogram/pages/home/index.wxml`
- `miniprogram/pages/home/index.wxss`
- `miniprogram/app.wxss`
- `miniprogram/static/workspace/workspace-notes.png`
- `miniprogram/static/workspace/workspace-property.png`
- `miniprogram/static/workspace/workspace-groupbuy.png`
- `miniprogram/static/workspace/workspace-service.png`

## 3. 今日待处理统计标签

| 工作台 | 统计标签 |
|---|---|
| 日常资料台 | 资料 / 打开 / 分享 / 资料包 |
| 房源工作台 | 房源 / 打开 / 客户 / 预约 |
| 团购工作台 | 商品 / 打开 / 接龙 / 买家 |
| 服务工作台 | 名片 / 打开 / 咨询 / 预约 |

说明：

- `statCardsForMode` 现在直接使用 `modeConfig.stats` 作为统计图标文案。
- `stat-icon` 调整为更适合两字 / 三字标签的宽度、字号和 nowrap 居中规则。

## 4. 快捷开始入口与跳转映射

### 日常资料台

| 入口 | 副标题 | 对应动作 |
|---|---|---|
| 写笔记 | 随手记录 | 进入普通资料创建页 |
| 存图片 | 图片放进笔记 | 进入普通资料创建页，并带 `scene=image_note` |
| 存链接 | 链接放进笔记 | 进入普通资料创建页，并带 `scene=link_note` |
| 建资料包 | 打包资料分享 | 进入合集 / 资料包 Tab |

说明：当前“写笔记 / 存图片 / 存链接”底层仍是普通笔记创建入口，文案避免承诺独立图片库或自动链接解析。

### 房源工作台

| 入口 | 副标题 | 对应动作 |
|---|---|---|
| 新建房源 | 粘贴房源文案 | 进入资料创建页，并带 `scene=property_listing` |
| 记需求 | 记录客户需求 | 进入普通资料创建页，并带 `scene=customer_need_note` |
| 房源合集 | 组合推荐 | 进入合集 / 资料包 Tab |
| 我的名片 | 发给客户 | 进入电子名片工作台 |

### 团购工作台

| 入口 | 副标题 | 对应动作 |
|---|---|---|
| 新建商品 | 粘贴团购文案 | 进入资料创建页，并带 `scene=groupbuy_product` |
| 记素材 | 记录团购素材 | 进入普通资料创建页，并带 `scene=groupbuy_material_note` |
| 团购合集 | 组合商品 | 进入合集 / 资料包 Tab |
| 查看接龙 | 处理名单 | 进入订单 / 接龙管理页 |

### 服务工作台

| 入口 | 副标题 | 对应动作 |
|---|---|---|
| 做名片 | 先给客户认识你 | 进入电子名片工作台 |
| 做方案 | 发服务介绍页 | 进入服务方案工作台 |
| 写笔记 | 记录服务素材 | 进入普通资料创建页，并带 `scene=service_material_note` |
| 案例合集 | 组合案例资料 | 进入合集 / 资料包 Tab |

## 5. 未做项及原因

- WebP 未做：当前本机缺少 WebP 写入工具；已先使用 240×240 PNG，4 张总大小约 240KB，仍在前端包可接受范围内。
- 普通笔记入口只新增轻量 `scene` 参数：当前创建页底层能力仍是统一普通资料创建，本轮不新增后端或大流程。
- 未改 Tabbar、后端接口、小程序上传流程。

## 6. 执行的检查命令

已通过：

```text
node --check miniprogram/pages/home/index.js
node --check miniprogram/utils/workspace-mode.js
python3 递归解析 miniprogram 下所有 .json：44 个通过
git diff --check
ls -lh miniprogram/static/workspace：4 张 240×240 PNG，总计约 240KB
```

## 7. 需要真机确认事项

- 今日待处理里的“资料包”等三字标签是否居中、不截字、不换行。
- 四个工作台切换后，快捷开始是否展示对应文案。
- 房源 / 团购 / 服务工作台点击“记需求 / 记素材 / 写笔记”是否能进入普通资料创建页。
- 顶部右侧 4 张插画在真机上是否清晰、不破图、不挤压、不遮挡标题文案。
- 首页整体在普通手机、大屏手机上是否无横向溢出，底部 Tabbar 不遮挡快捷入口。
