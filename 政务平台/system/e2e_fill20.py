#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过flow-control组件填写表单 + 经营范围"""
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

# 获取flow-control组件
def get_fc():
    return ev("""(function(){
        var app=document.getElementById('app');var vm=app.__vue__;
        return vm.$children[0].$children[0].$children[1].$children[0];
    })()""")

# ============================================================
# Step 1: 检查当前businessDataInfo状态
# ============================================================
print("Step 1: businessDataInfo状态")
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var bdi=fc.$data.businessDataInfo;
    if(!bdi)return{error:'no_bdi'};
    var important=['entName','entType','entTypeName','registerCapital','busType','shouldInvestWay',
        'entPhone','postcode','distCode','distCodeName','address','detAddress',
        'regionCode','businessAddress','detBusinessAddress',
        'itemIndustryTypeCode','industryTypeName','businessArea','busiAreaCode',
        'busiPeriod','busiDateEnd','multiIndustry','industryId',
        'isSelectDistCode','havaAdress','isBusinessRegMode',
        'secretaryServiceEnt','namePreFlag','partnerNum','fisDistCode'];
    var result={};
    for(var i=0;i<important.length;i++){
        var k=important[i];
        result[k]=bdi[k]===null||bdi[k]===undefined?'null':String(bdi[k]).substring(0,40);
    }
    return result;
})()""")
print(f"  bdi: {bdi}")

# ============================================================
# Step 2: 填写缺失字段
# ============================================================
print("\nStep 2: 填写缺失字段")
ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    var bdi=fc.$data.businessDataInfo;
    
    // 企业类型 (1100=有限责任公司)
    fc.$set(bdi,'entType','1100');
    fc.$set(bdi,'entTypeName','有限责任公司');
    
    // 注册资本
    fc.$set(bdi,'registerCapital','100');
    fc.$set(bdi,'registerCapitalName','100万元');
    fc.$set(bdi,'shouldInvestWay','1'); // 货币
    
    // 联系电话
    fc.$set(bdi,'entPhone','13800138000');
    
    // 邮政编码
    fc.$set(bdi,'postcode','530000');
    
    // 住所
    fc.$set(bdi,'distCode','450103');
    fc.$set(bdi,'distCodeName','青秀区');
    fc.$set(bdi,'fisDistCode','450103');
    fc.$set(bdi,'address','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detAddress','民族大道100号');
    fc.$set(bdi,'isSelectDistCode','1');
    fc.$set(bdi,'havaAdress','0');
    
    // 生产经营地址
    fc.$set(bdi,'regionCode','450103');
    fc.$set(bdi,'regionName','青秀区');
    fc.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detBusinessAddress','民族大道100号');
    
    // 行业类型
    fc.$set(bdi,'itemIndustryTypeCode','I65');
    fc.$set(bdi,'industryTypeName','软件和信息技术服务业');
    fc.$set(bdi,'multiIndustry','I65');
    fc.$set(bdi,'multiIndustryName','软件和信息技术服务业');
    fc.$set(bdi,'industryId','I65');
    fc.$set(bdi,'zlBusinessInd','I65');
    fc.$set(bdi,'busiAreaCode','I65');
    
    // 经营期限
    fc.$set(bdi,'busiPeriod','01'); // 长期
    fc.$set(bdi,'busiDateEnd','');
    
    // 其他
    fc.$set(bdi,'isBusinessRegMode','0');
    fc.$set(bdi,'secretaryServiceEnt','0');
    fc.$set(bdi,'namePreFlag','1');
    fc.$set(bdi,'partnerNum','1');
    
    fc.$forceUpdate();
    return 'set';
})()""")

