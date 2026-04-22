#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试字典数据与SPA实际选项是否匹配"""
import json, time, requests, websocket

# 加载字典
with open(r'g:\UFO\政务平台\data\industry_gb4754_2017.json', encoding='utf-8') as f:
    industry_dict = json.load(f)
with open(r'g:\UFO\政务平台\data\ent_type_codes.json', encoding='utf-8') as f:
    ent_type_dict = json.load(f)

# CDP连接
pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=10)
_mid = 0
def ev(js, timeout=10):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
    for _ in range(30):
        try:
            ws.settimeout(timeout); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"当前: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# ==================== 测试1: 企业类型 ====================
print("\n" + "="*60)
print("测试1: 企业类型代码匹配")
print("="*60)

# 从SPA获取企业类型列表
spa_ent_types = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){
        if(d>15)return null;
        if(vm.$options?.name===name)return vm;
        for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}
        return null;
    }
    // 找establish组件
    var est=findComp(vm,'establish',0);
    if(est&&est.$data.radioGroup){
        return est.$data.radioGroup.map(function(r){return{code:r.checked||r.value||r.code||'',name:r.name||r.label||r.text||''}});
    }
    // 也检查cardList
    if(est&&est.$data.cardList){
        return est.$data.cardList.map(function(c){return{code:c.code||c.value||c.entType||'',name:c.name||c.label||c.text||''}});
    }
    return{error:'no_establish',hash:location.hash};
})()""")
print(f"SPA企业类型: {spa_ent_types}")

# 如果不在establish页面，从当前表单获取
if not spa_ent_types or isinstance(spa_ent_types, dict):
    print("  不在establish页面，从表单获取已选企业类型")
    spa_ent_type_val = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findFormComp(vm,d){
            if(d>15)return null;
            if(vm.$data&&vm.$data.businessDataInfo&&typeof vm.$data.businessDataInfo==='object'){
                var fd=vm.$data.businessDataInfo.flowData||{};
                return{entType:fd.entType||fd.enterpriseType||'',entTypeName:fd.entTypeName||fd.enterpriseTypeName||''};
            }
            for(var i=0;i<(vm.$children||[]).length;i++){var r=findFormComp(vm.$children[i],d+1);if(r)return r}
            return null;
        }
        return findFormComp(vm,0);
    })()""")
    print(f"  当前企业类型: {spa_ent_type_val}")

# 对比字典
print("\n字典企业类型（1100系列）:")
dict_1100 = [c for c in ent_type_dict['categories'][0]['children'] if c['code'].startswith('11')]
for c in dict_1100:
    print(f"  [{c['code']}] {c['name']}")

# ==================== 测试2: 行业类型门类 ====================
print("\n" + "="*60)
print("测试2: 行业类型门类匹配")
print("="*60)

# 点击行业类型输入框触发下拉
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

# 获取SPA行业类型树的第一级（门类）
spa_industry = ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        if(nodes.length<10)continue;
        var result=[];
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            result.push({idx:i,text:text.substring(0,40)});
        }
        return{total:nodes.length,nodes:result};
    }
    return{error:'no_popper'};
})()""")
print(f"SPA行业类型门类: total={spa_industry.get('total',0) if spa_industry else 0}")

# 对比
dict_categories = industry_dict['categories']
print("\n对比结果:")
spa_nodes = spa_industry.get('nodes',[]) if spa_industry else []
match_count = 0
mismatch_count = 0
for sn in spa_nodes:
    spa_text = sn.get('text','')
    # 提取门类代码，如 [A]农、林、牧、渔业
    spa_code = ''
    for ch in spa_text:
        if ch == ']': break
        if ch == '[': continue
        if ch.isalpha(): spa_code = ch; break
    
    # 在字典中查找
    dict_match = None
    for cat in dict_categories:
        if cat['code'] == spa_code:
            dict_match = cat['name']
            break
    
    status = ''
    if dict_match:
        # 检查名称是否匹配
        if dict_match in spa_text or spa_text.replace(f'[{spa_code}]','').strip().startswith(dict_match[:4]):
            status = '✅ 匹配'
            match_count += 1
        else:
            status = f'⚠️ 名称不同 字典={dict_match}'
            mismatch_count += 1
    else:
        status = '❌ 字典无此门类'
        mismatch_count += 1
    
    print(f"  SPA: {spa_text[:35]:35s} → {status}")

print(f"\n门类匹配: {match_count} ✅ / {mismatch_count} ❌")

# ==================== 测试3: [I]门类子节点 ====================
print("\n" + "="*60)
print("测试3: [I]信息传输子节点匹配")
print("="*60)

# 展开[I]节点
ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            if(text.includes('[I]信息传输')){
                var expandIcon=nodes[i].querySelector('.el-tree-node__expand-icon');
                if(expandIcon)expandIcon.click();
                return;
            }
        }
    }
})()""")
time.sleep(2)

