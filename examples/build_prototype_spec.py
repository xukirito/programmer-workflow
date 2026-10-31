#!/usr/bin/env python3
"""Build the example Prototype.html spec.

The example doubles as a visual regression fixture: it exercises dark/light
directions, desktop/mobile viewports, palettes, and annotations.
"""
from __future__ import annotations

import json
from pathlib import Path

DESKTOP_A = r"""
<style>
.pa{--bg:#0a0f1d;--panel:#111a2e;--panel2:#16213a;--line:#24314d;--text:#e9eefb;--muted:#93a3bf;--dim:#667795;--accent:#8aa4ff;--green:#6ee7b7;--amber:#fbbf24;--red:#fb7185;background:var(--bg);color:var(--text);font-family:"Segoe UI","Microsoft YaHei",sans-serif;display:flex;min-height:690px;font-size:13px}
.pa *{box-sizing:border-box}
.pa-side{width:210px;flex:0 0 auto;background:#080d18;border-right:1px solid var(--line);padding:22px 14px;display:flex;flex-direction:column;gap:5px}
.pa-brand{display:flex;align-items:center;gap:10px;padding:0 8px 20px}
.pa-logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(145deg,#8aa4ff,#6ee7b7);display:grid;place-items:center;color:#08101f;font-weight:800;font-size:14px}
.pa-brand b{display:block;font-size:13px;letter-spacing:.02em}
.pa-brand span{display:block;color:var(--dim);font-size:10px;margin-top:2px}
.pa-nav{display:flex;flex-direction:column;gap:3px}
.pa-nav a{display:flex;align-items:center;gap:9px;padding:9px 10px;border-radius:8px;color:var(--muted);text-decoration:none;font-size:12px}
.pa-nav a.on{background:rgba(138,164,255,.13);color:var(--text);box-shadow:inset 2px 0 0 var(--accent)}
.pa-nav i{width:15px;height:15px;border:1.5px solid currentColor;border-radius:4px;opacity:.8}
.pa-nav .dot{width:6px;height:6px;border-radius:50%;background:var(--green);margin-left:auto}
.pa-side-foot{margin-top:auto;padding:12px 10px 0;border-top:1px solid var(--line);color:var(--dim);font-size:10px;line-height:1.6}
.pa-main{flex:1;min-width:0;padding:24px 26px;background:radial-gradient(700px 260px at 20% 0%,rgba(138,164,255,.12),transparent 70%)}
.pa-head{display:flex;align-items:flex-start;gap:16px}
.pa-head h1{margin:0;font-size:23px;letter-spacing:-.03em}
.pa-head p{margin:5px 0 0;color:var(--muted);font-size:12px}
.pa-head .right{margin-left:auto;display:flex;gap:8px;align-items:center}
.pa-btn{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:8px;padding:7px 11px;font-size:11px;font-family:inherit;cursor:pointer}
.pa-btn.primary{background:linear-gradient(145deg,rgba(138,164,255,.32),rgba(138,164,255,.16));border-color:rgba(138,164,255,.5)}
.pa-btn.ghost{background:transparent}
.pa-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:20px 0 16px}
.pa-kpi{background:linear-gradient(160deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:12px;padding:13px 14px}
.pa-kpi span{display:block;color:var(--dim);font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.pa-kpi b{display:block;font-size:25px;letter-spacing:-.03em;margin-top:4px}
.pa-kpi small{color:var(--muted);font-size:10px}
.pa-kpi .up{color:var(--green)}
.pa-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(250px,.75fr);gap:12px}
.pa-card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:15px 16px}
.pa-card h2{margin:0 0 10px;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--dim);display:flex;align-items:center;gap:8px}
.pa-card h2 em{font-style:normal;margin-left:auto;color:var(--accent);font-size:10px;text-transform:none;letter-spacing:0}
.pa-memory{display:flex;gap:11px;padding:10px 0;border-top:1px solid rgba(148,163,184,.1)}
.pa-memory:first-of-type{border-top:0;padding-top:0}
.pa-mem-icon{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:rgba(138,164,255,.13);color:var(--accent);font-size:11px;font-weight:700;flex:0 0 auto}
.pa-memory b{display:block;font-size:12px;font-weight:600}
.pa-memory p{margin:2px 0 0;color:var(--muted);font-size:10.5px;line-height:1.45}
.pa-memory .who{color:var(--dim);font-size:9.5px;margin-top:3px}
.pa-actions{margin-left:auto;display:flex;gap:4px;align-items:center;flex:0 0 auto}
.pa-mini{border:1px solid var(--line);background:transparent;color:var(--muted);border-radius:6px;font-size:9.5px;padding:3px 7px;cursor:pointer;font-family:inherit}
.pa-mini.yes{color:var(--green);border-color:rgba(110,231,183,.3);background:rgba(110,231,183,.08)}
.pa-mini.no{color:var(--red);border-color:rgba(251,113,133,.3);background:rgba(251,113,133,.08)}
.pa-task{display:flex;align-items:center;gap:9px;padding:8px 0;border-top:1px solid rgba(148,163,184,.1);font-size:11.5px}
.pa-task:first-of-type{border-top:0;padding-top:0}
.pa-task .box{width:14px;height:14px;border:1px solid var(--line);border-radius:4px;flex:0 0 auto}
.pa-task.done .box{background:var(--green);border-color:var(--green)}
.pa-task .tag{margin-left:auto;font-size:9px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:1px 6px}
.pa-progress{height:5px;border-radius:999px;background:#1b2740;overflow:hidden;margin-top:10px}
.pa-progress i{display:block;height:100%;width:64%;background:linear-gradient(90deg,var(--accent),var(--green))}
.pa-log{margin-top:12px;border-top:1px solid var(--line);padding-top:11px;font-family:Consolas,monospace;font-size:9.5px;color:var(--dim);line-height:1.75}
.pa-log b{color:var(--amber);font-weight:500}
.pa-log .ok{color:var(--green)}
.pa-log .er{color:var(--red)}
.pa-span{grid-column:1/-1}
.pa-split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pa-review{display:flex;gap:8px;align-items:center;margin-top:10px;padding:10px;border:1px dashed rgba(138,164,255,.28);border-radius:9px;background:rgba(138,164,255,.045);font-size:10.5px;color:var(--muted)}
.pa-review b{color:var(--text)}
.pa-swatches{display:flex;gap:5px;margin-top:8px}
.pa-swatches i{width:22px;height:22px;border-radius:6px;border:1px solid rgba(255,255,255,.15)}
</style>
<div class="pa">
  <aside class="pa-side">
    <div class="pa-brand"><div class="pa-logo">W</div><div><b>Workflow</b><span>COMPANION</span></div></div>
    <nav class="pa-nav">
      <a class="on"><i></i>指挥台</a>
      <a><i></i>记忆库 <span class="dot"></span></a>
      <a><i></i>调试舱</a>
      <a><i></i>工程文档</a>
      <a><i></i>设计原型</a>
    </nav>
    <div class="pa-side-foot">工作区<br><span style="color:#a9b8d4">AI_Skill-Plugin</span><br><br>DSH · 会话 1916d6</div>
  </aside>
  <main class="pa-main">
    <div class="pa-head">
      <div><h1>早上好，今天有 3 条记忆待你定夺。</h1><p>上一轮对话里，Agent 归纳了 5 条习惯，其中 2 条已生效。</p></div>
      <div class="right"><button class="pa-btn ghost">导入证据</button><button class="pa-btn primary">开始复盘</button></div>
    </div>
    <div class="pa-kpis">
      <div class="pa-kpi"><span>待审核记忆</span><b>03</b><small class="up">+2 今日</small></div>
      <div class="pa-kpi"><span>卡壳计数</span><b>1<span style="font-size:12px;color:var(--dim)">/3</span></b><small>尚未触发</small></div>
      <div class="pa-kpi"><span>渲染文档</span><b>2</b><small>Architecture · Features</small></div>
      <div class="pa-kpi"><span>调试日志</span><b>4</b><small class="up">TRIAGE 已生成</small></div>
    </div>
    <div class="pa-grid">
      <section class="pa-card">
        <h2>记忆候选 <em>逐条审批</em></h2>
        <div class="pa-memory"><div class="pa-mem-icon">习</div><div><b>中文沟通，代码与报错保留原文</b><p>来自最近 3 个工作区的对话；你多次要求不要翻译 stack trace。</p><div class="who">置信度 0.92 · 证据 4 处</div></div><div class="pa-actions"><button class="pa-mini yes">保留</button><button class="pa-mini">改</button><button class="pa-mini no">删</button></div></div>
        <div class="pa-memory"><div class="pa-mem-icon">风</div><div><b>先给结论，再展开证据</b><p>你在 6 次长回答后打断并索要“直接说重点”。</p><div class="who">置信度 0.78 · 证据 6 处</div></div><div class="pa-actions"><button class="pa-mini yes">保留</button><button class="pa-mini">改</button><button class="pa-mini no">删</button></div></div>
        <div class="pa-memory"><div class="pa-mem-icon">环</div><div><b>本机是纯开发环境，无硬件</b><p>工作区声明；调试时直接加日志，不等待实机。</p><div class="who">置信度 1.00 · 你亲口说明</div></div><div class="pa-actions"><button class="pa-mini yes">保留</button><button class="pa-mini">改</button><button class="pa-mini no">删</button></div></div>
        <div class="pa-review"><b>批量操作</b><span>全部保留</span><span>·</span><span>逐条审核</span><span style="margin-left:auto">评审记录将写入 MEMORY.md</span></div>
      </section>
      <section class="pa-card">
        <h2>当前任务</h2>
        <div class="pa-task done"><span class="box"></span><span>复现空指针</span><span class="tag">已修</span></div>
        <div class="pa-task"><span class="box"></span><span>补回归测试</span><span class="tag">进行中</span></div>
        <div class="pa-task"><span class="box"></span><span>清理临时 DBG 日志</span><span class="tag">待办</span></div>
        <div class="pa-progress"><i></i></div>
        <div style="display:flex;justify-content:space-between;color:var(--dim);font-size:9.5px;margin-top:5px"><span>本周目标</span><span>64%</span></div>
        <div class="pa-log"><b>[DBG-auth]</b> token=null at login.ts:42<br><span class="er">ERROR</span> TypeError: cannot read 'id'<br><span class="ok">FIX</span> null guard added<br><b>[TRIAGE]</b> 1 signature · 0 regression</div>
      </section>
      <section class="pa-card"><h2>设计评审 <em>Prototype.html</em></h2><div style="display:flex;gap:14px;align-items:center"><div style="flex:1"><b style="font-size:13px">方向 A · 指挥台</b><p style="margin:4px 0 0;color:var(--muted);font-size:10.5px">高密度、深色、适合长时间盯盘；已收到 2 条标注。</p><div class="pa-swatches"><i style="background:#0a0f1d"></i><i style="background:#8aa4ff"></i><i style="background:#6ee7b7"></i><i style="background:#fbbf24"></i></div></div><button class="pa-btn">打开原型</button></div></section>
      <section class="pa-card"><h2>下一步建议</h2><p style="margin:0;color:var(--muted);font-size:11px;line-height:1.6">把“先给结论”写入用户记忆，并在下次架构总结时默认采用“总览 → 模块 → 风险”的结构。</p><div style="display:flex;gap:6px;margin-top:10px"><button class="pa-btn primary">应用建议</button><button class="pa-btn ghost">稍后</button></div></section>
    </div>
  </main>
</div>
"""

