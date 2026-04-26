"""在浏览器 Runtime 里直接发一次 MBI save（用浏览器真实 session），对比 Python 结果。

目标：**区分**是 body 问题还是 session/cookie 问题
- 如果浏览器发同样 body → 成功 = Python 那边是 session 问题
- 如果浏览器发同样 body → 也 D0003 = body 确实还差字段
"""
from __future__ import annotations
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

import websocket  # type: ignore

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system"))

CDP_HTTP = "http://127.0.0.1:9225/json"


def pick_core_tab():
    tabs = json.loads(urllib.request.urlopen(CDP_HTTP, timeout=5).read())
    for t in tabs:
        if t.get("type") == "page" and "core.html" in t.get("url", ""):
            return t
    raise SystemExit("未找到 core.html tab")


def cdp(ws, method, params=None, mid=None, timeout=10):
    if mid is None:
        mid = int(time.time() * 10000) % 1000000
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    ws.settimeout(timeout)
    while True:
        try:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m.get("result") or m.get("error") or {}
        except websocket.WebSocketTimeoutException:
            return {"_err": "timeout"}


def ev(ws, expr, await_p=False, timeout=15):
    r = cdp(ws, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "awaitPromise": await_p
    }, timeout=timeout)
    if r.get("exceptionDetails"):
        return {"_exc": str(r["exceptionDetails"])[:500]}
    return (r.get("result") or {}).get("value")


def fetch_and_wait(ws, fetch_js_body_lines: list, wait_sec: int = 12) -> str:
    """fire-and-forget 模式：在浏览器里发 fetch，把结果存 window.__r__，轮询读取。

    fetch_js_body_lines 是 fetch() 的配置 JS（作为 await_expr 代替 fetch() 内部），
    此函数会包装成：window.__r__=null; fetch(...).then(r=>r.json()).then(j=>{window.__r__=j});
    然后 sleep wait_sec 秒再读 window.__r__
    """
    wrap = f"""
    (function(){{
        try {{
            window.__r__ = null; window.__e__ = null;
            {''.join(fetch_js_body_lines)}
            return 'sent';
        }} catch(e) {{ window.__e__ = String(e); return 'exc'; }}
    }})()
    """
    r = ev(ws, wrap, await_p=False, timeout=10)
    if r != "sent":
        return f"send_err: {r}"
    time.sleep(wait_sec)
    out = ev(ws, "JSON.stringify({r:window.__r__, e:window.__e__})", timeout=10)
    return out


def phase_a_python_to_step15():
    """Python 纯协议到 step 15 + 构造同样的 MBI load + save body。"""
    from icpsp_api_client import ICPSPClient  # type: ignore
    import phase2_protocol_driver as drv  # type: ignore
    import phase2_bodies as pb  # type: ignore

    CASE = json.load(open("docs/case_有为诚.json", encoding="utf-8"))
    BUSI_ID = "2047533149403086848"
    NAME_ID = "2047533981928857602"

    client = ICPSPClient()
    ctx = drv.Phase2Context(case=CASE, busi_id=BUSI_ID, ent_type="4540")
    ctx.name_id = NAME_ID
    ctx.snapshot["nameId"] = NAME_ID

    drv.step12_establish_location(client, ctx)
    time.sleep(0.4)
    try: drv.step13_ybb_select(client, ctx)
    except Exception: pass
    time.sleep(0.4)
    drv.step14_basicinfo_load(client, ctx)
    time.sleep(0.4)
    r15 = drv.step15_basicinfo_save(client, ctx)
    ebid = ctx.snapshot.get("establish_busiId")
    assert r15.get("code") == "00000" and ebid, f"step 15 failed: {r15}"
    print(f"  establish_busiId = {ebid}")

    # 预热 MBI → 拿 base 49-key 模板
    time.sleep(1.5)
    mbi_load_body = {
        "flowData": pb._base_flow_data(ctx.ent_type, ctx.name_id, "MemberBaseInfo", busi_id=ebid),
        "linkData": pb._base_link_data("MemberBaseInfo", ope_type="load",
                                          parents=["MemberPost"]),
        "itemId": "",
    }
    mbi_load_resp = client.post_json(
        "/icpsp-api/v4/pc/register/establish/component/MemberBaseInfo/loadBusinessDataInfo",
        mbi_load_body,
        extra_headers={"Referer": "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html"},
    )
    mbi_base = (mbi_load_resp.get("data") or {}).get("busiData") or {}
    print(f"  MBI load (Python) code={mbi_load_resp.get('code')} signInfo={mbi_base.get('signInfo')}")

    # 用这个 base 构造 save body（注意 ctx 和 CASE 都传进去）
    mbi_save_body = pb.build_memberbaseinfo_save_body(
        CASE, mbi_base,
        ent_type="4540", name_id=NAME_ID, busi_id=ebid,
    )
    return {
        "ebid": ebid,
        "nameId": NAME_ID,
        "mbi_load_body": mbi_load_body,
        "mbi_save_body": mbi_save_body,
    }


