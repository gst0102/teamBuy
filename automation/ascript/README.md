# 资料整理助手 AScript 统一入口

`automation/ascript/__init__.py` 是唯一需要在 AScript 中启动的入口，显示
3×3 九宫格。原有的 `xhs_find_group`、`wechat_group_inventory`、
`wechat_account_identity` 和 `wechat_marketing_sender` 暂时作为内部功能模块，
不再要求用户从 AScript 的本地小程序列表中逐个运行。

## 当前九宫格

1. 小红书找群：调用现有只读搜索模块。
2. 加微信群：入口预留，尚未执行加入。
3. 扫描微信群：调用现有原生微信群扫描入库模块。
4. 微信群库：提示到 PC 运营后台查看，手机负责采集回传。
5. 群营销：调用现有安全发送器；当前使用 AScript 原生输入，任务和发送 UI 门禁失败时不会发送。
6. 微信账号：调用双微信昵称识别模块。
7. 设备状态：查看当前 AScript 原生输入模式；ESP32 暂不加载。
8. 任务日志：入口预留。
9. 设置：入口预留。

旧的 `probe` / `diag` 工程属于开发探针。统一入口在设备上验证通过后，再从
AScript 本地小程序列表中按明确名称逐个清理，不批量删除未知工程。
