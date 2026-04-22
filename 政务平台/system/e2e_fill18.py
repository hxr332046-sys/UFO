#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整流程: 导航→填表→经营范围(通过对话框正确选择)→保存"""
import json, time, requests, websocket, sys

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
# Step 1: 导航回表单
# ============================================================
print("Step 1: 导航回表单")
cur_hash = ev("location.hash")
print(f"  当前: {cur_hash}")

if '#/flow/base/basic-info' not in (cur_hash or ''):
    # 尝试通过Vue Router导航
    nav_result = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        var router=vm.$router;
        if(!router)return 'no_router';
        try{
            router.push('/flow/base/basic-info');
            return 'pushed';
        }catch(e){
            return e.message;
        }
    })()""")
    print(f"  导航: {nav_result}")
    time.sleep(3)
    
    # 如果router导航失败，直接修改hash
    cur_hash = ev("location.hash")
    if '#/flow/base/basic-info' not in (cur_hash or ''):
        ev("location.hash='#/flow/base/basic-info'")
        time.sleep(5)
    
    cur_hash = ev("location.hash")
    print(f"  导航后: {cur_hash}")

# 检查表单是否加载
form_count = ev("document.querySelectorAll('.el-form-item').length")
print(f"  表单项: {form_count}")

# ============================================================
# Step 2: 填写基础字段
# ============================================================
print("\nStep 2: 填写基础字段")

# 找businessDataInfo组件
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return;
    var bdi=comp.$data.businessDataInfo;
    
    // 企业名称
    comp.$set(bdi,'entName','广西智信数据科技有限公司');
    comp.$set(bdi,'name','广西智信数据科技有限公司');
    
    // 地址
    comp.$set(bdi,'distCode','450103');
    comp.$set(bdi,'distCodeName','青秀区');
    comp.$set(bdi,'fisDistCode','450103');
    comp.$set(bdi,'address','广西壮族自治区/南宁市/青秀区');
    comp.$set(bdi,'detAddress','民族大道100号');
    comp.$set(bdi,'isSelectDistCode','1');
    comp.$set(bdi,'havaAdress','0');
    
    // 生产经营地址
    comp.$set(bdi,'regionCode','450103');
    comp.$set(bdi,'regionName','青秀区');
    comp.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    comp.$set(bdi,'detBusinessAddress','民族大道100号');
    
    // 行业类型
    comp.$set(bdi,'itemIndustryTypeCode','I65');
    comp.$set(bdi,'industryTypeName','软件和信息技术服务业');
    comp.$set(bdi,'multiIndustry','I65');
    comp.$set(bdi,'multiIndustryName','软件和信息技术服务业');
    comp.$set(bdi,'industryId','I65');
    comp.$set(bdi,'zlBusinessInd','I65');
    comp.$set(bdi,'busiAreaCode','I65');
    
    comp.$forceUpdate();
    return 'set';
})()""")

# 同步DOM输入框
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('企业名称')){
            s.call(input,'广西智信数据科技有限公司');
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }
        if(label.includes('详细地址')&&label.includes('住所')){
            s.call(input,'民族大道100号');
            input.dispatchEvent(new Event('input',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 3: 设置行业类型(I65) - 通过Vue store
# ============================================================
print("\nStep 3: 行业类型I65")

# 点击行业类型输入框打开下拉
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click();}
            return;
        }
    }
})()""")
time.sleep(3)

# 展开I节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');if(!tree)continue;
        var s=tree.__vue__?.store;if(!s)return;
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){roots[i].expand();return}
        }
    }
})()""")
time.sleep(3)

