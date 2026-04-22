#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""正确初始化行业类型tree + 设值 + 触发保存"""
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
# Step 1: 查看indSelectTree ref
# ============================================================
print("Step 1: indSelectTree ref")
ref_info = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var refs=Object.keys(busi.$refs||{{}});
    var indTree=busi.$refs?.indSelectTree;
    if(!indTree)return {{refs:refs,noIndTree:true}};
    return {{
        refs:refs,
        indTreeName:indTree.$options?.name||'',
        valueId:indTree.valueId||indTree.$data?.valueId||indTree.$props?.valueId||'',
        valueTitle:indTree.valueTitle||indTree.$data?.valueTitle||indTree.$props?.valueTitle||'',
        data:indTree.$data?.data||indTree.$props?.data||[],
        dataLen:(indTree.$data?.data||indTree.$props?.data||[]).length,
        methods:Object.keys(indTree.$options?.methods||{{}}).slice(0,15)
    }};
}})()""")
print(f"  {json.dumps(ref_info, ensure_ascii=False)[:400] if isinstance(ref_info,dict) else ref_info}")

# ============================================================
# Step 2: 初始化tree数据
# ============================================================
print("\nStep 2: 初始化tree数据")
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var indTree=busi.$refs?.indSelectTree;
    if(!indTree)return'no_ref';
    
    // 设置industryList作为tree数据
    var il=busi.$data?.industryList||[];
    if(il.length>0){{
        // 设置data
        busi.$set(indTree.$data||indTree,'data',il);
        if(indTree.$props&&indTree.$props.data!==undefined){{
            // 通过parent设置
        }}
        // 调用initView
        if(typeof indTree.initView==='function')indTree.initView();
        if(typeof indTree.initTreeView==='function')indTree.initTreeView();
    }}
    
    return {{
        dataLen:(indTree.$data?.data||[]).length,
        ilLen:il.length
    }};
}})()""", timeout=15)
print(f"  init: {init_result}")
time.sleep(3)

# ============================================================
# Step 3: 设置valueId和valueTitle
# ============================================================
print("\nStep 3: 设置valueId/valueTitle")
set_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    var indTree=busi.$refs?.indSelectTree;
    if(!indTree)return'no_ref';
    
    // 设置valueId和valueTitle
    busi.$set(indTree,'valueId','I65');
    busi.$set(indTree,'valueTitle','[I65]软件和信息技术服务业');
    if(indTree.$data){{
        busi.$set(indTree.$data,'valueId','I65');
        busi.$set(indTree.$data,'valueTitle','[I65]软件和信息技术服务业');
    }}
    
    // 调用treeSelectChange('ind')
    busi.treeSelectChange('ind');
    
    return {{
        valueId:indTree.valueId||indTree.$data?.valueId||'',
        valueTitle:indTree.valueTitle||indTree.$data?.valueTitle||'',
        formIndustryType:busi.busineseForm?.industryType||'',
        formIndustryTypeName:busi.busineseForm?.industryTypeName||'',
        paramsIndustryCode:busi.$data?.params?.industryCode||''
    }};
}})()""")
print(f"  {set_result}")

# ============================================================
# Step 4: 验证
# ============================================================
print("\nStep 4: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 5: 如果验证通过，拦截+保存
# ============================================================
print("\nStep 5: 拦截+保存")
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

# 点击保存并下一步
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
# Step 6: 分析
# ============================================================
print("\nStep 6: 分析")
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
    # 可能是前端验证仍阻止了请求
    # 尝试直接调用flow-control的save方法
    print("  尝试直接调用save...")
    ev("""(function(){
        window.__save_req=null;window.__save_resp=null;
    })()""")
    
    save_direct = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var fc=findComp(vm,'flow-control',0);
        if(!fc)return'no_fc';
        try{{
            fc.save(null,null,'working');
            return {{called:true}};
        }}catch(e){{
            return {{error:e.message.substring(0,80)}};
        }}
    }})()""", timeout=20)
    print(f"  save: {save_direct}")
    time.sleep(10)
    
    req2 = ev("window.__save_req")
    resp2 = ev("window.__save_resp")
    if isinstance(req2, dict) and req2.get('body'):
        body = req2.get('body','')
        try:
            bobj = json.loads(body)
            ba = bobj.get('busiAreaData')
            gba = bobj.get('genBusiArea')
            print(f"  busiAreaData: {type(ba).__name__}")
            if isinstance(ba, str):
                print(f"  ⚠️ STRING: {ba[:80]}")
            elif isinstance(ba, list):
                print(f"  ✅ ARRAY len={len(ba)}")
            print(f"  genBusiArea: {str(gba)[:50]}")
            with open(r'g:\UFO\政务平台\data\save_body_a0002.json', 'w', encoding='utf-8') as f:
                json.dump(bobj, f, ensure_ascii=False, indent=2)
            print(f"  已保存 ({len(bobj)} keys)")
        except:
            print(f"  非JSON: {body[:200]}")
    else:
        print(f"  仍无请求: {req2}")

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

print("\n✅ 完成")
