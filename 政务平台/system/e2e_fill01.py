#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""填写basic-info表单所有字段 → 重点处理行业类型+经营范围"""
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

# 确认在basic-info
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if not fc or fc.get('formCount',0) < 10:
    print("❌ 表单未加载，退出")
    ws.close(); exit()

# Step 1: 分析Vue组件数据模型
print("\nStep 1: 分析basic-info组件数据模型")
model = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>15)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return{error:'no_comp'};
    var data=bi.$data||{};
    return{
        compName:bi.$options?.name||'',
        dataKeys:Object.keys(data).slice(0,30),
        formKeys:data.form?Object.keys(data.form).slice(0,40):[],
        formSample:data.form?JSON.stringify(data.form).substring(0,500):'',
        methods:Object.keys(bi.$options?.methods||{}).slice(0,20)
    };
})()""")
print(f"  compName: {model.get('compName','') if model else ''}")
print(f"  dataKeys: {model.get('dataKeys',[]) if model else []}")
print(f"  formKeys: {model.get('formKeys',[]) if model else []}")
print(f"  formSample: {model.get('formSample','')[:300] if model else ''}")
print(f"  methods: {model.get('methods',[]) if model else []}")

# Step 2: 填写简单字段（文本+radio）
print("\nStep 2: 填写简单字段")
fill_result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>15)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'basic-info',0);
    if(!bi||!bi.$data?.form)return{error:'no_comp'};
    var form=bi.$data.form;
    var set=bi.$set.bind(bi);
    
    // 文本字段
    set(form,'entName','广西智信数据科技有限公司');
    // entType由系统决定，不修改
    set(form,'regCap','100');  // 注册资本100万
    set(form,'empNum','5');    // 从业人数
    set(form,'licCopyNum','1'); // 执照副本数量
    set(form,'tel','13800138000'); // 联系电话
    set(form,'postalCode','530022'); // 邮政编码
    set(form,'dom','南宁市青秀区'); // 企业住所
    set(form,'domDistrict','450103'); // 区域代码
    set(form,'detailAddr','民族大道100号'); // 详细地址
    set(form,'proLoc','南宁市青秀区'); // 生产经营地址
    set(form,'proLocDistrict','450103'); // 生产经营地区域
    set(form,'proDetailAddr','民族大道100号'); // 生产经营地详细地址
    
    // Radio字段
    set(form,'setUpMode','1'); // 设立方式: 1=发起
    set(form,'accountMethod','1'); // 核算方式: 1=独立核算
    set(form,'operTermType','1'); // 经营期限: 1=长期
    set(form,'isNeedPaperLic','0'); // 是否需要纸质营业执照: 0=否
    set(form,'isFreeTrade','0'); // 是否自贸区: 0=否
    
    bi.$forceUpdate();
    return{filled:true,formKeys:Object.keys(form).length};
})()""")
print(f"  fill_result: {fill_result}")

