---
description: 生成 plan.md 或 plan.html，等待用户审核后再执行
---

按 `programmer-workflow` 的 `workflowMode` 协议处理：$ARGUMENTS

1. 先收集证据，不修改源码、不运行项目命令。
2. 把计划写成 `.programmer-workflow/plan.json`，至少包含 `title`、`goal`、`steps`；每步写清变更、命令、风险、验证和回滚。
3. 按设置里的 `planFormat` 生成 `plan.md` 或 `plan.html`：
   `python "<skill>/scripts/companion.py" plan --host <当前宿主> --spec .programmer-workflow/plan.json`
4. 给出文件绝对路径和 3–5 行摘要，询问：`执行（推荐）` / `修改：...` / `取消`。
5. 只有用户回复 `执行` 后才开始操作；`full-authority` 下普通运行不需要逐条批准，但破坏性操作仍需确认。`--yes` 与 `--full-authority` 不能同时使用。
