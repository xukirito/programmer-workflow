# Prototype — UI, art, and model direction

Request 6. When the user needs something aesthetic, do not describe it only in prose. Generate `Prototype.html`, open it in a browser, and let them point at what they mean.

## When to use

- UI/UX: pages, dashboards, flows, navigation, components, design systems.
- Visual identity: logo, icon, color, typography, brand tone.
- Art direction: moodboard, style frames, materials, lighting, silhouettes.
- Game/3D concept: character or environment direction, turnaround references, palette.
- “先做个原型 / 给我几个方向 / 看看效果”.

## Clarify first

Ask at most 3 questions:

1. Platform and primary screen size (desktop web / mobile / desktop app / game).
2. Audience and context of use.
3. Must-keep content, brand constraints, or references.

If the user says “你决定”, proceed and list assumptions in the prototype. Do not ask ten questions about shade of blue.

## Differentiate directions

Each direction must differ in **information architecture and visual language**, not just accent color:

- density: command deck vs calm studio;
- tone: internal tool vs independent product vs paper notebook;
- platform priority: desktop-first vs mobile-first;
- structure: sidebar vs top navigation vs canvas-first;
- typography: sans/system vs serif/editorial;
- color: dark/technical vs warm/paper vs high-contrast.

Two strong directions beat four weak ones. Three is the maximum for a first review.

## Spec

```json
{
  "project": {
    "name": "Acme Console",
    "tagline": "一句话定位",
    "summary": "这段原型想验证什么。",
    "language": "zh-CN",
    "confidence": "medium",
    "source": "用户描述 + 参考图"
  },
  "brief": {
    "goal": "用户要完成的核心任务。",
    "audience": "谁在什么场景用。",
    "platform": "桌面 Web / 移动 / 桌面应用。",
    "constraints": ["必须保留的字段", "不能引入的东西"],
    "success_criteria": ["用户能在 30 秒内完成 X"]
  },
  "assumptions": [
    "用户主要在大屏工作",
    "首版不做多人协作"
  ],
  "directions": [
    {
      "id": "A",
      "name": "指挥台 · Mission Control",
      "thesis": "为什么这个方向成立，1–2 句。",
      "when_to_use": "什么场景/用户适合。",
      "palette": [
        { "name": "背景", "hex": "#0a0f1d", "role": "background" },
        { "name": "强调", "hex": "#8aa4ff", "role": "accent" }
      ],
      "typography": [
        { "name": "标题", "family": "Segoe UI", "size": "24px", "weight": "700" }
      ],
      "screens": [
        {
          "id": "dashboard",
          "name": "控制台",
          "device": "desktop",
          "html": "<div style=\"padding:32px\">…</div>",
          "notes": ["首屏第一任务是审批", "只保留 4 个 KPI"]
        }
      ],
      "components": ["KPI 卡", "审批行", "状态标签"],
      "motion": "只做 hover 与淡入，不做大幅位移。",
      "risks": ["深色长时间使用可能疲劳"]
    }
  ],
  "questions": [
    {
      "id": "q1",
      "question": "你更愿意每天打开哪一个？",
      "options": ["A 指挥台", "B 纸感工作台"],
      "default": "B"
    }
  ],
  "review_prompts": [
    "哪个方向更像你每天愿意打开的工具？",
    "首屏最想先看到什么？"
  ]
}
```

## Screen HTML rules

- `html` is inserted into a device frame. Use inline styles or a `<style>` block with a unique prefix (e.g. `.pa-*`).
- No `<script>`, `<iframe>`, inline `on*` handlers, or `javascript:` URLs. The renderer strips them; don't rely on them.
- Do not load external images/fonts/CDNs. Use CSS gradients, inline SVG, and system font stacks.
- Design for the declared device: desktop ~1280×720, tablet ~834×1112, mobile ~390×844.
- Put realistic content in, not “Lorem ipsum”. Use the user's domain language.
- Keep one screen focused; if there are multiple states, add screens rather than cramming.
- Label it as a prototype in the page; the shell already shows a `PROTOTYPE` badge.

Useful shell classes (available globally): `wc-card`, `wc-btn`, `wc-badge`, `wc-chip`, `wc-meta`, `wc-grid`, `wc-input`, `wc-table`. For screen-specific layout, prefer inline styles or prefixed classes to avoid collisions.

## Art / model direction

An HTML page cannot replace a 3D asset, but it can make the direction reviewable:

- **Moodboard**: 4–8 visual tiles made of gradients, SVG shapes, typography, and material notes.
- **Palette**: 5–8 swatches with roles (surface, accent, warning, material, light).
- **Typography**: display/body/mono, with sizes and weights.
- **Form language**: geometric vs organic, silhouette sketches (inline SVG), edge treatment.
- **Materials/lighting**: matte/gloss, roughness, key light, rim light, atmosphere.
- **References**: describe them in words if you cannot embed; do not hotlink.
- **Production notes**: what needs modeling, rigging, texturing, or a style guide.

State clearly: “这是视觉方向原型，不是最终资产；确认方向后再进入建模/切图。”

## Render

```bash
python "<skill>/scripts/companion.py" prototype --host <host> --spec design.json --out Prototype.html
```

Then tell the user:

> 用浏览器打开 `Prototype.html`。可以切换方向/视口，打开“标注模式”在画布上点选留言，底部通过或请求修改，导出评审 JSON。

## Review loop

- The page stores notes and pins in `localStorage` per spec hash.
- Pins are stored with direction, screen, x/y percent, and note; they export in the review JSON.
- Read the review JSON or pasted feedback; group by direction/screen.
- Fix blocking issues first; keep a short changelog in the next reply.
- If the user approves a direction, say what will be produced next (spec, components, assets) and what remains unconfirmed.
- Do not silently switch the chosen direction.

## Common mistakes

- Three directions that are only different accent colors.
- A desktop layout squeezed into mobile instead of a separate mobile screen.
- Fake charts with no labels or units.
- Using a real brand's logo/asset without permission.
- Calling a static mock “interactive” when only the shell is interactive.
- Forgetting the user's must-keep content.
- Overloading the first screen with every feature.
