/**
 * Programmer Workflow · DeepSeek Harness Host half.
 *
 * Owns DSH's own plugin root, but also reads/writes the independent config of
 * Kimi/CodeBuddy/Claude/Cursor/Codex when the settings page switches host. It
 * serves per-host status, prepares the two migration stages, and registers the
 * custom Settings page.
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const ENTRY_ID = 'programmer-workflow'
const VERSION = '0.1.0'
// Public defaults are empty: the settings page asks the user for a target.
// A machine-specific default must never ship, or a fresh install points at
// a drive/path that only the original author has.
const DEFAULT_MIGRATION_TARGET = ''
const DEFAULT_KIMI_TARGET = ''
// No implicit Kimi adapter path. An explicit `kimiMigrationTools` setting or
// KIMI_MIGRATION_TOOLS always wins.
const KIMI_TOOLS = ''
const BUNDLED_TOOLS = path.join(path.dirname(fileURLToPath(import.meta.url)), 'dsh-migration-tools')

const DEFAULT_CONFIG = {
  workspaceDataDir: '.programmer-workflow',
  debugLogDir: 'debug-logs',
  docsDir: 'docs',
  prototypeFile: 'Prototype.html',
  userMemoryEnabled: true,
  workspaceMemoryEnabled: true,
  satisfactionThreshold: 3,
  bugfixThreshold: 2,
  workflowMode: 'plan',
  devOnlyAutoInstrument: true,
  docsEnabled: true,
  prototypeEnabled: true,
  retentionDays: 30,
  language: 'zh-CN',
  promptMigration: true,
  migrationTarget: DEFAULT_MIGRATION_TARGET,
  migrationActionEnabled: true,
  kimiMigrationTarget: DEFAULT_KIMI_TARGET,
  kimiMigrationTools: '',
  planFormat: 'md',
  pluginMigrationTargetRoot: '',
  runtimeMigrationTargetRoot: '',
}

const WORKFLOW_MODES = [
  { id: 'plan', label: 'Plan', description: '先生成 plan.md 或 plan.html，用户批准后才执行。' },
  { id: 'full-authority', label: 'Full authority', description: '普通命令直接执行；破坏性操作仍需确认。' },
]
const WORKFLOW_MODE_IDS = WORKFLOW_MODES.map((mode) => mode.id)

const PATH_FIELDS = ['workspaceDataDir', 'debugLogDir', 'docsDir', 'prototypeFile']
const BOOL_FIELDS = [
  'userMemoryEnabled', 'workspaceMemoryEnabled',
  'devOnlyAutoInstrument', 'docsEnabled', 'prototypeEnabled', 'promptMigration',
  'migrationActionEnabled',
]
const INT_FIELDS = ['satisfactionThreshold', 'bugfixThreshold', 'retentionDays']

const HOSTS = {
  dsh: { id: 'dsh', label: 'DeepSeek Harness', dataDir: '.dsh', env: 'DSH_HOME', home: '~/.dsh', pluginMigration: true, runtimeMigration: true, runtimeAdapter: 'dsh' },
  kimi: { id: 'kimi', label: 'Kimi Code', dataDir: '.kimi-code', env: 'KIMI_HOME', home: '~/.kimi-code', pluginMigration: true, runtimeMigration: true, runtimeAdapter: 'kimi' },
  codebuddy: { id: 'codebuddy', label: 'CodeBuddy', dataDir: '.codebuddy', env: 'CODEBUDDY_HOME', home: '~/.codebuddy', pluginMigration: true, runtimeMigration: false, runtimeAdapter: null },
  claude: { id: 'claude', label: 'Claude Code', dataDir: '.claude', env: 'CLAUDE_HOME', home: '~/.claude', pluginMigration: true, runtimeMigration: false, runtimeAdapter: null },
  cursor: { id: 'cursor', label: 'Cursor', dataDir: '.cursor', env: 'CURSOR_HOME', home: '~/.cursor', pluginMigration: true, runtimeMigration: false, runtimeAdapter: null },
  codex: { id: 'codex', label: 'Codex', dataDir: '.codex', env: 'CODEX_HOME', home: '~/.codex', pluginMigration: true, runtimeMigration: false, runtimeAdapter: null },
  generic: { id: 'generic', label: 'Generic', dataDir: '.programmer-workflow', env: 'PROGRAMMER_WORKFLOW_GENERIC_HOME', home: '~/.programmer-workflow', pluginAtHome: true, pluginMigration: true, runtimeMigration: false, runtimeAdapter: null },
}

const HOST_ALIASES = {
  dsh: 'dsh', deepseek: 'dsh', 'deepseek-harness': 'dsh',
  kimi: 'kimi', 'kimi-code': 'kimi', kimicode: 'kimi',
  codebuddy: 'codebuddy', 'code-buddy': 'codebuddy',
  claude: 'claude', 'claude-code': 'claude',
  cursor: 'cursor', codex: 'codex', generic: 'generic',
}

function hostAlias(value) {
  const text = String(value == null ? '' : value).trim().toLowerCase().replace(/_/g, '-').replace(/\s+/g, '-')
  return HOST_ALIASES[text] || null
}

/**
 * Resolve an internal host argument.
 *
 * A missing value is the only case that defaults to DSH (internal callers use
 * `host = 'dsh'` defaults). Anything external — a route query, a request body,
 * a migration input, a config write — reaches this function with a value, and an
 * unknown or misspelled host must fail instead of silently reading DSH data.
 */
function normalizeHost(value) {
  if (value === undefined || value === null || String(value).trim() === '') return 'dsh'
  const id = hostAlias(value)
  if (!id) throw new Error(`unknown host: ${value}`)
  return id
}

function envPath(name) {
  const value = process.env[name]
  return value ? path.resolve(value) : null
}

function hostHome(host = 'dsh') {
  const spec = HOSTS[normalizeHost(host)]
  const override = spec.env ? process.env[spec.env] : ''
  if (override) return path.resolve(override)
  return path.join(os.homedir(), spec.home.replace(/^~[\\/]?/, ''))
}

function root(host = 'dsh') {
  const id = normalizeHost(host)
  // The same two overrides apply to every host, exactly like the Python CLI.
  const globalOverride = envPath('PROGRAMMER_WORKFLOW_GLOBAL')
  if (globalOverride) return globalOverride
  if (HOSTS[id].pluginAtHome) return hostHome(id)
  return path.join(hostHome(id), 'programmer-workflow')
}

function memoryRoot(host = 'dsh') {
  return envPath('PROGRAMMER_WORKFLOW_HOME') || path.join(root(host), 'memory')
}

function dataPaths(host = 'dsh') {
  const base = root(host)
  return {
    host: normalizeHost(host),
    globalRoot: base,
    memory: memoryRoot(host),
    artifacts: path.join(base, 'artifacts'),
    logs: path.join(base, 'logs'),
    config: path.join(base, 'config.json'),
    readme: path.join(base, 'README.md'),
  }
}

function safeRelative(value, fallback) {
  const text = String(value == null ? '' : value).trim().replace(/\\/g, '/')
  if (!text || text.startsWith('/') || /^[A-Za-z]:/.test(text)) return fallback
  const parts = text.split('/').filter((part) => part && part !== '.')
  if (!parts.length || parts.some((part) => part === '..')) return fallback
  return parts.join('/')
}

