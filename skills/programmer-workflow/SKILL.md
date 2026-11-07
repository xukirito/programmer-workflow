---
name: programmer-workflow
description: Persistent user/workspace memory with approval; 3-round stall escalation to industry practices; instrumented debugging with log triage (incl. dev-only/no-hardware); interactive docs/Architecture.html + docs/Features.html on architecture/feature summary requests; Prototype.html for UI/art/model direction. Use when asked to remember, when stuck, when a bug persists, or when summarizing/designing. 记忆、卡壳、调试、架构总结、原型评审。
---

# 程序员工作流 / Programmer Workflow

A review-first workflow for coding agents. Keep state outside the chat, make every inferred rule user-approved, and turn “stuck” into a concrete choice.

## Non-negotiables

- **Active memory is obeyed; proposed memory is not.** Treat only `status=active` entries as rules. Never silently promote a proposal.
- **The current instruction wins.** If memory conflicts with what the user just said, ask which to keep; do not argue from memory.
- **Evidence before confidence.** Every architecture/feature/habit claim gets a file path, command, or user statement. Mark inference as inference.
- **Reversible changes.** Debug logging and docs are temporary or reproducible; report what changed and how to undo it.
- **No secrets in memory, logs, docs, or HTML.** Redact tokens, passwords, private keys, customer data, and full personal paths when sharing.
- **Ask with options plus free-form.** Use the host's structured question tool when present; otherwise use a short numbered list. See `references/ask.md`.
- **Plan mode is a review gate, not a global approval tax.** In Plan mode, write `plan.md` or `plan.html` and wait for `执行`. In Full authority, proceed without approval for routine work; still confirm destructive or irreversible operations.

## Resolve paths

Let `<skill>` be this skill's directory (the host shows it when loading; Kimi expands `${KIMI_SKILL_DIR}`). Use:

```bash
python "<skill>/scripts/companion.py" <command> --workspace .
```

On Windows use `python` or the bundled runtime; quote paths with spaces. If Python is unavailable, tell the user and degrade to the text protocols in `references/`; never pretend a command ran.

## 0. Session start

1. If the host auto-loads this skill (Kimi `sessionStart`, bootstrap block), continue. Otherwise load it when a trigger matches.
2. Run `boot --host <current-host> --json` (or `boot`), or set `PROGRAMMER_WORKFLOW_HOST` first. Read active user memory and active workspace memory, plus the `workflow`/`devOnlyDirect` policy from boot.
3. If memory is uninitialized, that is fine; do not create entries yet. Mention that memory can be enabled when a habit or fact appears.
4. If pending proposals exist, mention the count once and offer to review them; do not block the current task.
5. Apply active entries silently unless they conflict with the current request.

## 0.5 Environment and commands

`boot` now includes a compact environment line from the workspace cache. The cache is
`<workspace>/.programmer-workflow/environment.json` and is mirrored into one active workspace
`environment` memory entry. It records the local OS, shell, GUI availability, and installed
commands; it never executes the probed commands.

- First time in a workspace, run `env probe` once (boot does it automatically when the cache is
  missing). Do not probe every turn.
- Before constructing a command, run `env check <command>` (or let `run` preflight it). If the
  command is missing, do **not** retry it: use an installed alternative printed by the check,
  install it, or ask the user.
- `run` checks the executable **before** consent/spawn, so a missing tool never creates a log
  directory or a failed retry loop.
- If the user explicitly names a different OS (Windows vs Linux), never execute that command on
  the local machine. Output the target OS's commands; `run --target-os <os>` and
  `env check --target-os <os>` refuse cross-OS execution.
- Environment facts are workspace memory, not global user memory: switch projects and the cache
  does not follow.

## 0.6 Screenshot / model vision / clipboard

Triggers: `/screenshot` (DSH direct command), `/截图` (Kimi/chat), or the user asks to read text from a specific app/window/screen.

