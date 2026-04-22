#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2E Final14: 精确分析tne-data-picker DOM → 精确点击 → select → 经营范围"""
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

# ===== STEP 1: 点击企业住所input触发picker =====
print("STEP 1: 触发企业住所picker")
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('企业住所')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
            return;
        }
    }
})()""")
time.sleep(2)

# ===== STEP 2: 精确分析picker DOM =====
print("\nSTEP 2: 精确分析picker DOM")
picker_dom = ev("""(function(){
    // 找到可见的picker viewer
    var viewers=document.querySelectorAll('.tne-data-picker-viewer');
    for(var i=0;i<viewers.length;i++){
        if(viewers[i].offsetParent!==null){
            // 获取完整HTML结构（前500字符）
            var html=viewers[i].innerHTML.substring(0,500);
            
            // 获取所有直接子元素
            var children=viewers[i].children;
            var childInfo=[];
            for(var j=0;j<children.length;j++){
                childInfo.push({
                    tag:children[j].tagName,
                    className:children[j].className?.substring(0,60)||'',
                    text:children[j].textContent?.trim()?.substring(0,50)||'',
                    childCount:children[j].children?.length||0
                });
            }
            
            // 找所有可点击的元素
            var clickables=viewers[i].querySelectorAll('[class*="item"],[class*="cell"],[class*="option"],[class*="node"],li,td');
            var clickableInfo=[];
            for(var j=0;j<Math.min(10,clickables.length);j++){
                clickableInfo.push({
                    tag:clickables[j].tagName,
                    className:clickables[j].className?.substring(0,60)||'',
                    text:clickables[j].textContent?.trim()?.substring(0,30)||'',
                    parentClass:clickables[j].parentElement?.className?.substring(0,30)||''
                });
            }
            
            return{html:html,childCount:children.length,childInfo:childInfo,clickableCount:clickables.length,clickableInfo:clickableInfo};
        }
    }
    return{error:'no_visible_viewer'};
})()""")
print(f"  html: {picker_dom.get('html','')[:300]}")
print(f"  childInfo: {picker_dom.get('childInfo',[])}")
print(f"  clickableInfo: {picker_dom.get('clickableInfo',[])}")

# ===== STEP 3: 也分析picker的父级结构 =====
print("\nSTEP 3: 分析picker父级")
picker_parent = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null||pickers[i].querySelector('.tne-data-picker-viewer')?.offsetParent!==null){
            var html=pickers[i].outerHTML.substring(0,800);
            // 获取所有class含item/cell/option的元素
            var all=pickers[i].querySelectorAll('*');
            var interesting=[];
            for(var j=0;j<all.length;j++){
                var cn=all[j].className||'';
                if(typeof cn==='string'&&(cn.includes('item')||cn.includes('cell')||cn.includes('option')||cn.includes('column')||cn.includes('group')||cn.includes('list')||cn.includes('panel')||cn.includes('wheel')||cn.includes('slot'))){
                    interesting.push({tag:all[j].tagName,class:cn.substring(0,50),text:all[j].textContent?.trim()?.substring(0,30)||'',children:all[j].children.length});
                }
            }
            return{tag:pickers[i].tagName,class:pickers[i].className,interesting:interesting.slice(0,20)};
        }
    }
    return{error:'no_picker'};
})()""")
for item in (picker_parent.get('interesting') or []):
    print(f"  {item.get('tag','')}.{item.get('class','')[:40]} text={item.get('text','')[:20]} children={item.get('children',0)}")

