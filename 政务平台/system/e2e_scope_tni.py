#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过tni-business-range组件正确选择经营范围"""
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
# Step 1: 分析tni-business-range组件
# ============================================================
print("Step 1: tni-business-range组件分析")
tbr = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    var dataKeys=Object.keys(comp.$data||{});
    var props=Object.keys(comp.$props||{});
    var methods=Object.keys(comp.$options?.methods||{});
    var refs=Object.keys(comp.$refs||{});
    var children=[];
    for(var i=0;i<(comp.$children||[]).length;i++){
        var c=comp.$children[i];
        children.push({name:c.$options?.name||'',dataKeys:Object.keys(c.$data||{}).slice(0,5)});
    }
    
    // 关键数据
    var selectedList=comp.selectedList||comp.$data?.selectedList||[];
    var industryList=comp.industryList||comp.$data?.industryList||[];
    var allBusinessList=comp.allBusinessList||comp.$data?.allBusinessList||[];
    
    return{
        dataKeys:dataKeys,
        props:props,
        methods:methods,
        refs:refs,
        children:children.slice(0,5),
        selectedListLen:selectedList.length,
        industryListLen:industryList.length,
        allBusinessListLen:allBusinessList.length,
        // selectedList sample
        selectedSample:selectedList.length>0?JSON.stringify(selectedList[0]).substring(0,200):'empty'
    };
})()""")
print(f"  tni-business-range: dataKeys={tbr.get('dataKeys',[]) if isinstance(tbr,dict) else tbr}")
if isinstance(tbr,dict):
    print(f"  props: {tbr.get('props',[])}")
    print(f"  methods: {tbr.get('methods',[])}")
    print(f"  refs: {tbr.get('refs',[])}")
    print(f"  selectedList: {tbr.get('selectedListLen',0)} industryList: {tbr.get('industryListLen',0)} allBusinessList: {tbr.get('allBusinessListLen',0)}")
    print(f"  selectedSample: {tbr.get('selectedSample','')}")

# ============================================================
# Step 2: 获取行业分类列表和经营范围列表
# ============================================================
print("\nStep 2: 获取经营范围列表")
biz_list = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    // 获取行业列表
    var il=comp.industryList||comp.$data?.industryList||[];
    var ilSample=[];
    for(var i=0;i<Math.min(il.length,3);i++){
        ilSample.push({code:il[i].code||il[i].value||'',name:il[i].name||il[i].label||'',children:il[i].children?.length||0});
    }
    
    // 获取allBusinessList
    var abl=comp.allBusinessList||comp.$data?.allBusinessList||[];
    var ablSample=[];
    for(var i=0;i<Math.min(abl.length,5);i++){
        ablSample.push(JSON.stringify(abl[i]).substring(0,100));
    }
    
    // 获取themeBusinessList
    var tbl=comp.themeBusinessList||comp.$data?.themeBusinessList||[];
    
    // 搜索"软件"相关
    var softwareItems=[];
    for(var i=0;i<abl.length;i++){
        var name=abl[i].name||abl[i].label||abl[i].text||'';
        if(name.includes('软件')||name.includes('信息技术')){
            softwareItems.push(JSON.stringify(abl[i]).substring(0,150));
        }
    }
    
    return{
        industryListLen:il.length,
        industrySample:ilSample,
        allBusinessListLen:abl.length,
        allBusinessSample:ablSample,
        themeBusinessListLen:tbl.length,
        softwareItems:softwareItems.slice(0,5)
    };
})()""")
print(f"  行业列表: {biz_list.get('industryListLen',0) if isinstance(biz_list,dict) else biz_list}")
if isinstance(biz_list,dict):
    print(f"  行业sample: {biz_list.get('industrySample',[])}")
    print(f"  经营范围列表: {biz_list.get('allBusinessListLen',0)}")
    print(f"  经营范围sample: {biz_list.get('allBusinessSample',[])}")
    print(f"  软件相关: {biz_list.get('softwareItems',[])}")