# 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input.el-input__inner');
        if(!input||!input.offsetParent)continue;
        var val='';
        if(label.includes('企业名称'))val='广西智信数据科技有限公司';
        else if(label.includes('注册资本'))val='100';
        else if(label.includes('从业人数'))val='5';
        else if(label.includes('执照副本'))val='1';
        else if(label.includes('联系电话'))val='13800138000';
        else if(label.includes('邮政编码'))val='530022';
        else if(label.includes('详细地址')&&!label.includes('生产经营'))val='民族大道100号';
        else if(label.includes('生产经营地详细'))val='民族大道100号';
        if(val){s.call(input,val);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))}
    }
})()""")
time.sleep(1)

# 勾选radio
ev("""(function(){
    var radios=document.querySelectorAll('.el-radio__input:not(.is-checked)');
    // 只勾选每组第一个
    var groups={};
    for(var i=0;i<radios.length;i++){
        var parent=radios[i].closest('.el-form-item');
        var label=parent?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(!groups[label]){groups[label]=true;radios[i].click()}
    }
})()""")
time.sleep(1)

# Step 3: 处理行业类型下拉
print("\nStep 3: 处理行业类型")
# 先分析行业类型的el-select组件
industry_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(!select)return{error:'no_select',label:label};
            var comp=select.__vue__;
            if(!comp)return{error:'no_vue'};
            return{
                label:label,
                compName:comp.$options?.name||'',
                value:comp.value||'',
                optionsCount:comp.options?.length||0,
                optionsSample:(comp.options||[]).slice(0,5).map(function(o){return{label:o.label?.substring(0,30)||'',value:o.value||'',children:!!o.children}}),
                props:JSON.stringify(comp.$props)?.substring(0,200)||'',
                remote:comp.remote||false,
                remoteMethod:comp.remoteMethod?.toString()?.substring(0,100)||''
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  industry_info: {industry_info}")

# Step 4: 如果行业类型有选项，选择
if industry_info and not industry_info.get('error'):
    if industry_info.get('optionsCount',0) > 0:
        # 找到软件/信息技术相关选项
        result = ev("""(function(){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
                var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                if(label.includes('行业类型')){
                    var select=items[i].querySelector('.el-select');
                    var comp=select?.__vue__;
                    if(!comp)return{error:'no_comp'};
                    
                    // 点击展开下拉
                    var input=select.querySelector('input');
                    input.click();
                    input.dispatchEvent(new Event('focus',{bubbles:true}));
                    input.dispatchEvent(new Event('click',{bubbles:true}));
                    return{clicked:true,optionsCount:comp.options?.length||0};
                }
            }
        })()""")
        print(f"  点击展开: {result}")
        time.sleep(2)
        
        # 查看展开后的选项
        options = ev("""(function(){
            var popper=document.querySelectorAll('.el-select-dropdown__item');
            var r=[];
            for(var i=0;i<Math.min(popper.length,20);i++){
                if(popper[i].offsetParent!==null){
                    r.push({idx:i,text:popper[i].textContent?.trim()?.substring(0,40)||'',group:!!popper[i].closest('.el-select-group')});
                }
            }
            return{visible:r.length,popper:popper.length,options:r};
        })()""")
        print(f"  options: visible={options.get('visible',0)} sample={options.get('options',[])[:5]}")
        
        # 选择信息传输/软件相关选项
        selected = ev("""(function(){
            var popper=document.querySelectorAll('.el-select-dropdown__item');
            for(var i=0;i<popper.length;i++){
                var t=popper[i].textContent?.trim()||'';
                if(t.includes('信息传输')||t.includes('软件')||t.includes('信息技术')||t.includes('I ')){
                    popper[i].click();
                    return{selected:t.substring(0,40),idx:i};
                }
            }
            // 如果没有匹配，选第一个
            for(var i=0;i<popper.length;i++){
                if(popper[i].offsetParent!==null){
                    popper[i].click();
                    return{selected:popper[i].textContent?.trim()?.substring(0,40)||'',idx:i,fallback:true};
                }
            }
            return{error:'no_visible_option'};
        })()""")
        print(f"  selected: {selected}")
        time.sleep(2)
    else:
        # 没有选项，可能是懒加载
        print("  无选项，可能是懒加载")
        # 触发focus事件
        ev("""(function(){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
                var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                if(label.includes('行业类型')){
                    var input=items[i].querySelector('input');
                    input.focus();
                    input.click();
                    return;
                }
            }
        })()""")
        time.sleep(3)
        
        # 再次检查
        opts2 = ev("""(function(){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
                var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                if(label.includes('行业类型')){
                    var select=items[i].querySelector('.el-select');
                    var comp=select?.__vue__;
                    return{optionsCount:comp?.options?.length||0,remote:comp?.remote||false,loading:comp?.loading||false};
                }
            }
        })()""")
        print(f"  opts2: {opts2}")

# Step 5: 处理经营范围
print("\nStep 5: 处理经营范围")
# 找经营范围按钮
scope_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            var btnInfo=[];
            for(var j=0;j<btns.length;j++){
                btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,30)||'',visible:btns[j].offsetParent!==null});
            }
            var comp=items[i].__vue__;
            return{label:label,btns:btnInfo,compName:comp?.$options?.name||'',dataKeys:comp?Object.keys(comp.$data||{}).slice(0,10):[]};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  scope_info: {scope_info}")

# 点击添加经营范围按钮
if scope_info and not scope_info.get('error'):
    for btn in scope_info.get('btns',[]):
        t = btn.get('text','')
        idx = btn.get('idx',0)
        if '添加' in t or '规范' in t or '选择' in t:
            print(f"  点击: {t}")
            ev(f"""(function(){{
                var items=document.querySelectorAll('.el-form-item');
                for(var i=0;i<items.length;i++){{
                    var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                    if(label.includes('经营范围')){{
                        var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
                        if(btns[{idx}])btns[{idx}].click();
                        return;
                    }}
                }}
            }})()""")
            time.sleep(3)
            
            # 检查弹出的对话框
            dialog = ev("""(function(){
                var dialogs=document.querySelectorAll('.el-dialog__wrapper,.tni-dialog,[class*="dialog"]');
                for(var i=0;i<dialogs.length;i++){
                    if(dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'){
                        var body=dialogs[i].querySelector('.el-dialog__body,.tni-dialog__body,[class*="body"]');
                        if(!body)body=dialogs[i];
                        var inputs=body.querySelectorAll('input');
                        var btns=body.querySelectorAll('button,.el-button');
                        var trees=body.querySelectorAll('.el-tree,[class*="tree"]');
                        var inputInfo=[];
                        for(var j=0;j<inputs.length;j++){inputInfo.push({idx:j,ph:inputs[j].placeholder||'',val:inputs[j].value||'',visible:inputs[j].offsetParent!==null})}
                        var btnInfo=[];
                        for(var j=0;j<btns.length;j++){btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||''})}
                        return{found:true,inputInfo:inputInfo,btnInfo:btnInfo,treeCount:trees.length,className:dialogs[i].className?.substring(0,50)||''};
                    }
                }
                return{found:false};
            })()""")
            print(f"  dialog: {dialog}")
            
            if dialog and dialog.get('found'):
                # 在搜索框输入
                for inp in dialog.get('inputInfo',[]):
                    ph = inp.get('ph','')
                    idx = inp.get('idx',0)
                    if '搜索' in ph or '查询' in ph or '关键字' in ph:
                        print(f"  搜索: #{idx} ph={ph}")
                        ev(f"""(function(){{
                            var dialogs=document.querySelectorAll('.el-dialog__wrapper,.tni-dialog,[class*="dialog"]');
                            for(var i=0;i<dialogs.length;i++){{
                                if(dialogs[i].offsetParent!==null){{
                                    var body=dialogs[i].querySelector('.el-dialog__body,.tni-dialog__body,[class*="body"]')||dialogs[i];
                                    var inputs=body.querySelectorAll('input');
                                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                                    s.call(inputs[{idx}],'软件开发');
                                    inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                                    return;
                                }}
                            }}
                        }})()""")
                        time.sleep(3)
                        break
                
                # 检查搜索结果
                search_result = ev("""(function(){
                    var dialogs=document.querySelectorAll('.el-dialog__wrapper,.tni-dialog,[class*="dialog"]');
                    for(var i=0;i<dialogs.length;i++){
                        if(dialogs[i].offsetParent!==null){
                            var body=dialogs[i].querySelector('.el-dialog__body,.tni-dialog__body,[class*="body"]')||dialogs[i];
                            var checkboxes=body.querySelectorAll('.el-checkbox__input:not(.is-checked),[class*="check"]');
                            var nodes=body.querySelectorAll('.el-tree-node,[class*="node"]');
                            var resultItems=body.querySelectorAll('[class*="result"] li,[class*="item"]');
                            return{checkboxes:checkboxes.length,nodes:nodes.length,resultItems:resultItems.length,
                                nodeSample:Array.from(nodes).slice(0,5).map(function(n){return n.textContent?.trim()?.substring(0,30)||''}),
                                resultSample:Array.from(resultItems).slice(0,5).map(function(n){return n.textContent?.trim()?.substring(0,30)||''})};
                        }
                    }
                })()""")
                print(f"  search_result: {search_result}")
                
                # 选择第一个匹配项
                ev("""(function(){
                    var dialogs=document.querySelectorAll('.el-dialog__wrapper,.tni-dialog,[class*="dialog"]');
                    for(var i=0;i<dialogs.length;i++){
                        if(dialogs[i].offsetParent!==null){
                            var body=dialogs[i].querySelector('.el-dialog__body,.tni-dialog__body,[class*="body"]')||dialogs[i];
                            // 尝试勾选checkbox
                            var cbs=body.querySelectorAll('.el-checkbox__input:not(.is-checked)');
                            for(var j=0;j<Math.min(cbs.length,3);j++){cbs[j].click()}
                            // 尝试点击tree node
                            var nodes=body.querySelectorAll('.el-tree-node__content');
                            for(var j=0;j<nodes.length;j++){
                                if(nodes[j].textContent?.includes('软件')||nodes[j].textContent?.includes('信息技术')){
                                    nodes[j].click();return;
                                }
                            }
                        }
                    }
                })()""")
                time.sleep(1)
                
                # 点击确定/保存
                for btn in dialog.get('btnInfo',[]):
                    t = btn.get('text','')
                    idx = btn.get('idx',0)
                    if '确定' in t or '确认' in t or '保存' in t:
                        print(f"  点击对话框: {t}")
                        ev(f"""(function(){{
                            var dialogs=document.querySelectorAll('.el-dialog__wrapper,.tni-dialog,[class*="dialog"]');
                            for(var i=0;i<dialogs.length;i++){{
                                if(dialogs[i].offsetParent!==null){{
                                    var btns=dialogs[i].querySelectorAll('button,.el-button');
                                    if(btns[{idx}])btns[{idx}].click();
                                    return;
                                }}
                            }}
                        }})()""")
                        time.sleep(2)
                        break
            break

# Step 6: 处理企业住所区域选择器
print("\nStep 6: 处理区域选择器")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业住所')&&!label.includes('详细')){
            var cascader=items[i].querySelector('.el-cascader');
            if(cascader){
                var input=cascader.querySelector('input');
                input.click();
                return{clicked:true,label:label};
            }
        }
    }
    return{clicked:false};
})()""")
time.sleep(2)

# 选择区域面板
ev("""(function(){
    var panels=document.querySelectorAll('.el-cascader-menu');
    for(var p=0;p<panels.length;p++){
        var items=panels[p].querySelectorAll('.el-cascader-node');
        for(var i=0;i<items.length;i++){
            var t=items[i].textContent?.trim()||'';
            if(t.includes('广西')||t.includes('南宁市')){
                items[i].click();
                return{clicked:t.substring(0,20),panel:p};
            }
        }
    }
})()""")
time.sleep(1)

# Step 7: 验证表单状态
print("\nStep 7: 验证表单状态")
form_state = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>15)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var bi=findComp(vm,'basic-info',0);
    if(!bi||!bi.$data?.form)return{error:'no_comp'};
    var form=bi.$data.form;
    return{
        entName:form.entName||'',
        regCap:form.regCap||'',
        empNum:form.empNum||'',
        tel:form.tel||'',
        dom:form.dom||'',
        detailAddr:form.detailAddr||'',
        industryType:form.industryType||form.industryBigType||form.busiType||'',
        businessArea:form.businessArea||form.businessScope||'',
        formKeys:Object.keys(form).length
    };
})()""")
print(f"  form_state: {form_state}")

# 最终检查
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

ws.close()
print("✅ 完成")
