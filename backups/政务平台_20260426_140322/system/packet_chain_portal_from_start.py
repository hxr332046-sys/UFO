#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从头走：portal 全部服务 → 设立登记 →（如进入）企业专区/申报须知 → 自动点主按钮，
直到页面出现「云提交」或「云端提交」文案即停（不自动点提交）。
含 CDP 断线重连；每步可重装 XHR hook；结果写入 JSON（不含脱敏时请自行保管）。
"""
from __future__ import annotations

import base64
import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import websocket

_icpsp_path = Path(__file__).resolve().parent / "icpsp_entry.py"
_spec = importlib.util.spec_from_file_location("icpsp_entry", _icpsp_path)
_icpsp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_icpsp)
pick_icpsp_target_prefer_logged_portal = _icpsp.pick_icpsp_target_prefer_logged_portal

_catt_path = Path(__file__).resolve().parent / "cdp_attachment_upload.py"
_spec_catt = importlib.util.spec_from_file_location("cdp_attachment_upload", _catt_path)
_catt = importlib.util.module_from_spec(_spec_catt)
assert _spec_catt.loader is not None
_spec_catt.loader.exec_module(_catt)
load_assets_cfg = _catt.load_assets_cfg
try_upload_for_current_page = _catt.try_upload_for_current_page

ROOT = Path(__file__).resolve().parent.parent
OUT = Path("G:/UFO/政务平台/dashboard/data/records/packet_chain_portal_from_start.json")

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from gov_task_run_model import finalize_task_model, new_run_id  # noqa: E402

OUT_ITER_LATEST = Path("G:/UFO/政务平台/dashboard/data/records/establish_iterate_latest.json")
SHOT_DIR = Path("G:/UFO/政务平台/dashboard/data/records/packet_chain_shots")

_CDP_PORT_CACHE: Optional[int] = None


def _cdp_port() -> int:
    global _CDP_PORT_CACHE
    if _CDP_PORT_CACHE is not None:
        return _CDP_PORT_CACHE
    p = ROOT / "config" / "browser.json"
    with p.open(encoding="utf-8") as f:
        _CDP_PORT_CACHE = int(json.load(f)["cdp_port"])
    return _CDP_PORT_CACHE


def _in_name_register_spa(href: str) -> bool:
    """portal 查询里常有 fromProject=name-register，不能当作已进入 name-register 子应用。"""
    return "name-register.html" in href

# 与线上一致：全部服务 + name-register 回跳（declaration-instructions）
PORTAL_INDEX_PAGE = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=name-register&fromPage=%2Fnamenotice%2Fdeclaration-instructions"
)
# 从名称业务 guide/base 回到门户「全部服务」时的入口（与常见截图 URL 一致）
PORTAL_INDEX_PAGE_GUIDE_BASE = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/page?fromProject=name-register&fromPage=%2Fguide%2Fbase"
)
ENTERPRISE_ZONE = (
    "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html"
    "#/index/enterprise/enterprise-zone?fromProject=portal&fromPage=%2Findex%2Fpage"
    "&busiType=02_4&merge=Y"
)

HOOK_JS = r"""(function(){
  window.__ufo_cap = window.__ufo_cap || {installed:false,items:[]};
  function pushOne(x){ try{ x.ts=Date.now(); window.__ufo_cap.items.push(x);
    if(window.__ufo_cap.items.length>300) window.__ufo_cap.items.shift(); }catch(e){} }
  if(!window.__ufo_cap.installed){
    var XO=XMLHttpRequest.prototype.open, XS=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){ this.__ufo={m:m,u:u}; return XO.apply(this,arguments); };
    XMLHttpRequest.prototype.send=function(body){
      var self=this, u=(self.__ufo&&self.__ufo.u)||'';
      if(String(u).indexOf('/icpsp-api/')>=0){
        pushOne({t:'xhr',m:(self.__ufo&&self.__ufo.m)||'',u:u,body:String(body||'').slice(0,40000)});
        self.addEventListener('loadend',function(){
          pushOne({t:'xhr_end',u:u,status:self.status,resp:String(self.responseText||'').slice(0,40000)});
        });
      }
      return XS.apply(this,arguments);
    };
    var OF=window.fetch;
    if(typeof OF==='function'){
      window.fetch=function(input,init){
        try{
          var u=(typeof input==='string')?input:(input&&input.url)||'';
          if(String(u).indexOf('/icpsp-api/')>=0){
            var m=(init&&init.method)||'GET';
            var b=(init&&init.body)?String(init.body).slice(0,40000):'';
            pushOne({t:'fetch',m:m,u:u,body:b});
            return OF.apply(this,arguments).then(function(res){
              try{
                return res.clone().text().then(function(txt){
                  pushOne({t:'fetch_end',u:u,status:res.status,resp:String(txt||'').slice(0,40000)});
                  return res;
                });
              }catch(e){ return res; }
            });
          }
        }catch(e){}
        return OF.apply(this,arguments);
      };
    }
    window.__ufo_cap.installed=true;
  }
  window.__ufo_cap.items=[];
  return {ok:true};
})()"""


def pick_ws() -> Tuple[Optional[str], str, List[Dict[str, Any]]]:
    best, dbg = pick_icpsp_target_prefer_logged_portal(_cdp_port())
    if not best:
        return None, "", dbg
    return best.get("webSocketDebuggerUrl"), best.get("url") or "", dbg


def _is_socket_dead_exc(e: BaseException) -> bool:
    s = repr(e).lower()
    keys = (
        "10053",
        "10054",
        "connection aborted",
        "connection reset",
        "broken pipe",
        "websocket",
        "closed",
        "fin",
        "eof",
    )
    return any(k in s for k in keys)


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=25)
        self.ws.settimeout(2.0)
        self.i = 1

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 22):
        if params is None:
            params = {}
        cid = self.i
        self.i += 1
        self.ws.send(json.dumps({"id": cid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = json.loads(self.ws.recv())
            except Exception as e:
                if _is_socket_dead_exc(e):
                    raise
                continue
            if msg.get("id") == cid:
                return msg
        return {"error": {"message": f"timeout {method}"}}

    def ev(self, expr: str, timeout_ms: int = 120000):
        m = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
                "timeout": timeout_ms,
            },
            timeout=25,
        )
        return ((m.get("result") or {}).get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

    def screenshot_png_file(self, path: Path) -> bool:
        """CDP Page.captureScreenshot → PNG 文件（用于卡点留证）。"""
        self.call("Page.enable", {})
        msg = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        if msg.get("error"):
            return False
        data = (msg.get("result") or {}).get("data")
        if not isinstance(data, str) or not data:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))
        return True


# 读取可见报错、弹窗、通知（卡点诊断）
READ_BLOCKER_UI_JS = r"""(function(){
  function pick(sel, lim){
    return [...document.querySelectorAll(sel)].map(function(e){
      return (e.textContent||'').replace(/\s+/g,' ').trim();
    }).filter(Boolean).slice(0, lim);
  }
  var errs=pick('.el-form-item__error,.el-message--error .el-message__content,.el-message__content,.el-notification__content,.el-message-box__message,.el-alert__description,.el-result__subtitle', 35);
  var warns=pick('.el-message--warning .el-message__content,.el-alert--warning .el-alert__description', 12);
  var dlg=document.querySelector('.el-dialog__wrapper:not([style*="display: none"]) .el-dialog__body,.el-dialog__wrapper:not([style*="display:none"]) .el-dialog__body');
  var dlgTxt=dlg?((dlg.innerText||'').replace(/\s+/g,' ').trim().slice(0,900)):'';
  var mb=document.querySelector('.el-message-box__wrapper:not([style*="display: none"]) .el-message-box__message');
  var mbTxt=mb?((mb.innerText||'').replace(/\s+/g,' ').trim().slice(0,500)):'';
  return {
    href: location.href,
    hash: location.hash,
    errors: errs,
    warnings: warns,
    dialogBody: dlgTxt,
    messageBox: mbTxt,
    hasBlocking: errs.length>0 || !!mbTxt
  };
})()"""

# S08（guide/base）无法进入 core 时的一次性诊断：MessageBox、级联、主按钮
S08_EXIT_DIAGNOSTIC_JS = r"""(function(){
  function vis(sel){
    return [...document.querySelectorAll(sel)].filter(function(e){return e.offsetParent!==null;});
  }
  var boxes=[];
  [...document.querySelectorAll('.el-message-box__wrapper')].forEach(function(w){
    var st=w.getAttribute('style')||'';
    if(st.indexOf('display: none')>=0||st.indexOf('display:none')>=0) return;
    if(w.offsetParent===null) return;
    var t=(w.querySelector('.el-message-box__title')||{}).innerText||'';
    var m=(w.querySelector('.el-message-box__message')||{}).innerText||'';
    var btns=[...w.querySelectorAll('button')].map(function(b){return (b.textContent||'').trim();}).filter(Boolean);
    boxes.push({title:(t||'').replace(/\s+/g,' ').trim().slice(0,200), message:(m||'').replace(/\s+/g,' ').trim().slice(0,700), buttons:btns});
  });
  var errs=vis('.el-form-item__error').map(function(e){return (e.textContent||'').trim();}).filter(Boolean).slice(0,15);
  var cin=[];
  var casc=document.querySelectorAll('.el-cascader');
  for(var i=0;i<casc.length;i++){
    var inp=casc[i].querySelector('.el-input__inner');
    cin.push({
      idx:i,
      placeholder:(inp&&inp.getAttribute('placeholder'))||'',
      value:(inp&&inp.value)||'',
      inputVisible:!!(inp&&inp.offsetParent)
    });
  }
  var menuCount=vis('.el-cascader-menu').length;
  var prim=[...document.querySelectorAll('button.el-button--primary,.el-button.el-button--primary')].filter(function(b){
    return b.offsetParent&&!b.disabled;
  }).map(function(b){return (b.textContent||'').replace(/\s+/g,' ').trim().slice(0,48)}).filter(Boolean).slice(0,18);
  var nextLike=[...document.querySelectorAll('button,.el-button')].filter(function(b){
    if(!b.offsetParent||b.disabled) return false;
    var t=(b.textContent||'').replace(/\s+/g,' ').trim();
    return t.indexOf('下一步')>=0||t.indexOf('保存并下一步')>=0||t.indexOf('确定')>=0;
  }).map(function(b){return (b.textContent||'').replace(/\s+/g,' ').trim().slice(0,56)}).slice(0,12);
  return {
    href: location.href,
    hash: location.hash,
    title: (document.title||'').slice(0,120),
    messageBoxes: boxes,
    formErrors: errs,
    cascaderInputs: cin,
    cascaderVisibleMenus: menuCount,
    primaryLikeButtons: prim,
    nextOrConfirmButtons: nextLike
  };
})()"""

# 卡点恢复：点 MessageBox 确定、关 toast、关带「关闭」的按钮
CLICK_RECOVERY_STUCK_JS = r"""(function(){
  var log=[];
  var btns=[...document.querySelectorAll('.el-message-box__btns button,.el-message-box button')];
  btns.forEach(function(b){
    if(!b.offsetParent||b.disabled) return;
    var t=((b.textContent||'').replace(/\s+/g,'')||'').trim();
    if(t.indexOf('取消')>=0) return;
    if(t.indexOf('确定')>=0||t.indexOf('我知道了')>=0||t.indexOf('继续')>=0){ b.click(); log.push('msgbox:'+t.slice(0,20)); }
  });
  [...document.querySelectorAll('.el-notification__closeBtn,.el-message__closeBtn,.el-icon-close')].forEach(function(x){
    try{ if(x && x.offsetParent){ x.click(); log.push('close_toast'); } }catch(e){}
  });
  [...document.querySelectorAll('button,.el-button,span')].forEach(function(b){
    if(!b.offsetParent||b.disabled) return;
    var t=((b.textContent||'').replace(/\s+/g,'')||'').trim();
    if(t==='关闭'||t==='关关闭'||(t.length<=4&&t.indexOf('关闭')>=0)){
      b.click(); log.push('close_btn');
    }
  });
  return {ok:log.length>0, log:log};
})()"""

S08_STATE_PROBE_JS = r"""(function(){
  function visible(el){ return !!(el && el.offsetParent!==null); }
  function walk(vm,d,pred){
    if(!vm||d>20) return null;
    if(pred(vm)) return vm;
    var ch=vm.$children||[];
    for(var i=0;i<ch.length;i++){
      var r=walk(ch[i],d+1,pred);
      if(r) return r;
    }
    return null;
  }
  var txt=(document.body&&document.body.innerText)||'';
  var dialogs=[...document.querySelectorAll('.el-dialog__wrapper')].filter(function(w){ return visible(w); });
  var app=document.getElementById('app');
  var guideVm=app&&app.__vue__?walk(app.__vue__,0,function(v){
    var n=(v.$options&&v.$options.name)||'';
    return n==='index'&&typeof v.flowSave==='function';
  }):null;
  var picker=guideVm?walk(guideVm,0,function(v){ return (v.$options&&v.$options.name)==='tne-data-picker'; }):null;
  var form=guideVm&&guideVm.form&&typeof guideVm.form==='object'?guideVm.form:null;
  var dataInfo=guideVm&&guideVm.dataInfo&&typeof guideVm.dataInfo==='object'?guideVm.dataInfo:null;
  return {
    href: location.href,
    hash: location.hash,
    hasNamePrompt: txt.indexOf('请选择是否需要名称')>=0,
    hasQualificationPrompt: txt.indexOf('请确认您属于上述人员范围')>=0,
    dialogCount: dialogs.length,
    qDialogVisible: dialogs.some(function(w){ return (w.innerText||'').indexOf('请确认您属于上述人员范围')>=0; }),
    nDialogVisible: dialogs.some(function(w){ return (w.innerText||'').indexOf('请选择是否需要名称')>=0; }),
    ghostDialogState: (txt.indexOf('请选择是否需要名称')>=0 || txt.indexOf('请确认您属于上述人员范围')>=0) && dialogs.length===0,
    hookCount: ((window.__ufo_cap&&window.__ufo_cap.items)||[]).length,
    guideVmFound: !!guideVm,
    guideDataInfoCode: dataInfo ? (dataInfo.code||dataInfo.entType||dataInfo.value||null) : null,
    guideChoiceName: guideVm ? (guideVm.choiceName||'') : '',
    guideEntTypeCode: guideVm ? (guideVm.entTypeCode||'') : '',
    guideEntTypeRealy: guideVm ? (guideVm.entTypeRealy||'') : '',
    guideHasPicker: !!picker,
    guidePickerCheckValue: picker ? (picker.checkValue||null) : null,
    guideDistListLen: guideVm&&Array.isArray(guideVm.distList) ? guideVm.distList.length : 0,
    guideForm: form ? {
      entType: form.entType||'',
      nameCode: form.nameCode||'',
      isnameType: form.isnameType||'',
      choiceName: form.choiceName||'',
      havaAdress: form.havaAdress||'',
      distCode: form.distCode||'',
      streetCode: form.streetCode||'',
      streetName: form.streetName||'',
      address: form.address||'',
      detAddress: form.detAddress||''
    } : null,
    buttons:[...document.querySelectorAll('button,.el-button')].filter(function(b){return visible(b);}).map(function(b){
      return {text:(b.textContent||'').replace(/\s+/g,' ').trim().slice(0,48), disabled:!!b.disabled};
    }).slice(0,16)
  };
})()"""

# guide/base S08 v2：名称 MessageBox 优先、未办理预保留优先于未申请（避免误选已办理=旧 nameId）、再企业类型与大段提示关闭
GUIDE_BASE_AUTOFILL_V2 = r"""(function(){
  var log=[];
  function clickElContains(sel, sub, maxLen){
    var arr=[...document.querySelectorAll(sel)].filter(function(e){return e.offsetParent!==null;});
    for(var i=0;i<arr.length;i++){
      var e=arr[i];
      var t=(e.textContent||'').replace(/\s+/g,' ').trim();
      if(!t||t.length>(maxLen||56)) continue;
      if(t.indexOf(sub)>=0){
        e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
        return {ok:true,h:t.slice(0,80)};
      }
    }
    return {ok:false};
  }
  var wBox=document.querySelector('.el-message-box__wrapper:not([style*=\"display: none\"]):not([style*=\"display:none\"])');
  if(wBox){
    var msg=((wBox.querySelector('.el-message-box__message')||{}).innerText||'');
    if(msg.indexOf('名称')>=0&&(msg.indexOf('是否')>=0||msg.indexOf('需要')>=0||msg.indexOf('选择')>=0)){
      var okb=[...wBox.querySelectorAll('button')].find(function(b){
        return b.offsetParent&&!b.disabled&&((b.textContent||'').indexOf('确定')>=0)&&((b.textContent||'').indexOf('取消')<0);
      });
      if(okb){ okb.click(); log.push('msgbox_name_need_ok'); }
    }
  }
  var wBox2=document.querySelector('.el-message-box__wrapper:not([style*=\"display: none\"]):not([style*=\"display:none\"])');
  if(wBox2){
    var ik=[...wBox2.querySelectorAll('button,.el-button')].find(function(b){
      if(!b||!b.offsetParent||b.disabled) return false;
      var t=(b.textContent||'').replace(/\s+/g,'').trim();
      return (t.indexOf('我知道了')>=0||t==='知道了')&&t.indexOf('取消')<0;
    });
    if(ik){ ik.click(); log.push('msgbox_iknow'); }
  }
  var mb=[...document.querySelectorAll('.el-message-box__btns button,.el-message-box button')].find(function(b){
    if(!b||!b.offsetParent||b.disabled) return false;
    var t=(b.textContent||'').replace(/\s+/g,'');
    return t.indexOf('取消')<0&&t.indexOf('确定')>=0;
  });
  if(mb){ mb.click(); log.push('msgbox_ok'); }
  var wraps=document.querySelectorAll('.el-dialog__wrapper');
  for(var wi=0;wi<wraps.length;wi++){
    var w=wraps[wi];
    var st=(w.getAttribute('style')||'');
    if(st.indexOf('display: none')>=0||st.indexOf('display:none')>=0) continue;
    if(w.offsetParent===null) continue;
    var foot=w.querySelector('.el-dialog__footer');
    if(foot){
      var ack=[...foot.querySelectorAll('button,.el-button')].find(function(b){
        if(!b.offsetParent||b.disabled) return false;
        var t=((b.textContent||'').replace(/\s+/g,'')||'').trim();
        return (t.indexOf('我知道了')>=0||t.indexOf('我已知晓')>=0||t.indexOf('知晓')>=0||t==='确认'||(t.indexOf('继续')>=0&&t.indexOf('取消')<0))&&t.indexOf('取消')<0;
      });
      if(ack){ ack.click(); log.push('dialog_footer_ack'); break; }
    }
    var cls=[...w.querySelectorAll('button,.el-button,span')].find(function(b){
      var t=((b.textContent||'').replace(/\s+/g,'')||'').trim();
      return t.indexOf('关闭')>=0;
    });
    if(cls){ cls.click(); log.push('dialog_close'); break; }
  }
  var sel='label,span,div,li,a,.el-radio,.el-radio__label';
  var r0=clickElContains(sel,'未办理企业名称预保留',50);
  if(r0.ok){ log.push('name:未办理预保留'); }
  else {
    var r2a=clickElContains(sel,'未申请',26);
    if(r2a.ok) log.push('name:未申请');
  }
  var r1=clickElContains(sel,'内资有限公司',42); if(r1.ok) log.push('ent:内资有限公司');
  // 关键补强：若仍出现“请选择是否需要名称？”，再次显式点击“未申请”，并尽力写入 guide VM 的 nameCode/isnameType/choiceName
  try{
    var txt=(document.body&&document.body.innerText)||'';
    if(txt.indexOf('请选择是否需要名称')>=0){
      var r2b=clickElContains(sel,'未申请',40);
      if(r2b.ok) log.push('name:未申请_retry');
    }
  }catch(e){}
  try{
    function walk(vm,d,pred){
      if(!vm||d>22) return null;
      if(pred(vm)) return vm;
      var ch=vm.$children||[];
      for(var i=0;i<ch.length;i++){ var r=walk(ch[i],d+1,pred); if(r) return r; }
      return null;
    }
    var app=document.getElementById('app');
    var root=app&&app.__vue__;
    var guideVm=root?walk(root,0,function(v){
      var n=(v.$options&&v.$options.name)||'';
      return n==='index' && v.$route && String(v.$route.path||'').indexOf('/guide/base')>=0 && v.form;
    }):null;
    if(guideVm && guideVm.$set && guideVm.form){
      // 新设：未申请名称
      guideVm.$set(guideVm.form,'nameCode','0');
      guideVm.$set(guideVm.form,'isnameType','0');
      guideVm.$set(guideVm.form,'choiceName','0');
      // 有些实现把 choiceName 放在 vm 上
      try{ if(typeof guideVm.choiceName!=='undefined') guideVm.$set(guideVm,'choiceName','未申请'); }catch(_e){}
      log.push('vm_set_name_unapplied');
    }
  }catch(e){ log.push('vm_set_name_err'); }
  return {ok:true,log:log,r0:r0,r1:r1};
})()"""

# 多个住所/区划级联时，依次点击可见的 cascader 输入框以展开面板（S08 常见卡点）
CASCADE_OPEN_MULTI_JS = r"""(function(){
  var sel='.el-form .el-cascader .el-input__inner,.el-form-item .el-cascader .el-input__inner,.el-cascader .el-input__inner';
  var inps=[...document.querySelectorAll(sel)].filter(function(i){return i&&i.offsetParent!==null&&!i.disabled;});
  var clicked=[];
  for(var k=0;k<Math.min(inps.length,5);k++){
    try{
      inps[k].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
      inps[k].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
      clicked.push(k);
    }catch(e){}
  }
  return {ok:clicked.length>0,totalInputs:inps.length,clickedIdx:clicked};
})()"""

# S08 住所/区划常见为 el-select 或非 cascader：按 label/placeholder 点开下拉
S08_REGION_SELECT_PROBE_JS = r"""(function(){
  var log=[];
  var cand=[...document.querySelectorAll('.el-form-item .el-input__inner,.el-form-item input,.el-select .el-input__inner')];
  for(var i=0;i<cand.length;i++){
    var el=cand[i];
    if(!el||!el.offsetParent||el.disabled) continue;
    var ph=(el.getAttribute&&el.getAttribute('placeholder'))||'';
    var p=el.closest&&el.closest('.el-form-item');
    var lab='';
    if(p){ var lb=p.querySelector('.el-form-item__label'); if(lb) lab=(lb.textContent||'').trim(); }
    var u=(lab+' '+ph);
    if(u.indexOf('省')>=0||u.indexOf('市')>=0||u.indexOf('区')>=0||u.indexOf('县')>=0||u.indexOf('住所')>=0||u.indexOf('区划')>=0||u.indexOf('地址')>=0){
      el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
      log.push(u.replace(/\s+/g,' ').trim().slice(0,40));
      if(log.length>=4) break;
    }
  }
  return {ok:log.length>0,log:log,scanned:cand.length};
})()"""

CASCADE_OPEN_JS = r"""(function(){
  var i=document.querySelector('.el-form .el-cascader .el-input__inner')||document.querySelector('.el-cascader .el-input__inner');
  if(i){ i.click(); return {ok:true}; }
  return {ok:false};
})()"""

CASCADE_PICK_FIRST_VISIBLE_JS = r"""(function(){
  var lb=document.querySelector('.el-cascader-menu .el-cascader-node .el-cascader-node__label');
  if(!lb) return {ok:false};
  lb.click();
  return {ok:true,text:(lb.textContent||'').trim().slice(0,40)};
})()"""

# 住所下拉可能是 el-select / popper，不一定是 cascader menu
S08_PICK_FIRST_DROPDOWN_OPTION_JS = r"""(function(){
  var sels=[
    '.el-select-dropdown:not([style*=\"display: none\"]) .el-select-dropdown__item',
    '.el-popper:not([style*=\"display: none\"]) .el-select-dropdown__item',
    '.el-cascader-menu .el-cascader-node__label',
    '.el-cascader-menu .el-cascader-node',
    '.tne-data-picker-popover:not([style*=\"display: none\"]) .sample-item',
    '.tne-data-picker-popover:not([style*=\"display: none\"]) li',
    '.tne-data-picker-popover:not([style*=\"display: none\"]) [role=\"option\"]',
    '.el-picker-panel .el-date-table td.available',
    '[role=\"listbox\"] [role=\"option\"]'
  ];
  for(var si=0;si<sels.length;si++){
    var el=document.querySelector(sels[si]);
    if(el&&el.offsetParent&&!el.disabled){
      el.click();
      return {ok:true,mode:sels[si].slice(0,48),text:(el.textContent||'').replace(/\s+/g,' ').trim().slice(0,40)};
    }
  }
  return {ok:false};
})()"""

def s08_pick_dropdown_by_text_js(text: str) -> str:
    t = json.dumps(str(text or "").strip(), ensure_ascii=False)
    return (
        r"""(function(){
  function vis(e){ return e && e.offsetParent!==null && !e.disabled; }
  var want = """
        + t
        + r""";
  if(!want) return {ok:false,reason:'empty_want'};
  var sels=[
    '.tne-data-picker-popover:not([style*="display: none"]) .sample-item',
    '.tne-data-picker-popover:not([style*="display: none"]) li',
    '.tne-data-picker-popover:not([style*="display: none"]) [role="option"]',
    '.el-select-dropdown:not([style*="display: none"]) .el-select-dropdown__item',
    '.el-popper:not([style*="display: none"]) .el-select-dropdown__item',
    '.el-cascader-menu .el-cascader-node__label',
    '[role="listbox"] [role="option"]'
  ];
  for(var si=0;si<sels.length;si++){
    var els=[...document.querySelectorAll(sels[si])].filter(vis);
    for(var i=0;i<els.length;i++){
      var txt=(els[i].textContent||'').replace(/\s+/g,' ').trim();
      if(!txt) continue;
      if(txt===want || txt.indexOf(want)>=0){
        try{ els[i].click(); }catch(e){}
        return {ok:true,mode:sels[si].slice(0,48),hit:txt.slice(0,60)};
      }
    }
  }
  // 终极兜底：扫描可见 popover 内所有节点（适配非 sample-item 渲染）
  try{
    var pops=[...document.querySelectorAll('.tne-data-picker-popover')].filter(function(p){return p.offsetParent!==null;});
    if(pops.length){
      var best=null;
      var nodes=[...pops[0].querySelectorAll('*')].filter(function(e){
        if(!vis(e)) return false;
        var tx=(e.textContent||'').replace(/\s+/g,' ').trim();
        if(!tx) return false;
        return tx.indexOf(want)>=0 && tx.length<=30;
      });
      for(var k=0;k<nodes.length;k++){
        var tx=(nodes[k].textContent||'').replace(/\s+/g,' ').trim();
        if(!best || tx.length < best.tx.length){
          best={el:nodes[k], tx:tx};
        }
      }
      if(best){
        var el=best.el;
        var tgt=el.closest('li,.item,.sample-item,[role=option],.el-select-dropdown__item,.el-cascader-node')||el;
        try{ tgt.click(); }catch(e){ try{ el.click(); }catch(_e){} }
        return {ok:true,mode:'popover_scan',hit:best.tx.slice(0,60)};
      }
    }
  }catch(e){}
  return {ok:false,reason:'not_found',want:want};
})()"""
    )

TNE_DATA_PICKER_OPEN_JS = r"""(function(){
  function vis(e){ return e && e.offsetParent!==null && !e.disabled; }
  var cand=[
    '.tne-data-picker .el-input__inner',
    '.tne-data-picker input',
    '.tne-data-picker',
    '.tne-data-picker__input',
    '.tne-data-picker__text'
  ];
  var clicked=[];
  for(var si=0;si<cand.length;si++){
    var els=[...document.querySelectorAll(cand[si])].filter(vis);
    for(var i=0;i<Math.min(els.length,3);i++){
      try{
        els[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
        els[i].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
        clicked.push({sel:cand[si],idx:i});
      }catch(e){}
    }
    if(clicked.length) break;
  }
  var pop=[...document.querySelectorAll('.tne-data-picker-popover')].filter(function(p){return p.offsetParent!==null;}).length;
  return {ok:clicked.length>0,clicked:clicked,popperVisibleCount:pop};
})()"""

S08_GUIDE_FLOWSAVE_JS = r"""(async function(){
  function clone(v){ try{ return JSON.parse(JSON.stringify(v)); }catch(e){ return v; } }
  function walk(vm,d,pred){
    if(!vm||d>20) return null;
    if(pred(vm)) return vm;
    var ch=vm.$children||[];
    for(var i=0;i<ch.length;i++){
      var r=walk(ch[i],d+1,pred);
      if(r) return r;
    }
    return null;
  }
  function txt(el){ return ((el&&el.textContent)||'').replace(/\s+/g,'').trim(); }
  var app=document.getElementById('app');
  var vm=app&&app.__vue__?walk(app.__vue__,0,function(v){
    var n=(v.$options&&v.$options.name)||'';
    return n==='index'&&typeof v.flowSave==='function';
  }):null;
  if(!vm) return {ok:false,msg:'no_guide_vm',href:location.href,hash:location.hash};
  var q=(vm.$route&&vm.$route.query)||{};
  var u=clone(vm.form||{});
  var prompt='';
  if(vm.form&&vm.form.entType){
    if(vm.entTypeRealy==='fzjg'){
      u.registerCapital='';
      u.fzSign='Y';
      u.entType=vm.parentEntType;
      if(vm.companyInfo&&vm.companyInfo.uniScID){
        u.parentBusinessArea=vm.companyInfo.businessArea;
        u.parentBusinessEndDate=vm.companyInfo.businessEndDate;
        u.longTerm=vm.companyInfo.longTerm;
      }
    }else{
      u.fzSign='N';
      if(!vm.isForeignBranch){
        u.parentEntRegno='';
        u.parentEntName='';
      }
    }
  }else{
    prompt=vm.choiceName||'';
  }
  try{ delete u.parentEntType; }catch(e){}
  if(vm.form&&vm.form.nameCode){
    if(String(vm.form.nameCode)==='1'){
      u.distCode='';
      u.distCodeArr=[];
      u.address='';
      u.streetCode='';
      u.streetName='';
      if(vm.dataInfo&&vm.dataInfo.nameId){
        u.nameId=vm.dataInfo.nameId;
        u.entType=vm.dataInfo.entType;
      }else{
        prompt='未获取到企业名称信息！';
      }
    }else{
      try{ delete u.name; }catch(e){}
      try{ delete u.number; }catch(e){}
    }
  }else{
    prompt='inputSelectCompanyName_missing';
  }
  var validResult=null, validateErr=null;
  try{
    validResult=await new Promise(function(resolve){
      try{
        if(vm.$refs&&vm.$refs.form&&typeof vm.$refs.form.validate==='function'){
          vm.$refs.form.validate(function(ok){ resolve(ok); });
        }else{
          resolve(null);
        }
      }catch(e){
        resolve('validate_err:'+String(e));
      }
    });
  }catch(e){
    validateErr=String(e);
  }
  var apiRes=null, apiErr=null, apiCode='';
  var flowRet=null, flowErr=null;
  var jumpParams=null, jumped=false;
  if(!prompt&&validResult===true&&vm.$api&&vm.$api.guide&&typeof vm.$api.guide.checkEstablishName==='function'){
    var payload=clone(u)||{};
    payload.gainError='1';
    if(typeof q.establishType!=='undefined') payload.establishType=q.establishType;
    try{
      apiRes=await vm.$api.guide.checkEstablishName(payload);
      apiCode=String((apiRes&&apiRes.code)||'');
    }catch(e){
      apiErr=String(e);
      try{ apiRes={error:e,data:e&&e.data||null,response:e&&e.response||null}; }catch(_e){}
      try{ apiCode=String((e&&e.code)||((e&&e.response&&e.response.data&&e.response.data.code)||'')); }catch(_e){}
    }
    if(apiCode==='A0002'&&vm.$router&&typeof vm.$router.jump==='function'){
      jumpParams={
        entType:u.entType||q.entType||'',
        busiType:q.busiType||'02_4',
        extra:'guideData',
        vipChannel:typeof q.vipChannel==='undefined'?null:q.vipChannel,
        ywlbSign:q.ywlbSign||'',
        busiId:q.busiId||'',
        extraDto:JSON.stringify({extraDto:u})
      };
      try{
        vm.$router.jump({project:'core',path:'/flow/base',target:'_self',params:jumpParams});
        jumped=true;
      }catch(e){
        flowErr='manual_jump_err:'+String(e);
      }
    }
  }
  if(!jumped){
    try{
      flowRet=vm.flowSave();
      if(flowRet&&typeof flowRet.then==='function'){
        try{ flowRet=await flowRet; }catch(e){ flowErr=String(e); }
      }
    }catch(e){
      flowErr=String(e);
    }
    var ok=[...document.querySelectorAll('button,.el-button')].find(function(x){
      return x.offsetParent!==null&&!x.disabled&&txt(x).indexOf('确定')>=0;
    });
    if(ok) ok.click();
  }
  await new Promise(function(r){setTimeout(r,1600);});
  return {
    ok:!prompt&&(!flowErr||jumped),
    jumped:jumped,
    jumpParams:jumpParams,
    prompt:prompt,
    validResult:validResult,
    validateErr:validateErr,
    apiCode:apiCode,
    apiErr:apiErr,
    apiRes:apiRes,
    flowErr:flowErr,
    flowRet:flowRet,
    href:location.href,
    hash:location.hash,
    form:vm.form||null
  };
 })()"""

LAST_HOOK_TAIL_JS = r"""(function(){
  var x=(window.__ufo_cap&&window.__ufo_cap.items)||[];
  var K=15;
 return {count:x.length,tail:x.slice(-K)};
})()"""

PERF_RESOURCE_TAIL_JS = r"""(function(){
  try{
    var arr=(performance&&performance.getEntriesByType)?performance.getEntriesByType('resource'):[];
    var K=15;
    var tail=arr.slice(Math.max(0,arr.length-K)).map(function(x){
      return {
        name:String((x&&x.name)||'').slice(0,260),
        initiatorType:(x&&x.initiatorType)||'',
        duration:Math.round((((x&&x.duration)||0)*100))/100,
        transferSize:(x&&x.transferSize)||0
      };
    });
    return {count:arr.length,tail:tail};
  }catch(e){
    return {count:0,tail:[],error:String(e)};
  }
})()"""

ACTIVE_FUC_ESTABLISH = r"""(function(){
   function txt(v){ return String(v||'').replace(/\s+/g,' ').trim(); }
   function walk(vm,d,pred){
     if(!vm||d>20) return null;
     if(pred(vm)) return vm;
     var ch=vm.$children||[];
     for(var i=0;i<ch.length;i++){
       var r=walk(ch[i],d+1,pred);
       if(r) return r;
     }
     return null;
   }
   function codeOf(x){ return String((x&&(x.code||x.businessModuleCode||x.id))||'').trim(); }
   function nameOf(x){ return txt(x&&(x.name||x.businessModuleName||x.label||x.title||x.nameI18n||x.i18nName||'')); }
   function urlOf(x){ return txt(x&&(x.url||x.route||x.path||'')); }
   function childrenOf(x){
     if(!x) return [];
     if(Array.isArray(x.childrenList)) return x.childrenList;
     if(Array.isArray(x.children)) return x.children;
     return [];
   }
   var app=document.getElementById('app');
   var root=app&&app.__vue__;
   var idx=root?walk(root,0,function(v){ return (v.$options&&v.$options.name)==='index'; }):null;
   var as=root?walk(root,0,function(v){ return (v.$options&&v.$options.name)==='all-services'; }):null;
   if(idx&&idx.$data&&idx.$data.compName!=='index-common'){
     try{
       if(typeof idx.$set==='function') idx.$set(idx.$data,'compName','index-common');
       else idx.$data.compName='index-common';
       if(typeof idx.$forceUpdate==='function') idx.$forceUpdate();
     }catch(e){}
   }
   if(!as||typeof as.activefuc!=='function') return {ok:false,err:'no_all_services',href:location.href,hash:location.hash};
   var cardlist=(as.$data&&as.$data.cardlist)||{};
   var topList=[];
   if(Array.isArray(cardlist.childrenList)) topList=cardlist.childrenList;
   else if(Array.isArray(cardlist.children)) topList=cardlist.children;
   else if(cardlist.allList&&Array.isArray(cardlist.allList.childrenList)) topList=cardlist.allList.childrenList;
   var topPick=null;
   for(var i=0;i<topList.length;i++){
     var one=topList[i];
     var nm=nameOf(one);
     var url=urlOf(one);
     if(nm.indexOf('设立登记')>=0||nm.indexOf('设立')>=0||url.indexOf('name-register')>=0||url.indexOf('qydj')>=0){
       topPick=one;
       break;
     }
   }
   var childPick=null;
   var childSource=topPick?childrenOf(topPick):[];
   if(!childSource.length){
     for(var j=0;j<topList.length&&!childPick;j++){
       var kids=childrenOf(topList[j]);
       for(var k=0;k<kids.length;k++){
         var c=kids[k];
         var cn=nameOf(c);
         var cu=urlOf(c);
         if(cn.indexOf('内资')>=0||cn.indexOf('公司设立')>=0||cn.indexOf('名称登记')>=0||cu.indexOf('name-register')>=0||cu.indexOf('namenot')>=0||cu.indexOf('qydj')>=0){
           childPick=c;
           break;
         }
       }
     }
   }else{
     for(var m=0;m<childSource.length;m++){
       var cc=childSource[m];
       var cnn=nameOf(cc);
       var cuu=urlOf(cc);
       if(cnn.indexOf('内资')>=0||cnn.indexOf('公司设立')>=0||cnn.indexOf('名称登记')>=0||cuu.indexOf('name-register')>=0||cuu.indexOf('namenot')>=0||cuu.indexOf('qydj')>=0){
         childPick=cc;
         break;
       }
     }
   }
   var pick=childPick||topPick;
   var code=codeOf(pick)||String((as.$data&&as.$data.active)||'100001');
   if(!code) return {ok:false,err:'no_target_code',href:location.href,hash:location.hash};
   try{
     as.activefuc(code);
     return {
       ok:true,
       code:code,
       name:nameOf(pick),
       url:urlOf(pick),
       active:String((as.$data&&as.$data.active)||''),
       href:location.href,
       hash:location.hash
     };
   }catch(e){
     return {ok:false,err:String(e),code:code,name:nameOf(pick),href:location.href,hash:location.hash};
   }
 })()"""

CLICK_ESTABLISH_DOM = r"""(async function(){
  function visible(el){ return !!(el&&el.offsetParent!==null); }
  function txt(el){ return ((el&&el.textContent)||'').replace(/\s+/g,' ').trim(); }
  function tap(el, mode){
    try{ el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window})); }catch(e){}
    try{ el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window})); }catch(e){}
    try{ el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); }catch(e){}
    try{ el.click(); }catch(e){}
    return {ok:true,mode:mode,text:txt(el).slice(0,120),href:location.href,hash:location.hash};
  }
  function findByWords(words){
    var sels=['.sec-menu','.third-menu','.children-item','.sub-menu','button','.el-button','a','li','div','span'];
    for(var si=0;si<sels.length;si++){
      var arr=[...document.querySelectorAll(sels[si])].filter(function(el){
        var t=txt(el);
        return visible(el)&&t&&t.length<=120;
      });
      for(var wi=0;wi<words.length;wi++){
        for(var ai=0;ai<arr.length;ai++){
          if(txt(arr[ai]).indexOf(words[wi])>=0) return {el:arr[ai],sel:sels[si],word:words[wi]};
        }
      }
    }
    return null;
  }
  var child=findByWords(['内资有限公司','公司设立','名称登记','名称自主申报','内资']);
  if(child) return tap(child.el,'child:'+child.word+'@'+child.sel);
  var top=findByWords(['设立登记','设立']);
  if(top){
    var first=tap(top.el,'top:'+top.word+'@'+top.sel);
    await new Promise(function(r){setTimeout(r,320);});
    child=findByWords(['内资有限公司','公司设立','名称登记','名称自主申报','内资']);
    if(child) return tap(child.el,'child_after_top:'+child.word+'@'+child.sel);
    return first;
  }
  return {ok:false,err:'no_establish_dom',href:location.href,hash:location.hash};
})()"""

CLICK_FIRST_PRIMARY = r"""(function(){
  function visible(el){ return !!(el && el.offsetParent!==null); }
  function txt(el){ return ((el&&el.textContent)||'').replace(/\s+/g,' ').trim(); }
  function tap(btn, mode){
    try{ btn.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); }catch(e){}
    try{ btn.click(); }catch(e){}
    return {ok:true,mode:mode,text:txt(btn).slice(0,80),cls:String((btn&&btn.className)||'').slice(0,120)};
  }
  var btns=[...document.querySelectorAll('button,.el-button')].filter(function(b){ return visible(b)&&!b.disabled; });
  var prefer=['保存并下一步','下一步','开始办理','确定','继续'];
  for(var i=0;i<prefer.length;i++){
    for(var j=0;j<btns.length;j++){
      var t=txt(btns[j]);
      if(t&&t.indexOf(prefer[i])>=0) return tap(btns[j],'text:'+prefer[i]);
    }
  }
  for(var k=0;k<btns.length;k++){
    var cls=String(btns[k].className||'');
    if(cls.indexOf('el-button--primary')>=0) return tap(btns[k],'primary_class');
  }
  return {
    ok:false,
    reason:'no_visible_primary',
    buttons:btns.map(function(b){return {text:txt(b).slice(0,60),cls:String((b&&b.className)||'').slice(0,80)};}).slice(0,12)
  };
})()"""

# 停点：页面出现「云提交」相关文案（不自动点击「云提交」以免误提交）
YUN_SUBMIT_PROBE = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var keys=['云提交','云端提交','提交至云','云平台上报','云侧提交'];
  var hasYun=false;
  for(var i=0;i<keys.length;i++){ if(t.indexOf(keys[i])>=0){ hasYun=true; break; } }
  return {
    href: location.href,
    hash: location.hash,
    hasYunSubmit: hasYun,
    hasYunbangbanMode: t.indexOf('云帮办流程模式选择')>=0,
    hasFaceSmsGate: /人脸识别|面容识别|短信验证|实人认证|活体检测/.test(t),
    head: t.replace(/\s+/g,' ').trim().slice(0, 900)
  };
})()"""


