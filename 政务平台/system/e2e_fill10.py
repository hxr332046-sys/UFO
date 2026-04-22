#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设置3个ElForm的model字段 → 清除验证 → 保存"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# Step 1: 设置3个ElForm的model
print("\nStep 1: 设置3个ElForm")
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findAllForms(vm,d){
        if(d>15)return[];
        var result=[];
        if(vm.$options?.name==='ElForm'&&vm.model&&Object.keys(vm.model).length>0){
            result.push(vm);
        }
        for(var i=0;i<(vm.$children||[]).length;i++){
            result=result.concat(findAllForms(vm.$children[i],d+1));
        }
        return result;
    }
    var forms=findAllForms(vm,0);
    var results=[];
    
    for(var f=0;f<forms.length;f++){
        var form=forms[f];
        var model=form.model;
        var keys=Object.keys(model);
        
        // Form 1: 基本信息 (regOrg, investMoney, etc)
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
            results.push({form:f,type:'basic',keys:keys.length});
        }
        
        // Form 2: 经营范围 (businessArea, industryTypeCode, etc)
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
            form.$set(model,'busiAreaData',[]);
            form.$set(model,'busiPeriod','1');
            form.$set(model,'busiDateEnd','');
            form.$set(model,'busiDateStart','');
            form.$set(model,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
            form.$set(model,'areaCategory','');
            form.$set(model,'secretaryServiceEnt','0');
            form.$set(model,'xfz','');
            form.$set(model,'businessUuid','');
            results.push({form:f,type:'scope',keys:keys.length});
        }
        
        // Form 3: 地址 (distCode, address, etc)
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
            results.push({form:f,type:'address',keys:keys.length});
        }
        
        form.clearValidate();
        form.$forceUpdate();
    }
    
    return{forms:forms.length,results:results};
})()""")
print(f"  result: {result}")

# Step 2: 同步DOM
print("\nStep 2: 同步DOM")
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
    // textarea
    var tas=document.querySelectorAll('textarea');
    for(var i=0;i<tas.length;i++){
        var ph=tas[i].placeholder||'';
        if(ph.includes('经营范围')||tas[i].closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent?.includes('经营范围')){
            var s2=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
            s2.call(tas[i],'软件开发;信息技术咨询服务;数据处理和存储支持服务');
            tas[i].dispatchEvent(new Event('input',{bubbles:true}));
        }
    }
})()""")
time.sleep(1)

# 勾选radio
ev("""(function(){
    var radios=document.querySelectorAll('.el-radio__input:not(.is-checked)');
    var groups={};
    for(var i=0;i<radios.length;i++){
        var parent=radios[i].closest('.el-form-item');
        var label=parent?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(!groups[label]){groups[label]=true;radios[i].click()}
    }
})()""")
time.sleep(1)

# Step 3: 验证
print("\nStep 3: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors: {errors}")

# Step 4: 如果还有错误，逐个修复
if errors:
    print("\nStep 4: 修复剩余错误")
    # 逐个验证每个form
    for err in errors:
        print(f"  修复: {err}")
        if '企业住所' in err or '生产经营地址' in err:
            # 需要通过cascader组件设置
            ev("""(function(){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                    var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    if((label.includes('企业住所')&&!label.includes('详细'))||(label.includes('生产经营地址')&&!label.includes('详细'))){
                        // 找cascader或tne-data-cascader
                        var cascader=items[i].querySelector('.el-cascader,[class*="cascader"],[class*="data-cascader"]');
                        if(cascader){
                            var comp=cascader.__vue__;
                            if(comp){
                                var val=['450000','450100','450103'];
                                comp.$emit('input',val);
                                comp.$emit('change',val);
                                // 触发内部方法
                                if(typeof comp.handlePick==='function')comp.handlePick(val);
                                if(typeof comp.handleValueChange==='function')comp.handleValueChange(val);
                                comp.presentText='广西壮族自治区/南宁市/青秀区';
                            }
                        }
                        // 找tne-data-cascader
                        var tneCascader=items[i].querySelector('[class*="tne-data"]');
                        if(tneCascader){
                            var comp2=tneCascader.__vue__;
                            if(comp2){
                                comp2.$emit('input',['450000','450100','450103']);
                                comp2.$emit('change',['450000','450100','450103']);
                            }
                        }
                    }
                }
            })()""")
        elif '行业类型' in err:
            # 通过tne-select tree选择
            ev("""(function(){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                    var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    if(label.includes('行业类型')){
                        var select=items[i].querySelector('.el-select');
                        if(select){
                            var comp=select.__vue__;
                            if(comp){
                                // 创建选中项对象
                                var selectedOpt={label:'[I]信息传输、软件和信息技术服务业/[65]软件和信息技术服务业',value:'I65'};
                                comp.$emit('input','I65');
                                comp.$emit('change','I65');
                                comp.handleOptionSelect(selectedOpt);
                            }
                        }
                    }
                }
            })()""")
        elif '经营范围' in err:
            # 通过Vue组件方法打开对话框
            ev("""(function(){
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){
                    var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    if(label.includes('经营范围')){
                        var btns=items[i].querySelectorAll('button');
                        for(var j=0;j<btns.length;j++){
                            if(btns[j].textContent?.trim()?.includes('添加')){
                                btns[j].click();
                                break;
                            }
                        }
                    }
                }
            })()""")
    time.sleep(3)
    
    # 再次验证
    errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
    print(f"  errors after fix: {errors2}")

# Step 5: 尝试通过businessDataInfo组件保存
print("\nStep 5: 保存")
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
    if(comp&&typeof comp.save==='function'){
        comp.save(null,function(){},'working');
        return{called:true};
    }
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

# 检查验证错误
errors3 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  errors after save: {errors3}")

# 最终页面状态
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

ws.close()
print("✅ 完成")
