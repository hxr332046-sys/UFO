#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复4个验证错误: cascader/radio/select → 保存 → 下一步"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    ws = websocket.create_connection(ws_url, timeout=10)
    return ws

ws = get_ws()
_mid = 0
def ev(js, timeout=10):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    except:
        try: ws = get_ws()
        except: return None
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    for _ in range(30):
        try:
            ws.settimeout(timeout); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if not fc or fc.get('formCount',0) < 10:
    print("❌ 表单未加载")
    ws.close(); sys.exit()

# Step 1: 设置3个ElForm model
print("\nStep 1: 设置ElForm model")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findAllForms(vm,d){
        if(d>15)return[];
        var result=[];
        if(vm.$options?.name==='ElForm'&&vm.model&&Object.keys(vm.model).length>0)result.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)result=result.concat(findAllForms(vm.$children[i],d+1));
        return result;
    }
    var forms=findAllForms(vm,0);
    var results=[];
    for(var f=0;f<forms.length;f++){
        var form=forms[f];var model=form.model;var keys=Object.keys(model);
        if(keys.includes('registerCapital')){
            form.$set(model,'registerCapital','100');
            form.$set(model,'investMoney','100');
            form.$set(model,'moneyKindCode','156');
            form.$set(model,'moneyKindCodeName','人民币');
            form.$set(model,'shouldInvestWay','1');
            form.$set(model,'entPhone','13800138000');
            form.$set(model,'postcode','530022');
            form.$set(model,'busType','1');
            form.$set(model,'partnerNum','0');
            form.$set(model,'limitPartnerNum','0');
            form.$set(model,'accCapital','0');
            form.$set(model,'subCapital','0');
            form.$set(model,'foreignCapital','0');
            form.$set(model,'conGroUSD','0');
            form.$set(model,'regCapUSD','0');
            form.$set(model,'isBusinessRegMode','0');
            form.$set(model,'namePreFlag',false);
            results.push('basic');
        }
        if(keys.includes('businessArea')){
            form.$set(model,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            form.$set(model,'itemIndustryTypeCode','I65');
            form.$set(model,'industryTypeName','软件和信息技术服务业');
            form.$set(model,'multiIndustryName','软件和信息技术服务业');
            form.$set(model,'multiIndustry','I65');
            form.$set(model,'industryId','I65');
            form.$set(model,'zlBusinessInd','I65');
            form.$set(model,'busiAreaCode','I65');
            form.$set(model,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            form.$set(model,'busiAreaData',[{name:'软件开发',code:'I6511'},{name:'信息技术咨询服务',code:'I6531'}]);
            form.$set(model,'busiPeriod','1');
            form.$set(model,'busiDateEnd','');
            form.$set(model,'busiDateStart','');
            form.$set(model,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            form.$set(model,'areaCategory','');
            form.$set(model,'secretaryServiceEnt','0');
            results.push('scope');
        }
        if(keys.includes('distCode')){
            form.$set(model,'distCode','450103');
            form.$set(model,'distCodeName','青秀区');
            form.$set(model,'fisDistCode','450103');
            form.$set(model,'address','广西壮族自治区南宁市青秀区');
            form.$set(model,'detAddress','民族大道100号');
            form.$set(model,'isSelectDistCode','1');
            form.$set(model,'havaAdress','0');
            form.$set(model,'regionCode','450103');
            form.$set(model,'regionName','青秀区');
            form.$set(model,'businessAddress','广西壮族自治区南宁市青秀区');
            form.$set(model,'detBusinessAddress','民族大道100号');
            form.$set(model,'streetCode','');
            form.$set(model,'streetName','');
            form.$set(model,'regionStreetCode','');
            form.$set(model,'regionStreetName','');
            form.$set(model,'certificateDate','');
            form.$set(model,'sellByNet',null);
            form.$set(model,'code','');
            results.push('address');
        }
        form.clearValidate();
        form.$forceUpdate();
    }
    return{forms:forms.length,results:results};
})()""")
print(f"  result: {result}")

# Step 2: 设置cascader组件 - 企业住所和生产经营地址
print("\nStep 2: 设置cascader")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if((label.includes('企业住所')&&!label.includes('详细'))||(label.includes('生产经营地址')&&!label.includes('详细'))){
            // 找tne-data-cascader或el-cascader
            var cascader=items[i].querySelector('.el-cascader,[class*="cascader"],[class*="tne-data"]');
            if(cascader){
                var comp=cascader.__vue__;
                if(comp){
                    var val=['450000','450100','450103'];
                    comp.$emit('input',val);
                    comp.$emit('change',val);
                    comp.presentText='广西壮族自治区/南宁市/青秀区';
                }
            }
        }
    }
})()""")
time.sleep(1)

