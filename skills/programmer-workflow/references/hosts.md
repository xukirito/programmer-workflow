# Host adapters

The same skill runs in several agents, but each host has its own data root and its
own runtime-migration support. The package does **not** share one plugin memory or
one config file across hosts.

## Data roots (default)

| Host | Plugin data root | Skill directories |
|---|---|---|
| DSH | `<DSH_HOME>/programmer-workflow` (default `~/.dsh/programmer-workflow`) | `~/.dsh/skills`, `.dsh/skills`, `~/.agents/skills` |
| Kimi Code | `<KIMI_HOME>/programmer-workflow` (default `~/.kimi-code/programmer-workflow`) | `~/.kimi-code/skills`; plugin `/plugins install` |
| CodeBuddy | `<CODEBUDDY_HOME>/programmer-workflow` (default `~/.codebuddy/programmer-workflow`) | user import + project `.codebuddy/skills` |
| Claude Code | `~/.claude/programmer-workflow` | `~/.claude/skills`; plugin |
| Cursor | `~/.cursor/programmer-workflow` | `~/.cursor/skills`, `.agents/skills` |
| Codex | `~/.codex/programmer-workflow` | `~/.codex/skills`, `.agents/skills` |
| Generic | `~/.programmer-workflow` | `.agents/skills` + an `AGENTS.md` bootstrap |

`--host` / `PROGRAMMER_WORKFLOW_HOST` selects the host. There is no cwd-based host
guessing and no non-DSH fallback to `~/.dsh`. If no host is supplied, commands fail
with an actionable error; use `--host generic` for an intentionally neutral root.

Each root contains `memory/`, `artifacts/`, `logs/` and `config.json`. A change in
one host is invisible to the others.

## Settings surfaces

| Host | Where to configure | Notes |
|---|---|---|
| DSH | **Settings → Programmer Workflow** | Host/Client bundle in `dsh-plugin/`; React Slot UI |
| Kimi Code | `/programmer-workflow:settings` local page | Python-only, loopback server; no React/DSH loader |
| CodeBuddy | local page with `--host codebuddy` | Project-level install still uses its own user-level data root |
| Claude/Cursor/Codex | none yet | CLI and manual config only |

The local page command is:

```bash
python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
```

`<skill>` must be resolved from the currently loaded skill. After `/plugins install` the
running copy is under `plugins/managed`, so do not hardcode `~/.kimi-code/skills`. The server
listens on `127.0.0.1` only, uses a random token in the URL fragment
(`#token=...`), and writes the same `<host-root>/config.json` read by `boot`, `docs`,
`prototype`, `run` and `stall`. It only prepares migration/rollback scripts; it never
executes them.

## Workflow mode and authority

`workflowMode` is a plugin policy: `plan` (default) or `full-authority`. It does
not change the host's Plan/read-only/sandbox permissions. `--yes` and
`--full-authority` are mutually exclusive; destructive commands remain blocked.

| Host | Plan/read-only behavior | Normal behavior |
|---|---|---|
| DSH | Host posture wins; write `plan.md`/`plan.html`, wait for `执行` | Routine commands run; destructive still confirmed |
| Kimi Code | Host UI wins; otherwise `workflowMode`/explicit “先给方案” | Routine commands run; destructive still confirmed |
| CodeBuddy | Project plan file + user approval | Full mode proceeds; safety checks stay |
| Others | Host posture wins; otherwise `workflowMode` | Routine commands as allowed by host |

## Migration (two stages)

1. **Plugin data** — only `<host-home>/programmer-workflow`, with its own backup,
   inventory, hashes and a junction at the source path. The registry models every host,
   but preparing a launcher needs that host's Skill CLI:
   `PROGRAMMER_WORKFLOW_CLI`, `<host-home>/skills/programmer-workflow/scripts/companion.py`,
   or the CLI that is actually running **when its host matches** the startup host. A managed
   Kimi plugin copy under `<KIMI_HOME>/plugins/managed` is therefore usable for Kimi, but the
   same file is never offered to DSH/CodeBuddy. Without a CLI the capability is reported as
   supported-but-not-ready and the prepare entry is disabled; CodeBuddy is the usual case
   because it installs project-level by default. Prepared launchers use the real
   `companion.py` and pass `--host <id>` explicitly.
2. **Editor runtime data** — separate adapter and separate target. It is gated on
   stage 1 `completed` + `verifiedAt` **and** on a complete adapter directory
   (`migrate-*` plus `rollback-*`). The launcher receives the target *root* in
   `DSH_MIG_DEST` / `KIMI_MIG_DEST` and the resolved host home in `DSH_MIG_SRC` /
   `KIMI_MIG_SRC`; the adapter appends its own data dir. Raw rollback runs through
   `run-stage2-rollback.cmd` first, then `run-stage1-rollback-plugin.cmd`. Both stages are
   also preparable from the local settings page; that page never runs the launchers.

| Host | Plugin migration | Runtime migration | Notes |
|---|---|---|---|
| DSH | supported (needs its CLI) | supported (bundled migrate + rollback) | Source is the resolved `DSH_HOME`, not `%USERPROFILE%\.dsh` |
| Kimi Code | supported when its skill is installed | only with a configured migrate+rollback pair | The adapter must honor `KIMI_MIG_SRC`; a fixed `%USERPROFILE%\.kimi-code` adapter is unavailable when `KIMI_HOME` differs |
| CodeBuddy | registry-supported; **ready only with a CLI** | **not implemented** | Project-level skill does not imply a user-level CLI |
| Claude/Cursor/Codex | registry-supported; ready only with a CLI | **not implemented** | No hardcoded fallback |

