#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深度分析表单组件 → Vue方法设置行业类型 → 打开经营范围对话框 → 填写所有字段"""
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

# Step 1: 找到包含businessDataInfo的组件及其完整方法列表
print("\nStep 1: 深度分析表单组件")
comp_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var methods=vm.$options?.methods||{};
            var methodSrcs={};
            for(var m in methods){
                var src=methods[m].toString();
                // 只保留关键方法
                if(src.includes('industry')||src.includes('Industry')||src.includes('business')||src.includes('Business')||
                   src.includes('scope')||src.includes('Scope')||src.includes('save')||src.includes('Save')||
                   src.includes('next')||src.includes('Next')||src.includes('submit')||src.includes('Submit')||
                   src.includes('handle')||src.includes('Handle')||src.includes('select')||src.includes('Select')||
                   src.includes('load')||src.includes('Load')||src.includes('init')||src.includes('Init')||
                   src.includes('set')||src.includes('Set')||src.includes('update')||src.includes('Update')||
                   src.includes('open')||src.includes('Open')||src.includes('add')||src.includes('Add')||
                   src.includes('widget')||src.includes('Widget')||src.includes('step')||src.includes('Step')){
                    methodSrcs[m]=src.substring(0,300);
                }
            }
            return{
                compName:vm.$options?.name||'',
                parentName:vm.$parent?.$options?.name||'',
                methods:Object.keys(methods),
                keyMethods:Object.keys(methodSrcs),
                methodSrcs:methodSrcs,
                bdiKeys:Object.keys(vm.$data.businessDataInfo).slice(0,30),
                flowDataKeys:vm.$data.businessDataInfo.flowData?Object.keys(vm.$data.businessDataInfo.flowData).slice(0,30):[]
            };
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  compName: {comp_info.get('compName','') if comp_info else 'None'}")
print(f"  parentName: {comp_info.get('parentName','') if comp_info else ''}")
print(f"  methods: {comp_info.get('methods',[]) if comp_info else []}")
print(f"  keyMethods: {comp_info.get('keyMethods',[]) if comp_info else []}")
print(f"  bdiKeys: {comp_info.get('bdiKeys',[]) if comp_info else []}")
print(f"  flowDataKeys: {comp_info.get('flowDataKeys',[]) if comp_info else []}")

# 打印关键方法源码
for m, src in (comp_info.get('methodSrcs',{}) or {}).items():
    if 'industry' in m.lower() or 'business' in m.lower() or 'scope' in m.lower() or 'widget' in m.lower() or 'save' in m.lower() or 'next' in m.lower() or 'step' in m.lower():
        print(f"\n  {m}: {src[:200]}")

