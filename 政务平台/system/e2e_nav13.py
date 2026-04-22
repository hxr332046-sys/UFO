#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航 - 触发toBanLi → 跟踪selectModuleFlows API → 自然导航到表单"""
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

# Step 1: 回首页
print("Step 1: 回首页")
ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm&&vm.$router)vm.$router.push('/index/page')})()""")
time.sleep(3)

# Step 2: 安装XHR拦截器
print("\nStep 2: 安装XHR拦截器")
ev("""(function(){
    window.__api_logs=[];
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;this.__method=m;return origOpen.apply(this,arguments)};
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(){
        var self=this;
        this.addEventListener('load',function(){
            if(self.__url&&!self.__url.includes('getUserInfo')&&!self.__url.includes('getCacheCreateTime')){
                window.__api_logs.push({url:self.__url,method:self.__method,status:self.status,response:self.responseText?.substring(0,300)||''});
            }
        });
        return origSend.apply(this,arguments);
    };
})()""")

# Step 3: 找到toBanLi方法并调用
print("\nStep 3: 调用toBanLi")
result = ev("""(function(){
    var allEls=document.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++){
        var t=allEls[i].textContent?.trim()||'';
        if(t==='设立登记'&&allEls[i].offsetParent!==null&&allEls[i].children.length===0){
            var el=allEls[i];
            var current=el;
            for(var d=0;d<15&&current;d++){
                var comp=current.__vue__;
                if(comp&&typeof comp.toBanLi==='function'){
                    // 找cardlist中设立登记对应的数据
                    var cardlist=comp.$data?.cardlist||comp.$data?.allList||[];
                    var targetCard=null;
                    for(var j=0;j<cardlist.length;j++){
                        var name=cardlist[j].name||cardlist[j].busiName||cardlist[j].title||'';
                        if(name.includes('设立登记')||name.includes('经营主体登记')){
                            targetCard=cardlist[j];break;
                        }
                    }
                    try{
                        comp.toBanLi(targetCard||{name:'设立登记',code:'07',busiType:'07'});
                        return{called:true,depth:d,cardFound:!!targetCard,cardData:JSON.stringify(targetCard)?.substring(0,100)||'none'};
                    }catch(e){
                        return{error:e.message,depth:d};
                    }
                }
                current=current.parentElement;
            }
            return{error:'no_toBanLi'};
        }
    }
    return{error:'not_found'};
})()""")
print(f"  result: {result}")
time.sleep(5)

# Step 4: 检查API调用和页面变化
print("\nStep 4: 检查结果")
api_logs = ev("window.__api_logs||[]")
for l in (api_logs or []):
    url = l.get('url','')
    print(f"  API: {l.get('method','')} {url.split('?')[0].split('/').pop()} status={l.get('status')} resp={l.get('response','')[:80]}")

page = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"  hash={page.get('hash','') if page else '?'} forms={page.get('formCount',0) if page else 0}")

# Step 5: 如果到了企业开办专区或名称选择页
if page and ('enterprise' in page.get('hash','') or 'without-name' in page.get('hash','') or 'select' in page.get('hash','')):
    print("\nStep 5: 继续导航")
    
    if 'enterprise' in page.get('hash',''):
        # 点击开始办理
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(5)
        page2 = ev("({hash:location.hash})")
        print(f"  hash2={page2.get('hash','') if page2 else '?'}")
    
    # 在名称选择页
    # 分析without-name/select-prise组件
    comp = ev("""(function(){
        var app=document.getElementById('app');var vm=app?.__vue__;
        function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
        var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
        if(!wn)return{error:'no_comp'};
        var methods=Object.keys(wn.$options?.methods||{});
        var dataKeys=Object.keys(wn.$data||{});
        return{
            compName:wn.$options?.name||'',
            methods:methods,
            dataKeys:dataKeys,
            priseListLen:wn.$data?.priseList?.length||0,
            busiDataListLen:wn.$data?.busiDataList?.length||0,
            nameId:wn.$data?.nameId||'',
            isOther:wn.$data?.isOther||false,
            form:JSON.stringify(wn.$data?.form)?.substring(0,100)||'',
            hash:location.hash
        };
    })()""")
    print(f"  comp: {comp.get('compName','') if comp else '?'} methods={comp.get('methods',[]) if comp else []}")
    print(f"  priseList={comp.get('priseListLen',0) if comp else 0} busiDataList={comp.get('busiDataListLen',0) if comp else 0}")
    print(f"  nameId={comp.get('nameId','') if comp else ''} isOther={comp.get('isOther') if comp else ''}")
    
    # 调用getData获取名称列表
    if comp and comp.get('priseListLen',0) == 0 and comp.get('busiDataListLen',0) == 0:
        print("  调用getData获取列表...")
        ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
            if(wn&&typeof wn.getData==='function')wn.getData();
        })()""")
        time.sleep(3)
        
        api_logs2 = ev("window.__api_logs||[]")
        new_apis = [l for l in (api_logs2 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs or [])]]
        for l in new_apis:
            print(f"  NEW API: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')} resp={l.get('response','')[:100]}")
        
        # 检查列表
        comp2 = ev("""(function(){
            var app=document.getElementById('app');var vm=app?.__vue__;
            function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
            var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
            if(!wn)return null;
            var pl=wn.$data?.priseList||wn.$data?.busiDataList||[];
            return{len:pl.length,first:pl.length>0?JSON.stringify(pl[0]).substring(0,150):''};
        })()""")
        print(f"  list: len={comp2.get('len',0) if comp2 else 0} first={comp2.get('first','') if comp2 else ''}")
        
        # 如果有列表项，选择第一个
        if comp2 and comp2.get('len',0) > 0:
            print("  选择第一个列表项...")
            ev("""(function(){
                var rows=document.querySelectorAll('.el-table__row,tr[class*="row"]');
                for(var i=0;i<rows.length;i++){
                    if(rows[i].offsetParent!==null){
                        rows[i].click();
                        rows[i].dispatchEvent(new Event('click',{bubbles:true}));
                        return;
                    }
                }
            })()""")
            time.sleep(2)
            
            # 检查nameId
            comp3 = ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                return{nameId:wn?.$data?.nameId||'',hash:location.hash};
            })()""")
            print(f"  comp3: nameId={comp3.get('nameId','') if comp3 else ''}")
            
            if comp3 and comp3.get('nameId'):
                nid = comp3['nameId']
                print(f"  ✅ nameId={nid}，调用startSheli")
                ev(f"""(function(){{
                    var app=document.getElementById('app');var vm=app?.__vue__;
                    function findComp(vm,name,d){{if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
                    var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                    if(wn&&typeof wn.startSheli==='function')wn.startSheli({{nameId:'{nid}'}});
                }})()""")
                time.sleep(5)
            else:
                # 尝试点击"开始办理"按钮
                print("  点击开始办理按钮...")
                ev("""(function(){
                    var btns=document.querySelectorAll('button,.el-button');
                    for(var i=0;i<btns.length;i++){
                        var t=btns[i].textContent?.trim()||'';
                        if((t.includes('开始办理')||t.includes('下一步')||t.includes('确定'))&&btns[i].offsetParent!==null){
                            btns[i].click();return;
                        }
                    }
                })()""")
                time.sleep(3)
        else:
            # 没有列表项，尝试"其他来源名称"
            print("  无列表项，使用其他来源名称...")
            ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var wn=findComp(vm,'without-name',0)||findComp(vm,'select-prise',0);
                if(wn){
                    if(typeof wn.toOther==='function')wn.toOther();
                    else if('isOther' in wn.$data)wn.$set(wn.$data,'isOther',true);
                    wn.$forceUpdate();
                }
            })()""")
            time.sleep(2)
            
            # 填写
            ev("""(function(){
                var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
                var inputs=document.querySelectorAll('.el-form-item .el-input__inner');
                for(var i=0;i<inputs.length;i++){
                    var ph=inputs[i].placeholder||'';
                    if(ph.includes('企业名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                    if(ph.includes('保留单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}
                }
            })()""")
            time.sleep(1)
            
            # 设置form
            ev("""(function(){
                var app=document.getElementById('app');var vm=app?.__vue__;
                function findComp(vm,name,d){if(d>10)return null;if(vm.$options?.name===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var sp=findComp(vm,'select-prise',0);
                if(sp&&sp.$data?.form){sp.$set(sp.$data.form,'name','广西智信数据科技有限公司');sp.$set(sp.$data.form,'numbers','GX2024001');sp.$forceUpdate()}
            })()""")
            time.sleep(1)
            
            # 点击选择已有名称
            ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('选择已有名称')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
            time.sleep(3)
            
            # 检查API
            api_logs3 = ev("window.__api_logs||[]")
            new_apis3 = [l for l in (api_logs3 or []) if l.get('url','') not in [x.get('url','') for x in (api_logs2 or [])]]
            for l in new_apis3:
                print(f"  API3: {l.get('method','')} {l.get('url','').split('?')[0].split('/').pop()} status={l.get('status')} resp={l.get('response','')[:100]}")

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

# 检查动态路由
routes = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;var router=vm?.$router;var routes=router?.options?.routes||[];
    function findRoutes(rs,prefix){var r=[];for(var i=0;i<rs.length;i++){var p=prefix+rs[i].path;r.push(p);if(rs[i].children)r=r.concat(findRoutes(rs[i].children,p+'/'))}return r}
    var all=findRoutes(routes,'');var flow=all.filter(function(r){return r.includes('flow')||r.includes('namenotice')});
    return{total:all.length,flow:flow};
})()""")
print(f"  routes: total={routes.get('total',0)} flow={routes.get('flow',[])}")

if fc and fc.get('formCount',0) > 10:
    print("✅ 表单已加载！")
    log("430.表单加载成功", {"hash":fc.get('hash'),"formCount":fc.get('formCount',0)})
else:
    log("430.表单未加载", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0,"flowRoutes":routes.get('flow',[])})

ws.close()
print("✅ 完成")
