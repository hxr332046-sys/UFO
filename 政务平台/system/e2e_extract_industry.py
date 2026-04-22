#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从SPA提取完整行业分类树数据，保存为JSON字典"""
import json, time, requests, websocket

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=15)
_mid = 0
def ev(js, timeout=15):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    for _ in range(40):
        try:
            ws.settimeout(timeout); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 找到行业类型tne-select组件，获取其treeData源
print("Step 1: 获取行业类型组件数据源")
tree_source = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            if(!select)continue;
            var comp=select.__vue__;
            if(!comp)continue;
            
            // 分析组件属性
            var keys=Object.keys(comp.$data||{});
            var props=Object.keys(comp.$props||{});
            
            // 找treeData/data/options
            var dataKeys=[];
            for(var k in comp.$data){
                var v=comp.$data[k];
                if(Array.isArray(v)&&v.length>0)dataKeys.push(k);
                else if(v&&typeof v==='object'&&!Array.isArray(v))dataKeys.push(k+':obj');
            }
            
            // 尝试获取treeData
            var td=comp.treeData||comp.data||comp.options||comp.treeOptions||null;
            var tdLen=Array.isArray(td)?td.length:0;
            var tdSample=null;
            if(tdLen>0){
                tdSample=JSON.stringify(td[0]).substring(0,200);
            }
            
            // 找lazy load方法
            var methods=comp.$options?.methods||{};
            var methodNames=Object.keys(methods);
            var lazyMethods=[];
            for(var m in methods){
                var src=methods[m].toString();
                if(src.includes('load')||src.includes('lazy')||src.includes('fetch')||src.includes('request')){
                    lazyMethods.push(m);
                }
            }
            
            return{
                compName:comp.$options?.name||'',
                dataKeys:dataKeys,
                treeDataLen:tdLen,
                treeDataSample:tdSample,
                props:props,
                methodNames:methodNames,
                lazyMethods:lazyMethods,
                lazy:comp.lazy||comp.$props?.lazy||false,
                loadFn:typeof comp.loadNode==='function'
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  tree_source: {tree_source}")

# Step 2: 如果有treeData直接提取
print("\nStep 2: 提取treeData")
tree_data = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            var td=comp.treeData||comp.data||comp.options||[];
            if(!Array.isArray(td)||td.length===0)return{error:'no_treeData'};
            
            function extractNode(node){
                var result={code:node.code||node.value||node.id||'',name:node.label||node.name||node.text||''};
                var children=node.children||node.child||[];
                if(Array.isArray(children)&&children.length>0){
                    result.children=children.map(extractNode);
                }
                return result;
            }
            
            return td.map(extractNode);
        }
    }
})()""")
if tree_data and not (isinstance(tree_data, dict) and tree_data.get('error')):
    print(f"  提取到 {len(tree_data)} 个门类")
    # 保存
    with open(r'g:\UFO\政务平台\data\industry_spa_extracted.json', 'w', encoding='utf-8') as f:
        json.dump({"source":"SPA_extracted","data":tree_data}, f, ensure_ascii=False, indent=2)
    print("  已保存到 industry_spa_extracted.json")
else:
    print(f"  无treeData: {tree_data}")
    
    # Step 3: 通过API获取行业分类数据
    print("\nStep 3: 通过API获取行业分类")
    # 安装XHR拦截
    ev("""(function(){
        window.__api_logs=[];
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
        var origSend=XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send=function(body){
            var self=this;self.__body=body;
            this.addEventListener('load',function(){
                if(self.__url&&self.__url.includes('industry')||self.__url.includes('Industry')||self.__url.includes('trade')||self.__url.includes('category')){
                    window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,2000)||''});
                }
            });
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 触发行业类型下拉加载
    ev("""(function(){
        var items=document.querySelectorAll('.el-form-item');
        for(var i=0;i<items.length;i++){
            var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
            if(label.includes('行业类型')){
                var select=items[i].querySelector('.el-select');
                var comp=select?.__vue__;
                if(comp){
                    // 触发visible-change
                    comp.$emit('visible-change',true);
                    comp.visible=true;
                    comp.handleFocus();
                    if(typeof comp.loadRoot==='function')comp.loadRoot();
                }
                var input=items[i].querySelector('input');
                if(input){input.focus();input.click()}
                return;
            }
        }
    })()""")
    time.sleep(3)
    
    # 检查API
    api_logs = ev("window.__api_logs||[]")
    print(f"  API calls: {len(api_logs or [])}")
    for l in (api_logs or []):
        print(f"    {l.get('method','')} {l.get('url','')[:80]} status={l.get('status')}")
    
    # Step 4: 从DOM树提取完整数据
    print("\nStep 4: 从DOM树提取")
    # 逐个展开门类获取子节点
    all_data = []
    
    # 先获取门类列表
    categories = ev("""(function(){
        var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
        for(var p=0;p<poppers.length;p++){
            var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
            if(!visible)continue;
            var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
            if(nodes.length<15)continue;
            var result=[];
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                // 只取门类级（带[A]~[T]格式的）
                if(/^\[[A-T]\]/.test(text)){
                    result.push({idx:i,text:text,code:text.match(/\[([A-T])\]/)?.[1]||''});
                }
            }
            return result;
        }
    })()""")
    
    if categories:
        print(f"  门类数: {len(categories)}")
        
        # 逐个展开每个门类，获取大类
        for cat in categories:
            cat_code = cat.get('code','')
            cat_text = cat.get('text','').replace(f'[{cat_code}]','').strip()
            cat_idx = cat.get('idx',0)
            print(f"\n  展开 [{cat_code}] {cat_text}")
            
            # 点击展开
            ev(f"""(function(){{
                var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
                for(var p=0;p<poppers.length;p++){{
                    var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
                    if(!visible)continue;
                    var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
                    if(nodes[{cat_idx}]){{
                        var expand=nodes[{cat_idx}].querySelector('.el-tree-node__expand-icon');
                        if(expand)expand.click();
                    }}
                }}
            }})()""")
            time.sleep(1.5)
            
            # 获取展开后的大类节点
            big_classes = ev("""(function(){
                var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
                for(var p=0;p<poppers.length;p++){
                    var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
                    if(!visible)continue;
                    var tree=poppers[p].querySelector('.el-tree');
                    if(!tree)continue;
                    // 获取所有可见的展开节点的子节点
                    var expandedNodes=tree.querySelectorAll('.el-tree-node.is-expanded');
                    var result=[];
                    for(var e=0;e<expandedNodes.length;e++){
                        var parentText=expandedNodes[e].querySelector(':scope > .el-tree-node__content')?.textContent?.trim()||'';
                        if(!parentText.includes('["""+cat_code+"""]'))continue;
                        var childContainer=expandedNodes[e].querySelector('.el-tree-node__children');
                        if(!childContainer)continue;
                        var childNodes=childContainer.querySelectorAll(':scope > .el-tree-node > .el-tree-node__content');
                        for(var c=0;c<childNodes.length;c++){
                            var text=childNodes[c].textContent?.trim()||'';
                            var codeMatch=text.match(/\[(\d+)\]/);
                            result.push({code:codeMatch?codeMatch[1]:'',name:text.replace(/\[\d+\]/,'').trim()});
                        }
                    }
                    return result;
                }
            })()""")
            
            cat_data = {"code": cat_code, "name": cat_text, "children": []}
            if big_classes:
                for bc in big_classes:
                    cat_data["children"].append({"code": bc.get('code',''), "name": bc.get('name','')})
                print(f"    大类数: {len(big_classes)}")
                for bc in big_classes[:3]:
                    print(f"      [{bc.get('code','')}] {bc.get('name','')[:20]}")
            else:
                print(f"    无子节点")
            
            all_data.append(cat_data)
            
            # 收起当前节点（避免树太长）
            ev(f"""(function(){{
                var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
                for(var p=0;p<poppers.length;p++){{
                    var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
                    if(!visible)continue;
                    var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
                    if(nodes[{cat_idx}]){{
                        var expand=nodes[{cat_idx}].querySelector('.el-tree-node__expand-icon.is-expanded');
                        if(expand)expand.click();
                    }}
                }}
            }})()""")
            time.sleep(0.5)
        
        # 保存
        with open(r'g:\UFO\政务平台\data\industry_spa_extracted.json', 'w', encoding='utf-8') as f:
            json.dump({"source":"SPA_DOM_extracted","data":all_data}, f, ensure_ascii=False, indent=2)
        print(f"\n已保存 {len(all_data)} 个门类到 industry_spa_extracted.json")

