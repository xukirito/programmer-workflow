# Programmer Workflow

[中文](README.md) | English

Review-first working memory, stall recovery, instrumented debugging, offline architecture/feature docs and
design prototypes for coding agents — portable across DeepSeek Harness, Kimi Code, CodeBuddy, Claude Code,
Cursor and Codex.

[![version](https://img.shields.io/badge/version-0.1.1--preview-orange)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](skills/programmer-workflow/scripts/companion.py)
[![hosts](https://img.shields.io/badge/hosts-DSH%20%7C%20Kimi%20%7C%20CodeBuddy%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-informational)](#compatibility)

> **v0.1.1 preview.** DSH installs from the GitHub root package; Kimi uses the official `/plugins install`.
> Config fields, review contracts and the DSH client bundle may still change. Real-host migration has not
> been verified by this plugin; see [Compatibility](#compatibility) and [docs/Migration.html](docs/Migration.html).

## What it does

- **Approval-gated memory** — inferred habits stay `proposed` until you approve them; only `active`
  entries are injected at session start.
- **Plan / full-authority workflow** — `plan` writes `plan.md` / `plan.html` and waits for your approval;
  `full-authority` skips routine approvals but still confirms destructive operations. This is plugin policy,
  never a replacement for the host's own permissions.
- **Stall recovery** — after repeated failures, stop guessing and choose between industry practice,
  instrumented debugging, re-interpretation or scope reduction.
- **Debug loop** — tagged logs, captured output, `TRIAGE.md`, and one hypothesis at a time.
- **Environment preflight** — probe the workspace OS/shell/commands once, cache it, and check an
  executable before `run`; a cross-OS target is never executed locally.
- **Screenshot / model vision / clipboard** — `/screenshot` or `/截图` captures a named window or
  screen and copies the PNG; the Agent reads text with the model's own vision capability, never local OCR.
- **DSH balance chip** — the current account balance above the account row; it never returns credentials.
- **Offline docs and prototypes** — `Architecture.html`, `Features.html` and `Prototype.html` are
  single-file, searchable, reviewable HTML; `localStorage` keeps review state and exports JSON.

Only the Python standard library and a browser are required. No MCP, database, cloud account or third-party
Python package.

## Compatibility

“Supported” means the code path exists and has contract/temporary-directory tests. “Verified” means it was
run against real host data. This repository never turns “a script exists” into “the plugin verified it”.

| Host | Install entry | Default plugin data root | Settings UI | Runtime-data migration | Verification |
|---|---|---|---|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add github:xukirito/programmer-workflow` (or root `add .`) | `<DSH_HOME>/programmer-workflow` (`~/.dsh/...`) | Yes (Settings → Programmer Workflow) | Built-in migrate + rollback (stage 2) | Root-package install applied; temp-dir/contract tests; real migration not verified |
| **Kimi Code** | `/plugins install` or `install.ps1 -Targets kimi` | `<KIMI_HOME>/programmer-workflow` (`~/.kimi-code/...`) | Yes (plugin homepage quick link / `/programmer-workflow:settings`) | Needs a user-supplied migrate + rollback tool pair | Local server + Chromium E2E; real Kimi session not verified |
| **CodeBuddy** | project `.codebuddy/skills` + `CODEBUDDY.md` | `<CODEBUDDY_HOME>/programmer-workflow` | Local page switch (`--host codebuddy`) | **Not adapted** | Installer/manifest tests; end-to-end not verified |
| **Claude Code** | `install.ps1 -Targets claude` / `.claude-plugin` | `~/.claude/programmer-workflow` | No | **Not adapted** | Manifest/install tests; marketplace flow not verified |
| **Cursor** | `install.ps1 -Targets cursor` | `~/.cursor/programmer-workflow` | No | **Not adapted** | Install-path/skill tests |
| **Codex** | `install.ps1 -Targets codex` | `~/.codex/programmer-workflow` | No | **Not adapted** | Install-path/skill tests |
| **Generic** | `.agents/skills` + `AGENTS.md` bootstrap | `~/.programmer-workflow` (`--host generic`) | No | Not provided | Temp-dir tests |

Notes:

- Tested with DSH `0.2.1-rc.5` on Windows, Python 3.8 and Node 18. DSH upgrades can change the client
  contract; check the DSH plugin page for a sync error and reinstall the local bundle.
- The DSH desktop app currently ships Windows installers; `install.sh` covers skill installs on macOS/Linux.
- Each host has its own data root. There is no shared cross-host memory and no non-DSH fallback to `.dsh`.

## Quick start

### DeepSeek Harness

The repository root is a normal DSH package, so install it from GitHub like `dsh-plugin-whale-pet`:

```powershell
dsh plugin --profile web add github:xukirito/programmer-workflow
```

Or install the local root (`dsh plugin --profile web add .`). The package contains the Skill, commands
and Host/Client halves; Host startup copies the bundled Skill to `<DSH_HOME>/skills/programmer-workflow`
when it is absent. **Settings → Programmer Workflow** should appear after a restart/refresh. If an old
`@local/programmer-workflow` bundle is still installed, remove it first.

`install.ps1` remains available for the managed `AGENTS.md` bootstrap or offline installs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets dsh -HostId dsh -Bootstrap
```

Verify:

```powershell
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" doctor --host dsh --workspace .
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" env probe --host dsh --workspace .
```

Use `$env:DSH_HOME` instead of `$env:USERPROFILE\.dsh` when DSH uses a custom home.

### Kimi Code / CodeBuddy / Claude Code / Cursor / Codex

```powershell
# Kimi Code
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets kimi -HostId kimi -Bootstrap

# CodeBuddy (project-level)
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets codebuddy -ProjectRoot "F:\work\my-app" -Bootstrap

# Claude Code
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets claude -HostId claude -Bootstrap

# Cursor / Codex
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets cursor -HostId cursor -Bootstrap
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets codex -HostId codex -Bootstrap
```

### Local settings page (Kimi Code / CodeBuddy / DSH)

After changing a local source installation, reinstall the same directory with `/plugins install <repository-root>`
(or remove and re-add it in the plugin manager). Kimi runs the copied `plugins/managed` snapshot; restarting alone
does not synchronize newer source files. Check the new version in plugin details, then start a new session.
There are two configuration entries:

1. Send `/programmer-workflow:settings` in the Kimi chat input (not CMD), or use the terminal command below.
2. On Windows, double-click `Open-Settings.vbs` without a model turn or command entry. Use either
   `<repository-root>\Open-Settings.vbs` or the installed copy at
   `<KIMI_HOME>\plugins\managed\programmer-workflow\Open-Settings.vbs` (`%USERPROFILE%\.kimi-code` by default).

The launcher opens the local page and starts the hidden service when needed. Keep it next to the plugin files.
Kimi may not render homepage links for custom plugins, so do not rely on that entry.
If a local install fails with `EPERM ... symlink`, remove stale `.tmp-tests/pwf-host-*` test directories and
their Windows junctions before adding the repository again; `.gitignore` does not exclude files from Kimi's copy.

Kimi has no DSH `settings.section` Slot, so the same Python configuration code is exposed as
`/programmer-workflow:settings`. The command starts a loopback-only page in a host background task:

```powershell
# <skill> is the skill directory actually loaded by the host
python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
```

- After `/plugins install`, the running copy lives under `plugins/managed`; let the agent resolve the CLI
  from the loaded skill instead of hardcoding `~/.kimi-code/skills`.
- The page defaults to the startup host and can switch DeepSeek Harness / Kimi Code / CodeBuddy. Every API
  request names a host explicitly; an unknown host is a 400 and never falls back to DSH.
- Values are written to `<host-home>/programmer-workflow/config.json`; a rejected save returns field-level
  errors and never silently replaces the draft with defaults.
- The page only **prepares** migration/rollback scripts. It never executes a migration, rollback or batch file.
- `--port 0` picks a random free port. Stop the background task (or press Ctrl+C); config, memory and
  migration state are kept.

macOS/Linux:

```bash
./install.sh --target agents,claude,kimi --bootstrap
./install.sh --target project --project ~/code/my-app --host generic --bootstrap
```

## Usage

Talk to the agent; you rarely need commands:

- “Remember: this project uses pnpm, not npm.” → a proposed memory with evidence; approve it to activate.
- “Open the Programmer Workflow settings.” → in Kimi/CodeBuddy, runs `/programmer-workflow:settings` and
  prints the local page URL.
- “Give me a plan first.” → `plan.md` / `plan.html`.
- “We tried three times and it still fails.” → stall escalation with concrete options.
- “Add logs and reproduce the 500.” → instrumented run + `TRIAGE.md`.
- “Summarize the architecture and features.” → `docs/Architecture.html`, `docs/Features.html`.
- “The UI prototype has two page orientation settings.” → `Prototype. html` with review/export.

Useful CLI:

```powershell
$CLI = "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py"
python $CLI boot --host dsh --workspace .
python $CLI memory review --host dsh --scope all
python $CLI docs --host dsh --spec docs/spec.json --out docs
python $CLI migrate-plugin status --host dsh --json
```

## Data and privacy

| Data | Default location | Moves with app migration? |
|---|---|---|
| Plugin memory/config | `<host-home>/programmer-workflow` | Stage 1 plugin-data migration |
| Workspace memory | `<workspace>/.programmer-workflow` | No, project data |
| Debug logs | `<workspace>/debug-logs` | No |
| Docs/prototypes | `<workspace>/docs`, `<workspace>/Prototype.html` | No |
| DSH runtime data | `%USERPROFILE%\.dsh` (`DSH_HOME` override) | Stage 2 runtime-data migration |

Everything stays local by default. The repository contains no runtime memory, credentials or logs.
`PROGRAMMER_WORKFLOW_GLOBAL` / `PROGRAMMER_WORKFLOW_HOME` are explicit overrides and are reported as
external paths outside the default migration.

## Workflow mode

| `workflowMode` | Behavior | Run with |
|---|---|---|
| `plan` (default) | Write a plan and wait for “执行”; no direct project edits | `run --yes` |
| `full-authority` | Routine runs need no per-command approval; destructive ops still confirmed | `run --full-authority` |

`--yes` and `--full-authority` are mutually exclusive. The host's Plan / read-only / sandbox limits always
win. Destructive commands remain blocked in both modes.

## Migration

1. **Plugin data** — only the current host's `programmer-workflow` directory; preflight, backup, SHA-256,
   then a generated launcher.
2. **Runtime data** — sessions, config, caches and credentials; requires a completed/verified stage 1 and a
   migrate + rollback adapter pair.

Both the DSH Settings page and the local page prepare, but never execute, migration scripts. Stage 1
launchers use the real `companion.py` and pass `--host` explicitly; stage 2 launchers pass
`KIMI_MIG_SRC` / `KIMI_MIG_DEST` (or the DSH equivalents) and record `runtime-state.json`. `prepared`
only means the scripts exist; a live link or real on-disk verification is required for `completed`.

Kimi needs a configured tool directory; CodeBuddy/Claude/Cursor/Codex runtime migration is not adapted.
Run only after fully quitting the target editor, and keep `.old` until the new location has been stable
for at least a day. See [docs/Migration.html](docs/Migration.html) and [docs/Reinstall-DSH.md](docs/Reinstall-DSH.md).

## Development

```powershell
python tests\run_tests.py
node --check dsh-plugin\index.js
node --check dsh-plugin\client.js
node --check skills\programmer-workflow\templates\settings.js
python skills\programmer-workflow\scripts\companion.py settings --help
python skills\programmer-workflow\scripts\companion.py docs --host dsh --spec docs\spec.json --check
```

Tests use temporary homes; they never write into real host memory. Regenerate generated HTML from
`docs/spec.json`; do not hand-edit it.

## Version and release

- Current: `v0.1.1` preview; **no GitHub Release or tag yet**.
- Changelog: [CHANGELOG.md](CHANGELOG.md).
- Before a release: all tests green, real-data migration verified, compatibility matrix updated, no personal
  paths or credentials in the tree.
- Report issues with host/version, command, and redacted logs. Never upload memory files or credentials.

## Tips

- Hope everyone can communicate more and provide suggestions. You can also upload bug fixes or submit your modifications on your own
- This plugin will continuously update the adaptation of the agents I have used in the future, and it will continue to be updated. You (experts) can also update new adaptation agents

## License

[MIT](LICENSE) © 2026 Workflow Companion Contributors
