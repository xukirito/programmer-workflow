# Architecture & Features docs

Request 5. Trigger phrases include “总结工程架构 / 总结一下工程的功能 / 画个架构图 / 接手这个项目 / summarize architecture/features”. Output is exactly two interactive files in `docs/`:

- `docs/Architecture.html`
- `docs/Features.html`

Both are single-file, offline, and end with a review bar.

## Workflow

1. **Confirm scope** only if the repo is large or ambiguous. Default: whole workspace.
2. **Gather evidence**:
   ```bash
   python "<skill>/scripts/companion.py" map --host <host> --workspace . --out .programmer-workflow/project-map.json
   ```
   Then read manifests, entry points, routes, schemas, tests, CI, and 5–15 key files. Do not rely on directory names alone.
3. **Write the spec** at `docs/spec.json` (or the path the user prefers). It must contain both `architecture` and `features`.
4. **Validate**:
   ```bash
   python "<skill>/scripts/companion.py" docs --host <host> --spec docs/spec.json --check
   ```
5. **Render**:
   ```bash
   python "<skill>/scripts/companion.py" docs --host <host> --spec docs/spec.json --out docs
   ```
6. **Prompt**: “用浏览器打开 `docs/Architecture.html` 和 `docs/Features.html`；可以搜索、筛选、看依赖图，底部提交评审并导出 JSON。”
7. **Review loop**: read pasted feedback or a `*.review.json` the user saved; update the spec; re-render. Mention the spec hash change.

Never write the HTML by hand for this workflow; let the renderer apply the schema, sanitization, and review UI. Hand-editing breaks the contract.

## Evidence rules

- Every module/feature gets at least one `evidence` path (or a user statement). If you cannot find one, set `confidence: "low"` and add a `question`.
- Distinguish:
  - **observed**: file exists, route is registered, test passes;
  - **inferred**: naming/architecture implies behavior;
  - **unknown**: no evidence.
- Do not invent endpoints, modules, or features to fill the page. Empty sections are better than fiction.
- Line counts are filled from the workspace at render time; do not guess them.
- Use repository-relative POSIX paths (`src/app.ts`), not absolute paths.

## Architecture schema

```json
{
  "architecture": {
    "project": {
      "name": "My App",
      "tagline": "一句话定位",
      "summary": "2–4 段：解决什么问题、给谁、边界在哪。",
      "version": "1.2.0",
      "commit": "abc1234",
      "generated_at": "",
      "language": "zh-CN",
      "confidence": "high",
      "scope": ["src", "docs"],
      "source": "源码 + 运行验证"
    },
    "stack": [
      { "name": "Python", "version": "3.12", "role": "后端", "evidence": "pyproject.toml" }
    ],
    "layers": [
      { "id": "api", "name": "接口层", "description": "HTTP 入口与校验" }
    ],
    "modules": [
      {
        "id": "auth",
        "name": "认证",
        "layer": "api",
        "path": "src/auth",
        "role": "登录、会话与权限校验。",
        "responsibilities": ["签发 token", "校验权限"],
        "key_files": [{ "path": "src/auth/service.ts", "purpose": "核心逻辑" }],
        "depends_on": ["db"],
        "used_by": ["api"],
        "evidence": ["src/auth/service.ts", "tests/auth.test.ts"],
        "confidence": "high",
        "notes": "可选"
      }
    ],
    "flows": [
      {
        "id": "login",
        "name": "登录",
        "summary": "从请求到会话建立。",
        "steps": [
          { "actor": "Client", "action": "POST /login", "target": "api", "detail": "提交凭据", "evidence": "src/routes.ts" },
          { "actor": "API", "action": "校验密码", "target": "auth", "detail": "bcrypt compare", "evidence": "src/auth/service.ts" }
        ],
        "artifacts": ["session cookie"],
        "failure_modes": ["密码错误", "账号锁定"]
      }
    ],
    "decisions": [
      {
        "id": "d1",
        "title": "选择 JWT 而非服务端 session",
        "choice": "短期 JWT + refresh token",
        "why": ["无状态扩容"],
        "tradeoffs": ["撤销复杂"],
        "alternatives": ["Redis session"],
        "evidence": ["src/auth/service.ts"],
        "status": "accepted"
      }
    ],
    "risks": [
      {
        "id": "r1",
        "title": "token 刷新竞态",
        "severity": "high",
        "impact": "并发刷新导致登出",
        "likelihood": "中",
        "mitigation": "单飞 + 重试",
        "owner": "auth",
        "evidence": ["src/auth/refresh.ts"]
      }
    ],
    "questions": [
      { "id": "q1", "question": "是否支持多设备会话？", "why": "影响存储与撤销设计", "default": "暂不支持" }
    ],
    "file_index": [
      { "path": "src/auth/service.ts", "module": "auth", "purpose": "核心逻辑", "lines": 0 }
    ],
    "glossary": [
      { "term": "refresh token", "definition": "用于换取新 access token 的长期凭据。" }
    ]
  },
  "features": {
    "project": { "name": "My App", "summary": "...", "language": "zh-CN", "confidence": "high" },
    "domains": [
      { "id": "account", "name": "账号", "description": "注册、登录、权限" }
    ],
    "features": [
      {
        "id": "f-login",
        "name": "登录",
        "domain": "account",
        "status": "implemented",
        "priority": "P0",
        "summary": "邮箱密码登录并建立会话。",
        "user_value": "进入产品。",
        "entry_points": ["POST /login", "src/routes.ts"],
        "user_flow": ["输入邮箱密码", "提交", "设置会话", "跳转首页"],
        "inputs": ["email", "password"],
        "outputs": ["session cookie"],
        "dependencies": [],
        "tests": ["tests/auth.test.ts"],
        "evidence": ["src/auth/service.ts"],
        "confidence": "high",
        "notes": ""
      }
    ],
    "journeys": [
      { "id": "j1", "name": "首次登录", "feature_ids": ["f-login"], "steps": ["打开首页", "登录", "进入控制台"] }
    ],
    "questions": [],
    "glossary": []
  }
}
```

