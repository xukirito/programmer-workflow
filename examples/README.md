# Examples

- `prototype.sample.json` — the spec for the example `Prototype.html` (two directions, desktop + mobile).
- `plan.sample.json` — sample Plan-mode spec used to generate `demo-output/Plan.md` and `Plan.html`.
- `build_prototype_spec.py` — regenerates that spec; the screen HTML lives here so the JSON stays readable.
- `demo-output/` — generated artifacts used for visual checks:
  - `Architecture.html`, `Features.html` — copies of this project's docs at the time of the demo.
  - `Prototype.html` — example design prototype.
  - `Plan.md`, `Plan.html` — Plan-mode review examples (Markdown and interactive HTML).
  - `Install.png` — install/verification guide.
  - `Migration.png` and `ui-*.png` — local-only screenshots captured from a real profile; they contain
    machine paths and are intentionally **not** committed. Regenerate them from `tests/ui_preview.mjs`
    after sanitizing its fixture if you need fresh images.
  - `*.png` — headless-browser screenshots of the overview, module graph, feature list/matrix, and prototype direction B.

Open any `.html` directly in a browser. No server is required.

To regenerate:

```bash
python examples/build_prototype_spec.py
python skills/programmer-workflow/scripts/companion.py prototype --host dsh --spec examples/prototype.sample.json --out examples/demo-output/Prototype.html
python skills/programmer-workflow/scripts/companion.py docs --host dsh --spec docs/spec.json --out examples/demo-output
```
