#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/night_autorun_to_yunbangban.json")
GUIDE_URL = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/name-register.html#/guide/base?busiType=02_4&entType=4540&marPrId=&marUniscId="


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "zhjg.scjdglj.gxzf.gov.cn:9087" in p.get("url", ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws_url, expr, timeout=90000):
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            ws.close()
            return msg.get("result", {}).get("result", {}).get("value")


def snap(ws_url):
    return ev(
        ws_url,
        r"""(function(){
          function find(vm,d){
            if(!vm||d>20) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='flow-control') return vm;
            for(var c of (vm.$children||[])){var r=find(c,d+1); if(r) return r;}
            return null;
          }
          var app=document.getElementById('app');
          var fc=(app&&app.__vue__)?find(app.__vue__,0):null;
          var fd=fc&&fc.params?fc.params.flowData:null;
          var txt=(document.body.innerText||'');
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
          return {
            href:location.href,hash:location.hash,
            hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,
            hasNameCheck:location.hash.indexOf('/flow/base/name-check-info')>=0,
            hasGuide:location.hash.indexOf('/guide/base')>=0,
            flowData:fd,errors:errs.slice(0,8),
            text:txt.slice(0,1200)
          };
        })()""",
    )


def act_guide(ws_url):
    return ev(
        ws_url,
        r"""(async function(){
          function clickBtn(kw){
            var b=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&!x.disabled&&((x.textContent||'').replace(/\s+/g,'').indexOf(kw.replace(/\s+/g,''))>=0));
            if(!b) return false;
            b.click(); return true;
          }
          function clickText(kw){
            var nodes=[...document.querySelectorAll('label,.tni-radio,.tni-radio__label,span,div')].filter(x=>x.offsetParent!==null);
            for(var n of nodes){
              var t=(n.textContent||'').replace(/\s+/g,' ').trim();
              if(t===kw||t.indexOf(kw)>=0){
                ['mousedown','mouseup','click'].forEach(function(tp){
                  n.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}));
                });
                return true;
              }
            }
            return false;
          }
          for(var i=0;i<3;i++){
            clickBtn('关 闭');
            clickBtn('确定');
            await new Promise(function(r){setTimeout(r,200);});
          }
          clickText('个人独资企业');
          clickText('未申请');
          // patch form directly
          function walk(vm,d){
            if(!vm||d>15) return null;
            var n=(vm.$options&&vm.$options.name)||'';
            if(n==='index'&&typeof vm.flowSave==='function') return vm;
            for(var c of (vm.$children||[])){var r=walk(c,d+1); if(r)return r;}
            return null;
          }
          var app=document.getElementById('app');
          var vm=app&&app.__vue__?walk(app.__vue__,0):null;
          if(vm&&vm.form){
            vm.$set(vm.form,'entType','4540');
            vm.$set(vm.form,'nameCode','0');
            vm.$set(vm.form,'havaAdress','0');
            vm.$set(vm.form,'distCode','450102');
            vm.$set(vm.form,'streetCode','450102');
            vm.$set(vm.form,'streetName','兴宁区');
            vm.$set(vm.form,'address','兴宁区');
            vm.$set(vm.form,'detAddress','容州大道88号');
          }
          var nextBtn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0);
          if(nextBtn&&nextBtn.__vue__&&nextBtn.__vue__.$listeners&&nextBtn.__vue__.$listeners.click){
            try{
              var p=nextBtn.__vue__.$listeners.click({type:'click',target:nextBtn,currentTarget:nextBtn});
              if(p&&typeof p.then==='function'){try{await p;}catch(e){}}
            }catch(e){}
          }else if(nextBtn){
            nextBtn.click();
          }
          await new Promise(function(r){setTimeout(r,500);});
          clickBtn('确定');
          return {ok:true};
        })()""",
    )


