#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final12: 点击企业住所/生产经营地址input触发弹窗 → 处理区域选择 → select下拉 → 经营范围iframe"""
import json, time, os, requests, websocket, base64
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log, add_auth_finding

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)

_mid = 0
def ev(js, mid=None):
    global _mid
    if mid is None: mid = _mid + 1; _mid = mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
    for _ in range(20):
        try:
            ws.settimeout(15)
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                return r.get("result",{}).get("result",{}).get("value")
        except:
            return None
    return None

def screenshot(name):
    try:
        ws.send(json.dumps({"id":9900+hash(name)%100,"method":"Page.captureScreenshot","params":{"format":"png"}}))
        for _ in range(10):
            try:
                ws.settimeout(10);r=json.loads(ws.recv())
                if r.get("id",0)>=9900:
                    d=r.get("result",{}).get("data","")
                    if d:
                        p=os.path.join(os.path.dirname(__file__),"..","data",f"e2e_{name}.png")
                        with open(p,"wb") as f:f.write(base64.b64decode(d))
                        print(f"  📸 {p}")
                    break
            except:break
    except:pass

# 恢复token
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;
    if(store)store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);
    xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")

# ===== STEP 1: 分析企业住所input的Vue组件 =====
print("STEP 1: 分析企业住所input组件")
addr_comp = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    var r=[];
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(!label)continue;
        var lt=label.textContent?.trim()||'';
        if(lt.includes('住所')||lt.includes('生产经营地址')){
            var input=fi[i].querySelector('.el-input__inner');
            var ph=input?.placeholder||'';
            var comp=input?.__vue__;
            var parentComp=comp?.$parent;
            var grandComp=parentComp?.$parent;
            
            // 找有地址选择相关方法的组件
            var methods=[];
            var c=comp;
            for(var d=0;d<5&&c;d++){
                var m=Object.keys(c.$options?.methods||{});
                if(m.length>0)methods.push({depth:d,name:c.$options?.name||'',methods:m.slice(0,10)});
                c=c.$parent;
            }
            
            // 检查是否有弹出选择器的绑定
            var events=[];
            if(input){
                var vnode=input.__vnode||comp?.$vnode;
                // 检查click事件
                var listeners=comp?.$listeners||{};
                events=Object.keys(listeners);
            }
            
            r.push({
                idx:i,label:lt,ph:ph,
                compName:comp?.$options?.name||'',
                parentName:parentComp?.$options?.name||'',
                grandName:grandComp?.$options?.name||'',
                methods:methods,
                events:events,
                prop:fi[i].__vue__?.prop||''
            });
        }
    }
    return r;
})()""")
for a in (addr_comp or []):
    print(f"\n  {a.get('label','')}: ph={a.get('ph','')}")
    print(f"    compName: {a.get('compName','')}")
    print(f"    parentName: {a.get('parentName','')}")
    print(f"    grandName: {a.get('grandName','')}")
    print(f"    prop: {a.get('prop','')}")
    print(f"    methods: {a.get('methods',[])}")
    print(f"    events: {a.get('events',[])}")

# ===== STEP 2: 点击企业住所input，观察弹窗 =====
print("\nSTEP 2: 点击企业住所input")
# 找企业住所input并点击
click_result = ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('企业住所')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input){
                input.click();
                input.focus();
                // 也触发Vue组件的focus事件
                input.dispatchEvent(new Event('focus',{bubbles:true}));
                input.dispatchEvent(new Event('click',{bubbles:true}));
                return{clicked:true,ph:input.placeholder};
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click: {click_result}")
time.sleep(2)

# 检查弹出的内容
popup = ev("""(function(){
    // 检查所有可能弹出的元素
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    var popovers=document.querySelectorAll('.el-popover');
    var dropdowns=document.querySelectorAll('.el-select-dropdown,.el-cascader__dropdown,.el-popper');
    var regionPickers=document.querySelectorAll('[class*="region"],[class*="area"],[class*="address"],[class*="district"],[class*="picker"]');
    
    var result={dialogCount:0,popoverCount:0,dropdownCount:0,regionPickerCount:regionPickers.length};
    
    // 检查可见的dialog
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
            result.dialogCount++;
            result.dialogTitle=dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'';
            result.dialogBody=dialogs[i].querySelector('.el-dialog__body')?.innerHTML?.substring(0,200)||'';
        }
    }
    
    // 检查可见的popover
    for(var i=0;i<popovers.length;i++){
        if(popovers[i].offsetParent!==null||popovers[i].style?.display!=='none'){
            result.popoverCount++;
            result.popoverText=popovers[i].innerText?.trim()?.substring(0,200)||'';
        }
    }
    
    // 检查可见的dropdown
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null||dropdowns[i].style?.display!=='none'){
            result.dropdownCount++;
            result.dropdownText=dropdowns[i].innerText?.trim()?.substring(0,200)||'';
        }
    }
    
    // 检查region picker
    for(var i=0;i<regionPickers.length;i++){
        if(regionPickers[i].offsetParent!==null){
            result.regionPickerText=regionPickers[i].innerText?.trim()?.substring(0,200)||'';
            result.regionPickerClass=regionPickers[i].className?.substring(0,50)||'';
        }
    }
    
    // 也检查新增的DOM元素
    var allNew=document.querySelectorAll('[class*="area-select"],[class*="region-select"],[class*="address-select"],[class*="location"]');
    result.newElements=allNew.length;
    
    return result;
})()""")
print(f"  popup: {popup}")

# ===== STEP 3: 如果没有弹窗，尝试调用Vue组件方法 =====
if not popup or (popup.get('dialogCount',0)==0 and popup.get('popoverCount',0)==0 and popup.get('dropdownCount',0)==0):
    print("\nSTEP 3: 无弹窗，尝试Vue组件方法")
    # 找有地址选择方法的组件
    method_result = ev("""(function(){
        var fi=document.querySelectorAll('.el-form-item');
        for(var i=0;i<fi.length;i++){
            var label=fi[i].querySelector('.el-form-item__label');
            if(label&&label.textContent.trim().includes('企业住所')){
                var input=fi[i].querySelector('.el-input__inner');
                var comp=input?.__vue__;
                // 向上遍历找有selectRegion/openArea等方法
                var c=comp;
                for(var d=0;d<8&&c;d++){
                    var methods=Object.keys(c.$options?.methods||{});
                    var regionMethods=methods.filter(function(m){
                        return m.toLowerCase().includes('region')||m.toLowerCase().includes('area')||m.toLowerCase().includes('address')||m.toLowerCase().includes('select')||m.toLowerCase().includes('open')||m.toLowerCase().includes('pick')||m.toLowerCase().includes('choose')||m.toLowerCase().includes('domicile');
                    });
                    if(regionMethods.length>0){
                        return{depth:d,compName:c.$options?.name||'',regionMethods:regionMethods,allMethods:methods.slice(0,15)};
                    }
                    c=c.$parent;
                }
                return{error:'no_region_methods'};
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  method_result: {method_result}")
    
    # 如果找到方法，调用它
    if method_result and method_result.get('regionMethods'):
        for m in method_result.get('regionMethods',[]):
            print(f"  尝试调用 {m}...")
            result = ev(f"""(function(){{
                var fi=document.querySelectorAll('.el-form-item');
                for(var i=0;i<fi.length;i++){{
                    var label=fi[i].querySelector('.el-form-item__label');
                    if(label&&label.textContent.trim().includes('企业住所')){{
                        var input=fi[i].querySelector('.el-input__inner');
                        var comp=input?.__vue__;
                        var c=comp;
                        for(var d=0;d<8&&c;d++){{
                            if(typeof c.{m}==='function'){{
                                try{{c.{m}();return{{called:true,method:'{m}',depth:d}}}}catch(e){{return{{error:e.message,method:'{m}'}}}}
                            }}
                            c=c.$parent;
                        }}
                    }}
                }}
                return{{error:'method_not_found'}};
            }})()""")
            print(f"    result: {result}")
            if result and result.get('called'):
                time.sleep(2)
                # 检查弹窗
                popup2 = ev("""(function(){
                    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
                    for(var i=0;i<dialogs.length;i++){
                        if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
                            return{title:dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'',body:dialogs[i].querySelector('.el-dialog__body')?.innerHTML?.substring(0,300)||''};
                        }
                    }
                    var popovers=document.querySelectorAll('.el-popover,[class*="popper"]');
                    for(var i=0;i<popovers.length;i++){
                        if(popovers[i].offsetParent!==null){
                            return{type:'popover',text:popovers[i].innerText?.trim()?.substring(0,200)||''};
                        }
                    }
                    return{type:'none'};
                })()""")
                print(f"    popup2: {popup2}")
                break

# ===== STEP 4: 如果仍然没有弹窗，尝试直接通过API获取区域数据并设置 =====
print("\nSTEP 4: 通过API获取区域数据")
area_api = ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var apis=[
        '/icpsp-api/v4/pc/common/tools/getAreaList?parentCode=0',
        '/icpsp-api/v4/pc/common/tools/getAreaList?parentCode=450000',
        '/icpsp-api/v4/pc/common/tools/getAreaList?parentCode=450100',
        '/icpsp-api/v4/pc/common/tools/getAreaList?parentCode=450103',
    ];
    var results=[];
    for(var i=0;i<apis.length;i++){
        var xhr=new XMLHttpRequest();
        xhr.open('GET',apis[i],false);
        xhr.setRequestHeader('top-token',t);
        try{
            xhr.send();
            if(xhr.status===200){
                var resp=JSON.parse(xhr.responseText);
                var data=resp.data?.busiData||resp.data||[];
                var sample=Array.isArray(data)?data.slice(0,3).map(function(d){return{code:d.code||d.areaCode||d.id,name:d.name||d.areaName||d.label}}):[];
                results.push({api:apis[i].split('?')[0].split('/').pop(),status:xhr.status,sample:sample,count:Array.isArray(data)?data.length:0});
            }else{
                results.push({api:apis[i],status:xhr.status});
            }
        }catch(e){
            results.push({api:apis[i],error:e.message});
        }
    }
    return results;
})()""")
print(f"  area_api: {area_api}")

# ===== STEP 5: 如果API可用，直接设置表单数据 =====
if area_api and any(a.get('sample') for a in area_api if isinstance(a, dict)):
    print("\nSTEP 5: 设置表单区域数据")
    # 找到businessDataInfo中的地址字段
    set_addr = ev("""(function(){
        var app=document.getElementById('app');
        var vm=app?.__vue__;
        
        function findBDI(vm,depth){
            if(depth>10)return null;
            if(vm.$data?.businessDataInfo)return vm;
            var children=vm.$children||[];
            for(var i=0;i<children.length;i++){var r=findBDI(children[i],depth+1);if(r)return r}
            return null;
        }
        
        var inst=findBDI(vm,0);
        if(!inst)return{error:'no_bdi'};
        var bdi=inst.$data.businessDataInfo;
        
        // 列出所有字段
        var allKeys=Object.keys(bdi);
        var addrRelated=allKeys.filter(function(k){
            var kl=k.toLowerCase();
            return kl.includes('addr')||kl.includes('area')||kl.includes('domicile')||kl.includes('province')||kl.includes('city')||kl.includes('district')||kl.includes('region')||kl.includes('location')||kl.includes('place')||kl.includes('street');
        });
        
        // 获取每个地址相关字段的当前值
        var addrValues=addrRelated.map(function(k){return{key:k,val:JSON.stringify(bdi[k]).substring(0,50)}});
        
        return{addrRelated:addrRelated,addrValues:addrValues,allKeysCount:allKeys.length};
    })()""")
    print(f"  addr fields: {set_addr}")

# ===== STEP 6: 处理行业类型select（通过点击展开下拉）=====
print("\nSTEP 6: 处理行业类型select")
# 先点击select input展开
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input){
                input.click();
                input.dispatchEvent(new Event('focus',{bubbles:true}));
            }
        }
    }
})()""")
time.sleep(2)

# 检查下拉
dropdown = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null||dropdowns[i].style?.display!=='none'){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            var itemTexts=[];
            for(var j=0;j<Math.min(10,items.length);j++){
                itemTexts.push(items[j].textContent?.trim()||'');
            }
            return{visible:true,items:items.length,itemTexts:itemTexts};
        }
    }
    return{visible:false};
})()""")
print(f"  dropdown: {dropdown}")

if dropdown and dropdown.get('visible'):
    # 选择包含"信息"或"软件"的选项
    ev("""(function(){
        var dropdowns=document.querySelectorAll('.el-select-dropdown');
        for(var i=0;i<dropdowns.length;i++){
            if(dropdowns[i].offsetParent!==null||dropdowns[i].style?.display!=='none'){
                var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                for(var j=0;j<items.length;j++){
                    var t=items[j].textContent?.trim()||'';
                    if(t.includes('信息')||t.includes('软件')||t.includes('技术')){
                        items[j].click();
                        return{selected:t};
                    }
                }
                // 没找到就选第一个非disabled
                for(var j=0;j<items.length;j++){
                    if(!items[j].className?.includes('disabled')&&items[j].textContent?.trim()){
                        items[j].click();
                        return{selected:items[j].textContent?.trim()};
                    }
                }
            }
        }
    })()""")
    time.sleep(1)

# ===== STEP 7: 处理经营范围iframe =====
print("\nSTEP 7: 处理经营范围iframe")
# 找到iframe
iframe_info = ev("""(function(){
    var iframes=document.querySelectorAll('iframe');
    var r=[];
    for(var i=0;i<iframes.length;i++){
        r.push({idx:i,src:iframes[i].src||'',id:iframes[i].id||'',name:iframes[i].name||''});
    }
    return r;
})()""")
print(f"  iframes: {iframe_info}")

# 经营范围按钮可能打开iframe，需要先点击
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('添加')||t.includes('规范')){
                    btns[j].click();
                    return{clicked:t};
                }
            }
        }
    }
})()""")
time.sleep(3)

