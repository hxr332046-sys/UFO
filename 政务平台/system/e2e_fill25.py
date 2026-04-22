#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复: 从业人数+businessAddress+busiAreaData格式"""
import json, time, requests, websocket

def ev(js, timeout=10):
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
# Step 1: 修复从业人数 (operatorNum)
# ============================================================
print("Step 1: 从业人数")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'regist-info',0);
    if(!ri)return;
    var form=ri.registForm||ri.$data?.registForm;
    if(!form)return;
    ri.$set(form,'operatorNum','5');
    ri.$forceUpdate();
}})()""")

# 同步DOM
ev("""(function(){
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var items=document.querySelectorAll('.el-form-item');
    for(var i=0;i<items.length;i++){
        var label=items[i].querySelector('.el-form-item__label')?.textContent?.trim()||'';
        var input=items[i].querySelector('input');
        if(!input)continue;
        if(label.includes('从业人数')){s.call(input,'5');input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
})()""")

# ============================================================
# Step 2: 修复businessAddress
# ============================================================
print("\nStep 2: businessAddress")
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var ri=findComp(vm,'residence-information',0);
    if(!ri)return;
    var form=ri.residenceForm||ri.$data?.residenceForm;
    if(!form)return;
    ri.$set(form,'businessAddress','广西壮族自治区/南宁市/青秀区');
    ri.$set(form,'regionCode','450103');
    ri.$set(form,'regionName','青秀区');
    ri.$forceUpdate();
}})()""")

# ============================================================
# Step 3: 获取正确的busiAreaData格式
# ============================================================
print("\nStep 3: busiAreaData格式")

# 先检查当前businese-info的busiAreaData
current_ba = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'businese-info',0);
    if(!bi)return{{error:'no_bi'}};
    var form=bi.busineseForm||{{}};
    var data=form.busiAreaData||[];
    return{{
        len:data.length,
        sample:data.length>0?JSON.stringify(data[0]).substring(0,200):'empty',
        genBusiArea:form.genBusiArea?.substring(0,30)||'',
        busiAreaCode:form.busiAreaCode||''
    }};
}})()""")
print(f"  当前busiAreaData: {current_ba}")

# 尝试通过tni-business-range获取searchList
# 先init
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return;
    if(typeof tbr.init==='function')tbr.init();
    else if(typeof tbr.initOptions==='function')tbr.initOptions();
}})()""")
time.sleep(4)

# 搜索
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return;
    var si=tbr.$refs?.searchInput;
    if(si){{
        var inputEl=si.$el?.querySelector('input');
        if(inputEl){{
            var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(inputEl,'软件开发');
            inputEl.dispatchEvent(new Event('input',{{bubbles:true}}));
        }}
    }}
}})()""")
time.sleep(4)

# 获取searchList
search_items = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var tbr=findComp(vm,'tni-business-range',0);
    if(!tbr)return[];
    var sl=tbr.searchList||tbr.$data?.searchList||[];
    var items=[];
    for(var i=0;i<sl.length;i++){{
        var name=sl[i].name||'';
        if(name==='软件开发'||name==='信息技术咨询服务'||name.includes('数据处理和存储'))
            items.push(JSON.parse(JSON.stringify(sl[i])));
    }}
    if(items.length===0){{
        var al=tbr.allBusinessList||tbr.$data?.allBusinessList||[];
        for(var i=0;i<al.length;i++){{
            var cat=al[i];
            if(cat.id==='I'&&cat.list){{
                for(var j=0;j<cat.list.length;j++){{
                    if(cat.list[j].id==='65'){{
                        var sub65=cat.list[j];
                        var children=sub65.children||sub65.list||[];
                        for(var k=0;k<children.length;k++){{
                            var ch=children[k];
                            if(ch.name==='软件开发'||ch.name==='信息技术咨询服务')items.push(JSON.parse(JSON.stringify(ch)));
                            var deep=ch.children||ch.list||[];
                            for(var l=0;l<deep.length;l++){{
                                if(deep[l].name==='软件开发'||deep[l].name==='信息技术咨询服务')items.push(JSON.parse(JSON.stringify(deep[l])));
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    return items;
}})()""", timeout=12)

