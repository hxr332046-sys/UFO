"""
纯 HTTP 扫码登录 + 获取 Authorization（完全无浏览器）

三种模式：
  full_login()   — 扫码登录 + 4 步 SSO → 拿 Authorization（首次/全过期时用）
  refresh_token() — 用已存 session cookies 静默续期（~2秒，无需扫码）
  ensure_token()  — 自动判断：token 有效→返回; 可续→续; 全过期→扫码

登录态层次：
  ① SESSIONFORTYRZ（tyrz 域，数小时） → 扫码建立，存 cookie 文件可跨次复用
  ② 6087 SESSION（TopIP） → SSO 链建立
  ③ Authorization（32位hex） → entservice 两轮 sign 获得，API 用这个

发现时间: 2026-04-22 23:41
"""
import json, time, re, sys, os, pickle
import requests
requests.packages.urllib3.disable_warnings()
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

PORTAL_9087 = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
PORTAL_6087 = "https://zhjg.scjdglj.gxzf.gov.cn:6087"
SSO_ENTSERVICE = f"{PORTAL_9087}/icpsp-api/sso/entservice?targetUrlKey=02_0002"
AUTH_FILE = ROOT / "packet_lab" / "out" / "runtime_auth_headers.json"
SESSION_FILE = ROOT / "packet_lab" / "out" / "http_session_cookies.pkl"
HEALTH_CHECK_URL = f"{PORTAL_9087}/icpsp-api/v4/pc/common/tools/getCacheCreateTime"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
XHR_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/plain, */*",
}

from login_qrcode import step1_get_login_page, step2_get_qrcode, step4_poll_scan, step5_submit_login


# ─── Session 持久化 ───

def _save_session(s):
    """保存 session cookies 到文件（跨次复用 SESSIONFORTYRZ）"""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "wb") as f:
        pickle.dump(s.cookies, f)

def _load_session(s):
    """从文件恢复 session cookies"""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "rb") as f:
                s.cookies = pickle.load(f)
            return True
        except Exception:
            pass
    return False

def _make_session():
    """创建干净的 requests session"""
    s = requests.Session()
    s.verify = False
    s.proxies = {"https": None, "http": None}
    s.headers.update(BROWSER_HEADERS)
    return s


# ─── 工具函数 ───

def follow_sso_chain(s, start_url, max_hops=20):
    """
    手动跟随 SSO redirect 链，处理 bridge 页面。
    返回 (最终 response, 所有 bridge POST 响应列表)
    """
    r = s.get(start_url, allow_redirects=False, timeout=15)
    bridge_responses = []
    
    for i in range(max_hops):
        loc = r.headers.get("Location", "")
        
        if r.status_code == 200:
            body = r.text
            # 检查是否是 bridge 页面
            if "tokenKey" in body and "xhr.open" in body:
                # 模拟 bridge JS: POST 到同一 URL
                r = s.post(r.url, allow_redirects=False, timeout=15, headers=XHR_HEADERS)
                bridge_responses.append(r)
                
                if r.status_code == 200:
                    try:
                        d = r.json()
                        code = d.get("code")
                        
                        if code == "0" or code == 0:
                            # 登录成功 → 检查 redirectUrl
                            data = d.get("data", {})
                            redirect_url = ""
                            if isinstance(data, dict):
                                redirect_url = data.get("redirectUrl", "")
                            
                            if redirect_url and redirect_url.startswith("http"):
                                # ssc 跳过
                                if "ssc.mohrss" in redirect_url:
                                    return r, bridge_responses
                                r = s.get(redirect_url, allow_redirects=False, timeout=15)
                                continue
                            # 相对 URL 或无 URL → 结束
                            return r, bridge_responses
                            
                        elif code == "-9" or code == -9:
                            # 需要 redirect 授权
                            data = d.get("data", {})
                            redirect_uri = ""
                            if isinstance(data, dict):
                                redirect_uri = data.get("redirect_uri", "")
                            if redirect_uri:
                                r = s.get(redirect_uri, allow_redirects=False, timeout=15)
                                continue
                    except Exception:
                        pass
                return r, bridge_responses
            # 非 bridge 的 200
            return r, bridge_responses
        
        if not loc:
            return r, bridge_responses
        
        # ssc 跳过
        if "ssc.mohrss" in loc:
            return r, bridge_responses
        
        # 跟随 redirect
        time.sleep(0.3)
        r = s.get(loc, allow_redirects=False, timeout=15)
    
    return r, bridge_responses


def extract_authorization(redirect_url):
    """从 redirectUrl 中提取 Authorization token"""
    m = re.search(r'Authorization=([a-f0-9]{32})', redirect_url)
    return m.group(1) if m else ""


# ─── 核心流程 ───

def _sso_steps_234(s, verbose=True):
    """
    Steps 2-4：用已有 SESSIONFORTYRZ 走 SSO 链拿 Authorization。
    不需要 QR 扫码。返回 token 或 None。
    """
    tag = "    " if verbose else ""
    def log(msg):
        if verbose:
            print(msg)
    
    # Step 2: 第一轮 SSO 链 → 6087 SESSION
    log(f"{tag}SSO 链 → 6087 SESSION...")
    r, bridges = follow_sso_chain(s, SSO_ENTSERVICE)
    has_6087 = any(c.name == "SESSION" and "TopIP" in c.path for c in s.cookies)
    if not has_6087:
        log(f"{tag}✗ 6087 SESSION 未建立（SESSIONFORTYRZ 可能过期）")
        return None
    log(f"{tag}✓ 6087 SESSION")

    # Step 3: 第一轮 entservice?sign → ENT_SERVICE session
    log(f"{tag}entservice?sign → ENT_SERVICE session...")
    try:
        s.cookies.clear(domain="zhjg.scjdglj.gxzf.gov.cn", path="/icpsp-api")
    except Exception:
        pass
    time.sleep(0.5)
    r, bridges = follow_sso_chain(s, SSO_ENTSERVICE)
    log(f"{tag}✓ ENT_SERVICE")

    # Step 4: 第二轮 entservice?sign → Authorization
    log(f"{tag}entservice?sign → Authorization...")
    time.sleep(0.5)
    r, bridges = follow_sso_chain(s, SSO_ENTSERVICE)
    
    auth_token = _extract_auth_from_bridges(bridges, r)
    if auth_token:
        log(f"{tag}✓ Authorization: {auth_token}")
    else:
        log(f"{tag}✗ 未找到 Authorization")
    return auth_token


def _extract_auth_from_bridges(bridges, final_r):
    """从 bridge 响应中提取 Authorization"""
    for br in bridges:
        try:
            d = br.json()
            data = d.get("data", {})
            if isinstance(data, dict):
                redir = data.get("redirectUrl", "")
                auth = extract_authorization(redir)
                if auth:
                    return auth
        except Exception:
            pass
    try:
        d = final_r.json()
        data = d.get("data", {})
        if isinstance(data, dict):
            return extract_authorization(data.get("redirectUrl", ""))
    except Exception:
        pass
    return ""


def _save_auth(auth_token, method_note=""):
    """保存 Authorization 到 runtime_auth_headers.json"""
    api_headers = {
        "User-Agent": BROWSER_HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "sec-ch-ua": BROWSER_HEADERS["sec-ch-ua"],
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Authorization": auth_token,
    }
    out = {
        "headers": api_headers,
        "ts": int(time.time()),
        "method": "qrcode_pure_http",
        "note": method_note or "纯HTTP扫码登录",
    }
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── 对外 API ───

def check_token_alive(token=None):
    """
    检查 token 是否还活着。
    返回 True/False。
    """
    if token is None:
        try:
            j = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
            token = j["headers"]["Authorization"]
        except Exception:
            return False
    if not token:
        return False
    try:
        h = {**BROWSER_HEADERS, "Authorization": token,
             "Accept": "application/json, text/plain, */*",
             "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"}
        r = requests.get(f"{HEALTH_CHECK_URL}?t={int(time.time()*1000)}",
                         headers=h, timeout=10, verify=False)
        j = r.json()
        return str(j.get("code")) == "00000"
    except Exception:
        return False


