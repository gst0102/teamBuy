# teamBuy 当前状态

## 本轮开发：互助任务一对一沟通与执行者报表 V1（本地实现，未部署/未上传小程序）

- 每个任务按“发布者 + 单个执行者”建立独立私聊，不建立多人任务群；同一任务的其他执行者看不到彼此的会话和消息。消息气泡由 `senderUserId === currentUserId` 判定：本人在右、对方在左，发布者与执行者两端镜像一致。
- V1 支持文字、经本人上传的截图、当前任务已配置的小程序入口卡片；卡片只允许打开任务配置的 `#小程序://` 入口。消息在后端持久化，会话保存未读数；前端每 4.5 秒轮询，不含微信订阅消息/实时推送。
- 执行者任务详情提供联系发布者入口；发布者任务管理详情展示已参与/已提交的执行者，可逐人开启私聊。公众号、网页、小程序入口打开/复制及羊毛福利解锁都会作为参与依据；发布者不能创建群聊。
- “我的”增加任务报表：按执行者汇总参与、完成、待验收、退回和已到账积分，并可回到对应任务。任务详情把完成提交入口放到任务说明/验收标准之后、评论之前。
- 后端专项与全套验证：`PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests -q`，451 项通过；涉及的 JavaScript `node --check`、`miniprogram/app.json` JSON 解析、`git diff --check` 通过。尚未在微信开发者工具编译/真机验收；体验版上传仍由用户手动完成。

## 最新实现：同名微信群按数量成组扫描与转发（后端已部署、手机已同步，待真机验收）

- 按当前决策，同一微信账号下相同群编号、规范化群名的多个微信群不再要求逐群建立身份；扫描器从实时 mode=6 控件树中统计同一快照下不同结果行矩形的数量，并将 `groupCode + groupName + occurrenceCount` 同步到 PC。
- PC 将这些扫描结果合成一个低颗粒度候选/路由包，保存 `groupOccurrenceCount`；任务仍报告物理收件数量。旧的多个候选别名也按一个包合并管理，包内任一候选被禁用/移出时整包跳过，明确找不到时整包更新移出状态。
- 发送器把路由包展开为对应数量的同名 UI 选择项；每项都重新读当前搜索结果矩形、重新定位后点击，并核验微信“完成(n)”逐次递增。超过 9 个收件项继续沿既有分块处理；不靠行序/固定坐标持久化群身份。
- 计数边界：扫描器跨滚动重叠页和搜索前缀取最大共现数，避免把同一物理行重复相加；如果两个同名群没有在任何同一实时快照里同时出现，则没有可靠信息推导其总数，当前数量可能低估。只有下一次完整可见扫描更新计数后，PC 数量才会随之刷新。
- 验证：定向后端/API、AScript 纯逻辑测试 `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests/test_automation_group_reconcile.py backend/tests/test_ascript_sender_logic.py backend/tests/test_ascript_inventory_logic.py -q`（56 项通过）；两份 AScript 模块及涉及的后端 Python 模块 `py_compile` 通过，相关差异 `git diff --check` 通过。2026-09-14 已部署后端并同步正式手机工程；尚未运行真实微信扫描/转发。历史运行结果未改写。

## 最新修复与同步：production reconcile `scanMode` 兼容

- 两次完成邮件均显示 g10/c10 前缀扫描本身成功（8 群 + 1 群），但 reconcile 无确认、发送器耗时和目标数均为 0，因此发送器没有启动，未进入素材群。
- 最新运行编号 `wechat-assistant-batch:1789325339124` 给出明确原因：线上 `/api/automation/group-candidates/reconcile` 对 `scanMode=targeted` 返回 HTTP 422，要求值只能为 `full` 或 `incremental`。本地工作树的后端 schema/service 虽已支持 `targeted`，但该版本未部署到线上；这是服务端版本契约不一致，不是 30 秒超时。
- 已在 AScript reconcile 请求中把本地定向扫描模式 `targeted` 映射为线上已支持的 `incremental`，并继续发送 `coverage=partial`、`deleteMissing=false`；手机仍按 PC 前缀配置执行定向扫描，PC 只做增量 upsert，不会因未扫描到而删除群。同步确认与错误细节报告、发送门禁均保留。
- 验证：扫描器 `py_compile` 通过；定向后端部分扫描测试及入口报告测试共 4 项通过；相关文件 `git diff --check` 通过。已只上传 `wechat_assistant/wechat_group_inventory/__init__.py` 至 nubia NX711J `192.168.1.237` 的正式工程；设备文件长度为 91369 字节，与本地相符。未部署后端、未启动 AScript、未执行群发。下一次手动运行需确认线上 reconcile 返回当前账号的 scanId 后，入口是否继续启动发送器。

## 最新排查：2026-09-14 02:02 扫描后未观察到素材群搜索

- 用户观察到本次运行执行了 `c10`、`g10` 扫描，但没有看到搜索“卡片素材群”或转发。约 02:07 只读复核时 AScript runtime 已停止；`get_run_log` 未收集到本次日志，设备树与屏幕观察不一致，无法确认本次扫描是否成功完成、PC 是否创建任务或发送器是否开始。
- 静态流程是每个账号先加载扫描器；若扫描错误/账号不完整，入口在 `preflight_failed` 处直接停止，不加载发送器。若通过门禁，则进入 `sender_started` 并加载发送器。发送器从 PC 请求当前账号的 `c1001` 批次任务；当 `createdCount=0` 且目标数、跳过数也为 0 时，会正常返回 `idle`，在打开素材群前结束账号流程。该分支最符合“扫描可见、素材群搜索未发生”的现象，但不是本次运行的已证实原因。
- 另发现统一入口尚未执行 PC `scanOnly` 配置门禁：入口清除 `TEAMBUY_PREFLIGHT_ONLY` 后会继续调用发送器；扫描器仅在独立 preflight-only 路径读取该开关。因此当前不能依赖 PC 的 `scanOnly=true` 阻止统一入口创建/领取发送任务。此项尚未修复。
- 本轮未修改 AScript 代码、未同步、未操作设备。需取得本次合并报告中的 `scanSummaries`、每账号 `queueSummary.createdCount/targetCount/skippedCount`（或 `sender_no_account_targets` 阶段）才能区分扫描门禁失败与 PC 零任务；不得把“看见前缀扫描”推断成群发任务已创建。

## 最新复测记录：2026-09-14 扫描阶段诊断日志补充（真机复测未进入扫描）

- AScript 入口现在会在扫描失败门禁前保存本轮已得到的扫描结果，并输出精简的账号/前缀诊断：前缀阶段、滚动次数、失败前群数及 PC reconcile 计数；扫描器也逐前缀记录阶段与计数。该记录不含群列表或凭证，且没有放宽“任一账号/前缀失败则禁止发送”的门禁。
- 为避免运行阶段记录中的同步 UI Toast 阻塞主流程，`_write_run_phase()` 现在只写状态文件和运行日志；这项改动是稳健性处理，尚未证实为本次停滞根因。
- 本地验证：AScript `py_compile` 通过；定向测试 32 项通过；`git diff --check` 通过。正式 `wechat_assistant` 工程入口和 `wechat_group_inventory` 扫描器已同步到设备。
- 两次均通过正式工程入口启动。第一次停在微信会话列表且无可用 AScript 运行日志；第二次在 Toast 移除后仍停在会话列表，状态文件最后更新时间为 01:52:28，运行日志仍未收集到。控件树与截图页面不一致，因此没有依据继续操作。两次均已停止，设备当前 `is_script_running=false`。
- 本轮没有确认任何群扫描完成、PC 群映射/任务创建、素材卡片转发、微信送达或后端结果；不得把本轮记为端到端测试成功。移除 Toast 后仍出现同样停滞，故阻塞的确切阶段/根因仍未知，需下一次运行能取得有效阶段日志后再定点处理。此前历史运行记录未改写。

## 最新复核：2026-09-13 23:22 群扫描在输入前被输入法门禁拦截

- 用户确认前缀顺序无关；设备 `android-01` 的 PC 配置 GET 返回 `searchPrefixes=[g10,c10]`、`scanOnly=false`，两个前缀都已配置。
- 23:22:23 启动的现场日志确认：入口收到“群发微信”、选中第 1 批、加载上述 PC 配置，并打开第一个双开槽位；账号身份成功读为 `gaoshiteng_01`。搜索首个前缀 `g10` 前，代码检测 `Ime.is_active()` 为 false，抛出“AScript 输入法未处于激活状态”；因此未调用 `Ime.input(g10)`，按前置扫描失败保护未继续 `c10`，没有群映射、任务创建或发送动作。扫描汇总为 0 群、degraded；完成邮件记录 failed 且已发送。
- 异常收尾日志显示执行了两次官方 HID 右滑并回到微信聊天列表，随后 `HID_BRIDGE_STOP_CONFIRMED`。屏幕截图也显示微信会话列表；但随后 10 秒 AScript 状态接口仍返回 `is_script_running=true`，期间没有新日志，因此不能确认 AScript runtime 已完全退出。
- 本轮只监控与读取，没有修改 AScript/后端代码、写 PC 配置、点击设备或同步工程。扫描输入失败根因已定位为输入法未激活；runtime 状态未退出是另一项独立待确认问题。

## 本轮定点修复：2026-09-13 九宫格点击后未启动扫描

- 用户约 22:29 测试反馈点击群发后没有扫描；AScript 日志未收集到输出，当前设备只确认 runtime 已停止，无法从该次运行日志还原确切停滞阶段。
- 代码检查发现入口回调在把功能事件放入队列前，先做状态文件/Toast 更新并同步关闭 WebWindow；若回调线程在这些操作上阻塞，主线程就收不到启动扫描事件。已改为回调先入队，状态更新和关闭窗口由入口主线程处理；窗口关闭异常会明确记录并停止，不会假装已开始扫描。
- 同步前设备正式工程入口为 32,876 字节（15:35），本地修复后入口为 33,613 字节；扫描器已是 22:19 的版本。已只上传正式工程入口，未启动自动化。入口 `py_compile` 与相关文件 `git diff --check` 通过；修复能否解决当次无响应仍待用户手动复测。

## 本轮修复：2026-09-13 定向扫描页面误判与多前缀部分结果保留

- 最近一次扫描的可用证据为：PC 扫描配置 GET 与微信账号 heartbeat 成功，但没有到达群候选 reconcile；AScript 未保留该次详细运行日志，因此不能断言具体失败前缀或动作。
- 用户约 22:12 手动测试报告“秒退”，并更正：底部 Tab + 顶部搜索入口在该设备是已验证的首页识别方案，不应因可见 action-bar 返回控件否定首页。已撤销这一新增门禁并恢复原来的页面识别规则；保留下面的多前缀部分结果保护。
- 多前缀扫描在任一前缀异常时停止后续 UI 操作；先前已读到的群仍以 `deleteMissing=false` 做 partial upsert，并将账号/运行标记为 degraded，禁止据不完整范围创建发送任务。
- 新增扫描器纯控件树回归测试；扫描器 `py_compile`、定向 pytest 16 项和 `git diff --check` 已通过。撤销首页门禁后的修正版已重新同步至正式 `wechat_assistant/wechat_group_inventory/__init__.py`，设备端与本地均为 85,797 字节（2026-09-13 22:19）；同步前停止了残留运行实例，上传后未启动，当前 runtime 已停止。完整真机扫描与 PC 台账结果仍待用户手动测试。

## 本轮开发：2026-09-13 PC 扫描范围配置与多目标群发收敛（后端已部署、扫描器已同步；待手动真机验收）

- PC 自动化设备面板现在可按设备配置群编号前缀（允许 `g`/`c` 开头，例如 `g10,c1001`），也可选“仅扫描同步”或“扫描后创建发送任务”。AScript 每次启动从后端读取配置；后端不可达或配置无效时停止，不回退到另一组前缀。旧设备默认仍为 `g10`。
- 定向扫描逐个查询所有配置前缀；重叠前缀按同一物理群候选合并。新增群沿用默认允许营销，已有管理员禁用状态不被扫描覆盖。运行邮件现在保留并显示本次扫描前缀及运行方式。
- 群候选、扫描映射与发送任务已支持可选的成员身份 SHA-256 指纹；PC 按候选 ID 区分同名群，并在一次扫描内合并相同指纹的重叠结果。原始成员名不上传或持久化。
- **未完成项：**当前手机扫描器还没有从微信群详情页提取前 10 位成员并在本地生成指纹。因此遇到同群编号、同群名的多个搜索结果时，手机会明确停止同步而不合并；此类重名群目前不能声称已支持自动区分/群发。需依据真实控件树实现并单独真机验收。
- 转发时若某目标在搜索输入已确认后得到明确“群不存在/无搜索结果”，会记录该目标并继续发送已确认选中的其他群；搜索输入未确认、同名结果数不匹配、选择数不一致等不确定状态仍停止，不点击“完成”。
- 验证与发布：完整后端测试 `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests -q` 为 428 项通过；本轮定向扫描/邮件测试 16 项通过；两个 AScript 入口 `py_compile`、PC 管理页扫描配置内联 JavaScript `node --check`、相关 `git diff --check` 通过。2026-09-13 已备份 Compose 与变更前后端源码，并仅热修部署 API（扫描配置 GET/PUT、`device-run`、`runs/complete`/合并邮件服务及 PC 管理页）；API、PostgreSQL 健康，OpenAPI 四条扫描相关路由已注册，设备认证 GET 成功；邮件配置启用且 SMTP 已配置，本轮未触发真实邮件。worker、PostgreSQL 未重启。nubia NX711J `192.168.1.237` 的正式工程 `wechat_assistant/wechat_group_inventory/__init__.py` 已同步至 82911 字节；同步前停止旧运行实例，上传后未启动，当前 AScript runtime 已停止。设备登记配置仍是 `searchPrefixes=[g10]`、`scanOnly=false`，部署没有改写扫描范围。尚未进行新的真机扫描或群发验收。

## 最新修复：2026-09-13 素材群搜索返回与失败后退出

- 发送后离开素材群时，若聊天页返回动作落到仍带有非空查询和唯一 mode=6 返回控件的微信搜索结果页，代码先确认该中间页，再点击其实时返回控件并确认会话列表；无法唯一确认时仍截图并停止，不盲点或盲滑。
- 入口失败详情写入运行阶段与 AScript 日志，不再用阻塞式 `Dialog.alert` 卡住单次脚本退出；合并报告仍按原流程发送。目标选择、发送动作和送达判定未放宽。
- 本地 `py_compile` 通过，`backend/tests/test_ascript_sender_logic.py` 15 项通过，相关文件 `git diff --check` 通过。
- 入口与发送器已同步至 nubia NX711J `192.168.1.237` 的正式工程 `wechat_assistant`；设备文件长度分别为 32102、171981 字节。只上传文件，未启动或执行真机测试；当前设备脚本停止，等待用户手动测试。

## 最新修复：2026-09-13 群发结果与微信收尾报告分离

- 合并完成邮件在双开账号各自“扫描 → c1001 转发”流程结束或停止后统一发送，不在账号扫描之间单独发送；发送器单独通知保持 defer。
- 邮件优先按 `targetResults` 统计群目标：区分 UI 确认送达、已发出发送动作但未自动确认、目标未发送/失败、目标结果未回报。旧版 `failureCount` 不再覆盖目标明细，避免把发送后的微信会话列表复位错误计成目标群发送失败。
- 微信页面复位失败作为独立流程/收尾异常报告。`send_action_sent_unverified` 仍不冒充 UI 或后端送达确认；本次邮件原始数据没有送达回执，用户另行确认两群实际收到，二者分别记录。
- 发送后回到会话列表优先从 mode=6 实时树定位唯一微信返回按钮并经官方 HID 点击，随后确认列表；不执行固定次数盲滑。流程结束后九宫格忽略重复入口事件，不自动重启下一轮。
- 后端定向邮件/AScript 逻辑测试共 16 项通过；两份 AScript 文件 `py_compile` 与本次文件 `git diff --check` 通过。仅为本地代码验证，未同步手机、未部署后端、未进行真实设备复测。

## 最新修复：2026-09-13 c1001 第二群搜索焦点与移出状态测试准备

- 发送器在每个转发目标前仍执行 `BleDevice.clear()` 并等待 0.6 秒；随后重新读取实时 mode=6 搜索输入框矩形，由官方 HID 再次点击并确认焦点，确认失败则在输入群名和点击“完成”前停止。这样保留当前清空方案，同时补上清空后、`Ime.input()` 前缺失的焦点确认；关键停止条件已写入代码注释。
- 设备端测试显示 leo 的 c1001“互助群”此前 `canSend=true` 但 `membershipStatus=removed`，任务生成因此会跳过。按用户授权仅将其状态改为 `unknown` 并清空过期 `lastVerifiedAt`；保留营销许可、最后活动记录、错误原因和历史任务，不把成员状态伪标成 `active`。当前状态为待重新确认群成员资格，允许本轮任务生成流程继续检验。
- 本地 `py_compile` 通过；`backend/tests/test_ascript_sender_logic.py` 为 12 项通过；发送器与状态文档 `git diff --check` 通过。
- 发送器单文件已上传正式 AScript 工程 `wechat_assistant`，设备文件长度与本地均为 164537 字节；通过 `run_project("wechat_assistant")` 后截图确认九宫格显示“状态：等待选择”，设备 runtime 正在等待。未选择批次、未扫描群、未打开转发页、未发送卡片或文字。AScript 日志工具未收集到输出；真实多群 UI 与后端发送结果仍待用户测试。

## 最新部署：2026-09-13 07:29–07:35 手机同步与后端热修复

- 已将本地发送器同步到 nubia NX711J `192.168.1.237` 的正式路径 `/storage/emulated/0/airscript/model/wechat_assistant/wechat_marketing_sender/__init__.py`；上传成功，设备文件长度与本地同为 163386 字节，`local_config.py` 修改时间保持不变。通过 `run_project("wechat_assistant")` 启动根入口，截图确认九宫格处于等待选择状态；日志工具未收集到输出，本轮没有选择批次或发送微信群。
- 后端按现行热修复流程，仅将已测试的 `create_device_batch_tasks` 方法移植到线上运行源码基线，保留其他线上行为；未将本地其他未发布改动一起上线。API、backend-worker、archive-worker 均更新，各容器与宿主机该文件 SHA256 为 `44b4e4425763c0596d95ac12ad29f3477611db4b3937a330aa8f9804783f6142`；部署方法 SHA256 与本地相同，为 `8de2ba75ac04fa30dc6f3b4afe0c9ed9b53c82fb5f3667999046d92ac381dc0d`。
- 备份目录 `/home/ubuntu/teambuy-backups/20260913-072946-c1001/` 保存原 Compose、原宿主机源码、原运行源码与发布源码；三个服务分别保留 `rollback-20260913-072946-c1001` 镜像标签。切换首次因临时构建容器继承 Compose 标签产生名称冲突，已恢复旧 API、删除本次三个未启动替换容器后重新切换成功；未删除镜像、数据卷或业务记录。
- 上线检查：三个应用容器与 PostgreSQL 均 healthy；容器 `/health` 与 `/health/db` 返回 200，数据库 connected=true；公网 `https://teambuy.lifelove.top/health` 返回 ok，生产映射保持 `8004:8000`。环境变量、密钥、媒体与数据库数据未修改。
- 同次只读线上群列表发现：leo 的 c1001 下，“测试群” canSend=true / membershipStatus=unknown；“互助群”（group_candidate_59116af545）canSend=true / membershipStatus=removed。当前后端会因 removed 跳过互助群，新版双目标完整性保护会拦截单群任务。该发现解释当前过滤结果，但不将其冒充历史每一次 skippedCount 的已留存明细；本次没有恢复成员状态或改写历史发送结果。

## 最新修复：2026-09-13 c1001 双目标链路收敛（本地验证）

- 素材扫描取消固定 12 次最低预算和 120 次截断；按当前可见 `act-x` 与目标编号中的最大数字确定总预算，不再把已完成次数重复加到剩余预算。找到目标或确认无进展即提前结束。官方 HID slide 后仍等待 1.5 秒，树恢复按 0.8 秒间隔有界轮询。
- 素材群标题和历史区域共用同一次 mode=6 树与统一标题规则；树漏标题时接受实时标题栏 OCR。历史滑动区域仍来自实际列表或 `act-*` 消息父容器，OCR 标题仅补充裁剪边界。移除卡片查找层重复的前后标题检查，由滑动函数统一复核。
- 修正 `_is_wechat_chat_list()` 向无参数 `_dump()` 传参的问题：此前 TypeError 被捕获后会恒返回 False。
- PC 入队先检查候选资格，再统计实际接受目标是否达到 `maxTargets`；禁用/移出候选不占名额。响应新增 `skippedItems`，包含群编号、群名、候选 ID、账号、原因码与说明；方案级错误带群编号和批次。手机输出 `QUEUE_SKIPPED` 并将明细放入既有运行汇总；旧后端仅返回计数时明确输出明细不可用。
- 领取任务再次检查完整测试群名数组，防止旧单群任务绕过入队检查。原生转发仍每组最多 9 群，每块只定位/长按一次卡片，逐个搜索真实群名后统一完成；`TEST_ONLY` 不允许部分目标进入发送。空任务且有跳过记录不再当正常空账号悄悄继续。
- 后续行为收敛见本文件顶部“本轮开发”：微信明确返回群缺失/无结果时允许发送已确认选中的其他目标；输入和点选状态不确定时仍停止。
- 验证：后端相关 26 项测试通过；设备无关发送器回归 11 项通过，覆盖数字预算、树漏标题时 OCR 辅助历史区域定位、首页读取参数、领取旧单群任务拒绝、滑动后第一帧仍旧时继续等待；AScript py_compile 与 git diff --check 通过。未同步手机、未部署后端、未执行微信动作，不能标记完整群发通过。历史运行记录保持原样。

更新时间：2026-09-13

本文件是当前项目状态的唯一汇总入口。它记录已确认事实、当前边界和未决事项，不替代代码本身的运行结果。

## 1. 读取顺序与状态定义

1. 根目录 `AGENTS.md`：全项目通用工程规则。
2. 本文件：当前产品、实现和风险状态。
3. `docs/decisions-active.md`：已确认的长期决策。
4. 相关代码、测试和配置：验证具体任务的真实状态。
5. `docs/archive/`：仅作历史追溯，不产生当前约束。

“已实现”只表示代码或配置已经存在；是否可用还要看对应静态检查、运行日志、真机结果和用户验收证据。

## 2. 产品当前基线

- 正式产品名：资料整理助手。
- 核心闭环：企业微信/微信/手动内容进入资料库，统一整理为 typed content card，再由小程序编辑、发布、展示和追踪。
- 稳定能力包括身份、会话归档、资料库、展示页、媒体资产、权限和支付权益；房源、团购、服务、电子名片、客户雷达等属于场景能力。
- 小程序可以按需登录；公开内容不应被登录弹窗阻断。
- 前端列表优先返回元数据，媒体和非关键计算后台补齐。

## 3. 当前架构事实

- 文字来源统一抽象为 `ContentObject`，通过 `content-to-note` 生成 `UserNote`。
- 资料卡使用 `cardType` 和 `structuredData`，第一版继续以 `UserNote` 作为统一容器。
- 用户归属以小程序微信 `openid` 为唯一锚点；企业微信身份是来源映射。
- 企业微信会话存档采用共享核心，项目只接收已路由事件并维护自己的幂等和处理状态。
- 图片媒体必须登记 `originalSha256`、`storageSha256`，业务入口复用统一媒体处理服务。
- 分享快照统一由 `share-snapshot` 插件和后端快照接口管理，版本不一致时必须重新准备。

## 4. 当前 AScript + ESP32 测试事实

- `automation/ascript/__init__.py` 是 AScript 入口；当前只启用“群发微信”卡位，运行时先完成两个微信账号的定向群台账扫描，再按 PC 批次执行发送器。专项规则见 `automation/ascript/AGENTS.override.md`。当前已同步到设备工程 `wechat_assistant`（入口页面显示“微信助手”）；手机实际启动的是哪一个工程，仍必须以设备上的实际工程路径/文件清单和运行日志确认，不能仅凭本地代码或同名项目推断。
- 历史确认（2026-09-08）：在 `hid_e2e_20260908` 工程中，`esp32` 模块可导入，ESP32 已连接，`hid-test`/HID 执行链路完成过真实微信 UI 发送；该成功记录仍然有效。当前运行状态必须单独核对，不能由历史结果代替。
- 当前连接核验（2026-09-10 00:27，手机本地时间）：通过 `run_project` 运行手机上现有的 `hid_e2e_20260908` 连接检查入口，`esp32` 导入成功，`HID_CONNECTED=True`，设备名为 `AS_4.8_905DDCBA2010`。本次只验证插件和连接，没有执行点击或微信发送；此前 `eval_python` 的导入异常不能作为正式工程不可用的证据。
- `BleDevice.click()` 的返回值为 `None` 是正常 API 行为；它只说明函数调用返回，不能单独证明手机界面已经发生目标变化。
- 用户已在手机界面观察到 `ble.clear()` 确实清空输入框，因此清空动作链路已有可观察证据。
- 2026-09-10 05:07：用户反馈“微信助手”九宫格第 3 格无响应。复核确认页面截图仍显示九宫格且 `wechat_assistant` 正在运行，但 `mode=0/6` 控件树均未暴露 WebWindow 页面控件；`mode=6` 同时返回截图中不可见的双开微信选择器，不能作为该页面点击状态的证据。入口已增加点击状态反馈、touch/click 双事件兼容和 15 秒无回调时的原生菜单兜底；本轮只验证兜底菜单出现，尚未验证第 3 格 WebWindow 回调或发送链路。
- 当前测试分为 `TEST_SINGLE`（单个 `TEST_ONLY` 测试群）和 `PRODUCTION` 两个明确模式。单个本人测试群允许完整端到端验证；生产路径不继承该测试权限。
- 微信卡片测试只允许通过微信客户端已有的正常转发 UI，不构造协议、不解析小程序 XML、不调用私有接口。
- 2026-09-10 已按“控件树感知 + ESP32 HID 执行 + 状态复核”重构 AScript 相关模块：`wechat_assistant` 的发送器和群扫描器已同步；HID 页面感知统一使用 `mode=6`，动作目标必须来自唯一控件树 `rect`，实际点击、长按、滑动、返回和输入由官方 `BleDevice` 执行，OCR 仅作状态确认；卡片定位的滚动要求控件树状态实际变化，避免重复盲滑。本轮只启动并验证了 `wechat_assistant` 九宫格，未执行真实群发。

## 5. 群路由当前状态

- 现有 AScript 模块包含微信群扫描/台账相关能力；当前代码和文档不能视为已经完成生产级批量执行。
- PC 群台账支持人工维护多个群编号（例如 `g1001`、`g1002`），用于按编号路由多个群；编号保存于 `AutomationGroupCandidate.groupCodes`，不是微信搜索关键词。
- 发送内容已从单群配置中抽离，统一保存于 `AutomationGroupContentPlan`：一个群编号对应多批文字/小程序卡片内容，一个群编号可以作用于多个群；群配置只维护群画像、营销状态、每日上限、编号和备注。
- PC 端只维护群编号、卡片目录和批次内容；AScript 启动时由用户选择第 N 批。后端按“微信账号 + 群编号”生成一个分组任务，任务内携带该编号下的真实群名单；手机端按微信原生最多 9 个收件群分组发送。群编号来自数据库配置，不写死 `c1001`，也不作为最终群身份。
- PC 端生成任务与手机执行分离；AScript 发送器仅在本地配置明确启用 `TEST_SINGLE`/`TEST_ONLY` 时执行官方 ESP32 HID + 微信正常 UI 的单次发送，其他情况保持 dry-run。每批必须有小程序卡片，文字是同一转发页的可选附加内容；生产营销发送仍未开放。
- 手机执行器对每个目标群返回独立结果；明确搜索不到的群会由后端标记为 `removed` 并记录原因，后续批次不再入队；页面状态不明确则停止，不自动跳过或盲点。
- 群路由需要绑定到具体微信账号和唯一聊天对象，并在进入聊天后用顶部标题或其他界面锚点复核，不能只依赖同名群标题。
- `g1001`、`g1002` 这类编码是可行候选，但用户尚未最终定版；在定版前不得让代码把旧的数字备注或新编码当成同时有效的生产协议。

## 6. 当前明确边界

