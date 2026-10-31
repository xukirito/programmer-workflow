---
description: 把一件事写入用户记忆或工作区记忆
---

用户要求记住：$ARGUMENTS

按 `programmer-workflow` 的记忆协议处理：

1. 先判断范围。用户没说是“用户记忆（全局）”还是“工作区记忆”时，必须问，不要猜。
2. 显式指令可直接写 active；你的推断只能写 proposed。
3. 用 `companion.py memory add --host <当前宿主>` 或 `memory propose --host <当前宿主>` 写入，带 kind、text、evidence。
4. 复述：存到哪一层、原文、id、如何删除（`memory forget <id>`）。
5. 不要把密钥、密码、个人信息写进记忆。
