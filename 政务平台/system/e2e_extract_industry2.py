#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从SPA Vue组件提取行业分类完整树数据"""
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

# Step 1: 找到行业类型select组件，分析其数据结构
print("Step 1: 分析行业类型组件数据结构")
comp_info = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 列出所有$data属性和类型
            var dataInfo={};
            for(var k in comp.$data){
                var v=comp.$data[k];
                if(v===null||v===undefined)dataInfo[k]='null';
                else if(Array.isArray(v))dataInfo[k]='Array['+v.length+']';
                else if(typeof v==='object')dataInfo[k]='obj:'+Object.keys(v).slice(0,5).join(',');
                else dataInfo[k]=String(v).substring(0,30);
            }
            
            // 列出$props
            var propsInfo={};
            for(var k in comp.$props){
                var v=comp.$props[k];
                if(v===null||v===undefined)propsInfo[k]='null';
                else if(Array.isArray(v))propsInfo[k]='Array['+v.length+']';
                else if(typeof v==='object')propsInfo[k]='obj';
                else propsInfo[k]=String(v).substring(0,30);
            }
            
            // 检查关键属性
            var treeData=comp.treeData;
            var data=comp.data;
            var options=comp.options;
            var treeOptions=comp.treeOptions;
            var nodes=comp.nodes;
            var store=comp.store;
            
            // 如果有el-tree的store
            var treeComp=comp.$refs?.tree||comp.$children?.find(function(c){return c.$options?.name==='ElTree'});
            var treeStore=treeComp?.store||comp.store;
            
            return{
                compName:comp.$options?.name||'',
                dataInfo:dataInfo,
                propsInfo:propsInfo,
                hasTreeData:Array.isArray(treeData),
                treeDataLen:Array.isArray(treeData)?treeData.length:0,
                hasData:Array.isArray(data),
                dataLen:Array.isArray(data)?data.length:0,
                hasOptions:Array.isArray(options),
                optionsLen:Array.isArray(options)?options.length:0,
                hasTreeOptions:Array.isArray(treeOptions),
                hasNodes:!!nodes,
                hasStore:!!store||!!treeStore,
                treeCompName:treeComp?.$options?.name||'',
                treeStoreNodes:treeStore?.nodes?Object.keys(treeStore.nodes).length:0
            };
        }
    }
    return{error:'not_found'};
})()""")
print(f"  comp_info: {comp_info}")

# Step 2: 从tree store提取数据
print("\nStep 2: 从tree store提取")
tree_data = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('行业类型')){
            var select=items[i].querySelector('.el-select');
            var comp=select?.__vue__;
            if(!comp)return{error:'no_comp'};
            
            // 找el-tree组件
            var treeComp=null;
            // 搜索子组件
            function findTree(vm,d){
                if(d>10)return null;
                if(vm.$options?.name==='ElTree')return vm;
                for(var i=0;i<(vm.$children||[]).length;i++){
                    var r=findTree(vm.$children[i],d+1);if(r)return r;
                }
                return null;
            }
            treeComp=findTree(comp,0);
            
            if(!treeComp){
                // 也检查popper
                var poppers=document.querySelectorAll('.el-select-dropdown');
                for(var p=0;p<poppers.length;p++){
                    if(poppers[p].offsetParent){
                        treeComp=poppers[p].querySelector('.el-tree')?.__vue__;
                        if(treeComp)break;
                    }
                }
            }
            
            if(!treeComp)return{error:'no_tree_comp'};
            
            var store=treeComp.store;
            if(!store)return{error:'no_store'};
            
            var rootNodes=store.root?.childNodes||[];
            
            function extractNode(node){
                var data=node.data||{};
                var result={
                    code:data.code||data.value||data.id||node.id||'',
                    name:data.label||data.name||data.text||''
                };
                if(node.childNodes&&node.childNodes.length>0){
                    result.children=node.childNodes.map(extractNode);
                }
                return result;
            }
            
            var result=rootNodes.map(extractNode);
            return{total:result.length,sample:JSON.stringify(result[0]||{}).substring(0,200),data:result};
        }
    }
})()""")

