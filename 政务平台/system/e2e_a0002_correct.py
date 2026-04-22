#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002正确修复：busiAreaData保留{firstPlace,param}对象+firstPlace改license"""
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
# Step 1: 安装正确修复拦截器
# ============================================================
print("Step 1: correct fix interceptor")
ev("""(function(){
    window.__cfix_info = null;
    window.__cfix_resp = null;
    window.__cfix_body = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {
        this.__url = u;
        return origOpen.apply(this, arguments);
    };

    function deepFix(v) {
        if (typeof v !== 'string') return v;
        // URL解码
        if (v.indexOf('%') === 0) {
            try { v = decodeURIComponent(v); } catch(e) {}
        }
        // JSON.parse
        try {
            var parsed = JSON.parse(v);
            if (typeof parsed === 'object') return parsed;
            if (typeof parsed === 'string') return parsed;
            return parsed;
        } catch(e) {
            if (v.charAt(0) === '"' && v.charAt(v.length - 1) === '"') {
                return v.substring(1, v.length - 1);
            }
            return v;
        }
    }

    function fixObjStrings(obj) {
        if (!obj || typeof obj !== 'object') return;
        Object.keys(obj).forEach(function(k) {
            var v = obj[k];
            if (typeof v === 'string' && (v.indexOf('%') === 0 || v.charAt(0) === '{' || v.charAt(0) === '[' || (v.charAt(0) === '"' && v.length > 2))) {
                obj[k] = deepFix(v);
            } else if (typeof v === 'object' && v !== null) {
                fixObjStrings(v);
            }
        });
    }

    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            try {
                var bobj = JSON.parse(body);

                // 修复所有URL编码/stringified字段
                fixObjStrings(bobj);
                if (bobj.linkData) fixObjStrings(bobj.linkData);

                // busiAreaData: 保留{firstPlace,param}对象，不提取param
                // 但修改firstPlace从"general"到"license"
                if (bobj.busiAreaData && typeof bobj.busiAreaData === 'object' && !Array.isArray(bobj.busiAreaData)) {
                    if (bobj.busiAreaData.firstPlace === 'general') {
                        bobj.busiAreaData.firstPlace = 'license';
                    }
                }

                // vipChannel: "null" -> null
                if (bobj.flowData && bobj.flowData.vipChannel === 'null') {
                    bobj.flowData.vipChannel = null;
                }

                body = JSON.stringify(bobj);
                window.__cfix_body = body;
                window.__cfix_info = {
                    busiAreaDataType: typeof bobj.busiAreaData,
                    busiAreaDataIsArray: Array.isArray(bobj.busiAreaData),
                    busiAreaDataFirstPlace: bobj.busiAreaData ? bobj.busiAreaData.firstPlace : 'N/A',
                    busiAreaDataParamLen: (bobj.busiAreaData && bobj.busiAreaData.param) ? bobj.busiAreaData.param.length : 'N/A',
                    genBusiArea: bobj.genBusiArea,
                    vipChannel: bobj.flowData ? bobj.flowData.vipChannel : 'N/A'
                };
            } catch(e) {
                window.__cfix_info = {error: e.message};
            }
            var self = this;
            self.addEventListener('load', function() {
                window.__cfix_resp = {status: self.status, text: self.responseText || ''};
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
info = ev("window.__cfix_info")
print(f"  info: {json.dumps(info, ensure_ascii=False)[:300] if isinstance(info, dict) else info}")

resp = ev("window.__cfix_resp")
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
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  no resp: {resp}")

# ============================================================
# Step 4: 保存修复后的body用于对比分析
# ============================================================
print("\nStep 4: save fixed body")
body = ev("window.__cfix_body")
if isinstance(body, str):
    try:
        bobj = json.loads(body)
        with open(r'g:\UFO\政务平台\data\corrected_body.json', 'w', encoding='utf-8') as f:
            json.dump(bobj, f, ensure_ascii=False, indent=2)
        # 检查所有null/空字段
        nulls = []
        for k, v in bobj.items():
            if v is None or v == '' or v == 'null':
                nulls.append(k)
        print(f"  saved ({len(bobj)} keys), null/empty fields: {nulls[:20]}")
    except:
        print(f"  parse error")

print("\nDONE")
