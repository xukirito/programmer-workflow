---
description: 生成 Architecture.html 与 Features.html
---

按 `programmer-workflow` 的工程文档协议，为当前工作区生成：

- `docs/Architecture.html`
- `docs/Features.html`

范围：$ARGUMENTS

要求：

1. 先运行 `companion.py map --host <当前宿主> --workspace .` 并阅读关键文件；结论附证据路径。
2. 写 `docs/spec.json`（architecture + features），不要手写 HTML。
3. `companion.py docs --host <当前宿主> --spec docs/spec.json --check` 校验，再渲染。
4. 不要编造模块/功能；证据不足就放到 `questions` 并标注置信度。
5. 完成后告诉用户用浏览器打开这两个文件，底部可提交评审并导出 JSON。
