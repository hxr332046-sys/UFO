#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
类人单步执行 guide/base -> 下一步 测试 (v2)
区划通过 Vue 组件直接设置（DOM picker 数据为空无法点击）
其余步骤保持类人点击
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
STEP_LOG = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "records" / "human_steps_guide_base_v2.jsonl"

def _jitter(min_sec=2.0, max_sec=4.0):
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

def _click_by_text(ws_url: str, text: str, tag_hint: str = "") -> bool:
    expr = f"""
    (function() {{
      const btns = Array.from(document.querySelectorAll('button, span, div, a, label'));
      const exact = btns.find(el => el.textContent.trim() === '{text}');
      if (exact) {{ exact.click(); return 'clicked_exact'; }}
      const fuzzy = btns.find(el => el.textContent.includes('{text}'));
      if (fuzzy) {{ fuzzy.click(); return 'clicked_fuzzy'; }}
      return 'not_found';
    }})()
    """
    res = _eval(ws_url, expr)
    val = res.get("result", {}).get("result", {}).get("value", "")
    return "clicked" in val

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

# ========== STEP 1: 选企业类型 ==========
print("\nSTEP 1: 选 [全部企业类型] -> [个人独资企业]")
time.sleep(_jitter(1.5, 3.0))

_log_step("ent_type", "attempt", "clicking 全部企业类型")
_click_by_text(ws_url, "全部企业类型")

time.sleep(_jitter(1.5, 3.0))

_log_step("ent_type", "attempt", "clicking 个人独资企业")
_click_by_text(ws_url, "个人独资企业")

time.sleep(_jitter(1.0, 2.0))

# 验证
expr = "document.body.innerText.includes('个人独资') ? 'found' : 'not_found'"
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("ent_type_verify", "OK" if "found" in val else "WARN", val)

# ========== STEP 2: 选名称申请状态 ==========
print("\nSTEP 2: 选 [未申请]")
time.sleep(_jitter(1.5, 3.0))

_log_step("name_status", "attempt", "clicking 未申请")
_click_by_text(ws_url, "未申请")

time.sleep(_jitter(1.0, 2.0))

expr = "document.body.innerText.includes('未申请') ? 'found' : 'not_found'"
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("name_status_verify", "OK" if "found" in val else "WARN", val)

# ========== STEP 3: 设置区划 (Vue 组件直接赋值) ==========
print("\nSTEP 3: 设置区划 [广西 > 玉林 > 容县] (Vue 组件直接赋值)")
time.sleep(_jitter(2.0, 4.0))

# 找到 Vue 表单并直接设置区划值
js_set_district = """
(function() {
  // 遍历所有元素找 Vue 实例
  const all = Array.from(document.querySelectorAll('*'));
  let targetVm = null;
  
  for (const el of all) {
    const vm = el.__vue__ || el.__VUE__;
    if (!vm) continue;
    
    // 找包含 form 且有 distCode 字段的组件
    let form = vm.$refs?.form || vm.form || vm.$data?.form;
    if (!form && vm.$children) {
      for (const child of vm.$children) {
        if (child.form) { form = child.form; targetVm = child; break; }
        if (child.$data && child.$data.form) { form = child.$data.form; targetVm = child; break; }
      }
    }
    
    if (form && (form.distCode !== undefined || form.distCodeArr !== undefined)) {
      targetVm = vm;
      break;
    }
  }
  
  if (!targetVm) {
    // 尝试通过全局 app 找
    const app = document.querySelector('#app');
    if (app) {
      const appVm = app.__vue__ || app.__VUE__;
      if (appVm) {
        let form = appVm.$refs?.form || appVm.form || appVm.$data?.form;
        if (!form && appVm.$children) {
          for (const child of appVm.$children) {
            if (child.form) { form = child.form; targetVm = child; break; }
            if (child.$data && child.$data.form) { form = child.$data.form; targetVm = child; break; }
          }
        }
        if (form && (form.distCode !== undefined || form.distCodeArr !== undefined)) {
          targetVm = appVm;
        }
      }
    }
  }
  
  if (!targetVm) return 'no_vue_form_found';
  
  let form = targetVm.$refs?.form || targetVm.form || targetVm.$data?.form;
  if (!form && targetVm.$children) {
    for (const child of targetVm.$children) {
      if (child.form) { form = child.form; break; }
      if (child.$data && child.$data.form) { form = child.$data.form; break; }
    }
  }
  
  if (!form) return 'no_form';
  
  // 直接设置值
  const before = JSON.stringify({distCode: form.distCode, distCodeArr: form.distCodeArr, address: form.address});
  
  form.distCode = '450921';
  form.distCodeArr = ['450000', '450900', '450921'];
  form.address = '广西壮族自治区玉林市容县';
  
  // 如果有 havaAdress 字段，也设置（之前已知的问题字段）
  if (form.havaAdress !== undefined) form.havaAdress = '0';
  if (form.havaAddress !== undefined) form.havaAddress = '0';
  
  // 触发 Vue 响应式更新
  if (targetVm.$forceUpdate) targetVm.$forceUpdate();
  
  const after = JSON.stringify({distCode: form.distCode, distCodeArr: form.distCodeArr, address: form.address});
  return JSON.stringify({status: 'set_ok', before: before, after: after});
})()
"""
res = _eval(ws_url, js_set_district)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("district_set", "OK" if "set_ok" in val else "FAIL", val)

