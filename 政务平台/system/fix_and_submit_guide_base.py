#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
精确修复 guide/base 表单并点击下一步
直接操作 namenotice 上的 Vue $data
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
STEP_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "fix_and_submit_steps.jsonl"

def _jitter(min_sec=1.0, max_sec=2.5):
    return random.uniform(min_sec, max_sec)

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
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    res = json.loads(ws.recv())
    ws.close()
    return res

# ========== STEP 0: 确认页面 ==========
print("=" * 60)
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

# ========== STEP 1: 精确设置表单数据 ==========
print("\nSTEP 1: 精确设置 Vue 表单数据")
time.sleep(_jitter(0.5, 1.0))

js_set_form = """
(function() {
  const all = Array.from(document.querySelectorAll('*'));
  let targetVm = null;
  let targetEl = null;
  
  for (const el of all) {
    const vm = el.__vue__ || el.__VUE__;
    if (!vm) continue;
    const data = vm.$data || vm;
    if (data.entType !== undefined && data.nameCode !== undefined && data.distCode !== undefined) {
      targetVm = vm;
      targetEl = el;
      break;
    }
  }
  
  if (!targetVm) return 'no_target_vm';
  
  const data = targetVm.$data;
  const before = JSON.stringify({
    entType: data.entType,
    nameCode: data.nameCode,
    distCode: data.distCode,
    distCodeArr: data.distCodeArr,
    address: data.address,
    streetCode: data.streetCode,
    streetName: data.streetName,
    havaAdress: data.havaAdress,
    fzSign: data.fzSign
  });
  
  // 设置所有关键字段
  data.entType = '4540';
  data.nameCode = '0';
  data.distCode = '450921';
  data.distCodeArr = ['450000', '450900', '450921'];
  data.address = '广西壮族自治区玉林市容县';
  data.streetCode = '';
  data.streetName = '';
  data.havaAdress = '0';  // 关键字段
  data.fzSign = 'N';
  
  // 触发 Vue 响应式更新
  if (targetVm.$forceUpdate) targetVm.$forceUpdate();
  
  // 如果有 form ref，也更新
  if (targetVm.$refs && targetVm.$refs.form) {
    const form = targetVm.$refs.form;
    if (form.model) {
      form.model.entType = '4540';
      form.model.nameCode = '0';
      form.model.distCode = '450921';
      form.model.distCodeArr = ['450000', '450900', '450921'];
      form.model.address = '广西壮族自治区玉林市容县';
      form.model.havaAdress = '0';
    }
  }
  
  const after = JSON.stringify({
    entType: data.entType,
    nameCode: data.nameCode,
    distCode: data.distCode,
    distCodeArr: data.distCodeArr,
    address: data.address,
    havaAdress: data.havaAdress
  });
  
  return JSON.stringify({status: 'set_ok', element: targetEl.tagName + '.' + targetEl.className, before: before, after: after});
})()
"""
res = _eval(ws_url, js_set_form)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("form_set", "OK" if "set_ok" in val else "FAIL", val)

time.sleep(_jitter(1.0, 2.0))

# ========== STEP 2: 验证表单 ==========
print("\nSTEP 2: 验证表单数据")
js_verify = """
(function() {
  const all = Array.from(document.querySelectorAll('*'));
  for (const el of all) {
    const vm = el.__vue__ || el.__VUE__;
    if (!vm) continue;
    const data = vm.$data || vm;
    if (data.entType !== undefined && data.distCode !== undefined) {
      return JSON.stringify({
        entType: data.entType,
        nameCode: data.nameCode,
        distCode: data.distCode,
        distCodeArr: data.distCodeArr,
        address: data.address,
        havaAdress: data.havaAdress
      });
    }
  }
  return 'no_form';
})()
"""
res = _eval(ws_url, js_verify)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("form_verify", "OK" if "entType" in val else "FAIL", val)

# ========== STEP 3: 触发区划 picker 的 change 事件（如果存在） ==========
print("\nSTEP 3: 触发 change 事件")
time.sleep(_jitter(0.5, 1.0))

js_trigger = """
(function() {
  const picker = document.querySelector('.tne-data-picker.wherecascader');
  if (picker) {
    const vm = picker.__vue__ || picker.__VUE__;
    if (vm && vm.$emit) {
      vm.$emit('change', '450921');
      vm.$emit('input', '450921');
    }
    picker.dispatchEvent(new Event('change', {bubbles: true}));
    picker.dispatchEvent(new Event('input', {bubbles: true}));
    return 'picker_events_dispatched';
  }
  return 'no_picker';
})()
"""
res = _eval(ws_url, js_trigger)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("trigger_change", "OK", val)

# ========== STEP 4: 点击下一步 ==========
print("\nSTEP 4: 点击 [下一步]")
time.sleep(_jitter(2.0, 4.0))

js_click_next = """
(function() {
  const btns = Array.from(document.querySelectorAll('button, span, div, a'));
  const next = btns.find(el => el.textContent.trim() === '下一步');
  if (next) { next.click(); return 'clicked_exact'; }
  const fuzzy = btns.find(el => el.textContent.includes('下一步'));
  if (fuzzy) { fuzzy.click(); return 'clicked_fuzzy'; }
  return 'not_found';
})()
"""
res = _eval(ws_url, js_click_next)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("click_next", "OK" if "clicked" in val else "FAIL", val)

# ========== STEP 5: 等待并验证跳转 + MITM ==========
print("\nSTEP 5: 等待跳转 + MITM 抓包...")

time.sleep(3.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("navigate_check_1", "OK" if "core.html" in href else "PENDING", f"href={href}")

time.sleep(3.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("navigate_check_2", "OK" if "core.html" in href else "PENDING", f"href={href}")

# 读取 MITM 日志
print("\n读取 MITM 日志...")
if MITM_LOG.exists():
    with MITM_LOG.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    
    for keyword in ["checkEstablishName", "loadCurrentLocationInfo"]:
        found = False
        for line in reversed(lines[-100:]):
            try:
                d = json.loads(line)
                if keyword in d.get("url", ""):
                    _log_step(f"mitm_{keyword}", "OK", f"status={d.get('status_code')} method={d.get('method')}")
                    found = True
                    break
            except:
                pass
        if not found:
            _log_step(f"mitm_{keyword}", "NOT_FOUND", "in last 100 lines")
else:
    _log_step("mitm_log", "MISSING", str(MITM_LOG))

# 最终验证
print("\n最终验证...")
time.sleep(2.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
title_res = _eval(ws_url, "document.title")
title = title_res.get("result", {}).get("result", {}).get("value", "")

final_status = "PASS" if ("core.html" in href and "name-check-info" in href) else "FAIL"
_log_step("final", final_status, f"href={href} title={title}")

print("\n" + "=" * 60)
print(f"执行完成: {final_status}")
print(f"日志: {STEP_LOG}")
print(f"MITM抓包: {MITM_LOG}")
