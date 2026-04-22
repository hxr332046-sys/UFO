#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: 行业类型同步到businese-info + 经营范围searchList加载"""
import json, time, requests, websocket

def ev(js, timeout=10):
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
# Step 1: 分析businese-info组件的form字段
# ============================================================
print("Step 1: businese-info form分析")
bi_form = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var form=comp.busineseForm||{};
    var keys=Object.keys(form);
    var result={};
    for(var i=0;i<keys.length;i++){
        var k=keys[i];var v=form[k];
        if(v===null||v===undefined)result[k]='null';
        else if(Array.isArray(v))result[k]='Array['+v.length+']';
        else if(typeof v==='object')result[k]='obj:'+Object.keys(v).slice(0,3).join(',');
        else result[k]=String(v).substring(0,40);
    }
    return result;
})()""")
print(f"  busineseForm: {bi_form}")

# ============================================================
# Step 2: 设置行业类型到businese-info form
# ============================================================
print("\nStep 2: 设置行业类型到businese-info")
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return;
    var form=comp.busineseForm;
    comp.$set(form,'itemIndustryTypeCode','I65');
    comp.$set(form,'industryTypeName','软件和信息技术服务业');
    // 也设置params
    if(comp.params){
        comp.$set(comp.params,'industryCode','I65');
    }
    comp.$forceUpdate();
    return{set:true};
})()""")

# 也通过treeSelectChange方法设置
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return;
    // 使用indSelectTree ref
    var tree=comp.$refs?.indSelectTree;
    if(tree){
        tree.valueId='I65';
        tree.valueTitle='软件和信息技术服务业';
        comp.treeSelectChange('ind');
        return{treeSelectChange:true};
    }
    return{error:'no_tree_ref'};
})()""")

# ============================================================
# Step 3: 验证行业类型
# ============================================================
print("\nStep 3: 验证行业类型")
ind_val = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    var form=comp.busineseForm||{};
    return{
        itemIndustryTypeCode:form.itemIndustryTypeCode||'',
        industryTypeName:form.industryTypeName||'',
        busiAreaDataLen:(form.busiAreaData||[]).length,
        businessArea:form.businessArea?.substring(0,30)||''
    };
})()""")
print(f"  busineseForm: {ind_val}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 4: 经营范围 - 先加载tni-business-range数据
# ============================================================
print("\nStep 4: 加载经营范围数据")

# 找到tni-business-range组件
tbr = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    var dataKeys=Object.keys(comp.$data||{});
    var props=Object.keys(comp.$props||{});
    var methods=Object.keys(comp.$options?.methods||{});
    var sl=(comp.searchList||comp.$data?.searchList||[]).length;
    var al=(comp.allBusinessList||comp.$data?.allBusinessList||[]).length;
    var il=(comp.industryList||comp.$data?.industryList||[]).length;
    var sel=(comp.selectedList||comp.$data?.selectedList||[]).length;
    return{dataKeys:dataKeys,props:props,methods:methods,searchListLen:sl,allBusinessListLen:al,industryListLen:il,selectedListLen:sel};
})()""")
print(f"  tni-business-range: {tbr}")

# 调用init加载经营范围列表
if isinstance(tbr, dict):
    init_result = ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        if(!comp)return{error:'no_comp'};
        // 调用init
        try{
            if(typeof comp.init==='function'){comp.init();return{called:'init'}}
            if(typeof comp.initOptions==='function'){comp.initOptions();return{called:'initOptions'}}
            if(typeof comp.initList==='function'){comp.initList();return{called:'initList'}}
        }catch(e){return{error:e.message}}
        return{error:'no_init_method'};
    })()""")
    print(f"  init: {init_result}")
    time.sleep(3)
    
    # 检查加载结果
    loaded = ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        var sl=(comp.searchList||comp.$data?.searchList||[]).length;
        var al=(comp.allBusinessList||comp.$data?.allBusinessList||[]).length;
        var il=(comp.industryList||comp.$data?.industryList||[]).length;
        // 找软件相关
        var all=comp.allBusinessList||comp.$data?.allBusinessList||[];
        var software=[];
        for(var i=0;i<all.length;i++){
            var cat=all[i];
            if(cat.id==='I'&&cat.list){
                for(var j=0;j<cat.list.length;j++){
                    if(cat.list[j].id==='65'){
                        var sub=cat.list[j];
                        software.push({id:sub.id,name:sub.name,childrenLen:sub.children?.length||sub.list?.length||0});
                    }
                }
            }
        }
        return{searchListLen:sl,allBusinessListLen:al,industryListLen:il,software:software};
    })()""")
    print(f"  加载后: searchList={loaded.get('searchListLen',0) if isinstance(loaded,dict) else '?'} allBusiness={loaded.get('allBusinessListLen',0) if isinstance(loaded,dict) else '?'} industry={loaded.get('industryListLen',0) if isinstance(loaded,dict) else '?'}")
    if isinstance(loaded,dict):
        print(f"  I.65: {loaded.get('software',[])}")

# ============================================================
# Step 5: 搜索"软件开发"并获取正确格式数据
# ============================================================
print("\nStep 5: 搜索经营范围")

# 触发搜索
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return;
    var si=comp.$refs?.searchInput;
    if(si){
        var inputEl=si.$el?.querySelector('input');
        if(inputEl){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputEl,'软件开发');
            inputEl.dispatchEvent(new Event('input',{bubbles:true}));
            return{search:'软件开发'};
        }
    }
    // 备选: DOM搜索
    var el=comp.$el;
    var inputs=el.querySelectorAll('input');
    for(var i=0;i<inputs.length;i++){
        var ph=inputs[i].placeholder||'';
        if(ph.includes('搜索')||ph.includes('关键词')||ph.includes('检索')){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputs[i],'软件开发');
            inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
            return{search:'软件开发_dom'};
        }
    }
    return{error:'no_search',inputCount:inputs.length};
})()""")
time.sleep(4)

