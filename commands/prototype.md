---
description: 为 UI/美术/模型需求生成 Prototype.html
---

按 `programmer-workflow` 的原型协议，为以下需求生成 `Prototype.html`：$ARGUMENTS

要求：

1. 最多问 3 个澄清问题（平台、受众、必须保留的内容、风格约束）；用户说“你决定”时先列假设。
2. 给 2–3 个在信息架构与视觉语言上真正不同的方向，不要只换颜色。
3. 写 `design.json`，用 `companion.py prototype --host <当前宿主> --spec design.json --out Prototype.html` 渲染。
4. 原型是静态视觉方向，不是成品；HTML 里不能有 script/iframe/内联事件。
5. 告诉用户打开 Prototype.html，可切换方向/视口、在画布上标注、导出评审 JSON。
