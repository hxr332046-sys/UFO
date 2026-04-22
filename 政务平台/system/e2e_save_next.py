#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""点击保存并下一步按钮，捕获请求"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
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
# Step 1: 拦截请求
# ============================================================
print("Step 1: 拦截请求")
ev("""(function(){
    window.__save_req=null;
    window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__save_req={url:url,body:body||'',bodyLen:(body||'').length};
            var self=this;
            self.addEventListener('load',function(){
                window.__save_resp={status:self.status,text:self.responseText||''};
            });
        }
        return origSend.apply(this,arguments);
    };
})()""")

# ============================================================
# Step 2: 点击"保存并下一步"
# ============================================================
print("\nStep 2: 点击保存并下一步")
ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('保存并下一步')){
            all[i].click();
            return {clicked:t};
        }
    }
    return 'no_btn';
})()""")
time.sleep(8)

# ============================================================
# Step 3: 检查请求和响应
# ============================================================
print("\nStep 3: 请求分析")
req = ev("window.__save_req")
resp = ev("window.__save_resp")

if isinstance(req, dict):
    body = req.get('body','')
    print(f"  URL: {req.get('url','')[:80]}")
    print(f"  body长度: {req.get('bodyLen',0)}")
    if body:
        try:
            bobj = json.loads(body)
            ba = bobj.get('busiAreaData')
            if ba is None:
                print("  ⚠️ busiAreaData: null/missing")
            elif isinstance(ba, str):
                print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                try:
                    d = json.loads(ba)
                    print(f"    → parsed: {type(d).__name__}")
                except:
                    print(f"    → first100: {ba[:100]}")
            elif isinstance(ba, (list, dict)):
                typ = 'ARRAY' if isinstance(ba,list) else 'OBJECT'
                print(f"  ✅ busiAreaData: {typ}")
                if isinstance(ba, dict) and 'param' in ba:
                    print(f"    firstPlace={ba.get('firstPlace')}, param.len={len(ba.get('param',[]))}")
                elif isinstance(ba, list) and ba:
                    print(f"    len={len(ba)}, first: {json.dumps(ba[0], ensure_ascii=False)[:80]}")
            
            gba = bobj.get('genBusiArea','')
            print(f"  genBusiArea: {str(gba)[:50]}")
            print(f"  operatorNum: {bobj.get('operatorNum')}")
            print(f"  distCode: {bobj.get('distCode')}")
            
            with open(r'g:\UFO\政务平台\data\save_body_next.json', 'w', encoding='utf-8') as f:
                json.dump(bobj, f, ensure_ascii=False, indent=2)
            print(f"  已保存 ({len(bobj)} keys)")
        except Exception as e:
            print(f"  parse error: {e}")
else:
    print(f"  无请求: {req}")

if isinstance(resp, dict):
    print(f"\n  API status={resp.get('status')}")
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            code = p.get('code','')
            msg = p.get('msg','')[:80]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
            else:
                d = p.get('data')
                if d: print(f"  data: {json.dumps(d, ensure_ascii=False)[:200]}")
        except:
            print(f"  raw: {text[:200]}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

hash_val = ev("location.hash")
print(f"  路由: {hash_val}")

print("\n✅ 完成")
