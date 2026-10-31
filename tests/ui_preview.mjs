// Renders the Settings page to static HTML for visual review in a browser.
//
// Uses the same fake `window.__ModuleLoader__`, `react` and hooks as
// tests/client_plugin_test.mjs, then serializes the element tree. Output is a
// review artifact only (not shipped); open the generated HTML or screenshot it.
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

const source = fs.readFileSync(path.resolve('dsh-plugin/client.js'), 'utf8')
const outDir = path.resolve('.tmp-tests', 'ui-preview')
fs.mkdirSync(outDir, { recursive: true })

// ---------------------------------------------------------------- module loader
const registrations = []
const sandbox = {
  window: { __ModuleLoader__: { load(spec) { registrations.push(spec) } } },
  console,
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  navigator: { clipboard: { writeText: async () => {} } },
  document: { createElement: () => ({ select() {}, remove() {} }), body: { appendChild() {} }, execCommand() {} },
}
vm.runInNewContext(source, sandbox, { filename: 'dsh-plugin/client.js' })
const registration = registrations[0]
if (!registration) throw new Error('client bundle did not register a factory')

// ---------------------------------------------------------------- react + hooks
const stores = new Map()
let currentStore = null
function storeOf(component) {
  let store = stores.get(component)
  if (!store) {
    store = { hooks: [], index: 0, dirty: false, effectRan: false, effects: [] }
    stores.set(component, store)
  }
  return store
}
const React = {
  createElement(type, props, ...children) {
    return { type, props: { ...(props || {}), children: children.length <= 1 ? children[0] : children } }
  },
  useState(initial) {
    const store = currentStore
    const slot = store.index++
    if (!(slot in store.hooks)) store.hooks[slot] = typeof initial === 'function' ? initial() : initial
    return [store.hooks[slot], (next) => {
      store.hooks[slot] = typeof next === 'function' ? next(store.hooks[slot]) : next
      store.dirty = true
    }]
  },
  useEffect(effect) {
    const store = currentStore
    const slot = store.index++
    if (!store.effectRan) store.effects[slot] = effect
  },
  useCallback(callback) {
    const store = currentStore
    const slot = store.index++
    if (!(slot in store.hooks)) store.hooks[slot] = callback
    return store.hooks[slot]
  },
}
let requireImpl = (id) => {
  if (id === 'react') return React
  throw new Error('unexpected module ' + id)
}
const clientModule = registration.factory((id) => requireImpl(id))
const registered = []
const ctx = {
  slots: {
    inject(key, callback) { callback(); return () => {} },
    register(options, component) { registered.push({ options, component }); return () => {} },
  },
}
clientModule.apply(ctx)
const page = (registered.find((item) => item.options.name === 'settings.section') || registered[0]).component