MOBILE_A = r"""
<style>
.pam{--bg:#0a0f1d;--panel:#111a2e;--line:#24314d;--text:#e9eefb;--muted:#93a3bf;--dim:#667795;--accent:#8aa4ff;--green:#6ee7b7;background:var(--bg);color:var(--text);font-family:"Segoe UI","Microsoft YaHei",sans-serif;min-height:720px;height:720px;display:flex;flex-direction:column;font-size:13px}
.pam *{box-sizing:border-box}
.pam-status{display:flex;justify-content:space-between;padding:12px 20px 4px;color:var(--dim);font-size:10px}
.pam-head{padding:14px 20px 10px}
.pam-head h1{margin:0;font-size:21px;letter-spacing:-.03em}
.pam-head p{margin:4px 0 0;color:var(--muted);font-size:11px}
.pam-body{padding:6px 16px;display:flex;flex-direction:column;gap:9px;overflow:auto;flex:1}
.pam-card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:13px 14px}
.pam-big{background:linear-gradient(150deg,rgba(138,164,255,.2),rgba(110,231,183,.08)),var(--panel);border-color:rgba(138,164,255,.34)}
.pam-big span{color:var(--dim);font-size:10px;letter-spacing:.07em;text-transform:uppercase}
.pam-big b{display:block;font-size:34px;letter-spacing:-.04em;margin:4px 0 0}
.pam-big small{color:var(--muted);font-size:10px}
.pam-row{display:flex;align-items:center;gap:9px;padding:9px 0;border-top:1px solid rgba(148,163,184,.1);font-size:11.5px}
.pam-row:first-of-type{border-top:0;padding-top:0}
.pam-row .ico{width:26px;height:26px;border-radius:7px;background:rgba(138,164,255,.13);color:var(--accent);display:grid;place-items:center;font-size:10px;font-weight:700;flex:0 0 auto}
.pam-row p{margin:2px 0 0;color:var(--muted);font-size:10px}
.pam-actions{display:flex;gap:5px;margin-left:auto}
.pam-actions button{border:1px solid var(--line);background:transparent;color:var(--muted);border-radius:6px;padding:3px 7px;font-size:9px}
.pam-actions .ok{color:var(--green);border-color:rgba(110,231,183,.3)}
.pam-nav{display:flex;justify-content:space-around;padding:10px 10px 16px;border-top:1px solid var(--line);background:#080d18;color:var(--dim);font-size:9px;text-align:center}
.pam-nav div{display:flex;flex-direction:column;gap:4px;align-items:center}
.pam-nav i{width:16px;height:16px;border:1.5px solid currentColor;border-radius:5px}
.pam-nav .on{color:var(--accent)}
</style>
<div class="pam">
  <div class="pam-status"><span>9:41</span><span>5G · 100%</span></div>
  <div class="pam-head"><h1>记忆待定夺</h1><p>3 条候选 · 2 条已生效</p></div>
  <div class="pam-body">
    <div class="pam-card pam-big"><span>待审核</span><b>03</b><small>来自最近 3 个工作区，逐条保留或删除</small></div>
    <div class="pam-card">
      <div class="pam-row"><div class="ico">习</div><div><b>中文沟通</b><p>代码与报错保留原文</p></div><div class="pam-actions"><button class="ok">保留</button><button>删</button></div></div>
      <div class="pam-row"><div class="ico">风</div><div><b>先给结论</b><p>6 次长回答后被打断</p></div><div class="pam-actions"><button class="ok">保留</button><button>删</button></div></div>
      <div class="pam-row"><div class="ico">环</div><div><b>纯开发环境</b><p>无硬件，调试直接加日志</p></div><div class="pam-actions"><button class="ok">保留</button><button>删</button></div></div>
    </div>
    <div class="pam-card"><div style="display:flex;justify-content:space-between;font-size:10px;color:var(--dim)"><span>本周卡壳</span><span>1 / 3</span></div><div style="height:5px;border-radius:999px;background:#1b2740;margin-top:8px;overflow:hidden"><i style="display:block;height:100%;width:33%;background:linear-gradient(90deg,#8aa4ff,#6ee7b7)"></i></div><p style="color:var(--muted);font-size:10px;margin:8px 0 0">再失败 2 轮将触发“行业做法”询问。</p></div>
  </div>
  <div class="pam-nav"><div class="on"><i></i>指挥台</div><div><i></i>记忆</div><div><i></i>调试</div><div><i></i>文档</div></div>
</div>
"""

