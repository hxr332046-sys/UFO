#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手动设置radioGroup → nextBtn → namenotice → 逐步前进 → flow路由"""
import json, time, requests, websocket

def get_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    ws_url = [p["webSocketDebuggerUrl"] for p in pages if p.get("type")=="page"][0]
    return websocket.create_connection(ws_url, timeout=30)

ws = get_ws()
_mid = 0
def ev(js):
    global _mid, ws; _mid += 1; mid = _mid
    try:
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    except:
        ws = get_ws()
        ws.send(json.dumps({"id":mid,"method":"Runtime.evaluate","params":{"expression":js,"returnByValue":True,"timeout":25000}}))
    for _ in range(60):
        try:
            ws.settimeout(25); r = json.loads(ws.recv())
            if r.get("id") == mid: return r.get("result",{}).get("result",{}).get("value")
        except: return None
    return None

# Step 1: 重载
print("Step 1: 重载页面")
ev("window.location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/page'")
time.sleep(8); ws = get_ws()
for _ in range(10):
    if ev("(function(){return !!document.getElementById('app')?.__vue__})()"): break
    time.sleep(2)

# Step 2: 恢复Vuex
ev("""(function(){
    var t=localStorage.getItem('top-token')||'';
    var vm=document.getElementById('app')?.__vue__;var store=vm?.$store;if(!store)return;
    store.commit('login/SET_TOKEN',t);
    var xhr=new XMLHttpRequest();xhr.open('GET','/icpsp-api/v4/pc/manager/usermanager/getUserInfo',false);
    xhr.setRequestHeader('top-token',t);xhr.setRequestHeader('Authorization',localStorage.getItem('Authorization')||t);
    try{xhr.send();if(xhr.status===200){var resp=JSON.parse(xhr.responseText);if(resp.code==='00000'&&resp.data?.busiData)store.commit('login/SET_USER_INFO',resp.data.busiData)}}catch(e){}
})()""")
time.sleep(2)

# Step 3: XHR拦截
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var self=this;self.__body=body;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,500)||'',body:self.__body?.substring(0,200)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 4: 导航到without-name → toNotName → establish
print("\nStep 4: 导航到establish")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
time.sleep(3)
ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
time.sleep(5)

# toNotName
ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var wn=findComp(vm,'without-name',0);
    if(wn&&typeof wn.toNotName==='function')wn.toNotName();
})()""")
time.sleep(5)

page = ev("({hash:location.hash})")
print(f"  hash={page.get('hash','') if page else '?'}")

# Step 5: 分析establish组件 - 获取cardList和radioGroup
print("\nStep 5: 分析establish组件")
est_info = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var est=findComp(vm,'establish',0);
    if(!est)return{error:'no_comp'};
    return{
        cardList:JSON.stringify(est.$data?.cardList)?.substring(0,300)||'',
        radioGroup:JSON.stringify(est.$data?.radioGroup)||'',
        busiType:est.$route?.query?.busiType||'',
        entType:est.$route?.query?.entType||''
    };
})()""")
print(f"  cardList: {est_info.get('cardList','')[:200] if est_info else ''}")
print(f"  radioGroup: {est_info.get('radioGroup','') if est_info else ''}")
print(f"  busiType: {est_info.get('busiType','') if est_info else ''}")
print(f"  entType: {est_info.get('entType','') if est_info else ''}")

# Step 6: 手动设置radioGroup并调用nextBtn
print("\nStep 6: 设置radioGroup并调用nextBtn")
# radioGroup有4个slot，需要设置其中一个的checked为有效的企业类型代码
# 常见企业类型代码: 1100=有限责任公司, 1200=股份有限公司, 1300=合伙企业, 1400=个人独资
result = ev("""(function(){
    var app=document.getElementById('app');var vm=app?.__vue__;
    function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
    var est=findComp(vm,'establish',0);
    if(!est)return{error:'no_comp'};
    
    // 如果cardList有数据，用第一个
    var cl=est.$data?.cardList||[];
    if(cl.length>0){
        var code=cl[0].code||cl[0].id||cl[0].value||'';
        est.$set(est.$data.radioGroup[0],'checked',code);
        est.$forceUpdate();
    }else{
        // cardList为空，手动设置常见代码
        // 1100=有限责任公司(法人独资)
        est.$set(est.$data.radioGroup[0],'checked','1100');
        est.$forceUpdate();
    }
    
    // 调用nextBtn
    if(typeof est.nextBtn==='function'){
        try{
            est.nextBtn();
            return{called:true,radioGroup:JSON.stringify(est.$data.radioGroup)};
        }catch(e){
            return{error:e.message};
        }
    }
    return{error:'no_nextBtn'};
})()""")
print(f"  result: {result}")
time.sleep(5)

