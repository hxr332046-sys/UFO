#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Step1: 提交材料 → LLM审核"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, load, save
import requests, time, json

load()
report = __import__("e2e_report").report
report["test_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
save()

MATERIALS = {
    "company_name": "广西智信数据科技有限公司",
    "company_type": "有限责任公司（自然人独资）",
    "reg_capital": "100万元人民币",
    "paid_capital": "100万元人民币",
    "capital_contribution_method": "货币",
    "business_scope_main": "软件开发、信息技术咨询服务、数据处理和存储支持服务",
    "business_scope_extra": "人工智能应用软件开发、网络技术服务",
    "registered_address_province": "广西壮族自治区",
    "registered_address_city": "南宁市",
    "registered_address_district": "青秀区",
    "registered_address_detail": "民族大道166号上东国际T3栋1801室",
    "business_term": "长期",
    "legal_person_name": "陈明辉",
    "legal_person_id_type": "居民身份证",
    "legal_person_id_number": "450103199001151234",
    "legal_person_phone": "13877151234",
    "legal_person_email": "chenmh@example.com",
    "legal_person_nationality": "中国",
    "legal_person_position": "执行董事兼经理",
    "shareholder_name": "陈明辉",
    "shareholder_id_number": "450103199001151234",
    "shareholder_contribution_amount": "100万元",
    "shareholder_contribution_ratio": "100%",
    "shareholder_contribution_method": "货币",
    "supervisor_name": "李芳",
    "supervisor_id_number": "450103199205051234",
    "supervisor_phone": "13877159876",
    "supervisor_position": "监事",
    "financial_officer_name": "陈明辉",
    "financial_officer_phone": "13877151234",
    "contact_phone": "13877151234",
    "contact_email": "chenmh@example.com",
    "company_articles_uploaded": True,
    "legal_person_id_copy_uploaded": True,
    "business_premise_proof_uploaded": True,
    "shareholder_id_copy_uploaded": True,
    "supervisor_id_copy_uploaded": True,
    "name_pre_approval_uploaded": True,
}

# Step 1: 创建任务
r = requests.post("http://localhost:9090/api/tasks", json={
    "task_type": "establish",
    "client_id": "TEST001",
    "client_name": "广西智信数据科技有限公司",
    "materials": MATERIALS
}, timeout=10)
t = r.json()
task_id = t["task_id"]
log("1.创建任务", {"task_id": task_id, "status": t["status"], "label": t.get("status_label","")})

# Step 2: 等待LLM审核
print("  等待LLM审核...")
for _ in range(30):
    time.sleep(2)
    t2 = requests.get(f"http://localhost:9090/api/tasks/{task_id}", timeout=10).json()
    if t2["status"] not in ("created", "reviewing"):
        break

issues = []
rr = t2.get("review_result", {})
if not rr.get("approved"):
    issues = rr.get("issues", [])

log("2.LLM审核结果", {
    "status": t2["status"],
    "label": t2.get("status_label",""),
    "approved": rr.get("approved"),
    "risk": rr.get("risk_level",""),
    "summary": (rr.get("summary","") or "")[:200],
    "issues_count": len(issues),
    "form_mapped": bool(t2.get("form_data",{}).get("fields")),
    "needs_action": t2.get("needs_client_action"),
    "action_msg": t2.get("client_action_message",""),
}, issues=issues)

# 保存 task_id 供后续步骤使用
with open(os.path.join(os.path.dirname(__file__), "..", "data", "e2e_task_id.txt"), "w") as f:
    f.write(task_id)

print(f"\n  Task ID saved: {task_id}")
print(f"  Current status: {t2['status']} / {t2.get('status_label','')}")
