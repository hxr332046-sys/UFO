#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精确处理: tne-select树形行业类型 + iframe经营范围树节点点击 + 避免过早保存"""
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

# Step 1: 分析tne-select组件结构
print("\nStep 1: 分析tne-select行业类型组件")
tne_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            // 分析tne-select的完整属性
            return{
                compName:comp.$options?.name||'',
                value:comp.value||'',
                valueKey:comp.valueKey||'',
                popperClass:comp.popperClass||'',
                treeData:JSON.stringify(comp.treeData||comp.data||comp.$data?.treeData)?.substring(0,300)||'none',
                props:JSON.stringify(comp.treeProps||comp.props)?.substring(0,200)||'none',
                lazy:comp.lazy||false,
                load:typeof comp.load==='function'?'function':'none',
                // 检查data中是否有tree相关
                dataKeys:Object.keys(comp.$data||{}).slice(0,20),
                // 检查$refs
                refs:Object.keys(comp.$refs||{}).slice(0,10)
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  tne_info: {tne_info}")

# Step 2: 点击行业类型展开树形下拉
print("\nStep 2: 展开行业类型树形下拉")
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){
                input.focus();
                input.click();
                // 触发visible-change
                var select=items[i].querySelector('.el-select');
                var comp=select?.__vue__;
                if(comp){
                    comp.visible=true;
                    comp.$emit('visible-change',true);
                }
            }
            return;
        }
    }
})()""")
time.sleep(3)

# 检查树形popper面板
tree_popper = ev("""(function(){
    // 找tree-popper
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"],.el-popper');
    var result=[];
    for(var i=0;i<poppers.length;i++){
        var visible=poppers[i].offsetParent!==null||poppers[i].style?.display!=='none'||poppers[i].style?.visibility!=='hidden';
        if(visible){
            var trees=poppers[i].querySelectorAll('.el-tree');
            var nodes=poppers[i].querySelectorAll('.el-tree-node');
            var text=poppers[i].textContent?.trim()?.substring(0,100)||'';
            result.push({idx:i,visible:true,trees:trees.length,nodes:nodes.length,text:text.substring(0,60),className:poppers[i].className?.substring(0,40)||''});
        }
    }
    return{poppers:result.length,visible:result};
})()""")
print(f"  tree_popper: poppers={tree_popper.get('poppers',0)}")
for p in (tree_popper.get('visible',[]) or []):
    print(f"    idx={p.get('idx')} trees={p.get('trees')} nodes={p.get('nodes')} class={p.get('className','')[:30]}")
    print(f"    text={p.get('text','')[:50]}")

# Step 3: 在树中找到[I]选项并展开
print("\nStep 3: 在树中找[I]选项")
# 查找所有树节点
tree_nodes = ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        var result=[];
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            var expanded=nodes[i].closest('.el-tree-node')?.classList?.contains('is-expanded')||false;
            result.push({idx:i,text:text.substring(0,50),expanded:expanded});
        }
        return{total:nodes.length,nodes:result};
    }
    return{error:'no_visible_popper'};
})()""")
print(f"  tree_nodes: total={tree_nodes.get('total',0) if tree_nodes else 0}")
for n in (tree_nodes.get('nodes',[]) or []):
    marker = ' ✅' if '[I]' in n.get('text','') or '信息传输' in n.get('text','') else ''
    print(f"    [{n.get('idx')}] exp={n.get('expanded',False)} {n.get('text','')[:40]}{marker}")

