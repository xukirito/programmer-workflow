// Verifies dsh-plugin/client.js against DSH's real Client loading protocol.
//
// DSH serves `dsh.client` bundles as classic browser scripts into the page's
// `window.__ModuleLoader__` lazy-CJS facade. The script must only register a
// factory; `factory(require)` returns the module exports, and `apply(ctx)` owns
// the Slot registrations through `ctx.slots.inject` / `ctx.slots.register`.
// An ESM bundle, or one that returns a registration object instead of calling
// `ctx.slots.register`, loads "without registering" and the Settings → Plugins
// page reports a sync failure while the Host enable state stays unchanged.
//
// This harness reproduces that contract without a browser: a fake module
// loader, a fake `react` module with a minimal hook runtime, a fake `slots`
// service, and a fake host response for the config endpoint.
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import assert from 'node:assert/strict'

const pluginDir = path.resolve('dsh-plugin')
const pkg = JSON.parse(fs.readFileSync(path.join(pluginDir, 'package.json'), 'utf8'))
const source = fs.readFileSync(path.join(pluginDir, 'client.js'), 'utf8')

// ---------------------------------------------------------------- module loader
const registrations = []
let fetchImpl = async () => {
  throw new Error('unexpected fetch during module materialization')
}
const sandbox = {
  window: {
    __ModuleLoader__: {
      load(spec) {
        registrations.push(spec)
      },
    },
  },
  console,
  fetch: (...args) => fetchImpl(...args),
  navigator: { clipboard: { writeText: async () => {} } },
  document: { createElement: () => ({ select() {}, remove() {} }), body: { appendChild() {} }, execCommand() {} },
}
vm.runInNewContext(source, sandbox, { filename: 'dsh-plugin/client.js' })

assert.equal(registrations.length, 1, 'the bundle must call window.__ModuleLoader__.load exactly once')
const [registration] = registrations
assert.equal(registration.id, pkg.name, 'the registered factory id must be the package name')
assert.equal(typeof registration.factory, 'function', 'the bundle must register a lazy factory')

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

const requested = []
function requireModule(id) {
  requested.push(id)
  if (id === 'react') return React
  throw new Error('unexpected client module request: ' + id)
}

const clientModule = registration.factory(requireModule)
assert.deepEqual(requested, ['react'], 'the bundle must only require the platform react module')
assert.ok(Array.isArray(clientModule.inject) && clientModule.inject.includes('slots'), 'the Client half must inject the slots service')
assert.equal(typeof clientModule.apply, 'function', 'the Client half must export apply(ctx)')

// ---------------------------------------------------------------- apply + slots
const injected = []
const registered = []
const disposers = []
const ctx = {
  slots: {
    inject(key, callback) {
      injected.push(key)
      const disposersFromCallback = callback()
      disposers.push(disposersFromCallback)
      return () => {}
    },
    register(options, component) {
      assert.equal(typeof component, 'function', 'ctx.slots.register needs a component')
      registered.push({ options, component })
      const dispose = () => {}
      disposers.push(dispose)
      return dispose
    },
  },
}

const returned = clientModule.apply(ctx)
assert.equal(typeof returned, 'function', 'apply must return the inject disposer from ctx.slots.inject')
assert.ok(injected.includes('settings.section'), 'the page must wait for the settings.section slot')
assert.ok(injected.includes('shell.overlay'), 'the migration banner must use the shell.overlay slot')
const settingsRegistration = registered.find((item) => item.options && item.options.name === 'settings.section')
assert.ok(settingsRegistration, 'apply must register the settings page through ctx.slots.register')
assert.ok(registered.some((item) => item.options && item.options.name === 'shell.overlay'), 'apply must register the migration banner')
const { options: entry, component: page } = settingsRegistration
assert.equal(entry.id, 'programmer-workflow')
assert.equal(entry.order, 30)
assert.equal(typeof entry.label, 'string')