# 检查页面和API
page2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  page: hash={page2.get('hash','') if page2 else '?'} forms={page2.get('formCount',0) if page2 else 0}")

api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    if 'notHmEnterpriseType' not in url and 'isNeedEnterpriseType' not in url and 'selectModuleFlows' not in url and 'selectBusinessModules' not in url and 'searchConsultPhone' not in url:
        print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")

# Step 7: 如果到了namenotice，逐步前进
if page2 and 'namenotice' in page2.get('hash',''):
    print("\nStep 7: 在namenotice页面，逐步前进")
    
    for step in range(12):
        current = ev("""(function(){return{hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length,btnCount:document.querySelectorAll('button:not([disabled])').length,checkboxCount:document.querySelectorAll('.el-checkbox__input:not(.is-checked)').length,radioCount:document.querySelectorAll('.el-radio__input:not(.is-checked)').length}})()""")
        h = current.get('hash','') if current else '?'
        fc = current.get('formCount',0) if current else 0
        bc = current.get('btnCount',0) if current else 0
        cc = current.get('checkboxCount',0) if current else 0
        rc = current.get('radioCount',0) if current else 0
        
        print(f"\n  步骤{step}: hash={h} forms={fc} btns={bc} checkboxes={cc} radios={rc}")
        
        if fc > 20:
            print("  ✅ 大量表单！")
            break
        
        # 检查flow路由
        flow = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');return all.filter(function(r){return r.includes('flow')})})()""")
        if flow:
            print(f"  ✅ flow路由: {flow}")
            for route in flow:
                if 'basic-info' in route:
                    ev(f"""(function(){{var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('{route}')}})()""")
                    time.sleep(5)
                    fc2 = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
                    if fc2 and fc2.get('formCount',0) > 10:
                        print(f"  ✅ 表单加载！hash={fc2.get('hash','')} forms={fc2.get('formCount',0)}")
                    break
            break
        
        # 勾选checkbox
        if cc > 0:
            ev("""(function(){var cbs=document.querySelectorAll('.el-checkbox__input:not(.is-checked)');for(var i=0;i<cbs.length;i++){cbs[i].click()}})()""")
            time.sleep(1)
        
        # 选择radio
        if rc > 0:
            ev("""(function(){var radios=document.querySelectorAll('.el-radio__input:not(.is-checked)');for(var i=0;i<radios.length;i++){radios[i].click()}})()""")
            time.sleep(1)
        
        # 点击下一步
        clicked = ev("""(function(){
            var btns=document.querySelectorAll('button,.el-button');
            for(var i=0;i<btns.length;i++){
                var t=btns[i].textContent?.trim()||'';
                if((t.includes('下一步')||t.includes('确定')||t.includes('同意')||t.includes('确认')||t.includes('我已阅读')||t.includes('我同意')||t.includes('继续'))&&btns[i].offsetParent!==null&&!btns[i].disabled){
                    btns[i].click();return{clicked:t};
                }
            }
            return{clicked:false};
        })()""")
        print(f"  点击: {clicked}")
        
        if not clicked or not clicked.get('clicked'):
            # 尝试Vue组件方法
            method_result = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findActive(vm,d){if(d>12)return null;
                    if(vm.$options?.name&&vm.$el?.offsetParent!==null){
                        var methods=vm.$options?.methods||{};
                        for(var m in methods){
                            if(m.includes('next')||m.includes('Next')||m.includes('start')||m.includes('toItem')||m.includes('handleNext')){
                                try{methods[m].call(vm);return{called:m,comp:vm.$options.name}}catch(e){}
                            }
                        }
                    }
                    for(var i=0;i<(vm.$children||[]).length;i++){var r=findActive(vm.$children[i],d+1);if(r)return r}return null}
                return findActive(vm,0);
            })()""")
            print(f"  method: {method_result}")
        
        time.sleep(3)
        
        # 检查API
        api_logs2 = ev("window.__api_logs||[]")
        new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
        for l in new_apis[-3:]:
            url = l.get('url','')
            print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')}")
        api_logs = api_logs2
        
        # 如果hash没变且没有按钮，停止
        if h == (current.get('hash','') if current else '') and bc == 0:
            print("  无变化且无按钮，停止")
            break

elif page2 and 'flow' in page2.get('hash',''):
    print("\n  ✅ 已到flow页面！")
elif page2 and 'establish' in page2.get('hash',''):
    print("\n  还在establish页面，nextBtn可能失败")
    # 检查错误消息
    msg = ev("""(function(){var msgs=document.querySelectorAll('.el-message,[class*="message"]');var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t)r.push(t)}return r.slice(0,3)})()""")
    print(f"  消息: {msg}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

routes = ev("""(function(){var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')});return{total:all.length,flow:flow}})()""")
print(f"  flow routes: {routes.get('flow',[])}")

ws.close()
print("✅ 完成")
