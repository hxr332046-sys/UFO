#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - select-prise页面 → 其他来源名称对话框 → 提交 → getHandleBusiness → 表单"""
import json, time, os, requests, websocket
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_report import log

pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
ws = websocket.create_connection(ws_url, timeout=30)
_mid = 0
def ev(js):
    global _mid; _mid += 1; mid = _mid
    ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":20000}}))
    for _ in range(30):
        try:
            ws.settimeout(20); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# 恢复Vuex
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;
    var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")

# Step 1: 确保在select-prise页面
page = ev("({hash:location.hash})")
print(f"当前: hash={page.get('hash','') if page else '?'}")

if page and 'select-prise' not in page.get('hash',''):
    # 导航到企业开办专区 → 开始办理 → select-prise
    print("导航到select-prise...")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
    time.sleep(3)
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/select-prise')})()""")
    time.sleep(3)

# Step 2: 分析select-prise组件
print("\nStep 2: 分析select-prise组件")
comp = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    var methods=Object.keys(sp.$options?.methods||{});
    var data=sp.$data||{};
    return{
        compName:sp.$options?.name||'',
        methods:methods,
        dataKeys:Object.keys(data),
        priseName:data.priseName||'',
        priseNo:data.priseNo||'',
        busiDataListLen:data.busiDataList?.length||0,
        nameId:data.nameId||''
    };
})()""")
print(f"  comp: {comp}")

# Step 3: 点击"其他来源名称"
print("\nStep 3: 点击其他来源名称")
ev("""(function(){
    var btns=document.querySelectorAll('button,.el-button');
    for(var i=0;i<btns.length;i++){
        if(btns[i].textContent?.trim()?.includes('其他来源')&&btns[i].offsetParent!==null){
            btns[i].click();return;
        }
    }
})()""")
time.sleep(2)

# Step 4: 分析对话框
print("\nStep 4: 分析对话框")
dialog = ev("""(function(){
    var dialogs=document.querySelectorAll('.el-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null){
            var inputs=dialogs[i].querySelectorAll('.el-input__inner,input,textarea');
            var btns=dialogs[i].querySelectorAll('button,.el-button');
            var inputInfo=[];
            for(var j=0;j<inputs.length;j++){
                inputInfo.push({idx:j,ph:inputs[j].placeholder||'',type:inputs[j].type||'',val:inputs[j].value||'',visible:inputs[j].offsetParent!==null});
            }
            var btnInfo=[];
            for(var j=0;j<btns.length;j++){
                btnInfo.push({idx:j,text:btns[j].textContent?.trim()?.substring(0,20)||''});
            }
            return{
                found:true,
                title:dialogs[i].querySelector('.el-dialog__title,[class*="title"]')?.textContent?.trim()||'',
                inputInfo:inputInfo,
                btnInfo:btnInfo,
                text:dialogs[i].textContent?.trim()?.substring(0,100)||''
            };
        }
    }
    return{found:false};
})()""")
print(f"  dialog: found={dialog.get('found') if dialog else '?'}")
if dialog and dialog.get('found'):
    print(f"  title: {dialog.get('title','')}")
    print(f"  inputs: {dialog.get('inputInfo',[])}")
    print(f"  buttons: {dialog.get('btnInfo',[])}")

# Step 5: 填写对话框
print("\nStep 5: 填写对话框")
if dialog and dialog.get('found') and dialog.get('inputInfo'):
    for inp in dialog.get('inputInfo',[]):
        ph = inp.get('ph','')
        idx = inp.get('idx',0)
        if '名称' in ph or '企业' in ph or '字号' in ph:
            val = '广西智信数据科技有限公司'
            print(f"  填写 #{idx} ph={ph}: {val}")
            ev(f"""(function(){{
                var dialogs=document.querySelectorAll('.el-dialog,[class*="dialog"]');
                for(var i=0;i<dialogs.length;i++){{
                    if(dialogs[i].offsetParent!==null){{
                        var inputs=dialogs[i].querySelectorAll('.el-input__inner,input');
                        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                        s.call(inputs[{idx}],'{val}');
                        inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                        inputs[{idx}].dispatchEvent(new Event('change',{{bubbles:true}}));
                        return;
                    }}
                }}
            }})()""")
        elif '单号' in ph or '保留' in ph or '通知' in ph or '文号' in ph:
            val = 'GX2024001'
            print(f"  填写 #{idx} ph={ph}: {val}")
            ev(f"""(function(){{
                var dialogs=document.querySelectorAll('.el-dialog,[class*="dialog"]');
                for(var i=0;i<dialogs.length;i++){{
                    if(dialogs[i].offsetParent!==null){{
                        var inputs=dialogs[i].querySelectorAll('.el-input__inner,input');
                        var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                        s.call(inputs[{idx}],'{val}');
                        inputs[{idx}].dispatchEvent(new Event('input',{{bubbles:true}}));
                        inputs[{idx}].dispatchEvent(new Event('change',{{bubbles:true}}));
                        return;
                    }}
                }}
            }})()""")
    time.sleep(1)

# Step 6: 点击确定
print("\nStep 6: 点击确定")
ev("""(function(){
    var dialogs=document.querySelectorAll('.el-dialog,[class*="dialog"]');
    for(var i=0;i<dialogs.length;i++){
        if(dialogs[i].offsetParent!==null){
            var btns=dialogs[i].querySelectorAll('button,.el-button');
            for(var j=0;j<btns.length;j++){
                var t=btns[j].textContent?.trim()||'';
                if(t.includes('确定')||t.includes('确认')||t.includes('提交')){
                    btns[j].click();return;
                }
            }
        }
    }
})()""")
time.sleep(3)

# Step 7: 检查提交结果
print("\nStep 7: 检查提交结果")
comp2 = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var sp=findComp(vm,'select-prise',0);
    if(!sp)return{error:'no_comp'};
    return{
        priseName:sp.$data?.priseName||'',
        priseNo:sp.$data?.priseNo||'',
        busiDataListLen:sp.$data?.busiDataList?.length||0,
        nameId:sp.$data?.nameId||'',
        hash:location.hash
    };
})()""")
print(f"  comp2: {comp2}")