// ------------------------------------------------------------------- scenarios
const baseStatus = {
  version: '0.1.0',
  paths: { config: 'C:/Users/example/.dsh/programmer-workflow/config.json', memory: 'C:/Users/example/.dsh/programmer-workflow/memory' },
  appData: { isJunction: true, target: 'D:/AgentData/migrated/.dsh' },
  hosts: {
    dsh: { label: 'DeepSeek Harness', configPath: 'C:/Users/example/.dsh/programmer-workflow/config.json', planFile: 'plan.md', dataDir: '.dsh', skillPath: 'C:/Users/example/.dsh/skills/programmer-workflow/SKILL.md', installed: true, projectLevel: false },
  },
  pluginData: {
    coverage: 'external',
    globalRoot: 'C:/Users/example/.dsh/programmer-workflow',
    realGlobalRoot: 'D:/AgentData/migrated/.dsh/programmer-workflow',
    memoryRoot: 'C:/Users/example/.dsh/programmer-workflow/memory',
    configPath: 'C:/Users/example/.dsh/programmer-workflow/config.json',
    insideHostHome: true,
    resolvedOutsideHostHome: true,
    externallyOverridden: false,
    legacy: { conflict: false, hasMemory: false, imported: false },
    inventory: { counts: { active: 5, proposed: 1, rejected: 0 }, sha256: { memory: '0'.repeat(64) } },
  },
  pluginMigration: {
    status: 'completed', completed: true, verified: false, completedVia: 'relocated',
    relocated: true, systemDrive: 'C:',
    actualTarget: 'D:/AgentData/migrated/.dsh/programmer-workflow',
    targetRoot: 'D:/AgentData/migrated',
    linkStatus: 'host-home-junction', hostHomeLink: true, actualTargetExists: true,
    source: 'C:/Users/example/.dsh/programmer-workflow', target: 'D:/AgentData/migrated/.dsh/programmer-workflow',
    backup: 'C:/Users/example/.dsh/.programmer-workflow-migration/backups/20261031-stage1-apply/plugin',
    supported: true, ready: true,
  },
  runtimeMigration: {
    status: 'ready', supported: true, adapterReady: true,
    stage2Status: 'completed', stage2Completed: true, stage2Verified: false,
    stage2CompletedVia: 'relocated', stage2Relocated: true, systemDrive: 'C:',
    stage1Done: true,
    actualLocation: 'D:/AgentData/migrated/.dsh',
    actualLocationExists: true, stage2LinkStatus: 'junction', appDataRelocated: true,
    target: 'D:/AgentData/migrated/.dsh',
    launcher: 'C:/Users/example/.dsh/.programmer-workflow-migration/run-stage2-runtime.cmd',
    rollbackLauncher: 'C:/Users/example/.dsh/.programmer-workflow-migration/run-stage2-rollback.cmd',
  },
  workflowModes: [
    { id: 'plan', label: 'Plan', description: 'approve first' },
    { id: 'full-authority', label: 'Full authority', description: 'run directly' },
  ],
}
const freshStatus = JSON.parse(JSON.stringify(baseStatus))
freshStatus.pluginMigration = {
  ...baseStatus.pluginMigration,
  status: 'not-started', completed: false, verified: false, completedVia: null, relocated: false,
  actualTarget: '', linkStatus: 'directory', hostHomeLink: true, actualTargetExists: false,
  target: '',
}
freshStatus.runtimeMigration = {
  ...baseStatus.runtimeMigration,
  status: 'blocked', stage2Status: 'blocked', stage2Completed: false, stage2Verified: false,
  stage2CompletedVia: null, stage2Relocated: false, actualLocation: '', actualLocationExists: false,
  stage2LinkStatus: 'missing', appDataRelocated: true,
}
const config = {
  workspaceDataDir: '.programmer-workflow', debugLogDir: 'debug-logs', docsDir: 'docs', prototypeFile: 'Prototype.html',
  userMemoryEnabled: true, workspaceMemoryEnabled: true, satisfactionThreshold: 3, bugfixThreshold: 2,
  workflowMode: 'plan', devOnlyAutoInstrument: true, docsEnabled: true, prototypeEnabled: true,
  retentionDays: 30, language: 'zh-CN', migrationActionEnabled: true, planFormat: 'md',
  pluginMigrationTargetRoot: 'D:/AgentData/migrated',
  runtimeMigrationTargetRoot: 'D:/AgentData/migrated',
  kimiMigrationTools: '',
}

// ------------------------------------------------------------------- serialize
const escapeHtml = (value) => String(value).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
function renderComponent(component, props) {
  const store = storeOf(component)
  store.index = 0
  store.dirty = false
  const previous = currentStore
  currentStore = store
  try {
    return component(props)
  } finally {
    currentStore = previous
  }
}
function attrsOf(props) {
  const attrs = []
  for (const [key, value] of Object.entries(props || {})) {
    if (key === 'children' || key === 'key' || key.startsWith('on')) continue
    if (value === null || value === undefined || value === false) continue
    const name = key === 'className' ? 'class' : key === 'htmlFor' ? 'for' : key
    if (name === 'value') continue
    if (value === true) { attrs.push(name); continue }
    attrs.push(`${name}="${escapeHtml(value)}"`)
  }
  return attrs.length ? ' ' + attrs.join(' ') : ''
}
function renderChildren(children, selectValue) {
  const list = Array.isArray(children) ? children : [children]
  return list.map((child) => {
    if (child && typeof child === 'object' && !Array.isArray(child) && child.type === 'option') {
      const selected = selectValue !== undefined && String(child.props.value) === String(selectValue)
      const optionProps = selected ? { ...child.props, selected: true } : child.props
      return renderNode({ ...child, props: optionProps })
    }
    return renderNode(child)
  }).join('')
}
function renderNode(node) {
  if (node === null || node === undefined || node === false || node === true) return ''
  if (Array.isArray(node)) return node.map(renderNode).join('')
  if (typeof node === 'string' || typeof node === 'number') return escapeHtml(node)
  if (typeof node !== 'object') return ''
  if (typeof node.type === 'function') return renderNode(renderComponent(node.type, node.props))
  if (node.type === 'style') return `<style>${node.props.children || ''}</style>`
  const tag = node.type
  const attrs = attrsOf(node.props)
  if (tag === 'input') {
    const value = node.props.value === undefined ? '' : node.props.value
    return `<input${attrs} value="${escapeHtml(value)}">`
  }
  if (tag === 'select') return `<select${attrs}>${renderChildren(node.props.children, node.props.value)}</select>`
  return `<${tag}${attrs}>${renderChildren(node.props.children)}</${tag}>`
}

