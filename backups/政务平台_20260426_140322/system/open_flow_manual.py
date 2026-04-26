from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

import websocket


def _first_page_tab(port: int) -> dict:
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5))
    for tab in tabs:
        if tab.get("type") == "page":
            return tab
    raise RuntimeError("no page tab found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--busi-id", required=True)
    ap.add_argument("--name-id", required=True)
    ap.add_argument("--ent-type", default="4540")
    ap.add_argument("--busi-type", default="02_4")
    ap.add_argument("--ent-name", default="")
    ap.add_argument("--port", type=int, default=9225)
    args = ap.parse_args()

    tab = _first_page_tab(args.port)
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
    cid = 0

    def send(method: str, params: dict | None = None) -> int:
        nonlocal cid
        cid += 1
        msg = {"id": cid, "method": method}
        if params is not None:
            msg["params"] = params
        ws.send(json.dumps(msg))
        return cid

    def ev(expr: str, timeout: int = 8):
        target = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        ws.settimeout(timeout)
        end = time.time() + timeout
        while time.time() < end:
            resp = json.loads(ws.recv())
            if resp.get("id") == target:
                return (((resp.get("result") or {}).get("result") or {}).get("value"))
        return None

    ent_name = urllib.parse.quote(args.ent_name)
    url = (
        "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base"
        f"?fromProject=portal&busiId={args.busi_id}&busiType={args.busi_type}"
        f"&entType={args.ent_type}&nameId={args.name_id}&entName={ent_name}"
    )
    print("NAV", url)
    send("Page.enable")
    send("Page.navigate", {"url": url})
    time.sleep(12)

    print("href=", ev("location.href"))
    print("title=", ev("document.title"))
    body = ev("document.body && document.body.innerText && document.body.innerText.slice(0,1200)", 5) or ""
    print("body=", body[:1200])
    flow = ev(r"""
(function(){
  var app = document.querySelector('#app');
  if (!app || !app.__vue__) return 'no_vue';
  var q = [app.__vue__];
  var seen = new Set();
  while (q.length) {
    var v = q.shift();
    if (!v || seen.has(v._uid)) continue;
    seen.add(v._uid);
    if (v.$options && v.$options.name === 'flow-control') {
      window.__fc = v;
      var fd = (v.$data.params && v.$data.params.flowData) || v.$data.flowData || {};
      return JSON.stringify({
        curCompUrl: v.$data.curCompUrl,
        curStep: v.$data.curStep,
        curCompName: v.$data.curCompName,
        busiId: fd.busiId,
        status: fd.status,
        currCompUrl: fd.currCompUrl
      });
    }
    if (v.$children) for (var i = 0; i < v.$children.length; i++) q.push(v.$children[i]);
  }
  return 'no_flow_control';
})()
""", 8)
    print("flow=", flow)
    ws.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