function parseMigrationTarget(value) {
  let text = String(value == null ? '' : value).trim().replace(/^"|"$/g, '')
  text = text.replace(/\//g, '\\')
  if (!/^[A-Za-z]:\\/.test(text)) return null
  if (/^\\\\/.test(text)) return null
  if (text.split('\\').includes('..')) return null
  if (/[%!&|<>^"\r\n]/.test(text)) return null
  return text
}

function safeMigrationTarget(value, fallback = DEFAULT_MIGRATION_TARGET) {
  return parseMigrationTarget(value) || fallback
}

function clampInt(value, fallback, low, high) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(low, Math.min(high, Math.trunc(parsed)))
}

function normalizeConfig(input) {
  const source = input && typeof input === 'object' ? input : {}
  const config = {}
  for (const key of PATH_FIELDS) config[key] = safeRelative(source[key], DEFAULT_CONFIG[key])
  for (const key of BOOL_FIELDS) {
    config[key] = typeof source[key] === 'boolean' ? source[key] : DEFAULT_CONFIG[key]
  }
  config.satisfactionThreshold = clampInt(source.satisfactionThreshold, 3, 1, 10)
  config.bugfixThreshold = clampInt(source.bugfixThreshold, 2, 1, 10)
  config.retentionDays = clampInt(source.retentionDays, 30, 1, 365)
  config.language = String(source.language || 'zh-CN').slice(0, 20)
  config.planFormat = source.planFormat === 'html' ? 'html' : 'md'
  config.workflowMode = WORKFLOW_MODE_IDS.includes(source.workflowMode) ? source.workflowMode : 'plan'
  config.migrationTarget = safeMigrationTarget(source.migrationTarget)
  config.kimiMigrationTarget = safeMigrationTarget(source.kimiMigrationTarget, DEFAULT_KIMI_TARGET)
  config.kimiMigrationTools = safeMigrationTarget(source.kimiMigrationTools, '')
  config.pluginMigrationTargetRoot = safeOptionalRoot(source.pluginMigrationTargetRoot)
  config.runtimeMigrationTargetRoot = safeOptionalRoot(source.runtimeMigrationTargetRoot)
  return config
}

function safeOptionalRoot(value) {
  const text = String(value == null ? '' : value).trim()
  if (!text) return ''
  return parseMigrationTarget(text) || ''
}

function validateConfigInput(source) {
  const errors = []
  const input = source && typeof source === 'object' ? source : {}
  for (const key of PATH_FIELDS) {
    const value = input[key]
    if (value === undefined) continue
    if (typeof value !== 'string' || !isSafeRelative(value)) errors.push(`${key} 必须是工作区内的相对路径`)
  }
  for (const key of BOOL_FIELDS) {
    if (input[key] !== undefined && typeof input[key] !== 'boolean') errors.push(`${key} 必须是布尔值`)
  }
  for (const key of INT_FIELDS) {
    if (input[key] === undefined) continue
    const number = Number(input[key])
    if (!Number.isFinite(number) || !Number.isInteger(number)) errors.push(`${key} 必须是整数`)
  }
  if (input.workflowMode !== undefined && !WORKFLOW_MODE_IDS.includes(input.workflowMode)) {
    errors.push(`workflowMode 必须是 ${WORKFLOW_MODE_IDS.join(' / ')}`)
  }
  if (input.planFormat !== undefined && input.planFormat !== 'md' && input.planFormat !== 'html') {
    errors.push('planFormat 必须是 md 或 html')
  }
  for (const key of ['migrationTarget', 'kimiMigrationTarget', 'kimiMigrationTools']) {
    if (input[key] === undefined || input[key] === '') continue
    if (!parseMigrationTarget(input[key])) errors.push(`${key} 必须是绝对路径，且不能包含 % ! & | < > ^ "`)
  }
  for (const key of ['pluginMigrationTargetRoot', 'runtimeMigrationTargetRoot']) {
    if (input[key] === undefined || input[key] === '') continue
    if (!parseMigrationTarget(input[key])) errors.push(`${key} 必须是绝对路径或留空`)
  }
  return errors
}

function isSafeRelative(value) {
  if (typeof value !== 'string' || !value.trim()) return false
  const text = value.trim().replace(/\\/g, '/')
  if (text.startsWith('/') || /^[A-Za-z]:/.test(text)) return false
  const parts = text.split('/').filter((part) => part && part !== '.')
  return parts.length > 0 && !parts.includes('..')
}

function readConfig(host = 'dsh') {
  try {
    const raw = JSON.parse(fs.readFileSync(dataPaths(host).config, 'utf8'))
    return normalizeConfig({ ...DEFAULT_CONFIG, ...raw })
  } catch {
    return { ...DEFAULT_CONFIG }
  }
}

function writeConfig(input, host = 'dsh') {
  const config = normalizeConfig(input)
  const paths = dataPaths(host)
  fs.mkdirSync(paths.globalRoot, { recursive: true })
  fs.mkdirSync(paths.memory, { recursive: true })
  fs.mkdirSync(paths.artifacts, { recursive: true })
  fs.mkdirSync(paths.logs, { recursive: true })
  const document = {
    schema: 1,
    name: 'Programmer Workflow',
    host: paths.host,
    version: VERSION,
    generatedAt: new Date().toISOString(),
    globalRoot: paths.globalRoot,
    ...config,
  }
  fs.writeFileSync(paths.config, JSON.stringify(document, null, 2) + '\n', 'utf8')
  if (!fs.existsSync(paths.readme)) writeReadme(paths.host)
  return config
}

function writeReadme(host = 'dsh') {
  const paths = dataPaths(host)
  const body = [
    `# Programmer Workflow · ${paths.host} global data`,
    '',
    'This directory belongs to one Agent/editor only. It is not shared with other hosts.',
    '',
    '- `memory/` — plugin user memory (`memory.json`, `MEMORY.md`)',
    '- `artifacts/` — global test/debug artifacts that are not workspace-specific',
    '- `logs/` — plugin/migration logs',
    '- `config.json` — settings mirror read by the Python CLI',
    '',
    `Host: ${paths.host}`,
    `Host home: ${hostHome(paths.host)}`,
    `Global root: ${paths.globalRoot}`,
    '',
  ].join('\n')
  fs.writeFileSync(paths.readme, body, 'utf8')
}

function copyLegacyMemory(host = 'dsh') {
  if (normalizeHost(host) !== 'dsh') return
  const legacy = path.join(os.homedir(), '.workflow-companion')
  const target = dataPaths(host).memory
  const legacyJson = path.join(legacy, 'memory.json')
  if (!fs.existsSync(legacyJson) || fs.existsSync(path.join(target, 'memory.json'))) return
  fs.mkdirSync(target, { recursive: true })
  for (const name of ['memory.json', 'MEMORY.md', 'README.md']) {
    const source = path.join(legacy, name)
    if (fs.existsSync(source)) fs.copyFileSync(source, path.join(target, name))
  }
  fs.writeFileSync(path.join(target, 'migrated-from.json'), JSON.stringify({
    from: legacy,
    to: target,
    at: new Date().toISOString(),
    note: 'Legacy Programmer Workflow user memory copied into the DSH global root.',
  }, null, 2) + '\n', 'utf8')
}

function pruneArtifacts(host = 'dsh') {
  const days = readConfig(host).retentionDays
  const cutoff = Date.now() - Math.max(1, days) * 86_400_000
  const directory = dataPaths(host).artifacts
  try {
    for (const name of fs.readdirSync(directory)) {
      const target = path.join(directory, name)
      try {
        const stat = fs.statSync(target)
        if (stat.isFile() && stat.mtimeMs < cutoff) fs.unlinkSync(target)
      } catch {}
    }
  } catch {}
}

function ensureLayout(host = 'dsh') {
  const paths = dataPaths(host)
  for (const dir of [paths.globalRoot, paths.memory, paths.artifacts, paths.logs]) {
    fs.mkdirSync(dir, { recursive: true })
  }
  copyLegacyMemory(host)
  if (!fs.existsSync(paths.config)) writeConfig(DEFAULT_CONFIG, host)
  writeReadme(host)
  try {
    fs.writeFileSync(path.join(paths.artifacts, 'last-start.json'), JSON.stringify({
      at: new Date().toISOString(),
      host: paths.host,
      version: VERSION,
      globalRoot: paths.globalRoot,
    }, null, 2) + '\n', 'utf8')
  } catch {}
  pruneArtifacts(host)
}

function pathIsJunction(target) {
  try {
    const stat = fs.lstatSync(target)
    const real = realPath(target)
    return { exists: true, junction: stat.isSymbolicLink() || real.toLowerCase() !== path.resolve(target).toLowerCase(), real }
  } catch {
    return { exists: false, junction: false, real: null }
  }
}

function kimiSources() {
  const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming')
  return [
    // Follow KIMI_HOME so the settings page, stage 1 and stage 2 agree.
    { label: 'Kimi Code', path: hostHome('kimi') },
    { label: 'Kimi 工具目录', path: path.join(os.homedir(), '.kimi-work') },
    { label: '网页桥接', path: path.join(os.homedir(), '.kimi-webbridge') },
    { label: 'Kimi 桌面端', path: path.join(appData, 'kimi-desktop') },
  ].map((item) => ({ ...item, ...pathIsJunction(item.path) }))
}

function sha256File(file) {
  try { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') } catch { return null }
}

function readJsonSafe(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return null }
}

function pathInside(child, parent) {
  try {
    const rel = path.relative(path.resolve(parent), path.resolve(child))
    return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel))
  } catch { return false }
}

