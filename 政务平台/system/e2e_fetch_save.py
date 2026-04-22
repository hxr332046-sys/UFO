#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接用fetch调API保存，绕过Vue save事件机制"""
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
# Step 1: 获取完整bdi + 各子组件form数据
# ============================================================
print("Step 1: 收集所有数据")

all_data = ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    var bdi=JSON.parse(JSON.stringify(fc.$data.businessDataInfo));
    
    // 合并regist-info form
    var ri=findComp(vm,'regist-info',0);
    if(ri){{
        var rform=ri.registForm||ri.$data?.registForm||{{}};
        var rk=Object.keys(rform);
        for(var i=0;i<rk.length;i++){{
            var k=rk[i];var v=rform[k];
            if(v!==null&&v!==undefined&&v!=='')bdi[k]=v;
        }}
    }}
    
    // 合并businese-info form
    var bi=findComp(vm,'businese-info',0);
    if(bi){{
        var bform=bi.busineseForm||{{}};
        var bk=Object.keys(bform);
        for(var i=0;i<bk.length;i++){{
            var k=bk[i];var v=bform[k];
            if(v!==null&&v!==undefined&&v!=='')bdi[k]=v;
        }}
    }}
    
    // 合并residence-information form
    var resi=findComp(vm,'residence-information',0);
    if(resi){{
        var rform2=resi.residenceForm||resi.$data?.residenceForm||{{}};
        var rk2=Object.keys(rform2);
        for(var i=0;i<rk2.length;i++){{
            var k=rk2[i];var v=rform2[k];
            if(v!==null&&v!==undefined&&v!=='')bdi[k]=v;
        }}
    }}
    
    // 清理不需要的字段
    delete bdi.currentLocationVo;
    delete bdi.busiComp;
    delete bdi.fieldList;
    delete bdi.flowData;
    delete bdi.jurisdiction;
    delete bdi.linkData;
    delete bdi.processVo;
    delete bdi.signInfo;
    
    // 确保关键字段
    bdi.operatorNum='5';
    bdi.empNum='5';
    bdi.distCode='450103';
    bdi.distCodeName='青秀区';
    bdi.fisDistCode='450103';
    bdi.address='广西壮族自治区/南宁市/青秀区';
    bdi.detAddress='民族大道100号';
    bdi.businessAddress='广西壮族自治区/南宁市/青秀区';
    bdi.detBusinessAddress='民族大道100号';
    bdi.regionCode='450103';
    bdi.regionName='青秀区';
    bdi.provinceCode='450000';
    bdi.isSelectDistCode='1';
    bdi.havaAdress='0';
    bdi.itemIndustryTypeCode='I65';
    bdi.industryTypeName='软件和信息技术服务业';
    bdi.busiAreaCode='I65';
    bdi.busiPeriod='01';
    bdi.entName='广西智信数据科技有限公司';
    bdi.name='广西智信数据科技有限公司';
    bdi.entType='1100';
    bdi.entTypeName='有限责任公司';
    bdi.registerCapital='100';
    bdi.shouldInvestWay='1';
    bdi.isBusinessRegMode='0';
    bdi.secretaryServiceEnt='0';
    bdi.namePreFlag='1';
    bdi.partnerNum='1';
    bdi.setWay='01';
    bdi.accountType='1';
    bdi.licenseRadio='0';
    bdi.copyCerNum='1';
    bdi.businessModeGT='10';
    bdi.organize='1';
    
    // busiAreaData - 用正确的firstPlace/param格式
    bdi.busiAreaData=JSON.stringify({{
        firstPlace:'license',
        param:[
            {{id:'I3006',stateCo:'3',name:'软件开发',pid:'65',minIndusTypeCode:'6511;6512;6513',midIndusTypeCode:'651;651;651',isMainIndustry:'1',category:'I',indusTypeCode:'6511;6512;6513',indusTypeName:'软件开发'}},
            {{id:'I3010',stateCo:'1',name:'信息技术咨询服务',pid:'65',minIndusTypeCode:'6560',midIndusTypeCode:'656',isMainIndustry:'0',category:'I',indusTypeCode:'6560',indusTypeName:'信息技术咨询服务'}}
        ]
    }});
    bdi.genBusiArea='软件开发;信息技术咨询服务';
    bdi.busiAreaName='软件开发;信息技术咨询服务';
    bdi.businessArea='许可经营项目：软件开发；信息技术咨询服务。（依法须经批准的项目，经相关部门批准后方可开展经营活动）';
    
    return JSON.stringify(bdi);
}})()""", timeout=15)

if isinstance(all_data, str) and all_data.startswith('{'):
    bdi_obj = json.loads(all_data)
    print(f"  合并后bdi: {len(bdi_obj)}个字段")
    # 检查关键字段
    for k in ['distCode','businessAddress','operatorNum','busiAreaData','busiAreaCode','itemIndustryTypeCode','entName']:
        v = bdi_obj.get(k, 'MISSING')
        if isinstance(v, str) and len(v) > 50:
            print(f"  {k}: {v[:50]}...")
        else:
            print(f"  {k}: {v}")
else:
    print(f"  ERROR: {all_data}")
    bdi_obj = None

# ============================================================
# Step 2: 获取API URL和token
# ============================================================
print("\nStep 2: 获取API信息")
api_info = ev("""(function(){
    var token=localStorage.getItem('top-token')||'';
    var auth=localStorage.getItem('Authorization')||'';
    // 找API base URL
    var baseUrl='';
    // 检查axios配置
    if(window.axios&&window.axios.defaults&&window.axios.defaults.baseURL){
        baseUrl=window.axios.defaults.baseURL;
    }
    return{token:token,auth:auth,baseUrl:baseUrl};
})()""")
print(f"  API info: token={api_info.get('token','')[:15]}... auth={api_info.get('auth','')[:15]}... base={api_info.get('baseUrl','')}")

# ============================================================
# Step 3: 先看之前保存请求的完整URL
# ============================================================
print("\nStep 3: 捕获保存请求URL")
ev("""(function(){
    window.__save_url=null;
    var origOpen=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(m,u){
        if(u.includes('operationBusinessData'))window.__save_url=u;
        return origOpen.apply(this,arguments);
    };
})()""")

# 触发一次save只为了获取URL
ev(f"""(function(){{
    var vm=document.getElementById('app').__vue__;
    {FC}
    var fc=findComp(vm,'flow-control',0);
    try{{fc.save(null,null,'working')}}catch(e){{}}
}})()""", timeout=10)
time.sleep(3)

save_url = ev("window.__save_url")
print(f"  保存URL: {save_url}")

# ============================================================
# Step 4: 直接fetch保存
# ============================================================
if bdi_obj and save_url:
    print("\nStep 4: fetch保存")
    
    # 构造请求 - 模仿Vue的请求格式
    save_js = f"""(function(){{
        var bdi={json.dumps(bdi_obj, ensure_ascii=False)};
        var token=localStorage.getItem('top-token')||'';
        var auth=localStorage.getItem('Authorization')||'';
        var url='{save_url}';
        
        return fetch(url,{{
            method:'POST',
            headers:{{
                'Content-Type':'application/json',
                'Authorization':auth,
                'top-token':token
            }},
            body:JSON.stringify(bdi)
        }}).then(function(r){{
            return r.text();
        }}).then(function(t){{
            return t.substring(0,500);
        }}).catch(function(e){{
            return 'FETCH_ERROR:'+e.message;
        }});
    }})()"""
    
    result = ev(save_js, timeout=20)
    print(f"  fetch结果: {result}")

print("\n✅ 完成")