# Step 8: 如果有nameId，调用getHandleBusiness
if comp2 and comp2.get('nameId'):
    print(f"\nStep 8: 调用getHandleBusiness (nameId={comp2.get('nameId')})")
    ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var sp=findComp(vm,'select-prise',0);
        if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness();
    })()""")
    time.sleep(3)
    
    # 检查动态路由
    routes = ev("""(function(){
        var vm=document.getElementById('app')?.__vue__;
        var router=vm?.$router;
        var routes=router?.options?.routes||[];
        function findRoutes(rs,prefix){
            var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r;
        }
        var all=findRoutes(routes,'');
        var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
        return{total:all.length,flow:flow};
    })()""")
    print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")
    
    # 导航到表单
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
    time.sleep(5)
else:
    # 如果没有nameId，检查API错误
    print("\nStep 8: 无nameId，检查API")
    
    # 检查是否有错误提示
    err_msg = ev("""(function(){
        var msgs=document.querySelectorAll('.el-message,[class*="message"],.el-alert');
        var r=[];
        for(var i=0;i<msgs.length;i++){
            var t=msgs[i].textContent?.trim()||'';
            if(t.length>2&&t.length<100)r.push(t);
        }
        return r.slice(0,5);
    })()""")
    print(f"  错误消息: {err_msg}")
    
    # 尝试直接调用API获取nameId
    print("  尝试API获取nameId...")
    api_result = ev("""(function(){
        var t=localStorage.getItem('top-token')||'';
        var xhr=new XMLHttpRequest();
        xhr.open('POST','/icpsp-api/v4/pc/flow/name/saveOtherName',false);
        xhr.setRequestHeader('Content-Type','application/json');
        xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
        try{
            xhr.send(JSON.stringify({entName:'广西智信数据科技有限公司',nameNoticeNo:'GX2024001',entType:'1100'}));
            if(xhr.status===200){
                var resp=JSON.parse(xhr.responseText);
                return{status:xhr.status,code:resp.code,data:JSON.stringify(resp.data)?.substring(0,200)||'',msg:resp.msg||''};
            }
            return{status:xhr.status,response:xhr.responseText?.substring(0,200)};
        }catch(e){return{error:e.message}}
    })()""")
    print(f"  api_result: {api_result}")
    
    # 如果API返回了nameId，设置到组件
    if api_result and api_result.get('code') == '00000':
        nameId = api_result.get('data','')
        print(f"  获取nameId: {nameId}")
        ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var sp=findComp(vm,'select-prise',0);
            if(sp){{sp.$set(sp.$data,'nameId','{nameId}');if(typeof sp.getHandleBusiness==='function')sp.getHandleBusiness()}}
        }})()""")
        time.sleep(3)
        ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
        time.sleep(5)

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

if fc and fc.get('formCount',0) > 0:
    print("✅ 表单已加载！")
else:
    # 尝试其他API路径
    print("\n尝试其他API路径...")
    for api_path in [
        '/icpsp-api/v4/pc/flow/name/saveOtherSourceName',
        '/icpsp-api/v4/pc/flow/namenotice/saveOtherName',
        '/icpsp-api/v4/pc/flow/base/getNameInfo',
        '/icpsp-api/v4/pc/flow/name/getHandleBusiness',
    ]:
        r = ev(f"""(function(){{
            var t=localStorage.getItem('top-token')||'';
            var xhr=new XMLHttpRequest();
            xhr.open('GET','{api_path}?entType=1100',false);
            xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
            try{{xhr.send();return{{status:xhr.status,code:JSON.parse(xhr.responseText).code,data:JSON.stringify(JSON.parse(xhr.responseText).data)?.substring(0,100)}}}}catch(e){{return{{error:e.message}}}}
        }})()""")
        print(f"  {api_path}: {r}")

log("360.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 完成")