def cascade_pick_nth_js(n: int) -> str:
    ni = int(n)
    return (
        "(function(){var labs=[...document.querySelectorAll('.el-cascader-menu .el-cascader-node .el-cascader-node__label')];"
        f"var n={ni};if(!labs[n])return{{ok:false,idx:n,cnt:labs.length}};"
        "labs[n].click();return{ok:true,idx:n,text:(labs[n].textContent||'').trim().slice(0,40)};})()"
    )


def run_s08_cascade_sequence(r: Any, rec: Dict[str, Any], tag: str, *, dist_path_texts: Optional[List[str]] = None) -> None:
    """级联：先多击所有可见 cascader 展开；再尝试住所类 el-select；再首轮每层首项；再打开一次并尝试第 2 项（降级），再补若干首项。"""
    mo = r.ev(CASCADE_OPEN_MULTI_JS, tag=f"{tag}_cascade_multi")
    rec["steps"].append({"step": f"{tag}_cascade_open_multi", "data": mo})
    sleep_human(0.42)
    tne = r.ev(TNE_DATA_PICKER_OPEN_JS, tag=f"{tag}_tne_open")
    rec["steps"].append({"step": f"{tag}_tne_open", "data": tne})
    sleep_human(0.35)
    reg = r.ev(S08_REGION_SELECT_PROBE_JS, tag=f"{tag}_region_sel")
    rec["steps"].append({"step": f"{tag}_region_select_probe", "data": reg})
    sleep_human(0.35)
    did_targeted = False
    if dist_path_texts:
        # 优先按目标路径逐层点选（如：广西壮族自治区→玉林市→容县），避免“每层都点第一项”导致不收敛
        picked: List[Dict[str, Any]] = []
        for ti, txt in enumerate([x for x in dist_path_texts if x][:4]):
            try:
                final_res: Any = None
                attempts: List[Dict[str, Any]] = []
                for aj in range(4):
                    # 确保 popover 打开
                    r.ev(TNE_DATA_PICKER_OPEN_JS, tag=f"{tag}_tne_open_{ti}_{aj}")
                    # 区县/街道常异步加载，给足时间
                    sleep_human(0.55 + 0.35 * aj)
                    res = r.ev(s08_pick_dropdown_by_text_js(txt), tag=f"{tag}_pick_txt_{ti}_{aj}")
                    attempts.append({"try": aj, "res": res})
                    final_res = res
                    if isinstance(res, dict) and res.get("ok"):
                        did_targeted = True
                        break
                    sleep_human(0.35 + 0.25 * aj)
                picked.append({"i": ti, "want": txt, "attempts": attempts, "res": final_res})
                sleep_human(0.85)
            except Exception as e:
                picked.append({"i": ti, "want": txt, "err": repr(e)})
        rec["steps"].append({"step": f"{tag}_region_pick_by_texts", "data": picked})
    # 若已按目标文本命中过，避免后续“点第一个选项”的兜底把正确选择冲掉
    if (not did_targeted) and isinstance(reg, dict) and reg.get("ok"):
        pk0 = r.ev(S08_PICK_FIRST_DROPDOWN_OPTION_JS, tag=f"{tag}_region_pick_dropdown")
        rec["steps"].append({"step": f"{tag}_region_pick_dropdown", "data": pk0})
        sleep_human(0.28)
        if not (isinstance(pk0, dict) and pk0.get("ok")):
            pk1 = r.ev(CASCADE_PICK_FIRST_VISIBLE_JS, tag=f"{tag}_region_pick_cascade")
            rec["steps"].append({"step": f"{tag}_region_pick_cascade", "data": pk1})
            sleep_human(0.28)
        for ri in range(4):
            pkx = r.ev(S08_PICK_FIRST_DROPDOWN_OPTION_JS, tag=f"{tag}_region_lvl_{ri}")
            rec["steps"].append({"step": f"{tag}_region_dropdown_chain_{ri}", "data": pkx})
            if not (isinstance(pkx, dict) and pkx.get("ok")):
                break
            sleep_human(0.26)
    co = r.ev(CASCADE_OPEN_JS, tag=f"{tag}_copen")
    rec["steps"].append({"step": f"{tag}_cascade_open", "data": co})
    for ci in range(4):
        sleep_human(0.35)
        pk = r.ev(CASCADE_PICK_FIRST_VISIBLE_JS, tag=f"{tag}_cfa_{ci}")
        rec["steps"].append({"step": f"{tag}_cascade_first_a_{ci}", "data": pk})
        if isinstance(pk, dict) and not pk.get("ok"):
            break
    sleep_human(0.45)
    r.ev(CASCADE_OPEN_JS, tag=f"{tag}_copen2")
    sleep_human(0.35)
    pk2 = r.ev(cascade_pick_nth_js(1), tag=f"{tag}_cn1")
    rec["steps"].append({"step": f"{tag}_cascade_pick_nth1", "data": pk2})
    for ci in range(3):
        sleep_human(0.32)
        pk = r.ev(CASCADE_PICK_FIRST_VISIBLE_JS, tag=f"{tag}_cfb_{ci}")
        rec["steps"].append({"step": f"{tag}_cascade_first_b_{ci}", "data": pk})
        if isinstance(pk, dict) and not pk.get("ok"):
            break
    sleep_human(0.75)


