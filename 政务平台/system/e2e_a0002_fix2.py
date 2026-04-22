#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002修复：拦截XHR.send()，解码busiAreaData和genBusiArea"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "core.html" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# ============================================================
# Step 1: 安装XHR修复拦截器
# ============================================================
print("Step 1: 安装修复拦截器")
ev("""(function(){
    window.__fix_result = null;
    window.__fix_resp = null;
    window.__bad_fields = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {
        this.__url = u;
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            try {
                var bobj = JSON.parse(body);
                var badFields = [];
                // 修复所有URL编码字段
                Object.keys(bobj).forEach(function(k) {
                    var v = bobj[k];
                    if (typeof v === 'string' && v.indexOf('%') === 0) {
                        badFields.push(k);
                        var decoded = decodeURIComponent(v);
                        // 尝试JSON.parse
                        try {
                            bobj[k] = JSON.parse(decoded);
                        } catch(e) {
                            // 去除多余引号
                            if (decoded.charAt(0) === '"' && decoded.charAt(decoded.length-1) === '"') {
                                decoded = decoded.substring(1, decoded.length-1);
                            }
                            bobj[k] = decoded;
                        }
                    }
                });
                window.__bad_fields = badFields;
                body = JSON.stringify(bobj);
                window.__fix_result = {
                    fixed: true,
                    badFields: badFields,
                    busiAreaDataType: typeof bobj.busiAreaData,
                    busiAreaDataIsArray: Array.isArray(bobj.busiAreaData),
                    genBusiArea: bobj.genBusiArea
                };
            } catch(e) {
                window.__fix_result = {error: e.message};
            }
            var self = this;
            self.addEventListener('load', function() {
                window.__fix_resp = {status: self.status, text: self.responseText || ''};
            });
            return origSend.apply(this, [body]);
        }
        return origSend.apply(this, arguments);
    };
    return 'fix_installed';
})()""")
print("  done")

# ============================================================
# Step 2: 保存并下一步
# ============================================================
print("\nStep 2: 保存并下一步")
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
# Step 3: 分析结果
# ============================================================
print("\nStep 3: 分析")
fix_result = ev("window.__fix_result")
print(f"  fix: {fix_result}")

fix_resp = ev("window.__fix_resp")
bad_fields = ev("window.__bad_fields")
print(f"  bad_fields: {bad_fields}")

if isinstance(fix_resp, dict):
    text = fix_resp.get('text', '')
    print(f"  status: {fix_resp.get('status')}")
    if text:
        try:
            p = json.loads(text)
            code = p.get('code', '')
            msg = str(p.get('msg', ''))[:100]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0', '0000', '200']:
                print("  >>> SUCCESS! A0002 FIXED! <<<")
            else:
                print("  >>> STILL ERROR <<<")
                with open(r'g:\UFO\政务平台\data\fix_resp.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  no resp: {fix_resp}")

print("\nDONE")