> DSH's slash-command parser only accepts `[a-z][a-z0-9_-]*`; use `/screenshot` there. Kimi/command-file
> hosts can expose the Chinese command, and a plain “截图” message is handled by this skill.

1. If the user explicitly invoked the command and named the target, consent is already given.
   If you inferred the need, ask once: “是否截图并把图片复制到剪贴板？”.
2. Run:
   `python "<skill>/scripts/companion.py" screenshot --host <host> --target "<window title or 屏幕>" --yes`
   Add `--list` when the window name is unknown. The command captures the target and copies the PNG.
   It never invokes Windows OCR, Tesseract or another local OCR engine.
3. In an Agent-driven flow, read the saved PNG with the host's image/media tool and transcribe the
   requested text with the model. Preserve languages and punctuation; mark uncertain text instead of
   guessing. DSH's direct command only performs capture/copy; ask the Agent to read that PNG for text.
4. Return the saved path, model recognition result when available, and clipboard status. Do not repeat
   the capture on failure; report the available window list or the missing capture/clipboard tool.
5. The `screenshotEnabled` setting switches the whole feature off. It is on by default; each run
   still needs consent (`--yes`).

## 1. Asking the user

Use this shape for every decision that needs the user:

- One decision per question; at most 3 questions in one turn.
- 2–4 concrete options, each with a one-line consequence. Put your recommendation first and label it `(推荐)`.
- Always include `其他（我来说明）` / free-form.
- For approvals: `全部保留` / `逐条审核` / `全部不保留` / `稍后`.
- After the answer: restate the decision and the next action in one line.

Host mapping and templates: `references/ask.md`.

## 1.5 Workflow mode and execution authority

`workflowMode` is a plugin-policy enum, not a host permission:

- `plan` (default): ordinary runs need approval; generate `plan.md`/`plan.html`, wait for `执行`, then use `run --yes`.
- `full-authority`: ordinary runs do not need per-command approval; use `run --full-authority` so the runner reflects it. Destructive operations still need confirmation, and obvious destructive commands stay blocked.

The plugin never detects or changes DSH/Kimi/CodeBuddy host permissions. If the host is Plan/read-only/sandboxed, those limits still apply and cannot be bypassed by this setting. `--yes` and `--full-authority` are mutually exclusive. Legacy `requireRunConsent=false` is **not** promoted to full authority; old configs default to `plan`.

Plan output: `plan.md` by default, or `plan.html` when `planFormat=html` / `--format html`. Both live at the workspace root unless `--out` says otherwise. Details and schema: `references/plan.md`.

## 2. Memory

Two scopes:

| Scope | Path | Use for |
|---|---|---|
| User (global) | `<host-home>/programmer-workflow/memory` for the current host | Writing/communication habits, tool preferences, cross-project rules |
| Workspace | `<workspace>/.programmer-workflow/` (configurable in settings) | Project conventions, environment facts, decisions, “this repo is dev-only” |

Hosts are isolated: DSH uses `<DSH_HOME>/programmer-workflow`, Kimi uses `<KIMI_HOME>/programmer-workflow`, CodeBuddy uses `<CODEBUDDY_HOME>/programmer-workflow`, and other hosts use their own registry entry. Never fall back to `~/.dsh` for a non-DSH host. Legacy shared data can be imported once with the settings page/CLI; after that the roots are independent. Run commands with `--host dsh|kimi|...` or set `PROGRAMMER_WORKFLOW_HOST`. `PROGRAMMER_WORKFLOW_GLOBAL` is a per-host root override and is reported as external; `PROGRAMMER_WORKFLOW_HOME` is the older exact memory-directory override.

Only `MEMORY.md` / `boot` active entries are rules. `proposed` waits for the user; `rejected` stays in JSON for audit. Details: `references/memory.md`.

If a memory write fails with `PermissionError` (common in DSH `workspace-write`), do not silently downgrade a global request to workspace memory. Explain the two options: grant this write full access, or set `PROGRAMMER_WORKFLOW_HOME` to a writable directory (local, not global). Workspace memory still works. Inspect the per-host path and two-stage migration status in **设置 → 程序员工作流**.