def collect_blocker_api_tail(r: Any) -> Dict[str, Any]:
    """卡点 L2/L1 轻量摘要：__ufo_cap 尾部 + Performance resource（icpsp-api）；hook 空则重装短等再读。"""
    out: Dict[str, Any] = {}
    try:
        out["hook_tail"] = r.ev(LAST_HOOK_TAIL_JS, tag="blocker_hook_tail")
    except BaseException as e:
        out["hook_tail"] = {"read_error": repr(e)}
    try:
        out["perf_resource_tail"] = r.ev(PERF_RESOURCE_TAIL_JS, tag="blocker_perf_tail")
    except BaseException as e:
        out["perf_resource_tail"] = {"read_error": repr(e)}
    ht = out.get("hook_tail")
    cnt = 0
    if isinstance(ht, dict):
        cnt = int(ht.get("count") or 0)
    if cnt == 0:
        try:
            install_hook(r.raw)
            sleep_human(0.5)
            out["hook_tail_after_reinstall"] = r.ev(LAST_HOOK_TAIL_JS, tag="blocker_hook_tail_re")
        except BaseException as e:
            out["hook_tail_after_reinstall"] = {"read_error": repr(e)}
    return out


def record_blocker_bundle(
    rec: Dict[str, Any],
    r: Any,
    reason_tag: str,
    *,
    round_i: Optional[int] = None,
) -> Dict[str, Any]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    rid = f"{reason_tag}_{ts}" if round_i is None else f"{reason_tag}_r{int(round_i)}_{ts}"
    bundle: Dict[str, Any] = {
        "tag": reason_tag,
        "wall_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "round": round_i,
        "ui": None,
        "png_path": None,
    }
    try:
        bundle["ui"] = r.ev(READ_BLOCKER_UI_JS, tag=f"read_ui_{rid}")
    except BaseException as e:
        bundle["ui"] = {"read_error": repr(e)}
    try:
        bundle["last_api"] = collect_blocker_api_tail(r)
    except BaseException as e:
        bundle["last_api"] = {"collect_error": repr(e)}
    try:
        ui = bundle.get("ui")
        href = ""
        if isinstance(ui, dict):
            href = str(ui.get("href") or "")
        if "guide/base" in href:
            bundle["guide_base_structured"] = r.ev(S08_EXIT_DIAGNOSTIC_JS, tag=f"s08_blk_{rid}")
    except BaseException as e:
        bundle["guide_base_structured"] = {"read_error": repr(e)}
    try:
        png_path = SHOT_DIR / f"{rid}.png"
        if r.raw.screenshot_png_file(png_path):
            bundle["png_path"] = str(png_path).replace("\\", "/")
    except BaseException as e:
        bundle["png_error"] = repr(e)
    rec.setdefault("blocker_evidence", []).append(bundle)
    rec["steps"].append({"step": f"blocker_evidence_{reason_tag}", "data": bundle})
    return bundle