function memoryInventoryForHost(host) {
  const paths = dataPaths(host)
  const raw = readJsonSafe(paths.memory + path.sep + 'memory.json')
  const entries = raw && Array.isArray(raw.entries) ? raw.entries : []
  const counts = { active: 0, proposed: 0, rejected: 0, total: entries.length }
  for (const entry of entries) {
    if (entry && counts[entry.status] !== undefined) counts[entry.status] += 1
  }
  return {
    ok: !!raw,
    missing: !fs.existsSync(paths.memory + path.sep + 'memory.json'),
    error: raw ? null : 'memory.json is missing or not valid JSON',
    counts,
    ids: entries.map((entry) => entry && entry.id).filter(Boolean).sort(),
    sha256: {
      memory: sha256File(paths.memory + path.sep + 'memory.json'),
      memoryMd: sha256File(paths.memory + path.sep + 'MEMORY.md'),
      config: sha256File(paths.config),
    },
  }
}

function pluginDataForHost(host) {
  const id = normalizeHost(host)
  const paths = dataPaths(id)
  const realRoot = realPath(paths.globalRoot)
  const realMemory = realPath(paths.memory)
  const realConfig = realPath(paths.config)
  const home = hostHome(id)
  const external = {
    globalOverride: envPath('PROGRAMMER_WORKFLOW_GLOBAL'),
    memoryOverride: envPath('PROGRAMMER_WORKFLOW_HOME'),
  }
  const legacyCandidates = [path.join(os.homedir(), '.workflow-companion')]
  if (id !== 'dsh') legacyCandidates.push(path.join(os.homedir(), '.dsh', 'programmer-workflow'))
  const legacyPaths = legacyCandidates.filter((candidate) => fs.existsSync(candidate))
  const legacyMemory = legacyPaths
    .map((candidate) => path.join(candidate, 'memory.json'))
    .find((candidate) => fs.existsSync(candidate)) || null
  const targetMemory = path.join(paths.memory, 'memory.json')
  const targetHasMemory = fs.existsSync(targetMemory)
  const importedMarker = path.join(paths.globalRoot, 'legacy-import.json')
  const imported = fs.existsSync(importedMarker) || fs.existsSync(path.join(paths.memory, 'migrated-from.json'))
  const legacyHash = legacyMemory ? sha256File(legacyMemory) : null
  const targetHash = targetHasMemory ? sha256File(targetMemory) : null
  const conflict = !!(legacyMemory && targetHasMemory && legacyHash !== targetHash)
  const same = !!(legacyMemory && targetHasMemory && legacyHash === targetHash)
  const logicalInside = pathInside(paths.globalRoot, home)
  let coverage = 'covered'
  if (!logicalInside) coverage = 'external'
  else if (conflict) coverage = 'legacy-conflict'
  else if (legacyMemory && !targetHasMemory) coverage = 'legacy-pending'
  else if (imported) coverage = 'imported'
  return {
    host: id,
    globalRoot: paths.globalRoot,
    memoryRoot: paths.memory,
    configPath: paths.config,
    realGlobalRoot: realRoot,
    realMemoryRoot: realMemory,
    realConfigPath: realConfig,
    hostHome: home,
    insideHostHome: logicalInside,
    resolvedOutsideHostHome: !pathInside(realRoot, home),
    externalOverrides: external,
    externallyOverridden: !!(external.globalOverride || external.memoryOverride || !logicalInside),
    legacy: {
      candidates: legacyCandidates,
      present: legacyPaths,
      hasMemory: !!legacyMemory,
      memoryPath: legacyMemory,
      imported,
      conflict,
      same,
      targetHasMemory,
      legacySha256: legacyHash,
      targetSha256: targetHash,
    },
    workspaceMemory: {
      migratesWithApp: false,
      note: '项目工作区记忆位于 <workspace>/.programmer-workflow，不随任何全局/宿主迁移移动。',
    },
    coverage,
    inventory: memoryInventoryForHost(id),
  }
}

function samePath(a, b) {
  if (!a || !b) return false
  return path.resolve(a).toLowerCase() === path.resolve(b).toLowerCase()
}

function migrationLink(target) {
  const stat = pathIsJunction(target)
  return {
    exists: stat.exists,
    isLink: !!stat.junction,
    real: stat.exists && stat.real ? path.resolve(stat.real) : null,
  }
}

/**
 * The drive the app itself runs from. A junction/mapped home is considered
 * migrated when its *real* location lands elsewhere (the C: path is only a
 * mapping). `PROGRAMMER_WORKFLOW_SYSTEM_DRIVE` exists for tests and for hosts
 * whose "local" volume is not C:.
 */
function systemDrive() {
  const raw = process.env.PROGRAMMER_WORKFLOW_SYSTEM_DRIVE || process.env.SystemDrive || (process.platform === 'win32' ? 'C:' : '')
  return String(raw || '').replace(/[\\/]+$/, '').toUpperCase()
}

function driveOf(target) {
  if (!target) return ''
  const root = path.parse(path.resolve(target)).root
  return root ? root.replace(/[\\/]+$/, '').toUpperCase() : ''
}

function isOffSystemDrive(target) {
  const sys = systemDrive()
  const drive = driveOf(target)
  return !!sys && !!drive && drive !== sys
}

/**
 * A completed record only counts when the live source resolves to its target
 * and at least one link proves the move: the plugin path itself (stage 1 only)
 * or the host home (after stage 2 wrapped the home in a junction). A state file
 * alone, or a plain directory at the default location, is never "completed".
 */
function verifiedRecord(records, sourceStat, homeIsLink) {
  for (const record of records) {
    if (!record || record.status !== 'completed' || !record.verifiedAt || !record.target) continue
    if (!sourceStat.exists || !sourceStat.real || !samePath(sourceStat.real, record.target)) continue
    if (sourceStat.isLink || homeIsLink) return record
  }
  return null
}

