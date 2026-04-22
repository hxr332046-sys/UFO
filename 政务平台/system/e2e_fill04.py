#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""行业类型懒加载触发 + 经营范围iframe选择 + 完整填写"""
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

# Step 1: 行业类型 - 触发懒加载
print("\nStep 1: 行业类型懒加载")
# tne-select需要先focus触发加载
load_result = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 获取popperClass判断
            var popperClass=comp.popperClass||'';
            
            // 触发visibleChange
            comp.visible=true;
            comp.$emit('visible-change',true);
            comp.$nextTick(function(){
                // 模拟focus
                var input=select.querySelector('input');
                if(input){input.focus();input.dispatchEvent(new Event('focus',{bubbles:true}))}
            });
            
            return{triggered:true,popperClass:popperClass,remote:comp.remote,filterable:comp.filterable};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  load_result: {load_result}")
time.sleep(3)

# 检查选项是否加载
opts_check = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            var opts=comp.options||[];
            var result=opts.slice(0,8).map(function(o){return{label:o.label?.substring(0,60)||'(empty)',value:o.value||'',hasChildren:!!o.children,childCount:o.children?.length||0}});
            return{total:opts.length,options:result};
        }
    }
})()""")
print(f"  opts_check: total={opts_check.get('total',0) if opts_check else 0}")
for o in (opts_check.get('options',[]) or []):
    print(f"    val={o.get('value','')} children={o.get('hasChildren',False)}({o.get('childCount',0)}) label={o.get('label','')[:50]}")

# 如果选项还是空，尝试点击输入框展开下拉
if opts_check and opts_check.get('total',0) <= 4:
    print("  选项未加载，尝试点击展开")
    ev("""(function(){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
            if(label.includes('行业类型')){
                var input=items[i].querySelector('input');
                if(input){
                    input.click();
                    input.dispatchEvent(new Event('click',{bubbles:true}));
                    input.dispatchEvent(new Event('mousedown',{bubbles:true}));
                    input.dispatchEvent(new Event('focus',{bubbles:true}));
                }
                return;
            }
        }
    })()""")
    time.sleep(3)
    
    # 检查下拉面板
    dropdown = ev("""(function(){
        var popper=document.querySelectorAll('.el-select-dropdown__item,.el-cascader-node,[class*="popper"] li');
        var r=[];
        for(var i=0;i<Math.min(popper.length,20);i++){
            var t=popper[i].textContent?.trim()||'';
            if(t)r.push({idx:i,text:t.substring(0,60)});
        }
        return{total:popper.length,visible:r.length,items:r};
    })()""")
    print(f"  dropdown: total={dropdown.get('total',0)} visible={dropdown.get('visible',0)}")
    for item in (dropdown.get('items',[]) or [])[:8]:
        print(f"    {item.get('idx')}: {item.get('text','')[:50]}")

    # 选择[I]选项
    if dropdown.get('visible',0) > 0:
        selected = ev("""(function(){
            var popper=document.querySelectorAll('.el-select-dropdown__item,.el-cascader-node,[class*="popper"] li');
            for(var i=0;i<popper.length;i++){
                var t=popper[i].textContent?.trim()||'';
                if(t.includes('[I]')||t.includes('信息传输')){
                    popper[i].click();
                    popper[i].dispatchEvent(new Event('click',{bubbles:true}));
                    return{selected:t.substring(0,50),idx:i};
                }
            }
            return{error:'no_I'};
        })()""")
        print(f"  selected: {selected}")
        time.sleep(2)
        
        # 如果需要选择子选项
        child_dropdown = ev("""(function(){
            var popper=document.querySelectorAll('.el-select-dropdown__item,[class*="popper"] li');
            var r=[];
            for(var i=0;i<popper.length;i++){
                var t=popper[i].textContent?.trim()||'';
                if(t&&popper[i].offsetParent!==null)r.push({idx:i,text:t.substring(0,60)});
            }
            return{visible:r.length,items:r.slice(0,10)};
        })()""")
        print(f"  child: visible={child_dropdown.get('visible',0)} items={child_dropdown.get('items',[])}")
        
        if child_dropdown.get('visible',0) > 0:
            for item in (child_dropdown.get('items',[]) or []):
                if '软件' in item.get('text','') or '信息技术' in item.get('text',''):
                    ev(f"""(function(){{
                        var popper=document.querySelectorAll('.el-select-dropdown__item,[class*="popper"] li');
                        if(popper[{item.get('idx',0)}])popper[{item.get('idx',0)}].click();
                    }})()""")
                    print(f"  选择子选项: {item.get('text','')[:40]}")
                    time.sleep(2)
                    break

# Step 2: 经营范围iframe - 通过CDP选择
print("\nStep 2: 经营范围iframe选择")
# 先点击添加规范经营用语
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

# 连接iframe CDP
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
core_targets = [t for t in targets if 'core.html' in t.get('url','')]
print(f"  core targets: {len(core_targets)}")

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
    
    # 分析iframe内容
    iframe_analysis = ev_iframe("""(function(){
        // 找经营范围选择对话框
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="custom-dialog"],.el-dialog');
        var result=[];
        for(var i=0;i<dialogs.length;i++){
            var visible=dialogs[i].offsetParent!==null||dialogs[i].style?.display!=='none'||getComputedStyle(dialogs[i]).display!=='none';
            if(visible){
                var text=dialogs[i].textContent?.trim()?.substring(0,100)||'';
                var inputs=dialogs[i].querySelectorAll('input');
                var btns=dialogs[i].querySelectorAll('button');
                var trees=dialogs[i].querySelectorAll('.el-tree,[class*="tree"]');
                result.push({idx:i,text:text.substring(0,60),inputs:inputs.length,btns:btns.length,trees:trees.length,className:dialogs[i].className?.substring(0,40)||''});
            }
        }
        return{dialogCount:result.length,dialogs:result};
    })()""")
    print(f"  iframe dialogs: {iframe_analysis}")
    
    # 如果没有可见对话框，可能在主页面
    # 检查所有可见元素
    visible_els = ev_iframe("""(function(){
        var all=document.querySelectorAll('*');
        var visible=[];
        for(var i=0;i<all.length;i++){
            if(all[i].offsetParent!==null&&all[i].textContent?.trim()?.includes('经营范围')){
                visible.push({tag:all[i].tagName,class:all[i].className?.substring(0,30)||'',text:all[i].textContent?.trim()?.substring(0,40)||''});
                if(visible.length>5)break;
            }
        }
        return visible;
    })()""")
    print(f"  visible with 经营范围: {visible_els}")
    
    # 在iframe中搜索经营范围
    search_result = ev_iframe("""(function(){
        var inputs=document.querySelectorAll('input');
        for(var i=0;i<inputs.length;i++){
            var ph=inputs[i].placeholder||inputs[i].getAttribute('placeholder')||'';
            var parent=inputs[i].closest('[class*="search"],[class*="query"],[class*="scope"]');
            if(ph.includes('查询')||ph.includes('搜索')||ph.includes('关键字')||parent){
                var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                s.call(inputs[i],'软件开发');
                inputs[i].dispatchEvent(new Event('input',{bubbles:true}));
                inputs[i].dispatchEvent(new Event('change',{bubbles:true}));
                return{searched:true,ph:ph,idx:i};
            }
        }
        return{searched:false,inputs:inputs.length};
    })()""")
    print(f"  search: {search_result}")
    time.sleep(3)
    
    # 查看搜索结果
    tree_result = ev_iframe("""(function(){
        var trees=document.querySelectorAll('.el-tree');
        var result=[];
        for(var i=0;i<trees.length;i++){
            var nodes=trees[i].querySelectorAll('.el-tree-node');
            var checked=trees[i].querySelectorAll('.is-checked .el-checkbox__input');
            result.push({idx:i,nodes:nodes.length,checked:checked.length,visible:trees[i].offsetParent!==null});
        }
        // 也检查搜索结果列表
        var lists=document.querySelectorAll('[class*="result"] li,[class*="item-list"] li,[class*="search-result"]');
        var listItems=[];
        for(var i=0;i<Math.min(lists.length,10);i++){
            listItems.push({text:lists[i].textContent?.trim()?.substring(0,40)||''});
        }
        return{trees:result,listItems:listItems.slice(0,5)};
    })()""")
    print(f"  tree_result: {tree_result}")
    
    # 选择树节点或列表项
    select_result = ev_iframe("""(function(){
        // 尝试勾选树节点
        var checkboxes=document.querySelectorAll('.el-tree-node .el-checkbox__input:not(.is-checked)');
        var selected=[];
        for(var i=0;i<Math.min(checkboxes.length,3);i++){
            var node=checkboxes[i].closest('.el-tree-node');
            var text=node?.textContent?.trim()?.substring(0,30)||'';
            if(text.includes('软件')||text.includes('信息技术')||text.includes('数据处理')){
                checkboxes[i].click();
                selected.push(text);
            }
        }
        // 如果没找到匹配的，选前3个
        if(selected.length===0){
            for(var i=0;i<Math.min(checkboxes.length,3);i++){
                var node=checkboxes[i].closest('.el-tree-node');
                var text=node?.textContent?.trim()?.substring(0,30)||'';
                checkboxes[i].click();
                selected.push(text);
            }
        }
        
        // 尝试点击列表项
        var listItems=document.querySelectorAll('[class*="result"] li,[class*="item-list"] li');
        for(var i=0;i<Math.min(listItems.length,3);i++){
            var text=listItems[i].textContent?.trim()?.substring(0,30)||'';
            if(text.includes('软件')||text.includes('信息技术')){
                listItems[i].click();
                selected.push('list:'+text);
            }
        }
        
        return{selected:selected,checkboxes:checkboxes.length};
    })()""")
    print(f"  select_result: {select_result}")
    time.sleep(1)
    
    # 点击确定按钮
    confirm_result = ev_iframe("""(function(){
        var btns=document.querySelectorAll('button,.el-button');
        for(var i=0;i<btns.length;i++){
            var t=btns[i].textContent?.trim()||'';
            if((t.includes('确定')||t.includes('确认')||t.includes('保存')||t.includes('选择'))&&btns[i].offsetParent!==null){
                btns[i].click();
                return{clicked:t,idx:i};
            }
        }
        return{error:'no_confirm_btn'};
    })()""")
    print(f"  confirm: {confirm_result}")
    time.sleep(2)
    
    iframe_ws.close()

# Step 3: 验证最终状态
print("\nStep 3: 验证")
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
    var errs=document.querySelectorAll('.el-form-item__error,[class*="error"]');
    var r=[];
    for(var i=0;i<errs.length;i++){
        var t=errs[i].textContent?.trim()||'';
        if(t)r.push(t.substring(0,40));
    }
    return r.slice(0,10);
})()""")
print(f"  errors: {errors}")

ws.close()
print("✅ 完成")
