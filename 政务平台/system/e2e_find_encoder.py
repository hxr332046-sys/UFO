#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找到operationBusinessDataInfo函数中的encodeURIComponent调用并patch"""
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

FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"

# ============================================================
# Step 1: 找operationBusinessDataInfo方法
# ============================================================
print("Step 1: find operationBusinessDataInfo")
src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.operationBusinessDataInfo||fc.$options?.methods?.operationBusinessDataInfo;
    if(!fn)return'no_fn';
    var s=fn.toString();
    return {{len:s.length,src:s.substring(0,1500)}};
}})()""", timeout=15)
if isinstance(src, dict):
    print(f"  len={src.get('len',0)}")
    s = src.get('src', '')
    # 找encodeURIComponent
    idx = s.find('encodeURIComponent')
    if idx >= 0:
        print(f"  === encodeURIComponent at pos {idx} ===")
        print(f"  {s[max(0,idx-100):idx+200]}")
    else:
        print(f"  no encodeURIComponent in first 1500 chars")
        # 搜索更多
        print(f"  src start: {s[:300]}")
else:
    print(f"  {src}")

# ============================================================
# Step 2: 获取完整源码并搜索encodeURIComponent
# ============================================================
print("\nStep 2: full source search")
full_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.operationBusinessDataInfo||fc.$options?.methods?.operationBusinessDataInfo;
    if(!fn)return'no_fn';
    var s=fn.toString();
    // 找所有encodeURIComponent
    var positions=[];
    var idx=0;
    while(true){{
        idx=s.indexOf('encodeURIComponent',idx);
        if(idx<0)break;
        positions.push({{pos:idx,context:s.substring(Math.max(0,idx-60),idx+80)}});
        idx+=10;
    }}
    return {{totalLen:s.length,encCount:positions.length,positions:positions}};
}})()""", timeout=15)
if isinstance(full_src, dict):
    print(f"  totalLen={full_src.get('totalLen',0)} encCount={full_src.get('encCount',0)}")
    for p in full_src.get('positions', []):
        print(f"  pos {p.get('pos')}: ...{p.get('context','')}...")
else:
    print(f"  {full_src}")

# ============================================================
# Step 3: 保存完整源码
# ============================================================
print("\nStep 3: save full source")
saved = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.operationBusinessDataInfo||fc.$options?.methods?.operationBusinessDataInfo;
    if(!fn)return'no_fn';
    return fn.toString();
}})()""", timeout=15)
if isinstance(saved, str) and len(saved) > 50:
    with open(r'g:\UFO\政务平台\data\operationBusinessDataInfo_src.js', 'w', encoding='utf-8') as f:
        f.write(saved)
    print(f"  saved {len(saved)} chars")

# ============================================================
# Step 4: Patch operationBusinessDataInfo - 去掉encodeURIComponent
# ============================================================
print("\nStep 4: patch operationBusinessDataInfo")
patch_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var fn=fc.operationBusinessDataInfo||fc.$options?.methods?.operationBusinessDataInfo;
    if(!fn)return'no_fn';
    var src=fn.toString();

    // 检查是否已被patch
    if(src.includes('__orig_enc'))return {{alreadyPatched:true}};

    // 保存原始encodeURIComponent
    if(!window.__orig_enc)window.__orig_enc=encodeURIComponent;

    // 替换全局encodeURIComponent为identity函数
    window.encodeURIComponent=function(s){{return s}};

    return {{patched:true,origSaved:true}};
}})()""")
print(f"  {patch_result}")

# ============================================================
# Step 5: 保存并下一步
# ============================================================
print("\nStep 5: save")
# 安装响应拦截
ev("""(function(){
    window.__save_resp = null;
    window.__save_body = null;
    var origSend = XMLHttpRequest.prototype.send;
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u) {this.__url = u;return origOpen.apply(this, arguments)};
    XMLHttpRequest.prototype.send = function(body) {
        var url = this.__url || '';
        if (url.includes('operationBusinessData') || url.includes('BasicInfo')) {
            window.__save_body = body;
            var self = this;
            self.addEventListener('load', function() {
                window.__save_resp = {status: self.status, text: self.responseText || ''};
            });
        }
        return origSend.apply(this, arguments);
    };
})()""")

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
# Step 6: 分析
# ============================================================
print("\nStep 6: analyze")
body = ev("window.__save_body")
resp = ev("window.__save_resp")

if isinstance(body, str):
    try:
        bobj = json.loads(body)
        ba = bobj.get('busiAreaData')
        gba = bobj.get('genBusiArea')
        print(f"  busiAreaData: {type(ba).__name__}, isArray={isinstance(ba,list)}")
        if isinstance(ba, str):
            print(f"    STILL STRING: {ba[:60]}")
        elif isinstance(ba, list):
            print(f"    ARRAY len={len(ba)}")
        elif isinstance(ba, dict):
            print(f"    OBJECT keys={list(ba.keys())[:5]}")
        print(f"  genBusiArea: {type(gba).__name__} = {str(gba)[:50]}")

        with open(r'g:\UFO\政务平台\data\patched_body.json', 'w', encoding='utf-8') as f:
            json.dump(bobj, f, ensure_ascii=False, indent=2)
        print(f"  saved ({len(bobj)} keys)")
    except:
        print(f"  non-JSON: {body[:200]}")

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

# 恢复encodeURIComponent
ev("if(window.__orig_enc)window.encodeURIComponent=window.__orig_enc")
print("\nDONE")
