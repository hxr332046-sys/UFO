#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
政务平台反向代理服务器
将政务平台 API 代理到本地，自动注入认证 Token
支持：API 代理、静态资源代理、Token 自动刷新

启动方式：
    python reverse_proxy.py [--port 8080] [--token TOKEN]

使用方式：
    1. 先通过 CDP 登录政务平台获取 Token
    2. 启动本代理服务器
    3. 访问 http://localhost:8080 即可使用已认证的 API
"""

import argparse
import json
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, urljoin, urlencode, parse_qs
import ssl

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)


# === 配置 ===
UPSTREAM_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
API_PREFIX = "/icpsp-api"
STATIC_PREFIX = "/icpsp-web-pc"
PROXY_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "proxy.json")


def load_proxy_config():
    """加载代理配置"""
    if os.path.exists(PROXY_CONFIG_PATH):
        with open(PROXY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_proxy_config(config):
    """保存代理配置"""
    os.makedirs(os.path.dirname(PROXY_CONFIG_PATH), exist_ok=True)
    with open(PROXY_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def fetch_token_from_cdp():
    """从 CDP 连接的浏览器中自动获取当前 Token"""
    try:
        import websocket as ws_lib
        cdp_port = 9225
        pages = requests.get(f"http://127.0.0.1:{cdp_port}/json", timeout=3).json()
        page = None
        for p in pages:
            if p.get("type") == "page" and "zhjg" in p.get("url", ""):
                page = p
                break
        if not page:
            for p in pages:
                if p.get("type") == "page":
                    page = p
                    break
        if not page:
            return None

        ws_url = page["webSocketDebuggerUrl"]
        ws = ws_lib.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": """
                    (function() {
                        return {
                            Authorization: localStorage.getItem('Authorization') || '',
                            topToken: localStorage.getItem('top-token') || ''
                        };
                    })()
                """,
                "returnByValue": True
            }
        }))
        result = json.loads(ws.recv())
        ws.close()
        value = result.get("result", {}).get("result", {}).get("value", {})
        if value and value.get("Authorization"):
            return value
    except Exception as e:
        print(f"CDP token fetch failed: {e}")
    return None


class GovProxyHandler(BaseHTTPRequestHandler):
    """政务平台反向代理处理器"""

    # 类级别共享状态
    auth_token = None
    top_token = None
    token_lock = threading.Lock()
    token_refresh_time = 0

    @classmethod
    def set_tokens(cls, authorization, top_token=None):
        """设置认证 Token"""
        with cls.token_lock:
            cls.auth_token = authorization
            cls.top_token = top_token
            cls.token_refresh_time = time.time()

    @classmethod
    def auto_refresh_token(cls):
        """自动从 CDP 刷新 Token（每5分钟）"""
        while True:
            time.sleep(300)
            tokens = fetch_token_from_cdp()
            if tokens and tokens.get("Authorization"):
                cls.set_tokens(tokens["Authorization"], tokens.get("topToken"))
                print(f"[Token] Auto-refreshed: {tokens['Authorization'][:16]}...")

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[Proxy] {self.address_string()} - {format % args}")

    def _proxy_request(self, method):
        """代理请求到上游服务器"""
        # 构建上游 URL
        parsed = urlparse(self.path)
        upstream_url = UPSTREAM_BASE + self.path

        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # 构建请求头
        headers = {}
        for key, value in self.headers.items():
            # 跳过 hop-by-hop 头和 host
            if key.lower() in ('host', 'connection', 'keep-alive', 'proxy-authenticate',
                               'proxy-authorization', 'te', 'trailers',
                               'transfer-encoding', 'upgrade'):
                continue
            headers[key] = value

        # 注入认证 Token
        with self.token_lock:
            if self.auth_token:
                headers["Authorization"] = self.auth_token
            if self.top_token:
                headers["top-token"] = self.top_token

        # 修改 Host 和 Origin
        headers["Host"] = "zhjg.scjdglj.gxzf.gov.cn:9087"
        headers["Origin"] = UPSTREAM_BASE
        headers["Referer"] = UPSTREAM_BASE + "/icpsp-web-pc/portal.html"

        try:
            # 发送请求到上游
            resp = requests.request(
                method=method,
                url=upstream_url,
                headers=headers,
                data=body,
                verify=False,  # 政务网站可能有自签名证书
                timeout=30,
                allow_redirects=False
            )

            # 返回响应头
            self.send_response(resp.status_code)

            # 透传响应头（跳过 hop-by-hop）
            for key, value in resp.headers.items():
                if key.lower() in ('connection', 'keep-alive', 'transfer-encoding',
                                   'content-encoding', 'content-length'):
                    continue
                self.send_header(key, value)

            # 处理 CORS
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, top-token, Content-Type")

            # 写入响应体
            content = resp.content
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except requests.RequestException as e:
            self.send_error(502, f"Upstream error: {str(e)}")

    def do_GET(self):
        """处理 GET 请求"""
        self._proxy_request("GET")

    def do_POST(self):
        """处理 POST 请求"""
        self._proxy_request("POST")

    def do_PUT(self):
        """处理 PUT 请求"""
        self._proxy_request("PUT")

    def do_DELETE(self):
        """处理 DELETE 请求"""
        self._proxy_request("DELETE")

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, top-token, Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="政务平台反向代理")
    parser.add_argument("--port", type=int, default=8080, help="代理端口 (默认 8080)")
    parser.add_argument("--token", type=str, help="Authorization Token (可选，不提供则自动从CDP获取)")
    parser.add_argument("--top-token", type=str, help="top-token (可选)")
    parser.add_argument("--no-auto-refresh", action="store_true", help="禁用自动Token刷新")
    args = parser.parse_args()

    # 获取 Token
    if args.token:
        auth_token = args.token
        top_token = args.top_token
        print(f"[Token] From argument: {auth_token[:16]}...")
    else:
        print("[Token] Fetching from CDP browser...")
        tokens = fetch_token_from_cdp()
        if tokens and tokens.get("Authorization"):
            auth_token = tokens["Authorization"]
            top_token = tokens.get("topToken")
            print(f"[Token] From CDP: Authorization={auth_token[:16]}... top-token={top_token[:16] if top_token else 'N/A'}...")
        else:
            # 尝试从配置文件读取
            config = load_proxy_config()
            auth_token = config.get("last_token")
            top_token = config.get("last_top_token")
            if auth_token:
                print(f"[Token] From config: {auth_token[:16]}...")
            else:
                print("[ERROR] No token available. Please login first or provide --token")
                sys.exit(1)

    # 设置 Token
    GovProxyHandler.set_tokens(auth_token, top_token)

    # 保存到配置
    config = load_proxy_config()
    config["last_token"] = auth_token
    config["last_top_token"] = top_token
    config["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_proxy_config(config)

    # 启动自动刷新
    if not args.no_auto_refresh:
        refresh_thread = threading.Thread(target=GovProxyHandler.auto_refresh_token, daemon=True)
        refresh_thread.start()
        print("[Token] Auto-refresh enabled (every 5 min from CDP)")

    # 启动代理服务器
    server = HTTPServer(("0.0.0.0", args.port), GovProxyHandler)
    print(f"\n{'='*60}")
    print(f"  政务平台反向代理已启动")
    print(f"  代理地址: http://localhost:{args.port}")
    print(f"  上游地址: {UPSTREAM_BASE}")
    print(f"  API 示例: http://localhost:{args.port}{API_PREFIX}/v4/pc/common/tools/getCacheCreateTime")
    print(f"  Token: {auth_token[:16]}...")
    print(f"{'='*60}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Proxy] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    # 禁用 SSL 警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