async function renderPage(statusPayload) {
  stores.clear()
  currentStore = null
  requireImpl = (id) => {
    if (id === 'react') return React
    throw new Error('unexpected module ' + id)
  }
  sandbox.fetch = async () => ({ ok: true, json: async () => ({ ok: true, host: 'dsh', config, status: statusPayload }) })
  let html = ''
  for (let round = 0; round < 20; round += 1) {
    const tree = renderComponent(page, { close() {} })
    html = renderNode(tree)
    let ranEffect = false
    for (const store of stores.values()) {
      if (!store.effectRan && store.effects.length) {
        store.effectRan = true
        for (const effect of store.effects) if (effect) await effect()
        ranEffect = true
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 0))
    const dirty = [...stores.values()].some((store) => store.dirty)
    if (!dirty && !ranEffect) break
  }
  return html
}

// ------------------------------------------------------------------ html shell
const lightVars = `
  --dsw-alias-bg-base:#ffffff; --dsw-alias-bg-layer-1:#ffffff; --dsw-alias-bg-layer-2:#f5f7fb;
  --dsw-alias-bg-overlay:#ffffff; --dsw-alias-border-l1:#e3e8f0; --dsw-alias-border-l2:#c9d2e0;
  --dsw-alias-brand-primary:#4f46e5; --dsw-alias-label-primary:#0f172a; --dsw-alias-label-secondary:#5c6b82;
  --dsw-alias-state-success-primary:#0f766e; --dsw-alias-state-warn-primary:#b45309;
  --dsw-alias-state-error-primary:#b91c1c; --dsw-alias-state-idle-primary:#64748b;
  background:#eef1f6; color:#0f172a;
`
const darkVars = `
  --dsw-alias-bg-base:#0b1018; --dsw-alias-bg-layer-1:#111827; --dsw-alias-bg-layer-2:#182134;
  --dsw-alias-bg-overlay:#111827; --dsw-alias-border-l1:#26324a; --dsw-alias-border-l2:#3a4a66;
  --dsw-alias-brand-primary:#818cf8; --dsw-alias-label-primary:#e7edf7; --dsw-alias-label-secondary:#9aabc3;
  --dsw-alias-state-success-primary:#34d399; --dsw-alias-state-warn-primary:#fbbf24;
  --dsw-alias-state-error-primary:#f87171; --dsw-alias-state-idle-primary:#94a3b8;
  background:#070b12; color:#e7edf7;
`
function documentFor(body, theme, panelHeight, scrollToBottom, panelWidth) {
  const vars = theme === 'dark' ? darkVars : lightVars
  const width = panelWidth || 620
  const scroll = scrollToBottom
    ? `<script>window.addEventListener('load', function () { var p = document.querySelector('.panel'); p.scrollTop = p.scrollHeight; });</script>`
    : ''
  return `<!doctype html>
<html lang="zh-CN" data-theme="${theme}">
<head><meta charset="utf-8"><title>Programmer Workflow settings · ${theme}</title>
<style>
  :root { ${vars} }
  * { box-sizing: border-box; }
  html, body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; }
  body { padding: 18px; display:flex; justify-content:center; background: ${theme === 'dark' ? '#070b12' : '#eef1f6'}; }
  .panel { width: ${width}px; max-width:100%; ${panelHeight ? `height:${panelHeight}px; overflow:auto;` : ''} background: var(--dsw-alias-bg-base); border:1px solid var(--dsw-alias-border-l1); border-radius:14px; padding:20px 20px 0; }
  .hint { position:fixed; top:8px; right:12px; font:11px ui-monospace,monospace; color:#94a3b8; }
</style></head>
<body><div class="hint">${theme} · panel ${width}px${panelHeight ? ' · scrolled' : ''}</div><div class="panel">${body}</div>${scroll}
<script>
  window.addEventListener('load', function () {
    var hint = document.querySelector('.hint');
    if (document.documentElement.scrollWidth > window.innerWidth + 1) hint.textContent += ' · OVERFLOW';
    var panel = document.querySelector('.panel');
    if (panel && panel.scrollWidth > panel.clientWidth + 1) hint.textContent += ' · PANEL-OVERFLOW';
  });
</script></body></html>`
}

const completed = await renderPage(baseStatus)
const fresh = await renderPage(freshStatus)
fs.writeFileSync(path.join(outDir, 'ui-light.html'), documentFor(completed, 'light'), 'utf8')
fs.writeFileSync(path.join(outDir, 'ui-dark.html'), documentFor(completed, 'dark'), 'utf8')
fs.writeFileSync(path.join(outDir, 'ui-fresh.html'), documentFor(fresh, 'light'), 'utf8')
fs.writeFileSync(path.join(outDir, 'ui-narrow.html'), documentFor(completed, 'light', 0, false, 420), 'utf8')
fs.writeFileSync(path.join(outDir, 'ui-light-scrolled.html'), documentFor(completed, 'light', 760, true), 'utf8')
console.log('preview written to', outDir)
