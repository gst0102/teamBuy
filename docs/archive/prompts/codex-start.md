# Codex Start Prompt

请先读取以下文件：

- `AGENTS.md`
- `docs/project-memory.md`
- `docs/decisions.md`
- `docs/pitfalls.md`
- `docs/dev-log.md`
- `docs/handoff-latest.md`

然后读取当前 Git 状态：

```powershell
git status --short --branch
git diff --stat
```

先不要改代码。

请先输出：

1. 你理解的项目目标
2. 当前代码状态
3. 已确认的重要决策
4. 当前风险
5. 下一步建议执行顺序

要求：

- 不要依赖聊天上下文。
- 不要把未提交内容当作已完成。
- 不要删除或覆盖用户/其他 Codex 产生的未提交改动。
- 等用户确认理解无误后，再开始具体开发或修复。
