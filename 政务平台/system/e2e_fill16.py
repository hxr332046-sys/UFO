#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精简版: 行业类型I65 + 经营范围对话框(无iframe)"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    ws = websocket.create_connection(ws_url, timeout=8)
    return ws

ws = get_ws()
_mid = 0
def ev(js, timeout=8):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    except:
        try: ws = get_ws()
        except: return None
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    try:
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
    except: return None

# 检查当前状态
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# ============================================================
# Step 1: 行业类型 - 清除旧值，选I65
# ============================================================
print("\nStep 1: 行业类型 I65")

# 先看当前值
cur = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            return{value:input?.value||'',error:items[i].querySelector('.el-form-item__error')?.textContent||''};
        }
    }
})()""")
print(f"  当前值: {cur}")

# 清除并重新选择
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(select){var comp=select.__vue__;if(comp){comp.$emit('input','');comp.selectedLabel='';}}
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click();}
            return;
        }
    }
})()""")
time.sleep(2)

# 检查下拉是否出现，找到[I]节点
dropdown = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var p=0;p<poppers.length;p++){
        var el=poppers[p];
        if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
        var tree=el.querySelector('.el-tree');
        if(!tree)continue;
        var nodes=tree.querySelectorAll('.el-tree-node__content');
        var result=[];
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            result.push({idx:i,text:text.substring(0,35)});
        }
        return{total:nodes.length,nodes:result};
    }
    return{error:'no_dropdown'};
})()""")
print(f"  下拉: total={dropdown.get('total',0) if dropdown else 0}")

# 找[I]的索引
i_idx = None
if dropdown and dropdown.get('nodes'):
    for n in dropdown['nodes']:
        if '[I]' in n.get('text','') and '信息传输' in n.get('text',''):
            i_idx = n['idx']
            print(f"  [I]索引: {i_idx}")
            break

if i_idx is not None:
    # 点击[I]展开
    ev(f"""(function(){{
        var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
        for(var p=0;p<poppers.length;p++){{
            var el=poppers[p];
            if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
            var tree=el.querySelector('.el-tree');if(!tree)continue;
            var nodes=tree.querySelectorAll('.el-tree-node__content');
            if(nodes[{i_idx}]){{
                var expand=nodes[{i_idx}].querySelector('.el-tree-node__expand-icon');
                if(expand)expand.click();
            }}
        }}
    }})()""")
    time.sleep(2)
    
    # 找[65]并点击
    result_65 = ev("""(function(){
        var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
        for(var p=0;p<poppers.length;p++){
            var el=poppers[p];
            if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
            var tree=el.querySelector('.el-tree');if(!tree)continue;
            var nodes=tree.querySelectorAll('.el-tree-node__content');
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                if(text.includes('[65]')&&text.includes('软件和信息技术')){
                    nodes[i].click();
                    return{clicked:text.substring(0,35)};
                }
            }
        }
        return{error:'no_65'};
    })()""")
    print(f"  [65]选择: {result_65}")
    time.sleep(2)
else:
    print("  ❌ 未找到[I]节点")

# 验证
ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型'))return{value:items[i].querySelector('input')?.value||''};
    }
})()""")
print(f"  行业类型值: {ind_val}")

# 关闭下拉
ev("document.body.click()")
time.sleep(1)

# ============================================================
# Step 2: 经营范围对话框
# ============================================================
print("\nStep 2: 经营范围对话框")

# 点击添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(3)

