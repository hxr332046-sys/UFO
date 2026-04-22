#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
类人单步执行 guide/base -> 下一步 测试
每一步有延迟、有验证、有记录
MITM 全量抓包同步进行
"""

import json
import time
import random
import sys
from pathlib import Path

import requests
import websocket

CDP_PORT = 9225
MITM_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "mitm_ufo_flows.jsonl"
STEP_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "human_steps_guide_base.jsonl"

def _jitter():
    return random.uniform(2.0, 4.0)

def _log_step(step_name: str, status: str, detail: str = ""):
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "step": step_name,
        "status": status,
        "detail": detail,
    }
    STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STEP_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[STEP] {step_name}: {status} {detail}")

def _get_ws_url() -> str:
    r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5)
    targets = r.json()
    for t in targets:
        url = str(t.get("url", ""))
        if "9087" in url and t.get("type") == "page":
            return str(t.get("webSocketDebuggerUrl", ""))
    return ""

def _eval(ws_url: str, expr: str, timeout: int = 10) -> dict:
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True}}))
    res = json.loads(ws.recv())
    ws.close()
    return res

def _wait_for_element(ws_url: str, selector: str, max_wait: float = 10.0) -> bool:
    expr = f"""
    (function() {{
      const el = document.querySelector('{selector}');
      return !!el;
    }})()
    """
    start = time.time()
    while time.time() - start < max_wait:
        res = _eval(ws_url, expr)
        if res.get("result", {}).get("result", {}).get("value"):
            return True
        time.sleep(0.5)
    return False

def _click_element(ws_url: str, selector: str) -> bool:
    expr = f"""
    (function() {{
      const el = document.querySelector('{selector}');
      if (!el) return 'not_found';
      el.click();
      return 'clicked';
    }})()
    """
    res = _eval(ws_url, expr)
    val = res.get("result", {}).get("result", {}).get("value", "")
    return val == "clicked"

def _mitm_tail_lines(n: int = 5) -> list:
    if not MITM_LOG.exists():
        return []
    with MITM_LOG.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-n:] if l.strip()]

def _wait_mitm_contains(keyword: str, timeout: float = 15.0) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        for rec in _mitm_tail_lines(10):
            if keyword in rec.get("url", ""):
                return rec
        time.sleep(0.5)
    return {}

# ========== STEP 0: 确认页面 ==========
print("=" * 50)
print("STEP 0: 确认当前页面位置")
ws_url = _get_ws_url()
if not ws_url:
    _log_step("init", "FAIL", "no_ws_url")
    sys.exit(1)

href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("init", "OK", f"href={href}")

if "guide/base" not in href:
    _log_step("init", "FAIL", f"not on guide/base: {href}")
    sys.exit(1)

# ========== STEP 1: 选企业类型 ==========
print("\nSTEP 1: 点击 [全部企业类型] -> 选 [个人独资企业]")
time.sleep(_jitter())

# 先点"全部企业类型"
clicked = _click_element(ws_url, '[class*="el-radio"], .tne-radio-group__item, button, [role="radio"]')
_log_step("ent_type_click", "attempt", f"selector_try=generic_radio")

# 更精确：找包含"全部企业类型"的按钮
expr = """
(function() {
  const btns = Array.from(document.querySelectorAll('button, span, div, a'));
  const btn = btns.find(el => el.textContent.includes('全部企业类型'));
  if (btn) { btn.click(); return 'clicked_all_ent'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("all_ent_types", "OK" if "clicked" in val else "WARN", val)

time.sleep(_jitter())

# 在弹窗里选"个人独资企业"
expr = """
(function() {
  const items = Array.from(document.querySelectorAll('span, div, li, button'));
  const target = items.find(el => el.textContent.trim() === '个人独资企业');
  if (target) { target.click(); return 'clicked_4540'; }
  // 模糊匹配
  const fuzzy = items.find(el => el.textContent.includes('个人独资'));
  if (fuzzy) { fuzzy.click(); return 'clicked_fuzzy'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("select_4540", "OK" if "clicked" in val else "FAIL", val)

time.sleep(_jitter())

# 验证：检查 Vue 组件中 entType 是否变成 4540
expr = """
(function() {
  const app = document.querySelector('#app') || document.body;
  if (app.__vue__ || app.__VUE__) {
    const vm = app.__vue__ || app.__VUE__;
    const form = vm.$refs?.form || vm.form || vm.$data?.form;
    if (form) return JSON.stringify({entType: form.entType, entTypeName: form.entTypeName});
  }
  // 退而求其次：检查页面上是否有"个人独资"文字
  return document.body.innerText.includes('个人独资') ? 'text_found' : 'unknown';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("verify_4540", "OK", val)

# ========== STEP 2: 选名称申请状态 ==========
print("\nSTEP 2: 选 [未申请]")
time.sleep(_jitter())

expr = """
(function() {
  const items = Array.from(document.querySelectorAll('span, div, label, button, [role="radio"]'));
  const target = items.find(el => el.textContent.trim() === '未申请');
  if (target) { target.click(); return 'clicked'; }
  const fuzzy = items.find(el => el.textContent.includes('未申请'));
  if (fuzzy) { fuzzy.click(); return 'clicked_fuzzy'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("select_unapplied", "OK" if "clicked" in val else "FAIL", val)

time.sleep(_jitter())

# ========== STEP 3: 选区划 ==========
print("\nSTEP 3: 选区划 [广西 > 玉林 > 容县]")
time.sleep(_jitter())

# 找区划选择触发器（通常是点击后弹出选择框）
expr = """
(function() {
  const labels = Array.from(document.querySelectorAll('label, span, div'));
  const distLabel = labels.find(el => el.textContent.includes('公司在哪里') || el.textContent.includes('住所') || el.textContent.includes('行政区划'));
  if (!distLabel) return 'no_label';
  // 找同级的输入框或点击区
  let parent = distLabel.parentElement;
  for (let i=0; i<5; i++) {
    if (!parent) break;
    const clickArea = parent.querySelector('input, .el-input, [class*="picker"], [class*="select"]');
    if (clickArea) { clickArea.click(); return 'opened_picker'; }
    parent = parent.parentElement;
  }
  return 'no_picker';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("open_district_picker", "OK" if "opened" in val else "WARN", val)

time.sleep(_jitter())

# 选广西壮族自治区
expr = """
(function() {
  const items = Array.from(document.querySelectorAll('li, div, span'));
  const gx = items.find(el => el.textContent.trim() === '广西壮族自治区');
  if (gx) { gx.click(); return 'clicked_gx'; }
  const fuzzy = items.find(el => el.textContent.includes('广西'));
  if (fuzzy) { fuzzy.click(); return 'clicked_fuzzy_gx'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("select_gx", "OK" if "clicked" in val else "WARN", val)

time.sleep(1.5)

# 选玉林市
expr = """
(function() {
  const items = Array.from(document.querySelectorAll('li, div, span'));
  const yl = items.find(el => el.textContent.trim() === '玉林市');
  if (yl) { yl.click(); return 'clicked_yl'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("select_yl", "OK" if "clicked" in val else "WARN", val)

time.sleep(1.5)

# 选容县
expr = """
(function() {
  const items = Array.from(document.querySelectorAll('li, div, span'));
  const rx = items.find(el => el.textContent.trim() === '容县');
  if (rx) { rx.click(); return 'clicked_rx'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("select_rx", "OK" if "clicked" in val else "WARN", val)

time.sleep(_jitter())

# 验证区划
expr = """
(function() {
  const body = document.body.innerText;
  return body.includes('容县') ? 'rongxian_found' : 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("verify_district", "OK" if "rongxian" in val else "WARN", val)

# ========== STEP 4: 点下一步 ==========
print("\nSTEP 4: 点击 [下一步]")
time.sleep(_jitter())

expr = """
(function() {
  const btns = Array.from(document.querySelectorAll('button, span, div, a'));
  const next = btns.find(el => el.textContent.trim() === '下一步');
  if (next) { next.click(); return 'clicked_next'; }
  const fuzzy = btns.find(el => el.textContent.includes('下一步'));
  if (fuzzy) { fuzzy.click(); return 'clicked_fuzzy'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("click_next", "OK" if "clicked" in val else "FAIL", val)

# ========== STEP 5: 等待跳转并验证 ==========
print("\nSTEP 5: 等待页面跳转...")
time.sleep(3.0)

# 检查是否跳转到 core.html
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("navigate_verify", "OK" if "core.html" in href else "PENDING", f"href={href}")

# 等 MITM 里的 checkEstablishName
print("\n等待 MITM 抓包出现 checkEstablishName...")
mitm_rec = _wait_mitm_contains("checkEstablishName", timeout=20.0)
if mitm_rec:
    _log_step("mitm_checkEstablishName", "OK", f"status={mitm_rec.get('status_code')} url={mitm_rec.get('url','')[:80]}")
else:
    _log_step("mitm_checkEstablishName", "TIMEOUT", "not found in 20s")

# 等 operationBusinessDataInfo
print("等待 MITM 抓包出现 operationBusinessDataInfo...")
mitm_rec2 = _wait_mitm_contains("operationBusinessDataInfo", timeout=30.0)
if mitm_rec2:
    _log_step("mitm_operationBusinessDataInfo", "OK", f"status={mitm_rec2.get('status_code')} url={mitm_rec2.get('url','')[:80]}")
else:
    _log_step("mitm_operationBusinessDataInfo", "TIMEOUT", "not found in 30s")

# 最终验证
print("\n最终验证...")
time.sleep(2.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
title_res = _eval(ws_url, "document.title")
title = title_res.get("result", {}).get("result", {}).get("value", "")

final_status = "PASS" if ("core.html" in href and "name-check-info" in href) else "PARTIAL"
_log_step("final", final_status, f"href={href} title={title}")

print("\n" + "=" * 50)
print(f"执行完成: {final_status}")
print(f"日志: {STEP_LOG}")
print(f"MITM抓包: {MITM_LOG}")
