# 配置迁移参考（给后续新项目复用）

更新时间：2026-07-05

## 1. 当前可复用的基础资源

### 1.1 域名与服务器

- 生产域名：`https://teambuy.lifelove.top`
- 生产服务器：`81.70.84.35`
- 登录用户：`ubuntu`
- 项目目录：`/home/ubuntu/teamBuy`
- SSH Key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`

说明：

- 这个域名当前已经同时承载生产和测试转发约定。
- 后续如果你要给新项目复用，最稳妥方式不是直接覆盖 teamBuy，而是：
  - 保留当前域名/Nginx/证书经验
  - 在新项目里重新规划新的路由前缀、容器名、Compose 服务名
  - 或者直接给新项目单独子域名

### 1.2 小程序 AppID

当前仓库内可见的小程序 AppID：

- `miniprogram/project.config.json`
- 当前值：`wxf43f7bc098d9858b`

说明：

- 这是开发者工具项目配置里使用的 AppID。
- 后端 `.env` 模板里 `WECHAT_MINIAPP_APPID` 也默认写的是同一个值。
- 如果新项目要复用小程序主体，后端和小程序工程配置要保持一致。
- 如果新项目换成新的小程序主体，则要同时替换：
  - `miniprogram/project.config.json`
  - 服务器环境变量 `WECHAT_MINIAPP_APPID`
  - 微信后台 request 合法域名 / web-view 业务域名 / navigateToMiniProgram 白名单等

## 2. 当前小程序前端环境配置

文件：`/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/app.js`

当前代码状态是“测试环境前端配置”：

```js
apiBaseUrl: "https://teambuy.lifelove.top"
apiRoutePrefix: "/test-api"
mediaRoutePrefix: "/test-media"
environmentName: "test"
```

这意味着：

- 当前小程序代码默认走测试后端
- API 请求走：`https://teambuy.lifelove.top/test-api/...`
- 媒体走：`https://teambuy.lifelove.top/test-media/...`

如果后续你在新项目里要上线生产前端，通常要切成：

```js
apiBaseUrl: "https://你的域名"
apiRoutePrefix: ""
mediaRoutePrefix: ""
environmentName: "production"
```

## 3. 当前 H5 资源工具接入方式

### 3.1 小程序入口

入口文件：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-tools-webview/index.wxml`

当前做法：

1. 小程序先调用后端创建 H5 ticket
2. 拼接 H5 URL
3. 使用 `web-view` 打开资源工具页面

### 3.2 H5 页面路径

后端文件：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_h5.py`

当前 H5 路由：

- `/h5/resource-tools/`
- `/api/h5/resource-tools/`

测试环境实际使用过的公网路径：

- `https://teambuy.lifelove.top/test-api/h5/resource-tools/`

### 3.3 H5 票据接口

已经接入：

- `POST /api/auth/h5-ticket`
- `GET /api/auth/h5-session`

如果新项目要复用这套模式，建议直接复用“短期票据 + web-view”的机制，不要把 `userId` 直接暴露给 H5。

## 4. 后端环境变量里值得复用的配置骨架

文件模板：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/.env.example`

后续新项目可以优先复用这些配置块的结构，而不是直接复制旧值：

### 4.1 基础服务

- `APP_ENV`
- `APP_HOST`
- `APP_PORT`
- `PUBLIC_BASE_URL`
- `DATABASE_BACKEND`
- `DATABASE_URL`

### 4.2 企业微信客服 / 会话存档

- `WECOM_ADMIN_TOKEN`
- `WECOM_USE_MOCK`
- `WECOM_API_BASE_URL`
- `WECOM_CORP_ID`
- `WECOM_CALLBACK_TOKEN`
- `WECOM_SECRET`
- `WECOM_ENCODING_AES_KEY`
- `WECOM_OPEN_KFID`
- `WECOM_ARCHIVE_ENABLED`
- `WECOM_ARCHIVE_SECRET`
- `WECOM_ARCHIVE_PRIVATE_KEY_PATH`
- `WECOM_ARCHIVE_PUBLIC_KEY_PATH`
- `WECOM_ARCHIVE_SDK_LIB_PATH`

### 4.3 OCR / 地图 / 小程序登录

- `OCR_PROVIDER`
- `OCR_LANGUAGE`
- `WECHAT_MINIAPP_APPID`
- `WECHAT_MINIAPP_SECRET`
- `TENCENT_MAP_KEY`

### 4.4 H5 登录态

- `H5_AUTH_SECRET`

说明：

- 真正的 Secret、Key、Webhook、私钥不要从本仓库抄历史值。
- 新项目建议只复用变量名和接线方式，在新环境重新生成新值。

## 5. 新项目如果要复用的页面与能力

### 已经有实现基础的

- 企业微信客服导入主链路
- 会话内容存档主链路
- OCR 配置骨架
- 小程序微信登录
- H5 ticket + web-view 打开模式
- 资源工具 H5 骨架

### 迁移时最值得优先复用的文件/目录

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_h5.py`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/api/routes_auth.py`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/core/config.py`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/resource-tools-webview/`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/miniprogram/pages/profile/index.js`
- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/backend/app/static/h5/resource-tools/`

## 6. 不建议直接照搬的内容

### 6.1 业务路由前缀

当前项目为了测试共存，已经形成：

- 生产：`/api`
- 测试：`/test-api`
- 测试媒体：`/test-media`

新项目如果没有这种历史包袱，完全可以重新设计得更干净。

### 6.2 资源工具业务本身

资源工具 H5 现在更适合当“可迁移原型”，不一定适合原样搬到新项目。  
可以复用：

- H5 打开方式
- 页面骨架
- 票据机制
- 列表/详情/发布/我的发布这种信息结构

但业务字段、积分规则、订阅逻辑、供需逻辑建议按新场景重新定义。

### 6.3 生产热修基线 artifacts

本地有一份：

- `/Users/yiyi/Desktop/Desktop/myprojects/teamBuy/artifacts/prod-baseline-20260702-ocr-property/`

它适合作为本地部署比对资料，不建议直接上传 GitHub，也不建议直接作为新项目模板。

## 7. 给新项目的最小复用顺序

建议顺序：

1. 先复用 `backend/.env.example` 的配置骨架
2. 再复用 H5 ticket 登录态模式
3. 再复用 `web-view -> H5` 打开链路
4. 最后才迁资源工具具体业务页面

这样你后面把域名、小程序 AppID、后端 HTTPS、业务域名先跑通，会轻松很多。