function pluginMigrationForHost(host) {
  const id = normalizeHost(host)
  const config = readConfig(id)
  const controlDir = path.join(hostHome(id), '.programmer-workflow-migration')
  const statePath = path.join(controlDir, 'plugin-state.json')
  const state = readJsonSafe(statePath)
  const spec = HOSTS[id]
  const targetRoot = config.pluginMigrationTargetRoot || ''
  const requestedTarget = targetRoot ? path.join(targetRoot, spec.dataDir, 'programmer-workflow') : ''
  const cli = companionForHost(id)
  const supported = !!spec.pluginMigration
  const valid = state && state.host === id ? state : null
  const previous = valid && valid.previous && valid.previous.host === id ? valid.previous : null
  const sourcePath = dataPaths(id).globalRoot
  const sourceStat = migrationLink(sourcePath)
  const homeStat = migrationLink(hostHome(id))
  const verified = verifiedRecord([valid, previous], sourceStat, homeStat.isLink)
  // A real landing off the system drive is a completed move even when this
  // plugin has no record (the user moved it with the sample scripts): the C:
  // path is only a junction then, and the app must not keep prompting.
  const realTarget = sourceStat.exists && sourceStat.real ? path.resolve(sourceStat.real) : ''
  const relocated = !!realTarget && isOffSystemDrive(realTarget)
  const completed = !!verified || relocated
  const requestedStatus = valid && valid.status ? String(valid.status) : 'not-started'
  let status = requestedStatus
  if (completed) status = 'completed'
  else if (!valid && (sourceStat.isLink || homeStat.isLink)) status = 'external'
  else if (requestedStatus === 'completed') status = 'stale'
  const actualTarget = realTarget || ((sourceStat.isLink || homeStat.isLink) && sourceStat.real ? path.resolve(sourceStat.real) : '')
  const pending = valid && valid.status === 'prepared'
    ? {
      status: 'prepared',
      target: valid.target || '',
      targetRoot: valid.targetRoot || '',
      preparedAt: valid.preparedAt || null,
      launcher: path.join(controlDir, 'run-stage1-plugin.cmd'),
      rollbackLauncher: path.join(controlDir, 'run-stage1-rollback-plugin.cmd'),
      previousTarget: previous && previous.target ? previous.target : '',
    }
    : null
  return {
    host: id,
    status,
    completed: !!completed,
    verified: !!verified,
    completedVia: verified ? 'record' : (relocated ? 'relocated' : null),
    relocated,
    systemDrive: systemDrive(),
    verifiedAt: verified ? verified.verifiedAt : null,
    verifiedTarget: verified ? path.resolve(verified.target) : '',
    verifiedTargetRoot: verified && verified.targetRoot ? verified.targetRoot : '',
    prepared: !!pending,
    pending,
    // A link exists that this plugin did not verify (no record, or a stale one).
    external: !completed && (sourceStat.isLink || homeStat.isLink),
    stale: status === 'stale',
    source: sourcePath,
    target: completed ? actualTarget : (valid && valid.target ? valid.target : requestedTarget),
    actualTarget,
    targetRoot,
    desiredTarget: requestedTarget,
    targetChanged: !!(completed && requestedTarget && !samePath(requestedTarget, actualTarget)),
    linkStatus: sourceStat.isLink ? 'junction' : (homeStat.isLink ? 'host-home-junction' : (sourceStat.exists ? 'directory' : 'missing')),
    hostHomeLink: homeStat.isLink,
    actualTargetExists: !!(actualTarget && fs.existsSync(actualTarget)),
    backup: verified && verified.backup ? verified.backup : (valid && valid.backup ? valid.backup : null),
    statePath,
    supported,
    // Capability has two parts: the host is modelled, and a CLI exists to run
    // stage 1. CodeBuddy is modelled but has no CLI until its skill is installed
    // or PROGRAMMER_WORKFLOW_CLI points at one, so prepare must refuse up front.
    cliPath: cli,
    ready: supported && !!cli,
    unavailableReason: !supported
      ? '该宿主暂不支持插件数据迁移。'
      : (cli ? '' : '未找到该宿主的 Skill CLI（companion.py）：请先安装 Programmer Workflow Skill，或设置 PROGRAMMER_WORKFLOW_CLI。'),
    inventory: verified && verified.inventory ? verified.inventory : (valid && valid.inventory ? valid.inventory : memoryInventoryForHost(id)),
  }
}

const STAGE2_MIGRATE = { dsh: 'migrate-dsh-data.bat', kimi: 'migrate-kimi-data.bat' }
const STAGE2_ROLLBACK = { dsh: 'rollback-dsh-data.bat', kimi: 'rollback-kimi-data.bat' }
const STAGE2_BLOCKING = ['prepared', 'active', 'completed']

function scriptMentions(file, token) {
  try { return fs.readFileSync(file, 'latin1').includes(token) } catch { return false }
}

/**
 * Return the first `call :Label` in a batch file whose label is missing.
 *
 * A staged adapter whose rollback script exits 0 without doing anything is
 * worse than an absent one, so readiness also proves the batch control flow
 * resolves. Encoding-agnostic (latin1 keeps ASCII tokens intact).
 */
function missingBatchLabel(file) {
  let text
  try { text = fs.readFileSync(file, 'latin1') } catch { return null }
  const labels = new Set()
  const calls = []
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (line.startsWith(':') && line.length > 1) {
      const label = line.slice(1).split(/\s+/)[0]
      if (label) labels.add(label.toLowerCase())
    }
    const call = /^call\s+:([A-Za-z0-9_.-]+)/i.exec(line)
    if (call) calls.push(call[1])
  }
  return calls.find((name) => !labels.has(name.toLowerCase())) || null
}

function kimiAdapterFollowsHome(toolsDir) {
  const home = process.env.KIMI_HOME
  if (!home) return true
  const resolved = path.resolve(home)
  if (path.resolve(path.join(os.homedir(), '.kimi-code')).toLowerCase() === resolved.toLowerCase()) return true
  return scriptMentions(path.join(toolsDir, STAGE2_MIGRATE.kimi), 'KIMI_MIG_SRC')
}

/**
 * Resolve the stage 2 adapter exactly the way Python's
 * `migration.inspect_runtime_adapter()` does: a directory is usable only when
 * both the migrate and the rollback script exist, and a Kimi adapter must honor
 * KIMI_MIG_SRC when the host home is not the default one.
 */
function runtimeToolsForHost(host, config, spec) {
  const adapter = spec.runtimeMigration ? spec.runtimeAdapter : null
  const result = {
    adapter,
    toolsPath: null,
    detectedToolsPath: null,
    adapterReady: false,
    reason: '',
    migrate: null,
    rollback: null,
  }
  if (!adapter) {
    result.reason = '当前尚未适配该编辑器的运行数据迁移。'
    return result
  }
  const migrateName = STAGE2_MIGRATE[adapter]
  const rollbackName = STAGE2_ROLLBACK[adapter]
  const candidates = adapter === 'kimi'
    ? [config.kimiMigrationTools, process.env.KIMI_MIGRATION_TOOLS, KIMI_TOOLS]
    : [process.env.PROGRAMMER_WORKFLOW_DSH_TOOLS, process.env.DSH_MIGRATION_TOOLS, BUNDLED_TOOLS]
  const has = (dir, name) => {
    try { return !!dir && fs.existsSync(path.join(dir, name)) } catch { return false }
  }
  const detected = candidates.filter(Boolean).find((dir) => has(dir, migrateName)) || null
  const complete = candidates.filter(Boolean).find((dir) => has(dir, migrateName) && has(dir, rollbackName)) || null
  // Whenever a complete pair exists, `detectedToolsPath` is the directory that
  // actually decided readiness — it is never a display-only extra path.
  result.detectedToolsPath = complete || detected
  result.toolsPath = complete || detected
  if (!complete) {
    result.reason = detected
      ? `适配器目录缺少 ${rollbackName}；第二阶段需要迁移与回滚成对的脚本。`
      : '未找到可用的运行数据迁移适配器（迁移与回滚脚本都需要）。'
    return result
  }
  if (adapter === 'kimi' && !kimiAdapterFollowsHome(complete)) {
    result.reason = 'KIMI_HOME 不在 ~/.kimi-code，但该 Kimi 适配器固定读取 %USERPROFILE%\\.kimi-code；请安装遵循 KIMI_MIG_SRC 的适配器，或恢复默认 KIMI_HOME。'
    return result
  }
  for (const scriptName of [migrateName, rollbackName]) {
    const missing = missingBatchLabel(path.join(complete, scriptName))
    if (missing) {
      result.reason = `${scriptName} 调用了不存在的批处理标签 :${missing}；该适配器的回滚/迁移路径无法执行。`
      return result
    }
  }
  result.adapterReady = true
  result.toolsPath = complete
  result.migrate = path.join(complete, migrateName)
  result.rollback = path.join(complete, rollbackName)
  result.reason = ''
  return result
}

