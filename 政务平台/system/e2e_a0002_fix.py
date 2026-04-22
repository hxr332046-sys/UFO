#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A0002修复：拦截XHR.send()，解码busiAreaData和genBusiArea后重发"""
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

FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"

# ============================================================
# Step 1: 安装XHR拦截修复器
# ============================================================
print("Step 1: 安装XHR修复拦截器")
ev("""(function(){
    window.__fix_result = null;
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
                // 修复1: busiAreaData - 从URL编码字符串解码为JSON对象
                if (typeof bobj.busiAreaData === 'string' && bobj.busiAreaData.startsWith('%')) {
                    var decoded = decodeURIComponent(bobj.busiAreaData);
                    try {
                        bobj.busiAreaData = JSON.parse(decoded);
                    } catch(e) {
                        bobj.busiAreaData = decoded;
                    }
                }
                // 修复2: genBusiArea - 从URL编码字符串解码为纯文本
                if (typeof bobj.genBusiArea === 'string' && bobj.genBusiArea.startsWith('%')) {
                    var decodedGen = decodeURIComponent(bobj.genBusiArea);
                    // 去除多余引号
                    if (decodedGen.startsWith('"') && decodedGen.endsWith('"')) {
                        decodedGen = decodedGen.substring(1, decodedGen.length - 1);
                    }
                    bobj.genBusiArea = decodedGen;
                }
                // 修复3: busiAreaName - 如果也被编码了
                if (typeof bobj.busiAreaName === 'string' && bobj.busiAreaName.startsWith('%')) {
                    bobj.busiAreaName = decodeURIComponent(bobj.busiAreaName);
                }
                body = JSON.stringify(bobj);
                window.__fix_result = {
                    fixed: true,
                    busiAreaDataType: typeof bobj.busiAreaData,
                    busiAreaDataIsArray: Array.isArray(bobj.busiAreaData),
                    genBusiArea: bobj.genBusiArea,
                    busiAreaName: bobj.busiAreaName
                };
            } catch(e) {
                window.__fix_result = {error: e.message};
            }
            var self = this;
            self.addEventListener('load', function() {
                window.__fix_resp = {status: self.status, text: self.responseText || ''};
            });
        }
        return origSend.apply(this, [body]);
    };
    return 'fix_installed';
})()""")
print("  ✅ 修复拦截器已安装")

# ============================================================
# Step 2: 点击保存并下一步
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
print(f"  点击: {click}")
time.sleep(12)

# ============================================================
# Step 3: 分析修复结果
# ============================================================
print("\nStep 3: 分析修复结果")
fix_result = ev("window.__fix_result")
print(f"  修复结果: {json.dumps(fix_result, ensure_ascii=False) if isinstance(fix_result,dict) else fix_result}")

fix_resp = ev("window.__fix_resp")
if isinstance(fix_resp, dict):
    text = fix_resp.get('text','')
    print(f"  API status: {fix_resp.get('status')}")
    if text:
        try:
            p = json.loads(text)
            code = p.get('code','')
            msg = p.get('msg','')[:100]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！A0002已修复！✅✅✅")
            else:
                print("  ❌ 仍有错误")
                # 保存响应分析
                with open(r'g:\UFO\政务平台\data\fix_resp.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
                # 检查是否还有其他字段问题
                data = p.get('data',{})
                if isinstance(data, dict):
                    print(f"  data keys: {list(data.keys())[:10]}")
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {fix_resp}")

# ============================================================
# Step 4: 如果仍失败，检查是否还有其他编码字段
# ============================================================
if isinstance(fix_resp, dict):
    text = fix_resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            if str(p.get('code','')) not in ['0','0000','200']:
                print("\nStep 4: 深度分析")
                # 重新拦截，这次记录完整修复后的body
                ev("""(function(){
                    window.__debug_body = null;
                    var origSend = XMLHttpRequest.prototype.send;
                    var origOpen = XMLHttpRequest.prototype.open;
                    XMLHttpRequest.prototype.open = function(m, u) {this.__url = u;return origOpen.apply(this, arguments)};
                    XMLHttpRequest.prototype.send = function(body) {
                        var url = this.__url || '';
                        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
                            window.__debug_body = body;
                            var bobj = JSON.parse(body);
                            // 修复
                            if (typeof bobj.busiAreaData === 'string' && bobj.busiAreaData.startsWith('%')) {
                                bobj.busiAreaData = JSON.parse(decodeURIComponent(bobj.busiAreaData));
                            }
                            if (typeof bobj.genBusiArea === 'string' && bobj.genBusiArea.startsWith('%')) {
                                var g = decodeURIComponent(bobj.genBusiArea);
                                if (g.startsWith('"') && g.endsWith('"')) g = g.substring(1, g.length-1);
                                bobj.genBusiArea = g;
                            }
                            if (typeof bobj.busiAreaName === 'string' && bobj.busiAreaName.startsWith('%')) {
                                bobj.busiAreaName = decodeURIComponent(bobj.busiAreaName);
                            }
                            // 检查所有字段是否有URL编码问题
                            var badFields = [];
                            Object.keys(bobj).forEach(function(k) {
                                var v = bobj[k];
                                if (typeof v === 'string' && v.startsWith('%')) {
                                    badFields.push(k + ':' + v.substring(0, 30));
                                }
                            });
                            window.__bad_fields = badFields;
                            body = JSON.stringify(bobj);
                            var self = this;
                            self.addEventListener('load', function() {
                                window.__fix_resp2 = {status: self.status, text: self.responseText || ''};
                            });
                            return origSend.apply(this, [body]);
                        }
                        return origSend.apply(this, arguments);
                    };
                })()""")
                
                click2 = ev("""(function(){
                    var all=document.querySelectorAll('button,.el-button');
                    for(var i=0;i<all.length;i++){
                        var t=all[i].textContent?.trim()||'';
                        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
                            all[i].click();return{clicked:t};
                        }
                    }
                    return 'no_btn';
                })()""")
                print(f"  点击: {click2}")
                time.sleep(12)
                
                bad_fields = ev("window.__bad_fields")
                print(f"  URL编码字段: {bad_fields}")
                
                fix_resp2 = ev("window.__fix_resp2")
                if isinstance(fix_resp2, dict):
                    text2 = fix_resp2.get('text','')
                    if text2:
                        try:
                            p2 = json.loads(text2)
                            print(f"  code={p2.get('code','')} msg={str(p2.get('msg',''))[:80]}")
                            with open(r'g:\UFO\政务平台\data\fix_resp2.json', 'w', encoding='utf-8') as f:
                                json.dump(p2, f, ensure_ascii=False, indent=2)
                        except:
                            print(f"  raw: {text2[:200]}")

print("\nDONE")
