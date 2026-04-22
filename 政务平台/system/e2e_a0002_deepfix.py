#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002深度修复：XHR拦截器将stringified字段parse回JSON对象"""
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
# Step 1: 安装深度修复拦截器
# ============================================================
print("Step 1: deep fix interceptor")
ev("""(function(){
    window.__deepfix_info = null;
    window.__deepfix_resp = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {
        this.__url = u;
        return origOpen.apply(this, arguments);
    };

    function deepFixValue(v) {
        if (typeof v !== 'string') return v;
        // URL编码？
        if (v.indexOf('%') === 0) {
            try { v = decodeURIComponent(v); } catch(e) {}
        }
        // 尝试JSON.parse
        try {
            var parsed = JSON.parse(v);
            // 如果是对象或数组，返回解析后的
            if (typeof parsed === 'object') return parsed;
            // 如果是纯字符串（带引号），去引号
            if (typeof parsed === 'string') return parsed;
            return parsed;
        } catch(e) {
            // 不是JSON，检查是否带引号
            if (v.charAt(0) === '"' && v.charAt(v.length - 1) === '"') {
                return v.substring(1, v.length - 1);
            }
            return v;
        }
    }

    function fixAllStrings(obj, path) {
        if (!obj || typeof obj !== 'object') return;
        Object.keys(obj).forEach(function(k) {
            var v = obj[k];
            if (typeof v === 'string') {
                // 检查是否需要修复
                if (v.indexOf('%') === 0 || v.charAt(0) === '{' || v.charAt(0) === '[' || (v.charAt(0) === '"' && v.length > 2)) {
                    var fixed = deepFixValue(v);
                    if (fixed !== v) {
                        obj[k] = fixed;
                    }
                }
            } else if (typeof v === 'object' && v !== null) {
                fixAllStrings(v, path + '.' + k);
            }
        });
    }

    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            try {
                var bobj = JSON.parse(body);
                var fixes = [];

                // 修复前记录
                var beforeBad = {};
                Object.keys(bobj).forEach(function(k) {
                    var v = bobj[k];
                    if (typeof v === 'string' && (v.indexOf('%') === 0 || v.charAt(0) === '{' || v.charAt(0) === '[')) {
                        beforeBad[k] = v.substring(0, 40);
                    }
                });

                // 深度修复
                fixAllStrings(bobj, '');

                // 修复linkData
                if (bobj.linkData) fixAllStrings(bobj.linkData, 'linkData');

                // busiAreaData特殊处理：如果是{firstPlace,param}对象，提取param数组
                if (bobj.busiAreaData && typeof bobj.busiAreaData === 'object'
                    && !Array.isArray(bobj.busiAreaData) && bobj.busiAreaData.param) {
                    bobj.busiAreaData = bobj.busiAreaData.param;
                    fixes.push('busiAreaData:extracted_param');
                }

                // vipChannel: "null" -> null
                if (bobj.flowData && bobj.flowData.vipChannel === 'null') {
                    bobj.flowData.vipChannel = null;
                }

                body = JSON.stringify(bobj);

                // 修复后记录
                var afterBad = {};
                Object.keys(bobj).forEach(function(k) {
                    var v = bobj[k];
                    if (typeof v === 'string' && (v.indexOf('%') === 0 || v.charAt(0) === '{' || v.charAt(0) === '[')) {
                        afterBad[k] = v.substring(0, 40);
                    }
                });

                window.__deepfix_info = {
                    beforeBad: beforeBad,
                    afterBad: afterBad,
                    busiAreaDataType: typeof bobj.busiAreaData,
                    busiAreaDataIsArray: Array.isArray(bobj.busiAreaData),
                    busiAreaDataLen: Array.isArray(bobj.busiAreaData) ? bobj.busiAreaData.length : 'N/A',
                    genBusiArea: bobj.genBusiArea
                };
            } catch(e) {
                window.__deepfix_info = {error: e.message};
            }
            var self = this;
            self.addEventListener('load', function() {
                window.__deepfix_resp = {status: self.status, text: self.responseText || ''};
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
info = ev("window.__deepfix_info")
print(f"  info: {json.dumps(info, ensure_ascii=False)[:500] if isinstance(info, dict) else info}")

resp = ev("window.__deepfix_resp")
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
                with open(r'g:\UFO\政务平台\data\deepfix_resp.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  no resp: {resp}")

print("\nDONE")