# Step 5: 对比SPA提取数据与字典数据
print("\nStep 5: 对比")
with open(r'g:\UFO\政务平台\data\industry_gb4754_2017.json', encoding='utf-8') as f:
    dict_data = json.load(f)

# 加载SPA数据
try:
    with open(r'g:\UFO\政务平台\data\industry_spa_extracted.json', encoding='utf-8') as f:
        spa_data = json.load(f)
    
    spa_cats = {c['code']: c for c in spa_data.get('data',[])}
    dict_cats = {c['code']: c for c in dict_data['categories']}
    
    print(f"SPA门类: {len(spa_cats)} 字典门类: {len(dict_cats)}")
    
    for code in sorted(set(list(spa_cats.keys()) + list(dict_cats.keys()))):
        spa = spa_cats.get(code)
        dic = dict_cats.get(code)
        spa_name = spa.get('name','') if spa else '(无)'
        dict_name = dic.get('name','') if dic else '(无)'
        match = '✅' if spa_name == dict_name or (spa_name and dict_name and spa_name[:4]==dict_name[:4]) else '❌'
        spa_children = len(spa.get('children',[])) if spa else 0
        dict_children = len(dic.get('children',[])) if dic else 0
        print(f"  [{code}] SPA={spa_name[:15]:15s} 字典={dict_name[:15]:15s} {match} 子节点: SPA={spa_children} 字典={dict_children}")
except Exception as e:
    print(f"  对比失败: {e}")

ev("document.body.click()")
ws.close()
print("✅ 完成")
