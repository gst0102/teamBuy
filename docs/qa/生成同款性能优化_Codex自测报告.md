# 生成同款性能优化 Codex 自测报告

日期：2026-08-24

## 结论

后端性能优化已完成并部署生产。生成同款不调用 AI、OCR、分享图生成或媒体转码；主要瓶颈是旧实现对完整 `AppState` 的全量读写。

## 修改内容

- `same_style_generations` 改为按用户和幂等键定向查询、按表写入。
- `referral_relations` 仅在需要时读取，并与生成记录合并为同一数据库事务。
- 同款净化流程减少源用户重复查询；公开内容、联系方式替换、统计隔离和幂等语义保持不变。

## 验证结果

- 本地 `backend/tests/test_sales_scrm.py -k same_style`：`3 passed`。
- Python compileall、AST 检查、`git diff --check`：通过。
- 生产 `/health`：200；`teambuy-backend-1`、`teambuy-backend-worker-1`：稳定运行。
- 线上已有幂等请求：部署前约 `0.468s`，优化后连续 5 次为 `0.0265–0.0308s`。
- 生产数据计数未变化：`same_style_generations=4`、`user_notes=1336`；未创建生产测试资料。

## 未覆盖与人工验收

本轮没有在生产创建新的同款资料，避免污染真实账号数据。请用户从公开资料页实际点击一次“生成同款”，确认首次生成快速进入编辑页，并检查内容净化及当前用户联系方式正确。

生产回滚备份：

- `/home/ubuntu/teamBuy-backups/same-style-performance-20260824-225504/`
- `/home/ubuntu/teamBuy-backups/same-style-performance-atomic-20260824-230235/repository.py`
- `/home/ubuntu/teamBuy-backups/same-style-profile-read-20260824-230555/app_service.py`
