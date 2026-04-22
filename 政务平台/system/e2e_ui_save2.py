#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过UI保存按钮触发保存，捕获完整请求body和响应"""
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
# Step 1: 先确保从业人数DOM同步
# ============================================================
print("Step 1: 从业人数DOM同步")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(ri){{
        var form=ri.registForm||ri.$data?.registForm;
        if(form){{
            ri.$set(form,'operatorNum','5');
            ri.$set(form,'empNum','5');
        }}
        // 找el-form并清除验证
        var elForm=ri.$refs?.registFormRef||ri.$refs?.elForm;
        if(elForm){{
            try{{elForm.clearValidate()}}catch(e){{}}
        }}
    }}
}})()""")

# DOM同步
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){
            s.call(input,'5');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
            input.dispatchEvent(new Event('blur',{bubbles:true}));
        }
        if(label.includes('详细地址')&&!label.includes('生产经营')){
            s.call(input,'民族大道100号');
            input.dispatchEvent(new Event('input',{bubbles:true}));
            input.dispatchEvent(new Event('change',{bubbles:true}));
        }
    }
})()""")

# ============================================================
# Step 2: 拦截完整请求+响应
# ============================================================
print("\nStep 2: 拦截请求")
ev("""(function(){
    window.__save_req=null;
    window.__save_resp=null;
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')){
            window.__save_req={
                url:url,
                body:body||'',
                bodyLen:(body||'').length,
                bodyStart:(body||'').substring(0,200)
            };
            var self=this;
            self.addEventListener('load',function(){
                window.__save_resp={
                    status:self.status,
                    text:self.responseText||''
                };
            });
        }
        return origSend.apply(this,arguments);
    };
})()""")

# ============================================================
# Step 3: 找并点击保存按钮
# ============================================================
print("\nStep 3: 找保存按钮")
btns = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    var r=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        var vis=all[i].offsetParent!==null;
        if(t.length>0&&t.length<20&&vis){
            r.push({idx:i,text:t,cls:all[i].className?.substring(0,40)||'',disabled:all[i].disabled});
        }
    }
    return r;
})()""")
print(f"  可见按钮: {btns}")

# 点击暂存按钮
click_result = ev("""(function(){
    var all=document.querySelectorAll('button,.el-button');
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if((t.includes('暂存')||t.includes('保存草稿'))&&!all[i].disabled){
            all[i].click();
            return {clicked:t,idx:i};
        }
    }
    // 也找底部操作栏按钮
    var footers=document.querySelectorAll('.footer-btn,.bottom-btn,.flow-footer,.operation-bar');
    for(var i=0;i<footers.length;i++){
        var btns2=footers[i].querySelectorAll('button');
        for(var j=0;j<btns2.length;j++){
            var t2=btns2[j].textContent?.trim()||'';
            if(t2.includes('暂存')||t2.includes('保存')){
                btns2[j].click();
                return {clicked:t2,from:'footer'};
            }
        }
    }
    return 'no_save_btn';
})()""")
print(f"  点击: {click_result}")
time.sleep(5)

# ============================================================
# Step 4: 检查请求和响应
# ============================================================
print("\nStep 4: 请求分析")
req = ev("window.__save_req")
resp = ev("window.__save_resp")

if isinstance(req, dict):
    print(f"  URL: {req.get('url','')[:80]}")
    print(f"  body长度: {req.get('bodyLen',0)}")
    body = req.get('body','')
    if body:
        try:
            bobj = json.loads(body)
            # 检查busiAreaData格式
            ba = bobj.get('busiAreaData')
            if ba is None:
                print("  ⚠️ busiAreaData: null/missing")
            elif isinstance(ba, str):
                print(f"  ⚠️ busiAreaData: STRING len={len(ba)}, first80={ba[:80]}")
                # 尝试解码
                try:
                    decoded = json.loads(ba)
                    print(f"    decoded type: {type(decoded).__name__}")
                    if isinstance(decoded, dict):
                        print(f"    decoded keys: {list(decoded.keys())}")
                except:
                    try:
                        decoded = json.loads(decodeURIComponent(ba))
                        print(f"    urlDecoded type: {type(decoded).__name__}")
                    except:
                        print("    cannot decode")
            elif isinstance(ba, list):
                print(f"  busiAreaData: ARRAY[{len(ba)}]")
                for item in ba[:2]:
                    print(f"    item: {json.dumps(item, ensure_ascii=False)[:80]}")
            elif isinstance(ba, dict):
                print(f"  busiAreaData: OBJECT keys={list(ba.keys())}")
            
            # 检查genBusiArea
            gba = bobj.get('genBusiArea')
            if isinstance(gba, str) and '%' in gba:
                print(f"  ⚠️ genBusiArea: URL-encoded: {gba[:60]}")
            else:
                print(f"  genBusiArea: {gba}")
            
            # 检查operatorNum
            print(f"  operatorNum: {bobj.get('operatorNum')}")
            print(f"  empNum: {bobj.get('empNum')}")
            
            # 保存完整body
            with open(r'g:\UFO\政务平台\data\save_body_ui.json', 'w', encoding='utf-8') as f:
                json.dump(bobj, f, ensure_ascii=False, indent=2)
            print(f"  完整body已保存到 data/save_body_ui.json ({len(bobj)} keys)")
        except Exception as e:
            print(f"  parse error: {e}")
            print(f"  body前300: {body[:300]}")
else:
    print(f"  无请求捕获: {req}")

if isinstance(resp, dict):
    print(f"\n  API status={resp.get('status')}")
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            print(f"  code={p.get('code')} msg={p.get('msg','')[:60]}")
            d = p.get('data')
            if d:
                print(f"  data: {json.dumps(d, ensure_ascii=False)[:200]}")
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {resp}")

# 验证错误
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"\n  验证错误: {errors}")

print("\n✅ 完成")