// ---------------------------------------------------------------- render the page
const config = {}
const status = {
  version: '0.1.0',
  paths: { config: '/fake/dsh/programmer-workflow/config.json', memory: '/fake/dsh/programmer-workflow/memory' },
  appData: { isJunction: false },
  hosts: {
    dsh: { label: 'DeepSeek Harness', configPath: '/fake/dsh/programmer-workflow/config.json', planFile: 'plan.md', dataDir: '.dsh', skillPath: '/fake/skill', installed: true, projectLevel: false },
    kimi: { label: 'Kimi Code', configPath: '/fake/kimi/programmer-workflow/config.json', planFile: 'plan.md', dataDir: '.kimi', installed: false },
    codebuddy: { label: 'CodeBuddy', configPath: '/fake/codebuddy/programmer-workflow/config.json', planFile: 'plan.md', dataDir: '.codebuddy', installed: false },
  },
  pluginData: {
    coverage: 'covered',
    globalRoot: '/fake/dsh/programmer-workflow',
    realGlobalRoot: '/fake/dsh/programmer-workflow',
    memoryRoot: '/fake/dsh/programmer-workflow/memory',
    configPath: '/fake/dsh/programmer-workflow/config.json',
    insideHostHome: true,
    resolvedOutsideHostHome: false,
    externallyOverridden: false,
    legacy: { conflict: false, hasMemory: false, imported: false },
    inventory: { counts: { active: 3, proposed: 0, rejected: 0 }, sha256: { memory: '0'.repeat(64) } },
  },
  pluginMigration: { status: 'not-started', source: '/fake/dsh/programmer-workflow', target: '', backup: '' },
  runtimeMigration: { status: 'blocked', supported: false, adapterReady: false, reason: 'not adapted', detectedToolsPath: null },
  workflowModes: [
    { id: 'plan', label: 'Plan', description: 'approve first' },
    { id: 'full-authority', label: 'Full authority', description: 'run without per-command approval' },
  ],
}

const fetches = []
fetchImpl = async (url, init) => {
  fetches.push(`${(init && init.method) || 'GET'} ${url}`)
  return {
    ok: true,
    json: async () => ({ ok: true, host: 'dsh', config, status, launcher: '/fake/launcher.cmd' }),
  }
}

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

function collect(node, out) {
  if (node === null || node === undefined || node === false || node === true) return out
  if (Array.isArray(node)) {
    for (const child of node) collect(child, out)
    return out
  }
  if (typeof node === 'string' || typeof node === 'number') {
    out.push(String(node))
    return out
  }
  if (typeof node === 'object' && node !== null) {
    if (typeof node.type === 'function') return collect(renderComponent(node.type, node.props), out)
    if (node.props && node.props.children !== undefined) collect(node.props.children, out)
  }
  return out
}

const pageComponent = page
function resetStores() {
  stores.clear()
  currentStore = null
}

async function renderPage(statusPayload, configPayload = {}) {
  resetStores()
  fetchImpl = async (url, init) => {
    fetches.push(`${(init && init.method) || 'GET'} ${url}`)
    return {
      ok: true,
      json: async () => ({ ok: true, host: 'dsh', config: configPayload, status: statusPayload, launcher: '/fake/launcher.cmd' }),
    }
  }
  let rendered = ''
  for (let round = 0; round < 20; round += 1) {
    const tree = renderComponent(pageComponent, { close() {} })
    rendered = collect(tree, []).join(' ')
    let ranEffect = false
    for (const store of stores.values()) {
      if (!store.effectRan && store.effects.length) {
        store.effectRan = true
        for (const effect of store.effects) {
          if (effect) await effect()
        }
        ranEffect = true
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 0))
    const dirty = [...stores.values()].some((store) => store.dirty)
    if (!dirty && !ranEffect) break
  }
  return rendered
}

function statusWith(overrides) {
  return {
    ...status,
    ...(overrides || {}),
    pluginMigration: { ...status.pluginMigration, ...((overrides && overrides.pluginMigration) || {}) },
    runtimeMigration: { ...status.runtimeMigration, ...((overrides && overrides.runtimeMigration) || {}) },
  }
}