# ===== STEP 4: 尝试精确点击picker中的广西 =====
print("\nSTEP 4: 精确点击picker")
# 根据DOM分析结果，用精确选择器
click_gx = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        var viewer=pickers[i].querySelector('.tne-data-picker-viewer');
        if(!viewer||viewer.offsetParent===null)continue;
        
        // 方法1: 找所有含"广西"文本的元素并点击
        var all=viewer.querySelectorAll('*');
        for(var j=0;j<all.length;j++){
            var t=all[j].textContent?.trim()||'';
            if(t==='广西壮族自治区'||t==='广西'){
                // 找到最小包含元素
                if(all[j].children.length===0||all[j].tagName==='SPAN'||all[j].tagName==='DIV'){
                    all[j].click();
                    all[j].dispatchEvent(new Event('click',{bubbles:true}));
                    return{method:'direct_click',text:t,tag:all[j].tagName,class:all[j].className};
                }
            }
        }
        
        // 方法2: 通过Vue组件方法
        var comp=viewer.__vue__||pickers[i].__vue__;
        if(comp){
            var methods=Object.keys(comp.$options?.methods||{});
            var selectMethods=methods.filter(function(m){return m.includes('select')||m.includes('pick')||m.includes('choose')||m.includes('click')||m.includes('change')||m.includes('handle')});
            if(selectMethods.length>0){
                return{method:'vue',methods:selectMethods,compName:comp.$options?.name};
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  click_gx: {click_gx}")
time.sleep(2)

# 检查picker是否更新
picker_after = ev("""(function(){
    var viewers=document.querySelectorAll('.tne-data-picker-viewer');
    for(var i=0;i<viewers.length;i++){
        if(viewers[i].offsetParent!==null){
            return{text:viewers[i].textContent?.trim()?.substring(0,100)||''};
        }
    }
    return{error:'no_viewer'};
})()""")
print(f"  picker_after: {picker_after}")

# ===== STEP 5: 如果直接点击不生效，尝试通过picker的Vue组件 =====
print("\nSTEP 5: 分析picker Vue组件")
picker_vue = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        var comp=pickers[i].__vue__;
        if(!comp)continue;
        
        var data=comp.$data||{};
        var dataKeys=Object.keys(data);
        var props=comp.$props||{};
        var propKeys=Object.keys(props);
        var methods=Object.keys(comp.$options?.methods||{});
        var computed=Object.keys(comp.$options?.computed||{});
        var watch=Object.keys(comp.$options?.watch||{});
        
        // 获取value相关
        var valueKeys=dataKeys.filter(function(k){return k.includes('value')||k.includes('Value')||k.includes('selected')||k.includes('Selected')||k.includes('current')||k.includes('Current')||k.includes('active')||k.includes('Active')});
        var valueData={};
        for(var j=0;j<valueKeys.length;j++){
            valueData[valueKeys[j]]=JSON.stringify(data[valueKeys[j]])?.substring(0,50);
        }
        
        return{
            compName:comp.$options?.name||'',
            dataKeys:dataKeys.slice(0,20),
            valueData:valueData,
            propKeys:propKeys.slice(0,10),
            methods:methods.slice(0,20),
            computed:computed.slice(0,10),
            watch:watch.slice(0,10)
        };
    }
    return{error:'no_vue_comp'};
})()""")
print(f"  compName: {picker_vue.get('compName','')}")
print(f"  dataKeys: {picker_vue.get('dataKeys',[])}")
print(f"  valueData: {picker_vue.get('valueData',{})}")
print(f"  methods: {picker_vue.get('methods',[])}")
print(f"  props: {picker_vue.get('propKeys',[])}")

# ===== STEP 6: 通过Vue组件方法选择区域 =====
if picker_vue and picker_vue.get('methods'):
    print("\nSTEP 6: 通过Vue方法选择区域")
    # 尝试调用select/change方法
    for method in ['handleSelect','selectItem','onSelect','handleChange','onChange','pick','choose']:
        if method in (picker_vue.get('methods') or []):
            print(f"  尝试 {method}...")
            result = ev(f"""(function(){{
                var pickers=document.querySelectorAll('.tne-data-picker');
                for(var i=0;i<pickers.length;i++){{
                    var comp=pickers[i].__vue__;
                    if(comp&&typeof comp.{method}==='function'){{
                        try{{
                            // 获取options
                            var opts=comp.$data?.options||comp.$data?.columns||comp.$data?.list||comp.options||[];
                            if(opts.length>0){{
                                comp.{method}(opts[0]);
                                return{{called:true,method:'{method}',optCount:opts.length}};
                            }}
                            // 尝试带广西参数
                            comp.{method}({{value:'450000',label:'广西壮族自治区'}});
                            return{{called:true,method:'{method}',param:'guangxi'}};
                        }}catch(e){{
                            return{{error:e.message,method:'{method}'}};
                        }}
                    }}
                }}
                return{{error:'method_not_found'}};
            }})()""")
            print(f"    result: {result}")
            time.sleep(1)

# ===== STEP 7: 如果Vue方法也不行，尝试直接设置数据 =====
print("\nSTEP 7: 直接设置picker数据")
set_data = ev("""(function(){
    var Vue=window.Vue||document.getElementById('app')?.__vue__?.constructor;
    var pickers=document.querySelectorAll('.tne-data-picker');
    for(var i=0;i<pickers.length;i++){
        var comp=pickers[i].__vue__;
        if(!comp)continue;
        var data=comp.$data;
        
        // 找value/selected/current相关字段
        var results=[];
        for(var k in data){
            var kl=k.toLowerCase();
            if(kl.includes('value')||kl.includes('selected')||kl.includes('current')||kl.includes('active')||kl.includes('result')||kl.includes('picked')){
                var old=JSON.stringify(data[k])?.substring(0,50);
                // 尝试设置
                if(Array.isArray(data[k])){
                    Vue.set(data,k,['450000','450100','450103']);
                    results.push({key:k,old:old,new:JSON.stringify(data[k]).substring(0,50)});
                }else if(typeof data[k]==='string'||data[k]===null){
                    Vue.set(data,k,'450103');
                    results.push({key:k,old:old,new:data[k]});
                }
            }
        }
        
        if(results.length>0){
            comp.$forceUpdate();
            return{results:results};
        }
    }
    return{error:'no_data_set'};
})()""")
print(f"  set_data: {set_data}")
time.sleep(2)

# 关闭picker
ev("document.body.click()")
time.sleep(1)

# ===== STEP 8: 处理行业类型 =====
print("\nSTEP 8: 行业类型select")
# 点击select
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('行业类型')){
            var input=fi[i].querySelector('.el-input__inner');
            if(input)input.click();
        }
    }
})()""")
time.sleep(2)

