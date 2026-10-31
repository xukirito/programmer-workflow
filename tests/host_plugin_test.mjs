import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'

// ------------------------------------------------------------------ sandbox
const root = path.resolve('.tmp-tests')
fs.mkdirSync(root, { recursive: true })
const base = fs.mkdtempSync(path.join(root, 'pwf-host-'))
const dshHome = path.join(base, 'dsh')
const kimiHome = path.join(base, 'kimi')
const codebuddyHome = path.join(base, 'codebuddy')
process.env.DSH_HOME = dshHome
process.env.KIMI_HOME = kimiHome
process.env.CODEBUDDY_HOME = codebuddyHome
// "System drive" defaults to the volume the temp sandbox sits on, so a normal
// temp path is NOT considered relocated; tests that need a moved landing set a
// different drive explicitly.
const baseDrive = path.parse(base).root.replace(/[\\/]+$/, '').toUpperCase()
process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE = baseDrive
for (const name of [
  'PROGRAMMER_WORKFLOW_GLOBAL', 'PROGRAMMER_WORKFLOW_HOME', 'PROGRAMMER_WORKFLOW_CLI',
  'KIMI_MIGRATION_TOOLS', 'PROGRAMMER_WORKFLOW_DSH_TOOLS', 'DSH_MIGRATION_TOOLS',
]) {
  delete process.env[name]
}

const handlers = {}
const child = {
  effect(fn) { fn() },
  webServer: { register(entry) { handlers[entry.path] = entry.handler } },
}
const ctx = {
  inject(_names, fn) { fn(child) },
}
const mod = await import(pathToFileURL(path.resolve('dsh-plugin/index.js')).href)
mod.apply(ctx)
assert.ok(handlers['/programmer-workflow/config'])
assert.ok(handlers['/programmer-workflow/status'])
assert.ok(handlers['/programmer-workflow/migration/prepare'])

function makeReq(method, url, body) {
  return {
    method,
    url,
    async *[Symbol.asyncIterator]() {
      if (body !== undefined) yield Buffer.from(JSON.stringify(body))
    },
  }
}
function makeRes() {
  return {
    statusCode: 0,
    body: '',
    writeHead(code) { this.statusCode = code },
    end(value) { this.body = String(value) },
  }
}
async function call(pathname, method, url, body) {
  const res = makeRes()
  await handlers[pathname](makeReq(method, url, body), res)
  return { status: res.statusCode, data: JSON.parse(res.body) }
}
function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, JSON.stringify(value, null, 2))
}
function controlDir(home) {
  return path.join(home, '.programmer-workflow-migration')
}
function makeJunction(source, target) {
  fs.mkdirSync(target, { recursive: true })
  fs.mkdirSync(path.dirname(source), { recursive: true })
  if (fs.existsSync(source)) fs.rmSync(source, { recursive: true, force: true })
  fs.symlinkSync(target, source, 'junction')
}
function writeCompletedStage1(home, host, target, targetRoot) {
  writeJson(path.join(controlDir(home), 'plugin-state.json'), {
    host,
    status: 'completed',
    source: path.join(home, 'programmer-workflow'),
    target,
    targetRoot,
    verifiedAt: new Date().toISOString(),
    backup: path.join(controlDir(home), 'backups', 'x', 'plugin'),
    inventory: { counts: { active: 0, proposed: 0, rejected: 0, total: 0 }, ids: [] },
  })
}

// ------------------------------------------------------- strict host handling
const beforeDsh = await call('/programmer-workflow/config', 'GET', '/programmer-workflow/config?host=dsh')
for (const bad of ['not-a-host', 'kimi-typo', 'deepseek-x']) {
  const response = await call('/programmer-workflow/config', 'POST', `/programmer-workflow/config?host=${bad}`, { workflowMode: 'plan' })
  assert.equal(response.status, 400, `unknown host ${bad} must fail`)
  assert.match(response.data.error, /unknown host/)
  const statusResponse = await call('/programmer-workflow/status', 'GET', `/programmer-workflow/status?host=${bad}`)
  assert.equal(statusResponse.status, 400)
}
const afterDsh = await call('/programmer-workflow/config', 'GET', '/programmer-workflow/config?host=dsh')
assert.deepEqual(afterDsh.data.config, beforeDsh.data.config, 'a misspelled host must never write DSH data')

// -------------------------------------------------------------- config rules
const badMode = await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=kimi', { host: 'kimi', workflowMode: 'bogus' })
assert.equal(badMode.status, 400)
assert.match(badMode.data.error, /workflowMode/)