# 点击[I]选项展开
if tree_nodes and tree_nodes.get('total',0) > 0:
    expand_result = ev("""(function(){
        var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
        for(var p=0;p<poppers.length;p++){
            var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
            if(!visible)continue;
            var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('[I]')||text.includes('信息传输')){
                    // 点击展开
                    var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                    if(expandIcon){
                        expandIcon.click();
                        return{expanded:true,text:text.substring(0,40),idx:i};
                    }
                    // 直接点击节点
                    nodes[i].click();
                    return{clicked:true,text:text.substring(0,40),idx:i};
                }
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  expand: {expand_result}")
    time.sleep(2)
    
    # 查看展开后的子节点
    child_nodes = ev("""(function(){
        var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
        for(var p=0;p<poppers.length;p++){
            var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
            if(!visible)continue;
            var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
            var result=[];
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text)result.push({idx:i,text:text.substring(0,50)});
            }
            return{total:nodes.length,nodes:result};
        }
    })()""")
    print(f"  child_nodes: total={child_nodes.get('total',0) if child_nodes else 0}")
    for n in (child_nodes.get('nodes',[]) or []):
        marker = ' ✅' if '软件' in n.get('text','') or '信息技术' in n.get('text','') else ''
        print(f"    [{n.get('idx')}] {n.get('text','')[:40]}{marker}")
    
    # 选择子节点（软件和信息技术服务业）
    select_child = ev("""(function(){
        var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
        for(var p=0;p<poppers.length;p++){
            var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
            if(!visible)continue;
            var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('软件')||text.includes('信息技术服务业')){
                    nodes[i].click();
                    return{selected:text.substring(0,40),idx:i};
                }
            }
            // 如果没有匹配，选[I]下面的第一个子节点
            var foundI=false;
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('[I]'))foundI=true;
                if(foundI&&text&&!text.includes('[I]')&&!text.includes('[A]')&&!text.includes('[B]')&&!text.includes('[C]')&&!text.includes('[D]')&&!text.includes('[E]')&&!text.includes('[F]')&&!text.includes('[G]')&&!text.includes('[H]')){
                    nodes[i].click();
                    return{selected:text.substring(0,40),idx:i,fallback:true};
                }
            }
        }
        return{error:'not_found'};
    })()""")
    print(f"  select_child: {select_child}")
    time.sleep(2)

# Step 4: 经营范围 - 通过iframe CDP精确操作
print("\nStep 4: 经营范围iframe操作")
# 先关闭之前的错误对话框
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('确定')||t.includes('关闭')){
            // 只关闭错误提示
            var dialog=btns[i].closest('.el-message-box,.el-dialog,.tni-dialog');
            if(dialog){
                var dt=dialog.textContent?.trim()||'';
                if(dt.includes('异常')||dt.includes('失败')||dt.includes('提示')){
                    btns[i].click();
                }
            }
        }
    }
})()""")
time.sleep(1)

