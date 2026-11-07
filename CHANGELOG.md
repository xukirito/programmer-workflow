# Changelog

All notable changes to Programmer Workflow. The project is in **v0.1.1 preview** and has **no GitHub
Release or tag yet**; entries below describe the source tree, not a published binary.

## [0.1.1] - 2026-11-07 (preview, source only)

### Added

- **Workspace environment preflight**: `env probe` detects the local OS, shell, GUI, installed
  commands and capture/clipboard tools once, caches `.programmer-workflow/environment.json`, and writes one
  active workspace `environment` memory entry. `boot` reuses the cache and prints one compact line;
  `run` checks the executable before consent/spawn and reports installed alternatives instead of
  retrying a missing command. `run --target-os` / `env check --target-os` refuse to execute a command
  for a different OS.
- **Screenshot / model vision / clipboard**: `companion.py screenshot`, DSH `/screenshot` and
  Kimi `/截图` capture and copy a PNG; the Agent reads text with the model's vision capability,
  never Windows OCR or Tesseract. Windows uses UTF-8 BOM + UTF-8 stream output, and a missing
  named window now fails instead of silently capturing the whole screen. `screenshotEnabled`
  remains in both settings surfaces; every capture still needs consent.
- **DSH balance chip**: `sidebar.footer.action` shows the current account balance above the account
  bar. `GET /programmer-workflow/balance` calls `deepseekAccount.getBalance`, caches for 30 seconds,
  never returns credentials, and pauses polling while the page is hidden. `balanceDisplay` and
  `balanceRefreshSeconds` (15–600) are editable in Settings.
- **DSH default install**: the repository root is now a normal DSH package
  (`dsh-plugin-programmer-workflow`) with `dsh.bundle.patch`, `dsh.client`, `exports` and `files`.
  `dsh plugin --profile web add github:xukirito/programmer-workflow` installs without a prior Skill
  copy; Host startup copies the bundled Skill to `<DSH_HOME>/skills/programmer-workflow` when absent.
- **Kimi quick settings**: Windows users double-click the packaged `Open-Settings.vbs`; it reuses the
  loopback `/quick` service or starts a hidden local server, with no command entry or model turn.
  Kimi custom-plugin details may not render homepage links, so the VBS launcher—not the manifest link—is
  the documented click entry. `/programmer-workflow:settings` remains a fallback.
- Settings pages (DSH React and local HTML) gained the screenshot switch; DSH also gained balance
  display/refresh controls. `docs/spec.json` and the generated Architecture/Features pages were
  updated for the new modules and flows.

### Changed

- Package/CLI version is `0.1.1`; the DSH package name is `dsh-plugin-programmer-workflow` (was the
  local-only `@local/programmer-workflow`).
- `boot` filters the environment cache entry out of the rendered memory block to avoid duplicating the
  compact environment line.
- README, `dsh-plugin/README.md`, `docs/Install.html`, `SKILL.md`, `SYSTEM.md` and the Kimi manifest
  document the new install path and tools.

### Known limitations (0.1.1)

- Windows Chinese window enumeration and UTF-8 streaming were verified; model transcription requires
  an Agent image-reading turn. DSH's direct command cannot itself invoke the model. Linux capture paths
  are implemented but not exercised on a graphical Linux session in this environment.
- The Kimi quick-settings server depends on a Python executable on PATH and a surviving SessionStart
  hook process; if the port is occupied or the process is recycled, use
  `/programmer-workflow:settings`.
- `dsh plugin remove @local/programmer-workflow` can report `bundle-in-use` if the old bundle is still
  in the profile's `bundles` list; remove the old dependency manually in the profile after backing it up.
- Migration verification limits from 0.1.0 still apply.

## [Unreleased]

### Added

- Kimi Code configuration surface: `/programmer-workflow:settings` starts
  `companion.py settings --host kimi --workspace . --open`, which serves a token-protected page on
  `127.0.0.1` and reads/writes the host's own `<host-home>/programmer-workflow/config.json`.
  The Kimi manifest is unchanged (no `settings`, `configFile`, `apps` or `inject` fields) and the page
  does not load `dsh-plugin/client.js` or React.
- `scripts/lib/config.py`: strict field validation, lock + read + merge + validate + atomic write,
  host isolation, and reset that only rewrites the current host's config while leaving memory intact.
- `scripts/lib/settings.py` plus `templates/settings.{html,css,js}`: grouped settings UI (plugin data,
  workspace paths, memory, workflow/debug, docs/prototype, two-stage migration), explicit host switch,
  unsaved-change feedback, field-level errors, light/dark tokens, responsive layout and keyboard/ARIA
  support. The page only prepares migration/rollback scripts.
- Stage 1 launcher generation in Python (`run-stage1-plugin.cmd` / `run-stage1-rollback-plugin.cmd`) and
  a testable Python implementation of the stage 2 rules (`KIMI_MIG_SRC` / `KIMI_MIG_DEST`, paired adapter,
  nested-target check, `runtime-state.json`).
