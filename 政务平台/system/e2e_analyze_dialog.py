#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析经营范围对话框真实结构 + 行业类型懒加载"""
import json, time, requests, websocket, sys

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=8)

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

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# ============================================================
# 分析1: 经营范围对话框 - 深度DOM分析
# ============================================================
print("\n分析1: 经营范围对话框深度分析")

# 先点添加按钮
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent?.trim()||'';
        if(t.includes('添加')&&btns[i].offsetParent!==null){btns[i].click();return}
    }
})()""")
time.sleep(5)  # 等更久让内容加载

# 深度分析对话框
dlg_analysis = ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null&&getComputedStyle(d).display==='none')continue;
        if(!d.textContent?.includes('经营范围'))continue;
        
        // 1. 检查iframe
        var iframes=d.querySelectorAll('iframe');
        var iframeInfo=[];
        for(var j=0;j<iframes.length;j++){
            iframeInfo.push({
                src:iframes[j].src||iframes[j].getAttribute('src')||'',
                width:iframes[j].width||iframes[j].style?.width||'',
                height:iframes[j].height||iframes[j].style?.height||'',
                display:getComputedStyle(iframes[j]).display,
                visibility:getComputedStyle(iframes[j]).visibility,
                contentDoc:!!iframes[j].contentDocument,
                contentWindow:!!iframes[j].contentWindow
            });
        }
        
        // 2. 检查shadow DOM
        var shadowHosts=[];
        var allEls=d.querySelectorAll('*');
        for(var j=0;j<allEls.length;j++){
            if(allEls[j].shadowRoot){
                shadowHosts.push({tag:allEls[j].tagName,class:allEls[j].className?.substring(0,30)||''});
            }
        }
        
        // 3. 列出直接子元素
        var children=[];
        for(var j=0;j<d.children.length;j++){
            children.push({tag:d.children[j].tagName,class:d.children[j].className?.substring(0,40)||'',text:d.children[j].textContent?.trim()?.substring(0,30)||''});
        }
        
        // 4. 查找body区域
        var body=d.querySelector('.tni-dialog__body,[class*="dialog-body"],.el-dialog__body');
        var bodyChildren=[];
        if(body){
            for(var j=0;j<body.children.length;j++){
                bodyChildren.push({tag:body.children[j].tagName,class:body.children[j].className?.substring(0,40)||'',text:body.children[j].textContent?.trim()?.substring(0,50)||'',childCount:body.children[j].children.length});
            }
        }
        
        // 5. 整体HTML结构（前500字符）
        var html=d.innerHTML?.substring(0,500)||'';
        
        return{
            visible:true,
            className:d.className,
            iframes:iframeInfo,
            shadowHosts:shadowHosts,
            children:children,
            bodyChildren:bodyChildren,
            htmlSample:html,
            totalElements:d.querySelectorAll('*').length
        };
    }
    return{visible:false};
})()""", timeout=12)
print(f"  对话框分析:")
if dlg_analysis:
    print(f"    className: {dlg_analysis.get('className','')[:50]}")
    print(f"    iframes: {dlg_analysis.get('iframes',[])}")
    print(f"    shadowHosts: {dlg_analysis.get('shadowHosts',[])}")
    print(f"    totalElements: {dlg_analysis.get('totalElements',0)}")
    print(f"    children: {dlg_analysis.get('children',[])}")
    print(f"    bodyChildren: {dlg_analysis.get('bodyChildren',[])}")
    print(f"    htmlSample: {dlg_analysis.get('htmlSample','')[:200]}")

# ============================================================
# 分析2: CDP targets（检查iframe是否有独立target）
# ============================================================
print("\n分析2: CDP targets")
targets = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
for t in targets:
    url = t.get('url','')
    ttype = t.get('type','')
    if ttype in ['page','iframe','other'] or 'scope' in url.lower() or 'jyfwyun' in url or 'business' in url.lower():
        print(f"  {ttype}: {url[:80]}")

# ============================================================
# 分析3: 行业类型树 - 懒加载分析
# ============================================================
print("\n分析3: 行业类型树懒加载")

# 关闭对话框先
ev("""(function(){
    var dialogs=document.querySelectorAll('.tni-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        var d=dialogs[i];
        if(d.offsetParent===null)continue;
        var closeBtn=d.querySelector('[class*="close"],[class*="Close"]');
        if(closeBtn)closeBtn.click();
    }
    document.body.click();
})()""")
time.sleep(1)

