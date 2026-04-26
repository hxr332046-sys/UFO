#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CDP 辅助模块 — BenefitUsers 受益所有人自动化

1151 有限公司 ComplementInfo 的 BenefitUsers 子流程需要 syr.samr.gov.cn iframe 交互，
纯 HTTP 协议无法完成。此模块通过 CDP 驱动浏览器完成以下 10 步流程：

  1. 连接 CDP → 找到 core.html 主页签
  2. 确保当前 SPA 在 busiId 的 ComplementInfo 组件（必要时导航）
  3. 找到 benefit-users 组件并调用 handleAction('add') 打开对话框
  4. 等待 syr iframe 加载（url 含 'syr' 或 'bow'）
  5. 连接 syr iframe target，enable Network 监听
  6. 填表：selectedOption='03'(承诺免报) + handleRadioChange + isButtonDisabled=false
  7. 提交 handleClickNext → POST /befapip/dataAdd.do
  8. 监听 dataAdd 响应 + rePro.do + BenefitCallback（必要时点"确定"弹窗）
  9. 补丁所有 Vue 组件的 flowData.currCompUrl：BenefitUsers → ComplementInfo
 10. 返回状态，调用方随后 HTTP save ComplementInfo

用法：
    from cdp_benefit_users import run_benefit_users_commit

    result = run_benefit_users_commit(
        busi_id="2047225160991752194",
        name_id="2047218022607474690",
        ent_type="1151",
        busi_type="02_4",
        timeout_total_sec=180,
    )
    if result["success"]:
        # HTTP save ComplementInfo
        ...

退出：
    成功: {"success": True, "stage": "done", "currCompUrl": "ComplementInfo" or "Rules", ...}
    失败: {"success": False, "stage": "...", "error": "...", ...}
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.error

try:
    import websocket  # type: ignore
except ImportError:  # pragma: no cover
    websocket = None


ROOT = Path(__file__).resolve().parent.parent
CFG_BROWSER = ROOT / "config" / "browser.json"

HOST_9087 = "zhjg.scjdglj.gxzf.gov.cn:9087"
CORE_URL_TPL = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"
    "#/flow/base?fromProject=portal&busiId={busi_id}"
    "&busiType={busi_type}&entType={ent_type}&nameId={name_id}"
)


# ─── CDP 基础 ────────────────────────────────────────────────────────
def _cdp_port() -> int:
    """从 config/browser.json 读 CDP 端口。"""
    try:
        with CFG_BROWSER.open(encoding="utf-8") as f:
            return int(json.load(f).get("cdp_port") or 9225)
    except Exception:
        return 9225


