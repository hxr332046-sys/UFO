#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务管理器 — 状态机驱动，合规流程控制
认证环节必须暂停等待客户完成，绝不绕过
"""

import json
import time
import os
import uuid
from enum import Enum
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")


class TaskStatus(str, Enum):
    CREATED = "created"
    REVIEWING = "reviewing"
    REJECTED = "rejected"
    APPROVED = "approved"
    FILLING = "filling"
    CONFIRMING = "confirming"
    SUBMITTING = "submitting"
    AUTH_WAIT = "auth_wait"
    SMS_WAIT = "sms_wait"
    TRACKING = "tracking"
    SUPPLEMENT = "supplement"
    COMPLETED = "completed"
    FAILED = "failed"


CLIENT_ACTION_STATES = {
    TaskStatus.REJECTED: "材料不合格，请补正后重新提交",
    TaskStatus.CONFIRMING: "请确认表单预览无误后授权提交",
    TaskStatus.AUTH_WAIT: "政务平台要求认证，请完成人脸/银行卡认证",
    TaskStatus.SMS_WAIT: "请提供收到的短信验证码",
    TaskStatus.SUPPLEMENT: "政务平台要求补正，请查看补正要求",
}

STATUS_LABELS = {
    TaskStatus.CREATED: "已创建",
    TaskStatus.REVIEWING: "LLM审核中",
    TaskStatus.REJECTED: "需补正",
    TaskStatus.APPROVED: "审核通过",
    TaskStatus.FILLING: "自动填表中",
    TaskStatus.CONFIRMING: "等待客户确认",
    TaskStatus.SUBMITTING: "提交中",
    TaskStatus.AUTH_WAIT: "等待客户认证",
    TaskStatus.SMS_WAIT: "等待验证码",
    TaskStatus.TRACKING: "跟踪进度中",
    TaskStatus.SUPPLEMENT: "需补正材料",
    TaskStatus.COMPLETED: "已办结",
    TaskStatus.FAILED: "失败",
}


class Task:
    def __init__(self, task_type, client_id, client_name="", materials=None):
        self.task_id = str(uuid.uuid4())[:8]
        self.task_type = task_type
        self.client_id = client_id
        self.client_name = client_name
        self.materials = materials or {}
        self.status = TaskStatus.CREATED
        self.history = []
        self.form_data = {}
        self.gov_response = {}
        self.auth_info = {}
        self.review_result = {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self._log(TaskStatus.CREATED, "任务创建")

    def _log(self, status, message, actor="system"):
        self.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status.value if isinstance(status, TaskStatus) else status,
            "message": message,
            "actor": actor
        })
        self.updated_at = datetime.now().isoformat()

    def transition(self, new_status, message="", actor="system"):
        old = self.status
        self.status = new_status
        self._log(new_status, message or f"{old.value} → {new_status.value}", actor)
        return self.needs_client_action()

    def needs_client_action(self):
        return self.status in CLIENT_ACTION_STATES

    def client_action_message(self):
        return CLIENT_ACTION_STATES.get(self.status, "")

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "client_id": self.client_id,
            "client_name": self.client_name,
            "status": self.status.value,
            "status_label": STATUS_LABELS.get(self.status, self.status.value),
            "materials": self.materials,
            "form_data": self.form_data,
            "gov_response": self.gov_response,
            "auth_info": self.auth_info,
            "review_result": self.review_result,
            "needs_client_action": self.needs_client_action(),
            "client_action_message": self.client_action_message(),
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskManager:
    def __init__(self):
        self.tasks = {}
        self._load()

    def _load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for t in data.get("tasks", []):
                    task = Task(t["task_type"], t["client_id"], t.get("client_name", ""), t.get("materials", {}))
                    task.task_id = t["task_id"]
                    task.status = TaskStatus(t["status"])
                    task.form_data = t.get("form_data", {})
                    task.gov_response = t.get("gov_response", {})
                    task.auth_info = t.get("auth_info", {})
                    task.review_result = t.get("review_result", {})
                    task.history = t.get("history", [])
                    task.created_at = t.get("created_at", task.created_at)
                    task.updated_at = t.get("updated_at", task.updated_at)
                    self.tasks[task.task_id] = task

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {"tasks": [t.to_dict() for t in self.tasks.values()]}
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_task(self, task_type, client_id, client_name="", materials=None):
        task = Task(task_type, client_id, client_name, materials)
        self.tasks[task.task_id] = task
        self._save()
        return task

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def update_task(self, task_id, **kwargs):
        task = self.tasks.get(task_id)
        if not task:
            return None
        if "status" in kwargs:
            msg = kwargs.pop("message", "")
            actor = kwargs.pop("actor", "system")
            task.transition(kwargs.pop("status"), msg, actor)
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        self._save()
        return task

    def list_tasks(self, status=None, client_id=None):
        result = list(self.tasks.values())
        if status:
            result = [t for t in result if t.status == status]
        if client_id:
            result = [t for t in result if t.client_id == client_id]
        return result

    def get_stats(self):
        stats = {}
        for s in TaskStatus:
            stats[s.value] = 0
        for t in self.tasks.values():
            stats[t.status.value] = stats.get(t.status.value, 0) + 1
        needs_action = sum(1 for t in self.tasks.values() if t.needs_client_action())
        return {
            "total": len(self.tasks),
            "needs_client_action": needs_action,
            "by_status": stats,
            "status_labels": {s.value: STATUS_LABELS[s] for s in TaskStatus},
        }