# 获取展开后的子节点
spa_I_children = ev("""(function(){
    var poppers=document.querySelectorAll('[class*="tree-popper"],[class*="popper-select"]');
    for(var p=0;p<poppers.length;p++){
        var visible=poppers[p].offsetParent!==null||poppers[p].style?.display!=='none';
        if(!visible)continue;
        var nodes=poppers[p].querySelectorAll('.el-tree-node__content');
        var result=[];
        for(var i=0;i<nodes.length;i++){
            var text=nodes[i].textContent?.trim()||'';
            if(text.includes('[63]')||text.includes('[64]')||text.includes('[65]')||text.includes('电信')||text.includes('互联网')||text.includes('软件')){
                result.push({idx:i,text:text.substring(0,40)});
            }
        }
        return result;
    }
})()""")
print(f"SPA [I]子节点:")
for n in (spa_I_children or []):
    print(f"  {n.get('text','')}")

# 字典中[I]的子节点
dict_I = [c for c in dict_categories if c['code']=='I'][0]
print(f"\n字典 [I]子节点:")
for c in dict_I.get('children',[]):
    print(f"  [{c['code']}] {c['name']}")
    for cc in c.get('children',[]):
        print(f"    [{cc['code']}] {cc['name']}")

# ==================== 测试4: 叶子节点路径查找 ====================
print("\n" + "="*60)
print("测试4: 代码路径查找测试")
print("="*60)

def find_industry_path(code, categories):
    """从行业代码找到完整路径"""
    # 确定门类
    first_char = code[0] if code else ''
    if first_char.isdigit():
        # 纯数字代码，如0610
        for cat in categories:
            for big in cat.get('children',[]):
                for mid in big.get('children',[]):
                    for small in mid.get('children',[]):
                        if small['code'] == code:
                            return [cat['code'], big['code'], mid['code'], small['code']], [cat['name'], big['name'], mid['name'], small['name']]
    elif first_char.isalpha():
        # 字母开头，如I65
        for cat in categories:
            if cat['code'] == first_char:
                rest = code[1:]
                for big in cat.get('children',[]):
                    if big['code'] == rest[:2] if len(rest)>=2 else False:
                        if len(rest) == 2:
                            return [cat['code'], big['code']], [cat['name'], big['name']]
                        for mid in big.get('children',[]):
                            if mid['code'] == rest[:3] if len(rest)>=3 else False:
                                if len(rest) == 3:
                                    return [cat['code'], big['code'], mid['code']], [cat['name'], big['name'], mid['name']]
                                for small in mid.get('children',[]):
                                    if small['code'] == rest:
                                        return [cat['code'], big['code'], mid['code'], small['code']], [cat['name'], big['name'], mid['name'], small['name']]
    return None, None

test_codes = ['0610', 'I65', 'I6511', 'I6560', 'A0111', '1100']
for code in test_codes:
    if code.startswith('1') and len(code)==4 and code[1]=='1':
        # 企业类型
        found = None
        for cat in ent_type_dict['categories']:
            for c in cat.get('children',[]):
                if c['code'] == code:
                    found = c['name']; break
        print(f"  {code} → {found or '❌ 未找到'} (企业类型)")
    else:
        path_codes, path_names = find_industry_path(code, dict_categories)
        if path_codes:
            print(f"  {code} → {'/'.join(path_codes)} {'/'.join(path_names)} ✅")
        else:
            print(f"  {code} → ❌ 未找到")

# 关闭下拉
ev("document.body.click()")

ws.close()
print("\n✅ 测试完成")