const good = await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=kimi', { host: 'kimi', workflowMode: 'full-authority', planFormat: 'html' })
assert.equal(good.status, 200)
assert.equal(good.data.config.workflowMode, 'full-authority')
assert.equal(good.data.config.planFormat, 'html')
assert.ok(good.data.status.paths.config.includes('kimi'))

// ------------------------------------------------- reset only affects one host
const dshSaved = await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=dsh', {
  host: 'dsh', workflowMode: 'full-authority', migrationActionEnabled: true,
})
assert.equal(dshSaved.status, 200)
assert.equal(dshSaved.data.config.workflowMode, 'full-authority')
const resetKimi = await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=kimi', { host: 'kimi', reset: true })
assert.equal(resetKimi.status, 200)
assert.equal(resetKimi.data.config.workflowMode, 'plan', 'reset restores the defaults for the selected host')
assert.equal(resetKimi.data.config.planFormat, 'md')
const dshAfterReset = await call('/programmer-workflow/config', 'GET', '/programmer-workflow/config?host=dsh')
assert.equal(dshAfterReset.data.config.workflowMode, 'full-authority', 'reset must not touch another host')
assert.ok(fs.existsSync(path.join(kimiHome, 'programmer-workflow', 'memory')), 'reset must not delete memory data')

// --------------------------------------------------- per-host CLI capability
const codebuddyStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=codebuddy')
assert.equal(codebuddyStatus.status, 200)
assert.equal(codebuddyStatus.data.pluginMigration.supported, true)
assert.equal(codebuddyStatus.data.pluginMigration.ready, false, 'CodeBuddy without a CLI is not ready')
assert.match(codebuddyStatus.data.pluginMigration.unavailableReason, /companion\.py|PROGRAMMER_WORKFLOW_CLI/i)
const blockedPrepare = await call('/programmer-workflow/plugin-migration/prepare', 'POST', '/programmer-workflow/plugin-migration/prepare', {
  host: 'codebuddy', targetRoot: path.join(base, 'codebuddy-target'),
})
assert.equal(blockedPrepare.status, 400)
assert.match(blockedPrepare.data.error, /CLI|companion\.py/i)

// Preparing becomes possible once the host really has a CLI.
writeJson(path.join(codebuddyHome, 'skills', 'programmer-workflow', 'scripts', 'companion.py'), { stub: true })
const readyCodebuddy = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=codebuddy')
assert.equal(readyCodebuddy.data.pluginMigration.ready, true)
assert.ok(readyCodebuddy.data.pluginMigration.cliPath.includes('companion.py'))

// ------------------------------------------------------------- stage 1 (DSH)
writeJson(path.join(dshHome, 'skills', 'programmer-workflow', 'scripts', 'companion.py'), { stub: true })
fs.mkdirSync(path.join(dshHome, 'programmer-workflow', 'memory'), { recursive: true })
writeJson(path.join(dshHome, 'programmer-workflow', 'memory', 'memory.json'), {
  schema: 1, scope: 'user', entries: [{ id: 'dsh-active', status: 'active', kind: 'habit', text: 'x' }],
})
const stage1Root = path.join(base, 'stage1-target')
const stage1 = await call('/programmer-workflow/plugin-migration/prepare', 'POST', '/programmer-workflow/plugin-migration/prepare', {
  host: 'dsh', targetRoot: stage1Root,
})
assert.equal(stage1.status, 200, JSON.stringify(stage1.data))
assert.equal(stage1.data.target, path.join(stage1Root, '.dsh', 'programmer-workflow'))
assert.ok(fs.existsSync(stage1.data.launcher))
assert.ok(fs.existsSync(stage1.data.rollbackLauncher))
assert.ok(fs.readFileSync(stage1.data.launcher, 'utf8').includes(`--target-root "${stage1Root}"`))
assert.match(fs.readFileSync(stage1.data.rollbackLauncher, 'utf8'), /migrate-plugin rollback/)

// Prepared is not completed: a generated launcher never means "migrated".
const stagedStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(stagedStatus.data.pluginMigration.status, 'prepared')
assert.equal(stagedStatus.data.pluginMigration.prepared, true)
assert.equal(stagedStatus.data.pluginMigration.completed, false, 'a prepared script must not count as completed')

// -------------------------------------------------- verified stage 1 (DSH)
const stage1Target = path.join(stage1Root, '.dsh', 'programmer-workflow')
makeJunction(path.join(dshHome, 'programmer-workflow'), stage1Target)
writeCompletedStage1(dshHome, 'dsh', stage1Target, stage1Root)
const verifiedStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(verifiedStatus.data.pluginMigration.completed, true)
assert.equal(verifiedStatus.data.pluginMigration.status, 'completed')
assert.equal(verifiedStatus.data.pluginMigration.stale, false)
assert.equal(verifiedStatus.data.pluginMigration.linkStatus, 'junction')
assert.equal(verifiedStatus.data.pluginMigration.actualTarget, stage1Target)
assert.equal(verifiedStatus.data.pluginMigration.targetChanged, false)