if tree_data and not (isinstance(tree_data, dict) and tree_data.get('error')):
    total = tree_data.get('total',0) if isinstance(tree_data, dict) else len(tree_data)
    print(f"  提取到 {total} 个门类")
    
    if isinstance(tree_data, dict) and tree_data.get('data'):
        data = tree_data['data']
        # 保存
        with open(r'g:\UFO\政务平台\data\industry_spa_extracted.json', 'w', encoding='utf-8') as f:
            json.dump({"source":"SPA_tree_store","data":data}, f, ensure_ascii=False, indent=2)
        print("  已保存到 industry_spa_extracted.json")
        
        # 打印摘要
        for cat in data:
            child_count = len(cat.get('children',[]))
            print(f"    [{cat.get('code','')}] {cat.get('name','')[:20]} → {child_count} 大类")
            for bc in (cat.get('children',[]) or [])[:3]:
                mid_count = len(bc.get('children',[]))
                print(f"      [{bc.get('code','')}] {bc.get('name','')[:20]} → {mid_count} 中类")
    else:
        print(f"  数据格式: {type(tree_data)}")
        print(f"  sample: {str(tree_data)[:200]}")
else:
    error = tree_data.get('error','unknown') if isinstance(tree_data, dict) else 'unknown'
    print(f"  提取失败: {error}")
    
    # Step 3: 备选方案 - 通过API拦截获取
    print("\nStep 3: 通过API获取行业分类数据")
    
    # 安装拦截器
    ev("""(function(){
        window.__industry_api=null;
        var origOpen=XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open=function(m,u){
            this.__url=u;this.__method=m;
            return origOpen.apply(this,arguments);
        };
        var origSend=XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send=function(body){
            var self=this;
            this.addEventListener('load',function(){
                var url=self.__url||'';
                if(url.includes('industry')||url.includes('Industry')||url.includes('tradeType')||url.includes('categoryList')||url.includes('getTrade')){
                    try{
                        var resp=JSON.parse(self.responseText);
                        if(resp.code==='0'||resp.code===0||resp.code==='200'){
                            window.__industry_api={url:url,data:resp.data||resp.result||resp};
                        }
                    }catch(e){}
                }
            });
            return origSend.apply(this,arguments);
        };
    })()""")
    
    # 触发加载
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
    
    api_data = ev("window.__industry_api")
    if api_data:
        print(f"  API: {api_data.get('url','')[:80]}")
        print(f"  data type: {type(api_data.get('data',''))}")
        print(f"  data sample: {str(api_data.get('data',''))[:200]}")
    else:
        print("  无API数据")
    
    # Step 4: 从DOM提取（展开每个门类）
    print("\nStep 4: 从DOM逐级展开提取")
    
    # 先获取门类
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
    time.sleep(2)
    
    # 获取所有可见节点文本
    all_nodes = ev("""(function(){
        var poppers=document.querySelectorAll('.el-select-dropdown');
        for(var p=0;p<poppers.length;p++){
            if(!poppers[p].offsetParent)continue;
            var tree=poppers[p].querySelector('.el-tree');
            if(!tree)continue;
            var nodes=tree.querySelectorAll('.el-tree-node__content');
            var result=[];
            for(var i=0;i<nodes.length;i++){
                var text=nodes[i].textContent?.trim()||'';
                var isExpanded=nodes[i].closest('.el-tree-node')?.classList?.contains('is-expanded')||false;
                result.push({idx:i,text:text,expanded:isExpanded});
            }
            return{total:nodes.length,nodes:result};
        }
    })()""")
    
    if all_nodes:
        print(f"  当前可见节点: {all_nodes.get('total',0)}")
        for n in (all_nodes.get('nodes',[]) or []):
            marker = ' 📂' if n.get('expanded') else ''
            print(f"    [{n.get('idx')}] {n.get('text','')[:35]}{marker}")

ev("document.body.click()")
ws.close()
print("\n✅ 完成")
