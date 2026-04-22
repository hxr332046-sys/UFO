#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找到设立登记入口 - 通过cardlist URL和activefuc导航"""
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
# Step 1: 重置compName到index-common
# ============================================================
print("Step 1: 重置compName")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var idx=findComp(vm,'index',0);
    if(idx){{idx.$set(idx.$data,'compName','index-common');idx.$forceUpdate()}}
}})()""")
time.sleep(2)

# ============================================================
# Step 2: 获取cardlist完整数据 - 找设立登记
# ============================================================
print("\nStep 2: 找设立登记项")
items = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    var cList=cl.childrenList||[];
    // 找URL包含qydj或enter的项
    var result=[];
    for(var i=0;i<cList.length;i++){{
        var c=cList[i];
        var urlStr=c.url||c.route||c.path||'';
        var name=c.name||c.businessModuleName||c.label||c.title||'';
        // 也看i18n name
        var nameI18n=c.nameI18n||c.i18nName||'';
        if(urlStr.includes('qydj')||urlStr.includes('enter')||urlStr.includes('name-register')||urlStr.includes('namenot')||name.includes('设立')||nameI18n.includes('设立')){{
            result.push({{idx:i,code:c.code||c.businessModuleCode||c.id||'',name:name,url:urlStr.substring(0,60),nameI18n:nameI18n}});
        }}
    }}
    // 也获取active对应的分类
    var active=as.$data?.active;
    var activeItem=cList.find(function(c){{return c.code===active||c.businessModuleCode===active||c.id===active}});
    return {{active:active,activeName:activeItem?(activeItem.name||activeItem.businessModuleName||''):'',matches:result}};
}})()""")
print(f"  {json.dumps(items, ensure_ascii=False)[:400] if isinstance(items,dict) else items}")

# ============================================================
# Step 3: 获取完整的cardlist结构 (含子分类)
# ============================================================
print("\nStep 3: cardlist完整结构")
structure = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    // 查看顶层keys
    var keys=Object.keys(cl);
    // allList
    var allList=cl.allList||as.$data?.allList||{{}};
    var allListKeys=Object.keys(allList);
    var allListChildren=allList.childrenList||[];
    // 设立登记分类的code
    var active=as.$data?.active;
    // 找active对应的childrenList
    var activeChildren=[];
    for(var i=0;i<allListChildren.length;i++){{
        var c=allListChildren[i];
        if(c.code===active||c.businessModuleCode===active||c.id===active){{
            activeChildren=c.childrenList||c.children||[];
            break;
        }}
    }}
    return {{
        cardlistKeys:keys,
        allListKeys:allListKeys,
        allListChildrenLen:allListChildren.length,
        active:active,
        activeChildrenLen:activeChildren.length,
        activeChildrenFirst3:activeChildren.slice(0,3).map(function(c){{
            return {{name:c.name||c.businessModuleName||'',code:c.code||c.businessModuleCode||c.id||'',url:(c.url||c.route||'').substring(0,50)}};
        }})
    }};
}})()""")
print(f"  {json.dumps(structure, ensure_ascii=False)[:500] if isinstance(structure,dict) else structure}")

# ============================================================
# Step 4: 点击sec-menu"设立登记"展开子菜单
# ============================================================
print("\nStep 4: 点击设立登记sec-menu")
ev("""(function(){
    var menus=document.querySelectorAll('.sec-menu');
    for(var i=0;i<menus.length;i++){
        var t=menus[i].textContent?.trim()||'';
        if(t.includes('设立登记')){
            menus[i].click();
            return {clicked:t.substring(0,20)};
        }
    }
    return 'no_menu';
})()""")
time.sleep(2)

# 查看展开后的子菜单
sub_items = ev("""(function(){
    var items=document.querySelectorAll('.third-menu,.sub-menu,.children-item,.sec-menu-children li,.el-submenu__title');
    var result=[];
    for(var i=0;i<items.length;i++){
        var t=items[i].textContent?.trim()?.substring(0,30)||'';
        var rect=items[i].getBoundingClientRect();
        var visible=rect.width>0&&rect.height>0;
        if(t&&visible)result.push({text:t,visible:visible,cls:(items[i].className||'').substring(0,30)});
    }
    return result.slice(0,15);
})()""")
print(f"  子菜单: {sub_items}")

# ============================================================
# Step 5: 查看activefuc调用后active变化
# ============================================================
print("\nStep 5: active变化")
active_after = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    return {{active:as.$data?.active,selected:as.$data?.selected}};
}})()""")
print(f"  {active_after}")

