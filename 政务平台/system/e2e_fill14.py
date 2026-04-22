#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按正确顺序填写: 住所cascader → 行业类型tne-select → 经营范围iframe对话框 → 保存"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    ws = websocket.create_connection(ws_url, timeout=15)
    return ws

ws = get_ws()
_mid = 0
def ev(js, timeout=15):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    except:
        ws = get_ws()
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    for _ in range(40):
        try:
            ws.settimeout(timeout); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if not fc or fc.get('formCount',0) < 10:
    print("❌ 表单未加载"); ws.close(); sys.exit()

# ============================================================
# Step 1: 先填简单字段
# ============================================================
print("\nStep 1: 填写简单字段")
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findAllForms(vm,d){
        if(d>15)return[];
        var result=[];
        if(vm.$options?.name==='ElForm'&&vm.model&&Object.keys(vm.model).length>0)result.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)result=result.concat(findAllForms(vm.$children[i],d+1));
        return result;
    }
    var forms=findAllForms(vm,0);
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
            form.$set(model,'secretaryServiceEnt','0');
        }
        if(keys.includes('busiPeriod')){
            form.$set(model,'busiPeriod','1');
            form.$set(model,'busiDateEnd','');
            form.$set(model,'busiDateStart','');
        }
        if(keys.includes('distCode')){
            form.$set(model,'distCode','450103');
            form.$set(model,'distCodeName','青秀区');
            form.$set(model,'fisDistCode','450103');
            form.$set(model,'detAddress','民族大道100号');
            form.$set(model,'isSelectDistCode','1');
            form.$set(model,'havaAdress','0');
            form.$set(model,'regionCode','450103');
            form.$set(model,'regionName','青秀区');
            form.$set(model,'detBusinessAddress','民族大道100号');
        }
        form.clearValidate();
    }
})()""")

# 同步DOM输入
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
        else if(label.includes('联系电话'))val='13800138000';
        else if(label.includes('邮政编码'))val='530022';
        else if(label.includes('详细地址')&&!label.includes('生产经营'))val='民族大道100号';
        else if(label.includes('生产经营地详细'))val='民族大道100号';
        if(val){s.call(input,val);input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# 经营期限radio
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营期限')){
            var radios=items[i].querySelectorAll('.el-radio');
            for(var j=0;j<radios.length;j++){
                if(radios[j].textContent?.trim()?.includes('长期')){
                    radios[j].click();
                }
            }
        }
    }
})()""")
time.sleep(1)

# ============================================================
# Step 2: 企业住所 cascader - 模拟点击选择
# ============================================================
print("\nStep 2: 企业住所 cascader")

