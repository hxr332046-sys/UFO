#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""捕获完整保存请求body，保存到文件分析"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
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

FC = """function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}"""

# ============================================================
# Step 1: 捕获完整请求body
# ============================================================
print("Step 1: 捕获完整请求body")
ev("""(function(){
    window.__full_body=null;
    window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__full_body=body||'';
            var self=this;
            self.addEventListener('load',function(){
                window.__save_resp={status:self.status,text:self.responseText||''};
            });
        }
        return origSend.apply(this,arguments);
    };
})()""")

ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{}}
}})()""", timeout=15)
time.sleep(5)

body = ev("window.__full_body")
resp = ev("window.__save_resp")

if isinstance(body, str) and body:
    # 保存到文件
    with open(r'g:\UFO\政务平台\data\save_request_body.json', 'w', encoding='utf-8') as f:
        f.write(body)
    print(f"  body长度: {len(body)}")
    
    # 解析并分析
    try:
        bobj = json.loads(body)
        print(f"  keys({len(bobj)}): {list(bobj.keys())}")
        
        # 检查每个字段的值
        for k, v in sorted(bobj.items()):
            if v is None or v == '' or v == 'null':
                print(f"  ⚠️ {k}: {v}")
            elif isinstance(v, str) and len(v) > 60:
                print(f"  {k}: {v[:60]}...")
            elif k == 'busiAreaData':
                # 解码busiAreaData
                if isinstance(v, str):
                    try:
                        decoded = json.loads(v)
                        print(f"  {k}: string->object, keys={list(decoded.keys()) if isinstance(decoded,dict) else 'array'}")
                        if isinstance(decoded, dict) and 'param' in decoded:
                            print(f"    firstPlace={decoded.get('firstPlace')}, param.len={len(decoded.get('param',[]))}")
                            for p in decoded.get('param',[])[:2]:
                                print(f"    param: id={p.get('id')}, name={p.get('name')}, stateCo={p.get('stateCo')}")
                    except:
                        print(f"  {k}: URL-encoded string, len={len(v)}")
                else:
                    print(f"  {k}: {type(v).__name__}")
            else:
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"  parse error: {e}")

if isinstance(resp, dict):
    print(f"\n  API status={resp.get('status')}")
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            print(f"  code={p.get('code')} msg={p.get('msg','')[:60]}")
            # 检查data中是否有详细错误
            d = p.get('data')
            if d:
                print(f"  data: {json.dumps(d, ensure_ascii=False)[:300]}")
        except:
            print(f"  raw: {text[:200]}")

# ============================================================
# Step 2: 分析"从业人数"字段的Vue绑定
# ============================================================
print("\n\nStep 2: 从业人数字段绑定")
emp_bind = ev("""(function(){
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('从业人数')){
            var input=items[i].querySelector('input');
            var comp=input?.__vue__;
            var parentComp=comp?comp.$parent:null;
            var propName='';
            if(comp){
                // 找v-model绑定
                var vnode=comp.$vnode;
                if(vnode&&vnode.data&&vnode.data.model){
                    propName=vnode.data.model.expression||'';
                }
            }
            return{
                inputValue:input?.value||'',
                prop:comp?.prop||comp?.$attrs?.prop||'',
                parentName:parentComp?.$options?.name||'',
                modelExpr:propName
            };
        }
    }
    return 'not_found';
})()""")
print(f"  从业人数: {emp_bind}")

# ============================================================
# Step 3: 检查regist-info的form验证规则
# ============================================================
print("\nStep 3: regist-info验证规则")
ri_rules = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return'no_ri';
    var form=ri.registForm||ri.$data?.registForm;
    // 找el-form的ref
    var formRef=ri.$refs?.registFormRef||ri.$refs?.form||ri.$refs?.elForm;
    // 检查rules
    var rules=ri.rules||ri.$data?.rules||{{}};
    var opRules=rules.operatorNum||rules.empNum||[];
    return{{
        operatorNum:form?.operatorNum||'MISSING',
        empNum:form?.empNum||'MISSING',
        opRules:opRules,
        formRef:!!formRef,
        rulesKeys:Object.keys(rules).slice(0,10)
    }};
}})()""")
print(f"  验证规则: {ri_rules}")

print("\n✅ 完成")
