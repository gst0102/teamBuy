# 阶段二文档包 README

## 1. 文件说明

本目录是 teamBuy 阶段二：文档/任务生成 的交付物。

文件列表：

| 文件 | 说明 |
|---|---|
| `01-product-plan.md` | 产品规划、用户场景、MVP 范围、不做清单 |
| `02-task-breakdown.md` | 任务拆解、目录结构、模块拆分、开发里程碑 |
| `03-tech-spec.md` | 技术栈、真实接入策略、mock 策略、安全合规要求 |
| `04-acceptance.md` | 页面、功能、数据、性能、安全、上线验收标准 |
| `05-resource-list.md` | 资源清单、官方文档、mock 数据、资源标准 |
| `06-data-structure.md` | 核心实体、TypeScript 类型、JSON 样例、字段说明 |
| `codex-prompt.md` | 阶段三交给 Codex 的启动任务说明 |

## 2. 如何使用

进入阶段三前，开发 Codex 必须先读取：

```text
AGENTS.md
stage1-thinking/05-stage2-input-brief.md
docs/stage2-docs/01-product-plan.md
docs/stage2-docs/02-task-breakdown.md
docs/stage2-docs/03-tech-spec.md
docs/stage2-docs/04-acceptance.md
docs/stage2-docs/05-resource-list.md
docs/stage2-docs/06-data-structure.md
docs/stage2-docs/codex-prompt.md
```

如果需要进入 QA 流程，AI 测试官必须读取：

```text
AGENTS.md
docs/stage2-docs/04-acceptance.md
skills/qa-acceptance/SKILL.md
```

## 3. 阶段流转方式

```text
阶段一：Thinking 商讨
  ↓
stage1-thinking/
  ↓
阶段二：文档/任务生成
  ↓
docs/stage2-docs/
  ↓
阶段三：代码落地执行
  ↓
backend/ + miniprogram/
```

阶段三推荐按里程碑执行：

1. 初始化项目
2. 生成 mock 数据
3. 实现后端导入聚合
4. 实现小程序核心页面
5. 实现查看统计和接龙
6. 接入真实企业微信和小程序能力
7. 自测和 QA 验收

## 4. 阶段二完成检查

- [x] 产品规划完整
- [x] MVP 范围清晰
- [x] 页面和模块清晰
- [x] 任务可执行
- [x] 技术规格可落地
- [x] mock 和真实接入边界清晰
- [x] 资源清单明确
- [x] 数据结构明确
- [x] 验收标准可逐项检查
- [x] 已生成给 Codex 的启动任务说明