# 检查iframe内容
iframe_content = ev("""(function(){
    var iframes=document.querySelectorAll('iframe');
    for(var i=0;i<iframes.length;i++){
        try{
            var doc=iframes[i].contentDocument||iframes[i].contentWindow?.document;
            if(doc){
                return{html:doc.body?.innerHTML?.substring(0,300)||'',text:doc.body?.innerText?.trim()?.substring(0,200)||''};
            }
        }catch(e){
            return{error:'cross_origin',src:iframes[i].src};
        }
    }
    return{error:'no_iframe'};
})()""")
print(f"  iframe_content: {iframe_content}")

# ===== STEP 8: 最终验证 =====
print("\nSTEP 8: 保存并下一步")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

screenshot("step8_result")

# ===== 总结当前状态 =====
print("\n" + "=" * 60)
print("E2E 当前状态总结")
print("=" * 60)
print("""
已完成:
  ✅ LLM材料审核（补正后通过）
  ✅ 导航到设立登记表单（#/flow/base/basic-info，35字段）
  ✅ text input填写（企业名称、注册资本、详细地址、联系电话等）
  ✅ 认证检测：电子签名(signAuth)在所有步骤中检测到
  
未完成（需要手动操作或进一步研究）:
  ❌ 企业住所/生产经营地址：自定义区域选择器组件，CDP无法触发弹窗
  ❌ 行业类型：select下拉选项为空（懒加载未触发）
  ❌ 经营范围：在iframe中，跨域无法访问

建议:
  1. 这3个字段需要用户手动在浏览器中填写
  2. 或者需要研究区域选择器的API接口直接设置
  3. 填写完成后，脚本可以继续遍历步骤到提交页
""")

log("160.E2E状态总结", {
    "completed": ["LLM审核","导航到表单","text填写","认证检测:signAuth"],
    "blocked": ["企业住所(区域选择器)","行业类型(懒加载select)","经营范围(iframe)"],
    "authTypes": ["signAuth(电子签名)"],
    "errors": errs
})

ws.close()
print("\n✅ e2e_final12.py 完成")
