/*
 * Programmer Workflow · local settings page
 *
 * Classic browser script: no modules, no eval, no inline handlers, no CDN.
 * The token arrives in location.hash and is sent in
 * X-Programmer-Workflow-Token; no workspace path is ever sent to the API.
 */
(function () {
  'use strict'

  var HOST_LABELS = {
    dsh: 'DeepSeek Harness',
    kimi: 'Kimi Code',
    codebuddy: 'CodeBuddy'
  }
  var HOST_POLICY_LABELS = {
    dsh: 'DeepSeek Harness',
    kimi: 'Kimi',
    codebuddy: 'CodeBuddy'
  }
  var TEXT_FIELDS = [
    'workspaceDataDir', 'debugLogDir', 'docsDir', 'prototypeFile',
    'language', 'pluginMigrationTargetRoot', 'runtimeMigrationTargetRoot',
    'kimiMigrationTools'
  ]
  var INT_FIELDS = ['satisfactionThreshold', 'bugfixThreshold', 'retentionDays']
  var SELECT_FIELDS = ['workflowMode', 'planFormat']
  var BOOL_FIELDS = [
    'userMemoryEnabled', 'workspaceMemoryEnabled', 'devOnlyAutoInstrument',
    'docsEnabled', 'prototypeEnabled', 'migrationActionEnabled', 'screenshotEnabled'
  ]

  var state = {
    host: 'kimi',
    data: null,
    config: null,
    saved: null,
    dirty: false,
    saving: false,
    loading: false,
    busy: false,
    expanded: { plugin: false, runtime: false },
    lastFocus: null,
    copyTimer: null,
    toastTimer: null,
    navTick: 0,
    token: ''
  }
  var pathValues = {}
  var el = {}

  // ------------------------------------------------------------------ helpers

  function byId(id) {
    return document.getElementById(id)
  }

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector))
  }

  function show(node, visible) {
    if (node) node.hidden = !visible
  }

  function inputFor(key) {
    return document.querySelector('[data-field-input="' + key + '"]')
  }

  function switchFor(key) {
    return document.querySelector('[data-switch="' + key + '"]')
  }

  function fieldFor(key) {
    return document.querySelector('[data-field="' + key + '"]')
  }

  function hostLabel(host) {
    return HOST_LABELS[host] || host
  }

  function readToken() {
    var match = /(?:^#|&)token=([^&]*)/.exec(window.location.hash || '')
    if (!match) return ''
    try {
      return decodeURIComponent(match[1])
    } catch (error) {
      return match[1]
    }
  }

  function readStartHost() {
    try {
      var host = new URLSearchParams(window.location.search).get('host')
      if (host && HOST_LABELS[host]) return host
    } catch (error) {
      /* older browsers: fall through to Kimi, the command's default host */
    }
    return 'kimi'
  }

  function api(path, options) {
    var settings = options || {}
    var headers = { Accept: 'application/json' }
    if (state.token) headers['X-Programmer-Workflow-Token'] = state.token
    var init = {
      method: settings.method || 'GET',
      headers: headers,
      cache: 'no-store',
      credentials: 'same-origin'
    }
    if (settings.body !== undefined) {
      headers['Content-Type'] = 'application/json'
      init.body = JSON.stringify(settings.body)
    }
    return fetch(path, init).then(function (response) {
      return response.json().catch(function () { return {} }).then(function (payload) {
        if (!response.ok) {
          var error = new Error((payload && payload.error) || ('HTTP ' + response.status))
          error.status = response.status
          error.payload = payload || {}
          throw error
        }
        return payload
      })
    })
  }

  function errorMessage(error) {
    if (error && error.status === 403) {
      return '访问令牌无效或缺失。请从命令行输出的完整 URL 重新打开设置页。'
    }
    if (error && error.message) return error.message
    return '无法连接本地设置服务。'
  }

  // ------------------------------------------------------------------- status

  function setSaveState(kind, message) {
    if (!el.saveState) return
    var extra = ''
    if (kind === 'dirty' || kind === 'success' || kind === 'error') extra = ' is-' + kind
    el.saveState.className = 'pwf-save-state' + extra
    el.saveState.textContent = message
  }

  function setFeedback(step, message, kind) {
    var node = step === 'plugin' ? el.pluginFeedback : el.runtimeFeedback
    if (!node) return
    node.textContent = message || ''
    node.hidden = !message
    node.className = 'pwf-step-feedback' + (kind ? ' is-' + kind : '')
  }

  function toast(message, kind) {
    if (!el.toast) return
    el.toast.textContent = message
    el.toast.className = 'pwf-toast' + (kind ? ' is-' + kind : '')
    el.toast.hidden = false
    window.clearTimeout(state.toastTimer)
    state.toastTimer = window.setTimeout(function () {
      el.toast.hidden = true
    }, 3200)
  }

  // ------------------------------------------------------------- field errors

  function setFieldError(key, message) {
    var field = fieldFor(key)
    var errorNode = document.querySelector('[data-field-error="' + key + '"]')
    var input = inputFor(key)
    if (field) field.classList.add('pwf-field--error')
    if (errorNode) {
      errorNode.textContent = message
      errorNode.hidden = false
    }
    if (input) input.setAttribute('aria-invalid', 'true')
  }

  function clearFieldError(key) {
    var field = fieldFor(key)
    var errorNode = document.querySelector('[data-field-error="' + key + '"]')
    var input = inputFor(key)
    if (field) field.classList.remove('pwf-field--error')
    if (errorNode) {
      errorNode.textContent = ''
      errorNode.hidden = true
    }
    if (input) input.removeAttribute('aria-invalid')
  }

  function clearFieldErrors() {
    all('[data-field-error]').forEach(function (node) {
      node.textContent = ''
      node.hidden = true
    })
    all('.pwf-field--error').forEach(function (node) {
      node.classList.remove('pwf-field--error')
    })
    all('[data-field-input]').forEach(function (node) {
      node.removeAttribute('aria-invalid')
    })
  }

  function showFieldErrors(fields) {
    var first = null
    Object.keys(fields || {}).forEach(function (key) {
      setFieldError(key, fields[key])
      if (!first) first = inputFor(key)
    })
    if (first) first.focus()
  }

  // --------------------------------------------------------------- draft state

  function snapshot() {
    var values = {}
    TEXT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      values[key] = node ? node.value : ''
    })
    SELECT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      values[key] = node ? node.value : ''
    })
    INT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      values[key] = node ? node.value : ''
    })
    BOOL_FIELDS.forEach(function (key) {
      var node = switchFor(key)
      values[key] = Boolean(node && node.getAttribute('aria-checked') === 'true')
    })
    return values
  }

  function buildPayload() {
    var payload = {}
    TEXT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      payload[key] = node ? node.value : ''
    })
    SELECT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      payload[key] = node ? node.value : ''
    })
    INT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      var raw = node ? node.value.trim() : ''
      payload[key] = raw === '' ? null : Number(raw)
    })
    BOOL_FIELDS.forEach(function (key) {
      var node = switchFor(key)
      payload[key] = Boolean(node && node.getAttribute('aria-checked') === 'true')
    })
    return payload
  }

  function updateDirty(announce) {
    state.dirty = JSON.stringify(snapshot()) !== JSON.stringify(state.saved || {})
    if (el.save) {
      el.save.disabled = !state.dirty || state.saving || state.busy
      if (!state.saving) el.save.textContent = '保存设置'
    }
    updateActionAvailability()
    if (announce && !state.saving) {
      if (state.dirty) setSaveState('dirty', '有未保存修改')
      else setSaveState('idle', '没有未保存修改')
    }
  }

  function updateActionAvailability() {
    if (!state.data) return
    var plugin = state.data.migration.plugin || {}
    var runtime = state.data.migration.runtime || {}
    var pluginReady = Boolean(plugin.ready) && !state.busy && !state.dirty
    var runtimeReady = Boolean(runtime.canPrepare) && !state.busy && !state.dirty
    if (el.pluginPrepare) {
      el.pluginPrepare.disabled = !pluginReady
      el.pluginPrepare.title = pluginReady ? '' : (state.dirty ? '请先保存设置' : (plugin.reason || '当前不可准备迁移脚本'))
    }
    if (el.runtimePrepare) {
      el.runtimePrepare.disabled = !runtimeReady
      el.runtimePrepare.title = runtimeReady ? '' : (state.dirty ? '请先保存设置' : (runtime.reason || '当前不可准备迁移脚本'))
    }
    var pluginReason = plugin.completed ? '' : (plugin.reason || '')
    if (!plugin.completed && state.dirty) {
      pluginReason = '请先保存设置，再准备迁移脚本。' + (pluginReason ? ' ' + pluginReason : '')
    }
    if (el.pluginReason) {
      el.pluginReason.textContent = pluginReason
      el.pluginReason.hidden = !pluginReason
    }
    var runtimeCompleted = runtime.stage2Status === 'completed' || runtime.stage2Completed === true
    var runtimeReason = runtimeCompleted ? '' : (runtime.reason || '')
    if (!runtimeCompleted && state.dirty) {
      runtimeReason = '请先保存设置，再准备迁移脚本。' + (runtimeReason ? ' ' + runtimeReason : '')
    }
    if (el.runtimeReason) {
      el.runtimeReason.textContent = runtimeReason
      el.runtimeReason.hidden = !runtimeReason
    }
    if (state.data) renderLegacy(state.data.migration.legacy)
  }

  function onDraftChange(event) {
    var node = event.target
    var key = node && (node.getAttribute('data-field-input') || node.getAttribute('data-switch'))
    if (key) clearFieldError(key)
    if (key === 'pluginMigrationTargetRoot' || key === 'runtimeMigrationTargetRoot') {
      updateTargetPreviews()
    }
    updateDirty(true)
  }

  function toggleSwitch(button) {
    var next = button.getAttribute('aria-checked') === 'true' ? 'false' : 'true'
    button.setAttribute('aria-checked', next)
    onDraftChange({ target: button })
  }

  // ---------------------------------------------------------------- rendering

  function fillForm(config) {
    TEXT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      if (node) node.value = config[key] === undefined || config[key] === null ? '' : String(config[key])
    })
    SELECT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      if (!node) return
      node.value = String(config[key] === undefined ? '' : config[key])
      if (node.selectedIndex < 0) node.selectedIndex = 0
    })
    INT_FIELDS.forEach(function (key) {
      var node = inputFor(key)
      if (node) node.value = config[key] === undefined || config[key] === null ? '' : String(config[key])
    })
    BOOL_FIELDS.forEach(function (key) {
      var node = switchFor(key)
      if (node) node.setAttribute('aria-checked', config[key] ? 'true' : 'false')
    })
    updateTargetPreviews()
  }

  function setPathValue(key, value, placeholder) {
    var node = document.querySelector('[data-path-value="' + key + '"]')
    var copy = document.querySelector('[data-copy-path="' + key + '"]')
    var real = value ? String(value) : ''
    if (node) node.textContent = real || placeholder || '—'
    pathValues[key] = real
    if (copy) copy.disabled = !real
  }

  function renderPaths(data) {
    pathValues = {}
    setPathValue('globalRoot', data.paths.globalRoot)
    setPathValue('realGlobalRoot', data.paths.realGlobalRoot)
    setPathValue('memoryRoot', data.paths.memoryRoot)
    setPathValue('configPath', data.paths.configPath)
    var external = data.external || {}
    var globalRow = document.querySelector('[data-path="externalGlobalOverride"]')
    var memoryRow = document.querySelector('[data-path="externalMemoryOverride"]')
    show(globalRow, Boolean(external.globalOverride))
    show(memoryRow, Boolean(external.memoryOverride))
    setPathValue('externalGlobalOverride', external.globalOverride || '')
    setPathValue('externalMemoryOverride', external.memoryOverride || '')
  }

  function notice(kind, message) {
    var wrap = document.createElement('div')
    wrap.className = 'pwf-notice pwf-notice--' + kind
    var icon = document.createElement('span')
    icon.className = 'pwf-notice-icon'
    icon.setAttribute('aria-hidden', 'true')
    icon.textContent = kind === 'error' || kind === 'warn' ? '!' : (kind === 'ok' ? '✓' : 'i')
    var body = document.createElement('div')
    body.className = 'pwf-notice-body'
    body.textContent = message
    wrap.appendChild(icon)
    wrap.appendChild(body)
    return wrap
  }

  function renderNotices(data) {
    if (!el.dataNotices) return
    el.dataNotices.textContent = ''
    var external = data.external || {}
    if (external.globalOverride) {
      el.dataNotices.appendChild(notice('warn', '检测到外部插件根 override（PROGRAMMER_WORKFLOW_GLOBAL）：' + external.globalOverride + '。默认迁移不会覆盖它，请自行备份或导出。'))
    }
    if (external.memoryOverride) {
      el.dataNotices.appendChild(notice('warn', '检测到外部记忆目录 override（PROGRAMMER_WORKFLOW_HOME）：' + external.memoryOverride + '。它不属于默认插件根，迁移前请先处理。'))
    }
    if (data.paths.globalRoot !== data.paths.realGlobalRoot) {
      el.dataNotices.appendChild(notice('info', '当前插件路径是 Junction 或符号链接；真实落盘位置为 ' + data.paths.realGlobalRoot + '。'))
    }
    var legacy = data.migration.legacy || {}
    if (legacy.conflict) {
      el.dataNotices.appendChild(notice('error', '旧共享记忆与当前记忆内容不同。一次性导入只会生成冲突报告，不会覆盖当前 memory.json。'))
    } else if (legacy.source && !legacy.imported) {
      el.dataNotices.appendChild(notice('warn', '发现旧共享记忆：' + legacy.source + '。可在“数据迁移”分组中一次性导入。'))
    }
    var workspaceNote = data.migration.workspaceMemory && data.migration.workspaceMemory.note
    if (workspaceNote) el.dataNotices.appendChild(notice('info', workspaceNote))
  }

  function previewTarget(rootValue, dataDir) {
    var text = String(rootValue || '').trim()
    if (!text) return '—'
    var clean = text.replace(/[\\/]+$/, '')
    var separator = clean.charAt(0) === '/' && clean.indexOf('\\') === -1 ? '/' : '\\'
    return clean + separator + dataDir
  }

  function updateTargetPreviews() {
    if (!state.data) return
    var info = state.data.hosts[state.data.host] || {}
    var dataDir = info.dataDir || '.kimi-code'
    var pluginInput = inputFor('pluginMigrationTargetRoot')
    var runtimeInput = inputFor('runtimeMigrationTargetRoot')
    el.pluginTargetPreview.textContent = previewTarget(pluginInput ? pluginInput.value : '', dataDir)
    el.runtimeTargetPreview.textContent = previewTarget(runtimeInput ? runtimeInput.value : '', dataDir)
  }

  function toneBadge(node, tone, label) {
    if (!node) return
    node.className = 'pwf-badge' + (tone && tone !== 'muted' ? ' pwf-badge--' + tone : ' pwf-badge--muted')
    node.textContent = label || '需要检查'
  }

  function targetVisibility(completed, expanded, targetWrap, expandButton, cancelButton) {
    var showTarget = !completed || expanded
    show(targetWrap, showTarget)
    show(expandButton, completed && !expanded)
    show(cancelButton, completed && expanded)
  }

  function renderMigration(migration) {
    if (!migration) return
    var plugin = migration.plugin || {}
    var runtime = migration.runtime || {}
    toneBadge(el.pluginBadge, plugin.tone, plugin.label)
    toneBadge(el.runtimeBadge, runtime.tone, runtime.label)

    var runtimeCompleted = runtime.stage2Status === 'completed' || runtime.stage2Completed === true

    targetVisibility(
      Boolean(plugin.completed), state.expanded.plugin,
      el.pluginTargetWrap, el.pluginExpand, el.pluginCancel
    )
    targetVisibility(
      Boolean(runtimeCompleted), state.expanded.runtime,
      el.runtimeTargetWrap, el.runtimeExpand, el.runtimeCancel
    )

    setPathValue('pluginSource', plugin.source || '')
    setPathValue('pluginTarget', plugin.target || plugin.desiredTarget || '', '准备后显示')
    setPathValue('pluginBackup', plugin.backup || '', '准备后生成')
    setPathValue('pluginLauncher', plugin.launcher || '', '准备后生成')
    setPathValue('pluginRollbackLauncher', plugin.rollbackLauncher || '', '准备后生成')
    setPathValue('pluginState', plugin.statePath || '')

    var hostHome = state.data && state.data.paths ? state.data.paths.hostHome : ''
    setPathValue('runtimeSource', runtime.source || hostHome || '')
    setPathValue('runtimeTarget', runtime.target || runtime.desiredTarget || '', '准备后显示')
    setPathValue('runtimeBackup', '', '由适配器在运行时创建')
    setPathValue('runtimeTools', runtime.toolsPath || runtime.detectedToolsPath || '', '未配置')
    setPathValue('runtimeLauncher', runtime.launcher || '', '准备后生成')
    setPathValue('runtimeRollbackLauncher', runtime.rollbackLauncher || '', '准备后生成')

    var hostOnly = all('[data-host-only]')
    hostOnly.forEach(function (node) {
      node.hidden = node.getAttribute('data-host-only') !== (state.data ? state.data.host : '')
    })
    updateTargetPreviews()
    updateActionAvailability()
  }

  function renderLegacy(legacy) {
    if (!el.legacy) return
    var source = legacy && legacy.source
    var visible = Boolean(source) && !legacy.imported
    show(el.legacy, visible)
    if (!visible) return
    var suffix = state.dirty ? ' 请先保存设置后再导入。' : ''
    if (legacy.conflict) {
      el.legacyDesc.textContent = '来源：' + source + '。内容与当前记忆不同；导入会生成冲突报告，当前文件不会被覆盖。' + suffix
      el.legacyImport.disabled = Boolean(state.dirty || state.busy)
      el.legacyImport.title = state.dirty ? '请先保存设置' : ''
    } else if (legacy.same) {
      el.legacyDesc.textContent = '来源：' + source + '。内容与当前记忆相同，无需重复导入。'
      el.legacyImport.disabled = true
      el.legacyImport.title = '内容相同，无需导入'
    } else {
      el.legacyDesc.textContent = '来源：' + source + '。导入会先备份当前记忆，并保留 active / proposed / rejected 状态。' + suffix
      el.legacyImport.disabled = Boolean(state.dirty || state.busy)
      el.legacyImport.title = state.dirty ? '请先保存设置' : ''
    }
  }

  function renderHostTabs(data) {
    all('.pwf-host-tab').forEach(function (button) {
      var host = button.getAttribute('data-host')
      var info = (data.hosts && data.hosts[host]) || {}
      button.setAttribute('aria-pressed', host === data.host ? 'true' : 'false')
      var meta = button.querySelector('[data-host-meta]')
      if (meta) {
        var prefix = info.installed ? '已安装' : '未安装'
        if (info.projectLevel) prefix += ' · 项目级'
        meta.textContent = prefix + ' · ' + (info.planFile || 'plan.md')
      }
    })
  }

  function renderHeader(data) {
    var label = hostLabel(data.host)
    el.version.textContent = 'v' + (data.version || '0.1.0')
    el.chipHost.textContent = label + ' · 本地配置'
    el.savebarHost.textContent = '当前宿主：' + label
    el.policyHost.textContent = HOST_POLICY_LABELS[data.host] || label
    var info = (data.hosts && data.hosts[data.host]) || {}
    el.hostSummary.textContent = '当前：' + label + ' · ' + (info.installed ? '已安装' : '未安装') +
      ' · Plan 文件：' + (info.planFile || 'plan.md')
    document.title = '程序员工作流 · ' + label + ' 设置'
  }

  function applyState(data) {
    state.data = data
    state.host = data.host
    state.config = data.config
    renderHeader(data)
    renderHostTabs(data)
    fillForm(data.config)
    renderPaths(data)
    renderNotices(data)
    renderMigration(data.migration)
    renderLegacy(data.migration.legacy)
    clearFieldErrors()
    show(el.loading, false)
    show(el.error, false)
    show(el.main, true)
    state.saved = snapshot()
    updateDirty(false)
    updateNav()
  }

  // -------------------------------------------------------------------- load

  function showInitialError(message) {
    show(el.loading, false)
    show(el.main, false)
    show(el.error, true)
    el.errorMessage.textContent = message
  }

  function load(host, reason) {
    if (state.loading) return Promise.resolve()
    state.loading = true
    state.host = host
    var initial = !state.data
    if (initial) {
      show(el.loading, true)
      show(el.error, false)
    }
    setSaveState('loading', '正在读取 ' + hostLabel(host) + ' 的配置…')
    return api('/api/status?host=' + encodeURIComponent(host)).then(
      function (data) {
        state.loading = false
        applyState(data)
        if (reason === 'saved') setSaveState('success', '已保存到 ' + hostLabel(host) + ' 的独立 config.json')
        else if (reason === 'reset') setSaveState('success', '已恢复 ' + hostLabel(host) + ' 的默认设置（记忆未删除）')
        else if (reason === 'reloaded') setSaveState('success', '已重新读取 ' + hostLabel(host) + ' 的配置')
        else if (reason === 'switched') setSaveState('idle', '已切换到 ' + hostLabel(host) + ' · 没有未保存修改')
        else setSaveState('idle', '已读取 ' + hostLabel(host) + ' 的配置')
      },
      function (error) {
        state.loading = false
        var message = errorMessage(error)
        if (state.data) state.host = state.data.host
        if (initial) showInitialError(message)
        else {
          setSaveState('error', '读取失败：' + message)
          toast('读取失败：' + message, 'error')
        }
      }
    )
  }

  // --------------------------------------------------------------- confirm UI

  function confirmAction(options) {
    return new Promise(function (resolve) {
      if (!el.confirm || typeof el.confirm.showModal !== 'function') {
        resolve(window.confirm(options.title + '\n\n' + options.message))
        return
      }
      el.confirmTitle.textContent = options.title
      el.confirmText.textContent = options.message
      el.confirmOk.textContent = options.confirmLabel || '继续'
      el.confirmOk.className = 'pwf-btn ' + (options.danger ? 'pwf-btn--danger' : 'pwf-btn--primary')
      el.confirmCancel.textContent = options.cancelLabel || '取消'
      state.lastFocus = document.activeElement
      var settled = false
      function finish(value) {
        if (settled) return
        settled = true
        el.confirm.removeEventListener('close', onClose)
        if (el.confirm.open) el.confirm.close()
        if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus()
        resolve(value)
      }
      function onClose() {
        finish(el.confirm.returnValue === 'confirm')
      }
      el.confirm.returnValue = ''
      el.confirm.addEventListener('close', onClose)
      el.confirm.showModal()
      el.confirmOk.focus()
    })
  }

  // ------------------------------------------------------------------ actions

  function switchHost(host) {
    if (!host || host === state.host || state.loading || state.busy) return
    if (state.dirty) {
      confirmAction({
        title: '切换宿主？',
        message: '当前有未保存修改。切换到 ' + hostLabel(host) + ' 会丢弃这些修改，且不会写入当前宿主。',
        confirmLabel: '丢弃并切换',
        cancelLabel: '留在 ' + hostLabel(state.host)
      }).then(function (ok) {
        if (ok) load(host, 'switched')
      })
      return
    }
    load(host, 'switched')
  }

  function reload() {
    if (state.loading || state.busy) return
    if (!state.dirty) {
      load(state.host, 'reloaded')
      return
    }
    confirmAction({
      title: '重新读取？',
      message: '重新读取 ' + hostLabel(state.host) + ' 会丢弃当前未保存的修改。',
      confirmLabel: '丢弃并重新读取'
    }).then(function (ok) {
      if (ok) load(state.host, 'reloaded')
    })
  }

  function resetDefaults() {
    if (state.loading || state.busy || state.saving) return
    var message = '恢复默认只会重置 ' + hostLabel(state.host) + ' 的 config.json，' +
      '不会删除 memory/、MEMORY.md 或 memory.json，也不会影响其他宿主。'
    if (state.dirty) message += ' 当前未保存的修改会被丢弃。'
    confirmAction({
      title: '恢复 ' + hostLabel(state.host) + ' 的默认设置？',
      message: message,
      confirmLabel: '恢复默认',
      danger: true
    }).then(function (ok) {
      if (!ok) return
      setSaveState('loading', '正在恢复 ' + hostLabel(state.host) + ' 的默认设置…')
      api('/api/config?host=' + encodeURIComponent(state.host), {
        method: 'POST',
        body: { host: state.host, reset: true }
      }).then(function (payload) {
        applyState(payload.state)
        setSaveState('success', '已恢复 ' + hostLabel(state.host) + ' 的默认设置（记忆未删除）')
        toast('已恢复默认设置；记忆文件未被删除', 'success')
      }, function (error) {
        setSaveState('error', '恢复默认失败：' + errorMessage(error))
        toast('恢复默认失败：' + errorMessage(error), 'error')
      })
    })
  }

  function save() {
    if (state.saving || state.busy || !state.dirty) return
    state.saving = true
    clearFieldErrors()
    if (el.save) {
      el.save.disabled = true
      el.save.textContent = '保存中…'
      el.save.setAttribute('aria-busy', 'true')
    }
    setSaveState('loading', '正在保存到 ' + hostLabel(state.host) + ' 的 config.json…')
    api('/api/config?host=' + encodeURIComponent(state.host), {
      method: 'POST',
      body: buildPayload()
    }).then(function (payload) {
      state.saving = false
      if (el.save) {
        el.save.removeAttribute('aria-busy')
        el.save.textContent = '保存设置'
      }
      applyState(payload.state)
      setSaveState('success', '已保存到 ' + hostLabel(state.host) + ' 的独立 config.json')
      toast('已保存到 ' + hostLabel(state.host) + ' 的独立 config.json', 'success')
    }, function (error) {
      state.saving = false
      if (el.save) {
        el.save.removeAttribute('aria-busy')
        el.save.textContent = '保存设置'
      }
      if (error.status === 400 && error.payload && error.payload.fields) {
        showFieldErrors(error.payload.fields)
      }
      var message = errorMessage(error)
      setSaveState('error', '保存失败：' + message)
      toast('保存失败：' + message, 'error')
      updateDirty(false)
    })
  }

  function beginBusy(button, label) {
    state.busy = true
    if (button) {
      button.setAttribute('data-idle-label', button.textContent)
      button.textContent = label
      button.disabled = true
      button.setAttribute('aria-busy', 'true')
    }
    updateDirty(false)
  }

  function endBusy(button) {
    state.busy = false
    if (button) {
      var idle = button.getAttribute('data-idle-label')
      if (idle) button.textContent = idle
      button.removeAttribute('data-idle-label')
      button.removeAttribute('aria-busy')
    }
    updateDirty(false)
    if (state.data) renderMigration(state.data.migration)
  }

  function actionFailure(step, error) {
    if (error.status === 400 && error.payload && error.payload.fields) {
      showFieldErrors(error.payload.fields)
    }
    var message = errorMessage(error)
    setFeedback(step, message, 'error')
    toast('操作失败：' + message, 'error')
  }

  function preparePlugin() {
    if (state.busy) return
    if (state.dirty) {
      toast('请先保存设置，再准备迁移脚本。', 'error')
      return
    }
    var target = inputFor('pluginMigrationTargetRoot').value.trim()
    if (!target) {
      setFieldError('pluginMigrationTargetRoot', '请填写第一阶段插件数据目标根')
      inputFor('pluginMigrationTargetRoot').focus()
      return
    }
    setFeedback('plugin', '')
    beginBusy(el.pluginPrepare, '正在准备…')
    api('/api/migration/plugin/prepare', {
      method: 'POST',
      body: { host: state.host, targetRoot: target }
    }).then(function (payload) {
      state.expanded.plugin = false
      applyState(payload.state)
      setFeedback('plugin', '已生成第一阶段迁移与回滚脚本；请退出当前宿主后运行脚本。', 'success')
      setSaveState('success', '已准备 ' + hostLabel(state.host) + ' 的第一阶段脚本')
      toast('已准备第一阶段迁移脚本', 'success')
    }, function (error) {
      actionFailure('plugin', error)
    }).then(function () {
      endBusy(el.pluginPrepare)
    })
  }

  function prepareRuntime() {
    if (state.busy) return
    if (state.dirty) {
      toast('请先保存设置，再准备迁移脚本。', 'error')
      return
    }
    var targetInput = inputFor('runtimeMigrationTargetRoot')
    var target = targetInput.value.trim()
    if (!target) {
      setFieldError('runtimeMigrationTargetRoot', '请填写第二阶段运行数据目标根')
      targetInput.focus()
      return
    }
    setFeedback('runtime', '')
    beginBusy(el.runtimePrepare, '正在准备…')
    api('/api/migration/runtime/prepare', {
      method: 'POST',
      body: {
        host: state.host,
        targetRoot: target,
        kimiMigrationTools: inputFor('kimiMigrationTools') ? inputFor('kimiMigrationTools').value.trim() : ''
      }
    }).then(function (payload) {
      state.expanded.runtime = false
      applyState(payload.state)
      setFeedback('runtime', '已生成第二阶段迁移与回滚启动器；请退出当前宿主后按顺序运行。', 'success')
      setSaveState('success', '已准备 ' + hostLabel(state.host) + ' 的第二阶段脚本')
      toast('已准备第二阶段迁移脚本', 'success')
    }, function (error) {
      actionFailure('runtime', error)
    }).then(function () {
      endBusy(el.runtimePrepare)
    })
  }

  function importLegacy() {
    if (state.busy) return
    if (state.dirty) {
      toast('请先保存设置，再导入旧记忆。', 'error')
      return
    }
    var legacy = state.data && state.data.migration.legacy
    if (!legacy || !legacy.source) return
    confirmAction({
      title: '导入旧共享记忆？',
      message: '将一次性导入 ' + legacy.source + ' 到当前宿主（' + hostLabel(state.host) +
        '）。内容不同时会生成冲突报告，不会覆盖现有记忆；active / proposed / rejected 状态保持不变。',
      confirmLabel: '导入',
      danger: Boolean(legacy.conflict)
    }).then(function (ok) {
      if (!ok) return
      beginBusy(el.legacyImport, '正在导入…')
      api('/api/migration/legacy-import', {
        method: 'POST',
        body: { host: state.host }
      }).then(function (payload) {
        applyState(payload.state)
        setSaveState('success', '已导入旧共享记忆到 ' + hostLabel(state.host))
        toast('旧共享记忆已导入', 'success')
      }, function (error) {
        toast('导入失败：' + errorMessage(error), 'error')
        if (error.status === 409 && error.payload && error.payload.state) {
          applyState(error.payload.state)
        }
        if (error.status === 409) {
          setSaveState('error', '旧记忆与当前记忆冲突，已生成报告，未覆盖任何文件。')
        }
      }).then(function () {
        endBusy(el.legacyImport)
      })
    })
  }

  // -------------------------------------------------------------------- copy

  function copyText(value) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(value)
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea')
      area.value = value
      area.setAttribute('readonly', '')
      area.className = 'pwf-visually-hidden'
      document.body.appendChild(area)
      area.select()
      try {
        var ok = document.execCommand('copy')
        document.body.removeChild(area)
        if (ok) resolve()
        else reject(new Error('copy failed'))
      } catch (error) {
        document.body.removeChild(area)
        reject(error)
      }
    })
  }

  function resetCopyButton(button) {
    button.classList.remove('is-copied', 'is-copy-failed')
    button.textContent = '复制'
  }

  function copyPath(key, button) {
    var value = pathValues[key]
    if (!value) {
      toast('这个路径还没有生成，暂时无法复制。', 'error')
      return
    }
    copyText(value).then(function () {
      button.classList.remove('is-copy-failed')
      button.classList.add('is-copied')
      button.textContent = '已复制'
      window.clearTimeout(state.copyTimer)
      state.copyTimer = window.setTimeout(function () { resetCopyButton(button) }, 1600)
    }, function () {
      button.classList.remove('is-copied')
      button.classList.add('is-copy-failed')
      button.textContent = '复制失败'
      toast('无法自动复制，请手动选择路径并复制。', 'error')
      window.setTimeout(function () { resetCopyButton(button) }, 2000)
    })
  }

  // --------------------------------------------------------------------- nav

  function updateNav() {
    var sections = all('[data-section]')
    if (!sections.length) return
    var current = sections[0].getAttribute('data-section')
    var offset = 140
    sections.forEach(function (section) {
      if (section.getBoundingClientRect().top <= offset) {
        current = section.getAttribute('data-section')
      }
    })
    var documentBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8
    if (documentBottom) current = sections[sections.length - 1].getAttribute('data-section')
    all('[data-section-link]').forEach(function (link) {
      if (link.getAttribute('data-section-link') === current) link.setAttribute('aria-current', 'location')
      else link.removeAttribute('aria-current')
    })
  }

  function onScroll() {
    if (state.navTick) return
    if (window.requestAnimationFrame) {
      state.navTick = window.requestAnimationFrame(function () {
        state.navTick = 0
        updateNav()
      })
    } else {
      state.navTick = window.setTimeout(function () {
        state.navTick = 0
        updateNav()
      }, 80)
    }
  }

  // -------------------------------------------------------------------- wiring

  function cacheElements() {
    el = {
      loading: byId('pwf-loading'),
      error: byId('pwf-error'),
      errorMessage: byId('pwf-error-message'),
      retry: byId('pwf-retry'),
      main: byId('pwf-main'),
      version: byId('pwf-version'),
      chipHost: byId('pwf-chip-host'),
      hostSummary: byId('pwf-host-summary'),
      dataNotices: byId('pwf-data-notices'),
      policyHost: byId('pwf-policy-host'),
      savebarHost: byId('pwf-savebar-host'),
      saveState: byId('pwf-save-state'),
      save: byId('pwf-save'),
      reload: byId('pwf-reload'),
      reset: byId('pwf-reset'),
      pluginBadge: byId('pwf-plugin-badge'),
      pluginReason: byId('pwf-plugin-reason'),
      pluginExpand: byId('pwf-plugin-expand'),
      pluginTargetWrap: byId('pwf-plugin-target-wrap'),
      pluginCancel: byId('pwf-plugin-cancel'),
      pluginPrepare: byId('pwf-plugin-prepare'),
      pluginFeedback: byId('pwf-plugin-feedback'),
      pluginTargetPreview: byId('pwf-plugin-target-preview'),
      runtimeBadge: byId('pwf-runtime-badge'),
      runtimeReason: byId('pwf-runtime-reason'),
      runtimeExpand: byId('pwf-runtime-expand'),
      runtimeTargetWrap: byId('pwf-runtime-target-wrap'),
      runtimeCancel: byId('pwf-runtime-cancel'),
      runtimePrepare: byId('pwf-runtime-prepare'),
      runtimeFeedback: byId('pwf-runtime-feedback'),
      runtimeTargetPreview: byId('pwf-runtime-target-preview'),
      legacy: byId('pwf-legacy'),
      legacyDesc: byId('pwf-legacy-desc'),
      legacyImport: byId('pwf-legacy-import'),
      confirm: byId('pwf-confirm'),
      confirmTitle: byId('pwf-confirm-title'),
      confirmText: byId('pwf-confirm-text'),
      confirmOk: byId('pwf-confirm-ok'),
      confirmCancel: byId('pwf-confirm-cancel'),
      toast: byId('pwf-toast')
    }
  }

  function wire() {
    all('[data-field-input]').forEach(function (node) {
      node.addEventListener('input', onDraftChange)
      node.addEventListener('change', onDraftChange)
    })
    all('[data-switch]').forEach(function (node) {
      node.addEventListener('click', function () { toggleSwitch(node) })
    })
    all('.pwf-host-tab').forEach(function (button) {
      button.addEventListener('click', function () {
        switchHost(button.getAttribute('data-host'))
      })
    })
    all('[data-copy-path]').forEach(function (button) {
      button.addEventListener('click', function () {
        copyPath(button.getAttribute('data-copy-path'), button)
      })
    })
    all('[data-section-link]').forEach(function (link) {
      link.addEventListener('click', function () {
        all('[data-section-link]').forEach(function (other) { other.removeAttribute('aria-current') })
        link.setAttribute('aria-current', 'location')
      })
    })
    el.save.addEventListener('click', save)
    el.reload.addEventListener('click', reload)
    el.reset.addEventListener('click', resetDefaults)
    el.retry.addEventListener('click', function () { load(state.host || readStartHost(), 'switched') })
    el.pluginPrepare.addEventListener('click', preparePlugin)
    el.runtimePrepare.addEventListener('click', prepareRuntime)
    el.pluginExpand.addEventListener('click', function () {
      state.expanded.plugin = true
      if (state.data) renderMigration(state.data.migration)
    })
    el.pluginCancel.addEventListener('click', function () {
      state.expanded.plugin = false
      if (state.data) renderMigration(state.data.migration)
    })
    el.runtimeExpand.addEventListener('click', function () {
      state.expanded.runtime = true
      if (state.data) renderMigration(state.data.migration)
    })
    el.runtimeCancel.addEventListener('click', function () {
      state.expanded.runtime = false
      if (state.data) renderMigration(state.data.migration)
    })
    el.legacyImport.addEventListener('click', importLegacy)
    el.confirmOk.addEventListener('click', function () {
      el.confirm.returnValue = 'confirm'
      el.confirm.close()
    })
    el.confirmCancel.addEventListener('click', function () {
      el.confirm.returnValue = 'cancel'
      el.confirm.close()
    })
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    window.addEventListener('beforeunload', function (event) {
      if (!state.dirty) return
      event.preventDefault()
      event.returnValue = ''
      return ''
    })
  }

  function init() {
    cacheElements()
    state.token = readToken()
    wire()
    if (!state.token) {
      showInitialError('缺少访问令牌。请从命令行运行 settings 命令，并用它输出的完整 URL 打开本页。')
      return
    }
    state.host = readStartHost()
    load(state.host, 'initial')
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
