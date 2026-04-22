#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP 自动化执行器 — 合规地操作政务平台
- 自动填写表单
- 检测认证要求（人脸/短信）
- 提交表单
- 查询办件进度
- 上传材料文件
"""

import json
import time
import os
import sys
import base64
import requests
import websocket

CDP_PORT = 9225
# 与 icpsp_entry 同目录的上一级为 system/
_SYSTEM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SYSTEM_DIR not in sys.path:
    sys.path.insert(0, _SYSTEM_DIR)
UPSTREAM_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
SITE_BASE = UPSTREAM_BASE + "/icpsp-web-pc/portal.html"

# 业务类型 → 路由映射
TASK_ROUTES = {
    "establish": "/index/enterprise/establish",
    "change": "/index/change-registration",
    "cancel_simple": "/index/force-cancel",
    "name_check": "/index/name-check",
    "enterprise_zone": "/index/enterprise/enterprise-zone",
    "track": "/company/my-space/selecthandle-progress",
    "track_detail": "/company/my-space/selecthandleprogress-detail",
    "enterprise_list": "/company/enterprise-list",
}


def get_ws(navigate_policy="host_only", busi_type="02_4"):
    """
    连接 CDP 页签。默认会按 icpsp_entry 规则优先选 9087 政务平台页签；
    若当前只有 6087 门户或其它页面，则导航到 9087 企业专区入口（不打断 core/name-register）。
    """
    try:
        from icpsp_entry import get_ws_url_for_icpsp

        u = get_ws_url_for_icpsp(
            CDP_PORT, busi_type=busi_type, navigate_policy=navigate_policy
        )
        if u:
            return u
    except Exception:
        pass
    pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"]
    return None


def cdp_eval(ws, js, msg_id=1, timeout=15):
    ws.send(json.dumps({
        "id": msg_id, "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}
    }))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == msg_id:
            return r.get("result", {}).get("result", {}).get("value")


def cdp_exec(ws, method, params=None, msg_id=1):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == msg_id:
            return r


class CDPAutomation:
    """CDP 自动化执行器"""

    def __init__(self):
        self.ws = None

    def connect(self):
        ws_url = get_ws()
        if not ws_url:
            return False
        self.ws = websocket.create_connection(ws_url, timeout=15)
        return True

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def ensure_connected(self):
        if not self.ws:
            return self.connect()
        try:
            self.ws.ping()
            return True
        except:
            self.ws = None
            return self.connect()

    # === 页面导航 ===

    def navigate_to_route(self, route_path, wait=4):
        """通过 Vue Router 跳转"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}
        result = cdp_eval(self.ws, f"""
            var app = document.getElementById('app');
            if (app && app.__vue__) {{
                app.__vue__.$router.push('{route_path}');
                return 'navigating';
            }}
            return 'no_vue';
        """)
        time.sleep(wait)
        # 验证导航结果
        current = cdp_eval(self.ws, "location.hash")
        return {"success": True, "route": route_path, "current_hash": current}

    # === 表单填写 ===

    def fill_form(self, form_data):
        """
        根据表单映射数据填写政务平台表单
        form_data: LLM 生成的 fields 映射
        """
        if not self.ensure_connected():
            return {"error": "CDP not connected"}

        results = {"filled": 0, "skipped": 0, "errors": []}
        fields = form_data.get("fields", {})

        for field_name, field_info in fields.items():
            if not field_info.get("auto_fill", True):
                results["skipped"] += 1
                continue
            if field_info.get("needs_confirm") or field_info.get("needs_client_input"):
                results["skipped"] += 1
                continue

            value = field_info.get("value", "")
            if not value:
                results["skipped"] += 1
                continue

            # 尝试多种方式填写
            fill_result = self._fill_field(field_name, value)
            if fill_result.get("success"):
                results["filled"] += 1
            else:
                results["errors"].append(f"{field_name}: {fill_result.get('error', 'unknown')}")

        return results

    def _fill_field(self, field_name, value):
        """智能填写单个字段：先按 label 找，再按 placeholder 找"""
        js = f"""
        (function() {{
            var value = `{value}`;
            var fieldName = '{field_name}';

            // 方式1: 按 el-form-item label 查找
            var formItems = document.querySelectorAll('.el-form-item');
            for (var i = 0; i < formItems.length; i++) {{
                var label = formItems[i].querySelector('.el-form-item__label');
                if (label && label.textContent.trim().includes(fieldName)) {{
                    var input = formItems[i].querySelector('.el-input__inner, .el-textarea__inner');
                    if (input) {{
                        var setter = Object.getOwnPropertyDescriptor(
                            window[input.tagName === 'TEXTAREA' ? 'HTMLTextAreaElement' : 'HTMLInputElement'].prototype, 'value'
                        ).set;
                        setter.call(input, value);
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return {{success: true, method: 'label', field: fieldName}};
                    }}
                    // 可能是 select
                    var selectInput = formItems[i].querySelector('.el-select .el-input__inner');
                    if (selectInput) {{
                        return {{success: false, method: 'select_needed', field: fieldName}};
                    }}
                }}
            }}

            // 方式2: 按 placeholder 查找
            var inputs = document.querySelectorAll('.el-input__inner, .el-textarea__inner');
            for (var i = 0; i < inputs.length; i++) {{
                var ph = inputs[i].placeholder || '';
                if (ph.includes(fieldName)) {{
                    var setter = Object.getOwnPropertyDescriptor(
                        window[inputs[i].tagName === 'TEXTAREA' ? 'HTMLTextAreaElement' : 'HTMLInputElement'].prototype, 'value'
                    ).set;
                    setter.call(inputs[i], value);
                    inputs[i].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{success: true, method: 'placeholder', field: fieldName}};
                }}
            }}

            return {{success: false, error: 'field_not_found', field: fieldName}};
        }})()
        """
        return cdp_eval(self.ws, js)

    def click_button(self, button_text):
        """点击按钮"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}
        return cdp_eval(self.ws, f"""
            (function() {{
                var btns = document.querySelectorAll('button, .el-button');
                for (var i = 0; i < btns.length; i++) {{
                    if (btns[i].textContent.trim().includes('{button_text}')) {{
                        btns[i].click();
                        return {{success: true, clicked: '{button_text}'}};
                    }}
                }}
                return {{error: 'button_not_found', text: '{button_text}'}};
            }})()
        """)

    # === 认证检测 ===

    def check_auth_required(self):
        """检测页面是否弹出认证要求（人脸/银行卡/短信）"""
        if not self.ensure_connected():
            return {"auth_required": False, "error": "CDP not connected"}

        result = cdp_eval(self.ws, """
            (function() {
                // 检测人脸认证弹窗
                var dialogs = document.querySelectorAll('.el-dialog, .el-message-box');
                for (var i = 0; i < dialogs.length; i++) {
                    var d = dialogs[i];
                    if (d.style.display !== 'none' && !d.classList.contains('hidden')) {
                        var text = d.textContent || '';
                        if (text.includes('人脸') || text.includes('认证') || text.includes('身份验证')) {
                            return {auth_required: true, auth_type: 'face', dialog_text: text.substring(0, 200)};
                        }
                    }
                }

                // 检测短信验证码输入框
                var smsInputs = document.querySelectorAll('input[placeholder*="验证码"], input[placeholder*="短信"]');
                if (smsInputs.length > 0) {
                    var visible = false;
                    for (var i = 0; i < smsInputs.length; i++) {
                        if (smsInputs[i].offsetParent !== null) {
                            visible = true;
                            break;
                        }
                    }
                    if (visible) {
                        return {auth_required: true, auth_type: 'sms', message: '需要短信验证码'};
                    }
                }

                // 检测银行卡认证区域
                var bankInputs = document.querySelectorAll('input[placeholder*="银行卡"], input[placeholder*="银行"]');
                if (bankInputs.length > 0) {
                    for (var i = 0; i < bankInputs.length; i++) {
                        if (bankInputs[i].offsetParent !== null) {
                            return {auth_required: true, auth_type: 'bank', message: '需要银行卡认证'};
                        }
                    }
                }

                // 检测页面文本中的认证提示
                var bodyText = document.body.innerText || '';
                if (bodyText.includes('请完成实名认证') || bodyText.includes('请进行人脸识别')) {
                    return {auth_required: true, auth_type: 'face', message: '页面要求认证'};
                }

                return {auth_required: false};
            })()
        """)
        return result or {"auth_required": False}

    def fill_sms_code(self, code):
        """填入短信验证码（客户提供的）"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}
        return cdp_eval(self.ws, f"""
            (function() {{
                var inputs = document.querySelectorAll('input[placeholder*="验证码"], input[placeholder*="短信"]');
                for (var i = 0; i < inputs.length; i++) {{
                    if (inputs[i].offsetParent !== null) {{
                        var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                        setter.call(inputs[i], '{code}');
                        inputs[i].dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return {{success: true}};
                    }}
                }}
                return {{error: 'sms_input_not_found'}};
            }})()
        """)

    # === 文件上传 ===

    def upload_file(self, file_path, label_hint=""):
        """通过 CDP 上传文件（不弹对话框）"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}

        # 找到 input[type=file] 并获取其 nodeId
        result = cdp_eval(self.ws, """
            (function() {
                var fileInputs = document.querySelectorAll('input[type="file"]');
                var results = [];
                for (var i = 0; i < fileInputs.length; i++) {
                    results.push({
                        index: i,
                        id: fileInputs[i].id,
                        name: fileInputs[i].name,
                        accept: fileInputs[i].accept,
                        visible: fileInputs[i].offsetParent !== null
                    });
                }
                return results;
            })()
        """)

        if not result or len(result) == 0:
            return {"error": "No file input found"}

        # 使用 DOM.setFileInputFiles 设置文件
        # 先获取 document 元素
        doc_result = cdp_exec(self.ws, "DOM.getDocument", {"depth": 0}, msg_id=100)
        root_node_id = doc_result.get("result", {}).get("root", {}).get("nodeId", 0)

        # 查找 file input 节点
        find_result = cdp_exec(self.ws, "DOM.querySelector", {
            "nodeId": root_node_id,
            "selector": "input[type='file']"
        }, msg_id=101)
        node_id = find_result.get("result", {}).get("nodeId", 0)

        if node_id == 0:
            return {"error": "File input node not found in DOM"}

        # 设置文件
        file_result = cdp_exec(self.ws, "DOM.setFileInputFiles", {
            "files": [file_path],
            "nodeId": node_id
        }, msg_id=102)

        return {"success": True, "file": file_path, "result": file_result.get("result", {})}

    # === 办件进度查询 ===

    def check_progress(self):
        """查询当前用户的办件进度"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}

        # 先跳转到办件进度页面
        self.navigate_to_route(TASK_ROUTES["track"], wait=4)

        # 读取表格数据
        table_data = cdp_eval(self.ws, """
            (function() {
                var table = document.querySelector('.el-table');
                if (!table) return {error: 'No table found', bodyText: document.body.innerText.substring(0, 500)};

                var headers = [];
                var ths = table.querySelectorAll('.el-table__header th .cell');
                for (var i = 0; i < ths.length; i++) {
                    headers.push(ths[i].textContent.trim());
                }

                var rows = [];
                var trs = table.querySelectorAll('.el-table__body tr');
                for (var i = 0; i < trs.length; i++) {
                    var cells = trs[i].querySelectorAll('td .cell');
                    var row = {};
                    for (var j = 0; j < cells.length && j < headers.length; j++) {
                        row[headers[j]] = cells[j].textContent.trim();
                    }
                    rows.push(row);
                }
                return {headers: headers, rows: rows, rowCount: rows.length};
            })()
        """)
        return table_data or {"error": "Failed to read table"}

    def get_enterprise_list(self):
        """查询经营主体列表"""
        if not self.ensure_connected():
            return {"error": "CDP not connected"}
        self.navigate_to_route(TASK_ROUTES["enterprise_list"], wait=4)
        return cdp_eval(self.ws, """
            (function() {
                var table = document.querySelector('.el-table');
                if (!table) return {error: 'No table found'};
                var headers = [];
                var ths = table.querySelectorAll('.el-table__header th .cell');
                for (var i = 0; i < ths.length; i++) headers.push(ths[i].textContent.trim());
                var rows = [];
                var trs = table.querySelectorAll('.el-table__body tr');
                for (var i = 0; i < trs.length; i++) {
                    var cells = trs[i].querySelectorAll('td .cell');
                    var row = {};
                    for (var j = 0; j < cells.length && j < headers.length; j++) row[headers[j]] = cells[j].textContent.trim();
                    rows.push(row);
                }
                return {headers: headers, rows: rows, rowCount: rows.length};
            })()
        """)

    # === 截图 ===

    def screenshot(self, save_path=None):
        """截图当前页面"""
        if not self.ensure_connected():
            return None
        msg_id = 900
        self.ws.send(json.dumps({
            "id": msg_id, "method": "Page.captureScreenshot",
            "params": {"format": "png", "quality": 80}
        }))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == msg_id:
                b64 = r.get("result", {}).get("data")
                if b64 and save_path:
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                return b64

    # === Token 获取 ===

    def get_token(self):
        """从浏览器获取当前 Token"""
        if not self.ensure_connected():
            return None
        result = cdp_eval(self.ws, """
            (function() {
                return {
                    Authorization: localStorage.getItem('Authorization') || '',
                    topToken: localStorage.getItem('top-token') || ''
                };
            })()
        """)
        return result

    # === API 调用（通过网关） ===

    def call_api(self, api_path, method="GET", data=None, gateway_port=8080):
        """通过 API 网关调用政务平台 API"""
        url = f"http://localhost:{gateway_port}{api_path}"
        try:
            if method == "GET":
                r = requests.get(url, timeout=30)
            else:
                r = requests.post(url, json=data, timeout=30)
            return r.json()
        except Exception as e:
            return {"error": str(e)}
