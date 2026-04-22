#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精简版: 逐步操作，避免WebSocket卡死"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=6)

def ev(js, timeout=6):
    try:
        ws = get_ws()
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

# 每次调用ev都新建连接，避免卡死

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: {fc}")

# ============================================================
# Step 1: 分析经营范围对话框结构
# ============================================================
print("\nStep 1: 打开经营范围对话框")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return 'clicked'}
    }
    return 'no_btn';
})()""")
time.sleep(5)

# 深度分析
dlg = ev("""(function(){
    var ds=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<ds.length;i++){
        var d=ds[i];
        if(d.offsetParent===null)continue;
        if(!d.textContent?.includes('经营范围'))continue;
        var r={cls:d.className?.substring(0,50),els:d.querySelectorAll('*').length};
        // iframe
        var ifs=d.querySelectorAll('iframe');
        r.iframes=[];
        for(var j=0;j<ifs.length;j++)r.iframes.push({src:ifs[j].src||ifs[j].getAttribute('src')||'',display:getComputedStyle(ifs[j]).display});
        // body
        var b=d.querySelector('[class*="body"]');
        if(b){
            r.bodyEls=b.querySelectorAll('*').length;
            r.bodyHTML=b.innerHTML?.substring(0,300)||'';
        }
        return r;
    }
    return 'no_dialog';
})()""")
print(f"  对话框: {dlg}")

# ============================================================
# Step 2: 检查CDP iframe targets
# ============================================================
print("\nStep 2: CDP targets")
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
for t in targets:
    print(f"  {t.get('type','')}: {t.get('url','')[:80]}")

# ============================================================
# Step 3: 行业类型 - 通过Vue store操作
# ============================================================
print("\nStep 3: 行业类型 - Vue store")

# 关闭对话框
ev("document.body.click()")
time.sleep(1)

# 打开行业类型下拉
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click();}
            return 'opened';
        }
    }
})()""")
time.sleep(3)

# 分析tree store
tree_info = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var comp=tree.__vue__;
        if(!comp)return 'no_comp';
        var s=comp.store;
        if(!s)return 'no_store';
        var roots=s.root?.childNodes||[];
        var r=[];
        for(var i=0;i<roots.length;i++){
            r.push({code:roots[i].data?.code||'',label:roots[i].data?.label||''.substring(0,20),isLeaf:roots[i].isLeaf,loaded:roots[i].loaded,expanded:roots[i].expanded,childCount:roots[i].childNodes?.length||0});
        }
        return{lazy:comp.lazy||comp.$props?.lazy||false,total:roots.length,roots:r.slice(0,5)};
    }
    return 'no_tree';
})()""")
print(f"  tree: {tree_info}")

# 展开I节点
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var comp=tree.__vue__;
        var s=comp?.store;if(!s)return 'no_store';
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){
                roots[i].expand();
                return 'expanded_I';
            }
        }
    }
    return 'no_I';
})()""")
time.sleep(4)