function runtimeControlDir(host) {
  return path.join(hostHome(host), '.programmer-workflow-migration')
}

function runtimeMarkers(host) {
  const control = runtimeControlDir(host)
  return {
    completed: path.join(control, 'runtime-completed.txt'),
    rolledBack: path.join(control, 'runtime-rolled-back.txt'),
    launcher: path.join(control, 'run-stage2-runtime.cmd'),
    rollbackLauncher: path.join(control, 'run-stage2-rollback.cmd'),
  }
}

/**
 * Stage 2 state, derived like Python's `runtime_stage_status`.
 *
 * `completed` is true when the launcher marker matches a live home junction, or
 * when the home really lands off the system drive (the C: home is only a
 * mapping — the sample scripts do this without leaving a marker). A marker
 * without a matching link is `stale`; prepared never claims completion.
 */
function stage2InfoForHost(host, spec, config) {
  const control = runtimeControlDir(host)
  const markers = runtimeMarkers(host)
  const state = readJsonSafe(path.join(control, 'runtime-state.json'))
  const valid = state && state.host === host ? state : null
  const markerCompleted = fs.existsSync(markers.completed)
  const markerRolledBack = fs.existsSync(markers.rolledBack)
  const recordedTarget = valid && valid.target ? String(valid.target) : ''
  const link = migrationLink(hostHome(host))
  const verified = markerCompleted && link.isLink && !!recordedTarget && samePath(link.real, recordedTarget)
  const realLocation = link.exists && link.real ? path.resolve(link.real) : ''
  const relocated = !!realLocation && isOffSystemDrive(realLocation)
  const completed = !!verified || relocated
  let status = 'not-started'
  if (completed) status = 'completed'
  else if (markerCompleted) status = 'stale'
  else if (markerRolledBack) status = 'rolled-back'
  else if (valid && valid.status) status = String(valid.status)
  else if (link.isLink) status = 'external'
  // The DSH adapter also moves %APPDATA%\@deepseek-ai; report it but never use
  // it to fake completion on its own.
  const appDataRoot = process.env.APPDATA ? path.join(process.env.APPDATA, '@deepseek-ai') : ''
  const appDataStat = appDataRoot ? pathIsJunction(appDataRoot) : { exists: false, junction: false, real: null }
  return {
    status,
    completed: !!completed,
    verified: !!verified,
    completedVia: verified ? 'record' : (relocated ? 'relocated' : null),
    relocated,
    systemDrive: systemDrive(),
    verifiedAt: verified && valid && valid.completedAt ? valid.completedAt : null,
    actualLocation: realLocation,
    recordedTarget,
    recordedTargetRoot: valid && valid.targetRoot ? String(valid.targetRoot) : '',
    linkStatus: link.isLink ? 'junction' : (link.exists ? 'directory' : 'missing'),
    appDataRelocated: !!(appDataStat.exists && appDataStat.real && isOffSystemDrive(path.resolve(appDataStat.real))),
    prepared: !completed && !!valid && valid.status === 'prepared',
    pending: !completed && valid && valid.status === 'prepared'
      ? { target: valid.target || '', targetRoot: valid.targetRoot || '' }
      : null,
    launcher: fs.existsSync(markers.launcher) ? markers.launcher : null,
    rollbackLauncher: fs.existsSync(markers.rollbackLauncher) ? markers.rollbackLauncher : null,
  }
}

function runtimeMigrationForHost(host) {
  const id = normalizeHost(host)
  const config = readConfig(id)
  const spec = HOSTS[id]
  const plugin = pluginMigrationForHost(id)
  const stage1Done = !!plugin.completed
  const supported = !!spec.runtimeMigration
  const runtime = runtimeToolsForHost(id, config, spec)
  const stage2 = stage2InfoForHost(id, spec, config)
  let status = 'unavailable'
  let reason = supported ? (runtime.reason || '当前宿主运行数据适配器不可用。') : '当前尚未适配该编辑器的运行数据迁移。'
  if (!stage1Done) {
    status = 'blocked'
    reason = '请先完成并校验第一阶段插件数据迁移。'
  } else if (!supported) {
    status = 'unavailable'
    reason = '当前仅支持迁移 Programmer Workflow 插件数据，尚未适配该编辑器的运行数据迁移。'
  } else if (!runtime.adapterReady) {
    status = 'unavailable'
    reason = runtime.reason
  } else {
    status = 'ready'
    reason = ''
  }
  const targetRoot = config.runtimeMigrationTargetRoot || ''
  return {
    host: id,
    supported,
    adapter: runtime.adapter,
    adapterReady: runtime.adapterReady,
    stage1Done,
    status,
    reason,
    stage2Status: stage2.status,
    stage2Completed: stage2.completed,
    stage2Verified: stage2.verified,
    stage2CompletedVia: stage2.completedVia,
    stage2Relocated: stage2.relocated,
    appDataRelocated: stage2.appDataRelocated,
    systemDrive: stage2.systemDrive,
    stage2VerifiedAt: stage2.verifiedAt,
    actualLocation: stage2.actualLocation,
    actualLocationExists: !!(stage2.actualLocation && fs.existsSync(stage2.actualLocation)),
    stage2LinkStatus: stage2.linkStatus,
    pending: stage2.pending,
    targetRoot,
    target: stage2.recordedTarget || (targetRoot ? path.join(targetRoot, spec.dataDir) : ''),
    toolsPath: runtime.toolsPath,
    detectedToolsPath: runtime.detectedToolsPath,
    migrateScript: runtime.migrate,
    rollbackScript: runtime.rollback,
    toolsConfigured: runtime.adapter === 'kimi' ? !!config.kimiMigrationTools : runtime.adapter === 'dsh',
    toolsExist: runtime.adapterReady,
    launcher: stage2.launcher,
    rollbackLauncher: stage2.rollbackLauncher,
    verified: stage2.verified,
    note: spec.runtimeNote || '',
  }
}

function appDataForHost(host) {
  const id = normalizeHost(host)
  const home = hostHome(id)
  const stat = pathIsJunction(home)
  const config = readConfig(id)
  return {
    host: id,
    home,
    isJunction: !!stat.junction,
    target: stat.junction ? stat.real : null,
    recommended: !stat.junction && path.parse(home).root.toLowerCase().startsWith('c:'),
    runtimeTargetRoot: config.runtimeMigrationTargetRoot || '',
  }
}