DESKTOP_B = r"""
<style>
.pb{--bg:#f7f3ec;--ink:#1f2937;--muted:#6b7280;--line:#e2d8c9;--card:#fffdf8;--terra:#b45309;--teal:#0f766e;--soft:#efe7da;background:var(--bg);color:var(--ink);font-family:"Segoe UI","Microsoft YaHei",sans-serif;display:flex;min-height:690px;font-size:13px}
.pb *{box-sizing:border-box}
.pb-side{width:190px;flex:0 0 auto;padding:26px 20px;border-right:1px solid var(--line);display:flex;flex-direction:column}
.pb-mark{font-family:Georgia,"Songti SC",serif;font-size:19px;letter-spacing:-.02em;line-height:1.15}
.pb-mark span{display:block;color:var(--terra);font-family:"Segoe UI","Microsoft YaHei",sans-serif;font-size:9px;letter-spacing:.18em;margin-top:7px}
.pb-nav{display:flex;flex-direction:column;gap:13px;margin-top:34px;font-size:11.5px;color:var(--muted)}
.pb-nav a{color:inherit;text-decoration:none}
.pb-nav a.on{color:var(--ink);font-weight:650}
.pb-nav a.on::before{content:"";display:inline-block;width:13px;height:1px;background:var(--terra);vertical-align:4px;margin-right:7px}
.pb-side-note{margin-top:auto;padding-top:18px;border-top:1px solid var(--line);font-size:9.5px;color:var(--muted);line-height:1.7}
.pb-main{flex:1;min-width:0;padding:30px 34px}
.pb-head{display:flex;align-items:flex-start;gap:18px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.pb-head h1{margin:0;font-family:Georgia,"Songti SC",serif;font-size:31px;font-weight:500;letter-spacing:-.03em;line-height:1.18}
.pb-head p{margin:8px 0 0;color:var(--muted);font-size:11.5px;max-width:440px;line-height:1.6}
.pb-head .date{margin-left:auto;text-align:right;font-size:10px;color:var(--muted);line-height:1.7}
.pb-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:16px;margin-top:20px}
.pb-block{background:var(--card);border:1px solid var(--line);border-radius:3px;padding:16px 17px}
.pb-block h2{margin:0 0 4px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
.pb-block h2 em{font-style:normal;float:right;color:var(--terra);letter-spacing:0;text-transform:none}
.pb-mem{display:flex;gap:11px;padding:11px 0;border-bottom:1px solid var(--soft);align-items:flex-start}
.pb-mem:last-child{border-bottom:0;padding-bottom:0}
.pb-num{font-family:Georgia,serif;font-size:17px;color:var(--terra);width:18px;flex:0 0 auto;line-height:1.2}
.pb-mem b{font-size:12px;font-weight:650;display:block}
.pb-mem p{margin:3px 0 0;color:var(--muted);font-size:10.5px;line-height:1.55}
.pb-mem .ev{font-size:9px;color:var(--muted);margin-top:4px;letter-spacing:.02em}
.pb-mem .act{margin-left:auto;display:flex;gap:4px;flex:0 0 auto}
.pb-mem .act button{border:1px solid var(--line);background:#fff;border-radius:2px;padding:3px 7px;font-size:9px;cursor:pointer;color:var(--muted)}
.pb-mem .act .keep{background:var(--teal);color:#fff;border-color:var(--teal)}
.pb-quote{font-family:Georgia,"Songti SC",serif;font-size:18px;line-height:1.55;color:var(--ink);margin:8px 0 12px}
.pb-small{color:var(--muted);font-size:10.5px;line-height:1.65}
.pb-rule{height:1px;background:var(--line);margin:13px 0}
.pb-metrics{display:flex;gap:18px;margin-top:6px}
.pb-metric b{display:block;font-family:Georgia,serif;font-size:26px;font-weight:500;color:var(--ink)}
.pb-metric span{font-size:9px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.pb-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:10px}
.pb-tag{font-size:9px;color:var(--teal);border:1px solid rgba(15,118,110,.25);background:rgba(15,118,110,.05);border-radius:999px;padding:2px 7px}
.pb-wide{grid-column:1/-1}
.pb-review{display:flex;align-items:center;gap:10px;padding:12px 0 0;border-top:1px solid var(--line);margin-top:14px;font-size:10.5px;color:var(--muted)}
.pb-review b{color:var(--ink)}
.pb-btn{border:1px solid var(--line);background:#fff;border-radius:3px;padding:6px 10px;font-size:10px;color:var(--ink);cursor:pointer}
.pb-btn.primary{background:var(--ink);border-color:var(--ink);color:#fff}
.pb-swatches{display:flex;gap:5px;margin-top:8px}
.pb-swatches i{width:26px;height:26px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px var(--line)}
</style>
<div class="pb">
  <aside class="pb-side">
    <div class="pb-mark">Workflow<br>Companion<span>WORKING NOTES</span></div>
    <nav class="pb-nav"><a class="on">今日工作台</a><a>记忆审核</a><a>调试笔记</a><a>工程文档</a><a>设计方向</a></nav>
    <div class="pb-side-note">本地优先 · 无云端<br>所有记录可导出<br><br>AI_Skill-Plugin<br>2026 · 秋</div>
  </aside>
  <main class="pb-main">
    <div class="pb-head"><div><h1>把工作流<br>摊开来看。</h1><p>不追着 Agent 问“做到哪了”。记忆、调试、文档与设计，各自有位置，也各自可被否决。</p></div><div class="date">10 / 31<br>周五<br><br>3 条待定夺</div></div>
    <div class="pb-grid">
      <section class="pb-block"><h2>记忆审核 <em>逐条</em></h2>
        <div class="pb-mem"><div class="pb-num">1</div><div><b>中文沟通，代码不翻译</b><p>多次要求保留 stack trace 与报错原文；这条应进入全局记忆。</p><div class="ev">证据 4 处 · 置信度 .92 · 来自对话</div></div><div class="act"><button class="keep">保留</button><button>改</button><button>删</button></div></div>
        <div class="pb-mem"><div class="pb-num">2</div><div><b>先结论，后展开</b><p>长回答被打断 6 次；适合作为回答结构偏好，而不是硬规则。</p><div class="ev">证据 6 处 · 置信度 .78 · 来自对话</div></div><div class="act"><button class="keep">保留</button><button>改</button><button>删</button></div></div>
        <div class="pb-mem"><div class="pb-num">3</div><div><b>纯开发环境，无硬件</b><p>此工作区不等待实机；调试直接加可回滚日志。</p><div class="ev">用户亲口说明 · 置信度 1.00 · 工作区</div></div><div class="act"><button class="keep">保留</button><button>改</button><button>删</button></div></div>
        <div class="pb-review"><b>本次将写入</b> MEMORY.md · 全局 2 条 / 工作区 1 条 <span style="margin-left:auto"><button class="pb-btn">稍后</button> <button class="pb-btn primary">确认选择</button></span></div>
      </section>
      <section class="pb-block"><h2>本周节奏</h2><div class="pb-quote">“先给结论，<br>再给证据。”</div><div class="pb-small">这句话已经出现三次。也许它不只是偏好，而是你希望所有 Agent 共享的工作方式。</div><div class="pb-rule"></div><div class="pb-metrics"><div class="pb-metric"><b>3</b><span>卡壳</span></div><div class="pb-metric"><b>2</b><span>文档</span></div><div class="pb-metric"><b>4</b><span>调试</span></div></div><div class="pb-tags"><span class="pb-tag">记忆审批</span><span class="pb-tag">日志分诊</span><span class="pb-tag">架构总结</span></div></section>
      <section class="pb-block"><h2>正在评审 <em>Prototype</em></h2><div style="display:flex;gap:14px;align-items:center"><div style="flex:1"><div style="font-family:Georgia,serif;font-size:17px">方向 B · 纸感工作台</div><p class="pb-small" style="margin:4px 0 0">暖纸色、编辑排版、低密度；适合需要长时间阅读与思考的场景。</p><div class="pb-swatches"><i style="background:#f7f3ec"></i><i style="background:#b45309"></i><i style="background:#0f766e"></i><i style="background:#1f2937"></i></div></div><button class="pb-btn primary">打开原型</button></div></section>
      <section class="pb-block"><h2>下一步</h2><p class="pb-small" style="margin:0">把“先结论”提升为用户记忆，并在下次架构总结时默认使用“总览 → 模块 → 风险”的结构。设计方向收敛到 B，再补一版移动端。</p><div style="display:flex;gap:6px;margin-top:11px"><button class="pb-btn primary">采纳建议</button><button class="pb-btn">先不改</button></div></section>
    </div>
  </main>
</div>
"""