def run_s08_exit_diagnostic_bundle(r: Any, rec: Dict[str, Any], round_i: int, reason_tag: str) -> Any:
    diag = r.ev(S08_EXIT_DIAGNOSTIC_JS, tag=f"s08_diag_{round_i}")
    record_blocker_bundle(rec, r, reason_tag, round_i=round_i)
    rec["steps"].append({"step": "s08_exit_diagnostic", "data": {"round": round_i, "reason": reason_tag, "diagnostic": diag}})
    return diag


def _s08_prompts_blocking(state: Any) -> bool:
    if not isinstance(state, dict):
        return False
    return bool(
        state.get("hasNamePrompt")
        or state.get("hasQualificationPrompt")
        or state.get("ghostDialogState")
    )


def _s08_prompt_recovery_summary(before: Any, after: Any) -> Dict[str, Any]:
    b = before if isinstance(before, dict) else {}
    a = after if isinstance(after, dict) else {}
    return {
        "state_changed": b != a,
        "still_blocking": _s08_prompts_blocking(a),
        "before": b,
        "after": a,
    }


def _s08_needs_vm_prefill(state: Any) -> bool:
    if not isinstance(state, dict):
        return False
    form = state.get("guideForm")
    if not isinstance(form, dict):
        form = {}
    choice_name = str(state.get("guideChoiceName") or "").strip()
    form_isname_type = str(form.get("isnameType") or "").strip()
    form_choice_name = str(form.get("choiceName") or "").strip()
    form_dist_code = str(form.get("distCode") or "").strip()
    form_street_code = str(form.get("streetCode") or "").strip()
    form_street_name = str(form.get("streetName") or "").strip()
    return bool(
        state.get("guideVmFound")
        and (
            not str(state.get("guideDataInfoCode") or "").strip()
            or not str(form.get("nameCode") or "").strip()
            or not form_isname_type
            or not form_choice_name
            or not str(form.get("havaAdress") or "").strip()
            or not form_dist_code
            or not form_street_code
            or not form_street_name
            or choice_name in ("", "请选择企业类型")
        )
    )