# 分析cascader组件结构
cascader_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业住所')&&!label.includes('详细')){
            var cascader=items[i].querySelector('.el-cascader,[class*="cascader"],[class*="tne-data"]');
            if(!cascader)return{error:'no_cascader',label:label};
            var comp=cascader.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 分析组件
            var compName=comp.$options?.name||'';
            var dataKeys=Object.keys(comp.$data||{}).filter(function(k){var v=comp.$data[k];return v!==null&&v!==undefined&&v!==''});
            var propKeys=Object.keys(comp.$props||{});
            
            // 找options/data
            var opts=comp.options||comp.dataList||comp.list||comp.areaList||null;
            var optsLen=Array.isArray(opts)?opts.length:0;
            var optsSample=null;
            if(optsLen>0)optsSample=JSON.stringify(opts[0]).substring(0,200);
            
            return{
                compName:compName,
                dataKeys:dataKeys,
                propKeys:propKeys,
                optsLen:optsLen,
                optsSample:optsSample,
                value:comp.value||comp.modelValue||comp.$props?.value||comp.$props?.modelValue||null,
                label:label
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  cascader_info: {cascader_info}")

# 尝试通过Vue组件方法设置cascader
cascader_result = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if((label.includes('企业住所')&&!label.includes('详细'))||(label.includes('生产经营地址')&&!label.includes('详细'))){
            // 找所有可能的cascader组件
            var allComps=items[i].querySelectorAll('[class*="cascader"],[class*="tne-data"],.el-cascader');
            for(var c=0;c<allComps.length;c++){
                var comp=allComps[c].__vue__;
                if(!comp)continue;
                
                // 尝试不同方式设置值
                var val=['450000','450100','450103'];
                
                // 方式1: 直接设value
                if(comp.$emit){
                    comp.$emit('input',val);
                    comp.$emit('change',val);
                }
                
                // 方式2: 设presentText
                if('presentText' in comp){
                    comp.presentText='广西壮族自治区/南宁市/青秀区';
                }
                
                // 方式3: 找内部el-cascader
                var innerCascader=comp.$children?.find(function(ch){return ch.$options?.name==='ElCascader'});
                if(innerCascader){
                    innerCascader.$emit('input',val);
                    innerCascader.$emit('change',val);
                    innerCascader.presentText='广西壮族自治区/南宁市/青秀区';
                    if(innerCascader.$refs?.panel){
                        innerCascader.$refs.panel.$emit('active-value-change',val);
                    }
                }
                
                // 方式4: 找tne-data-cascader内部方法
                var methods=comp.$options?.methods||{};
                if(methods.setValue){
                    comp.setValue(val);
                }
                if(methods.handleValueChange){
                    comp.handleValueChange(val);
                }
                if(methods.handleChange){
                    comp.handleChange(val);
                }
                
                return{set:true,compName:comp.$options?.name||'',label:label};
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  cascader_result: {cascader_result}")

# ============================================================
# Step 3: 行业类型 - 模拟UI交互选择
# ============================================================
print("\nStep 3: 行业类型 tne-select")

# 点击行业类型输入框触发下拉
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){
                input.focus();
                input.click();
                input.dispatchEvent(new Event('focus',{bubbles:true}));
            }
            return;
        }
    }
})()""")
time.sleep(3)

# 检查下拉是否出现
dropdown_state = ev("""(function(){
    var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent!==null||poppers[p].style?.display!=='none'){
            var tree=poppers[p].querySelector('.el-tree');
            if(tree){
                var nodes=tree.querySelectorAll('.el-tree-node__content');
                var visible=[];
                for(var i=0;i<Math.min(nodes.length,30);i++){
                    visible.push({idx:i,text:nodes[i].textContent?.trim()?.substring(0,35)||''});
                }
                return{visible:true,total:nodes.length,nodes:visible};
            }
        }
    }
    return{visible:false};
})()""")
print(f"  dropdown: visible={dropdown_state.get('visible',False)} total={dropdown_state.get('total',0)}")

# 展开[I]门类
if dropdown_state.get('visible'):
    # 找到[I]节点并点击展开
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
        for(var p=0;p<poppers.length;p++){
            if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
            var tree=poppers[p].querySelector('.el-tree');
            if(!tree)continue;
            var nodes=tree.querySelectorAll('.el-tree-node__content');
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('[I]信息传输')||text.includes('[I]软件')){
                    // 点击展开图标
                    var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                    if(expandIcon&&!expandIcon.classList.contains('expanded')){
                        expandIcon.click();
                    }
                    return;
                }
            }
        }
    })()""")
    time.sleep(2)
    
    # 找到[65]并点击
    ev("""(function(){
        var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
        for(var p=0;p<poppers.length;p++){
            if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
            var tree=poppers[p].querySelector('.el-tree');
            if(!tree)continue;
            var nodes=tree.querySelectorAll('.el-tree-node__content');
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('[65]软件和信息技术服务业')||text.includes('[65]软件')){
                    nodes[i].click();
                    return{clicked:text.substring(0,30)};
                }
            }
        }
    })()""")
    time.sleep(2)
    
    # 检查选中状态
    industry_val = ev("""(function(){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
            if(label.includes('行业类型')){
                var input=items[i].querySelector('input');
                return{value:input?.value||'',placeholder:input?.placeholder||''};
            }
        }
    })()""")
    print(f"  industry_val: {industry_val}")

# 关闭下拉
ev("document.body.click()")
time.sleep(1)

# ============================================================
# Step 4: 经营范围 - 打开iframe对话框
# ============================================================
print("\nStep 4: 经营范围对话框")

# 先检查当前验证错误
errors_before = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  当前验证错误: {errors_before}")