def refresh_token(verbose=True):
    """
    静默续期：用已存的 session cookies（含 SESSIONFORTYRZ）走 Step 2-4。
    不需要扫码，~2秒完成。
    返回新 Authorization 或 None（SESSIONFORTYRZ 过期则返回 None）。
    """
    s = _make_session()
    if not _load_session(s):
        if verbose:
            print("[refresh] 无保存的 session cookies")
        return None
    
    tyrz = s.cookies.get("SESSIONFORTYRZ", "")
    if not tyrz:
        if verbose:
            print("[refresh] SESSIONFORTYRZ 已丢失")
        return None
    
    if verbose:
        print(f"[refresh] 用已存 SESSIONFORTYRZ 静默续期...")
    
    token = _sso_steps_234(s, verbose=verbose)
    if token:
        _save_auth(token, "静默续期（无扫码）")
        _save_session(s)
        if verbose:
            print(f"[refresh] ✓ 新 token: {token}")
    else:
        if verbose:
            print(f"[refresh] ✗ 续期失败（SESSIONFORTYRZ 可能过期，需重新扫码）")
    return token


def full_login(verbose=True):
    """
    全新登录：QR 扫码 + 4 步 SSO → Authorization。
    需要人工扫码（~30秒）。
    返回 Authorization 或 None。
    """
    s = _make_session()

    if verbose:
        print("=" * 60)
        print("  纯 HTTP 扫码登录（完全无浏览器）")
        print("=" * 60)

    # Step 1: QR 扫码
    if verbose:
        print("\n[Step 1] QR 扫码登录...")
    csrf = step1_get_login_page(s)
    if not csrf:
        if verbose: print("ERROR: 获取登录页失败")
        return None

    session_id, qr_img = step2_get_qrcode(s, user_type=1)
    if not session_id:
        if verbose: print("ERROR: 获取 QR 码失败")
        return None

    qr_path = ROOT / "packet_lab" / "out" / "login_qrcode.png"
    qr_path.parent.mkdir(parents=True, exist_ok=True)
    qr_path.write_bytes(qr_img)
    os.startfile(str(qr_path))
    if verbose:
        print(f"    二维码已打开，请用智桂通APP扫码...")

    if not step4_poll_scan(s, session_id, timeout_sec=180):
        if verbose: print("ERROR: 扫码超时")
        return None

    redirect_url = step5_submit_login(s, csrf, session_id)
    if not redirect_url:
        if verbose: print("ERROR: 提交登录失败")
        return None

    tyrz = s.cookies.get("SESSIONFORTYRZ", "")
    if verbose:
        print(f"    ✓ SESSIONFORTYRZ: {tyrz[:20]}...")

    # Steps 2-4: SSO 链
    if verbose:
        print(f"\n[Step 2-4] SSO 链 → Authorization...")
    token = _sso_steps_234(s, verbose=verbose)
    
    if token:
        _save_auth(token, "纯HTTP扫码登录")
        _save_session(s)  # 保存 cookies 供后续静默续期
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"  ✓ 纯 HTTP 全流程完成！")
            print(f"  Authorization: {token}")
            print(f"  session 已保存，后续可静默续期（无需扫码）")
            print(f"{'=' * 60}")
    else:
        if verbose:
            print(f"ERROR: 未找到 Authorization")
    return token