- 不修改微信客户端，不注入微信进程，不研究私有协议，不提取 token/session/key。
- 不自动加群、加好友，不做无人值守的营销执行，不用随机延迟或其他方式规避安全检测。
- 测试只使用本人设备、本人账号和本人创建/授权的测试群；一次只处理一个测试群和一条明确内容。
- 生产部署、微信体验版上传、真实用户数据操作和上线决定都必须另行确认。

## 7. 目前未决事项

- `g1001` 编码是否成为正式群路由格式。
- 群唯一标识在微信 UI 中的最终复核策略和失败恢复策略。
- 生产发送能力是否采用官方能力，以及对应的权限、审计和限额设计。

## 8. 工作区提示

本次文档治理前工作区已有大量业务代码和文档未提交改动。本次整理不修改业务代码；若要继续开发，必须重新查看当前 Git 状态，不得把已有未提交内容误判为本次完成结果。

## 12. 2026-09-09 测试证据与 AScript 工程隔离

- 2026-09-08 的真实端到端测试记录仍然有效：当时使用的具体工程、运行环境和日志证明了 ESP32 HID + 微信原生 UI 的文字发送与小程序卡片转发链路成功。后续某一次运行失败，不得改写或否定这条历史证据。
- 2026-09-09 对新工程 `wechat_assistant` 重跑两个 `c1001` 群前，手机设备仍为 nubia NX711J、Android 15、AScript 4.0.03、HID 模式；PC 端已生成 `测试群`、`互助群` 两条任务，但发送器在 `plug.load("esp32")` 后执行 `from esp32 import BleDevice` 时返回 `ImportError: bad magic number in 'esp32': b'H8tX'`。因此本次只确认“当前导入异常”，未领取任务、未点击微信发送、未验证文字或卡片。
- `bad magic number` 发生在手机 Python 导入 `.pyc` 阶段；当次运行时看到的文件头不是 Python 3.8 可识别的字节码头。它只能说明当前插件缓存/加载环境不可用，不能单凭此错误断定昨天成功无效，也不能未经同环境对比直接下结论说是版本不匹配。具体变化来源仍需 AScript 官方插件/运行时对照确认。
- Mac 本地 Python 3.13（当前为 3.13.14）只用于本地静态检查、后端或部署工具；不能替代手机端 AScript Python 3.8，也不能加载依赖 Android/Chaquopy/BLE 环境的 `ascript.android` 和 `esp32`。Android/iOS AScript 脚本必须在设备端运行。
- 后续复盘固定按运行实例记录：历史成功保持原样；当前失败只新增当前运行记录。必须同时核对工程名和实际路径、设备与账号、AScript/Python 运行时、插件来源与缓存、运行日志和页面截图；没有页面证据不得报告发送成功，没有异常输出不得补写异常。
- 2026-09-09 的 `eval_python` 导入异常（包括 `bad magic number`）只能标记为“当前这一次运行的导入异常”。在没有对齐工程路径、运行时版本、插件缓存、设备状态和运行日志之前，不得扩大表述为“之前测试不成立”或“已经确认版本不匹配”。
- AScript 测试报告必须绑定：工程名及实际工程路径、设备/微信账号、开始时间、运行编号、运行时与插件状态、关键日志和页面截图；报告必须明确区分“历史成功”“当前调用异常”“页面未验证”“用户验收通过”。没有异常输出时，不得凭推测补写异常；没有页面证据时，也不得把连接日志写成发送成功。
- 本轮确认采用独立工程方案：新建并验收“微信助手”作为正式九宫格入口；现有“资料整理助手”保留为备份。新工程未完成文件核对、部署和用户验收前，不删除、不覆盖、不宣称已部署。
- 设备上存在多个 AScript 工程副本时，先记录实际启动工程和路径，再进行同步或测试；仅查询到某个同名副本，不足以证明它就是手机当前启动的工程。

## 13. 2026-09-10 ESP32 插件恢复尝试

- 手机端 AScript 已由 4.0.03 升级到 4.0.12，`eval_python` 主进程仍使用 Python 3.8.16。升级后的 `eval_python` 调用中，`plug.load("esp32")` 返回成功，随后 `from esp32 import BleDevice` 报 `ImportError: bad magic number in 'esp32': b'H8tX'`；这条记录只适用于该调用环境。
- 之前已备份当前缓存为 `esp32.reinstall_backup_20260910`、重新获取 `esp32:4.7.0`；升级后也清理并重新加载过明确的外部插件目录，备份保留。这些尝试没有消除 `eval_python` 的异常，但不能由此推断正式工程需要换插件包。
- 本轮只读核对：真实包名为 `com.aojoy.airscript`。用户提供的 `com.ascript.app` 两个缓存路径在该设备上未发现；实际应用 `cache` 下扫描 22 个目录未发现 `esp32` 条目。运行工程前，`importlib.util.find_spec("esp32")` 的 `origin` 和 `cached` 均明确指向 `/data/user/0/com.aojoy.airscript/files/line_plug/esp32/__init__.pyc`，加载器为 `SourcelessFileLoader`，不存在本次导入优先使用所述另一份缓存的证据。
- 2026-09-10 00:27:49–00:27:50（手机本地时间），直接用 `run_project` 运行现有 `/storage/emulated/0/airscript/model/hid_e2e_20260908/__init__.py`。运行前读取入口确认只有官方 `plug.load("esp32")`、`BleDevice()` 和连接输出，没有点击/发送。实时日志显示“模块 'esp32' 成功导入！”、`HID_NAME=AS_4.8_905DDCBA2010`、`HID_CONNECTED=True`。运行后截图仍为 AScript 首页。
- 工程运行前插件 `__init__.pyc` 的 SHA-256 为 `9869c5d2f82e45b8aca0059d6ac84d7cbf2da0fa4397b7633a2b874a24c8c976`、文件头为 `H8tX`；工程运行后该 `.pyc` 已不在目录中，资源、`build.as` 和插件包文件仍在；`eval_python` 主进程中也没有已加载的 `esp32` 模块。本轮没有清缓存或改插件文件。可确认工程加载过程与直接 Python 导入的行为不同；底层处理机制尚未核实，不能把此文件头直接定义为损坏或版本不匹配。
- 撤回此前“当前手机插件不可用、必须取得匹配插件包后才能继续”的扩大结论。后续 ESP32 验证及持久连接优先使用正式工程运行，`eval_python` 单次失败必须经工程日志复核。此次已验证插件导入和连接，尚未重新验证 HID 动作或两个 `c1001` 群发送；2026-09-08 历史成功保持有效。
- 新增固定操作约束：正式 ESP32 HID 测试不再使用 `eval_python` 导入、点击或发送；完整测试统一通过实际 AScript 工程的 `run_project` 执行。`eval_python` 只用于必要的只读诊断，不能用来替代正式工程测试，也不自动清理 AScript 运行缓存。

## 14. 2026-09-10 双开微信 c1001 测试复核

- 本次 `wechat_assistant` 的 `TEST_ONLY` 运行已确认 ESP32 HID 连接成功、PC 已生成 `c1001` 批次任务、`act-001` 卡片已在“卡片素材群”定位；但任务只创建了 1 个微信账号分组（目标数 2），原生转发页未完成两个目标群的匹配，因此没有发送成功 UI 证据。
- 设备双开选择器实际显示两个微信入口，两个入口均可通过 ESP32 HID 选择。两个账号的昵称都显示为 `leo`，但微信号不同（已观察到 `qq673105954` 与 `gaoshiteng_01`）；现有身份代码仅按昵称生成 `wechat-nickname-*`，会把两个账号合并，不能作为双开账号唯一身份。
- 后续双开发送前必须以微信号（或其他稳定且唯一的账号标识）更新账号身份、群候选归属和发送任务；在映射修复并重新核对两个账号的 `c1001` 目标前，不得报告双账号发送成功。测试结束后已停止运行并恢复 `wechat_assistant` 根入口文件。

## 9. 2026-09-08 电子名片客户预览

- 私有本人预览响应现在返回名片拥有者自己的联系方式；普通电子名片不使用商机场景的脱敏/隐藏规则。
- 客户预览页已将联系方式前置，并展示电话、微信、邮箱、网址、二维码；联系方式未填写时显示明确空状态，拥有者可返回编辑页补充。
- 精选资料已返回公开过滤后的图片、PDF 和链接附件元数据，客户预览页可查看图片、打开 PDF 或复制链接。
- 后端已部署到生产容器 `teambuy-backend-1`；本次仅替换 `backend/app/services/app_service.py` 和 `backend/app/api/routes_notes.py`，未修改数据库结构、环境变量、媒体目录或 secrets。
- 生产回退备份：`/home/ubuntu/teambuy-backups/20260908-200402-business-card-preview`；回退镜像：`teambuy-backend:rollback-20260908-200402-business-card-preview`。
- 本地相关后端回归测试通过；小程序静态检查通过。小程序体验版尚未上传，需由用户在微信开发者工具中手动上传并完成真机验收。

## 10. 2026-09-09 生产运行时修复

- 已将 `backend/app/services/app_service.py` 和 `backend/app/api/routes_notes.py` 同步到生产 runtime Compose 实际挂载目录 `/home/ubuntu/teamBuy/backend/`，本人预览接口现在返回 `ownerProfile`，联系方式可由客户预览页读取。
- 本次未修改数据库、数据库卷、环境变量、secrets 或媒体目录；生产备份目录为 `/home/ubuntu/teambuy-backups/20260909-093901-business-card-preview-runtime`。
- 当前运行镜像为 `teambuy-backend:business-card-preview-20260908-200402`，回退标签为 `teambuy-backend:rollback-20260909-093901-business-card-preview-runtime`。
- 2026-09-09 已部署动态群编号批次任务准备增量；运行镜像为 `teambuy-backend:dynamic-group-routing-20260909-dynamic-group-routing-final` 的服务标签，备份目录为 `/home/ubuntu/teambuy-backups/20260909-dynamic-group-routing`。三个后端容器和 PostgreSQL 均 healthy，未删除数据库卷；本次仍未开放生产手机 UI 实际发送。
- 2026-09-09 群编号批次准备已调整为不因群状态 `unknown`、活跃时间或群画像未完善而预先跳过；手机执行器明确找不到群时，会把对应台账标记为 `removed`、写入失败原因，后续批次不再为该群生成任务。本地定向回归 8 项通过；本次后端调整已部署到生产 API、backend-worker 和 archive-worker，三者代码 SHA-256 均为 `96e0d611f1fb2923bed58c6518f38ecd6fbbc1e7804eb5ace7acc0e485467439`，服务健康检查通过。
- 生产 runtime Compose 的默认 `PRODUCTION_RUNTIME_IMAGE` 仍指向缺少 `psycopg_pool` 的测试镜像；本次使用已验证的生产镜像显式启动，后续任何 runtime Compose 重建都必须显式指定可用镜像，不能直接使用默认值。
- 部署后 backend、backend-worker、archive-worker、PostgreSQL 均 healthy；内网 `/health`、`/health/db` 和公网 `/health` 均通过。

## 11. 2026-09-09 互助提交性能优化

- `create_mutual_help_submission` 已改为只在一个事务中 upsert 本次变更的互助任务、提交记录、积分账户和积分流水，不再在提交关键路径重写全部 Postgres 表；JSON 仓储仍保留原有全量快照语义。
- 本地互助积分测试 `11 passed`，后端编译检查和 `git diff --check` 通过。
- 已部署到生产 `teambuy-backend-1`、`teambuy-backend-worker-1`、`teambuy-archive-worker-1`；热修复镜像为 `teambuy-backend:hotfix-20260909-173453-mutual-help-submit`，三个服务标签指向同一镜像。生产备份目录为 `/home/ubuntu/teambuy-backups/20260909-173453-mutual-help-submit-fast-path`，旧镜像回退标签后缀为 `rollback-20260909-173453`。
- 部署后应用容器和 PostgreSQL 均 healthy，数据库仍使用原 `teambuy_postgres_data` 卷；互助任务/提交记录数量检查为 20/7，内网和公网 `/health`、`/health/db` 均通过，近期后端日志无异常。
- 部署过程中曾误用 `docker-compose.production-runtime.yml` 启动缺少 `psycopg_pool` 的测试镜像，应用容器短暂重启；已立即改用默认 `docker-compose.yml` 恢复，PostgreSQL 数据卷未删除，数据检查正常。
- 新的 `wechat_assistant` AScript 工程已创建并完成入口、群扫描、发送器和本地配置文件核对；“资料整理助手”仍保留为备份。手机真实 `c1001` 发送验收尚未执行，需在 PC 端先准备对应群编号方案、卡片目录标题和设备账号槽位后再做单次 TEST_ONLY。

## 14. 2026-09-10 任务分享卡片宣传语去重部署

- 任务分享卡片后端渲染器已统一使用 `mutual_task_backend_v5`；普通任务底部宣传语由后端唯一渲染为“更多人可参与，选任务就能轻松互动”。前端任务分享模型不再传入重复的 `marketingLine`、`trustLine`。
- 已部署到 `teambuy-backend-1`、`teambuy-backend-worker-1`、`teambuy-archive-worker-1`；三个容器内两个变更文件的 SHA-256 一致，均为 `share_card_renderer.py=ee745deed7349926232835d65634729813a6d66c3aa8eff5a8ca2c6aa4ed7799`、`routes_scrm.py=619a56e26a4bb034b256a62a5ddb86532688303e24da1d429ca4c8fe2e812062`。
- 生产备份目录：`/home/ubuntu/teambuy-backups/20260910-0005-share-card-slogan`；三个服务均保留回退标签 `rollback-20260910-0005-share-card-slogan`。未修改数据库、数据库卷、`.env`、secrets 或媒体卷。
- 部署后 backend、backend-worker、archive-worker、PostgreSQL 均 healthy；内网 `/health`、`/health/db` 和公网 `/health` 均通过。已存在任务 `local_1788847701125_321` 的分享快照返回 `ready`、`mutual_task_backend_v5`、`backend`。
- 小程序前端代码尚未由 Codex 上传体验版；前端 `task-share.js` 仍需用户在微信开发者工具中手动上传并验收。

## 15. 2026-09-10 双开身份修复后的当前结果

- 已将 `wechat_account_identity` 和 `wechat_group_inventory` 的账号边界从昵称改为微信“我”页读到的唯一微信号，内部 ID 形式为 `wechat-id-<wechat_id>`；昵称只作为展示字段。读不到唯一微信号时立即停止，不再回退为昵称派生 ID。

## 16. 2026-09-10 双开昵称更正与群发 SOP

- 用户更正当前双开昵称：两个账号分别显示为“高同学”和“leo”，不再是两个都显示为 `leo`。历史第 14 节保留当次观察，不改写；当前账号唯一边界仍是微信号，不使用昵称派生 ID。
- 正式工程运行确认第二个双开入口为 `leo / qq673105954`；第一个入口的 `mode=6` 树确认微信号为 `gaoshiteng_01`，其昵称按用户当前确认记录为“高同学”。该微信昵称大字当前未暴露在 `mode=6` 树，设备截图链路也出现黑屏，因此运行时硬门禁使用更稳定且树中可读的微信号；昵称只作显示核对。
- 已把完整群发 SOP 同步到 `automation/ascript/README.md`：选择批次后先从 PC 取得“账号 + 群编号 + 真实群名 + 文字 + 卡片编号”映射，再打开并核验微信账号、打开置顶素材群、按卡片编号定位相邻卡片、原生转发、多选、每组最多 9 群、可选文字、发送后 UI 确认和逐群回写，最后切换另一微信重复。
- 当前发送器的实际调用顺序已经是先请求 PC `device-run` 创建批次任务，再进入微信；上一轮能进入“卡片素材群”说明任务映射已经返回。上一轮失败根因仍是两个账号被合并为一个账号任务并携带两个目标，不能改写为“未查询 PC 数据”。
- 2026-09-10 11:34–11:38 正式 `wechat_assistant` 工程运行确认官方 ESP32 `AS_4.8_905DDCBA2010` 连接成功；本次只做账号身份读取，没有点击发送，也没有新增发送成功结论。
- 2026-09-10 11:57–12:00 使用正式 `wechat_assistant` 工程、官方 ESP32 HID 和 mode=6 实时矩形完成两个账号的定向只读核验。两个账号均通过“我”页微信号硬门禁：槽位 0 为 `wechat-id-gaoshiteng_01 / 高同学`，槽位 1 为 `wechat-id-qq673105954 / leo`。
- 按正式 SOP 搜索 `c1001` 后，`gaoshiteng_01` 的结果为“Python 资料”“小说素材”；`qq673105954` 的结果为“Python 资料”“互助群”“测试群”。直接按真实群名复核时，`qq673105954` 能进入“测试群”；“互助群”需通过 `c1001` 结果中的“群聊名: 互助群”匹配。上述操作没有长按卡片、没有进入转发页、没有发送。
- 同期生产库只读核对显示，当前 `c1001` 候选仍只有“测试群”和“互助群”两条，二者都归属旧账号 `wechat-nickname-* / leo`。真实 UI 表明二者都在 `qq673105954` 下，不在 `gaoshiteng_01` 下；因此不能把这两条候选强行拆成两个账号任务。若验收要求两个账号各一个 `c1001` 目标，PC 端必须先明确 `gaoshiteng_01` 应使用“Python 资料”还是“小说素材”（或配置其他真实目标），否则两个账号任务门禁应继续失败。
- 本轮发送测试未满足“两账号各一个目标”的前置映射，未创建新的稳定账号发送任务，也没有任何目标群发送结果。设备工程已停止并恢复 `wechat_assistant` 根入口；不把本轮报告为发送成功。
- 已将 `wechat_assistant` 设备端 `TEST_ONLY` 配置为两个账号 ID：槽位 0 为 `wechat-id-gaoshiteng_01`（“高同学”），槽位 1 为 `wechat-id-qq673105954`（“leo”）；测试白名单保持为 `c1001` 下的“测试群”和“互助群”，卡片固定校验 `act-001`。设备端敏感配置只保留在 AScript 本地配置文件，未写入文档或前端。
- 双开选择器的实时 `mode=6` 控件树已按 `GridView` 下的单项容器矩形取点；不会使用共享 `GridView` 矩形、固定坐标或昵称判断账号。此前实测的两个单项矩形分别位于左、右两个入口，代码按实时矩形的横向顺序映射槽位。
- 后端任务生成的回归验证已覆盖稳定账号隔离：`wechat-id-qq673105954` 和 `wechat-id-gaoshiteng_01` 各生成一个 `c1001`/`act-001` 账号级任务，各含一个真实目标；定向测试 `10 passed`。
- 2026-09-10 11:17（手机本地时间）通过实际 `wechat_assistant` 工程的 `deploy_and_run` 调用发送模块进行正式尝试。官方 `esp32` 插件导入成功，但 `BleDevice()` 与连续 `re_connect()` 均报告“蓝牙设备连接失败”，最终日志为 `RuntimeError('官方 ESP32 HID 未连接')`；未出现 `HID_READY`、`BATCH_RUN_QUEUED` 或任何微信点击/发送日志，因此本次没有领取任务、没有更新实际群候选归属，也没有生成每目标发送结果。
- 本次正式尝试已调用 `stop_project`，并重新上传原始 `wechat_assistant/__init__.py`；设备工程根入口已恢复，运行态为停止。截图显示未进入微信转发页，故不能报告本轮发送成功。2026-09-08 的历史 HID 成功记录保持不变。
- 上述 11:17 的蓝牙阻塞已在 11:34 后解除，正式工程已多次记录 `HID_READY AS_4.8_905DDCBA2010`。两个槽位的微信号已核对；下一步仍只允许执行两个 `c1001` 目标，并同时取得原生“发送”后的页面证据及后端逐目标结果。

## 17. 2026-09-10 leo 单账号 c1001 正式测试结果

- 本轮按已确认范围只测试 `wechat-id-qq673105954 / leo`，PC 第 1 批返回 1 个账号级任务、2 个 `c1001` 目标：`互助群`、`测试群`；卡片为 `act-001`，附加文字为“今天天气有点冷”。账号、批次、卡片和目标映射均来自后端任务响应，未扩展其他群或账号。
- 通过正式 `wechat_assistant` 工程 `run_project` 执行，官方 ESP32 `AS_4.8_905DDCBA2010` 完成账号切换、微信号核验、置顶“卡片素材群”打开、`act-001` 定位、一次受控滚动、长按卡片、进入“转发”、进入原生“多选”和原生搜索框；正式运行未使用 `eval_python`。
- 原生多选页按 `c1001` 搜索时，同编号行只显示 `c1001`；清空同一搜索框后搜索“互助群”，mode=6 树能暴露 `昵称: 互助群`，但目标行子树只有头像 `ImageView` rect，未暴露左侧选择圈/CheckBox。此前尝试使用该头像 rect `(43,649,151,757)`，微信进入了“发送给：c1001(4人)”单群预览，随后因页面不是多选页而停止；最新正式任务 `automation_task_dc637ab32a` 的后端结果为 `failed`，错误为“选择群后未确认仍在微信原生多选页”，`targetResults=[]`。
- 根因是当前设备/微信构建在搜索结果页没有向 mode=6 控件树提供可执行的左侧选择控件。为遵守“控件树提供 rect、ESP32 HID 执行、不得固定坐标”的门禁，发送器已移除非可点击头像 `ImageView` 作为候选；找不到真实选择控件时会在选择前停止，不再误入单群预览。该最终安全门禁只做了本地 `py_compile` 和 `git diff --check`，未将未验证的安全停止写成运行成功。
- 本轮没有点击最终“发送”，没有发送任何目标群，后端没有目标发送结果；因此不能报告成功。截图现场为 13:59 左右的微信“选择聊天”页：搜索框为“互助群”，结果显示 `c1001` 和 `昵称: 互助群`，之后的“发送给：c1001(4人)”属于误触头像后的单群预览，不是成功发送证据。
- 测试已停止，设备 `wechat_assistant` 根入口已恢复为原始 `automation/ascript/__init__.py`，运行态为 stopped；发送器子模块保留最新安全门禁。2026-09-08 的历史 HID 成功记录保持不变，不被本轮失败改写。

## 18. 2026-09-10 方案 2 单群转发复测结果

- 用户确认正式采用方案 2：PC 端返回账号、群编号、真实群名、文字和卡片编号；微信端按真实群名逐个定位目标群，再进入原生单群转发预览。当前验收范围仍只包含 `wechat-id-qq673105954 / leo` 的第 1 批 `c1001` 两个目标“互助群”“测试群”，卡片 `act-001`，附加文字“今天天气有点冷”。
- 14:29 左右的正式运行任务 `automation_task_dc62750207` 已确认账号、批次、卡片和两个目标来自 PC；官方 ESP32 `AS_4.8_905DDCBA2010` 已连接，卡片素材群和 `act-001` 均已定位。由于 mode=6 树未暴露多选页左侧选择控件，脚本按安全门禁停止，后端状态为 `failed`，`targetResults=[]`，未点击最终发送。
- 14:35 左右的定向复测任务 `automation_task_1ae98b2477` 使用方案 2 的逐群路径：重新打开置顶卡片素材群、长按 `act-001`、进入微信原生转发/多选、搜索 `c1001` 后再搜索真实群名“互助群”。官方 HID 点击真实群名后，截图和实时 mode=6 树已经确认进入“发送给：c1001(4人)”原生单群预览，树中同时有卡片、文字输入框和底部 `发送` 按钮；但发送器的状态检查把标题错误限定在顶部 420px，因此误报为“未确认微信原生单群转发预览”并安全停止。后端该任务仍为 `failed`，`targetResults=[]`，没有点击最终发送，也没有产生目标发送结果。
- 已修正发送器状态检查：底部预览页的“发送给：”标题按实时屏幕位置放宽到 `y=700..1300`；仍只允许 mode=6 树提供发送按钮 rect，动作仍由官方 ESP32 HID 执行，OCR 只用于状态补充。修正已通过本地 `py_compile`、`git diff --check` 并上传到设备发送器子模块；本轮不再重复发送，故该修正尚未再次进行端到端发送验证。
- 本轮正式运行未使用 `eval_python`；设备最终已 `stop_project`，`wechat_assistant` 根入口已恢复原始 `__init__.py`，运行态为 stopped。2026-09-08 历史成功测试保持原样；本轮只能报告为“方案 2 路径已定位到原生预览、最终发送尚未验证”，不能报告发送成功。

## 19. 2026-09-10 方案 2 正式成功

- 用户确认继续测试后，使用修正后的实际 `wechat_assistant` 工程通过 `deploy_and_run` 正式运行；测试范围严格限定为 `wechat-id-qq673105954 / leo`、第 1 批、`c1001`、两个目标“互助群”“测试群”、卡片 `act-001` 和附加文字“今天天气有点冷”。未扩展其他账号或群，未使用 `eval_python`。
- 官方 ESP32 `AS_4.8_905DDCBA2010` 连接成功，运行模式为 HID。账号切换后通过“我”页核验为 `wechat-id-qq673105954 / leo`；置顶第一行“卡片素材群”打开成功；`act-001` 通过 marker 和卡片树矩形定位成功。
- 方案 2 的实际路径已跑通：每个目标分别重新打开素材卡片、长按卡片、进入微信原生转发和多选页，搜索 `c1001` 后清空同一搜索框并按 PC 返回的真实群名搜索；“互助群”和“测试群”均唯一定位，进入原生“发送给：c1001(4人)”预览，填写文字，使用 mode=6 控件树提供的实时发送按钮矩形，由 ESP32 HID 点击发送，并确认发送后的页面状态。
- 任务 `automation_task_c9b1b29440` 后端状态为 `success`，`sentCount=2`、`targetCount=2`、`uiVerified=true`、`cardForwarded=true`、`textIncluded=true`、`missingCount=0`；后端逐目标结果均为 `sent_ui_confirmed`：`互助群`、`测试群`。这次成功不改写此前失败记录，失败任务仍保留为失败。
- 成功日志关键节点为：`确认目标群单群转发预览 / 互助群`、`发送小程序卡片和文字`、`记录本次转发结果 / 互助群`；随后同样完成`测试群`，最终 `TASK_COMPLETED ... success`。测试结束后已停止运行，`wechat_assistant` 根入口恢复原始 `__init__.py`；设备端根文件长度核对为 14264，运行态为 stopped。

## 20. 2026-09-10 微信群台账全量扫描效率测试

- 本轮按用户要求只测试“扫描微信群 + 与 PC 台账同步”，不发送任何小程序卡片或文字；没有使用 `eval_python`，通过实际 `wechat_assistant` AScript 工程的临时调度入口调用现有 `wechat_group_inventory` 模块，扫描动作仍由控件树感知和官方 ESP32 HID 执行。
- 第一次全量运行约从 15:16:32 开始，ESP32 `AS_4.8_905DDCBA2010` 已 `HID_READY`；第一个槽位在进入双开微信后报 `微信“我”页未读到登录昵称`。当时工程仍处于运行态，未形成可核对的完整扫描结果，随后已停止。
- 仅做一次定向重试（约 15:24:25 开始）：日志在约 15:24:39 和 15:24:56 分别记录两个槽位的 `扫描失败`；未出现“通讯录群聊扫描完成”“微信会话列表群扫描完成”或 `/group-candidates/reconcile` 完成结果。重试期间截图显示微信停留在“群聊”页，页面可见 `9个群聊`，mode=6 实时树可读到 `g1005` 等群名，但扫描器在进入该阶段前的双开恢复/身份识别流程已失败，不能把这组页面可见数据当作完整扫描结果。
- 重试曾将一个错误识别的昵称 `+状态C` 写入设备心跳元数据；未将其作为账号事实保留。测试收尾已通过设备心跳恢复 `android-01` 为 `ready`，当前已知账号为 `wechat-id-qq673105954 / leo / qq673105954`。后台只读核对显示，现有 `wechat_native` 候选数量和最新更新时间未因本轮增加或刷新，设备的 `nativeGroupScans` 也没有新增本轮扫描记录；本轮没有数据库台账同步成功证据。
- 因两个槽位均未完成“身份确认 → 通讯录群聊全量扫描 → 会话列表扫描 → reconcile”的闭环，本轮不能回答“完整扫描是否几分钟完成”。目前可确认的只是：ESP32 连接正常，微信群聊页面在约几十秒内可到达；全量覆盖耗时、扫描数量、增量/新增数量和数据库写入耗时仍未测得。
- 测试结束后已停止 AScript 运行并恢复 `wechat_assistant` 正式根入口；设备运行态为 stopped，根文件长度为 14264。本轮不修改业务代码；后续若继续测试，首个阻塞应先修复为“从双开恢复的子页面可靠回到‘我’页并以微信号确认账号”，再重新测量全量扫描，不应先据此决定把扫描固定为群发前置步骤。