# 选择65节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');if(!tree)continue;
        var comp=tree.__vue__;if(!comp)return;
        var s=comp.store;if(!s)return;
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){
                var cs=roots[i].childNodes||[];
                for(var j=0;j<cs.length;j++){
                    if(cs[j].data?.code==='65'){
                        var selectComp=null;
                        var items=document.querySelectorAll('.el-form-item');
                        for(var k=0;k<items.length;k++){
                            var l=items[k].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                            if(l.includes('行业类型')){
                                selectComp=items[k].querySelector('.el-select')?.__vue__;
                                break;
                            }
                        }
                        if(selectComp){
                            selectComp.$emit('input','I65');
                            selectComp.$emit('change',cs[j].data);
                            selectComp.selectedLabel='软件和信息技术服务业';
                        }
                        return;
                    }
                }
            }
        }
    }
})()""")
time.sleep(2)

# 关闭下拉
ev("document.body.click()")
time.sleep(1)

# 验证行业类型
ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型'))return items[i].querySelector('input')?.value||'';
    }
})()""")
print(f"  行业类型: {ind_val}")

# ============================================================
# Step 4: 经营范围 - 通过对话框搜索选择
# ============================================================
print("\nStep 4: 经营范围对话框")

# 点击添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(5)

# 检查tni-business-range组件是否可见
tbr_visible = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    var el=comp.$el;
    var visible=el.offsetParent!==null;
    var elCount=el.querySelectorAll('*').length;
    var inputs=el.querySelectorAll('input').length;
    var checkboxes=el.querySelectorAll('.el-checkbox').length;
    var dataKeys=Object.keys(comp.$data||{}).slice(0,10);
    var searchListLen=(comp.searchList||comp.$data?.searchList||[]).length;
    var allBusinessListLen=(comp.allBusinessList||comp.$data?.allBusinessList||[]).length;
    return{visible:visible,elCount:elCount,inputs:inputs,checkboxes:checkboxes,dataKeys:dataKeys,searchListLen:searchListLen,allBusinessListLen:allBusinessListLen};
})()""")
print(f"  tni-business-range: {tbr_visible}")

# 如果searchList为空，触发搜索
if isinstance(tbr_visible, dict) and tbr_visible.get('searchListLen', 0) == 0:
    print("  触发搜索...")
    # 在搜索框输入
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
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
                inputEl.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
                return{search:'软件开发'};
            }
        }
        // 备选: 直接在DOM中找搜索框
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
        return{error:'no_search_input',inputCount:inputs.length};
    })()""")
    time.sleep(4)

# 获取搜索结果
search_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    var sl=comp.searchList||comp.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name==='软件开发'||name.includes('信息技术咨询')||name.includes('数据处理和存储')){
            items.push(JSON.parse(JSON.stringify(sl[i])));
        }
    }
    // 如果searchList为空，检查其他列表
    if(items.length===0){
        var al=comp.allBusinessList||comp.$data?.allBusinessList||[];
        // 遍历找65门类下的
        for(var i=0;i<al.length;i++){
            var cat=al[i];
            if(cat.id==='I'&&cat.list){
                for(var j=0;j<cat.list.length;j++){
                    var sub=cat.list[j];
                    if(sub.id==='65'&&sub.list){
                        // 返回65门类下的子项
                        return{from:'allBusinessList.I.65',subItems:JSON.parse(JSON.stringify(sub.list)).slice(0,5)};
                    }
                }
            }
        }
    }
    return{from:'searchList',items:items};
})()""", timeout=12)
print(f"  搜索结果: {json.dumps(search_result, ensure_ascii=False)[:300] if isinstance(search_result,dict) else search_result}")

# ============================================================
# Step 5: 选择经营范围项
# ============================================================
print("\nStep 5: 选择经营范围")

# 获取完整数据并选择
select_data = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    if(!comp)return{error:'no_comp'};
    
    var sl=comp.searchList||comp.$data?.searchList||[];
    var selectedList=comp.selectedList||comp.$data?.selectedList||[];
    
    // 找"软件开发"项
    var softwareItem=null;
    var itConsultItem=null;
    for(var i=0;i<sl.length;i++){
        if(sl[i].name==='软件开发')softwareItem=sl[i];
        if(sl[i].name==='信息技术咨询服务')itConsultItem=sl[i];
    }
    
    // 如果searchList没有，从allBusinessList找
    if(!softwareItem){
        var al=comp.allBusinessList||comp.$data?.allBusinessList||[];
        for(var i=0;i<al.length;i++){
            if(al[i].id==='I'&&al[i].list){
                for(var j=0;j<al[i].list.length;j++){
                    if(al[i].list[j].id==='65'&&al[i].list[j].children){
                        var ch=al[i].list[j].children;
                        for(var k=0;k<ch.length;k++){
                            if(ch[k].name==='软件开发')softwareItem=ch[k];
                            if(ch[k].name==='信息技术咨询服务')itConsultItem=ch[k];
                        }
                    }
                }
            }
        }
    }
    
    // 添加到selectedList
    if(softwareItem){
        var item1=JSON.parse(JSON.stringify(softwareItem));
        item1.isMainIndustry='1';
        item1.stateCo='3';
        comp.$set(comp.$data,'selectedList',[item1]);
        selectedList.push(item1);
    }
    if(itConsultItem){
        var item2=JSON.parse(JSON.stringify(itConsultItem));
        item2.isMainIndustry='0';
        item2.stateCo='1';
        comp.$data.selectedList.push(item2);
    }
    
    comp.$forceUpdate();
    
    return{
        selectedListLen:comp.$data.selectedList.length,
        sample:comp.$data.selectedList.length>0?JSON.stringify(comp.$data.selectedList[0]).substring(0,200):'empty'
    };
})()""", timeout=12)
print(f"  选择结果: {select_data}")