# ============================================================
# Step 3: 如果列表为空，调用init/getAllBusinessList加载
# ============================================================
if isinstance(biz_list,dict) and biz_list.get('allBusinessListLen',0)==0:
    print("\nStep 3: 加载经营范围列表")
    load_result = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        if(!comp)return{error:'no_comp'};
        
        // 调用init加载
        try{
            if(typeof comp.init==='function')comp.init();
            else if(typeof comp.initList==='function')comp.initList();
            else if(typeof comp.getAllBusinessList==='function')comp.getAllBusinessList();
            return{called:true};
        }catch(e){
            return{error:e.message};
        }
    })()""")
    print(f"  加载结果: {load_result}")
    time.sleep(3)
    
    # 重新获取列表
    biz_list2 = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        var abl=comp.allBusinessList||comp.$data?.allBusinessList||[];
        var softwareItems=[];
        for(var i=0;i<abl.length;i++){
            var name=abl[i].name||abl[i].label||abl[i].text||'';
            if(name.includes('软件')||name.includes('信息技术')){
                softwareItems.push(JSON.stringify(abl[i]).substring(0,200));
            }
        }
        return{allBusinessListLen:abl.length,softwareItems:softwareItems.slice(0,5)};
    })()""")
    print(f"  重新获取: allBusinessList={biz_list2.get('allBusinessListLen',0) if isinstance(biz_list2,dict) else 0}")
    if isinstance(biz_list2,dict):
        print(f"  软件相关: {biz_list2.get('softwareItems',[])}")

# ============================================================
# Step 4: 搜索并选择经营范围项
# ============================================================
print("\nStep 4: 搜索并选择经营范围")

# 通过搜索框搜索
search_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    // 使用searchInput ref
    var searchInput=comp.$refs?.searchInput;
    if(searchInput){
        var inputEl=searchInput.$el?.querySelector('input')||searchInput;
        if(inputEl){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputEl,'软件开发');
            inputEl.dispatchEvent(new Event('input',{bubbles:true}));
            return{search:'软件开发'};
        }
    }
    
    // 也尝试直接调用组件方法
    if(typeof comp.search==='function'){
        comp.search('软件开发');
        return{called:'search'};
    }
    if(typeof comp.handleSearch==='function'){
        comp.handleSearch('软件开发');
        return{called:'handleSearch'};
    }
    
    return{error:'no_search_method',refs:Object.keys(comp.$refs||{})};
})()""")
print(f"  搜索: {search_result}")
time.sleep(3)

# 检查搜索结果
search_items = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    // 检查搜索结果列表
    var searchResult=comp.searchResult||comp.$data?.searchResult||comp.searchList||comp.$data?.searchList||[];
    var filterList=comp.filterList||comp.$data?.filterList||[];
    var currentList=comp.currentList||comp.$data?.currentList||[];
    
    // 也检查所有可能包含"软件"的数据
    var allData=comp.$data||{};
    var found=[];
    for(var k in allData){
        var v=allData[k];
        if(Array.isArray(v)){
            for(var i=0;i<v.length;i++){
                var text=JSON.stringify(v[i])||'';
                if(text.includes('软件')){
                    found.push({key:k,idx:i,text:text.substring(0,150)});
                    if(found.length>=5)break;
                }
            }
        }
        if(found.length>=5)break;
    }
    
    return{
        searchResultLen:searchResult.length,
        filterListLen:filterList.length,
        currentListLen:currentList.length,
        found:found
    };
})()""")
print(f"  搜索结果: {search_items}")

# ============================================================
# Step 5: 直接通过行业分类选择
# ============================================================
print("\nStep 5: 通过行业分类选择经营范围")

# 点击[I]信息传输门类
industry_select = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    // 调用getIndurstyBusinessList
    if(typeof comp.getIndurstyBusinessList==='function'){
        try{
            comp.getIndurstyBusinessList('I');
            return{called:'getIndurstyBusinessList',arg:'I'};
        }catch(e){
            return{error:e.message};
        }
    }
    
    // 也尝试点击DOM中的行业分类
    var el=comp.$el;
    var cats=el.querySelectorAll('[class*="category"],[class*="industry"],[class*="tree-node"],li,span');
    for(var i=0;i<cats.length;i++){
        var text=cats[i].textContent?.trim()||'';
        if(text.includes('信息传输')||text.includes('软件')){
            cats[i].click();
            return{clicked:text.substring(0,30),idx:i};
        }
    }
    
    return{error:'no_method',methods:Object.keys(comp.$options?.methods||{})};
})()""")
print(f"  行业选择: {industry_select}")
time.sleep(3)

# 检查加载的经营范围列表
biz_after = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    var allData=comp.$data||{};
    var found=[];
    for(var k in allData){
        var v=allData[k];
        if(Array.isArray(v)&&v.length>0){
            var sample=JSON.stringify(v[0]).substring(0,100);
            found.push({key:k,len:v.length,sample:sample});
        }
    }
    // 找含"软件"的
    var software=[];
    for(var k in allData){
        var v=allData[k];
        if(Array.isArray(v)){
            for(var i=0;i<v.length;i++){
                var t=JSON.stringify(v[i])||'';
                if(t.includes('软件')&&software.length<3){
                    software.push({key:k,idx:i,json:t.substring(0,200)});
                }
            }
        }
    }
    return{dataArrays:found.slice(0,10),software:software};
})()""")
print(f"  数据: arrays={len(biz_after.get('dataArrays',[])) if isinstance(biz_after,dict) else 0}")
if isinstance(biz_after,dict):
    for a in biz_after.get('dataArrays',[]):
        print(f"    {a.get('key','')}: len={a.get('len',0)} sample={a.get('sample','')}")
    print(f"  软件项: {biz_after.get('software',[])}")