## 21. 2026-09-10 定向群台账同步实现与运行结果

- 根据当前决策，新增 `targeted` 扫描路径：进入双开微信后先通过“我”页读取唯一微信号；回到微信首页，搜索已配置编号前缀（当前为 `g10`），进入“群聊”结果的“更多群聊”，从 mode=6 控件树读取 `群聊名` 和 `g1001` 等编号，再以 partial 覆盖回传 `/group-candidates/reconcile`。定向扫描不进入通讯录“群聊”页，不扫描会话列表，不做人数检测，也不发送卡片或文字。
- 双开选择器逻辑保留：两个“微信”标签共用 GridView 时，实时树中分别取单项容器矩形计算槽位点击位置；所有页面动作仍由官方 ESP32 `AS_4.8_905DDCBA2010` HID 执行，树只提供实时 `rect`，定向列表没有 `scrollable` 矩形时不会使用固定坐标盲滑。
- 正式代码已同步到设备工程 `wechat_assistant`：根入口第一项改为“同步已配置群”，扫描接口允许 `scanMode=targeted`；后端 targeted 结果只做账号隔离的群名 upsert，不执行缺失删除，已有人工群编号和营销开关不被覆盖。已完成本地 `py_compile`、`git diff --check`，群台账 reconcile 测试 `10 passed`。
- 运行编号：2026-09-10 15:54 的 `deploy_and_run` 定向测试。首次调度因临时入口直接 `import wechat_group_inventory`，设备日志为 `ModuleNotFoundError`，未进入微信；随后仅做一次针对性重试，日志确认 `TARGET_SCAN_DISPATCH_START`、`HID_READY`、`ACCOUNT_IDENTITY`，之后在进入定向搜索前打印 `扫描失败`，没有出现 `TARGET_SEARCH_QUERY`、`TARGET_SEARCH_SCAN_DONE` 或 reconcile 完成日志。截图显示脚本结束后手机回到桌面。
- 本次没有定向群结果、没有数据库同步写入证据；后台只读核对显示本轮 `nativeGroupScans` 没有新增，现有候选数量未刷新。可确认的阻塞边界是“识别账号后到打开微信首页搜索之间”，当时旧日志的多参数 `print` 没有保留异常对象的详细文本，不能把未观察到的下一步错误补写成确定原因；已将失败日志改为单行包含槽位和异常的格式，留待下一次正式工程运行验证。
- 收尾状态：已执行 `stop_project`，恢复 `wechat_assistant` 正式根入口（设备根文件长度 14283），运行态为 stopped；设备心跳已恢复为 `ready`，当前稳定身份为 `wechat-id-qq673105954 / leo / qq673105954`。本轮未改变历史成功发送记录，也未把本轮失败报告为成功。

## 22. 2026-09-10 定向搜索群台账复测结果

- 本轮把用户确认的最短路径实际跑通到 `g10` 搜索结果：进入微信首页，使用控件树取得搜索按钮矩形，由官方 ESP32 HID 点击；使用控件树取得搜索输入矩形，由 HID 粘贴 `g10`；读取实时 mode=6 树中的“更多群聊”和群编号/群聊名。全程未发送卡片或文字。
- 正式运行时间约为 `16:30:47–16:31:11`，使用实际工程 `wechat_assistant` 的 `deploy_and_run` 临时调度现有模块，未使用 `eval_python`。ESP32 `AS_4.8_905DDCBA2010` 连接成功并记录 `HID_READY`。
- `wechat-id-qq673105954`（当前展示昵称 `leo`）成功读到 12 个群：`g1001` 3 个、`g1003` 1 个、`g1005` 6 个、`g1007` 2 个；从账号身份确认到 reconcile 完成约 16 秒。扫描结果为 `coverage=partial`、`stopReason=targeted_no_scroll_rect`，因为 mode=6 没有可用的滚动容器矩形，本次只记录当前 `g10` 搜索结果，不宣称完成全量微信群扫描。
- 同一运行中，`wechat-id-gaoshiteng_01` 在双开选择器阶段停止，准确日志为：`扫描失败 slot=wechat-instance-1 error=未找到双开微信选择器的两个微信入口`；因此本轮整体状态为 `degraded`，不能报告两个账号都已完成同步，也没有为该账号写入扫描结果。现场最终截图停留在另一个账号的微信 `g10` 群聊结果页。
- 线上原先因旧 schema 返回的 HTTP 422 已定位为生产容器未包含 `scanMode=targeted`。已按生产热修复清单备份 Compose、源码并保留 `teambuy-backend:rollback-20260910-1625` 标签；仅替换 API 镜像中的 `automation.py` 和 `automation_control_service.py`，未改 `.env`、secrets、数据库卷或媒体卷。线上 `/health`、`/health/db`、容器健康状态和容器内 targeted schema 均通过。
- 账号 `wechat-id-qq673105954` 的线上 reconcile 首次创建 12 条 `wechat_native` 群候选；随后用本次已明确读到的同一组群名将 OCR 噪声展示名 `?!` 更正为 `leo`，线上响应为 `createdCount=0`、`updatedCount=12`。当前数据库该账号共有 14 条 native 候选（包含既有“互助群”“测试群”），扫描元数据为 `seenCount=12`、`coverage=partial`；账号 `wechat-id-gaoshiteng_01` 本轮无新增台账结果。
- 为避免后续把 `?!` 等 OCR 噪声写入展示字段，昵称候选现在至少必须含中文、英文或数字；稳定账号边界仍只使用微信号。设备端最新模块已同步，正式根入口 `/storage/emulated/0/airscript/model/wechat_assistant/__init__.py` 已恢复，文件长度 14283，运行态为 stopped；心跳已恢复为 `ready`。
- 本轮没有打开素材群、没有定位 `act-001`、没有创建或执行发送任务；2026-09-08 及第 19 节的历史发送成功记录保持不变。

## 23. 2026-09-10 g10 群台账扫描规则补充与双微信复测

- 根据用户确认，定向群扫描的最短路径固定为：进入已核验的微信账号首页 → 用控件树取得首页搜索框矩形 → 由官方 ESP32 HID 点击并输入 `g10` → 忽略“最常使用/最近使用”区块 → 只处理“群聊”区块。
- “群聊”区块先读取当前实时 `mode=6` 控件树；若出现“更多群聊”，通过其实时控件矩形点击进入，再用实时列表矩形由 HID 向下滚动并持续重读控件树，不能把首屏 12 行当成全部结果；若结果已有群聊行但没有“更多群聊”，按用户确认视为正常结束，不因缺少该入口阻塞。没有可确认的实时列表矩形时停止，不使用固定坐标盲滑。
- 已将上述“最常使用/最近使用”过滤、无“更多群聊”的正常结束和可继续下滚动规则写入 `wechat_group_inventory`；本地 `py_compile`、`git diff --check` 和 `backend/tests/test_automation_group_reconcile.py` 均通过（10 passed）。
- 双微信复测使用真实 `wechat_assistant` 工程的 `run_project`，没有使用 `eval_python`，设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，官方 ESP32 为 `AS_4.8_905DDCBA2010`。测试只做 `g10` 扫描观察，不发送卡片或文字。
- 槽位 0（`wechat-id-gaoshiteng_01`，昵称“高同学”）在双开选择器阶段停止，准确日志为：`扫描失败 slot=wechat-instance-1 error=object of type 'NoneType' has no len()`。因此该账号没有形成本轮扫描完成或数据库同步结果。
- 槽位 1（`wechat-id-qq673105954`，昵称“leo”）完成微信号身份确认并进入 `g10` 群聊结果页；一次实时 `mode=6` 树读到 `ListView id=mfg rect=[0,229,1080,2400]`，当前深层页面可见 13 条“群聊名”行，页面已不显示“更多群聊”。本轮日志未出现扫描完成或 reconcile 完成标志，不能据此宣称已经读完该账号全部群或已同步数据库。
- 本轮收尾时已停止 AScript 运行并恢复 `wechat_assistant` 正式根入口；设备运行态为 stopped，根入口文件长度 14283，扫描模块已同步到设备。未打开卡片素材群、未定位 `act-001`、未创建发送任务；第 19 节历史发送成功记录保持不变。
- 当前真实阻塞是槽位 0 的 `NoneType` 长度错误，以及槽位 1 缺少完整结束日志；下一次应先定位该错误并补齐扫描完成/reconcile 证据，再测量两账号的完整数量和耗时，不能把本轮现场数据报告为完整同步成功。

## 24. 2026-09-10 修复后双微信 g10 扫描重跑

- 已修复第 23 节暴露的最小代码错误：可选“更多群聊”等待超时返回 `None` 时，分支不再调用 `len(None)`。本地 `py_compile`、`git diff --check` 和群台账 reconcile 回归测试均通过，测试为 `10 passed`；修复后的扫描模块已上传 `wechat_assistant` 设备工程。
- 修复后通过实际 `wechat_assistant` 工程 `run_project` 重跑，仍为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，官方 ESP32 `AS_4.8_905DDCBA2010`，未使用 `eval_python`，本轮仍只扫描 `g10`，不发送卡片或文字。
- `wechat-id-gaoshiteng_01`（“高同学”）日志：`2026-09-10 17:21:40 扫描失败 slot=wechat-instance-1 error=微信搜索框未出现`。该账号已进入对应流程，但没有读到可由控件树确认的搜索框矩形，因此没有点击或盲输，也没有形成扫描结果。
- `wechat-id-qq673105954`（“leo”）日志：`17:21:46 ACCOUNT_IDENTITY`、`17:21:47 TARGET_CHAT_HOME_READY`、`17:21:49 TARGET_SEARCH_QUERY prefix=g10`、`17:22:06 TARGET_SEARCH_SCAN_DONE prefix=g10 rows=38 scrolls=4 stopReason=targeted_bottom_stable`。这证明“更多群聊”路径、实时 `ListView` 矩形下滚和到底稳定判断已跑通；现场截图/树仍显示真实 `g10` 群聊名结果。
- 本次重跑没有拿到后端 reconcile 返回及最终工程结果日志；因此只能确认 leo 的 38 条 `g10` 扫描结果已在手机端读到，不能报告两个账号都完成扫描，也不能确认本轮 PC 数据库已成功更新。没有发送任何卡片或文字。
- 发现高同学阻塞后，按规则停止运行并恢复 `wechat_assistant` 正式根入口；最终设备运行态为 stopped。历史成功发送记录不变，当前失败和未完成的数据库核验不改写成成功。

## 25. 2026-09-10 扫描、PC 映射与 c1001 任务准备闭环

- 本轮按用户确认的最小范围执行：两个微信只搜索 `g10`，只读取“群聊”区块；不进入卡片素材群，不领取发送任务，不打开微信转发页，不发送文字或小程序卡片。正式执行使用 `wechat_assistant` 工程 `deploy_and_run`，没有使用 `eval_python`。
- 设备为 nubia NX711J / NX711J / Android 15 / AScript 4.0.12 / HID，官方 ESP32 `AS_4.8_905DDCBA2010` 已在日志中 `HID_READY`。扫描动作的点击、输入和下滑均由官方 ESP32 HID 执行，mode=6 控件树只提供实时控件矩形；双开选择器仍按共用 GridView 下的两个单项矩形计算槽位。
- 18:37:22–18:38:23 的最终准备运行完成两个槽位：`wechat-id-gaoshiteng_01`（高同学对应账号，当前树未返回昵称文本）搜索得到 8 行、下滑 2 次、`targeted_bottom_stable`；`wechat-id-qq673105954`（leo）搜索得到 38 行、下滑 4 次、`targeted_bottom_stable`。两者都通过微信号完成身份边界确认，未用昵称生成账号 ID。
- 两个账号的 `groupCode + groupName` 已回传线上 `/group-candidates/reconcile`：高同学 `mappedCount=8`，leo `mappedCount=38`，均为 partial 台账更新，不执行缺失删除。线上只读核对显示高同学当前 8 条 native 候选没有 `c1001`；leo 当前有 2 个 `c1001` 目标：`互助群`、`测试群`。不能把不存在于高同学本轮扫描结果的 `c1001` 任务虚报给该账号。
- PC 已按第 1 批、`c1001` 创建 1 个账号级待执行任务 `automation_task_09750d3a18`，目标账号为 `wechat-id-qq673105954`，包含 2 个目标“互助群”“测试群”；任务状态为 `pending`，本轮没有领取、完成或发送，所以没有发送结果记录。
- 后端本轮新增 `groupMappings` 入参和服务器端完成通知接口；已部署生产容器，备份目录为 `/home/ubuntu/teambuy-backups/20260910-182658-group-scan-preflight`，三个服务均重新创建并 healthy，内网/公网 `/health`、`/health/db` 和容器内 schema/路由检查通过。未修改 `.env`、secrets、数据库卷或媒体卷。
- 完成通知已回传服务器，返回 `configured=false / sent=false / automation_completion_email_disabled`。服务器收件人已是 `250667571@qq.com`，但当前未启用 SMTP，也没有配置 SMTP 主机/账号；因此不能报告邮件已发送。后续只需由服务器运维配置 `AUTOMATION_COMPLETION_EMAIL_ENABLED` 及 SMTP 参数，不把密码写入代码、日志或文档。
- 运行结束后已停止 AScript；正式根入口已恢复，设备端 `wechat_assistant/__init__.py` 长度 14996，扫描模块已同步最新版本，设备运行态为 stopped。第 19 节历史方案 2 发送成功和本轮此前失败记录均保持原样。

## 26. 2026-09-10 扫描前置 + c1001 群发闭环与通知部署

- 已将定向 `g10` 群扫描接入“群发微信”入口：进入每个双开微信后先由 mode=6 控件树感知首页搜索、`g10`、`更多群聊` 和列表矩形，所有点击、输入、下滑、返回和发送继续由官方 ESP32 `AS_4.8_905DDCBA2010` HID 执行；扫描完成后才请求 PC 按账号、群编号和批次创建发送任务。
- 2026-09-10 19:07 左右通过实际 `wechat_assistant` 工程 `deploy_and_run` 完成组合运行。高同学账号 `wechat-id-gaoshiteng_01` 扫描得到 8 行、下滑 2 次；leo 账号 `wechat-id-qq673105954` 扫描得到 38 行、下滑 4 次；两账号均以微信号隔离，未使用昵称生成 ID。扫描回传均为 partial reconcile，不删除历史残留，人工 `canSend` 等配置不被扫描覆盖。
- PC 第 1 批只创建 1 个 leo 账号级任务 `automation_task_a250fe48f5`，群编号为 `c1001`，目标为“互助群”“测试群”，卡片 `act-001`，文字“今天天气有点冷”。这是本轮用户指定的 leo 范围；高同学本轮没有 c1001 目标，未虚构高同学任务。任务于 19:09 左右完成，后端状态 `success`。
- 该任务的后端结果确认两个目标均为 `sent_ui_confirmed`，`sentCount=2`、`targetCount=2`、`uiVerified=true`、`cardForwarded=true`、`textIncluded=true`、`missingCount=0`；步骤记录包含 act-001 定位、长按、原生转发、多选、按真实群名搜索、单群预览、输入文字和发送后的结果记录。历史失败任务仍保留为失败，没有被改写。
- 服务器完成通知已补齐 `forwardSummary` schema，确保邮件正文能收到转发耗时、成功/失败数和逐目标结果；`0` 计数也不会再被格式化为空。服务器已复用 `project-monitor` 现有 SMTP 配置，teamBuy 的服务器环境启用收件人 `250667571@qq.com`；使用本次实际运行汇总回放验证，`/api/automation/runs/complete` 返回 `configured=true / sent=true`。这证明 SMTP 已被服务器接受，不等同于邮箱客户端已读回执。
- 本次设备运行的扫描秒数没有写入任务表，回放邮件没有伪造分账号扫描耗时；AScript 代码已经在运行报告中记录每个账号的 `scanDurationSeconds` 和总 `scanSummary.durationSeconds`，下一次正常完成回调会直接带出这些值。设备原始完成回调发生在 SMTP 接入前，曾返回未发送；配置完成后的回放才是本次实际 SMTP 验证。
- 通知代码和完成报告 schema 已按生产热修复流程部署；备份目录为 `/home/ubuntu/teambuy-backups/20260910-1925-automation-email-fields`，新镜像为 `teambuy-backend:automation-email-20260910-1925-automation-email-fields`，源码哈希已与容器内文件核对一致。backend、backend-worker、archive-worker、PostgreSQL 均 healthy，内网 `/health`、`/health/db` 和公网 `/health` 均通过；未修改数据库卷、媒体卷或服务器敏感配置以外的本地仓库文件。
- 组合运行后已停止设备工程并恢复正式 `wechat_assistant` 根入口；设备 runtime 为 stopped，设备端根入口长度 15584，sender 的本地敏感配置仍保留在设备端，未写入仓库或文档。未发现可安全删除的额外旧代码：`scan_all_groups`/`scan_new_groups` 仍是兼容入口，`wechat_account_identity` 仍被身份核验链路使用；不因“清理”删除它们。此前已有的 `xhs_find_group` 删除保持原状。
- 当前仍不可直接宣称“无人值守生产群发已开放”：发送器默认 dry-run，设备当前测试配置仍受 `TEST_ONLY` 保护；本轮证明的是扫描前置、PC 映射、一次受控 c1001 UI 群发和服务器通知闭环。生产发送若要开放，仍需另行确定白名单、审计、限额和回滚策略。

## 27. 2026-09-10 AScript 入口精简与 Android 回归阻塞

- 按用户确认，AScript 统一入口只保留“群发微信”一项，并将前置 `g10` 群台账扫描与卡片转发合并；已移除独立“全部微信群”“每日新增群”、设备状态和任务日志占位入口，以及入口文件中对应的死代码和重复内嵌 HTML。`wechat_group_inventory`、`wechat_account_identity`、`wechat_marketing_sender` 和必要的历史测试证据继续保留。
- `automation/ascript/xhs_find_group/__init__.py` 的既有删除状态未改写；没有批量删除未知 AScript 工程、历史证据或设备端敏感配置。
- 本地检查通过：四个 AScript Python 文件 `py_compile`、启动器内嵌 JavaScript `node --check`、`git diff --check`。本轮没有修改微信正式小程序 `miniprogram/` 和后端业务模块。
- Android 最小回归尚未能启动：AScript 工具连接 `192.168.1.237:9096` 返回“无法访问 AirScript 服务”，局域网扫描未发现设备；本机也没有 `adb` 命令。因此没有上传本轮入口、没有运行发送任务、没有触碰微信页面，手机端仍保持上一次已停止的正式入口。
- 下一步恢复 Android 设备 AirScript 服务后，只需通过真实 `wechat_assistant` 工程 `deploy_and_run` 做一次入口加载/前置扫描链路回归；本轮不调试鸿蒙，不使用 `eval_python`。

## 28. 2026-09-10 Android AScript 工程清理与入口回归

- 已通过设备工程管理接口逐个删除四个明确的临时/旧工程：`chooser_select_test`、编码异常的 `%E5%BE%AE%E4%BF%A1%E5%8A%A9%E6%89%8B`、旧 `微信助手` 和 `hid-test`。没有删除正式 `wechat_assistant`、回退工程 `资料整理助手` 或历史 HID 证据 `hid_e2e_20260908`。
- 设备最终工程清单只剩：`wechat_assistant`、`资料整理助手`、`hid_e2e_20260908`。本轮删除前确认没有脚本运行；完成入口回归后再次确认 `is_script_running=false`。
- 本地精简后的 `automation/ascript/__init__.py` 和 `res/ui/launcher.html` 已上传到 `wechat_assistant`，通过真实 `run_project` 加载。Android 15 / nubia NX711J / AScript 4.0.12 / HID 现场显示原生兜底菜单只有“群发微信（扫描前置）”一个入口，证明旧功能入口已不再暴露。
- 本轮只做入口加载和列表核验，没有点击群发入口，没有扫描微信群，没有领取任务，没有打开微信转发页，没有发送卡片或文字；没有使用 `eval_python`，没有新增或修改后端任务结果。
- 本地 `py_compile`、启动器 JavaScript `node --check` 和 `git diff --check` 通过。鸿蒙控件树和 HID 能力调试按计划留到下一轮。

## 29. 2026-09-10 Android 最小入口回归

- 通过实际 `wechat_assistant` 工程 `run_project` 启动 Android 15 / nubia NX711J / AScript 4.0.12 / HID；设备端工程清单仍为 `wechat_assistant`、`资料整理助手` 和 `hid_e2e_20260908`。
- 入口在 WebWindow 15 秒未收到功能卡片回调后，进入原生兜底菜单；现场唯一功能项为“群发微信（扫描前置）”。这不是只有扫描功能，而是统一群发入口的展示名称。
- 设备端 `wechat_assistant` 文件清单确认包含 `wechat_group_inventory/__init__.py`、`wechat_marketing_sender/__init__.py` 和 `wechat_account_identity/__init__.py`；发送器并未缺失或只存在于本地。
- 本次未触发该功能项，因此没有进入第 1 批选择框，没有扫描 `g10`、更新 PC 映射、创建任务或发送卡片/文字。运行日志为：`九宫格 15 秒未收到点击回调，切换原生菜单`。
- 21:06 进行了一次立即抓屏的针对性重试，`run_project` 返回成功且设备仍为 HID，但屏幕仍停留在 AScript 本地工程列表，随后主动停止；因此没有把“批次选择框已出现”误报为已验证。
- 运行已停止，设备最终为 stopped；本次没有使用 `eval_python`，没有修改历史发送结果。下一次正式回归应验证点击该唯一入口后出现“第 1 批～第 10 批”选择框，再继续扫描前置和发送器接管验证。

## 30. 2026-09-10 Android 验收路径现场结论

- 按验收要求再次通过实际 `wechat_assistant` 工程 `run_project` 启动，目标仍为 Android 15 / nubia NX711J / HID；设备端文件清单已确认包含群扫描、账号身份和 `wechat_marketing_sender` 三个模块。
- 本轮只完成了入口加载现场核对，未触发“群发微信”功能项，因此未进入批次选择、`g10` 扫描、PC 映射或任务创建；没有领取任务，也没有发送卡片或文字。
- 当前 AScript 本地工具没有单独的官方 ESP32 HID 点按调用；本轮禁止用 `eval_python` 代替正式工程操作，因此不能把未触发入口后的链路报告为已验收。
- 运行已停止，设备状态恢复为 stopped，正式入口未留下临时调试入口，历史成功和失败记录均未改写。

## 31. 2026-09-10 Android 3×3 入口实现与最小路径验收

- 按当前决策恢复 `wechat_assistant` 的 3×3 展示壳，但只启用 1 号“群发微信”卡位；2–9 号为禁用的后续扩展占位，不恢复已清理的旧功能入口。占位方向包括鸿蒙适配、iOS 适配、群台账工具、批次管理、发送记录和设备诊断。
- 本地已通过四个 AScript Python 文件 `py_compile`、启动器内嵌 JavaScript `node --check` 和 `git diff --check`；页面实际包含 9 个卡位，只有 1 个 `send_batches` 回调。根入口标题统一为“群发微信”，前置扫描说明保留在副标题和功能流程中。
- 新版 `automation/ascript/__init__.py`（9,155 bytes）和 `res/ui/launcher.html`（5,024 bytes）已上传到 Android 设备 `192.168.1.237` 的正式工程 `wechat_assistant`；设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，官方 ESP32 仍为 `AS_4.8_905DDCBA2010`。
- 通过实际 `run_project({name: "wechat_assistant"})` 启动并截图确认 3×3 页面可显示。因本地 AScript 工具没有独立的官方 HID 点按调用，本轮未使用 `eval_python`，无法代替用户点击 1 号卡位；等待入口回调超时后进入原生“群发微信”菜单，日志为 `九宫格 15 秒未收到点击回调，切换原生菜单`。随后已执行 `stop_project`，停止日志为 `2026-09-10 21:35:57:320 小程序已停止`。
- 因未触发 1 号功能，本轮没有进入批次选择，没有执行两个微信账号的 `g10` 扫描、PC 群映射更新或任务创建，也没有进入素材群、定位 `act-001` 或发送任何卡片/文字。不能把本轮报告为 Android 最小路径完整验收通过；第 19、26 节历史成功记录保持不变。
- 当前剩余阻塞边界明确为：需要在 AScript 官方工程操作链中提供真实 HID 点按入口，或由用户在 3×3 页面点击 1 号卡位；在此之前不得用猜测坐标、`eval_python` 或临时调试入口代替正式验收。设备最终运行态为 stopped，正式根入口已保留，未留下临时调试入口。

## 32. 2026-09-10 正式工程 HID 入口桥接验证

- 为解决统一 3×3 入口无法由正式 AScript 工具触发的问题，已在 `wechat_assistant` 根入口加入短轮询 HID 桥：MCP 只提交当前实时 `mode=6` 控件树解析出的 `rect`，设备端工程计算中心点后调用官方 ESP32 `BleDevice.click()`；桥接层不接受裸 `x/y`，不使用固定坐标，也不使用 `eval_python`。
- 已在本机 AScript MCP 的当前安装包中注册 `hid_click` 一等工具，支持语义控件条件、`mode=6`、唯一性校验和必要的精确 OCR 补充；重复文本只有显式指定 `occurrence` 才会选择。代码已通过 MCP 模块 `py_compile`，设备工程代码也通过 `py_compile` 和 `git diff --check`。
- 使用同一台 Android 15 / nubia NX711J / AScript 4.0.12 / HID 设备和官方 ESP32 `AS_4.8_905DDCBA2010` 做了实际验证：实时 OCR 取得入口和原生菜单矩形，HID 依次触发“群发微信”“打开”“第1批”“开始执行”。这些是设备动作和入口路径证据，不等于扫描、PC 同步或发送成功。
- 启动前置扫描后，约 15 秒时脚本仍在运行，但没有可读的扫描完成、reconcile 或任务结果日志；现场截图 `/tmp/teamBuy-scan-current.jpg` 显示已回到正式“微信助手”菜单。为避免在无法确认页面状态时继续操作，已停止工程，最终 runtime 为 stopped，未继续发送卡片或文字，也未改写历史任务结果。
- 当前 Codex 会话原先的 `ascript-local` 连接器进程在重载后没有被宿主自动拉起，工具调用返回 `Transport closed`。本轮设备验证使用的是同一安装包中的底层 AScript MCP 模块直连设备，因此不能把“连接器已重连”写成完成事实；下一次需要宿主重新加载该连接器后，才能在正常工具命名空间直接使用 `hid_click`。

## 33. 2026-09-10 连接器未恢复时的 Android 正式入口实测

- 用户手动点击了 `wechat_assistant` 3×3 页面的一号“群发微信”入口；设备确认已进入批次选择页。由于 OCR 对“第1批”同时返回标题和列表行，第一次按返回顺序点击到了标题；截图核对后使用实时列表行矩形重新点击，确认列表行变为蓝色选中，未盲目继续。
- 随后通过运行中的正式 `wechat_assistant` 工程桥接点击实时识别的“开始执行”，动作仍由官方 ESP32 `AS_4.8_905DDCBA2010` 的 `BleDevice` 完成，未使用 `eval_python`。日志确认高同学账号 `wechat-id-gaoshiteng_01` 的 `g10` 定向扫描完成：`rows=8`、`scrolls=2`、`stopReason=targeted_bottom_stable`；之后日志确认流程核验到 leo `wechat-id-qq673105954`，并请求 `act-001`、打开置顶“卡片素材群”、定位到 `act-001` 卡片。
- 本次日志在素材卡片定位后的后续阶段没有形成可读的原生转发完成、最终发送或逐目标回写证据；最终截图 `/tmp/teamBuy-forwarding-current.jpg` 显示素材群背景上的“微信助手”菜单，未显示“发送”后的聊天确认。使用设备令牌读取运营任务列表返回 HTTP 403，不能据此确认后端任务状态或推断发送成功。
- 按“页面状态无法确认立即停止”规则，本次已停止工程，设备 runtime 为 stopped；没有继续点击发送、没有新增发送成功结论，也没有改写历史成功/失败记录。当前只能确认入口、批次选择、前置扫描一段和 `act-001` 定位，不能把本次报告为完整 Android 群发验收通过。
- `ascript-local` 正常工具命名空间仍返回 `Transport closed`；本轮继续使用同一已修改的 AScript MCP 底层模块直连设备验证，不能把连接器重载写成完成事实。

