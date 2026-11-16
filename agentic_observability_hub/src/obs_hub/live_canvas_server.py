"""FastAPI + SSE Dual-Pane Live Workflow Topology & LLM Prompt/Context Inspector (:8765)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from obs_hub.config import ObsHubSettings, SecretRedactor
from obs_hub.dual_exporter import DualStackTelemetryExporter, LiveStore, NodeSpanRecord

# Fixed canonical topology of BoilerSense-AI™ 8-stage IPD workflow (all nodes visible even before running)
CANONICAL_TOPOLOGY: dict[str, Any] = {
    "nodes": [
        {"id": "s0_prior_recon", "label": "Stage 0a\n语料入库 & 宏侦察", "x": 60, "y": 50, "w": 175, "h": 58, "kind": "tool"},
        {"id": "s0_pm", "label": "Stage 0b\n首席 PM Step-Back", "x": 280, "y": 50, "w": 185, "h": 58, "kind": "agent"},
        {"id": "s1_search_pdf", "label": "Stage 1a\n检索 & 18份PDF验真", "x": 510, "y": 50, "w": 190, "h": 58, "kind": "tool"},

        {"id": "t1", "label": "T1 市场政策\n专家调研", "x": 40, "y": 155, "w": 122, "h": 54, "kind": "agent"},
        {"id": "t2", "label": "T2 竞品拆解\n专家调研", "x": 175, "y": 155, "w": 122, "h": 54, "kind": "agent"},
        {"id": "t3", "label": "T3 光电硬件\n系统选型", "x": 310, "y": 155, "w": 122, "h": 54, "kind": "agent"},
        {"id": "t4", "label": "T4 特种光纤\n锅炉焊接", "x": 445, "y": 155, "w": 122, "h": 54, "kind": "agent"},
        {"id": "t5", "label": "T5 解调算法\n与锅炉AI", "x": 580, "y": 155, "w": 122, "h": 54, "kind": "agent"},
        {"id": "t6", "label": "T6 NPI质量\n财务与GTM", "x": 715, "y": 155, "w": 122, "h": 54, "kind": "agent"},

        {"id": "s2_calcs", "label": "Stage 2 · PALMs 算账\nPHY/BOM/FIN/ROI", "x": 45, "y": 260, "w": 210, "h": 58, "kind": "tool"},
        {"id": "s3_ipd", "label": "Stage 3a · IPD 内审\n6角色工程评审会", "x": 285, "y": 260, "w": 175, "h": 58, "kind": "agent"},
        {"id": "s3_storm", "label": "Stage 3b · 电厂买方\n4角色 STORM 拷问", "x": 485, "y": 260, "w": 180, "h": 58, "kind": "agent"},
        {"id": "s4_elo", "label": "Stage 4 · Elo 锦标赛\n5路线瑞士轮裁决", "x": 690, "y": 260, "w": 165, "h": 58, "kind": "agent"},

        {"id": "w00", "label": "Vol 00\n立项路线图", "x": 30, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w01", "label": "Vol 01\n市场竞品", "x": 150, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w02", "label": "Vol 02\n选型BOM", "x": 270, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w03", "label": "Vol 03\n接口详设", "x": 390, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w04", "label": "Vol 04\n算法锅炉AI", "x": 510, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w05", "label": "Vol 05\n安装QA/QC", "x": 630, "y": 370, "w": 108, "h": 52, "kind": "writer"},
        {"id": "w06", "label": "Vol 06\n财务GTM培训", "x": 750, "y": 370, "w": 108, "h": 52, "kind": "writer"},

        {"id": "s6_critic", "label": "Stage 6 · 异构 Critic\n反思 & 引用/PDF校验", "x": 100, "y": 475, "w": 225, "h": 58, "kind": "gate"},
        {"id": "s6_crag", "label": "CRAG 定向补搜\n与并行重写 (≤2轮)", "x": 375, "y": 475, "w": 185, "h": 58, "kind": "gate"},
        {"id": "s7_judge", "label": "Stage 7a · 100分\nStage-Gate 门禁", "x": 595, "y": 475, "w": 135, "h": 58, "kind": "gate"},
        {"id": "s7_export", "label": "Stage 7b · 导出\n07/08 & Draw.io", "x": 750, "y": 475, "w": 125, "h": 58, "kind": "tool"},
    ],
    "edges": [
        ["s0_prior_recon", "s0_pm", "solid"],
        ["s0_pm", "s1_search_pdf", "solid"],
        ["s1_search_pdf", "t1", "solid"],
        ["s1_search_pdf", "t2", "solid"],
        ["s1_search_pdf", "t3", "solid"],
        ["s1_search_pdf", "t4", "solid"],
        ["s1_search_pdf", "t5", "solid"],
        ["s1_search_pdf", "t6", "solid"],
        ["t1", "s2_calcs", "solid"],
        ["t3", "s2_calcs", "solid"],
        ["t6", "s2_calcs", "solid"],
        ["s2_calcs", "s3_ipd", "solid"],
        ["s3_ipd", "s3_storm", "solid"],
        ["s3_storm", "s4_elo", "solid"],
        ["s4_elo", "w00", "solid"],
        ["s4_elo", "w02", "solid"],
        ["s4_elo", "w03", "solid"],
        ["s4_elo", "w04", "solid"],
        ["s4_elo", "w06", "solid"],
        ["w00", "s6_critic", "solid"],
        ["w03", "s6_critic", "solid"],
        ["w06", "s6_critic", "solid"],
        ["s6_critic", "s6_crag", "dashed"],
        ["s6_crag", "s6_critic", "dashed"],
        ["s6_critic", "s7_judge", "solid"],
        ["s7_judge", "s7_export", "solid"],
    ],
}


HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>Agentic Dual-Stack Live Topology & Prompt Studio</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0B1120; color: #E2E8F0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  header { height: 54px; background: #0F172A; border-bottom: 1px solid #1E293B; padding: 0 18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .brand { font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 10px; color: #F8FAFC; }
  .pill { font-size: 11px; padding: 3px 9px; border-radius: 999px; background: #1E293B; color: #94A3B8; border: 1px solid #334155; }
  .pill.ok { background: #064E3B; color: #6EE7B7; border-color: #059669; }
  .pill.off { background: #450A0A; color: #FCA5A5; border-color: #DC2626; }
  .controls { display: flex; align-items: center; gap: 8px; }
  select, button, a.btn { background: #1E293B; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 6px 11px; font-size: 12px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 5px; }
  button.primary { background: #2563EB; border-color: #3B82F6; font-weight: 600; }
  button.primary:hover { background: #1D4ED8; }
  a.btn-b { background: #1E3A8A; border-color: #3B82F6; }
  a.btn-a { background: #4C1D95; border-color: #8B5CF6; }
  main { flex: 1; display: grid; grid-template-columns: 54% 46%; min-height: 0; }
  .left-pane { position: relative; border-right: 1px solid #1E293B; background: radial-gradient(circle at 20% 20%, #111C33 0%, #0B1120 75%); overflow: auto; padding: 12px; }
  .legend { display: flex; gap: 12px; font-size: 11px; margin-bottom: 8px; color: #94A3B8; flex-wrap: wrap; }
  .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 4px; }
  svg#topo { width: 100%; min-width: 880px; height: 560px; background: rgba(15, 23, 42, 0.55); border: 1px solid #1E293B; border-radius: 10px; }
  .node-rect { stroke-width: 2; cursor: pointer; transition: all 0.25s ease; }
  .node-PENDING { fill: #1E293B; stroke: #475569; }
  .node-RUNNING { fill: #1E3A8A; stroke: #38BDF8; stroke-width: 3; filter: drop-shadow(0 0 8px #38BDF8); }
  .node-DONE { fill: #064E3B; stroke: #10B981; }
  .node-RETRY { fill: #7F1D1D; stroke: #F87171; }
  .node-selected { stroke: #FBBF24 !important; stroke-width: 3.5 !important; }
  .edge-line { fill: none; stroke: #334155; stroke-width: 2; }
  .edge-dashed { stroke-dasharray: 6 5; }
  .edge-active { stroke: #38BDF8; stroke-width: 3; stroke-dasharray: 8 5; animation: flow 0.8s linear infinite; }
  .edge-done { stroke: #10B981; stroke-width: 2.2; }
  @keyframes flow { to { stroke-dashoffset: -26; } }
  .right-pane { display: flex; flex-direction: column; min-height: 0; background: #0F172A; }
  .inspector-hdr { padding: 12px 16px; border-bottom: 1px solid #1E293B; }
  .inspector-title { font-size: 14px; font-weight: 700; color: #F8FAFC; }
  .inspector-meta { font-size: 11px; color: #94A3B8; margin-top: 4px; display: flex; gap: 12px; flex-wrap: wrap; }
  .tabs { display: flex; border-bottom: 1px solid #1E293B; background: #0B1120; padding: 0 12px; gap: 4px; }
  .tab { padding: 9px 14px; font-size: 12px; cursor: pointer; color: #94A3B8; border-bottom: 2px solid transparent; }
  .tab.active { color: #38BDF8; border-bottom-color: #38BDF8; font-weight: 600; }
  .tab-body { flex: 1; overflow: auto; padding: 14px 16px; }
  pre.code-box { white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.55; background: #020617; border: 1px solid #1E293B; border-radius: 8px; padding: 12px; color: #E2E8F0; margin: 0 0 12px 0; }
  .section-lbl { font-size: 11px; font-weight: 700; color: #38BDF8; text-transform: uppercase; letter-spacing: 0.05em; margin: 10px 0 6px; }
  .event-list { margin-top: 10px; border: 1px solid #1E293B; border-radius: 8px; max-height: 150px; overflow: auto; background: #0F172A; }
  .event-row { padding: 6px 12px; font-size: 11px; border-bottom: 1px solid #1E293B; display: flex; justify-content: space-between; cursor: pointer; }
  .event-row:hover { background: #1E293B; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <span>⚡ BoilerSense-AI™ 多智能体全景拓扑与双栈对比台 (:8765)</span>
    <span id="status-b" class="pill">Langfuse v3 (:3000) 检测中...</span>
    <span id="status-a" class="pill">Arize Phoenix (:6006) 检测中...</span>
  </div>
  <div class="controls">
    <select id="run-select" onchange="loadRun(this.value)"></select>
    <button class="primary" onclick="animateReplay()">▶ 10x 动态流转重放</button>
    <a id="link-langfuse" class="btn btn-b" href="http://localhost:3000" target="_blank">打开方案 B · Langfuse v3 ↗</a>
    <a id="link-phoenix" class="btn btn-a" href="http://localhost:6006" target="_blank">打开方案 A · Phoenix ↗</a>
  </div>
</header>
<main>
  <section class="left-pane">
    <div class="legend">
      <span><i class="dot" style="background:#475569"></i>待命 (Pending)</span>
      <span><i class="dot" style="background:#38BDF8"></i>运行中 / 动态流光 (Running)</span>
      <span><i class="dot" style="background:#10B981"></i>已完成 (Done)</span>
      <span><i class="dot" style="background:#F87171"></i>Critic 打回重写 (Retry)</span>
      <span style="margin-left:auto;color:#FBBF24">点击任意节点 → 右侧审查完整 Prompt / Context / 思考链</span>
    </div>
    <svg id="topo" viewBox="0 0 900 560"></svg>
    <div class="section-lbl">执行序列事件流 (点击任意事件同样定位查看)</div>
    <div id="event-list" class="event-list"></div>
  </section>
  <section class="right-pane">
    <div class="inspector-hdr">
      <div id="insp-title" class="inspector-title">请点击左侧任意智能体或工具节点</div>
      <div id="insp-meta" class="inspector-meta"></div>
    </div>
    <div class="tabs">
      <div class="tab active" onclick="switchTab('prompt', this)">① Prompt & 注入 Context</div>
      <div class="tab" onclick="switchTab('thinking', this)">② Thinking 思考链</div>
      <div class="tab" onclick="switchTab('output', this)">③ LLM 原始输出</div>
      <div class="tab" onclick="switchTab('compare', this)">④ A/B 双栈直达对照</div>
    </div>
    <div id="tab-body" class="tab-body">
      <pre class="code-box">等待选择节点...</pre>
    </div>
  </section>
</main>
<script>
let TOPO = null;
let CURRENT_RUN = null;
let EVENTS = [];
let NODE_STATUS = {};
let SELECTED_NODE = null;
let SELECTED_EVENT = null;
let ACTIVE_TAB = 'prompt';

async function init() {
  const topoRes = await fetch('/api/topology');
  TOPO = await topoRes.json();
  checkStacks();
  setInterval(checkStacks, 8000);
  await refreshRuns();
  const es = new EventSource('/api/stream');
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'update') refreshRuns(msg.run_id);
  };
}

async function checkStacks() {
  try {
    const r = await fetch('/api/stack-health');
    const h = await r.json();
    const b = document.getElementById('status-b');
    const a = document.getElementById('status-a');
    b.textContent = h.langfuse ? '方案B Langfuse v3 (:3000) 在线' : '方案B Langfuse v3 离线';
    b.className = 'pill ' + (h.langfuse ? 'ok' : 'off');
    a.textContent = h.phoenix ? '方案A Phoenix (:6006) 在线' : '方案A Phoenix 离线';
    a.className = 'pill ' + (h.phoenix ? 'ok' : 'off');
  } catch (err) {}
}

async function refreshRuns(preferredId) {
  const res = await fetch('/api/runs');
  const runs = await res.json();
  const sel = document.getElementById('run-select');
  sel.innerHTML = '';
  runs.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.run_id;
    opt.textContent = `${r.workflow_name} | ${r.run_id} (${r.engine_mode})`;
    sel.appendChild(opt);
  });
  if (runs.length > 0) {
    const target = preferredId || CURRENT_RUN?.run_id || runs[0].run_id;
    sel.value = target;
    await loadRun(target);
  } else {
    renderGraph();
  }
}

async function loadRun(runId) {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
  const data = await res.json();
  CURRENT_RUN = data.run;
  EVENTS = data.events || [];
  NODE_STATUS = {};
  EVENTS.forEach(ev => { NODE_STATUS[ev.node_id] = ev.status || 'DONE'; });

  if (CURRENT_RUN) {
    document.getElementById('link-langfuse').href = `http://localhost:3000/project/boiler-fbg-rd/traces/${CURRENT_RUN.trace_id_hex}`;
  }
  renderGraph();
  renderEventList();
  if (EVENTS.length > 0 && !SELECTED_EVENT) {
    selectEvent(EVENTS[0]);
  }
}

function renderGraph(activeEdgePairs = new Set()) {
  if (!TOPO) return;
  const svg = document.getElementById('topo');
  svg.innerHTML = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 10 5 L 0 9 z" fill="#64748B"/></marker></defs>`;
  const map = {};
  TOPO.nodes.forEach(n => map[n.id] = n);

  TOPO.edges.forEach(([s, t, style]) => {
    const a = map[s], b = map[t];
    if (!a || !b) return;
    const x1 = a.x + a.w / 2, y1 = a.y + a.h;
    const x2 = b.x + b.w / 2, y2 = b.y;
    const midY = (y1 + y2) / 2;
    const d = (Math.abs(a.y - b.y) < 10)
      ? `M ${a.x + a.w} ${a.y + a.h/2} L ${b.x} ${b.y + b.h/2}`
      : `M ${x1} ${y1} L ${x1} ${midY} L ${x2} ${midY} L ${x2} ${y2}`;
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const stS = NODE_STATUS[s] || 'PENDING';
    const stT = NODE_STATUS[t] || 'PENDING';
    let cls = 'edge-line ' + (style === 'dashed' ? 'edge-dashed ' : '');
    if (activeEdgePairs.has(s + '->' + t) || stT === 'RUNNING') cls += 'edge-active';
    else if (stS === 'DONE' && stT === 'DONE') cls += 'edge-done';
    p.setAttribute('d', d);
    p.setAttribute('class', cls);
    p.setAttribute('marker-end', 'url(#arrow)');
    svg.appendChild(p);
  });

  TOPO.nodes.forEach(n => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const st = NODE_STATUS[n.id] || 'PENDING';
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', n.x); rect.setAttribute('y', n.y);
    rect.setAttribute('width', n.w); rect.setAttribute('height', n.h);
    rect.setAttribute('rx', 8);
    rect.setAttribute('class', `node-rect node-${st} ${SELECTED_NODE === n.id ? 'node-selected' : ''}`);
    rect.onclick = () => selectNode(n.id);
    g.appendChild(rect);

    const lines = n.label.split('\\n');
    lines.forEach((ln, i) => {
      const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      txt.setAttribute('x', n.x + n.w / 2);
      txt.setAttribute('y', n.y + (lines.length === 1 ? n.h/2 + 4 : 21 + i * 17));
      txt.setAttribute('text-anchor', 'middle');
      txt.setAttribute('fill', '#F8FAFC');
      txt.setAttribute('font-size', i === 0 ? '11' : '10');
      txt.setAttribute('font-weight', i === 0 ? '700' : '400');
      txt.style.pointerEvents = 'none';
      txt.textContent = ln;
      g.appendChild(txt);
    });
    svg.appendChild(g);
  });
}

function renderEventList() {
  const el = document.getElementById('event-list');
  el.innerHTML = '';
  EVENTS.forEach(ev => {
    const row = document.createElement('div');
    row.className = 'event-row';
    row.onclick = () => selectEvent(ev);
    row.innerHTML = `<span><b>#${ev.seq_order} [${ev.node_id}]</b> ${ev.role_title}</span><span style="color:#94A3B8">${ev.model_name || ev.span_kind} | in:${ev.prompt_tokens} out:${ev.completion_tokens} | ${(ev.latency_ms/1000).toFixed(1)}s</span>`;
    el.appendChild(row);
  });
}

function selectNode(nodeId) {
  SELECTED_NODE = nodeId;
  const matches = EVENTS.filter(e => e.node_id === nodeId);
  if (matches.length > 0) {
    selectEvent(matches[matches.length - 1]);
  } else {
    SELECTED_EVENT = { node_id: nodeId, role_title: nodeId, stage_label: '尚未产生执行记录', model_name: '-', system_prompt: '', user_prompt: '(该节点在当前运行中尚未触发)', thinking: '', output_text: '' };
    renderInspector();
    renderGraph();
  }
}

function selectEvent(ev) {
  SELECTED_EVENT = ev;
  SELECTED_NODE = ev.node_id;
  renderInspector();
  renderGraph();
}

function switchTab(tab, el) {
  ACTIVE_TAB = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  renderInspector();
}

function renderInspector() {
  const ev = SELECTED_EVENT;
  if (!ev) return;
  document.getElementById('insp-title').textContent = `[${ev.node_id}] ${ev.role_title}`;
  document.getElementById('insp-meta').innerHTML = `<span>阶段: ${ev.stage_label}</span><span>模型: ${ev.model_name || '-'}</span><span>Prompt Tokens: ${ev.prompt_tokens || 0}</span><span>Output Tokens: ${ev.completion_tokens || 0}</span><span>耗时: ${((ev.latency_ms||0)/1000).toFixed(2)}s</span>`;

  const body = document.getElementById('tab-body');
  if (ACTIVE_TAB === 'prompt') {
    body.innerHTML = `<div class="section-lbl">System Prompt</div><pre class="code-box">${esc(ev.system_prompt || '(空)')}</pre><div class="section-lbl">User Prompt & 完整注入 Context (${(ev.user_prompt||'').length} 字符)</div><pre class="code-box">${esc(ev.user_prompt || '(空)')}</pre>`;
  } else if (ACTIVE_TAB === 'thinking') {
    body.innerHTML = `<div class="section-lbl">Thinking / Reasoning 思考过程</div><pre class="code-box">${esc(ev.thinking || '(该步骤为确定性工具或未返回独立思维链)')}</pre>`;
  } else if (ACTIVE_TAB === 'output') {
    body.innerHTML = `<div class="section-lbl">LLM 原始返回 / JSON / Markdown (${(ev.output_text||'').length} 字符)</div><pre class="code-box">${esc(ev.output_text || '(空)')}</pre>`;
  } else {
    const lfUrl = CURRENT_RUN ? `http://localhost:3000/project/boiler-fbg-rd/traces/${CURRENT_RUN.trace_id_hex}` : 'http://localhost:3000';
    body.innerHTML = `
      <div class="section-lbl">双栈企业平台一键同屏对比</div>
      <pre class="code-box">Trace ID: ${CURRENT_RUN?.trace_id_hex || '-'}\nSpan ID : ${ev.span_id_hex || '-'}\n\n1. 点击下方蓝色按钮，在企业主力【方案 B · Langfuse v3】中查看该条 Trace 的 Tree / Timeline / Graph / Playground。\n2. 点击下方紫色按钮，在轻量级【方案 A · Arize Phoenix】中对比 OpenInference Message 气泡视图。\n3. 本控制台 (:8765) 保留 100% 未截断全文，可直接全文检索与复制任何注入的 [EV-*] 与工程表。</pre>
      <div style="display:flex;gap:10px;margin-top:8px;">
        <a class="btn btn-b" href="${lfUrl}" target="_blank">在 Langfuse v3 (:3000) 中检查此 Trace ↗</a>
        <a class="btn btn-a" href="http://localhost:6006" target="_blank">在 Arize Phoenix (:6006) 中对比 ↗</a>
      </div>`;
  }
}

async function animateReplay() {
  if (!EVENTS.length) return;
  const saved = { ...NODE_STATUS };
  NODE_STATUS = {};
  TOPO.nodes.forEach(n => NODE_STATUS[n.id] = 'PENDING');
  renderGraph();

  for (let i = 0; i < EVENTS.length; i++) {
    const ev = EVENTS[i];
    NODE_STATUS[ev.node_id] = 'RUNNING';
    const actEdges = new Set();
    TOPO.edges.forEach(([s, t]) => { if (t === ev.node_id) actEdges.add(s + '->' + t); });
    SELECTED_EVENT = ev;
    SELECTED_NODE = ev.node_id;
    renderGraph(actEdges);
    renderInspector();
    await new Promise(r => setTimeout(r, 380));
    NODE_STATUS[ev.node_id] = ev.status || 'DONE';
  }
  NODE_STATUS = saved;
  renderGraph();
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
init();
</script>
</body>
</html>
"""


