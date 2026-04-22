#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""创建演示任务"""
import requests, json

tasks = [
    {"task_type": "establish", "client_id": "C001", "client_name": "南宁某某科技有限公司",
     "materials": {"company_name": "南宁某某科技有限公司", "reg_capital": "100万", "business_scope": "软件开发", "legal_person": "张三"}},
    {"task_type": "change", "client_id": "C002", "client_name": "柳州某某贸易公司",
     "materials": {"change_type": "经营范围变更", "new_scope": "贸易+餐饮服务"}},
    {"task_type": "establish", "client_id": "C003", "client_name": "桂林某某餐饮管理",
     "materials": {"company_name": "桂林某某餐饮管理有限公司"}},
]

for t in tasks:
    r = requests.post("http://localhost:9090/api/tasks", json=t, timeout=5)
    d = r.json()
    print(f"Created: {d['task_id']} status={d['status']} client={d.get('client_name','')}")
