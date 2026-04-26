#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CDP Helper for 政务平台自动化
提供浏览器连接、页面跳转、表单操控、截图等基础能力
"""

import json
import time
import base64
import requests
import websocket


class CDPHelper:
    """Chrome DevTools Protocol helper for 政务平台"""

    CDP_PORT = 9225
    CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"
    SITE_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"

    def __init__(self, port=9225):
        self.port = port
        self.cdp_http = f"http://127.0.0.1:{port}"
        self.ws = None
        self._msg_id = 0

    def _next_id(self):
        self._msg_id += 1
        return self._msg_id

    def connect(self):
        """连接到当前活动页面"""
        pages = requests.get(f"{self.cdp_http}/json", timeout=5).json()
        page = None
        for p in pages:
            if p.get("type") == "page" and "chrome://" not in p.get("url", ""):
                page = p
                break
        if not page:
            for p in pages:
                if p.get("type") == "page":
                    page = p
                    break
        if not page:
            raise ConnectionError("No CDP page found")
        ws_url = page["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=15)
        return page

    def close(self):
        """关闭连接"""
        if self.ws:
            self.ws.close()
            self.ws = None

    def eval(self, js, timeout=15):
        """执行 JavaScript 并返回结果"""
        msg_id = self._next_id()
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}
        }))
        while True:
            result = json.loads(self.ws.recv())
            if result.get("id") == msg_id:
                return result.get("result", {}).get("result", {}).get("value")

    def navigate(self, route_path, wait=3):
        """
        通过 Vue Router 跳转到指定路由
        :param route_path: 如 '/index/enterprise/enterprise-zone'
        :param wait: 等待页面渲染时间(秒)
        """
        self.eval(f"""
            var app = document.getElementById('app');
            if (app && app.__vue__) {{
                app.__vue__.$router.push('{route_path}');
            }}
        """)
        time.sleep(wait)

    def navigate_url(self, url, wait=5):
        """通过 CDP Page.navigate 导航到完整 URL"""
        msg_id = self._next_id()
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        time.sleep(wait)

    def get_page_info(self):
        """获取当前页面信息"""
        return self.eval("""
            (function() {
                return {
                    title: document.title,
                    url: location.href,
                    hash: location.hash,
                    readyState: document.readyState
                };
            })()
        """)

    def get_vuex_state(self, module=None):
        """获取 Vuex store 状态"""
        if module:
            return self.eval(f"""
                var app = document.getElementById('app');
                app && app.__vue__ && app.__vue__.$store ? app.__vue__.$store.state['{module}'] : null
            """)
        return self.eval("""
            var app = document.getElementById('app');
            if (app && app.__vue__ && app.__vue__.$store) {
                var state = app.__vue__.$store.state;
                var keys = Object.keys(state);
                var summary = {};
                for (var i = 0; i < keys.length; i++) {
                    var k = keys[i];
                    var v = state[k];
                    summary[k] = typeof v === 'object' ? Object.keys(v) : v;
                }
                return summary;
            }
            return null;
        """)

    # === Element-UI 表单操控 ===

    def set_el_input(self, selector, value):
        """
        设置 Element-UI el-input 的值并触发 Vue 响应式
        :param selector: CSS 选择器，如 '.el-input__inner'
        :param value: 要设置的值
        """
        return self.eval(f"""
            (function() {{
                var input = document.querySelector('{selector}');
                if (!input) return {{error: 'Element not found', selector: '{selector}'}};
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                nativeInputValueSetter.call(input, '{value}');
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return {{success: true, value: '{value}'}};
            }})()
        """)

    def set_el_textarea(self, selector, value):
        """设置 el-textarea 的值"""
        return self.eval(f"""
            (function() {{
                var textarea = document.querySelector('{selector}');
                if (!textarea) return {{error: 'Element not found'}};
                var nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                nativeTextareaValueSetter.call(textarea, `{value}`);
                textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return {{success: true}};
            }})()
        """)

    def click_el_select_option(self, select_selector, option_text, wait=0.5):
        """
        点击 el-select 并选择指定选项
        :param select_selector: el-select 的 CSS 选择器
        :param option_text: 选项文本
        """
        self.eval(f"""
            var select = document.querySelector('{select_selector} .el-input__inner') ||
                         document.querySelector('{select_selector}');
            if (select) select.click();
        """)
        time.sleep(wait)
        return self.eval(f"""
            (function() {{
                var options = document.querySelectorAll('.el-select-dropdown__item');
                for (var i = 0; i < options.length; i++) {{
                    if (options[i].textContent.trim() === '{option_text}') {{
                        options[i].click();
                        return {{success: true, selected: '{option_text}'}};
                    }}
                }}
                return {{error: 'Option not found', available: Array.from(options).map(function(o) {{ return o.textContent.trim(); }}).slice(0, 20)}};
            }})()
        """)

    def click_el_radio(self, label_text):
        """点击 el-radio 指定选项"""
        return self.eval(f"""
            (function() {{
                var labels = document.querySelectorAll('.el-radio, .el-radio-button');
                for (var i = 0; i < labels.length; i++) {{
                    var span = labels[i].querySelector('.el-radio__label, .el-radio-button__inner');
                    if (span && span.textContent.trim() === '{label_text}') {{
                        labels[i].querySelector('input').click();
                        return {{success: true, selected: '{label_text}'}};
                    }}
                }}
                return {{error: 'Radio not found', label: '{label_text}'}};
            }})()
        """)

    def click_button(self, button_text):
        """点击指定文本的按钮"""
        return self.eval(f"""
            (function() {{
                var btns = document.querySelectorAll('button, .el-button');
                for (var i = 0; i < btns.length; i++) {{
                    if (btns[i].textContent.trim().includes('{button_text}')) {{
                        btns[i].click();
                        return {{success: true, clicked: '{button_text}'}};
                    }}
                }}
                return {{error: 'Button not found', text: '{button_text}'}};
            }})()
        """)

    def click_card(self, card_title):
        """点击首页服务卡片"""
        return self.eval(f"""
            (function() {{
                var cards = document.querySelectorAll('[class*="card"]');
                for (var i = 0; i < cards.length; i++) {{
                    var title = cards[i].querySelector('[class*="title"]');
                    if (title && title.textContent.trim() === '{card_title}') {{
                        cards[i].click();
                        return {{success: true, clicked: '{card_title}'}};
                    }}
                }}
                return {{error: 'Card not found', title: '{card_title}'}};
            }})()
        """)

    # === 数据读取 ===

    def get_el_table_data(self, table_selector='.el-table'):
        """读取 Element-UI 表格数据"""
        return self.eval(f"""
            (function() {{
                var table = document.querySelector('{table_selector}');
                if (!table) return {{error: 'Table not found'}};
                var headers = [];
                var ths = table.querySelectorAll('.el-table__header th .cell');
                for (var i = 0; i < ths.length; i++) {{
                    headers.push(ths[i].textContent.trim());
                }}
                var rows = [];
                var trs = table.querySelectorAll('.el-table__body tr');
                for (var i = 0; i < trs.length; i++) {{
                    var cells = trs[i].querySelectorAll('td .cell');
                    var row = {{}};
                    for (var j = 0; j < cells.length && j < headers.length; j++) {{
                        row[headers[j]] = cells[j].textContent.trim();
                    }}
                    rows.push(row);
                }}
                return {{headers: headers, rows: rows, rowCount: rows.length}};
            }})()
        """)

    def get_el_form_data(self, form_selector='.el-form'):
        """读取 Element-UI 表单当前值"""
        return self.eval(f"""
            (function() {{
                var form = document.querySelector('{form_selector}');
                if (!form) return {{error: 'Form not found'}};
                var inputs = form.querySelectorAll('.el-input__inner, .el-textarea__inner, .el-select .el-input__inner');
                var data = {{}};
                for (var i = 0; i < inputs.length; i++) {{
                    var inp = inputs[i];
                    var label = '';
                    var formItem = inp.closest('.el-form-item');
                    if (formItem) {{
                        var lbl = formItem.querySelector('.el-form-item__label');
                        label = lbl ? lbl.textContent.trim() : 'field_' + i;
                    }}
                    data[label] = inp.value || inp.textContent || '';
                }}
                return data;
            }})()
        """)

    # === 截图 ===

    def screenshot(self, save_path=None):
        """截图当前页面"""
        msg_id = self._next_id()
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.captureScreenshot",
            "params": {"format": "png", "quality": 80}
        }))
        while True:
            result = json.loads(self.ws.recv())
            if result.get("id") == msg_id:
                b64 = result.get("result", {}).get("data")
                if b64 and save_path:
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                return b64

    # === 网络监听 ===

    def enable_network(self):
        """启用网络请求监听"""
        self.ws.send(json.dumps({"id": self._next_id(), "method": "Network.enable", "params": {}}))

    def wait_for_response(self, url_pattern, timeout=15):
        """等待匹配 URL 模式的网络响应"""
        self.ws.settimeout(timeout)
        while True:
            msg = json.loads(self.ws.recv())
            method = msg.get("method", "")
            if method == "Network.responseReceived":
                url = msg.get("params", {}).get("response", {}).get("url", "")
                if url_pattern in url:
                    return msg.get("params", {})
            if method == "Network.requestWillBeSent":
                url = msg.get("params", {}).get("request", {}).get("url", "")
                if url_pattern in url:
                    request_id = msg.get("params", {}).get("requestId")
                    # Wait for corresponding response
                    continue


# === 便捷函数 ===

def create_helper(port=9225):
    """创建并连接 CDP Helper"""
    helper = CDPHelper(port)
    helper.connect()
    return helper
