#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
政务助手系统 — Web 服务
管理员面板 + 客户API + 合规代理
"""

import json
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
from engine_full import Engine
from task_manager import TaskStatus

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
PORT = 9090


class GovAssistantHandler(BaseHTTPRequestHandler):
    engine = None

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def _send_html(self, html):
        content = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_static(self, path):
        full_path = os.path.join(STATIC_DIR, path)
        if not os.path.exists(full_path):
            self.send_error(404)
            return
        ext = os.path.splitext(full_path)[1]
        ct = {".js": "application/javascript", ".css": "text/css", ".png": "image/png",
              ".svg": "image/svg+xml", ".ico": "image/x-icon"}.get(ext, "application/octet-stream")
        with open(full_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(content)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    # === 路由 ===

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # 静态文件
        if path.startswith("/static/"):
            self._send_static(path[8:])
            return

        # 管理员面板
        if path == "/" or path == "/admin":
            self._send_html(DASHBOARD_HTML)
            return

        # API 路由
        if path == "/api/dashboard":
            data = self.engine.get_dashboard_data()
            self._send_json(data)
        elif path == "/api/tasks":
            status = params.get("status", [None])[0]
            s = TaskStatus(status) if status else None
            tasks = [t.to_dict() for t in self.engine.tm.list_tasks(status=s)]
            self._send_json({"tasks": tasks})
        elif path.startswith("/api/tasks/"):
            task_id = path.split("/")[-1]
            task = self.engine.tm.get_task(task_id)
            if task:
                self._send_json(task.to_dict())
            else:
                self._send_json({"error": "Task not found"}, 404)
        elif path == "/api/stats":
            self._send_json(self.engine.tm.get_stats())
        elif path == "/api/cdp/status":
            self._send_json(self.engine.admin_get_cdp_status())

        elif path == "/api/notifications":
            limit = int(params.get("limit", [30])[0])
            self._send_json({"notifications": self.engine.notifier.get_recent(limit=limit)})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/tasks":
            # 创建任务（客户提交材料）
            task = self.engine.submit_materials(
                task_type=body.get("task_type", "establish"),
                client_id=body.get("client_id", ""),
                client_name=body.get("client_name", ""),
                materials=body.get("materials", {})
            )
            self._send_json(task.to_dict(), 201)

        elif path.startswith("/api/tasks/") and path.endswith("/confirm"):
            task_id = path.split("/")[-2]
            result = self.engine.client_confirm(task_id)
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/auth-done"):
            task_id = path.split("/")[-2]
            result = self.engine.client_auth_done(task_id)
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/sms"):
            task_id = path.split("/")[-2]
            result = self.engine.client_provide_sms(task_id, body.get("sms_code", ""))
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/resubmit"):
            task_id = path.split("/")[-2]
            result = self.engine.client_resubmit(task_id, body.get("materials", {}))
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/approve"):
            task_id = path.split("/")[-2]
            result = self.engine.admin_approve(task_id)
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/cancel"):
            task_id = path.split("/")[-2]
            result = self.engine.admin_force_cancel(task_id, body.get("reason", "管理员取消"))
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        elif path.startswith("/api/tasks/") and path.endswith("/check-progress"):
            task_id = path.split("/")[-2]
            result = self.engine.check_progress(task_id)
            self._send_json(result or {"error": "no progress data"})

        elif path.startswith("/api/tasks/") and path.endswith("/advance"):
            task_id = path.split("/")[-2]
            result = self.engine.admin_force_advance(
                task_id, body.get("target_status", "tracking"), body.get("reason", "")
            )
            self._send_json(result.to_dict() if hasattr(result, "to_dict") else result)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# === 管理员面板 HTML ===
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>政务助手 — 管理面板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.header{background:#1e293b;border-bottom:1px solid #334155;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:20px;color:#f8fafc}
.header .badge{background:#ef4444;color:white;padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px}
.header .time{color:#94a3b8;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:20px 24px}
.stat-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;text-align:center}
.stat-card .num{font-size:28px;font-weight:700;color:#f8fafc}
.stat-card .label{font-size:12px;color:#94a3b8;margin-top:4px}
.stat-card.warn{border-color:#f59e0b}
.stat-card.warn .num{color:#f59e0b}
.stat-card.danger{border-color:#ef4444}
.stat-card.danger .num{color:#ef4444}
.stat-card.success{border-color:#22c55e}
.stat-card.success .num{color:#22c55e}
.main{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:0 24px 24px}
.panel{background:#1e293b;border:1px solid #334155;border-radius:12px;overflow:hidden}
.panel-header{padding:12px 16px;border-bottom:1px solid #334155;display:flex;justify-content:space-between;align-items:center}
.panel-header h2{font-size:15px;color:#f8fafc}
.panel-body{padding:12px 16px;max-height:600px;overflow-y:auto}
.task-item{padding:12px;border:1px solid #334155;border-radius:8px;margin-bottom:8px;cursor:pointer;transition:all .15s}
.task-item:hover{border-color:#3b82f6;background:#1e3a5f}
.task-item.active{border-color:#3b82f6}
.task-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.task-id{font-size:12px;color:#64748b;font-family:monospace}
.task-type{font-size:13px;font-weight:600;color:#f8fafc}
.status-badge{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.status-created{background:#1e3a5f;color:#60a5fa}
.status-reviewing{background:#422006;color:#fbbf24}
.status-rejected{background:#450a0a;color:#f87171}
.status-approved{background:#052e16;color:#4ade80}
.status-filling{background:#1e3a5f;color:#60a5fa}
.status-confirming{background:#422006;color:#fbbf24}
.status-submitting{background:#1e3a5f;color:#60a5fa}
.status-auth_wait{background:#7c2d12;color:#fb923c}
.status-sms_wait{background:#7c2d12;color:#fb923c}
.status-tracking{background:#052e16;color:#4ade80}
.status-supplement{background:#422006;color:#fbbf24}
.status-completed{background:#052e16;color:#22c55e}
.status-failed{background:#450a0a;color:#ef4444}
.task-client{font-size:12px;color:#94a3b8}
.task-time{font-size:11px;color:#475569}
.needs-action{border-left:3px solid #f59e0b}
.needs-action::before{content:'⚠️';margin-right:4px}
.notify-item{padding:8px 0;border-bottom:1px solid #1e293b;font-size:12px}
.notify-item .n-time{color:#475569;font-family:monospace}
.notify-item .n-target{color:#60a5fa}
.notify-item .n-msg{color:#cbd5e1;margin-top:2px}
.detail-modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}
.detail-modal.show{display:flex}
.detail-content{background:#1e293b;border:1px solid #334155;border-radius:16px;width:90%;max-width:700px;max-height:85vh;overflow-y:auto;padding:24px}
.detail-content h3{margin-bottom:16px;color:#f8fafc}
.detail-content .field{margin-bottom:12px}
.detail-content .field-label{font-size:12px;color:#64748b;margin-bottom:2px}
.detail-content .field-value{font-size:14px;color:#e2e8f0;padding:6px 10px;background:#0f172a;border-radius:6px}
.history-item{padding:6px 0;border-bottom:1px solid #1e293b;font-size:12px}
.history-item .h-time{color:#475569;font-family:monospace;margin-right:8px}
.history-item .h-status{font-weight:600}
.history-item .h-msg{color:#94a3b8}
.btn{padding:6px 14px;border-radius:6px;border:none;cursor:pointer;font-size:12px;font-weight:600}
.btn-primary{background:#3b82f6;color:white}
.btn-danger{background:#ef4444;color:white}
.btn-warn{background:#f59e0b;color:#0f172a}
.btn-success{background:#22c55e;color:white}
.actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.refresh-btn{background:#334155;color:#94a3b8;border:1px solid #475569;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px}
.refresh-btn:hover{background:#475569;color:#e2e8f0}
.empty{text-align:center;color:#475569;padding:40px;font-size:14px}
@media(max-width:768px){.main{grid-template-columns:1fr}.stats{grid-template-columns:repeat(3,1fr)}}
</style>
</head>
<body>

<div class="header">
  <div style="display:flex;align-items:center">
    <h1>🏛️ 政务助手管理面板</h1>
    <span class="badge" id="actionBadge" style="display:none">0</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span id="cdpStatus" style="font-size:12px">🔴 CDP</span>
    <span class="time" id="currentTime"></span>
    <button class="refresh-btn" onclick="refresh()">🔄 刷新</button>
  </div>
</div>

<div class="stats" id="statsRow"></div>

<div class="main">
  <div class="panel">
    <div class="panel-header">
      <h2>📋 任务列表</h2>
      <select id="statusFilter" onchange="refresh()" style="background:#0f172a;color:#94a3b8;border:1px solid #334155;border-radius:6px;padding:4px 8px;font-size:12px">
        <option value="">全部</option>
        <option value="auth_wait">⚠️ 等待认证</option>
        <option value="sms_wait">📱 等待验证码</option>
        <option value="confirming">⏳ 等待确认</option>
        <option value="rejected">❌ 需补正</option>
        <option value="tracking">📍 跟踪中</option>
        <option value="completed">✅ 已办结</option>
      </select>
    </div>
    <div class="panel-body" id="taskList"></div>
  </div>

  <div>
    <div class="panel" style="margin-bottom:16px">
      <div class="panel-header"><h2>⚠️ 待处理</h2></div>
      <div class="panel-body" id="actionList"></div>
    </div>
    <div class="panel">
      <div class="panel-header"><h2>🔔 通知记录</h2></div>
      <div class="panel-body" id="notifyList" style="max-height:300px"></div>
    </div>
  </div>
</div>

<div class="detail-modal" id="detailModal" onclick="if(event.target===this)closeDetail()">
  <div class="detail-content" id="detailContent"></div>
</div>

<script>
const STATUS_LABELS = {
  created:'已创建',reviewing:'LLM审核中',rejected:'需补正',approved:'审核通过',
  filling:'自动填表中',confirming:'等待客户确认',submitting:'提交中',
  auth_wait:'等待客户认证',sms_wait:'等待验证码',tracking:'跟踪进度中',
  supplement:'需补正材料',completed:'已办结',failed:'失败'
};
const STATUS_ICONS = {
  created:'📝',reviewing:'🤖',rejected:'❌',approved:'✅',
  filling:'✍️',confirming:'⏳',submitting:'📤',
  auth_wait:'🔐',sms_wait:'📱',tracking:'📍',
  supplement:'📋',completed:'🎉',failed:'💀'
};
const CLIENT_ACTION = ['rejected','confirming','auth_wait','sms_wait','supplement'];

let allTasks = [];

async function api(path, method='GET', body=null) {
  const opts = {method, headers:{'Content-Type':'application/json'}};
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

function renderStats(stats) {
  const s = stats.by_status;
  const row = document.getElementById('statsRow');
  const cards = [
    {num:stats.total, label:'总任务', cls:''},
    {num:stats.needs_client_action, label:'待客户操作', cls:stats.needs_client_action>0?'warn':''},
    {num:(s.tracking||0), label:'跟踪中', cls:(s.tracking||0)>0?'success':''},
    {num:(s.completed||0), label:'已办结', cls:(s.completed||0)>0?'success':''},
    {num:(s.auth_wait||0)+(s.sms_wait||0), label:'认证等待', cls:(s.auth_wait||0)+(s.sms_wait||0)>0?'danger':''},
    {num:(s.rejected||0)+(s.supplement||0), label:'需补正', cls:(s.rejected||0)+(s.supplement||0)>0?'warn':''},
  ];
  row.innerHTML = cards.map(c => `<div class="stat-card ${c.cls}"><div class="num">${c.num}</div><div class="label">${c.label}</div></div>`).join('');

  const badge = document.getElementById('actionBadge');
  if (stats.needs_client_action > 0) {
    badge.textContent = stats.needs_client_action;
    badge.style.display = 'inline';
  } else {
    badge.style.display = 'none';
  }
}

function renderTasks(tasks) {
  allTasks = tasks;
  const filter = document.getElementById('statusFilter').value;
  const filtered = filter ? tasks.filter(t => t.status === filter) : tasks;
  const list = document.getElementById('taskList');

  if (!filtered.length) {
    list.innerHTML = '<div class="empty">暂无任务</div>';
    return;
  }

  list.innerHTML = filtered.map(t => {
    const isAction = CLIENT_ACTION.includes(t.status);
    return `<div class="task-item ${isAction?'needs-action':''}" onclick="showDetail('${t.task_id}')">
      <div class="task-top">
        <span class="task-type">${STATUS_ICONS[t.status]||''} ${t.task_type==='establish'?'设立登记':t.task_type==='change'?'变更登记':t.task_type==='cancel'?'注销登记':'进度查询'}</span>
        <span class="status-badge status-${t.status}">${STATUS_LABELS[t.status]||t.status}</span>
      </div>
      <div class="task-client">${t.client_name||t.client_id} · <span class="task-id">${t.task_id}</span></div>
      <div class="task-time">${t.updated_at?.substring(5,19).replace('T',' ')||''}</div>
    </div>`;
  }).join('');
}

function renderActions(needsAction) {
  const list = document.getElementById('actionList');
  if (!needsAction.length) {
    list.innerHTML = '<div class="empty" style="padding:20px">无待处理项</div>';
    return;
  }
  list.innerHTML = needsAction.map(t => {
    const msg = t.client_action_message || '';
    return `<div class="task-item needs-action" onclick="showDetail('${t.task_id}')" style="margin-bottom:6px">
      <div style="font-size:13px;font-weight:600">${t.client_name||t.client_id}</div>
      <div style="font-size:11px;color:#f59e0b;margin-top:2px">${msg.substring(0,40)}</div>
    </div>`;
  }).join('');
}

function renderNotifications(notifications) {
  const list = document.getElementById('notifyList');
  if (!notifications.length) {
    list.innerHTML = '<div class="empty" style="padding:16px">暂无通知</div>';
    return;
  }
  list.innerHTML = notifications.reverse().map(n => {
    return `<div class="notify-item">
      <span class="n-time">${n.time?.substring(11,19)||''}</span>
      <span class="n-target">[${n.target}]</span>
      <div class="n-msg">${(n.message||'').substring(0,60)}</div>
    </div>`;
  }).join('');
}

async function showDetail(taskId) {
  const t = await api(`/api/tasks/${taskId}`);
  const modal = document.getElementById('detailModal');
  const content = document.getElementById('detailContent');

  const isAction = CLIENT_ACTION.includes(t.status);
  let actionsHtml = '';
  if (t.status === 'confirming') {
    actionsHtml = `<button class="btn btn-success" onclick="doAction('${t.task_id}','confirm')">✅ 客户已确认提交</button>`;
    actionsHtml += ` <button class="btn btn-primary" onclick="doAction('${t.task_id}','approve')">👨‍💼 管理员审核通过</button>`;
  } else if (t.status === 'auth_wait') {
    actionsHtml = `<button class="btn btn-success" onclick="doAction('${t.task_id}','auth-done')">✅ 客户已完成认证</button>`;
  } else if (t.status === 'sms_wait') {
    actionsHtml = `<input id="smsInput" placeholder="输入验证码" style="padding:6px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;width:100px">
      <button class="btn btn-primary" onclick="doAction('${t.task_id}','sms')">提交验证码</button>`;
  } else if (t.status === 'rejected' || t.status === 'supplement') {
    actionsHtml = `<button class="btn btn-warn" onclick="alert('请通过API提交补正材料')">补正提交</button>`;
  } else if (t.status === 'tracking') {
    actionsHtml = `<button class="btn btn-primary" onclick="doAction('${t.task_id}','check-progress')">🔍 检查进度</button>`;
  }
  actionsHtml += ` <button class="btn btn-danger" onclick="doAction('${t.task_id}','cancel')">取消任务</button>`;

  const taskTypeLabel = {establish:'设立登记',change:'变更登记',cancel:'注销登记',track:'进度查询',name_check:'名称查询'}[t.task_type]||t.task_type;
  const reviewNote = t.review_result?.summary ? `<div class="field"><div class="field-label">LLM审核摘要</div><div class="field-value">${t.review_result.summary}</div></div>` : '';
  const formPreview = t.form_data?.fields ? `<div class="field"><div class="field-label">表单填写预览</div><div class="field-value" style="max-height:150px;overflow-y:auto;font-size:12px">${Object.entries(t.form_data.fields).map(([k,v])=>`<b>${k}</b>: ${v.value||v}${v.needs_confirm?' ⚠️需确认':''}`).join('<br>')}</div></div>` : '';
  const govResp = t.gov_response?.submit_result ? `<div class="field"><div class="field-label">政务平台响应</div><div class="field-value">${JSON.stringify(t.gov_response.submit_result).substring(0,200)}</div></div>` : '';
  const latestProgress = t.gov_response?.latest_progress ? `<div class="field"><div class="field-label">最新进度</div><div class="field-value">${JSON.stringify(t.gov_response.latest_progress.analysis||{}).substring(0,200)}</div></div>` : '';

  content.innerHTML = `
    <h3>${STATUS_ICONS[t.status]||''} 任务 ${t.task_id} — ${taskTypeLabel}</h3>
    <div class="field"><div class="field-label">客户</div><div class="field-value">${t.client_name||t.client_id}</div></div>
    <div class="field"><div class="field-label">状态</div><div class="field-value"><span class="status-badge status-${t.status}">${STATUS_LABELS[t.status]}</span> ${isAction?'⚠️ 需要客户操作':''}</div></div>
    ${t.client_action_message?`<div class="field"><div class="field-label">客户操作要求</div><div class="field-value" style="color:#f59e0b">${t.client_action_message}</div></div>`:''}
    ${reviewNote}
    ${t.review_result?.issues?.length?`<div class="field"><div class="field-label">审核问题</div><div class="field-value">${t.review_result.issues.map(i=>'• '+i).join('<br>')}</div></div>`:''}
    ${formPreview}
    ${govResp}
    ${latestProgress}
    <div class="field"><div class="field-label">操作历史</div>
      <div style="background:#0f172a;border-radius:6px;padding:8px;max-height:200px;overflow-y:auto">
        ${(t.history||[]).map(h=>`<div class="history-item"><span class="h-time">${h.time?.substring(11,19)||''}</span><span class="h-status status-badge status-${h.status}" style="font-size:10px">${STATUS_LABELS[h.status]||h.status}</span> <span class="h-msg">${h.message}</span></div>`).join('')}
      </div>
    </div>
    <div class="actions">${actionsHtml}</div>
  `;
  modal.classList.add('show');
}

function closeDetail() {
  document.getElementById('detailModal').classList.remove('show');
}

async function doAction(taskId, action) {
  let result;
  if (action === 'confirm') {
    result = await api(`/api/tasks/${taskId}/confirm`, 'POST');
  } else if (action === 'approve') {
    if (!confirm('确认审核通过？')) return;
    result = await api(`/api/tasks/${taskId}/approve`, 'POST');
  } else if (action === 'auth-done') {
    result = await api(`/api/tasks/${taskId}/auth-done`, 'POST');
  } else if (action === 'sms') {
    const code = document.getElementById('smsInput')?.value || '';
    result = await api(`/api/tasks/${taskId}/sms`, 'POST', {sms_code: code});
  } else if (action === 'check-progress') {
    result = await api(`/api/tasks/${taskId}/check-progress`, 'POST');
  } else if (action === 'cancel') {
    const reason = prompt('取消原因:');
    if (!reason) return;
    result = await api(`/api/tasks/${taskId}/cancel`, 'POST', {reason});
  }
  closeDetail();
  refresh();
}

async function refresh() {
  const data = await api('/api/dashboard');
  renderStats(data.stats);
  renderTasks(data.recent_tasks);
  renderActions(data.needs_action);
  renderNotifications(data.notifications);
  // CDP status
  const cdpEl = document.getElementById('cdpStatus');
  if (cdpEl && data.cdp_status) {
    cdpEl.textContent = data.cdp_status.cdp_connected ? '🟢 CDP已连接' : '🔴 CDP未连接';
    cdpEl.style.color = data.cdp_status.cdp_connected ? '#22c55e' : '#ef4444';
  }
  document.getElementById('currentTime').textContent = data.timestamp;
}

// 启动
refresh();
setInterval(refresh, 10000);  // 10秒自动刷新
</script>
</body>
</html>
"""


def main():
    engine = Engine()
    GovAssistantHandler.engine = engine

    server = HTTPServer(("0.0.0.0", PORT), GovAssistantHandler)
    print(f"\n{'='*60}")
    print(f"  🏛️ 政务助手管理面板已启动")
    print(f"  地址: http://localhost:{PORT}")
    print(f"  API: http://localhost:{PORT}/api/dashboard")
    print(f"{'='*60}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