## Field rules

- `status`: `implemented` (works + evidence + test or manual verification), `partial` (main path works, gaps), `planned` (intent only).
- `priority`: `P0`–`P3`; use P0 for core flows.
- `confidence`: `high` (observed + test), `medium` (observed, no test), `low` (inferred).
- `severity`: `high` / `medium` / `low`.
- IDs: stable, short, `[A-Za-z0-9_.:-]`; used for cross-links and graph edges.
- `depends_on` / `used_by` / feature `dependencies` only reference existing IDs; dangling IDs are dropped.
- `file_index.lines` is optional; the CLI fills it from real files when rendering.
- Maximums: 300 file rows, 30 stack items, 30 modules are practical; split a huge repo by scope instead of cramming.

## What the pages give the user

Architecture:
- hero with confidence and scope, KPI strip;
- searchable module cards + layer filters;
- interactive dependency graph (pan/zoom/click);
- flow picker with step timeline, artifacts, failure modes;
- decision cards, risk cards, open questions;
- file index with copy-path buttons;
- review bar: notes, approve / request changes, export JSON, copy summary.

Features:
- domain overview with coverage bars;
- searchable feature cards filtered by status/domain;
- coverage matrix (click a cell to filter);
- user journeys;
- open questions;
- feature drawer with entry points, flow, inputs/outputs, dependencies, tests, evidence;
- same review bar.

## Review loop

- The page stores review state in `localStorage` under `wc-review:<kind>:<spec_hash>`.
- “导出评审 JSON” downloads `programmer-workflow-<kind>-review-<timestamp>.json`.
- “复制摘要” copies Markdown; the user can paste it back.
- When feedback arrives, change the spec and re-render. If the user saved the JSON into the repo (e.g. `docs/architecture.review.json`), read it and apply notes; do not silently ignore blocking notes.
- A new `spec_hash` means old review links are stale; say so.

## Quality checklist

- [ ] Both files exist and open without a server.
- [ ] No external URLs, fonts, or CDN.
- [ ] Every module has a role and evidence; every feature has a status and evidence.
- [ ] At least one flow describes a real end-to-end path.
- [ ] Risks/questions are specific, not generic.
- [ ] The summary distinguishes observed vs inferred.
- [ ] The user was told how to open and review the files.
