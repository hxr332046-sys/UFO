#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""选择行业类型子选项[65] + 等待经营范围对话框加载 + 选择经营范围"""
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

# Step 1: 重新展开行业类型，选择子选项[65]
print("\nStep 1: 行业类型 - 选择[65]软件和信息技术服务业")
# 先点击行业类型输入框
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

# 找到[I]节点并展开，然后选择[65]
select_result = ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        
        // 先找[I]并展开
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            if(text.includes('[I]信息传输')){
                var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                if(expandIcon&&!nodes[i].closest('.el-tree-node')?.classList?.contains('is-expanded')){
                    expandIcon.click();
                }
                break;
            }
        }
    }
    return{step:'expand_I'};
})()""")
time.sleep(2)

# 现在选择[65]子节点
select_child = ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            // 选择[65]软件和信息技术服务业（叶子节点）
            if(text.includes('65')&&text.includes('软件')){
                nodes[i].click();
                return{selected:text.substring(0,40),idx:i};
            }
        }
    }
    return{error:'no_65'};
})()""")
print(f"  select_child: {select_child}")
time.sleep(2)

# 关闭下拉（点击其他地方）
ev("document.body.click()")
time.sleep(1)

# 验证行业类型值
industry_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            return{value:input?.value||'',label:label};
        }
    }
})()""")
print(f"  industry value: {industry_val}")

# Step 2: 经营范围 - 点击添加按钮
print("\nStep 2: 经营范围")
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
time.sleep(5)  # 等待对话框加载

# Step 3: 通过iframe CDP操作经营范围对话框
print("\nStep 3: iframe CDP操作")
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
    
    # 等待对话框加载完成
    for attempt in range(5):
        dialog_ready = ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                    if(!body)body=dialogs[i];
                    var trees=body.querySelectorAll('.el-tree');
                    var inputs=body.querySelectorAll('input');
                    var btns=body.querySelectorAll('button');
                    var allEls=body.querySelectorAll('*');
                    return{trees:trees.length,inputs:inputs.length,btns:btns.length,allEls:allEls.length,
                        bodyHTML:body.innerHTML?.substring(0,200)||''};
                }
            }
            return{found:false};
        })()""")
        print(f"  attempt {attempt}: {dialog_ready}")
        
        if dialog_ready and dialog_ready.get('trees',0) > 0:
            break
        time.sleep(3)
    
    # 详细分析对话框
    dialog_detail = ev_iframe("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
        for(var i=0;i<dialogs.length;i++){
            var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
            var title=header?.textContent?.trim()||'';
            if(title.includes('经营范围选择')){
                var body=dialogs[i].querySelector('.tni-dialog__body,[class*="body"]');
                if(!body)body=dialogs[i];
                
                // 列出所有子元素
                var children=body.children;
                var childInfo=[];
                for(var c=0;c<children.length;c++){
                    childInfo.push({tag:children[c].tagName,class:children[c].className?.substring(0,40)||'',text:children[c].textContent?.trim()?.substring(0,40)||''});
                }
                
                // 找所有Vue组件
                var comps=[];
                var allEls=body.querySelectorAll('*');
                for(var e=0;e<allEls.length;e++){
                    var comp=allEls[e].__vue__;
                    if(comp&&comp.$options?.name){
                        comps.push({name:comp.$options.name,tag:allEls[e].tagName});
                    }
                }
                
                return{childCount:children.length,children:childInfo.slice(0,10),vueComps:comps.slice(0,10),
                    bodyHTML:body.innerHTML?.substring(0,500)||''};
            }
        }
    })()""")
    print(f"  dialog_detail: children={dialog_detail.get('childCount',0) if dialog_detail else 0}")
    if dialog_detail:
        for c in (dialog_detail.get('children',[]) or []):
            print(f"    {c.get('tag')} class={c.get('class','')[:30]} text={c.get('text','')[:30]}")
        for c in (dialog_detail.get('vueComps',[]) or []):
            print(f"    Vue: {c.get('name')} tag={c.get('tag')}")
    
    # 如果对话框内容为空，可能是嵌套iframe
    if dialog_detail and dialog_detail.get('childCount',0) == 0:
        print("  对话框内容为空，检查是否有嵌套iframe")
        nested = ev_iframe("""(function(){
            var dialogs=document.querySelectorAll('.tni-dialog.custom-dialog');
            for(var i=0;i<dialogs.length;i++){
                var header=dialogs[i].querySelector('.tni-dialog__header,[class*="header"]');
                var title=header?.textContent?.trim()||'';
                if(title.includes('经营范围选择')){
                    var iframes=dialogs[i].querySelectorAll('iframe');
                    var result=[];
                    for(var j=0;j<iframes.length;j++){
                        result.push({src:iframes[j].src||iframes[j].getAttribute('data-src')||'',id:iframes[j].id||''});
                    }
                    return{iframes:result};
                }
            }
        })()""")
        print(f"  nested iframes: {nested}")
        
        # 如果有嵌套iframe，获取其CDP target
        if nested and nested.get('iframes'):
            for iframe in nested.get('iframes',[]):
                src = iframe.get('src','')
                print(f"  嵌套iframe: {src[:80]}")
    
    # 尝试直接在iframe中查找所有对话框
    all_dialogs = ev_iframe("""(function(){
        var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
        var result=[];
        for(var i=0;i<all.length;i++){
            var visible=all[i].offsetParent!==null||getComputedStyle(all[i]).display!=='none';
            if(visible){
                var text=all[i].textContent?.trim()?.substring(0,60)||'';
                if(text.includes('经营范围')||text.includes('经营用语')){
                    var trees=all[i].querySelectorAll('.el-tree,[class*="tree"]');
                    var inputs=all[i].querySelectorAll('input');
                    result.push({idx:i,tag:all[i].tagName,class:all[i].className?.substring(0,30)||'',
                        trees:trees.length,inputs:inputs.length,text:text.substring(0,40)});
                }
            }
        }
        return result;
    })()""")
    print(f"  all_dialogs_with_scope: {all_dialogs}")
    
    # 如果找到了有tree的对话框，操作它
    if all_dialogs:
        for d in all_dialogs:
            if d.get('trees',0) > 0 or d.get('inputs',0) > 0:
                print(f"  操作对话框: trees={d.get('trees')} inputs={d.get('inputs')}")
                
                # 在搜索框输入
                ev_iframe(f"""(function(){{
                    var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
                    var el=all[{d.get('idx',0)}];
                    var inputs=el.querySelectorAll('input');
                    for(var j=0;j<inputs.length;j++){{
                        var ph=inputs[j].placeholder||'';
                        if(ph.includes('查询')||ph.includes('搜索')||ph.includes('关键字')){{
                            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                            s.call(inputs[j],'软件开发');
                            inputs[j].dispatchEvent(new Event('input',{{bubbles:true}}));
                            return{{searched:true,ph:ph}};
                        }}
                    }}
                    return{{searched:false}};
                }})()""")
                time.sleep(3)
                
                # 查看树节点
                tree_result = ev_iframe(f"""(function(){{
                    var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
                    var el=all[{d.get('idx',0)}];
                    var trees=el.querySelectorAll('.el-tree');
                    for(var t=0;t<trees.length;t++){{
                        if(!trees[t].offsetParent)continue;
                        var nodes=trees[t].querySelectorAll('.el-tree-node__content');
                        var result=[];
                        for(var n=0;n<Math.min(nodes.length,15);n++){{
                            result.push({{idx:n,text:nodes[n].textContent?.trim()?.substring(0,40)||''}});
                        }}
                        return{{total:nodes.length,nodes:result}};
                    }}
                }})()""")
                print(f"  tree: total={tree_result.get('total',0) if tree_result else 0}")
                for n in (tree_result.get('nodes',[]) or []):
                    marker = ' ✅' if '软件' in n.get('text','') else ''
                    print(f"    [{n.get('idx')}] {n.get('text','')[:30]}{marker}")
                
                # 点击包含"软件"的节点
                click_result = ev_iframe(f"""(function(){{
                    var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
                    var el=all[{d.get('idx',0)}];
                    var trees=el.querySelectorAll('.el-tree');
                    for(var t=0;t<trees.length;t++){{
                        if(!trees[t].offsetParent)continue;
                        var nodes=trees[t].querySelectorAll('.el-tree-node__content');
                        for(var n=0;n<nodes.length;n++){{
                            var text=nodes[n].textContent?.trim()||'';
                            if(text.includes('软件开发')||text.includes('信息技术咨询')){{
                                // 检查checkbox
                                var cb=nodes[n].querySelector('.el-checkbox__input:not(.is-checked)');
                                if(cb){{cb.click();return{{type:'checkbox',text:text.substring(0,30)}}}}
                                nodes[n].click();
                                return{{type:'click',text:text.substring(0,30)}};
                            }}
                        }}
                    }}
                    return{{error:'not_found'}};
                }})()""")
                print(f"  click: {click_result}")
                time.sleep(1)
                
                # 再选几个
                ev_iframe(f"""(function(){{
                    var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
                    var el=all[{d.get('idx',0)}];
                    var trees=el.querySelectorAll('.el-tree');
                    for(var t=0;t<trees.length;t++){{
                        if(!trees[t].offsetParent)continue;
                        var cbs=trees[t].querySelectorAll('.el-checkbox__input:not(.is-checked)');
                        for(var c=0;c<Math.min(cbs.length,3);c++){{
                            cbs[c].click();
                        }}
                    }}
                }})()""")
                time.sleep(1)
                
                # 点击确定
                confirm = ev_iframe(f"""(function(){{
                    var all=document.querySelectorAll('[class*="dialog"],[class*="modal"]');
                    var el=all[{d.get('idx',0)}];
                    var btns=el.querySelectorAll('button,.el-button');
                    for(var j=0;j<btns.length;j++){{
                        var t=btns[j].textContent?.trim()||'';
                        if((t.includes('确定')||t.includes('确认')||t.includes('选择')||t.includes('保存'))&&btns[j].offsetParent!==null){{
                            btns[j].click();return{{clicked:t}};
                        }}
                    }}
                }})()""")
                print(f"  confirm: {confirm}")
                time.sleep(2)
                break
    
    iframe_ws.close()

# Step 4: 验证
print("\nStep 4: 验证")
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

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r.slice(0,10)})()""")
print(f"  validation errors: {errors}")

ws.close()
print("✅ 完成")
