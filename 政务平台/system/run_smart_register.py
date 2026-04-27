#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能注册执行器 v2 — 基于 Pipeline 编排器框架

用法:
  .\.venv-portal\Scripts\python.exe system\run_smart_register.py --case docs\case_美的为.json
  .\.venv-portal\Scripts\python.exe system\run_smart_register.py --case docs\case_美的为.json --login
  .\.venv-portal\Scripts\python.exe system\run_smart_register.py --case docs\case_美的为.json --resume

特性:
  ✅ 启动前检查 Auth 有效性
  ✅ 启动前查办件列表防重复登记
  ✅ Pipeline 引擎 — 统一步骤协议
  ✅ Hook 插件 — 日志/限流/交互纠错/状态提取/结果写入
  ✅ 断点续跑 — Phase 2 中断后从断点恢复
  ✅ 核名交互纠错 — 禁限词暂停、改名原地恢复
  ✅ Phase 1 → Phase 2 自动衔接
  ✅ 到 PreSubmitSuccess 停（可选 --submit 执行最终提交）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
requests.packages.urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system"))

from orchestrator import Pipeline, PipelineContext, StepSpec, StepResult, PipelineResult
from orchestrator.hooks import (
    LoggingHook, ThrottleHook, StateExtractorHook,
    NameCorrectionHook, ResultWriterHook, default_hooks, full_hooks,
)
from orchestrator.checkpoint import Checkpoint, CheckpointHook
from orchestrator.adapters import Phase1Adapter, Phase2Adapter
from node_asset_exporter import export_latest_node_assets

RECORDS_DIR = ROOT / "dashboard" / "data" / "records"
CHECKPOINT_DIR = ROOT / "dashboard" / "data" / "checkpoints"
ASSETS_DIR = ROOT / "dashboard" / "data" / "assets"
PHASE2_PROGRESS_CONTRACT_VERSION = 8

# ─── 颜色输出 ───
def _c(text: str, color: str) -> str:
    codes = {"r": "31", "g": "32", "y": "33", "b": "34", "m": "35", "c": "36", "w": "37"}
    return f"\033[{codes.get(color, '37')}m{text}\033[0m"

def info(msg: str):  print(_c(f"  ℹ {msg}", "c"))
def ok(msg: str):    print(_c(f"  ✅ {msg}", "g"))
def warn(msg: str):  print(_c(f"  ⚠ {msg}", "y"))
def fail(msg: str):  print(_c(f"  ❌ {msg}", "r"))
def step_header(i: int, total: int, name: str):
    print(_c(f"\n[{i}/{total}] {name}", "b"))


