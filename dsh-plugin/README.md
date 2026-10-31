# Programmer Workflow · DSH plugin

DeepSeek Harness Host/Client bundle for the `programmer-workflow` skill.

## What it adds

- **Settings → 程序员工作流** with per-host tabs (DSH / Kimi / CodeBuddy) that read and
  write each host's **own** `programmer-workflow/config.json`; host tabs never share
  memory or config.
- **Workflow mode** enum (`plan` / `full-authority`) with safe migration from old
  `requireRunConsent` configs (missing/invalid → `plan`; old `false` is not promoted).
- **Two-stage migration**:
  1. plugin data only (`<host-home>/programmer-workflow`), with inventory, SHA-256,
     independent backup, conflict/legacy checks and a target-bound launcher;
  2. editor runtime data, disabled until stage 1 is `completed` + `verifiedAt`.
- **Per-host status**: logical/real paths, in-host-home flag, external overrides,
  legacy/shared memory conflict, memory counts/IDs/hashes, workspace-memory note,
  `pluginMigration` state and `runtimeMigration` support/reason.
- **Migration tutorial** at `/programmer-workflow/migration`; bundled DSH tools and a
  configurable Kimi tool path (default empty; “found” does not mean “verified”).
- **Client-side migration guard**: Settings only writes config and prepares scripts;
  it never migrates while DSH is running.

## Files

```text
index.js                 Host: per-host roots/config/status + prepare routes
client.js                Client: settings page and two-stage migration UI
migration.html           DSH/Kimi migration tutorial (synced to docs/Migration.html)
dsh-migration-tools/     Bundled DSH runtime migration/rollback scripts
```

## Routes

| Route | Purpose |
|---|---|
| `GET /programmer-workflow/status?host=dsh` | Per-host status; `hosts` lists registry entries |
| `GET|POST /programmer-workflow/config?host=kimi` | Read/save that host's own config; invalid writes return HTTP 400 |
| `POST /programmer-workflow/plugin-migration/prepare` | Stage 1 preflight/backup/state + launcher |
| `POST /programmer-workflow/plugin-migration/legacy-import` | One-time import; refuses overwrite on conflict |
| `POST /programmer-workflow/migration/prepare` | Stage 2 launcher + rollback launcher; blocked until stage 1 completes and the adapter is complete |
| `GET /programmer-workflow/migration` | Tutorial |

`POST /programmer-workflow/config` with `{"reset": true, "host": "<id>"}` restores the
defaults of that host only; memory data is not touched.

## Data boundaries

- Plugin root: `<host-home>/programmer-workflow`; DSH uses `DSH_HOME`, Kimi uses
  `KIMI_HOME`, CodeBuddy uses `CODEBUDDY_HOME`. `DSH_HOME` affects only DSH.
- `PROGRAMMER_WORKFLOW_GLOBAL` / `PROGRAMMER_WORKFLOW_HOME` apply to **every** host,
  exactly like the Python CLI; status, config reads/writes and migration preflight
  resolve through the same two overrides.
- A missing host defaults to DSH only for internal calls with no value; any route or
  body carrying an unknown/misspelled host returns HTTP 400 instead of reading DSH.
- Workspace memory belongs to the project and never moves with a global migration.
- A `.dsh` junction alone never proves plugin stage 1 completed; read
  `pluginMigration.status`/`verifiedAt` and the state file.
- `retentionDays` prunes only top-level files under the plugin `artifacts/` directory.
- Stage 1/2 launchers are prepared in `<host-home>/.programmer-workflow-migration/`;
  backups are outside the plugin directory being renamed.

## Stage 2 contract

- `DSH_MIG_DEST` / `KIMI_MIG_DEST` receive the **target root**; the adapter appends its
  own host data dir (`%DESTROOT%\.dsh`, `%DESTROOT%\.kimi-code`), so the launcher must
  never pass `<root>/.dsh`. `DSH_MIG_SRC` / `KIMI_MIG_SRC` carry the resolved host home.
- The reported `launcher`, the file actually written, and `runtime-state.json` are the
  same path.