def create_app(settings: ObsHubSettings | None = None) -> FastAPI:
    cfg = settings or ObsHubSettings.load()
    store = LiveStore(cfg.sqlite_path)
    redactor = SecretRedactor.from_workspace(cfg.workspace_root)
    subscribers: set[asyncio.Queue[str]] = set()

    app = FastAPI(title="Agentic Dual-Stack Live Topology Studio")
    app.state.settings = cfg
    app.state.store = store

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return HTML_PAGE

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/topology")
    async def get_topology() -> dict[str, Any]:
        return CANONICAL_TOPOLOGY

    @app.get("/api/stack-health")
    async def stack_health() -> dict[str, bool]:
        async def _probe(url: str) -> bool:
            try:
                async with httpx.AsyncClient(timeout=1.2) as c:
                    r = await c.get(url)
                    return r.status_code < 500
            except Exception:
                return False

        lf, ph = await asyncio.gather(
            _probe(f"{cfg.langfuse_web_url}/api/public/health"),
            _probe(f"{cfg.phoenix_web_url}/healthz"),
        )
        return {"langfuse": lf, "phoenix": ph}

    @app.get("/api/runs")
    async def list_runs() -> list[dict[str, Any]]:
        return store.list_runs()

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        runs = [r for r in store.list_runs() if r["run_id"] == run_id]
        if not runs:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run": runs[0], "events": store.get_run_events(run_id)}

    @app.post("/api/events")
    async def ingest_live_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Receive real-time execution events from LangGraph or CLI runs and broadcast via SSE."""
        ev = NodeSpanRecord.model_validate(payload)
        exporter = DualStackTelemetryExporter(cfg, redactor=redactor)
        try:
            res = exporter.emit_workflow_run(
                run_id=ev.run_id,
                workflow_name=ev.workflow_name,
                engine_mode="live_stream",
                events=[ev],
                push_otlp=True,
            )
        finally:
            exporter.close()

        msg = json.dumps({"type": "update", "run_id": ev.run_id, "node_id": ev.node_id})
        for q in list(subscribers):
            await q.put(msg)
        return res

    @app.get("/api/stream")
    async def sse_stream(request: Request) -> StreamingResponse:
        q: asyncio.Queue[str] = asyncio.Queue()
        subscribers.add(q)

        async def _gen():
            try:
                yield "data: {\"type\":\"connected\"}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield f"data: {data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                subscribers.discard(q)

        return StreamingResponse(_gen(), media_type="text/event-stream")

    return app
