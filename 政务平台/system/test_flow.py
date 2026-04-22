#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端测试：创建任务 → LLM审核 → 查看结果"""
import requests, json, time

BASE = "http://localhost:9090"

# 1. 创建任务（材料完整的设立登记）
print("=== 1. 创建任务 ===")
r = requests.post(f"{BASE}/api/tasks", json={
    "task_type": "establish",
    "client_id": "C001",
    "client_name": "南宁某某科技有限公司",
    "materials": {
        "company_name": "南宁某某科技有限公司",
        "company_type": "有限责任公司",
        "reg_capital": "100万元",
        "business_scope": "软件开发、信息技术服务",
        "legal_person_name": "张三",
        "legal_person_id": "450921198812051251",
        "legal_person_phone": "13800138000",
        "registered_address": "南宁市青秀区民族大道100号",
        "shareholders": "张三 100%",
        "supervisor": "李四",
    }
}, timeout=30)
t = r.json()
print(f"  Task: {t['task_id']} Status: {t['status']} Label: {t.get('status_label','')}")
if t.get('review_result'):
    print(f"  Review: approved={t['review_result'].get('approved')} issues={t['review_result'].get('issues',[])}")
    print(f"  Summary: {t['review_result'].get('summary','')[:100]}")

# 2. 创建一个材料不完整的任务
print("\n=== 2. 创建不完整任务 ===")
r2 = requests.post(f"{BASE}/api/tasks", json={
    "task_type": "establish",
    "client_id": "C002",
    "client_name": "柳州某某贸易公司",
    "materials": {
        "company_name": "柳州某某贸易公司",
    }
}, timeout=30)
t2 = r2.json()
print(f"  Task: {t2['task_id']} Status: {t2['status']} Label: {t2.get('status_label','')}")
if t2.get('review_result'):
    print(f"  Review: approved={t2['review_result'].get('approved')} issues={t2['review_result'].get('issues',[])}")
    print(f"  Summary: {t2['review_result'].get('summary','')[:100]}")

# 3. 查看面板数据
print("\n=== 3. 面板数据 ===")
r3 = requests.get(f"{BASE}/api/dashboard", timeout=10)
d = r3.json()
print(f"  Total: {d['stats']['total']}")
print(f"  CDP: {'connected' if d.get('cdp_status',{}).get('cdp_connected') else 'not connected'}")
for t in d['recent_tasks']:
    print(f"  {t['task_id']} | {t['client_name']} | {t['status_label']} | needs_action={t['needs_client_action']}")