# 找"添加规范经营用语"按钮并点击
btn_result = ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button,[class*="add"]');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if((t.includes('添加')||t.includes('规范')||t.includes('经营范围'))&&btns[i].offsetParent!==null){
            btns[i].click();
            btns[i].dispatchEvent(new Event('click',{bubbles:true}));
            return{clicked:t.substring(0,30),idx:i};
        }
    }
    return{error:'no_btn'};
})()""")
print(f"  btn_result: {btn_result}")
time.sleep(3)

# 检查对话框是否出现
dialog_state = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog,[class*="dialog"],[class*="Dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent!==null||d.style?.display!=='none'){
            var text=d.textContent?.trim()?.substring(0,100)||'';
            if(text.includes('经营范围')||text.includes('主营项目')){
                // 检查iframe
                var iframe=d.querySelector('iframe');
                return{
                    visible:true,
                    hasIframe:!!iframe,
                    iframeSrc:iframe?.src||iframe?.getAttribute('src')||'',
                    text:text.substring(0,80),
                    className:d.className?.substring(0,50)||''
                };
            }
        }
    }
    return{visible:false};
})()""")
print(f"  dialog_state: {dialog_state}")

# 如果对话框可见且有iframe，连接iframe CDP
if dialog_state.get('visible') and dialog_state.get('hasIframe'):
    print("  经营范围对话框已打开，含iframe")
    
    # 获取iframe的CDP target
    targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    iframe_targets = [t for t in targets if 'jyfwyun' in t.get('url','') or 'businessScope' in t.get('url','') or 'scope' in t.get('url','').lower()]
    
    if not iframe_targets:
        # 也检查所有iframe类型target
        iframe_targets = [t for t in targets if t.get('type')=='iframe' or t.get('type')=='other']
    
    print(f"  iframe targets: {len(iframe_targets)}")
    for t in iframe_targets[:3]:
        print(f"    {t.get('type','')} {t.get('url','')[:80]}")
    
    if iframe_targets:
        iframe_ws_url = iframe_targets[0]["webSocketDebuggerUrl"]
        iframe_ws = websocket.create_connection(iframe_ws_url, timeout=15)
        _mid2 = 0
        
        def ev_iframe(js, timeout=15):
            global _mid2, iframe_ws
            _mid2 += 1; mid = _mid2
            try:
                iframe_ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
            except:
                iframe_ws = websocket.create_connection(iframe_ws_url, timeout=15)
                iframe_ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
            for _ in range(40):
                try:
                    iframe_ws.settimeout(timeout); r = json.loads(iframe_ws.recv())
                    if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
                except: return None
            return None
        
        # 在iframe中搜索"软件开发"
        print("\n  iframe内搜索: 软件开发")
        search_result = ev_iframe("""(function(){
            var input=document.querySelector('input[placeholder*="关键词"],input[placeholder*="搜索"],input.search-input,input[type="text"]');
            if(!input){
                // 列出所有input
                var inputs=document.querySelectorAll('input');
                var list=[];
                for(var i=0;i<inputs.length;i++){
                    list.push({idx:i,type:inputs[i].type,placeholder:inputs[i].placeholder||'',class:inputs[i].className?.substring(0,30)||''});
                }
                return{error:'no_search_input',inputs:list};
            }
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(input,'软件开发');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
            return{search:'软件开发'};
        })()""")
        print(f"  search_result: {search_result}")
        time.sleep(3)
        
        # 查看搜索结果
        search_results = ev_iframe("""(function(){
            var items=document.querySelectorAll('.el-tree-node__content,[class*="tree-node"],[class*="result-item"],[class*="scope-item"],li,td');
            var results=[];
            for(var i=0;i<Math.min(items.length,30);i++){
                var text=items[i].textContent?.trim()||'';
                if(text.includes('软件')||text.includes('信息技术')||text.includes('开发')){
                    results.push({idx:i,text:text.substring(0,50)});
                }
            }
            // 也检查checkbox
            var checkboxes=document.querySelectorAll('.el-checkbox,[class*="checkbox"],input[type="checkbox"]');
            var cbResults=[];
            for(var i=0;i<Math.min(checkboxes.length,20);i++){
                var text=checkboxes[i].closest('li,td,div,[class*="item"]')?.textContent?.trim()||'';
                if(text.includes('软件')||text.includes('信息技术')){
                    cbResults.push({idx:i,text:text.substring(0,50)});
                }
            }
            return{treeResults:results,checkboxResults:cbResults,totalItems:items.length};
        })()""")
        print(f"  search_results: {search_results}")
        
        # 点击搜索结果中的"软件开发"checkbox
        if search_results and (search_results.get('checkboxResults') or search_results.get('treeResults')):
            ev_iframe("""(function(){
                var checkboxes=document.querySelectorAll('.el-checkbox,[class*="checkbox"]');
                for(var i=0;i<checkboxes.length;i++){
                    var text=checkboxes[i].closest('li,td,div,[class*="item"]')?.textContent?.trim()||'';
                    if(text.includes('软件开发')){
                        checkboxes[i].click();
                        return{clicked:'软件开发',idx:i};
                    }
                }
                // 也尝试tree节点
                var nodes=document.querySelectorAll('.el-tree-node__content');
                for(var i=0;i<nodes.length;i++){
                    var text=nodes[i].textContent?.trim()||'';
                    if(text.includes('软件开发')){
                        nodes[i].click();
                        return{clicked:'软件开发_tree',idx:i};
                    }
                }
                return{error:'not_found'};
            })()""")
            time.sleep(1)
            
            # 也选"信息技术咨询服务"
            ev_iframe("""(function(){
                var checkboxes=document.querySelectorAll('.el-checkbox,[class*="checkbox"]');
                for(var i=0;i<checkboxes.length;i++){
                    var text=checkboxes[i].closest('li,td,div,[class*="item"]')?.textContent?.trim()||'';
                    if(text.includes('信息技术咨询')){
                        checkboxes[i].click();
                        return{clicked:'信息技术咨询',idx:i};
                    }
                }
                return{error:'not_found'};
            })()""")
            time.sleep(1)
        
        # 点击确定/确认按钮
        confirm_result = ev_iframe("""(function(){
            var btns=document.querySelectorAll('button,.el-button,[class*="btn"],[class*="confirm"],[class*="submit"]');
            for(var i=0;i<btns.length;i++){
                var t=btns[i].textContent?.trim()||'';
                if((t.includes('确定')||t.includes('确认')||t.includes('提交')||t.includes('保存'))&&btns[i].offsetParent!==null){
                    btns[i].click();
                    return{clicked:t.substring(0,20),idx:i};
                }
            }
            return{error:'no_confirm_btn'};
        })()""")
        print(f"  confirm_result: {confirm_result}")
        time.sleep(2)
        
        iframe_ws.close()
    else:
        print("  ❌ 未找到iframe CDP target")
        # 列出所有targets
        all_targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        for t in all_targets[:10]:
            print(f"    {t.get('type','')} {t.get('url','')[:80]}")