States are idempotent: `prepared` only means a launcher exists; `completed` means the
live link resolves to the recorded target (or, after stage 2, a junctioned host home),
**or** the real landing (junction resolved) is on a volume other than the app's system
drive — then `C:` is only a mapping and the UI must not prompt again. That second form is
labelled “已有迁移”, not “verified”, and never invents `verifiedAt`. An unverified
same-drive link is reported as external. A completed stage is not re-offered — the only
follow-up is an explicit “move to a new address”, which re-runs the full preflight and
reads the live data through the current link. The plugin's own launchers have not been
executed against real user data yet; coverage comes from temporary-directory and contract
tests.

Nested junctions are **partially** supported: same-target-root nesting is accepted,
while cross-root or manifest rebuilding is detected and refused — the package does not
claim a complete rebuild.

Workspace memory (`<workspace>/.programmer-workflow`) is project data and never
moves with a plugin/application migration. Legacy shared data from
`~/.workflow-companion` or the old DSH shared root is **not** read as a fallback;
the settings page/CLI can import it once after a conflict check, preserving
`active`/`proposed`/`rejected` and never overwriting.

External overrides (`PROGRAMMER_WORKFLOW_GLOBAL`, `PROGRAMMER_WORKFLOW_HOME`) apply to
**every** host, exactly like the Host plugin, and are reported as “外部路径，未由默认迁移
覆盖”; export/back up manually.

## Auto-load / session start

- **DSH**: skill catalog from the directories above; installer can add a managed
  bootstrap block that runs `boot --host dsh`. The default `dsh plugin add` path also
  copies the bundled Skill on first Host load.
- **Kimi**: `kimi.plugin.json` (`sessionStart.skill`, system prompt, commands,
  `hooks.SessionStart`), including the plugin-details homepage quick link and
  `/programmer-workflow:settings`. The manifest deliberately has no `settings`/`configFile`
  extension fields; the local Python page provides configuration. The hook starts
  `127.0.0.1:8765` idempotently; `/quick?host=kimi` 302s to the tokenized page.
- **Claude**: skill discovery + `.claude-plugin` manifest/commands.
- **Cursor/Codex**: `.agents/skills` plus their bootstrap/`AGENTS.md` support.
- **CodeBuddy**: project `.codebuddy/skills` + `CODEBUDDY.md`, or Settings → Skills.
- **Generic/others**: project `.agents/skills` + an `AGENTS.md` block.

The memory read is **not a background timer**. It happens when the host starts a new/resumed
session and the skill's `boot` step runs; the managed `AGENTS.md` block is what makes DSH run
`boot` at task start. If neither the bootstrap block nor `sessionStart` is present, memory is
not injected automatically.

Always pass the host in bootstrap commands; the installer writes the matching
`--host` unless `-HostId`/`--host` overrides it.

## Question tools

| Host | Tool / mechanism | Fallback |
|---|---|---|
| DSH | `ask_user_question` | numbered list |
| Claude Code | `AskUserQuestion` | numbered list |
| Kimi Code | host question/confirmation UI | numbered list |
| Cursor / Codex / Generic | host prompt if present | numbered list + “其他” |
| CodeBuddy | host options if available | numbered list |

Never fail a task because a host lacks a structured question tool.

## Shell / Python

The skill needs Python 3.8+ for memory, scanning, running, triage, and HTML
rendering. If Python is unavailable, read `MEMORY.md` manually, use the text
protocols, and say which commands were not run; never fake results. On Windows,
quote paths with spaces.

## Plugin vs skill

- **Skill**: instructions + scripts, discoverable by many hosts.
- **Kimi plugin**: skill + manifest + `sessionStart` + commands + the local Python settings page.
- **Claude plugin**: manifest + skills + commands.
- **DSH plugin**: this repository really ships one at `dsh-plugin/` — a Host/Client
  bundle with a settings page, per-host config/status, migration preparation and
  `migration.html`. Do not describe the package as skill-only.

## Installation checklist

1. Copy the skill/plugin using `install.ps1` or `install.sh` for the target host.
2. Start a new session so the catalog refreshes.
3. Run `doctor` with `--host <id>`.
4. Verify memory/config paths are under that host's own root.
5. Open the settings surface for that host (DSH Settings page, or the local
   `settings --host <id>` page) and confirm the paths match.
6. If the host does not trigger the skill, add its managed bootstrap block; use
   the installer's `-HostId`/`--host` option.

## Environment overrides

```bash
PROGRAMMER_WORKFLOW_HOST=kimi          # required when the host cannot pass --host
PROGRAMMER_WORKFLOW_GLOBAL=/path       # plugin-data root override for the current host
PROGRAMMER_WORKFLOW_HOME=/path         # exact memory-directory override for the current host
PROGRAMMER_WORKFLOW_WORKSPACE=/path    # workspace root override
PROGRAMMER_WORKFLOW_CLI=/path/companion.py  # Skill CLI used to run stage 1
```

Overrides outside the host's default root are reported as external and are not
covered by the default migration. `DSH_HOME` affects **only** DSH; the two
`PROGRAMMER_WORKFLOW_*` overrides affect whatever host `--host` selects.