# Step 3: 设置经营期限radio
print("\nStep 3: 经营期限")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营期限')){
            var group=items[i].querySelector('.el-radio-group');
            if(group){
                var comp=group.__vue__;
                if(comp){comp.$emit('input','1');comp.$emit('change','1')}
            }
            var radios=items[i].querySelectorAll('.el-radio__input');
            for(var j=0;j<radios.length;j++){
                var text=radios[j].closest('.el-radio')?.textContent?.trim()||'';
                if(text.includes('长期')&&!radios[j].classList.contains('is-checked'))radios[j].click();
            }
        }
    }
})()""")
time.sleep(1)

# Step 4: 设置行业类型tne-select
print("\nStep 4: 行业类型")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(select){
                var comp=select.__vue__;
                if(comp){
                    comp.$emit('input','I65');
                    comp.$emit('change',{value:'I65',label:'软件和信息技术服务业'});
                    comp.selectedLabel='软件和信息技术服务业';
                }
            }
        }
    }
})()""")
time.sleep(1)

# Step 5: 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input.el-input__inner');
        if(!input||!input.offsetParent||input.disabled)continue;
        var val='';
        if(label.includes('注册资本'))val='100';
        else if(label.includes('从业人数'))val='5';
        else if(label.includes('执照副本'))val='1';
        else if(label.includes('联系电话'))val='13800138000';
        else if(label.includes('邮政编码'))val='530022';
        else if(label.includes('详细地址')&&!label.includes('生产经营'))val='民族大道100号';
        else if(label.includes('生产经营地详细'))val='民族大道100号';
        if(val){s.call(input,val);input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# Step 6: 验证
print("\nStep 6: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors: {errors}")

# Step 7: 保存
print("\nStep 7: 保存")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

save_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findFormComp(vm,0);
    if(comp&&typeof comp.save==='function'){comp.save(null,function(){},'working');return{called:true}}
    return{error:'no_save'};
})()""")
print(f"  save: {save_result}")
time.sleep(5)

# 检查API
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'getUserInfo' not in url and 'getCacheCreateTime' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        if l.get('status') == 200:
            try:
                resp = json.loads(l.get('response','{}'))
                print(f"    code={resp.get('code','')} msg={resp.get('msg','')[:30]}")
            except: pass

# Step 8: 检查保存后状态
errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"\n  errors after save: {errors2}")

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 9: 遍历步骤
print("\nStep 9: 遍历步骤")
for step in range(7):
    current = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findFormComp(vm,d){
            if(d>15)return null;
            if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
                var bdi=vm.$data.businessDataInfo;
                return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,curCompUrl:bdi.flowData?.currCompUrl||'',stepList:bdi.processVo?.stepList?.map(function(s){return s.stepName||s.name||''})||[]};
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
            return null;
        }
        return findFormComp(vm,0);
    })()""")
    if not current: break
    print(f"\n  步骤{step}: hash={current.get('hash','')} forms={current.get('formCount',0)} compUrl={current.get('curCompUrl','')}")
    if current.get('stepList'): print(f"    steps: {current.get('stepList',[])}")
    
    # 找下一步按钮
    btn = ev("""(function(){
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if((t.includes('保存并下一步')||t.includes('下一步'))&&btns[i].offsetParent!==null&&!btns[i].disabled)return{idx:i,text:t};
        }
        return null;
    })()""")
    if not btn: print("    无下一步按钮"); break
    print(f"    点击: {btn.get('text','')}")
    idx = btn.get('idx',0)
    ev(f"""(function(){{var btns=document.querySelectorAll('button,.el-button');if(btns[{idx}])btns[{idx}].click()}})()""")
    time.sleep(5)
    
    # 检查API
    api_logs2 = ev("window.__api_logs||[]")
    new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
    for l in new_apis[-3:]:
        url = l.get('url','')
        print(f"    API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
    api_logs = api_logs2

# 最终
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

ws.close()
print("✅ 完成")
