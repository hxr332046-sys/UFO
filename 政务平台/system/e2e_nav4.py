#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到表单 - 通过Vue组件方法点击设立登记卡片"""
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

# 检查当前状态
state = ev("""(function(){
    var vm=document.getElementById('app')?.__vue__;
    return{hash:location.hash,hasVue:!!vm,text:(document.body?.innerText||'').substring(0,80)};
})()""")
print(f"当前: hash={state.get('hash','')} vue={state.get('hasVue')} text={state.get('text','')[:50] if state else 'None'}")

# 如果在404或首页，恢复Vuex
if state and state.get('hasVue'):
    print("恢复Vuex")
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
    time.sleep(2)

# 分析设立登记卡片的Vue组件
print("\n分析设立登记卡片")
card_analysis = ev("""(function(){
    var all=document.querySelectorAll('[class*="card"],[class*="service"],[class*="item"],[class*="swiper-slide"]');
    var cards=[];
    for(var i=0;i<all.length;i++){
        var t=all[i].textContent?.trim()||'';
        if(t.includes('设立登记')&&t.length<50&&all[i].offsetParent!==null){
            var comp=all[i].__vue__;
            var parentComp=all[i].parentElement?.__vue__;
            var compMethods=comp?Object.keys(comp.$options?.methods||{}):[];
            var parentMethods=parentComp?Object.keys(parentComp.$options?.methods||{}):[];
            var clickHandler=null;
            // 检查v-on:click绑定
            var vnode=comp?comp.$vnode:null;
            var on=vnode?.data?.on||{};
            var onKeys=Object.keys(on);
            
            cards.push({
                idx:i,
                text:t.substring(0,30),
                tag:all[i].tagName,
                class:(all[i].className||'').substring(0,40),
                hasVue:!!comp,
                compName:comp?comp.$options?.name||'':'',
                compMethods:compMethods.slice(0,10),
                parentName:parentComp?parentComp.$options?.name||'':'',
                parentMethods:parentMethods.slice(0,10),
                onKeys:onKeys,
                href:all[i].href||all[i].dataset?.href||''
            });
        }
    }
    return{count:cards.length,cards:cards};
})()""")
print(f"  卡片数: {card_analysis.get('count',0) if card_analysis else 0}")
for c in (card_analysis.get('cards',[]) if card_analysis else []):
    print(f"  [{c.get('idx')}] {c.get('text','')} tag={c.get('tag','')} vue={c.get('hasVue')} comp={c.get('compName','')}")
    print(f"    methods={c.get('compMethods',[])} parent={c.get('parentName','')} parentMethods={c.get('parentMethods',[])}")
    print(f"    onKeys={c.get('onKeys',[])} href={c.get('href','')}")

# 尝试通过Vue组件方法点击
print("\n尝试Vue组件方法点击")
for c in (card_analysis.get('cards',[]) if card_analysis else []):
    if c.get('hasVue'):
        idx = c.get('idx',0)
        result = ev(f"""(function(){{
            var all=document.querySelectorAll('[class*="card"],[class*="service"],[class*="item"],[class*="swiper-slide"]');
            var el=all[{idx}];
            var comp=el?.__vue__;
            if(!comp)return{{error:'no_comp'}};
            
            // 尝试调用handleClick或类似方法
            var methods=comp.$options?.methods||{{}};
            for(var m in methods){{
                if(m.includes('click')||m.includes('Click')||m.includes('handle')||m.includes('Handle')||m.includes('go')||m.includes('navigate')||m.includes('to')){{
                    try{{
                        methods[m].call(comp);
                        return{{called:m}};
                    }}catch(e){{
                        // 有些方法需要参数
                    }}
                }}
            }}
            
            // 尝试$emit click
            comp.$emit('click');
            comp.$emit('nativeClick');
            
            // 尝试parent的方法
            var parent=comp.$parent;
            if(parent){{
                var pmethods=parent.$options?.methods||{{}};
                for(var m in pmethods){{
                    if(m.includes('click')||m.includes('Click')||m.includes('handle')||m.includes('Handle')){{
                        try{{
                            pmethods[m].call(parent,comp);
                            return{{called:'parent.'+m}};
                        }}catch(e){{}}
                    }}
                }}
            }}
            
            return{{error:'no_click_method',compMethods:Object.keys(methods)}};
        }})()""")
        print(f"  result: {result}")
        time.sleep(3)
        
        # 检查是否导航了
        page = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
        print(f"  page: hash={page.get('hash','') if page else '?'} text={page.get('text','')[:40] if page else 'None'}")
        
        if page and page.get('hash','') != '#/index/page':
            print("  ✅ 导航成功！")
            break

# 如果仍在首页，尝试通过router直接导航
page = ev("({hash:location.hash})")
if page and page.get('hash','') == '#/index/page':
    print("\n尝试router导航到企业开办专区")
    ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/index/enterprise/enterprise-zone')})()""")
    time.sleep(3)
    
    page2 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
    print(f"  page2: hash={page2.get('hash','') if page2 else '?'} text={page2.get('text','')[:40] if page2 else 'None'}")
    
    if page2 and 'enterprise' in page2.get('hash',''):
        print("  在企业开办专区，点击开始办理")
        ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('开始办理')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
        time.sleep(3)
        
        page3 = ev("({hash:location.hash,text:(document.body?.innerText||'').substring(0,80)})")
        print(f"  page3: hash={page3.get('hash','') if page3 else '?'}")
        
        # 如果到了名称选择页
        if page3 and ('without-name' in page3.get('hash','') or 'select' in page3.get('hash','')):
            print("  名称选择页")
            ev("""(function(){var btns=document.querySelectorAll('button,.el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('其他来源')&&btns[i].offsetParent!==null){btns[i].click();return}}})()""")
            time.sleep(2)
            ev("""(function(){var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;var inputs=document.querySelectorAll('.el-dialog .el-input__inner');for(var i=0;i<inputs.length;i++){var ph=inputs[i].placeholder||'';if(ph.includes('名称')){s.call(inputs[i],'广西智信数据科技有限公司');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}if(ph.includes('单号')){s.call(inputs[i],'GX2024001');inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}}})()""")
            time.sleep(1)
            ev("""(function(){var btns=document.querySelectorAll('.el-dialog button,.el-dialog .el-button');for(var i=0;i<btns.length;i++){if(btns[i].textContent?.trim()?.includes('确定')||btns[i].textContent?.trim()?.includes('确认')){btns[i].click();return}}})()""")
            time.sleep(2)
            ev("""(function(){var app=document.getElementById('app');var vm=app?.__vue__;function findComp(vm,d){if(d>10)return null;if(vm.$options?.name==='select-prise')return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],d+1);if(r)return r}return null}var sp=findComp(vm,0);if(sp&&typeof sp.getHandleBusiness==='function')sp.getHandleBusiness()})()""")
            time.sleep(3)
            ev("""(function(){var vm=document.getElementById('app')?.__vue__;if(vm)vm.$router.push('/flow/base/basic-info')})()""")
            time.sleep(5)

# 最终验证
fc = ev("({hash:location.hash,formCount:document.querySelectorAll('.el-form-item').length})")
print(f"\n最终: hash={fc.get('hash','') if fc else '?'} forms={fc.get('formCount',0) if fc else 0}")

log("340.导航", {"hash":fc.get('hash','') if fc else 'None',"formCount":fc.get('formCount',0) if fc else 0})
ws.close()
print("✅ 导航完成")
