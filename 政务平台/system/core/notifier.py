#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通知引擎 — 给客户和管理员发通知
支持：微信、短信、邮件、系统内消息
"""

import json
import os
import time
from datetime import datetime

NOTIFY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
NOTIFY_LOG = os.path.join(NOTIFY_DIR, "notifications.jsonl")


class Notifier:
    """通知引擎：客户通知 + 管理员告警"""

    def __init__(self):
        os.makedirs(NOTIFY_DIR, exist_ok=True)

    def _log(self, target, message, notify_type, task_id=None):
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target": target,
            "type": notify_type,
            "message": message,
            "task_id": task_id
        }
        with open(NOTIFY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def notify_client(self, client_id, message, task_id=None, channel="system"):
        """通知客户"""
        entry = self._log(client_id, message, f"client_{channel}", task_id)
        print(f"[Notify→客户] {client_id}: {message[:80]}")
        # TODO: 接入微信/短信/邮件
        return entry

    def notify_admin(self, message, level="info", task_id=None):
        """通知管理员"""
        entry = self._log("admin", message, f"admin_{level}", task_id)
        print(f"[Notify→管理员][{level}] {message[:80]}")
        return entry

    def auth_required(self, client_id, auth_type, task_id=None, gov_url=None):
        """通知客户需要完成认证"""
        msg = f"政务平台要求完成{auth_type}认证。"
        if gov_url:
            msg += f"\n请打开以下链接完成认证：\n{gov_url}"
        msg += "\n认证完成后系统将自动继续。"
        self.notify_client(client_id, msg, task_id, channel="urgent")
        self.notify_admin(f"任务{task_id}等待客户{auth_type}认证", level="warning", task_id=task_id)

    def sms_code_required(self, client_id, phone_tail, task_id=None):
        """通知客户需要提供短信验证码"""
        msg = f"请提供发送到尾号{phone_tail}手机的短信验证码。"
        self.notify_client(client_id, msg, task_id, channel="urgent")

    def task_completed(self, client_id, task_type, result, task_id=None):
        """通知客户任务完成"""
        msg = f"您的{task_type}业务已办结。结果：{result}"
        self.notify_client(client_id, msg, task_id)

    def supplement_required(self, client_id, issues, task_id=None):
        """通知客户需要补正"""
        msg = f"政务平台要求补正，问题如下：\n" + "\n".join(f"• {i}" for i in issues)
        self.notify_client(client_id, msg, task_id, channel="urgent")
        self.notify_admin(f"任务{task_id}需要补正", level="warning", task_id=task_id)

    def get_recent(self, limit=50, target=None):
        """获取最近的通知记录"""
        if not os.path.exists(NOTIFY_LOG):
            return []
        entries = []
        with open(NOTIFY_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if target is None or entry.get("target") == target:
                        entries.append(entry)
                except:
                    continue
        return entries[-limit:]