def act_namecheck(ws_url):
    return ev(
        ws_url,
        r"""(async function(){
          function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var c of (vm.$children||[])){var r=walk(c,d+1,pred);if(r)return r;}return null;}
          var app=document.getElementById('app'); var root=app&&app.__vue__;
          if(!root) return {ok:false,msg:'no_root'};
          var idx=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index'&&v.$parent&&v.$parent.$options&&v.$parent.$options.name==='name-check-info';});
          if(!idx) return {ok:false,msg:'no_namecheck_vm'};
          idx.formInfo=idx.formInfo||{};
          idx.$set(idx.formInfo,'areaCode','广西南宁');
          idx.$set(idx.formInfo,'namePre','广西南宁');
          idx.$set(idx.formInfo,'nameMark','桂柚百货');
          idx.$set(idx.formInfo,'allIndKeyWord','贸易');
          idx.$set(idx.formInfo,'showKeyWord','贸易');
          idx.$set(idx.formInfo,'industrySpecial','贸易');
          idx.$set(idx.formInfo,'industry','5299');
          idx.$set(idx.formInfo,'industryName','其他未列明零售业');
          idx.$set(idx.formInfo,'organize','802');
          idx.$set(idx.formInfo,'declarationMode','Y');
          idx.$set(idx.formInfo,'isCheckBox','Y');
          idx.$set(idx.formInfo,'name','广西南宁桂柚百货贸易（个人独资）');
          // sync visible inputs
          var setInput=function(kw,val){
            var items=document.querySelectorAll('.el-form-item');
            for(var i=0;i<items.length;i++){
              var lb=items[i].querySelector('.el-form-item__label');
              var t=(lb&&lb.textContent||'').replace(/\s+/g,' ').trim();
              if(t.indexOf(kw)>=0){
                var inp=items[i].querySelector('input.el-input__inner,textarea.el-textarea__inner');
                if(inp&&!inp.disabled){
                  var setter=Object.getOwnPropertyDescriptor((inp.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement).prototype,'value').set;
                  setter.call(inp,val); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
                  return true;
                }
              }
            }
            return false;
          };
          setInput('字号','桂柚百货');
          var btn=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('保存并下一步')>=0&&!x.disabled);
          if(btn) btn.click();
          await new Promise(function(r){setTimeout(r,400);});
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0&&!x.disabled);
          if(ok) ok.click();
          return {ok:true,flowData:(function(){function f(vm,d){if(!vm||d>20)return null;var n=(vm.$options&&vm.$options.name)||'';if(n==='flow-control')return vm;for(var c of (vm.$children||[])){var r=f(c,d+1);if(r)return r;}return null;}var fc=root?f(root,0):null;return fc&&fc.params?fc.params.flowData:null;})()};
        })()""",
    )


def main():
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "iterations": [], "result": "running"}
    for i in range(240):
        ws, url = pick_ws()
        if not ws:
            rec["iterations"].append({"i": i, "error": "no_ws"})
            time.sleep(5)
            continue
        if i == 0:
            ev(ws, f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", timeout=20000)
            time.sleep(4)
        s0 = snap(ws)
        row = {"i": i, "before": s0}
        if s0.get("hasYunbangban"):
            rec["result"] = "stopped_at_yunbangban"
            rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            rec["iterations"].append(row)
            OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Reached yunbangban. Saved: {OUT}")
            return
        if s0.get("hasGuide"):
            row["act"] = {"guide": act_guide(ws)}
            time.sleep(3)
        elif s0.get("hasNameCheck"):
            row["act"] = {"namecheck": act_namecheck(ws)}
            time.sleep(4)
        else:
            row["act"] = {"navigate": ev(ws, f"location.href={json.dumps(GUIDE_URL, ensure_ascii=False)}", timeout=20000)}
            time.sleep(4)
        row["after"] = snap(ws)
        rec["iterations"].append(row)
        if i % 5 == 0:
            rec["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    rec["result"] = "max_iterations_reached"
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Finished max iterations. Saved: {OUT}")


if __name__ == "__main__":
    main()