# 检查I子节点
i_kids = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper');
    for(var p=0;p<poppers.length;p++){
        if(poppers[p].offsetParent===null)continue;
        var tree=poppers[p].querySelector('.el-tree');
        if(!tree)continue;
        var s=tree.__vue__?.store;if(!s)return 'no_store';
        var roots=s.root?.childNodes||[];
        for(var i=0;i<roots.length;i++){
            if(roots[i].data?.code==='I'){
                var cs=roots[i].childNodes||[];
                var r=[];
                for(var j=0;j<cs.length;j++){
                    r.push({code:cs[j].data?.code||'',label:(cs[j].data?.label||'').substring(0,25),isLeaf:cs[j].isLeaf,loaded:cs[j].loaded,childCount:cs[j].childNodes?.length||0});
                }
                return{total:cs.length,kids:r};
            }
        }
    }
    return 'no_I';
})()""")
print(f"  [I]子节点: {i_kids}")

# 展开并选择65
if i_kids and isinstance(i_kids, dict) and i_kids.get('kids'):
    for k in i_kids['kids']:
        if k.get('code') == '65':
            # 先展开
            ev("""(function(){
                var poppers=document.querySelectorAll('.el-popper');
                for(var p=0;p<poppers.length;p++){
                    if(poppers[p].offsetParent===null)continue;
                    var tree=poppers[p].querySelector('.el-tree');
                    if(!tree)continue;
                    var s=tree.__vue__?.store;if(!s)return;
                    var roots=s.root?.childNodes||[];
                    for(var i=0;i<roots.length;i++){
                        if(roots[i].data?.code==='I'){
                            var cs=roots[i].childNodes||[];
                            for(var j=0;j<cs.length;j++){
                                if(cs[j].data?.code==='65'){
                                    cs[j].expand();
                                    return 'expanded_65';
                                }
                            }
                        }
                    }
                }
            })()""")
            time.sleep(3)
            
            # 选择65节点（点击）
            sel = ev("""(function(){
                var poppers=document.querySelectorAll('.el-popper');
                for(var p=0;p<poppers.length;p++){
                    if(poppers[p].offsetParent===null)continue;
                    var tree=poppers[p].querySelector('.el-tree');
                    if(!tree)continue;
                    var comp=tree.__vue__;if(!comp)return;
                    var s=comp.store;if(!s)return;
                    var roots=s.root?.childNodes||[];
                    for(var i=0;i<roots.length;i++){
                        if(roots[i].data?.code==='I'){
                            var cs=roots[i].childNodes||[];
                            for(var j=0;j<cs.length;j++){
                                if(cs[j].data?.code==='65'){
                                    // 点击DOM节点
                                    var nodeEl=tree.querySelectorAll('.el-tree-node')[0]; // 需要更精确
                                    // 直接通过select组件选择
                                    var selectComp=null;
                                    var items=document.querySelectorAll('.el-form-item');
                                    for(var k=0;k<items.length;k++){
                                        var l=items[k].querySelector('.el-form-item__label')?.textContent?.trim()||'';
                                        if(l.includes('行业类型')){
                                            selectComp=items[k].querySelector('.el-select')?.__vue__;
                                            break;
                                        }
                                    }
                                    if(selectComp){
                                        selectComp.$emit('input','I65');
                                        selectComp.$emit('change',cs[j].data);
                                        selectComp.selectedLabel=cs[j].data?.label||'软件和信息技术服务业';
                                        return{selected:'I65',label:cs[j].data?.label};
                                    }
                                    return 'no_select_comp';
                                }
                            }
                        }
                    }
                }
            })()""")
            print(f"  选择65: {sel}")
            break

# 验证
ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型'))return items[i].querySelector('input')?.value||'';
    }
})()""")
print(f"  行业类型值: {ind_val}")

# 关闭下拉
ev("document.body.click()")
time.sleep(1)

# ============================================================
# Step 4: 经营范围 - 通过Vue方法直接设置
# ============================================================
print("\nStep 4: 经营范围 - Vue方法")

# 找businessDataInfo组件并设置经营范围
scope_set = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function find(vm,d){
        if(d>15)return null;
        if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object')return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}
        return null;
    }
    var comp=find(vm,0);
    if(!comp)return 'no_comp';
    var bdi=comp.$data.businessDataInfo;
    
    // 设置经营范围相关字段
    comp.$set(bdi,'businessArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'busiAreaCode','I65');
    comp.$set(bdi,'busiAreaName','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'genBusiArea','软件开发;信息技术咨询服务;数据处理和存储支持服务');
    comp.$set(bdi,'itemIndustryTypeCode','I65');
    comp.$set(bdi,'industryTypeName','软件和信息技术服务业');
    comp.$set(bdi,'multiIndustry','I65');
    comp.$set(bdi,'multiIndustryName','软件和信息技术服务业');
    comp.$set(bdi,'industryId','I65');
    comp.$set(bdi,'zlBusinessInd','I65');
    comp.$set(bdi,'busiAreaData',[
        {name:'软件开发',code:'6511',isMain:true},
        {name:'信息技术咨询服务',code:'6560',isMain:false},
        {name:'数据处理和存储支持服务',code:'6550',isMain:false}
    ]);
    
    comp.$forceUpdate();
    
    // 找ElForm并clearValidate
    function findForms(vm,d){
        if(d>15)return[];
        var r=[];
        if(vm.$options?.name==='ElForm'&&vm.model)r.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)r=r.concat(findForms(vm.$children[i],d+1));
        return r;
    }
    var forms=findForms(vm,0);
    for(var i=0;i<forms.length;i++){
        if('businessArea' in (forms[i].model||{})){
            forms[i].clearValidate();
        }
    }
    
    return {set:true,fields:Object.keys(bdi).filter(function(k){return bdi[k]&&String(bdi[k]).includes('软件')}).join(',')};
})()""")
print(f"  设置经营范围: {scope_set}")

# ============================================================
# Step 5: 最终验证
# ============================================================
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

print("\n✅ 完成")
