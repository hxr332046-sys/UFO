#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用递归findComp访问组件 + 完整填写 + 保存"""
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

# 通用findComp函数（注入到页面）
FIND_COMP = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: initData + 基础字段
# ============================================================
print("Step 1: initData + 基础字段")
ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    if(typeof fc.initData==='function')fc.initData();
    var bdi=fc.$data.businessDataInfo;
    if(!bdi)return'no_bdi';
    fc.$set(bdi,'entName','广西智信数据科技有限公司');
    fc.$set(bdi,'entPhone','13800138000');
    fc.$set(bdi,'postcode','530000');
    fc.$set(bdi,'registerCapital','100');
    fc.$set(bdi,'shouldInvestWay','1');
    fc.$set(bdi,'detAddress','民族大道100号');
    fc.$set(bdi,'detBusinessAddress','民族大道100号');
    fc.$set(bdi,'isSelectDistCode','1');
    fc.$set(bdi,'havaAdress','0');
    fc.$set(bdi,'isBusinessRegMode','0');
    fc.$set(bdi,'secretaryServiceEnt','0');
    fc.$set(bdi,'namePreFlag','1');
    fc.$set(bdi,'partnerNum','1');
    fc.$forceUpdate();
    return'ok';
})()""")
time.sleep(2)

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
        if(label.includes('详细地址')&&label.includes('住所')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
        if(label.includes('详细地址')&&label.includes('经营')){s.call(input,'民族大道100号');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 2: 行业类型 - 通过businese-info
# ============================================================
print("\nStep 2: 行业类型")
bi_check = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{error:'no_bi'};
    var form=bi.busineseForm||{};
    bi.$set(form,'itemIndustryTypeCode','I65');
    bi.$set(form,'industryTypeName','软件和信息技术服务业');
    // indSelectTree ref
    var tree=bi.$refs?.indSelectTree;
    if(tree){
        tree.valueId='I65';
        tree.valueTitle='软件和信息技术服务业';
        bi.treeSelectChange('ind');
    }
    bi.$forceUpdate();
    return{itemIndustryTypeCode:form.itemIndustryTypeCode,industryTypeName:form.industryTypeName};
})()""")
print(f"  businese-info: {bi_check}")

# ============================================================
# Step 3: 经营范围 - 通过tni-business-range
# ============================================================
print("\nStep 3: 经营范围")

# 初始化tni-business-range
tbr_init = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return{error:'no_tbr'};
    var al=(tbr.allBusinessList||tbr.$data?.allBusinessList||[]).length;
    var sl=(tbr.searchList||tbr.$data?.searchList||[]).length;
    if(al===0&&sl===0){
        if(typeof tbr.init==='function')tbr.init();
        else if(typeof tbr.initOptions==='function')tbr.initOptions();
        else if(typeof tbr.getAllBusinessList==='function')tbr.getAllBusinessList();
        return{called:true,allBusinessListLen:al,searchListLen:sl};
    }
    return{called:false,allBusinessListLen:al,searchListLen:sl};
})()""")
print(f"  tbr init: {tbr_init}")
time.sleep(4)

# 搜索"软件开发"
ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return;
    var si=tbr.$refs?.searchInput;
    if(si){
        var inputEl=si.$el?.querySelector('input');
        if(inputEl){
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputEl,'软件开发');
            inputEl.dispatchEvent(new Event('input',{bubbles:true}));
            return;
        }
    }
    var el=tbr.$el;
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
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return[];
    var sl=tbr.searchList||tbr.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){
        var name=sl[i].name||'';
        if(name==='软件开发'||name==='信息技术咨询服务'||name.includes('数据处理和存储'))
            items.push(JSON.parse(JSON.stringify(sl[i])));
    }
    if(items.length===0){
        var al=tbr.allBusinessList||tbr.$data?.allBusinessList||[];
        for(var i=0;i<al.length;i++){
            var cat=al[i];
            if(cat.id==='I'&&cat.list){
                for(var j=0;j<cat.list.length;j++){
                    if(cat.list[j].id==='65'){
                        var sub65=cat.list[j];
                        var children=sub65.children||sub65.list||[];
                        for(var k=0;k<children.length;k++){
                            var ch=children[k];
                            if(ch.name==='软件开发'||ch.name==='信息技术咨询服务')items.push(JSON.parse(JSON.stringify(ch)));
                            var deep=ch.children||ch.list||[];
                            for(var l=0;l<deep.length;l++){
                                if(deep[l].name==='软件开发'||deep[l].name==='信息技术咨询服务')items.push(JSON.parse(JSON.stringify(deep[l])));
                            }
                        }
                    }
                }
            }
        }
    }
    return items;
})()""", timeout=12)

print(f"  搜索: {len(search_items) if isinstance(search_items,list) else search_items}项")
if isinstance(search_items, list) and len(search_items) > 0:
    for it in search_items[:3]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:80]}")
    search_items[0]['isMainIndustry'] = '1'
    search_items[0]['stateCo'] = '3'
    for i in range(1, len(search_items)):
        search_items[i]['isMainIndustry'] = '0'
        if search_items[i].get('stateCo') != '3': search_items[i]['stateCo'] = '1'
    names = ';'.join([it.get('name','') for it in search_items])
    confirm_data = {'busiAreaData': search_items, 'genBusiArea': names, 'busiAreaCode': 'I65', 'busiAreaName': names}
    confirm_json = json.dumps(confirm_data, ensure_ascii=False)
    confirm_js = '(function(){var vm=document.getElementById("app").__vue__;function findComp(vm,name,d){if(d>20)return null;var n=vm.$options&&vm.$options.name||"";if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var bi=findComp(vm,"businese-info",0);if(!bi)return;bi.confirm(' + confirm_json + ');})()'
    ev(confirm_js)
    print(f"  confirm: {len(search_items)}项, {names[:40]}")
else:
    print("  用已知格式confirm")
    ev("""(function(){
        var vm=document.getElementById('app').__vue__;
        function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var bi=findComp(vm,'businese-info',0);
        if(!bi)return;
        bi.confirm({
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
# Step 4: 住所 - 通过residence-information
# ============================================================
print("\nStep 4: 住所")
ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return;
    var form=ri.$data?.residenceForm||ri.residenceForm||{};
    if(form){
        ri.$set(form,'distCode','450103');
        ri.$set(form,'distCodeName','青秀区');
        ri.$set(form,'address','广西壮族自治区/南宁市/青秀区');
        ri.$set(form,'detAddress','民族大道100号');
    }
    ri.$forceUpdate();
})()""")

# ============================================================
# Step 5: 验证
# ============================================================
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

bf = ev("""(function(){
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{error:'no_bi'};
    var form=bi.busineseForm||{};
    return{
        itemIndustryTypeCode:form.itemIndustryTypeCode||'',
        industryTypeName:form.industryTypeName||'',
        busiAreaDataLen:(form.busiAreaData||[]).length,
        genBusiArea:form.genBusiArea?.substring(0,30)||'',
        busiAreaCode:form.busiAreaCode||''
    };
})()""")
print(f"  busineseForm: {bf}")

# ============================================================
# Step 6: 保存草稿
# ============================================================
print("\nStep 6: 保存草稿")

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
    var vm=document.getElementById('app').__vue__;
    function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var fc=findComp(vm,'flow-control',0);
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
