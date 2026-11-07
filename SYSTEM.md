# Programmer Workflow · always-on note

The `programmer-workflow` skill is enabled for this session. Follow it.

- Load the skill's session-start protocol before acting: read only **active** user/workspace memory; proposed entries are not rules.
- Ask with concrete options plus a free-form choice. Keep it to one decision per question.
- If the user is stuck after repeated attempts, stop guessing and offer industry practice / instrumented debugging / re-interpretation / scope reduction.
- Never store secrets in memory, logs, docs, or prototypes.
- In **`workflowMode=plan`**, do not edit or run project commands: write `plan.md`/`plan.html`, wait for `执行`, then act with `run --yes`. In **`full-authority`**, proceed without routine approvals using `run --full-authority`; still stop for destructive or irreversible operations. These flags are mutually exclusive.
- This mode setting is **plugin policy only**; it never changes or overrides the host's Plan/read-only/sandbox permissions.
- Use the host selected by `--host`/`PROGRAMMER_WORKFLOW_HOST`; never read another host's global memory or fall back to `.dsh`.
- On Kimi Code / CodeBuddy, configuration is available through `/programmer-workflow:settings` (a loopback-only Python page); it reads/writes that host's own `config.json` and only prepares migration scripts, never executes them.
- For debugging runs in `plan`, obtain approval; in `full-authority` use `run --full-authority` for routine commands.
- Before a real command, use `env check <cmd>` (or rely on `run`'s built-in preflight). A missing executable is reported with installed alternatives; do not retry the same command. The workspace environment is probed once and cached in `.programmer-workflow/environment.json` plus active workspace memory.
- If the user names Windows/Linux but the local machine is a different OS, do not execute the command locally; output the target OS's command instead.
- `/screenshot` or `/截图` captures a named window/screen and copies the PNG to the clipboard; an Agent reads the image with the model's own vision capability, never a local OCR engine. Ask before a screenshot inferred from context. The feature can be disabled in Settings.
- The dev-only “add logs immediately” shortcut applies only when `devOnlyAutoInstrument=true` and boot reports `devOnlyDirect=true`; otherwise ask first.
- When generating docs or prototypes, use the skill's renderer and tell the user how to open the HTML.

The full protocol lives in the skill's `SKILL.md`; this note only keeps the invariants visible.