def ensure_token(verbose=True):
    """
    智能获取 token（推荐入口）：
      1. 当前 token 有效 → 直接返回
      2. 有保存的 session → 静默续期（~2秒）
      3. 都不行 → QR 扫码登录（~30秒）
    """
    # 1. 检查现有 token
    try:
        j = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        existing = j["headers"]["Authorization"]
        if check_token_alive(existing):
            if verbose:
                print(f"[ensure] ✓ 现有 token 仍然有效: {existing[:8]}...")
            return existing
        if verbose:
            print(f"[ensure] 现有 token 已过期")
    except Exception:
        if verbose:
            print(f"[ensure] 无已保存 token")
    
    # 2. 尝试静默续期
    if verbose:
        print(f"[ensure] 尝试静默续期...")
    token = refresh_token(verbose=verbose)
    if token:
        return token
    
    # 3. 全新扫码登录
    if verbose:
        print(f"[ensure] 需要重新扫码登录")
    return full_login(verbose=verbose)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="纯 HTTP 扫码登录")
    parser.add_argument("--refresh", action="store_true", help="只静默续期，不扫码")
    parser.add_argument("--check", action="store_true", help="只检查 token 是否存活")
    parser.add_argument("--login", action="store_true", help="强制全新扫码登录")
    args = parser.parse_args()
    
    if args.check:
        alive = check_token_alive()
        print(f"Token {'alive ✓' if alive else 'dead ✗'}")
        sys.exit(0 if alive else 1)
    elif args.refresh:
        token = refresh_token()
        sys.exit(0 if token else 1)
    elif args.login:
        token = full_login()
        sys.exit(0 if token else 1)
    else:
        token = ensure_token()
        sys.exit(0 if token else 1)