elif dialog_state.get('visible') and not dialog_state.get('hasIframe'):
    print("  对话框可见但无iframe，直接在主页面操作")
    # 在主页面中搜索和选择
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
        for(var i=0;i<dialogs.length;i++){
            var d=dialogs[i];
            if(d.offsetParent===null&&d.style?.display==='none')continue;
            if(!d.textContent?.includes('经营范围'))continue;
            // 找搜索输入框
            var inputs=d.querySelectorAll('input');
            for(var j=0;j<inputs.length;j++){
                var ph=inputs[j].placeholder||'';
                if(ph.includes('关键词')||ph.includes('搜索')){
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    s.call(inputs[j],'软件开发');
                    inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
                    return{search:'软件开发'};
                }
            }
        }
    })()""")
else:
    print("  ❌ 经营范围对话框未打开")
    # 尝试通过Vue方法打开
    print("  尝试Vue方法打开...")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findFormComp(vm,d){
            if(d>15)return null;
            if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
            return null;
        }
        var comp=findFormComp(vm,0);
        if(comp){
            var methods=comp.$options?.methods||{};
            var names=Object.keys(methods);
            var scopeMethods=names.filter(function(n){return n.includes('scope')||n.includes('Scope')||n.includes('business')||n.includes('Area')||n.includes('Dialog')||n.includes('Modal')});
            return{methods:scopeMethods,allMethods:names.slice(0,20)};
        }
    })()""")

# ============================================================
# Step 5: 最终验证
# ============================================================
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# 检查行业类型值
industry_final = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            return{value:input?.value||'',error:items[i].querySelector('.el-form-item__error')?.textContent||''};
        }
    }
})()""")
print(f"  行业类型: {industry_final}")

# 检查经营范围值
scope_final = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var input=items[i].querySelector('input,textarea');
            var text=items[i].querySelector('.el-form-item__content')?.textContent?.trim()||'';
            return{value:input?.value||'',text:text.substring(0,80),error:items[i].querySelector('.el-form-item__error')?.textContent||''};
        }
    }
})()""")
print(f"  经营范围: {scope_final}")

ws.close()
print("\n✅ 完成")