# Step 2: 分析行业类型el-select的Vue组件链
print("\nStep 2: 行业类型组件链")
industry_comp = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 向上找form-item组件
            var formItem=items[i].__vue__;
            var prop=formItem?.prop||formItem?.$props?.prop||'';
            
            // 分析tne-select的tree配置
            var treeData=comp.treeData||comp.data||[];
            var treeProps=comp.treeProps||comp.props||{};
            
            // 获取el-form的model
            var formComp=null;
            var current=comp;
            for(var d=0;d<10&&current;d++){
                if(current.$options?.name==='ElForm'||current.$el?.classList?.contains('el-form')){
                    formComp=current;break;
                }
                current=current.$parent;
            }
            var model=formComp?.model?Object.keys(formComp.model).slice(0,20):[];
            
            return{
                selectCompName:comp.$options?.name||'',
                prop:prop,
                value:comp.value||'',
                treeDataLen:Array.isArray(treeData)?treeData.length:0,
                treeDataSample:Array.isArray(treeData)&&treeData.length>0?JSON.stringify(treeData[0]).substring(0,100):'none',
                treeProps:JSON.stringify(treeProps)?.substring(0,100)||'none',
                lazy:comp.lazy||false,
                modelKeys:model,
                formModelProp:formComp?.model?.[prop]||'undefined'
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  industry_comp: {industry_comp}")

# Step 3: 通过el-form model设置行业类型
print("\nStep 3: 设置行业类型")
# 找到el-form model并直接设置
set_industry = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var formItem=items[i].__vue__;
            var prop=formItem?.prop||'';
            
            // 找el-form
            var formComp=null;
            var current=formItem;
            for(var d=0;d<10&&current;d++){
                if(current.$options?.name==='ElForm'||current.$el?.classList?.contains('el-form')){
                    formComp=current;break;
                }
                current=current.$parent;
            }
            
            if(formComp&&formComp.model&&prop){
                // 设置行业类型值
                var val='I65';  // 信息传输、软件和信息技术服务业
                formComp.$set(formComp.model,prop,val);
                formComp.$emit('validate',prop);
                formComp.validateField(prop);
                
                // 也设置select组件
                var select=items[i].querySelector('.el-select');
                var selectComp=select?.__vue__;
                if(selectComp){
                    selectComp.$emit('input',val);
                    selectComp.$emit('change',val);
                    selectComp.value=val;
                }
                
                return{set:true,prop:prop,value:val,modelKeys:Object.keys(formComp.model).slice(0,20)};
            }
            return{error:'no_form',prop:prop};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  set_industry: {set_industry}")

# Step 4: 填写所有businessDataInfo字段
print("\nStep 4: 填写businessDataInfo")
fill = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            return vm;
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findFormComp(vm,0);
    if(!comp)return{error:'no_comp'};
    var bdi=comp.$data.businessDataInfo;
    var fd=bdi.flowData||{};
    
    // 设置flowData字段
    comp.$set(fd,'entName','广西智信数据科技有限公司');
    comp.$set(fd,'regCap','100');
    comp.$set(fd,'empNum','5');
    comp.$set(fd,'licCopyNum','1');
    comp.$set(fd,'tel','13800138000');
    comp.$set(fd,'postalCode','530022');
    comp.$set(fd,'detailAddr','民族大道100号');
    comp.$set(fd,'proDetailAddr','民族大道100号');
    comp.$set(fd,'setUpMode','1');
    comp.$set(fd,'accountMethod','1');
    comp.$set(fd,'operTermType','1');
    comp.$set(fd,'isNeedPaperLic','0');
    comp.$set(fd,'isFreeTrade','0');
    comp.$set(fd,'industryType','I65');
    comp.$set(fd,'industryBigType','I');
    comp.$set(fd,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    
    // 设置bdi顶层字段
    comp.$set(bdi,'name','广西智信数据科技有限公司');
    comp.$set(bdi,'telephone','13800138000');
    comp.$set(bdi,'postcode','530022');
    comp.$set(bdi,'registerCapital','100');
    comp.$set(bdi,'detailAddr','民族大道100号');
    comp.$set(bdi,'proDetailAddr','民族大道100号');
    comp.$set(bdi,'fisRegionCode','450103');
    comp.$set(bdi,'businessPremises','自有');
    comp.$set(bdi,'shouldInvestWay','1');
    comp.$set(bdi,'investMoney','100');
    comp.$set(bdi,'regCapRMB','100');
    
    comp.$forceUpdate();
    return{filled:true};
})()""")
# fix: bdi typo
fill = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){return vm}
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=findFormComp(vm,0);
    if(!comp)return{error:'no_comp'};
    var bdi=comp.$data.businessDataInfo;
    var fd=bdi.flowData||{};
    comp.$set(fd,'entName','广西智信数据科技有限公司');
    comp.$set(fd,'regCap','100');
    comp.$set(fd,'empNum','5');
    comp.$set(fd,'licCopyNum','1');
    comp.$set(fd,'tel','13800138000');
    comp.$set(fd,'postalCode','530022');
    comp.$set(fd,'detailAddr','民族大道100号');
    comp.$set(fd,'proDetailAddr','民族大道100号');
    comp.$set(fd,'setUpMode','1');
    comp.$set(fd,'accountMethod','1');
    comp.$set(fd,'operTermType','1');
    comp.$set(fd,'isNeedPaperLic','0');
    comp.$set(fd,'isFreeTrade','0');
    comp.$set(fd,'industryType','I65');
    comp.$set(fd,'industryBigType','I');
    comp.$set(fd,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'name','广西智信数据科技有限公司');
    comp.$set(bdi,'telephone','13800138000');
    comp.$set(bdi,'postcode','530022');
    comp.$set(bdi,'registerCapital','100');
    comp.$set(bdi,'detailAddr','民族大道100号');
    comp.$set(bdi,'proDetailAddr','民族大道100号');
    comp.$set(bdi,'fisRegionCode','450103');
    comp.$set(bdi,'businessPremises','自有');
    comp.$set(bdi,'shouldInvestWay','1');
    comp.$set(bdi,'investMoney','100');
    comp.$set(bdi,'regCapRMB','100');
    comp.$forceUpdate();
    return{filled:true};
})()""")
print(f"  fill: {fill}")

