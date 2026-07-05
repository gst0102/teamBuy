# 新项目迁移执行清单

更新时间：2026-07-05

适用目的：

- 你准备新开一个项目
- 希望复用 `teamBuy` 已经跑通过的域名 / 小程序 / H5 / 企业微信 / 后端配置经验
- 但不想把 `teamBuy` 当前复杂业务包袱整包带过去

这份文档就是给“另一个项目开发”直接使用的。

---

## 0. 先说结论

新项目最值得复用的是这四层：

1. 部署与域名接线方式
2. 小程序基础配置
3. `web-view + H5 ticket` 打开模式
4. 企业微信 / 会话存档 / OCR 的后端配置骨架

不建议直接整包复用的是：

1. 资源工具具体业务字段
2. `/test-api`、`/test-media` 这种历史测试前缀设计
3. teamBuy 当前的房源 / 商机 / 供需 / 积分规则
4. 各种阶段性 UI 打磨页和临时兼容逻辑

---

## 1. 当前可复用的真实资源

### 1.1 域名与服务器

- 生产域名：`https://teambuy.lifelove.top`
- 服务器 IP：`81.70.84.35`
- SSH 用户：`ubuntu`
- 项目目录：`/home/ubuntu/teamBuy`
- SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`

给新项目的建议：

- 不要直接覆盖 `/home/ubuntu/teamBuy`
- 建议新项目单独目录，例如：
  - `/home/ubuntu/new-project`
- 建议新项目单独 docker compose 服务名
- 如果继续复用同一域名，建议按以下二选一：
  - 方案 A：新项目用新子域名
  - 方案 B：新项目用新路径前缀

更推荐：

- `newproject.lifelove.top`

而不是继续往 `teambuy.lifelove.top` 里叠更多历史路由。

### 1.2 小程序 AppID

当前仓库里的 AppID：

- 文件：`miniprogram/project.config.json`
- 当前值：`wxf43f7bc098d9858b`

如果新项目继续复用这个小程序主体，需要同步检查：

1. 微信公众平台 request 合法域名
2. uploadFile 合法域名
3. downloadFile 合法域名
4. web-view 业务域名
5. `navigateToMiniProgramAppIdList`

如果新项目换新的小程序主体，则必须一起替换：

1. `miniprogram/project.config.json`
2. 后端环境变量 `WECHAT_MINIAPP_APPID`
3. 后端环境变量 `WECHAT_MINIAPP_SECRET`

---

## 2. 哪些文件可以直接复制

以下是“可直接复制作为起点”的内容。

### 2.1 后端配置骨架

直接复制参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/.env.example`

用途：

- 新项目后端环境变量模板
- 给运维或另一个开发说明需要准备哪些 Secret / Key / Token

说明：

- 复制变量结构
- 不复制旧项目真实值

### 2.2 H5 外壳路由

直接参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_h5.py`

用途：

- 给新项目提供静态 H5 入口
- 让小程序 `web-view` 有统一后端出口

### 2.3 H5 ticket 登录态模式

直接参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_auth.py`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/schemas/auth.py`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/services/app_service.py`

重点是复用这个思路：

1. 小程序先向后端申请一个短期票据
2. H5 打开时带 ticket
3. H5 再向后端换 session/user 信息
4. H5 不直接裸传 `userId`

### 2.4 小程序 web-view 外壳

直接复制参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-tools-webview/`

用途：

- 新项目小程序里快速接一个 H5 页面容器

### 2.5 小程序打开 H5 的入口逻辑

直接参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js`

重点看：

- `buildResourceToolsH5Url`
- `handleOpenOpportunityRadar`

这部分适合抽成新项目通用方法。

### 2.6 后端配置对象

直接参考：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/core/config.py`

用途：

- 新项目统一读取环境变量
- 保持企业微信 / 小程序 / OCR / 地图 / H5 secret 这些配置入口一致

---

## 3. 哪些值必须重配，不能照搬

这些一定要在新项目重配。

### 3.1 小程序相关

- `WECHAT_MINIAPP_APPID`
- `WECHAT_MINIAPP_SECRET`

### 3.2 企业微信相关

- `WECOM_ADMIN_TOKEN`
- `WECOM_CORP_ID`
- `WECOM_CALLBACK_TOKEN`
- `WECOM_SECRET`
- `WECOM_ENCODING_AES_KEY`
- `WECOM_OPEN_KFID`
- `WECOM_ARCHIVE_SECRET`
- `WECOM_ARCHIVE_PRIVATE_KEY_PATH`
- `WECOM_ARCHIVE_PUBLIC_KEY_PATH`
- `WECOM_GROUP_BOT_WEBHOOKS`

### 3.3 H5 / 登录态相关

- `H5_AUTH_SECRET`

### 3.4 地图 / OCR / 存储

- `TENCENT_MAP_KEY`
- `OBJECT_STORAGE_*`
- `OCR_PROVIDER`

### 3.5 基础运行环境

- `PUBLIC_BASE_URL`
- `DATABASE_URL`

---

## 4. 哪些代码不要直接带过去

这部分最重要。

### 4.1 不要直接带 `/test-api` 与 `/test-media`

teamBuy 当前小程序文件：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/app.js`

