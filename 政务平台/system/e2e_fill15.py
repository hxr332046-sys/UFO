#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: 行业类型选I65 + 经营范围对话框(无iframe,直接在主页面)"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=15)

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

# ============================================================
# Step 1: 清除错误的行业类型，重新选择I65
# ============================================================
print("\nStep 1: 重新选择行业类型 I65")

# 先清除当前值
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(select){
                var comp=select.__vue__;
                if(comp){
                    // 清除当前选中
                    comp.$emit('input','');
                    comp.$emit('change','');
                    comp.selectedLabel='';
                    comp.value='';
                }
            }
            // 也点击clear图标
            var clearBtn=items[i].querySelector('.el-select__caret.is-circle-close,.el-icon-circle-close');
            if(clearBtn)clearBtn.click();
            return;
        }
    }
})()""")
time.sleep(1)

# 点击输入框打开下拉
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click()}
            return;
        }
    }
})()""")
time.sleep(3)

# 列出当前可见节点
visible_nodes = ev("""(function(){
    var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var nodes=tree.querySelectorAll('.el-tree-node__content');
        var result=[];
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            var isExpanded=nodes[i].closest('.el-tree-node')?.classList?.contains('is-expanded')||false;
            result.push({idx:i,text:text.substring(0,40),expanded:isExpanded});
        }
        return{total:nodes.length,nodes:result};
    }
})()""")
print(f"  可见节点: {visible_nodes.get('total',0) if visible_nodes else 0}")

# 找到[I]节点索引并展开
i_node = ev("""(function(){
    var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var nodes=tree.querySelectorAll('.el-tree-node__content');
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            if(text.match(/\\[I\\]/)&&text.includes('信息传输')){
                // 点击展开图标
                var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                if(expandIcon&&!expandIcon.classList.contains('expanded')){
                    expandIcon.click();
                }
                return{idx:i,text:text.substring(0,30),expanded:true};
            }
        }
    }
    return{error:'no_I_node'};
})()""")
print(f"  [I]节点: {i_node}")
time.sleep(2)

# 展开后找[65]并展开
ev("""(function(){
    var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var nodes=tree.querySelectorAll('.el-tree-node__content');
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            if(text.includes('[65]')&&text.includes('软件和信息技术')){
                var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                if(expandIcon&&!expandIcon.classList.contains('expanded')){
                    expandIcon.click();
                }
                return{idx:i,text:text.substring(0,30)};
            }
        }
    }
})()""")
time.sleep(2)

# 点击[65]节点选中（叶子节点级别选择）
select_result = ev("""(function(){
    var poppers=document.querySelectorAll('.el-select-dropdown,.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null&&poppers[p].style?.display==='none')continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var nodes=tree.querySelectorAll('.el-tree-node__content');
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            // 选中[65]软件和信息技术服务业这个中类节点
            if(text.includes('[65]')&&text.includes('软件和信息技术服务业')){
                nodes[i].click();
                return{selected:text.substring(0,40)};
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"  选中: {select_result}")
time.sleep(2)

# 验证行业类型值
industry_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            return{value:input?.value||''};
        }
    }
})()""")
print(f"  行业类型值: {industry_val}")

# 关闭下拉
ev("document.body.click()")
time.sleep(1)

# ============================================================
# Step 2: 经营范围对话框（无iframe，直接在主页面）
# ============================================================
print("\nStep 2: 经营范围对话框")

# 点击"添加规范经营用语"按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){
            btns[i].click();
            return{clicked:t};
        }
    }
})()""")
time.sleep(3)

# 检查对话框内容
dialog_content = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        // 分析对话框结构
        var body=d.querySelector('.tni-dialog__body,[class*="body"],.el-dialog__body');
        if(!body)body=d;
        
        var inputs=body.querySelectorAll('input');
        var inputList=[];
        for(var j=0;j<inputs.length;j++){
            inputList.push({idx:j,placeholder:inputs[j].placeholder||'',type:inputs[j].type,class:inputs[j].className?.substring(0,30)||''});
        }
        
        var trees=body.querySelectorAll('.el-tree,[class*="tree"]');
        var treeList=[];
        for(var j=0;j<trees.length;j++){
            var nodes=trees[j].querySelectorAll('.el-tree-node__content');
            treeList.push({idx:j,nodeCount:nodes.length,firstNodes:[]});
            for(var k=0;k<Math.min(nodes.length,5);k++){
                treeList[j].firstNodes.push(nodes[k].textContent?.trim()?.substring(0,35)||'');
            }
        }
        
        var btns=body.querySelectorAll('button,.el-button');
        var btnList=[];
        for(var j=0;j<btns.length;j++){
            btnList.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||''});
        }
        
        var checkboxes=body.querySelectorAll('.el-checkbox');
        var tabs=body.querySelectorAll('.el-tabs__item,[class*="tab"]');
        
        return{
            visible:true,
            inputCount:inputs.length,
            inputs:inputList.slice(0,5),
            treeCount:trees.length,
            trees:treeList,
            btnCount:btns.length,
            btns:btnList,
            checkboxCount:checkboxes.length,
            tabCount:tabs.length,
            textSample:body.textContent?.trim()?.substring(0,100)||''
        };
    }
    return{visible:false};
})()""")
print(f"  对话框结构: inputs={dialog_content.get('inputCount',0)} trees={dialog_content.get('treeCount',0)} btns={dialog_content.get('btnCount',0)} checkboxes={dialog_content.get('checkboxCount',0)} tabs={dialog_content.get('tabCount',0)}")