def _build_s08_vm_prefill_js(guide_seed: Dict[str, Any]) -> str:
    dist_code_path_raw = guide_seed.get("distCodePath") or []
    dist_path_texts_raw = guide_seed.get("distPathTexts") or []
    seed = {
        "distCode": str(guide_seed.get("distCode") or "").strip(),
        "streetCode": str(guide_seed.get("streetCode") or guide_seed.get("distCode") or "").strip(),
        "streetName": str(guide_seed.get("streetName") or "").strip(),
        "address": str(guide_seed.get("address") or "").strip(),
        "detAddress": str(guide_seed.get("detAddress") or "").strip(),
        "nameCode": str(guide_seed.get("nameCode") or "0").strip() or "0",
        "isnameType": str(guide_seed.get("isnameType") or guide_seed.get("nameCode") or "0").strip() or "0",
        "formChoiceName": str(guide_seed.get("formChoiceName") or guide_seed.get("nameCode") or "0").strip() or "0",
        "havaAdress": str(guide_seed.get("havaAdress") or "1").strip() or "1",
        "distCodePath": [str(x).strip() for x in dist_code_path_raw if str(x).strip()],
        "distPathTexts": [str(x).strip() for x in dist_path_texts_raw if str(x).strip()],
    }
    js = r"""(function(seed){
  function clone(v){ try{ return JSON.parse(JSON.stringify(v)); }catch(e){ return v; } }
  function walk(vm,d,pred){
    if(!vm||d>20) return null;
    if(pred(vm)) return vm;
    var ch=vm.$children||[];
    for(var i=0;i<ch.length;i++){
      var r=walk(ch[i],d+1,pred);
      if(r) return r;
    }
    return null;
  }
  function findByCode(arr, code){
    if(!Array.isArray(arr)) return null;
    for(var i=0;i<arr.length;i++){
      var x=arr[i];
      if(String((x&&x.code)||'')===code) return clone(x);
      var r=findByCode(x&&x.child, code);
      if(r) return r;
    }
    return null;
  }
  function clickText(t){
    if(!t) return null;
    var nodes=[...document.querySelectorAll('label,.tni-radio,.tni-radio__label,span,div')].filter(function(n){return n&&n.offsetParent!==null;});
    for(var i=0;i<nodes.length;i++){
      var n=nodes[i];
      var tx=(n.textContent||'').replace(/\s+/g,' ').trim();
      if(tx===t||tx.indexOf(t)>=0){
        ['mousedown','mouseup','click'].forEach(function(tp){
          try{ n.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window})); }catch(e){}
        });
        return tx;
      }
    }
    return null;
  }
  var app=document.getElementById('app');
  var vm=app&&app.__vue__?walk(app.__vue__,0,function(v){
    var n=(v.$options&&v.$options.name)||'';
    return n==='index'&&typeof v.flowSave==='function';
  }):null;
  if(!vm) return {ok:false,msg:'no_guide_vm',href:location.href,hash:location.hash};
  var setv=function(obj,key,val){
    if(!obj||!key) return;
    try{ if(vm.$set) vm.$set(obj,key,val); else obj[key]=val; }catch(e){ obj[key]=val; }
  };
  vm.form=vm.form||{};
  var entType=String((vm.form&&vm.form.entType)||vm.entTypeCode||((vm.$route&&vm.$route.query&&vm.$route.query.entType)||'')||'').trim();
  var pick=null;
  if(Array.isArray(vm.companys)){
    for(var i=0;i<vm.companys.length;i++){
      var one=vm.companys[i];
      if(String((one&&one.code)||'')===entType){ pick=clone(one); break; }
    }
  }
  if(!pick) pick=findByCode(vm.entTypeTree, entType);
  if(!pick) pick=findByCode(vm.entTypeTreeTwo, entType);
  setv(vm.form,'entType', entType);
  setv(vm.form,'nameCode', seed.nameCode||'0');
  setv(vm.form,'isnameType', seed.isnameType||seed.nameCode||'0');
  setv(vm.form,'choiceName', seed.formChoiceName||seed.nameCode||'0');
  setv(vm.form,'havaAdress', seed.havaAdress||'1');
  if(seed.distCode) setv(vm.form,'distCode', seed.distCode);
  if(seed.streetCode) setv(vm.form,'streetCode', seed.streetCode);
  if(seed.streetName) setv(vm.form,'streetName', seed.streetName);
  if(seed.address) setv(vm.form,'address', seed.address);
  if(seed.detAddress) setv(vm.form,'detAddress', seed.detAddress);
  if(pick) setv(vm,'dataInfo', pick);
  if(pick&&pick.name) setv(vm,'choiceName', pick.name);
  if(entType) setv(vm,'entTypeCode', entType);
  if(pick&&pick.showType) setv(vm,'entTypeRealy', pick.showType);
  if(typeof vm.searchAlready!=='undefined') setv(vm,'searchAlready', false);
  if(typeof vm.isnameType!=='undefined') setv(vm,'isnameType', false);
  if(!vm.fzSign) setv(vm,'fzSign', 'N');
  if(seed.address) setv(vm,'totalAddress', seed.address);
  var picker=walk(vm,0,function(v){ return (v.$options&&v.$options.name)==='tne-data-picker'; });
  var pathCodes=Array.isArray(seed.distCodePath)&&seed.distCodePath.length ? seed.distCodePath : (seed.distCode?[seed.distCode]:[]);
  var pathTexts=Array.isArray(seed.distPathTexts) ? seed.distPathTexts : [];
  var pathObjs=[];
  for(var j=0;j<pathCodes.length;j++){
    pathObjs.push({value:pathCodes[j],text:pathTexts[j]||pathCodes[j]});
  }
  var businessDistList=clone(pathCodes);
  if(seed.streetCode){
    if(businessDistList.length>=4) businessDistList[businessDistList.length-1]=seed.streetCode;
    else businessDistList.push(seed.streetCode);
  }
  if(picker){
    try{ picker.selected=clone(pathObjs); }catch(e){}
    try{ picker.inputSelected=clone(pathObjs); }catch(e){}
    try{ picker.checkValue=clone(pathCodes); }catch(e){}
    try{ picker.selectedIndex=Math.max(0,pathCodes.length-1); }catch(e){}
    try{ picker.$emit&&picker.$emit('input', clone(pathCodes)); }catch(e){}
    try{ picker.$emit&&picker.$emit('change', clone(pathCodes)); }catch(e){}
    try{ picker.updateBindData&&picker.updateBindData(); }catch(e){}
    try{ picker.updateSelected&&picker.updateSelected(); }catch(e){}
    try{ picker.onchange&&picker.onchange(clone(pathCodes)); }catch(e){}
    try{ picker.ondatachange&&picker.ondatachange(); }catch(e){}
    try{ picker.inputSelected=clone(pathObjs); }catch(e){}
    try{ picker.selected=clone(pathObjs); }catch(e){}
    try{ if(picker.$forceUpdate) picker.$forceUpdate(); }catch(e){}
  }
  if(businessDistList.length){
    try{ setv(vm,'distList', clone(businessDistList)); }catch(e){}
    try{ setv(vm.form,'distList', clone(businessDistList)); }catch(e){}
  }
  if(seed.distCode) setv(vm.form,'distCode', seed.distCode);
  if(seed.streetCode) setv(vm.form,'streetCode', seed.streetCode);
  if(seed.streetName) setv(vm.form,'streetName', seed.streetName);
  if(seed.address) setv(vm.form,'address', seed.address);
  if(seed.detAddress) setv(vm.form,'detAddress', seed.detAddress);
  try{ if(typeof vm.getTotalAddress==='function') vm.getTotalAddress(); }catch(e){}
  try{ if(vm.$forceUpdate) vm.$forceUpdate(); }catch(e){}
  if(pick&&pick.name) clickText(pick.name);
  clickText('未申请');
  try{
    if(vm.$refs&&vm.$refs.form&&typeof vm.$refs.form.clearValidate==='function') vm.$refs.form.clearValidate();
  }catch(e){}
  return {
    ok:true,
    entType:entType,
    picked:pick?{code:pick.code,name:pick.name,showType:pick.showType}:null,
    form:vm.form||null,
    choiceName:vm.choiceName||'',
    dataInfoCode:(vm.dataInfo&&(vm.dataInfo.code||vm.dataInfo.entType||vm.dataInfo.value))||null,
    pickerCheckValue:(picker&&picker.checkValue)||null,
    pickerInputSelected:(picker&&picker.inputSelected)||null,
    distList:vm.distList||null,
    href:location.href,
    hash:location.hash
  };
})(__SEED__)"""
    return js.replace("__SEED__", json.dumps(seed, ensure_ascii=False))


def snap(c: CDP) -> dict:
    return c.ev(
        r"""(function(){
          var t=(document.body&&document.body.innerText)||'';
          var head=t.slice(0,1400);
          var guest=/登录\s*\/\s*注册/.test(head);
          var task=head.indexOf('办件中心')>=0;
          return {
            href:location.href,
            hash:location.hash,
            title:document.title,
            hasTaskCenter:task,
            guestHeaderLogin:guest,
            likelyLoggedIn:task && !guest,
            snippet:t.replace(/\s+/g,' ').trim().slice(0,280)
          };
        })()"""
    )


def install_hook(c: CDP) -> Any:
    return c.ev(HOOK_JS)


def dump_cap(c: CDP) -> dict:
    return c.ev(
        r"""(function(){
          var x=window.__ufo_cap||{items:[]};
          var arr=Array.isArray(x.items)?x.items:[];
          var K=20;
          return {count:arr.length,items:arr.slice(Math.max(0,arr.length-K))};
        })()"""
    )


# Element 弹窗底部主按钮（主按钮点不到时的兜底）
CLICK_DIALOG_PRIMARY = r"""(function(){
  var wraps=document.querySelectorAll('.el-dialog__wrapper');
  var dlg=null;
  for(var i=0;i<wraps.length;i++){
    var w=wraps[i];
    var st=(w.getAttribute('style')||'');
    if(st.indexOf('display: none')>=0||st.indexOf('display:none')>=0) continue;
    if(w.offsetParent===null) continue;
    dlg=w; break;
  }
  if(!dlg) return {ok:false,reason:'no_visible_dialog'};
  var foot=dlg.querySelector('.el-dialog__footer');
  if(!foot) return {ok:false,reason:'no_footer'};
  var btn=foot.querySelector('button.el-button--primary')||foot.querySelector('.el-button--primary');
  if(btn && !btn.disabled && btn.offsetParent!==null){
    btn.click();
    return {ok:true,mode:'dialog_primary',text:(btn.textContent||'').replace(/\s+/g,' ').trim().slice(0,80)};
  }
  return {ok:false,reason:'no_primary_in_footer'};
})()"""

# 停点：页面出现「云提交」相关文案（不自动点击「云提交」以免误提交）
YUN_SUBMIT_PROBE = r"""(function(){
  var t=(document.body&&document.body.innerText)||'';
  var keys=['云提交','云端提交','提交至云','云平台上报','云侧提交'];
  var hasYun=false;
  for(var i=0;i<keys.length;i++){ if(t.indexOf(keys[i])>=0){ hasYun=true; break; } }
  return {
    href: location.href,
    hash: location.hash,
    hasYunSubmit: hasYun,
    hasYunbangbanMode: t.indexOf('云帮办流程模式选择')>=0,
    hasFaceSmsGate: /人脸识别|面容识别|短信验证|实人认证|活体检测/.test(t),
    head: t.replace(/\s+/g,' ').trim().slice(0, 900)
  };
})()"""


class _ResilientCDP:
    """CDP eval with auto-reconnect on transient socket errors."""

    def __init__(self, first: "CDP", rec: Dict[str, Any]):
        self._cdp = first
        self.rec = rec

    @property
    def raw(self) -> CDP:
        return self._cdp

    def close(self) -> None:
        try:
            self._cdp.close()
        except Exception:
            pass

    def ev(self, expr: str, tag: str = "ev", timeout_ms: int = 120000) -> Any:
        for attempt in range(8):
            try:
                return self._cdp.ev(expr, timeout_ms=timeout_ms)
            except BaseException as e:
                if attempt >= 7 or not _is_socket_dead_exc(e):
                    self.rec["steps"].append({"step": "cdp_fatal", "data": {"tag": tag, "err": repr(e), "attempt": attempt}})
                    raise
                self.rec["steps"].append(
                    {"step": "cdp_reconnect", "data": {"tag": tag, "attempt": attempt, "err": repr(e)}}
                )
                try:
                    self._cdp.close()
                except BaseException:
                    pass
                ws_url2, u2, dbg = pick_ws()
                if not ws_url2:
                    self.rec["steps"].append({"step": "cdp_reconnect_no_tab", "data": dbg})
                    raise RuntimeError("no CDP page after socket loss") from e
                time.sleep(0.45 + 0.2 * attempt)
                self._cdp = CDP(ws_url2)
        return None


def wait_href_contains_r(r: _ResilientCDP, needle: str, max_wait: float = 12.0) -> bool:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        href = r.ev(r"""(function(){return location.href;})()""", tag="wait_href")
        if isinstance(href, str) and needle in href:
            return True
        time.sleep(0.25)
    return False


def portal_entry_url(entry: str) -> str:
    e = (entry or "namenotice").strip().lower()
    if e in ("guide", "guide_base", "guide-base"):
        return PORTAL_INDEX_PAGE_GUIDE_BASE
    return PORTAL_INDEX_PAGE


def l3_step_code_from_href(href: str) -> str:
    """与 context_table_driven_playbook 对齐的粗粒度阶段码，仅用于 L3 留痕。"""
    if not isinstance(href, str):
        return "SXX_UNKNOWN"
    u = href
    ul = u.lower()
    if "portal.html" in ul and "#/index/page" in ul and "enterprise-zone" not in ul:
        return "S00_PORTAL_INDEX"
    if "enterprise-zone" in ul:
        return "S05_ENTERPRISE_ZONE"
    if "name-register.html" in ul:
        if "guide/base" in ul:
            return "S08_NAME_REG_GUIDE_BASE"
        return "S10_NAME_REGISTER_SPA"
    if "core.html" in ul:
        if "name-check" in ul:
            return "S12_CORE_NAMECHECK"
        if "basic-info" in ul:
            return "S13_CORE_BASIC_INFO"
        if "member-post" in ul:
            return "S14_CORE_MEMBER"
        return "S20_CORE_FLOW"
    return "SXX_OTHER"


def enrich_probe_l3(probe: Any) -> Dict[str, Any]:
    if not isinstance(probe, dict):
        return {"raw": probe, "l3_step_code": "SXX_UNKNOWN"}
    href = probe.get("href")
    code = l3_step_code_from_href(href if isinstance(href, str) else "")
    out = dict(probe)
    out["l3_step_code"] = code
    return out


def _steps_reached_core_html(steps: List[Dict[str, Any]]) -> bool:
    for s in steps:
        d = s.get("data")
        if not isinstance(d, dict):
            continue
        h = d.get("href")
        if isinstance(h, str) and "core.html" in h:
            return True
        if str(s.get("step") or "").startswith("before_primary_round_"):
            h2 = d.get("href")
            if isinstance(h2, str) and "core.html" in h2:
                return True
    return False


def compute_phase_verdict(rec: Dict[str, Any]) -> Dict[str, Any]:
    """两阶段业务结论（与 docs/阶段验收清单.md 对齐）；供 JSON 与复盘，不等同于 AC 技术项。"""
    steps = rec.get("steps") or []
    yun = any(s.get("step") == "reached_yun_submit" for s in steps)
    core = _steps_reached_core_html(steps)
    gate = next((s for s in steps if s.get("step") == "case_company_listing_gate"), None)
    skipped = next((s for s in steps if s.get("step") == "case_company_listing_gate_skipped"), None)
    abort_p1 = next(
        (
            s
            for s in steps
            if s.get("step") == "abort" and s.get("reason") == "case_company_not_in_my_case_list"
        ),
        None,
    )

    p1_status = "unknown"
    p1_detail: Dict[str, Any] = {}
    if isinstance(gate, dict):
        gd = gate.get("data") if isinstance(gate.get("data"), dict) else {}
        p1_detail["listing_company_match"] = bool(gd.get("present"))
        p1_status = "pass" if gd.get("present") else "fail"
    elif isinstance(skipped, dict):
        sd = skipped.get("data") if isinstance(skipped.get("data"), dict) else {}
        p1_detail["skipped_list_gate"] = True
        p1_detail["href_at_skip"] = sd.get("href")
        if core:
            p1_status = "pass"
            p1_detail["note"] = "未验办件列表，但本 run 曾进入 core.html，视为已具备进入设立主流程条件（第一阶段应已在人工侧完成）"
        else:
            p1_status = "unknown"
            p1_detail["note"] = "未在办件列表页做企业名匹配；若尚未核名/无对应用件，则第一阶段未完成"
    if abort_p1 is not None:
        p1_status = "fail"
        p1_detail["abort_reason"] = "case_company_not_in_my_case_list"

    p2_status = "pass" if yun else "fail"

    actions: List[str] = []
    if p1_status == "fail":
        actions.append(
            "【第一阶段】若启用了列表门禁：列表正文须含拟设企业名；否则请从**名称登记/核名**入口继续**新设**，勿把「列表尚无该行」单独当唯一失败依据。"
        )
    elif p1_status == "unknown":
        actions.append(
            "【第一阶段·新设】拟设主体：完成名称自主申报/核名；办件是否已出现在「我的办件」取决于进度，**未出现不代表核名逻辑已失败**。"
        )
    if not yun:
        actions.append("【第二阶段】进入 core 后完成各步表单与材料上传，直至页面出现「云提交」类文案（本自动化不点提交）。")

    out_pv: Dict[str, Any] = {
        "schema": "ufo.phase_verdict.v1",
        "phase1_name_then_case_row": {
            "title": "第一阶段：名称登记/核名可接续（列表是否已有该行取决于进度；可选列表门禁见 case_company_listing_gate）",
            "status": p1_status,
            "detail": p1_detail,
        },
        "phase2_to_yun_submit_stop": {
            "title": "第二阶段：长表单推进至云提交文案停点（不点云提交）",
            "status": p2_status,
            "reached_core_html": core,
            "reached_yun_submit": yun,
        },
        "suggested_human_actions": actions[:10],
    }
    if rec.get("phase1_only"):
        out_pv["run_mode"] = "phase1_only"
        p2b = out_pv.get("phase2_to_yun_submit_stop")
        if isinstance(p2b, dict):
            p2b = dict(p2b)
            p2b["status"] = "skipped"
            p2b["note"] = "本 run 为第一阶段专用：主循环未执行；核名与材料在浏览器内完成后，再跑第二阶段脚本。"
            out_pv["phase2_to_yun_submit_stop"] = p2b
    return out_pv


