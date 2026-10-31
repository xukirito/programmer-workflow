/* Programmer Workflow · interactive Architecture.html / Features.html */
(function () {
  "use strict";
  const PAGE = JSON.parse(document.getElementById("wc-data").textContent);
  const DATA = PAGE.data;
  const KIND = DATA.kind;
  const esc = WC.escape;
  const app = WC.byId("wc-app");
  const state = {
    tab: "overview",
    moduleQuery: "",
    featureQuery: "",
    fileQuery: "",
    decisionQuery: "",
    layer: "all",
    status: "all",
    domain: "all",
    flow: (DATA.flows && DATA.flows[0] && DATA.flows[0].id) || "",
    graph: false
  };
  const review = new WC.Review({
    kind: KIND,
    title: PAGE.title,
    specHash: DATA.spec_hash || "",
    sections: tabs().map(function (tab) { return { id: tab.id, label: tab.label }; })
  });

  function tabs() {
    if (KIND === "architecture") {
      const list = [
        { id: "overview", label: "总览" },
        { id: "modules", label: "模块地图", count: DATA.modules.length },
        { id: "flows", label: "数据流", count: DATA.flows.length },
        { id: "decisions", label: "关键决策", count: DATA.decisions.length },
        { id: "risks", label: "风险与问题", count: DATA.risks.length + DATA.questions.length },
        { id: "files", label: "文件索引", count: DATA.file_index.length }
      ];
      if (DATA.glossary.length) list.push({ id: "glossary", label: "术语", count: DATA.glossary.length });
      return list;
    }
    const list = [
      { id: "overview", label: "总览" },
      { id: "features", label: "功能清单", count: DATA.features.length },
      { id: "matrix", label: "覆盖矩阵" },
      { id: "journeys", label: "用户路径", count: DATA.journeys.length },
      { id: "questions", label: "待确认", count: DATA.questions.length }
    ];
    if (DATA.glossary.length) list.push({ id: "glossary", label: "术语", count: DATA.glossary.length });
    return list;
  }

  /* ---------------------------------------------------------------- utils */
  function badge(text, cls) { return '<span class="wc-badge ' + (cls || "") + '">' + esc(text) + '</span>'; }
  function chip(text, cls, attrs) { return '<button class="wc-chip clickable ' + (cls || "") + '" ' + (attrs || "") + '>' + esc(text) + '</button>'; }
  function meta(items) {
    return '<div class="wc-meta">' + items.filter(Boolean).map(function (item, index) {
      if (typeof item === "string") return '<span class="' + (index ? "dot" : "") + '">' + esc(item) + '</span>';
      return '<span class="' + (index ? "dot" : "") + '">' + item + '</span>';
    }).join("") + '</div>';
  }
  function confidenceBadge(value) {
    const cls = value === "high" ? "ok" : value === "low" ? "warn" : "info";
    const label = value === "high" ? "高置信" : value === "low" ? "低置信" : "中置信";
    return badge(label, cls);
  }
  function copyPath(path) {
    if (!path) return "";
    return '<span class="file-path"><code>' + esc(path) + '</code><button class="wc-copy" data-copy="' + esc(path) + '" title="复制路径">复制</button></span>';
  }
  function empty(title, hint) {
    return '<div class="wc-empty"><strong>' + esc(title) + '</strong>' + esc(hint || "") + '</div>';
  }
  function sectionHead(title, subtitle, extra) {
    return '<div class="wc-section-head"><div><h2>' + esc(title) + '</h2>' +
      (subtitle ? '<p>' + esc(subtitle) + '</p>' : "") + '</div>' + (extra || "") + '</div>';
  }

  /* ---------------------------------------------------------------- theme/sibling */
  function initChrome() {
    const sibling = WC.byId("wc-sibling-link");
    if (sibling) {
      sibling.href = KIND === "architecture" ? "Features.html" : "Architecture.html";
      sibling.textContent = KIND === "architecture" ? "功能地图 →" : "工程架构 →";
    }
    const copy = WC.byId("wc-copy-md");
    if (copy) copy.addEventListener("click", function () { WC.copy(pageMarkdown()); });
    const title = WC.byId("wc-page-title");
    if (title) title.textContent = PAGE.title;
    const generated = WC.byId("wc-generated");
    if (generated) generated.textContent = WC.formatDate(PAGE.generated_at);
    document.documentElement.lang = (DATA.project && DATA.project.language) || "zh-CN";
  }

  function pageMarkdown() {
    const lines = ["# " + PAGE.title, "", DATA.project.summary || "", ""];
    if (KIND === "architecture") {
      lines.push("## 模块");
      DATA.modules.forEach(function (m) {
        lines.push("- **" + m.name + "** (`" + m.path + "`)：" + m.role);
      });
      lines.push("", "## 关键决策");
      DATA.decisions.forEach(function (d) {
        lines.push("- **" + d.title + "**：" + d.choice);
      });
      lines.push("", "## 风险");
      DATA.risks.forEach(function (r) {
        lines.push("- **" + r.title + "**（" + r.severity + "）：" + r.mitigation);
      });
    } else {
      lines.push("## 功能");
      DATA.features.forEach(function (f) {
        lines.push("- **" + f.name + "**（" + f.status + "）：" + f.summary);
      });
    }
    lines.push("", "> 由 Programmer Workflow 生成。交互式版本：" + location.href);
    return lines.join("\n");
  }

  /* ---------------------------------------------------------------- hero */
  function hero() {
    const p = DATA.project || {};
    const stats = DATA.stats || {};
    const confidence = p.confidence || "medium";
    const ring = confidence === "high" ? 86 : confidence === "low" ? 46 : 68;
    let side = "";
    if (KIND === "architecture") {
      side = [
        '<div><h3>工程快照</h3><div class="list">',
        item("模块", stats.modules), item("核心流程", stats.flows),
        item("关键决策", stats.decisions), item("风险", stats.risks),
        item("扫描文件", stats.files), item("代码行", stats.loc),
        "</div></div>"
      ].join("");
    } else {
      const pct = stats.features ? Math.round((stats.implemented / stats.features) * 100) : 0;
      side = [
        '<div><h3>功能快照</h3><div class="list">',
        item("功能总数", stats.features), item("已实现", stats.implemented),
        item("部分实现", stats.partial), item("规划中", stats.planned),
        item("领域", stats.domains), item("待确认", stats.questions),
        "</div><div class=\"wc-meter\" style=\"margin-top:12px\"><i style=\"width:" + pct + "%\"></i></div><div class=\"wc-meta\" style=\"margin-top:5px\"><span>实现覆盖 " + pct + "%</span></div></div>"
      ].join("");
    }
    side += '<div><h3>阅读置信度</h3><div class="confidence-ring"><div class="ring" style="--p:' + ring + '"><b>' + ring + '%</b></div><div class="ring-label">' +
      (confidence === "high" ? "证据充分" : confidence === "low" ? "证据有限，需核对" : "部分推断，建议抽查") +
      '<br><span class="wc-dim">基于文件、配置与运行信号</span></div></div></div>';
    const scope = (p.scope || []).length ? "扫描范围：" + p.scope.join(" · ") : "";
    return '<section class="doc-hero">' +
      '<div class="doc-hero-main"><div class="wc-meta" style="margin-bottom:10px">' +
      badge(KIND === "architecture" ? "工程架构" : "功能地图", "violet") +
      (p.version ? badge("v" + p.version) : "") +
      (p.commit ? badge(p.commit) : "") +
      '</div><h2>' + esc(p.name) + '</h2>' +
      (p.tagline ? '<p class="tagline">' + esc(p.tagline) + '</p>' : "") +
      '<p class="summary">' + esc(p.summary || "暂无摘要。") + '</p>' +
      meta([p.generated_at ? "生成于 " + WC.formatDate(p.generated_at) : "", scope, p.source || ""]) +
      '</div><aside class="doc-hero-side">' + side + '</aside></section>';
  }
  function item(label, value) {
    return '<div class="item"><span>' + esc(label) + '</span><span>' + esc(value == null || value === "" ? "—" : value) + '</span></div>';
  }

  function kpis() {
    let items = [];
    if (KIND === "architecture") {
      items = [
        ["模块", DATA.stats.modules, "可独立说明的代码单元"],
        ["流程", DATA.stats.flows, "从入口到结果"],
        ["决策", DATA.stats.decisions, "有取舍的选择"],
        ["风险", DATA.stats.risks, "需持续观察"],
        ["文件", DATA.stats.files, "扫描到的关键文件"],
        ["待确认", DATA.stats.questions, "需要你拍板"]
      ];
    } else {
      items = [
        ["功能", DATA.stats.features, "按领域归类"],
        ["已实现", DATA.stats.implemented, "有代码与证据"],
        ["部分实现", DATA.stats.partial, "可用但不完整"],
        ["规划中", DATA.stats.planned, "仅有意图"],
        ["领域", DATA.stats.domains, "功能分组"],
        ["待确认", DATA.stats.questions, "需要你拍板"]
      ];
    }
    return '<div class="wc-kpis">' + items.map(function (it) {
      return '<div class="wc-kpi"><div class="n">' + esc(it[1]) + '</div><div class="l">' + esc(it[0]) + '</div><div class="h">' + esc(it[2]) + '</div></div>';
    }).join("") + '</div>';
  }

  function tabbar() {
    return '<nav class="wc-tabs" role="tablist" aria-label="文档章节">' + tabs().map(function (tab) {
      return '<button class="wc-tab ' + (state.tab === tab.id ? "active" : "") + '" role="tab" aria-selected="' + (state.tab === tab.id) + '" data-tab="' + tab.id + '">' +
        esc(tab.label) + (tab.count != null ? '<span class="count">' + tab.count + '</span>' : "") + '</button>';
    }).join("") + '</nav>';
  }

  /* ---------------------------------------------------------------- overview */
  function overview() {
    if (KIND === "architecture") {
      const layers = DATA.layers.length ? DATA.layers : deriveLayers();
      const stack = DATA.stack.length ? '<div class="stack-grid">' + DATA.stack.map(function (s) {
        return '<div class="stack-item"><strong>' + esc(s.name) + '</strong><span>' + esc(s.role || "") + '</span>' +
          (s.version ? '<code>' + esc(s.version) + '</code>' : "") + '</div>';
      }).join("") + '</div>' : empty("未识别技术栈", "规范里没有提供 stack 信息。");
      const topModules = DATA.modules.slice(0, 6).map(moduleCard).join("");
      const decisions = DATA.decisions.slice(0, 2).map(function (d) {
        return '<div class="wc-card decision-card clickable" data-jump-tab="decisions"><h3>' + esc(d.title) + '</h3><p>' + esc(d.choice) + '</p></div>';
      }).join("");
      return '<div class="tab-panel">' +
        sectionHead("工程在做什么", "用一页快速建立心智模型，再按需深入模块、流程与决策。") +
        '<div class="overview-columns"><div>' + DATA.project.summary.split(/\n+/).map(function (para) {
          return '<p class="wc-muted">' + esc(para) + '</p>';
        }).join("") +
        '<h3 style="margin-top:18px">模块分层</h3><div class="layer-list">' + layers.map(function (layer) {
          const count = DATA.modules.filter(function (m) { return (m.layer || "未分层") === (layer.id || "未分层"); }).length;
          return '<div class="layer-item"><strong>' + esc(layer.name) + '</strong> <span class="wc-dim">' + count + ' 个模块</span><p>' + esc(layer.description || "") + '</p></div>';
        }).join("") + '</div>' +
        '<h3 style="margin-top:20px">先看这几个模块</h3><div class="wc-grid auto">' + topModules + '</div>' +
        (decisions ? '<h3 style="margin-top:20px">关键决策速览</h3><div class="wc-grid cols-2">' + decisions + '</div>' : "") +
        '</div><aside><div class="reading-guide"><h3>怎么读这份文档</h3><ol>' +
        '<li><strong>总览</strong>：先确认工程边界与分层是否和你的理解一致。</li>' +
        '<li><strong>模块地图</strong>：点开卡片看职责、依赖与证据；切到依赖图看结构。</li>' +
        '<li><strong>数据流</strong>：沿着一条真实链路检查入口、状态与失败模式。</li>' +
        '<li><strong>风险与问题</strong>：把不认同的条目写成评审意见，底部可导出。</li>' +
        '</ol><div class="wc-note" style="margin-top:12px">文档是“带证据的快照”，不是永久真理。代码变化后重新生成，旧评审会按文档标识失效。</div></div>' +
        '<h3 style="margin-top:18px">技术栈</h3>' + stack + '</aside></div></div>';
    }

    const domains = DATA.domains.map(function (domain) {
      const list = DATA.features.filter(function (f) { return f.domain === domain.id; });
      const done = list.filter(function (f) { return f.status === "implemented"; }).length;
      const pct = list.length ? Math.round((done / list.length) * 100) : 0;
      return '<div class="wc-card"><div class="wc-card-head"><div class="wc-card-title"><h3>' + esc(domain.name) + '</h3></div>' + badge(list.length + " 项") + '</div>' +
        '<p>' + esc(domain.description || "未填写领域说明") + '</p><div class="wc-meter" style="margin-top:12px"><i style="width:' + pct + '%"></i></div>' +
        '<div class="wc-meta" style="margin-top:6px"><span>' + done + '/' + list.length + ' 已实现</span><span class="dot">点击筛选</span></div></div>';
    }).join("");
    const top = DATA.features.slice().sort(function (a, b) {
      const order = { implemented: 0, partial: 1, planned: 2 };
      return (order[a.status] - order[b.status]) || a.name.localeCompare(b.name);
    }).slice(0, 6).map(featureCard).join("");
    return '<div class="tab-panel">' +
      sectionHead("功能全景", "按领域理解产品能力，再逐项核对入口、证据与测试。") +
      '<div class="wc-grid auto">' + domains + '</div>' +
      '<h3 style="margin-top:24px">优先核对的功能</h3><div class="wc-grid auto">' + top + '</div>' +
      (DATA.journeys.length ? '<h3 style="margin-top:24px">用户路径</h3><div class="wc-grid">' + DATA.journeys.slice(0, 3).map(journeyCard).join("") + '</div>' : "") +
      '</div>';
  }

  function deriveLayers() {
    const seen = [];
    DATA.modules.forEach(function (m) {
      const name = m.layer || "未分层";
      if (!seen.some(function (s) { return s.id === name; })) seen.push({ id: name, name: name, description: "" });
    });
    return seen;
  }

  /* ---------------------------------------------------------------- modules */
  function moduleCard(m) {
    const deps = (m.depends_on || []).slice(0, 4).map(function (id) {
      const target = DATA.modules.find(function (x) { return x.id === id; });
      return '<span class="dep">' + esc(target ? target.name : id) + '</span>';
    }).join("");
    return '<article class="wc-card clickable module-card" data-module="' + esc(m.id) + '" data-name="' + esc((m.name + " " + m.path + " " + m.role).toLowerCase()) + '" data-layer="' + esc(m.layer || "") + '" tabindex="0">' +
      '<div class="module-top"><div><h3>' + esc(m.name) + '</h3><div class="module-path wc-path">' + esc(m.path || "—") + '</div></div><span class="layer-chip">' + esc(m.layer || "未分层") + '</span></div>' +
      '<p class="role">' + esc(m.role || m.notes || "未填写职责") + '</p>' +
      '<div class="deps">' + (deps || '<span class="dep">无内部依赖</span>') + '</div></article>';
  }

  function modulesTab() {
    const layers = deriveLayers();
    const chips = '<div class="wc-toolbar"><div class="wc-search"><svg class="wc-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg>' +
      '<input id="module-search" class="wc-input" placeholder="搜索模块、路径、职责…" value="' + esc(state.moduleQuery) + '" aria-label="搜索模块"></div>' +
      '<button class="wc-btn small ' + (state.layer === "all" ? "primary" : "") + '" data-layer="all">全部层</button>' +
      layers.map(function (layer) {
        return '<button class="wc-btn small ' + (state.layer === layer.id ? "primary" : "") + '" data-layer="' + esc(layer.id) + '">' + esc(layer.name) + '</button>';
      }).join("") +
      '<span class="wc-right"></span><button class="wc-btn small ' + (state.graph ? "primary" : "") + '" data-graph="' + (state.graph ? "0" : "1") + '">' +
      '<svg class="wc-icon" viewBox="0 0 24 24"><circle cx="5" cy="12" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 12h4a4 4 0 0 0 4-4"/><path d="M7 12h4a4 4 0 0 1 4 4"/></svg>' + (state.graph ? "卡片视图" : "依赖图") + '</button></div>';
    if (state.graph) {
      return '<div class="tab-panel">' + sectionHead("依赖关系图", "节点是模块，箭头指向被依赖方。拖拽平移、滚轮缩放、点击查看详情。") + chips + graphHTML() + '</div>';
    }
    return '<div class="tab-panel">' + sectionHead("模块地图", "每个模块都带路径、职责和依赖；点开卡片查看关键文件与证据。",
      '<span class="wc-meta" id="module-visible-count">' + DATA.modules.length + ' 个模块</span>') + chips +
      '<div class="wc-grid auto" id="module-grid">' + DATA.modules.map(moduleCard).join("") + '</div>' +
      '<div id="module-empty" class="wc-hide">' + empty("没有匹配的模块", "换个关键词或切回全部层。") + '</div></div>';
  }

  function layoutGraph() {
    const layers = DATA.layers.length ? DATA.layers : deriveLayers();
    const order = {};
    layers.forEach(function (layer, index) { order[layer.id] = index; });
    const groups = {};
    DATA.modules.forEach(function (m) {
      const key = m.layer || "未分层";
      if (order[key] == null) order[key] = Object.keys(order).length;
      (groups[key] = groups[key] || []).push(m);
    });
    const nodeW = 168, nodeH = 48, gapX = 235, gapY = 92;
    const nodes = [];
    Object.keys(groups).forEach(function (key) {
      const column = order[key];
      groups[key].forEach(function (m, row) {
        nodes.push({ m: m, x: 40 + column * gapX, y: 46 + row * gapY, w: nodeW, h: nodeH });
      });
    });
    const maxX = nodes.reduce(function (max, n) { return Math.max(max, n.x + n.w); }, 0);
    const maxY = nodes.reduce(function (max, n) { return Math.max(max, n.y + n.h); }, 0);
    const W = Math.max(900, maxX + 60);
    const H = Math.max(460, maxY + 70);
    const byId = {};
    nodes.forEach(function (n) { byId[n.m.id] = n; });
    const edges = [];
    nodes.forEach(function (n) {
      (n.m.depends_on || []).forEach(function (id) {
        if (byId[id]) edges.push({ from: n, to: byId[id], id: n.m.id + "__" + id });
      });
    });
    return { nodes: nodes, edges: edges, W: W, H: H, byId: byId };
  }

  function graphHTML() {
    const layout = layoutGraph();
    const nodeMarkup = layout.nodes.map(function (n) {
      const sub = n.m.layer || "";
      return '<g class="node" data-module="' + esc(n.m.id) + '" data-graph-node="' + esc(n.m.id) + '" transform="translate(' + n.x + ',' + n.y + ')" tabindex="0" role="button" aria-label="' + esc(n.m.name) + '">' +
        '<rect width="' + n.w + '" height="' + n.h + '" rx="10"></rect>' +
        '<text x="' + (n.w / 2) + '" y="20" text-anchor="middle">' + esc(n.m.name.length > 18 ? n.m.name.slice(0, 17) + "…" : n.m.name) + '</text>' +
        '<text class="sub" x="' + (n.w / 2) + '" y="35" text-anchor="middle">' + esc(sub.length > 22 ? sub.slice(0, 21) + "…" : sub) + '</text></g>';
    }).join("");
    const edgeMarkup = layout.edges.map(function (e) {
      const x1 = e.from.x + e.from.w, y1 = e.from.y + e.from.h / 2;
      const x2 = e.to.x, y2 = e.to.y + e.to.h / 2;
      const dx = Math.max(38, Math.abs(x2 - x1) * 0.45);
      return '<path class="edge" data-edge="' + esc(e.id) + '" data-from="' + esc(e.from.m.id) + '" data-to="' + esc(e.to.m.id) + '" d="M' + x1 + ',' + y1 + ' C' + (x1 + dx) + ',' + y1 + ' ' + (x2 - dx) + ',' + y2 + ' ' + x2 + ',' + y2 + '"></path>';
    }).join("");
    return '<div class="graph-wrap" id="graph-wrap"><svg class="graph-svg" id="graph-svg" viewBox="0 0 ' + layout.W + ' ' + layout.H + '" role="img" aria-label="模块依赖图">' +
      '<defs><marker id="wc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="rgba(148,163,184,.55)"></path></marker></defs>' +
      '<g id="graph-viewport">' + edgeMarkup + nodeMarkup + '</g></svg>' +
      '<div class="graph-controls"><button class="wc-btn small icon ghost" data-zoom="in" title="放大">+</button><button class="wc-btn small icon ghost" data-zoom="out" title="缩小">−</button><button class="wc-btn small ghost" data-zoom="reset">重置</button></div>' +
      '<div class="graph-legend"><span><i style="background:var(--wc-accent)"></i>点击节点查看详情</span><span><i style="background:var(--wc-ok)"></i>箭头 = 依赖</span></div>' +
      '<div class="graph-hint">拖拽平移 · 滚轮缩放</div></div>';
  }

  /* ---------------------------------------------------------------- flows */
  function flowsTab() {
    if (!DATA.flows.length) return '<div class="tab-panel">' + sectionHead("数据流", "") + empty("还没有记录流程", "在 spec 的 flows 中补充入口、步骤和失败模式。") + '</div>';
    const current = DATA.flows.find(function (f) { return f.id === state.flow; }) || DATA.flows[0];
    const list = DATA.flows.map(function (flow) {
      return '<button class="flow-pick ' + (flow.id === current.id ? "active" : "") + '" data-flow="' + esc(flow.id) + '">' + esc(flow.name) + '<small>' + flow.steps.length + ' 步 · ' + esc(flow.summary || "") + '</small></button>';
    }).join("");
    const steps = current.steps.map(function (step, index) {
      return '<li class="wc-step" data-index="' + (index + 1) + '"><h4>' + (step.actor ? '<span class="timeline-actor">' + esc(step.actor) + '</span>' : "") + esc(step.action || "步骤 " + (index + 1)) + '</h4>' +
        (step.target ? '<div class="timeline-target">' + esc(step.target) + '</div>' : "") +
        (step.detail ? '<p>' + esc(step.detail) + '</p>' : "") +
        (step.evidence ? '<div class="wc-meta">' + copyPath(step.evidence) + '</div>' : "") + '</li>';
    }).join("");
    return '<div class="tab-panel">' + sectionHead("数据流", "选一条真实链路，逐步核对入口、状态变化和失败模式。") +
      '<div class="flow-layout"><div class="flow-list">' + list + '</div><div class="flow-detail wc-card">' +
      '<h3>' + esc(current.name) + '</h3><p class="flow-summary">' + esc(current.summary || "") + '</p>' +
      '<ol class="wc-timeline" style="margin-top:18px">' + steps + '</ol>' +
      (current.artifacts.length ? '<div class="flow-artifacts">' + current.artifacts.map(function (a) { return badge(a, "info"); }).join("") + '</div>' : "") +
      (current.failure_modes.length ? '<h4 style="margin-top:20px">失败模式</h4><ul class="wc-muted">' + current.failure_modes.map(function (f) { return '<li>' + esc(f) + '</li>'; }).join("") + '</ul>' : "") +
      '</div></div></div>';
  }

  /* ---------------------------------------------------------------- decisions */
  function decisionsTab() {
    const q = state.decisionQuery.toLowerCase();
    const items = DATA.decisions.filter(function (d) {
      return !q || (d.title + " " + d.choice + " " + (d.why || []).join(" ")).toLowerCase().indexOf(q) >= 0;
    });
    return '<div class="tab-panel">' + sectionHead("关键决策", "记录“选了什么、为什么、代价是什么”，方便以后复盘而不是重新争论。") +
      '<div class="wc-toolbar"><div class="wc-search"><svg class="wc-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg><input id="decision-search" class="wc-input" placeholder="搜索决策…" value="' + esc(state.decisionQuery) + '"></div><span class="wc-meta">' + items.length + ' 条</span></div>' +
      '<div class="wc-grid cols-2" id="decision-grid">' + items.map(function (d) {
        return '<article class="wc-card decision-card" data-name="' + esc((d.title + " " + d.choice).toLowerCase()) + '"><div class="wc-card-head"><div class="wc-card-title"><h3>' + esc(d.title) + '</h3></div>' + badge(d.status || "accepted", "ok") + '</div>' +
          '<div class="choice">' + esc(d.choice) + '</div>' +
          (d.why.length ? '<h4 class="wc-small wc-dim" style="margin:12px 0 2px">为什么</h4><ul>' + d.why.map(function (w) { return '<li>' + esc(w) + '</li>'; }).join("") + '</ul>' : "") +
          (d.tradeoffs.length ? '<h4 class="wc-small wc-dim" style="margin:12px 0 2px">代价</h4><ul>' + d.tradeoffs.map(function (w) { return '<li>' + esc(w) + '</li>'; }).join("") + '</ul>' : "") +
          (d.alternatives.length ? '<div class="wc-meta" style="margin-top:10px">备选：' + d.alternatives.map(function (a) { return badge(a); }).join(" ") + '</div>' : "") +
          '</article>';
      }).join("") + '</div><div id="decision-empty" class="' + (items.length ? "wc-hide" : "") + '">' + empty("没有匹配的决策", "清空搜索试试。") + '</div></div>';
  }

  /* ---------------------------------------------------------------- risks */
  function risksTab() {
    const sev = { high: 0, medium: 1, low: 2 };
    const risks = DATA.risks.slice().sort(function (a, b) { return sev[a.severity] - sev[b.severity]; });
    return '<div class="tab-panel">' + sectionHead("风险与待确认问题", "风险按严重度排序；问题需要你拍板，可直接复制到对话里。") +
      (risks.length ? '<div class="wc-grid cols-2">' + risks.map(function (r) {
        return '<article class="wc-card risk-card ' + esc(r.severity) + '"><div class="risk-head"><h3>' + esc(r.title) + '</h3>' + badge(r.severity === "high" ? "高" : r.severity === "low" ? "低" : "中", r.severity === "high" ? "danger" : r.severity === "low" ? "ok" : "warn") + '</div>' +
          '<p><strong>影响：</strong>' + esc(r.impact || "—") + '</p><p><strong>缓解：</strong>' + esc(r.mitigation || "—") + '</p>' +
          '<div class="wc-meta">' + (r.owner ? '<span>负责人 ' + esc(r.owner) + '</span>' : "") + (r.evidence || []).slice(0, 2).map(function (e) { return '<span class="dot">' + copyPath(e) + '</span>'; }).join("") + '</div></article>';
      }).join("") + '</div>' : empty("未记录风险", "这不代表没有风险，可能只是还没整理。")) +
      (DATA.questions.length ? '<h3 style="margin:26px 0 10px">需要你确认</h3><div class="wc-grid">' + DATA.questions.map(questionCard).join("") + '</div>' : "") + '</div>';
  }

  function questionCard(q) {
    return '<article class="wc-card"><div class="wc-card-head"><div class="wc-card-title"><h3>' + esc(q.question) + '</h3></div>' + badge(q.id ?? "") + '</div>' +
      (q.why ? '<p>' + esc(q.why) + '</p>' : "") +
      (q.default ? '<div class="wc-note" style="margin-top:10px">默认假设：' + esc(q.default) + '</div>' : "") +
      '<div class="wc-meta" style="margin-top:10px"><button class="wc-copy" data-copy="' + esc(q.question + (q.why ? "\n\n背景：" + q.why : "")) + '">复制问题</button></div></article>';
  }

  /* ---------------------------------------------------------------- files */
  function filesTab() {
    return '<div class="tab-panel">' + sectionHead("文件索引", "只列出与架构理解最相关的文件；完整树用项目工具查看。") +
      '<div class="wc-toolbar"><div class="wc-search"><svg class="wc-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg><input id="file-search" class="wc-input" placeholder="搜索路径或用途…" value="' + esc(state.fileQuery) + '"></div><span class="wc-meta" id="file-count">' + DATA.file_index.length + ' 个文件</span></div>' +
      '<div class="wc-table-wrap"><table class="wc-table"><thead><tr><th>路径</th><th>模块</th><th>用途</th><th>行数</th></tr></thead><tbody id="file-body">' +
      DATA.file_index.map(function (f) {
        return '<tr data-name="' + esc((f.path + " " + f.purpose).toLowerCase()) + '"><td>' + copyPath(f.path) + '</td><td>' + esc(f.module || "—") + '</td><td>' + esc(f.purpose || "—") + '</td><td class="wc-nowrap">' + (f.lines || "—") + '</td></tr>';
      }).join("") + '</tbody></table></div><div id="file-empty" class="wc-hide">' + empty("没有匹配文件", "换个关键词。") + '</div></div>';
  }

  /* ---------------------------------------------------------------- features */
  function featureCard(f) {
    const label = f.status === "implemented" ? "已实现" : f.status === "planned" ? "规划中" : "部分实现";
    const cls = f.status === "implemented" ? "ok" : f.status === "planned" ? "info" : "warn";
    const domain = (DATA.domains.find(function (d) { return d.id === f.domain; }) || {}).name || f.domain || "未分组";
    return '<article class="wc-card clickable feature-card" data-feature="' + esc(f.id) + '" data-name="' + esc((f.name + " " + f.summary + " " + domain).toLowerCase()) + '" data-domain="' + esc(f.domain || "") + '" data-status="' + esc(f.status) + '" tabindex="0">' +
      '<div class="feature-top"><div><h3>' + esc(f.name) + '</h3><div class="wc-meta" style="margin-top:4px"><span>' + esc(domain) + '</span>' + (f.priority ? '<span class="dot">' + esc(f.priority) + '</span>' : "") + '</div></div>' +
      '<span class="wc-badge ' + cls + '"><i class="status-dot ' + esc(f.status === "implemented" ? "" : f.status) + '"></i>' + label + '</span></div>' +
      '<p class="feature-summary">' + esc(f.summary || "未填写功能说明") + '</p>' +
      '<div class="feature-foot">' + confidenceBadge(f.confidence) + (f.tests.length ? badge(f.tests.length + " 个测试", "violet") : badge("未记录测试", "warn")) + (f.dependencies.length ? badge(f.dependencies.length + " 依赖") : "") + '</div></article>';
  }

  function featuresTab() {
    const domains = DATA.domains;
    return '<div class="tab-panel">' + sectionHead("功能清单", "按状态和领域筛选；点击卡片查看入口、用户路径、依赖与证据。",
      '<span class="wc-meta" id="feature-count">' + DATA.features.length + ' 项功能</span>') +
      '<div class="wc-toolbar"><div class="wc-search"><svg class="wc-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg><input id="feature-search" class="wc-input" placeholder="搜索功能…" value="' + esc(state.featureQuery) + '"></div>' +
      '<button class="wc-btn small ' + (state.status === "all" ? "primary" : "") + '" data-status="all">全部</button>' +
      '<button class="wc-btn small ' + (state.status === "implemented" ? "primary" : "") + '" data-status="implemented">已实现</button>' +
      '<button class="wc-btn small ' + (state.status === "partial" ? "primary" : "") + '" data-status="partial">部分实现</button>' +
      '<button class="wc-btn small ' + (state.status === "planned" ? "primary" : "") + '" data-status="planned">规划中</button>' +
      '<select class="wc-select" id="feature-domain" style="max-width:170px"><option value="all">全部领域</option>' +
      domains.map(function (d) { return '<option value="' + esc(d.id) + '" ' + (state.domain === d.id ? "selected" : "") + '>' + esc(d.name) + '</option>'; }).join("") + '</select></div>' +
      '<div class="wc-grid auto" id="feature-grid">' + DATA.features.map(featureCard).join("") + '</div><div id="feature-empty" class="wc-hide">' + empty("没有匹配的功能", "换个关键词或筛选条件。") + '</div></div>';
  }

  function matrixTab() {
    const statuses = [["implemented", "已实现"], ["partial", "部分实现"], ["planned", "规划中"]];
    const rows = DATA.domains.map(function (d) {
      const list = DATA.features.filter(function (f) { return f.domain === d.id; });
      return '<div class="matrix-row"><div class="matrix-cell matrix-label">' + esc(d.name) + '<div class="wc-dim wc-small">' + list.length + ' 项</div></div>' +
        statuses.map(function (s) {
          const count = list.filter(function (f) { return f.status === s[0]; }).length;
          return '<button class="matrix-cell n ' + (count ? "" : "zero") + '" data-matrix="' + esc(d.id) + '|' + s[0] + '" title="点击筛选">' + count + '</button>';
        }).join("") + '</div>';
    }).join("");
    return '<div class="tab-panel">' + sectionHead("覆盖矩阵", "领域 × 状态的分布；点击数字跳到对应筛选。") +
      '<div class="matrix"><div class="matrix-row"><div class="matrix-head" style="text-align:left">领域</div>' + statuses.map(function (s) { return '<div class="matrix-head">' + s[1] + '</div>'; }).join("") + '</div>' + rows + '</div>' +
      '<div class="wc-note" style="margin-top:16px">矩阵只反映文档记录的状态，不等同于产品质量。规划中的功能尤其需要确认是否真的要做。</div></div>';
  }

  function journeysTab() {
    return '<div class="tab-panel">' + sectionHead("用户路径", "把功能串成真实任务，检查断裂点和缺失环节。") +
      (DATA.journeys.length ? '<div class="wc-grid">' + DATA.journeys.map(journeyCard).join("") + '</div>' : empty("还没有用户路径", "可以在 spec 的 journeys 中补充。")) + '</div>';
  }

  function journeyCard(j) {
    return '<div class="journey"><h3>' + esc(j.name) + '</h3><ol>' + j.steps.map(function (step) { return '<li>' + esc(step) + '</li>'; }).join("") + '</ol>' +
      '<div class="wc-meta" style="margin-top:10px">' + j.feature_ids.map(function (id) {
        const f = DATA.features.find(function (x) { return x.id === id; });
        return f ? '<button class="wc-copy" data-feature="' + esc(f.id) + '">' + esc(f.name) + '</button>' : "";
      }).join(" · ") + '</div></div>';
  }

  function questionsTab() {
    return '<div class="tab-panel">' + sectionHead("待确认", "这些问题会直接影响文档结论；复制到对话里让用户拍板。") +
      (DATA.questions.length ? '<div class="wc-grid">' + DATA.questions.map(questionCard).join("") + '</div>' : empty("没有待确认问题", "可能已经确认过，或还没暴露。")) + '</div>';
  }

  function glossaryTab() {
    return '<div class="tab-panel">' + sectionHead("术语", "统一叫法，减少沟通偏差。") +
      '<div class="wc-table-wrap"><table class="wc-table"><thead><tr><th>术语</th><th>定义</th></tr></thead><tbody>' +
      DATA.glossary.map(function (g) { return '<tr><td class="wc-strong">' + esc(g.term) + '</td><td>' + esc(g.definition) + '</td></tr>'; }).join("") +
      '</tbody></table></div></div>';
  }

  /* ---------------------------------------------------------------- drawers */
  function drawer(title, subtitle, bodyHTML) {
    const node = WC.byId("wc-drawer");
    const overlay = WC.byId("wc-overlay");
    if (!node) return;
    node.innerHTML = '<div class="wc-drawer-head"><div><h3>' + esc(title) + '</h3>' +
      (subtitle ? '<div class="wc-meta" style="margin-top:4px">' + esc(subtitle) + '</div>' : "") +
      '</div><button class="wc-btn small icon ghost" data-close-drawer aria-label="关闭">✕</button></div>' + bodyHTML;
    node.classList.add("open");
    node.setAttribute("aria-hidden", "false");
    overlay.hidden = false;
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
    WC.bindCopy(node);
    node.querySelectorAll("[data-goto-module]").forEach(function (button) {
      button.addEventListener("click", function () { openModule(button.getAttribute("data-goto-module")); });
    });
    node.querySelectorAll("[data-goto-feature]").forEach(function (button) {
      button.addEventListener("click", function () { openFeature(button.getAttribute("data-goto-feature")); });
    });
  }
  function closeDrawer() {
    const node = WC.byId("wc-drawer");
    const overlay = WC.byId("wc-overlay");
    if (!node) return;
    node.classList.remove("open");
    node.setAttribute("aria-hidden", "true");
    overlay.classList.remove("open");
    overlay.hidden = true;
    document.body.style.overflow = "";
  }
  function openModule(id) {
    const m = DATA.modules.find(function (x) { return x.id === id; });
    if (!m) return;
    const deps = m.depends_on.map(function (dep) {
      const target = DATA.modules.find(function (x) { return x.id === dep; });
      return target ? '<button class="wc-chip clickable" data-goto-module="' + esc(target.id) + '">' + esc(target.name) + '</button>' : '<span class="wc-chip">' + esc(dep) + '</span>';
    }).join(" ");
    const usedBy = m.used_by.map(function (dep) {
      const target = DATA.modules.find(function (x) { return x.id === dep; });
      return target ? '<button class="wc-chip clickable" data-goto-module="' + esc(target.id) + '">' + esc(target.name) + '</button>' : "";
    }).join(" ");
    const body = '<p>' + esc(m.role || "未填写职责") + '</p>' +
      '<h4>职责</h4>' + (m.responsibilities.length ? '<ul>' + m.responsibilities.map(function (r) { return '<li>' + esc(r) + '</li>'; }).join("") + '</ul>' : '<p class="wc-muted">未记录。</p>') +
      '<h4>位置</h4><p>' + copyPath(m.path) + '</p>' +
      (m.key_files.length ? '<h4>关键文件</h4><div class="wc-table-wrap"><table class="wc-table"><tbody>' + m.key_files.map(function (f) {
        return '<tr><td>' + copyPath(f.path) + '</td><td>' + esc(f.purpose || "") + '</td></tr>';
      }).join("") + '</tbody></table></div>' : "") +
      '<h4>依赖</h4><p>' + (deps || '<span class="wc-muted">无内部依赖</span>') + '</p>' +
      '<h4>被谁使用</h4><p>' + (usedBy || '<span class="wc-muted">无记录</span>') + '</p>' +
      '<h4>证据</h4>' + (m.evidence.length ? '<ul>' + m.evidence.map(function (e) { return '<li>' + copyPath(e) + '</li>'; }).join("") + '</ul>' : '<p class="wc-muted">未附证据。</p>') +
      (m.notes ? '<h4>备注</h4><p>' + esc(m.notes) + '</p>' : "") +
      '<div class="wc-meta" style="margin-top:18px">' + confidenceBadge(m.confidence) + '<span>模块 ' + esc(m.id) + '</span></div>';
    drawer(m.name, m.path, body);
  }
  function openFeature(id) {
    const f = DATA.features.find(function (x) { return x.id === id; });
    if (!f) return;
    const domain = (DATA.domains.find(function (d) { return d.id === f.domain; }) || {}).name || f.domain;
    const body = '<p>' + esc(f.summary || "未填写功能说明") + '</p>' +
      (f.user_value ? '<h4>用户价值</h4><p>' + esc(f.user_value) + '</p>' : "") +
      '<h4>状态</h4><p>' + badge(f.status === "implemented" ? "已实现" : f.status === "planned" ? "规划中" : "部分实现", f.status === "implemented" ? "ok" : f.status === "planned" ? "info" : "warn") +
      ' ' + confidenceBadge(f.confidence) + (f.priority ? ' ' + badge(f.priority) : "") + '</p>' +
      (f.entry_points.length ? '<h4>入口</h4><ul>' + f.entry_points.map(function (e) { return '<li>' + copyPath(e) + '</li>'; }).join("") + '</ul>' : "") +
      (f.user_flow.length ? '<h4>用户路径</h4><ol class="wc-timeline">' + f.user_flow.map(function (step, index) { return '<li class="wc-step" data-index="' + (index + 1) + '"><p>' + esc(step) + '</p></li>'; }).join("") + '</ol>' : "") +
      ((f.inputs.length || f.outputs.length) ? '<h4>输入 / 输出</h4><p><strong>输入：</strong>' + esc(f.inputs.join("、") || "—") + '<br><strong>输出：</strong>' + esc(f.outputs.join("、") || "—") + '</p>' : "") +
      (f.dependencies.length ? '<h4>依赖功能</h4><p>' + f.dependencies.map(function (dep) {
        const target = DATA.features.find(function (x) { return x.id === dep; });
        return target ? '<button class="wc-chip clickable" data-goto-feature="' + esc(target.id) + '">' + esc(target.name) + '</button>' : '<span class="wc-chip">' + esc(dep) + '</span>';
      }).join(" ") + '</p>' : "") +
      (f.tests.length ? '<h4>测试</h4><ul>' + f.tests.map(function (t) { return '<li>' + copyPath(t) + '</li>'; }).join("") + '</ul>' : '<h4>测试</h4><p class="wc-muted">未记录测试文件或验证步骤。</p>') +
      '<h4>证据</h4>' + (f.evidence.length ? '<ul>' + f.evidence.map(function (e) { return '<li>' + copyPath(e) + '</li>'; }).join("") + '</ul>' : '<p class="wc-muted">未附证据。</p>') +
      (f.notes ? '<h4>备注</h4><p>' + esc(f.notes) + '</p>' : "") +
      '<div class="wc-meta" style="margin-top:18px"><span>' + esc(domain || "未分组") + '</span><span>功能 ' + esc(f.id) + '</span></div>';
    drawer(f.name, domain || "", body);
  }

  /* ---------------------------------------------------------------- filters */
  function applyModuleFilter() {
    const grid = WC.byId("module-grid");
    if (!grid) return;
    const q = state.moduleQuery.trim().toLowerCase();
    let visible = 0;
    grid.querySelectorAll(".module-card").forEach(function (card) {
      const matchQ = !q || card.getAttribute("data-name").indexOf(q) >= 0;
      const matchL = state.layer === "all" || card.getAttribute("data-layer") === state.layer;
      const show = matchQ && matchL;
      card.classList.toggle("wc-hide", !show);
      if (show) visible += 1;
    });
    const count = WC.byId("module-visible-count");
    if (count) count.textContent = visible + " 个模块";
    const emptyNode = WC.byId("module-empty");
    if (emptyNode) emptyNode.classList.toggle("wc-hide", visible !== 0);
  }
  function applyFeatureFilter() {
    const grid = WC.byId("feature-grid");
    if (!grid) return;
    const q = state.featureQuery.trim().toLowerCase();
    let visible = 0;
    grid.querySelectorAll(".feature-card").forEach(function (card) {
      const matchQ = !q || card.getAttribute("data-name").indexOf(q) >= 0;
      const matchS = state.status === "all" || card.getAttribute("data-status") === state.status;
      const matchD = state.domain === "all" || card.getAttribute("data-domain") === state.domain;
      const show = matchQ && matchS && matchD;
      card.classList.toggle("wc-hide", !show);
      if (show) visible += 1;
    });
    const count = WC.byId("feature-count");
    if (count) count.textContent = visible + " 项功能";
    const emptyNode = WC.byId("feature-empty");
    if (emptyNode) emptyNode.classList.toggle("wc-hide", visible !== 0);
  }
  function applyFileFilter() {
    const body = WC.byId("file-body");
    if (!body) return;
    const q = state.fileQuery.trim().toLowerCase();
    let visible = 0;
    body.querySelectorAll("tr").forEach(function (row) {
      const show = !q || row.getAttribute("data-name").indexOf(q) >= 0;
      row.classList.toggle("wc-hide", !show);
      if (show) visible += 1;
    });
    const count = WC.byId("file-count");
    if (count) count.textContent = visible + " 个文件";
    const emptyNode = WC.byId("file-empty");
    if (emptyNode) emptyNode.classList.toggle("wc-hide", visible !== 0);
  }
  function applyDecisionFilter() {
    document.querySelectorAll("#decision-grid .decision-card").forEach(function (card) {
      card.classList.toggle("wc-hide", !!state.decisionQuery && card.getAttribute("data-name").indexOf(state.decisionQuery.toLowerCase()) < 0);
    });
  }

  /* ---------------------------------------------------------------- graph interactions */
  function bindGraph() {
    const svg = WC.byId("graph-svg");
    const wrap = WC.byId("graph-wrap");
    if (!svg || !wrap) return;
    const layout = layoutGraph();
    let view = { x: 0, y: 0, w: layout.W, h: layout.H };
    let drag = null;
    let lastMoved = false;
    function apply() { svg.setAttribute("viewBox", view.x + " " + view.y + " " + view.w + " " + view.h); }
    function reset() { view = { x: 0, y: 0, w: layout.W, h: layout.H }; apply(); }
    function zoom(factor, cx, cy) {
      const nw = Math.max(layout.W * 0.25, Math.min(layout.W * 3, view.w * factor));
      const ratio = nw / view.w;
      const px = cx == null ? view.x + view.w / 2 : cx;
      const py = cy == null ? view.y + view.h / 2 : cy;
      view.x = px - (px - view.x) * ratio;
      view.y = py - (py - view.y) * ratio;
      view.w = nw;
      view.h = nw * (layout.H / layout.W);
      apply();
    }
    function worldPoint(event) {
      const rect = svg.getBoundingClientRect();
      return {
        x: view.x + ((event.clientX - rect.left) / rect.width) * view.w,
        y: view.y + ((event.clientY - rect.top) / rect.height) * view.h
      };
    }
    svg.addEventListener("wheel", function (event) {
      event.preventDefault();
      const p = worldPoint(event);
      zoom(event.deltaY > 0 ? 1.14 : 0.88, p.x, p.y);
    }, { passive: false });
    svg.addEventListener("pointerdown", function (event) {
      if (event.target.closest(".node")) return;
      drag = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y, moved: false };
      svg.classList.add("dragging");
      svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener("pointermove", function (event) {
      if (!drag) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      view.x = drag.vx - (dx / svg.getBoundingClientRect().width) * view.w;
      view.y = drag.vy - (dy / svg.getBoundingClientRect().height) * view.h;
      apply();
    });
    function endDrag() {
      if (!drag) return;
      lastMoved = drag.moved;
      drag = null;
      svg.classList.remove("dragging");
    }
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointercancel", endDrag);
    svg.querySelectorAll("[data-graph-node]").forEach(function (node) {
      node.addEventListener("mouseenter", function () {
        const id = node.getAttribute("data-graph-node");
        svg.querySelectorAll(".node").forEach(function (n) {
          const nid = n.getAttribute("data-graph-node");
          n.classList.toggle("hot", nid === id);
          n.classList.toggle("dim", nid !== id && !connected(id, nid));
        });
        svg.querySelectorAll(".edge").forEach(function (edge) {
          const hot = edge.getAttribute("data-from") === id || edge.getAttribute("data-to") === id;
          edge.classList.toggle("hot", hot);
          edge.classList.toggle("dim", !hot);
        });
      });
      node.addEventListener("mouseleave", function () {
        svg.querySelectorAll(".node").forEach(function (n) { n.classList.remove("hot", "dim"); });
        svg.querySelectorAll(".edge").forEach(function (e) { e.classList.remove("hot", "dim"); });
      });
    });
    svg.addEventListener("click", function (event) {
      if (lastMoved) { lastMoved = false; return; }
      const node = event.target.closest("[data-graph-node]");
      if (node) openModule(node.getAttribute("data-graph-node"));
    });
    wrap.querySelectorAll("[data-zoom]").forEach(function (button) {
      button.addEventListener("click", function () {
        const action = button.getAttribute("data-zoom");
        if (action === "in") zoom(0.82);
        else if (action === "out") zoom(1.2);
        else reset();
      });
    });
    apply();
  }
  function connected(a, b) {
    return DATA.modules.some(function (m) {
      return (m.id === a && m.depends_on.indexOf(b) >= 0) || (m.id === b && m.depends_on.indexOf(a) >= 0);
    });
  }

  /* ---------------------------------------------------------------- render */
  function render() {
    let content = "";
    switch (state.tab) {
      case "modules": content = modulesTab(); break;
      case "flows": content = flowsTab(); break;
      case "decisions": content = decisionsTab(); break;
      case "risks": content = risksTab(); break;
      case "files": content = filesTab(); break;
      case "features": content = featuresTab(); break;
      case "matrix": content = matrixTab(); break;
      case "journeys": content = journeysTab(); break;
      case "questions": content = questionsTab(); break;
      case "glossary": content = glossaryTab(); break;
      default: content = overview();
    }
    app.innerHTML = hero() + kpis() + tabbar() + content;
    WC.bindCopy(app);
    if (state.tab === "modules") {
      const search = WC.byId("module-search");
      if (search) {
        search.addEventListener("input", function () { state.moduleQuery = search.value; applyModuleFilter(); });
        applyModuleFilter();
      }
      if (state.graph) bindGraph();
    }
    if (state.tab === "features") {
      const search = WC.byId("feature-search");
      if (search) {
        search.addEventListener("input", function () { state.featureQuery = search.value; applyFeatureFilter(); });
      }
      const select = WC.byId("feature-domain");
      if (select) {
        select.value = state.domain;
        select.addEventListener("change", function () { state.domain = select.value; applyFeatureFilter(); });
      }
      applyFeatureFilter();
    }
    if (state.tab === "files") {
      const search = WC.byId("file-search");
      if (search) {
        search.addEventListener("input", function () { state.fileQuery = search.value; applyFileFilter(); });
      }
      applyFileFilter();
    }
    if (state.tab === "decisions") {
      const search = WC.byId("decision-search");
      if (search) {
        search.addEventListener("input", function () { state.decisionQuery = search.value; applyDecisionFilter(); });
      }
      applyDecisionFilter();
    }
    review.sections = tabs().map(function (tab) { return { id: tab.id, label: tab.label }; });
    review.renderStatus();
  }

  function setTab(tab, updateHash) {
    state.tab = tab;
    if (updateHash !== false) {
      try { history.replaceState(null, "", "#" + tab); } catch (err) {}
    }
    render();
    const nav = document.querySelector(".wc-tabs");
    if (nav) nav.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------------------------------------------------------------- events */
  function bindEvents() {
    app.addEventListener("click", function (event) {
      const tab = event.target.closest("[data-tab]");
      if (tab) { setTab(tab.getAttribute("data-tab")); return; }
      const jump = event.target.closest("[data-jump-tab]");
      if (jump) { setTab(jump.getAttribute("data-jump-tab")); return; }
      const moduleNode = event.target.closest("[data-module]");
      if (moduleNode) { openModule(moduleNode.getAttribute("data-module")); return; }
      const featureNode = event.target.closest("[data-feature]");
      if (featureNode) { openFeature(featureNode.getAttribute("data-feature")); return; }
      const flow = event.target.closest("[data-flow]");
      if (flow) { state.flow = flow.getAttribute("data-flow"); render(); return; }
      const layer = event.target.closest("[data-layer]");
      if (layer) { state.layer = layer.getAttribute("data-layer"); render(); return; }
      const status = event.target.closest("[data-status]");
      if (status) { state.status = status.getAttribute("data-status"); render(); return; }
      const matrix = event.target.closest("[data-matrix]");
      if (matrix) {
        const parts = matrix.getAttribute("data-matrix").split("|");
        state.domain = parts[0];
        state.status = parts[1];
        setTab("features");
        return;
      }
      const graph = event.target.closest("[data-graph]");
      if (graph) { state.graph = graph.getAttribute("data-graph") === "1"; render(); return; }
      const drawerClose = event.target.closest("[data-close-drawer]");
      if (drawerClose) { closeDrawer(); return; }
      const copy = event.target.closest("[data-copy]");
      if (copy) { WC.copy(copy.getAttribute("data-copy")); return; }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeDrawer();
      const card = event.target.closest && event.target.closest(".module-card, .feature-card");
      if (card && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        if (card.hasAttribute("data-module")) openModule(card.getAttribute("data-module"));
        else openFeature(card.getAttribute("data-feature"));
      }
    });
    const overlay = WC.byId("wc-overlay");
    if (overlay) overlay.addEventListener("click", closeDrawer);
    window.addEventListener("hashchange", function () {
      const tab = location.hash.replace("#", "");
      if (tabs().some(function (t) { return t.id === tab; })) setTab(tab, false);
    });
  }

  /* ---------------------------------------------------------------- boot */
  initChrome();
  review.bind();
  bindEvents();
  const initial = location.hash.replace("#", "");
  if (tabs().some(function (tab) { return tab.id === initial; })) state.tab = initial;
  try {
    const params = new URLSearchParams(location.search);
    if (params.get("graph") === "1") {
      state.tab = "modules";
      state.graph = true;
    }
  } catch (err) { /* ignore */ }
  render();
})();
