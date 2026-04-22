#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复：entName→bdi, tne-select-tree行业类型, genBusiArea字符串, 保存+分析"""
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
# Step 1: 设置entName在bdi上
# ============================================================
print("Step 1: 设置entName")
name_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var bdi=fc.$data?.businessDataInfo;
    if(!bdi)return'no_bdi';
    fc.$set(bdi,'entName','广西智信数据科技有限公司');
    fc.$set(bdi,'entShortName','智信数据');
    fc.$set(bdi,'entType','1100');
    fc.$set(bdi,'entTypeName','内资有限公司');
    fc.$set(bdi,'nameFlag','0');
    // DOM同步
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var inputs=document.querySelectorAll('.el-form-item input');
    for(var i=0;i<inputs.length;i++){{
        var label=inputs[i].closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业名称')){{
            s.call(inputs[i],'广西智信数据科技有限公司');
            inputs[i].dispatchEvent(new Event('input',{{bubbles:true}}));
            inputs[i].dispatchEvent(new Event('change',{{bubbles:true}}));
        }}
    }}
    return {{entName:bdi.entName}};
}})()""")
print(f"  {name_result}")

# ============================================================
# Step 2: 行业类型 - tne-select-tree
# ============================================================
print("\nStep 2: 行业类型tne-select-tree")
tree_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    var trees=[];
    function walk(vm,d){{
        if(d>15)return;
        var n=vm.$options?.name||'';
        if(n==='tne-select-tree')trees.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(vm,0);
    if(!trees.length)return'no_tree';
    
    // 找行业类型的tree（查看props.placeholder或data）
    var result=[];
    for(var i=0;i<trees.length;i++){{
        var t=trees[i];
        var ph=t.$props?.placeholder||t.placeholder||'';
        var v=t.$props?.value||t.value||t.$data?.value||'';
        var data=t.$data?.data||t.$props?.data||[];
        result.push({{idx:i,placeholder:ph,value:v,dataLen:data.length,methods:Object.keys(t.$options?.methods||{{}}).slice(0,10)}});
    }}
    return result;
}})()""")
print(f"  trees: {json.dumps(tree_result, ensure_ascii=False)[:400] if isinstance(tree_result,list) else tree_result}")

# 设置行业类型
set_industry = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var f=busi.busineseForm||busi.$data?.busineseForm;
    if(!f)return'no_form';
    
    // 直接设置industryType
    busi.$set(f,'industryType','I65');
    busi.$set(f,'industryTypeName','软件和信息技术服务业');
    busi.$set(f,'industryCode','I65');
    
    // 也设置在bdi上
    var fc=findComp(vm,'flow-control',0);
    if(fc){{
        var bdi=fc.$data?.businessDataInfo;
        if(bdi){{
            fc.$set(bdi,'industryType','I65');
            fc.$set(bdi,'industryTypeName','软件和信息技术服务业');
        }}
    }}
    
    // 找tne-select-tree并设置值
    var trees=[];
    function walk(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='tne-select-tree')trees.push(vm);
        for(var i=0;i<(vm.$children||[]).length;i++)walk(vm.$children[i],d+1);
    }}
    walk(busi,0);
    
    // 第一个tree应该是行业类型
    if(trees.length>0){{
        var tree=trees[0];
        tree.$emit('input','I65');
        tree.$emit('change','I65');
        // 也尝试setValue
        if(typeof tree.setValue==='function')tree.setValue('I65');
        if(typeof tree.handleInput==='function')tree.handleInput('I65');
    }}
    
    return {{set:true,treesFound:trees.length,industryType:f.industryType}};
}})()""")
print(f"  set: {set_industry}")

# ============================================================
# Step 3: 修复genBusiArea（字符串而非数组）
# ============================================================
print("\nStep 3: 修复genBusiArea")
gen_fix = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var f=busi.busineseForm||busi.$data?.busineseForm;
    if(!f)return'no_form';
    
    // genBusiArea应为字符串
    var genBusiArea=f.genBusiArea;
    if(Array.isArray(genBusiArea)){{
        // 从busiAreaData生成
        var bad=f.busiAreaData||[];
        var names=bad.map(function(x){{return x.name||x.indusTypeName||''}});
        busi.$set(f,'genBusiArea',names.join(';'));
    }}else if(!genBusiArea){{
        var bad=f.busiAreaData||[];
        var names=bad.map(function(x){{return x.name||x.indusTypeName||''}});
        busi.$set(f,'genBusiArea',names.join(';'));
    }}
    
    // 也设置busiAreaCode
    if(!f.busiAreaCode||f.busiAreaCode==='I3006|I3010'){{
        busi.$set(f,'busiAreaCode','I65');
    }}
    
    return {{
        genBusiArea:f.genBusiArea,
        busiAreaCode:f.busiAreaCode,
        busiAreaDataLen:(f.busiAreaData||[]).length
    }};
}})()""")
print(f"  {gen_fix}")

