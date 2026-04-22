#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""flow-control完整填表v2 - 修复企业名称+行业类型+经营范围"""
import json, time, requests, websocket

def ev(js, timeout=15):
    try:
        pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
        page = [p for p in pages if p.get("type")=="page" and "core.html" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "zhjg" in p.get("url","")]
        if not page:
            page = [p for p in pages if p.get("type")=="page" and "chrome-error" not in p.get("url","")]
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
# Step 1: 检查当前状态
# ============================================================
print("Step 1: 当前状态")
state = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bi=findComp(vm,'basic-info',0);
    var ri=findComp(vm,'regist-info',0);
    var busi=findComp(vm,'businese-info',0);
    var resi=findComp(vm,'residence-information',0);
    var br=findComp(vm,'tni-business-range',0);
    return {{
        fc:!!fc,bi:!!bi,ri:!!ri,busi:!!busi,resi:!!resi,br:!!br,
        fcCurComp:fc?fc.$data?.curCompUrlPath:'',
        busiAreaData:busi?(busi.busineseForm?.busiAreaData||'null'):'',
        searchListLen:br?(br.searchList||[]).length:0,
        entName:bi?(bi.basicForm?.entName||''):'',
        industryType:busi?(busi.busineseForm?.industryType||''):''
    }};
}})()""")
print(f"  {json.dumps(state, ensure_ascii=False)[:400] if isinstance(state,dict) else state}")

# ============================================================
# Step 2: 设置企业名称 (basic-info)
# ============================================================
print("\nStep 2: 设置企业名称")
name_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    if(!bi)return'no_bi';
    var f=bi.basicForm||bi.$data?.basicForm;
    if(!f)return'no_form';
    bi.$set(f,'entName','广西智信数据科技有限公司');
    bi.$set(f,'entNameEn','');
    bi.$set(f,'entShortName','智信数据');
    bi.$set(f,'entType','1100');
    bi.$set(f,'entTypeName','内资有限公司');
    bi.$set(f,'nameFlag','0');
    // DOM同步
    var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    var inputs=document.querySelectorAll('.el-form-item input');
    for(var i=0;i<inputs.length;i++){{
        var label=inputs[i].closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent?.trim()||'';
        if(label.includes('企业名称')){{
            s.call(inputs[i],'广西智信数据科技有限公司');
            inputs[i].dispatchEvent(new Event('input',{{bubbles:true}}));
        }}
    }}
    return {{set:true,entName:f.entName}};
}})()""")
print(f"  {name_result}")

# ============================================================
# Step 3: 行业类型 - 展开tree并选择I65
# ============================================================
print("\nStep 3: 行业类型I65")
# 方法：找到tree store，展开I节点，等待懒加载，然后选择I65
industry_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    
    // 查找tree组件
    var tree=null;
    function findTree(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='ElTree'||vm.$options?.name==='el-tree'){{
            tree=vm;return;
        }}
        for(var i=0;i<(vm.$children||[]).length;i++)findTree(vm.$children[i],d+1);
    }}
    findTree(busi,0);
    
    if(!tree)return'no_tree';
    var store=tree.store;
    var roots=store?.roots||[];
    
    // 找I节点（信息传输、软件和信息技术服务业）
    var iNode=null;
    for(var i=0;i<roots.length;i++){{
        if(roots[i].data?.code==='I'||roots[i].data?.label?.includes('信息传输')){{
            iNode=roots[i];
            break;
        }}
    }}
    if(!iNode)return'no_inode:roots='+roots.map(function(r){{return r.data?.code||r.data?.label||''}}).join(',');
    
    // 展开I节点
    iNode.expand();
    return {{expanded:'I',hasChildren:!!iNode.childNodes?.length,childrenLen:iNode.childNodes?.length||0}};
}})()""", timeout=15)
print(f"  展开I: {industry_result}")
time.sleep(4)  # 等待懒加载

# 选择I65
select_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var busi=findComp(vm,'businese-info',0);
    if(!busi)return'no_busi';
    
    var tree=null;
    function findTree(vm,d){{
        if(d>15)return;
        if(vm.$options?.name==='ElTree'||vm.$options?.name==='el-tree'){{tree=vm;return}}
        for(var i=0;i<(vm.$children||[]).length;i++)findTree(vm.$children[i],d+1);
    }}
    findTree(busi,0);
    if(!tree)return'no_tree';
    
    var store=tree.store;
    var roots=store?.roots||[];
    var iNode=null;
    for(var i=0;i<roots.length;i++){{
        if(roots[i].data?.code==='I'||roots[i].data?.label?.includes('信息传输')){{iNode=roots[i];break;}}
    }}
    if(!iNode)return'no_inode';
    
    // 找I65子节点
    var i65=null;
    var children=iNode.childNodes||[];
    for(var i=0;i<children.length;i++){{
        var c=children[i];
        if(c.data?.code==='65'||c.data?.value==='I65'||c.data?.label?.includes('软件')){{
            i65=c;break;
        }}
    }}
    if(!i65)return'no_i65:children='+children.slice(0,5).map(function(c){{return c.data?.code||c.data?.label||''}}).join(',');
    
    // 选择I65
    tree.$emit('node-click',i65.data,i65,i65);
    busi.$set(busi.busineseForm||busi.$data?.busineseForm,'industryType','I65');
    busi.$set(busi.busineseForm||busi.$data?.busineseForm,'industryTypeName','软件和信息技术服务业');
    
    return {{selected:true,code:i65.data?.code||i65.data?.value,label:i65.data?.label||''}};
}})()""")
print(f"  选择I65: {select_result}")