// A state file alone is not enough: removing the link makes it stale, not done.
fs.unlinkSync(path.join(controlDir(dshHome), 'plugin-state.json'))
const externalStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(externalStatus.data.pluginMigration.external, true)
assert.equal(externalStatus.data.pluginMigration.completed, false, 'an unrecorded link is not plugin-verified')
writeCompletedStage1(dshHome, 'dsh', stage1Target, stage1Root)

// A real landing on another drive is a completed move even without a record
// (the C: path is only a junction) — the page must stop prompting.
const savedPluginState = fs.readFileSync(path.join(controlDir(dshHome), 'plugin-state.json'), 'utf8')
fs.unlinkSync(path.join(controlDir(dshHome), 'plugin-state.json'))
process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE = 'Q:'
const relocatedStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(relocatedStatus.data.pluginMigration.completed, true)
assert.equal(relocatedStatus.data.pluginMigration.completedVia, 'relocated')
assert.equal(relocatedStatus.data.pluginMigration.relocated, true)
assert.equal(relocatedStatus.data.pluginMigration.verified, false, 'relocated is not faked as plugin-verified')
assert.equal(relocatedStatus.data.pluginMigration.status, 'completed')
process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE = baseDrive
fs.writeFileSync(path.join(controlDir(dshHome), 'plugin-state.json'), savedPluginState)

// A different configured target root is reported as "move to a new address".
const movedRoot = path.join(base, 'new-address')
const savedRoot = await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=dsh', {
  host: 'dsh', pluginMigrationTargetRoot: movedRoot,
})
assert.equal(savedRoot.status, 200, JSON.stringify(savedRoot.data))
const changedStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(changedStatus.data.pluginMigration.targetChanged, true)
assert.equal(changedStatus.data.pluginMigration.desiredTarget, path.join(movedRoot, '.dsh', 'programmer-workflow'))
await call('/programmer-workflow/config', 'POST', '/programmer-workflow/config?host=dsh', {
  host: 'dsh', pluginMigrationTargetRoot: stage1Root,
})

// ----------------------------------------------------- stage 2 success (DSH)
// Both stages must share one target root: the plugin data lives inside the
// editor data dir, and cross-root rebuilding is deliberately unsupported.
const stage2Root = stage1Root
const stage2 = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'dsh', targetRoot: stage2Root,
})
assert.equal(stage2.status, 200, JSON.stringify(stage2.data))
assert.equal(stage2.data.target, path.join(stage2Root, '.dsh'), 'the reported target is <root>/.dsh')
const launched = fs.readFileSync(stage2.data.launcher, 'utf8')
assert.ok(launched.includes(`set "DSH_MIG_DEST=${stage2Root}"`), 'the launcher must pass the target ROOT')
assert.ok(!launched.includes(`set "DSH_MIG_DEST=${path.join(stage2Root, '.dsh')}"`), 'the data dir must not be double-spliced')
assert.ok(launched.includes(`set "DSH_MIG_SRC=${dshHome}"`), 'the launcher must pass the resolved DSH home')
assert.ok(launched.includes('migrate-dsh-data.bat'))
assert.ok(launched.includes('exit /b 1'), 'a failing adapter must end non-zero')
assert.match(launched, /runtime-completed\.txt/, 'success must be recorded for the status page')
const rolled = fs.readFileSync(stage2.data.rollbackLauncher, 'utf8')
assert.ok(rolled.includes(`set "DSH_MIG_DEST=${stage2Root}"`))
assert.ok(rolled.includes(`set "DSH_MIG_SRC=${dshHome}"`))
assert.ok(rolled.includes('rollback-dsh-data.bat'), 'stage 2 rollback must call the host rollback tool')
const runtimeState = JSON.parse(fs.readFileSync(path.join(controlDir(dshHome), 'runtime-state.json'), 'utf8'))
assert.equal(runtimeState.status, 'prepared')
assert.equal(runtimeState.launcher, stage2.data.launcher)
assert.equal(runtimeState.rollbackLauncher, stage2.data.rollbackLauncher)

const afterStage2 = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(afterStage2.data.runtimeMigration.stage2Status, 'prepared')
assert.equal(afterStage2.data.runtimeMigration.stage2Completed, false, 'a generated stage 2 launcher is not completed')
assert.equal(afterStage2.data.runtimeMigration.launcher, stage2.data.launcher)
assert.equal(afterStage2.data.runtimeMigration.rollbackLauncher, stage2.data.rollbackLauncher)