# ============================================================
# Step 6: 确认选择 - 通过confirm回调
# ============================================================
print("\nStep 6: 确认选择")

# 获取selectedList完整数据
selected = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}
        return null;
    }
    var comp=findComp(vm,'tni-business-range',0);
    var sl=comp.$data?.selectedList||[];
    return JSON.parse(JSON.stringify(sl));
})()""", timeout=12)

if isinstance(selected, list) and len(selected) > 0:
    names = ';'.join([it.get('name','') for it in selected])
    confirm_data = {
        'busiAreaData': selected,
        'genBusiArea': names,
        'busiAreaCode': 'I65',
        'busiAreaName': names
    }
    
    # 调用businese-info的confirm
    confirm_json = json.dumps(confirm_data, ensure_ascii=False)
    confirm_js = '(function(){var app=document.getElementById("app");var vm=app&&app.__vue__;function findComp(vm,name,d){if(d>15)return null;if(vm.$options&&vm.$options.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var comp=findComp(vm,"businese-info",0);if(!comp)return;comp.confirm(' + confirm_json + ');})()'
    ev(confirm_js)
    print(f"  confirm: {len(selected)}项, names={names[:40]}")
else:
    print("  ❌ selectedList为空，无法confirm")
    # 打印所有数据用于调试
    all_data = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){
            if(d>15)return null;
            if(vm.$options?.name===name)return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}}
            return null;
        }
        var comp=findComp(vm,'tni-business-range',0);
        var d=comp.$data||{};
        var result={};
        for(var k in d){
            var v=d[k];
            if(Array.isArray(v))result[k]='Array['+v.length+']';
            else if(typeof v==='object'&&v!==null)result[k]='obj';
            else result[k]=String(v).substring(0,30);
        }
        return result;
    })()""")
    print(f"  tni-business-range $data: {all_data}")

# ============================================================
# Step 7: 验证并保存
# ============================================================
print("\nStep 7: 验证并保存")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

bf = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}}}
        return null;
    }
    var comp=findComp(vm,'businese-info',0);
    if(!comp)return{error:'no_comp'};
    var form=comp.busineseForm||{};
    return{
        busiAreaDataLen:(form.busiAreaData||[]).length,
        sample:(form.busiAreaData||[]).length>0?JSON.stringify(form.busiAreaData[0]).substring(0,200):'empty',
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
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}}}
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
            if code == '0' or code == 0 or code == '0000':
                print("  ✅ 保存成功！")
        except:
            print(f"  raw: {r[:150]}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