- Managed-plugin CLI resolution: a running `scripts/companion.py` may serve stage 1 only for the host
  that started it; the Kimi managed copy is never reused as DSH/CodeBuddy's CLI.
- Tests: `tests/test_settings.py` (config round-trips, host isolation, strict validation, token/HTTP
  rules, static whitelist, body limit, `boot --json`), plus `test_hosts.py`, `test_migration.py` and
  `test_manifests.py` coverage for managed CLI scope, launchers and the settings surface.

### Changed

- README / README.en compatibility matrices and configuration entry points now describe the Kimi local
  settings page; `SKILL.md`, `references/hosts.md`, `AGENTS.md` and `docs/spec.json` were regenerated.
- `docs/Architecture.html` and `docs/Features.html` are regenerated from the updated spec; the generated
  HTML is not edited by hand.

### Known limitations (Unreleased)

- The local page was verified with Edge/Chromium against a disposable loopback server at 1440×900,
  1024×768, 768×1024 and 390×844 in light/dark mode. It has **not** yet been run inside a real Kimi Code
  session; the managed-plugin path is covered by unit tests and CLI resolution, not by a live Kimi install.
- Copy success feedback is covered by a stubbed clipboard in the CDP run. Headless Edge denied real
  clipboard access, so the manual-copy fallback was exercised; a real browser copy was not verified.
- Real migration/rollback was not executed against user data; only temporary-directory and contract tests.

### Planned before the first release

- Verify stage 1 / stage 2 migration against real DSH and Kimi data, then update the support matrix.
- Re-check the DSH Client bundle contract against the current DSH release.
- Add end-to-end checks for CodeBuddy, Claude Code, Cursor and Codex host discovery.
- Decide whether an installable archive (skill only / DSH bundle) is worth shipping.

## [0.1.0] - 2026-10-31 (preview, source only)

First public source preview. This is the repository version that was previously developed as an internal
`0.1.1` tree; the public preview is renumbered to `0.1.0` and is not a stable API.

### Added

- Portable Agent Skill with `SKILL.md`, references, commands and a Python standard-library CLI
  (`boot`, `memory`, `scan`, `map`, `env`, `stall`, `run`, `plan`, `triage`, `docs`, `prototype`,
  `migrate-plugin`, `doctor`).
- Approval-gated user/workspace memory with `proposed` / `active` / `rejected` states and per-host roots.
- `workflowMode` (`plan` / `full-authority`), plan Markdown/HTML rendering and a run wrapper with consent,
  timeout and log capture.
- Stall escalation to industry practice / instrumented debugging / re-interpretation / scope reduction.
- Offline `Architecture.html` and `Features.html` with filtering, a module graph and review export.
- Offline `Prototype.html` with multiple directions, viewport preview and review export.
- DSH Host/Client bundle: **Settings → Programmer Workflow**, per-host config/status, workspace paths,
  memory switches, migration controls and a `migration.html` tutorial.
- Two-stage migration: plugin data (stage 1) and editor runtime data (stage 2), with SHA-256 inventory,
  independent backups, target-bound launchers and paired rollback scripts for DSH.
- Windows `install.ps1` and macOS/Linux `install.sh`, managed bootstrap blocks, Kimi and Claude manifests.
- Tests for manifests, hosts, memory, migration, docs/prototypes, the DSH client contract and installer
  dry runs.

### Changed

- Public preview renumbered to `0.1.0`; version fields are read from `VERSION` in the manifest test.
- Removed machine-specific default migration targets and the Kimi legacy tool path from the shipped code.
- README rewritten for source download/install, with an explicit compatibility matrix and honest
  verification caveats; English README added.
- Test fixtures use generic example paths instead of a real user profile.

### Known limitations

- Real-host migration has **not** been executed by this plugin; coverage is temporary-directory and
  contract tests only.
- CodeBuddy / Claude / Cursor / Codex runtime migration is not adapted.
- Kimi runtime migration requires a user-supplied tool directory containing both migrate and rollback
  scripts; custom `KIMI_HOME` additionally requires the adapter to honor `KIMI_MIG_SRC`.
- Nested junctions are only partially supported (same target root); cross-root manifest rebuilds are
  refused.
- DSH Client bundle loading is pinned to the tested `0.2.1-rc.5` behavior; DSH upgrades may require a
  bundle reinstall or code update.
- The DSH desktop app is currently distributed for Windows; skill installs work on macOS/Linux, but the
  DSH settings page has not been validated there.

### Security

- No secrets, runtime memory, credentials or logs are part of the repository.
- The plugin never uploads data; all state is local by default.
- Destructive commands are blocked in both workflow modes; `--allow-destructive` requires explicit
  confirmation.
