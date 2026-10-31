# Memory — user, workspace, approval

Memory keeps habits and workspace facts across sessions. It is deliberately simple: one JSON file and one rendered Markdown file per scope, plus one approval gate.

## Scopes

| Scope | Location | Belongs there |
|---|---|---|
| User (global) | `<host-home>/programmer-workflow/memory` for the selected host | Communication style, language, answer structure, tool preferences, “always/never” rules that apply across projects for that host |
| Workspace | `<workspace>/.programmer-workflow/` (configurable in settings) | Project conventions, architecture decisions, environment facts, commands, “this repo is dev-only / no hardware” |

Hosts are independent: DSH uses `<DSH_HOME>`, Kimi uses `<KIMI_HOME>`, CodeBuddy uses `<CODEBUDDY_HOME>`, etc. A non-DSH command must not fall back to `~/.dsh`. Old shared memory is imported once (with conflict checks), not read as a background fallback. Workspace memory belongs to the project and never moves with a host/plugin migration.

A workspace root is the nearest ancestor containing `.git` or `.programmer-workflow`; otherwise the current directory. Override with `--workspace`; select the host with `--host`/`PROGRAMMER_WORKFLOW_HOST`.

## Files

- `memory.json` — structured entries, including proposed/rejected audit history.
- `MEMORY.md` — rendered active + proposed; the model reads this at boot.
- `memory.lock` — short-lived write lock.
- `README.md` — local explanation.

Only `active` entries are obeyed. `proposed` entries are suggestions that need the user. `rejected` entries are kept for audit but never rendered as rules.

## Entry schema

```json
{
  "id": "u-20261031-a1b2c3",
  "status": "active",
  "kind": "habit",
  "text": "沟通使用中文，代码、命令和报错保留原文。",
  "detail": "不要翻译 stack trace；必要时给中文解释。",
  "evidence": ["用户多次要求保留原文", "README 为中文"],
  "confidence": 0.9,
  "source": "conversation",
  "tags": ["language"],
  "created_at": "2026-10-31T14:00:00+08:00",
  "updated_at": "2026-10-31T14:00:00+08:00",
  "approved_at": "2026-10-31T14:01:00+08:00"
}
```

Kinds: `workflow`, `habit`, `preference`, `convention`, `environment`, `decision`, `fact`, `reminder`.

## Status machine

```text
propose ──accept──▶ active ──forget──▶ deleted
   │                  │
   ├──reject──▶ rejected
   └──edit────▶ proposed
```

- Inferred habit → `proposed` only.
- Explicit “记住” → may be `active` after scope is confirmed.
- User-stated environment fact → `active` immediately (request 4).
- Promotion workspace → user always creates `proposed` at the user scope.

## What to store

Good:

- “先给结论，再展开证据。”
- “Python 项目用 4 空格；不引入第三方依赖。”
- “这个工作区是纯开发环境，没有硬件；调试直接加日志。”
- “我不喜欢在回复里重复我说过的话。”
- “提交信息用中文，格式 `类型: 摘要`。”

Bad:

- Secrets, tokens, passwords, private keys, cookies, customer data.
- A single accidental preference (“这次用英文”) turned into a global rule.
- Unverifiable psychoanalysis (“用户有完美主义”).
- Duplicated entries with different wording; dedupe or supersede.
- Temporary task state (“正在修 bug #42”); use the task/plan, not memory.

## Conflict rules

1. The user's current instruction wins.
2. If current instruction contradicts active memory, ask which to keep. Options: update memory / ignore memory this time / keep both with a scope note.
3. If two active entries conflict, prefer the newer one and propose superseding the older; ask the user before deleting.
4. If memory is stale (old project, changed stack), say so and offer `edit`/`forget`.

## Habit harvest (request 1)

### Evidence sources

- Project files: indentation, line endings, naming, comment language, docs language, test layout.
- Tooling: `.editorconfig`, Prettier/ESLint, Ruff, clang-format, CI, commit conventions.
- Git history: commit language/style, branch naming, recent subjects.
- Conversation: **only with explicit consent**. Default `scan` does not read transcripts.
- User's own statements: the strongest evidence.

### Procedure

1. Say what you want to scan and why; ask consent if transcripts are involved.
2. `scan --out .programmer-workflow/scan.json`.
3. Read the scan, not the whole repo. Pick 3–8 candidates that are repeated and actionable.
4. For each: text, evidence, confidence, suggested scope.
5. Write `proposed`.
6. Present a compact review; let the user accept/edit/reject.
7. Report active entries and storage paths.

### Heuristics

- Repeated across files + config + commits → higher confidence.
- One file or one session → low confidence, probably not a habit.
- Contradictory evidence (mixed indentation) → do not propose a rule; propose “follow each file's existing style”.
- Prefer behavioral rules over vague adjectives.
- A habit should change future behavior; if it does not, it is trivia.

## “Remember” (request 7)

If the user says “记住…”:

1. If scope is explicit, use it.
2. If not, ask: user (global) vs workspace.
3. If the statement is a clear instruction, write `active`; if it is your inference, write `proposed`.
4. Restate: text, scope, id, how to remove.

Examples:

- “记住我不喜欢 emoji” → user, active, kind `preference`.
- “记住这个项目用 pnpm” → workspace, active, kind `convention`.
- “记住我刚才说的那个思路” → ambiguous; ask what exactly to store and which scope.

## Environment facts (request 4)

When the user states:

- pure development environment, no deployment;
- no hardware / cannot connect a device;
- sandboxed/offline machine;

run:

```bash
python "<skill>/scripts/companion.py" env set --host <host> --dev-only --no-hardware --reason "用户说明"
```

This writes an active workspace `environment` entry and prints the implications. Do not ask again in this workspace. If the user later says hardware is available, add a new entry and mark the old one superseded.

## CLI

```bash
memory init --scope all
memory show --scope all --status all
memory propose --scope user --kind habit --text "..." --evidence "..." --confidence 0.8
memory review --scope all
memory accept <id> --scope user
memory reject <id> --scope workspace
memory edit <id> --scope user --text "..."
memory forget <id> --scope user
memory promote <workspace-id>
memory status
```

IDs are prefixed `u-` (user) or `w-` (workspace); prefixes are accepted if unambiguous.

## Boot format

`boot` prints a compact block with only active entries plus pending counts. If there is no memory, it says so. Do not dump the whole `MEMORY.md` into the chat unless the user asks.

## Privacy

- Memory is local; never upload it.
- Do not store full conversation transcripts in memory.
- When quoting evidence, use short excerpts and redact names/secrets.
- Offer export/delete when the user asks what is stored.
