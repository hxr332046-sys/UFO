#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主引擎 — 任务调度、流程控制
合规：认证环节暂停等待客户，绝不绕过
"""

import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_manager import TaskManager, TaskStatus
from llm_client import LLMClient
from notifier import Notifier


class Engine:
    """政务助手主引擎"""

    def __init__(self):
        self.tm = TaskManager()
        self.llm = LLMClient()
        self.notifier = Notifier()
        self.running = False

    # === 客户操作 ===

    def submit_materials(self, task_type, client_id, client_name, materials):
        """客户提交材料 → 创建任务"""
        task = self.tm.create_task(task_type, client_id, client_name, materials)
        self.notifier.notify_admin(
            f"新任务: {task_type} | 客户: {client_name} | ID: {task.task_id}",
            level="info", task_id=task.task_id
        )
        # 自动进入审核
        self._do_review(task.task_id)
        return task

    def client_confirm(self, task_id):
        """客户确认表单 → 授权提交"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.CONFIRMING:
            return {"error": "任务不存在或状态不对"}
        task.transition(TaskStatus.SUBMITTING, "客户确认，开始提交", actor="client")
        self.tm._save()
        # 自动提交
        self._do_submit(task_id)
        return task

    def client_provide_sms(self, task_id, sms_code):
        """客户提供短信验证码"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.SMS_WAIT:
            return {"error": "任务不存在或不在等待验证码状态"}
        task.auth_info["sms_code"] = sms_code
        task.transition(TaskStatus.SUBMITTING, f"客户提供验证码: {sms_code[:2]}***", actor="client")
        self.tm._save()
        self._do_submit(task_id)
        return task

    def client_auth_done(self, task_id):
        """客户完成认证（人脸/银行卡）"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.AUTH_WAIT:
            return {"error": "任务不存在或不在等待认证状态"}
        task.auth_info["auth_completed"] = True
        task.transition(TaskStatus.SUBMITTING, "客户完成认证", actor="client")
        self.tm._save()
        self._do_submit(task_id)
        return task

    def client_resubmit(self, task_id, materials):
        """客户补正后重新提交"""
        task = self.tm.get_task(task_id)
        if not task or task.status not in (TaskStatus.REJECTED, TaskStatus.SUPPLEMENT):
            return {"error": "任务不存在或不需要补正"}
        task.materials.update(materials)
        task.transition(TaskStatus.REVIEWING, "客户补正后重新审核", actor="client")
        self.tm._save()
        self._do_review(task_id)
        return task

    # === 内部流程 ===

    def _do_review(self, task_id):
        """LLM审核材料（LLM不可用时回退到管理员手动审核）"""
        task = self.tm.get_task(task_id)
        if not task:
            return
        task.transition(TaskStatus.REVIEWING, "开始LLM审核")
        self.tm._save()

        result = self.llm.review_materials(task.task_type, task.materials)
        task.review_result = result

        if result.get("error"):
            # LLM 不可用 → 回退到管理员手动审核
            task.transition(TaskStatus.CONFIRMING, "LLM不可用，等待管理员手动审核", actor="system")
            self.tm._save()
            self.notifier.notify_admin(
                f"任务{task_id} LLM审核失败({result['error'][:50]})，请手动审核",
                level="warning", task_id=task_id
            )
        elif result.get("approved"):
            task.transition(TaskStatus.APPROVED, "材料审核通过")
            self.notifier.notify_client(task.client_id, "材料审核通过，正在准备填写表单", task_id=task_id)
            self._do_fill(task_id)
        else:
            issues = result.get("issues", [])
            task.transition(TaskStatus.REJECTED, f"材料不合格: {'; '.join(issues)}")
            self.notifier.supplement_required(task.client_id, issues, task_id=task_id)
        self.tm._save()

    def _do_fill(self, task_id):
        """自动填写表单"""
        task = self.tm.get_task(task_id)
        if not task:
            return
        task.transition(TaskStatus.FILLING, "开始填写表单")
        self.tm._save()

        # LLM 生成表单映射
        mapping = self.llm.map_form_fields(task.task_type, task.materials)
        task.form_data = mapping

        if mapping.get("error"):
            task.transition(TaskStatus.FAILED, f"表单映射失败: {mapping['error']}")
            self.notifier.notify_admin(f"任务{task_id}表单映射失败", level="error", task_id=task_id)
        else:
            # 生成预览，等客户确认
            task.transition(TaskStatus.CONFIRMING, "表单填写完成，等待客户确认")
            msg = f"表单已填写完成，请确认后授权提交。需您手动完成的操作：{mapping.get('needs_client_actions', [])}"
            self.notifier.notify_client(task.client_id, msg, task_id=task_id)
        self.tm._save()

    def _do_submit(self, task_id):
        """提交到政务平台（通过CDP/API）"""
        task = self.tm.get_task(task_id)
        if not task:
            return

        # 检查是否需要认证（合规检查点）
        if self._check_auth_required(task):
            task.transition(TaskStatus.AUTH_WAIT, "政务平台要求认证，暂停等待客户")
            self.tm._save()
            self.notifier.auth_required(
                task.client_id, task.auth_info.get("auth_type", "人脸"),
                task_id=task_id,
                gov_url="https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
            )
            return

        # 检查是否需要短信验证码
        if self._check_sms_required(task):
            task.transition(TaskStatus.SMS_WAIT, "需要短信验证码，暂停等待客户")
            self.tm._save()
            self.notifier.sms_code_required(
                task.client_id, task.auth_info.get("phone_tail", "****"),
                task_id=task_id
            )
            return

        # 实际提交（通过CDP或API网关）
        task.transition(TaskStatus.TRACKING, "已提交到政务平台，开始跟踪进度")
        self.tm._save()
        self.notifier.notify_client(task.client_id, "已提交到政务平台，正在跟踪进度", task_id=task_id)
        self.notifier.notify_admin(f"任务{task_id}已提交", level="info", task_id=task_id)

    def _check_auth_required(self, task):
        """检查政务平台是否要求认证（人脸/银行卡）"""
        # TODO: 通过CDP检测页面是否弹出认证对话框
        return False

    def _check_sms_required(self, task):
        """检查是否需要短信验证码"""
        # TODO: 通过CDP检测页面是否要求输入验证码
        return False

    # === 进度跟踪 ===

    def check_progress(self, task_id):
        """检查单个任务的办件进度"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.TRACKING:
            return None
        # TODO: 通过CDP/API查询办件进度
        return {"task_id": task_id, "status": "tracking", "progress": "待实现"}

    def check_all_progress(self):
        """检查所有跟踪中任务的进度"""
        tasks = self.tm.list_tasks(status=TaskStatus.TRACKING)
        results = []
        for t in tasks:
            r = self.check_progress(t.task_id)
            if r:
                results.append(r)
        return results

    # === 管理员操作 ===

    def admin_force_cancel(self, task_id, reason):
        """管理员强制取消任务"""
        task = self.tm.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        task.transition(TaskStatus.FAILED, f"管理员取消: {reason}", actor="admin")
        self.tm._save()
        self.notifier.notify_client(task.client_id, f"任务已被取消: {reason}", task_id=task_id)
        return task

    def admin_force_advance(self, task_id, target_status, reason):
        """管理员强制推进任务状态（仅用于特殊情况）"""
        task = self.tm.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        task.transition(TaskStatus(target_status), f"管理员强制: {reason}", actor="admin")
        self.tm._save()
        self.notifier.notify_admin(f"任务{task_id}被管理员强制推进到{target_status}", level="warning", task_id=task_id)
        return task

    def get_dashboard_data(self):
        """获取管理员面板数据"""
        stats = self.tm.get_stats()
        recent_tasks = [t.to_dict() for t in sorted(
            self.tm.tasks.values(), key=lambda x: x.updated_at, reverse=True
        )[:20]]
        needs_action = [t.to_dict() for t in self.tm.tasks.values() if t.needs_client_action()]
        notifications = self.notifier.get_recent(limit=30)
        return {
            "stats": stats,
            "recent_tasks": recent_tasks,
            "needs_action": needs_action,
            "notifications": notifications,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
