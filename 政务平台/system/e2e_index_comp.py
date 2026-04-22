#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析index组件的动态组件渲染机制"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
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
# Step 1: index组件render/template
# ============================================================
print("Step 1: index组件render函数")
render_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var idx=findComp(vm,'index',0);
    if(!idx)return'no_idx';
    // render函数
    var render=idx.$options?.render||idx.$options?.staticRenderFns;
    if(render)return render.toString().substring(0,800);
    // template
    var tpl=idx.$options?.template||'';
    if(tpl)return tpl.substring(0,800);
    return 'no_render_no_template';
})()""", timeout=15)
print(f"  render: {render_src}")

# ============================================================
# Step 2: index组件的完整子组件注册
# ============================================================
print("\nStep 2: index注册的组件")
components = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var idx=findComp(vm,'index',0);
    if(!idx)return'no_idx';
    var comps=idx.$options?.components||{};
    return Object.keys(comps);
})()""")
print(f"  components: {components}")

# ============================================================
# Step 3: 查看activefuc方法源码 (all-services的点击处理)
# ============================================================
print("\nStep 3: activefuc源码")
activefuc_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var fn=as.$options?.methods?.activefuc;
    if(!fn)return'no_method';
    return fn.toString().substring(0,500);
})()""")
print(f"  activefuc: {activefuc_src}")

# ============================================================
# Step 4: getcardlist方法源码
# ============================================================
print("\nStep 4: getcardlist源码")
getcardlist_src = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var fn=as.$options?.methods?.getcardlist;
    if(!fn)return'no_method';
    return fn.toString().substring(0,500);
})()""")
print(f"  getcardlist: {getcardlist_src}")

# ============================================================
# Step 5: 查看cardlist数据
# ============================================================
print("\nStep 5: cardlist数据")
cardlist = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist;
    if(!cl)return'no_cardlist';
    // 列出所有key
    var keys=Object.keys(cl);
    var result={};
    for(var i=0;i<keys.length;i++){
        var v=cl[keys[i]];
        if(Array.isArray(v)){
            result[keys[i]]='A['+v.length+']';
            // 取第一项的key
            if(v.length>0&&typeof v[0]==='object'){
                result[keys[i]]+=' keys:'+Object.keys(v[0]).slice(0,5).join(',');
            }
        }else{
            result[keys[i]]=typeof v==='object'?JSON.stringify(v).substring(0,60):v;
        }
    }
    return result;
})()""")
print(f"  {json.dumps(cardlist, ensure_ascii=False)[:400] if isinstance(cardlist,dict) else cardlist}")

# ============================================================
# Step 6: 查看active值对应的服务
# ============================================================
print("\nStep 6: active=100001对应的服务")
active_data = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist;
    var active=as.$data?.active;
    // 找active对应的children
    var children=cl?.children||[];
    var match=children.filter(function(c){return c.code===active||c.businessModuleCode===active||c.id===active});
    if(match.length)return match.map(function(m){return{name:m.name||m.businessModuleName||'',code:m.code||m.businessModuleCode||m.id||'',url:m.url||m.route||''}});
    // 也看childrenList
    var cList=cl?.childrenList||[];
    var match2=cList.filter(function(c){return c.code===active||c.businessModuleCode===active});
    if(match2.length)return match2.map(function(m){return{name:m.name||'',code:m.code||m.businessModuleCode||''}});
    return {active:active,childrenLen:children.length,cListLen:cList.length,firstChild:children[0]?JSON.stringify(children[0]).substring(0,100):'none'};
})()""")
print(f"  {active_data}")

# ============================================================
# Step 7: 调用activefuc('100001')看是否触发导航
# ============================================================
print("\nStep 7: 调用activefuc")
activefuc_call = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    // activefuc的参数
    as.activefuc('100001');
    return 'called';
})()""")
print(f"  result: {activefuc_call}")
time.sleep(3)

comps = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var wn=findComp(vm,'without-name',0);
    var est=findComp(vm,'establish',0);
    var idx=findComp(vm,'index',0);
    return {{flowControl:!!fc,withoutName:!!wn,establish:!!est,compName:idx?.$data?.compName,hash:location.hash}};
}})()""")
print(f"  组件: {comps}")

# ============================================================
# Step 8: 查看cardlist.childrenList中的设立登记项
# ============================================================
print("\nStep 8: 设立登记项")
setup_items = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{};
    var cList=cl.childrenList||[];
    var setup=cList.filter(function(c){
        var name=(c.name||c.businessModuleName||c.label||'').toLowerCase();
        return name.includes('设立')||name.includes('登记')||name.includes('名称');
    });
    return setup.map(function(s){
        return {name:s.name||s.businessModuleName||'',code:s.code||s.businessModuleCode||s.id||'',url:s.url||s.route||'',type:s.type||''};
    }).slice(0,10);
})()""")
print(f"  {setup_items}")

print("\n✅ 完成")