if dialog_content.get('inputCount',0) > 0:
    print(f"  输入框: {dialog_content.get('inputs',[])}")

if dialog_content.get('trees'):
    for t in dialog_content.get('trees',[]):
        print(f"  树{t.get('idx',0)}: {t.get('nodeCount',0)}节点 → {t.get('firstNodes',[])}")

if dialog_content.get('btns'):
    print(f"  按钮: {dialog_content.get('btns',[])}")

# 在搜索框输入"软件开发"
search_result = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        var inputs=d.querySelectorAll('input');
        for(var j=0;j<inputs.length;j++){
            var ph=inputs[j].placeholder||'';
            if(ph.includes('关键词')||ph.includes('搜索')||ph.includes('检索')){
                var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                s.call(inputs[j],'软件开发');
                inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
                inputs[j].dispatchEvent(new Event('change',{bubbles:true}));
                inputs[j].dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,key:'Enter'}));
                return{search:'软件开发',inputIdx:j};
            }
        }
    }
    return{error:'no_search_input'};
})()""")
print(f"\n  搜索: {search_result}")
time.sleep(3)

# 查看搜索结果
search_results = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        // 找所有可能的结果元素
        var allItems=d.querySelectorAll('.el-tree-node__content,[class*="result"],[class*="item"],li,td');
        var matches=[];
        for(var j=0;j<allItems.length;j++){
            var text=allItems[j].textContent?.trim()||'';
            if(text.includes('软件')||text.includes('信息技术')||text.includes('开发')){
                var hasCheckbox=!!allItems[j].querySelector('.el-checkbox,[class*="checkbox"]');
                matches.push({idx:j,text:text.substring(0,50),hasCheckbox:hasCheckbox});
            }
        }
        
        // 也检查checkbox
        var checkboxes=d.querySelectorAll('.el-checkbox');
        var cbMatches=[];
        for(var j=0;j<checkboxes.length;j++){
            var text=checkboxes[j].closest('div,li,td')?.textContent?.trim()||'';
            if(text.includes('软件')||text.includes('信息技术')){
                cbMatches.push({idx:j,text:text.substring(0,50),checked:checkboxes[j].classList.contains('is-checked')});
            }
        }
        
        return{itemMatches:matches.slice(0,10),checkboxMatches:cbMatches};
    }
})()""")
print(f"  搜索结果: items={len(search_results.get('itemMatches',[])) if search_results else 0} checkboxes={len(search_results.get('checkboxMatches',[])) if search_results else 0}")
if search_results:
    for m in (search_results.get('itemMatches') or [])[:5]:
        print(f"    item: {m}")
    for m in (search_results.get('checkboxMatches') or [])[:5]:
        print(f"    checkbox: {m}")

# 点击匹配项的checkbox
if search_results and search_results.get('checkboxMatches'):
    for m in search_results.get('checkboxMatches',[]):
        if '软件开发' in m.get('text','') or '信息技术咨询' in m.get('text',''):
            ev(f"""(function(){{
                var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
                for(var i=0;i<dialogs.length;i++){{
                    var d=dialogs[i];
                    if(d.offsetParent===null&&d.style?.display==='none')continue;
                    var checkboxes=d.querySelectorAll('.el-checkbox');
                    if(checkboxes[{m['idx']}])checkboxes[{m['idx']}].click();
                    return;
                }}
            }})()""")
            time.sleep(0.5)
elif search_results and search_results.get('itemMatches'):
    # 点击包含"软件开发"的tree节点
    for m in search_results.get('itemMatches',[]):
        if '软件开发' in m.get('text',''):
            ev(f"""(function(){{
                var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
                for(var i=0;i<dialogs.length;i++){{
                    var d=dialogs[i];
                    if(d.offsetParent===null&&d.style?.display==='none')continue;
                    var nodes=d.querySelectorAll('.el-tree-node__content');
                    if(nodes[{m['idx']}])nodes[{m['idx']}].click();
                    return;
                }}
            }})()""")
            time.sleep(1)
            break

