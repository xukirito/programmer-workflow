# AGENTS.md · Programmer Workflow repository

This repository builds a portable Agent Skill / plugin. The installable payload is `skills/programmer-workflow/`; the root also holds host manifests, installers, examples, tests, and this project's own docs.

## Read first

- `README.md` — concise user-facing capabilities, host roots, commands and safety boundaries.
- `skills/programmer-workflow/SKILL.md` — the protocol the model follows.
- `skills/programmer-workflow/references/` — detailed protocols; load only the relevant file.
- `docs/spec.json` — the spec used to generate this project's own `docs/Architecture.html` and `docs/Features.html`.

## Development rules

- **Do not hand-edit generated HTML** (`docs/Architecture.html`, `docs/Features.html`, `examples/demo-output/*.html`, `Prototype.html`). Edit the spec or templates and re-render.
- **Keep `SKILL.md` frontmatter description ≤ 500 chars** (DSH catalog limit). The test suite checks it.
- **No third-party runtime dependencies.** Python standard library only; HTML/CSS/JS must work offline with no CDN.
- **Keep the review contract stable**: `wc-data` JSON, `spec_hash`, localStorage key, review JSON fields.
- **Sanitize prototype HTML** in `lib/render/spec.py`; never add `eval`, inline event handlers, or remote resources.
- **Memory defaults are tested** with temporary homes; do not write into the real `<DSH_HOME>/programmer-workflow` during development.
- **Windows paths** contain spaces in some environments; quote them in commands and HTML examples.
- **Execution policy**: this machine may block `.ps1`; use `pwsh -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 ...` or the test's bypassed invocation.

## Regenerate artifacts

```bash
python tests/run_tests.py
python skills/programmer-workflow/scripts/companion.py docs --host dsh --spec docs/spec.json --out docs
python skills/programmer-workflow/scripts/companion.py prototype --host dsh --spec examples/prototype.sample.json --out examples/demo-output/Prototype.html
```

To rebuild the example prototype spec:

```bash
python examples/build_prototype_spec.py
```

## Test expectations

- Python 3.8+ (3.8 is supported even though it is EOL).
- `WC_NODE` may point to a Node binary for inline-JS syntax checks; otherwise that check is skipped.
- Tests use `.tmp-tests/` under the workspace because the host sandbox may deny the system temp directory.
- The installer DryRun test is Windows-only and uses `-ExecutionPolicy Bypass`.

## Package layout

- `skills/programmer-workflow/scripts/companion.py` — CLI entry (including `settings`).
- `skills/programmer-workflow/scripts/lib/` — memory, scan, debug, stall, render, strict `config.py`, local `settings.py`, environment preflight and model-vision `screenshot.py` capture.
- `skills/programmer-workflow/scripts/platform/` — Windows capture helper; writes UTF-8 and requires a UTF-8 BOM for Windows PowerShell 5.
- `skills/programmer-workflow/templates/` — `base.css`, `docs.*`, `prototype.*`, `review.js`, `settings.html/css/js`.
- `kimi.plugin.json` + `SYSTEM.md` + `commands/` + `scripts/kimi_settings_hook.py` + `Open-Settings.vbs` — Kimi plugin surface; Windows users double-click the VBS launcher, while `settings.md` remains the fallback.
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — Claude Code plugin surface.
- `dsh-plugin/` — DeepSeek Harness Host/Client plugin: per-host Settings, config/status, two-stage migration preparation and `migration.html`.
- `dsh-plugin/dsh-migration-tools/` — bundled DSH runtime migration/rollback scripts, generated into target-bound launchers by Settings.
- `docs/Install.html` / `docs/Migration.html` — three-host install guide and migration tutorial.
- `docs/GitHub-Publish.md` / `docs/Reinstall-DSH.md` — maintainer publish steps and data-preserving DSH reinstall.
- `README.en.md` / `CHANGELOG.md` — English entry point and version/limitations log.
- `install.ps1` / `install.sh` — copy skills and optional managed bootstrap blocks (including CodeBuddy project target).
- `bootstrap/*.example` — manual snippets; not auto-loaded (the `.example` suffix keeps agents from treating them as project instructions).

## Using the skill in this repo

The skill is installed at `.agents/skills/programmer-workflow/` for project-level discovery after running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets project -ProjectRoot . -HostId dsh -Bootstrap
# CodeBuddy users can add: -Targets codebuddy (writes .codebuddy/skills + CODEBUDDY.md)
# Generic project: -HostId generic
```

Start a new session to load it. The managed block appended to this file runs `boot` before tasks.

<!-- programmer-workflow:start -->
## Programmer Workflow (managed)

At the start of every task, load the `programmer-workflow` skill if it is available. Before acting, run:

```
python ".agents\skills\programmer-workflow\scripts\companion.py" boot --host dsh --workspace .
```

Obey **active** memory entries. Treat **proposed** entries as suggestions that need the user's approval first. If active memory conflicts with the user's current instruction, ask which one to keep. Follow the skill's ask, stall, debugging, docs and prototype protocols. Do not edit this block by hand; the installer owns it.
<!-- programmer-workflow:end -->