## 34. 2026-09-10 c1001 前置扫描复测阻塞

- 用户确认 `c1001` 为测试范围后，重新通过正式 `wechat_assistant` 工程启动 Android 15 / nubia NX711J / AScript 4.0.12 / HID 测试；只选择第 1 批和 PC 当前 c1001 配置，未扩展其他群，也未使用 `eval_python`。
- 用户手动点击一号“群发微信”入口；随后由正式工程 HID 桥根据实时 mode=6/OCR 矩形完成“打开”、选择第 1 批和“开始执行”。第一次 OCR 命中批次标题而非列表行，已通过截图识别并改用实时列表行矩形，确认第 1 批蓝色选中。
- 本次前置扫描在第二个双开槽位停止，界面明确显示：`微信群前置扫描未完成：[{"slot":"wechat-instance-2","error":"微信“我”页未读到唯一微信号","scanDurationSeconds":24.538}]`。因此未创建可确认的本次发送任务，未进入 act-001 转发，也未点击最终发送。
- 现场截图为 `/tmp/teamBuy-c1001-running.jpg`；截图显示错误提示弹窗，后台任务列表使用设备令牌只读查询返回 HTTP 403，无法核对运营任务状态，不能把本次报告为成功。工程已停止，最终 runtime 为 stopped。
- 当前最小根因仍是第二个双开槽位无法在微信“我”页读到唯一微信号；下一次应只修复/验证该账号身份回到“我”页的读取，不应绕过唯一微信号门禁或继续发送。历史成功与失败记录保持不变。

## 35. 2026-09-10 发送后回微信首页状态边界修复

- 根据本轮根因确认，发送器增加统一“回微信首页（会话列表）”边界：切换账号后、身份核验后、每个已确认目标发送后、账号任务完成后，以及切换下一个账号前，均通过官方 HID 返回并用 mode=6 控件树确认会话列表；卡片素材群、原生转发页、搜索结果不得作为下一个任务起点。
- 任务出现不确定或异常页面时立即停止，外层队列不再在失败后继续切换到另一个微信账号；已确认发送结果在停止报告中保留，不把 UI 未确认写成成功。
- 本地 `py_compile`、`git diff --check` 和 `backend/tests/test_automation_group_reconcile.py` 均通过（11 passed）。发送器已上传 `wechat_assistant` 正式设备工程。
- 本轮 Android 实测没有形成新的发送闭环：3×3 WebWindow 点击未触发回调并自动降级原生菜单；批次页高层 OCR 曾把“返回九宫格/开始执行”合并，后续已用实时 OCR 得到独立“开始执行”矩形并交给正式工程 HID 桥，但没有出现 sender 的可读运行日志或微信页面。因此未确认扫描、PC 任务、act-001、最终发送或后端逐目标结果，未发送卡片或文字。
- 最后已停止工程并恢复 `wechat_assistant` 正式根入口。本轮未使用 `eval_python`，未修改鸿蒙路径；历史成功和失败记录保持不变。

## 36. 2026-09-11 正式入口自动点击与微信内状态停止

- 已确认不需要用户人工点击入口：`WebWindow` 改用官方命名事件处理器，并切换到 `mode(-1)` 主页面模式；Android 15 下通过实时 mode=6 控件树识别 3×3“群发微信”矩形，再由正式工程 HID 桥和官方 ESP32 `AS_4.8_905DDCBA2010` 自动点击。此前 `mode(0)` 的可见页面会丢失点击回调，已不再作为入口模式。
- 本轮通过正式 `wechat_assistant` 工程自动完成入口点击、打开群发、选择第 1 批和“开始执行”，随后进入微信并完成 `g10` 搜索、群列表扫描和置顶“卡片素材群”定位；微信内继续按实时控件树取矩形、官方 ESP32 HID 执行。
- 微信随后出现“已发送”提示，但界面仍停留在“卡片素材群”，没有同时确认目标群标题、原生转发完成页、发送后目标聊天页面或后端逐目标结果。因此本轮不登记 c1001 发送成功，不更新历史任务结果，也不继续点击。
- 工程已停止，设备 runtime 为 stopped；正式根入口保留。本轮未使用 `eval_python`，未调试鸿蒙，未留下临时入口。入口文件本地 `py_compile` 和 `git diff --check` 通过。

## 37. 2026-09-11 g10 前置后卡片素材群确认阻塞

- 本轮使用实际 `wechat_assistant` 工程 `run_project` 自动启动，完成统一入口 HID 点击、批次第 1 批选择，并进入微信 `g10` 搜索页；设备仍为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，官方 ESP32 为 `AS_4.8_905DDCBA2010`，没有使用 `eval_python`。
- 服务器只读日志确认两个账号的群台账 reconcile 请求均返回 200；随后为 leo（`wechat-id-qq673105954`）创建了本次 `c1001`、`act-001`、附加文字“今天天气有点冷”的账号级任务，目标仍是“互助群”“测试群”。任务 `automation_task_5a59150f44` 于 01:35:45 领取，01:36:13 失败，准确错误为 `聊天列表第一行未确认是卡片素材群`；`ambiguous=true`、`targetResults=[]`，未点击最终发送，不能报告本轮发送成功。
- 最小根因是前置 `g10` 搜索结果页可能残留底部 Tab 和搜索按钮，旧首页判定未优先排除搜索输入框，导致素材群首行确认阶段拿不到真实会话列表。已在本地发送器的 `_is_wechat_chat_list()` 增加搜索输入框门禁：仍有搜索框时一律返回微信会话列表，不把搜索结果当作发送起点。
- 本地发送器通过 `py_compile` 和 `git diff --check`；但本轮收尾后设备连接中断，上传修复返回 `No route to host`，重新连接与局域网扫描均未发现 `192.168.1.237:9096` 的 AirScript 服务。因此修复尚未同步到手机，也没有进行第二次发送尝试。
- 设备工程已停止，正式 `wechat_assistant` 根入口保留；历史发送成功和失败记录不改写。设备恢复在线后，下一步只需重新上传该单文件修复并再执行一次受控 c1001 回归，确认先回真实会话列表、再定位“卡片素材群”，不扩展其他群编号。

## 38. 2026-09-11 修复后双账号 c1001 回归现场停止

- 本轮按用户限定只做一件事：使用已修复的“控件树优先素材群”路径，通过实际 `wechat_assistant` 工程 `run_project` 对两个双开微信执行一次第 1 批、`g10`/`c1001` 受控流程；卡片为 `act-001`，未使用 `eval_python`，微信内动作仍由官方 ESP32 HID `AS_4.8_905DDCBA2010` 完成，控件树只提供实时矩形。
- 已重新连接 Android 15 / nubia NX711J / AScript 4.0.12 / HID 设备 `192.168.1.237:9096`，将本地发送器修复上传到正式工程 `wechat_assistant`。修复内容是：检测到实时搜索输入框时，不把 `g10` 搜索结果页误判为微信会话列表，从而在发送起点先返回真实会话列表；没有新增临时工程或入口。
- 第 1 批列表行和“开始执行”均取自当时 `mode=3` 的实时控件树矩形，再提交给正式工程 HID 桥完成点击。开始后设备日志只记录到 `2026-09-11 02:04:59 TARGET_SEARCH_QUERY prefix=g10`，没有形成两个账号身份、扫描完成、PC 同步、任务创建或发送结果的本轮可读证据。
- 随后现场截图显示设备落在普通微信群“群起个啥名呢？”聊天页并展开表情面板，不是允许的 `c1001` 转发流程。按“遇到问题立即结束”要求立即停止，未继续点击、未猜测页面、未点击最终发送。后台只读核对未发现本次新的任务记录；最近可见任务仍是历史 `automation_task_5a59150f44`（leo，失败于旧的素材群首行确认），不能把它归入本轮。
- 本轮结论：两个账号均未完成本次完整流程，`c1001`/`act-001` 本轮没有新的发送成功记录；历史成功记录和历史失败记录均保持不变。设备在 02:05 左右停止，`is_script_running=false`，Wi‑Fi 仍在线，正式 `wechat_assistant` 根入口保留。

## 39. 2026-09-11 首页复位与两次有限重试回归

- 按用户确认的容错规则，本轮对正式 `wechat_assistant` 执行 1 次初始尝试 + 2 次有限重试；每次前置扫描尝试都由工程通过官方 ESP32 HID 复位到微信首页后再进入双开微信。范围仍严格限定为两个 Android 微信账号、第 1 批、`c1001` 和 `act-001`，未使用 `eval_python`，未执行任何最终发送。
- 正式工程已通过真实 `run_project` 启动；3×3 页面上的“群发微信”、第 1 批和“开始执行”均由实时控件树/OCR 提供矩形，再交给正式 HID 桥调用官方 ESP32 `AS_4.8_905DDCBA2010`，没有固定坐标盲点。第 1 批列表行被确认选中后才继续。
- 第 1 次前置扫描失败：`wechat-instance-1` 报 `微信“我”页未读到唯一微信号`，`wechat-instance-2` 报 `微信首页未出现“我”入口`；扫描耗时 `52.317s`。工程随后打印 `PREFLIGHT_RETRY attempt=2` 并复位。
- 第 2 次前置扫描仍失败，错误相同；随后按规则进入最后第 3 次尝试。第 3 次仍失败：`wechat-instance-1` 报 `微信“我”页未读到唯一微信号`（`25.212s`），`wechat-instance-2` 报 `微信首页未出现“我”入口`（`27.821s`），该次扫描总耗时 `53.038s`。达到重试上限后未进入发送器、未创建本轮账号任务。
- 本轮后端只读任务核对未发现新的任务记录；最新可见仍为历史 `automation_task_5a59150f44`（leo，历史失败，`targetResults=[]`），不能归入本轮。历史 `automation_task_d935a7fb71` 等成功记录保持成功，不改写为失败或成功。
- 工程已在第 3 次失败后立即 `stop_project`；02:41 现场截图仍显示微信 `g10` 搜索结果列表，未继续点击。设备运行已停止，正式 `wechat_assistant` 根入口保留。当前阻塞点仅为本轮双开微信无法稳定从首页进入并读到两个账号身份；不是素材群、`act-001`、原生转发页或发送动作的失败。

## 40. 2026-09-11 AScript 网络影响静态排查

- 已检查 `automation/ascript/` 及相关工程代码，没有发现 Wi‑Fi/WLAN 开关、网络重置、飞行模式、重启、关机或系统 shell 调用。根入口仅调用 `Device.wake_up()`、`Device.keep_screen_on()`，并加载官方 ESP32 `BleDevice` HID 桥；扫描器和发送器只通过 HID 操作微信、剪贴板和控件树。
- 代码中唯一的网络相关行为是向 PC 后端发起 `urllib.request.urlopen(..., timeout=8)` 请求；网络断开时会表现为请求失败或超时，不会主动关闭 Wi‑Fi 或重启手机。`plug.load("esp32")` 属于蓝牙 HID 加载，不是 Wi‑Fi 控制。
- 因此目前没有代码证据证明 `wechat_assistant` 主动影响 Wi‑Fi。手机重启后 AirScript 服务不可访问，更符合设备重启后的服务/地址/局域网状态问题；在没有重启时刻的系统日志前，不能进一步认定具体硬件或系统原因。本次未修改代码、未启动工程、未操作微信。

## 41. 2026-09-11 双账号完整链路复测的前置门禁停止

- 手机恢复连接后，本轮通过真实 `run_project({name: "wechat_assistant"})` 启动 Android 15 / nubia NX711J / AScript 4.0.12 / HID 工程；通过实时 mode=6/OCR 矩形点击 3×3 的“群发微信”，再用实时 mode=3 控件树矩形选择“第1批”和“开始执行”。所有设备动作仍由官方 ESP32 `AS_4.8_905DDCBA2010` HID 完成，未使用 `eval_python`。
- 前置扫描阶段曾形成两条可确认的数据库同步结果：高同学 `wechat-id-gaoshiteng_01` 扫描 `g10` 得到 8 个群并回写 `updated=8`；leo `wechat-id-qq673105954` 扫描得到 38 个群并回写 `updated=38`。这些是扫描/映射结果，不是群发成功结果。
- 但同一轮前置扫描的最终聚合出现双开入口状态异常：重试前报 `wechat-instance-1: 微信首页未出现“我”入口`；之后执行第 2、3 次尝试。第 3 次两个槽位均报 `微信首页未出现“我”入口`，单次总耗时 `55.600s`，达到“初始 + 2 次重试”上限。
- 因前置扫描最终状态为 `failed`，没有进入发送器，没有创建本轮账号级发送任务，没有定位 `act-001`，没有进入原生转发页，也没有发送文字或卡片。服务器任务列表最新仍为历史 `automation_task_5a59150f44`，本轮没有新增任务；历史成功与失败记录保持不变。
- 10:45 现场截图显示 g10 搜索结果页上的“群发微信执行失败”提示，错误内容为两个槽位均未出现“我”入口。随后已执行 `stop_project`，设备 `is_script_running=false`，Wi‑Fi 仍为 `192.168.1.237`。本轮结论是双开微信首页/入口状态门禁阻塞，不是 Wi‑Fi 断开，也不是素材群或转发动作失败。

## 42. 2026-09-11 搜索页复位修复后的双账号完整链路复测

- 已在 `wechat_group_inventory` 和 `wechat_marketing_sender` 增加用户确认的搜索页复位路径：从实时控件树取得“取消”矩形并由官方 ESP32 HID 点击；再取得搜索框 X 的实时矩形并由 HID 点击；最后根据实时搜索结果列表矩形执行向右滑动回微信首页。没有加入固定坐标兜底。两个模块已上传正式 `wechat_assistant` 工程。
- 本轮通过真实工程 `run_project` 启动并由实时 mode=6/mode=3 矩形完成 3×3“群发微信”、第 1 批和“开始执行”，设备仍为 Android 15 / AScript 4.0.12 / HID，官方 ESP32 为 `AS_4.8_905DDCBA2010`；未使用 `eval_python`。执行过程中保持 Wi‑Fi 在线，最终已 `stop_project`。
- 完整链路实际进入了微信，但三次前置扫描都记录 `wechat-instance-1`、`wechat-instance-2` 的 `微信首页未出现“我”入口`，最终错误弹窗也在微信会话首页显示。停止后立即复核截图：页面为真正的微信会话首页，底部存在“微信/我”，顶部存在“微信(7268)”和置顶“卡片素材群”；随后 mode=3 和 mode=6 均重新读到“我”及其有效实时矩形。
- 因此本轮失败的准确边界是：双开切换后扫描器读取 mode=6 控件树的窗口内曾返回空树，代码把“树暂时不可读”与“首页没有我”合并成同一个错误；不是本轮仍停留在 g10 搜索页，也没有新的 Wi‑Fi 断开证据。用户确认的三步搜索页复位代码已部署，但本轮未进入素材群/`act-001` 转发阶段。
- 本轮没有创建新的账号级发送任务，没有定位 `act-001`，没有进入原生转发页，没有发送 c1001 文字或卡片，也没有改写历史成功/失败记录；正式根入口保留且设备运行已停止。下一步只需处理 mode=6 读树时的短暂空树状态并做一次受控回归，不应把本轮报告为完整链路成功。

## 43. 2026-09-11 首页判定最小化修复后的 Android 回归

- 针对第 42 节现场继续做了最小修正：双开切换后先等待 2 秒；首页的“微信”“我”、返回箭头和搜索框均从同一份实时 mode=6 树判断；兼容 mode=6 返回短资源 ID（如 `cj1`、`kbq`）；不再要求会话行名称必须可读，因为 Android 15/HID 有时只暴露头像、时间而不暴露标题。没有加入固定坐标操作。
- 修复通过本地 `py_compile` 和 `git diff --check`，并上传正式 `wechat_assistant`。最后一次正式 `run_project` 通过实时识别矩形完成九宫格、`第1批` 和 `开始执行`，随后进入微信搜索页；没有获得扫描完成、PC 同步、任务创建或发送结果日志，之后页面回到九宫格，按状态不可确认规则停止。
- 本轮未创建新的账号级任务，未定位 `act-001`，未进入 c1001 原生转发页，未发送文字或卡片；设备为 Wi‑Fi `192.168.1.237`、HID 模式，停止后 `is_script_running=false`。历史成功与失败记录保持不变。
- 当前剩余问题不是固定坐标或 Wi‑Fi：正式工程的首页识别已能通过到微信搜索页，但本次日志采集没有形成后续扫描证据，无法把回到九宫格解释为成功或失败的具体业务步骤。下一步应先补齐正式工程的阶段日志/结束回执，再做一次受控回归。

## 44. 2026-09-11 搜索页快速复位方案

- 根据 Android 15 现场行为，搜索页回微信首页优先采用最多两次从左向右滑动；每次滑动区域都重新从当前 mode=6 控件树取得，间隔 0.5 秒，滑动后确认“微信/我”首页。若第一次已经确认首页，不再执行第二次，避免多余状态变化。
- 两次实时右滑无法确认首页时，保留原有“取消 → 清除搜索内容 → 实时结果区右滑”的有限兜底；所有动作仍由官方 ESP32 HID 执行，不使用固定坐标。
- 本地 `py_compile` 与 `git diff --check` 已通过；本节改动是在本轮 AScript 长轮询被用户中断后完成，尚未重新上传到手机或完成真实设备回归，不能把它报告为运行通过。9096 端口随后通过 TCP 和 HTTP `200 OK` 验证可达，之前的卡顿属于日志长轮询，不构成 Wi‑Fi 断开证据。

## 45. 2026-09-11 人工入口启动后的旧版本监控结果

- 用户人工启动了手机上的 `wechat_assistant` 并完成入口、批次和开始执行；本轮只监控，没有代为点击微信内控件。日志出现旧版 `SEARCH_HOME_RESET_STEP 1 cancel`，未出现新版 `SEARCH_HOME_RESET_SWIPE`，说明手机端尚未同步第 44 节的两次右滑版本。
- 高同学 `wechat-id-gaoshiteng_01` 本轮扫描得到 8 个 `g10` 群，后端 reconcile 成功并回写 `updated=8`；但旧收尾路径因未找到搜索框 X 记录 `cleanup_home` 失败。第二个槽位随后报“微信首页未出现我”，没有进入发送器。
- 现场弹窗明确为前置扫描失败，背景已是微信会话首页（可见底部“微信/我”和置顶“卡片素材群”）；没有创建本轮发送任务，没有定位 `act-001`，没有发送卡片或文字。达到当前运行边界后已停止工程，设备 Wi‑Fi 仍为 `192.168.1.237`，runtime 为 stopped。历史成功与失败记录保持不变。

## 46. 2026-09-11 右滑后普通群聊状态识别回归

- 扫描器与发送器均增加了有限右滑复位：每次官方 ESP32 HID 右滑后等待 1 秒，再读取新的 mode=6 控件树；状态分为搜索页、普通群聊页、其他子页和微信首页。两个模块已同步到正式 `wechat_assistant` 工程，本轮未使用 `eval_python`。
- 用户人工点击九宫格“群发微信”和第 1 批后，工程完成双开启动。日志首先记录高同学槽位扫描台账 `groupCount=3`、后端 `reconcile.success=true`、`updatedCount=3`；但收尾复位仍报告 `搜索页缺少唯一的实时搜索框控件`，随后第二槽位同类失败。有限重试后最终报告 `微信首页未出现“我”入口`，没有进入发送器，没有创建本轮账号级发送任务，也没有发送 `c1001`/`act-001`。
- 现场截图确认右滑后的真实页面是普通微信群 `g1007(17)`（副标题“新晃宠物交流群”），不是 Wi‑Fi 或 HID 断开。此 Android 15 页面在 mode=6 树中仅暴露返回按钮和图片/布局节点，未暴露可识别的群标题或底部编辑框，因此新增分类器仍得到 `state=unknown`，随后落入旧搜索框错误分支。该事实是下一轮需要处理的唯一代码阻塞，不把本轮报告为成功。
- 本轮已停止 `wechat_assistant`；设备仍为 Wi‑Fi `192.168.1.237`、HID 模式，runtime 为 stopped。历史成功和失败记录保持不变，正式根入口保留。

## 47. 2026-09-11 删除右滑复位旧搜索兜底

- 删除扫描器 `_reset_from_search_page()` 末尾旧的“取消 → 搜索框 X → 搜索结果区右滑”兜底，以及两个模块中仅供该路径使用的旧搜索框清除辅助函数。
- 现在扫描器和发送器只使用状态机：搜索页、普通群聊页或其他已识别子页才允许继续使用实时 mode=6 矩形右滑；右滑后等待 1 秒重新读树；状态为 `unknown` 时直接报告页面状态无法确认并停止，不再伪报“搜索框缺失”。
- 本地 `py_compile`、`git diff --check` 通过；两个模块已重新上传正式 `wechat_assistant`。本轮未启动测试，未改变任何发送或历史任务结果。

## 48. 2026-09-11 删除旧兜底后的第一批监控结果

- 用户人工启动正式 `wechat_assistant` 并点击第 1 批后，本轮只做运行监控，没有额外点击或扩展测试范围。设备为 Wi-Fi `192.168.1.237`、AScript 4.0.12、HID 模式，官方 ESP32 `AS_4.8_905DDCBA2010` 已连接。
- 第一个微信槽位在扫描前置的回首页阶段读到 `state=chat`；正式日志为 `微信右滑复位后页面状态无法确认：state=chat swipes=0`。扫描未完成，之后的有限重试仍在同一前置门禁停止。现场截图显示 AScript 错误弹窗，背景为微信页面；这不是 Wi-Fi 断开，也没有进入卡片素材群或发送流程。
- 本轮没有形成两个账号扫描结果、PC 映射更新、账号级发送任务、`act-001` 定位、c1001 原生转发或最终发送结果；历史成功/失败记录未改写。已执行 `stop_project`，设备 `is_script_running=false`，正式 `wechat_assistant` 根入口保留。

## 49. 2026-09-11 多次右滑复位版本实机回归

- 本轮将本地 `wechat_group_inventory` 与 `wechat_marketing_sender` 两个修复模块上传到正式 `wechat_assistant`，通过真实 `run_project` 启动；入口、批次第 1 批和“开始执行”均由实时感知后交给正式工程官方 ESP32 HID 完成，未使用 `eval_python`。
- 第一个账号槽位识别到 `wechat-id-gaoshiteng_01`，但进入扫描前读取到 `state=chat`。新复位逻辑已实际执行 3 次 generic 实时控件树右滑，每次使用当时树提供的矩形 `(0, 0, 1080, 2400)`，从 `(324, 1080)` 滑到 `(648, 1080)`；每次等待后状态仍为 `chat`，最终记录 `微信右滑复位后页面状态无法确认：state=chat swipes=3`。
- 随后第二个槽位也进入同一 `state=chat` 复位路径，本轮在第二个槽位第 1 次右滑后由人工要求停止。没有完成 `g10` 扫描、PC 台账同步、账号级发送任务、`act-001` 定位、c1001 原生转发或最终发送；没有新的后端发送结果，历史成功/失败记录保持不变。
- 本轮现场截图已保留；设备停止后 `is_script_running=false`，Wi-Fi 仍为 `192.168.1.237`，HID 模式保持。当前实际阻塞是：Android 15 的普通聊天页对这组右滑没有回到微信首页，需下一轮单独验证右滑方向/有效手势区域；不是扫描阶段主动点击 `g1007`，也不是发送动作成功或失败。

## 50. 2026-09-11 动作前页面核对门禁实现

- 扫描器和发送器已增加统一的动作前实时页面核对：点击、长按、输入、回车，以及关键素材滚动，先重新读取当前 mode=6 控件树并验证预期页面锚点。
- 预期状态不匹配时不复用旧 rect；先用实时页面矩形执行有界右滑复位，复位后抛出当前阶段错误，由上层重新读取页面并重新定位目标。双开选择器还会在点击前重新确认对应单项矩形仍存在。
- 已覆盖扫描前的微信首页、搜索页、更多群聊、双开槽位和账号页，以及发送器的聊天列表、卡片素材群、长按菜单、原生转发页、多选页、真实群名结果和发送预览页。
- 素材群向上滚动也已改为从当前实时 WeChat 控件树内容区域计算 HID 滑动点，不再使用屏幕宽高百分比作为动作位置。
- 本地 `py_compile` 与 `git diff --check` 通过；静态动作通道审计未发现 `action.click`、`action.swipe`、`eval_python` 或 `g1007` 硬编码。随后已将正式入口、启动页、扫描器和发送器上传到手机 `wechat_assistant`：`__init__.py`、`res/ui/launcher.html`、`wechat_group_inventory/__init__.py`、`wechat_marketing_sender/__init__.py`。上传后设备仍为 Wi‑Fi `192.168.1.237`、HID 模式，`is_script_running=false`；本轮仅同步代码，尚未启动新的实机回归。

## 51. 2026-09-11 上传后第 1 批监控结果

- 用户人工点击了 `wechat_assistant` 九宫格的“群发微信”和第 1 批；本轮仅监控，没有代替用户点击或扩展测试范围。
- 设备保持 Wi‑Fi `192.168.1.237`、AScript 4.0.12、HID 模式，官方 ESP32 HID 连接正常。运行日志显示两个微信槽位均在进入扫描前的页面复位阶段读到 `state=unknown`，各执行最多 3 次实时控件树右滑；没有进入 `g10` 扫描、PC 映射同步或发送器。
- 本轮没有创建新的账号级任务，没有定位 `act-001`，没有发送 c1001 文字或卡片，也没有改写历史成功/失败记录。现场截图确认工程已回到九宫格“等待选择”页面；随后执行 `stop_project`，最终 `is_script_running=false`。
- 本轮准确阻塞是页面状态识别仍为 `unknown`，不是 Wi‑Fi 或 HID 断开，也不是代码主动点击了 `g1007`。本记录只反映本轮监控事实，不能视为群发成功。

## 52. 2026-09-11 编辑器级双开复位流程修正

- 修改正式入口：前置扫描失败后不再重新加载整个扫描器，不再重复执行“系统 Home → 打开双开微信 → 恢复旧微信页面”的整体重试；单次运行由扫描器内部完成有界的微信页面复位。
- 修改扫描器和发送器：`state=unknown` 时先等待 2 秒重新读取 mode=6 控件树；右滑只允许使用实时微信内容区域，排除 `(0,0,屏幕宽,屏幕高)` 的外层包装矩形，并记录找不到有效内容区域的明确日志。
- 本地 `py_compile` 与 `git diff --check` 通过；本轮未上传手机、未启动 AScript 实机测试。下一步应在手机同步后验证：微信内部首页复位、双开切换、g10 搜索和后续完整链路。

## 53. 2026-09-11 同步手机后的正式入口实机回归

- 已将当前正式入口、启动页、扫描器和发送器同步到手机 `wechat_assistant`，通过真实 `run_project` 启动；九宫格“群发微信”、第 1 批和“开始执行”均使用实时控件树矩形感知后交给官方 ESP32 HID 完成，未使用 `eval_python`。电脑编辑器只负责编辑和部署，不能替代手机端微信页面的完整 HID 操作。
- 本轮在第一个微信槽位的前置扫描阶段停止。准确错误为：`动作前页面状态不符合：action=聚焦微信群搜索框 expected=search state=unknown query=''`；随后清理首页执行了 `swipes=3`，仍为 `state=unknown`，并弹出“微信群前置扫描未完成”。
- 因状态无法确认，未进入 `g10` 搜索、更多群聊、PC 映射同步、账号级发送任务、`act-001` 定位或 c1001 转发；第二个微信账号未开始。本轮不能报告为完整链路成功，也未改写历史成功/失败记录。
- 已执行 `stop_project`，设备 `is_script_running=false`；现场截图为 AScript 错误弹窗，设备 Wi-Fi `192.168.1.237` 仍在线。该轮阻塞是实时控件树页面状态为 `unknown`，没有 Wi-Fi 断开证据。

## 54. 2026-09-11 页面标识修正后的正式入口回归