当前配置是：

```js
apiBaseUrl: "https://teambuy.lifelove.top",
apiRoutePrefix: "/test-api",
mediaRoutePrefix: "/test-media",
environmentName: "test"
```

这只是 teamBuy 当前测试环境约定。

新项目建议：

- 直接使用干净生产前缀：
  - `apiRoutePrefix: ""`
  - `mediaRoutePrefix: ""`
- 如果确实需要测试环境，建议重新设计，例如：
  - `test.newproject.com`
  - 或独立 `staging` 子域名

### 4.2 不要直接带资源工具业务字段

不要直接照搬这些业务概念：

- 商机雷达
- 供需广场
- 回应包
- 资源积分
- 房源 / 合集 / 服务介绍页

原因：

- 这些已经深度绑定 teamBuy 当前业务语义
- 新项目场景一变，字段和流程大概率都要改

建议：

- 只复用“列表页 / 详情页 / 发布页 / 我的发布页 / 订阅页”的页面结构
- 不直接复用字段名和扣分规则

### 4.3 不要直接带旧测试兼容逻辑

比如：

- demo/mock id 特判
- 预览模式兜底数据
- 旧页面回退分支
- 针对 teamBuy 当前测试库的临时文案

这些适合作为开发时参考，不适合作为新项目正式起点。

---

## 5. 推荐的新项目落地顺序

这是最实用的一部分，建议另一个项目开发就按这个顺序来。

### 第一步：先起后端空壳

要做的事：

1. 复制 `backend/.env.example`
2. 复制 `backend/app/core/config.py`
3. 建立新项目自己的：
   - `main.py`
   - 健康检查路由
   - auth 路由
   - h5 路由

验收标准：

- 本地能跑
- 服务器能跑
- 域名 HTTPS 正常
- `GET /health` 正常

### 第二步：接小程序登录

要做的事：

1. 配 `WECHAT_MINIAPP_APPID`
2. 配 `WECHAT_MINIAPP_SECRET`
3. 跑通 `wx.login -> 后端登录 -> user session`

验收标准：

- 小程序能拿到真实 openid
- 后端能识别当前用户

### 第三步：接 web-view + H5 ticket

要做的事：

1. 复制 H5 ticket 机制
2. 复制 `resource-tools-webview`
3. 在小程序中打开一个最简单的 H5 页面

验收标准：

- 小程序能安全打开 H5
- H5 能识别用户
- H5 不依赖裸 `userId`

### 第四步：接新项目自己的业务页

要做的事：

1. 只复用页面骨架
2. 重新定义业务字段
3. 重新定义列表、详情、发布、我的四类页面

验收标准：

- 页面结构是新的
- 不是 teamBuy 原业务硬改名

### 第五步：最后再决定要不要接企业微信 / OCR / 地图

原因：

- 这些都属于“增强能力”
- 不该挡住新项目最初闭环

---

## 6. 建议给另一个项目开发的具体交付话术

你可以直接把下面这段话给对方：

> 这是一个从 teamBuy 项目里抽出来的迁移任务。  
> 请不要整包复用旧业务，只复用以下能力骨架：  
> 1）后端环境变量模板；  
> 2）小程序登录；  
> 3）H5 ticket + web-view 打开模式；  
> 4）H5 静态入口与用户识别；  
> 5）企业微信 / OCR / 地图配置入口。  
>  
> 请优先完成“新项目自己的最小闭环”，不要先把 teamBuy 的商机雷达、供需广场、回应包、积分规则原样搬过去。  
>  
> 先确保域名、HTTPS、小程序 request 域名、web-view 业务域名、后端登录态这几层全通，再开始接业务页面。

---

## 7. 本次迁移最值得看的文件

按优先级排序：

1. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/config-migration-reference.md`
2. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/.env.example`
3. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/core/config.py`
4. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_h5.py`
5. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-tools-webview/`
6. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js`
7. `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/docs/project-closeout-20260705.md`

---

## 8. 当前 GitHub 状态

已经上传到 GitHub 当前分支：

- 仓库：`git@github.com:gst0102/teamBuy.git`
- 分支：`codex/version-protection-20260629`

也就是说：

- 这次阶段成果已经在远端仓库里了
- 你现在把这份文档给另一个项目开发，他既可以看文档，也可以直接拉这个分支参考代码

