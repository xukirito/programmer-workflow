# Stall escalation and vague requirements

Request 2: after repeated failure, stop guessing and bring in outside structure. The point is not to apologize; it is to change the search space.

## When to trigger

Count **substantive attempts**, not clarifying questions or tool retries.

Triggers:

- 3 attempts and the user still says it is wrong/not what they meant;
- explicit dissatisfaction: “还是不行”, “不对”, “不是这个意思”, “你怎么还没…”, “算了”;
- the same bug survives 2 fixes (also bump `bugfix`);
- you notice you are repeating a variant of the same approach.

Do not trigger:

- the user is adding new requirements;
- one failed test that you immediately diagnosed;
- a clarification round where the user changed the scope.

You can persist a counter:

```bash
python "<skill>/scripts/companion.py" stall bump --host <host> --track satisfaction
python "<skill>/scripts/companion.py" stall status --host <host> --track satisfaction
python "<skill>/scripts/companion.py" stall reset --host <host>
```

Thresholds: satisfaction 3, bugfix 2. Counters expire after 8 hours without activity.

## Immediate move

1. **Stop editing.** No “let me try one more thing” without a new hypothesis.
2. Write a 3-line status:
   - goal (what the user actually wants);
   - attempts (what you tried and what happened);
   - unknown (the one thing you cannot explain).
3. Ask for a direction (see `ask.md`):
   - industry-standard approach;
   - instrumented debugging;
   - re-interpret the requirement;
   - reduce scope / change approach.
4. If the user chooses industry practice, do the research before proposing code.
5. If the user chooses debugging, follow `debugging.md`.
6. Reset the counter after a direction is chosen and verified.

## Industry escalation

### Infer the industry

Look at, in order:

1. the user's own wording and examples;
2. repo domain: dependencies, schemas, device files, compliance terms;
3. docs/README, issue titles, variable names;
4. recent conversation topics.

If confidence is low (< 0.6), ask. Do not present a generic list of ten industries; use 2–4 candidates drawn from the evidence plus “其他”.

```text
我从工程里看到 STM32/串口/固件目录，猜是嵌入式/工业设备。对吗？

1. 工业自动化 / 嵌入式（推荐）— 我会按设备生命周期、现场可维护性来讲
2. 消费电子 — 更重视成本、功耗与量产
3. 其他行业 — 你说明，我换一套做法
```

### Industry practice card

For each approach:

```markdown
### <名称>
- 业界通常怎么做：<2–3 句，具体到方法/模式/工具>
- 适用条件：<什么时候值得>
- 代价与风险：<时间、复杂度、迁移成本、团队要求>
- 在这个项目里第一步：<一个可验证的小动作>
- 证据/来源：<文件、标准、文章；没有就写“基于通用实践，需验证”>
```

Then recommend one and say why. Keep it to 3 approaches. If you used web research, cite URLs; if not, label the advice as general practice.

## Vague requirements: interpretation card

Do not code from a vague feeling. Produce a card and ask the user to confirm/edit:

```markdown
## 我理解的目标
<one paragraph>

## 用户与场景
- 谁：
- 什么时候用：
- 成功是什么样：

## 约束
- 平台/技术：
- 时间/成本：
- 不能动的部分：

## 我的假设（请确认或否定）
1. ...
2. ...

## 非目标
- ...

## 验收标准
1. ...
2. ...

## 可选路线
A. ...（推荐）— 代价
B. ... — 代价
```

Rules:

- Separate “你说的” from “我推断的”.
- Make assumptions falsifiable and numbered.
- Include a non-goal; it prevents scope creep.
- Ask one question: “这张卡哪里不对？直接改编号也行。”
- Do not implement until the user confirms, unless they explicitly said “按你的假设先做”.

## Worked example: repeated wrong UI

Situation: three attempts at a settings page; user says “不对，太挤了”.

Bad: reduce padding again.

Good:

1. Stop.
2. Status: goal = settings usable on 13" laptop; attempts = 3 layouts; unknown = whether “挤” means spacing, density, or too many fields.
3. Ask: “挤”指哪一种？(A) 留白不足 (B) 一屏字段太多 (C) 分组不清 (D) 其他.
4. If B: interpretation card with “split into basic/advanced; keep 6 fields visible”.
5. Prototype two variants (dense vs progressive disclosure), let the user pick.

## Worked example: repeated backend bug

Situation: two fixes, same 500.

1. Bump `bugfix`.
2. Offer instrumentation vs static analysis.
3. If instrumentation: add one log at the boundary and one at the failing branch, run, triage.
4. If the log shows the input is already malformed, the bug is upstream; change the hypothesis, not the patch.
5. After fix: regression test + cleanup.

## Anti-patterns

- Apologizing and trying again with no new information.
- Asking “你具体想要什么？” with no options.
- Dumping a textbook of industry practices without choosing.
- Treating a vague answer as approval.
- Resetting the counter without a verified fix.