// Cross-root targets are refused (partial nested-junction support, not a full rebuild).
const crossRoot = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'dsh', targetRoot: path.join(base, 'other-root'),
})
assert.equal(crossRoot.status, 400)
assert.match(crossRoot.data.error, /同一目标根|跨根/)

// `target` (the final dir) is never accepted as a root: only `targetRoot` is.
const targetAlias = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'dsh', target: path.join(stage2Root, '.dsh'),
})
assert.equal(targetAlias.status, 400, 'a final target must not be reused as a target root')

// ---------------------------------------------------- stage 2 success (Kimi)
const kimiTools = path.join(base, 'kimi-tools')
fs.mkdirSync(kimiTools, { recursive: true })
fs.writeFileSync(path.join(kimiTools, 'migrate-kimi-data.bat'), '@echo off\r\nREM KIMI_MIG_SRC is honored\r\n', 'utf8')
fs.writeFileSync(path.join(kimiTools, 'rollback-kimi-data.bat'), '@echo off\r\nREM KIMI_MIG_SRC is honored\r\n', 'utf8')
const kimiStage2Root = path.join(base, 'kimi-stage2')
const kimiPluginRoot = path.join(kimiHome, 'programmer-workflow')
const kimiPluginTarget = path.join(kimiStage2Root, '.kimi-code', 'programmer-workflow')
// The plugin config lives inside the plugin root, so it moves into the target
// before the link is created (the Host must read it through the junction).
fs.mkdirSync(kimiPluginTarget, { recursive: true })
writeJson(path.join(kimiPluginTarget, 'config.json'), { kimiMigrationTools: kimiTools })
makeJunction(kimiPluginRoot, kimiPluginTarget)
writeCompletedStage1(kimiHome, 'kimi', kimiPluginTarget, kimiStage2Root)
const kimiStage2 = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'kimi', targetRoot: kimiStage2Root,
})
assert.equal(kimiStage2.status, 200, JSON.stringify(kimiStage2.data))
assert.equal(kimiStage2.data.target, path.join(kimiStage2Root, '.kimi-code'))
const kimiLauncher = fs.readFileSync(kimiStage2.data.launcher, 'utf8')
assert.ok(kimiLauncher.includes(`set "KIMI_MIG_DEST=${kimiStage2Root}"`))
assert.ok(!kimiLauncher.includes(`set "KIMI_MIG_DEST=${path.join(kimiStage2Root, '.kimi-code')}"`))
assert.ok(kimiLauncher.includes(`set "KIMI_MIG_SRC=${kimiHome}"`), 'KIMI_HOME must reach the adapter')
assert.ok(kimiLauncher.includes('migrate-kimi-data.bat'))
assert.ok(fs.readFileSync(kimiStage2.data.rollbackLauncher, 'utf8').includes('rollback-kimi-data.bat'))

// An adapter that ignores KIMI_MIG_SRC cannot follow a custom host home.
fs.writeFileSync(path.join(kimiTools, 'migrate-kimi-data.bat'), '@echo off\r\nREM fixed USERPROFILE path\r\n', 'utf8')
const kimiStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=kimi')
assert.equal(kimiStatus.data.runtimeMigration.adapterReady, false)
assert.match(kimiStatus.data.runtimeMigration.reason, /KIMI_MIG_SRC/)
const refused = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'kimi', targetRoot: kimiStage2Root,
})
assert.equal(refused.status, 400)
assert.match(refused.data.error, /KIMI_MIG_SRC|KIMI_HOME/)

// A rollback that calls a missing label exits 0 without rolling back.
fs.writeFileSync(path.join(kimiTools, 'migrate-kimi-data.bat'), '@echo off\r\nREM KIMI_MIG_SRC is honored\r\n', 'utf8')
fs.writeFileSync(path.join(kimiTools, 'rollback-kimi-data.bat'), '@echo off\r\ncall :RollbackOne\r\nexit /b 0\r\n', 'utf8')
const brokenRollback = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=kimi')
assert.equal(brokenRollback.data.runtimeMigration.adapterReady, false)
assert.match(brokenRollback.data.runtimeMigration.reason, /RollbackOne/)
fs.writeFileSync(path.join(kimiTools, 'rollback-kimi-data.bat'), '@echo off\r\nREM KIMI_MIG_SRC is honored\r\n', 'utf8')