time.sleep(_jitter(1.0, 2.0))

# 验证区划
expr = "document.body.innerText.includes('容县') ? 'rongxian_found' : 'not_found'"
res = _eval(ws_url, expr)
val = res.get("result", {}).get("result", {}).get("value", "")
_log_step("district_verify", "OK" if "rongxian" in val else "WARN", val)

# ========== STEP 4: 点下一步 ==========
print("\nSTEP 4: 点击 [下一步]")
time.sleep(_jitter(2.0, 4.0))

_log_step("click_next", "attempt", "clicking 下一步")
_click_by_text(ws_url, "下一步")

# ========== STEP 5: 等待跳转并抓包验证 ==========
print("\nSTEP 5: 等待页面跳转 + MITM 抓包...")

time.sleep(3.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("navigate_check_1", "OK" if "core.html" in href else "PENDING", f"href={href}")

time.sleep(3.0)
href_res = _eval(ws_url, "location.href")
href = href_res.get("result", {}).get("result", {}).get("value", "")
_log_step("navigate_check_2", "OK" if "core.html" in href else "PENDING", f"href={href}")

# 等 MITM 里的 checkEstablishName
print("\n等待 MITM checkEstablishName...")
start = time.time()
mitm_found = None
while time.time() - start < 25.0:
    if MITM_LOG.exists():
        with MITM_LOG.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-50:]):
            try:
                d = json.loads(line)
                if "checkEstablishName" in d.get("url", ""):
                    mitm_found = d
                    break
            except:
                pass
        if mitm_found:
            break
    time.sleep(0.5)

if mitm_found:
    _log_step("mitm_checkEstablishName", "OK", f"status={mitm_found.get('status_code')} url={mitm_found.get('url','')[:80]}")
    # 读取响应体
    resp_body = mitm_found.get("resp_body", "")[:200]
    _log_step("mitm_checkEstablishName_resp", "OK", resp_body)
else:
    _log_step("mitm_checkEstablishName", "TIMEOUT", "not found in 25s")

# 等 operationBusinessDataInfo
print("等待 MITM operationBusinessDataInfo...")
start = time.time()
mitm_found2 = None
while time.time() - start < 30.0:
    if MITM_LOG.exists():
        with MITM_LOG.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-50:]):
            try:
                d = json.loads(line)
                if "operationBusinessDataInfo" in d.get("url", ""):
                    mitm_found2 = d
                    break
            except:
                pass
        if mitm_found2:
            break
    time.sleep(0.5)

if mitm_found2:
    _log_step("mitm_operationBusinessDataInfo", "OK", f"status={mitm_found2.get('status_code')} url={mitm_found2.get('url','')[:80]}")
else:
    _log_step("mitm_operationBusinessDataInfo", "TIMEOUT", "not found in 30s")

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