# 备选：直接用treeSelectChange
if isinstance(select_result, str) and 'no_' in select_result:
    print("  尝试treeSelectChange...")
    ev(f"""(function(){{var vm=document.getElementById('app').__vue__;{FC};var bi=findComp(vm,'businese-info',0);bi.treeSelectChange('I65')}})()""")
    time.sleep(3)

# ============================================================
# Step 4: 经营范围 - init + search + confirm
# ============================================================
print("\nStep 4: 经营范围")

# 先查看tni-business-range的完整方法
br_methods = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    var methods=Object.keys(br.$options?.methods||{{}});
    var data=br.$data||{{}};
    var dataKeys=Object.keys(data);
    var dataVals={{}};
    for(var i=0;i<dataKeys.length;i++){{
        var v=data[dataKeys[i]];
        if(v===null||v===undefined||v===''||v===false)continue;
        if(Array.isArray(v))dataVals[dataKeys[i]]='A['+v.length+']';
        else if(typeof v==='object')dataVals[dataKeys[i]]='O:'+Object.keys(v).length;
        else dataVals[dataKeys[i]]=v;
    }}
    return {{methods:methods,dataVals:dataVals,searchListLen:(br.searchList||[]).length}};
}})()""")
print(f"  br状态: {json.dumps(br_methods, ensure_ascii=False)[:300] if isinstance(br_methods,dict) else br_methods}")

# init
init_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    // 尝试各种初始化方法
    if(typeof br.init==='function')br.init();
    if(typeof br.loadData==='function')br.loadData();
    if(typeof br.searchListInit==='function')br.searchListInit();
    if(typeof br.getSearchList==='function')br.getSearchList();
    return {{called:true,searchListLen:(br.searchList||[]).length}};
}})()""", timeout=15)
print(f"  init: {init_result}")
time.sleep(3)

# 搜索
search_result = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    // 查看search方法
    var searchFn=br.search||br.$options?.methods?.search;
    if(!searchFn)return'no_search_method';
    br.search('软件开发');
    return {{searched:true,searchListLen:(br.searchList||[]).length}};
}})()""", timeout=15)
print(f"  search: {search_result}")
time.sleep(3)

# 检查searchList
sl_check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var br=findComp(vm,'tni-business-range',0);
    if(!br)return'no_br';
    var sl=br.searchList||[];
    return {{len:sl.length,first3:sl.slice(0,3).map(function(s){{return JSON.stringify(s).substring(0,60)}})}};
}})()""")
print(f"  searchList: {sl_check}")