# 点击添加规范经营用语
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var btns=items[i].querySelectorAll('button,.el-button,[class*="add"]');
            for(var j=0;j<btns.length;j++){
                if(btns[j].textContent?.trim()?.includes('添加')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# 连接iframe
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
    
    # 找经营范围选择对话框
    dialog_info = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var visible=getComputedStyle(dialogs[i]).display!=='none'&&dialogs[i].offsetParent!==null;
                var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                if(!body)body=dialogs[i];
                var html=body.innerHTML?.substring(0,500)||'';
                var text=body.textContent?.trim()?.substring(0,200)||'';
                return{found:true,idx:i,visible:visible,title:title,bodyText:text.substring(0,100),htmlSample:html.substring(0,200)};
            }
        }
        return{found:false};
    })()""")
    print(f"  dialog: found={dialog_info.get('found',False)} visible={dialog_info.get('visible',False)}")
    print(f"  bodyText: {dialog_info.get('bodyText','')[:80]}")
    print(f"  htmlSample: {dialog_info.get('htmlSample','')[:100]}")
    
    # 如果对话框不可见，尝试打开
    if dialog_info and not dialog_info.get('visible'):
        print("  对话框不可见，尝试打开...")
        ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    dialogs[i].style.display='block';
                    var mask=dialogs[i].previousElementSibling||dialogs[i].closest('.tni-dialog__wrapper');
                    if(mask)mask.style.display='block';
                    return{opened:true};
                }
            }
        })()""")
        time.sleep(1)
    
    # 分析对话框内的树结构
    tree_info = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]')||dialogs[i];
                var trees=body.querySelectorAll('.el-tree');
                var inputs=body.querySelectorAll('input');
                var btns=body.querySelectorAll('button,.el-button');
                var pickers=body.querySelectorAll('[class*="picker"],[class*="selected"]');
                var tabs=body.querySelectorAll('.el-tabs__item,[class*="tab"]');
                
                var treeInfo=[];
                for(var t=0;t<trees.length;t++){
                    var nodes=trees[t].querySelectorAll('.el-tree-node');
                    var checked=trees[t].querySelectorAll('.is-checked');
                    treeInfo.push({idx:t,nodes:nodes.length,checked:checked.length,visible:trees[t].offsetParent!==null});
                }
                
                var inputInfo=[];
                for(var j=0;j<inputs.length;j++){
                    inputInfo.push({idx:j,ph:inputs[j].placeholder||'',val:inputs[j].value||'',type:inputs[j].type||'',visible:inputs[j].offsetParent!==null});
                }
                
                var tabInfo=[];
                for(var j=0;j<tabs.length;j++){
                    tabInfo.push({idx:j,text:tabs[j].textContent?.trim()?.substring(0,20)||'',active:tabs[j].classList?.contains('is-active')||false});
                }
                
                return{
                    trees:treeInfo,
                    inputs:inputInfo,
                    btnCount:btns.length,
                    pickers:pickers.length,
                    tabs:tabInfo
                };
            }
        }
        return{error:'no_dialog'};
    })()""")
    print(f"  tree_info: {tree_info}")
    
    # 在搜索框输入
    if tree_info and tree_info.get('inputs'):
        for inp in tree_info.get('inputs',[]):
            ph = inp.get('ph','')
            idx = inp.get('idx',0)
            if '查询' in ph or '搜索' in ph:
                print(f"  搜索: #{idx} ph={ph}")
                ev_iframe(f"""(function(){{
                    var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
                    for(var i=0;i<dialogs.length;i++){{
                        var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                        var title=header?.textContent?.trim()||'';
                        if(title.includes('经营范围选择')){{
                            var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]')||dialogs[i];
                            var inputs=body.querySelectorAll('input');
                            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                            s.call(inputs[{idx}],'软件开发');
                            inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                            inputs[{idx}].dispatchEvent(new Event('change',{{bubbles:true}}));
                            return;
                        }}
                    }}
                }})()""")
                time.sleep(3)
                break
    
    # 查看树节点
    tree_nodes2 = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]')||dialogs[i];
                var trees=body.querySelectorAll('.el-tree');
                for(var t=0;t<trees.length;t++){
                    if(!trees[t].offsetParent)continue;
                    var nodes=trees[t].querySelectorAll('.el-tree-node__content');
                    var result=[];
                    for(var n=0;n<Math.min(nodes.length,20);n++){
                        var text=nodes[n].textContent?.trim()||'';
                        var expanded=nodes[n].closest('.el-tree-node')?.classList?.contains('is-expanded')||false;
                        result.push({idx:n,text:text.substring(0,40),expanded:expanded});
                    }
                    return{treeIdx:t,total:nodes.length,nodes:result};
                }
            }
        }
    })()""")
    print(f"  tree_nodes2: total={tree_nodes2.get('total',0) if tree_nodes2 else 0}")
    for n in (tree_nodes2.get('nodes',[]) or []):
        marker = ' ✅' if '软件' in n.get('text','') else ''
        print(f"    [{n.get('idx')}] exp={n.get('expanded',False)} {n.get('text','')[:30]}{marker}")
    
    # 点击包含"软件"的树节点
    if tree_nodes2 and tree_nodes2.get('total',0) > 0:
        click_result = ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]')||dialogs[i];
                    var trees=body.querySelectorAll('.el-tree');
                    for(var t=0;t<trees.length;t++){
                        if(!trees[t].offsetParent)continue;
                        var nodes=trees[t].querySelectorAll('.el-tree-node__content');
                        for(var n=0;n<nodes.length;n++){
                            var text=nodes[n].textContent?.trim()||'';
                            if(text.includes('软件开发')||text.includes('信息技术咨询')){
                                // 检查是否有checkbox
                                var checkbox=nodes[n].querySelector('.el-checkbox__input');
                                if(checkbox){
                                    checkbox.click();
                                    return{type:'checkbox',text:text.substring(0,30),idx:n};
                                }
                                // 没有checkbox，直接点击
                                nodes[n].click();
                                return{type:'click',text:text.substring(0,30),idx:n};
                            }
                        }
                    }
                }
            }
            return{error:'not_found'};
        })()""")
        print(f"  click: {click_result}")
        time.sleep(2)
    
    # 点击对话框的确定按钮
    confirm = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var footer=dialogs[i].querySelector('.tni-dialog__footer,[class*="footer"]');
                if(!footer)footer=dialogs[i];
                var btns=footer.querySelectorAll('button,.el-button');
                for(var j=0;j<btns.length;j++){
                    var t=btns[j].textContent?.trim()||'';
                    if(t.includes('确定')||t.includes('确认')||t.includes('选择')){
                        btns[j].click();
                        return{clicked:t,idx:j};
                    }
                }
            }
        }
        return{error:'no_btn'};
    })()""")
    print(f"  confirm: {confirm}")
    time.sleep(2)
    
    iframe_ws.close()

# Step 5: 验证
print("\nStep 5: 验证")
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
                industryType:fd.industryType||fd.industryBigType||bdi.industryType||'',
                businessArea:fd.businessArea||bdi.businessArea||bdi.businessScope||'',
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

# 检查验证错误
errors = ev("""(function(){
    var errs=document.querySelectorAll('.el-form-item__error');
    var r=[];
    for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}
    return r.slice(0,10);
})()""")
print(f"  validation errors: {errors}")

ws.close()
print("✅ 完成")