class SmartRegisterRunner:
    """有感知的智能注册执行器。"""

    def __init__(self, case_path: Path, *, verbose: bool = False, dry_run: bool = False, do_login: bool = False, do_resume: bool = False, cleanup_on_fail: bool = False):
        self.case_path = case_path
        self.verbose = verbose
        self.dry_run = dry_run
        self.do_login = do_login
        self.do_resume = do_resume
        self.cleanup_on_fail = cleanup_on_fail
        self.case: Dict[str, Any] = {}
        self.client = None
        self.log: List[Dict[str, Any]] = []
        self.phase1_busi_id: Optional[str] = None
        self.phase1_name_id: Optional[str] = None
        self.establish_busi_id: Optional[str] = None
        self.user_id: str = ""
        self.final_status: str = "not_started"
        self.started_at = datetime.now()
        self.resume_candidate: Optional[Dict[str, Any]] = None
        self.resume_source: Optional[str] = None
        self.phase2_start_from: int = 0
        self.last_phase2_state: Dict[str, Any] = {}
        self.last_diagnosis: Dict[str, Any] = {}
        self.phase2_recovery_guard: Dict[str, Any] = {}
        self.latest_node_assets: Dict[str, Any] = {}

    def _extract_phase2_recovery_guard(self, cp_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(cp_data, dict):
            return {}
        failure = cp_data.get("failure") or {}
        if not isinstance(failure, dict):
            failure = {}
        diagnosis = failure.get("diagnosis") or {}
        if not isinstance(diagnosis, dict):
            diagnosis = {}
        failed_code = str(failure.get("failed_step_code") or diagnosis.get("code") or "").strip()
        recovery_action = str(diagnosis.get("recovery_action") or "").strip()
        if not failed_code and not recovery_action:
            return {}
        state = cp_data.get("context_state") or {}
        if not isinstance(state, dict):
            state = {}
        return {
            "failed_code": failed_code,
            "failed_step_name": str(failure.get("failed_step_name") or diagnosis.get("step_name") or "").strip(),
            "failed_step_index": failure.get("failed_step_index"),
            "recovery_action": recovery_action,
            "page_name": str(diagnosis.get("page_name") or "").strip(),
            "meaning": str(diagnosis.get("meaning") or "").strip(),
            "suggested_action": str(diagnosis.get("suggested_action") or "").strip(),
            "saved_name_id": str(state.get("name_id") or state.get("phase2_driver_name_id") or "").strip(),
            "saved_busi_id": str(state.get("phase1_busi_id") or state.get("phase2_driver_busi_id") or "").strip(),
            "current_comp_url": str(state.get("current_comp_url") or diagnosis.get("current_comp_url") or "").strip(),
            "current_status": str(state.get("current_status") or diagnosis.get("current_status") or "").strip(),
            "saved_progress_contract_version": int(
                state.get("phase2_progress_contract_version")
                or diagnosis.get("progress_contract_version")
                or 0
            ),
        }

    def _phase2_guard_requires_name_refresh(self, guard: Optional[Dict[str, Any]] = None) -> bool:
        active_guard = guard if isinstance(guard, dict) else self.phase2_recovery_guard
        return (
            str(active_guard.get("recovery_action") or "") == "refresh_name_id_then_resume"
            or str(active_guard.get("failed_code") or "") == "GS52010400B0017"
        )

    def _phase2_recovery_resolved(self, guard: Optional[Dict[str, Any]] = None) -> bool:
        active_guard = guard if isinstance(guard, dict) else self.phase2_recovery_guard
        if not active_guard:
            return True
        recovery_action = str(active_guard.get("recovery_action") or "")
        if recovery_action == "refresh_name_id_then_resume":
            current_name_id = str(self.phase1_name_id or "").strip()
            saved_name_id = str(active_guard.get("saved_name_id") or "").strip()
            return bool(current_name_id) and current_name_id != saved_name_id
        if recovery_action == "refresh_session_then_resume":
            return bool(self.do_login)
        if recovery_action == "inspect_progress_contract_then_resume":
            saved_version = int(active_guard.get("saved_progress_contract_version") or 0)
            if saved_version < PHASE2_PROGRESS_CONTRACT_VERSION:
                return True
            return bool(active_guard.get("progress_contract_reviewed"))
        return True

    def _should_ignore_phase2_checkpoint(self, guard: Optional[Dict[str, Any]] = None) -> bool:
        active_guard = guard if isinstance(guard, dict) else self.phase2_recovery_guard
        if self._phase2_guard_requires_name_refresh(active_guard) and self._phase2_recovery_resolved(active_guard):
            return True
        # ★ Phase 1 刚跑完拿到新 nameId，但 checkpoint 保存的是旧 nameId → 旧 Phase 2 上下文失效
        if self.phase1_name_id:
            cp = Checkpoint(CHECKPOINT_DIR)
            cp_data = cp.load("phase2_establish", case_path=self.case_path, case=self.case)
            if cp_data:
                saved_name_id = (cp_data.get("context_state") or {}).get("name_id") or (cp_data.get("context_state") or {}).get("phase2_driver_name_id")
                if saved_name_id and str(saved_name_id) != str(self.phase1_name_id):
                    return True
        return False

    def _force_phase1_refresh_for_guard(self, guard: Optional[Dict[str, Any]] = None) -> None:
        active_guard = guard if isinstance(guard, dict) else self.phase2_recovery_guard
        if not self._phase2_guard_requires_name_refresh(active_guard):
            return
        warn("上次失败已确认旧 nameId 失效：忽略断点/活跃办件的直接续跑资格，先重新跑 Phase 1。")
        self.log.append({
            "phase": "bootstrap",
            "event": "force_phase1_refresh",
            "reason": active_guard.get("failed_code") or active_guard.get("recovery_action"),
            "saved_name_id": active_guard.get("saved_name_id"),
        })
        self.resume_candidate = None
        self.resume_source = "phase1_name_refresh_required"
        self.phase2_start_from = 0
        self.establish_busi_id = None
        self.phase1_busi_id = None
        self.phase1_name_id = None

    def _block_unresolved_phase2_recovery(self, guard: Optional[Dict[str, Any]] = None) -> bool:
        active_guard = guard if isinstance(guard, dict) else self.phase2_recovery_guard
        if not active_guard or self._phase2_recovery_resolved(active_guard):
            return False
        recovery_action = str(active_guard.get("recovery_action") or "")
        category = "recovery_action_required"
        meaning = str(active_guard.get("meaning") or "上次失败后的恢复动作尚未完成。")
        suggested_action = str(active_guard.get("suggested_action") or "先完成恢复动作后再继续。")
        if recovery_action == "refresh_name_id_then_resume":
            category = "name_id_expired"
            meaning = "上次失败已经确认旧 nameId 已失效，本次仍未获得新的 nameId，已阻止重复请求。"
            suggested_action = "先重跑 Phase 1 获取新的 nameId，再进入 Phase 2。"
        elif recovery_action == "refresh_session_then_resume":
            category = "session_expired"
            meaning = "上次失败是会话失效，本次未执行重新登录，已阻止重复请求。"
            suggested_action = "请使用 --login 重新扫码登录后再续跑。"
        elif recovery_action == "inspect_progress_contract_then_resume":
            category = "step_not_advanced"
            meaning = "上次失败是接口返回成功但服务端未推进；协议推进合同尚未修正，已阻止重复请求同一步。"
            suggested_action = "先完成该组件的协议合同检查或修正（如按钮语义、continueFlag、真实前端请求体/额外动作），再续跑。"
        step_index = active_guard.get("failed_step_index")
        protocol_step = int(step_index) + 1 if isinstance(step_index, int) else None
        self.final_status = "phase2_recovery_guard"
        self.last_phase2_state = {
            "current_comp_url": active_guard.get("current_comp_url"),
            "current_status": active_guard.get("current_status"),
        }
        self.last_diagnosis = {
            "schema": "smart_diagnosis.v1",
            "pipeline": "phase2_establish",
            "step_name": active_guard.get("failed_step_name") or "?",
            "page_name": active_guard.get("page_name") or "?",
            "protocol_step": protocol_step,
            "code": "RESUME_RECOVERY_GUARD",
            "category": category,
            "severity": "blocker",
            "meaning": meaning,
            "suggested_action": suggested_action,
            "recovery_action": recovery_action or "complete_recovery_then_resume",
            "current_comp_url": active_guard.get("current_comp_url"),
            "current_status": active_guard.get("current_status"),
        }
        self.log.append({
            "phase": "phase2",
            "event": "recovery_guard_block",
            "failed_code": active_guard.get("failed_code"),
            "recovery_action": recovery_action,
            "saved_name_id": active_guard.get("saved_name_id"),
        })
        fail(suggested_action)
        return True

    # ════════════════════════════════════════════════
    # 0. 加载 case
    # ════════════════════════════════════════════════
    def load_case(self) -> bool:
        if not self.case_path.exists():
            fail(f"案例文件不存在: {self.case_path}")
            return False
        try:
            self.case = json.loads(self.case_path.read_text(encoding="utf-8"))
            name = self.case.get("phase1_check_name") or self.case.get("company_name_full") or "未知"
            ok(f"案例加载成功: {name}")
            info(f"  entType: {self.case.get('entType_default', '4540')}")
            info(f"  投资人: {(self.case.get('person') or {}).get('name', '?')}")
            return True
        except Exception as e:
            fail(f"案例文件解析失败: {e}")
            return False

    def qr_login(self) -> bool:
        print(_c("\n═══ 扫码登录（纯 HTTP） ═══", "m"))

        try:
            from login_qrcode_pure_http import refresh_token, full_login
        except ImportError as e:
            fail(f"无法导入 login_qrcode_pure_http: {e}")
            return False

        print()
        print(_c("  ★★★ 如需扫码，请用智桂通APP扫描弹出的二维码 ★★★", "y"))
        print()

        # 优先静默续期（重建 9087 SESSION + Authorization），失败才走扫码
        info("尝试静默续期（重建全部 session cookies）...")
        token = refresh_token(verbose=True)
        if not token:
            warn("静默续期失败，需要扫码登录")
            token = full_login(verbose=True)
        if token:
            ok(f"Authorization: {token[:8]}... (len={len(token)})")
            return True
        fail("登录失败（token 未获取）")
        return False

    def _silent_session_refresh(self) -> bool:
        """静默刷新 session cookies（每次 execute 入口都调用，无需 --login）。
        若 SESSIONFORTYRZ 仍有效则 ~2s 完成；失败则继续（用已有 token 碰运气）。
        """
        try:
            from login_qrcode_pure_http import refresh_token
            token = refresh_token(verbose=False)
            if token:
                info("session 静默刷新成功")
                return True
            warn("session 静默刷新失败（SESSIONFORTYRZ 可能过期），将使用现有 token")
        except Exception as e:
            warn(f"session 静默刷新异常: {e}")
        return False

    def check_auth(self) -> bool:
        print(_c("\n═══ 步骤 0: 认证检查 ═══", "m"))
        from icpsp_api_client import ICPSPClient

        try:
            self.client = ICPSPClient()
        except Exception as e:
            fail(f"ICPSPClient 初始化失败: {e}")
            fail("请确认浏览器已登录且 session cookies 可用")
            return False

        try:
            resp = self.client.get_json(
                "/icpsp-api/v4/pc/manager/usermanager/getUserInfo",
                params={}
            )
            code = resp.get("code")
            if code == "00000":
                data = resp.get("data") or {}
                bd = data.get("busiData") or {}
                username = bd.get("realName") or bd.get("name") or ""
                uid = str(bd.get("id") or "")
                if uid:
                    self.user_id = uid
                if username:
                    ok(f"认证有效 — 当前用户: {username} (id={uid})")
                    return True
                # 用户名为空说明 session cookies 失效（Authorization 还活但 9087 SESSION 过期）
                warn("getUserInfo 返回 00000 但用户名为空，尝试刷新 session...")
                self._silent_session_refresh()
                self.client = ICPSPClient()  # 重建 client 加载新的 pkl cookies
                resp2 = self.client.get_json("/icpsp-api/v4/pc/manager/usermanager/getUserInfo", params={})
                bd2 = ((resp2.get("data") or {}).get("busiData") or {})
                username2 = bd2.get("realName") or bd2.get("name") or "未知"
                if resp2.get("code") == "00000":
                    ok(f"认证有效 — 当前用户: {username2}")
                    return True
            fail(f"认证失败 code={code}: {resp.get('msg', '')}")
            fail("请重新扫码登录后再试")
            return False
        except Exception as e:
            fail(f"认证检查请求失败: {e}")
            fail("可能原因: 浏览器未登录 / session cookies 过期 / 网络不通")
            return False

    # ════════════════════════════════════════════════
    # 2. 重复登记检查
    # ════════════════════════════════════════════════
    def check_duplicate(self) -> bool:
        """查办件列表，看有没有同名企业已在办。"""
        print(_c("\n═══ 步骤 0.1: 重复登记检查 ═══", "m"))
        name_mark = self.case.get("name_mark") or ""
        check_name = self.case.get("phase1_check_name") or self.case.get("company_name_full") or ""

        if not name_mark:
            warn("case 缺少 name_mark，跳过重复检查")
            return True

        try:
            resp = self.client.get_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                params={
                    "searchText": name_mark,
                    "pageNum": 1,
                    "pageSize": 50,
                    "matterTypeCode": "",
                    "matterStateCode": "",
                    "timeRange": "",
                    "useType": "0",
                }
            )
            code = resp.get("code")
            if code != "00000":
                warn(f"办件查询返回 code={code}，无法确认是否重复，继续执行")
                return True

            items = (resp.get("data") or {}).get("busiData") or []
            duplicates = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                ent_name = it.get("entName") or ""
                # 匹配: 名称包含 name_mark 的
                if name_mark in ent_name:
                    state_code = it.get("matterStateCode") or it.get("listMatterStateCode") or "?"
                    busi_id = it.get("id") or "?"
                    duplicates.append({
                        "name": ent_name,
                        "busi_id": busi_id,
                        "state": state_code,
                        "busiType": it.get("busiType"),
                        "nameId": it.get("nameId"),
                        "entType": it.get("entType"),
                    })

            if not duplicates:
                ok(f"办件列表中未找到含 \"{name_mark}\" 的企业 — 可以安全创建")
                return True
            else:
                fail(f"⚠⚠⚠ 发现 {len(duplicates)} 条含 \"{name_mark}\" 的办件:")
                for d in duplicates:
                    state_desc = {
                        "10": "填写中", "20": "预审中", "30": "已办结",
                        "51": "名称已提交", "90": "已提交(云)"
                    }.get(str(d["state"]), d["state"])
                    print(f"    - {d['name']}  busiId={d['busi_id']}  状态={state_desc}")

                # 如果全部都是已办结(30)或已提交(90)，可能可以新建
                active = [d for d in duplicates if str(d["state"]) not in ("30", "90")]
                if active:
                    candidate = self._pick_resume_candidate(active)
                    if candidate:
                        self.resume_candidate = candidate
                        self.resume_source = "active_matter"
                        self.phase1_busi_id = candidate.get("busi_id")
                        self.phase1_name_id = candidate.get("name_id")
                        self.establish_busi_id = candidate.get("busi_id")
                        self.phase2_start_from = max(self.phase2_start_from, int(candidate.get("start_from_index") or 0))
                        ok(
                            f"发现可恢复办件: busiId={candidate.get('busi_id')} currCompUrl={candidate.get('currCompUrl') or '?'}"
                        )
                        info(f"后续将优先从 step={self.phase2_start_from + 1} 续跑")
                        # ★ 自动清理多余活跃办件（保留 candidate，删除其余）
                        to_clean = [d for d in active if d["busi_id"] != candidate.get("busi_id")]
                        if to_clean:
                            self._cleanup_matters(to_clean)
                        self.log.append({
                            "phase": "bootstrap",
                            "event": "resume_candidate",
                            "source": "active_matter",
                            "busi_id": candidate.get("busi_id"),
                            "name_id": candidate.get("name_id"),
                            "currCompUrl": candidate.get("currCompUrl"),
                            "start_from_index": candidate.get("start_from_index"),
                        })
                        return True
                    # ★ 没有可恢复 candidate，自动清理所有活跃办件
                    warn("存在活跃办件，但未能识别为合法 Phase 2 断点；自动清理后继续。")
                    self._cleanup_matters(active)
                    return True
                else:
                    warn("已有的全部是已办结状态，允许新建（但请确认需要）")
                    return True

        except Exception as e:
            warn(f"办件列表查询失败: {e}，继续执行（请人工确认无重复）")
            return True

    def _cleanup_matters(self, matters: list) -> None:
        """删除指定办件（先撤回 btnCode=104，再删除 btnCode=103）。

        ★ btnCode=104 撤回申请：仅对 state=101（进行中）办件有效，撤回后名称释放回可用。
        ★ btnCode=103 删除办件：两步确认（before + operate），删除残留办件。
        """
        import time as _t
        API = "/icpsp-api/v4/pc/manager/mattermanager/matters/operate"
        HDRS = {"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"}
        info(f"自动清理 {len(matters)} 条多余办件...")
        for d in matters:
            bid = str(d.get("busi_id") or "")
            nm = d.get("name", "")
            state = str(d.get("state") or d.get("matterStateCode") or "")
            if not bid:
                continue
            try:
                # Step 1: 先尝试撤回（btnCode=104），释放名称占用
                r_wd = self.client.post_json(API, {"busiId": bid, "btnCode": "104", "dealFlag": "before"},
                                             extra_headers=HDRS)
                wd_code = r_wd.get("code", "")
                wd_rt = str((r_wd.get("data") or {}).get("resultType", ""))
                if wd_code == "00000" and wd_rt == "2":
                    # 撤回确认提示，执行第二步
                    _t.sleep(0.3)
                    r_wd2 = self.client.post_json(API, {"busiId": bid, "btnCode": "104", "dealFlag": "operate"},
                                                  extra_headers=HDRS)
                    wd2_code = r_wd2.get("code", "")
                    if wd2_code == "00000":
                        ok(f"已撤回 {bid} ({nm}) — 名称已释放")
                    else:
                        warn(f"撤回 {bid} ({nm}) 失败: code={wd2_code}")
                _t.sleep(0.3)

                # Step 2: 删除办件（btnCode=103）
                r1 = self.client.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "before"}, extra_headers=HDRS)
                _t.sleep(0.3)
                r2 = self.client.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "operate"}, extra_headers=HDRS)
                code2 = r2.get("code", "")
                msg2 = (r2.get("data") or {}).get("msg", r2.get("msg", ""))[:60]
                if code2 == "00000":
                    ok(f"已删除 {bid} ({nm})")
                else:
                    warn(f"删除 {bid} ({nm}) 失败: code={code2} msg={msg2}")
                _t.sleep(0.3)
            except Exception as e:
                warn(f"清理 {bid} ({nm}) 异常: {e}")

    def _estimate_phase2_start_from(self, comp_url: str, ent_type: str) -> int:
        from phase2_protocol_driver import get_steps_spec

        target = str(comp_url or "").strip()
        if not target:
            return 0

        for step_num, name, _fn, _optional in get_steps_spec(ent_type):
            if (
                f"/{target}/" in name
                or f"/{target} " in name
                or f"/{target}[" in name
                or name.endswith(f"/{target}")
            ):
                return max(step_num - 1, 0)
        return 0

    def _is_establish_resume_candidate(self, item: Dict[str, Any]) -> bool:
        busi_type = str(item.get("busiType") or item.get("busi_type") or "").strip()
        name_id = str(item.get("name_id") or item.get("nameId") or "").strip()
        # ★ busiType=01/02 + nameId = 名称阶段完成，可通过 matters/operate 108 进入设立
        if name_id and busi_type.startswith(("02", "01")):
            return True
        # ★ matters/search 不返回 nameId，但 status=51（名称已提交）说明名称阶段完成
        state = str(item.get("state") or item.get("matterStateCode") or item.get("status") or "").strip()
        if state in ("51", "104") and not busi_type.startswith("30"):
            return True
        return False

    def _probe_matter_progress(self, *, busi_id: str, name_id: Optional[str],
                                ent_type: str, busi_type: str) -> Dict[str, Any]:
        body = {
            "flowData": {
                "busiId": busi_id,
                "entType": ent_type,
                "busiType": busi_type,
                "ywlbSign": "4",
                "busiMode": None,
                "nameId": name_id,
                "marPrId": None,
                "secondId": None,
                "vipChannel": None,
            },
            "linkData": {"continueFlag": "continueFlag", "token": ""},
        }
        resp = self.client.post_json(
            "/icpsp-api/v4/pc/register/establish/loadCurrentLocationInfo",
            body,
            extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
        )
        code = resp.get("code")
        if code != "00000":
            return {
                "success": False,
                "code": code,
                "message": resp.get("msg", ""),
            }

        bd = (resp.get("data") or {}).get("busiData") or {}
        fd = bd.get("flowData") or {}
        return {
            "success": True,
            "currCompUrl": fd.get("currCompUrl"),
            "status": fd.get("status"),
            "flowData": fd,
        }

    def _pick_resume_candidate(self, active: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        check_name = self.case.get("phase1_check_name") or self.case.get("company_name_full") or ""
        establish_active = [d for d in active if self._is_establish_resume_candidate(d)]
        ranked = [d for d in establish_active if d.get("name") == check_name] or establish_active
        chosen = ranked[0] if ranked else None
        if not chosen:
            if active:
                warn("存在活跃办件，但都不是合法的 Phase 2 续跑候选（缺 nameId 或非 establish 办件），本次不把它们当成 Phase 2 断点。")
            return None

        ent_type = str(chosen.get("entType") or self.case.get("entType_default") or "4540")
        busi_type = str(chosen.get("busiType") or self.case.get("busiType_default") or "02_4")
        progress = self._probe_matter_progress(
            busi_id=str(chosen.get("busi_id") or ""),
            name_id=chosen.get("name_id") or chosen.get("nameId"),
            ent_type=ent_type,
            busi_type=busi_type,
        )
        if not progress.get("success"):
            return None

        curr_comp = str(progress.get("currCompUrl") or "")
        # ★ probe 的 flowData 可能包含 nameId（matters/search 不返回）
        probed_name_id = (progress.get("flowData") or {}).get("nameId") or chosen.get("name_id") or chosen.get("nameId")
        return {
            "busi_id": str(chosen.get("busi_id") or ""),
            "name_id": probed_name_id,
            "ent_type": ent_type,
            "busi_type": busi_type,
            "currCompUrl": curr_comp,
            "establish_status": progress.get("status"),
            "start_from_index": self._estimate_phase2_start_from(curr_comp, ent_type),
        }

    # ════════════════════════════════════════════════
    # 3. Phase 1 核名（Pipeline + NameCorrectionHook）
    # ════════════════════════════════════════════════
    def run_phase1(self) -> bool:
        """运行 Phase 1 核名。

        使用 Pipeline 框架执行，NameCorrectionHook 处理交互纠错。
        改名后自动重建 adapter 和 Pipeline，原地重试。
        """
        max_retries = 5

        for attempt in range(1, max_retries + 1):
            print(_c("\n═══════════════════════════════════════", "m"))
            if attempt == 1:
                print(_c("       Phase 1: 名称登记（Pipeline 8 步）", "m"))
            else:
                print(_c(f"       Phase 1: 名称登记 — 第 {attempt} 次尝试", "m"))
            print(_c("═══════════════════════════════════════", "m"))

            # 每次尝试都重建 adapter（改名后 case 变了）
            adapter = Phase1Adapter(self.case)

            info(f"名称: {adapter.driver_ctx.full_name}")
            info(f"字号: {adapter.driver_ctx.name_mark}")

            steps = adapter.make_steps()

            # Hook 组合：日志 + 限流 + 状态提取 + 核名纠错 + 结果写入
            hooks = full_hooks(verbose=self.verbose, output_dir=RECORDS_DIR)

            ctx = PipelineContext(
                case=self.case,
                case_path=self.case_path,
                client=self.client,
                verbose=self.verbose,
            )

            pipe = Pipeline("phase1_name_check", steps=steps, hooks=hooks)
            t0 = time.time()
            result = pipe.run(ctx)
            dt = time.time() - t0

            self.log.append({
                "phase": "phase1", "attempt": attempt,
                "success": result.success,
                "exit_reason": result.exit_reason,
                "exit_detail": result.exit_detail,
                "duration_s": round(dt, 1),
            })

            # ── 成功 ──
            if result.success:
                # 优先从 PipelineContext 取，其次从 adapter 取
                self.phase1_busi_id = ctx.phase1_busi_id or adapter.driver_ctx.busi_id
                self.phase1_name_id = ctx.name_id
                if self.phase1_busi_id:
                    ok(f"Phase 1 核名成功! busiId={self.phase1_busi_id}  ({dt:.1f}s)")
                    if self.phase1_name_id:
                        info(f"nameId: {self.phase1_name_id}")
                    return True
                else:
                    # ★ 检测 15 分钟核名限流 → 自动等待重试
                    # ★ 限流是按（行政区划+行业+组织形式）combo 计数，不是按字号
                    #   重试也会发新请求，最多只重试 2 次避免无限循环
                    is_rate_limited = getattr(adapter.driver_ctx, "_rate_limited_15min", False)
                    rate_retry_count = getattr(self, "_rate_retry_count", 0)
                    if is_rate_limited and attempt < max_retries and rate_retry_count < 2:
                        self._rate_retry_count = rate_retry_count + 1
                        wait_min = 16  # 等 16 分钟（留 1 分钟余量）
                        warn(f"核名限流（15 分钟内同区划+行业+组织形式超限）— 自动等待 {wait_min} 分钟后重试 ({self._rate_retry_count}/2)")
                        for remaining in range(wait_min, 0, -1):
                            print(f"    ⏳ 等待中... {remaining} 分钟", flush=True)
                            time.sleep(60)
                        # 等待期间 token 可能过期，刷新一下
                        info("冷却完成，刷新 token 后重新核名...")
                        self.qr_login()
                        continue
                    elif is_rate_limited and rate_retry_count >= 2:
                        fail("核名限流重试已达上限（2次）— 请等待 15 分钟后手动重新执行")
                        self.final_status = "phase1_rate_limited"
                        return False
                    fail(f"Pipeline 成功但无 busiId — 可能需要干预  ({dt:.1f}s)")
                    self.final_status = "phase1_no_busi_id"
                    return False

            # ── 用户改名 → 重启 Pipeline ──
            if result.exit_reason == "__restart__":
                # NameCorrectionHook 已更新 ctx.case 和磁盘文件
                self.case = ctx.case
                info("用新名称重新核名...")
                time.sleep(1.5)
                continue

            # ── 用户主动退出 ──
            if result.exit_reason == "user_abort":
                info("用户选择退出")
                self.final_status = "user_abort"
                return False

            # ── 其他失败 ──
            fail(f"Phase 1 失败: {result.exit_reason}  ({dt:.1f}s)")
            if result.exit_detail:
                fail(f"  详情: {result.exit_detail[:200]}")
            self.final_status = result.exit_reason or "phase1_failed"
            return False

        fail("核名重试次数已达上限")
        self.final_status = "phase1_max_retries"
        return False

    def run_name_completion(self) -> bool:
        if self.phase1_name_id:
            return True
        if not self.phase1_busi_id:
            fail("没有 Phase 1 busiId，无法补全名称阶段")
            self.final_status = "phase1_no_busi_id"
            return False

        ent_type = str(self.case.get("entType_default") or "4540")
        print(_c("\n═══════════════════════════════════════", "m"))
        print(_c("       Phase 1: 名称补充与提交（复用 Phase2 step1-9）", "m"))
        print(_c("═══════════════════════════════════════", "m"))

        adapter = Phase2Adapter(self.case, self.phase1_busi_id, self.phase1_name_id,
                                user_id=self.user_id)
        steps = adapter.make_steps(ent_type)
        hooks = default_hooks(verbose=self.verbose, output_dir=RECORDS_DIR)
        ctx = PipelineContext(
            case=self.case,
            case_path=self.case_path,
            client=self.client,
            verbose=self.verbose,
        )
        ctx.phase1_busi_id = self.phase1_busi_id

        t0 = time.time()
        result = Pipeline("phase1_name_completion", steps=steps, hooks=hooks).run(ctx, start_from=0, stop_after=9)
        dt = time.time() - t0

        self.phase1_name_id = (
            ctx.name_id
            or ctx.state.get("phase2_driver_name_id")
            or adapter.p2_ctx.name_id
            or self.phase1_name_id
        )
        self.last_phase2_state = dict(ctx.state)
        self.last_diagnosis = dict(ctx.state.get("last_diagnosis") or {})
        self.log.append({
            "phase": "phase1_name_completion",
            "success": result.success,
            "exit_reason": result.exit_reason,
            "exit_detail": result.exit_detail,
            "duration_s": round(dt, 1),
            "name_id": self.phase1_name_id,
        })

        if result.success and self.phase1_name_id:
            ok(f"名称阶段完成! nameId={self.phase1_name_id}  ({dt:.1f}s)")
            self.phase2_start_from = max(self.phase2_start_from, 9)
            return True

        fail(f"名称补充/提交未完成，无法进入设立阶段  ({dt:.1f}s)")
        if result.exit_detail:
            fail(f"  详情: {result.exit_detail[:200]}")
        self.final_status = result.exit_reason or "phase1_name_completion_failed"
        return False

    # ════════════════════════════════════════════════
    # 4. Phase 2 设立登记（Pipeline + Checkpoint）
    # ════════════════════════════════════════════════
    def run_phase2(self) -> bool:
        """运行 Phase 2 设立登记，默认到 PreSubmitSuccess 停止。

        使用 Pipeline 框架执行，支持断点续跑。
        若 case.run_goal 含 "submit"，则继续执行 step26/29 最终提交。
        """
        if not self.phase1_busi_id:
            fail("没有 Phase 1 busiId，无法启动 Phase 2")
            return False
        if self._block_unresolved_phase2_recovery():
            return False

        ent_type = str(self.case.get("entType_default") or "4540")
        ent_label = "1151 有限公司" if ent_type == "1151" else "4540 个人独资"

        print(_c("\n═══════════════════════════════════════", "m"))
        print(_c(f"   Phase 2: 设立登记（{ent_label} → 云提交停点）", "m"))
        print(_c("═══════════════════════════════════════", "m"))

        # 创建 adapter
        adapter = Phase2Adapter(self.case, self.phase1_busi_id, self.phase1_name_id,
                                establish_busi_id=self.establish_busi_id,
                                user_id=self.user_id)
        steps = adapter.make_steps(ent_type)

        info(f"busiId  : {self.phase1_busi_id}")
        info(f"entType : {ent_type} ({ent_label})")
        info(f"总步数  : {len(steps)}")
        print()

        # Hook 组合：日志 + 限流 + 状态提取 + 结果写入 + 断点
        hooks = default_hooks(verbose=self.verbose, output_dir=RECORDS_DIR)
        cp = Checkpoint(CHECKPOINT_DIR)
        hooks.append(CheckpointHook(cp, pipeline_name="phase2_establish"))

        # 创建 PipelineContext
        ctx = PipelineContext(
            case=self.case,
            case_path=self.case_path,
            client=self.client,
            verbose=self.verbose,
        )
        ctx.phase1_busi_id = self.phase1_busi_id
        if self.phase1_name_id:
            ctx.name_id = self.phase1_name_id
        if self.establish_busi_id:
            ctx.establish_busi_id = self.establish_busi_id
        ctx.state["phase2_progress_contract_version"] = PHASE2_PROGRESS_CONTRACT_VERSION

        # dry-run
        if self.dry_run:
            ok("[dry-run] Phase 2 steps:")
            for i, step in enumerate(steps):
                ok(f"  {i+1}. {step.name}")
            return True

        # 断点恢复
        start_from = self.phase2_start_from
        # ★ 有 nameId = 名称阶段已完成，至少从 step10（matters/operate）开始
        if self.phase1_name_id and start_from < 9:
            start_from = 9
        cp_data = cp.load("phase2_establish", case_path=self.case_path, case=self.case)
        ignore_phase2_checkpoint = self._should_ignore_phase2_checkpoint()
        if ignore_phase2_checkpoint:
            warn("检测到 nameId 已刷新：旧 Phase 2 断点上下文已失效，本次从新的 Phase 2 上下文启动。")
            start_from = self.phase2_start_from
        elif cp_data:
            cp_start = cp.get_resume_index("phase2_establish", case_path=self.case_path, case=self.case)
            if cp.restore_context("phase2_establish", ctx):
                adapter.restore_from_pipeline_ctx(ctx)
            if cp_start > start_from:
                start_from = cp_start
            if cp_data.get("failure"):
                failure = cp_data.get("failure") or {}
                warn(
                    f"上次失败: {failure.get('failed_step_name') or cp_data.get('pipeline')} code={failure.get('failed_step_code') or '?'}"
                )
                diag = failure.get("diagnosis") or {}
                if isinstance(diag, dict) and diag:
                    warn(f"上次诊断: {diag.get('page_name') or '?'} / {diag.get('meaning') or '?'}")
                    warn(f"建议动作: {diag.get('suggested_action') or '?'}")
                if failure.get("failed_step_code") == "STEP_POSITION_GUARD":
                    probe = adapter.probe_current_location(self.client, ctx)
                    if probe.get("server_curr_comp_url"):
                        info(
                            f"已按诊断建议读取真实位置: {probe.get('server_curr_comp_url')} "
                            f"status={probe.get('server_status') or '?'}"
                        )
        elif self.do_resume:
            info("未找到此 case 的断点，按当前办件进度执行")

        if self.resume_candidate:
            if self.resume_candidate.get("currCompUrl"):
                ctx.state["current_comp_url"] = self.resume_candidate.get("currCompUrl")
            if self.resume_candidate.get("establish_status"):
                ctx.state["current_status"] = self.resume_candidate.get("establish_status")
            ctx.state["resume_source"] = self.resume_source or "active_matter"

        if start_from > 0 or self.resume_candidate or cp_data:
            probe = adapter.probe_current_location(self.client, ctx)
            if probe.get("server_curr_comp_url") or probe.get("server_status"):
                info(
                    f"续跑前已读取真实位置: {probe.get('server_curr_comp_url') or '?'} "
                    f"status={probe.get('server_status') or '?'}"
                )

        observed_component = str(
            ctx.state.get("server_curr_comp_url")
            or ctx.state.get("current_comp_url")
            or ""
        ).strip()
        # ★ busiType=01 + currCompUrl=None = 名称阶段完成但未进入设立
        # probe 用 02 查 01 办件可能返回旧 establish 残留（BasicInfo），不可信
        probed_busi_type = str(
            ctx.state.get("server_busi_type") or ""
        ).strip()
        probed_busi_id = str(
            ctx.state.get("server_busi_id") or ""
        ).strip()
        if probed_busi_type.startswith("01") and not observed_component:
            warn(f"办件仍在名称阶段(busiType={probed_busi_type})，强制从 step10 进入设立")
            start_from = max(start_from, 9)
            observed_component = ""
        elif probed_busi_type.startswith("02") and probed_busi_id and not observed_component:
            # ★ busiType=02 + busiId 非空 + currCompUrl=None = 已在 establish 但还没到具体组件
            # 不需要再走 step10-11，从 step13（YbbSelect load）开始
            warn(f"办件已在设立阶段(busiType=02, busiId={probed_busi_id})，从 step13 开始")
            start_from = max(start_from, 12)
            observed_component = ""
        # ★ nameId 刷新时，probe 的位置是旧 establish 残留，不可信；
        # 必须从 step10（matters/operate）重新进入 establish
        if ignore_phase2_checkpoint and observed_component:
            warn(f"nameId 已刷新，忽略 probe 位置 {observed_component}，强制从 step10 进入 establish")
            observed_component = ""
        if observed_component:
            aligned_start = adapter.recommend_start_from(
                observed_component,
                fallback_index=start_from,
                ent_type=ent_type,
            )
            if aligned_start != start_from:
                warn(
                    f"根据当前位置 {observed_component} 重算恢复步位: step={start_from + 1} -> step={aligned_start + 1}"
                )
                ctx.state["resume_realigned_component"] = observed_component
                ctx.state["resume_realigned_from_step"] = start_from + 1
                ctx.state["resume_realigned_to_step"] = aligned_start + 1
                start_from = aligned_start

        if start_from > 0:
            ok(f"从 step={start_from + 1} 继续执行")

        pipe = Pipeline("phase2_establish", steps=steps, hooks=hooks)
        result = pipe.run(ctx, start_from=start_from)

        # 提取关键状态
        self.establish_busi_id = ctx.establish_busi_id or self.establish_busi_id
        self.last_phase2_state = dict(ctx.state)
        self.last_diagnosis = dict(ctx.state.get("last_diagnosis") or {})
        self.log.append({
            "phase": "phase2",
            "success": result.success,
            "exit_reason": result.exit_reason,
            "exit_detail": result.exit_detail,
            "stopped_at_step": result.stopped_at_step,
            "start_from_index": start_from,
            "current_comp_url": ctx.state.get("current_comp_url"),
            "current_status": ctx.state.get("current_status"),
            "diagnosis": ctx.state.get("last_diagnosis"),
            "problem": ctx.state.get("last_problem"),
        })

        if result.success:
            self.final_status = "success"
            if ctx.state.get("reached_pre_submit"):
                ok("★ 已达 PreSubmitSuccess 云提交停点!")
            if ctx.state.get("reached_status_90"):
                ok("★ status=90!")
            return True
        else:
            self.final_status = result.exit_reason or "phase2_failed"
            if result.exit_detail:
                fail(f"  详情: {result.exit_detail[:200]}")
            self._print_diagnosis(self.last_diagnosis)
            return False

    # ════════════════════════════════════════════════
    # 主入口
    # ════════════════════════════════════════════════
    def execute(self) -> int:
        """完整执行流程。返回退出码 0=成功, 非0=失败。"""
        print(_c("╔═══════════════════════════════════════════════╗", "m"))
        print(_c("║  智能注册执行器 v2 — Pipeline 编排 · Hook 插件 · 断点续跑 ║", "m"))
        print(_c("╚═══════════════════════════════════════════════╝", "m"))

        # Step 0: 加载 case
        if not self.load_case():
            return 2

        # Step 0.0: 登录（如果需要）
        if self.do_login:
            if not self.qr_login():
                return 1
        else:
            # 不管有没有 --login，都尝试静默刷新 session cookies（~2s，SESSIONFORTYRZ 还活则成功）
            self._silent_session_refresh()

        # Step 0.1: 认证检查
        if not self.check_auth():
            return 3

        # Step 0.2: 重复登记检查
        if not self.check_duplicate():
            return 4

        if self.dry_run:
            ok("Dry run 完成 — 认证有效、无重复、case 正确。若要实际执行请去掉 --dry-run")
            return 0

        # Phase 1: 核名（--resume 时如果断点已有 busiId 则跳过）
        skip_phase1 = False
        cp = Checkpoint(CHECKPOINT_DIR)
        cp_data = cp.load("phase2_establish", case_path=self.case_path, case=self.case)
        self.phase2_recovery_guard = self._extract_phase2_recovery_guard(cp_data)
        if self._phase2_guard_requires_name_refresh(self.phase2_recovery_guard):
            self._force_phase1_refresh_for_guard(self.phase2_recovery_guard)
        if cp_data and cp_data.get("status") != "completed":
            saved_state = cp_data.get("context_state") or {}
            saved_busi_id = saved_state.get("phase1_busi_id")
            saved_name_id = saved_state.get("name_id") or saved_state.get("phase2_driver_name_id")
            cp_start = cp.get_resume_index("phase2_establish", case_path=self.case_path, case=self.case)
            if saved_busi_id:
                if self._phase2_guard_requires_name_refresh(self.phase2_recovery_guard):
                    warn("忽略 checkpoint 的 Phase 2 续跑资格：本次必须先刷新 nameId。")
                else:
                    self.phase1_busi_id = saved_busi_id
                    self.phase1_name_id = saved_name_id
                    self.phase2_start_from = max(self.phase2_start_from, cp_start)
                    skip_phase1 = True
                    self.resume_source = self.resume_source or "checkpoint"
                    ok(f"发现 case 状态，可从 step={self.phase2_start_from + 1} 续跑")

        if self.resume_candidate:
            if self._phase2_guard_requires_name_refresh(self.phase2_recovery_guard):
                warn("忽略活跃办件的直接续跑资格：上次失败要求先刷新 nameId。")
            else:
                skip_phase1 = True
                self.phase1_busi_id = self.resume_candidate.get("busi_id") or self.phase1_busi_id
                self.phase1_name_id = self.resume_candidate.get("name_id") or self.phase1_name_id
                self.establish_busi_id = self.resume_candidate.get("busi_id") or self.establish_busi_id
                self.phase2_start_from = max(self.phase2_start_from, int(self.resume_candidate.get("start_from_index") or 0))
                self.resume_source = self.resume_source or "active_matter"
                ok(f"跳过 Phase 1，直接续跑已有办件 busiId={self.phase1_busi_id}")

        if not skip_phase1:
            if not self.run_phase1():
                self._print_summary()
                return 5

        if not self.phase1_name_id:
            if not self.run_name_completion():
                self._print_summary()
                return 5

        # Phase 2: 设立登记 → PreSubmitSuccess
        if not self.run_phase2():
            cleanup_id = self.establish_busi_id or self.phase1_busi_id
            if self.cleanup_on_fail and cleanup_id and self.final_status not in ("user_abort", "session_expired"):
                self._cleanup_establish(cleanup_id)
            else:
                warn("失败现场已保留，可直接使用 --resume 或继续办理定位后续跑")
            self._print_summary()
            return 6

        self._print_summary()
        return 0

    def _cleanup_establish(self, busi_id: str):
        """★ 失败后自动清理 establish 办件，避免残留影响下次运行。"""
        if not busi_id:
            return
        try:
            warn(f"自动清理失败办件 busiId={busi_id} ...")
            r1 = self.client.post_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                {"busiId": busi_id, "btnCode": "103", "dealFlag": "before"},
            )
            time.sleep(1)
            r2 = self.client.post_json(
                "/icpsp-api/v4/pc/manager/mattermanager/matters/operate",
                {"busiId": busi_id, "btnCode": "103", "dealFlag": "operate"},
            )
            msg = (r2.get("data") or {}).get("msg", "")
            if r2.get("code") == "00000":
                ok(f"清理成功: {msg}")
            else:
                warn(f"清理结果: code={r2.get('code')} {msg}")
        except Exception as e:
            warn(f"清理异常: {e}")

    def _print_summary(self):
        """打印最终汇总。"""
        self._write_run_record()
        elapsed = (datetime.now() - self.started_at).total_seconds()
        print()
        print(_c("╔═══════════════════════════════════════════════╗", "m"))
        print(_c("║                 执行结果汇总                    ║", "m"))
        print(_c("╚═══════════════════════════════════════════════╝", "m"))

        name = self.case.get("phase1_check_name") or "?"
        if self.final_status == "success":
            ok(f"企业: {name}")
            ok(f"Phase 1 busiId : {self.phase1_busi_id}")
            ok(f"Establish busiId: {self.establish_busi_id}")
            ok(f"状态: ★ 已达 PreSubmitSuccess 云提交停点 ★")
            ok(f"总耗时: {elapsed:.1f}s")
            print()
            if self.case.get("run_goal") == "submit":
                ok("run_goal=submit: 已执行最终提交")
            else:
                warn("注意: 未执行真正的云提交。如需提交，请在浏览器中操作，或在 case 中设置 run_goal=\"submit\"")
        else:
            fail(f"企业: {name}")
            fail(f"状态: {self.final_status}")
            if self.phase1_busi_id:
                info(f"Phase 1 busiId: {self.phase1_busi_id}")
            if self.establish_busi_id:
                info(f"Establish busiId: {self.establish_busi_id}")
            if self.last_phase2_state.get("current_comp_url"):
                info(f"当前位置: {self.last_phase2_state.get('current_comp_url')} status={self.last_phase2_state.get('current_status')}")
            self._print_diagnosis(self.last_diagnosis)
            fail(f"总耗时: {elapsed:.1f}s")

        if self.resume_source:
            info(f"恢复来源: {self.resume_source}")

        info(f"详细结果: dashboard/data/records/smart_register_latest.json")
        if self.latest_node_assets.get("manifest_path"):
            info(f"节点资产: {self.latest_node_assets.get('manifest_path')}")

    def _write_run_record(self):
        if not self.case:
            return
        try:
            cp = Checkpoint(CHECKPOINT_DIR)
            cp_data = cp.load("phase2_establish", case_path=self.case_path, case=self.case)
            name = self.case.get("phase1_check_name") or self.case.get("company_name_full") or "?"
            payload = {
                "schema": "smart_register.v2",
                "case_path": str(self.case_path),
                "case_id": self.case.get("case_id"),
                "case_name": name,
                "final_status": self.final_status,
                "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "phase1_busi_id": self.phase1_busi_id,
                "phase1_name_id": self.phase1_name_id,
                "establish_busi_id": self.establish_busi_id,
                "phase2_start_from_index": self.phase2_start_from,
                "resume_source": self.resume_source,
                "resume_candidate": self.resume_candidate,
                "last_phase2_state": self.last_phase2_state,
                "latest_diagnosis": self.last_diagnosis,
                "checkpoint": cp_data,
                "log": self.log,
                "encountered_problems": [item for item in self.log if item.get("success") is False],
            }
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            RECORDS_DIR.mkdir(parents=True, exist_ok=True)
            latest = RECORDS_DIR / "smart_register_latest.json"
            safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in self.case_path.stem) or "case"
            case_out = RECORDS_DIR / f"smart_register__{safe_stem}.json"
            latest.write_text(text, encoding="utf-8")
            case_out.write_text(text, encoding="utf-8")
            self.latest_node_assets = export_latest_node_assets(records_dir=RECORDS_DIR, assets_dir=ASSETS_DIR)
        except Exception as e:
            warn(f"写 smart_register 结果失败: {e}")

    def _print_diagnosis(self, diagnosis: Dict[str, Any]):
        if not diagnosis:
            return
        print()
        print(_c("═══ 智能诊断摘要 ═══", "m"))
        info(f"阶段: {diagnosis.get('business_stage_name') or '?'}")
        info(f"页面: {diagnosis.get('page_name') or '?'}")
        info(f"协议 step: {diagnosis.get('protocol_step') or '?'}")
        info(f"错误类型: {diagnosis.get('category') or '?'} / {diagnosis.get('severity') or '?'}")
        info(f"含义: {diagnosis.get('meaning') or '?'}")
        info(f"建议: {diagnosis.get('suggested_action') or '?'}")
        info(f"恢复动作: {diagnosis.get('recovery_action') or '?'}")