# ============================================================
# Step 4: 同步bdi字段
# ============================================================
print("\nStep 4: 同步bdi")
sync_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    if(!fc)return'no_fc';
    var bdi=fc.$data?.businessDataInfo;
    if(!bdi)return'no_bdi';
    
    // 从businese-info同步
    var busi=findComp(vm,'businese-info',0);
    var bf=busi?.busineseForm||busi?.$data?.busineseForm||{{}};
    
    fc.$set(bdi,'busiAreaData',bf.busiAreaData||[]);
    fc.$set(bdi,'genBusiArea',bf.genBusiArea||'');
    fc.$set(bdi,'busiAreaCode',bf.busiAreaCode||'I65');
    fc.$set(bdi,'busiAreaName',bf.busiAreaName||'软件开发;信息技术咨询服务');
    fc.$set(bdi,'industryType','I65');
    fc.$set(bdi,'industryTypeName','软件和信息技术服务业');
    fc.$set(bdi,'entName','广西智信数据科技有限公司');
    fc.$set(bdi,'operatorNum','5');
    fc.$set(bdi,'empNum','5');
    fc.$set(bdi,'entPhone','13800138000');
    fc.$set(bdi,'postcode','530000');
    fc.$set(bdi,'registerCapital','100');
    fc.$set(bdi,'moneyKindCode','156');
    fc.$set(bdi,'distCode','450103');
    fc.$set(bdi,'fisDistCode','450103');
    fc.$set(bdi,'address','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detAddress','民族大道100号');
    fc.$set(bdi,'regionCode','450103');
    fc.$set(bdi,'regionName','青秀区');
    fc.$set(bdi,'businessAddress','广西壮族自治区/南宁市/青秀区');
    fc.$set(bdi,'detBusinessAddress','民族大道100号');
    
    return {{synced:true,bdiKeys:Object.keys(bdi).length}};
}})()""")
print(f"  {sync_result}")

# ============================================================
# Step 5: 验证前端
# ============================================================
print("\nStep 5: 验证前端")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误: {errors}")

check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=fc?.$data?.businessDataInfo||{{}};
    var busi=findComp(vm,'businese-info',0);
    var bf=busi?.busineseForm||{{}};
    return {{
        bdi_entName:bdi.entName||'',
        bdi_industryType:bdi.industryType||'',
        bdi_busiAreaData:bdi.busiAreaData?'set':'null',
        bdi_genBusiArea:bdi.genBusiArea||'',
        bf_genBusiArea:bf.genBusiArea||'',
        bf_industryType:bf.industryType||'',
        bf_busiAreaDataLen:(bf.busiAreaData||[]).length
    }};
}})()""")
print(f"  关键字段: {json.dumps(check, ensure_ascii=False) if isinstance(check,dict) else check}")

# ============================================================
# Step 6: 拦截XHR + 保存
# ============================================================
print("\nStep 6: 拦截+保存")
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
# Step 7: 分析请求和响应
# ============================================================
print("\nStep 7: 分析")
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
            print(f"  ⚠️ busiAreaData是STRING! len={len(ba)}")
            print(f"     前80字符: {ba[:80]}")
            try:
                decoded = json.loads(ba)
                print(f"     JSON.parse后: {type(decoded).__name__} len={len(decoded)}")
            except:
                print(f"     JSON.parse失败")
        elif isinstance(ba, list):
            print(f"  ✅ busiAreaData是ARRAY len={len(ba)}")
            if ba:
                print(f"     第一项keys: {list(ba[0].keys())[:8]}")
        elif isinstance(ba, dict):
            print(f"  ✅ busiAreaData是OBJECT keys={list(ba.keys())[:5]}")
        print(f"  genBusiArea: {type(gba).__name__} = {str(gba)[:50]}")
        
        with open(r'g:\UFO\政务平台\data\save_body_a0002.json', 'w', encoding='utf-8') as f:
            json.dump(bobj, f, ensure_ascii=False, indent=2)
        print(f"  已保存 ({len(bobj)} keys)")
    except json.JSONDecodeError:
        # 可能是URL-encoded
        print(f"  body非JSON, 前200字符: {body[:200]}")
else:
    print(f"  无请求: {req}")

if isinstance(resp, dict):
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            code = p.get('code','')
            msg = p.get('msg','')[:100]
            print(f"  API code={code} msg={msg}")
            if str(code) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
            else:
                print(f"  ❌ 错误!")
                with open(r'g:\UFO\政务平台\data\save_resp_a0002.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {resp}")

errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(后): {errors2}")

print("\n✅ 完成")