print(f"  searchList: {len(search_items) if isinstance(search_items,list) else search_items}项")
if isinstance(search_items, list) and len(search_items) > 0:
    for it in search_items[:3]:
        print(f"    {json.dumps(it, ensure_ascii=False)[:100]}")
    # 用searchList格式confirm
    search_items[0]['isMainIndustry'] = '1'
    search_items[0]['stateCo'] = '3'
    for i in range(1, len(search_items)):
        search_items[i]['isMainIndustry'] = '0'
        if search_items[i].get('stateCo') != '3': search_items[i]['stateCo'] = '1'
    names = ';'.join([it.get('name','') for it in search_items])
    confirm_data = {'busiAreaData': search_items, 'genBusiArea': names, 'busiAreaCode': 'I65', 'busiAreaName': names}
    confirm_json = json.dumps(confirm_data, ensure_ascii=False)
    confirm_js = '(function(){var vm=document.getElementById("app").__vue__;function findComp(vm,name,d){if(d>20)return null;var n=vm.$options&&vm.$options.name||"";if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var bi=findComp(vm,"businese-info",0);if(!bi)return;bi.confirm(' + confirm_json + ');})()'
    ev(confirm_js)
    print(f"  confirm(searchList格式): {len(search_items)}项")
else:
    print("  searchList为空，尝试getIndurstyBusinessList")
    # 通过行业分类获取
    ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var tbr=findComp(vm,'tni-business-range',0);
        if(!tbr)return;
        if(typeof tbr.getIndurstyBusinessList==='function'){{
            tbr.getIndurstyBusinessList('I');
        }}
    }})()""")
    time.sleep(4)
    
    # 重新获取
    search_items2 = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var tbr=findComp(vm,'tni-business-range',0);
        if(!tbr)return[];
        var sl=tbr.searchList||tbr.$data?.searchList||[];
        var items=[];
        for(var i=0;i<sl.length;i++){{
            var name=sl[i].name||'';
            if(name==='软件开发'||name==='信息技术咨询服务')
                items.push(JSON.parse(JSON.stringify(sl[i])));
        }}
        return items;
    }})()""", timeout=12)
    
    if isinstance(search_items2, list) and len(search_items2) > 0:
        print(f"  getIndurstyBusinessList后: {len(search_items2)}项")
        for it in search_items2[:3]:
            print(f"    {json.dumps(it, ensure_ascii=False)[:100]}")
        search_items2[0]['isMainIndustry'] = '1'
        search_items2[0]['stateCo'] = '3'
        for i in range(1, len(search_items2)):
            search_items2[i]['isMainIndustry'] = '0'
            if search_items2[i].get('stateCo') != '3': search_items2[i]['stateCo'] = '1'
        names = ';'.join([it.get('name','') for it in search_items2])
        confirm_data = {'busiAreaData': search_items2, 'genBusiArea': names, 'busiAreaCode': 'I65', 'busiAreaName': names}
        confirm_json = json.dumps(confirm_data, ensure_ascii=False)
        confirm_js = '(function(){var vm=document.getElementById("app").__vue__;function findComp(vm,name,d){if(d>20)return null;var n=vm.$options&&vm.$options.name||"";if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}var bi=findComp(vm,"businese-info",0);if(!bi)return;bi.confirm(' + confirm_json + ');})()'
        ev(confirm_js)
        print(f"  confirm: {len(search_items2)}项")
    else:
        print("  ❌ 仍无结果，用已知格式")
        # 拦截API请求查看保存payload
        ev("""(function(){
            window.__req_body=null;
            var origSend=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send=function(body){
                var url=this.__url||'';
                if(url.includes('operationBusinessData')){
                    window.__req_body=body?.substring(0,2000)||'';
                }
                return origSend.apply(this,arguments);
            };
        })()""")

# ============================================================
# Step 4: 验证
# ============================================================
print("\nStep 4: 验证")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,40))}return r})()""")
print(f"  验证错误: {errors}")

# ============================================================
# Step 5: 保存草稿
# ============================================================
print("\nStep 5: 保存草稿")

ev("""(function(){
    window.__save_result=null;
    var origSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(body){
        var url=this.__url||'';
        var self=this;
        this.addEventListener('load',function(){
            if(url.includes('operationBusinessData')){
                window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||''};
            }
        });
        return origSend.apply(this,arguments);
    };
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
})()""")

ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{return e.message}}
}})()""", timeout=15)
time.sleep(5)

resp = ev("window.__save_result")
if resp:
    print(f"  API status={resp.get('status')}")
    r = resp.get('resp','')
    if r:
        try:
            p = json.loads(r)
            code = p.get('code','')
            msg = p.get('msg','')[:60]
            print(f"  code={code} msg={msg}")
            if str(code) in ['0','0000']:
                print("  ✅ 保存成功！")
        except:
            print(f"  raw: {r[:150]}")
else:
    print("  无API响应")

# 检查请求payload
req_body = ev("window.__req_body")
if req_body:
    print(f"  请求body: {req_body[:300]}")

hash = ev("location.hash")
print(f"  路由: {hash}")

print("\n✅ 完成")