def main():
    ap = argparse.ArgumentParser(description="智能注册执行器 — 有感知、防重复、到云提交即停")
    ap.add_argument("--case", type=Path, required=True, help="案例 JSON 路径")
    ap.add_argument("--verbose", action="store_true", help="打印每步 busiData 预览")
    ap.add_argument("--dry-run", action="store_true", help="只做预检（认证+重复检查），不实际执行")
    ap.add_argument("--login", action="store_true", help="先扫码登录再执行注册")
    ap.add_argument("--resume", action="store_true", help="从上次断点恢复 Phase 2")
    ap.add_argument("--cleanup-on-fail", action="store_true", help="失败后自动删除办件（默认保留现场）")
    ap.add_argument("--cleanup", action="store_true",
                    help="仅执行办件清理（不跑注册流程），必须配合 --cleanup-names 指定授权删除名称")
    ap.add_argument("--cleanup-names", type=str, default="",
                    help="授权删除的企业名称列表，逗号分隔（如 '美裕盈,钰启维'）。"
                         "仅删除名称完全匹配且状态为填写中(100)的办件。"
                         "不指定则只列出办件不删除。")
    args = ap.parse_args()

    # ★ 独立清理模式
    if args.cleanup:
        return _run_cleanup(args)

    runner = SmartRegisterRunner(args.case, verbose=args.verbose, dry_run=args.dry_run, do_login=args.login, do_resume=args.resume, cleanup_on_fail=args.cleanup_on_fail)
    return runner.execute()