const notStarted = await renderPage(statusWith({}))
assert.ok(fetches.some((line) => line.includes('/programmer-workflow/config')), 'the page must read its config over the plugin route')
assert.match(notStarted, /程序员工作流/, 'the page must render its title')
assert.match(notStarted, /插件数据位置/)
assert.match(notStarted, /工作流与调试/)
assert.match(notStarted, /数据迁移（两个阶段）/)
assert.match(notStarted, /保存设置/)
assert.match(notStarted, /准备第一阶段脚本/, 'a fresh profile offers the stage 1 prepare action')
assert.doesNotMatch(notStarted, /无需再次操作/, 'a fresh profile must not claim a completed migration')
assert.doesNotMatch(notStarted, /读取配置失败/, 'the page must not fall into its error state')
assert.match(notStarted, /迁移教程与支持矩阵/, 'the settings page links to the migration guide')

// Verified stage 1: no repeated prompt, the default action is "move to a new address".
const completed = await renderPage(statusWith({
  config: { promptMigration: false },
  pluginMigration: {
    status: 'completed',
    completed: true,
    verifiedAt: '2026-10-31T00:00:00.000Z',
    actualTarget: 'D:/AgentData/.dsh/programmer-workflow',
    linkStatus: 'junction',
    actualTargetExists: true,
    target: 'D:/AgentData/.dsh/programmer-workflow',
    backup: 'C:/backups/stage1',
  },
  runtimeMigration: {
    status: 'ready',
    supported: true,
    adapterReady: true,
    stage2Completed: true,
    stage2Status: 'completed',
    actualLocation: 'D:/AgentData/.dsh',
    stage2LinkStatus: 'junction',
    actualLocationExists: true,
  },
}))
assert.match(completed, /插件数据已迁移，无需再次操作/)
assert.match(completed, /D:\/AgentData\/\.dsh\/programmer-workflow/)
assert.match(completed, /编辑器运行数据已迁移，无需再次操作/)
assert.match(completed, /D:\/AgentData\/\.dsh/)
assert.match(completed, /迁移到新地址/)
assert.doesNotMatch(completed, /准备第一阶段脚本/, 'a verified stage 1 must not offer the first-time prepare button')
assert.doesNotMatch(completed, /尚未迁移/, 'a verified stage 1 must not keep warning about migration')

// A real landing off the system drive counts as done even without our record.
const relocated = await renderPage(statusWith({
  pluginMigration: {
    status: 'completed',
    completed: true,
    verified: false,
    completedVia: 'relocated',
    relocated: true,
    systemDrive: 'C:',
    actualTarget: 'D:/AgentData/.dsh/programmer-workflow',
    linkStatus: 'junction',
    actualTargetExists: true,
  },
  runtimeMigration: {
    status: 'ready',
    supported: true,
    adapterReady: true,
    stage2Completed: true,
    stage2Verified: false,
    stage2CompletedVia: 'relocated',
    stage2Relocated: true,
    stage2Status: 'completed',
    actualLocation: 'D:/AgentData/.dsh',
    stage2LinkStatus: 'junction',
    actualLocationExists: true,
  },
}))
assert.match(relocated, /插件数据已迁移，无需再次操作/)
assert.match(relocated, /编辑器运行数据已迁移，无需再次操作/)
assert.match(relocated, /已有迁移/)
assert.match(relocated, /不在系统盘/)
assert.doesNotMatch(relocated, /尚未迁移/)
assert.doesNotMatch(relocated, /准备第一阶段脚本/)

// Prepared is not completed.
const prepared = await renderPage(statusWith({
  pluginMigration: {
    status: 'prepared',
    prepared: true,
    pending: { launcher: 'C:/control/run-stage1-plugin.cmd', target: 'D:/New/.dsh/programmer-workflow' },
    target: 'D:/New/.dsh/programmer-workflow',
  },
}))
assert.match(prepared, /脚本已生成，尚未执行/)
assert.doesNotMatch(prepared, /已迁移，无需再次操作/, 'prepared must never render as completed')

// A link this plugin did not create is reported, never faked as verified.
const external = await renderPage(statusWith({
  pluginMigration: {
    status: 'external',
    external: true,
    actualTarget: 'E:/ManuallyMoved/.dsh/programmer-workflow',
    linkStatus: 'junction',
  },
}))
assert.match(external, /检测到已有迁移链接/)
assert.doesNotMatch(external, /已迁移，无需再次操作/)

console.log('client plugin tests ok')
