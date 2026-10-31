# Changelog

All notable changes to Programmer Workflow. The project is in **v0.1.0 preview** and has **no GitHub
Release or tag yet**; entries below describe the source tree, not a published binary.

## [Unreleased]

### Planned before the first release

- Verify stage 1 / stage 2 migration against real DSH and Kimi data, then update the support matrix.
- Re-check the DSH Client bundle contract against the current DSH release.
- Add end-to-end checks for CodeBuddy, Claude Code, Cursor and Codex host discovery.
- Decide whether an installable archive (skill only / DSH bundle) is worth shipping.

## [0.1.0] - 2026-10-31 (preview, source only)

First public source preview. This is the repository version that was previously developed as an internal
`0.2.0` tree; the public preview is renumbered to `0.1.0` and is not a stable API.

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
