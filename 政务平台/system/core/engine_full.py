#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主引擎 — 任务调度、流程控制（完整版）
合规：认证环节暂停等待客户，绝不绕过
集成：LLM审核 + CDP自动填表 + 认证检测 + 进度跟踪
"""

import json
import time
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_manager import TaskManager, TaskStatus, STATUS_LABELS
from llm_client import LLMClient
from notifier import Notifier
from cdp_automation import CDPAutomation, TASK_ROUTES

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
for d in [DATA_DIR, SCREENSHOT_DIR]:
    os.makedirs(d, exist_ok=True)


class Engine:
    """政务助手主引擎"""

    def __init__(self):
        self.tm = TaskManager()
        self.llm = LLMClient()
        self.notifier = Notifier()
        self.cdp = CDPAutomation()
        self._tracking_thread = None
        self._tracking_running = False

    # === 客户操作 ===

    def submit_materials(self, task_type, client_id, client_name, materials):
        """客户提交材料 → 创建任务 → 后台自动审核"""
        task = self.tm.create_task(task_type, client_id, client_name, materials)
        self.notifier.notify_admin(
            f"新任务: {task_type} | 客户: {client_name} | ID: {task.task_id}",
            level="info", task_id=task.task_id
        )
        # 后台线程执行审核，避免阻塞 HTTP 服务器
        threading.Thread(target=self._do_review, args=(task.task_id,), daemon=True).start()
        return task

    def client_confirm(self, task_id):
        """客户确认表单 → 授权提交"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.CONFIRMING:
            return {"error": "任务不存在或状态不对"}
        task.transition(TaskStatus.SUBMITTING, "客户确认，开始提交", actor="client")
        self.tm._save()
        threading.Thread(target=self._do_submit, args=(task_id,), daemon=True).start()
        return task

    def client_provide_sms(self, task_id, sms_code):
        """客户提供短信验证码"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.SMS_WAIT:
            return {"error": "任务不存在或不在等待验证码状态"}
        task.auth_info["sms_code"] = sms_code
        task.transition(TaskStatus.SUBMITTING, f"客户提供验证码: {sms_code[:2]}***", actor="client")
        self.tm._save()
        threading.Thread(target=self._do_submit_with_sms, args=(task_id, sms_code), daemon=True).start()
        return task

    def client_auth_done(self, task_id):
        """客户完成认证（人脸/银行卡）"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.AUTH_WAIT:
            return {"error": "任务不存在或不在等待认证状态"}
        task.auth_info["auth_completed"] = True
        task.transition(TaskStatus.SUBMITTING, "客户完成认证", actor="client")
        self.tm._save()
        threading.Thread(target=self._do_submit, args=(task_id,), daemon=True).start()
        return task

    def client_resubmit(self, task_id, materials):
        """客户补正后重新提交"""
        task = self.tm.get_task(task_id)
        if not task or task.status not in (TaskStatus.REJECTED, TaskStatus.SUPPLEMENT):
            return {"error": "任务不存在或不需要补正"}
        task.materials.update(materials)
        task.transition(TaskStatus.REVIEWING, "客户补正后重新审核", actor="client")
        self.tm._save()
        threading.Thread(target=self._do_review, args=(task_id,), daemon=True).start()
        return task

    # === 内部流程 ===

    def _do_review(self, task_id):
        """LLM审核材料"""
        task = self.tm.get_task(task_id)
        if not task:
            return
        task.transition(TaskStatus.REVIEWING, "开始LLM审核")
        self.tm._save()

        result = self.llm.review_materials(task.task_type, task.materials)
        task.review_result = result

        if result.get("error"):
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
        """自动填写表单：LLM映射 + CDP执行"""
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
            self.tm._save()
            return

        # CDP 自动填表
        route = TASK_ROUTES.get(task.task_type, TASK_ROUTES.get("enterprise_zone"))
        nav_result = self.cdp.navigate_to_route(route)
        task.form_data["navigation"] = nav_result

        if nav_result.get("error"):
            task.transition(TaskStatus.FAILED, f"导航失败: {nav_result['error']}")
            self.notifier.notify_admin(f"任务{task_id}导航失败", level="error", task_id=task_id)
            self.tm._save()
            return

        # 执行填写
        fill_result = self.cdp.fill_form(mapping)
        task.form_data["fill_result"] = fill_result

        # 截图预览
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{task_id}_preview.png")
        self.cdp.screenshot(screenshot_path)
        task.form_data["screenshot"] = screenshot_path

        # 生成预览，等客户确认
        task.transition(TaskStatus.CONFIRMING, "表单填写完成，等待客户确认")
        msg = f"表单已填写完成，请确认后授权提交。"
        needs_client = mapping.get("needs_client_actions", [])
        if needs_client:
            msg += f" 需您手动完成的操作：{needs_client}"
        self.notifier.notify_client(task.client_id, msg, task_id=task_id)
        self.tm._save()

    def _do_submit_with_sms(self, task_id, sms_code):
        """填入短信验证码后提交"""
        try:
            self.cdp.ensure_connected()
            self.cdp.fill_sms_code(sms_code)
            time.sleep(1)
        except Exception as e:
            task = self.tm.get_task(task_id)
            if task:
                task.auth_info["sms_fill_error"] = str(e)
                self.tm._save()
        self._do_submit(task_id)

    def _do_submit(self, task_id):
        """提交到政务平台（通过CDP）"""
        task = self.tm.get_task(task_id)
        if not task:
            return

        # CDP 检测认证要求
        auth_check = self.cdp.check_auth_required()
        if auth_check.get("auth_required"):
            auth_type = auth_check.get("auth_type", "人脸")
            task.auth_info["auth_type"] = auth_type
            task.auth_info["auth_message"] = auth_check.get("message", auth_check.get("dialog_text", ""))
            task.transition(TaskStatus.AUTH_WAIT, f"政务平台要求{auth_type}认证，暂停等待客户")
            self.tm._save()
            self.notifier.auth_required(
                task.client_id, auth_type,
                task_id=task_id,
                gov_url="https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
            )
            return

        # 如果之前有短信验证码，填入后点提交
        if task.auth_info.get("sms_code"):
            sms_result = self.cdp.fill_sms_code(task.auth_info["sms_code"])
            task.auth_info["sms_fill_result"] = sms_result
            time.sleep(1)

        # 点击提交按钮
        submit_result = self.cdp.click_button("提交")
        task.gov_response["submit_result"] = submit_result
        time.sleep(3)

        # 再次检测认证（提交后可能触发）
        auth_check2 = self.cdp.check_auth_required()
        if auth_check2.get("auth_required"):
            auth_type = auth_check2.get("auth_type", "人脸")
            task.auth_info["auth_type"] = auth_type
            task.transition(TaskStatus.AUTH_WAIT, f"提交后要求{auth_type}认证，暂停等待客户")
            self.tm._save()
            self.notifier.auth_required(
                task.client_id, auth_type, task_id=task_id,
                gov_url="https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
            )
            return

        # 截图提交结果
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{task_id}_submitted.png")
        self.cdp.screenshot(screenshot_path)
        task.gov_response["screenshot"] = screenshot_path

        # 检测提交后的页面反馈
        page_feedback = self.cdp.check_auth_required()  # 复用检测逻辑看页面状态
        task.gov_response["page_feedback"] = page_feedback

        task.transition(TaskStatus.TRACKING, "已提交到政务平台，开始跟踪进度")
        self.tm._save()
        self.notifier.notify_client(task.client_id, "已提交到政务平台，正在跟踪进度", task_id=task_id)
        self.notifier.notify_admin(f"任务{task_id}已提交", level="info", task_id=task_id)

        # 启动进度跟踪
        self._start_tracking()

    # === 进度跟踪 ===

    def _start_tracking(self):
        """启动进度跟踪线程"""
        if self._tracking_running:
            return
        self._tracking_running = True
        self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._tracking_thread.start()

    def _tracking_loop(self):
        """定期检查所有跟踪中任务的进度"""
        while self._tracking_running:
            try:
                tasks = self.tm.list_tasks(status=TaskStatus.TRACKING)
                if not tasks:
                    self._tracking_running = False
                    return
                for t in tasks:
                    progress = self._check_single_progress(t.task_id)
                    if progress:
                        t.gov_response["latest_progress"] = progress
                        # 检测是否需要补正
                        if progress.get("need_supplement"):
                            t.transition(TaskStatus.SUPPLEMENT, "政务平台要求补正", actor="gov")
                            self.tm._save()
                            self.notifier.supplement_required(
                                t.client_id, progress.get("supplement_issues", []),
                                task_id=t.task_id
                            )
                        elif progress.get("completed"):
                            t.transition(TaskStatus.COMPLETED, "办件完成", actor="gov")
                            self.tm._save()
                            self.notifier.task_completed(t.client_id, t.task_type, progress.get("result", ""), task_id=t.task_id)
                self.tm._save()
            except Exception as e:
                print(f"[Tracking] Error: {e}")
            time.sleep(120)  # 每2分钟检查一次

    def _check_single_progress(self, task_id):
        """检查单个任务的办件进度"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.TRACKING:
            return None

        # 通过 CDP 查询办件进度
        progress_data = self.cdp.check_progress()
        if not progress_data or progress_data.get("error"):
            return None

        # LLM 分析进度
        analysis = self.llm.analyze_gov_response(progress_data)
        return {
            "raw_data": progress_data,
            "analysis": analysis,
            "need_supplement": analysis.get("result") == "supplement_needed",
            "supplement_issues": analysis.get("issues", []),
            "completed": analysis.get("result") == "approved",
            "result": analysis.get("summary", ""),
        }

    def check_progress(self, task_id):
        """手动检查单个任务进度"""
        return self._check_single_progress(task_id)

    def check_all_progress(self):
        """手动检查所有跟踪中任务的进度"""
        tasks = self.tm.list_tasks(status=TaskStatus.TRACKING)
        results = []
        for t in tasks:
            r = self._check_single_progress(t.task_id)
            if r:
                results.append({"task_id": t.task_id, **r})
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
        """管理员强制推进任务状态"""
        task = self.tm.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        task.transition(TaskStatus(target_status), f"管理员强制: {reason}", actor="admin")
        self.tm._save()
        self.notifier.notify_admin(f"任务{task_id}被管理员强制推进到{target_status}", level="warning", task_id=task_id)
        return task

    def admin_approve(self, task_id):
        """管理员手动审核通过（LLM不可用时）"""
        task = self.tm.get_task(task_id)
        if not task or task.status != TaskStatus.CONFIRMING:
            return {"error": "任务不存在或不在待审核状态"}
        task.transition(TaskStatus.APPROVED, "管理员手动审核通过", actor="admin")
        self.tm._save()
        threading.Thread(target=self._do_fill, args=(task_id,), daemon=True).start()
        return task

    def admin_get_cdp_status(self):
        """获取 CDP 浏览器状态"""
        connected = self.cdp.ensure_connected()
        token = self.cdp.get_token() if connected else None
        page_info = None
        if connected:
            page_info = self.cdp.navigate_to_route.__func__  # just check connection
        return {
            "cdp_connected": connected,
            "token": token,
        }

    def get_dashboard_data(self):
        """获取管理员面板数据"""
        stats = self.tm.get_stats()
        recent_tasks = [t.to_dict() for t in sorted(
            self.tm.tasks.values(), key=lambda x: x.updated_at, reverse=True
        )[:20]]
        needs_action = [t.to_dict() for t in self.tm.tasks.values() if t.needs_client_action()]
        notifications = self.notifier.get_recent(limit=30)
        cdp_status = self.admin_get_cdp_status()
        return {
            "stats": stats,
            "recent_tasks": recent_tasks,
            "needs_action": needs_action,
            "notifications": notifications,
            "cdp_status": cdp_status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