- 按当前决策将搜索页判断收紧为“搜索框 + `页面设置` + 搜索分类关键字”；进入有查询结果的搜索页时使用 `取消`、搜索结果相关关键字作为补充条件。同步了正式 `wechat_assistant` 入口、启动页、扫描器和发送器，并通过真实 `run_project` 运行，微信页面动作仍由官方 ESP32 HID 完成，未使用 `eval_python`。
- 用户人工选择了九宫格“群发微信”、第 1 批并点击开始执行。本轮在第一个微信槽位的扫描前置复位阶段停止，手机弹窗准确显示：`微信右滑复位后页面状态无法确认：state=unknown swipes=2`；清理首页阶段同样为 `state=unknown swipes=2`。该弹窗是 AScript 工程报告，不是微信发送结果。
- 现场截图已捕获：弹窗背后可见微信搜索/最近使用区域，但当前截图被 AScript 弹窗遮挡，不能据此确认底层具体页面；弹窗后的 mode=6 控件树也未提供可见的微信节点。当前证据只能确认“实时控件树未被页面分类器确认”，不能推断为代码主动进入某个群或 Wi-Fi 断开。
- 本轮未进入 `g10` 输入、更多群聊、PC 映射同步、账号级任务创建、`act-001` 定位、c1001 转发或第二个微信账号；没有新增后端发送结果，历史成功/失败记录未改写。已停止工程，设备仍为 Wi-Fi `192.168.1.237`、HID 模式，`is_script_running=false`。

## 55. 2026-09-11 用户重新启动后的监控结果

- 用户重新点击开始执行后，正式 `wechat_assistant` 仍在 Android 15、Wi-Fi `192.168.1.237`、HID 模式运行；本轮只监控，不代替用户点击。
- 第一个微信槽位在“聚焦微信群搜索框”的动作前置核对阶段再次失败。运行日志为：`SEARCH_HOME_RESET_STATE after_swipe=1 state=unknown`，随后执行第 2 次实时控件树右滑，仍为 `state=unknown`；最终为 `TARGET_ACTION_PRECHECK_RESET_FAILED action=聚焦微信群搜索框 error=微信右滑复位后页面状态无法确认：state=unknown swipes=2`。
- 系统截图在日志出现后已经看到工程自动回到九宫格“等待选择”页面；随后执行 `stop_project`。因此本轮没有进入 `g10`、更多群聊、PC 映射同步、任务创建、`act-001` 或 c1001 转发，也未开始第二个微信账号。Wi-Fi 仍在线，历史结果未改写。

## 57. 2026-09-11 修复后正式入口触发回归未形成业务运行

- 已将修复后的 `wechat_group_inventory` 与 `wechat_marketing_sender` 上传到正式 `wechat_assistant`；本地 `py_compile` 与 `git diff --check` 通过。
- 通过实时 OCR 取得九宫格“群发微信”、批次“第1批”和“开始执行”的矩形，并由正式入口的官方 ESP32 HID 完成点击。入口随后回到九宫格“等待选择”，本轮没有取得新的扫描日志，也没有进入微信页面或产生业务运行证据。
- 因无法确认“开始执行”是否真正触发了前置扫描，已停止工程。最终设备仍为 Wi-Fi `192.168.1.237`、HID 模式、`is_script_running=false`；本轮没有 `g10` 扫描、PC 映射同步、任务创建、发送动作或后端结果，历史结果未改写。

## 56. 2026-09-11 用户现场反馈确认两个独立阻塞

- 用户现场确认：工程实际停留在微信搜索页面，搜索框没有输入 `g10`。因此前置的“搜索页识别失败”是真实问题；它发生在输入动作之前，不应继续归结为等待或网络问题。当前实现要求 `_wechat_page_state()` 先返回 `search`，否则 `_before_action(expected=\"search\")` 会先进入复位并阻断输入。
- 用户现场同时确认：两次右滑没有产生可见的返回首页效果。当前日志中的 `hid_action_sent` 只表示 `BleDevice.slide` 调用返回，没有验证触摸是否被微信页面接收、滑动前后页面是否变化；不能把该日志当作滑动成功。
- 这两个问题需分开处理：一是用实时控件树正确确认当前搜索页并允许聚焦输入框；二是用实时内容区域执行右滑，并增加滑动前/后的页面证据，区分 `hid_action_sent` 与 `hid_action_verified`。本轮不继续测试、不进入 `g10` 或发送流程。

## 58. 2026-09-11 统一入口阶段可观测性补强

- 正式入口增加安全阶段记录：九宫格启动、功能回调、批次弹窗、批次选择、前置扫描开始/完成/失败、发送器开始/完成、流程返回/失败。阶段同时输出固定 `WECHAT_ASSISTANT_PHASE` 日志，并写入手机工程内的 `.wechat_assistant_status.json`；状态不包含微信号、设备令牌或其他敏感配置。批次返回值无法解析时不再静默返回，而是记录阶段并报告错误；兼容单元素列表/元组返回值。
- 本地 `py_compile` 与 `git diff --check` 通过，入口已上传正式 `wechat_assistant`。通过实时 OCR 获取九宫格“群发微信”、第 1 批和“开始执行”矩形，并由正式工程官方 ESP32 HID 点击；手机工程文件树确认新增运行状态文件已生成。
- 本次短验证点击“开始执行”后约 10 秒内回到九宫格，`get_run_log` 仍未收集到输出，截图未出现微信页面或错误弹窗；因此只能确认入口未形成可见的微信业务运行证据，尚不能从本轮日志判定具体停在批次返回、前置扫描加载还是模块内部。已停止工程，Wi-Fi `192.168.1.237`、HID 模式保持，未进入 `g10`、未更新 PC 映射、未创建任务、未发送 `act-001`/c1001，历史结果未改写。

## 59. 2026-09-11 阶段日志可观测性验证后的实际阻塞

- 用户点击“开始执行”后，本轮日志已能形成业务阶段证据：高同学槽位 `wechat-id-gaoshiteng_01` 已进入微信首页，`返回微信会话列表` 与 `打开微信搜索` 两个动作前置核对均通过。
- 随后在 `聚焦微信群搜索框` 前置核对处停止：`TARGET_ACTION_PRECHECK_FAILED action=聚焦微信群搜索框 expected=search state=unknown query=`。系统截图显示屏幕为黑色过渡/空页面，未出现可输入 `g10` 的搜索页；没有进入更多群聊或后续发送流程。
- 设备状态显示脚本当时仍在运行、Wi-Fi `192.168.1.237` 在线、HID 模式保持；已执行 `stop_project`。本轮未完成扫描、PC 映射更新、任务创建或 c1001/`act-001` 发送，历史结果未改写。阶段日志补强已证明入口和业务启动可观测，当前剩余阻塞收敛为“打开微信搜索后页面短暂为空/控件树为 unknown”以及对应的等待/状态恢复策略。

## 60. 2026-09-11 隔离微信搜索 g10 测试

- 为验证最小动作链路，新建并上传独立 AScript 工程 `wechat_search_g10_test`；本轮只执行双开微信选择、回到会话列表、打开搜索、输入 `g10`、显示结果和退出，不扫描群台账、不创建发送任务、不发送卡片或文字。正式 `wechat_assistant` 未被本轮执行，历史结果未改写。
- 本地 `py_compile` 与 `git diff --check` 通过；实际通过 `deploy_and_run` 运行，官方 ESP32 `AS_4.8_905DDCBA2010` 连接成功。初次启动错误 `Device.home` 不存在已改为官方 HID `home()`，没有使用 `eval_python` 或固定坐标动作。
- 一次运行中，双开选择和 HID 打开微信搜索入口成功，搜索页由实时 mode=6 控件树的唯一文字 `页面设置` 确认；随后实时树未找到可输入控件，未输入 `g10`。另一次运行在双开选择后没有读到唯一的微信首页页签，未继续点击；现场系统截图为黑屏，收尾时 mode=6 未提供可见的 `com.tencent.mm` 节点。
- 当前可确认：`search_item` 不是搜索页身份标识，而是后续输入动作所需的实时输入控件对象；搜索页识别已改为优先使用 `页面设置`，但当实时控件树为空或没有输入控件时仍不能安全操作。该隔离测试已停止，设备 `is_script_running=false`；当前阻塞是微信页面渲染/控件树可用性不稳定，尚不能归因于页面设置判断本身。

## 61. 2026-09-11 后续隔离测试账号范围

- 用户确认高同学原版微信当前出现黑屏；后续实机测试只使用 leo（微信号 `qq673105954`），不再对高同学账号执行搜索、扫描或发送测试。
- 隔离工程 `wechat_search_g10_test` 已增加 leo 槽位选择和实时控件树微信号核验；未核验到 `qq673105954` 时立即停止，禁止继续操作。对抗式审查后收紧了包名范围：仅搜索输入框允许兼容空 `packageName`，双开入口、页签、搜索入口和页面标识仍必须来自对应实时微信节点。
- 本地 `py_compile` 通过，隔离工程已重新上传手机；本轮未启动运行，正式 `wechat_assistant` 未修改。

## 62. 2026-09-11 leo 隔离测试双开选择器控件树为空

- 本轮直接通过 `deploy_and_run` 启动隔离工程 `wechat_search_g10_test`，目标是选择右侧带双开标识的 leo 微信；官方 ESP32 HID 已连接，但日志没有出现 `HID_TAP label=双开 leo 微信`。
- 现场系统截图显示双开选择器确实在前台，左侧为普通微信，右侧为带双开标识的微信；但同一时刻 mode=6 返回 `mode=-1`、`viewCount=0`、`views=[]`，因此脚本无法从实时控件树取得右侧单项矩形，也没有使用截图位置盲点或错误点击。
- 隔离工程随后以 `微信页面未进入前台` 结束并已停止，最终 `is_script_running=false`。本轮没有进入 leo 微信、没有输入 `g10`，没有扫描、映射、任务创建或发送；高同学账号和历史结果未改写。
- 当前准确阻塞是：双开选择器可见，但 AScript mode=6 实时控件树为空/模式无效，导致“右侧 leo 入口”无法满足控件树矩形门禁；不是左右索引选错。后续应先解决该选择器树数据恢复，再继续测试。

## 63. 2026-09-11 双开选择器系统窗口包名兼容修正

- 双开入口识别已做最小兼容修正：除 `com.zte.cn.doubleapp` 外，若实时 mode=6 树明确暴露“请选择要使用的应用”或“取消”，且两个 `微信` 节点各自位于 `GridView` 单项容器内，也允许使用这些系统窗口节点；仍必须得到恰好两个单项矩形，按横向顺序选择右侧 leo，不使用 OCR 或固定坐标作为动作目标。
- 隔离工程在无法取得入口时改报 `双开选择器控件树不可用：mode=... viewCount=...`，避免把“树不可用”误报成“左右入口不存在”。正式扫描器和发送器同步采用相同的结构约束。
- 四个 AScript 模块通过本地 `py_compile` 和 `git diff --check`；本次尚未重新部署或启动实机，因为当前设备 mode=0/1/2/3/6 均返回 `mode=-1、viewCount=0、views=[]`，且设备状态显示 Android 辅助功能未授予。当前仍需先恢复手机端辅助控件树，才能验证右侧 leo 的真实矩形点击。

## 64. 2026-09-11 开启辅助功能后的 leo 选择器复测

- 用户确认已开启辅助功能后，重新通过隔离工程 `wechat_search_g10_test` 执行一次；官方 ESP32 `AS_4.8_905DDCBA2010` 连接成功，Wi-Fi 在线。
- 本轮仍未取得双开选择器的 mode=6 实时树，日志为：`双开选择器控件树不可用：mode=None viewCount=None；未取得右侧 leo 实时矩形`；现场系统截图显示手机仍在“无障碍”设置页，双开选择器覆盖在页面底部。没有执行任何选择器点击、没有进入 leo、没有输入 `g10`。
- 运行已停止，`is_script_running=false`。设备状态接口仍返回 `accessibility.granted=false`，因此“手机设置页面显示开启”和“AScript 连接器可读取辅助控件树”目前不一致；需先解决该状态不一致或确认双开系统窗口不向 mode=6 暴露节点，才能继续。

## 65. 2026-09-11 正式工程 leo 单账号复测

- 按用户最新要求改回正式工程 `wechat_assistant`，本轮只准备测试 leo（`wechat-id-qq673105954`），不执行高同学。为避免改变默认双账号行为，扫描器增加了仅在运行时环境明确指定时才生效的槽位范围；发送器只使用本次前置扫描成功返回的账号 ID，默认仍覆盖所有已配置账号。
- 通过正式工程 `deploy_and_run` 启动一次，官方 ESP32 `AS_4.8_905DDCBA2010` HID 桥已就绪；但正式入口的 `hid_click` 读取不到九宫格“群发微信”目标，实时 mode=6 返回 `mode=-1`、`viewCount=0`、`views=[]`。因此没有点击入口、没有选择批次、没有打开 leo、没有扫描 `g10`、没有创建任务或发送。
- 现场截图显示手机停留在“无障碍”设置页，底部覆盖“双开微信选择器”（普通微信和带双开标识的微信），与实时控件树为空相互印证。运行日志未形成新的业务阶段输出；本轮准确阻塞仍是 AScript 连接器无法读取 mode=6 控件树，不是 leo 账号、卡片素材群或群发动作失败。
- 已执行 `stop_project`，并重新上传当前正式 `automation/ascript/__init__.py` 覆盖临时单账号运行根入口；设备最终为 Wi-Fi `192.168.1.237`、HID 模式、`is_script_running=false`。本轮没有改写历史成功/失败记录。

## 66. 2026-09-11 正式工程 leo 入口点击复测

- 用户打开 AScript 页面后，本轮再次通过正式工程 `wechat_assistant` 启动，并以临时运行环境限定 leo 槽位（slot 1）；官方 ESP32 HID 桥日志为 `HID_BRIDGE_READY mode=6 official=BleDevice`，九宫格正常显示。
- 九宫格显示后，实时 mode=6 仍返回 `mode=-1`、`viewCount=0`、`views=[]`。尝试用正式 `hid_click` 定位“群发微信”时只获得两个 OCR 矩形，控件树有效节点为 0；按规则没有把 OCR 矩形直接作为点击目标，因此未点击、未选批次、未进入 leo 微信、未扫描/映射/发送。
- 现场截图显示的是 AScript 九宫格，不是黑屏或微信页面；运行日志未产生新的业务日志。已执行 `stop_project`，并重新上传当前本地正式根入口，清除了本次临时 leo 运行注入。设备保持 Wi-Fi/HID，脚本已停止；历史结果未改写。

## 67. 2026-09-11 重启后 AScript 控件树恢复

- 用户重启手机后，设备状态显示 Wi-Fi `192.168.1.237` 在线、HID 模式、辅助功能 `granted=true`、录屏授权正常，当前没有脚本运行。
- 直接读取 mode=6 成功：返回 `mode=6`，树中实际遍历到 197 个节点，其中 113 个属于 `com.aojoy.airscript`，可读到 `AScript`、`wechat_assistant`、`wechat_search_g10_test` 等工程入口；现场截图为正常 AScript 页面，两个微信未出现黑屏现象。
- AScript 接口的 `config.viewCount` 仍报告为 0，且当前聚合页面 `packageName` 为空，但 `views` 实际包含完整节点；因此本次已确认“实时树可用”，同时记录该计数字段不一致。尚未启动群发或点击微信，下一步可在此基础上继续 leo 正式路径。

## 68. 2026-09-11 重启后正式工程 leo 启动复测

- 手机重启后，正式工程 `wechat_assistant` 以临时 leo 槽位范围启动成功；日志确认 `HID_BRIDGE_READY mode=6 official=BleDevice`，九宫格现场截图正常显示。
- 九宫格是 AScript `WebView` 页面。实时 mode=6 虽能读取 AScript 外层节点，但没有“群发微信”卡片的可操作文本/单项矩形；观察结果只能看到外层 `WebView`，不能把外层矩形或 OCR 文字矩形当作 HID 点击目标。
- 因此本轮未点击“群发微信”、未选择批次、未进入 leo、未扫描/映射/发送。已停止运行并重新上传当前本地正式根入口，清除临时 leo 运行注入；历史结果未改写。若继续实测，需要用户手动点一次九宫格“群发微信”，之后再由实时控件树/HID 接管后续流程。

## 69. 2026-09-11 手动启动后的搜索页复测

- 用户手动启动正式 `wechat_assistant` 后，本轮实际运行到微信搜索页；现场截图不是黑屏，实时树能读到 `com.tencent.mm:id/d98` 可编辑搜索框，提示文字为“搜索本地或网络结果”，但尚未输入 `g10`。
- 日志显示扫描器仍把页面判为 `state=unknown`：第一次通用 HID 右滑结果为 `verified`，第二次为 `no_visible_change`，随后在“聚焦微信群搜索框”前置检查处停止；本轮未进入更多群聊、数据库映射或发送。
- 按用户要求未继续重试，已执行 `stop_project`。最终 Wi-Fi `192.168.1.237` 在线、辅助功能 `granted=true`、HID 模式、脚本已停止；历史成功/失败记录未改写。

## 70. 2026-09-11 放宽搜索页门禁后的定向重试

- 按用户要求不再把 `state=unknown` 本身作为搜索输入的停止条件，扫描器改为在动作前重新读取实时 mode=6 树，并以微信可编辑搜索节点作为搜索动作依据；同时修正了相关辅助函数必须传入实时树的调用错误。本地 `py_compile` 通过，修复后的扫描器已上传正式 `wechat_assistant`。
- 本轮只做一次定向 leo 槽位运行，仍通过正式 `run_project`，微信动作由官方 ESP32 `BleDevice` HID 完成，未使用 `eval_python`。脚本在“聚焦微信群搜索框”前置复核处停止，现场错误为：`action=聚焦微信群搜索框 expected=search state=unknown query=`；收尾复位仍为 `state=unknown swipes=2`。
- 系统截图显示微信搜索页，搜索框为空，未输入 `g10`；因此没有进入更多群聊、PC 映射同步、任务创建、`act-001` 或 c1001 转发。此次不是成功测试，也没有改写历史成功/失败记录。
- 设备已停止，`is_script_running=false`；Wi-Fi `192.168.1.237` 在线、辅助功能已授予、HID 模式保持。临时 leo 运行范围已清除并恢复正式入口。当前剩余问题是：先前同类实时树可读到 `com.tencent.mm:id/d98`，但动作前重新取树时辅助函数仍未匹配到该节点，导致放宽逻辑没有真正放行输入；下一步应复用已找到的实时 `input_rect` 完成聚焦前检查，再进行一次最小验证。

## 71. 2026-09-11 直接使用搜索框矩形的修正

- 按用户要求删除搜索框动作前的重复 `expected=search` 页面复核：当前 mode=6 树找到唯一可编辑微信搜索框后，直接用该实时矩形通过官方 HID 点击，再输入 `g10`；不再因周边页面状态为 `unknown` 触发右滑复位。扫描器本地 `py_compile`、`git diff --check` 通过，已上传正式 `wechat_assistant`。
- 已通过真实 `run_project` 启动正式工程。当前手机停在九宫格“等待选择”页面；mode=6 只能读到外层/底层节点，没有暴露九宫格 WebView 内“群发微信”卡片的可操作节点，因此没有使用 OCR 或固定坐标代替 HID 点击。
- 尚未进入批次选择、微信搜索或 `g10` 输入；没有数据库同步、任务创建或群发结果。本轮等待用户从九宫格手动选择“群发微信”、第 1 批并开始执行，之后继续监控搜索框直输验证。

## 72. 2026-09-11 直接输入搜索框后的正式回归

- 用户启动正式 `wechat_assistant` 后，本轮只做一次监控运行。扫描器已不再对已取得的实时搜索框矩形执行重复 `search` 页面复核，并成功越过“聚焦微信群搜索框”阶段。
- 第一个微信槽位停止于“双开微信选择器”：未取得控件树中的两个微信入口；第二个微信槽位完成搜索框聚焦并执行了输入动作，但输入后的实时控件树未核验到 `g10`，错误为：`输入微信群编号后未在控件树中核验到搜索内容`。现场截图显示 AScript 错误弹窗，背景为微信搜索页，搜索框仍为空。
- 本轮没有进入更多群聊、PC 映射同步、任务创建、`act-001` 或 c1001 转发；没有新增后端发送结果，也没有改写历史成功/失败记录。当前失败已停止，不继续盲重试。
- 设备最终 `is_script_running=false`；Wi-Fi `192.168.1.237` 在线、辅助功能已授予、HID 模式保持。当前剩余问题从“搜索框前置复核阻塞”收敛为“官方 HID 输入后，mode=6 树未看到输入文本”，以及双开选择器偶发无两个入口节点。

## 73. 2026-09-11 增加搜索框聚焦等待后的正式启动监控

- 按用户要求，在取得实时微信搜索框矩形并通过官方 ESP32 HID 聚焦后增加 `2.5` 秒等待，再执行 `Clipboard.put("g10")` 与官方 HID 粘贴；代码输出 `TARGET_ACTION_WAIT action=输入微信群编号 seconds=2.5`。本地 `py_compile` 与 `git diff --check` 通过，扫描器已上传正式 `wechat_assistant`。
- 随后通过正式 `run_project` 启动监控。设备状态曾报告工程运行、Wi-Fi `192.168.1.237` 在线、HID 模式和辅助功能可用，但连续读取不到业务日志；现场系统截图显示仍停留在 AScript 本地工程列表，没有进入批次、微信或搜索流程。因此本轮不能证明 2.5 秒等待已走到，也不能判定 `g10` 输入成功。
- 已停止工程清理现场。本轮没有进入微信、没有扫描或同步 PC 群映射、没有创建任务或发送 `act-001`/c1001；历史成功/失败记录未改写。下一次应先确保九宫格内“群发微信 → 第 1 批 → 开始执行”已形成可观测启动，再验证新增等待。

## 74. 2026-09-11 增加 2.5 秒等待后的正式复测结果

- 用户点击“开始执行”后，正式 `wechat_assistant` 确实进入高同学/`wechat-instance-1` 的微信搜索页；扫描日志为：`输入微信群编号后未在控件树中核验到搜索内容`，该账号扫描耗时 `21.507` 秒。
- 系统截图显示微信搜索页输入框仍为空，背景为“最近在搜”列表；弹窗同时记录收尾 `cleanup_home` 失败：`微信右滑复位后页面状态无法确认: state=unknown swipes=2`。因此本轮没有确认 `g10` 已输入，不能把 2.5 秒等待视为已解决问题。
- 已按约定立即停止工程。本轮没有进入“更多群聊”、PC 映射同步、任务创建或 `act-001`/c1001 转发；历史成功/失败记录未改写。设备 Wi-Fi `192.168.1.237`、HID 模式保持。

## 75. 2026-09-11 搜索框二次聚焦改动后的正式复测

- 已在搜索输入链路增加第二次实时搜索框矩形 HID 点击：首次聚焦后等待 `1.5` 秒，重新读取搜索框矩形并再次点击，再等待 `1.5` 秒后执行官方 HID 粘贴 `g10`，粘贴后再等待 `1.5` 秒核验。代码本地 `py_compile`、`git diff --check` 通过并已上传正式 `wechat_assistant`。
- 本轮正式运行在搜索前停止：日志为 `ACCOUNT_IDENTITY slot=wechat-instance-1 accountId=wechat-id-gaoshiteng_01`，随后 `打开通讯录` 前置核验通过，但 `打开通讯录群聊` 被判为 `expected=contacts state=home`。系统截图实际显示微信“通讯录”页面，且可见“群聊”入口；因此这是通讯录页面状态识别门禁与现场页面不一致，尚未进入搜索框，不能评价本轮二次聚焦或 `g10` 输入效果。
- 已立即停止工程。本轮没有进入 `g10`、更多群聊、PC 映射同步、任务创建或 `act-001`/c1001 转发；历史成功/失败记录未改写。设备保持 Wi-Fi `192.168.1.237` 与 HID 模式。

## 76. 2026-09-11 通讯录状态门禁重复监控

- 用户再次点击“开始执行”后，正式工程保持运行状态，但现场截图仍停留在微信“通讯录”页，页面可见“群聊”入口；短轮询期间没有新的业务日志，也没有进入搜索框。
- 本轮在确认页面和日志均无变化后立即停止。新增的搜索框二次聚焦、`g10` 输入及其等待链路未被执行；没有扫描、PC 映射同步、任务创建或 c1001 转发，历史成功/失败记录未改写。

## 77. 2026-09-11 Android 微信助手对抗式审查

### 当前确认的正式 SOP

1. 统一入口显示九宫格，用户选择“群发微信”和发送批次；手机端不重复配置群、文字或卡片。
2. 每个账号槽位先由官方 ESP32 HID 回到手机前台并打开微信；双开选择器必须从实时 mode=6 树读取两个“微信”单项容器矩形，按槽位点击，不能使用共享 `GridView`、OCR 或固定坐标。
3. 进入微信后等待页面稳定；只在微信“首页/微信会话列表”和“我的”页之间操作。点击“我”后从实时树/OCR读取唯一微信号，账号 ID 使用 `wechat-id-<wechat_id>`，昵称只作展示；再由 HID 点击“微信”回到会话首页。
4. 从会话首页读取实时搜索入口，HID 点击搜索框，等待控件树稳定后再聚焦并通过官方 HID 粘贴 `g10`；必须在实时树中核验输入内容。
5. HID 点击实时树中的“更多群聊”，读取群聊区的 `groupCode + groupName`；依据实时列表矩形下滑到底部，等待并重读控件树，完成该账号的 partial reconcile，更新 PC 群台账。
6. 扫描结束或发生异常时，读取当前实时树；若不是微信会话首页，使用实时内容矩形执行水平 HID 复位，按下、移动、抬起后等待 1–2 秒并重新判定，最多有限重试；未确认首页就截图、记录日志并停止。
7. PC 在两个账号扫描和映射完成后，按“微信账号 + 群编号 + 批次”创建任务。测试只允许 `c1001`，卡片为 `act-001`，目标群名来自 PC 映射。
8. 每个账号回到微信会话首页后，使用实时树定位置顶“卡片素材群”，定位 `act-001`，由官方 HID 长按、转发、进入原生多选页，按 PC 提供的真实群名选择目标群，输入文字并发送；发送后的目标群标题/消息 UI 与后端逐目标结果都必须确认。
9. 每个目标或账号完成后都必须回到微信会话首页，再切换下一个账号；运行结束停止工程、恢复正式根入口并发送服务器端完成通知。

### 对抗式审查结论

- **高风险：微信首页判定存在误判通讯录的缺陷。** 发送器 `_is_wechat_chat_list()`（`wechat_marketing_sender/__init__.py:1326`）把底部出现“通讯录”“我”或“发现”任一项、同时有顶部搜索入口就当作会话首页，没有确认“微信”页签处于当前会话列表状态。扫描器 `_wechat_page_state()` / `_wechat_home_point()` 也主要依赖“微信”和“我”底部节点、无返回箭头、无搜索框，不能排除通讯录页的底部残留节点。该缺陷可以直接解释“页面实际在通讯录，却被识别为 home”。最小修正应统一要求“微信”页签 + 会话列表搜索入口，并把“通讯录/发现/我”页签仅作为负面或非首页信号。
- **高风险：旧通讯录路径仍存在。** 扫描器的默认 `full` 分支仍会调用 `_open_group_chat_list()`（`wechat_group_inventory/__init__.py:2470`），模块文件顶部说明也仍把“通讯录 → 群聊”写成主流程。统一入口当前设置 `TEAMBUY_SCAN_MODE=targeted`，所以本地源码的正常定向分支会提前 `continue`，但环境未注入、设备端代码未同步或其他入口调用默认值时仍可能重新进入旧路径。它不符合当前“首页 → 搜索 g10 → 更多群聊”决策，应从正式路径移除或隔离。
- **高风险：每个微信动作后的等待不满足当前要求。** 扫描器 `_tap()`/`_back()` 只有 `0.7s`；发送器 `_tap()`、`_paste()` 只有 `0.35s`，`_send_enter()` 为 `0.6s`，部分返回动作是 `0.8s`。虽然若干动作后还有状态轮询，但代码没有统一保证“动作完成后至少等待 1–2 秒再取树/判定”。这会把页面尚未渲染误报成阻塞。应在 HID 动作封装层统一加入最小 1 秒的动作后等待，再叠加状态驱动等待。
- **高风险：右滑没有按要求显式拆成三个触摸原子动作。** 扫描器 `__init__.py:253`、发送器 `__init__.py:1095` 和 `:2098` 调用的是官方 `BleDevice.slide()`，不是显式的 `touch_down → touch_move → touch_up`。官方插件文档确认 `slide()` 是合法高阶滑动 API，且支持按下/抬起参数；但从当前项目源码和日志无法证明它已经按用户要求拆成三段。发送器长按 `:1275–1277` 使用了 `touch_down + touch_up`，这是长按，不是右滑，不能替代滑动三段动作。
- **中风险：滑动成功日志仍可能被高估。** 当前复位将“控件树指纹发生变化”记录为 `hid_action_verified`，但树变化也可能来自异步渲染；真正的复位成功必须单独以“滑动后确认微信会话首页”为准。`hid_action_sent`、树发生变化和首页已确认应分成三个结果。
- **中风险：前置扫描对降级账号没有“两个账号必须全部成功”的硬门禁。** 定向扫描中 reconcile 出错会把该账号记为 `degraded`，但不一定写入顶层 `errors`；统一入口随后只收集 `status == success` 的账号并继续发送。若一个账号降级、另一个成功，理论上可能只为成功账号创建任务，不符合双账号完整流程。应在任务创建前要求所有本次目标槽位均为 `success`，否则只同步报告、不进入发送。
- **低风险：当前文档与源码存在漂移。** `docs/decisions-active.md` 已明确采用定向 `g10` 搜索，但扫描器模块 docstring 和 full/incremental 辅助函数仍描述通讯录扫描。它不一定影响 targeted 运行，却会增加后续误调用旧分支的概率。

