"""Try different login entry points to find the working one."""
import json, sys, time, requests, websocket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws_url = target["webSocketDebuggerUrl"]

def try_url(url, label, wait=5):
    ws = websocket.create_connection(ws_url, timeout=15)
    _id = [0]
    def ev(expr):
        _id[0] += 1
        ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                             "params": {"expression": expr, "returnByValue": True, "timeout": 15000}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == _id[0]:
                return msg.get("result", {}).get("result", {}).get("value")

    # Navigate
    ws.send(json.dumps({"id": 999, "method": "Page.navigate", "params": {"url": url}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 999:
            break
    time.sleep(wait)
    
    state = ev("""(function(){
        return {
            href: location.href,
            title: document.title || '',
            body: (document.body && document.body.innerText || '').substring(0, 300),
            hasInputs: document.querySelectorAll('input').length,
            hasPassword: document.querySelectorAll('input[type="password"]').length,
            hasSlider: !!document.querySelector('[class*="slider"],[class*="slide-verify"]'),
            iframes: document.querySelectorAll('iframe').length,
            auth: (localStorage.getItem('Authorization') || '').substring(0, 12),
        };
    })()""")
    ws.close()
    
    href = state.get("href", "") if state else "error"
    body = state.get("body", "")[:100] if state else ""
    inputs = state.get("hasInputs", 0) if state else 0
    pwd = state.get("hasPassword", 0) if state else 0
    slider = state.get("hasSlider", False) if state else False
    iframes = state.get("iframes", 0) if state else 0
    auth = state.get("auth", "") if state else ""
    
    print(f"\n=== {label} ===")
    print(f"  URL:     {url[:80]}")
    print(f"  Landed:  {href[:100]}")
    print(f"  Inputs:  {inputs} (password: {pwd})")
    print(f"  Slider:  {slider}")
    print(f"  Iframes: {iframes}")
    print(f"  Auth:    {auth or '(empty)'}")
    print(f"  Body:    {body[:120]}")
    return state

# Try different routes
urls = [
    ("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/page", "login/page"),
    ("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/login/authPage", "login/authPage"),
    ("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone", "enterprise-zone"),
    ("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html", "portal root"),
]

for url, label in urls:
    try:
        try_url(url, label, wait=6)
    except Exception as e:
        print(f"\n=== {label} === ERROR: {e}")
    time.sleep(2)
