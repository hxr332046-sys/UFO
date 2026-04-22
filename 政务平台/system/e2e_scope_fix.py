#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析经营范围正确数据结构 + 修复"""
import json, time, requests, websocket

def ev(js, timeout=10):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
        ws = websocket.create_connection(ws_url, timeout=8)
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
# Step 1: 分析currentLocationVo（含entName）
# ============================================================
print("Step 1: currentLocationVo结构")
clv = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    var bdi=comp.$data.businessDataInfo;
    var clv=bdi.currentLocationVo||{};
    return JSON.parse(JSON.stringify(clv));
})()""")
print(f"  currentLocationVo: {json.dumps(clv, ensure_ascii=False)[:200] if isinstance(clv,dict) else clv}")

# ============================================================
# Step 2: 拦截保存请求，分析请求体
# ============================================================
print("\nStep 2: 拦截保存请求")

ev("""(function(){
    window.__save_bodies=[];
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')||url.includes('save')||url.includes('Save')){
            window.__save_bodies.push({url:url,body:body||''});
        }
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

# 保存
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

# 获取请求体
bodies = ev("window.__save_bodies")
if bodies and isinstance(bodies, list) and len(bodies) > 0:
    body = bodies[-1].get('body','')
    url = bodies[-1].get('url','')
    print(f"  API: {url[:60]}")
    try:
        parsed = json.loads(body)
        # 保存完整请求体
        with open(r'g:\UFO\政务平台\data\save_request_body.json','w',encoding='utf-8') as f:
            json.dump(parsed,f,ensure_ascii=False,indent=2)
        print("  已保存到 save_request_body.json")
        
        # 找经营范围相关字段
        def find_scope(obj, prefix=''):
            if isinstance(obj, dict):
                for k,v in obj.items():
                    path = f"{prefix}.{k}" if prefix else k
                    if any(w in k.lower() for w in ['scope','area','busi','indus','trade','business']):
                        if isinstance(v, str):
                            print(f"  {path}: {v[:60]}")
                        elif isinstance(v, list):
                            print(f"  {path}: Array[{len(v)}]")
                            for i,item in enumerate(v[:3]):
                                print(f"    [{i}]: {json.dumps(item,ensure_ascii=False)[:80]}")
                        elif isinstance(v, dict):
                            print(f"  {path}: {json.dumps(v,ensure_ascii=False)[:80]}")
                        else:
                            print(f"  {path}: {v}")
                    find_scope(v, path)
            elif isinstance(obj, list):
                for i,item in enumerate(obj[:5]):
                    find_scope(item, f"{prefix}[{i}]")
        
        find_scope(parsed)
    except:
        print(f"  body(raw): {body[:300]}")

# ============================================================
# Step 3: 分析经营范围对话框的正确用法
# ============================================================
print("\nStep 3: 经营范围对话框Vue组件分析")

# 找经营范围相关的Vue组件和方法
scope_comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d,path){
        if(d>15)return[];
        var result=[];
        var name=vm.$options?.name||'';
        var hasScope=false;
        
        // 检查是否包含经营范围相关方法
        var methods=vm.$options?.methods||{};
        var methodNames=Object.keys(methods);
        var scopeMethods=methodNames.filter(function(m){
            return m.includes('scope')||m.includes('Scope')||m.includes('Area')||m.includes('area')||
                   m.includes('businessScope')||m.includes('BusinessScope')||m.includes('addScope')||
                   m.includes('selectScope')||m.includes('handleScope')||m.includes('openDialog');
        });
        
        if(scopeMethods.length>0){
            result.push({name:name,methods:scopeMethods,path:path});
        }
        
        for(var i=0;i<(vm.$children||[]).length;i++){
            result=result.concat(find(vm.$children[i],d+1,path+'/'+i));
        }
        return result;
    }
    return find(vm,0,'root');
})()""")
print(f"  含scope方法的组件: {scope_comp}")

# ============================================================
# Step 4: 尝试通过对话框正确选择经营范围
# ============================================================
print("\nStep 4: 通过对话框选择经营范围")

# 点击添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(5)

# 深度分析对话框DOM
dlg_dom = ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        // 递归列出DOM树（前3层）
        function walk(el,depth){
            if(depth>3)return'';
            var tag=el.tagName||'?';
            var cls=el.className&&typeof el.className==='string'?el.className.substring(0,30):'';
            var text=el.childNodes?.length===1&&el.childNodes[0].nodeType===3?el.textContent?.trim()?.substring(0,30):'';
            var children='';
            for(var j=0;j<el.children.length;j++){
                children+=walk(el.children[j],depth+1);
            }
            var indent='  '.repeat(depth);
            return indent+'<'+tag+' class="'+cls+'">'+(text||'')+'\\n'+children;
        }
        return walk(d,0).substring(0,1500);
    }
    return 'no_dialog';
})()""", timeout=12)
print(f"  对话框DOM:\n{dlg_dom}")

# 检查iframe（可能是动态加载的）
iframe_check = ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        var ifs=d.querySelectorAll('iframe');
        var r=[];
        for(var j=0;j<ifs.length;j++){
            r.push({
                src:ifs[j].src||ifs[j].getAttribute('src')||'',
                dataSrc:ifs[j].getAttribute('data-src')||'',
                width:ifs[j].offsetWidth,
                height:ifs[j].offsetHeight,
                display:getComputedStyle(ifs[j]).display,
                loaded:ifs[j].contentDocument!==null
            });
        }
        return r;
    }
})()""")
print(f"  iframe: {iframe_check}")

# 关闭对话框
ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        var close=d.querySelector('[class*="close"],[class*="Close"],.tni-dialog__close');
        if(close){close.click();return}
    }
    document.body.click();
})()""")
time.sleep(1)

print("\n✅ 分析完成")