def _list_targets(port: int) -> List[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return []


def _pick_core_tab(port: int) -> Optional[Dict[str, Any]]:
    """选 core.html 主页签。"""
    tabs = _list_targets(port)
    for t in tabs:
        if t.get("type") == "page" and "core.html" in str(t.get("url") or ""):
            return t
    # 兜底：9087 上任意 page
    for t in tabs:
        if t.get("type") == "page" and HOST_9087 in str(t.get("url") or ""):
            return t
    return None


def _pick_syr_tab(port: int) -> Optional[Dict[str, Any]]:
    """找 syr.samr.gov.cn iframe target（url 含 'syr' 或 'bow'）。"""
    tabs = _list_targets(port)
    for t in tabs:
        u = str(t.get("url") or "").lower()
        if t.get("type") in ("iframe", "page") and ("syr" in u or "bow" in u):
            return t
    return None


class _CDP:
    """简单的 CDP WebSocket 封装，支持 Runtime.evaluate 和方法调用。"""

    def __init__(self, ws_url: str, *, timeout: int = 60):
        if websocket is None:
            raise RuntimeError("websocket-client not installed")
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self._id = 0

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def call(self, method: str, params: Optional[Dict[str, Any]] = None,
             *, timeout: float = 15.0) -> Dict[str, Any]:
        """发送 CDP 方法调用并等响应（只拿匹配 id 的那条）。"""
        mid = self._next_id()
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.ws.settimeout(max(0.5, deadline - time.time()))
                raw = self.ws.recv()
            except Exception:
                continue
            try:
                m = json.loads(raw)
            except Exception:
                continue
            if m.get("id") == mid:
                return m.get("result") or {}
        return {}

    def eval(self, expr: str, *, timeout: float = 20.0,
             await_promise: bool = False) -> Any:
        """Runtime.evaluate → 返回 value（或错误字符串前缀 "__cdp_ex: ..."）。"""
        res = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "timeout": int(timeout * 1000),
            },
            timeout=timeout + 2,
        )
        if not res:
            return None
        if res.get("exceptionDetails"):
            ex = res["exceptionDetails"]
            return f"__cdp_ex: {ex.get('text') or json.dumps(ex)}"
        return (res.get("result") or {}).get("value")

    def recv_event(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """非阻塞接收 CDP 事件（method 字段有值）。"""
        try:
            self.ws.settimeout(max(0.1, timeout))
            raw = self.ws.recv()
        except Exception:
            return None
        try:
            m = json.loads(raw)
        except Exception:
            return None
        if m.get("method"):
            return m
        return None


# ─── Vue 树查找 JS 片段 ─────────────────────────────────────────────────
JS_FIND_FC = """
(function(){
    var app = document.querySelector('#app');
    if (!app || !app.__vue__) return 'no_app';
    var q = [app.__vue__]; var vis = new Set();
    while (q.length) {
        var v = q.shift();
        if (vis.has(v._uid)) continue; vis.add(v._uid);
        if (v.$options && v.$options.name === 'flow-control') {
            window.__fc = v;
            var fd = v.$data.flowData || {};
            return JSON.stringify({
                curCompUrl: v.$data.curCompUrl || v.curCompUrl,
                curStep: v.$data.curStep,
                busiId: fd.busiId,
                entType: fd.entType,
                currCompUrl_server: fd.currCompUrl,
            });
        }
        if (v.$children) for (var i = 0; i < v.$children.length; i++) q.push(v.$children[i]);
    }
    return 'no_fc';
})()
"""

JS_OPEN_BU_DIALOG = """
(function(){
    var app = document.querySelector('#app');
    if (!app || !app.__vue__) return 'no_app';
    var q = [app.__vue__]; var vis = new Set();
    while (q.length) {
        var v = q.shift();
        if (vis.has(v._uid)) continue; vis.add(v._uid);
        if (v.$options && v.$options.name === 'benefit-users' && v.$data && v.$data.operationType !== undefined) {
            window.__bu = v;
            try { v.handleAction('add'); return 'opened'; }
            catch(e) { return 'error: ' + e.message; }
        }
        if (v.$children) for (var i = 0; i < v.$children.length; i++) q.push(v.$children[i]);
    }
    return 'no_bu';
})()
"""

JS_PATCH_FLOW = """
(function(){
    var app = document.querySelector('#app');
    if (!app || !app.__vue__) return 'no_app';
    var q = [app.__vue__]; var vis = new Set(); var patched = [];
    while (q.length) {
        var v = q.shift();
        if (vis.has(v._uid)) continue; vis.add(v._uid);
        if (v.$data) {
            var d = v.$data;
            if (d.flowData && d.flowData.currCompUrl === 'BenefitUsers') {
                d.flowData.currCompUrl = 'ComplementInfo';
                patched.push(v.$options.name + ':flowData(uid=' + v._uid + ')');
            }
            if (d.businessDataInfo && d.businessDataInfo.data) {
                var bdd = d.businessDataInfo.data;
                if (bdd.flowData && bdd.flowData.currCompUrl === 'BenefitUsers') {
                    bdd.flowData.currCompUrl = 'ComplementInfo';
                    patched.push(v.$options.name + ':bdi.flowData(uid=' + v._uid + ')');
                }
                if (bdd.linkData && bdd.linkData.compUrl === 'BenefitUsers') {
                    bdd.linkData.compUrl = 'ComplementInfo';
                    patched.push(v.$options.name + ':bdi.linkData.compUrl(uid=' + v._uid + ')');
                }
            }
            if (d.businessInfoList && d.businessInfoList.flowData
                && d.businessInfoList.flowData.currCompUrl === 'BenefitUsers') {
                d.businessInfoList.flowData.currCompUrl = 'ComplementInfo';
                patched.push(v.$options.name + ':bil.flowData(uid=' + v._uid + ')');
            }
        }
        if (v.$children) for (var i = 0; i < v.$children.length; i++) q.push(v.$children[i]);
    }
    return JSON.stringify(patched);
})()
"""

JS_CLOSE_DIALOGS = """
(function(){
    document.querySelectorAll('.el-message-box__btns .el-button--primary').forEach(function(b){
        if(b.offsetParent) b.click();
    });
    var app = document.querySelector('#app');
    if (!app || !app.__vue__) return 'no_app';
    var q = [app.__vue__]; var vis = new Set();
    while (q.length) {
        var v = q.shift();
        if (vis.has(v._uid)) continue; vis.add(v._uid);
        if (v.$data && v.$data.dialogVisible !== undefined
            && v.$options && v.$options.name === 'benefit-users') {
            v.$data.dialogVisible = false;
        }
        if (v.$children) for (var i = 0; i < v.$children.length; i++) q.push(v.$children[i]);
    }
    return 'cleaned';
})()
"""


# ─── 主流程 ───────────────────────────────────────────────────────────
def _navigate_if_needed(cdp: _CDP, *, busi_id: str, name_id: str,
                        ent_type: str, busi_type: str) -> Dict[str, Any]:
    """检查 flow-control 是否在正确 busiId，否则导航。"""
    state_s = cdp.eval(JS_FIND_FC, timeout=10)
    if isinstance(state_s, str) and state_s.startswith("{"):
        try:
            st = json.loads(state_s)
            if str(st.get("busiId") or "") == str(busi_id):
                return {"navigated": False, "state": st}
        except Exception:
            pass
    # 导航
    url = CORE_URL_TPL.format(
        busi_id=busi_id, name_id=name_id,
        ent_type=ent_type, busi_type=busi_type,
    )
    cdp.eval(f"window.location.href = {json.dumps(url)};", timeout=5)
    time.sleep(8)
    # 重新探测
    for _ in range(5):
        state_s = cdp.eval(JS_FIND_FC, timeout=10)
        if isinstance(state_s, str) and state_s.startswith("{"):
            try:
                return {"navigated": True, "state": json.loads(state_s)}
            except Exception:
                pass
        time.sleep(3)
    return {"navigated": True, "state": None}


def _wait_syr_iframe(port: int, *, timeout_sec: int = 30) -> Optional[Dict[str, Any]]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        t = _pick_syr_tab(port)
        if t and t.get("webSocketDebuggerUrl"):
            return t
        time.sleep(1.5)
    return None


def _commit_in_syr(syr_cdp: _CDP, *, monitor_timeout_sec: int = 120) -> Dict[str, Any]:
    """在 syr iframe 内选"承诺免报" → handleClickNext → 监听网络。"""
    # 开 Network
    syr_cdp.call("Network.enable", timeout=5)
    time.sleep(0.5)

    # 读 vm 状态
    info = syr_cdp.eval("""(function(){
        var el = document.querySelector('#CompanyPage');
        if (!el || !el.__vue__) return 'no_vm';
        var vm = el.__vue__;
        return JSON.stringify({
            sessionid: vm.sessionid,
            selectedOption: vm.selectedOption,
            isButtonDisabled: vm.isButtonDisabled,
        });
    })()""", timeout=10)

    # 选 承诺免报 (03)
    syr_cdp.eval("""(function(){
        var vm = document.querySelector('#CompanyPage').__vue__;
        vm.selectedOption = '03';
        try { vm.handleRadioChange('03'); } catch(e) {}
        vm.isButtonDisabled = false;
        return 'selected';
    })()""", timeout=10)
    time.sleep(1)

    # 提交
    syr_cdp.eval("""(function(){
        var vm = document.querySelector('#CompanyPage').__vue__;
        vm.handleClickNext();
        return 'submitted';
    })()""", timeout=10)

    # 监听 Network：dataAdd.do / rePro.do / BenefitCallback
    results: Dict[str, Any] = {"info": info, "events": []}
    saw_dataadd = False
    saw_callback = False
    deadline = time.time() + monitor_timeout_sec
    while time.time() < deadline:
        ev = syr_cdp.recv_event(timeout=2.0)
        if not ev:
            continue
        m = ev.get("method") or ""
        p = ev.get("params") or {}
        if m == "Network.responseReceived":
            url = str((p.get("response") or {}).get("url") or "")
            status = (p.get("response") or {}).get("status")
            lurl = url.lower()
            if "dataadd" in lurl or "repro" in lurl or "benefit" in lurl:
                results["events"].append({"url": url[:200], "status": status})
                if "dataadd" in lurl and status == 200:
                    saw_dataadd = True
                if "benefitcallback" in lurl and status == 200:
                    saw_callback = True
                    # 回调到了就可以退出监听
                    break
        # 无事件 hook 弹窗确认
    results["saw_dataadd"] = saw_dataadd
    results["saw_callback"] = saw_callback
    return results


def run_benefit_users_commit(
    *,
    busi_id: str,
    name_id: str,
    ent_type: str = "1151",
    busi_type: str = "02_4",
    timeout_total_sec: int = 240,
) -> Dict[str, Any]:
    """BenefitUsers 完整 CDP 流程。

    成功返回 {"success": True, "stage": "done", "events": [...], ...}
    失败返回 {"success": False, "stage": "<失败点>", "error": "..."}
    """
    if websocket is None:
        return {"success": False, "stage": "prereq",
                "error": "websocket-client 未安装；无法通过 CDP 驱动"}

    t_start = time.time()
    port = _cdp_port()

    # 1. 主 tab
    main_tab = _pick_core_tab(port)
    if not main_tab or not main_tab.get("webSocketDebuggerUrl"):
        return {"success": False, "stage": "connect_main",
                "error": f"CDP {port} 无 core.html 页签（请先打开 Edge Dev 并登录）"}

    main_cdp = _CDP(main_tab["webSocketDebuggerUrl"], timeout=60)
    try:
        # 2. 导航到正确 busiId
        nav_info = _navigate_if_needed(
            main_cdp, busi_id=busi_id, name_id=name_id,
            ent_type=ent_type, busi_type=busi_type,
        )

        # 3. 先清理遗留弹窗
        main_cdp.eval(JS_CLOSE_DIALOGS, timeout=10)
        time.sleep(1)

        # 4. 打开 benefit-users dialog
        open_ret = main_cdp.eval(JS_OPEN_BU_DIALOG, timeout=10)
        if open_ret != "opened":
            return {"success": False, "stage": "open_dialog",
                    "error": f"无法打开 benefit-users 对话框: {open_ret}",
                    "nav": nav_info}

        # 5. 等 syr iframe
        syr_tab = _wait_syr_iframe(port, timeout_sec=40)
        if not syr_tab:
            return {"success": False, "stage": "wait_syr",
                    "error": "syr/bow iframe 未出现（可能 syr 服务不稳定，稍后重试）",
                    "nav": nav_info}

        # 6. 连接 syr CDP target 并提交"承诺免报"
        syr_cdp = _CDP(syr_tab["webSocketDebuggerUrl"], timeout=120)
        try:
            remain = max(60, timeout_total_sec - int(time.time() - t_start))
            commit_ret = _commit_in_syr(syr_cdp, monitor_timeout_sec=min(120, remain))
        finally:
            syr_cdp.close()

        # 7. 回到主页面处理弹窗确认 → 触发 rePro.do + form.submit → BenefitCallback
        main_cdp.eval(
            """document.querySelectorAll('.el-message-box__btns .el-button--primary')
               .forEach(function(b){ if(b.offsetParent) b.click(); });""",
            timeout=5,
        )
        time.sleep(3)

        # 8. 等一会儿让 BenefitCallback 完成（如果监听没抓到）
        if not commit_ret.get("saw_callback"):
            time.sleep(8)

        # 9. 关闭所有对话框
        main_cdp.eval(JS_CLOSE_DIALOGS, timeout=5)
        time.sleep(1)

        # 10. 补丁所有 flowData.currCompUrl
        patch_ret = main_cdp.eval(JS_PATCH_FLOW, timeout=10)

        # 读最终状态
        state_s = main_cdp.eval(JS_FIND_FC, timeout=10)
        final_state = None
        try:
            if isinstance(state_s, str) and state_s.startswith("{"):
                final_state = json.loads(state_s)
        except Exception:
            pass

        return {
            "success": True,
            "stage": "done",
            "commit": commit_ret,
            "patched": patch_ret,
            "state": final_state,
            "elapsed_sec": round(time.time() - t_start, 2),
        }
    except Exception as e:
        return {"success": False, "stage": "exception", "error": str(e)}
    finally:
        main_cdp.close()


__all__ = ["run_benefit_users_commit"]