def main():
    print("=" * 60)
    print("[A] Python 跑 step 1-15 + 预构造 MBI load/save body")
    print("=" * 60)
    info = phase_a_python_to_step15()

    print("\n" + "=" * 60)
    print("[B] 连浏览器 core.html tab，用浏览器 session 发同一个 MBI load")
    print("=" * 60)

    tab = pick_core_tab()
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)
    cdp(ws, "Runtime.enable")

    # 把我们的 body 传到浏览器里，用 fetch 发出去
    load_body_json = json.dumps(info["mbi_load_body"], ensure_ascii=False)
    load_b64 = base64.b64encode(load_body_json.encode("utf-8")).decode("ascii")

    print(f"\n[B-1] 浏览器 fetch MBI load (Python 构造的同一 body)")
    r = fetch_and_wait(ws, [
        f"var auth = localStorage.getItem('Authorization');",
        f"var b64 = '{load_b64}';",
        "var body = JSON.parse(decodeURIComponent(escape(atob(b64))));",
        "fetch('/icpsp-api/v4/pc/register/establish/component/MemberBaseInfo/loadBusinessDataInfo?t='+Date.now(), {",
        "  method:'POST',",
        "  headers:{'Authorization':auth,'Content-Type':'application/json;charset=UTF-8','language':'CH'},",
        "  body:JSON.stringify(body),",
        "  credentials:'include',",
        "}).then(function(r){return r.json();}).then(function(j){window.__r__=j;}).catch(function(e){window.__e__=String(e);});",
    ], wait_sec=8)
    print(f"  {r[:300]}")

    # 关键：发 MBI save 用浏览器 session
    save_body_json = json.dumps(info["mbi_save_body"], ensure_ascii=False)
    save_b64 = base64.b64encode(save_body_json.encode("utf-8")).decode("ascii")
    print(f"\n  body size: {len(save_body_json)} chars, base64: {len(save_b64)}")

    print(f"\n[B-2] 浏览器 fetch MBI save (Python 构造的同一 body)")
    time.sleep(1.5)
    r = fetch_and_wait(ws, [
        f"var auth = localStorage.getItem('Authorization');",
        f"var b64 = '{save_b64}';",
        "var body = JSON.parse(decodeURIComponent(escape(atob(b64))));",
        "fetch('/icpsp-api/v4/pc/register/establish/component/MemberBaseInfo/operationBusinessDataInfo?t='+Date.now(), {",
        "  method:'POST',",
        "  headers:{'Authorization':auth,'Content-Type':'application/json;charset=UTF-8','language':'CH'},",
        "  body:JSON.stringify(body),",
        "  credentials:'include',",
        "}).then(function(r){return r.json();}).then(function(j){window.__r__=j;}).catch(function(e){window.__e__=String(e);});",
    ], wait_sec=12)
    print(f"  {r[:500]}")

    ws.close()

    print("\n=== 解读 ===")
    print("  如果 [B-2] code=00000 → 浏览器能过，Python 是 session 问题")
    print("  如果 [B-2] code=D0003 → body 本身有问题（不是 session）")
    print("  如果 [B-2] code=D0001/A0002 → 字段校验失败，看 msg")


if __name__ == "__main__":
    main()
