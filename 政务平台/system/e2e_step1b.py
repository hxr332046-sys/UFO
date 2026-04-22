#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step1b: 修正材料后重新提交"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log
import requests, time, json

# 读取 task_id
with open(os.path.join(os.path.dirname(__file__), "..", "data", "e2e_task_id.txt"), "r") as f:
    task_id = f.read().strip()

# 修正材料：1.财务负责人换人 2.实缴资本改为0
log("1b.修正材料", {
    "fix1": "财务负责人改为独立人员张丽华",
    "fix2": "实缴资本改为0（认缴制）"
})

r = requests.post(f"http://localhost:9090/api/tasks/{task_id}/resubmit", json={
    "materials": {
        "paid_capital": "0万元（认缴制）",
        "financial_officer_name": "张丽华",
        "financial_officer_phone": "13877158888",
        "financial_officer_id_number": "450103199308081234",
    }
}, timeout=10)
t = r.json()
log("1b.重新提交结果", {"status": t.get("status"), "label": t.get("status_label","")})

# 等待审核
print("  等待LLM重新审核...")
for _ in range(30):
    time.sleep(2)
    t2 = requests.get(f"http://localhost:9090/api/tasks/{task_id}", timeout=10).json()
    if t2["status"] not in ("created", "reviewing"):
        break

rr = t2.get("review_result", {})
log("1b.重新审核结果", {
    "status": t2["status"],
    "label": t2.get("status_label",""),
    "approved": rr.get("approved"),
    "risk": rr.get("risk_level",""),
    "summary": (rr.get("summary","") or "")[:200],
    "issues": rr.get("issues", []),
    "form_mapped": bool(t2.get("form_data",{}).get("fields")),
    "needs_action": t2.get("needs_client_action"),
}, issues=rr.get("issues",[]))

# 如果审核通过，记录表单映射
if t2.get("form_data", {}).get("fields"):
    fields = t2["form_data"]["fields"]
    log("1b.表单映射详情", {
        "field_count": len(fields),
        "fields": {k: (v.get("value","") if isinstance(v,dict) else str(v))[:60] for k,v in list(fields.items())[:20]}
    })
    needs_client = t2.get("form_data",{}).get("needs_client_actions",[])
    if needs_client:
        log("1b.需客户手动操作", {"actions": needs_client})