# confirm
if isinstance(sl_check, dict) and sl_check.get('len', 0) > 0:
    confirm = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var br=findComp(vm,'tni-business-range',0);
        var bi=findComp(vm,'businese-info',0);
        if(!br||!bi)return'no_comp';
        var sl=br.searchList||[];
        var items=sl.slice(0,2);
        var names=items.map(function(x){{return x.name||x.indusTypeName||''}});
        bi.confirm({{
            busiAreaData:items,
            genBusiArea:names.join(';'),
            busiAreaCode:items[0].pid||'65',
            busiAreaName:names.join(';'),
            firstPlaceParams:{{firstPlace:'license',param:items}}
        }});
        return {{ok:true,gen:names.join(';')}};
    }})()""")
    print(f"  confirm: {confirm}")
else:
    # 手动构造经营范围数据
    print("  searchList为空，手动构造...")
    manual_data = [
        {"id":"I3006","stateCo":"1","name":"软件开发","pid":"65","minIndusTypeCode":"6511;6512;6513","midIndusTypeCode":"651;651;651","isMainIndustry":"0","category":"I","indusTypeCode":"6511;6512;6513","indusTypeName":"软件开发"},
        {"id":"I3010","stateCo":"1","name":"信息技术咨询服务","pid":"65","minIndusTypeCode":"6560","midIndusTypeCode":"656","isMainIndustry":"0","category":"I","indusTypeCode":"6560","indusTypeName":"信息技术咨询服务"}
    ]
    manual_json = json.dumps(manual_data, ensure_ascii=False)
    confirm = ev(f"""(function(){{
        var vm=document.getElementById('app').__vue__;
        {FC}
        var bi=findComp(vm,'businese-info',0);
        if(!bi)return'no_bi';
        var items={manual_json};
        var names=items.map(function(x){{return x.name}});
        bi.confirm({{
            busiAreaData:items,
            genBusiArea:names.join(';'),
            busiAreaCode:'65',
            busiAreaName:names.join(';'),
            firstPlaceParams:{{firstPlace:'license',param:items}}
        }});
        return {{ok:true,gen:names.join(';')}};
    }})()""")
    print(f"  manual confirm: {confirm}")

# ============================================================
# Step 5: 验证前端
# ============================================================
print("\nStep 5: 验证前端")
errors = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误: {errors}")

# 检查关键字段
check = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var bi=findComp(vm,'basic-info',0);
    var busi=findComp(vm,'businese-info',0);
    return {{
        entName:bi?(bi.basicForm?.entName||''):'',
        industryType:busi?(busi.busineseForm?.industryType||''):'',
        busiAreaDataLen:busi?(busi.busineseForm?.busiAreaData||[]).length:0,
        genBusiArea:busi?(busi.busineseForm?.genBusiArea||''):''
    }};
}})()""")
print(f"  关键字段: {json.dumps(check, ensure_ascii=False) if isinstance(check,dict) else check}")

# ============================================================
# Step 6: 拦截XHR + 保存
# ============================================================
print("\nStep 6: 拦截+保存")
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
# Step 7: 分析请求和响应
# ============================================================
print("\nStep 7: 分析")
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
            print(f"  ⚠️ busiAreaData是STRING! len={len(ba)}")
            print(f"     前80字符: {ba[:80]}")
            try:
                decoded = json.loads(ba)
                print(f"     JSON.parse后: {type(decoded).__name__}")
            except:
                print(f"     JSON.parse失败")
        elif isinstance(ba, list):
            print(f"  ✅ busiAreaData是ARRAY len={len(ba)}")
        print(f"  genBusiArea: {str(gba)[:50]}")
        
        with open(r'g:\UFO\政务平台\data\save_body_a0002.json', 'w', encoding='utf-8') as f:
            json.dump(bobj, f, ensure_ascii=False, indent=2)
        print(f"  已保存 ({len(bobj)} keys)")
    except:
        print(f"  body非JSON: {body[:200]}")
else:
    print(f"  无请求: {req}")

if isinstance(resp, dict):
    text = resp.get('text','')
    if text:
        try:
            p = json.loads(text)
            print(f"  API code={p.get('code','')} msg={str(p.get('msg',''))[:80]}")
            if str(p.get('code','')) in ['0','0000','200']:
                print("  ✅✅✅ 保存成功！✅✅✅")
            else:
                print(f"  ❌ 错误!")
                with open(r'g:\UFO\政务平台\data\save_resp_a0002.json', 'w', encoding='utf-8') as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)
        except:
            print(f"  raw: {text[:200]}")
else:
    print(f"  无响应: {resp}")

errors2 = ev("""(function(){var errs=document.querySelectorAll('.el-form-item__error');var r=[];for(var i=0;i<errs.length;i++){var t=errs[i].textContent?.trim()||'';if(t)r.push(t.substring(0,50))}return r})()""")
print(f"  验证错误(后): {errors2}")

print("\n✅ 完成")