# 也尝试点击[I]门类展开经营范围树
ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        // 找左侧行业分类树
        var trees=d.querySelectorAll('.el-tree');
        for(var t=0;t<trees.length;t++){
            var nodes=trees[t].querySelectorAll('.el-tree-node__content');
            for(var n=0;n<nodes.length;n++){
                var text=nodes[n].textContent?.trim()||'';
                if(text.includes('信息传输')||text.includes('[I]')){
                    // 展开
                    var expandIcon=nodes[n].querySelector('.el-tree-node__expand-icon');
                    if(expandIcon&&!expandIcon.classList.contains('expanded')){
                        expandIcon.click();
                    }
                    return;
                }
            }
        }
    }
})()""")
time.sleep(2)

# 在对话框中找[65]并展开选择
ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        var trees=d.querySelectorAll('.el-tree');
        for(var t=0;t<trees.length;t++){
            var nodes=trees[t].querySelectorAll('.el-tree-node__content');
            for(var n=0;n<nodes.length;n++){
                var text=nodes[n].textContent?.trim()||'';
                if(text.includes('[65]')&&text.includes('软件')){
                    var expandIcon=nodes[n].querySelector('.el-tree-node__expand-icon');
                    if(expandIcon&&!expandIcon.classList.contains('expanded')){
                        expandIcon.click();
                    }
                    return;
                }
            }
        }
    }
})()""")
time.sleep(2)

# 点击"软件开发"叶子节点
scope_select = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        var trees=d.querySelectorAll('.el-tree');
        for(var t=0;t<trees.length;t++){
            var nodes=trees[t].querySelectorAll('.el-tree-node__content');
            for(var n=0;n<nodes.length;n++){
                var text=nodes[n].textContent?.trim()||'';
                if(text.includes('软件开发')&&!text.includes('信息技术')){
                    nodes[n].click();
                    // 也找checkbox
                    var cb=nodes[n].querySelector('.el-checkbox');
                    if(cb)cb.click();
                    return{selected:text.substring(0,40),hasCheckbox:!!cb};
                }
            }
        }
    }
    return{error:'not_found'};
})()""")
print(f"\n  选择软件开发: {scope_select}")
time.sleep(1)

# 也选"信息技术咨询服务"
scope_select2 = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        var trees=d.querySelectorAll('.el-tree');
        for(var t=0;t<trees.length;t++){
            var nodes=trees[t].querySelectorAll('.el-tree-node__content');
            for(var n=0;n<nodes.length;n++){
                var text=nodes[n].textContent?.trim()||'';
                if(text.includes('信息技术咨询')){
                    nodes[n].click();
                    var cb=nodes[n].querySelector('.el-checkbox');
                    if(cb)cb.click();
                    return{selected:text.substring(0,40)};
                }
            }
        }
    }
})()""")
print(f"  选择信息技术咨询: {scope_select2}")
time.sleep(1)

# 检查"已选择"区域
selected_scope = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        // 找已选择区域
        var selected=d.querySelectorAll('[class*="selected"],[class*="chosen"],[class*="picked"]');
        var texts=[];
        for(var j=0;j<selected.length;j++){
            var text=selected[j].textContent?.trim()||'';
            if(text.length>5)texts.push(text.substring(0,50));
        }
        // 也检查"主营项目"标记
        var mainItems=d.querySelectorAll('[class*="main"],[class*="primary"]');
        var mainTexts=[];
        for(var j=0;j<mainItems.length;j++){
            var text=mainItems[j].textContent?.trim()||'';
            if(text.length>5&&text.length<80)mainTexts.push(text.substring(0,50));
        }
        return{selectedTexts:texts.slice(0,10),mainTexts:mainTexts.slice(0,5)};
    }
})()""")
print(f"\n  已选择: {selected_scope}")

# 点击确定按钮
confirm = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,.el-dialog');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&d.style?.display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        var btns=d.querySelectorAll('button,.el-button');
        for(var j=0;j<btns.length;j++){
            var t=btns[j].textContent?.trim()||'';
            if((t.includes('确定')||t.includes('确认')||t.includes('完成'))&&btns[j].offsetParent!==null){
                btns[j].click();
                return{clicked:t};
            }
        }
    }
    return{error:'no_confirm'};
})()""")
print(f"  确定按钮: {confirm}")
time.sleep(3)

# ============================================================
# Step 3: 验证
# ============================================================
print("\nStep 3: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

industry_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            return{value:input?.value||''};
        }
    }
})()""")
print(f"  行业类型: {industry_val}")

scope_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('经营范围')){
            var content=items[i].querySelector('.el-form-item__content');
            return{text:content?.textContent?.trim()?.substring(0,80)||''};
        }
    }
})()""")
print(f"  经营范围: {scope_val}")

ws.close()
print("\n✅ 完成")
