# Plan mode — write the plan, wait, then execute

Plan review is a **plugin workflow policy**, not the host's permission system.
The host decides whether the session can edit files or run commands; this skill
only decides whether it should write a reviewable plan first.

## Workflow mode

`workflowMode` is a per-host enum:

| Value | What the agent does |
|---|---|
| `plan` (default) | Ordinary runs need approval. Do not edit or run project commands while planning; inspect evidence, write `plan.md` or `plan.html`, summarize it, and wait for `执行`. After approval use `run --yes`. |
| `full-authority` | Ordinary runs do not need per-command approval. Use `run --full-authority`. Still confirm destructive operations, credentials, publishing, deletion, and anything that leaves the workspace. |

`--yes` and `--full-authority` are mutually exclusive. Obvious destructive
commands are blocked in both modes. The setting does **not** change DSH/Kimi/
CodeBuddy permissions; a host Plan/read-only/sandbox restriction still wins.
Legacy `requireRunConsent=false` is not a promotion to full authority; an old
config without `workflowMode` loads as `plan`.

If the user has not chosen a mode and the host has no reliable mode API, ask once:
`这次用 Plan 模式还是 Full authority？` Do not claim the page detected the host
mode, and do not infer Full authority from a vague “继续”.

## When to generate a plan

Generate a plan when any of these is true:

- `workflowMode=plan`, or the host is in Plan/read-only;
- the user asks “先给方案 / 计划 / 怎么做”;
- the change spans multiple files, a migration, a dependency, or an external system;
- the change cannot be undone with a single revert;
- the agent is unsure about scope, credentials, data location, or test strategy.

Skip the plan for a one-file typo, a read-only lookup, or an explicitly approved
small fix in Full authority.

## Workflow

1. Gather evidence first: `map`, manifests, entry points, tests, current git state.
2. Write a plan spec to `.programmer-workflow/plan.json` (inside the workspace).
3. Render:
   - Markdown (default): `plan --spec .programmer-workflow/plan.json --format md`
   - HTML: `plan --spec .programmer-workflow/plan.json --format html`
   - Or omit `--format` to use the Settings value `planFormat`.
4. The output is `plan.md` or `plan.html` at the workspace root unless `--out` says otherwise.
5. Show the absolute path and a 3–5 line summary. Ask one approval question:
   - `执行（推荐）`
   - `修改：...`
   - `取消`
6. Do not run project commands or edit source while waiting.
7. On `执行`, execute the plan in order. Re-check each command's effect; stop and
   ask if reality diverges. In `plan` mode use `run --yes` after approval.
8. In `full-authority`, use `run --full-authority` for routine commands; omit both
   flags only when you intentionally want the CLI's interactive consent prompt.

## Plan spec

```json
{
  "title": "short title",
  "goal": "one sentence",
  "context": "evidence and constraints",
  "mode": "Plan mode / 待审核",
  "assumptions": ["..."],
  "steps": [
    {
      "title": "step title",
      "change": "files or behavior changed",
      "command": "exact command, optional",
      "why": "why this step is needed",
      "risk": "low|medium|high",
      "verify": "how to know it worked"
    }
  ],
  "verification": ["test or check"],
  "rollback": "how to undo",
  "questions": ["only real blockers"]
}
```

`steps` is required. Keep it to 24 steps. A plan is a snapshot; regenerate it
after the user changes scope.

## Format choice

- `plan.md`: best for CodeBuddy, Kimi Code, git review, and copy into a PR.
- `plan.html`: best for visual review; has checkboxes, copy buttons, and a clear
  “回复执行” gate. It is still only a review artifact — it cannot approve itself.

## Host notes

- **CodeBuddy**: project-level `.codebuddy/skills` + `CODEBUDDY.md`; put `plan.md`
  at the project root so CodeBuddy's plan review flow sees it.
- **Kimi Code**: plugin install; plan file at the project root; use the same
  `planFormat` setting.
- **DeepSeek Harness**: Plan mode / Full authority is chosen by the host. The
  Settings page only explains the plugin behavior; it does not grant authority.