function hostStatus(host = 'dsh') {
  const id = normalizeHost(host)
  const paths = dataPaths(id)
  paths.realGlobalRoot = realPath(paths.globalRoot)
  paths.realMemory = realPath(paths.memory)
  const pluginData = pluginDataForHost(id)
  const appData = appDataForHost(id)
  return {
    host: id,
    config: readConfig(id),
    paths,
    pluginData,
    pluginMigration: pluginMigrationForHost(id),
    runtimeMigration: runtimeMigrationForHost(id),
    appData,
    migrationCoverage: {
      appDataMigrated: !!appData.isJunction,
      pluginRootInDefaultLocation: pluginData.coverage === 'covered' || pluginData.coverage === 'imported',
      pluginDataCoverage: pluginData.coverage,
      externalOverride: pluginData.externallyOverridden,
      legacyPending: !!(pluginData.legacy && pluginData.legacy.hasMemory && !pluginData.legacy.imported),
      workspaceMemoryMigrates: false,
    },
    workflowModes: WORKFLOW_MODES,
  }
}

function hostsInfoV2() {
  const result = {}
  for (const spec of Object.values(HOSTS)) {
    const id = spec.id
    const config = readConfig(id)
    const skillPath = path.join(hostHome(id), 'skills', 'programmer-workflow', 'SKILL.md')
    const cli = companionForHost(id)
    const runtime = runtimeToolsForHost(id, config, spec)
    result[id] = {
      label: spec.label,
      dataDir: spec.dataDir,
      home: hostHome(id),
      pluginRoot: root(id),
      memoryRoot: memoryRoot(id),
      configPath: dataPaths(id).config,
      planFile: `plan.${config.planFormat}`,
      installed: fs.existsSync(skillPath),
      skillPath,
      projectLevel: id === 'codebuddy',
      pluginMigrationSupported: !!spec.pluginMigration,
      pluginMigrationReady: !!spec.pluginMigration && !!cli,
      pluginMigrationCli: cli,
      pluginMigrationReason: cli ? '' : pluginDataReadyMessage(id),
      runtimeMigrationSupported: !!spec.runtimeMigration,
      runtimeAdapter: spec.runtimeAdapter || null,
      runtimeAdapterReady: runtime.adapterReady,
      runtimeReason: runtime.reason,
      runtimeNote: spec.runtimeNote || '',
    }
  }
  return result
}

function statusPayload(host = 'dsh') {
  return {
    application: 'programmer-workflow',
    version: VERSION,
    ...hostStatus(host),
    hosts: hostsInfoV2(),
  }
}

function legacyImportPlugin(input) {
  const host = normalizeHost(input.host)
  const data = pluginDataForHost(host)
  const sourceRoot = input.source || (data.legacy && data.legacy.present && data.legacy.present
    .find((candidate) => fs.existsSync(path.join(candidate, 'memory.json')) || fs.existsSync(path.join(candidate, 'memory', 'memory.json')))) || ''
  if (!sourceRoot) throw new Error('没有找到旧版/共享 memory 源')
  const sourceMemory = path.join(sourceRoot, 'memory.json')
  const nestedMemory = path.join(sourceRoot, 'memory', 'memory.json')
  const sourceMemDir = fs.existsSync(sourceMemory) ? sourceRoot : (fs.existsSync(nestedMemory) ? path.join(sourceRoot, 'memory') : '')
  if (!sourceMemDir) throw new Error('旧数据源没有 memory.json')
  const targetMemDir = dataPaths(host).memory
  const targetMemory = path.join(targetMemDir, 'memory.json')
  const sourceHash = sha256File(path.join(sourceMemDir, 'memory.json'))
  if (fs.existsSync(targetMemory)) {
    if (sha256File(targetMemory) === sourceHash) return { ok: true, status: 'same', source: sourceRoot }
    const reportDir = path.join(hostHome(host), '.programmer-workflow-migration', 'legacy-conflicts')
    fs.mkdirSync(reportDir, { recursive: true })
    const report = path.join(reportDir, `${Date.now()}.json`)
    fs.writeFileSync(report, JSON.stringify({
      host, source: sourceRoot, target: targetMemDir, at: new Date().toISOString(),
      sourceInventory: inventoryJson(sourceMemDir), targetInventory: inventoryJson(targetMemDir),
    }, null, 2) + '\n', 'utf8')
    return { ok: false, status: 'conflict', source: sourceRoot, report }
  }
  const backup = path.join(hostHome(host), '.programmer-workflow-migration', 'backups', `legacy-${Date.now()}`, 'plugin')
  fs.mkdirSync(backup, { recursive: true })
  for (const name of fs.readdirSync(sourceMemDir)) {
    if (name === 'memory.lock') continue
    const src = path.join(sourceMemDir, name)
    if (fs.statSync(src).isFile()) fs.copyFileSync(src, path.join(backup, name))
  }
  fs.mkdirSync(targetMemDir, { recursive: true })
  for (const name of fs.readdirSync(sourceMemDir)) {
    if (name === 'memory.lock') continue
    const src = path.join(sourceMemDir, name)
    if (fs.statSync(src).isFile()) fs.copyFileSync(src, path.join(targetMemDir, name))
  }
  fs.writeFileSync(path.join(dataPaths(host).globalRoot, 'legacy-import.json'), JSON.stringify({
    host, source: sourceRoot, importedAt: new Date().toISOString(), backup, status: 'imported',
  }, null, 2) + '\n', 'utf8')
  return { ok: true, status: 'imported', source: sourceRoot, target: targetMemDir, backup }
}

function inventoryJson(root) {
  const file = path.join(root, 'memory.json')
  const data = readJsonSafe(file)
  const entries = data && Array.isArray(data.entries) ? data.entries : []
  const counts = { active: 0, proposed: 0, rejected: 0, total: entries.length }
  for (const entry of entries) if (entry && counts[entry.status] !== undefined) counts[entry.status] += 1
  return { sha256: sha256File(file), counts, ids: entries.map((e) => e && e.id).filter(Boolean).sort() }
}

function companionForHost(host) {
  const id = normalizeHost(host)
  const override = process.env.PROGRAMMER_WORKFLOW_CLI
  if (override) return fs.existsSync(override) ? path.resolve(override) : null
  const candidate = path.join(hostHome(id), 'skills', 'programmer-workflow', 'scripts', 'companion.py')
  return fs.existsSync(candidate) ? candidate : null
}

function pluginDataReadyMessage(host) {
  const id = normalizeHost(host)
  return `未找到 ${HOSTS[id].label} 的 Skill CLI（companion.py）：第一阶段插件数据迁移需要该宿主的 CLI。请先安装 Programmer Workflow Skill，或把 PROGRAMMER_WORKFLOW_CLI 指向可用的 companion.py。`
}

function pluginTargetForHost(host, targetRoot) {
  const id = normalizeHost(host)
  const spec = HOSTS[id] || HOSTS.dsh
  const text = String(targetRoot || '').trim()
  if (!text) throw new Error('请填写第一阶段插件数据目标根')
  if (text.startsWith('\\\\') || text.startsWith('//')) throw new Error('Junction 迁移不支持 UNC 目标')
  if (!path.isAbsolute(text)) throw new Error('目标根必须是绝对路径')
  return path.join(path.resolve(text), spec.dataDir, 'programmer-workflow')
}