# 打开行业类型下拉
ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var input=items[i].querySelector('input');
            if(input){input.focus();input.click();}
            return;
        }
    }
})()""")
time.sleep(3)

# 分析tree组件的lazy load机制
tree_info = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var p=0;p<poppers.length;p++){
        var el=poppers[p];
        if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
        var tree=el.querySelector('.el-tree');
        if(!tree)continue;
        var comp=tree.__vue__;
        if(!comp)return{error:'no_tree_comp'};
        
        var props=comp.$props||{};
        var data=comp.$data||{};
        var store=comp.store;
        
        // 检查lazy配置
        var lazy=props.lazy||data.lazy||false;
        var load=typeof props.load==='function';
        
        // 获取root节点
        var rootNodes=store?.root?.childNodes||[];
        var rootNodeData=[];
        for(var i=0;i<rootNodes.length;i++){
            var nd=rootNodes[i];
            rootNodeData.push({
                label:nd.data?.label||nd.data?.name||'',
                code:nd.data?.code||nd.data?.value||'',
                isLeaf:nd.isLeaf,
                loaded:nd.loaded,
                loading:nd.loading,
                childCount:nd.childNodes?.length||0,
                expanded:nd.expanded
            });
        }
        
        return{
            lazy:lazy,
            hasLoadFn:load,
            rootNodeCount:rootNodes.length,
            rootNodes:rootNodeData.slice(0,5),
            // 找[I]节点
            iNode:rootNodeData.find(function(n){return n.code==='I'||n.label?.includes('信息传输')})||null
        };
    }
})()""", timeout=12)
print(f"  tree_info: lazy={tree_info.get('lazy',False) if tree_info else '?'} hasLoad={tree_info.get('hasLoadFn',False) if tree_info else '?'}")
if tree_info and tree_info.get('iNode'):
    print(f"  [I]节点: {tree_info['iNode']}")
if tree_info and tree_info.get('rootNodes'):
    for n in tree_info['rootNodes'][:3]:
        print(f"    [{n.get('code','')}] {n.get('label','')[:20]} leaf={n.get('isLeaf')} loaded={n.get('loaded')} children={n.get('childCount')}")

# 展开I节点并等待加载
ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var p=0;p<poppers.length;p++){
        var el=poppers[p];
        if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
        var tree=el.querySelector('.el-tree');if(!tree)continue;
        var comp=tree.__vue__;if(!comp)continue;
        var store=comp.store;
        var rootNodes=store?.root?.childNodes||[];
        for(var i=0;i<rootNodes.length;i++){
            var nd=rootNodes[i];
            if(nd.data?.code==='I'||nd.data?.label?.includes('信息传输')){
                nd.expand();
                return{expanded:true};
            }
        }
    }
})()""")
time.sleep(4)  # 等待懒加载

# 检查[I]子节点
i_children = ev("""(function(){
    var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
    for(var p=0;p<poppers.length;p++){
        var el=poppers[p];
        if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
        var tree=el.querySelector('.el-tree');if(!tree)continue;
        var comp=tree.__vue__;if(!comp)continue;
        var store=comp.store;
        var rootNodes=store?.root?.childNodes||[];
        for(var i=0;i<rootNodes.length;i++){
            var nd=rootNodes[i];
            if(nd.data?.code==='I'||nd.data?.label?.includes('信息传输')){
                var children=nd.childNodes||[];
                var result=[];
                for(var j=0;j<children.length;j++){
                    result.push({
                        code:children[j].data?.code||'',
                        label:children[j].data?.label||children[j].data?.name||'',
                        isLeaf:children[j].isLeaf,
                        loaded:children[j].loaded,
                        childCount:children[j].childNodes?.length||0
                    });
                }
                return{total:children.length,children:result};
            }
        }
    }
})()""", timeout=12)
print(f"\n  [I]子节点: total={i_children.get('total',0) if i_children else 0}")
if i_children and i_children.get('children'):
    for c in i_children['children']:
        print(f"    [{c.get('code','')}] {c.get('label','')[:25]} leaf={c.get('isLeaf')} loaded={c.get('loaded')} children={c.get('childCount')}")

# 找到[65]节点并展开
if i_children and i_children.get('children'):
    for c in i_children['children']:
        if c.get('code','') == '65':
            # 展开并选择
            ev("""(function(){
                var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
                for(var p=0;p<poppers.length;p++){
                    var el=poppers[p];
                    if(el.offsetParent===null&&getComputedStyle(el).display==='none')continue;
                    var tree=el.querySelector('.el-tree');if(!tree)continue;
                    var comp=tree.__vue__;if(!comp)continue;
                    var store=comp.store;
                    var rootNodes=store?.root?.childNodes||[];
                    for(var i=0;i<rootNodes.length;i++){
                        var nd=rootNodes[i];
                        if(nd.data?.code==='I'){
                            var children=nd.childNodes||[];
                            for(var j=0;j<children.length;j++){
                                if(children[j].data?.code==='65'){
                                    // 选择这个节点
                                    children[j].expand();
                                    // 也通过handleCheckChange或handleNodeClick
                                    comp.$emit('node-click',children[j].data,children[j]);
                                    comp.handleNodeClick(children[j].data,children[j]);
                                    return{selected:true,code:'65'};
                                }
                            }
                        }
                    }
                }
            })()""", timeout=8)
            time.sleep(2)
            break

# 验证行业类型
ind_val = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var l=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(l.includes('行业类型'))return items[i].querySelector('input')?.value||'';
    }
})()""")
print(f"\n  行业类型值: {ind_val}")

ev("document.body.click()")
ws.close()
print("\n✅ 分析完成")