### 2.1 Harvest habits

1. Ask permission before scanning. State what will be read: project files by default; conversation transcripts **only** with an explicit second opt-in.
2. Run `scan --out .programmer-workflow/scan.json`. This only gathers evidence; it never writes memory.
3. Summarize 3–8 candidate habits, each with: text, evidence, confidence, scope suggestion. Do not turn a single occurrence into a rule.
4. Write them with `memory propose --scope user|workspace --kind habit --text ... --evidence ...` (status `proposed`).
5. Ask the user to decide per item or in bulk (`memory review`, then `accept` / `reject` / `edit`).
6. Report what became active and where it is stored.

### 2.2 “Remember”

When the user says “记住 / remember this / 以后都…”:

1. Determine the scope. If they did not say user-level or workspace-level, **ask** with the two options and examples.
2. If the instruction is explicit, write it active: `memory add --scope ... --kind ... --text "..."`.
3. Restate exactly what was stored, which scope, and how to remove it (`memory forget <id>`).
4. If it is an inference rather than an explicit instruction, write `proposed` instead.

### 2.3 Environment declarations

When the user says the workspace is a pure dev environment, has no deployment target, or has no hardware:

1. Run `env set --dev-only --no-hardware --reason "<short quote>"` immediately; this records an **active** workspace environment fact for a fact the user just stated.
2. Follow section 4.2 only if `devOnlyAutoInstrument` is enabled **and** boot reports `devOnlyDirect=true`. Otherwise do not claim the direct-instrumentation shortcut; ask first.
3. Do not ask “do you have hardware?” again in this workspace.

## 3. Stuck after repeated attempts

Signals: 3 substantive attempts rejected, the user says “还是不对 / 不是这个意思 / 你怎么还没…”, or 2 failed bug fixes. You may also use `stall bump --track satisfaction|bugfix`; threshold is 3 / 2.

When triggered, **stop trying variations**. Do this:

1. Write a 3-line status: goal, what was tried, what is still unknown.
2. Ask which direction to take (options + free-form):
   - A. 按行业常用做法重做（推荐，若行业明确）
   - B. 加日志/最小复现，先定位再改
   - C. 我理解错了，先重述需求
   - D. 缩小范围或换方案
3. If the industry is unknown, infer from the repo/history; if confidence is low, ask with options drawn from the user's own history. Do not dump a generic industry list.
4. Present 2–4 industry-standard approaches with: what it is, when it fits, cost/risk, and what you would do first here. Cite sources when you use web research; mark uncertainty.
5. If the user is vague, produce an **interpretation card** before coding: goal, users, constraints, assumptions, non-goals, acceptance criteria, 2–3 options. Ask them to confirm or edit. Do not implement until they respond.
6. After a direction is chosen, reset the counter and state the next verification step.

Templates and worked examples: `references/satisfaction.md`.

## 4. Bug fixes and debugging

### 4.1 Trigger and offer

If a bug survives 2 failed fixes or 3 rounds, offer:

- A. 加最小排查日志 + 自动运行 + 日志分诊（推荐）
- B. 只加日志，不自动运行；我给你命令
- C. 先静态分析/二分/最小复现
- D. 需要实机/硬件配合（我列操作清单）

Ask before running any command **in Plan mode**; in Full authority, routine runs may proceed with `--full-authority`. The runner blocks obvious destructive commands in every mode.

### 4.2 Dev-only / no hardware

Only when `devOnlyAutoInstrument` is enabled **and** boot reports `devOnlyDirect=true` (an active workspace dev-only/no-hardware fact is present):

- Do **not** ask for permission to add logging. Add the smallest reversible instrumentation, then give exact commands to reproduce and locate the problem.
- Tell the user where the log is, what to search for, and what to paste back.
- Do not block on hardware; if real-device verification is unavoidable, say so explicitly and provide the checklist.

