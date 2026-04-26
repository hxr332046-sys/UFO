#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 portal tab (已认证) 的 JS 上下文直接调用 ComplementInfo API。
完全绕过 session 注入问题 — 浏览器的 cookie 就是 portal 页签已有的那套。
"""
import json, time, sys
from pathlib import Path
import requests, websocket

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "packet_lab" / "out" / "complement_info_save_body.json"
OUT2 = ROOT / "packet_lab" / "out" / "complement_info_load_resp.json"
CDP_PORT = 9225

BUSI_ID  = "2047910256739598337"
NAME_ID  = "2047910192228147201"
ENT_TYPE = "4540"
BASE_API = "https://zhjg.scjdglj.gxzf.gov.cn:9087"
SIGN_INFO = "-1607173598"

def find_portal_tab():
    tabs = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=5).json()
    # 优先找 9087 portal
    for t in tabs:
        if t.get("type") == "page" and "9087" in t.get("url", ""):
            return t
    for t in tabs:
        if t.get("type") == "page":
            return t
    return None

def connect_ws(url):
    ws = websocket.WebSocket()
    ws.connect(url, timeout=30)
    ws.settimeout(60)
    return ws

def send_c(ws, method, params=None, mid=1):
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r
        except websocket.WebSocketTimeoutException:
            continue
    raise TimeoutError(method)

def js_fetch(ws, url, body_dict, mid=1):
    """在浏览器 JS 上下文中用 fetch 调用 API，返回响应 JSON。"""
    body_json = json.dumps(json.dumps(body_dict))  # double-encode for JS string
    js = f"""
