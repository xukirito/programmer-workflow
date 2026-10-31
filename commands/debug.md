---
description: 进入调试流程（加日志、运行、分诊）
---

按 `programmer-workflow` 的调试协议处理：$ARGUMENTS

要求：

1. 先判断是否已经多轮未修复；必要时 `companion.py stall status --host <当前宿主> --track bugfix`。
2. 给出选项：加日志+自动运行+分诊 / 只加日志 / 静态分析 / 需要硬件。
3. 若工作区已被声明为纯开发/无硬件：不要问是否加日志，直接加最小可回滚日志并给定位步骤；确认环境记忆已写入。
4. 运行任何命令前取得用户同意；用 `companion.py run --host <当前宿主> --yes -- <command>`。
5. 运行后 `companion.py triage <log> --host <当前宿主>`，一次只验证一个假设。
6. 修复后补回归测试、删除或关闭临时日志，并报告改动的文件。