### 本轮验证边界

- 本轮只做静态审查，没有部署、启动或点击手机，没有发送微信消息。
- `python3 -m py_compile` 已通过：统一入口、群扫描器、发送器、账号身份模块；`git diff --check` 已通过。
- `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests/test_automation_group_reconcile.py`：11 passed。
- `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests/test_automation_control.py backend/tests/test_automation_notifications.py`：15 passed。
- 当前不能把代码报告为“完全符合 SOP”或“已适合生产”；上述高风险问题需要修正并重新进行一次受控 Android 验证。

## 78. 2026-09-11 对抗式审查修正（静态验证）

- 统一首页判定：必须同时看到微信底部页签、我的页签和顶部搜索入口；显式排除“通讯录”“发现”“我”顶部页标题、搜索输入框和返回箭头，避免把通讯录页误判为微信会话首页。
- 右滑与素材群滚动统一改为官方 ESP32 HID 的 `touch_down → touch_move → touch_up` 三段动作；动作坐标仍来自当前 mode=6 控件树矩形，未加入固定坐标。
- 扫描器和发送器的点击、粘贴、回车、返回、Home、滑动及双开页面切换均增加统一的 1.2 秒动作后等待；原有状态轮询继续作为最终判断。
- 生产扫描模式固定为 targeted；统一入口在进入发送器前要求本次所有扫描槽位均返回 `status=success`，任何账号降级、缺失或顶层扫描错误都会阻止发送。
- 扫描器和发送器的任务异常、账号异常和收尾复位异常增加设备端阻塞截图，路径打印为 `sdcard/airscript/screen/gp/teamBuy_blocker_<stage>_<timestamp>.jpg`，不记录 Token 或其他敏感配置。
- 本轮仅修改 AScript 代码和当前状态文档，未部署手机、未运行真实微信测试、未发送消息。`py_compile`、`git diff --check` 及现有相关后端测试需在本轮代码修改完成后重新执行。

## 79. 2026-09-12 删除废弃通讯录扫描代码

- 根据当前决策，已从 `wechat_group_inventory` 直接删除废弃的“通讯录 → 群聊”和微信会话列表全量扫描实现，以及仅服务该旧路径的群人数任务、旧群头像分类辅助和相关常量。
- 当前生产扫描代码只保留“微信首页 → 搜索 g10 → 更多群聊 → mode=6 实时群行 → partial reconcile”路径；页面识别中保留“通讯录”作为负面状态，用于防止把通讯录页误判为首页，不代表会进入通讯录操作。
- 已确认 AScript 代码不再引用旧通讯录入口、旧会话列表扫描或群人数任务；未删除当前账号身份、双开选择、官方 ESP32 HID、前置扫描、PC 映射同步和发送器代码。
- 本轮只做代码清理和静态校验，尚未部署或运行手机测试；历史测试记录不变。

## 81. 2026-09-12 搜索输入提交与微信搜索按钮修正

- 用户约 01:44 两次实测后确认：第一次运行中键盘侧可见 `g10`，但微信搜索框没有显示内容；现场 mode=6 树随后确认 `com.tencent.mm:id/d98` 为 `focused=true`、`text=""`，并暴露真实微信搜索按钮 `id=mdg`，因此问题是 HID 粘贴内容停留在输入法组合区、未提交到微信输入框/搜索动作未完成，不是搜索页不存在。
- 群扫描器现会在官方 HID 粘贴后核验微信输入框；若仍为空，发送一次官方 HID `Enter` 提交输入法组合内容；若实时树暴露唯一微信“搜索”按钮，则使用该控件实时矩形点击，并等待搜索结果。
- 发送器的搜索输入链路同步增加相同的提交和实时“搜索”按钮处理；不使用固定键盘坐标，不调用 `eval_python`。
- 本地 `py_compile`、`git diff --check` 通过；两个正式 AScript 文件已上传 `wechat_assistant`。本轮未启动新的真实测试，未进入群发闭环，历史成功/失败记录未改写。

## 80. 2026-09-12 删除动作前页面状态门禁并修复搜索控件识别

- 用户约 01:25 实测时确认现场已在微信搜索页，搜索框仍显示“搜索本地或网络结果”，但正式入口弹出“微信搜索框未出现”；该错误发生在输入、聚焦和粘贴之前，因此本轮没有输入 `g10`，也没有进入发送阶段。
- 扫描器和发送器不再使用 `_before_action` 的全局 `state=home/search/...` 作为 HID 动作前置门禁；页面分类仅保留为观察和收尾复位依据，具体动作继续要求实时目标控件唯一存在。
- 搜索输入识别允许 Android 15/HID mode=6 将 `packageName` 挂在微信上层容器、动态输入叶子节点包名为空的情况，并接受实时树中已确认的“搜索本地或网络结果”占位符；不使用固定坐标。
- 本地 `py_compile`、`git diff --check` 通过；群扫描器和发送器已上传正式 `wechat_assistant`，`local_config.py` 未改动。设备保持 Wi-Fi/HID，失败运行已停止；本轮尚未重新执行真实微信流程，历史成功/失败记录未改写。

## 82. 2026-09-12 02:03 搜索输入根因与 HID ASCII 修正

- 02:03 运行的正式工程弹窗明确记录：`微信群前置扫描未完成`，原因是 `输入微信群编号后未在控件树中核验到搜索内容`；现场截图中微信搜索框仍显示“搜索本地或网络结果”，因此本次不是输入法未启用，也不是首页判定导致的首个失败。
- 本次根因收敛为：扫描器和发送器对 ASCII 搜索词 `g10`、`c1001` 仍走 `Clipboard.put` + `BleDevice.paste()`，没有使用官方 Android ESP32 HID 的直接 `BleDevice.input()`。已将 ASCII 搜索词切换为官方 HID 逐键输入，中文文字和其他非 ASCII 内容仍保留剪贴板路径。
- 本地 `py_compile` 与 `git diff --check` 通过；群扫描器和发送器已于 02:08 上传正式 `wechat_assistant`，远端文件更新时间分别为 02:08:50 和 02:08:51。上传后未启动新的真实运行，当前不能报告输入修正已通过微信 UI 验证；历史成功/失败记录保持不变。

## 83. 2026-09-12 02:03 失败后的控件树核验修正

- 复核后确认“输入内容未核验”不能简单归因于等待不足：失败截图中的微信搜索框仍是占位符，前置运行已等待粘贴后 1.5 秒、查询核验最长 6 秒，并在回车后继续等待和核验。
- Android 15/HID mode=6 可能同时暴露同一搜索框的外层 `EditText` 与同矩形子输入叶子；此前内容核验只读取 `_search_input_item()` 选出的单个节点，存在读到占位符节点而漏掉实际文本节点的风险。现已将扫描器和发送器的内容核验改为检查同一微信搜索区域内的所有合法输入叶子，动作定位逻辑保持唯一矩形约束。
- 本地 `py_compile`、`git diff --check` 通过；两个 AScript 模块已再次上传正式 `wechat_assistant`。本次修正尚未重新进行真实设备验证，历史成功/失败记录保持不变。

## 84. 2026-09-12 02:16 直接 HID ASCII 输入仍未写入微信

- 02:16 正式运行仍失败在 `输入微信群编号后未在控件树中核验到搜索内容`；停止前读取 mode=6 全部相关节点，微信搜索输入外层 `d98` 为 `focused=true、text=""`，同矩形子输入叶子仍为占位符 `搜索本地或网络结果`，另一个背景输入节点为空且未聚焦。没有任何节点出现 `g10`。
- 因此本轮排除“只读取错了一个输入叶子”和“等待时间不足”；当前更具体的阻塞是官方 `BleDevice.input("g10")` 调用后字符没有写入该微信输入控件。设备 Wi-Fi、HID 模式和辅助功能仍正常；运行已停止，未进入更多群聊或发送，历史结果未改写。

## 85. 2026-09-12 AScript Ime 搜索输入实验已部署

- 按用户明确授权，群扫描器和发送器的 ASCII 搜索词（`g10`、`c1001`）改为使用已安装 AScript 官方 `Ime.is_active()` / `Ime.input()`；点击、返回、长按、滑动和其他微信 UI 动作仍使用官方 ESP32 HID。输入法未激活时立即停止。
- 本地 `py_compile` 与 `git diff --check` 通过；两个模块已上传正式 `wechat_assistant`。正式工程已启动并停在九宫格“等待选择”，尚未点击“群发微信”、尚未运行本次实验。该实验只验证正常微信 UI 是否接收搜索文本，不做或声称任何规避微信检测的能力。

## 86. 2026-09-12 02:27 首页复位未执行右滑的修正

- 用户 02:27 实测失败在群编号列表前，提示“微信返回后未确认首页”；复核当时源码确认：从“我”页返回曾点击底部“微信”页签，搜索/子页面复位曾使用 HID `back()`，并非用户要求的两次右滑，因此现场看不到滑动动作是代码路径事实。
- 扫描器和发送器现统一使用当前 mode=6 微信控件树计算可用内容区域，最多执行两次官方 ESP32 HID 显式 `touch_down → touch_move → touch_up` 右滑；每次动作后等待 1–2 秒并重新确认微信会话列表首页，第一次已确认则不执行第二次。实时滑动区域不存在或两次后仍未确认时立即截图、记录并停止。
- 02:42 实测发现原先按内容区 8% 边距计算的起点仍过于靠近 Android 左边缘，可能触发系统返回/退出手势；现改为实时内容区域内约 35% → 75% 的中部右滑，仍不使用固定屏幕坐标。
- 03:03 实测发现 35% → 75% 的水平幅度对微信返回手势仍可能不足；现将终点扩大到实时内容区域 95%，起点保持 35%，继续避开左边缘并使用实时矩形计算。
- “我”页读取真实微信号后返回首页也已改用同一右滑复位逻辑，不再点击底部“微信”页签作为返回手段。
- 本地 `py_compile` 与 `git diff --check` 通过；两个模块已重新上传正式 `wechat_assistant`。设备当前在线、Wi-Fi/HID/辅助功能状态可用，工程未启动新的真实测试，尚未报告微信 UI 或后端闭环成功。

## 87. 2026-09-12 02:42 启动阶段提前右滑修正

- 02:42 实测确认右滑发生在点击“我”之前，导致没有读取微信号、没有进入 `g10` 搜索。根因是扫描器 `_open_wechat()` 在首页状态分类为 `unknown` 时提前调用了复位右滑；这违反了“先点击我核验账号，再返回首页搜索”的顺序。
- 扫描器现在启动后只从实时微信树定位唯一底部“我”入口并点击；页面分类异常时不再提前右滑，找不到入口就截图、记录并停止。账号真实微信号读取完成后，才调用中部右滑返回首页，再进入 `g10` 搜索。
- 发送器移除了进入任务后的提前复位右滑，改为先执行“我”页账号核验，核验完成后再复位到微信首页。
- 本轮修改已通过 `py_compile` 和 `git diff --check`，两个模块已重新上传正式 `wechat_assistant`；设备当前已有一轮工程运行，需停止或自然结束后重新启动才能使用本次上传内容，尚未报告搜索、UI 或后端闭环成功。

## 88. 2026-09-12 返回方式按阶段拆分

- 用户要求“我”页返回微信首页恢复原来的实时底部“微信”Tab 点击方式；扫描器和发送器现均在读取真实微信号后定位并点击唯一“微信”Tab，等待并确认会话列表首页，不再用右滑。
- 右滑仅保留给搜索/群列表等子页面返回首页；其实时区域坐标改为 `x=0% → x=50%`、`y=top + height×50%`。该右滑不再用于 profile 返回。
- 本轮尚未重新启动真实测试；需在工程停止后重新启动，才能验证新的阶段化返回顺序。

## 89. 2026-09-12 03:29 动作后等待与首批 c1001 测试准备

- 用户确认 03:29 测试中“我”页返回首页已成功，但点击、读取微信号和返回动作衔接偏快；扫描器与发送器的 HID 动作统一等待从 1.2 秒提高到 1.5 秒，并在读取真实微信号后额外等待 1.5 秒再返回首页。
- 首批发送测试继续限定为批次 1、群编号 `c1001`、卡片 `act-001`；发送器已有 `TEST_ONLY` 白名单校验，不放宽其他群或批次。
- 本轮修改需完成静态检查和上传后，才可开始新的受控真实测试；不得把上一轮成功扩大为完整群发成功。

## 90. 2026-09-12 c1001 的发送语义确认

- `c1001` 是本轮实际要发送的目标群编号；“测试群”表示目标范围和授权边界，不表示 dry-run。
- 发送器的 `TEST_ONLY` 是 c1001/act-001/账号槽位的安全白名单闸门，但通过该闸门后仍会执行原生转发、输入文字并点击微信“发送”；只有未启用 `TEST_SINGLE`/`TEST_ONLY` 时才返回 `dry_run`。
- 本轮不把 c1001 改成泛生产范围，也不放开其他群或批次。

## 91. 2026-09-12 按账号串行执行扫描与 c1001 群发

- 03:38 运行确认没有执行 c1001 转发；原因不是把 c1001 当成 dry-run，而是旧统一入口先完成两个账号的扫描，再统一加载发送器，且 native g10 新记录的 `canSend` 为 `None`，PC 会把它们判为待审核并跳过建任务。
- 现在统一入口按两个双开槽位分别执行：当前账号进入“我”页读取真实微信号和昵称，搜索 `g10` 读取全部可见 `groupCode + groupName`，通过 `/api/automation/group-candidates/reconcile` 按微信号写入 PC；本次发现的新 native g10 群默认 `canSend=True`，已有人工 `canSend=False` 不被扫描覆盖。
- 当前账号的扫描和 reconcile 成功后，立即只为该账号创建/领取批次任务，进入“卡片素材群”定位 `act-001`，按 PC 群名映射进入原生多选转发；每次最多 9 个群，超过 9 个分块，完成当前账号后才切换下一个微信账号。
- 原生多选优先使用实时 mode=6 树暴露的目标群选择控件；若选择框未暴露、群名不唯一或页面状态不明，立即截图、记录并停止，不使用固定坐标盲点。明确找不到目标群时，后端保留历史候选记录但设置 `canSend=False`、`membershipStatus=removed`，后续营销任务自动跳过。
- 本轮只完成代码调整，尚未重新同步手机或进行真实微信 UI/后端发送验证；不能把静态检查、代码上传或历史 03:29 成功当作本轮 c1001 闭环成功。

## 92. 2026-09-12 11:53 素材群未观察到滑动与错误详情透传

- 用户 11:53 开始的测试在“卡片素材群(4)”页面报告失败，现场截图只显示统一入口生成的账号级错误 `当前微信账号群发失败：slot=1 account=...`。设备工程元数据显示发送器文件已于 11:50:56 更新，因此该测试不是运行旧版发送器；但本轮运行日志已不可读取，截图本身不能证明 HID 滑动是否发送。
- 源码复核确认发送器可能在 HID 滑动前因卡片标记已识别但卡片动作控件未匹配、素材群/控件树/滑动区域不可确认而停止；入口此前又丢弃了发送器的 `error` 与 `steps`，所以本次失败的确切分支无法从现存证据恢复。不得据此报告“滑动已发送”或推定滑动方向/坐标是根因。
- 已为 `_forward_card` 的停止异常保留最近步骤，并把 `lastError`、最近 8 条失败步骤及阻塞截图路径从发送器摘要传至统一入口错误弹窗；未改变滑动坐标、方向、等待、任务范围或发送行为。
- `automation/ascript/__init__.py` 与 `wechat_marketing_sender/__init__.py` 已通过本地 `py_compile`、`git diff --check`，并上传正式设备工程 `wechat_assistant`；随后只重新运行根入口并确认手机停在九宫格“等待选择”。本轮未启动群发、未点击发送；实际滚动效果和 c1001 UI/后端闭环仍待用户下一次受控测试。

## 93. 2026-09-12 12:23 素材群 HID 滑动未产生可观察滚动

- 本次失败弹窗显示步骤 14 的 `touch_down → touch_move → touch_up` 已调用，坐标为 `(540, 939) → (540, 1905)`；随后等待 1.5 秒、按 0.8 秒间隔读取控件树，`changed=False`。步骤 17 仍只看到 `act-002`、未找到 `act-001`，步骤 18 因没有滚动进展而安全停止。因此本次不是“滑动前门禁拦截”，也不是尚未等待控件树。
- 失败后只读 mode=6 树中没有可用的 `scrollable=true` 滚动候选；现有 `_generic_wechat_gesture_rect()` 因此回退到 15 个宽矩形的并集 `[0,153,1080,2400]`。按该矩形与代码比例计算，得到的正是弹窗记录的起止坐标；这证明本次手势区域来自通用视图并集，而不是已确认的聊天历史滚动容器。
- 主要根因判断：HID 手势调用完成，但手势落点没有使微信聊天历史发生可观察滚动；通用并集可能覆盖卡片内容/其他页面区域，具体是否被卡片子视图拦截仍是推断。等待已达 1.5 秒，当前证据不支持继续增加等待时间。坐标 y 递增，表示手指向下滑；这符合查找更旧消息的预期方向，现有证据不支持将方向判为根因。
- 本轮未改动或同步代码。下一步应移除“宽矩形并集”兜底，只在能从实时树确定聊天历史区域时执行滚动；否则停止并明确提示缺少可验证滚动区域。不得单纯增加循环次数或重复盲滑。

## 94. 2026-09-12 素材群历史滚动区域与 HID 手势修正

- 针对 12:23 失败证据，素材群历史扫描不再使用通用 WeChat 宽矩形并集。滚动区域必须由同一个可见 mode=6 页面中的“卡片素材群”标题、聊天输入框及其共同层级下唯一的 `ListView`/`RecyclerView` 确认，并裁剪在标题与输入框之间；候选不唯一、树缺失或层级不一致时截图并停止。
- 素材群历史滚动改用官方 ESP32 `BleDevice.slide()`（连续 HID 报文、700ms 匀速、30ms 报文间隔）；微信首页导航用的其他 HID 手势未改。调用记录只证明 API 已调用，不视为 UI 已滚动。
- 保持手指向下拖动以查找较早消息；每次滑动后等待 1.5 秒，再以 0.8 秒间隔轮询 mode=6 树。只有实时树发生变化才继续，未变化仍立即安全停止，不增加盲滑次数。
- 本次本地 `py_compile` 与 `git diff --check` 通过；发送器已上传正式设备工程 `wechat_assistant`，远端文件长度为 130418 字节、更新时间 13:11:36。随后 `run_project` 成功，手机截图确认正式入口停在“状态：等待选择”。未点击“群发微信”，没有运行真实扫描或发送；尚无滑动生效、微信 UI 或后端结果验证。

## 95. 2026-09-12 13:20 素材群历史区识别误拦截

- 13:20 现场失败弹窗显示 `ListView/RecyclerView` 候选为 0，步骤 12 的 `scroll=0/12`；本次在滑动 API 调用前已停止。当前树仍可识别可见 `act-*` 消息标记，因此不是 OCR 没识别到编号，也不是高阶 HID 滑动没有执行。
- 与 12:23 记录的“已发送一次 HID 滑动但树未变化”是不同故障：上一轮把历史区门槛收紧为必须存在 `ListView/RecyclerView`，导致微信实际使用普通 `FrameLayout`/`RelativeLayout` 时被误拦截。最近失败可由这次代码回归解释；更早成功运行的具体版本/日志不足以作同版本比较，不改写历史结论。
- 已调整为：优先使用同页唯一列表控件；缺少该语义节点时，仅沿同页可见 `act-*` 控件的父层级找足够大的容器，并严格裁剪在“卡片素材群”标题与输入框之间。若页面锚点、标记父容器或区域仍不唯一，则截图并停止。没有改成纯 OCR；本次失败不是文字识别缺失，OCR 不能提供控件父层级或滚动容器语义。若后续实时树不再暴露 `act-*` 文本，再单独评估 OCR 作为“文字识别”兜底，仍不让 OCR 框直接决定手势坐标。
- 本次变更本地 `py_compile` 和目标文件 `git diff --check` 通过。发送器已同步到正式设备工程 `wechat_assistant`，远端文件长度 134211 字节、更新时间 13:37:47；`run_project` 成功后截图确认根入口为“状态：等待选择”。本轮没有发送滑动或群发动作，修复后的真实设备滚动效果、微信 UI 和后端结果仍待用户受控测试。

## 96. 2026-09-12 13:58 第 1 批启动状态异常

- 正式入口已停在“群发微信”批次选择框；实时树唯一识别到“开始执行”按钮，界面说明首次默认第 1 批。通过正式工程 HID 请求桥提交该实时矩形后，下一次观察到 Android `SystemUI` 通知面板，未出现预期的流程页面；AScript 运行日志为空。
- 只读工程元数据显示 HID 回执文件更新时间为 14:01:25，但 AScript 阶段状态文件仍停留在批次弹窗打开时的 13:56:16；回执正文无法通过当前 AScript 工具读取，本机也没有 `adb`。因此没有证据确认 `batch_selected` 或扫描启动，不能把 HID 请求上传成功等同于点击成功。
- 已停止 `wechat_assistant`，设备状态确认 `is_script_running=false`。现有证据不能确定这次按钮动作是否被界面接收，也不能确定是否已开始扫描；未取得本次扫描、PC 任务、目标群发送或邮件回执结果。
- 不据此修改任何群的营销状态，不登记发送成功，也不改写历史任务记录。当前不能将本轮报告为完整闭环成功；需要先由可观察的正式入口/页面重新确认运行状态，再继续受控测试。

## 97. 2026-09-12 15:53 第 1 批 c1001 / act-001 双目标实机测试

- 用户明确本次 `c1001` 下的“互助群”和“测试群”两个目标都在授权范围；本轮没有扩展到其他 g10 群编号或批次。正式 `wechat_assistant` 工程通过官方 ESP32 HID 启动，批次为第 1 批。
- `wechat-id-gaoshiteng_01` 的定向 `g10` 扫描读取 8 个群并由后端确认更新 8 条；该账号本次队列为 0 个 c1001 目标，未发送。随后 `wechat-id-qq673105954` 扫描读取 47 个群并由后端确认更新 47 条。
- 后端为 leo 创建任务 `automation_task_32a766382e`：`c1001 / act-001`，目标名为“互助群”“测试群”，目标数 2。发送器在素材群滚动后由实时树同时看到 `act-001`、`act-002`，定位 act-001 卡片并记录官方 HID 长按、进入原生转发和打开多选页；日志至少记录到开始按真实群名搜索“互助群”。
- 该任务最终失败，运行摘要为 `processed=1, failed=1, forwardSuccessCount=0, targetResults=[]`。最后错误是 `HID返回后仍未确认微信会话列表：state=child query=`；收尾截图显示仍在微信原生“选择聊天”页、搜索框为 `c1001`、多个同编号候选，且“完成”不可用。由于运行日志工具已不再保留中间选择阶段的完整记录，不能确认最初异常发生在真实群名输入、目标选择还是随后页面状态识别，也不能声称任一目标已发送。阻塞截图已保存在设备：`sdcard/airscript/screen/gp/teamBuy_blocker_task_automation_task_32a766382e_1789199810.jpg` 及 cleanup 截图 `sdcard/airscript/screen/gp/teamBuy_blocker_task_cleanup_automation_task_32a766382e_1789199845.jpg`。
- 合并完成报告日志为 `BATCH_COMPLETION_REPORT status=failed emailSent=True`。已停止正式工程，设备状态确认 `is_script_running=false`。不得将本轮记为转发成功或自动重试；两个目标的逐群后端结果为空，下一次测试前应先修复并核实多选页的目标搜索/选择状态，以及失败时保留原始异常步骤。

## 98. 2026-09-12 16:08 搜索输入核验修复与第二次实机运行

- 针对第 97 节证据，发送器新增硬门槛：搜索输入经 HID 回车提交后，仍须由实时 mode=6 控件树在同一个搜索 EditText 中精确核验预期文本；否则以 `ambiguous` 停止，不得沿用旧的 `c1001` 搜索结果继续点选。目标缺失后的页面复位若失败，异常现在会保留原始目标结果和步骤，并附加复位错误，避免清空失败上下文。
- 本地 `py_compile` 与发送器目标文件 `git diff --check` 通过；只将 `wechat_marketing_sender/__init__.py` 上传到正式 `wechat_assistant` 工程，未覆盖工程 `local_config.py`。
- 第二次正式运行重新完成第一个账号的 g10 定向扫描与 8 条台账同步。切换 `wechat-instance-2` 后，扫描器观察到 `state=child`，未能唯一定位“我”入口，报错“微信首页未出现可唯一定位的‘我’入口，未执行右滑”，并保存截图 `sdcard/airscript/screen/gp/teamBuy_blocker_scan_wechat-instance-2_1789200607.jpg`。失败发生在账号扫描/身份流程，搜索输入修复尚未进入执行。
- 因双账号扫描门槛未通过，本次没有进入发送器、没有创建新的 c1001 任务、没有转发或发送动作。随后已停止正式工程并确认 `is_script_running=false`；现场屏幕仍是卡片素材群上的失败提示，不视为首页复位成功。第二次运行的合并邮件状态未从运行日志中确认，不报告邮件已送达。

## 99. c1001 原生多选转发逻辑（更正）

- 本节先前关于“每个群分别重新打开素材群、单独转发”的描述不符合当前发送器代码，已删除该错误描述。当前实际逻辑是：PC 按微信账号和群编号生成任务，任务携带该账号下匹配的真实群名列表；AScript 按最多 9 个目标分块，在同一个微信原生多选页逐个搜索并选择群名，然后点击一次“完成”、填写批次文字并点击一次“发送”，将同一张卡片和文字发给本块已选目标。
- 已核实的代码行为：PC 返回的目标列表会在 `TEST_ONLY` 下与配置的两个测试群名比对；转发页某个群名在已核验搜索框后仍无结果时，代码会记录该目标并继续检查其他目标。临时测试保护要求 `TEST_ONLY` 的已选目标数必须等于 PC 下发目标数，否则在点击“完成”前停止，不发送部分目标；普通非 `TEST_ONLY` 路径仍保留缺群记录后继续的既有行为。发送动作本身仍标记为未核验送达。
- 以上是当前工作区源码逻辑，不代表手机已同步或本轮真机验证通过。

## 100. 2026-09-12 21:03 素材群入口搜索分支移除与实机重测

- 用户提供的失败截图显示发送器进入微信搜索页后，因“搜索输入框未核验到预期文本：卡片素材群”停止。源码确认 `_open_material_chat_first()` 在首行未确认时主动打开微信搜索；该兜底已移除，改为要求先确认微信会话列表，只允许实时 mode=6 首行控件/该行 OCR 确认“卡片素材群”后点击；首行不匹配时仅在控件树确认的会话行区域执行有界 HID 下滑、等待树变化并重新核验，不再搜索素材群。
- 另外修正群台账扫描器的“我”Tab 目标定位，过滤控件树中不可见页面及不可见祖先。实机运行确认两个微信真实 ID：`gaoshiteng_01`、`qq673105954`；本轮记录的扫描/后台同步为 8 群和 47 群，分别更新 8、47 条。PC 为 `wechat-id-qq673105954` 返回 `c1001 / act-001`，目标“互助群”“测试群”。
- 首次发送尝试发现首页签名读取短暂不一致：`_is_wechat_chat_list()` 未确认，但新页面快照给出 `state=home`，旧逻辑仍把该状态送入未知页停止。已改为将新鲜正向 `home` 快照作为确认，不再对已在首页的界面额外滑动/返回。
- 随后再次从正式 `wechat_assistant` 入口测试：流程未进入素材群搜索页；从会话列表实时行范围发出一次向顶部的 HID 手势后，实时控件树未变化（`scroll=1/24`），系统截图并停止。阻塞截图：`sdcard/airscript/screen/gp/teamBuy_blocker_task_automation_task_59f075eab7_1789218168.jpg`。本轮没有确认点击“卡片素材群”、长按 `act-001`、进入转发、点击发送或后端逐目标成功；最终运行的邮件回执也未确认，不能报告群发闭环成功。
- 群台账扫描器与发送器已通过本地 `py_compile` 和目标文件 `git diff --check`，并同步到正式设备工程；设备上的 `local_config.py` 未覆盖。最终已停止 `wechat_assistant`，`is_script_running=false`。下一步应先核实该账号会话列表首行/滚动手势的实际变化，再继续转发测试；不得在页面状态不明时盲点、盲滑或自动重试。

