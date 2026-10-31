# Ask protocol — options plus free-form

Use this whenever the user must decide, approve, or disambiguate. The goal is a decision, not an interview.

## Decide vs ask

Ask only when the answer changes what you do next. Decide yourself when:

- the choice is low-impact and reversible;
- the user already stated a preference (active memory or current message);
- one option is clearly safer and the user asked you to handle it.

Ask when:

- scope is ambiguous (user vs workspace memory, whole repo vs subdir);
- a change is destructive or runs code;
- two approaches have materially different cost/risk;
- the user is vague about the goal or aesthetic direction;
- you are about to override active memory because the current instruction conflicts.

## Shape

- One decision per question. At most 3 questions per turn.
- 2–4 concrete options. Each option gets a one-line consequence.
- Put the recommended option first and append `（推荐）`.
- Always allow free-form: `其他（我来说明）`.
- Do not use “是否继续？” when there is a real trade-off; name the trade-off.
- After the answer: `已按「X」处理；下一步 Y。`

## Host mapping

| Host | Preferred mechanism | Notes |
|---|---|---|
| DSH | `ask_user_question` tool with `questions[].options[]` | Options are `label` + `description`; the user can still answer freely |
| Claude Code | `AskUserQuestion` tool | Supports multi-select; keep labels short |
| Kimi Code | Use the host's structured question/confirmation UI if available | Otherwise numbered list in chat |
| Cursor | Numbered list in chat | No stable structured question tool to rely on |
| Codex | Numbered list in chat | Use the host's prompt mechanism if one is available |
| Generic | Numbered list + “其他” | Always make it copy-paste friendly |

If a host tool rejects more than N questions or options, split into two turns rather than dropping the free-form option.

## Text fallback

```text
我需要你定一下：<一句话问题>

1. <选项 A>（推荐）— <代价/收益>
2. <选项 B> — <代价/收益>
3. <选项 C> — <代价/收益>
其他：直接说你想要的方式。

你选哪个？
```

For approvals:

```text
<变更摘要，2–3 行>
1. 通过（推荐）— 我继续下一步
2. 只改其中一条 — 你指出编号
3. 先不执行 — 我保留方案
其他：告诉我怎么调。
```

## Scenario templates

### Memory scope (request 7)

```text
这条要记到哪一层？

1. 用户记忆（全局，推荐）— 以后所有工作区都遵守
2. 工作区记忆 — 只在这个项目里生效
其他：你描述使用范围。
```

If the user says “remember” but the statement is project-specific (“这个仓库用 pnpm”), recommend workspace. If it is about communication (“先给结论”), recommend user.

### Habit approval (request 1)

First ask how to review:

```text
我根据最近的文件和对话归纳了 5 条习惯。你想怎么处理？

1. 逐条审核（推荐）— 我一次列出，你保留/修改/删除
2. 全部保留 — 我直接写入生效记忆
3. 全部不保留 — 只保留扫描报告，不写记忆
4. 稍后 — 先不动
其他：告诉我保留哪几条。
```

If逐条: show a compact numbered table with evidence and confidence, then ask the user to reply with keep/change/delete numbers. Do not write active until they answer.

### Debug option (request 3)

```text
这个 bug 已经试了 2 次还没修好。下一步怎么走？

1. 加最小日志 + 自动运行 + 分诊（推荐）— 需要你批准运行命令
2. 只加日志，不自动运行 — 我给你命令，你本地跑
3. 先静态分析/最小复现 — 不改代码，先缩小范围
4. 需要实机/硬件 — 我列操作清单，你回传结果
其他：你指定方向。
```

### Docs scope (request 5)

```text
这次总结覆盖多大范围？

1. 整个工作区（推荐）— 架构与功能都出
2. 只总结一个子目录/模块 — 你指定路径
3. 只出架构，不出功能 — 先看结构
其他：描述范围。
```

### Prototype direction (request 6)

```text
我先做 2–3 个方向的原型，你想先看哪种差异？

1. 信息密度：指挥台 vs 纸感工作台（推荐）
2. 品牌气质：克制内部工具 vs 有辨识度的产品
3. 平台：桌面优先 vs 移动优先
其他：描述你想要的风格或参考。
```

If the user already gave a style reference, skip this and state your interpretation.

## Anti-patterns

- Ten questions in one turn.
- “可以吗？” with no consequence.
- Options that are synonyms (“方案 A / 方案 A'”).
- Hiding the recommendation to appear neutral.
- Asking for permission to add logging in a workspace the user already declared dev-only/no-hardware.
- Asking scope when the user explicitly said “用户记忆” or “这个项目”.
- Treating a free-form answer as consent to a different option.
