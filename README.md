# teamBuy

teamBuy 的正式产品方向是“资料整理助手”：把企业微信、微信、手动输入、图片和链接中的内容整理成可编辑、可检索、可分享的资料卡，并按房源、团购、服务、电子名片等场景提供工作台能力。

## 当前入口

- 当前状态：[docs/CURRENT.md](docs/CURRENT.md)
- 当前决策：[docs/decisions-active.md](docs/decisions-active.md)
- 历史文档索引：[docs/archive/README.md](docs/archive/README.md)
- AScript 专项规则：[automation/ascript/AGENTS.override.md](automation/ascript/AGENTS.override.md)
- 小程序代码：`miniprogram/`
- 后端代码：`backend/`

## 开发前

```bash
git status --short --branch
git diff --stat
```

然后阅读根目录 `AGENTS.md`、`docs/CURRENT.md` 和 `docs/decisions-active.md`。历史文档只有在需要追溯具体实现时才从 `docs/archive/` 查阅。

## 基础检查

```bash
PYTHONPATH=.:backend ./.venv313/bin/python -m pytest backend/tests
```

小程序体验版上传和真机验收由用户在微信开发者工具中完成。