function preparePluginMigration(input) {
  const host = normalizeHost(input.host)
  const config = readConfig(host)
  if (!config.migrationActionEnabled) throw new Error('设置页的迁移准备开关当前关闭；请先保存打开后再试。')
  const targetRoot = String(input.targetRoot || config.pluginMigrationTargetRoot || '').trim()
  const target = pluginTargetForHost(host, targetRoot)
  const source = dataPaths(host).globalRoot
  const current = pluginMigrationForHost(host)
  const currentTarget = current.completed ? current.actualTarget : ''
  if (currentTarget && samePath(target, currentTarget)) {
    throw new Error(`目标与当前迁移位置相同：${currentTarget}；无需再次迁移。`)
  }
  if (pathInside(target, source) || pathInside(source, target)) {
    throw new Error('目标不能与源插件目录重叠；请选择另一个目标根。')
  }
  if (currentTarget && (pathInside(target, currentTarget) || pathInside(currentTarget, target))) {
    throw new Error('新目标不能与当前实际迁移位置重叠；请选择完全独立的空目录。')
  }
  const pluginData = pluginDataForHost(host)
  if (pluginData.externallyOverridden) {
    throw new Error('检测到外部路径 override；默认迁移不会覆盖它，请先备份/导出并移除 override，或手工迁移。')
  }
  const companion = companionForHost(host)
  if (!companion) {
    throw new Error(pluginDataReadyMessage(host))
  }
  if (!fs.existsSync(source)) throw new Error(`源插件目录不存在：${source}`)
  if (path.resolve(source) === path.resolve(target)) throw new Error('目标不能与源插件目录相同')
  if (fs.existsSync(target) && fs.readdirSync(target).length) {
    throw new Error('目标目录已有内容；请选择空目录，避免静默合并')
  }
  const inv = memoryInventoryForHost(host)
  if (!inv.ok && !inv.missing) throw new Error(inv.error || 'memory.json 无法解析')
  const stamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14)
  const control = path.join(hostHome(host), '.programmer-workflow-migration')
  let backup = path.join(control, 'backups', `${stamp}-prepare`, 'plugin')
  for (let counter = 2; fs.existsSync(backup); counter += 1) {
    backup = path.join(control, 'backups', `${stamp}-prepare-${counter}`, 'plugin')
  }
  fs.mkdirSync(backup, { recursive: true })
  for (const name of ['memory.json', 'MEMORY.md', 'config.json', 'README.md']) {
    const file = path.join(dataPaths(host).memory, name)
    const rootFile = path.join(source, name)
    if (fs.existsSync(file)) fs.copyFileSync(file, path.join(backup, name))
    else if (fs.existsSync(rootFile)) fs.copyFileSync(rootFile, path.join(backup, name))
  }
  fs.writeFileSync(path.join(backup, 'inventory.json'), JSON.stringify(inv, null, 2) + '\n', 'utf8')
  // Keep the record of a migration that is still in effect: preparing a new
  // target must not erase the fact that the current link is verified.
  const previous = current.verified
    ? { host, status: 'completed', source: current.source, target: current.actualTarget, targetRoot: current.verifiedTargetRoot, backup: current.backup, verifiedAt: current.verifiedAt, inventory: current.inventory }
    : null
  const state = {
    host,
    status: 'prepared',
    source,
    target,
    targetRoot,
    backup,
    preparedAt: new Date().toISOString(),
    verifiedAt: null,
    inventory: inv,
    previous,
  }
  fs.mkdirSync(control, { recursive: true })
  fs.writeFileSync(path.join(control, 'plugin-state.json'), JSON.stringify(state, null, 2) + '\n', 'utf8')
  const cmd = [
    '@echo off', 'setlocal',
    `set "PROGRAMMER_WORKFLOW_HOST=${host}"`,
    `set "PROGRAMMER_WORKFLOW_GLOBAL=${source}"`,
    `python "${companion}" migrate-plugin apply --host ${host} --target-root "${targetRoot}" --yes`,
    'if errorlevel 1 (echo.',
    '  echo Plugin data migration failed. See the error above and keep the backup.',
    '  pause',
    '  exit /b 1',
    ')',
    'endlocal',
    '',
  ].join('\r\n')
  const launcher = path.join(control, 'run-stage1-plugin.cmd')
  fs.writeFileSync(launcher, cmd, 'utf8')
  const rollback = [
    '@echo off', 'setlocal',
    'REM Order is enforced: while stage 2 is prepared/active/completed the CLI',
    'REM refuses to restore stage 1. Roll stage 2 back first.',
    `set "PROGRAMMER_WORKFLOW_HOST=${host}"`,
    `set "PROGRAMMER_WORKFLOW_GLOBAL=${source}"`,
    `python "${companion}" migrate-plugin rollback --host ${host}`,
    'if errorlevel 1 (echo.',
    '  echo Plugin data rollback failed. The latest backup remains under .programmer-workflow-migration\\backups.',
    '  pause',
    '  exit /b 1',
    ')',
    'endlocal',
    '',
  ].join('\r\n')
  const rollbackLauncher = path.join(control, 'run-stage1-rollback-plugin.cmd')
  fs.writeFileSync(rollbackLauncher, rollback, 'utf8')
  return {
    ok: true, host, source, target, targetRoot, backup, launcher, rollbackLauncher,
    statePath: path.join(control, 'plugin-state.json'), status: 'prepared',
    reprepare: !!previous, previousTarget: previous ? previous.target : null,
  }
}

function prepareRuntimeMigration(input) {
  const host = normalizeHost(input.host)
  const config = readConfig(host)
  if (!config.migrationActionEnabled) throw new Error('设置页的迁移准备开关当前关闭；请先保存打开后再试。')
  const plugin = pluginMigrationForHost(host)
  if (!plugin.completed) {
    throw new Error('请先完成并校验第一阶段插件数据迁移。')
  }
  const spec = HOSTS[host]
  if (!spec.runtimeMigration) {
    throw new Error('当前仅支持迁移 Programmer Workflow 插件数据，尚未适配该编辑器的运行数据迁移。')
  }
  const runtime = runtimeToolsForHost(host, config, spec)
  if (!runtime.adapterReady || !runtime.migrate || !runtime.rollback) {
    throw new Error(runtime.reason || '运行数据迁移适配器不可用。')
  }
  const targetRoot = String(input.targetRoot || config.runtimeMigrationTargetRoot || '').trim()
  if (!targetRoot) throw new Error('请填写第二阶段运行数据目标根')
  if (targetRoot.startsWith('\\\\') || targetRoot.startsWith('//')) throw new Error('运行数据迁移不支持 UNC 目标')
  if (!path.isAbsolute(targetRoot)) throw new Error('目标根必须是绝对路径')
  const resolvedRoot = path.resolve(targetRoot)
  // `targetRoot` is the user's root; `target` is what the adapter writes
  // (`<root>/<host data dir>`). The adapter appends the data dir itself, so the
  // launcher must export the ROOT — exporting `target` would double it.
  const target = path.join(resolvedRoot, spec.dataDir)
  const stage2 = stage2InfoForHost(host, spec, config)
  if (stage2.completed && samePath(target, stage2.actualLocation)) {
    throw new Error(`目标与当前运行数据位置相同：${stage2.actualLocation}；无需再次迁移。`)
  }
  if (plugin.target && !pathInside(plugin.target, target)) {
    throw new Error('第一阶段插件目标不在第二阶段运行数据目标内；本版本只支持同一目标根下的嵌套 Junction（跨根按清单重建尚未实现）。请把两阶段目标放在同一根下，或先手工迁移插件数据。')
  }
  const control = runtimeControlDir(host)
  fs.mkdirSync(control, { recursive: true })
  const markers = runtimeMarkers(host)
  const previousRuntime = stage2.completed
    ? {
      status: 'completed',
      target: stage2.recordedTarget,
      targetRoot: stage2.recordedTargetRoot,
      completedAt: stage2.verifiedAt,
    }
    : null
  const envDest = runtime.adapter === 'kimi' ? 'KIMI_MIG_DEST' : 'DSH_MIG_DEST'
  const envSrc = runtime.adapter === 'kimi' ? 'KIMI_MIG_SRC' : 'DSH_MIG_SRC'
  const source = hostHome(host)
  const commonLines = [
    '@echo off', 'setlocal',
    `set "${envDest}=${resolvedRoot}"`,
    `set "${envSrc}=${source}"`,
    runtime.adapter === 'kimi'
      ? `set "KIMI_MIGRATION_TOOLS=${runtime.toolsPath}"`
      : `set "PROGRAMMER_WORKFLOW_DSH_TOOLS=${runtime.toolsPath}"`,
  ]
  const launcher = markers.launcher
  const rollbackLauncher = markers.rollbackLauncher
  const migrateLines = [
    ...commonLines,
    `call "${runtime.migrate}"`,
    'if errorlevel 1 (echo.',
    '  echo Stage 2 runtime migration failed. See the error above.',
    '  pause',
    '  exit /b 1',
    ')',
    `del "${markers.rolledBack}" >nul 2>&1`,
    `echo completed %DATE% %TIME% > "${markers.completed}"`,
    'endlocal',
    '',
  ]
  const rollbackLines = [
    ...commonLines,
    `call "${runtime.rollback}"`,
    'if errorlevel 1 (echo.',
    '  echo Stage 2 rollback failed. See the error above.',
    '  pause',
    '  exit /b 1',
    ')',
    `del "${markers.completed}" >nul 2>&1`,
    `echo rolled back %DATE% %TIME% > "${markers.rolledBack}"`,
    'endlocal',
    '',
  ]
  // Both launchers are written and reported from these same variables.
  fs.writeFileSync(launcher, migrateLines.join('\r\n'), 'utf8')
  fs.writeFileSync(rollbackLauncher, rollbackLines.join('\r\n'), 'utf8')
  const state = {
    host,
    status: 'prepared',
    adapter: runtime.adapter,
    source,
    target,
    targetRoot: resolvedRoot,
    toolsPath: runtime.toolsPath,
    migrateScript: runtime.migrate,
    rollbackScript: runtime.rollback,
    launcher,
    rollbackLauncher,
    preparedAt: new Date().toISOString(),
    previous: previousRuntime,
  }
  fs.writeFileSync(path.join(control, 'runtime-state.json'), JSON.stringify(state, null, 2) + '\n', 'utf8')
  return {
    ok: true,
    host,
    adapter: runtime.adapter,
    source,
    target,
    targetRoot: resolvedRoot,
    toolsPath: runtime.toolsPath,
    launcher,
    rollbackLauncher,
    statePath: path.join(control, 'runtime-state.json'),
    status: 'prepared',
    reprepare: !!previousRuntime,
    previousLocation: previousRuntime ? previousRuntime.target : null,
  }
}

