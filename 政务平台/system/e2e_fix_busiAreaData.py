#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拦截保存请求，修正busiAreaData为JSON对象而非URL编码字符串"""
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
# Step 1: 先看busiAreaData当前是什么格式
# ============================================================
print("Step 1: busiAreaData格式分析")
ba_raw = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return'no_bi';
    var form=bi.busineseForm;
    var ba=form.busiAreaData;
    if(!ba)return'null';
    if(typeof ba==='string')return'type:string,len:'+ba.length+',first50:'+ba.substring(0,50);
    if(Array.isArray(ba))return'type:array,len:'+ba.length;
    if(typeof ba==='object')return'type:object,keys:'+Object.keys(ba).join(',');
    return'type:'+typeof ba;
}})()""")
print(f"  busiAreaData: {ba_raw}")

# ============================================================
# Step 2: 拦截XHR - 修正busiAreaData格式
# ============================================================
print("\nStep 2: 拦截+修正busiAreaData")

ev("""(function(){
    window.__save_result=null;
    window.__patch_log=[];
    var origSend=XMLHttpRequest.prototype.send;
    var origOpen=XMLHttpRequest.prototype.open;
    var origSetHeader=XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
    XMLHttpRequest.prototype.setRequestHeader=function(k,v){this.__headers=this.__headers||{};this.__headers[k]=v;return origSetHeader.apply(this,arguments)};
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        if(url.includes('operationBusinessData')&&body){
            try{
                var data=JSON.parse(body);
                // 修正busiAreaData: 如果是字符串则解析为JSON对象
                if(typeof data.busiAreaData==='string'){
                    try{
                        var decoded=decodeURIComponent(data.busiAreaData);
                        data.busiAreaData=JSON.parse(decoded);
                        window.__patch_log.push('busiAreaData: string->object');
                    }catch(e){
                        try{
                            data.busiAreaData=JSON.parse(data.busiAreaData);
                            window.__patch_log.push('busiAreaData: string->object(direct)');
                        }catch(e2){
                            window.__patch_log.push('busiAreaData: parse failed:'+e2.message);
                        }
                    }
                }
                // 确保businessArea有值
                if(!data.businessArea||data.businessArea===''){
                    data.businessArea='许可经营项目：软件开发；信息技术咨询服务。（依法须经批准的项目，经相关部门批准后方可开展经营活动）';
                }
                if(!data.genBusiArea){
                    data.genBusiArea='软件开发;信息技术咨询服务';
                }
                if(!data.busiAreaName){
                    data.busiAreaName='软件开发;信息技术咨询服务';
                }
                body=JSON.stringify(data);
            }catch(e){
                window.__patch_log.push('parse_error:'+e.message);
            }
            var self=this;
            self.addEventListener('load',function(){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            });
        }
        return origSend.apply(this,[body]);
    };
})()""")

# ============================================================
# Step 3: 触发保存
# ============================================================
print("\nStep 3: 保存")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

# 检查patch日志
patch_log = ev("window.__patch_log")
print(f"  patch日志: {patch_log}")

# 检查结果
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
                    print(f"  data: {json.dumps(d, ensure_ascii=False)[:200]}")
        except:
            print(f"  raw: {r[:200]}")
else:
    print("  无API响应")

errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

print("\n✅ 完成")