- An adapter directory counts as ready only with both `migrate-*` and `rollback-*`
  scripts. `run-stage2-rollback.cmd` calls the host rollback tool and must run before
  the stage 1 rollback; while stage 2 is `prepared`/`completed` the stage 1 rollback is
  refused.
- Stage states are idempotent: `prepared` means only "script generated", `completed`
  requires a live link to the recorded target (or a junctioned host home after stage 2)
  plus `verifiedAt`, **or** a real landing (after resolving junctions) on a volume other
  than the app's system drive (`SystemDrive`/`PROGRAMMER_WORKFLOW_SYSTEM_DRIVE`). The
  second form is how data moved with the sample scripts shows up: the `C:` path is only
  a mapping, the page says “已迁移，无需再次操作”, reports the real location, and labels
  it “已有迁移，未记为本插件验证” without fabricating `verifiedAt`. A state file or
  leftover script alone is reported as `stale`; a same-drive link without a record is
  `external`, never completed.
- A completed stage is not re-offered: the page shows “无需再次操作” and the only action
  is an explicit “迁移到新地址”. That path re-runs the full preflight, reads the live
  data through the current link (not `.old`), keeps the previous state until the new
  one succeeds, and still requires the user to run the generated script.
- Nested junctions are **partially** supported: same-target-root nesting is accepted,
  cross-root or manifest rebuilding is refused (not implemented).

## Client loading protocol

DSH serves `dsh.client` bundles as **classic browser scripts** into the page's
`window.__ModuleLoader__` lazy-CJS facade. `client.js` must therefore:

- contain no top-level `import`/`export` (a classic script cannot parse ESM);
- call `window.__ModuleLoader__.load({ id: '@local/programmer-workflow', factory(require) { … } })`
  where `id` is exactly the package name;
- take React from the module table — `const React = require('react')` plus
  `React.createElement`; there is no `h` export to import;
- return `{ inject: ['slots'], apply(ctx) }` from the factory;
- register the Settings page through `ctx.slots.inject('settings.section', () => ctx.slots.register({ … }, Component))`.
  Returning a registration object from the callback does nothing.

A bundle that loads without calling `load()` (or registers nothing) makes Settings →
Plugins report a page-local sync failure while the Host enable state stays unchanged.
`tests/client_plugin_test.mjs` reproduces this contract without a browser, and
`node --check` must be run on a `.cjs` copy: `package.json` says `"type": "module"`,
so checking `client.js` directly would accept the ESM syntax that breaks the page.

## Notes

- `enabled: false` under the `ui-settings` patch entry is the shared Web/desktop
  developer-tools preference (`Config = z.object({ enabled })` in
  `@deepseek-ai/dsh-client-ui-settings`). It does **not** disable the Settings shell
  or plugin loading, so it is not a cause of a Client plugin sync failure.
- The actual `.dsh`/Kimi runtime launchers are Windows batch adapters. Stage 1 is
  implemented by the Python CLI (`companion.py migrate-plugin ...`) and is covered by
  temporary-directory tests; it has not been executed against real user data.
- Kimi runtime support requires a `kimiMigrationTools` path that contains **both**
  `migrate-kimi-data.bat` and `rollback-kimi-data.bat`, and the migrate script must
  read `KIMI_MIG_SRC` when `KIMI_HOME` is not the default `~/.kimi-code`. Otherwise the
  status is unavailable and prepare is disabled.
- Stage 1 needs that host's `companion.py` (`<host-home>/skills/programmer-workflow/scripts/companion.py`)
  or `PROGRAMMER_WORKFLOW_CLI`. CodeBuddy/Claude/Cursor/Codex are supported in the
  registry but report `pluginMigration.ready = false` until a CLI exists.
- CodeBuddy, Claude, Cursor and Codex runtime migration is not implemented; stage 2 is
  disabled for them.
- The settings page also restores `恢复默认` (per-host reset) and the `promptMigration`
  overlay banner (`shell.overlay`); the banner only points at stage 1.