## 101. 2026-09-12 21:27 素材群入口切换为微信搜索

- 按用户选择，`_open_material_chat_first()` 不再尝试把会话列表滚到顶部；确认微信会话列表后，打开微信搜索、搜索“卡片素材群”，仅接受 mode=6 控件树唯一结果并由官方 ESP32 HID 点击，进入后还要确认搜索框已消失且群聊标题匹配。列表滚动相关辅助函数保留但不再由该入口调用。
- 修正搜索输入核验顺序：先在实时 mode=6 EditText 精确核验；控件树未暴露文本时，仅对控件树定位的输入框矩形做 OCR 状态确认。两者均未确认则停止，不再先发送 Enter 再检查可能已消失的输入框。已确认查询后，优先点击实时树中的搜索按钮；没有该控件时才用 HID Enter 提交。搜索结果仍须唯一且由控件树提供点击矩形。
- 发送器通过本地 AScript `py_compile` 与该文件 `git diff --check`，并已将单个 `wechat_marketing_sender/__init__.py` 上传到设备正式工程 `wechat_assistant`；未上传或覆盖任何 `local_config.py`。
- 同步后 `get_project_files` 确认设备发送器文件长度为 136786 字节，与本地一致；设备为 Android 15 / AScript 4.0.12 / HID，运行状态 `is_script_running=false`。
- 本轮尚未启动正式运行：设备截图 API 返回 Android Bitmap 空引用，mode=6 控件树为空，OCR 也因无截图失败。为避免在页面状态未知时启动扫描或群发，本轮没有读取新的群台账、创建任务、搜索、转发或发送；方案 2 的真机 UI 与后端结果仍待设备观察恢复后验证。

## 102. 2026-09-12 23:07 方案 2 真机测试

- 设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，Wi-Fi 可用；截图与实时控件树恢复。通过正式 `wechat_assistant` 入口和既有控件树矩形 HID 桥进入群发、明确选择第 1 批并启动；没有使用 `eval_python` 或临时入口。
- 两个双开槽位都进入 `g10` 前置扫描流程；slot 0 日志确认扫描到底并稳定结束（8 行、2 次滚动）。slot 1 的“我”页控件树与截图确认微信号 `qq673105954`（昵称 leo），之后也通过前置扫描进入该账号发送器。
- slot 1 为账号 `wechat-id-qq673105954` 创建了 1 个 `c1001 / act-001` 任务，目标数 2、跳过 0；准备定位素材群时，搜索“卡片素材群”的实时 mode=6 树返回 2 个同名结果节点，界面分别处于群聊结果和“搜索网络结果”区域。发送器按唯一结果安全停止，未点击任一结果、未进入素材群、未长按/转发卡片、未选目标群或发送文字；后端逐目标发送结果为空，不能报告群发成功。
- 主阻塞截图：`sdcard/airscript/screen/gp/teamBuy_blocker_task_automation_task_b61dbc18e3_1789225748.jpg`。失败后的首页收尾也未确认，另存截图：`sdcard/airscript/screen/gp/teamBuy_blocker_task_cleanup_automation_task_b61dbc18e3_1789225783.jpg`。统一完成报告接口回执为 `emailSent=True`（收件箱到达未人工核验）；正式工程已调用停止，停止后手机仍停留在搜索结果页。
- 下一步应在实时树中把候选范围限定到“群聊”结果区并排除“搜索网络结果”区，再同步后重新测试；不得仅因同名文本完全一致就按顺序任选一个。

## 103. 2026-09-12 23:46 群聊结果区筛选与转发搜索复测

- 发送器素材群搜索从全页同名控件匹配改为同一份 mode=6 树中的区域匹配：候选必须位于“群聊”标题之后、“搜索网络结果”标题之前；点击矩形也必须落在该群聊结果区。`_group_search_result_rects()` 未改，c1001 目标搜索不受此筛选影响。
- 第一次正式复测中，两个账号的定向 `g10` 扫描和台账更新分别完成：`wechat-id-gaoshiteng_01` 更新 8 条、`wechat-id-qq673105954` 更新 47 条。后者收到 `c1001 / act-001` 任务；新素材群搜索分支通过，进入“卡片素材群”，在历史内容中观察到 `act-002` 并继续查找 `act-001`，随后进入微信原生转发目标搜索。
- 第一次复测没有确认任何目标群被选中或发送。停机时 mode=6 搜索输入框文本为 `c1001互助群`，列表未显示可确认的收件人；日志在页面复位处失败，截图 `sdcard/airscript/screen/gp/teamBuy_blocker_return_home_child_page_1789227227.jpg`。现有运行日志不足以确定该输入值是目标名本身还是旧 `c1001` 查询未清空后拼接；逐目标后端结果和合并邮件回执均未核实。
- 据此给转发目标搜索增加安全条件：HID `clear()` 后必须用可见控件树确认搜索 EditText 为空，最多清空两次；仍非空则截图并停止，不再输入新群名，也不将此类不确定状态标记为群不存在。搜索输入定位与核验同时过滤不可见祖先。
- 上述发送器变更通过本地 `python3 -m py_compile` 和该文件 `git diff --check`，并单文件同步至正式 `wechat_assistant`；`get_project_files` 确认设备端长度 `140017` 字节。未覆盖 `local_config.py`，未使用 `eval_python` 或临时入口。
- 第二次正式复测启动第 1 批后，slot 0（`wechat-id-gaoshiteng_01`）扫描 8 条并更新 8 条；该账号队列为空。slot 1 失败于身份页前置步骤：“微信首页未出现可唯一定位的‘我’入口，未执行右滑”，阻塞截图 `sdcard/airscript/screen/gp/teamBuy_blocker_scan_wechat-instance-2_1789227986.jpg`。双账号前置门槛未通过，slot 1 的发送器未启动；本次清空校验也因此没有设备运行验证。
- 正式 `wechat_assistant` 已停止。当前设备截图仍显示在“卡片素材群”（可见 `act-001`、`act-002`），不视为首页复位成功。两次复测都没有微信 UI 发送确认或后端逐目标成功结果；统一完成邮件是否发送/送达未确认，不能报告群发闭环成功。

## 104. 2026-09-12 转发目标只按真实群名搜索

- 复核转发页代码发现，每次打开微信原生转发目标列表后，曾先输入 PC 内部路由编号 `c1001`，之后才清空并输入真实微信群名。内部编号不是微信群名，不应作为搜索词；该多余预搜索已移除。
- 现在进入转发目标列表后只由 `_search_forward_group_by_name()` 清空并核验搜索框，再输入 PC 任务返回的真实群名（例如“互助群”“测试群”），唯一匹配后才点击。`c1001` 继续只用于 PC 任务路由与结果审计，不进入微信转发页搜索。
- 本次是源码修正，尚未同步或在手机上运行；真实群名搜索、点击、发送和后端逐目标结果仍需正式设备验证。此前成功/失败记录未改写。

## 105. 2026-09-13 新修复正式重试未进入批次

- 本地发送器 `__init__.py` 仅删除转发目标列表打开后对内部编号 `c1001` 的预搜索；本地 `python3 -m py_compile` 与目标文件 `git diff --check` 通过。单文件同步到正式设备工程 `wechat_assistant`，远端发送器长度为 139777 字节；设备 `local_config.py` 长度/修改时间未变。
- 设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，Wi-Fi 在线，电量 37% 且充电，脚本初始未运行。屏幕先显示微信会话列表，顶部可见“卡片素材群”。通过正式 `run_project(name="wechat_assistant")` 显示统一九宫格；实时 mode=2 树唯一识别“群发微信”入口 rect `[60,498,357,927]`。
- 两次按实时矩形向正式入口 HID 请求桥提交点击后，画面均未离开九宫格“等待选择”，没有出现批次选择弹窗。设备端 request/result 元数据有更新，但回执正文无法读取；因此不把请求文件消费或 API 调用视为 UI 点击确认。为避免延迟事件或重复动作，第二次无变化后停止工程；当前 `is_script_running=false`，手机回到微信会话列表。
- 本轮未选择批次、未进入任一微信账号、未扫描 g10、未创建/领取发送任务、未进入素材群、未搜索目标群或发送卡片/文字；无微信 UI 发送确认、后端逐目标结果或邮件回执。因阻塞发生在正式入口点击阶段，`c1001` 仅用于 PC 路由、微信只搜真实群名的修复尚未到达设备执行验证。历史结果未改写。

## 106. 2026-09-13 素材群搜索结果区域 OR 修正

- 本轮手动启动的正式运行已进入素材群搜索步骤。实时截图中，查询词为“卡片素材群”，目标项位于“最常使用”区域，页面下方另有“搜索网络结果”；当前控件树筛选只接受“群聊”区域，故返回 0 个候选，未对搜索结果发送点击。任务 `automation_task_b1e6bc3c77` 失败，`forwardSuccessCount=0`、`targetResults=[]`；失败后回首页也未确认（`state=unknown`）。截图：`sdcard/airscript/screen/gp/teamBuy_blocker_task_automation_task_b1e6bc3c77_1789229948.jpg`，复位截图：`sdcard/airscript/screen/gp/teamBuy_blocker_task_cleanup_automation_task_b1e6bc3c77_1789229983.jpg`。邮件回执未确认。
- `_material_chat_search_result_rects()` 已按 OR 逻辑接受同一份实时 mode=6 树中“群聊”或“最常使用/最近使用”区域的精确群名行；仍以可见区域标题划定边界、排除“搜索网络结果”，只在候选唯一时点击。未改写此前已进入素材群/转发搜索的历史成功记录。
- 本地发送器 `python3 -m py_compile` 与该文件 `git diff --check` 通过。此次修改尚未同步到设备，也未做修正后的真机验证；未使用 `eval_python` 或临时入口。

## 107. 2026-09-13 转发搜索清空后未输入真实群名

- 用户约 00:42 的正式运行停在微信原生“选择聊天”页面。失败日志步骤 53、56 显示转发搜索框发送了两次 HID 清空，随后因控件树未确认空值而停止；群名输入、目标群点击、卡片转发和文字发送均未发生。屏幕截图中的搜索框视觉上为空；不据此改写此前真实群发送成功记录。
- 按用户明确要求，移除转发搜索框的控件树判空与重复清空门禁：官方 `BleDevice.clear()` 后固定等待 0.6 秒，随后直接用 AScript Ime 输入 PC 返回的真实微信群名；此分支不再额外核验输入框文本/提交输入法搜索，直接从实时结果中按真实群名定位。
- 仍保留真实群名结果必须唯一、点击后必须确认原生单群转发预览；后续卡片及附加文字发送逻辑未改。修改通过本地 `py_compile` 和该文件 `git diff --check`；尚未同步到手机或进行真机验证。

## 108. 2026-09-13 c1001 多目标转发流程与页面门禁

- 用户更正：本轮图 2 是用户手动完成的正确流程示例，并非自动化运行到达的页面。自动化失败图和运行步骤显示：真实群名结果已由 mode=6 控件树唯一定位并发出点击；随后旧代码等待“单群转发预览”，因此没有继续搜索任务中的下一个真实群名，也没有到达用户图 2 的后续手动流程。
- 发送器改为每个最多 9 个目标只打开一次卡片原生多选器，按 PC 任务的真实微信群名逐个搜索并选择；选完后只点击一次“完成”，再定位输入框填写并核验文字，最后定位并点击一次“发送”。删除了选择目标后的“单群预览”检查和发送后的“预览消失”检查；保留实时群名行、完成按钮、文字输入框和发送按钮的控件树目标定位，这些用于找动作对象，不用来判断页面是否存在。
- 成功调用发送按钮后只记录 `send_action_sent_unverified`，不把 HID 动作等同于微信 UI/后端送达确认；合并邮件区分“UI确认成功”“发送动作已发出但待确认”和失败。明确找不到的目标仍单独记录，已找到目标可继续在同一次多选中发送。
- 本地 `py_compile`（4 个修改的 Python 文件）、`backend/tests/test_automation_notifications.py`（1 项通过）和对应文件 `git diff --check` 通过。尚未同步手机或进行真实设备运行；当前只能确认代码静态检查，不代表实际选中、发送或后端结果成功。

## 109. 2026-09-13 原生多选按钮解析与多目标核验

- 只读检查设备当前失败画面及 mode=6 树：微信真实按钮显示 `完成(1)`，同时重复暴露为 Button 与重叠 TextView；通用“文本包含完成”定位因此产生多个矩形候选，触发“未唯一定位原生转发完成按钮”。同一份实时树中，筛出可点击 Button 并按矩形去重后仅有一个候选 `[854,121,1037,207]`，计数为 1。
- 发送器改为优先用 mode=6 树的可点击 Button 矩形定位“完成(n)”；OCR 只在树无法读出计数时辅助核验计数，不提供点击坐标。每个目标增加序号/真实群名阶段日志；成功点选后核验多选计数加 1，群不存在仍记录并继续下一个目标，最后汇总已选/缺失数并只点击一次“完成”。
- 已通过发送器 `python3 -m py_compile` 与该文件 `git diff --check`。设备原先 `wechat_assistant` 停留在失败提示且脚本运行标记为 true；同步前已停止该工程，并将单个发送器文件上传至正式工程。设备端文件长度 `146592` 字节，与本地一致；未运行本次修正后的群发链路，真实多群发送仍待用户测试。停止后手机留在微信“选择聊天”原生多选页，显示 `完成(1)`，保留上次已选的一个群；开始新测试前请先取消/退出这张旧选择页，避免沿用旧选择。

## 110. 2026-09-13 03:20 多目标与附加文字复测反馈

- 用户报告本次只看到一个群被选中，随后点击了“完成”，附加文字未输入，也没有发送。AScript 运行日志本轮未收集到；测试结束时设备屏幕可观察到已恢复正式 `wechat_assistant` 九宫格“等待选择”，因此无法从本轮运行证据区分 PC 任务目标数为 1，还是第二个群名未被界面匹配。
- 源码确认：目标任务按每个账号携带 `targets` 列表；每个目标均尝试按真实群名搜索。若群名无匹配，按既有约定记录 `group_not_found` 后继续，最后只对已选目标点一次“完成”；因此只选到一群再完成，可能表示第二群被记录为未找到，并非跳过了目标循环。转发附加文字原先走 `Clipboard.put + ble.paste()`，与搜索文字使用的 AScript `Ime.input()` 不同；发送按钮也要求唯一树匹配。
- 已修正发送器：真实群名结果在控件树未暴露时允许有界精确 OCR 坐标兜底；转发附加文字改为 AScript IME 输入并继续核验；发送按钮树匹配缺失时可用 OCR 兜底，多候选时仅选择与唯一“取消”同一行的发送项，否则仍停止；初始任务步骤会记录目标群名，便于区分 PC 任务缺项与 UI 未匹配。
- 本地 `python3 -m py_compile automation/ascript/wechat_marketing_sender/__init__.py` 与该文件 `git diff --check` 通过。仅将该发送器同步到正式 `wechat_assistant` 工程，设备端长度 148093 字节与本地一致；随后 `run_project` 成功，截图确认停在九宫格“状态：等待选择”。本轮没有启动批次或执行群发，真实第二群选择、附加文字输入、发送按钮及后端结果仍待用户受控实测。

## 111. 2026-09-13 03:32 c1001 单目标发送反馈

- 用户报告约 03:32 测试时有一个群发送成功，但本应配置的两个群中只发送了一个。该反馈尚无本次 UI 收件群确认或后端逐目标回执佐证。
- 只读设备截图约为 03:49，显示微信会话列表；AScript 运行日志接口未返回本次日志。当前本机后台 API 未运行，配置的本地 PostgreSQL 连接也因认证失败不可读，因此未取得本次 `createdCount/targetCount/targets/skipped` 或逐群 `targetResults`。没有据此重跑发送或改动代码。
- 源码显示统一入口按微信账号依次执行；每次入队只查询该账号的候选群，候选最多取 `maxTargets=2`，再跳过 `canSend=False/None` 或已标记 `membershipStatus=removed` 的群。账号范围运行时，发送器测试白名单允许队列只包含配置群名的子集，因此单个可入队目标仍可能正常发送。若队列实际含两个目标，发送器会逐个搜索；明确找不到的目标记为 `group_not_found` 并继续，最终不应汇总为全成功。
- 因缺少本次任务载荷与逐群结果，不能判断是第二群未进入 PC 下发任务，还是进入任务后未找到/未选中。最近一次有设备运行记录的两目标队列见第 102 节；后续扫描可能改变候选账号归属或可营销状态，不据该旧记录替代本次核验。
- 可观测性核对：入队 API 响应的 `tasks[].payload.targets` 有群名，AScript 当场将其打印为 `QUEUE_TASK`；但这只是设备运行日志，本轮 `get_run_log` 返回空。发送器最终 `queue` 与统一邮件的 `queueSummary.accountRuns` 只保留 created/target/skipped 计数，未带群名清单；后台 `create_device_batch_tasks()` 虽在内存中收集跳过群名和原因，返回值只含 `skippedCount`，完成邮件端也不会持久化整份运行报告。后台自动化任务记录本身有任务 payload，但当前本机没有远端 API 地址/查询凭据，本地 API 未运行，PostgreSQL 连接认证失败，故本会话无法读取那笔远端任务。后续若要稳定追责，应把每账号创建任务明细（taskId、目标数、群名）及具体 skipped rows 带入完成报告/持久化运行记录，并在邮件中结构化展示；同时区分 `createdCount`（任务数）和 `targetCount`（群数）。

## 112. 2026-09-13 多目标搜索逐目标记录与同步

- 发送器对 PC 下发的每个目标记录序号/总数、真实群名、搜索框聚焦、清空调用及 0.6 秒等待、AScript IME 输入调用、搜索框核验来源（mode=6 控件树或输入框实时区域 OCR）、结果数、点击矩形与点击前后已选数；这些结构化记录附在对应 `targetResults[].stageTrace` 中，经现有任务结果回传。邮件模板目前不会展开完整 `stageTrace`，未修改后端或邮件渲染。
- 只有真实群名已在搜索框核验后，8 秒内结果为零才记录 `group_not_found` 并继续处理后续群。群名未核验时记为 `search_input_unverified` 并停止本次多选流程，不把它误记为群缺失，也不点击“完成”；已选的其他目标记为未发送。成功点击“完成”及发送动作也会逐目标记录；发送动作本身仍标记为未核验送达。
- 发送器通过 `python3 -m py_compile automation/ascript/wechat_marketing_sender/__init__.py` 与该文件 `git diff --check`；仅上传 `wechat_marketing_sender/__init__.py` 至正式 `wechat_assistant` 工程，设备端文件长度 158558 字节，与本地相同。设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID，上传前后均未运行脚本；本轮没有启动群发或操作微信，修复后的两目标输入、选择、发送及后端结果仍待用户测试。

## 113. 2026-09-13 04:39 多目标测试只观察到一个群

- 用户报告约 04:39 测试时只看到一个群被点选；随后补充确认该群已成功发送，本轮没有错误弹窗截图。此为用户确认的一群发送结果，不代表两个目标均完成；无需再索取本轮错误弹窗截图。
- 该观察尚未附任务详情、运行日志或可读截图，不能单凭此认定 PC 只下发一个目标或第二群输入失败。
- 发送器修复版本在 04:33:28 已同步到正式 `wechat_assistant`（远端长度 158558 字节）。约 04:45 检查时 AScript 显示 `is_script_running=false`；`get_run_log` 未收集到本轮日志，设备截图只有 869 字节、mode=6 控件树为 0 个节点，无法还原测试页面或拦截弹窗。
- 本机未发现可读的本地后端 API 服务；针对 `automation_tasks` 的只读 PostgreSQL 查询因 `teambuy` 用户认证失败而未返回任务。故本轮的 PC `targets` 数、第二群阶段日志和 `targetResults[].stageTrace` 均未能核对。
- 当前发送器分支可区分原因：第二群搜索框文本未核验会以 `search_input_unverified` 停止，不会点击“完成”；搜索框已核验而结果为零则记录 `group_not_found` 并继续，因此可能只选中第一群后再点“完成”。PC 实际只下发一群也是可能情况。只有本轮任务结果/逐群日志可在这些原因间作出区分；本次不据用户观察推断具体原因，也未重跑或修改历史记录。

## 114. 2026-09-13 c1001 双群任务定点修复与同步

- `TEST_ONLY` 的 c1001 任务下发前现在校验本机配置的两个真实群名与 PC 返回的全部任务目标名集合完全一致；若 PC 只下发一个配置群，发送器会在领取/操作微信前失败并记录 expected/actual，不再只发一个目标后继续。每轮日志打印安全的测试群名配置；任务完成/失败日志包含逐目标结果，便于核对第二群是否进入输入、搜索和点选阶段。
- 保持现有规则：已核验群名输入但没有搜索结果时记录该目标并继续其他目标；只有微信明确显示已退群/被移出等提示，才标记群不可用。修正发送器汇总状态中“发送动作未确认”分支的不可达判断。
- 已通过 `python3 -m py_compile automation/ascript/wechat_marketing_sender/__init__.py` 和该文件 `git diff --check`；只将该发送器文件上传到正式 `wechat_assistant`，设备端长度 160455 字节，与本地一致。通过 `run_project("wechat_assistant")` 启动统一入口，设备为用户确认的 nubia NX711J / Android 15 / AScript 4.0.12 / HID，当前停在九宫格。
- 本轮 c1001 测试尚未启动、没有群发动作：launcher 在 mode=2/6 实时控件树中仅暴露不可点击的 WebView，没有可供官方 ESP32 HID 唯一定位的“群发微信”节点；按 HID 专项规则不使用 OCR 坐标点击。需先由用户点一次九宫格“群发微信”，之后可继续检查原生批次对话框并监控运行。

## 115. 2026-09-13 约 05:22 c1001 仍只发送一个群

- 用户报告又测试一次，仍只有一个群发送成功。设备 `192.168.1.237` 当前 AScript runtime 已停止，`get_run_log` 未收集到本次运行日志；观察到的截图只有 869 字节，无法还原当时页面。统一入口状态文件元数据最后修改于 05:31:45，但状态内容不可读。
- 手机发送器文件当前长度为 160455 字节，远端修改时间为 05:24:38；用户估计测试在约 05:22，早于该同步时间，但时间为近似值且入口状态元数据较晚，故无法确定这笔测试实际加载了新旧哪版代码。
- 当前版 `TEST_ONLY` 会在微信操作前要求 PC 任务目标名集合等于配置的两个群名；若使用该版且配置正确，PC 只下发一群应在发送前失败。另一方面，逐群流程在搜索框文字已核验、但 8 秒内结果为零时会记录该群并继续发送已选群；如果这是新版本运行，单群成功更符合“第二群搜索无结果后被跳过”，而不是“第二群输入未核验”（后者会停止并且不会点完成）。以上是代码路径推断，不是本次运行事实。
- 本次没有足够日志区分队列只含一群、第二群搜索无结果或运行版本；没有据此改代码、重跑或改写历史成功记录。下一次有日志时需以 `QUEUE_TASK` 和第二个 `targetResults[].stageTrace` 的输入核验/结果数/选中数为准。

## 116. 2026-09-13 06:49 c1001 复测前增加 TEST_ONLY 全目标保护

- 发送器新增临时保护：`TEST_ONLY` 下若实际选中数少于 PC 本次下发目标数，在点击“完成”前停止并回传逐目标结果；本地 `python3 -m py_compile automation/ascript/wechat_marketing_sender/__init__.py` 与目标文件 `git diff --check` 通过。仅将发送器同步至设备 `wechat_assistant/wechat_marketing_sender/__init__.py`，未覆盖设备 `local_config.py`。
- 通过正式 `run_project("wechat_assistant")` 运行并选择第 1 批。指定设备为 nubia NX711J / Android 15 / AScript 4.0.12 / HID；运行日志确认官方 ESP32 `AS_4.8_905DDCBA2010` 已连接。两个账号的定向 g10 扫描均成功，`wechat-id-gaoshiteng_01` 更新 8 条、`wechat-id-qq673105954` 更新 47 条。
- 第一账号的 c1001 队列为空。第二账号返回任务 `automation_task_f08478dbdf`（`c1001 / act-001`），但 `BATCH_RUN_QUEUED` 是 `createdCount=1, targetCount=1, skippedCount=1`，`QUEUE_TASK` 仅含“测试群”。因此本轮没有得到预期的“互助群、测试群”双目标；目标数在微信多选之前就已是 1，无法验证“两个目标下发但只选中一个时禁止完成”的新保护，也没有继续让单群进入发送。
- 停止时设备仍在“卡片素材群”，画面可见 `act-002`；AScript `is_script_running=false`。没有观察到转发选择页、“完成”或发送后的聊天页；由于没有可读的任务完成/失败回执，不将本轮记作发送成功，也不声称后端已记录任务失败。`skippedCount=1` 的具体群名和原因未由运行日志输出，需从 PC 端候选资格/设备运行响应中核实。

## 117. 2026-09-13 15:35 卡片转发收尾与多分块复用修正

- 更正上一轮口头同步说明：当时重新上传的是 `wechat_assistant/__init__.py` 入口文件；发送器文件没有同步，因此发送器中的卡片转发复位修复并未随该次上传到手机。此前关于“三次右滑已上线”的说法不准确，本条更正不改写任何历史测试结果。
- 发送器首页识别现在优先接受 mode=6 树中明确选中的“微信”Tab；如果该构建没有正向 Tab 选中标记，则要求底部“微信/我”Tab 与顶部搜索入口同时出现，并排除搜索输入框及“通讯录/发现/我”页面标题。复位等待要求连续两次首页签名，减少单帧旧树造成的误判。
- 原生卡片发送成功后的收尾单独使用官方 ESP32 HID，最多从实时 WeChat 内容矩形左侧向右滑到中部三次；每次动作后等待并复读 mode=6 树，稳定确认首页即停止。此路径只用于卡片转发完成后的收尾；其他页面保留原有导航方式。超过 9 个目标时，成功分块之间等待 1.2 秒并优先复用当前素材群直接长按同一张卡片；只有实时标题/搜索控件显示已离开素材群时才重新定位。
- `python3 -m py_compile`（正式入口、发送器）通过；`backend/tests/test_ascript_sender_logic.py` 为 16 项通过；AScript、测试文件和两份状态/决策文档 `git diff --check` 通过。
- nubia NX711J / Android 15 / AScript 4.0.12 / Wi‑Fi `192.168.1.237` / HID。当前正式工程两个代码文件均已上传：`__init__.py` 32,876 字节、`wechat_marketing_sender/__init__.py` 176,907 字节，与本地大小一致。设备 `is_script_running=false`。本轮没有启动脚本或执行群发；三次复位、两分块连续转发和后端/微信结果仍待用户手动实测。

## 118. 2026-09-14 两阶段扫描与 c1001 同名群选择