# ============================================================
# Step 6: 获取active=100001对应的子项列表
# ============================================================
print("\nStep 6: active=100001的子项")
sub_list = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var as=findComp(vm,'all-services',0);
    if(!as)return'no_as';
    var cl=as.$data?.cardlist||{{}};
    var cList=cl.childrenList||[];
    var active=as.$data?.active;
    // 找active对应的项
    var activeItem=null;
    for(var i=0;i<cList.length;i++){{
        if(cList[i].code===active||cList[i].businessModuleCode===active||cList[i].id===active){{
            activeItem=cList[i];break;
        }}
    }}
    if(!activeItem)return {{active:active,notFound:true}};
    var children=activeItem.childrenList||activeItem.children||[];
    return {{
        active:active,
        itemName:activeItem.name||activeItem.businessModuleName||'',
        childrenLen:children.length,
        children:children.slice(0,10).map(function(c){{
            return {{
                name:c.name||c.businessModuleName||'',
                code:c.code||c.businessModuleCode||c.id||'',
                url:(c.url||c.route||c.path||'').substring(0,60)
            }};
        }})
    }};
}})()""")
print(f"  {json.dumps(sub_list, ensure_ascii=False)[:600] if isinstance(sub_list,dict) else sub_list}")

# ============================================================
# Step 7: 找内资公司设立登记子项并调用activefuc
# ============================================================
print("\nStep 7: 找内资公司设立并导航")
if isinstance(sub_list, dict) and sub_list.get('children'):
    for child in sub_list.get('children', []):
        name = child.get('name', '')
        code = child.get('code', '')
        url = child.get('url', '')
        print(f"  尝试: {name} code={code} url={url}")
        if '内资' in name or '公司设立' in name or 'qydj' in url or 'name-register' in url:
            print(f"  → 调用activefuc({code})")
            ev(f"""(function(){{
                var vm=document.getElementById('app').__vue__;
                {FC}
                var as=findComp(vm,'all-services',0);
                as.activefuc('{code}');
            }})()""")
            time.sleep(5)
            
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
            
            if isinstance(comps, dict) and (comps.get('flowControl') or comps.get('withoutName') or comps.get('establish')):
                print("  ✅ 到达表单页面！")
                break
else:
    # 尝试直接用URL导航
    print("  尝试URL导航...")
    # 从cardlist中找name-register的URL
    nav_url = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var as=findComp(vm,'all-services',0);
        var cl=as.$data?.cardlist||{{}};
        var cList=cl.childrenList||[];
        for(var i=0;i<cList.length;i++){{
            var children=cList[i].childrenList||[];
            for(var j=0;j<children.length;j++){{
                var url=children[j].url||children[j].route||'';
                if(url.includes('name-register'))return url;
            }}
        }}
        return 'not_found';
    }})()""")
    print(f"  name-register URL: {nav_url}")
    
    # 尝试解析URL并导航
    if isinstance(nav_url, str) and nav_url.startswith('{'):
        try:
            url_obj = json.loads(nav_url)
            project = url_obj.get('project', '')
            path = url_obj.get('path', '')
            print(f"  project={project} path={path}")
            if project == 'portal':
                ev(f"""(function(){{
                    var vm=document.getElementById('app').__vue__;
                    vm.$router.push('{path}');
                }})()""")
                time.sleep(3)
                comps = ev(f"""(function(){{
                    var vm=document.getElementById('app').__vue__;
                    {FC}
                    var fc=findComp(vm,'flow-control',0);
                    var wn=findComp(vm,'without-name',0);
                    return {{flowControl:!!fc,withoutName:!!wn,hash:location.hash}};
                }})()""")
                print(f"  组件: {comps}")
        except:
            pass

print("\n✅ 完成")