# 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('联系电话')){s.call(input,'13800138000');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('邮政编码')){s.call(input,'530000');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('注册资本')){s.call(input,'100');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 3: 设置企业类型下拉
# ============================================================
print("\nStep 3: 企业类型")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业类型')){
            var select=items[i].querySelector('.el-select');
            if(select){
                var comp=select.__vue__;
                comp.$emit('input','1100');
                comp.selectedLabel='有限责任公司';
            }
            return;
        }
    }
})()""")

# ============================================================
# Step 4: 设置住所cascader
# ============================================================
print("\nStep 4: 住所cascader")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业住所')&&!label.includes('详细')){
            var cascader=items[i].querySelector('.tne-data-picker');
            if(cascader){
                var comp=cascader.__vue__;
                comp.$emit('input',['450000','450100','450103']);
                comp.$set(comp.$data,'selected',[
                    {allName:'广西壮族自治区',id:'450000',isStreet:'N',value:'450000',text:'广西壮族自治区'},
                    {allName:'南宁市',id:'450100',parentId:'450000',isStreet:'N',value:'450100',text:'南宁市'},
                    {allName:'南宁市青秀区',id:'450103',parentId:'450100',isStreet:'N',value:'450103',text:'青秀区'}
                ]);
                comp.$set(comp.$data,'inputSelected',comp.$data.selected);
            }
            return;
        }
    }
})()""")

# ============================================================
# Step 5: 经营范围 - 通过tni-business-range
# ============================================================
print("\nStep 5: 经营范围")

# 找tni-business-range组件
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
    var sl=(comp.searchList||comp.$data?.searchList||[]).length;
    var al=(comp.allBusinessList||comp.$data?.allBusinessList||[]).length;
    var il=(comp.industryList||comp.$data?.industryList||[]).length;
    var sel=(comp.selectedList||comp.$data?.selectedList||[]).length;
    var refs=Object.keys(comp.$refs||{});
    var methods=Object.keys(comp.$options?.methods||{});
    return{searchListLen:sl,allBusinessListLen:al,industryListLen:il,selectedListLen:sel,refs:refs,methods:methods};
})()""")
print(f"  tni-business-range: {tbr}")

# 如果allBusinessList为空，调用init
if isinstance(tbr, dict) and tbr.get('allBusinessListLen', 0) == 0:
    print("  加载经营范围列表...")
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
        if(typeof comp.init==='function')comp.init();
        else if(typeof comp.initOptions==='function')comp.initOptions();
        else if(typeof comp.getAllBusinessList==='function')comp.getAllBusinessList();
    })()""")
    time.sleep(4)

# 搜索"软件开发"
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
            return;
        }
    }
    var el=comp.$el;
    var inputs=el.querySelectorAll('input');
    for(var i=0;i<inputs.length;i++){
        var ph=inputs[i].placeholder||'';
        if(ph.includes('搜索')||ph.includes('关键词')||ph.includes('检索')){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputs[i],'软件开发');
            inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
            return;
        }
    }
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
    if(items.length===0){
        var al=comp.allBusinessList||comp.$data?.allBusinessList||[];
        for(var i=0;i<al.length;i++){
            var cat=al[i];
            if(cat.id==='I'&&cat.list){
                for(var j=0;j<cat.list.length;j++){
                    if(cat.list[j].id==='65'){
                        var sub65=cat.list[j];
                        var children=sub65.children||sub65.list||[];
                        for(var k=0;k<children.length;k++){
                            var ch=children[k];
                            if(ch.name==='软件开发'||ch.name==='信息技术咨询服务'){
                                items.push(JSON.parse(JSON.stringify(ch)));
                            }
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
if isinstance(search_items, list) and len(search_items) > 0:
    for it in search_items[:3]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:100]}")
    
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
    print(f"  confirm: {len(search_items)}项")
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
# Step 6: 验证
# ============================================================
print("\nStep 6: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 7: 保存草稿
# ============================================================
print("\nStep 7: 保存草稿")

ev("""(function(){
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

ev("""(function(){
    var app=document.getElementById('app');var vm=app.__vue__;
    var fc=vm.$children[0].$children[0].$children[1].$children[0];
    try{fc.save(null,null,'working')}catch(e){return e.message}
})()""", timeout=15)
time.sleep(5)

resp = ev("window.__save_result")
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
