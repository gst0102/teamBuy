# 生成同款复用与排序优化 Codex 自测报告

日期：2026-08-24

## 结论

通过本地自动化验证和生产只读验证。小程序前端尚未上传体验版，真机验收待人工完成。

## 实现范围

- 同一用户、同一来源、`reuse_content` 模式再次生成时，复用仍有效且归属正确的历史同款。
- 资料库和合集列表按同款生成时间置顶，普通资料保持原排序。
- 列表返回并展示“同款”标识；生成成功后清理服务端和客户端列表缓存。
- 公开资料页将时间戳幂等键改为稳定键；`use_own_content` 暂不做语义去重。

## 验证记录

| 项目 | 结果 |
| --- | --- |
| `backend/tests/test_sales_scrm.py -k same_style` | 3 passed |
| Python 编译 | 通过 |
| 相关 JS `node --check` | 通过 |
| `git diff --check` | 通过 |
| 生产 `/health` | 200，PostgreSQL configured |
| 生产只读语义复用 | `duplicate=true`、`reused=true`，未新增资料或生成记录 |
| 生产列表排序 | 首项为已有同款，`isSameStyle=true`、标签为“同款” |

## 生产变更与回滚

- 生产备份：`/home/ubuntu/teamBuy-backups/same-style-reuse-sort-20260824-232549/`。
- 只更新后端 `app_service.py` 与生产基线补丁版 `repository.py`；未覆盖生产环境变量、密钥、数据库或媒体目录。
- 如需回滚，恢复该备份中的两个后端文件后重启 `teambuy-backend-1` 和 `teambuy-backend-worker-1`。

## 待人工验收

在微信开发者工具上传体验版后验证：公开资料页点击“生成同款”能快速打开结果；返回资料库/合集后已有同款置顶并显示“同款”；再次点击同一来源不会新增重复资料。