# 获取搜索结果
search_items = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return[];
    var sl=comp.searchList||comp.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name==='软件开发'||name==='信息技术咨询服务'||name.includes('数据处理和存储')){
            items.push(JSON.parse(JSON.stringify(sl[i])));
        }
    }
    // 如果searchList为空，从allBusinessList深度搜索
    if(items.length===0){
        var al=comp.allBusinessList||comp.$data?.allBusinessList||[];
        for(var i=0;i<al.length;i++){
            var cat=al[i];
            if(cat.id==='I'&&cat.list){
                for(var j=0;j<cat.list.length;j++){
                    if(cat.list[j].id==='65'){
                        // 65下面的子分类
                        var sub65=cat.list[j];
                        var children=sub65.children||sub65.list||[];
                        for(var k=0;k<children.length;k++){
                            var ch=children[k];
                            if(ch.name==='软件开发'||ch.name==='信息技术咨询服务'){
                                items.push(JSON.parse(JSON.stringify(ch)));
                            }
                            // 也检查更深层
                            var deep=ch.children||ch.list||[];
                            for(var l=0;l<deep.length;l++){
                                if(deep[l].name==='软件开发'||deep[l].name==='信息技术咨询服务'){
                                    items.push(JSON.parse(JSON.stringify(deep[l])));
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return items;
})()""", timeout=12)
print(f"  搜索结果: {len(search_items) if isinstance(search_items,list) else search_items}项")
if isinstance(search_items, list):
    for it in search_items[:5]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:120]}")

# ============================================================
# Step 6: 用正确格式confirm
# ============================================================
print("\nStep 6: confirm经营范围")

if isinstance(search_items, list) and len(search_items) > 0:
    # 标记主营
    search_items[0]['isMainIndustry'] = '1'
    search_items[0]['stateCo'] = '3'
    for i in range(1, len(search_items)):
        search_items[i]['isMainIndustry'] = '0'
        if search_items[i].get('stateCo') != '3':
            search_items[i]['stateCo'] = '1'
    
    names = ';'.join([it.get('name','') for it in search_items])
    confirm_data = {
        'busiAreaData': search_items,
        'genBusiArea': names,
        'busiAreaCode': 'I65',
        'busiAreaName': names
    }
    
    confirm_json = json.dumps(confirm_data, ensure_ascii=False)
    confirm_js = '(function(){var app=document.getElementById("app");var vm=app&&app.__vue__;function findComp(vm,name,d){if(d>15)return null;if(vm.$options&&vm.$options.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var comp=findComp(vm,"businese-info",0);if(!comp)return;comp.confirm(' + confirm_json + ');})()'
    ev(confirm_js)
    print(f"  confirm: {len(search_items)}项, {names[:40]}")
else:
    print("  ❌ 无搜索结果，用已知格式")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options&&vm.$options.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
            return null;
        }
        var comp=findComp(vm,'businese-info',0);
        if(!comp)return;
        comp.confirm({
            busiAreaData:[
                {id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'},
                {id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}
            ],
            genBusiArea:'软件开发;信息技术咨询服务',
            busiAreaCode:'I65',
            busiAreaName:'软件开发;信息技术咨询服务'
        });
    })()""")

# ============================================================
# Step 7: 验证并保存
# ============================================================
print("\nStep 7: 验证并保存")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options&&vm.$options.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var form=comp.busineseForm||{};
    return{
        itemIndustryTypeCode:form.itemIndustryTypeCode||'',
        industryTypeName:form.industryTypeName||'',
        busiAreaDataLen:(form.busiAreaData||[]).length,
        genBusiArea:form.genBusiArea?.substring(0,40)||'',
        busiAreaCode:form.busiAreaCode||''
    };
})()""")
print(f"  busineseForm: {bf}")

# 保存
ev("""(function(){
    window.__save_final=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_final={status:self.status,resp:self.responseText?.substring(0,500)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    try{comp.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

resp = ev("window.__save_final")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            code = p.get('code','')
            msg = p.get('msg','')[:60]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000']:
                print("  ✅ 保存成功！")
        except:
            print(f"  raw: {r[:150]}")
else:
    print("  无API响应")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