# 同步DOM
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

# Step 5: 经营范围 - 找到打开对话框的Vue方法
print("\nStep 5: 经营范围对话框")
# 分析"添加规范经营用语"按钮的Vue组件
scope_btn = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')){
                    var comp=btns[j].__vue__;
                    if(!comp)comp=btns[j].closest('[class*="widget"]')?.__vue__;
                    if(!comp){
                        // 向上遍历找Vue组件
                        var el=btns[j];
                        for(var d=0;d<10&&el;d++){
                            if(el.__vue__){comp=el.__vue__;break}
                            el=el.parentElement;
                        }
                    }
                    if(comp){
                        var methods=comp.$options?.methods||{};
                        var srcs={};
                        for(var m in methods){
                            var src=methods[m].toString();
                            if(src.includes('dialog')||src.includes('Dialog')||src.includes('open')||src.includes('Open')||
                               src.includes('scope')||src.includes('Scope')||src.includes('add')||src.includes('Add')||
                               src.includes('business')||src.includes('Business')){
                                srcs[m]=src.substring(0,300);
                            }
                        }
                        return{compName:comp.$options?.name||'',methods:Object.keys(methods),srcs:srcs};
                    }
                    return{error:'no_vue_on_btn'};
                }
            }
        }
    }
})()""")
print(f"  scope_btn: compName={scope_btn.get('compName','') if scope_btn else ''}")
if scope_btn:
    for m, src in (scope_btn.get('srcs',{}) or {}).items():
        print(f"  {m}: {src[:200]}")

# Step 6: 通过Vue方法打开经营范围对话框
print("\nStep 6: 打开经营范围对话框")
open_result = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')){
                    // 找到按钮的Vue组件
                    var el=btns[j];
                    var comp=null;
                    for(var d=0;d<10&&el;d++){
                        if(el.__vue__){comp=el.__vue__;break}
                        el=el.parentElement;
                    }
                    if(comp){
                        // 尝试调用所有可能的方法
                        var methods=comp.$options?.methods||{};
                        for(var m in methods){
                            var src=methods[m].toString();
                            if(src.includes('dialog')||src.includes('Dialog')||src.includes('open')||src.includes('Open')||
                               src.includes('scope')||src.includes('add')||src.includes('Add')){
                                try{
                                    methods[m].call(comp);
                                    return{called:m,compName:comp.$options?.name||''};
                                }catch(e){
                                    // 尝试带参数
                                    try{
                                        methods[m].call(comp,{});
                                        return{called:m+'({})',compName:comp.$options?.name||''};
                                    }catch(e2){}
                                }
                            }
                        }
                        // 直接click
                        btns[j].click();
                        btns[j].dispatchEvent(new Event('click',{bubbles:true}));
                        return{clicked:true};
                    }
                }
            }
        }
    }
})()""")
print(f"  open_result: {open_result}")
time.sleep(5)

# Step 7: 检查iframe中对话框是否打开
print("\nStep 7: 检查iframe对话框")
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
core_targets = [t for t in targets if 'core.html' in t.get('url','')]