(async function() {{
    try {{
        var resp = await fetch({json.dumps(url)}, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'Authorization': localStorage.getItem('Authorization') || ''
            }},
            credentials: 'include',
            body: {body_json}
        }});
        var text = await resp.text();
        return JSON.stringify({{status: resp.status, body: text.substring(0,3000)}});
    }} catch(e) {{
        return JSON.stringify({{error: e.message}});
    }}
}})()
"""
    r = send_c(ws, "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
        "awaitPromise": True,
        "timeout": 60000
    }, mid=mid)
    val = (r.get("result") or {}).get("result", {}).get("value", "{}")
    try:
        return json.loads(val)
    except Exception:
        return {"raw": val}

def main():
    tab = find_portal_tab()
    if not tab:
        print("[!] 找不到 9087 页签"); return
    print(f"[tab] {tab['url'][:80]}")
    ws = connect_ws(tab["webSocketDebuggerUrl"])
    mid = 1

    send_c(ws, "Network.enable", {}, mid=mid); mid += 1

    # ─── Step 1: 先 load ComplementInfo，获取服务端当前数据 ───────────────
    load_url = f"{BASE_API}/icpsp-api/v4/pc/register/establish/component/ComplementInfo/loadBusinessDataInfo"
    load_body = {
        "flowData": {
            "busiId": BUSI_ID,
            "entType": ENT_TYPE,
            "busiType": "02_4",
            "currCompUrl": "ComplementInfo"
        },
        "linkData": {
            "compUrl": "ComplementInfo",
            "opeType": "load",
            "compUrlPaths": ["ComplementInfo"]
        },
        "signInfo": SIGN_INFO,
        "itemId": ""
    }
    print("[load] 调用 loadBusinessDataInfo...")
    lr = js_fetch(ws, load_url, load_body, mid=mid); mid += 1
    lb = lr.get("body", "")
    try:
        ld = json.loads(lb)
        print(f"  code={ld.get('code')} msg={ld.get('msg','')}")
        data = ld.get("data", {})
        bd = data.get("busiData", {})
        pbf = bd.get("partyBuildFlag")
        pbd = bd.get("partyBuildDto")
        si  = data.get("signInfo") or data.get("linkData", {}).get("signInfo")
        lk  = data.get("linkData", {})
        print(f"  partyBuildFlag: {pbf}")
        print(f"  partyBuildDto: {json.dumps(pbd, ensure_ascii=False)[:300] if pbd else 'None'}")
        print(f"  signInfo (from load): {si}")
        print(f"  linkData keys: {list(lk.keys())}")
        OUT2.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT2, "w", encoding="utf-8") as f:
            json.dump(ld, f, ensure_ascii=False, indent=2)
        print(f"  → 完整 load 响应保存到: {OUT2}")
    except Exception as e:
        print(f"  解析失败: {e}, raw: {lb[:200]}")
        ld = {}
        data = {}; bd = {}; pbd = {}; lk = {}; si = SIGN_INFO

    # 获取动态 signInfo
    dyn_si = data.get("signInfo") or (data.get("linkData",{}).get("signInfo")) or SIGN_INFO

    # ─── Step 2: 构建 save body ──────────────────────────────────────────
    # 从 load 响应里取 linkData，并把 opeType 改为 save
    save_lk = dict(lk) if lk else {}
    save_lk["opeType"] = "save"
    if not save_lk.get("compUrl"):
        save_lk["compUrl"] = "ComplementInfo"
    if not save_lk.get("compUrlPaths"):
        save_lk["compUrlPaths"] = ["ComplementInfo"]

    # 去掉 busiCompComb（触发 D0029 的元凶）
    save_lk.pop("busiCompComb", None)
    save_lk.pop("compCombArr", None)

    # 构造 partyBuildDto — 所有选"否"
    pbd_save = {
        "partyBuildFlag": "6",
        "estParSign":     "2",   # 是否建立党组织建制 → 否
        "numParM":        "0",   # 党员人数
        "legRepSign":     "2",   # 法定代表人党组织书记标志 → 否
        "annInspSign":    "2",   # 本年检年度组建党组织标志 → 否
        "legRepParMemSign": "2"  # 法定代表人党员标志 → 否
    }

    # 如果 load 里有现成 pbd，合并进去
    if pbd and isinstance(pbd, dict):
        merged = {**pbd, **pbd_save}
        # 过滤元数据字段
        skip = {"fieldList", "editFlag", "required", "label", "placeholder",
                "type", "optionList", "maxLength", "reg"}
        merged = {k: v for k, v in merged.items() if k not in skip}
    else:
        merged = pbd_save

    save_body = {
        "flowData": {
            "busiId":       BUSI_ID,
            "entType":      ENT_TYPE,
            "busiType":     "02_4",
            "currCompUrl":  "ComplementInfo"
        },
        "linkData":      save_lk,
        "signInfo":      str(dyn_si),
        "itemId":        "",
        "partyBuildDto": merged,
    }
    print(f"\n[save] body partyBuildDto: {json.dumps(merged, ensure_ascii=False)}")
    print(f"[save] linkData keys: {list(save_lk.keys())}")

    save_url = f"{BASE_API}/icpsp-api/v4/pc/register/establish/component/ComplementInfo/operationBusinessDataInfo"
    print(f"[save] 调用 save...")
    sr = js_fetch(ws, save_url, save_body, mid=mid); mid += 1
    sb = sr.get("body", "")
    try:
        sd = json.loads(sb)
        code = sd.get("code")
        msg  = sd.get("msg","")
        dat  = sd.get("data", {})
        rt   = dat.get("resultType")
        rmsg = dat.get("msg","")
        print(f"\n  code={code} msg={msg}")
        print(f"  resultType={rt} msg={rmsg}")
        if code == "00000" and str(rt) == "0":
            print("  ✅ 保存成功!")
        elif rt == "1":
            print(f"  ⚠ 校验失败: {rmsg}")
        else:
            print(f"  ❌ 其他: {json.dumps(dat, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  解析失败: {e}, raw: {sb[:300]}")

    # 保存请求体到文件
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(save_body, f, ensure_ascii=False, indent=2)
    print(f"\n[body] 已保存到: {OUT}")

if __name__ == "__main__":
    main()