function prepareMigration(input) {
  return prepareRuntimeMigration(input)
}

function realPath(target) {
  try {
    return fs.realpathSync.native ? fs.realpathSync.native(target) : fs.realpathSync(target)
  } catch {
    return target
  }
}

function requestHost(req, bodyHost) {
  const url = new URL(req.url || '/', 'http://dsh.invalid')
  const raw = String(url.searchParams.get('host') || bodyHost || 'dsh')
  const id = hostAlias(raw)
  if (!id) throw new Error(`unknown host: ${raw}`)
  return id
}

function sendJson(res, code, value) {
  const body = JSON.stringify(value)
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Content-Length': Buffer.byteLength(body),
  })
  res.end(body)
}

async function readJsonBody(req, limit = 1_000_000) {
  let size = 0
  const chunks = []
  for await (const chunk of req) {
    size += chunk.length
    if (size > limit) throw new Error('request body too large')
    chunks.push(chunk)
  }
  if (!chunks.length) return {}
  const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'))
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('body must be an object')
  return parsed
}

function copyDir(source, target) {
  fs.mkdirSync(target, { recursive: true })
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name)
    const to = path.join(target, entry.name)
    if (entry.isDirectory()) copyDir(from, to)
    else if (entry.isFile()) fs.copyFileSync(from, to)
  }
}

function serveMigration(_req, res) {
  const file = path.join(path.dirname(fileURLToPath(import.meta.url)), 'migration.html')
  try {
    const html = fs.readFileSync(file, 'utf8')
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Length': Buffer.byteLength(html),
    })
    res.end(html)
  } catch (error) {
    sendJson(res, 500, { error: 'migration tutorial not found', detail: String(error) })
  }
}

export function apply(ctx) {
  try {
    ensureLayout()
  } catch (error) {
    console.error('[programmer-workflow] cannot prepare global data root:', error)
  }

  // This plugin ships its own Settings page and stores its config in
  // <globalRoot>/config.json, so it does not depend on the Host settings schema.
  ctx.inject(['webServer'], (child) => {
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/status',
      handler: (req, res) => {
        try {
          sendJson(res, 200, statusPayload(requestHost(req)))
        } catch (error) {
          sendJson(res, 400, { ok: false, error: String(error.message || error) })
        }
      },
    }))
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/config',
      handler: async (req, res) => {
        try {
          const host = requestHost(req)
          if (req.method === 'GET') return sendJson(res, 200, { ok: true, host, config: readConfig(host), status: statusPayload(host) })
          const body = await readJsonBody(req)
          body.host = body.host || host
          const targetHost = requestHost(req, body.host)
          if (body.reset !== true) {
            const merged = { ...readConfig(targetHost), ...body }
            const errors = validateConfigInput(merged)
            if (errors.length) return sendJson(res, 400, { ok: false, error: errors.join('；'), fields: errors })
            const config = writeConfig(merged, targetHost)
            return sendJson(res, 200, { ok: true, host: targetHost, config, status: statusPayload(targetHost) })
          }
          const config = writeConfig(DEFAULT_CONFIG, targetHost)
          sendJson(res, 200, { ok: true, host: targetHost, config, status: statusPayload(targetHost) })
        } catch (error) {
          sendJson(res, 400, { ok: false, error: String(error && error.message ? error.message : error) })
        }
      },
    }))
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/plugin-migration/legacy-import',
      handler: async (req, res) => {
        try {
          if (req.method !== 'POST') return sendJson(res, 405, { ok: false, error: 'POST required' })
          const body = await readJsonBody(req)
          const result = legacyImportPlugin({ host: body.host || requestHost(req), source: body.source })
          sendJson(res, result.ok ? 200 : 409, { ...result, status: statusPayload(normalizeHost(body.host || 'dsh')) })
        } catch (error) {
          sendJson(res, 400, { ok: false, error: String(error && error.message ? error.message : error) })
        }
      },
    }))
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/plugin-migration/prepare',
      handler: async (req, res) => {
        try {
          if (req.method !== 'POST') return sendJson(res, 405, { ok: false, error: 'POST required' })
          const body = await readJsonBody(req)
          const result = preparePluginMigration({ host: body.host || requestHost(req), targetRoot: body.targetRoot })
          sendJson(res, 200, { ok: true, ...result, status: statusPayload(result.host) })
        } catch (error) {
          sendJson(res, 400, { ok: false, error: String(error && error.message ? error.message : error) })
        }
      },
    }))
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/migration/prepare',
      handler: async (req, res) => {
        try {
          if (req.method !== 'POST') return sendJson(res, 405, { ok: false, error: 'POST required' })
          const body = await readJsonBody(req)
          const host = normalizeHost(body.host || requestHost(req))
          const result = prepareRuntimeMigration({ host, targetRoot: body.targetRoot })
          sendJson(res, 200, { ok: true, ...result, status: statusPayload(host) })
        } catch (error) {
          sendJson(res, 400, { ok: false, error: String(error && error.message ? error.message : error) })
        }
      },
    }))
    child.effect(() => child.webServer.register({
      kind: 'exact',
      path: '/programmer-workflow/migration',
      handler: serveMigration,
    }))
  })
}

export { ENTRY_ID, DEFAULT_CONFIG, VERSION }