if core_targets:
    iframe_ws_url = core_targets[0]["webSocketDebuggerUrl"]
    iframe_ws = websocket.create_connection(iframe_ws_url, timeout=15)
    iframe_mid = 0
    
    def ev_iframe(js):
        global iframe_mid; iframe_mid += 1; mid = iframe_mid
        iframe_ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":15000}}))
        for _ in range(30):
            try:
                iframe_ws.settimeout(15); r = json.loads(iframe_ws.recv())
                if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
            except: return None
        return None
    
    # 检查经营范围对话框状态
    dialog_state = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                var display=getComputedStyle(wrapper).display;
                var dialogEl=wrapper.querySelector('.el-dialog');
                var dialogDisplay=dialogEl?getComputedStyle(dialogEl).display:'';
                var body=wrapper.querySelector('.el-dialog__body,[class*="body"]');
                var bodyHTML=body?body.innerHTML?.substring(0,300):'no body';
                var bodyText=body?body.textContent?.trim()?.substring(0,100):'';
                var trees=body?body.querySelectorAll('.el-tree').length:0;
                var inputs=body?body.querySelectorAll('input').length:0;
                var btns=body?body.querySelectorAll('button').length:0;
                return{display:display,dialogDisplay:dialogDisplay,trees:trees,inputs:inputs,btns:btns,
                    bodyText:bodyText.substring(0,60),bodyHTMLSample:bodyHTML.substring(0,100)};
            }
        }
        return{notFound:true};
    })()""")
    print(f"  dialog_state: {dialog_state}")
    
    # 如果对话框display:none，强制显示
    if dialog_state and dialog_state.get('display') == 'none':
        print("  强制显示对话框")
        ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                    wrapper.style.display='block';
                    var dialogEl=wrapper.querySelector('.el-dialog');
                    if(dialogEl)dialogEl.style.display='block';
                    // 也调用Vue方法
                    var comp=wrapper.__vue__||dialogEl?.__vue__;
                    if(comp){
                        comp.$emit('open');
                        if(typeof comp.open==='function')comp.open();
                        if(typeof comp.show==='function')comp.show();
                    }
                    return{forced:true};
                }
            }
        })()""")
        time.sleep(3)
    
    # 再次检查
    dialog_state2 = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                var body=wrapper.querySelector('.el-dialog__body,[class*="body"]');
                var trees=body?body.querySelectorAll('.el-tree').length:0;
                var inputs=body?body.querySelectorAll('input').length:0;
                var allEls=body?body.querySelectorAll('*').length:0;
                var bodyText=body?body.textContent?.trim()?.substring(0,200):'';
                return{display:getComputedStyle(wrapper).display,trees:trees,inputs:inputs,allEls:allEls,bodyText:bodyText.substring(0,80)};
            }
        }
    })()""")
    print(f"  dialog_state2: {dialog_state2}")
    
    # 如果对话框有内容了，操作树
    if dialog_state2 and dialog_state2.get('trees',0) > 0:
        print("  对话框有树，操作")
        # 搜索
        ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                    var body=wrapper.querySelector('.el-dialog__body,[class*="body"]');
                    var inputs=body.querySelectorAll('input');
                    for(var j=0;j<inputs.length;j++){
                        var ph=inputs[j].placeholder||'';
                        if(ph.includes('查询')||ph.includes('搜索')){
                            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                            s.call(inputs[j],'软件开发');
                            inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
                            return;
                        }
                    }
                }
            }
        })()""")
        time.sleep(3)
        
        # 选择树节点
        ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                    var body=wrapper.querySelector('.el-dialog__body,[class*="body"]');
                    var trees=body.querySelectorAll('.el-tree');
                    for(var t=0;t<trees.length;t++){
                        if(!trees[t].offsetParent)continue;
                        var cbs=trees[t].querySelectorAll('.el-checkbox__input:not(.is-checked)');
                        for(var c=0;c<Math.min(cbs.length,3);c++){
                            var node=cbs[c].closest('.el-tree-node');
                            var text=node?.textContent?.trim()||'';
                            if(text.includes('软件')||text.includes('信息技术')){
                                cbs[c].click();
                            }
                        }
                        // 如果没有匹配的，选前3个
                        if(trees[t].querySelectorAll('.is-checked').length===0){
                            for(var c=0;c<Math.min(cbs.length,3);c++){cbs[c].click()}
                        }
                    }
                }
            }
        })()""")
        time.sleep(1)
        
        # 点击确定
        ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var wrapper=dialogs[i].closest('.el-dialog__wrapper')||dialogs[i];
                    var btns=wrapper.querySelectorAll('button,.el-button');
                    for(var j=0;j<btns.length;j++){
                        var t=btns[j].textContent?.trim()||'';
                        if(t.includes('确定')||t.includes('确认')||t.includes('选择')){
                            btns[j].click();return;
                        }
                    }
                }
            }
        })()""")
        time.sleep(2)
    
    iframe_ws.close()

# Step 8: 验证
print("\nStep 8: 验证")
bdi = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findFormComp(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
            var bdi=vm.$data.businessDataInfo;
            var fd=bdi.flowData||{};
            return{
                name:bdi.name||fd.entName||'',
                telephone:bdi.telephone||fd.tel||'',
                regCap:bdi.registerCapital||fd.regCap||'',
                industryType:fd.industryType||fd.industryBigType||'',
                businessArea:fd.businessArea||bdi.businessArea||'',
                detailAddr:bdi.detailAddr||fd.detailAddr||'',
                formCount:document.querySelectorAll('.el-form-item').length,
                hash:location.hash
            };
        }
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    return findFormComp(vm,0);
})()""")
print(f"  bdi: {bdi}")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,15)})()""")
print(f"  validation errors: {errors}")

ws.close()
print("✅ 完成")
