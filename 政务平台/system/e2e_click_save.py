#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""点击保存按钮，捕获完整请求"""
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

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
# Step 2: 先点"更多"看有没有暂存
# ============================================================
print("\nStep 2: 点更多按钮")
ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t==='更多'){
            all[i].click();
            return 'clicked_more';
        }
    }
    return 'no_more_btn';
})()""")
time.sleep(1)

# 查看更多菜单
menu_items = ev("""(function(){
    var menus=document.querySelectorAll('.el-dropdown-menu li,.el-menu li,.el-dropdown__menu li');
    var r=[];
    for(var i=0;i<menus.length;i++){
        var t=menus[i].textContent?.trim()||'';
        if(t)r.push(t);
    }
    return r;
})()""")
print(f"  更多菜单: {menu_items}")

# 如果有暂存就点
if menu_items and isinstance(menu_items, list):
    for item in menu_items:
        if '暂存' in item or '保存草稿' in item:
            ev(f"""(function(){{
                var menus=document.querySelectorAll('.el-dropdown-menu li,.el-menu li,.el-dropdown__menu li');
                for(var i=0;i<menus.length;i++){{
                    var t=menus[i].textContent?.trim()||'';
                    if(t.includes('暂存')||t.includes('保存草稿')){{
                        menus[i].click();
                        return 'clicked_'+t;
                    }}
                }}
            }})()""")
            time.sleep(5)
            break
else:
    # 没有暂存，直接用flow-control.save()
    print("  无暂存菜单，用fc.save()")
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
    }})()""", timeout=15)
    time.sleep(5)

# ============================================================
# Step 3: 检查请求
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
            # 关键字段检查
            ba = bobj.get('busiAreaData')
            if ba is None:
                print("  ⚠️ busiAreaData: null/missing")
            elif isinstance(ba, str):
                print(f"  ⚠️ busiAreaData: STRING len={len(ba)}")
                try:
                    d = json.loads(ba)
                    print(f"    → parsed: {type(d).__name__}, keys={list(d.keys()) if isinstance(d,dict) else 'array'}")
                except:
                    print(f"    → cannot parse, first100: {ba[:100]}")
            elif isinstance(ba, (list, dict)):
                typ = 'ARRAY' if isinstance(ba,list) else 'OBJECT'
                print(f"  ✅ busiAreaData: {typ}")
                if isinstance(ba, dict):
                    print(f"    keys: {list(ba.keys())}")
                    if 'param' in ba:
                        print(f"    param.len={len(ba['param'])}")
                elif isinstance(ba, list):
                    print(f"    len={len(ba)}")
                    if ba:
                        print(f"    first: {json.dumps(ba[0], ensure_ascii=False)[:100]}")
            
            gba = bobj.get('genBusiArea','')
            if isinstance(gba, str) and '%' in gba:
                print(f"  ⚠️ genBusiArea: URL-encoded: {gba[:60]}")
            else:
                print(f"  genBusiArea: {str(gba)[:40]}")
            
            print(f"  operatorNum: {bobj.get('operatorNum')}")
            print(f"  distCode: {bobj.get('distCode')}")
            print(f"  businessAddress: {bobj.get('businessAddress','')[:30]}")
            
            # 保存
            with open(r'g:\UFO\政务平台\data\save_body_latest.json', 'w', encoding='utf-8') as f:
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
            msg = p.get('msg','')[:60]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
        except:
            print(f"  raw: {text[:200]}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

print("\n✅ 完成")