// ------------------------------------- verified vs stale stage 2 (fresh homes)
const previousDshHome = process.env.DSH_HOME
const runtimeRoot = path.join(base, 'dsh-runtime-root')
const runtimeTarget = path.join(runtimeRoot, '.dsh')
const completedHome = path.join(base, 'dsh-completed-home')
fs.mkdirSync(runtimeTarget, { recursive: true })
fs.symlinkSync(runtimeTarget, completedHome, 'junction')
process.env.DSH_HOME = completedHome
// After stage 2 wraps the host home, the plugin path is a plain directory
// inside the target; the home junction is what proves the move.
const completedPluginTarget = path.join(runtimeTarget, 'programmer-workflow')
fs.mkdirSync(completedPluginTarget, { recursive: true })
writeCompletedStage1(runtimeTarget, 'dsh', completedPluginTarget, runtimeRoot)
writeJson(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-state.json'), {
  host: 'dsh', status: 'prepared', target: runtimeTarget, targetRoot: runtimeRoot, adapter: 'dsh',
})
fs.writeFileSync(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-completed.txt'), 'completed', 'utf8')
const completedStage2 = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(completedStage2.data.pluginMigration.completed, true, 'the home junction proves the plugin move after stage 2')
assert.equal(completedStage2.data.runtimeMigration.stage2Completed, true)
assert.equal(completedStage2.data.runtimeMigration.stage2Status, 'completed')
assert.equal(completedStage2.data.runtimeMigration.actualLocation, runtimeTarget)
assert.equal(completedStage2.data.runtimeMigration.verified, true)

// Stage 2 moved with the sample scripts leaves no marker; a real landing on
// another drive still counts as completed.
fs.unlinkSync(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-completed.txt'))
fs.unlinkSync(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-state.json'))
process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE = 'Q:'
const relocatedStage2 = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(relocatedStage2.data.runtimeMigration.stage2Completed, true)
assert.equal(relocatedStage2.data.runtimeMigration.stage2CompletedVia, 'relocated')
assert.equal(relocatedStage2.data.runtimeMigration.stage2Relocated, true)
assert.equal(relocatedStage2.data.runtimeMigration.stage2Verified, false)
assert.equal(relocatedStage2.data.runtimeMigration.actualLocation, runtimeTarget)
process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE = baseDrive
writeJson(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-state.json'), {
  host: 'dsh', status: 'prepared', target: runtimeTarget, targetRoot: runtimeRoot, adapter: 'dsh',
})
fs.writeFileSync(path.join(runtimeTarget, '.programmer-workflow-migration', 'runtime-completed.txt'), 'completed', 'utf8')

// Moving to a "new address" must actually be a different address.
const sameLocation = await call('/programmer-workflow/migration/prepare', 'POST', '/programmer-workflow/migration/prepare', {
  host: 'dsh', targetRoot: runtimeRoot,
})
assert.equal(sameLocation.status, 400, 'stage 2 must refuse the current location as a new address')
assert.match(sameLocation.data.error, /相同|无需/)

// A completion marker without a matching link is stale, never "completed".
const staleHome = path.join(base, 'dsh-stale-home')
const staleRoot = path.join(base, 'dsh-stale-root')
const stalePluginTarget = path.join(staleRoot, '.dsh', 'programmer-workflow')
fs.mkdirSync(stalePluginTarget, { recursive: true })
fs.mkdirSync(staleHome, { recursive: true })
makeJunction(path.join(staleHome, 'programmer-workflow'), stalePluginTarget)
writeCompletedStage1(staleHome, 'dsh', stalePluginTarget, staleRoot)
writeJson(path.join(controlDir(staleHome), 'runtime-state.json'), {
  host: 'dsh', status: 'prepared', target: path.join(staleRoot, '.dsh'), targetRoot: staleRoot, adapter: 'dsh',
})
fs.writeFileSync(path.join(controlDir(staleHome), 'runtime-completed.txt'), 'completed', 'utf8')
process.env.DSH_HOME = staleHome
const staleStage2 = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.equal(staleStage2.data.runtimeMigration.stage2Completed, false)
assert.equal(staleStage2.data.runtimeMigration.stage2Status, 'stale')
process.env.DSH_HOME = previousDshHome

// -------------------------------------------------- per-host path isolation
const status = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=codebuddy')
assert.equal(status.data.runtimeMigration.supported, false)
assert.ok(status.data.pluginData.globalRoot.includes('codebuddy'))
const dshStatus = await call('/programmer-workflow/status', 'GET', '/programmer-workflow/status?host=dsh')
assert.notEqual(status.data.pluginData.globalRoot, dshStatus.data.pluginData.globalRoot)

console.log('host plugin tests ok')
fs.rmSync(base, { recursive: true, force: true })