# 检查dropdown内容
dropdown = ev("""(function(){
    var dropdowns=document.querySelectorAll('.el-select-dropdown');
    for(var i=0;i<dropdowns.length;i++){
        if(dropdowns[i].offsetParent!==null){
            var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
            var r=[];
            for(var j=0;j<items.length;j++){
                var t=items[j].textContent?.trim()||'';
                var disabled=items[j].className?.includes('disabled')||false;
                if(t)r.push({idx:j,text:t.substring(0,40),disabled:disabled});
            }
            return{visible:true,items:r};
        }
    }
    return{visible:false};
})()""")
print(f"  dropdown: {dropdown}")

if dropdown and dropdown.get('visible'):
    # 选择[I]信息传输
    for item in (dropdown.get('items') or []):
        if not item.get('disabled') and ('[I]' in item.get('text','') or '信息传输' in item.get('text','')):
            idx = item.get('idx',0)
            print(f"  选择: {item.get('text','')[:30]}")
            ev(f"""(function(){{
                var dropdowns=document.querySelectorAll('.el-select-dropdown');
                for(var i=0;i<dropdowns.length;i++){{
                    if(dropdowns[i].offsetParent!==null){{
                        var items=dropdowns[i].querySelectorAll('.el-select-dropdown__item');
                        if(items[{idx}])items[{idx}].click();
                    }}
                }}
            }})()""")
            time.sleep(1)
            break

# ===== STEP 9: 经营范围 =====
print("\nSTEP 9: 经营范围")
# 点击添加按钮
ev("""(function(){
    var fi=document.querySelectorAll('.el-form-item');
    for(var i=0;i<fi.length;i++){
        var label=fi[i].querySelector('.el-form-item__label');
        if(label&&label.textContent.trim().includes('经营范围')){
            var btns=fi[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')||btns[j].textContent?.trim()?.includes('规范')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# 检查弹出的picker
scope_picker = ev("""(function(){
    var pickers=document.querySelectorAll('.tne-data-picker');
    var visible=[];
    for(var i=0;i<pickers.length;i++){
        if(pickers[i].offsetParent!==null){
            var text=pickers[i].textContent?.trim()?.substring(0,100)||'';
            var comp=pickers[i].__vue__;
            visible.push({idx:i,text:text,compName:comp?.$options?.name||'',methods:comp?Object.keys(comp.$options?.methods||{}).slice(0,10):[]});
        }
    }
    // 也检查dialog
    var dialogs=document.querySelectorAll('.el-dialog__wrapper');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null){
            visible.push({type:'dialog',title:dialogs[i].querySelector('.el-dialog__title')?.textContent?.trim()||'',text:dialogs[i].querySelector('.el-dialog__body')?.textContent?.trim()?.substring(0,100)||''});
        }
    }
    return visible;
})()""")
print(f"  scope_picker: {scope_picker}")

# ===== STEP 10: 验证 =====
print("\nSTEP 10: 验证")
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('保存并下一步')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

errs = ev("""(function(){var msgs=document.querySelectorAll('.el-form-item__error,.el-message');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80&&t.length>2)r.push(t)}return r.slice(0,10)})()""")
page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  errors: {errs}")
print(f"  hash={page.get('hash')} forms={page.get('formCount',0)}")

screenshot("step10_result")

log("180.最终验证", {"errors":errs,"hash":page.get('hash'),"formCount":page.get('formCount',0)})

ws.close()
print("\n✅ e2e_final14.py 完成")