def build_acceptance(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps = rec.get("steps") or []

    def pick(step: str) -> Any:
        for s in steps:
            if s.get("step") == step:
                return s.get("data")
        return None

    ac: List[Dict[str, Any]] = []
    ok_cdp = rec.get("error") != "no_cdp_page"
    ac.append({"id": "AC-CDP", "ok": ok_cdp, "note": "已连接 CDP 且存在 9087 页签"})

    nav = pick("snap_after_resume") or pick("snap_after_portal_nav")
    li = bool(isinstance(nav, dict) and nav.get("likelyLoggedIn"))
    ac.append({"id": "AC-LOGIN", "ok": li, "note": "顶栏像已登录（办件中心且无 登录/注册 访客条）", "detail": nav})

    gp = pick("case_company_listing_gate")
    sk = pick("case_company_listing_gate_skipped")
    if isinstance(gp, dict):
        ac.append(
            {
                "id": "AC-PHASE1-COMPANY-ON-LIST",
                "ok": bool(gp.get("present")),
                "note": "【阶段验收】我的办件列表正文含案例企业全称（第一阶段可接续的前置条件）",
                "detail": gp,
            }
        )
    elif isinstance(sk, dict):
        ac.append(
            {
                "id": "AC-PHASE1-COMPANY-ON-LIST",
                "ok": True,
                "skipped": True,
                "note": "【阶段验收】未在列表页做企业名自动匹配（非列表页或已在 core）；请人工确认办件与资料一致",
                "detail": sk,
            }
        )

    if rec.get("resume_current"):
        ac.append(
            {
                "id": "AC-CLICK-ESTABLISH",
                "ok": True,
                "note": "resume_current：未从门户重跑设立入口点击",
                "skipped": True,
            }
        )
    else:
        af = pick("try_activefuc_establish")
        dom = pick("fallback_dom_click_establish")
        click_ok = bool((isinstance(af, dict) and af.get("ok")) or (isinstance(dom, dict) and dom.get("ok")))
        ac.append({"id": "AC-CLICK-ESTABLISH", "ok": click_ok, "note": "activefuc 或 DOM 命中「设立登记」", "activefuc": af, "dom": dom})

    reached_zone = False
    reached_nr = False
    reached_guide = False
    reached_yun_submit = any(s.get("step") == "reached_yun_submit" for s in steps)
    for s in steps:
        d = s.get("data")
        if not isinstance(d, dict):
            continue
        h = d.get("href") if isinstance(d.get("href"), str) else ""
        if "enterprise-zone" in h:
            reached_zone = True
        if _in_name_register_spa(h):
            reached_nr = True
        if isinstance(h, str) and "guide/base" in h:
            reached_guide = True
        if d.get("hasYunSubmit"):
            reached_yun_submit = True
    for s in steps:
        if s.get("step") == "reached_guide_base":
            reached_guide = True
            break
    for s in steps:
        if isinstance(s.get("step"), str) and s["step"].startswith("milestone_guide_base_"):
            reached_guide = True
            break

    reached_core = False
    for s in steps:
        d = s.get("data")
        if not isinstance(d, dict):
            continue
        h = d.get("href")
        if isinstance(h, str) and "core.html" in h:
            reached_core = True
            break
        if s.get("step", "").startswith("before_primary_round_"):
            h2 = d.get("href")
            if isinstance(h2, str) and "core.html" in h2:
                reached_core = True
                break

    ac.append(
        {
            "id": "AC-REACH-FLOW",
            "ok": reached_zone or reached_nr or reached_guide or reached_yun_submit,
            "note": "技术里程碑：曾出现 enterprise-zone / name-register / guide/base / 云提交停点之一（不等于业务上两阶段已验收）",
            "flags": {
                "enterprise_zone": reached_zone,
                "name_register_spa": reached_nr,
                "guide_base": reached_guide,
                "yun_submit": reached_yun_submit,
            },
        }
    )
    ac.append({"id": "AC-GUIDE-BASE", "ok": reached_guide, "note": "出现过 guide/base（中间里程碑）"})
    ac.append(
        {
            "id": "AC-CORE-REACHED",
            "ok": reached_core,
            "note": "曾进入 core.html（设立主流程/材料等）",
        }
    )
    ac.append(
        {
            "id": "AC-YUN-SUBMIT",
            "ok": reached_yun_submit,
            "note": (
                "页面文案出现「云提交」或「云端提交」（主停点）"
                if reached_yun_submit
                else "本轮未在页面文案中检测到「云提交/云端提交」停点（可能卡在名称引导/材料页之前）"
            ),
        }
    )
    early_auth = any(s.get("step") == "l3_warn_auth_gate_early" for s in steps)
    ac.append(
        {
            "id": "AC-NO-EARLY-AUTH",
            "ok": not early_auth,
            "note": "云提交停点前未出现实人/短信类门控（若失败请复核是否环境变更）",
        }
    )

    be = rec.get("blocker_evidence") or []

    def _blocker_bundle_has_evidence(b: Any) -> bool:
        if not isinstance(b, dict):
            return False
        if b.get("png_path"):
            return True
        la = b.get("last_api") or {}
        if not isinstance(la, dict):
            return False
        for k in ("hook_tail", "hook_tail_after_reinstall"):
            ht = la.get(k) or {}
            if isinstance(ht, dict) and int(ht.get("count") or 0) > 0:
                return True
        pr = la.get("perf_resource_tail") or {}
        if isinstance(pr, dict) and isinstance(pr.get("items"), list) and len(pr["items"]) > 0:
            return True
        return False

    blocker_evidence_ok = (not be) or all(_blocker_bundle_has_evidence(x) for x in be)
    ac.append(
        {
            "id": "AC-BLOCKER-EVIDENCE",
            "ok": blocker_evidence_ok,
            "note": "若有 blocker_evidence 记录，则每条须含 png_path 或 last_api 中非空 hook/perf 摘要",
            "count": len(be),
        }
    )
    return ac


def synthesize_framework_notes(rec: Dict[str, Any]) -> Dict[str, Any]:
    """从一次完整 run 的 rec 提炼问题 / 提示 / 建议（供演练报告与后续框架迭代）。"""
    issues: List[str] = []
    prompts: List[str] = []
    recs: List[str] = []
    if rec.get("error") == "no_cdp_page":
        issues.append("CDP 无可用 9087 页签")
        prompts.append("先双击 打开登录器.cmd，确认 http://127.0.0.1:9225/json 有 page 目标后再跑")
    pv = rec.get("phase_verdict")
    if isinstance(pv, dict):
        p1 = pv.get("phase1_name_then_case_row") or {}
        if p1.get("status") == "fail":
            issues.append(
                "【阶段结论】第一阶段未满足（核名/办件列表无对应用件）：见 JSON 字段 phase_verdict.phase1_name_then_case_row"
            )
        p2 = pv.get("phase2_to_yun_submit_stop") or {}
        if p2.get("status") == "fail":
            issues.append(
                "【阶段结论】第二阶段未达云提交文案停点：见 phase_verdict.phase2_to_yun_submit_stop 与 acceptance 中 AC-YUN-SUBMIT"
            )
        for ha in pv.get("suggested_human_actions") or []:
            if isinstance(ha, str) and ha not in prompts:
                prompts.append(ha)
    for s in rec.get("steps") or []:
        if s.get("step") == "abort":
            issues.append(f"脚本中止: {s.get('reason') or s.get('data')}")
        if s.get("step") == "blocked_need_login":
            issues.append("判定为未登录或顶栏非办件中心")
            prompts.append("在 CDP Chrome 完成登录，或关闭多余 9087 标签仅保留已登录页签")
    for ac in rec.get("acceptance") or []:
        if ac.get("skipped"):
            continue
        if not ac.get("ok"):
            issues.append(f"验收项未通过 {ac.get('id')}: {ac.get('note')}")
    att_ok = 0
    att_fail = 0
    for s in rec.get("steps") or []:
        if not isinstance(s.get("step"), str) or not s["step"].startswith("attachment_try_"):
            continue
        d = s.get("data") or {}
        for row in d.get("dom_results") or []:
            if isinstance(row, dict) and row.get("ok"):
                att_ok += 1
            elif isinstance(row, dict) and "ok" in row and not row.get("ok"):
                att_fail += 1
    if att_fail:
        issues.append(f"附件 CDP 注入有失败项: ok={att_ok}, fail={att_fail}")
        recs.append("核对 accept 类型（仅 pdf 槽位用 mock_contract.pdf）；国徽面/反面文案匹配反面图")
    elif att_ok:
        recs.append(f"本 run 经 CDP 成功注入 {att_ok} 个 file 控件（含身份证与模拟件）")
    else:
        att_tries = sum(1 for s in (rec.get("steps") or []) if isinstance(s.get("step"), str) and s["step"].startswith("attachment_try_"))
        if att_tries > 0:
            recs.append(
                "全程未出现可见 input[type=file]（多在 core 材料步骤）；若卡在 name-register/guide/base，"
                "需先人工关闭「请选择是否需要名称」等弹窗并完成级联住所，再继续跑或改从已进 core 的页签启动"
            )
    if any(s.get("step") == "phase1_only_stop" for s in (rec.get("steps") or [])):
        recs.append("第一阶段专用模式已结束：请在浏览器完成核名与材料下载；第二阶段再运行 run_case_rongxian_to_yun_submit.py（不带 --phase1-only，常用 --resume-current）")
    if any(s.get("step") == "reached_yun_submit" for s in (rec.get("steps") or [])):
        recs.append("已到达云提交停点：未自动点击云提交；可在此人工复核材料后再决定")
    elif not any(s.get("step") == "phase1_only_stop" for s in (rec.get("steps") or [])):
        prompts.append("未检测到「云提交」文案：可看 blocker_evidence 截图与最后数步 snap")
    if any(s.get("step") == "abort_s08_stagnation_cap" for s in (rec.get("steps") or [])):
        issues.append("S08（guide/base）连续停滞已达阈值：已早停并写入 s08_exit_diagnostic")
        recs.append("查 JSON 中 s08_exit_diagnostic.diagnostic；优先处理 MessageBox 与住所级联后再跑，或 --resume-current")
    n_obs = len(rec.get("llm_observations") or [])
    if n_obs:
        recs.append(f"本轮已生成 {n_obs} 条 llm_observation.v1（供后续 LLM 规划/RAG）；见 rec.llm_observations")
    if not issues:
        issues.append("（本 run 无结构化阻塞项；仍以 acceptance 与截图为准）")
    return {"issues": issues, "prompts": prompts, "recommendations": recs}


def write_framework_rehearsal_md(rec: Dict[str, Any], path: Path) -> None:
    notes = rec.get("framework_notes") or {}
    lines = [
        "# 设立流程演练（至云提交停点）",
        "",
        f"- **开始**: {rec.get('started_at')}",
        f"- **结束**: {rec.get('ended_at')}",
        f"- **门户入口**: {rec.get('portal_entry')}",
        f"- **resume_current**: {bool(rec.get('resume_current'))}",
        f"- **llm_observations**: {len(rec.get('llm_observations') or [])} 条 (ufo.llm_observation.v1)",
        f"- **run_id**: `{rec.get('run_id')}`",
        f"- **task.state**: {(rec.get('task') or {}).get('state')}",
        "",
        "## 问题 / 阻塞",
        "",
    ]
    for x in notes.get("issues") or []:
        lines.append(f"- {x}")
    lines.extend(["", "## 提示", ""])
    for x in notes.get("prompts") or []:
        lines.append(f"- {x}")
    lines.extend(["", "## 建议", ""])
    for x in notes.get("recommendations") or []:
        lines.append(f"- {x}")
    pv2 = rec.get("phase_verdict")
    if isinstance(pv2, dict):
        lines.extend(["", "## 阶段结论（phase_verdict）", ""])
        p1 = pv2.get("phase1_name_then_case_row") or {}
        p2 = pv2.get("phase2_to_yun_submit_stop") or {}
        lines.append(f"- **第一阶段** `status={p1.get('status')}`: {p1.get('title')}")
        lines.append(f"- **第二阶段** `status={p2.get('status')}`: {p2.get('title')}（reached_core={p2.get('reached_core_html')} reached_yun={p2.get('reached_yun_submit')}）")
    lines.extend(["", "## 验收项摘要", ""])
    for ac in rec.get("acceptance") or []:
        if ac.get("skipped"):
            mark = "SKIP"
        else:
            mark = "OK" if ac.get("ok") else "FAIL"
        lines.append(f"- **{mark}** `{ac.get('id')}`: {ac.get('note')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_llm_observation_v1(
    round_i: int,
    ep: Dict[str, Any],
    snap_d: Any,
    ui_block: Any,
    click_res: Any,
) -> Dict[str, Any]:
    """
    供后续 LLM 规划层消费的紧凑观测（不替代完整 steps；字段保持稳定便于 RAG/工具链）。
    schema: ufo.llm_observation.v1
    """
    l3 = ep.get("l3_step_code") if isinstance(ep, dict) else None
    href = str(ep.get("href") or "") if isinstance(ep, dict) else ""
    errs = (ui_block.get("errors") or [])[:10] if isinstance(ui_block, dict) else []
    mb = str(ui_block.get("messageBox") or "")[:260] if isinstance(ui_block, dict) else ""
    dlg = str(ui_block.get("dialogBody") or "")[:260] if isinstance(ui_block, dict) else ""
    snip = str((snap_d or {}).get("snippet") or "")[-520:] if isinstance(snap_d, dict) else ""
    clk = None
    if isinstance(click_res, dict):
        clk = click_res.get("kw")
    suggests: List[Dict[str, str]] = []
    if errs:
        suggests.append({"kind": "fix_form", "text": "先处理表单标红/校验提示，再点下一步"})
    if mb or dlg or (isinstance(ui_block, dict) and ui_block.get("hasBlocking")):
        suggests.append({"kind": "dismiss_or_confirm_modal", "text": "确认或关闭弹窗/MessageBox 后再继续"})
    if l3 == "S08_NAME_REG_GUIDE_BASE" and ("住所" in snip or "区划" in snip or "区县" in snip):
        suggests.append({"kind": "complete_address_cascade", "text": "完成住所到区县级联；若级联未展开可多击住所输入框"})
    if "core.html" in href:
        suggests.append({"kind": "materials_and_core", "text": "在 core 检查材料上传与各表单项"})
    if isinstance(ep, dict) and ep.get("hasYunSubmit"):
        suggests.append({"kind": "human_gate_yun", "text": "已检测到云提交相关文案：勿自动点提交，人工复核"})
    return {
        "schema": "ufo.llm_observation.v1",
        "round": int(round_i),
        "l3_step_code": l3,
        "href_tail": href[-220:] if href else "",
        "has_yun_submit_text": bool(ep.get("hasYunSubmit")) if isinstance(ep, dict) else False,
        "click_kw": clk,
        "snippet_tail": snip,
        "likely_logged_in": (snap_d or {}).get("likelyLoggedIn") if isinstance(snap_d, dict) else None,
        "ui_errors": errs,
        "message_box_excerpt": mb,
        "dialog_body_excerpt": dlg,
        "suggested_next": suggests[:6],
    }


# 实网默认保守轮次：避免长时间连续推进触发风控
MAX_PRIMARY_ROUNDS = 18

# 连续处于 guide/base（S08）且未进入 core 的最大轮数，超过则早停并写 s08_exit_diagnostic
S08_STUCK_MAX_ROUNDS = 6


def run(
    entry: str = "namenotice",
    out_path: Optional[Path] = None,
    also_write_iter_latest: bool = False,
    assets_path: Optional[Path] = None,
    framework_md_path: Optional[Path] = None,
    resume_current: bool = False,
    human_fast: bool = False,
    require_listing_company_substr: Optional[str] = None,
    phase1_only: bool = False,
    guide_seed: Optional[Dict[str, Any]] = None,
    max_primary_rounds: int = MAX_PRIMARY_ROUNDS,
) -> None:
    portal_start = portal_entry_url(entry)
    out_main = out_path or OUT
    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=human_fast)
    max_primary_rounds = max(4, int(max_primary_rounds))

    ws_url, page0, tab_debug = pick_ws()
    rec: Dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "portal_entry": entry,
        "portal_start_url": portal_start,
        "page_before": page0,
        "cdp_tab_probe": tab_debug,
        "steps": [],
        "framework": {
            "name": "four_layer_evidence + L3_context_tables",
            "version": "2026-04-19b",
            "layers": {"L0": "mitmproxy optional", "L1": "CDP Network.enable + Performance resource tail + hook timing", "L2": "XHR/fetch hook in page (__ufo_cap tail)", "L3": "step JSON + l3_step_code"},
            "stop_condition": "page_text_yun_submit_without_click",
            "note": "实人/短信若出现在云提交停点之前，仅记 l3_warn_auth_gate_early 供复核（预期不应出现）。",
            "blocker_capture": "blocker_evidence[] 含 UI + last_api（hook_tail / perf_resource_tail）+ packet_chain_shots/*.png；S08 用 GUIDE_BASE_AUTOFILL_V2 + 级联双通道；卡顿时 recovery_stuck_js",
            "attachments": "可选 --assets：每轮尝试 DOM.setFileInputFiles；身份证按表单项标签匹配正/反面，其余槽位用 mock PDF/JPEG",
            "llm_observation": "每轮末尾写入 llm_observations[]，schema=ufo.llm_observation.v1，供规划层/RAG 消费",
            "task_run": "run_id + task{} 见 ufo.gov_task_run.v1：state、events（步骤摘要）、summary",
        },
        "run_id": new_run_id(),
        "rehearsal_assets": None,
        "resume_current": bool(resume_current),
        "require_listing_company_substr": require_listing_company_substr,
        "phase1_only": bool(phase1_only),
        "guide_seed_enabled": bool(guide_seed),
        "loop_limits": {
            "max_primary_rounds": int(max_primary_rounds),
            "s08_stuck_max_rounds": int(S08_STUCK_MAX_ROUNDS),
        },
        "llm_observations": [],
        "human_pacing": {"config": "config/human_pacing.json", "fast": bool(human_fast)},
    }
    if not ws_url:
        rec["error"] = "no_cdp_page"
        rec["acceptance"] = build_acceptance(rec)
        rec["phase_verdict"] = compute_phase_verdict(rec)
        rec["task"] = finalize_task_model(rec)
        rec["framework_notes"] = synthesize_framework_notes(rec)
        out_main.parent.mkdir(parents=True, exist_ok=True)
        out_main.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {out_main}")
        if framework_md_path is not None:
            write_framework_rehearsal_md(rec, framework_md_path)
            print(f"Framework MD: {framework_md_path}")
        return

    assets_cfg = None
    if assets_path is not None and assets_path.is_file():
        assets_cfg = load_assets_cfg(assets_path, ROOT)
        rec["rehearsal_assets"] = {
            "config_path": str(assets_path).replace("\\", "/"),
            "id_front": str(assets_cfg["id_front"]),
            "id_back": str(assets_cfg["id_back"]),
            "mock_pdf": str(assets_cfg["mock_pdf"]),
            "mock_image": str(assets_cfg["mock_image"]),
        }

    r: Optional[_ResilientCDP] = None
    err: Optional[str] = None
    try:
        r = _ResilientCDP(CDP(ws_url), rec)
        try:
            r.raw.call("Network.enable", {})
        except Exception:
            pass

        if resume_current:
            href0 = r.ev(r"""(function(){return location.href;})()""", tag="resume_href0")
            rec["steps"].append({"step": "resume_current_skip_portal_nav", "data": {"href": href0}})
            if not isinstance(href0, str) or "zhjg.scjdglj.gxzf.gov.cn:9087" not in href0 or "icpsp-web-pc" not in href0:
                rec["steps"].append(
                    {
                        "step": "abort_resume_not_icpsp9087",
                        "data": {"href": href0, "need": "9087 icpsp-web-pc 页签"},
                    }
                )
                return
            install_hook(r.raw)
            sleep_human(3.0)
            rec["steps"].append({"step": "snap_after_resume", "data": snap(r.raw)})
            rec["steps"].append({"step": "cap_after_hook_resume", "data": dump_cap(r.raw)})
            # 办件列表门禁：避免第一阶段未生成对应用件时在列表页空跑主循环（类人节奏、无连点）
            if require_listing_company_substr and str(require_listing_company_substr).strip():
                need = str(require_listing_company_substr).strip()
                href_gate = r.ev(r"""(function(){return location.href||"";})()""", tag="gate_href")
                hs = str(href_gate or "")
                on_list = "space-index" in hs or "my-space" in hs
                in_core = "core.html" in hs
                if on_list and not in_core:
                    sleep_human(1.5)
                    body = r.ev(
                        r"""(function(){return (document.body&&document.body.innerText)||"";})()""",
                        tag="gate_body",
                    )
                    ok = isinstance(body, str) and need in body
                    rec["steps"].append(
                        {
                            "step": "case_company_listing_gate",
                            "data": {
                                "required_substr": need,
                                "present": ok,
                                "href": href_gate,
                                "hint": "第一阶段须在名称登记完成核名后，于「我的办件」出现与案例一致的企业名称，再点继续办理；否则勿空跑主循环以免风控",
                            },
                        }
                    )
                    if not ok:
                        rec["steps"].append(
                            {
                                "step": "abort",
                                "reason": "case_company_not_in_my_case_list",
                            }
                        )
                        return
                else:
                    rec["steps"].append(
                        {
                            "step": "case_company_listing_gate_skipped",
                            "data": {
                                "required_substr": need,
                                "href": href_gate,
                                "note": "当前不在我的办件列表页（或已在 core），跳过列表门禁；请自行确认办件与资料一致",
                            },
                        }
                    )
        else:
            rec["steps"].append({"step": "nav_portal_index_page", "data": portal_start})
            r.ev(f"location.href={json.dumps(portal_start, ensure_ascii=False)}", tag="nav_portal")
            sleep_human(6.0)
            rec["steps"].append({"step": "snap_after_portal_nav", "data": snap(r.raw)})

            rec["steps"].append({"step": "try_activefuc_establish", "data": r.ev(ACTIVE_FUC_ESTABLISH, tag="activefuc")})
            sleep_human(2.2)
            h1 = r.ev(r"""(function(){return location.href;})()""", tag="href_after_establish_try")
            if (
                isinstance(h1, str)
                and "enterprise-zone" not in h1
                and not _in_name_register_spa(h1)
            ):
                rec["steps"].append({"step": "fallback_dom_click_establish", "data": r.ev(CLICK_ESTABLISH_DOM, tag="dom_establish")})

            wait_href_contains_r(r, "enterprise-zone", 15) or wait_href_contains_r(r, "name-register.html", 12)
            sleep_human(2.2)
            rec["steps"].append({"step": "snap_after_establish_click", "data": snap(r.raw)})

            href_now = r.ev(r"""(function(){return location.href;})()""", tag="href_now")
            snap_est = snap(r.raw)
            looks_logged_out = not bool((snap_est or {}).get("likelyLoggedIn"))
            if (
                isinstance(href_now, str)
                and "enterprise-zone" not in href_now
                and not _in_name_register_spa(href_now)
            ):
                if looks_logged_out and "zhjg.scjdglj.gxzf.gov.cn:9087" in str(href_now):
                    rec["steps"].append(
                        {
                            "step": "blocked_need_login",
                            "note": "当前 CDP 所连标签顶栏像未登录；请把已登录「办件中心」页签切到前台或关掉多余9087 标签后重试",
                            "data": snap_est,
                        }
                    )
                    rec["steps"].append(
                        {
                            "step": "abort",
                            "reason": "请先在本机浏览器登录 9087 后再运行本脚本继续抓包",
                        }
                    )
                    return
                else:
                    rec["steps"].append(
                        {
                            "step": "fallback_nav_enterprise_zone",
                            "note": "设立登记未跳转，直拉企业专区(02_4)",
                            "data": r.ev(
                                f"location.href={json.dumps(ENTERPRISE_ZONE, ensure_ascii=False)}",
                                tag="nav_enterprise_zone",
                            ),
                        }
                    )
                    sleep_human(5.5)
                    rec["steps"].append({"step": "snap_after_enterprise_fallback", "data": snap(r.raw)})

            install_hook(r.raw)
            sleep_human(3.2)
            rec["steps"].append({"step": "cap_after_hook_1", "data": dump_cap(r.raw)})

            href_zone = r.ev(r"""(function(){return location.href;})()""", tag="href_zone")
            if isinstance(href_zone, str) and "enterprise-zone" in href_zone:
                rec["steps"].append({"step": "click_start_if_zone", "data": r.ev(CLICK_FIRST_PRIMARY, tag="click_start_zone")})
                deadline = time.time() + 15
                while time.time() < deadline:
                    h = r.ev(r"""(function(){return location.href;})()""", tag="wait_name_register")
                    if isinstance(h, str) and _in_name_register_spa(h):
                        break
                    time.sleep(0.25)
                sleep_human(2.4)
                rec["steps"].append({"step": "snap_after_start", "data": snap(r.raw)})
                install_hook(r.raw)
                sleep_human(5.5)
                rec["steps"].append({"step": "cap_after_name_register_load", "data": dump_cap(r.raw)})

        if phase1_only:
            href_end = r.ev(r"""(function(){return location.href;})()""", tag="phase1_only_href")
            rec["steps"].append(
                {
                    "step": "phase1_only_stop",
                    "data": {
                        "href": href_end,
                        "note": "仅第一阶段：未执行「直至云提交」主循环。请在浏览器内完成名称申报/核名及系统提示的材料下载；第二阶段再运行：python system/run_case_rongxian_to_yun_submit.py --resume-current",
                    },
                }
            )
            rec["steps"].append({"step": "final_snap", "data": snap(r.raw)})
            rec["steps"].append({"step": "final_cap", "data": dump_cap(r.raw)})
            return

        # 向前推进直到页面出现「云提交」相关文案（停点，不自动点击「云提交」）；CDP 断线自动重连
        no_click_streak = 0
        s08_stagnate = 0
        last_s08_sig: Optional[str] = None
        s08_stuck_counter = 0
        for round_i in range(max_primary_rounds):
            probe = r.ev(YUN_SUBMIT_PROBE, tag=f"yun_probe_{round_i}")
            if not isinstance(probe, dict):
                rec["steps"].append({"step": f"probe_bad_{round_i}", "data": probe})
                break
            ep = enrich_probe_l3(probe)
            rec["steps"].append({"step": f"before_primary_round_{round_i}", "data": ep})
            if ep.get("hasYunSubmit"):
                record_blocker_bundle(rec, r, "reached_yun_submit_ok", round_i=round_i)
                rec["steps"].append({"step": "reached_yun_submit", "data": ep})
                break

            href_chk = str(ep.get("href") or "")
            l3_early = ep.get("l3_step_code")
            if "core.html" in href_chk or ("name-register.html" in href_chk and "guide/base" not in href_chk):
                s08_stuck_counter = 0
            elif "guide/base" in href_chk and l3_early == "S08_NAME_REG_GUIDE_BASE":
                s08_stuck_counter += 1
            if s08_stuck_counter >= S08_STUCK_MAX_ROUNDS:
                run_s08_exit_diagnostic_bundle(r, rec, round_i, "s08_exit_blocked_cap")
                rec["steps"].append(
                    {
                        "step": "abort_s08_stagnation_cap",
                        "data": {
                            "s08_stuck_counter": s08_stuck_counter,
                            "threshold": S08_STUCK_MAX_ROUNDS,
                            "round": round_i,
                            "hint": "人工处理 MessageBox/住所级联后再跑，或使用 --resume-current 从 core 继续",
                        },
                    }
                )
                break

            if assets_cfg is not None:
                try:
                    ures = try_upload_for_current_page(r, assets_cfg)
                    rec["steps"].append({"step": f"attachment_try_{round_i}", "data": ures})
                except Exception as e:
                    rec["steps"].append({"step": f"attachment_try_err_{round_i}", "error": repr(e)})
                sleep_human(0.75)
            if ep.get("hasFaceSmsGate") and not ep.get("hasYunSubmit"):
                rec["steps"].append({"step": "l3_warn_auth_gate_early", "data": ep})
            href_p = ep.get("href")
            if isinstance(href_p, str) and "guide/base" in href_p:
                rec["steps"].append({"step": f"milestone_guide_base_{round_i}", "data": {"href": href_p, "l3": ep.get("l3_step_code")}})
            l3c = ep.get("l3_step_code")
            if l3c == "S08_NAME_REG_GUIDE_BASE":
                h_sig = f"{ep.get('hash')}|{(href_p if isinstance(href_p, str) else '')[:200]}"
                if h_sig == last_s08_sig:
                    s08_stagnate += 1
                else:
                    s08_stagnate = 0
                    last_s08_sig = h_sig
                if s08_stagnate >= 3:
                    rec["steps"].append(
                        {"step": f"s08_hash_stagnate_{round_i}", "data": {"streak": s08_stagnate, "sig": h_sig}}
                    )
                    gfill_s = r.ev(GUIDE_BASE_AUTOFILL_V2, tag=f"guide_base_stagnate_{round_i}")
                    rec["steps"].append({"step": f"guide_base_autofill_stagnate_{round_i}", "data": gfill_s})
                    run_s08_cascade_sequence(r, rec, f"stagnate_{round_i}")
                    s08_stagnate = 0
            else:
                s08_stagnate = 0
                last_s08_sig = None
            if l3c == "S08_NAME_REG_GUIDE_BASE" and not rec.get("_guide_autofill_s08_v2_done"):
                gfill = r.ev(GUIDE_BASE_AUTOFILL_V2, tag="guide_base_autofill_v2")
                rec["steps"].append({"step": "guide_base_autofill_v2", "data": gfill})
                rec["_guide_autofill_s08_v2_done"] = True
                sleep_human(0.65)
                run_s08_cascade_sequence(r, rec, "guide_init")
            skip_primary_click = False
            s08_recovery_res = None
            s08_vm_prefill_res = None
            s08_flow_save_res = None
            s08_skip_reason = None
            s08_skip_recovery_round = False
            if l3c == "S08_NAME_REG_GUIDE_BASE":
                s08_state_before = r.ev(S08_STATE_PROBE_JS, tag=f"s08_state_{round_i}")
                rec["steps"].append({"step": f"s08_state_probe_{round_i}", "data": s08_state_before})
                if guide_seed is not None and _s08_needs_vm_prefill(s08_state_before):
                    s08_vm_prefill_res = r.ev(_build_s08_vm_prefill_js(guide_seed), tag=f"s08_vm_prefill_{round_i}")
                    rec["steps"].append({"step": f"s08_vm_prefill_{round_i}", "data": s08_vm_prefill_res})
                    sleep_human(0.85)
                    s08_state_prefill = r.ev(S08_STATE_PROBE_JS, tag=f"s08_state_after_prefill_{round_i}")
                    rec["steps"].append({"step": f"s08_state_after_prefill_{round_i}", "data": s08_state_prefill})
                    skip_primary_click = True
                    s08_skip_reason = "s08_vm_prefill_or_flow_save"
                    s08_skip_recovery_round = True
                    if not rec.get("_s08_vm_flow_save_done"):
                        s08_flow_save_res = r.ev(S08_GUIDE_FLOWSAVE_JS, tag=f"s08_flow_save_{round_i}")
                        rec["steps"].append({"step": f"s08_flow_save_{round_i}", "data": s08_flow_save_res})
                        rec["_s08_vm_flow_save_done"] = True
                        sleep_human(1.2)
                        s08_state_after_flow = r.ev(S08_STATE_PROBE_JS, tag=f"s08_state_after_flow_save_{round_i}")
                        rec["steps"].append({"step": f"s08_state_after_flow_save_{round_i}", "data": s08_state_after_flow})
                if not s08_skip_recovery_round and _s08_prompts_blocking(s08_state_before):
                    s08_recovery_res = r.ev(CLICK_RECOVERY_STUCK_JS, tag=f"s08_prompt_recovery_{round_i}")
                    rec["steps"].append({"step": f"s08_prompt_recovery_{round_i}", "data": s08_recovery_res})
                    sleep_human(0.95)
                    s08_state_after = r.ev(S08_STATE_PROBE_JS, tag=f"s08_state_after_recovery_{round_i}")
                    rec["steps"].append({"step": f"s08_state_after_recovery_{round_i}", "data": s08_state_after})
                    rec["steps"].append(
                        {
                            "step": f"s08_prompt_recovery_assert_{round_i}",
                            "data": _s08_prompt_recovery_summary(s08_state_before, s08_state_after),
                        }
                    )
                    skip_primary_click = True
                    s08_skip_reason = "s08_prompt_blocking"
            if skip_primary_click:
                click_res = {
                    "ok": False,
                    "skipped": True,
                    "reason": s08_skip_reason or "s08_prompt_blocking",
                    "recovery": s08_recovery_res,
                    "vm_prefill": s08_vm_prefill_res,
                    "flow_save": s08_flow_save_res,
                }
            else:
                if l3c == "S08_NAME_REG_GUIDE_BASE":
                    click_res = r.ev(S08_GUIDE_FLOWSAVE_JS, tag=f"s08_business_advance_{round_i}")
                else:
                    click_res = r.ev(CLICK_FIRST_PRIMARY, tag=f"click_primary_{round_i}")
            rec["steps"].append({"step": f"click_primary_round_{round_i}", "data": click_res})
            dialog_res = None
            if not skip_primary_click and (not isinstance(click_res, dict) or not click_res.get("ok")):
                dialog_res = r.ev(CLICK_DIALOG_PRIMARY, tag=f"click_dialog_{round_i}")
                rec["steps"].append({"step": f"click_dialog_fallback_{round_i}", "data": dialog_res})
            ok_click = bool(skip_primary_click) or (isinstance(click_res, dict) and click_res.get("ok")) or (
                isinstance(dialog_res, dict) and dialog_res.get("ok")
            )
            if ok_click:
                no_click_streak = 0
            else:
                no_click_streak += 1
                if no_click_streak in (2, 3, 4, 5):
                    recov = r.ev(CLICK_RECOVERY_STUCK_JS, tag=f"recovery_stuck_{round_i}")
                    rec["steps"].append({"step": f"recovery_stuck_js_{round_i}", "data": recov})
                    record_blocker_bundle(
                        rec,
                        r,
                        f"no_primary_streak_{no_click_streak}",
                        round_i=round_i,
                    )
                    if isinstance(recov, dict) and recov.get("ok"):
                        no_click_streak = max(0, no_click_streak - 2)
                if no_click_streak >= 6:
                    record_blocker_bundle(rec, r, "abort_streak_final", round_i=round_i)
                    rec["steps"].append(
                        {
                            "step": "abort_no_primary_button_streak",
                            "data": {"streak": no_click_streak, "last_probe": ep, "last_primary": click_res, "last_dialog": dialog_res},
                        }
                    )
                    break
            sleep_human(3.5)
            install_hook(r.raw)
            sleep_human(2.0)
            rec["steps"].append({"step": f"cap_round_{round_i}", "data": dump_cap(r.raw)})
            snap_d = snap(r.raw)
            rec["steps"].append({"step": f"snap_round_{round_i}", "data": snap_d})
            try:
                ui_b = r.ev(READ_BLOCKER_UI_JS, tag=f"read_ui_llm_obs_{round_i}")
                rec["llm_observations"].append(
                    build_llm_observation_v1(round_i, ep, snap_d, ui_b, click_res)
                )
            except Exception as e:
                rec["llm_observations"].append(
                    {"schema": "ufo.llm_observation.v1", "round": round_i, "error": repr(e)}
                )
            if round_i > 0 and round_i % 12 == 0:
                record_blocker_bundle(rec, r, "heartbeat_long_run", round_i=round_i)

        if not any(s.get("step") == "reached_yun_submit" for s in rec["steps"]):
            stop_reason = "max_primary_rounds_or_abort_streak"
            if any(s.get("step") == "abort_s08_stagnation_cap" for s in rec["steps"]):
                stop_reason = "abort_s08_stagnation_cap"
            rec["steps"].append(
                {
                    "step": "stopped_without_yun_submit",
                    "data": {
                        "reason": stop_reason,
                        "max_primary_rounds": max_primary_rounds,
                    },
                }
            )

        rec["steps"].append({"step": "final_snap", "data": snap(r.raw)})
        rec["steps"].append({"step": "final_cap", "data": dump_cap(r.raw)})
    except Exception as e:
        err = repr(e)
        rec["steps"].append({"step": "aborted_cdp_or_eval", "error": err})
        try:
            if r is not None:
                record_blocker_bundle(rec, r, "python_exception", round_i=None)
        except BaseException:
            pass
    finally:
        rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if err:
            rec["run_error"] = err
        rec.pop("_guide_autofill_s08_v2_done", None)
        rec["acceptance"] = build_acceptance(rec)
        rec["phase_verdict"] = compute_phase_verdict(rec)
        rec["task"] = finalize_task_model(rec)
        rec["framework_notes"] = synthesize_framework_notes(rec)
        out_main.parent.mkdir(parents=True, exist_ok=True)
        out_main.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {out_main}")
        if framework_md_path is not None:
            write_framework_rehearsal_md(rec, framework_md_path)
            print(f"Framework MD: {framework_md_path}")
        if also_write_iter_latest and out_main != OUT_ITER_LATEST:
            OUT_ITER_LATEST.parent.mkdir(parents=True, exist_ok=True)
            OUT_ITER_LATEST.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved: {OUT_ITER_LATEST}")
        if r is not None:
            try:
                r.close()
            except Exception:
                pass


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Portal -> 设立登记 -> 专区/名称子应用 -> 自动点主按钮，直到页面出现「云提交」文案停点；含 CDP 重连与 AC 验收"
    )
    ap.add_argument(
        "--entry",
        choices=("namenotice", "guide"),
        default="namenotice",
        help="门户入口：namenotice=declaration-instructions 回跳；guide=从 guide/base 回跳（全部服务截图）",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="JSON 输出路径，默认 packet_chain_portal_from_start.json",
    )
    ap.add_argument(
        "--iter-latest",
        action="store_true",
        help="额外写入 establish_iterate_latest.json 便于迭代对照",
    )
    ap.add_argument(
        "--assets",
        type=Path,
        default=None,
        help="附件映射 JSON（如 config/rehearsal_assets.json）；每轮尝试 CDP 注入 file 控件",
    )
    ap.add_argument(
        "--framework-md",
        type=Path,
        default=None,
        help="写入演练摘要 Markdown；默认 dashboard/data/records/framework_rehearsal_latest.md",
    )
    ap.add_argument(
        "--resume-current",
        action="store_true",
        help="不跳转门户：从当前 9087 icpsp-web-pc 页签直接装 hook 并进入主循环（用于已在 core 等页面续跑）",
    )
    ap.add_argument(
        "--human-fast",
        action="store_true",
        help="关闭类人节奏（默认按 config/human_pacing.json 乘子+抖动放慢，避免比真人快太多）",
    )
    ap.add_argument(
        "--require-listing-substr",
        type=str,
        default=None,
        metavar="STR",
        help="与 --resume-current 合用：若当前为我的办件列表页，则页面正文须含该字符串，否则立即中止（防空跑）",
    )
    ap.add_argument(
        "--phase1-only",
        action="store_true",
        help="仅第一阶段：导航/快照后停止，不进入直至云提交的主循环（名称核名须人工在浏览器完成）",
    )
    args = ap.parse_args()
    md_path = args.framework_md
    if md_path is None:
        md_path = ROOT / "dashboard" / "data" / "records" / "framework_rehearsal_latest.md"
    run(
        entry=args.entry,
        out_path=args.output,
        also_write_iter_latest=args.iter_latest,
        assets_path=args.assets,
        framework_md_path=md_path,
        resume_current=args.resume_current,
        human_fast=args.human_fast,
        require_listing_company_substr=args.require_listing_substr,
        phase1_only=bool(args.phase1_only),
    )
