/* Programmer Workflow · shared review + UI helpers (no dependencies) */
(function () {
  "use strict";
  const WC = (window.WC = window.WC || {});

  WC.escape = function (value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  };
  WC.byId = function (id) { return document.getElementById(id); };
  WC.el = function (tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        const value = attrs[key];
        if (value == null || value === false) return;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "html") node.innerHTML = value;
        else if (key === "dataset") Object.keys(value).forEach(function (k) { node.dataset[k] = value[k]; });
        else if (key.indexOf("on") === 0 && typeof value === "function") node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value === true ? "" : value);
      });
    }
    (children || []).forEach(function (child) {
      if (child == null) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  };
  WC.formatDate = function (iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("zh-CN", { hour12: false });
    } catch (err) { return String(iso); }
  };
  WC.copy = async function (text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      WC.toast("已复制到剪贴板");
      return true;
    } catch (err) {
      WC.toast("复制失败，请手动选择文本");
      return false;
    }
  };
  WC.download = function (filename, text, mime) {
    const blob = new Blob([text], { type: mime || "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  };
  let toastTimer = null;
  WC.toast = function (message) {
    const node = WC.byId("wc-toast");
    if (!node) return;
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove("show"); }, 2200);
  };
  WC.storage = {
    get: function (key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (err) { return fallback; }
    },
    set: function (key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); return true; }
      catch (err) { return false; }
    },
    remove: function (key) { try { localStorage.removeItem(key); } catch (err) {} }
  };

  /* ---- modal ---------------------------------------------------------- */
  let modalCleanup = null;
  WC.modal = function (options) {
    const wrap = WC.byId("wc-modal");
    const title = WC.byId("wc-modal-title");
    const desc = WC.byId("wc-modal-desc");
    const body = WC.byId("wc-modal-body");
    const actions = WC.byId("wc-modal-actions");
    if (!wrap) return;
    title.textContent = options.title || "";
    desc.textContent = options.description || "";
    desc.classList.toggle("wc-hide", !options.description);
    body.innerHTML = "";
    if (options.body) body.appendChild(options.body);
    actions.innerHTML = "";
    (options.actions || [{ label: "关闭" }]).forEach(function (action) {
      const button = WC.el("button", {
        class: "wc-btn small " + (action.className || ""),
        text: action.label || "确定",
        onclick: function () {
          if (action.onClick) {
            const result = action.onClick();
            if (result === false) return;
          }
          WC.closeModal();
        }
      });
      actions.appendChild(button);
    });
    wrap.classList.add("open");
    document.body.style.overflow = "hidden";
    const first = body.querySelector("input, textarea, select, button");
    if (first) setTimeout(function () { first.focus(); }, 30);
    modalCleanup = function (event) {
      if (event && event.key && event.key !== "Escape") return;
      WC.closeModal();
    };
    document.addEventListener("keydown", modalCleanup);
    wrap.onclick = function (event) { if (event.target === wrap) WC.closeModal(); };
  };
  WC.closeModal = function () {
    const wrap = WC.byId("wc-modal");
    if (!wrap) return;
    wrap.classList.remove("open");
    document.body.style.overflow = "";
    if (modalCleanup) { document.removeEventListener("keydown", modalCleanup); modalCleanup = null; }
  };

  /* ---- copy hooks ----------------------------------------------------- */
  WC.bindCopy = function (root) {
    (root || document).querySelectorAll("[data-copy]").forEach(function (node) {
      if (node.__wcCopy) return;
      node.__wcCopy = true;
      node.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        WC.copy(node.getAttribute("data-copy"));
      });
    });
  };

  /* ---- theme ---------------------------------------------------------- */
  WC.applyTheme = function (theme) {
    document.documentElement.setAttribute("data-theme", theme);
    WC.storage.set("wc-theme", theme);
  };
  WC.initTheme = function () {
    const saved = WC.storage.get("wc-theme", null);
    const preferred = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    WC.applyTheme(saved || preferred);
    const button = WC.byId("wc-theme");
    if (button) button.addEventListener("click", function () {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      WC.applyTheme(next);
      WC.toast(next === "dark" ? "已切换深色主题" : "已切换浅色主题");
    });
  };

  /* ---- review controller --------------------------------------------- */
  function Review(options) {
    this.kind = options.kind || "doc";
    this.title = options.title || document.title;
    this.specHash = options.specHash || "";
    this.sections = options.sections || [];
    this.storageKey = "wc-review:" + this.kind + ":" + this.specHash;
    const saved = WC.storage.get(this.storageKey, null);
    this.state = saved && typeof saved === "object" ? saved : {
      decision: "pending", sections: {}, notes: [], pins: [], updated_at: null
    };
    this.state.notes = Array.isArray(this.state.notes) ? this.state.notes : [];
    this.state.pins = Array.isArray(this.state.pins) ? this.state.pins : [];
    this.onChange = null;
  }
  Review.prototype.save = function () {
    this.state.updated_at = new Date().toISOString();
    const ok = WC.storage.set(this.storageKey, this.state);
    if (!ok) WC.toast("浏览器禁用了本地存储，评审只保留在当前页面");
    this.renderStatus();
    if (this.onChange) this.onChange(this.state);
  };
  Review.prototype.decisionLabel = function () {
    return this.state.decision === "approved" ? "已通过"
      : this.state.decision === "changes_requested" ? "请求修改" : "未提交";
  };
  Review.prototype.renderStatus = function () {
    const node = WC.byId("wc-review-status");
    if (!node) return;
    node.innerHTML = "评审：<strong>" + WC.escape(this.decisionLabel()) + "</strong>";
    if (this.state.notes.length) node.innerHTML += " · " + this.state.notes.length + " 条意见";
    if (this.state.pins.length) node.innerHTML += " · " + this.state.pins.length + " 个标注";
    node.title = "点击查看评审意见";
    node.style.cursor = "pointer";
    node.onclick = this.showNotes.bind(this);
  };
  Review.prototype.approve = function () {
    this.state.decision = "approved";
    this.save();
    WC.toast("已标记为通过；请导出评审 JSON 或复制反馈给 Agent");
  };
  Review.prototype.requestChanges = function () {
    this.state.decision = "changes_requested";
    this.save();
    this.noteModal("blocking");
  };
  Review.prototype.showNotes = function () {
    const self = this;
    const body = WC.el("div");
    if (!this.state.notes.length && !this.state.pins.length) {
      body.appendChild(WC.el("div", { class: "wc-empty", text: "还没有评审意见。点击底部“添加意见”或“请求修改”。" }));
    } else {
      this.state.notes.forEach(function (note, index) {
        const card = WC.el("div", { class: "wc-card", style: "margin-bottom:10px" }, [
          WC.el("div", { class: "wc-card-head" }, [
            WC.el("strong", { text: (index + 1) + ". " + (note.target || "整体") }),
            WC.el("span", { class: "wc-badge " + (note.severity === "blocking" ? "danger" : note.severity === "question" ? "info" : "warn"), text: note.severity === "blocking" ? "必须修改" : note.severity === "question" ? "疑问" : "建议" })
          ]),
          WC.el("p", { text: note.text }),
          WC.el("div", { class: "wc-meta" }, [WC.el("span", { text: WC.formatDate(note.created_at) }), WC.el("button", {
            class: "wc-copy", text: "删除", onclick: function () { self.removeNote(note.id); WC.closeModal(); self.showNotes(); }
          })])
        ]);
        body.appendChild(card);
      });
      if (this.state.pins.length) {
        const list = WC.el("div", {}, [WC.el("h4", { text: "画布标注" })]);
        this.state.pins.forEach(function (pin, index) {
          list.appendChild(WC.el("div", { class: "wc-note", style: "margin-bottom:8px" }, [
            WC.el("strong", { text: "#" + (index + 1) + " " + (pin.direction || "") + " / " + (pin.screen || "") }),
            WC.el("div", { text: pin.note || "" })
          ]));
        });
        body.appendChild(list);
      }
    }
    WC.modal({ title: "评审意见", description: "意见保存在本机浏览器；导出 JSON 后可交给 Agent。", body: body, actions: [{ label: "关闭" }] });
  };
  Review.prototype.noteModal = function (severity) {
    const self = this;
    const form = WC.el("div");
    const targetLabel = WC.el("label", { class: "wc-small wc-muted", text: "针对哪一部分" });
    const select = WC.el("select", { class: "wc-select" });
    (self.sections.length ? self.sections : [{ id: "overall", label: "整体" }]).forEach(function (section) {
      select.appendChild(WC.el("option", { value: section.id, text: section.label }));
    });
    const textLabel = WC.el("label", { class: "wc-small wc-muted", text: "意见", style: "display:block;margin-top:12px" });
    const textarea = WC.el("textarea", { class: "wc-textarea", placeholder: "具体哪里需要改？期望是什么？", rows: "5" });
    const severityLabel = WC.el("label", { class: "wc-small wc-muted", text: "类型", style: "display:block;margin-top:12px" });
    const severitySelect = WC.el("select", { class: "wc-select" });
    [["blocking", "必须修改"], ["suggestion", "建议"], ["question", "疑问"]].forEach(function (item) {
      severitySelect.appendChild(WC.el("option", { value: item[0], text: item[1] }));
    });
    severitySelect.value = severity || "suggestion";
    form.appendChild(targetLabel); form.appendChild(select);
    form.appendChild(textLabel); form.appendChild(textarea);
    form.appendChild(severityLabel); form.appendChild(severitySelect);
    WC.modal({
      title: severity === "blocking" ? "请求修改" : "添加评审意见",
      description: "写清楚位置、现象和期望，Agent 才能直接修改。",
      body: form,
      actions: [
        { label: "取消" },
        {
          label: "保存意见", className: "primary",
          onClick: function () {
            const text = textarea.value.trim();
            if (!text) { WC.toast("请先写意见"); textarea.focus(); return false; }
            self.state.notes.push({
              id: (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now() + Math.random()),
              target: select.value, severity: severitySelect.value, text: text,
              created_at: new Date().toISOString()
            });
            if (severitySelect.value === "blocking") self.state.decision = "changes_requested";
            self.save();
            WC.toast("意见已保存");
          }
        }
      ]
    });
  };
  Review.prototype.removeNote = function (id) {
    this.state.notes = this.state.notes.filter(function (note) { return note.id !== id; });
    this.save();
  };
  Review.prototype.addPin = function (pin) {
    this.state.pins.push(Object.assign({
      id: (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now() + Math.random()),
      created_at: new Date().toISOString()
    }, pin));
    this.save();
  };
  Review.prototype.removePin = function (id) {
    this.state.pins = this.state.pins.filter(function (pin) { return pin.id !== id; });
    this.save();
  };
  Review.prototype.summaryMarkdown = function () {
    const lines = [
      "## " + this.title + " 评审",
      "",
      "- 结论：" + this.decisionLabel(),
      "- 文档标识：" + this.kind + " / " + this.specHash,
      "- 时间：" + new Date().toLocaleString("zh-CN", { hour12: false }),
      ""
    ];
    if (this.state.notes.length) {
      lines.push("### 意见");
      this.state.notes.forEach(function (note, index) {
        lines.push((index + 1) + ". [" + (note.severity || "suggestion") + "] " + (note.target || "整体") + "：" + note.text);
      });
      lines.push("");
    }
    if (this.state.pins.length) {
      lines.push("### 画布标注");
      this.state.pins.forEach(function (pin, index) {
        lines.push((index + 1) + ". " + (pin.direction || "") + " / " + (pin.screen || "") + "： " + (pin.note || ""));
      });
      lines.push("");
    }
    return lines.join("\n");
  };
  Review.prototype.export = function () {
    const payload = {
      schema: 1,
      generator: "programmer-workflow",
      kind: this.kind,
      title: this.title,
      spec_hash: this.specHash,
      decision: this.state.decision,
      sections: this.state.sections,
      notes: this.state.notes,
      pins: this.state.pins,
      reviewed_at: new Date().toISOString(),
      page_url: location.href,
      user_agent: navigator.userAgent
    };
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    WC.download("programmer-workflow-" + this.kind + "-review-" + stamp + ".json", JSON.stringify(payload, null, 2));
    WC.toast("评审 JSON 已下载；把它放回工作区或复制反馈给 Agent");
  };
  Review.prototype.bind = function () {
    const self = this;
    const approve = WC.byId("wc-review-approve");
    const changes = WC.byId("wc-review-changes");
    const note = WC.byId("wc-review-note");
    const exportButton = WC.byId("wc-review-export");
    if (approve) approve.addEventListener("click", function () { self.approve(); });
    if (changes) changes.addEventListener("click", function () { self.requestChanges(); });
    if (note) note.addEventListener("click", function () { self.noteModal("suggestion"); });
    if (exportButton) exportButton.addEventListener("click", function () { self.export(); });
    self.renderStatus();
  };
  WC.Review = Review;
  WC.copyMarkdown = function (text) { return WC.copy(text); };

  document.addEventListener("DOMContentLoaded", function () {
    WC.initTheme();
    const top = WC.byId("wc-top");
    if (top) {
      const onScroll = function () { top.classList.toggle("scrolled", window.scrollY > 8); };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    const print = WC.byId("wc-print");
    if (print) print.addEventListener("click", function () { window.print(); });
  });
})();
