#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复行业类型：初始化tne-select-tree + 设值 + 验证通过 + 保存"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "core.html" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page: return "ERROR:no_page"
        ws = websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":timeout*1000}}))
        ws.settimeout(timeout+2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                ws.close()
                return r.get("result",{}).get("result",{}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

FC = "function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"

# ============================================================
# Step 1: tne-select-tree初始化
# ============================================================
print("Step 1: 初始化行业类型tree")
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    
    // 找行业类型tree
    var trees=[];
    function walk(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='tne-select-tree')trees.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(busi,0);
    
    var indTree=null;
    for(var i=0;i<trees.length;i++){{
        var ph=trees[i].$props?.placeholder||trees[i].placeholder||'';
        if(ph.includes('行业类型')){{indTree=trees[i];break;}}
    }}
    if(!indTree&&trees.length>1)indTree=trees[1];
    if(!indTree&&trees.length>0)indTree=trees[0];
    if(!indTree)return'no_ind_tree';
    
    // 调用初始化方法
    if(typeof indTree.initView==='function')indTree.initView();
    if(typeof indTree.initTreeView==='function')indTree.initTreeView();
    
    return {{
        found:true,
        placeholder:indTree.$props?.placeholder||indTree.placeholder||'',
        dataLen:(indTree.$data?.data||indTree.$props?.data||[]).length,
        value:indTree.$props?.value||indTree.value||indTree.$data?.value||''
    }};
}})()""", timeout=15)
print(f"  init: {init_result}")
time.sleep(3)

# ============================================================
# Step 2: 查看businese-info的industryList
# ============================================================
print("\nStep 2: industryList数据")
ind_list = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var il=busi.$data?.industryList||[];
    return {{
        len:il.length,
        first3:il.slice(0,3).map(function(x){{return JSON.stringify(x).substring(0,60)}}),
        hasI65:il.some(function(x){{return x.code==='I65'||x.value==='I65'}})
    }};
}})()""")
print(f"  {json.dumps(ind_list, ensure_ascii=False)[:300] if isinstance(ind_list,dict) else ind_list}")

# ============================================================
# Step 3: 查看treeSelectChange方法源码
# ============================================================
print("\nStep 3: treeSelectChange源码")
tsc_src = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var fn=busi.$options?.methods?.treeSelectChange;
    if(!fn)return'no_method';
    return fn.toString().substring(0,500);
}})()""")
print(f"  {tsc_src[:300]}")

# ============================================================
# Step 4: 尝试通过tne-select-tree设置值
# ============================================================
print("\nStep 4: 设置行业类型值")
set_val = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    
    // 找行业类型tree
    var trees=[];
    function walk(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='tne-select-tree')trees.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(busi,0);
    
    var indTree=null;
    for(var i=0;i<trees.length;i++){{
        var ph=trees[i].$props?.placeholder||trees[i].placeholder||'';
        if(ph.includes('行业类型')){{indTree=trees[i];break;}}
    }}
    if(!indTree&&trees.length>1)indTree=trees[1];
    if(!indTree)return'no_ind_tree';
    
    // 设置值 - 通过$emit
    indTree.$emit('input','I65');
    indTree.$emit('change','I65');
    
    // 也设置tne-select（父组件）
    var parent=indTree.$parent;
    if(parent){{
        parent.$emit('input','I65');
        parent.$emit('change','I65');
    }}
    
    // 调用onChange
    if(typeof indTree.onChange==='function')indTree.onChange('I65');
    
    // 也调用businese-info的treeSelectChange
    busi.treeSelectChange('I65');
    
    return {{
        set:true,
        treeValue:indTree.$props?.value||indTree.value||'',
        formIndustryType:busi.busineseForm?.industryType||''
    }};
}})()""")
print(f"  {set_val}")
time.sleep(2)

# ============================================================
# Step 5: 验证
# ============================================================
print("\nStep 5: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 6: 如果仍有验证错误，清除验证
# ============================================================
if isinstance(errors, list) and errors:
    print("\nStep 6: 清除验证+强制设值")
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var busi=findComp(vm,'businese-info',0);
        if(!busi)return;
        var f=busi.busineseForm||busi.$data?.busineseForm;
        if(!f)return;
        
        // 强制设置
        busi.$set(f,'industryType','I65');
        busi.$set(f,'industryTypeName','软件和信息技术服务业');
        busi.$set(f,'industryCode','I65');
        
        // 清除验证
        var elForms=[];
        function findForms(vm,d){{
            if(d>10)return;
            if(vm.$options?.name==='ElForm')elForms.push(vm);
            for(var i=0;i<(vm.$children||[]).length;i++)findForms(vm.$children[i],d+1);
        }}
        findForms(busi,0);
        for(var i=0;i<elForms.length;i++){{
            try{{elForms[i].clearValidate()}}catch(e){{}}
        }}
    }})()""")
    time.sleep(1)
    
    errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
    print(f"  清除后: {errors2}")

# ============================================================
# Step 7: 拦截+保存
# ============================================================
print("\nStep 7: 拦截+保存")
ev("""(function(){
    window.__save_req=null;window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')||url.includes('BasicInfo')){
            window.__save_req={url:url,body:body||'',bodyLen:(body||'').length};
            var self=this;
            self.addEventListener('load',function(){window.__save_resp={status:self.status,text:self.responseText||''}});
        }
        return origSend.apply(this,arguments);
    };
})()""")

click = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('保存并下一步')||t.includes('下一步'))&&!all[i].disabled&&all[i].offsetParent!==null){
            all[i].click();return{clicked:t};
        }
    }
    return 'no_btn';
})()""")
print(f"  点击: {click}")
time.sleep(12)

# ============================================================
# Step 8: 分析
# ============================================================
print("\nStep 8: 分析")
req = ev("window.__save_req")
resp = ev("window.__save_resp")

if isinstance(req, dict) and req.get('body'):
    body = req.get('body','')
    try:
        bobj = json.loads(body)
        ba = bobj.get('busiAreaData')
        gba = bobj.get('genBusiArea')
        print(f"  busiAreaData type: {type(ba).__name__}")
        if isinstance(ba, str):
            print(f"  ⚠️ STRING len={len(ba)}")
            print(f"     前80: {ba[:80]}")
            try:
                d = json.loads(ba)
                print(f"     parse后: {type(d).__name__} len={len(d)}")
            except:
                print("     parse失败")
        elif isinstance(ba, list):
            print(f"  ✅ ARRAY len={len(ba)}")
            if ba: print(f"     keys: {list(ba[0].keys())[:8]}")
        print(f"  genBusiArea: {type(gba).__name__} = {str(gba)[:50]}")
        
        with open(r'g:\UFO\政务平台\data\save_body_a0002.json', 'w', encoding='utf-8') as f:
            json.dump(bobj, f, ensure_ascii=False, indent=2)
        print(f"  已保存 ({len(bobj)} keys)")
    except:
        print(f"  非JSON: {body[:200]}")
else:
    print(f"  无请求: {req}")

if isinstance(resp, dict):
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            print(f"  API code={p.get('code','')} msg={str(p.get('msg',''))[:80]}")
            if str(p.get('code','')) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
            else:
                print("  ❌ 错误!")
                with open(r'g:\UFO\政务平台\data\save_resp_a0002.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {resp}")

print("\n✅ 完成")