MOBILE_B = r"""
<style>
.pbm{--bg:#f7f3ec;--ink:#1f2937;--muted:#6b7280;--line:#e2d8c9;--card:#fffdf8;--terra:#b45309;--teal:#0f766e;background:var(--bg);color:var(--ink);font-family:"Segoe UI","Microsoft YaHei",sans-serif;min-height:720px;height:720px;display:flex;flex-direction:column;font-size:13px}
.pbm *{box-sizing:border-box}
.pbm-status{display:flex;justify-content:space-between;padding:12px 20px 2px;color:var(--muted);font-size:10px}
.pbm-head{padding:16px 20px 10px;border-bottom:1px solid var(--line)}
.pbm-head h1{margin:0;font-family:Georgia,"Songti SC",serif;font-size:26px;font-weight:500;letter-spacing:-.03em;line-height:1.2}
.pbm-head p{margin:6px 0 0;color:var(--muted);font-size:10.5px}
.pbm-body{padding:12px 16px;display:flex;flex-direction:column;gap:9px;overflow:auto;flex:1}
.pbm-card{background:var(--card);border:1px solid var(--line);border-radius:2px;padding:13px 14px}
.pbm-card h2{margin:0 0 7px;font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.pbm-card .big{font-family:Georgia,serif;font-size:38px;line-height:1;color:var(--terra)}
.pbm-card p{margin:4px 0 0;color:var(--muted);font-size:10.5px;line-height:1.55}
.pbm-mem{display:flex;gap:9px;padding:9px 0;border-top:1px solid #efe7da;font-size:11px;align-items:flex-start}
.pbm-mem:first-of-type{border-top:0;padding-top:0}
.pbm-mem .n{font-family:Georgia,serif;color:var(--terra);font-size:15px;width:13px;flex:0 0 auto}
.pbm-mem b{display:block;font-size:11px}
.pbm-mem span{display:block;color:var(--muted);font-size:9.5px;margin-top:2px}
.pbm-btns{display:flex;gap:4px;margin-left:auto}
.pbm-btns button{border:1px solid var(--line);background:#fff;border-radius:2px;padding:2px 6px;font-size:8.5px;color:var(--muted)}
.pbm-btns .keep{background:var(--teal);border-color:var(--teal);color:#fff}
.pbm-nav{display:flex;justify-content:space-around;padding:10px 10px 16px;border-top:1px solid var(--line);background:#fffdf8;color:var(--muted);font-size:8.5px;text-align:center}
.pbm-nav div{display:flex;flex-direction:column;gap:4px;align-items:center}
.pbm-nav i{width:15px;height:15px;border:1.4px solid currentColor;border-radius:3px}
.pbm-nav .on{color:var(--terra)}
</style>
<div class="pbm">
  <div class="pbm-status"><span>9:41</span><span>5G · 100%</span></div>
  <div class="pbm-head"><h1>今日工作台</h1><p>3 条记忆待定夺 · 2 份文档已生成</p></div>
  <div class="pbm-body">
    <div class="pbm-card"><h2>待审核</h2><div class="big">03</div><p>其中 2 条将进入全局用户记忆，1 条只属于当前工作区。</p></div>
    <div class="pbm-card"><h2>候选记忆</h2>
      <div class="pbm-mem"><div class="n">1</div><div><b>中文沟通</b><span>代码与报错保留原文</span></div><div class="pbm-btns"><button class="keep">留</button><button>删</button></div></div>
      <div class="pbm-mem"><div class="n">2</div><div><b>先给结论</b><span>6 次长回答后被打断</span></div><div class="pbm-btns"><button class="keep">留</button><button>删</button></div></div>
      <div class="pbm-mem"><div class="n">3</div><div><b>纯开发环境</b><span>无硬件，直接加日志</span></div><div class="pbm-btns"><button class="keep">留</button><button>删</button></div></div>
    </div>
    <div class="pbm-card"><h2>本周</h2><div style="display:flex;gap:18px"><div><div class="big" style="font-size:26px">2</div><p>文档</p></div><div><div class="big" style="font-size:26px">4</div><p>调试</p></div><div><div class="big" style="font-size:26px">1</div><p>卡壳</p></div></div></div>
  </div>
  <div class="pbm-nav"><div class="on"><i></i>工作台</div><div><i></i>记忆</div><div><i></i>调试</div><div><i></i>文档</div></div>
</div>
"""

