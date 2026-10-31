/* Programmer Workflow · interactive Prototype.html */
(function () {
  "use strict";
  const PAGE = JSON.parse(document.getElementById("wc-data").textContent);
  const DATA = PAGE.data;
  const esc = WC.escape;
  const state = {
    direction: 0,
    screen: 0,
    device: (DATA.directions[0].screens[0] || {}).device || "desktop",
    annotate: false
  };

  function currentDirection() { return DATA.directions[state.direction]; }
  function currentScreen() {
    const direction = currentDirection();
    return direction.screens[Math.min(state.screen, direction.screens.length - 1)];
  }
  function reviewSections() {
    const sections = [{ id: "overall", label: "整体方向" }];
    DATA.directions.forEach(function (direction) {
      sections.push({ id: direction.id, label: "方向 " + direction.id + " · " + direction.name });
      direction.screens.forEach(function (screen) {
        sections.push({ id: direction.id + "/" + screen.id, label: "  " + screen.name });
      });
    });
    return sections;
  }
  const review = new WC.Review({
    kind: "prototype",
    title: PAGE.title,
    specHash: DATA.spec_hash || "",
    sections: reviewSections()
  });
  review.onChange = function () {
    renderPins();
    renderInspector();
  };

  /* ---------------------------------------------------------------- brief */
  function renderBrief() {
    const brief = DATA.brief || {};
    const node = WC.byId("proto-brief");
    if (!node) return;
    const assumptions = DATA.assumptions || [];
    node.innerHTML = '<h3>设计简报</h3>' +
      (brief.goal ? '<p class="brief-goal">' + esc(brief.goal) + '</p>' : "") +
      '<div class="wc-meta" style="margin-top:0;margin-bottom:8px">' +
      (brief.audience ? '<span>受众：' + esc(brief.audience) + '</span>' : "") +
      (brief.platform ? '<span>平台：' + esc(brief.platform) + '</span>' : "") + '</div>' +
      (brief.constraints && brief.constraints.length ? '<div class="inspector-block"><h4>约束</h4><ul class="brief-list">' + brief.constraints.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join("") + '</ul></div>' : "") +
      (brief.success_criteria && brief.success_criteria.length ? '<div class="inspector-block"><h4>成功标准</h4><ul class="brief-list">' + brief.success_criteria.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join("") + '</ul></div>' : "") +
      (assumptions.length ? '<div class="inspector-block"><h4>我的假设（可改）</h4><ul class="brief-list">' + assumptions.map(function (a) { return '<li>' + esc(a) + '</li>'; }).join("") + '</ul></div>' : "") +
      '<div class="wc-meta" style="margin-top:8px">' + (DATA.project.confidence ? '<span class="wc-badge info">' + esc(DATA.project.confidence === "high" ? "高置信" : DATA.project.confidence === "low" ? "低置信" : "中置信") + '</span>' : "") + '<span>' + esc(DATA.project.generated_at ? WC.formatDate(DATA.project.generated_at) : "") + '</span></div>';
  }

  /* ---------------------------------------------------------------- navigation */
  function renderDirections() {
    const node = WC.byId("proto-directions");
    if (!node) return;
    node.innerHTML = '<h3>设计方向 · ' + DATA.directions.length + '</h3><div class="direction-tabs">' +
      DATA.directions.map(function (direction, index) {
        return '<button class="direction-tab ' + (index === state.direction ? "active" : "") + '" data-direction="' + index + '"><strong>' + esc(direction.id + " · " + direction.name) + '</strong><span>' + esc(direction.thesis || direction.when_to_use || "") + '</span></button>';
      }).join("") + '</div>';
  }

  function renderScreens() {
    const node = WC.byId("proto-screens");
    if (!node) return;
    const direction = currentDirection();
    node.innerHTML = '<h3>界面 · ' + direction.screens.length + '</h3><div class="screen-tabs">' +
      direction.screens.map(function (screen, index) {
        return '<button class="screen-tab ' + (index === state.screen ? "active" : "") + '" data-screen="' + index + '"><span class="idx">' + (index + 1) + '</span><span>' + esc(screen.name) + '</span><span class="dev">' + esc(screen.device) + '</span></button>';
      }).join("") + '</div>' +
      '<div class="wc-note" style="margin-top:10px">这是静态视觉原型，不是可运行产品。交互只在当前页面（切换、标注、评审）生效。</div>';
  }

  /* ---------------------------------------------------------------- inspector */
  function renderInspector() {
    const node = WC.byId("proto-inspector");
    if (!node) return;
    const direction = currentDirection();
    const palette = (direction.palette || []).map(function (color) {
      return '<button class="swatch" data-copy="' + esc(color.hex) + '" title="复制 ' + esc(color.hex) + '"><i style="background:' + esc(color.hex) + '"></i><span><b>' + esc(color.name || color.role || "颜色") + '</b>' + esc(color.hex) + '</span></button>';
    }).join("");
    const typography = (direction.typography || []).map(function (type) {
      return '<div class="type-row" style="font-family:' + esc(type.family || "inherit") + '"><b>' + esc(type.name || "文本") + '</b><span>' + esc(type.family || "") + ' · ' + esc(type.size || "") + ' · ' + esc(type.weight || "") + '</span></div>';
    }).join("");
    const pins = review.state.pins.filter(function (pin) {
      return pin.direction === direction.id && pin.screen === currentScreen().id;
    });
    node.innerHTML = '<h3>设计说明</h3>' +
      (direction.thesis ? '<p>' + esc(direction.thesis) + '</p>' : "") +
      (direction.when_to_use ? '<div class="wc-note" style="margin-top:8px">适合：' + esc(direction.when_to_use) + '</div>' : "") +
      (palette ? '<div class="inspector-block"><h4>色板（点击复制）</h4><div class="swatches">' + palette + '</div></div>' : "") +
      (typography ? '<div class="inspector-block"><h4>字体</h4>' + typography + '</div>' : "") +
      (direction.components && direction.components.length ? '<div class="inspector-block"><h4>组件</h4><div class="chip-list">' + direction.components.map(function (c) { return '<span class="wc-chip">' + esc(c) + '</span>'; }).join("") + '</div></div>' : "") +
      (direction.motion ? '<div class="inspector-block"><h4>动效</h4><p>' + esc(direction.motion) + '</p></div>' : "") +
      (direction.risks && direction.risks.length ? '<div class="inspector-block"><h4>风险</h4><ul class="brief-list">' + direction.risks.map(function (r) { return '<li>' + esc(r) + '</li>'; }).join("") + '</ul></div>' : "") +
      '<div class="inspector-block"><h4>本屏标注 · ' + pins.length + '</h4>' +
      (pins.length ? '<div class="pin-list">' + pins.map(function (pin, index) {
        return '<div class="pin-item"><b>#' + (index + 1) + '</b><span>' + esc(pin.note) + '</span><button data-del-pin="' + esc(pin.id) + '" title="删除">✕</button></div>';
      }).join("") + '</div>' : '<p class="wc-dim">还没有标注。打开“标注模式”后点击画布。</p>') + '</div>' +
      (DATA.questions && DATA.questions.length ? '<div class="inspector-block"><h4>待你确认</h4>' + DATA.questions.map(function (q) {
        return '<div class="wc-note" style="margin-bottom:6px"><div>' + esc(q.question) + '</div><button class="wc-copy" data-copy="' + esc(q.question + (q.options && q.options.length ? "\n选项：" + q.options.join(" / ") : "")) + '">复制问题</button></div>';
      }).join("") + '</div>' : "");
    WC.bindCopy(node);
  }

  /* ---------------------------------------------------------------- stage */
  function renderStage() {
    const device = WC.byId("proto-device");
    const screen = WC.byId("proto-screen");
    const meta = WC.byId("proto-screen-meta");
    const url = WC.byId("proto-url");
    if (!device || !screen) return;
    const direction = currentDirection();
    const current = currentScreen();
    device.setAttribute("data-device", state.device);
    screen.innerHTML = current.html || '<div style="padding:40px;font-family:system-ui;color:#64748b">这个界面没有提供 HTML。请检查 spec 的 directions[].screens[].html。</div>';
    screen.scrollTop = 0;
    if (url) url.textContent = "prototype.local/" + direction.id.toLowerCase() + "/" + current.id;
    if (meta) meta.innerHTML = '<span>方向 ' + esc(direction.id) + '</span><span class="dot">' + esc(current.name) + '</span><span class="dot">' + esc(state.device) + '</span>';
    document.querySelectorAll("#proto-viewport [data-device]").forEach(function (button) {
      button.classList.toggle("active", button.getAttribute("data-device") === state.device);
    });
    renderPins();
  }

  function renderPins() {
    const layer = WC.byId("proto-pins");
    if (!layer) return;
    const direction = currentDirection();
    const screen = currentScreen();
    const pins = review.state.pins.filter(function (pin) {
      return pin.direction === direction.id && pin.screen === screen.id;
    });
    layer.classList.toggle("annotate", state.annotate);
    layer.innerHTML = pins.map(function (pin, index) {
      return '<button class="pin" style="left:' + Number(pin.x) + '%;top:' + Number(pin.y) + '%" data-pin-id="' + esc(pin.id) + '" title="' + esc(pin.note) + '">' + (index + 1) + '</button>';
    }).join("");
  }

  function setAnnotate(enabled) {
    state.annotate = enabled;
    const button = WC.byId("proto-annotate");
    const canvas = WC.byId("proto-canvas");
    if (button) button.setAttribute("aria-pressed", String(enabled));
    if (button) button.classList.toggle("primary", enabled);
    if (canvas) canvas.classList.toggle("annotate", enabled);
    renderPins();
    if (enabled) WC.toast("标注模式：点击画布添加留言");
  }

  /* ---------------------------------------------------------------- pins */
  function pinModal(x, y) {
    const textarea = WC.el("textarea", { class: "wc-textarea", rows: "5", placeholder: "这里是什么问题？期望改成什么？" });
    const body = WC.el("div", {}, [
      WC.el("p", { class: "wc-muted", style: "margin:0 0 8px", text: "标注位置：" + Math.round(x) + "% / " + Math.round(y) + "%" }),
      textarea
    ]);
    WC.modal({
      title: "添加画布标注",
      description: "标注会保存在本机浏览器，并随评审 JSON 一起导出。",
      body: body,
      actions: [
        { label: "取消" },
        {
          label: "保存标注", className: "primary",
          onClick: function () {
            const note = textarea.value.trim();
            if (!note) { WC.toast("请先写标注内容"); textarea.focus(); return false; }
            review.addPin({ direction: currentDirection().id, screen: currentScreen().id, x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10, note: note });
            WC.toast("标注已保存");
          }
        }
      ]
    });
  }

  function showPin(pin) {
    const body = WC.el("div", {}, [
      WC.el("p", { text: pin.note }),
      WC.el("div", { class: "wc-meta" }, [WC.el("span", { text: pin.direction + " / " + pin.screen }), WC.el("span", { text: WC.formatDate(pin.created_at) })])
    ]);
    WC.modal({
      title: "标注",
      body: body,
      actions: [
        { label: "关闭" },
        {
          label: "删除标注", className: "danger",
          onClick: function () { review.removePin(pin.id); WC.toast("标注已删除"); }
        }
      ]
    });
  }

  /* ---------------------------------------------------------------- copy */
  function briefMarkdown() {
    const brief = DATA.brief || {};
    const lines = ["# " + DATA.project.name + " · 设计原型", ""];
    if (brief.goal) lines.push("**目标：** " + brief.goal, "");
    if (brief.audience) lines.push("**受众：** " + brief.audience);
    if (brief.platform) lines.push("**平台：** " + brief.platform);
    lines.push("", "## 方向");
    DATA.directions.forEach(function (direction) {
      lines.push("### " + direction.id + " · " + direction.name);
      if (direction.thesis) lines.push(direction.thesis);
      if (direction.when_to_use) lines.push("适合：" + direction.when_to_use);
      lines.push("");
    });
    if (DATA.assumptions.length) {
      lines.push("## 我的假设（请确认或否定）");
      DATA.assumptions.forEach(function (assumption) { lines.push("- " + assumption); });
    }
    if (DATA.questions.length) {
      lines.push("", "## 需要你拍板");
      DATA.questions.forEach(function (q) { lines.push("- " + q.question + (q.default ? "（默认：" + q.default + "）" : "")); });
    }
    return lines.join("\n");
  }

  /* ---------------------------------------------------------------- render */
  function renderAll() {
    renderBrief();
    renderDirections();
    renderScreens();
    renderInspector();
    renderStage();
    review.renderStatus();
  }

  function selectDirection(index) {
    state.direction = index;
    state.screen = 0;
    state.device = currentScreen().device || "desktop";
    renderAll();
    updateHash();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectScreen(index) {
    state.screen = index;
    state.device = currentScreen().device || "desktop";
    renderScreens();
    renderInspector();
    renderStage();
    updateHash();
  }

  function updateHash() {
    try {
      const hash = "#" + currentDirection().id + "/" + currentScreen().id;
      if (location.hash !== hash) history.replaceState(null, "", hash);
    } catch (err) { /* file:// browsers may disallow history; ignore */ }
  }

  function applyHash() {
    const raw = location.hash.replace(/^#/, "");
    if (!raw) return;
    const parts = raw.split("/");
    const directionIndex = DATA.directions.findIndex(function (direction) { return direction.id === parts[0]; });
    if (directionIndex < 0) return;
    state.direction = directionIndex;
    const screenIndex = currentDirection().screens.findIndex(function (screen) { return screen.id === parts[1]; });
    state.screen = screenIndex >= 0 ? screenIndex : 0;
    state.device = currentScreen().device || "desktop";
  }

  /* ---------------------------------------------------------------- events */
  function bind() {
    document.addEventListener("click", function (event) {
      const direction = event.target.closest("[data-direction]");
      if (direction) { selectDirection(Number(direction.getAttribute("data-direction"))); return; }
      const screen = event.target.closest("[data-screen]");
      if (screen) { selectScreen(Number(screen.getAttribute("data-screen"))); return; }
      const device = event.target.closest("#proto-viewport [data-device]");
      if (device) { state.device = device.getAttribute("data-device"); renderStage(); return; }
      const del = event.target.closest("[data-del-pin]");
      if (del) { review.removePin(del.getAttribute("data-del-pin")); WC.toast("标注已删除"); return; }
      const pin = event.target.closest("[data-pin-id]");
      if (pin) {
        const found = review.state.pins.find(function (item) { return item.id === pin.getAttribute("data-pin-id"); });
        if (found) showPin(found);
        return;
      }
      const copy = event.target.closest("[data-copy]");
      if (copy) { WC.copy(copy.getAttribute("data-copy")); return; }
    });

    const annotate = WC.byId("proto-annotate");
    if (annotate) annotate.addEventListener("click", function () { setAnnotate(!state.annotate); });

    const layer = WC.byId("proto-pins");
    if (layer) layer.addEventListener("click", function (event) {
      if (!state.annotate) return;
      if (event.target.closest(".pin")) return;
      const screen = WC.byId("proto-screen");
      if (!screen) return;
      const rect = screen.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) return;
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      pinModal(x, y);
    });

    const copyBrief = WC.byId("wc-copy-brief");
    if (copyBrief) copyBrief.addEventListener("click", function () { WC.copy(briefMarkdown()); });

    review.bind();
    window.addEventListener("hashchange", function () {
      applyHash();
      renderAll();
    });
  }

  document.documentElement.lang = (DATA.project && DATA.project.language) || "zh-CN";
  if (DATA.project && DATA.project.name) {
    document.title = "设计原型 · " + DATA.project.name;
    const title = WC.byId("proto-title");
    if (title) title.textContent = document.title;
    const project = WC.byId("proto-project");
    if (project) project.textContent = DATA.project.name;
    const generated = WC.byId("proto-generated");
    if (generated) generated.textContent = WC.formatDate(PAGE.generated_at);
  }
  applyHash();
  bind();
  renderAll();
})();
