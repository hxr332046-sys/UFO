#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""正确导航：重置compName → 查看cardlist → 点击正确子项"""
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
# Step 1: 重置compName
# ============================================================
print("Step 1: 重置compName")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var idx=findComp(vm,'index',0);
    if(idx){{
        idx.$set(idx.$data,'compName','index-common');
        idx.$forceUpdate();
    }}
}})()""")
time.sleep(2)

# ============================================================
# Step 2: 找all-services组件和cardlist
# ============================================================
print("\nStep 2: cardlist数据")
cardlist = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    var active=as.$data?.active;
    // 列出所有一级分类
    var categories=cl.categories||cl.list||cl.items||[];
    // 也看cl的直接属性
    var keys=Object.keys(cl);
    // childrenList
    var cList=cl.childrenList||[];
    var first5=cList.slice(0,5).map(function(c){{
        return {{name:c.name||c.businessModuleName||c.label||'',code:c.code||c.businessModuleCode||c.id||'',url:c.url||c.route||c.path||''}};
    }});
    return {{active:active,keys:keys.slice(0,15),childrenListLen:cList.length,first5:first5}};
}})()""")
print(f"  {json.dumps(cardlist, ensure_ascii=False)[:500] if isinstance(cardlist,dict) else cardlist}")

# ============================================================
# Step 3: 列出所有childrenList项
# ============================================================
print("\nStep 3: 全部childrenList")
all_items = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    var cList=cl.childrenList||[];
    return cList.map(function(c){{
        return {{
            name:(c.name||c.businessModuleName||c.label||'').substring(0,20),
            code:c.code||c.businessModuleCode||c.id||'',
            url:(c.url||c.route||c.path||'').substring(0,40),
            pid:c.pid||c.parentId||''
        }};
    }});
}})()""")
if isinstance(all_items, list):
    for item in all_items:
        print(f"  {item}")
else:
    print(f"  {all_items}")

# ============================================================
# Step 4: 找设立登记对应的项并点击
# ============================================================
print("\nStep 4: 找设立登记项")
setup_item = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    var cList=cl.childrenList||[];
    for(var i=0;i<cList.length;i++){{
        var c=cList[i];
        var name=(c.name||c.businessModuleName||c.label||'');
        if(name.includes('设立登记')){{
            return {{idx:i,name:name,code:c.code||c.businessModuleCode||c.id||'',url:c.url||c.route||c.path||'',full:JSON.stringify(c).substring(0,200)}};
        }}
    }}
    return 'not_found';
}})()""")
print(f"  {setup_item}")

# ============================================================
# Step 5: 查看activefuc方法源码（从Vue组件实例获取）
# ============================================================
print("\nStep 5: activefuc源码")
activefuc = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var fn=as.activefuc;
    if(!fn)return'no_fn';
    return fn.toString().substring(0,500);
}})()""")
print(f"  {activefuc}")

# ============================================================
# Step 6: 查看getcardlist源码
# ============================================================
print("\nStep 6: getcardlist源码")
getcardlist = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var fn=as.getcardlist;
    if(!fn)return'no_fn';
    return fn.toString().substring(0,500);
}})()""")
print(f"  {getcardlist}")

# ============================================================
# Step 7: 查看all-services的template/render
# ============================================================
print("\nStep 7: all-services render")
as_render = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var r=as.$options?.render;
    if(r)return r.toString().substring(0,500);
    var t=as.$options?.template||'';
    if(t)return 'tpl:'+t.substring(0,500);
    return 'no_render';
}})()""", timeout=15)
print(f"  {as_render}")

# ============================================================
# Step 8: 尝试点击设立登记的DOM元素
# ============================================================
print("\nStep 8: 点击设立登记DOM")
# 先看当前可见的所有可点击元素
clickable = ev("""(function(){
    var result=[];
    var all=document.querySelectorAll('.sec-menu,.menu-item,.card-item,.service-item,.grid-item,.children-item');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()?.substring(0,30)||'';
        var rect=all[i].getBoundingClientRect();
        var visible=rect.width>0&&rect.height>0;
        if(visible&&t.length>0){
            result.push({idx:i,text:t,cls:(all[i].className||'').substring(0,30),tag:all[i].tagName});
        }
    }
    return result.slice(0,20);
})()""")
print(f"  可见元素: {clickable}")

# 点击设立登记对应的子项
if isinstance(setup_item, dict) and setup_item.get('idx') is not None:
    click_result = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var as=findComp(vm,'all-services',0);
        if(!as)return'no_as';
        var cl=as.$data?.cardlist||{{}};
        var cList=cl.childrenList||[];
        var item=cList[{setup_item['idx']}];
        if(!item)return'no_item';
        // 调用activefuc
        as.activefuc(item.code||item.businessModuleCode||item.id||'');
        return {{called:true,code:item.code||item.businessModuleCode||item.id}};
    }})()""")
    print(f"  activefuc调用: {click_result}")
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

print("\n✅ 完成")
