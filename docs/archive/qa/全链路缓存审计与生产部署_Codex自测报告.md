# 全链路缓存审计与生产部署 Codex 自测报告

日期：2026-08-27

## 结论

本轮已完成缓存边界审计、最小修复和生产后端部署。后端缓存契约与服务端健康检查通过；小程序缓存代码静态检查和 Node 行为验证通过。小程序端的实际手机验收仍需要重新上传体验版。

## 发现与修复

### 小程序运行内存缓存

- 资料、合集、专题、资源列表增加内存优先读取，TTL 统一为 60 秒；分类为 10 分钟。
- 客户详情/雷达详情继续只保留短时进程内缓存，不进入 wx 持久化存储。
- 增加用户、环境、API 地址和场景隔离，避免切换账号后复用旧数据。
- 退出登录和会话过期时清理资源、媒体、接口及客户作用域缓存。

### 小程序持久化缓存

- 列表元数据和分类允许异步 wx.setStorage，不阻塞首屏；内存命中时不重复读写。
- 联系方式草稿从持久化改为内存变量；非敏感房源城市偏好保留用户/环境隔离存储。
- 媒体缓存只处理 HTTPS 图片，限制为 7 天、80 个文件、32 MB，单资料最多 3 张；PDF/视频不落本地媒体文件缓存。

### 服务端缓存

- 资料/合集相关列表缓存 TTL 从长缓存降为 60 秒。
- 发布、复制、删除分类、资料浏览、资料互动和卡片行为写入后主动失效列表缓存。
- /api/ 和 /health 使用 Cache-Control: no-store, max-age=0、Pragma: no-cache、Vary: Authorization。
- /media/ 使用长期公开缓存头，依赖内容版本化地址保证变更后不复用旧资源。

## 验证记录

- 小程序 JS：node --check 通过，覆盖 API、资源 store、媒体缓存、匿名访客、app 和个人页。
- Python：python3 -m compileall -q backend/app backend/tests 通过。
- 后端：.venv313/bin/pytest -q backend/tests，结果 293 passed in 12.87s。
- 客户端缓存行为 Node mock：通过；覆盖元数据缓存命中、异步持久化和非 HTTPS 媒体不缓存。
- 全仓 pytest：未通过收集，阻塞点为历史共享核心测试 platform/wecom-archive-core/tests/test_engine.py 缺少 app.codec，与本轮缓存改动无关。

## 生产部署与公网验证

- 部署文件：backend/app/main.py、backend/app/services/app_service.py。
- 部署前检查：服务器磁盘 59G 中使用 26G、可用 31G；Docker 未执行 prune；生产容器和 PostgreSQL 健康。
- 备份目录：/home/ubuntu/teambuy-backups/cache-audit-20260827-050322。
- 部署后：backend、worker、archive worker 重启成功；本地健康检查通过；公网 https://teambuy.lifelove.top/health 返回 200 和 no-store 响应头。
- 生产文件 SHA256 与本地待部署文件一致。
- 未部署小程序包；手机端必须由用户在微信开发者工具重新编译并上传体验版。

## 未覆盖项与风险

- 未在真实微信手机上测量冷启动、页面返回和缓存命中耗时；需要体验版人工验收。
- 生产当前为单 API 进程的进程内服务端缓存；多进程/多副本扩容前需要 Redis 或共享失效机制。
- 公网业务接口未使用真实登录令牌做完整业务链路验证，本轮以健康检查、响应头、后端测试和源码校验为主。
