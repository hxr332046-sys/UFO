#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002全面修复：解码所有URL编码字段+busiAreaData提取param"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type") == "page" and "core.html" in p.get("url", "")]
        if not page:
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "")]
        if not page:
            return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
        ws.settimeout(timeout + 2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 安装全面修复拦截器
# ============================================================
print("Step 1: install fix interceptor")
ev("""(function(){
    window.__fix_info = null;
    window.__fix_resp = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {
        this.__url = u;
        return origOpen.apply(this, arguments);
    };

    function fixValue(v) {
        if (typeof v !== 'string' || v.indexOf('%') !== 0) return v;
        try {
            var decoded = decodeURIComponent(v);
            try {
                return JSON.parse(decoded);
            } catch(e) {
                if (decoded.charAt(0) === '"' && decoded.charAt(decoded.length - 1) === '"') {
                    decoded = decoded.substring(1, decoded.length - 1);
                }
                return decoded;
            }
        } catch(e2) {
            return v;
        }
    }

    function fixObj(obj, prefix) {
        if (!obj || typeof obj !== 'object') return;
        Object.keys(obj).forEach(function(k) {
            if (typeof obj[k] === 'string' && obj[k].indexOf('%') === 0) {
                obj[k] = fixValue(obj[k]);
            }
        });
    }

    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            try {
                var bobj = JSON.parse(body);
                var fixes = [];

                // fix top-level
                Object.keys(bobj).forEach(function(k) {
                    if (typeof bobj[k] === 'string' && bobj[k].indexOf('%') === 0) {
                        var oldType = typeof bobj[k];
                        bobj[k] = fixValue(bobj[k]);
                        fixes.push(k + ':' + oldType + '->' + typeof bobj[k]);
                    }
                });

                // fix linkData
                if (bobj.linkData && typeof bobj.linkData === 'object') {
                    Object.keys(bobj.linkData).forEach(function(k) {
                        if (typeof bobj.linkData[k] === 'string' && bobj.linkData[k].indexOf('%') === 0) {
                            bobj.linkData[k] = fixValue(bobj.linkData[k]);
                            fixes.push('linkData.' + k);
                        }
                    });
                }

                // busiAreaData: extract param array from {firstPlace,param} object
                if (bobj.busiAreaData && typeof bobj.busiAreaData === 'object'
                    && !Array.isArray(bobj.busiAreaData) && bobj.busiAreaData.param) {
                    bobj.busiAreaData = bobj.busiAreaData.param;
                    fixes.push('busiAreaData:extracted_param');
                }

                // vipChannel: "null" -> null
                if (bobj.flowData && bobj.flowData.vipChannel === 'null') {
                    bobj.flowData.vipChannel = null;
                    fixes.push('flowData.vipChannel:"null"->null');
                }

                body = JSON.stringify(bobj);
                window.__fix_info = {
                    fixes: fixes,
                    busiAreaDataIsArray: Array.isArray(bobj.busiAreaData),
                    busiAreaDataLen: Array.isArray(bobj.busiAreaData) ? bobj.busiAreaData.length : 'N/A',
                    genBusiArea: bobj.genBusiArea
                };
            } catch(e) {
                window.__fix_info = {error: e.message};
            }
            var self = this;
            self.addEventListener('load', function() {
                window.__fix_resp = {status: self.status, text: self.responseText || ''};
            });
            return origSend.apply(this, [body]);
        }
        return origSend.apply(this, arguments);
    };
    return 'installed';
})()""")
print("  done")

# ============================================================
# Step 2: save
# ============================================================
print("\nStep 2: save")
click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
            all[i].click();return{clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  click: {click}")
time.sleep(12)

# ============================================================
# Step 3: analyze
# ============================================================
print("\nStep 3: analyze")
info = ev("window.__fix_info")
print(f"  fix: {json.dumps(info, ensure_ascii=False)[:300] if isinstance(info, dict) else info}")

resp = ev("window.__fix_resp")
if isinstance(resp, dict):
    text = resp.get('text', '')
    print(f"  status: {resp.get('status')}")
    if text:
        try:
            p = json.loads(text)
            code = p.get('code', '')
            msg = str(p.get('msg', ''))[:100]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0', '0000', '200']:
                print("  >>> SUCCESS <<<")
            else:
                print("  >>> STILL ERROR <<<")
                with open(r'g:\UFO\政务平台\data\fix_resp3.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  no resp: {resp}")

print("\nDONE")
