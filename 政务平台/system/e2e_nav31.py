#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到flow/base/basic-info表单 → 验证表单加载"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 检查当前状态
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# 查找basic-info路由
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');
    var basic=all.filter(function(r){return r.includes('basic-info')});
    var flowBase=all.filter(function(r){return r.match(/\\/flow\\/base\\/[^/]+$/)});
    return{total:all.length,basic:basic,flowBaseSample:flowBase.slice(0,10)};
})()""")
print(f"  basic-info routes: {routes.get('basic',[])}")
print(f"  flow/base sample: {routes.get('flowBaseSample',[])}")

# 导航到basic-info
if routes.get('basic'):
    for route in routes.get('basic',[]):
        print(f"\n导航: {route}")
        ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
        time.sleep(5)
        
        fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,text:(document.body?.innerText||'').substring(0,100)})")
        print(f"  hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")
        print(f"  text={fc.get('text','')[:60] if fc else ''}")
        
        if fc and fc.get('formCount',0) > 10:
            print("✅ 表单已加载！")
            
            # 列出表单字段
            fields = ev("""(function(){
                var items=document.querySelectorAll('.el-form-item');
                var r=[];
                for(var i=0;i<Math.min(items.length,40);i++){
                    var label=items[i].querySelector('.el-form-item__label');
                    var input=items[i].querySelector('input,select,textarea');
                    var type=input?input.tagName+(input.type?'('+input.type+')':''):'none';
                    r.push({idx:i,label:label?.textContent?.trim()?.substring(0,30)||'',type:type});
                }
                return r;
            })()""")
            print(f"\n  表单字段 ({len(fields)}个):")
            for f in (fields or []):
                print(f"    {f.get('idx')}: {f.get('label','')} [{f.get('type','')}]")
            break
        else:
            # 可能需要先点击下一步
            print("  表单未加载，尝试点击下一步...")
            for btn_text in ['下一步','确定','同意','我已阅读','继续']:
                cr = ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){{if(btns[i].textContent?.trim()?.includes('{btn_text}')&&btns[i].offsetParent!==null&&!btns[i].disabled){{btns[i].click();return{{clicked:true}}}}}}return{{clicked:false}}}})()""")
                if cr and cr.get('clicked'):
                    print(f"  点击: {btn_text}")
                    time.sleep(3)
                    break
            
            fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
            if fc2 and fc2.get('formCount',0) > 10:
                print(f"  ✅ 表单加载！forms={fc2.get('formCount',0)}")
                break
else:
    # 没有basic-info路由，尝试其他路径
    print("\n没有basic-info路由，尝试flow/base/aaa或其他")
    # 先看当前页面内容
    text = ev("(document.body?.innerText||'').substring(0,200)")
    print(f"  text: {text[:100]}")
    
    # 尝试导航到flow/base
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base')})()""")
    time.sleep(3)
    fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
    print(f"  /flow/base: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

ws.close()
print("✅ 完成")