# ============================================================
# Step 6: 选择经营范围项并确认
# ============================================================
print("\nStep 6: 选择经营范围项")

# 找到并选择"软件开发"项
select_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    // 在DOM中找checkbox或可选项
    var el=comp.$el;
    var checkboxes=el.querySelectorAll('.el-checkbox');
    var items=el.querySelectorAll('[class*="item"],[class*="option"],li');
    
    var cbMatches=[];
    for(var i=0;i<checkboxes.length;i++){
        var text=checkboxes[i].parentElement?.textContent?.trim()||checkboxes[i].closest('div,li')?.textContent?.trim()||'';
        if(text.includes('软件')||text.includes('信息技术')){
            cbMatches.push({idx:i,text:text.substring(0,40),checked:checkboxes[i].classList.contains('is-checked')});
        }
    }
    
    var itemMatches=[];
    for(var i=0;i<items.length;i++){
        var text=items[i].textContent?.trim()||'';
        if((text.includes('软件开发')||text.includes('信息技术咨询'))&&text.length<50){
            itemMatches.push({idx:i,text:text.substring(0,40)});
        }
    }
    
    return{checkboxCount:checkboxes.length,cbMatches:cbMatches,itemMatches:itemMatches};
})()""")
print(f"  选择: checkboxes={select_result.get('checkboxCount',0) if isinstance(select_result,dict) else 0}")
if isinstance(select_result,dict):
    for c in select_result.get('cbMatches',[]):
        print(f"    cb[{c['idx']}]: {c['text']} checked={c.get('checked')}")
    for c in select_result.get('itemMatches',[]):
        print(f"    item[{c['idx']}]: {c['text']}")

# 点击匹配的checkbox
if isinstance(select_result,dict) and select_result.get('cbMatches'):
    for c in select_result['cbMatches']:
        if '软件开发' in c['text'] and not c.get('checked'):
            ev(f"""(function(){{
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){{
                    if(d>15)return null;
                    if(vm.$options?.name===name)return vm;
                    for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
                    return null;
                }}
                var comp=findComp(vm,'tni-business-range',0);
                var cbs=comp.$el.querySelectorAll('.el-checkbox');
                cbs[{c['idx']}].click();
            }})()""")
            print(f"  点击cb[{c['idx']}]: {c['text']}")
            time.sleep(1)

# 点击确认按钮
confirm_btn = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    var el=comp.$el;
    var btns=el.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('确定')||t.includes('确认')||t.includes('完成'))&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t};
        }
    }
    // 也检查父对话框
    var dlg=el.closest('.tni-dialog,[class*="dialog"]');
    if(dlg){
        var dlgBtns=dlg.querySelectorAll('button,.el-button');
        for(var i=0;i<dlgBtns.length;i++){
            var t=dlgBtns[i].textContent?.trim()||'';
            if((t.includes('确定')||t.includes('确认'))&&dlgBtns[i].offsetParent!==null){
                dlgBtns[i].click();
                return{clicked:t,from:'dialog'};
            }
        }
    }
    return{error:'no_confirm',btnTexts:Array.from(btns).map(function(b){return b.textContent?.trim()?.substring(0,15)||''})};
})()""")
print(f"  确认按钮: {confirm_btn}")
time.sleep(3)

# ============================================================
# Step 7: 验证并保存
# ============================================================
print("\nStep 7: 验证保存")

# 检查busineseForm
bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    var form=comp.busineseForm||{};
    var data=form.busiAreaData||[];
    return{
        busiAreaDataLen:data.length,
        busiAreaDataSample:data.length>0?JSON.stringify(data[0]).substring(0,200):'empty',
        genBusiArea:form.genBusiArea?.substring(0,30)||'',
        busiAreaCode:form.busiAreaCode||'',
        busiAreaName:form.busiAreaName?.substring(0,30)||''
    };
})()""")
print(f"  busineseForm: {bf}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# 保存
ev("""(function(){
    window.__save_resp2=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_resp2={status:self.status,resp:self.responseText?.substring(0,300)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

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

resp = ev("window.__save_resp2")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            print(f"  code={p.get('code','')} msg={p.get('msg','')[:50]}")
        except:
            print(f"  raw: {r[:100]}")

print("\n✅ 完成")
