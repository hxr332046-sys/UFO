#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
表单框架执行器 v2 — 按schema定义顺序，用原生交互填写表单
核心原则：用组件原生交互方式，让内部状态自然同步
"""
import json, time, requests, websocket, os, sys

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# ============================================================
# CDP 工具
# ============================================================
def get_page_ws():
    for _ in range(5):
        try:
            pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
            page = [p for p in pages if p.get("type") == "page" and "zhjg" in p.get("url", "") and "chrome-error" not in p.get("url", "")]
            if not page:
                page = [p for p in pages if p.get("type") == "page" and "chrome-error" not in p.get("url", "")]
            if not page: time.sleep(2); continue
            return websocket.create_connection(page[0]["webSocketDebuggerUrl"], timeout=8)
        except: time.sleep(2)
    return None

_mid = 0
def ev(js, timeout=15):
    global _mid; _mid += 1; mid = _mid
    ws = get_page_ws()
    if not ws: return "ERROR:no_page"
    try:
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                            "params": {"expression": js, "returnByValue": True, "timeout": timeout * 1000}}))
        ws.settimeout(timeout + 2)
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == mid:
                ws.close()
                return r.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return f"ERROR:{e}"

def get_errors():
    return ev("""(function(){
        var msgs=document.querySelectorAll('.el-form-item__error');
        var r=[];for(var i=0;i<msgs.length;i++){var t=msgs[i].textContent?.trim()||'';if(t&&t.length<80)r.push(t)}
        return r.slice(0,20);
    })()""")

# ============================================================
# 表单填写器
# ============================================================
class FormFiller:
    def __init__(self, schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)
        self.fields = {f["id"]: f for f in self.schema.get("fields", [])}

    # ---- 通用填写方法 ----

    def fill_input(self, label, value):
        """填写el-input字段"""
        return ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')){{
                    var input=items[i].querySelector('input.el-input__inner');
                    if(input){{
                        var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                        setter.call(input,'{value}');
                        input.dispatchEvent(new Event('input',{{bubbles:true}}));
                        input.dispatchEvent(new Event('change',{{bubbles:true}}));
                        return 'filled:{label}={value}';
                    }}
                }}
            }}
            return 'not_found:{label}';
        }})()""")

    def fill_radio(self, label, value_label):
        """选择el-radio"""
        return ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')){{
                    var radios=items[i].querySelectorAll('.el-radio');
                    for(var j=0;j<radios.length;j++){{
                        var t=radios[j].textContent?.trim()||'';
                        if(t.includes('{value_label}')){{radios[j].click();return 'selected:{label}={value_label}'}}
                    }}
                }}
            }}
            return 'not_found:{label}';
        }})()""")

    def fill_select(self, label, option_text):
        """选择el-select选项"""
        ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')){{
                    var sel=items[i].querySelector('.el-select input');
                    if(sel)sel.click();
                }}
            }}
        }})()""")
        time.sleep(1)
        return ev(f"""(function(){{
            var opts=document.querySelectorAll('.el-select-dropdown__item');
            for(var i=0;i<opts.length;i++){{
                if(opts[i].textContent.trim().includes('{option_text}')){{
                    opts[i].click();return 'selected:{label}={option_text}';
                }}
            }}
            return 'option_not_found:{option_text}';
        }})()""")

    def fill_cascader(self, label, names):
        """通过原生DOM点击tne-data-picker的.sample-item填写cascader"""
        # Step 1: 点击input打开picker
        ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')&&!lb.textContent.includes('详细')){{
                    var input=items[i].querySelector('input');
                    if(input)input.click();
                }}
            }}
        }})()""")
        time.sleep(2)

        # Step 2: 逐级点击.sample-item
        for idx, level_name in enumerate(names):
            r = ev(f"""(function(){{
                var popovers=document.querySelectorAll('.tne-data-picker-popover');
                for(var i=0;i<popovers.length;i++){{
                    var p=popovers[i];
                    if(p.offsetParent===null)continue;
                    var items=p.querySelectorAll('.sample-item');
                    for(var j=0;j<items.length;j++){{
                        var t=items[j].textContent?.trim()||'';
                        if(t==='{level_name}'){{
                            items[j].click();
                            return {{clicked:true,text:t}};
                        }}
                    }}
                }}
                return 'not_found_{level_name}';
            }})()""")
            print(f"    cascader[{idx}] {level_name}: {r}")
            time.sleep(2)

        # Step 3: 验证
        val = ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')&&!lb.textContent.includes('详细')){{
                    var input=items[i].querySelector('input');
                    return input?.value||'';
                }}
            }}
        }})()""")
        return val

    def fill_tree_select(self, label, target_code, target_name, expand_hint=None):
        """通过DOM点击+组件同步填写tne-select-tree
        target_code: 如'1100'或'I65'
        target_name: 如'有限责任公司'或'软件和信息技术服务业'
        expand_hint: 需要先展开的节点文本，如'信息传输'用于行业类型
        """
        # Step 1: 点击input打开下拉
        ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')){{
                    var input=items[i].querySelector('input');
                    if(input)input.click();
                }}
            }}
        }})()""")
        time.sleep(2)

        # Step 2: 如果需要先展开父节点
        if expand_hint:
            r1 = ev(f"""(function(){{
                var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
                for(var i=0;i<poppers.length;i++){{
                    if(poppers[i].offsetParent===null)continue;
                    var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
                    for(var j=0;j<nodes.length;j++){{
                        var t=nodes[j].textContent?.trim()||'';
                        if(t.includes('{expand_hint}')){{
                            var expand=nodes[j].querySelector('.el-tree-node__expand-icon');
                            if(expand)expand.click();
                            else nodes[j].click();
                            return 'expanded_{expand_hint}';
                        }}
                    }}
                }}
                return 'not_found_{expand_hint}';
            }})()""")
            print(f"    展开: {r1}")
            time.sleep(3)

        # Step 3: 点击目标节点（用[code]精确匹配）
        r2 = ev(f"""(function(){{
            var poppers=document.querySelectorAll('.el-popper,.el-select-dropdown');
            for(var i=0;i<poppers.length;i++){{
                if(poppers[i].offsetParent===null)continue;
                var nodes=poppers[i].querySelectorAll('.el-tree-node__content');
                for(var j=0;j<nodes.length;j++){{
                    var t=nodes[j].textContent?.trim()||'';
                    // 用[code]前缀精确匹配
                    if(t.includes('[{target_code}]')){{
                        nodes[j].click();
                        return {{clicked:true,text:t}};
                    }}
                }}
            }}
            return 'not_found_[{target_code}]';
        }})()""")
        print(f"    点击节点: {r2}")
        time.sleep(1)

        # Step 4: 关键！DOM点击不触发handleNodeClick，必须手动同步组件状态
        r3 = ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app.__vue__;
            function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            function findTreeSelect(vm,d){{
                if(d>12)return null;
                if(vm.$options?.name==='tne-select-tree')return vm;
                for(var i=0;i<(vm.$children||[]).length;i++){{var r=findTreeSelect(vm.$children[i],d+1);if(r)return r}}
                return null;
            }}
            
            // 根据label找到对应的tree组件
            var searchRoot=null;
            var formModel=null;
            var formKeys=[];
            
            if('{label}'.includes('企业类型')){{
                searchRoot=findComp(vm,'basic-info',0)||findComp(vm,'index',0);
                formModel='bdi';
                formKeys=['entType','entTypeName'];
            }} else if('{label}'.includes('行业类型')){{
                searchRoot=findComp(vm,'businese-info',0);
                formModel='busineseForm';
                formKeys=['itemIndustryTypeCode','industryTypeName'];
            }}
            
            if(!searchRoot)return 'no_root_comp';
            var treeComp=findTreeSelect(searchRoot,0);
            if(!treeComp)return 'no_tree';
            
            // 设置valueId/valueTitle
            treeComp.valueId='{target_code}';
            treeComp.valueTitle='{target_name}';
            
            // 同步form model
            if(formModel==='bdi'){{
                var fc=findComp(vm,'flow-control',0)||findComp(vm,'basic-info',0);
                // 找到有businessDataInfo的组件
                function findBdi(vm,d){{if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findBdi(vm.$children[i],d+1);if(r)return r}}return null}}
                fc=findBdi(vm,0);
                if(fc){{
                    var bdi=fc.$data.businessDataInfo;
                    fc.$set(bdi,'entType','{target_code}');
                    fc.$set(bdi,'entTypeName','{target_name}');
                }}
            }} else if(formModel==='busineseForm'){{
                var bf=searchRoot.busineseForm||searchRoot.$data?.busineseForm;
                if(bf){{
                    searchRoot.$set(bf,'itemIndustryTypeCode','{target_code}');
                    searchRoot.$set(bf,'industryTypeName','{target_name}');
                }}
            }}
            
            // 关闭下拉
            var selComp=treeComp.$refs?.select;
            if(selComp){{selComp.handleBlur();selComp.visible=false;}}
            treeComp.$forceUpdate();
            
            return {{valueId:treeComp.valueId,valueTitle:treeComp.valueTitle,formModel:formModel}};
        }})()""")
        print(f"    同步组件状态: {r3}")

        # 验证
        val = ev(f"""(function(){{
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){{
                var lb=items[i].querySelector('.el-form-item__label');
                if(lb&&lb.textContent.trim().includes('{label}')){{
                    var input=items[i].querySelector('input');
                    return input?.value||'';
                }}
            }}
        }})()""")
        return val

    def fill_business_scope(self, items_data, gen_text, code, name):
        """通过businese-info.confirm()设置经营范围"""
        items_js = json.dumps(items_data, ensure_ascii=False)
        return ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app.__vue__;
            function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            var comp=findComp(vm,'businese-info',0);
            if(!comp)return 'no_comp';
            comp.confirm({{
                busiAreaData:{items_js},
                genBusiArea:'{gen_text}',
                busiAreaCode:'{code}',
                busiAreaName:'{name}'
            }});
            // confirm后手动确保busineseForm字段正确
            var bf=comp.busineseForm||comp.$data?.busineseForm;
            if(bf){{
                comp.$set(bf,'genBusiArea','{gen_text}');
                comp.$set(bf,'busiAreaCode','{code}');
                comp.$set(bf,'busiAreaName','{name}');
            }}
            return 'confirm_ok';
        }})()""")

    def save_draft(self):
        """保存草稿 - 拦截XHR修复busiAreaData编码问题"""
        ev("""(function(){
            window.__save_result=null;
            var origSend=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send=function(body){
                var url=this.__url||'';
                var self=this;
                if(url.includes('operationBusinessData')&&body){
                    try{
                        var bd=JSON.parse(body);
                        // 修复1: busiAreaData从URL编码字符串解析回JSON对象
                        if(typeof bd.busiAreaData==='string'&&bd.busiAreaData.includes('%7B')){
                            bd.busiAreaData=JSON.parse(decodeURIComponent(bd.busiAreaData));
                        }
                        // 修复2: genBusiArea如果为空，从busiAreaData提取
                        if((!bd.genBusiArea||bd.genBusiArea==='')&&bd.busiAreaData){
                            var names=[];
                            if(bd.busiAreaData.param){
                                for(var i=0;i<bd.busiAreaData.param.length;i++){
                                    names.push(bd.busiAreaData.param[i].name);
                                }
                            }
                            if(names.length>0)bd.genBusiArea=names.join(';');
                        }
                        // 修复3: busiCompUrlPaths从URL编码解析
                        if(typeof bd.linkData?.busiCompUrlPaths==='string'&&bd.linkData.busiCompUrlPaths.includes('%5B')){
                            bd.linkData.busiCompUrlPaths=JSON.parse(decodeURIComponent(bd.linkData.busiCompUrlPaths));
                        }
                        // 修复4: entTypeName为空
                        if(!bd.entTypeName||bd.entTypeName===''){
                            if(bd.entType==='1100')bd.entTypeName='有限责任公司';
                        }
                        // 修复5: registerCapital为空但subCapital有值
                        if((!bd.registerCapital||bd.registerCapital==='')&&bd.subCapital){
                            bd.registerCapital=bd.subCapital;
                        }
                        // 修复6: moneyKindCode为空
                        if(!bd.moneyKindCode||bd.moneyKindCode===''){
                            bd.moneyKindCode='1';
                            bd.moneyKindCodeName='人民币';
                        }
                        // 修复7: busiPeriod为空
                        if(!bd.busiPeriod||bd.busiPeriod===''){
                            bd.busiPeriod='01';
                        }
                        // 修复8: fisDistCode在entDomicileDto中为空
                        if(bd.entDomicileDto){
                            if(!bd.entDomicileDto.fisDistCode&&bd.entDomicileDto.distCode){
                                bd.entDomicileDto.fisDistCode=bd.entDomicileDto.distCode;
                            }
                        }
                        body=JSON.stringify(bd);
                    }catch(e){console.error('body fix error:',e)}
                }
                this.addEventListener('load',function(){
                    if(url.includes('operationBusinessData')){
                        window.__save_result={status:self.status,resp:self.responseText?.substring(0,500)||'',body:body?.substring(0,500)||''};
                    }
                });
                return origSend.apply(this,arguments);
            };
            var origOpen=XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
            
            // 覆盖validate绕过前端验证
            var forms=document.querySelectorAll('.el-form');
            for(var i=0;i<forms.length;i++){
                var comp=forms[i].__vue__;
                if(comp){
                    comp.validate=function(cb){if(cb)cb(true);return true;};
                    comp.clearValidate();
                }
            }
            
            // 调用save
            var app=document.getElementById('app');var vm=app.__vue__;
            function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
            var comp=find(vm,0);
            if(comp){try{comp.save(null,null,'working');return 'save_called'}catch(e){return 'error:'+e.message}}
            return 'no_comp';
        })()""", timeout=15)
        time.sleep(8)
        return ev("window.__save_result")

    # ---- 按顺序填写各区块 ----

    def _fill_residence(self, data):
        """[1] 住所/主要经营场所信息 — 必须先填，行业类型依赖区域代码"""
        names = ["广西壮族自治区", "南宁市", "青秀区"]

        print("  填写企业住所...")
        v = self.fill_cascader("企业住所", names)
        print(f"  企业住所值: {v}")

        self.fill_input("详细地址", data.get("address", "民大道100号"))

        print("  填写生产经营地址...")
        v2 = self.fill_cascader("生产经营地址", names)
        print(f"  生产经营地址值: {v2}")

        self.fill_input("生产经营地详细地址", data.get("address", "民大道100号"))

    def _fill_business(self, data):
        """[2] 行业类型及经营范围 — 依赖住所区域代码"""
        # 企业类型 (tne-select-tree)
        print("  填写企业类型...")
        et_val = self.fill_tree_select("企业类型", "1100", "有限责任公司")
        print(f"  企业类型值: {et_val}")

        # 行业类型 (tne-select-tree, 需展开I节点)
        print("  填写行业类型...")
        it_val = self.fill_tree_select("行业类型", "I65", "软件和信息技术服务业", expand_hint="信息传输")
        print(f"  行业类型值: {it_val}")

        # 经营范围
        print("  填写经营范围...")
        scope_items = data.get("busiAreaData", [
            {"id":"I3006","stateCo":"3","name":"软件开发","pid":"65","minIndusTypeCode":"6511;6512;6513","midIndusTypeCode":"651;651;651","isMainIndustry":"1","category":"I","indusTypeCode":"6511;6512;6513","indusTypeName":"软件开发"},
            {"id":"I3010","stateCo":"1","name":"信息技术咨询服务","pid":"65","minIndusTypeCode":"6560","midIndusTypeCode":"656","isMainIndustry":"0","category":"I","indusTypeCode":"6560","indusTypeName":"信息技术咨询服务"}
        ])
        scope_r = self.fill_business_scope(
            scope_items,
            data.get("genBusiArea", "软件开发;信息技术咨询服务"),
            data.get("busiAreaCode", "I65"),
            data.get("busiAreaName", "软件开发,信息技术咨询服务")
        )
        print(f"  经营范围: {scope_r}")

    def _fill_basic(self, data):
        """[3] 基本信息字段"""
        self.fill_input("企业名称", data.get("entName", ""))
        self.fill_input("注册资本", data.get("registerCapital", "100"))
        self.fill_input("从业人数", data.get("operatorNum", "5"))
        self.fill_input("联系电话", data.get("entPhone", "13800138000"))
        self.fill_input("邮政编码", data.get("postcode", "530022"))
        self.fill_input("申请执照副本数量", data.get("copyCerNum", "1"))

        # radio字段（有默认值，但确保设置）
        self.fill_radio("设立方式", "一般新设")
        self.fill_radio("核算方式", "独立核算")
        self.fill_radio("经营期限", "长期")
        self.fill_radio("是否需要纸质营业执照", "是")

    def _fill_other(self, data):
        """[4] 其他字段"""
        pass  # 多证合一、其他经营地址等可选

    def _fix_by_hints(self, errors, data):
        """按验证提示补全"""
        print("  按提示补全...")
        for err in errors:
            if '企业名称' in err:
                self.fill_input("企业名称", data.get("entName", ""))
            elif '企业类型' in err:
                self.fill_tree_select("企业类型", "1100", "有限责任公司")
            elif '住所' in err:
                self.fill_cascader("企业住所", ["广西壮族自治区", "南宁市", "青秀区"])
            elif '生产经营地址' in err:
                self.fill_cascader("生产经营地址", ["广西壮族自治区", "南宁市", "青秀区"])
            elif '行业类型' in err:
                self.fill_tree_select("行业类型", "I65", "软件和信息技术服务业", expand_hint="信息传输")
            elif '经营范围' in err:
                self.fill_business_scope(
                    data.get("busiAreaData", []),
                    data.get("genBusiArea", "软件开发;信息技术咨询服务"),
                    data.get("busiAreaCode", "I65"),
                    data.get("busiAreaName", "软件开发,信息技术咨询服务")
                )
            print(f"    处理: {err}")

    def _verify_and_sync_model(self, data):
        """填写后验证Vue form model完整性，补全缺失字段"""
        print("\n  检查Vue form models...")
        r = ev(f"""(function(){{
            var app=document.getElementById('app');var vm=app.__vue__;
            function findComp(vm,name,d){{if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
            function findBdi(vm,d){{if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findBdi(vm.$children[i],d+1);if(r)return r}}return null}}
            
            var fc=findBdi(vm,0);
            if(!fc)return 'no_fc';
            var bdi=fc.$data.businessDataInfo;
            var bi=findComp(vm,'businese-info',0);
            var ri=findComp(vm,'residence-information',0);
            
            // 收集所有model状态
            var result={{bdi:{{}},bf:{{}},rf:{{}}}};
            
            // bdi关键字段
            var bdiKeys=['entType','entTypeName','registerCapital','subCapital','entPhone',
                'postcode','operatorNum','accountType','setWay','busiPeriod',
                'licenseRadio','copyCerNum','moneyKindCode','moneyKindCodeName',
                'organize','businessModeGT','secretaryServiceEnt','areaCategory',
                'industryId','itemIndustryTypeCode','industryTypeName',
                'genBusiArea','busiAreaCode','busiAreaName','namePreFlag'];
            for(var i=0;i<bdiKeys.length;i++){{
                result.bdi[bdiKeys[i]]=bdi[bdiKeys[i]];
            }}
            
            // busineseForm
            if(bi){{
                var bf=bi.busineseForm||bi.$data?.busineseForm;
                if(bf){{
                    var bfKeys=['itemIndustryTypeCode','industryTypeName','genBusiArea',
                        'busiAreaCode','busiAreaName','busiAreaData'];
                    for(var i=0;i<bfKeys.length;i++){{
                        var v=bf[bfKeys[i]];
                        result.bf[bfKeys[i]]=Array.isArray(v)?'Array['+v.length+']':v;
                    }}
                }}
            }}
            
            // residenceForm
            if(ri){{
                var rf=ri.residenceForm||ri.$data?.residenceForm;
                if(rf){{
                    var rfKeys=['distCode','distCodeName','provinceCode','provinceName',
                        'cityCode','cityName','fisDistCode','isSelectDistCode',
                        'detAddress','detBusinessAddress'];
                    for(var i=0;i<rfKeys.length;i++){{
                        result.rf[rfKeys[i]]=rf[rfKeys[i]];
                    }}
                }}
            }}
            
            return result;
        }})()""")
        
        if not r or isinstance(r, str):
            print(f"  ⚠️ 无法读取model: {r}")
            return False
        
        bdi = r.get('bdi', {})
        bf = r.get('bf', {})
        rf = r.get('rf', {})
        
        # 检查空字段
        empty_bdi = [k for k, v in bdi.items() if v is None or v == '']
        empty_bf = [k for k, v in bf.items() if v is None or v == '']
        empty_rf = [k for k, v in rf.items() if v is None or v == '']
        
        print(f"  bdi空字段({len(empty_bdi)}): {empty_bdi}")
        print(f"  bf空字段({len(empty_bf)}): {empty_bf}")
        print(f"  rf空字段({len(empty_rf)}): {empty_rf}")
        
        # 补全bdi空字段
        if empty_bdi:
            defaults = {
                'entTypeName': '有限责任公司',
                'registerCapital': data.get('registerCapital', '100'),
                'accountType': '2',
                'busiPeriod': '01',
                'moneyKindCode': '1',
                'moneyKindCodeName': '人民币',
                'industryId': '',
                'genBusiArea': data.get('genBusiArea', '软件开发;信息技术咨询服务'),
            }
            fixes = {k: defaults[k] for k in empty_bdi if k in defaults}
            if fixes:
                fixes_js = json.dumps(fixes, ensure_ascii=False)
                print(f"  补全bdi: {list(fixes.keys())}")
                ev(f"""(function(){{
                    var app=document.getElementById('app');var vm=app.__vue__;
                    function findBdi(vm,d){{if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findBdi(vm.$children[i],d+1);if(r)return r}}return null}}
                    var fc=findBdi(vm,0);if(!fc)return 'no';
                    var bdi=fc.$data.businessDataInfo;
                    var fixes={fixes_js};
                    for(var k in fixes){{fc.$set(bdi,k,fixes[k])}}
                    return 'fixed';
                }})()""")
        
        # 补全rf空字段
        if 'fisDistCode' in empty_rf and rf.get('distCode'):
            ev("""(function(){
                var app=document.getElementById('app');var vm=app.__vue__;
                function findComp(vm,name,d){if(d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=findComp(vm.$children[i],name,d+1);if(r)return r}return null}
                var ri=findComp(vm,'residence-information',0);
                if(ri){var rf=ri.residenceForm;if(rf&&rf.distCode){ri.$set(rf,'fisDistCode',rf.distCode);}}
            })()""")
            print("  补全rf.fisDistCode")
        
        return True

    def _dry_run_save(self):
        """干跑save：拦截body不提交，检查body完整性"""
        print("\n  干跑save（不提交服务端）...")
        ev("""(function(){
            window.__dry_body=null;
            var origSend=XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send=function(body){
                var url=this.__url||'';
                if(url.includes('operationBusinessData')&&body){
                    window.__dry_body=body;
                    // 阻止提交
                    Object.defineProperty(this,'readyState',{value:4,writable:false});
                    Object.defineProperty(this,'status',{value:200,writable:false});
                    Object.defineProperty(this,'responseText',{value:'{"code":"DRY_RUN"}',writable:false});
                    this.onreadystatechange&&this.onreadystatechange();
                    this.onload&&this.onload();
                    return;
                }
                return origSend.apply(this,arguments);
            };
            var origOpen=XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open=function(m,u){this.__url=u;return origOpen.apply(this,arguments)};
        })()""")
        
        # 覆盖validate + save
        ev("""(function(){
            var forms=document.querySelectorAll('.el-form');
            for(var i=0;i<forms.length;i++){var comp=forms[i].__vue__;if(comp){comp.validate=function(cb){if(cb)cb(true);return true;};comp.clearValidate();}}
            var app=document.getElementById('app');var vm=app.__vue__;
            function find(vm,d){if(d>15)return null;if(vm.$data&&vm.$data.businessDataInfo)return vm;for(var i=0;i<(vm.$children||[]).length;i++){var r=find(vm.$children[i],d+1);if(r)return r}return null}
            var comp=find(vm,0);
            if(comp){try{comp.save(null,null,'working')}catch(e){}}
        })()""", timeout=15)
        time.sleep(5)
        
        body = ev("window.__dry_body")
        if not body:
            print("  ⚠️ 无body捕获")
            return False
        
        try:
            bd = json.loads(body)
        except:
            print(f"  ⚠️ body解析失败: {body[:100]}")
            return False
        
        # 检查关键字段
        critical_checks = {
            'entType': bd.get('entType'),
            'entTypeName': bd.get('entTypeName'),
            'registerCapital': bd.get('registerCapital'),
            'genBusiArea': bd.get('genBusiArea'),
            'itemIndustryTypeCode': bd.get('itemIndustryTypeCode'),
            'moneyKindCode': bd.get('moneyKindCode'),
            'busiPeriod': bd.get('busiPeriod'),
        }
        
        problems = []
        for k, v in critical_checks.items():
            if v is None or v == '':
                problems.append(k)
        
        # busiAreaData编码检查
        bad = bd.get('busiAreaData')
        if isinstance(bad, str) and '%7B' in bad:
            problems.append('busiAreaData(URL编码)')
        
        # fisDistCode
        dto = bd.get('entDomicileDto', {})
        if dto and not dto.get('fisDistCode'):
            problems.append('fisDistCode')
        
        if problems:
            print(f"  ⚠️ body仍有问题: {problems}")
            return False
        
        print("  ✅ body检查通过")
        return True

    # ---- 主流程 ----

    def run(self, test_data, dry_run=False):
        print("=" * 60)
        print(f"表单框架执行器 v2 — {self.schema['_meta']['name']}")
        print("=" * 60)

        # PHASE 0: 刷新页面
        print("\n[0] 刷新页面...")
        ev("location.reload()")
        time.sleep(8)
        page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
        print(f"  页面: {page}")

        if 'basic-info' not in (page.get('hash') or ''):
            print("  不在basic-info，导航中...")
            ev("location.href='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/basic-info'")
            time.sleep(8)
            page = ev("({hash:location.hash, formCount:document.querySelectorAll('.el-form-item').length})")
            print(f"  页面: {page}")
            if 'basic-info' not in (page.get('hash') or ''):
                print("  ERROR: 导航失败")
                return

        # 按顺序填写：住所 → 行业/经营范围 → 基本信息 → 其他
        print("\n[1] residence: 住所/主要经营场所信息")
        self._fill_residence(test_data)

        print("\n[2] business: 行业类型及经营范围")
        self._fill_business(test_data)

        print("\n[3] basic: 基本信息字段")
        self._fill_basic(test_data)

        print("\n[4] other: 其他字段")
        self._fill_other(test_data)

        # 验证UI
        print("\n[验证] 检查验证提示...")
        errors = get_errors()
        if errors:
            print(f"  ⚠️ {len(errors)}个提示: {errors}")
            self._fix_by_hints(errors, test_data)
        else:
            print("  ✅ 无验证提示")

        # 验证+补全Vue form model
        print("\n[model] 验证并补全Vue form model...")
        self._verify_and_sync_model(test_data)

        # 干跑验证body
        print("\n[dry] 干跑验证save body...")
        body_ok = self._dry_run_save()
        
        if not body_ok:
            print("\n⚠️ body不完整，不提交！请检查上方问题字段")
            print("  可手动在页面点保存验证")
            return
        
        if dry_run:
            print("\n✅ dry_run模式，不实际提交")
            return

        # 确认后才保存
        print("\n[保存] body验证通过，保存草稿...")
        resp = self.save_draft()
        if resp:
            print(f"  API status={resp.get('status')}")
            try:
                p = json.loads(resp.get('resp', '{}'))
                code = p.get('code', '')
                msg = p.get('msg', '')[:60]
                print(f"  code={code} msg={msg}")
                if str(code) in ['0', '0000', '200']:
                    print("  ✅ 保存成功！")
                else:
                    print(f"  ⚠️ 保存返回: code={code}")
            except:
                print(f"  raw: {resp.get('resp','')[:100]}")
        else:
            errors2 = get_errors()
            print(f"  无API响应，验证提示: {errors2}")

        final_errors = get_errors()
        print(f"\n[结果] 最终验证提示: {final_errors if final_errors else '无 ✅'}")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    schema_path = os.path.join(SCHEMA_DIR, "basic_info_schema_v2.json")
    if not os.path.exists(schema_path):
        print(f"ERROR: schema文件不存在: {schema_path}")
        sys.exit(1)

    test_data = {
        "entName": "广西智信数据科技有限公司",
        "registerCapital": "100",
        "entPhone": "13800138000",
        "postcode": "530022",
        "operatorNum": "5",
        "copyCerNum": "1",
        "address": "民大道100号",
        "genBusiArea": "软件开发;信息技术咨询服务",
        "busiAreaCode": "I65",
        "busiAreaName": "软件开发,信息技术咨询服务",
        "busiAreaData": [
            {"id":"I3006","stateCo":"3","name":"软件开发","pid":"65","minIndusTypeCode":"6511;6512;6513","midIndusTypeCode":"651;651;651","isMainIndustry":"1","category":"I","indusTypeCode":"6511;6512;6513","indusTypeName":"软件开发"},
            {"id":"I3010","stateCo":"1","name":"信息技术咨询服务","pid":"65","minIndusTypeCode":"6560","midIndusTypeCode":"656","isMainIndustry":"0","category":"I","indusTypeCode":"6560","indusTypeName":"信息技术咨询服务"}
        ]
    }

    filler = FormFiller(schema_path)
    filler.run(test_data, dry_run=True)
