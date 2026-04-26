#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
政务平台 API 网关
增强版反向代理，支持：
1. Token 自动注入与刷新（从 CDP 浏览器获取）
2. API 请求日志记录
3. 响应缓存（减少重复请求）
4. API 路由重写
5. 批量操作接口
6. Web 管理面板

启动方式：
    python api_gateway.py [--port 8080]
"""

import argparse
import json
import hashlib
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import OrderedDict
import ssl

try:
    import requests
    import websocket as ws_lib
except ImportError:
    print("Please install: pip install requests websocket-client")
    sys.exit(1)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# === 配置 ===
UPSTREAM_BASE = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
API_PREFIX = "/icpsp-api"
CDP_PORT = 9225
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache")

for d in [DATA_DIR, LOG_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)


# === Token 管理器 ===
class TokenManager:
    """Token 自动管理：从 CDP 获取、自动刷新、持久化"""

    TOKEN_FILE = os.path.join(DATA_DIR, "tokens.json")

    def __init__(self):
        self.authorization = None
        self.top_token = None
        self.user_info = None
        self.lock = threading.Lock()
        self.refresh_time = 0
        self._load()

    def _load(self):
        """从文件加载 Token"""
        if os.path.exists(self.TOKEN_FILE):
            with open(self.TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.authorization = data.get("authorization")
                self.top_token = data.get("top_token")
                self.user_info = data.get("user_info")
                self.refresh_time = data.get("refresh_time", 0)
                if self.authorization:
                    print(f"[Token] Loaded from file: {self.authorization[:16]}...")

    def _save(self):
        """持久化 Token"""
        with open(self.TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "authorization": self.authorization,
                "top_token": self.top_token,
                "user_info": self.user_info,
                "refresh_time": self.refresh_time,
                "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }, f, ensure_ascii=False, indent=2)

    def get_from_cdp(self):
        """从 CDP 浏览器获取 Token"""
        try:
            pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3).json()
            page = None
            for p in pages:
                if p.get("type") == "page" and "zhjg" in p.get("url", ""):
                    page = p
                    break
            if not page:
                for p in pages:
                    if p.get("type") == "page" and "chrome://" not in p.get("url", ""):
                        page = p
                        break
            if not page:
                return False

            ws_url = page["webSocketDebuggerUrl"]
            ws = ws_lib.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """
                        (function() {
                            var app = document.getElementById('app');
                            var vuexUser = app && app.__vue__ && app.__vue__.$store ?
                                app.__vue__.$store.state.common : {};
                            return {
                                Authorization: localStorage.getItem('Authorization') || '',
                                topToken: localStorage.getItem('top-token') || '',
                                userInfo: vuexUser.userInfo || null,
                                token: vuexUser.token || ''
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
                with self.lock:
                    self.authorization = value["Authorization"]
                    self.top_token = value.get("topToken")
                    self.user_info = value.get("userInfo")
                    self.refresh_time = time.time()
                self._save()
                print(f"[Token] Refreshed from CDP: {self.authorization[:16]}...")
                return True
        except Exception as e:
            print(f"[Token] CDP fetch error: {e}")
        return False

    def get_headers(self):
        """获取认证请求头"""
        with self.lock:
            headers = {}
            if self.authorization:
                headers["Authorization"] = self.authorization
            if self.top_token:
                headers["top-token"] = self.top_token
            return headers

    def auto_refresh(self, interval=300):
        """自动刷新循环"""
        while True:
            time.sleep(interval)
            self.get_from_cdp()

    def is_valid(self):
        """检查 Token 是否有效"""
        return bool(self.authorization)


# === API 缓存 ===
class LRUCache:
    """LRU 缓存，减少重复 API 请求"""

    def __init__(self, max_size=100, ttl=60):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def _key(self, method, url, body=None):
        raw = f"{method}:{url}:{body or ''}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, method, url, body=None):
        with self.lock:
            k = self._key(method, url, body)
            if k in self.cache:
                entry = self.cache[k]
                if time.time() - entry["time"] < self.ttl:
                    self.cache.move_to_end(k)
                    return entry["data"]
                else:
                    del self.cache[k]
        return None

    def set(self, method, url, data, body=None):
        with self.lock:
            k = self._key(method, url, body)
            self.cache[k] = {"data": data, "time": time.time()}
            self.cache.move_to_end(k)
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def clear(self):
        with self.lock:
            self.cache.clear()


# === API 日志 ===
class APILogger:
    """API 请求日志记录"""

    LOG_FILE = os.path.join(LOG_DIR, "api_log.jsonl")

    def __init__(self):
        self.lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0

    def log(self, method, path, status, duration, token_prefix=None):
        self.request_count += 1
        if status >= 400:
            self.error_count += 1
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration * 1000),
            "token": token_prefix
        }
        with self.lock:
            with open(self.LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_stats(self):
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "log_file": self.LOG_FILE
        }


# === 网关处理器 ===
class GatewayHandler(BaseHTTPRequestHandler):
    """API 网关请求处理器"""

    token_mgr = None
    cache = None
    api_logger = None

    # 不缓存的路径模式
    NO_CACHE_PATTERNS = ["/login", "/logout", "/submit", "/apply", "/save", "/delete", "/update"]

    def log_message(self, format, *args):
        pass  # 使用自定义日志

    def _is_api_request(self):
        """判断是否为 API 请求"""
        return self.path.startswith(API_PREFIX)

    def _is_admin_request(self):
        """判断是否为管理面板请求"""
        return self.path.startswith("/_admin")

    def _proxy_api(self, method):
        """代理 API 请求"""
        start = time.time()
        upstream_url = UPSTREAM_BASE + self.path

        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # 检查缓存（仅 GET 且非敏感路径）
        use_cache = (method == "GET" and
                     not any(p in self.path for p in self.NO_CACHE_PATTERNS))
        if use_cache:
            cached = self.cache.get(method, upstream_url)
            if cached:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Cache", "HIT")
                content = json.dumps(cached, ensure_ascii=False).encode('utf-8')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # 构建请求头
        headers = {}
        for key, value in self.headers.items():
            if key.lower() in ('host', 'connection', 'keep-alive', 'transfer-encoding',
                               'content-encoding', 'content-length'):
                continue
            headers[key] = value

        # 注入认证 Token
        auth_headers = self.token_mgr.get_headers()
        headers.update(auth_headers)
        headers["Host"] = "zhjg.scjdglj.gxzf.gov.cn:9087"
        headers["Origin"] = UPSTREAM_BASE
        headers["Referer"] = UPSTREAM_BASE + "/icpsp-web-pc/portal.html"

        try:
            resp = requests.request(
                method=method,
                url=upstream_url,
                headers=headers,
                data=body,
                verify=False,
                timeout=30,
                allow_redirects=False
            )

            duration = time.time() - start

            # 记录日志
            token_prefix = self.token_mgr.authorization[:16] if self.token_mgr.authorization else "None"
            self.api_logger.log(method, self.path, resp.status_code, duration, token_prefix)

            # 处理 Token 过期
            if resp.status_code == 401:
                # 尝试刷新 Token 并重试
                if self.token_mgr.get_from_cdp():
                    auth_headers = self.token_mgr.get_headers()
                    headers.update(auth_headers)
                    resp = requests.request(
                        method=method, url=upstream_url, headers=headers,
                        data=body, verify=False, timeout=30, allow_redirects=False
                    )

            # 返回响应
            self.send_response(resp.status_code)

            for key, value in resp.headers.items():
                if key.lower() in ('connection', 'keep-alive', 'transfer-encoding',
                                   'content-encoding', 'content-length'):
                    continue
                self.send_header(key, value)

            # CORS
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, top-token, Content-Type")

            content = resp.content
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

            # 缓存成功的 GET 响应
            if use_cache and resp.status_code == 200:
                try:
                    data = resp.json()
                    self.cache.set(method, upstream_url, data)
                except:
                    pass

        except requests.RequestException as e:
            duration = time.time() - start
            self.api_logger.log(method, self.path, 502, duration, "ERROR")
            self.send_error(502, f"Upstream error: {str(e)}")

    def _handle_admin(self):
        """处理管理面板请求"""
        if self.path == "/_admin/status":
            status = {
                "token": {
                    "authorization": (self.token_mgr.authorization[:16] + "...") if self.token_mgr.authorization else None,
                    "top_token": (self.token_mgr.top_token[:16] + "...") if self.token_mgr.top_token else None,
                    "refresh_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.token_mgr.refresh_time)) if self.token_mgr.refresh_time else None,
                    "is_valid": self.token_mgr.is_valid()
                },
                "cache": {
                    "size": len(self.cache.cache),
                    "max_size": self.cache.max_size,
                    "ttl": self.cache.ttl
                },
                "stats": self.api_logger.get_stats(),
                "upstream": UPSTREAM_BASE
            }
            self._send_json(status)

        elif self.path == "/_admin/token/refresh":
            success = self.token_mgr.get_from_cdp()
            self._send_json({"success": success, "token": (self.token_mgr.authorization[:16] + "...") if self.token_mgr.authorization else None})

        elif self.path == "/_admin/cache/clear":
            self.cache.clear()
            self._send_json({"success": True, "message": "Cache cleared"})

        elif self.path == "/_admin/token/set":
            # POST: 手动设置 Token
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(body)
            if data.get("authorization"):
                self.token_mgr.authorization = data["authorization"]
                self.token_mgr.top_token = data.get("top_token")
                self.token_mgr._save()
                self._send_json({"success": True})
            else:
                self._send_json({"error": "authorization required"}, 400)

        else:
            self._send_json({"error": "Unknown admin endpoint", "available": [
                "/_admin/status", "/_admin/token/refresh",
                "/_admin/token/set (POST)", "/_admin/cache/clear"
            ]}, 404)

    def _send_json(self, data, status=200):
        """发送 JSON 响应"""
        content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self._is_admin_request():
            self._handle_admin()
        else:
            self._proxy_api("GET")

    def do_POST(self):
        if self._is_admin_request():
            self._handle_admin()
        else:
            self._proxy_api("POST")

    def do_PUT(self):
        self._proxy_api("PUT")

    def do_DELETE(self):
        self._proxy_api("DELETE")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, top-token, Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="政务平台 API 网关")
    parser.add_argument("--port", type=int, default=8080, help="网关端口 (默认 8080)")
    parser.add_argument("--cache-ttl", type=int, default=60, help="缓存 TTL 秒 (默认 60)")
    parser.add_argument("--cache-size", type=int, default=100, help="缓存最大条目 (默认 100)")
    parser.add_argument("--refresh-interval", type=int, default=300, help="Token 刷新间隔秒 (默认 300)")
    parser.add_argument("--no-auto-refresh", action="store_true", help="禁用自动 Token 刷新")
    args = parser.parse_args()

    # 初始化组件
    token_mgr = TokenManager()
    cache = LRUCache(max_size=args.cache_size, ttl=args.cache_ttl)
    api_logger = APILogger()

    GatewayHandler.token_mgr = token_mgr
    GatewayHandler.cache = cache
    GatewayHandler.api_logger = api_logger

    # 首次获取 Token
    if not token_mgr.is_valid():
        print("[Init] Fetching token from CDP...")
        token_mgr.get_from_cdp()

    if not token_mgr.is_valid():
        print("[ERROR] No token available. Please login to 政务平台 first.")
        sys.exit(1)

    # 启动自动刷新
    if not args.no_auto_refresh:
        refresh_thread = threading.Thread(
            target=token_mgr.auto_refresh,
            args=(args.refresh_interval,),
            daemon=True
        )
        refresh_thread.start()
        print(f"[Token] Auto-refresh every {args.refresh_interval}s")

    # 启动网关
    server = HTTPServer(("0.0.0.0", args.port), GatewayHandler)
    print(f"\n{'='*60}")
    print(f"  政务平台 API 网关已启动")
    print(f"  网关地址: http://localhost:{args.port}")
    print(f"  上游地址: {UPSTREAM_BASE}")
    print(f"  管理面板: http://localhost:{args.port}/_admin/status")
    print(f"  Token刷新: http://localhost:{args.port}/_admin/token/refresh")
    print(f"  缓存清理: http://localhost:{args.port}/_admin/cache/clear")
    print(f"  API 示例: http://localhost:{args.port}{API_PREFIX}/v4/pc/common/tools/getCacheCreateTime")
    print(f"  Token: {token_mgr.authorization[:16]}...")
    print(f"{'='*60}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