If the config flag is off, or the workspace fact is missing/proposed, do **not** claim the dev-only shortcut: ask before adding logs, or record the fact first. Never auto-promote a proposed environment entry.

### 4.3 Instrumentation rules

- Tag every line `[DBG-<ticket>-<n>]`; include timestamp, function, branch, key inputs/state, error, elapsed time.
- Log at boundaries (entry/exit), state transitions, external calls, retries, and catch blocks; not inside tight loops without sampling.
- Redact secrets/PII; cap string length and log size; prefer one structured line over multi-line dumps.
- Make it removable: a single patch or a `DEBUG` flag; list every touched file.
- Language recipes (Python, JS/TS, C/C++, C#, Java, Go, Rust): `references/debugging.md`.

### 4.4 Run and triage

1. Show the exact command and why; in Plan mode get approval.
2. Run in Plan mode: `run --label <short> --timeout 120 --yes -- <command>`. In Full authority use `--full-authority` instead of `--yes` (they are mutually exclusive).
3. Triage: `triage "<log>"`; read `TRIAGE.md` (error signatures, first context, hypotheses).
4. Add **one** probe at a time; re-run; compare. Do not change multiple variables at once.
5. Fix, add a regression test, remove/gate the temporary logs, and report the evidence.

If hardware is required, use the checklist in `references/debugging.md`: device, connection, permissions, firmware, reproduce steps, what to capture, and what to send back.

## 5. Architecture and Features docs

Triggers: “总结工程架构 / 总结功能 / 画个架构图 / summarize architecture or features / 接手这个项目”.

1. Confirm scope only if the repo is large or ambiguous; default to the whole workspace.
2. Gather evidence: `map --out .programmer-workflow/project-map.json`, then read manifests, entry points, routes, schemas, tests, and key modules. Cite paths.
3. Write a spec JSON with `architecture` and `features` objects (schema and example: `references/docs.md`). Put it at `docs/spec.json` unless the user prefers elsewhere.
4. Validate: `docs --spec docs/spec.json --check`.
5. Render: `docs --spec docs/spec.json --out docs`. This produces exactly `docs/Architecture.html` and `docs/Features.html`.
6. Tell the user: “用浏览器打开 docs/Architecture.html 和 docs/Features.html；页面可搜索、筛选、看依赖图，底部可提交评审并导出 JSON。”
7. When they return feedback (pasted or `*.review.json`), update the spec and re-render. Mention that the spec hash changed, so old review links are stale.
8. Never invent modules or features to fill the template. If evidence is missing, use `questions` with a default assumption.

## 6. UI / art / model prototypes

Triggers: UI, UX, layout, visual style, logo, icon, theme, art direction, moodboard, 3D model concept, game asset, “先做个原型看看”.

1. Ask at most 3 clarifying questions (platform, audience, must-keep content, style constraints). If the user says “你决定”, proceed and list assumptions.
2. Choose 2–3 **meaningfully different** directions (information architecture + visual language), not recolors.
3. Write a prototype spec (`references/prototype.md`), then render: `prototype --spec design.json --out Prototype.html`.
4. For art/models, use a style board: palette, typography, materials/lighting, silhouettes, references, and a clear “visual direction, not final asset” note.
5. Tell the user to open `Prototype.html`; they can switch direction/viewport, click the canvas to annotate, approve or request changes, then export review JSON.
6. Iterate blocking feedback first; keep the chosen direction and note what changed.

## 7. Output and handoff

- Lead with the result; put evidence and commands after it.
- Say exactly which files changed and whether they are reversible.
- For every generated HTML, give the absolute path and one line on how to review it.
- If a step was skipped (no browser, no hardware, no Python), say so and give the manual fallback.
- Close the loop: what the user decided, what is now active memory, what remains proposed.

## 8. Settings pages and data migration

**DSH**: the Host plugin adds **设置 → 程序员工作流**.

**Kimi Code / CodeBuddy / other CLI hosts**: use the local settings page. The Agent locates `companion.py` from the loaded skill (a `/plugins install` managed copy is valid) and starts it as a host background task:

```bash
python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
```

The command prints `http://127.0.0.1:<port>/?host=<id>#token=...`, listens on loopback only, and keeps running until the background task is stopped. Do not wrap it in `companion.py run` with a fixed timeout.

Both settings surfaces manage the same per-host file, `<host-home>/programmer-workflow/config.json`:

- workspace data / debug log / docs / prototype paths (must stay inside the workspace);
- memory load switches, stall thresholds, `workflowMode` (`plan`/`full-authority`), `devOnlyAutoInstrument`, `planFormat`, docs/prototype switches, retention and language;
- per-host plugin-data root/target and the two migration stages;
- `kimiMigrationTools` when the Kimi adapter is used.

The local API (`GET /api/config`, `GET /api/status`, `POST /api/config`, `/api/migration/*`) requires an explicit `host` and the startup token. Unknown hosts and invalid fields are rejected; the page never falls back to DSH. It only **prepares** migration and rollback scripts — it never executes a migration, rollback or external batch file.

`boot`, `docs`, `prototype`, `run` and `stall` read the saved mirror after `--host`/`PROGRAMMER_WORKFLOW_HOST` selects the host. If the page and CLI disagree, the file is the source the CLI uses; ask the user to save again in Settings.

Never move the workspace outputs outside the workspace. The CLI rejects absolute or `..` output paths. Global data belongs to one host; do not imply that Kimi/CodeBuddy share DSH's memory. Workspace memory is project data and never moves with an application/plugin migration.

## References (load only what the task needs)

| File | Load when |
|---|---|
| `references/ask.md` | Any question, approval, or option set |
| `references/plan.md` | Plan mode, Full authority, plan.md/plan.html, execution approval |
| `references/memory.md` | Boot, harvest, remember, scope conflict, environment facts |
| `references/satisfaction.md` | 3-round stall, industry practices, vague requirements |
| `references/debugging.md` | Bug stall, instrumentation, run/triage, hardware checklist |
| `references/docs.md` | Architecture/Features spec, evidence rules, review loop |
| `references/prototype.md` | UI/art/model direction, spec schema, review loop |
| `references/hosts.md` | Install paths, host question tools, auto-load behavior |
| `references/safety.md` | Privacy, destructive commands, reversibility, HTML safety |

## Command cheat sheet

```bash
# --host is required when the environment does not set PROGRAMMER_WORKFLOW_HOST
python "<skill>/scripts/companion.py" boot --host dsh --workspace .
python "<skill>/scripts/companion.py" plan --host dsh --spec .programmer-workflow/plan.json --format md
python "<skill>/scripts/companion.py" memory review --host dsh --scope all
python "<skill>/scripts/companion.py" memory propose --host dsh --scope user --kind habit --text "..." --evidence "..."
python "<skill>/scripts/companion.py" memory accept <id> --host dsh --scope user
python "<skill>/scripts/companion.py" scan --host dsh --workspace . --out .programmer-workflow/scan.json
python "<skill>/scripts/companion.py" env set --host dsh --dev-only --no-hardware --reason "..."
python "<skill>/scripts/companion.py" env probe --host dsh --workspace .
python "<skill>/scripts/companion.py" env check pnpm --host dsh --workspace .
python "<skill>/scripts/companion.py" screenshot --host dsh --target "微信" --yes
python "<skill>/scripts/companion.py" stall bump --host dsh --track bugfix
python "<skill>/scripts/companion.py" run --host dsh --label repro --timeout 120 --yes -- python app.py
python "<skill>/scripts/companion.py" triage debug-logs/<dir>/combined.log --host dsh
python "<skill>/scripts/companion.py" map --host dsh --workspace .
python "<skill>/scripts/companion.py" docs --host dsh --spec docs/spec.json --out docs
python "<skill>/scripts/companion.py" prototype --host dsh --spec design.json --out Prototype.html
python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
```
