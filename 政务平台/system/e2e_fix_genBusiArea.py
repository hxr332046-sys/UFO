#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修正genBusiArea双重编码 + busiAreaData格式 + 完整保存"""
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
# Step 1: 修正businese-info form中的genBusiArea
# ============================================================
print("Step 1: 修正genBusiArea编码问题")

# 先检查当前值
gen_val = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    var form=bi.busineseForm;
    return{{
        genBusiArea:typeof form.genBusiArea+'|'+String(form.genBusiArea).substring(0,60),
        busiAreaName:typeof form.busiAreaName+'|'+String(form.busiAreaName).substring(0,60),
        businessArea:typeof form.businessArea+'|'+String(form.businessArea).substring(0,60),
        busiAreaCode:form.busiAreaCode||''
    }};
}})()""")
print(f"  当前值: {gen_val}")

# 修正为纯文本
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return;
    var form=bi.busineseForm;
    // 解码genBusiArea如果是URL编码的
    var gba=form.genBusiArea||'';
    if(typeof gba==='string'&&gba.includes('%')){{
        try{{gba=decodeURIComponent(gba)}}catch(e){{}}
    }}
    // 如果还是JSON字符串（带引号），去掉引号
    if(typeof gba==='string'&&gba.startsWith('"')){{
        try{{gba=JSON.parse(gba)}}catch(e){{gba=gba.replace(/^"|"$/g,'')}}
    }}
    bi.$set(form,'genBusiArea','软件开发;信息技术咨询服务');
    bi.$set(form,'busiAreaName','软件开发;信息技术咨询服务');
    bi.$set(form,'busiAreaCode','I65');
    bi.$set(form,'businessArea','许可经营项目：软件开发；信息技术咨询服务。（依法须经批准的项目，经相关部门批准后方可开展经营活动）');
    bi.$forceUpdate();
    return{{fixed:true,genBusiArea:form.genBusiArea}};
}})()""")

# ============================================================
# Step 2: 拦截XHR - 全面修正请求body
# ============================================================
print("\nStep 2: 拦截+全面修正")
ev("""(function(){
    window.__save_result=null;
    window.__fix_log=[];
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')&&body){
            try{
                var data=JSON.parse(body);
                
                // 1. 修正genBusiArea: 去掉URL编码和JSON引号
                if(typeof data.genBusiArea==='string'){
                    var gba=data.genBusiArea;
                    if(gba.includes('%')){
                        try{gba=decodeURIComponent(gba)}catch(e){}
                    }
                    if(gba.startsWith('"')){
                        try{gba=JSON.parse(gba)}catch(e){gba=gba.replace(/^"|"$/g,'')}
                    }
                    data.genBusiArea='软件开发;信息技术咨询服务';
                    window.__fix_log.push('genBusiArea: fixed to plain text');
                }
                
                // 2. 修正busiAreaName
                if(typeof data.busiAreaName==='string'){
                    var ban=data.busiAreaName;
                    if(ban.includes('%')){
                        try{ban=decodeURIComponent(ban)}catch(e){}
                    }
                    if(ban.startsWith('"')){
                        try{ban=JSON.parse(ban)}catch(e){ban=ban.replace(/^"|"$/g,'')}
                    }
                    data.busiAreaName='软件开发;信息技术咨询服务';
                }
                
                // 3. 修正busiAreaData格式
                if(typeof data.busiAreaData==='string'){
                    try{
                        var decoded=decodeURIComponent(data.busiAreaData);
                        data.busiAreaData=JSON.parse(decoded);
                        window.__fix_log.push('busiAreaData: url-string->object');
                    }catch(e){
                        try{
                            data.busiAreaData=JSON.parse(data.busiAreaData);
                            window.__fix_log.push('busiAreaData: string->object');
                        }catch(e2){
                            window.__fix_log.push('busiAreaData: parse failed');
                        }
                    }
                }
                
                // 4. 确保businessArea有值
                if(!data.businessArea||data.businessArea===''){
                    data.businessArea='许可经营项目：软件开发；信息技术咨询服务。（依法须经批准的项目，经相关部门批准后方可开展经营活动）';
                }
                
                // 5. 修正busiDateEnd/Start
                if(data.busiPeriod==='01'){
                    data.busiDateEnd='';
                    data.busiDateStart='';
                }
                
                // 6. 确保namePreFlag是boolean
                // 注意：原始body中namePreFlag是false，但bdi中是'1'
                // 保持原样，让Vue处理
                
                body=JSON.stringify(data);
            }catch(e){
                window.__fix_log.push('error:'+e.message);
            }
            var self=this;
            self.addEventListener('load',function(){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,800)||''};
            });
        }
        return origSend.apply(this,[body]);
    };
})()""")

# ============================================================
# Step 3: 保存
# ============================================================
print("\nStep 3: 保存")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

fix_log = ev("window.__fix_log")
print(f"  修正日志: {fix_log}")

resp = ev("window.__save_result")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            code = p.get('code','')
            msg = p.get('msg','')[:80]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000']:
                print("  ✅ 保存成功！")
            else:
                d = p.get('data')
                if d:
                    if isinstance(d, str):
                        print(f"  data(str): {d[:200]}")
                    else:
                        print(f"  data: {json.dumps(d, ensure_ascii=False)[:200]}")
                # 检查是否有更详细的错误信息
                if isinstance(p, dict):
                    for k,v in p.items():
                        if k not in ['code','msg','data','page']:
                            print(f"  {k}: {str(v)[:60]}")
        except:
            print(f"  raw: {r[:200]}")
else:
    print("  无API响应")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

print("\n✅ 完成")
