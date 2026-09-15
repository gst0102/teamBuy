# 生产 / 测试环境隔离说明

更新时间：2026-06-30

## 1. 当前环境

### 生产环境

- 域名：`https://teambuy.lifelove.top`
- 服务器：`81.70.84.35`
- 项目目录：`/home/ubuntu/teamBuy`
- Docker project：默认 `teamBuy`
- 后端端口：`8002 -> 8000`
- 生产入口：
  - API：`https://teambuy.lifelove.top/api/`
  - PC 后台：`https://teambuy.lifelove.top/ops`
  - 健康检查：`https://teambuy.lifelove.top/health`
  - 媒体：`https://teambuy.lifelove.top/media/`

生产环境只用于：

- 小程序审核和正式版本
- 真实用户数据
- 正式资源内容
- 正式运营入口
- 已验收稳定的后端接口

### 测试环境

- 与生产共用服务器，但容器、数据库、媒体卷、端口和入口隔离。
- Docker project：`teambuy-test`
- Compose 文件：`docker-compose.test.yml`
- 测试后端配置：`backend/.env.test`，不提交 Git。
- 后端端口：`8003 -> 8000`
- 测试入口：
  - API：`https://teambuy.lifelove.top/test-api/`
  - PC 后台：`https://teambuy.lifelove.top/test-ops`
  - 健康检查：`https://teambuy.lifelove.top/test-health`
  - 媒体：`https://teambuy.lifelove.top/test-media/`

测试环境用于：

- 企业群机器人运营卡片生成器
- 每日运营内容测试
- 测试群 webhook 配置和发送
- 外部群二维码挂载测试
- 资源内容上架测试
- 外部群二维码 / 黄页 / 服务内容爬取实验
- 支付、分销、推广位等未上线能力验证

## 2. 隔离规则

- 生产和测试不得共用数据库卷。
- 生产和测试不得共用媒体卷。
- 生产和测试不得共用正式群 webhook。
- 测试环境默认关闭企业微信会话拉取和会话存档 worker。
- 测试环境默认 `WECOM_GROUP_BOT_WEBHOOKS={}`，需要测试群发时只在测试后台配置测试群 webhook。
- 小程序审核前，生产环境只修 P0/P1，不把试验功能临时接进生产主链路。

## 3. 代码和数据防污染规则

### 3.1 实验代码

实验功能必须满足至少一条：

- 独立路由或独立页面入口。
- 独立模板名称或独立生成器名称。
- 独立环境变量开关。
- 仅在测试环境启用。

禁止：

- 直接改正式分享卡片生成器来试运营卡片。
- 把临时假数据、假图、测试 webhook 写进正式代码路径。
- 用同一个函数同时承担“正式分享封面”和“机器人运营海报”两套职责，除非已有清晰模板参数和测试覆盖。

### 3.2 测试数据

测试数据必须可识别：

- 标题或备注包含 `测试` / `test` / `演练`。
- 群标识使用 `test_*` 或明确测试群名称。
- 测试资源默认不进入正式展示池。

### 3.3 生成器规则

正式小程序分享卡片和企业群机器人运营卡片要分层：

- 底层可以复用绘图工具、图片下载、文字截断、上传能力。
- 上层模板必须分开：
  - 小程序分享封面：用于用户手动发客户。
  - 机器人运营卡片：用于群机器人日报、重点资料、合集入口。

这样可以避免后续运营卡片试验破坏小程序正式分享封面。

## 4. 常用命令

查看测试环境：

```bash
cd /home/ubuntu/teamBuy
docker compose -f docker-compose.test.yml --env-file backend/.env.test -p teambuy-test ps
```

启动 / 更新测试环境：

```bash
cd /home/ubuntu/teamBuy
docker compose -f docker-compose.test.yml --env-file backend/.env.test -p teambuy-test up -d --build
```

查看测试后端日志：

```bash
cd /home/ubuntu/teamBuy
docker compose -f docker-compose.test.yml --env-file backend/.env.test -p teambuy-test logs -f backend-test
```

验证测试环境：

```bash
curl https://teambuy.lifelove.top/test-health
curl https://teambuy.lifelove.top/test-api/ops-admin/overview
```

第二条不带管理口令返回 403 属于正常，说明测试 API 路由和鉴权生效。