# 检查对话框
dlg = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&getComputedStyle(d).display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        var body=d.querySelector('[class*="body"]')||d;
        var inputs=body.querySelectorAll('input');
        var trees=body.querySelectorAll('.el-tree');
        var btns=body.querySelectorAll('button,.el-button');
        var info={
            visible:true,
            inputs:inputs.length,
            trees:trees.length,
            btns:btns.length,
            inputPH:[],
            btnTexts:[]
        };
        for(var j=0;j<Math.min(inputs.length,5);j++)info.inputPH.push(inputs[j].placeholder||'');
        for(var j=0;j<Math.min(btns.length,10);j++)info.btnTexts.push(btns[j].textContent?.trim()?.substring(0,15)||'');
        return info;
    }
    return{visible:false};
})()""")
print(f"  对话框: {dlg}")

if dlg and dlg.get('visible'):
    # 在搜索框输入关键词
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
        for(var i=0;i<dialogs.length;i++){
            var d=dialogs[i];
            if(d.offsetParent===null&&getComputedStyle(d).display==='none')continue;
            if(!d.textContent?.includes('经营范围'))continue;
            var inputs=d.querySelectorAll('input');
            for(var j=0;j<inputs.length;j++){
                var ph=inputs[j].placeholder||'';
                if(ph.includes('关键词')||ph.includes('搜索')||ph.includes('检索')){
                    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                    s.call(inputs[j],'软件开发');
                    inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
                    return{ok:true};
                }
            }
        }
    })()""")
    time.sleep(3)
    
    # 查看搜索结果 - 找checkbox或tree节点
    results = ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
        for(var i=0;i<dialogs.length;i++){
            var d=dialogs[i];
            if(d.offsetParent===null&&getComputedStyle(d).display==='none')continue;
            if(!d.textContent?.includes('经营范围'))continue;
            
            // 找所有checkbox
            var cbs=d.querySelectorAll('.el-checkbox');
            var cbList=[];
            for(var j=0;j<Math.min(cbs.length,30);j++){
                var text=cbs[j].parentElement?.textContent?.trim()||cbs[j].closest('div,li')?.textContent?.trim()||'';
                if(text.length<100)cbList.push({idx:j,text:text.substring(0,40),checked:cbs[j].classList.contains('is-checked')});
            }
            
            // 找tree节点
            var trees=d.querySelectorAll('.el-tree');
            var treeNodes=[];
            for(var t=0;t<trees.length;t++){
                var nodes=trees[t].querySelectorAll('.el-tree-node__content');
                for(var n=0;n<Math.min(nodes.length,20);n++){
                    var text=nodes[n].textContent?.trim()||'';
                    if(text.includes('软件')||text.includes('信息技术')||text.includes('开发')){
                        treeNodes.push({treeIdx:t,nodeIdx:n,text:text.substring(0,40)});
                    }
                }
            }
            
            return{checkboxes:cbList,treeNodes:treeNodes};
        }
    })()""")
    print(f"  搜索结果: checkboxes={len(results.get('checkboxes',[])) if results else 0} treeNodes={len(results.get('treeNodes',[])) if results else 0}")
    if results:
        for c in results.get('checkboxes',[])[:5]:
            print(f"    cb[{c['idx']}]: {c['text']}")
        for n in results.get('treeNodes',[])[:5]:
            print(f"    tree[{n['treeIdx']}][{n['nodeIdx']}]: {n['text']}")
    
    # 点击checkbox选择"软件开发"
    if results and results.get('checkboxes'):
        for c in results['checkboxes']:
            if '软件开发' in c['text'] and not c.get('checked'):
                ev(f"""(function(){{var d=document.querySelector('.tni-dialog,[class*="dialog"]');var cbs=d.querySelectorAll('.el-checkbox');cbs[{c['idx']}].click()}})()""")
                print(f"  点击checkbox[{c['idx']}]: {c['text']}")
                time.sleep(1)
                break
    
    # 如果没有checkbox，尝试tree节点
    if results and results.get('treeNodes') and not results.get('checkboxes'):
        n = results['treeNodes'][0]
        ev(f"""(function(){{var d=document.querySelector('.tni-dialog');var trees=d.querySelectorAll('.el-tree');var nodes=trees[{n['treeIdx']}].querySelectorAll('.el-tree-node__content');nodes[{n['nodeIdx']}].click()}})()""")
        print(f"  点击treeNode: {n['text']}")
        time.sleep(1)
    
    # 也选"信息技术咨询"
    if results and results.get('checkboxes'):
        for c in results['checkboxes']:
            if '信息技术咨询' in c['text'] and not c.get('checked'):
                ev(f"""(function(){{var d=document.querySelector('.tni-dialog');var cbs=d.querySelectorAll('.el-checkbox');cbs[{c['idx']}].click()}})()""")
                print(f"  点击checkbox[{c['idx']}]: {c['text']}")
                time.sleep(1)
                break
    
    # 点击确定
    ev("""(function(){
        var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
        for(var i=0;i<dialogs.length;i++){
            var d=dialogs[i];
            if(d.offsetParent===null&&getComputedStyle(d).display==='none')continue;
            var btns=d.querySelectorAll('button,.el-button');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if((t.includes('确定')||t.includes('确认')||t.includes('完成'))&&btns[j].offsetParent!==null){
                    btns[j].click();return{clicked:t};
                }
            }
        }
    })()""")
    print("  点击确定")
    time.sleep(3)

# ============================================================
# Step 3: 验证
# ============================================================
print("\nStep 3: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

ind = ev("""(function(){var items=document.querySelectorAll('.el-form-item');for(var i=0;i<items.length;i++){var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';if(l.includes('行业类型'))return items[i].querySelector('input')?.value||''}return''})()""")
print(f"  行业类型: {ind}")

scope = ev("""(function(){var items=document.querySelectorAll('.el-form-item');for(var i=0;i<items.length;i++){var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';if(l.includes('经营范围'))return items[i].querySelector('.el-form-item__content')?.textContent?.trim()?.substring(0,80)||''}return''})()""")
print(f"  经营范围: {scope}")

ws.close()
print("\n✅ 完成")
