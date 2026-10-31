window.__ModuleLoader__.load({
  id: '@local/programmer-workflow',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useCallback, useEffect, useState } = React

    const ENTRY_ID = 'programmer-workflow'

    const DEFAULTS = {
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
      migrationTarget: '',
      migrationActionEnabled: true,
      kimiMigrationTarget: '',
      kimiMigrationTools: '',
      planFormat: 'md',
      pluginMigrationTargetRoot: '',
      runtimeMigrationTargetRoot: '',
    }

    const HOST_TABS = [
      { id: 'dsh', label: 'DeepSeek Harness' },
      { id: 'kimi', label: 'Kimi Code' },
      { id: 'codebuddy', label: 'CodeBuddy' },
    ]

    const FALLBACK_MODES = [
      { id: 'plan', label: 'Plan', description: '先生成计划，用户批准后执行。' },
      { id: 'full-authority', label: 'Full authority', description: '普通命令直接执行；破坏性操作仍需确认。' },
    ]

    function normalizeDraft(value) {
      const source = value && typeof value === 'object' ? value : {}
      const next = { ...DEFAULTS, ...source }
      next.workflowMode = ['plan', 'full-authority'].includes(next.workflowMode) ? next.workflowMode : 'plan'
      next.planFormat = next.planFormat === 'html' ? 'html' : 'md'
      return next
    }

    function Field(props) {
      return h('div', { className: 'pwf-field' }, [
        h('label', { key: 'l', htmlFor: props.id }, props.label),
        props.children,
        props.hint ? h('p', { key: 'h', className: 'pwf-hint' }, props.hint) : null,
      ])
    }

    function PathRow(props) {
      return h('div', { className: 'pwf-pathrow' }, [
        h('span', { key: 'l', className: 'pwf-pathlabel' }, props.label),
        h('code', { key: 'v', className: 'pwf-pathval' + (props.value ? '' : ' is-empty'), title: props.value || '' }, props.value || props.empty || '未解析'),
        props.badge ? h('span', { key: 'b', className: 'pwf-inline-badge' }, props.badge) : null,
        props.value ? h('button', { key: 'c', type: 'button', className: 'pwf-copy', onClick: props.onCopy }, '复制') : null,
      ])
    }

    function Switch(props) {
      return h('button', {
        type: 'button',
        role: 'switch',
        className: 'pwf-switch' + (props.checked ? ' is-on' : ''),
        'aria-checked': props.checked ? 'true' : 'false',
        'aria-label': props.label,
        disabled: props.disabled,
        onClick: function () { props.onChange(!props.checked) },
      }, h('span', { className: 'pwf-knob' }))
    }

    function modeLabel(modes, id) {
      const found = (modes || []).find(function (mode) { return mode.id === id })
      return found ? found.label : (id || 'plan')
    }

    function coverageLabel(coverage) {
      return ({
        covered: '路径位于宿主默认根；是否已完成移动见下方阶段状态',
        imported: '已从旧共享/旧版数据导入',
        external: '外部 override，未由默认迁移覆盖',
        'legacy-pending': '发现旧版/共享记忆，尚未导入',
        'legacy-conflict': '旧版/共享记忆与当前记忆冲突',
      })[coverage] || coverage || '未解析'
    }

    const MODE_OPTION_LABELS = {
      plan: 'Plan · 审核后执行',
      'full-authority': 'Full authority · 普通任务直接执行',
    }
    const MODE_HELP = 'Plan 会先让你确认计划再执行；Full authority 会直接处理普通任务，危险操作仍会拦截。'

    function migrationLabel(value) {
      return ({
        'not-started': '未开始',
        prepared: '已准备，尚未执行',
        completed: '已完成',
        blocked: '待完成第一阶段',
        unsupported: '尚未适配',
        unavailable: '当前不可用',
        failed: '失败',
        external: '已有迁移',
        stale: '需要检查',
        'rolled-back': '已回滚',
      })[value] || value || '未开始'
    }

    function migrationTone(value) {
      if (value === 'completed') return 'is-done'
      if (value === 'failed') return 'is-error'
      if (value === 'prepared' || value === 'blocked' || value === 'external' || value === 'stale' || value === 'rolled-back') return 'is-warn'
      return 'is-idle'
    }

    function pluginInventoryText(inventory) {
      if (!inventory || !inventory.counts) return ''
      const counts = inventory.counts
      const parts = ['生效 ' + (counts.active || 0) + ' 条', '待审核 ' + (counts.proposed || 0) + ' 条']
      if (counts.rejected) parts.push('已拒绝 ' + counts.rejected + ' 条')
      return '插件清单：' + parts.join('，')
    }

    function SettingsPage() {
      const [host, setHost] = useState('dsh')
      const [config, setConfig] = useState(null)
      const [status, setStatus] = useState(null)
      const [draft, setDraft] = useState(normalizeDraft(DEFAULTS))
      const [busy, setBusy] = useState(false)
      const [message, setMessage] = useState('')
      const [error, setError] = useState('')
      const [prepared, setPrepared] = useState(null)
      // "Move to a new address" is opt-in: a verified migration must not show a
      // prepare button until the user explicitly asks for another move.
      const [reprepare, setReprepare] = useState(false)
      const [reprepareRuntime, setReprepareRuntime] = useState(false)

      const load = useCallback(async function (targetHost) {
        setBusy(true)
        setError('')
        try {
          const response = await fetch('/programmer-workflow/config?host=' + encodeURIComponent(targetHost))
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.error || '读取配置失败')
          setConfig(data.config)
          setDraft(normalizeDraft(data.config))
          setStatus(data.status)
          setPrepared(null)
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally {
          setBusy(false)
        }
      }, [])

      useEffect(function () { load(host) }, [host, load])

      if (!config || !status) {
        return h('div', { className: 'pwf-page' }, [
          h('header', { key: 'header', className: 'pwf-header' }, [
            h('div', { key: 'title', className: 'pwf-titleblock' }, [
              h('h1', { key: 'h' }, '程序员工作流'),
              h('p', { key: 's', className: 'pwf-tagline' }, status ? '按宿主独立的插件数据、工作流与迁移设置' : '正在读取配置'),
            ]),
            status ? h('span', { key: 'v', className: 'pwf-version' }, 'v' + (status.version || '')) : null,
          ]),
          h('div', { key: 'hosts', className: 'pwf-hostbar' }, [
            ...HOST_TABS.map(function (tab) {
              return h('button', { key: tab.id, type: 'button', className: 'pwf-hosttab' + (host === tab.id ? ' is-active' : ''), onClick: function () { setHost(tab.id) } }, tab.label)
            }),
          ]),
          error ? h('div', { key: 'e', className: 'pwf-note pwf-error' }, error) : h('div', { key: 'l', className: 'pwf-note' }, '正在读取该宿主的独立配置…'),
        ])
      }

      const hostInfo = (status.hosts && status.hosts[host]) || {}
      const pluginData = status.pluginData || {}
      const pluginMigration = status.pluginMigration || {}
      const runtimeMigration = status.runtimeMigration || {}
      const modes = status.workflowModes && status.workflowModes.length ? status.workflowModes : FALLBACK_MODES
      const stage1Completed = !!pluginMigration.completed
      const stage1Pending = !stage1Completed && (pluginMigration.prepared === true || pluginMigration.status === 'prepared')
      const stage2Completed = !!runtimeMigration.stage2Completed
      const stage2Pending = !stage2Completed && runtimeMigration.stage2Status === 'prepared'
      const stage2RolledBack = runtimeMigration.stage2Status === 'rolled-back'
      // `ready === false` means the Host found no CLI for this host (for example
      // CodeBuddy without its skill installed); `undefined` keeps older payloads
      // working.
      const stage1CliMissing = pluginMigration.ready === false

      function value(key) { return draft[key] }
      function setValue(key, next) { setDraft(function (previous) { return { ...previous, [key]: next } }) }

      async function copyText(text) {
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(text)
          else {
            const area = document.createElement('textarea')
            area.value = text
            document.body.appendChild(area)
            area.select()
            document.execCommand('copy')
            area.remove()
          }
          setMessage('已复制')
        } catch { setError('复制失败，请手动选择文本') }
      }

      async function save() {
        setBusy(true)
        setError('')
        try {
          const response = await fetch('/programmer-workflow/config?host=' + encodeURIComponent(host), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...draft, host }),
          })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.error || '保存失败')
          setConfig(data.config)
          setDraft(normalizeDraft(data.config))
          setStatus(data.status)
          setMessage('已保存到 ' + host + ' 的独立 config.json')
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally { setBusy(false) }
      }

      async function resetConfig() {
        if (!window.confirm('恢复默认只重置「' + (hostInfo.label || host) + '」这一套配置；其他宿主和记忆数据都不会被改动。继续？')) return
        setBusy(true); setError(''); setMessage('')
        try {
          const response = await fetch('/programmer-workflow/config?host=' + encodeURIComponent(host), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, reset: true }),
          })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.error || '恢复默认失败')
          setConfig(data.config)
          setDraft(normalizeDraft(data.config))
          setStatus(data.status)
          setMessage('已恢复「' + host + '」的默认配置；记忆数据未改动。')
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally { setBusy(false) }
      }

      async function preparePlugin() {
        if (pluginMigration.completed) {
          const ok = window.confirm('将把插件数据从当前位置迁移到新地址：\n' + (pluginMigration.actualTarget || '') + '\n\n会重新预检、备份，并从当前位置读取最新数据；脚本不会自动执行。继续？')
          if (!ok) return
        }
        setBusy(true); setError(''); setMessage('')
        try {
          const response = await fetch('/programmer-workflow/plugin-migration/prepare', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, targetRoot: draft.pluginMigrationTargetRoot }),
          })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.error || '准备失败')
          setPrepared(data)
          setStatus(data.status)
          setMessage('第一阶段脚本已准备：' + data.launcher)
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally { setBusy(false) }
      }

      async function prepareRuntime() {
        if (runtimeMigration.stage2Completed) {
          const ok = window.confirm('运行数据已在：\n' + (runtimeMigration.actualLocation || '') + '\n\n迁移到新地址会重新预检并生成新脚本，不会自动执行。继续？')
          if (!ok) return
        }
        setBusy(true); setError(''); setMessage('')
        try {
          const response = await fetch('/programmer-workflow/migration/prepare', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, targetRoot: draft.runtimeMigrationTargetRoot }),
          })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.error || '准备失败')
          setPrepared(data)
          setStatus(data.status)
          setMessage('第二阶段脚本已准备：' + data.launcher)
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally { setBusy(false) }
      }

      async function importLegacy() {
        setBusy(true); setError(''); setMessage('')
        try {
          const response = await fetch('/programmer-workflow/plugin-migration/legacy-import', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host }),
          })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.report ? ('冲突报告：' + data.report) : (data.error || data.status || '旧数据导入失败'))
          setStatus(data.status)
          setMessage(data.status === 'same' ? '旧数据与当前记忆一致，无需导入。' : '旧数据已一次性导入到当前宿主；后续不再同步。')
        } catch (exc) {
          setError(String(exc && exc.message ? exc.message : exc))
        } finally { setBusy(false) }
      }

      const stage1Status = stage1Completed
        ? 'completed'
        : (stage1Pending ? 'prepared' : (pluginMigration.stale ? 'stale' : (pluginMigration.external ? 'external' : (pluginMigration.status || 'not-started'))))
      const stage2Status = stage2Completed
        ? 'completed'
        : (runtimeMigration.stage2Status || runtimeMigration.status || 'blocked')
      const stage2Capability = !runtimeMigration.supported
        ? '尚未适配：当前宿主只支持插件数据迁移。'
        : (!stage1Completed
          ? '等待第一阶段完成。'
          : (!runtimeMigration.adapterReady
            ? '需要额外工具：' + (runtimeMigration.reason || '迁移工具未配置。')
            : '已适配，但尚未在真实数据上执行验证。'))
      const stage1Actual = stage1Completed && pluginMigration.actualTarget ? pluginMigration.actualTarget : ''
      const stage2Actual = stage2Completed && runtimeMigration.actualLocation ? runtimeMigration.actualLocation : ''

      return h('div', { className: 'pwf-page' }, [
        h('header', { key: 'header', className: 'pwf-header' }, [
          h('div', { key: 'title', className: 'pwf-titleblock' }, [
            h('h1', { key: 'h' }, '程序员工作流'),
            h('p', { key: 's', className: 'pwf-tagline' }, '按宿主独立的插件数据、工作流与迁移设置'),
          ]),
          h('span', { key: 'v', className: 'pwf-version' }, 'v' + (status.version || '')),
        ]),

        h('div', { key: 'hosts', className: 'pwf-hostbar' }, [
          ...HOST_TABS.map(function (tab) {
            return h('button', {
              key: tab.id, type: 'button',
              className: 'pwf-hosttab' + (host === tab.id ? ' is-active' : ''),
              onClick: function () { setHost(tab.id) },
            }, tab.label)
          }),
        ]),
        h('div', { key: 'hostnote', className: 'pwf-hostsummary' }, [
          h('strong', { key: 's' }, hostInfo.label || host),
          h('span', { key: 'b', className: 'pwf-inline-badge' + (hostInfo.installed === true ? ' is-done' : '') }, hostInfo.installed === true ? '已安装' : hostInfo.installed === false ? '未安装' : '项目级'),
          h('span', { key: 'p', className: 'pwf-meta-item' }, ['Plan 文件 ', h('code', { key: 'f', className: 'pwf-inline-code' }, hostInfo.planFile || ('plan.' + value('planFormat')))]),
          h('button', { key: 'c', type: 'button', className: 'pwf-copy', onClick: function () { copyText(hostInfo.skillPath || status.paths.memory) } }, '复制 Skill 路径'),
        ]),
        h('p', { key: 'policy', className: 'pwf-policyline' }, '工作流模式只影响插件审核策略，不改变宿主权限。'),

        h('section', { key: 'data', className: 'pwf-card' }, [
          h('h2', null, '插件数据位置'),
          h('p', { className: 'pwf-desc' }, '每个宿主使用独立的数据目录；这里显示当前宿主实际使用的路径。'),
          h('div', { className: 'pwf-paths' }, [
            h(PathRow, { key: 'root', label: '数据根', value: pluginData.globalRoot, onCopy: function () { copyText(pluginData.globalRoot || '') } }),
            h(PathRow, { key: 'realroot', label: '实际落盘', value: pluginData.realGlobalRoot, badge: !pluginData.insideHostHome ? '外部' : (pluginData.resolvedOutsideHostHome ? '联接外盘' : '宿主目录内'), onCopy: function () { copyText(pluginData.realGlobalRoot || '') } }),
            h(PathRow, { key: 'memory', label: '插件记忆', value: pluginData.memoryRoot, onCopy: function () { copyText(pluginData.memoryRoot || '') } }),
            h(PathRow, { key: 'config', label: '配置文件', value: pluginData.configPath, onCopy: function () { copyText(pluginData.configPath || '') } }),
          ]),
          pluginData.externallyOverridden ? h('p', { key: 'ext', className: 'pwf-note pwf-warn' }, '检测到外部路径设置（环境变量覆盖）。这个位置不会被默认迁移自动搬动，请单独备份或导出。') : null,
          pluginData.legacy && pluginData.legacy.conflict ? h('p', { key: 'lc', className: 'pwf-note pwf-warn' }, '旧版共享记忆和当前记忆内容不同，没有覆盖也没有合并；两份都保留，请手工决定。') : null,
          pluginData.legacy && !pluginData.legacy.conflict && pluginData.legacy.hasMemory && !pluginData.legacy.imported ? h('p', { key: 'lp', className: 'pwf-note' }, '发现旧版共享记忆，可以一次性导入；不会自动把待审核条目提升为生效。') : null,
          h('p', { key: 'ws', className: 'pwf-help' }, '项目记忆保存在当前项目中，不随全局数据迁移。'),
        ]),

        h('section', { key: 'workspace', className: 'pwf-card' }, [
          h('h2', null, '工作区输出'),
          h('p', { className: 'pwf-desc' }, '这些文件保存在当前项目中，只需填写项目内的相对路径。'),
          h('div', { className: 'pwf-grid is-two' }, [
            h(Field, { key: 'ws', id: 'pwf-ws', label: '记忆与扫描目录', hint: '默认 .programmer-workflow' }, h('input', { id: 'pwf-ws', className: 'pwf-input', value: value('workspaceDataDir'), disabled: busy, onChange: function (e) { setValue('workspaceDataDir', e.target.value) } })),
            h(Field, { key: 'dbg', id: 'pwf-dbg', label: '调试日志目录', hint: '默认 debug-logs' }, h('input', { id: 'pwf-dbg', className: 'pwf-input', value: value('debugLogDir'), disabled: busy, onChange: function (e) { setValue('debugLogDir', e.target.value) } })),
            h(Field, { key: 'docs', id: 'pwf-docs', label: '工程文档目录', hint: '工程文档默认保存到 docs' }, h('input', { id: 'pwf-docs', className: 'pwf-input', value: value('docsDir'), disabled: busy, onChange: function (e) { setValue('docsDir', e.target.value) } })),
            h(Field, { key: 'proto', id: 'pwf-proto', label: '界面原型文件名', hint: '界面原型默认保存为 Prototype.html' }, h('input', { id: 'pwf-proto', className: 'pwf-input', value: value('prototypeFile'), disabled: busy, onChange: function (e) { setValue('prototypeFile', e.target.value) } })),
          ]),
        ]),

        h('section', { key: 'memory', className: 'pwf-card' }, [
          h('h2', null, '记忆'),
          h('p', { className: 'pwf-desc' }, '这两个开关只控制新会话开始时是否读取记忆；已有内容不会被删除。'),
          h('div', { className: 'pwf-stack' }, [
            h('div', { className: 'pwf-row', key: 'u' }, [
              h('div', { key: 't', className: 'pwf-rowtext' }, [h('b', null, '启动时加载全局记忆'), h('span', null, '新会话开始时，读取这个宿主保存的偏好和约定。')]),
              h(Switch, { key: 's', label: '启动时加载全局记忆', checked: !!value('userMemoryEnabled'), disabled: busy, onChange: function (v) { setValue('userMemoryEnabled', v) } }),
            ]),
            h('div', { className: 'pwf-row', key: 'w' }, [
              h('div', { key: 't', className: 'pwf-rowtext' }, [h('b', null, '启动时加载工作区记忆'), h('span', null, '新会话开始时，读取当前项目的记忆，不影响其他项目。')]),
              h(Switch, { key: 's', label: '启动时加载工作区记忆', checked: !!value('workspaceMemoryEnabled'), disabled: busy, onChange: function (v) { setValue('workspaceMemoryEnabled', v) } }),
            ]),
          ]),
          h('p', { className: 'pwf-help' }, '全局记忆只属于当前宿主，其他宿主不会读取。'),
        ]),

        h('section', { key: 'workflow', className: 'pwf-card' }, [
          h('h2', null, '工作流与调试'),
          h('div', { className: 'pwf-grid is-two' }, [
            h(Field, { key: 'mode', id: 'pwf-mode', label: '工作流模式', hint: MODE_HELP }, h('select', {
              id: 'pwf-mode', className: 'pwf-input', value: value('workflowMode'), disabled: busy,
              onChange: function (e) { setValue('workflowMode', e.target.value) },
            }, modes.map(function (mode) { return h('option', { key: mode.id, value: mode.id }, MODE_OPTION_LABELS[mode.id] || mode.label) }))),
            h(Field, { key: 'plan', id: 'pwf-planfmt', label: 'Plan 文件格式', hint: '选择计划用 Markdown 文档还是网页展示，只影响查看方式。' }, h('select', {
              id: 'pwf-planfmt', className: 'pwf-input', value: value('planFormat'), disabled: busy,
              onChange: function (e) { setValue('planFormat', e.target.value) },
            }, [h('option', { key: 'md', value: 'md' }, 'Markdown · plan.md'), h('option', { key: 'html', value: 'html' }, 'HTML · plan.html')])),
            h(Field, { key: 'sat', id: 'pwf-sat', label: '未满意阈值', hint: '连续几次没有达到预期后，停止重复尝试并换一种处理方式。' }, h('input', { id: 'pwf-sat', type: 'number', min: 1, max: 10, className: 'pwf-input', value: value('satisfactionThreshold'), disabled: busy, onChange: function (e) { setValue('satisfactionThreshold', Number(e.target.value)) } })),
            h(Field, { key: 'bug', id: 'pwf-bug', label: 'Bug 失败阈值', hint: '连续几次修复失败后，开始收集日志并调整排查方向。' }, h('input', { id: 'pwf-bug', type: 'number', min: 1, max: 10, className: 'pwf-input', value: value('bugfixThreshold'), disabled: busy, onChange: function (e) { setValue('bugfixThreshold', Number(e.target.value)) } })),
            h(Field, { key: 'ret', id: 'pwf-ret', label: '全局临时文件保留', hint: '设置全局临时文件的保留天数，不会删除记忆、项目日志或迁移备份。' }, h('input', { id: 'pwf-ret', type: 'number', min: 1, max: 365, className: 'pwf-input', value: value('retentionDays'), disabled: busy, onChange: function (e) { setValue('retentionDays', Number(e.target.value)) } })),
            h(Field, { key: 'lang', id: 'pwf-lang', label: '文档默认语言', hint: '生成文档和界面原型时使用的默认语言。' }, h('select', { id: 'pwf-lang', className: 'pwf-input', value: value('language'), disabled: busy, onChange: function (e) { setValue('language', e.target.value) } }, [h('option', { key: 'zh', value: 'zh-CN' }, '中文（zh-CN）'), h('option', { key: 'en', value: 'en' }, 'English')])),
          ]),
          h('div', { className: 'pwf-row' }, [
            h('div', { key: 't', className: 'pwf-rowtext' }, [h('b', null, '纯开发/无硬件时直接加日志'), h('span', null, '项目不需要连接硬件时，允许 Agent 直接添加少量排查日志。')]),
            h(Switch, { key: 's', label: '纯开发/无硬件时直接加日志', checked: !!value('devOnlyAutoInstrument'), disabled: busy, onChange: function (v) { setValue('devOnlyAutoInstrument', v) } }),
          ]),
          h('p', { className: 'pwf-help' }, '当前模式：' + modeLabel(modes, value('workflowMode')) + '。普通运行是否需要逐步确认由这里的模式决定；危险命令在任何模式下都会拦截。'),
        ]),

        h('section', { key: 'docs', className: 'pwf-card' }, [
          h('h2', null, '文档与界面原型'),
          h('div', { className: 'pwf-row' }, [
            h('div', { className: 'pwf-rowtext', key: 'd' }, [h('b', null, '工程文档'), h('span', null, '根据项目代码生成架构和功能网页，方便查看和评审。')]),
            h(Switch, { key: 's', label: '生成工程文档', checked: !!value('docsEnabled'), disabled: busy, onChange: function (v) { setValue('docsEnabled', v) } }),
          ]),
          h('div', { className: 'pwf-row' }, [
            h('div', { className: 'pwf-rowtext', key: 'p' }, [h('b', null, '生成 UI 界面原型'), h('span', null, '设计或调整界面时，先生成可预览的 Prototype.html，方便比较方案、查看不同屏幕尺寸并标注修改意见；不会直接改动项目界面。')]),
            h(Switch, { key: 's', label: '生成 UI 界面原型', checked: !!value('prototypeEnabled'), disabled: busy, onChange: function (v) { setValue('prototypeEnabled', v) } }),
          ]),
          h('p', { className: 'pwf-help' }, '原型用于界面设计与评审，不会生成或修改项目的最终界面代码。'),
        ]),

        h('section', { key: 'migration', className: 'pwf-card' }, [
          h('h2', null, '数据迁移（两个阶段）'),
          h('p', { className: 'pwf-desc' }, '两个阶段按顺序进行。设置页只准备脚本，不会在 DSH 运行期间自动迁移。'),
          h('p', { key: 'scope', className: 'pwf-help' }, [
            '当前宿主的真实适配范围见 ',
            h('a', { key: 'doc', href: '/programmer-workflow/migration', target: '_blank', rel: 'noreferrer' }, '迁移教程与支持矩阵'),
            '，或 dsh-plugin/README.md。',
          ]),
          h('div', { className: 'pwf-row' }, [
            h('div', { className: 'pwf-rowtext', key: 'a' }, [h('b', null, '允许从设置页准备迁移脚本'), h('span', null, '不会在 DSH 运行期间自动迁移；脚本由你在退出程序后运行。')]),
            h(Switch, { key: 's', label: '允许准备迁移脚本', checked: !!value('migrationActionEnabled'), disabled: busy, onChange: function (v) { setValue('migrationActionEnabled', v) } }),
          ]),

          h('div', { key: 'stage1', className: 'pwf-stage' }, [
            h('div', { key: 'head', className: 'pwf-stage-head' }, [
              h('h3', { key: 'h' }, '第一步：插件数据'),
              h('span', { key: 'b', className: 'pwf-status-badge ' + migrationTone(stage1Status) }, migrationLabel(stage1Status)),
            ]),
            h('p', { key: 'd', className: 'pwf-stage-desc' }, '迁移这个宿主保存的插件记忆、配置和运行产物，不移动编辑器本身的数据。'),
            h('p', { key: 's', className: 'pwf-stage-status' }, stage1Completed
              ? '插件数据已迁移，无需再次操作'
              : pluginMigration.stale
                ? '状态文件显示已完成，但源目录不是指向该目标的链接，请检查后再操作。'
                : pluginMigration.external
                  ? '检测到已有迁移链接，但不是本插件记录。'
                  : stage1Pending
                    ? '脚本已生成，尚未执行。'
                    : '尚未迁移；完成后才能使用第二阶段。'),
            h('div', { key: 'paths', className: 'pwf-paths' }, [
              h(PathRow, { key: 's', label: '源目录', value: pluginMigration.source || pluginData.globalRoot, onCopy: function () { copyText(pluginMigration.source || pluginData.globalRoot || '') } }),
              h(PathRow, { key: 't', label: '目标', value: (stage1Completed ? pluginMigration.actualTarget : pluginMigration.target) || '', empty: '待填写目标根', onCopy: function () { copyText((stage1Completed ? pluginMigration.actualTarget : pluginMigration.target) || '') } }),
              h(PathRow, { key: 'b', label: '独立备份', value: pluginMigration.backup || '尚未生成', onCopy: function () { copyText(pluginMigration.backup || '') } }),
            ]),
            stage1Completed ? h('p', { key: 'done', className: 'pwf-note pwf-policy' }, '当前实际落盘位置：' + (stage1Actual || '未知') + '（' + (pluginMigration.verified ? '本插件已验证' : '已有迁移，未记为本插件验证') + (pluginMigration.actualTargetExists ? '，目标可读' : '，目标不可读') + (pluginMigration.relocated ? '，不在系统盘 ' + (pluginMigration.systemDrive || '') : '') + '）。') : null,
            !stage1Completed && pluginMigration.external ? h('p', { key: 'ext', className: 'pwf-note pwf-warn' }, '检测到已有迁移链接：' + (pluginMigration.actualTarget || '未知') + '。当前状态记录没有把它验证为本插件完成的迁移，因此不会标记为已完成，也不会覆盖它。') : null,
            !stage1Completed && pluginMigration.stale ? h('p', { key: 'stale', className: 'pwf-note pwf-warn' }, '状态文件记录为已完成，但当前源目录不是指向记录目标的链接（可能被手动改动）。本页不会把它当作已验证，请检查链接后再操作。') : null,
            stage1Pending ? h('p', { key: 'pending', className: 'pwf-note' }, ['退出 DSH 后运行脚本：', h('code', { key: 'c', className: 'pwf-code' }, (pluginMigration.pending && pluginMigration.pending.launcher) || (prepared && prepared.launcher) || '（见 .programmer-workflow-migration）')]) : null,

            stage1Completed && !reprepare
              ? h('div', { key: 'actions-done', className: 'pwf-actions' }, [
                h('button', { key: 'new', type: 'button', className: 'pwf-btn pwf-btn-quiet', disabled: busy || !value('migrationActionEnabled') || stage1CliMissing, onClick: function () { setReprepare(true) } }, '迁移到新地址'),
              ])
              : h('div', { key: 'actions-prepare', className: 'pwf-actions-block' }, [
                stage1Completed ? h('p', { key: 'hint', className: 'pwf-help' }, '迁移到新地址会重新预检空目录、路径重叠和记忆完整性并备份，从当前实际位置复制最新数据；不会自动执行。') : null,
                h('div', { key: 'grid', className: 'pwf-grid' }, [
                  h(Field, { key: 'pr', id: 'pwf-plugin-root', label: '插件数据目标根', hint: '目标会拼成 <根>/' + (hostInfo.dataDir || '.dsh') + '/programmer-workflow' }, h('input', { id: 'pwf-plugin-root', className: 'pwf-input', value: value('pluginMigrationTargetRoot'), disabled: busy, onChange: function (e) { setValue('pluginMigrationTargetRoot', e.target.value) }, placeholder: '例如 D:\\AgentData' })),
                ]),
                h('div', { key: 'row', className: 'pwf-actions' }, [
                  h('button', { key: 'go', type: 'button', className: 'pwf-btn pwf-btn-primary', disabled: busy || !value('migrationActionEnabled') || stage1CliMissing, onClick: preparePlugin }, stage1Completed ? '准备迁移到新地址的脚本' : '准备第一阶段脚本'),
                  stage1Completed ? h('button', { key: 'cancel', type: 'button', className: 'pwf-btn', disabled: busy, onClick: function () { setReprepare(false) } }, '取消') : null,
                  prepared && prepared.launcher ? h('code', { key: 'p', className: 'pwf-code' }, prepared.launcher) : null,
                ]),
              ]),
            stage1CliMissing ? h('p', { key: 'cli', className: 'pwf-note pwf-warn' }, pluginMigration.unavailableReason || '该宿主尚未安装可用的 Skill CLI，第一阶段迁移暂不可用。') : null,
            pluginData.inventory ? h('p', { key: 'inv', className: 'pwf-help' }, pluginInventoryText(pluginData.inventory)) : null,
            pluginData.legacy && pluginData.legacy.hasMemory ? h('div', { key: 'legacy', className: 'pwf-note pwf-warn' }, [
              h('span', { key: 't' }, '旧版/共享记忆：' + (pluginData.legacy.conflict ? '存在冲突，未覆盖、未自动合并。' : pluginData.legacy.imported ? '已标记导入。' : '尚未导入，可单独做一次性导入。')),
              !pluginData.legacy.conflict && !pluginData.legacy.imported
                ? h('button', { key: 'i', type: 'button', className: 'pwf-btn', disabled: busy, onClick: importLegacy }, '一次性导入到当前宿主')
                : null,
            ]) : null,
          ]),

          h('div', { key: 'stage2', className: 'pwf-stage' }, [
            h('div', { key: 'head', className: 'pwf-stage-head' }, [
              h('h3', { key: 'h' }, '第二步：编辑器运行数据'),
              h('span', { key: 'b', className: 'pwf-status-badge ' + migrationTone(stage2Status) }, migrationLabel(stage2Status)),
            ]),
            h('p', { key: 'd', className: 'pwf-stage-desc' }, '迁移编辑器自己的会话、设置和缓存。只有当前宿主已适配，并且第一阶段完成后才能使用。'),
            h('p', { key: 'cap', className: 'pwf-stage-cap' }, '能力：' + stage2Capability),
            h('p', { key: 's', className: 'pwf-stage-status' }, stage2Completed
              ? '编辑器运行数据已迁移，无需再次操作'
              : stage2Pending
                ? '脚本已生成，尚未执行。'
                : stage2RolledBack
                  ? '已回滚到迁移前状态。'
                  : runtimeMigration.supported
                    ? (stage1Completed ? (runtimeMigration.adapterReady ? '可以准备脚本；执行前请先退出编辑器。' : '当前不可用。') : '请先完成第一阶段。')
                    : '当前宿主尚未适配运行数据迁移。'),
            stage2Completed ? h('p', { key: 'done2', className: 'pwf-note pwf-policy' }, '当前运行数据实际落盘位置：' + (stage2Actual || '未知') + '（' + (runtimeMigration.stage2Verified ? '本插件已验证' : '已有迁移，未记为本插件验证') + (runtimeMigration.actualLocationExists ? '，目标可读' : '，目标不可读') + (runtimeMigration.stage2Relocated ? '，不在系统盘 ' + (runtimeMigration.systemDrive || '') : '') + (runtimeMigration.appDataRelocated ? '；桌面端缓存也已映射' : '') + '）。') : null,
            stage2Pending && stage2Actual ? h('p', { key: 'pending2', className: 'pwf-note' }, '新地址脚本已生成；在运行它之前，当前仍使用：' + stage2Actual) : null,
            runtimeMigration.reason && !stage2Completed ? h('p', { key: 'reason2', className: 'pwf-note' }, runtimeMigration.reason) : null,

            stage2Completed && !reprepareRuntime
              ? h('div', { key: 'actions2-done', className: 'pwf-actions' }, [
                h('button', { key: 'new2', type: 'button', className: 'pwf-btn pwf-btn-quiet', disabled: busy || !value('migrationActionEnabled') || !runtimeMigration.adapterReady, onClick: function () { setReprepareRuntime(true) } }, '迁移到新地址'),
              ])
              : h('div', { key: 'actions2-prepare', className: 'pwf-actions-block' }, [
                h('div', { key: 'grid2', className: 'pwf-grid' }, [
                  h(Field, { key: 'rr', id: 'pwf-runtime-root', label: '运行数据目标根', hint: '第二阶段目标为 <根>/' + (hostInfo.dataDir || '.dsh') }, h('input', { id: 'pwf-runtime-root', className: 'pwf-input', value: value('runtimeMigrationTargetRoot'), disabled: busy, onChange: function (e) { setValue('runtimeMigrationTargetRoot', e.target.value) }, placeholder: '例如 D:\\AgentData' })),
                  host === 'kimi' ? h(Field, { key: 'kt', id: 'pwf-kimi-tools', label: 'Kimi 迁移工具路径', hint: runtimeMigration.detectedToolsPath ? '检测到：' + runtimeMigration.detectedToolsPath : '留空表示未配置，迁移按钮不可用。' }, h('input', { id: 'pwf-kimi-tools', className: 'pwf-input', value: value('kimiMigrationTools'), disabled: busy, onChange: function (e) { setValue('kimiMigrationTools', e.target.value) }, placeholder: '例如 D:\\KimiData\\kimi-migration-tools' })) : null,
                ]),
                h('div', { key: 'row2', className: 'pwf-actions' }, [
                  h('button', { key: 'go2', type: 'button', className: 'pwf-btn', disabled: busy || !value('migrationActionEnabled') || !stage1Completed || !runtimeMigration.supported || !runtimeMigration.adapterReady, onClick: prepareRuntime }, stage2Completed ? '准备迁移到新地址的脚本' : '准备第二阶段脚本'),
                  stage2Completed ? h('button', { key: 'cancel2', type: 'button', className: 'pwf-btn', disabled: busy, onClick: function () { setReprepareRuntime(false) } }, '取消') : null,
                  prepared && prepared.rollbackLauncher ? h('code', { key: 'rl', className: 'pwf-code' }, prepared.rollbackLauncher) : null,
                ]),
              ]),
          ]),
          h('p', { className: 'pwf-help' }, '回滚顺序与迁移相反：先回滚第二阶段运行数据，再回滚第一阶段插件数据；回滚前会单独备份当前最新插件数据。'),
        ]),

        h('div', { key: 'savebar', className: 'pwf-savebar' }, [
          h('div', { key: 'l', className: 'pwf-savebar-left' }, [
            h('span', { key: 'h', className: 'pwf-savebar-host' }, '当前宿主：' + (hostInfo.label || host)),
            error ? h('span', { key: 'e', className: 'pwf-savebar-feedback is-error' }, error) : null,
            message ? h('span', { key: 'm', className: 'pwf-savebar-feedback is-ok' }, message) : null,
          ]),
          h('div', { key: 'r', className: 'pwf-savebar-actions' }, [
            h('button', { key: 'reload', type: 'button', className: 'pwf-btn', disabled: busy, onClick: function () { load(host) } }, '重新读取'),
            h('button', { key: 'reset', type: 'button', className: 'pwf-btn', disabled: busy, onClick: resetConfig }, '恢复默认'),
            h('button', { key: 'save', type: 'button', className: 'pwf-btn pwf-btn-primary', disabled: busy, onClick: save }, busy ? '保存中…' : '保存设置'),
          ]),
        ]),
      ])
    }

    const css = `
    .pwf-shell { container-type: inline-size;
      --pwf-bg: var(--dsw-alias-bg-layer-1, #ffffff);
      --pwf-subtle: var(--dsw-alias-bg-layer-2, #f8fafc);
      --pwf-base: var(--dsw-alias-bg-base, #ffffff);
      --pwf-hover: var(--dsw-alias-bg-layer-2, #f8fafc);
      --pwf-text: var(--dsw-alias-label-primary, #0f172a);
      --pwf-muted: var(--dsw-alias-label-secondary, #64748b);
      --pwf-border: var(--dsw-alias-border-l1, #e2e8f0);
      --pwf-border-strong: var(--dsw-alias-border-l2, #cbd5e1);
      --pwf-primary: var(--dsw-alias-brand-primary, #4f46e5);
      --pwf-primary-soft: rgba(79,70,229,.16);
      --pwf-ok: var(--dsw-alias-state-success-primary, #047857);
      --pwf-warn: var(--dsw-alias-state-warn-primary, #b45309);
      --pwf-error: var(--dsw-alias-state-error-primary, #b91c1c);
      --pwf-idle: var(--dsw-alias-state-idle-primary, #64748b);
      --pwf-switch-off: var(--dsw-alias-border-l2, #94a3b8);
    }
    .pwf-page { max-width: 960px; margin: 0 auto; padding: 2px 0 96px; color: var(--pwf-text); font: 13px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; }
    .pwf-header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin:0 0 14px; }
    .pwf-titleblock { min-width:0; }
    .pwf-header h1 { margin:0; font-size:21px; line-height:1.25; font-weight:650; letter-spacing:-.02em; }
    .pwf-tagline { margin:4px 0 0; color:var(--pwf-muted); font-size:12px; }
    .pwf-version { flex:0 0 auto; color:var(--pwf-muted); font:11px/1 ui-monospace,Consolas,monospace; border:1px solid var(--pwf-border); background:var(--pwf-subtle); border-radius:999px; padding:5px 9px; white-space:nowrap; }
    .pwf-hostbar { display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin:0 0 12px; }
    .pwf-hosttab { min-height:32px; padding:0 12px; border:1px solid var(--pwf-border); background:var(--pwf-bg); color:var(--pwf-muted); border-radius:8px; font:12.5px inherit; cursor:pointer; }
    .pwf-hosttab:hover { color:var(--pwf-text); background:var(--pwf-hover); }
    .pwf-hosttab:focus-visible { outline:2px solid var(--pwf-primary); outline-offset:2px; }
    .pwf-hosttab.is-active { background:var(--pwf-primary); border-color:var(--pwf-primary); color:#fff; }
    .pwf-hostsummary { display:flex; align-items:center; flex-wrap:wrap; gap:8px 12px; margin:0 0 8px; color:var(--pwf-muted); font-size:12px; }
    .pwf-hostsummary strong { color:var(--pwf-text); font-size:12.5px; font-weight:600; }
    .pwf-meta-item { display:inline-flex; align-items:center; gap:6px; }
    .pwf-inline-badge { border:1px solid var(--pwf-border); border-radius:999px; padding:1px 8px; font-size:11px; color:var(--pwf-muted); background:var(--pwf-subtle); white-space:nowrap; }
    .pwf-inline-badge.is-done { color:var(--pwf-ok); border-color:currentColor; background:transparent; }
    .pwf-inline-code { font:11px/1.5 ui-monospace,Consolas,monospace; background:var(--pwf-subtle); border:1px solid var(--pwf-border); border-radius:6px; padding:1px 6px; color:var(--pwf-text); overflow-wrap:anywhere; }
    .pwf-policyline { margin:0 0 18px; color:var(--pwf-muted); font-size:12px; }
    .pwf-card { background:var(--pwf-bg); border:1px solid var(--pwf-border); border-radius:12px; padding:18px 20px; margin:0 0 16px; }
    .pwf-card h2 { margin:0 0 6px; font-size:15px; font-weight:600; letter-spacing:-.01em; }
    .pwf-desc { margin:0 0 14px; color:var(--pwf-muted); font-size:12px; line-height:1.6; }
    .pwf-help { margin:12px 0 0; color:var(--pwf-muted); font-size:11.5px; line-height:1.65; }
    .pwf-help a { color:var(--pwf-primary); text-decoration:none; }
    .pwf-help a:hover { text-decoration:underline; }
    .pwf-paths { display:flex; flex-direction:column; border:1px solid var(--pwf-border); border-radius:10px; overflow:hidden; background:var(--pwf-subtle); }
    .pwf-stage .pwf-paths { background:var(--pwf-bg); }
    .pwf-pathrow { display:grid; grid-template-columns:minmax(64px,84px) minmax(0,1fr) auto auto; align-items:center; gap:10px; min-width:0; padding:9px 12px; border-bottom:1px solid var(--pwf-border); }
    .pwf-pathrow:last-child { border-bottom:0; }
    .pwf-pathlabel { color:var(--pwf-muted); font-size:12px; white-space:nowrap; }
    .pwf-pathval { min-width:0; color:var(--pwf-text); font:11px/1.55 ui-monospace,Consolas,monospace; overflow-wrap:anywhere; word-break:break-word; }
    .pwf-pathval.is-empty { color:var(--pwf-muted); font-family:inherit; font-size:12px; }
    .pwf-copy { border:1px solid var(--pwf-border-strong); background:var(--pwf-bg); color:var(--pwf-muted); border-radius:6px; min-height:26px; padding:0 9px; font:11.5px inherit; cursor:pointer; white-space:nowrap; }
    .pwf-copy:hover { color:var(--pwf-primary); border-color:var(--pwf-primary); }
    .pwf-copy:focus-visible { outline:2px solid var(--pwf-primary); outline-offset:2px; }
    .pwf-note { border:1px solid var(--pwf-border); background:var(--pwf-subtle); border-radius:8px; padding:9px 11px; margin:12px 0 0; color:var(--pwf-muted); font-size:12px; line-height:1.6; overflow-wrap:anywhere; }
    .pwf-note > span { display:inline; }
    .pwf-note .pwf-btn { margin-left:8px; }
    .pwf-policy { border-left:3px solid var(--pwf-primary); }
    .pwf-warn { border-left:3px solid var(--pwf-warn); }
    .pwf-error { border-left:3px solid var(--pwf-error); }
    .pwf-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px 18px; }
    .pwf-grid.is-two { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .pwf-field { display:flex; flex-direction:column; gap:6px; min-width:0; }
    .pwf-field label { color:var(--pwf-text); font-size:12.5px; font-weight:500; }
    .pwf-hint { margin:0; color:var(--pwf-muted); font-size:11.5px; line-height:1.6; }
    .pwf-input { width:100%; box-sizing:border-box; height:38px; padding:0 10px; background:var(--pwf-bg); color:var(--pwf-text); border:1px solid var(--pwf-border-strong); border-radius:8px; font:12.5px inherit; outline:none; }
    .pwf-input:hover:not(:disabled) { border-color:var(--pwf-primary); }
    .pwf-input:focus-visible { border-color:var(--pwf-primary); box-shadow:0 0 0 3px var(--pwf-primary-soft); }
    .pwf-input:disabled { opacity:.6; cursor:default; }
    select.pwf-input { padding-right:8px; }
    .pwf-row { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:12px 0; border-bottom:1px solid var(--pwf-border); }
    .pwf-row:last-child { border-bottom:0; }
    .pwf-row:first-child { padding-top:2px; }
    .pwf-rowtext { display:flex; flex-direction:column; gap:3px; min-width:0; }
    .pwf-rowtext b { font-size:12.5px; font-weight:600; color:var(--pwf-text); }
    .pwf-rowtext span { color:var(--pwf-muted); font-size:11.5px; line-height:1.6; }
    .pwf-stack .pwf-row:first-child { padding-top:2px; }
    .pwf-switch { width:44px; height:26px; flex:0 0 44px; padding:0; border:1px solid var(--pwf-border-strong); border-radius:999px; background:var(--pwf-switch-off); position:relative; cursor:pointer; transition:background .15s,border-color .15s; }
    .pwf-switch.is-on { background:var(--pwf-primary); border-color:var(--pwf-primary); }
    .pwf-switch:focus-visible { outline:2px solid var(--pwf-primary); outline-offset:2px; }
    .pwf-switch:disabled { opacity:.5; cursor:default; }
    .pwf-knob { position:absolute; top:2px; left:2px; width:20px; height:20px; border-radius:50%; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.25); transition:transform .15s; }
    .pwf-switch.is-on .pwf-knob { transform:translateX(18px); }
    .pwf-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:12px 0 0; }
    .pwf-actions-block { margin-top:4px; }
    .pwf-btn { min-height:34px; padding:0 12px; border:1px solid var(--pwf-border-strong); border-radius:8px; background:var(--pwf-bg); color:var(--pwf-text); font:12.5px inherit; cursor:pointer; white-space:nowrap; }
    .pwf-btn:hover:not(:disabled) { border-color:var(--pwf-primary); color:var(--pwf-primary); }
    .pwf-btn:focus-visible { outline:2px solid var(--pwf-primary); outline-offset:2px; }
    .pwf-btn:disabled { opacity:.45; cursor:default; }
    .pwf-btn-primary { background:var(--pwf-primary); border-color:var(--pwf-primary); color:#fff; }
    .pwf-btn-primary:hover:not(:disabled) { color:#fff; filter:brightness(1.06); }
    .pwf-btn-quiet { border-color:var(--pwf-border); background:transparent; color:var(--pwf-muted); }
    .pwf-code { display:block; max-width:100%; margin-top:8px; padding:7px 9px; border:1px solid var(--pwf-border); border-radius:8px; background:var(--pwf-subtle); color:var(--pwf-text); font:11px/1.55 ui-monospace,Consolas,monospace; overflow-wrap:anywhere; word-break:break-word; }
    .pwf-stage { margin-top:16px; padding:16px; border:1px solid var(--pwf-border); border-radius:10px; background:var(--pwf-subtle); }
    .pwf-stage-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin:0 0 6px; }
    .pwf-stage-head h3 { margin:0; font-size:13.5px; font-weight:600; }
    .pwf-stage-desc { margin:0 0 6px; color:var(--pwf-muted); font-size:12px; line-height:1.6; }
    .pwf-stage-cap { margin:0 0 4px; color:var(--pwf-muted); font-size:11.5px; line-height:1.6; }
    .pwf-stage-status { margin:0 0 12px; color:var(--pwf-text); font-size:12px; }
    .pwf-status-badge { flex:0 0 auto; border:1px solid var(--pwf-border); border-radius:999px; padding:2px 9px; font-size:11px; color:var(--pwf-idle); background:var(--pwf-bg); white-space:nowrap; }
    .pwf-status-badge.is-done { color:var(--pwf-ok); border-color:currentColor; }
    .pwf-status-badge.is-warn { color:var(--pwf-warn); border-color:currentColor; }
    .pwf-status-badge.is-error { color:var(--pwf-error); border-color:currentColor; }
    .pwf-savebar { position:sticky; bottom:0; z-index:30; display:flex; align-items:center; justify-content:space-between; gap:12px 16px; flex-wrap:wrap; margin-top:20px; padding:10px 0; border-top:1px solid var(--pwf-border); background:var(--pwf-base); }
    .pwf-savebar-left { display:flex; flex-direction:column; gap:4px; min-width:0; flex:1 1 220px; }
    .pwf-savebar-host { color:var(--pwf-muted); font-size:12px; }
    .pwf-savebar-feedback { font-size:12px; line-height:1.5; overflow-wrap:anywhere; }
    .pwf-savebar-feedback.is-ok { color:var(--pwf-ok); }
    .pwf-savebar-feedback.is-error { color:var(--pwf-error); }
    .pwf-savebar-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-left:auto; }
    @container (max-width: 720px) {
      .pwf-card { padding:16px; }
      .pwf-pathrow { grid-template-columns:minmax(56px,72px) minmax(0,1fr) auto auto; gap:8px; }
      .pwf-pathlabel { white-space:normal; }
    }
    @container (max-width: 480px) {
      .pwf-pathrow { display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px; }
      .pwf-pathrow .pwf-pathlabel { flex:1 1 100%; }
      .pwf-pathrow .pwf-pathval { flex:1 1 180px; }
    }
    @container (max-width: 560px) {
      .pwf-grid, .pwf-grid.is-two { grid-template-columns:1fr; }
      .pwf-header { flex-wrap:wrap; }
      .pwf-row { flex-wrap:wrap; }
      .pwf-savebar-actions { margin-left:0; }
    }
    `
    function Style() { return h('style', null, css) }
    function Style() { return h('style', null, css) }

    const bannerCss = `
.pwf-banner { position:fixed; right:16px; bottom:18px; z-index:60; pointer-events:auto; max-width:430px; display:flex; gap:10px; align-items:flex-start; padding:11px 12px; border:1px solid var(--dsw-alias-border-l1,#e2e8f0); border-radius:9px; background:var(--dsw-alias-bg-layer-1,#fff); color:var(--dsw-alias-label-primary,#0f172a); box-shadow:0 8px 24px rgba(15,23,42,.16); font:12px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; }
.pwf-banner-text { display:flex; flex-direction:column; gap:3px; min-width:0; }
.pwf-banner-text strong { font-size:12.5px; font-weight:600; }
.pwf-banner-text span { color:var(--dsw-alias-label-secondary,#64748b); }
.pwf-banner-actions { flex:0 0 auto; }
@media (max-width: 640px) { .pwf-banner { left:12px; right:12px; max-width:none; bottom:12px; } }
`
    // Dismissal lasts for this page session; the config switch (`promptMigration`)
    // is the real opt-out and is read from the host status on every mount.
    let migrationBannerDismissed = false

    function MigrationBanner() {
      const [status, setStatus] = useState(null)
      const [hidden, setHidden] = useState(migrationBannerDismissed)
      useEffect(function () {
        if (migrationBannerDismissed) return undefined
        let active = true
        fetch('/programmer-workflow/status?host=dsh')
          .then(function (response) { return response.json() })
          .then(function (data) { if (active && data && data.pluginMigration) setStatus(data) })
          .catch(function () {})
        return function () { active = false }
      }, [])
      if (hidden || !status) return null
      const config = status.config && typeof status.config === 'object' ? status.config : {}
      if (config.promptMigration === false) return null
      const plugin = status.pluginMigration || {}
      if (plugin.status === 'completed' || plugin.prepared === true || plugin.supported === false) return null
      return h('div', { className: 'pwf-banner', role: 'status' }, [
        h('style', { key: 'css' }, bannerCss),
        h('div', { key: 't', className: 'pwf-banner-text' }, [
          h('strong', { key: 'h' }, '插件数据还没有迁移'),
          h('span', { key: 'b' }, '第一阶段只移动当前宿主的 Programmer Workflow 插件数据：打开 设置 → 程序员工作流 准备脚本，完全退出 DSH 后再运行它。会话、缓存等编辑器运行数据不属于第一阶段。'),
        ]),
        h('div', { key: 'a', className: 'pwf-banner-actions' }, [
          h('button', {
            key: 'd', type: 'button', className: 'pwf-btn',
            onClick: function () { migrationBannerDismissed = true; setHidden(true) },
          }, '知道了'),
        ]),
      ])
    }

    function apply(ctx) {
      const page = function ProgrammerWorkflowPage() {
        return h('div', { className: 'pwf-shell' }, [h(Style, { key: 'css' }), h(SettingsPage, { key: 'page' })])
      }
      ctx.slots.inject('shell.overlay', function () {
        return ctx.slots.register({
          name: 'shell.overlay',
          id: ENTRY_ID + '-migration-hint',
          order: 60,
        }, MigrationBanner)
      })
      return ctx.slots.inject('settings.section', function () {
        return ctx.slots.register({
          name: 'settings.section',
          id: ENTRY_ID,
          order: 30,
          label: '程序员工作流',
        }, page)
      })
    }

    return { inject: ['slots'], apply: apply }
  },
})