spec = {
    "project": {
        "name": "Programmer Workflow",
        "tagline": "把记忆、调试与评审摊开来看",
        "summary": "一个面向工作流搭档的控制台概念：左侧是待定夺的记忆与任务，中间是当前上下文，右侧是文档与设计评审。",
        "generated_at": "",
        "language": "zh-CN",
        "confidence": "medium",
        "source": "示例原型，用于演示 Prototype.html 的方向对比与评审能力",
    },
    "brief": {
        "goal": "让用户在一个界面里完成记忆审批、卡壳决策、文档/原型评审，而不是在多个对话与文件之间来回切换。",
        "audience": "同时使用多个编码 Agent、需要长期维护个人工作流的独立开发者。",
        "platform": "桌面 Web 为主，移动端用于快速审批与随手记录。",
        "constraints": [
            "本地优先，不引入云端账号",
            "单文件 HTML 原型，断网可看",
            "信息密度高，但不能牺牲可读性",
            "所有自动结论都必须可被用户否决",
        ],
        "success_criteria": [
            "用户能在 30 秒内看清“哪些记忆待定夺”",
            "能从卡壳直接进入调试或行业做法",
            "文档/原型评审结果能回到 Agent",
            "深浅两套视觉都能长时间阅读",
        ],
    },
    "assumptions": [
        "用户主要在大屏上工作，移动端是补充场景",
        "用户愿意为“可控”多花一次点击，但不愿重复解释",
        "界面默认中文，代码、路径与日志保留英文",
        "首版不需要多人协作与权限模型",
    ],
    "directions": [
        {
            "id": "A",
            "name": "指挥台 · Mission Control",
            "thesis": "深色高密度界面，把待审核记忆、卡壳计数、调试日志和评审放在同一视野里，适合长时间盯盘。",
            "when_to_use": "用户每天长时间使用、需要同时监控多个工作流，且不介意较高信息密度。",
            "palette": [
                {"name": "深空背景", "hex": "#0a0f1d", "role": "background"},
                {"name": "面板", "hex": "#111a2e", "role": "surface"},
                {"name": "主强调", "hex": "#8aa4ff", "role": "accent"},
                {"name": "成功", "hex": "#6ee7b7", "role": "success"},
                {"name": "警告", "hex": "#fbbf24", "role": "warning"},
                {"name": "危险", "hex": "#fb7185", "role": "danger"},
            ],
            "typography": [
                {"name": "标题", "family": "Segoe UI / Microsoft YaHei", "size": "23px", "weight": "700"},
                {"name": "正文", "family": "Segoe UI / Microsoft YaHei", "size": "12–13px", "weight": "400"},
                {"name": "日志", "family": "Consolas / monospace", "size": "9.5px", "weight": "400"},
            ],
            "components": ["记忆审批行", "KPI 卡", "任务清单", "日志摘要", "设计评审卡", "批量操作条"],
            "motion": "行内按钮 hover 轻微提亮；新日志以 120ms 淡入；不使用大幅位移。",
            "risks": ["长期深色可能疲劳", "信息密度高，首次使用需要引导", "移动端需要重新排布而非简单缩放"],
            "screens": [
                {"id": "dashboard", "name": "指挥台", "device": "desktop", "html": DESKTOP_A, "notes": ["左侧导航固定，主区可滚动", "记忆审批是首屏第一任务", "KPI 只保留 4 个，避免指标过载"]},
                {"id": "mobile-review", "name": "移动审批", "device": "mobile", "html": MOBILE_A, "notes": ["移动端只保留审批与卡壳计数", "底部导航四项", "大面积数字用于快速扫读"]},
            ],
        },
        {
            "id": "B",
            "name": "纸感工作台 · Paper Studio",
            "thesis": "暖纸色、编辑排版与低密度，把工作流当作一份可以翻阅的笔记，适合需要思考与写作的场景。",
            "when_to_use": "用户更常在文档、设计与长文语境中工作，希望界面安静、可读、有呼吸感。",
            "palette": [
                {"name": "纸白", "hex": "#f7f3ec", "role": "background"},
                {"name": "卡片", "hex": "#fffdf8", "role": "surface"},
                {"name": "墨色", "hex": "#1f2937", "role": "text"},
                {"name": "陶土", "hex": "#b45309", "role": "accent"},
                {"name": "青绿", "hex": "#0f766e", "role": "success"},
                {"name": "浅线", "hex": "#e2d8c9", "role": "border"},
            ],
            "typography": [
                {"name": "大标题", "family": "Georgia / Songti SC", "size": "31px", "weight": "500"},
                {"name": "正文", "family": "Segoe UI / Microsoft YaHei", "size": "10.5–12px", "weight": "400"},
                {"name": "数字", "family": "Georgia", "size": "26px", "weight": "500"},
            ],
            "components": ["编辑式页头", "编号记忆条目", "节奏卡", "评审预览", "细线分隔", "圆形色板"],
            "motion": "几乎无动效；只保留 hover 下划线、按钮 80ms 变色与页面淡入。",
            "risks": ["低密度导致首屏信息少", "暖色在低亮度屏幕上偏黄", "需要更克制的图标系统"],
            "screens": [
                {"id": "dashboard", "name": "工作台", "device": "desktop", "html": DESKTOP_B, "notes": ["页头用衬线字体建立编辑感", "记忆条目用编号而非标签", "卡片阴影极弱，靠细线与留白分层"]},
                {"id": "mobile-today", "name": "今日", "device": "mobile", "html": MOBILE_B, "notes": ["移动端保留纸感与衬线标题", "只展示今天的待办与待审核", "底部导航与桌面保持同一信息架构"]},
            ],
        },
    ],
    "questions": [
        {"id": "q-density", "question": "你更愿意每天打开哪一种：信息密集的指挥台，还是安静的纸感工作台？", "options": ["A 指挥台", "B 纸感工作台", "两者结合：默认 B，评审时切 A"], "default": "B 纸感工作台，保留 A 的高密度评审视图"},
        {"id": "q-mobile", "question": "移动端首屏最重要的是审批记忆，还是查看当前任务？", "options": ["审批记忆", "查看任务", "只看卡壳提醒"], "default": "审批记忆"},
        {"id": "q-brand", "question": "这个工具需要多强的品牌感？", "options": ["像内部工具，克制", "像独立产品，有辨识度", "像纸手账，弱化技术感"], "default": "像独立产品，但不过度装饰"},
    ],
    "review_prompts": [
        "两个方向里，哪个更像你每天愿意打开的工具？",
        "首屏最想先看到什么：待审批、卡壳、还是当前任务？",
        "有没有必须保留/必须删掉的具体元素？",
        "移动端你会在什么场景下用？",
    ],
}

out = Path(__file__).with_name("prototype.sample.json")
out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes)")
