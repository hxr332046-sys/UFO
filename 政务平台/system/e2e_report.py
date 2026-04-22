#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E测试报告工具"""
import json, os
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "e2e_report.json")
report = {"test_time": "", "steps": [], "issues": [], "auth_findings": [], "conclusion": ""}

def load():
    global report
    if os.path.exists(REPORT):
        with open(REPORT, "r", encoding="utf-8") as f:
            report = json.load(f)

def save():
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

def log(step, data, issues=None):
    load()
    entry = {"step": step, "time": __import__("time").strftime("%H:%M:%S"), "data": data, "issues": issues or []}
    report["steps"].append(entry)
    for i in (issues or []):
        if i not in report["issues"]:
            report["issues"].append(i)
    save()
    print(f"\n[{entry['time']}] {step}")
    if isinstance(data, dict):
        for k, v in data.items():
            s = str(v)
            print(f"  {k}: {s[:120]}")
    for i in (issues or []):
        print(f"  ⚠️ {i}")

def add_auth_finding(finding):
    load()
    report["auth_findings"].append(finding)
    save()
    print(f"  🔐 认证发现: {finding}")

def set_conclusion(text):
    load()
    report["conclusion"] = text
    save()
