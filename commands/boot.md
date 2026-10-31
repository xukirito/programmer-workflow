---
description: 加载 Programmer Workflow，读取生效记忆与待审核条目
---

加载 `programmer-workflow` skill，并执行它的会话启动协议。

1. 运行 `companion.py boot --host <当前宿主> --workspace .`；宿主未设置时用 `PROGRAMMER_WORKFLOW_HOST`。
2. 只把 **active** 记忆当作规则；报告待审核数量，但不要把它们当规则。
3. 如果 active 记忆与用户当前要求冲突，先问保留哪一条。
4. 用 3–5 行汇报：生效的用户记忆、生效的工作区记忆、待审核数量、需要用户现在决定的事。

$ARGUMENTS