- 用户报告约 03:12 的流程观察为：先扫描一个微信的 `g10/c10`，再扫描另一个微信，之后回到第一个微信执行卡片素材群转发。最新本地入口此前实际是“扫一个账号后立即启动该账号发送器”，与用户观察及希望的“两个账号先扫描、再分别发送”不一致。
- 用户截图显示微信原生“选择聊天”页有两个同名“测试群”结果，分别显示 4 人和 5 人，按钮为“完成(1)”。这是截图能证明的事实：两个同名结果可见、当前选中数为 1；截图不能证明 PC 本次任务下发了几个候选。
- 本轮无法取得与 03:12 运行绑定的 PC `QUEUE_TASK/targetCount` 或发送器阶段日志；设备运行日志没有收集到该次记录，故不能确认后台本次是否下发两个独立候选，也不能把截图直接归因为第二目标搜索失败。后端服务代码和既有测试表明：候选 ID 不同且群身份记录可区分时，同名群可作为两个目标入队；这不是本次运行结果证据。
- 本地代码已改为两个账号扫描和 reconcile 全部通过后，才按槽位 0、1 启动独立发送器；发送阶段通过实时双开选择器重新选槽，并在进入素材群前再次核验真实微信号。重名目标仍按 PC 下发数量一次搜索；每次点选前重读 mode=6 结果矩形，点击后核验“完成(n)”递增，数量不符或计数未递增时不点击“完成”。
- 本地验证：AScript `py_compile` 通过；发送器逻辑与群候选队列目标测试 `44 passed`；`git diff --check` 通过。本轮未同步手机、未启动工程、未执行微信扫描或群发；新流程及设备上的同名选择行为仍待正式 AScript 工程受控验证。

## 119. 2026-09-14 更正发送器调度

- 更正第 118 节中“本地入口此前是逐账号扫描后立即启动发送器”的判断：用户指出既有流程已经是扫描阶段与发送阶段分开，本轮不应重构扫描调度。上一版入口新增了“每个账号分别调用一次发送器”的路径；这与 `TEST_ONLY` 一次领取并校验双账号完整目标集合的门禁冲突，现已撤回该逐账号调用，恢复为两个账号扫描/reconcile 完成后只运行一次发送模块，并向其传递完整扫描结果和账号集合。
- 同名群的实时重读结果矩形与“完成(n)”递增核验仍保留。发送槽位在统一发送器运行时由稳定账号 ID 映射到双开槽位，并继续核验微信真实号。
- 设备没有保留这次“未扫描”运行日志；因此不能仅凭当前证据断言扫描未执行的具体原因。本地静态检查与单元测试通过不等于手机链路已成功。

## 120. 2026-09-14 c10“更多群聊”扫描与同名群点选修正

- 针对用户约 10:36 的反馈修正两个发送前问题：第二个微信搜索 `c10` 后未点击“更多群聊”，以及原生多选页出现两个同名“测试群”但只选中一个。
- 扫描器现在从实时 mode=6 控件树的可见 text/desc/contentDesc 节点读取“更多群聊”自身矩形，并兼容“更多群聊(n)”等带数量文案；只有唯一矩形才通过官方 ESP32 HID 点击。缺少或出现歧义时，记录 `TARGET_MORE_GROUPS_LINK_UNCONFIRMED` 并将该前缀视为不完整，不再把首屏结果当成完整扫描或放行发送。
- 同名群初始结果数仍须与 PC 下发的同名目标数一致。每次选择前重读控件树；如果微信隐藏已选行，可按“剩余未选行数”从当前第一项继续；每次点选后仍必须确认“完成(n)”恰好加 1，否则停止，不点击“完成”。
- 本地定向回归测试 `backend/tests/test_ascript_inventory_logic.py` 与 `backend/tests/test_ascript_sender_logic.py`、AScript `py_compile` 和 `git diff --check` 已通过。此次仅修改本地代码与当前决策/状态说明；未同步手机、未运行微信扫描/群发，以上只表示本地实现及检查通过，实际设备行为仍待测试。

## 121. 2026-09-14 两个 AScript 模块同步至正式手机工程

- 将本地 `wechat_group_inventory/__init__.py`（92,521 字节）和 `wechat_marketing_sender/__init__.py`（187,723 字节）上传到 nubia NX711J / Android 15 / AScript 4.0.12 / HID 的正式 `wechat_assistant` 工程；设备文件清单回读长度与本地一致。
- 未覆盖统一入口 `wechat_assistant/__init__.py` 或两个模块的 `local_config.py`；同步后脚本状态仍为 `is_script_running=false`。本轮没有启动自动化、扫描微信或发送消息，也没有部署后端；修复后的实机行为仍待用户测试。

## 122. 2026-09-14 c10 无“更多群聊”入口的正常结束修正

- 用户约 11:37 的邮件日志显示：`gaoshiteng_01` 的 `g10` 扫描成功读取 8 群；`c10` 页面有 1 个可见群，但没有“更多群聊”入口。扫描失败是上一轮新增的“入口缺失即失败”逻辑导致，任务未生成（`runIds=[]`），发送器没有启动；这不是群发器或 PC 创建任务接口报错。
- 已更正扫描分支：实时树唯一找到“更多群聊”时点击并继续滚动；等待后没有该入口时，将当前可见群行作为该前缀完整结果正常结束（包括零行）；只有入口多于一个、无法安全区分时才停止。保留兼容“更多群聊(n)”及 text/desc/contentDesc 的实时树定位。
- 本地定向测试、AScript `py_compile` 与 `git diff --check` 通过后，本地状态记录更新；本修正尚未同步手机，也未运行扫描、创建任务或发送。此前第 120 节记录的是修正前策略，不代表当前行为。

## 123. 2026-09-14 c10 扫描修正同步至手机

- 用户要求同步后，设备当时仍报告 `wechat_assistant` 正在运行且未收集到运行日志；先停止该残留工程，再上传扫描器文件，避免覆盖运行中的工程。
- 仅同步 `wechat_group_inventory/__init__.py` 到 nubia NX711J / Android 15 / AScript 4.0.12 / HID 的正式 `wechat_assistant` 工程。设备回读长度 93,030 字节；统一入口 37,387 字节、发送器 187,723 字节及两个 `local_config.py` 长度均保持不变。
- 同步后设备 `is_script_running=false`。本轮没有启动脚本、执行扫描/群发或部署后端；设备上的 c10 无“更多群聊”入口分支仍待用户手动测试。

## 124. 2026-09-14 12:07 同名测试群逐个重搜与点选

- 用户反馈约 12:07 的测试仍无法分别定位两个同名“测试群”，并明确要求：搜索群名、读取并点击一个结果；随后重新聚焦搜索框、再次搜索同一群名，再定位并点击另一个结果。
- 发送器原先对同名目标只搜索一次，再逐个刷新结果矩形；这没有在每次点选后恢复搜索框焦点并重做查询。现改为按不同 `candidateId` 逐个重新聚焦、清空、输入并核验群名，再读取本轮结果矩形点击；每次仍以“完成(n)”恰好递增作为点选成功条件。
- 每轮结果数仅接受“仍显示全部同名行”或“WeChat 隐藏已选行后恰为剩余行数”两种情况；其他数量变化、焦点或输入无法核验都停止，不使用固定坐标。不同候选仍分别对应 PC 目标。
- 本地验证为 AScript 语法编译、发送器逻辑定向测试及差异空白检查通过后记录；本次只改本地发送器、回归测试和当前规则，没有同步手机、启动脚本、扫描或发送。设备端行为仍待用户手动测试。

## 125. 2026-09-14 同名微信群路由包部署与手机同步

- 后端微信群自动化源文件已部署到生产 API、backend-worker、archive-worker 三个镜像：`domain.py`、`schemas/automation.py`、`services/automation_control_service.py`、`api/routes_automation.py`。PostgreSQL、数据卷、环境变量及其他业务模块未改。
- 部署备份位于 `/home/ubuntu/teambuy-backups/20260914-150009`，三个旧镜像均保留 `rollback-20260914-150009` 标签。定向后端测试 `56 passed`；部署后 API、两个 worker 均 healthy，内网数据库检查及公网 `https://teambuy.lifelove.top/health` 通过，容器内模型/schema/API 路由导入通过。
- 已将本地扫描器（94,357 字节）和发送器（192,393 字节）上传到 nubia NX711J / Android 15 / AScript 4.0.12 / HID 的正式 `wechat_assistant` 工程。设备回读长度吻合，统一入口和 `local_config.py` 未覆盖；设备 `is_script_running=false`。
- 本轮没有启动 AScript，没有运行微信扫描、选择同名群或实际发送。因此当前状态是后端已部署、手机代码已同步，端到端行为仍待用户手动测试，不能报告群发成功。

## 126. 2026-09-14 后端模型热修复及正式 AScript 工程完整同步

- 重新核对发现：生产 API、backend-worker、archive-worker 的 `domain.py` 仍为旧版（哈希 `8553303b…`），而此前新模型/schema 相关部署中该文件没有进入运行镜像；本次只热修复 `backend/app/models/domain.py`，三个容器内哈希均与本地 `4b7408fc…` 一致。其他后端文件此前已与本地一致，未重复改动。
- 部署前已备份 Compose 与三个容器中的旧模型文件至 `/home/ubuntu/teambuy-backups/20260914-154222`，旧 API/worker/archive 镜像保留 `rollback-20260914-154222` 标签。未触碰 `.env`、PostgreSQL、数据卷或媒体目录。
- 部署后 API 与两个 worker 均 healthy；内网 `/health`、数据库健康检查及公网 `https://teambuy.lifelove.top/health` 通过，API 容器已成功导入带 `groupOccurrenceCount` 的新模型。
- 对正式 `wechat_assistant` 一次上传入口、`res/ui/launcher.html`、扫描器、发送器四个文件；设备文件清单长度分别为 34,639、4,935、94,357、192,393 字节，与本地一致。nubia NX711J / Android 15 / AScript 4.0.12 / HID 上 `is_script_running=false`。未启动脚本，未执行微信扫描或群发；仍需用户手动验收，不能视为端到端成功。

## 127. 2026-09-14 15:58 群候选已同步，发送被 TEST_SINGLE 白名单拦截

- 只读查询生产 `automation_group_candidates`：15:56:37 更新了 `wechat-id-gaoshiteng_01` 的“小说素材”，群编号 `c1001`、`canSend=true`、`groupOccurrenceCount=1`；15:58:15 更新了 `wechat-id-qq673105954` 的“测试群”“互助群”“Python 资料”“👸公主说的都对”，均为 `c1001`、`canSend=true`、`groupOccurrenceCount=1`。这些行的 `membershipStatus=unknown`，不等于营销关闭；此次扫描未把它们标为 `removed`。
- 15:58:32 的 `automation_task_8a7d68be34` 状态为 `failed`，错误为“单次测试任务含有未列入白名单的群：Python 资料、👸公主说的都对”。发送器本地 `TEST_SINGLE` 白名单校验在进入微信素材群 UI 前拒绝了这两个目标，因此没有开始卡片转发；这是发送未启动的直接原因，不是候选未写入 PC。
- AScript `get_run_log` 未收集到本次日志；复查时设备仍报告正式工程 `wechat_assistant` 正在运行。未操作或停止设备。历史运行记录未改写。

## 128. 2026-09-14 移除 AScript 端静态收件群名单

- 针对第 127 节的实际失败，发送器不再读取/校验本地 `TEST_GROUP_NAMES`、`TEST_GROUP_NAME` 或 `TEST_GROUP_CANDIDATE_IDS`；`TEST_SINGLE` 与 `TEST_ONLY` 都不会因 PC 新增的同编号目标名称或候选 ID 而拒绝整笔任务。
- 测试任务仍以本地配置的 c 群编号限定队列范围，并保留账号槽位、账号归属、卡片/批次格式等校验；目标名单由 PC 任务及 PC 端营销/成员资格筛选决定。测试任务请求不再被本地 `maxTargets=2` 截断，上限为 1000；原生转发仍按每次最多 9 个目标分块。
- 验证：定向发送器测试 39 项通过，AScript 语法编译及相关差异检查通过。2026-09-14 16:57 已只同步正式手机工程 `wechat_assistant/wechat_marketing_sender/__init__.py`；设备文件 189,801 字节，与本地一致。同步前确认 nubia NX711J / Android 15 / AScript 4.0.12 / HID 且脚本未运行；同步后再次确认脚本仍未运行。未启动脚本、未扫描或发送。
- 本次修复仅变更 AScript 发送器，不包含后端代码变更，因此没有后端版本需要部署；工作区中其他未提交后端改动未纳入部署。未来 g10 生产发送不由本次变更启用，仍须遵循单独的生产运行策略。
- 第 127 节保留当时的失败事实，不回写历史记录。

## 129. 2026-09-14 c 测试同名群实时数量高于 PC 记录

- 17:10 邮件运行 `android-01-1789377202976` 中，扫描阶段成功，发送队列有 4 个 PC 目标；微信搜索“测试群”实时返回 2 行，而本轮发送器从 PC 任务展开后仅有 1 个同名目标（日志 `expected=1 allowed=(1,) observed=2`），因此原有 fail-closed 检查在点击前停止。这是 PC/扫描计数低于实时可见数量触发的保护，不是搜索框未输入或长按卡片失败。
- 发送器现在仅对明确的 `TEST_SINGLE`/`TEST_ONLY` c 编号测试，允许精确群名实时行数补足 PC 低报的同名目标；每个新增选择项仍重新读取当前矩形并核对微信“完成(n)”递增。单个原生多选仍最多 9 个，超限停止；生产路径仍按 PC 数量严格校验。新增日志会记录 PC 数、实时行数及扩展数。
- 定向发送器测试 41 项通过，AScript `py_compile` 与相关 `git diff --check` 通过。已于 2026-09-14 17:27 将发送器同步到 nubia NX711J `192.168.1.237` 的正式工程 `wechat_assistant`；手机文件 194,811 字节，与本地相同。同步前后 runtime 均为停止；没有运行手机脚本或真实群发，不能据静态验证认定端到端通过。

## 130. 2026-09-14 统一入口持久记录完成邮件回调

- 统一入口将发送器或扫描器返回的完成通知结果写入 `.wechat_assistant_status.json` 的 `completionReport` 字段，记录运行编号、回调是否发起/返回、通知和邮件的 `sent` 值、失败原因及安全的错误类型；后续 `run_stopped_after_batch` 阶段更新会保留该字段。
- 回调异常仅持久化错误类型，不保存请求头、凭证或原始邮件内容。若设备端只显示最终阶段但未收到邮件，可据 `completionReport.reason`、`emailSent` 与 `errorType` 区分未配置、回调失败、邮件未发送或结果缺失。
- 本次仅修改 AScript 入口、两个通知返回错误类型及入口回归测试；已将正式工程 `wechat_assistant` 的 `__init__.py`（39,233 字节）、`wechat_group_inventory/__init__.py`（94,590 字节）和 `wechat_marketing_sender/__init__.py`（195,048 字节）同步到 nubia NX711J（192.168.1.237），设备文件长度回读一致，且 `is_script_running=false`。本补丁没有后端源码变更，因此未部署后端；未启动设备脚本或执行群发，邮件回调落盘仍待下一次运行验证。

## 131. 2026-09-14 最新测试完成邮件回调被后端校验拒绝

- 设备运行 `android-01-1789390572536` 的 `.wechat_assistant_status.json` 已持久记录：`phase=run_stopped_after_batch`、`reportStatus=unverified`、`requestAttempted=true`、`notifierResultAvailable=true`、`emailSent=null`、`errorType=HTTPError`。
- 生产 `teambuy-backend-1` 在 20:58:09（上海时间）记录 `POST /api/automation/runs/complete` 返回 HTTP 422；只读检查生产 Pydantic 字段确认 `status` 仅允许 `success/degraded/failed`，不含设备提交的 `unverified`。FastAPI 请求校验在路由函数执行前拒绝请求，故邮件服务没有被调用；不是 SMTP 已尝试后发送失败。后端 `/health` 与数据库状态正常。
- 当前完成邮件不是独立队列：接口通过校验后在同一请求中同步调用 SMTP。下一步最小修复是让后端接受语义明确的 `unverified` 状态（并补接口测试、部署）；若要求邮件与回调彻底解耦，则需另做持久队列/outbox。本轮只诊断并记录，未改代码、部署或重启设备。设备 runtime 仍报告脚本运行中，虽状态文件已是终态；未停止现场进程。

## 132. 2026-09-14 完成邮件改为持久任务队列（本地实现，未部署）

- `/api/automation/runs/complete` 现在接受设备报告的 `unverified`，并将完整报告写入 PostgreSQL 共用的 `sync_tasks` 持久队列；接口不再同步等待 SMTP。`automation-completion-email` 由后台 worker 执行，SMTP 失败最多重试 5 次，最终状态和安全错误原因保存在任务及任务日志中。
- 使用 `deviceId + runId` 派生幂等任务 ID，设备重试同一完成回调不会重复排入邮件；任务报告留在队列 payload，队列日志只记录任务类型，不复制完整报告。
- `unverified` 422 是上一笔邮件未发出的直接原因：FastAPI 在调用邮件服务前拒绝请求。此处修复校验契约，并增加队列去重与完成回调回归测试。邮件投递采用持久化的至少一次处理语义；若 SMTP 已接受邮件后进程恰在任务标记成功前崩溃，重试理论上可能造成重复邮件。
- 本地全量后端测试 `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests -q` 为 461 项通过，`git diff --check` 通过；尚未部署后端，也未检查或操作手机。线上可靠投递需在部署后确认 API 与 `backend-worker` 使用同一数据库且 worker 健康，并查看 `automation-completion-email` 任务终态。

## 133. 2026-09-14 完成邮件持久队列后端部署

- 已基于生产运行镜像做定点热修复，只部署 `routes_automation.py`、`dependencies.py`、`schemas/automation.py`、`sync_task_queue.py`、`repository.py` 五个后端文件；未把工作区其他未提交改动或本地 Compose 文件带入生产。
- 部署备份位于 `/home/ubuntu/teambuy-backups/20260914-mail-outbox`，API、backend-worker、archive-worker 旧镜像分别保留 `rollback-20260914-mail-outbox` 标签。`.env`、数据库卷、媒体目录未触碰。
- 部署后 API、两个 worker 与 PostgreSQL 均 healthy；内网 `/health`、`/health/db` 和公网 `https://teambuy.lifelove.top/health` 通过。容器内确认 `unverified` schema 合法、后台 worker 已注册 `automation-completion-email`，三个运行容器中的五个文件 SHA-256 一致。
- 未调用真实完成回调，避免创建伪运行记录或触发测试邮件；下一次设备运行需检查持久任务最终状态及实际收件情况。本轮只部署后端，没有同步或操作手机。

## 134. 2026-09-14 23:46 左右运行的完成邮件队列已成功处理，但用户未收到

- 生产后端于 23:47:40 收到设备 `android-01` 的完成回调并返回 HTTP 200；持久队列任务 `sync_task_7e0b04cb1d8a93a3c7f3d88fcb11349a57c3cc7b` 对应运行 `android-01-1789400744578`、批次 1，报告状态为 `unverified`。
- 队列任务在 23:47:41 进入 `success`，`attempts=0/5`，结果为 `configured=true, sent=true`。生产邮件配置已启用，收件地址脱敏为 `25***@qq.com`，SMTP host/from 均已配置。由此可排除本次回调未到达、任务未入队或 worker 重试失败；应用记录只能证明邮件发送调用未抛异常，不能证明最终进入收件箱。
- 生产运行代码与本地邮件通知服务 SHA-256 一致。`send_automation_completion_email()` 未保存 SMTP 的服务端投递回执/Message-ID，因此当前无法从队列追踪最终投递、退信或垃圾邮件归类。AScript 在 23:52 仍报告 `wechat_assistant` 运行中，但这与已完成的邮件队列任务是分离状态；本次未重发邮件或操作设备。
- 本轮通过生产 PostgreSQL 只读复核同一 outbox 行：23:47:40.228 入队，23:47:40.270 / 23:47:40.593 / 23:47:41.566 依次记录 `queued/running/success`；最终 `result.email` 仅含 `configured=true, sent=true`，`errorMessage` 为空。对应时窗 API 与 worker 容器日志没有额外的 SMTP/邮件/该 taskId 记录。
- 生产 SMTP host 为 QQ SMTP。按 Python `smtplib` 正常返回语义，结合当前单收件人的邮件，这次调用未抛异常表示 SMTP 事务接受了该收件人并完成 DATA 阶段；但应用没有持久化返回值或 Message-ID，异常也被折叠为通用 `smtp_send_failed`，任务日志没有 SMTP 拒绝码/回复文本。当前可访问工具中没有 QQ/腾讯邮箱投递记录连接器，本轮没有查到 QQ 侧投递、退信或收件箱记录；因此不能确认最终邮箱投递或退信。下一步需检查发件 QQ 邮箱/服务商的该时段发送或投递记录，以及收件箱、垃圾箱和退信通知；之后应以稳定 Message-ID 和不含明文地址的收件人指纹关联记录。

## 135. 2026-09-15 完成邮件增加按微信账号的群推送统计

- 邮件正文新增独立“账号推送统计”区块，按账号列出计划推送数、收到结果数、UI 确认成功数、发送动作待确认数、失败/未发送数和结果未回报数；“发送动作待确认”不计为成功，页面收尾异常也不计为目标群失败。
- 统计优先读取完成报告中的 `queueSummary.accountRuns`，没有该字段时按 `forwardSummary.targetResults[].wechatAccountId` 回退，并用扫描报告中的账号补齐零目标账号。相同群名在手机端扩展出的物理目标按逐条结果计数，同时保留计划目标与收到结果的区别。
- 本地验证：`PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests/test_automation_notifications.py -q`（4 项通过）；邮件通知服务 `py_compile` 和相关 `git diff --check` 通过。此次仅修改本地邮件渲染与测试，未部署、未发送测试邮件。

## 136. 2026-09-15 修复统一入口未执行 scanOnly 门禁

- 对抗式审查确认：PC 的 `scanOnly=true` 原先只在独立 `TEAMBUY_PREFLIGHT_ONLY` 路径生效；统一九宫格入口会清除该环境变量，扫描后仍加载发送器并调用 `device-run`，因此只扫描配置不能阻止创建/领取发送任务。
- 统一入口现在把每个扫描结果的 `scanConfig.scanOnly` 合并为不可清除的运行状态；双账号扫描完成后若该开关为真，直接写入 `scan_only_completed`、标记队列 `skipped=scan_only_configuration` 并跳过发送器。完成报告带上脱敏的扫描配置，仍通过原有唯一完成通知路径发送。
- 新增纯逻辑回归测试覆盖开关粘性与报告配置；本地全量后端测试 `PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests -q` 为 463 项通过，AScript/邮件服务 `py_compile` 与 `git diff --check` 通过。尚未同步手机、部署生产或运行真实扫描/群发。

## 137. 2026-09-15 完成邮件记录 SMTP 接受/拒绝摘要

- 对抗式审查确认 `smtplib.send_message()` 的收件人拒绝字典原先被忽略，可能把 SMTP 已拒绝收件人误记为 `sent=true`。
- 邮件服务现在为同一 `deviceId + runId` 生成稳定 Message-ID，返回收件人短指纹、`smtpAccepted` 和安全的拒绝码/回复文本；异常返回错误类型与截断后的安全错误，不记录完整收件地址或凭证。SMTP 无拒绝时的 `sent=true` 仍只表示服务器接受本次 SMTP 事务，不表示最终进入邮箱。
- 新增拒绝回归测试；本地全量后端测试更新为 464 项通过。未部署生产、未发送测试邮件；相关代码已在提交 `515029e` 中推送到当前 GitHub 功能分支。

## 138. 2026-09-15 最终验收审查与鸿蒙边界

- 对抗式审查发现并修复两项可造成误判的缺陷：统一入口原先忽略 PC `scanOnly` 门禁；邮件服务原先忽略 `send_message()` 的收件人拒绝字典。当前代码已分别在 `515029e` 与前一提交中覆盖，并通过 464 项后端测试。
- AScript 设备发现本轮只找到一台 Android-237（Android/Wi-Fi）；本地 AScript 平台 API 概览只有 Android、iOS、Windows，没有 HarmonyOS 平台入口。仓库没有鸿蒙执行模块，`automation/ascript/res/ui/launcher.html` 第 2 格仍为禁用“鸿蒙适配”占位。因此本轮没有鸿蒙运行/控件树/HID 证据，不能报告鸿蒙兼容或通过。
- GitHub 远端 `gst0102/teamBuy` 的 `codex/version-protection-20260629` 已与本地同步，当前 HEAD 为 `a0fb59c`；未推送 `main`。鸿蒙二期需要先确定 HarmonyOS 自动化运行时、设备和控件/HID 通道，再定义独立适配层与验收用例。

## 139. 2026-09-15 发送器 dry-run 门禁前移

- 对抗式审查确认：`TEST_MODE` 为空时，发送器原先仍先调用 `device-run` 创建任务，之后才在素材群前停止；这会制造无意义的生产任务记录。
- 发送器现在在队列创建前要求 `TEST_SINGLE` 或 `TEST_ONLY`，其他模式直接返回 `degraded`、`production_send_disabled`，不创建或领取发送任务；原有素材群前安全门禁继续保留作为第二道保护。
- 新增发送模式回归测试；本地全量后端测试更新为 465 项通过，AScript 语法编译通过。尚未部署生产或运行手机群发。

## 140. 2026-09-15 SMTP 异常文本脱敏补强

- SMTP 发送异常写入 outbox 结果前统一移除收件地址、SMTP 主机、用户名和密码，仅保留截断后的安全错误文本、`errorType`、Message-ID 和收件人短指纹；这样既能定位失败类型，也不会把敏感配置带入任务结果或日志。
- 新增异常脱敏回归测试；本地全量后端测试为 466 项通过，相关 Python 语法检查通过。代码已推送当前 GitHub 功能分支，未部署生产、未发送测试邮件。

## 141. 2026-09-15 验收前 SMTP 拒绝语义与扫描失败兜底

- `SMTPRecipientsRefused`（全部收件人被拒绝）现在与 `send_message()` 返回的拒绝字典统一记录 SMTP 拒绝码/安全回复；普通连接异常的 `smtpAccepted` 改为 `null`，表示客户端无法判断服务器是否已在 DATA 阶段接受，避免把不确定状态写成确定拒绝。
- 拒绝回复和异常文本统一移除收件地址、SMTP 主机、用户名、密码及发件地址；PC 扫描配置请求失败时预先使用安全的 `scanOnly=false` 默认值，保留原始配置错误并停止流程，不再因二次 `NameError` 覆盖根因。
- 定向邮件测试 8 项、后端全量测试 468 项通过；AScript 相关模块语法检查通过。未发送测试邮件、未操作手机、未部署生产。
- 截至本节记录，GitHub 远端 `gst0102/teamBuy` 的功能分支 `codex/version-protection-20260629` 已同步到 HEAD `89e275c`；当时工作区干净，未推送 `main`。

## 142. 2026-09-15 延长群发任务租约

- 发送器领取包含多个原生分块的群发任务时，将租约从 120 秒提高到接口上限 900 秒，避免正常长批次在完成回执前过期并被再次领取。超过 15 分钟的极长批次仍存在租约风险，二期应增加受控续租接口或更细任务分块；本次未引入复杂续租框架。
- 相关 AScript 语法检查和后端全量测试通过；未启动手机群发、未部署生产。

## 143. 2026-09-15 新 Android 设备同步群扫描与群转发脚本

- 新设备 `192.168.1.71:9096` 已通过 AScript 连接，识别为 HONOR MAA-AN10、Android 15、HID 模式；设备原先只有空白 `test` 工程，运行状态为停止。
- 在设备上新建 `wechat_assistant` 工程并上传统一入口、九宫格 UI、`wechat_group_inventory/__init__.py` 和 `wechat_marketing_sender/__init__.py`；四个文件回读长度分别为 41,556、4,935、94,810、196,305 字节，与本地一致。
- 未复制任何本地 `local_config.py`、设备令牌或其他敏感配置，也未启动脚本、扫描微信群或执行群转发。新设备要做后端联调，需在设备端补齐其专用运行配置；本次同步仅证明代码文件完整。

## 144. 2026-09-15 新 Android 设备 16:27 测试状态

- 新设备状态文件在 16:27:43 写入 `phase=run_stopped_after_batch`；完成报告为 `reportStatus=failed`，`requestAttempted=false`，`notificationSent=false`，`emailSent=null`，原因 `backend_not_configured`。这证明统一入口实际启动并走到终态，但没有向后端发起完成回调，也不会产生 outbox 邮件任务。
- 只读收集 5 秒和 15 秒 AScript 日志均无输出；设备运行接口仍报告 `is_script_running=true`，与终态文件不一致，当前不能据此认定脚本仍在执行。未自动停止、重启或重新运行设备。
- 直接原因是新设备工程未配置运行时 `local_config.py`；代码文件已同步，后端地址、设备令牌、账号/测试参数仍需在新设备端按其专用配置补齐后才能做端到端测试。