def _run_cleanup(args):
    """独立清理模式：列出办件，仅删除授权名称的填写中办件。"""
    from icpsp_api_client import ICPSPClient
    import time as _t

    API = "/icpsp-api/v4/pc/manager/mattermanager/matters/operate"
    HDRS = {"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"}
    client = ICPSPClient()

    # 解析授权名称列表
    authorized = [n.strip() for n in args.cleanup_names.split(",") if n.strip()] if args.cleanup_names else []

    # 查询所有办件
    r = client.get_json("/icpsp-api/v4/pc/manager/mattermanager/matters/search",
                        params={"pageNo": "1", "pageSize": "50"})
    items = (r.get("data") or {}).get("busiData") or []

    print(f"\n{'='*60}")
    print(f"  办件清理工具 — 共 {len(items)} 条办件")
    print(f"  授权删除名称: {authorized or '(无 — 仅列出)'}")
    print(f"{'='*60}\n")

    status_map = {"10": "草稿", "20": "待审核", "50": "已受理",
                  "51": "审核中", "55": "已完成", "60": "已撤回",
                  "100": "填写中", "101": "待受理", "104": "已完成"}

    to_delete = []
    for it in items:
        bid = it.get("id", "")
        state = str(it.get("matterStateCode") or it.get("listMatterStateCode") or "")
        state_lang = str(it.get("matterStateLangCode") or "")
        bt = it.get("busiType", "")
        nm = it.get("entName", "")
        state_desc = status_map.get(state, state_lang)

        # 判断是否可删除：名称匹配 + 状态为填写中(100)
        is_authorized = any(a in nm for a in authorized) if authorized else False
        is_fill = "100" in state_lang or state in ("10", "100")
        can_delete = is_authorized and is_fill

        marker = "🗑️" if can_delete else ("⚠️" if is_authorized and not is_fill else "  ")
        print(f"  {marker} {bid}  状态={state_desc}  busiType={bt}  {nm}")

        if can_delete:
            to_delete.append({"busi_id": bid, "name": nm})

    if not authorized:
        print(f"\n  ⚠ 未指定 --cleanup-names，仅列出办件不执行删除")
        print(f"  用法: --cleanup --cleanup-names '名称1,名称2'")
        return 0

    if not to_delete:
        print(f"\n  ✅ 没有需要删除的办件（授权名称中无填写中的办件）")
        return 0

    print(f"\n  将删除 {len(to_delete)} 条办件:")
    for d in to_delete:
        print(f"    🗑️ {d['busi_id']}  {d['name']}")

    # 执行删除
    success_count = 0
    for d in to_delete:
        bid = str(d["busi_id"])
        nm = d["name"]
        try:
            r1 = client.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "before"}, extra_headers=HDRS)
            _t.sleep(0.3)
            r2 = client.post_json(API, {"busiId": bid, "btnCode": "103", "dealFlag": "operate"}, extra_headers=HDRS)
            code2 = r2.get("code", "")
            msg2 = (r2.get("data") or {}).get("msg", r2.get("msg", ""))[:60]
            if code2 == "00000":
                ok(f"已删除 {bid} ({nm})")
                success_count += 1
            else:
                fail(f"删除 {bid} ({nm}) 失败: code={code2} msg={msg2}")
            _t.sleep(0.3)
        except Exception as e:
            fail(f"删除 {bid} ({nm}) 异常: {e}")

    print(f"\n  清理完成: 成功 {success_count}/{len(to_delete)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
