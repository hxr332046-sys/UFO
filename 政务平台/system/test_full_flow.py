#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整流程测试：LLM审核通过 → 填表 → 确认 → 提交"""
import requests, json, time

BASE = "http://localhost:9090"

# 创建一个材料完整的变更登记任务（变更登记比设立登记简单，更容易通过）
print("=== 1. 创建变更登记任务 ===")
r = requests.post(f"{BASE}/api/tasks", json={
    "task_type": "change",
    "client_id": "C003",
    "client_name": "广西华信科技有限公司",
    "materials": {
        "company_name": "广西华信科技有限公司",
        "unified_social_credit_code": "91450100MA5KWG2E5X",
        "change_type": "经营范围变更",
        "original_business_scope": "软件开发、信息技术咨询服务",
        "new_business_scope": "软件开发、信息技术咨询服务、数据处理和存储支持服务、人工智能应用软件开发",
        "legal_person_name": "王建国",
        "legal_person_id_number": "450102198501151234",
        "contact_phone": "0771-5551234",
        "change_reason": "公司业务拓展需要，增加数据处理和AI相关业务",
        "resolution_document": "已上传股东会决议扫描件",
        "business_license_copy": "已上传营业执照副本扫描件",
        "legal_person_id_copy": "已上传法定代表人身份证扫描件",
    }
}, timeout=60)
t = r.json()
task_id = t['task_id']
print(f"  Task: {task_id} Status: {t['status']} Label: {t.get('status_label','')}")

if t.get('review_result'):
    print(f"  Approved: {t['review_result'].get('approved')}")
    print(f"  Summary: {t['review_result'].get('summary','')[:150]}")
    if t['review_result'].get('issues'):
        for i in t['review_result']['issues']:
            print(f"  Issue: {i}")

# 如果到了 confirming，查看表单映射结果
if t['status'] in ('confirming', 'approved', 'filling'):
    print(f"\n=== 2. 查看任务详情 ===")
    r2 = requests.get(f"{BASE}/api/tasks/{task_id}", timeout=10)
    detail = r2.json()
    print(f"  Status: {detail['status_label']}")
    if detail.get('form_data', {}).get('fields'):
        print(f"  Form fields mapped:")
        for k, v in list(detail['form_data']['fields'].items())[:10]:
            val = v.get('value', v) if isinstance(v, dict) else v
            auto = '✅' if (v.get('auto_fill', True) if isinstance(v, dict) else True) else '⚠️'
            print(f"    {auto} {k}: {str(val)[:50]}")
    if detail.get('form_data', {}).get('needs_client_actions'):
        print(f"  Needs client: {detail['form_data']['needs_client_actions']}")

# 管理员审核通过（如果还在 confirming）
if t['status'] == 'confirming':
    print(f"\n=== 3. 管理员审核通过 ===")
    r3 = requests.post(f"{BASE}/api/tasks/{task_id}/approve", timeout=60)
    t3 = r3.json()
    print(f"  After approve: {t3.get('status', t3.get('error',''))} {t3.get('status_label','')}")
    if t3.get('form_data', {}).get('fields'):
        print(f"  Form fields:")
        for k, v in list(t3['form_data']['fields'].items())[:8]:
            val = v.get('value', v) if isinstance(v, dict) else v
            print(f"    {k}: {str(val)[:50]}")

# 面板最终状态
print(f"\n=== 面板状态 ===")
rd = requests.get(f"{BASE}/api/dashboard", timeout=10).json()
for t in rd['recent_tasks']:
    print(f"  {t['task_id']} | {t['client_name']} | {t['status_label']}")
print(f"  CDP: {'connected' if rd.get('cdp_status',{}).get('cdp_connected') else 'disconnected'}")
