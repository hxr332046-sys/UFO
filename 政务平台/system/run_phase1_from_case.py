#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一阶段（名称登记）——按 docs/case_*.json 尽量往下推：
企业专区 establish（市场主体类型 / 名称是否已申请 / 住所级联 → 下一步）→ 申报须知 → guide/base → 名称核查页，
并调用禁限用词 + 名称库查重（可走 icpsp-api），在名称核查 VM 上尽力执行 flowSave（保存下一步）。

**不能代替**：你在政务系统上的法定最终设立提交、验证码、实人核验；法律效力与材料真实性仍由你负责。

用法（政务平台根目录，且 Chrome Dev CDP 9225 已开）:
  python system/run_phase1_from_case.py
  python system/run_phase1_from_case.py --case docs/case_广西容县李陈梦.json
  python system/run_phase1_from_case.py --no-protocol   # 仅 CDP，不调后台核名接口

录制 icpsp-api 顺序链（便于收敛纯 HTTP 重放）:
  python system/phase1_recipe_cdp_record.py
  python system/phase1_recipe_replay_http.py --dry-run   # 默认不写请求；加 --execute 才 POST
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
import requests
import websocket

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "system") not in sys.path:
    sys.path.insert(0, str(ROOT / "system"))

from human_pacing import configure_human_pacing, sleep_human  # noqa: E402
from packet_chain_portal_from_start import (  # noqa: E402
    ACTIVE_FUC_ESTABLISH,
    CLICK_ESTABLISH_DOM,
    CLICK_FIRST_PRIMARY,
    CLICK_RECOVERY_STUCK_JS,
    GUIDE_BASE_AUTOFILL_V2,
    PORTAL_INDEX_PAGE,
    S08_GUIDE_FLOWSAVE_JS,
    S08_STATE_PROBE_JS,
    _build_s08_vm_prefill_js,
    _in_name_register_spa,
    _s08_needs_vm_prefill,
    run_s08_cascade_sequence,
)

HOST = "zhjg.scjdglj.gxzf.gov.cn:9087"
OUT_JSON = ROOT / "dashboard" / "data" / "records" / "run_phase1_from_case_latest.json"

try:
    from icpsp_api_client import ICPSPClient  # noqa: E402
except ImportError:
    ICPSPClient = None  # type: ignore


def pick_ws(prefer: str | None = None):
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    if prefer:
        for p in pages:
            if p.get("type") == "page" and prefer in (p.get("url") or ""):
                return p["webSocketDebuggerUrl"], p.get("url", "")
        return None, None
    for p in pages:
        if p.get("type") == "page" and HOST.split(":")[0] in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def pick_ws_wait(prefer: str | None = None, *, timeout_sec: float = 12.0, allow_fallback: bool = True):
    end = time.time() + max(0.5, timeout_sec)
    last = (None, None)
    while time.time() < end:
        ws_url, cur = pick_ws(prefer)
        last = (ws_url, cur)
        if ws_url:
            return ws_url, cur
        if allow_fallback and prefer:
            ws_url, cur = pick_ws()
            last = (ws_url, cur)
            if ws_url:
                return ws_url, cur
        time.sleep(0.8)
    return last


def _need_ws_or_exit(rec: dict, ws_url: str | None, current_url: str | None, *, error_code: str, step: str) -> str | None:
    if ws_url:
        return ws_url
    rec["error"] = error_code
    rec["steps"].append({"step": step, "data": {"ok": False, "msg": error_code, "href": current_url}})
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT_JSON}")
    print(f"ERROR: {error_code}")
    return None


def ev(ws_url: str, expr: str, timeout_ms: int = 90000):
    wall = max(20, timeout_ms / 1000 + 15)
    ws = websocket.create_connection(ws_url, timeout=25)
    ws.settimeout(2.0)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout_ms},
                }
            )
        )
        deadline = time.time() + wall
        while time.time() < deadline:
            try:
                m = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                continue
            if m.get("id") == 1:
                return ((m.get("result") or {}).get("result") or {}).get("value")
        return {"__ev_timeout": True, "wall": wall}
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _derive_name_mark(company_full: str) -> str:
    """拟设全称中取字号：去掉常见尾巴后取中间最短合理段（≤10 汉字）；失败则用前四字。"""
    s = (company_full or "").strip()
    for suf in ("有限公司", "股份有限公司", "有限责任公司", "个人独资", "工作室", "中心"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    s = s.strip()
    if len(s) > 10:
        return s[:10]
    if not s:
        return "字号"
    return s


def _resolve_name_mark(case: dict) -> str:
    m = str(case.get("name_mark") or "").strip()
    if m:
        return m[:10]
    return _derive_name_mark(str(case.get("company_name_full") or ""))


def _explain_repeat_mini(resp: dict) -> dict:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    busi = data.get("busiData") if isinstance(data.get("busiData"), dict) else {}
    hits = busi.get("checkResult") if isinstance(busi.get("checkResult"), list) else []
    top = hits[0] if hits else {}
    return {
        "code": resp.get("code"),
        "checkState": busi.get("checkState"),
        "langStateCode": busi.get("langStateCode"),
        "top_remark": top.get("remark") if isinstance(top, dict) else None,
        "hit_count": len(hits),
    }


def _explain_banned_mini(resp: dict) -> dict:
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    busi = data.get("busiData") if isinstance(data.get("busiData"), dict) else {}
    return {
        "code": resp.get("code"),
        "success": busi.get("success"),
        "tipStr": busi.get("tipStr"),
    }


def run_protocol_probe(case: dict) -> dict:
    """
    逆向前端：bannedLexiconCalibration + nameCheckRepeat（需 runtime_auth_headers / mitm / cdp watch 之一有 32 位 Authorization）。
    名称与组织形式尽量与 case 一致；个人独资默认组织形式「厂」，与截图路径一致时可与全称中的「有限公司」并存为两路资料，以 case 为准。
    """
    out: dict = {"ok": False, "error": None, "bannedLexiconCalibration": None, "nameCheckRepeat": None}
    if ICPSPClient is None:
        out["error"] = "icpsp_api_client unavailable"
        return out
    ent = str(case.get("entType_default") or "1100").strip()
    name_mark = _resolve_name_mark(case)
    name_pre = str(case.get("phase1_name_pre") or "广西").strip()
    ind_spec = str(case.get("phase1_industry_special") or "软件开发").strip()
    organize = str(case.get("phase1_organize") or (("厂" if ent == "4540" else "有限公司"))).strip()
    full_name = str(case.get("phase1_check_name") or "").strip()
    if not full_name:
        full_name = f"{name_pre}{name_mark}{ind_spec}{organize}"
    dist_codes = case.get("phase1_dist_codes")
    dist_code = "450921"
    if isinstance(dist_codes, list) and dist_codes:
        dist_code = str(dist_codes[-1])
    busi_repeat = str(case.get("phase1_protocol_busi_type") or "01").strip()
    industry_code = str(case.get("phase1_industry_code") or "7329").strip()
    try:
        c = ICPSPClient()
        banned = c.get_json(
            "/icpsp-api/v4/pc/register/verifidata/bannedLexiconCalibration",
            {"nameMark": name_mark},
        )
        out["bannedLexiconCalibration"] = {"raw": banned, "explain": _explain_banned_mini(banned)}
        repeat_body = {
            "condition": "1",
            "busiId": None,
            "busiType": busi_repeat,
            "entType": ent,
            "name": full_name,
            "namePre": name_pre,
            "nameMark": name_mark,
            "distCode": dist_code,
            "areaCode": dist_code,
            "organize": organize,
            "industry": industry_code,
            "indSpec": ind_spec,
            "hasParent": None,
            "jtParentEntName": "",
        }
        repeat = c.post_json("/icpsp-api/v4/pc/register/name/component/NameCheckInfo/nameCheckRepeat", repeat_body)
        out["nameCheckRepeat"] = {"request": repeat_body, "raw": repeat, "explain": _explain_repeat_mini(repeat)}
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)
    return out


def enterprise_zone_establish_js(ent_code: str, dist_codes: list[str]) -> str:
    """portal enterprise-zone：`establish` 选类型 + 未申请 + 级联 + nextBtn。"""
    dc = json.dumps(dist_codes, ensure_ascii=False)
    ec = json.dumps(ent_code, ensure_ascii=False)
    # dc/ec 已是合法 JSON 字面量，可直接嵌入脚本（勿在 r""" 内再写 """，否则会截断字符串）
    return f"""(function(){{
  var DC = {dc};
  var ENT = {ec};
  function findComp(vm,name,d){{if(!vm||d>20)return null;var n=vm.$options?.name||'';if(n===name)return vm;for(var i=0;i<(vm.$children||[]).length;i++){{var r=findComp(vm.$children[i],name,d+1);if(r)return r}}return null}}
  function findCas(vm,d){{
    if(!vm||d>18)return null;
    var nm=vm.$options?.name||'';
    if(nm==='ElCascader'||nm==='tne-data-picker')return vm;
    for(var c of (vm.$children||[])){{var r=findCas(c,d+1);if(r)return r;}}
    return null;
  }}
  var app=document.getElementById('app'); var root=app&&app.__vue__;
  if(!root)return {{ok:false,msg:'no_root'}};
  var est=findComp(root,'establish',0);
  if(!est)return {{ok:false,msg:'no_establish'}};
  try{{ est.$set(est.$data,'radioGroup',ENT); }}catch(e){{}}
  if(typeof est.checkchange==='function'){{
    try{{ est.checkchange(ENT,true); }}catch(e){{}}
  }}
  var nodes=[...document.querySelectorAll('label,span,div,button,.el-radio,.el-radio__label')].filter(function(n){{return n.offsetParent!==null;}});
  var nameClick=null;
  for(var i=0;i<nodes.length;i++){{
    var t=(nodes[i].textContent||'').replace(/\\s+/g,' ').trim();
    if(t==='未申请'||(t.indexOf('未申请')>=0&&t.length<24)){{ nodes[i].click(); nameClick=t; break; }}
  }}
  var cas=findCas(est,0);
  if(cas){{
    try{{ cas.$emit('input',DC); cas.$emit('change',DC); }}catch(e){{}}
    try{{
      if(cas.$data){{
        cas.$set(cas.$data,'presentText','');
        cas.$set(cas.$data,'selectedLabel','');
      }}
    }}catch(e){{}}
  }}
  if(typeof est.nextBtn==='function'){{
    try{{
      est.nextBtn();
      return {{ok:true,via:'nextBtn',nameClick:nameClick,dc:DC,ent:ENT}};
    }}catch(e){{
      return {{ok:false,via:'nextBtn_err',err:String(e),nameClick:nameClick}};
    }}
  }}
  var b=[...document.querySelectorAll('button,.el-button')].find(function(x){{
    return x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled;
  }});
  if(b){{ b.click(); return {{ok:true,via:'dom_next',nameClick:nameClick,dc:DC}}; }}
  return {{ok:false,msg:'no_next',nameClick:nameClick}};
}})()"""


def build_namecheck_fill_js(case: dict, name_mark: str, dist_codes: list) -> str:
    """名称核查页：与 main() 中逻辑一致，供 CDP 录制脚本等复用。"""
    nm_lit = json.dumps(name_mark, ensure_ascii=False)
    ind_lit = json.dumps(str(case.get("phase1_industry_special") or "软件开发"), ensure_ascii=False)
    ind_code_lit = json.dumps(str(case.get("phase1_industry_code") or "7329"), ensure_ascii=False)
    mbd_lit = json.dumps(str(case.get("phase1_main_business_desc") or "软件开发"), ensure_ascii=False)
    dc_tail = json.dumps(str(dist_codes[-1]) if dist_codes else "450921", ensure_ascii=False)
    return (
        r"""(async function(){
          function walk(vm,d,pred){if(!vm||d>25)return null;if(pred(vm))return vm;for(var ch of (vm.$children||[])){var r=walk(ch,d+1,pred);if(r)return r;}return null;}
          var app=document.getElementById('app'); var root=app&&app.__vue__;
          if(!root) return {ok:false,msg:'no_root'};
          var indexVm=walk(root,0,function(v){var n=(v.$options&&v.$options.name)||'';return n==='index' && v.$parent && v.$parent.$options && v.$parent.$options.name==='name-check-info';});
          var indVm=walk(root,0,function(v){return (v.$options&&v.$options.name)==='tni-industry-select';});
          var orgVm=walk(root,0,function(v){return (v.$options&&v.$options.name)==='organization-select';});
          if(!indexVm) return {ok:false,msg:'no_index_namecheck',href:location.href};
          var trace=[];
          indexVm.formInfo=indexVm.formInfo||{};
          indexVm.$set(indexVm.formInfo,'nameMark',"""
        + nm_lit
        + r""");
          var indSpec = """
        + ind_lit
        + r""";
          indexVm.$set(indexVm.formInfo,'industrySpecial',indSpec);
          indexVm.$set(indexVm.formInfo,'allIndKeyWord',indSpec.length>6?indSpec.slice(0,6):indSpec);
          indexVm.$set(indexVm.formInfo,'showKeyWord',indSpec);
          indexVm.$set(indexVm.formInfo,'mainBusinessDesc',"""
        + mbd_lit
        + r""");
          trace.push('set_nameMark_case');
          if(!indexVm.formInfo.distCode){ indexVm.$set(indexVm.formInfo,'distCode',"""
        + dc_tail
        + r"""); trace.push('dist_fallback'); }
          if(!indexVm.formInfo.streetCode){ indexVm.$set(indexVm.formInfo,'streetCode',"""
        + dc_tail
        + r"""); trace.push('street_fallback'); }
          if(orgVm){
            var gl = orgVm.groupList || [];
            var picked = Array.isArray(gl) && gl.length ? gl[0] : null;
            try{ if(picked&&typeof orgVm.radioChange==='function') orgVm.radioChange(picked); trace.push('org_radio'); }catch(e){ trace.push('org_err'); }
          }
          if(!indexVm.formInfo.organize) indexVm.$set(indexVm.formInfo,'organize','01');
          if(indVm){
            try{ if(typeof indVm.show==='function') indVm.show(); if(typeof indVm.renderList==='function') await indVm.renderList(); }catch(e){}
            var list = indVm.industryList || [];
            var want = """
        + ind_code_lit
        + r""";
            var hit = Array.isArray(list) ? list.find(function(x){ return String(x.value||x.code||x.id||'')===want; }) : null;
            var first = hit || (Array.isArray(list) && list.length ? list[0] : null);
            if(first){
              try{ if(typeof indVm.handleSelect==='function') indVm.handleSelect(first); }catch(e){}
              indexVm.$set(indexVm.formInfo,'industry',first.value||first.code||first.id||"""
        + ind_code_lit
        + r""");
              indexVm.$set(indexVm.formInfo,'industryName',first.label||first.name||'');
            } else {
              indexVm.$set(indexVm.formInfo,'industry',"""
        + ind_code_lit
        + r""");
              indexVm.$set(indexVm.formInfo,'industryName','软件开发');
            }
          } else {
            indexVm.$set(indexVm.formInfo,'industry',"""
        + ind_code_lit
        + r""");
            indexVm.$set(indexVm.formInfo,'industryName','软件开发');
          }
          indexVm.$set(indexVm.formInfo,'isCheckBox','Y');
          indexVm.$set(indexVm.formInfo,'declarationMode','Y');
          try{
            var rad=[...document.querySelectorAll('input[type=radio][name],.el-radio input')].find(function(r){
              return r&&r.offsetParent!==null&&String(r.value)==='10';
            });
            if(rad&&!rad.checked){ rad.click(); trace.push('name_struct_10'); }
          }catch(e){ trace.push(['name_struct_err',String(e)]); }
          try{
            if(typeof indexVm.nameCheckRepeat==='function'){
              var r1=indexVm.nameCheckRepeat();
              if(r1&&typeof r1.then==='function') r1=await r1;
              trace.push(['nameCheckRepeat',String(r1&&r1.code||r1)]);
            }
          }catch(e){ trace.push(['nameCheckRepeat_err',String(e)]); }
          try{
            if(typeof indexVm.getFormPromise==='function'){
              var gp=indexVm.getFormPromise();
              if(gp&&typeof gp.then==='function'){ await gp; trace.push('getFormPromise_ok'); }
            }
          }catch(e){ trace.push(['getFormPromise_err',String(e)]); }
          try{
            var agree=[...document.querySelectorAll('label,span,div,.el-checkbox')].find(function(x){
              return x.offsetParent!==null&&(x.textContent||'').indexOf('我已阅读并同意')>=0&&(x.textContent||'').indexOf('名称登记自主申报须知')>=0;
            });
            if(agree){
              agree.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
              trace.push('dom_click_agree_notice');
            }
          }catch(e){ trace.push(['agree_click_err',String(e)]); }
          try{
            var okDlg=[...document.querySelectorAll('button,.el-button')].find(function(x){
              return x.offsetParent!==null&&!x.disabled&&(x.textContent||'').replace(/\\s+/g,'').indexOf('确定')>=0;
            });
            if(okDlg){ okDlg.click(); trace.push('click_ok_dialog'); }
          }catch(e){ trace.push(['ok_dialog_err',String(e)]); }
          try{
            var saveBtn=[...document.querySelectorAll('button,.el-button')].find(function(x){
              return x.offsetParent!==null&&!x.disabled&&(x.textContent||'').replace(/\\s+/g,'').indexOf('保存并下一步')>=0;
            });
            if(saveBtn){
              saveBtn.click();
              trace.push('click_save_and_next');
            } else if(typeof indexVm.flowSave==='function'){
              var r2=indexVm.flowSave();
              if(r2&&typeof r2.then==='function') r2=await r2;
              trace.push(['flowSave_fallback',String(r2&&r2.code!==undefined?r2.code:r2)]);
            } else { trace.push('no_save_btn_no_flowSave'); }
          }catch(e){ trace.push(['save_next_err',String(e)]); }
          var errs=[...document.querySelectorAll('.el-form-item__error,.el-message,.el-message__content')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean).slice(0,12);
          return {ok:true,trace:trace,errors:errs,nameMark:indexVm.formInfo.nameMark,href:location.href};
        })()"""
    )


def _build_phase1_guide_seed(case: dict, dist_codes: list[str]) -> dict:
    region_text = str(case.get("region_text") or "").strip()
    address_full = str(case.get("address_full") or "").strip()
    dist_code = str(dist_codes[-1]) if dist_codes else ""
    district_name = region_text.replace("广西壮族自治区", "").replace("广西", "").strip()
    detail = address_full
    for prefix in ("广西壮族自治区", "广西", "玉林市"):
        if prefix and detail.startswith(prefix):
            detail = detail[len(prefix) :].strip()
    if district_name and detail.startswith(district_name):
        detail = detail[len(district_name) :].strip()
    if not detail:
        detail = address_full
    path_texts: list[str] = []
    if dist_codes:
        path_texts.append("广西壮族自治区")
    if len(dist_codes) >= 2:
        path_texts.append("玉林市")
    if len(dist_codes) >= 3:
        path_texts.append(district_name or dist_code)
    while len(path_texts) < len(dist_codes):
        path_texts.append(str(dist_codes[len(path_texts)]))
    address_value = district_name or region_text or address_full
    return {
        "distCode": dist_code,
        "streetCode": dist_code,
        "streetName": address_value,
        "address": address_value,
        "detAddress": detail,
        "nameCode": "0",
        "isnameType": "0",
        "formChoiceName": "0",
        "havaAdress": "1",
        "distCodePath": [str(x) for x in dist_codes],
        "distPathTexts": path_texts,
    }


class _Phase1GuideRunner:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url

    def ev(self, expr: str, timeout_ms: int = 120000, tag: str | None = None):
        return ev(self.ws_url, expr, timeout_ms=timeout_ms)


def _advance_guide_base_phase1(ws_url: str, rec: dict, guide_seed: dict, rounds: int = 4) -> dict:
    runner = _Phase1GuideRunner(ws_url)
    last_state = None
    total_rounds = max(1, rounds)
    for round_i in range(total_rounds):
        state_before = runner.ev(S08_STATE_PROBE_JS, timeout_ms=90000, tag=f"phase1_s08_state_before_{round_i}")
        rec["steps"].append({"step": f"phase1_s08_state_before_{round_i}", "data": state_before})
        gfill = runner.ev(GUIDE_BASE_AUTOFILL_V2, timeout_ms=90000, tag=f"phase1_guide_base_autofill_v2_{round_i}")
        rec["steps"].append({"step": f"phase1_guide_base_autofill_v2_{round_i}", "data": gfill})
        sleep_human(0.65)
        if round_i == 0 or _s08_needs_vm_prefill(state_before):
            run_s08_cascade_sequence(
                runner,
                rec,
                f"phase1_guide_{round_i}",
                dist_path_texts=(
                    (guide_seed.get("distPathTexts") if isinstance(guide_seed, dict) else None) or []
                )[1:4],
            )
        if _s08_needs_vm_prefill(state_before):
            vm_prefill = runner.ev(_build_s08_vm_prefill_js(guide_seed), timeout_ms=120000, tag=f"phase1_s08_vm_prefill_{round_i}")
            rec["steps"].append({"step": f"phase1_s08_vm_prefill_{round_i}", "data": vm_prefill})
            sleep_human(0.85)
        if isinstance(state_before, dict) and (
            state_before.get("hasNamePrompt")
            or state_before.get("hasQualificationPrompt")
            or state_before.get("ghostDialogState")
        ):
            recovery = runner.ev(CLICK_RECOVERY_STUCK_JS, timeout_ms=90000, tag=f"phase1_s08_prompt_recovery_{round_i}")
            rec["steps"].append({"step": f"phase1_s08_prompt_recovery_{round_i}", "data": recovery})
            sleep_human(0.95)
        flow = runner.ev(S08_GUIDE_FLOWSAVE_JS, timeout_ms=120000, tag=f"phase1_s08_flow_save_{round_i}")
        rec["steps"].append({"step": f"phase1_s08_flow_save_{round_i}", "data": flow})
        sleep_human(1.25)
        state_after = runner.ev(S08_STATE_PROBE_JS, timeout_ms=90000, tag=f"phase1_s08_state_after_{round_i}")
        rec["steps"].append({"step": f"phase1_s08_state_after_{round_i}", "data": state_after})
        last_state = state_after
        href_after = str((state_after or {}).get("href") or "") if isinstance(state_after, dict) else ""
        if _is_phase1_progress_href(href_after):
            return {"ok": True, "round": round_i, "state": state_after}
        if href_after and ("space-index" in href_after or "my-space" in href_after):
            return {"ok": False, "msg": "diverted_to_my_space", "round": round_i, "state": state_after}
    return {"ok": False, "rounds": total_rounds, "state": last_state}


def _is_phase1_progress_href(href: str | None) -> bool:
    hs = str(href or "")
    return "core.html" in hs or ("name-register.html" in hs and "guide/base" not in hs)


def _recover_from_my_space(ws_url: str, rec: dict, target_ent_type: str, target_busi_type: str) -> tuple[str | None, str | None]:
    """
    若被导流到 my-space，自动点击“继续办理”并尽量解析 operate 返回 route 直达 core。
    返回: (ws_url, href)
    """
    te = json.dumps(str(target_ent_type or "").strip(), ensure_ascii=False)
    tb = json.dumps(str(target_busi_type or "").strip(), ensure_ascii=False)
    click_resume_js = (
        r"""(async function(){
      function clean(s){return String(s||'').replace(/\s+/g,' ').trim();}
      function isVis(el){return !!(el && el.offsetParent!==null && !el.disabled);}
      var TARGET_ENT = """
        + te
        + r""";
      var TARGET_BUSI = """
        + tb
        + r""";
      function parseRouteText(t){
        if(!t) return null;
        try{
          var j=JSON.parse(t);
          var d=(j&&j.data&&j.data.busiData)||{};
          if(d.route){
            if(typeof d.route==='string'){ try{return JSON.parse(d.route);}catch(e){} }
            if(typeof d.route==='object') return d.route;
          }
        }catch(e){}
        return null;
      }
      function buildRouteUrl(route){
        if(!route||!route.project||!route.path) return '';
        var base='https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/'+route.project+'.html#'+route.path;
        var p=route.params||{};
        var q=Object.keys(p).map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(String(p[k]===undefined?'':p[k]));}).join('&');
        return q ? (base+'?'+q) : base;
      }
      var cap={resps:[]};
      var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open=function(m,u){this.__u=u; return oo.apply(this,arguments);};
      XMLHttpRequest.prototype.send=function(b){
        var self=this;
        self.addEventListener('loadend', function(){
          var u=String(self.__u||'');
          if(u.indexOf('/mattermanager/matters/operate')>=0){
            cap.resps.push({u:u,s:self.status,t:String(self.responseText||'').slice(0,8000)});
          }
        });
        return os.apply(this,arguments);
      };
      try{
        var rows=[].slice.call(document.querySelectorAll('tbody tr,.el-table__row')).filter(isVis).filter(function(r){
          return clean(r.innerText||'').indexOf('继续办理')>=0;
        });
        if(!rows.length) return {ok:false,msg:'no_continue_row'};
        var attempts=[];
        var picked=null, pickedUrl='', pickedRoute=null;
        for(var i=0;i<rows.length;i++){
          var row=rows[i];
          var rowText=clean(row.innerText||'');
          var btn=[].slice.call(row.querySelectorAll('button,.el-button,a,span')).find(function(x){return isVis(x)&&clean(x.textContent).indexOf('继续办理')>=0;});
          if(!btn){
            attempts.push({idx:i,row:rowText.slice(0,180),skip:'no_btn'});
            continue;
          }
          var before=cap.resps.length;
          btn.click();
          await new Promise(function(r){setTimeout(r,2600);});
          var newResps=cap.resps.slice(before);
          var route=null;
          for(var k=0;k<newResps.length;k++){
            route=parseRouteText(newResps[k].t||'');
            if(route) break;
          }
          var entType=((route&&route.params&&route.params.entType)||'')+'';
          var busiType=((route&&route.params&&route.params.busiType)||'')+'';
          var matched=!!(route && entType===TARGET_ENT && busiType===TARGET_BUSI);
          attempts.push({idx:i,row:rowText.slice(0,180),resp:newResps.length,entType:entType,busiType:busiType,matched:matched});
          if(matched){
            picked=rowText;
            pickedRoute=route;
            pickedUrl=buildRouteUrl(route);
            break;
          }
        }
        if(!pickedRoute){
          return {ok:false,msg:'no_target_route',target:{entType:TARGET_ENT,busiType:TARGET_BUSI},attempts:attempts,captures:cap.resps.length};
        }
        if(pickedUrl){ location.href=pickedUrl; }
        return {ok:true,reason:'target_route',row:String(picked||'').slice(0,200),route:pickedRoute,url:pickedUrl,captures:cap.resps.length,attempts:attempts};
      } finally {
        XMLHttpRequest.prototype.open=oo;
        XMLHttpRequest.prototype.send=os;
      }
    })()"""
    )
    resume = ev(ws_url, click_resume_js, timeout_ms=120000)
    rec["steps"].append({"step": "my_space_resume_continue", "data": resume})
    sleep_human(4.0)
    ws2, href2 = pick_ws_wait(timeout_sec=12.0)
    rec["steps"].append({"step": "my_space_resume_after", "data": {"href": href2}})
    return ws2, href2


def main() -> int:
    ap = argparse.ArgumentParser(description="第一阶段：按 case 驱动名称登记链路至名称查重（不代最终提交）")
    ap.add_argument("--case", type=Path, default=ROOT / "docs" / "case_广西容县李陈梦.json")
    ap.add_argument("--human-fast", action="store_true", help="仅调试：缩短类人间隔")
    ap.add_argument("--no-protocol", action="store_true", help="跳过 icpsp-api 禁限用词+查重探针")
    args = ap.parse_args()

    configure_human_pacing(ROOT / "config" / "human_pacing.json", fast=bool(args.human_fast))

    if not args.case.is_file():
        print("ERROR: case 文件不存在:", args.case)
        return 2

    case = json.loads(args.case.read_text(encoding="utf-8"))
    company_full = str(case.get("company_name_full") or "").strip()
    busi = str(case.get("busiType_default") or "02_4").strip()
    ent = str(case.get("entType_default") or "1100").strip()
    name_mark = _resolve_name_mark(case)
    dist_codes = case.get("phase1_dist_codes")
    if not isinstance(dist_codes, list) or len(dist_codes) < 3:
        dist_codes = ["450000", "450900", "450921"]

    print("=== 第一阶段（按案例推进）===")
    print("  company_name_full:", company_full)
    print("  字号 nameMark:", name_mark)
    print("  busiType:", busi, " entType:", ent)
    print("  phase1 级联 dist:", dist_codes)

    proto = None if args.no_protocol else run_protocol_probe(case)
    if proto:
        print("  协议探针:", "ok" if proto.get("ok") else proto.get("error", "fail"))
        if proto.get("nameCheckRepeat"):
            expl = (proto.get("nameCheckRepeat") or {}).get("explain") or {}
            print("    nameCheckRepeat 摘要:", expl)

    ws, cur = pick_ws_wait(timeout_sec=8.0, allow_fallback=False)
    rec: dict = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "case_path": str(args.case),
        "steps": [],
        "protocol_probe": proto,
    }
    if not ws:
        rec["error"] = "no_cdp_page"
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ERROR: 无 9087 页签；请先 python scripts/launch_browser.py")
        return 2
    rec["steps"].append({"step": "start", "url": cur})

    URL_ENTERPRISE = (
        f"https://{HOST}/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone"
        f"?fromProject=portal&fromPage=%2Findex%2Fpage&busiType={busi}&merge=Y"
    )
    URL_DECL = (
        f"https://{HOST}/icpsp-web-pc/name-register.html#/namenotice/declaration-instructions"
        f"?fromProject=portal&fromPage=%2Findex%2Fenterprise%2Fenterprise-zone&entType={ent}&busiType={busi}"
    )
    URL_GUIDE = (
        f"https://{HOST}/icpsp-web-pc/name-register.html#/guide/base"
        f"?busiType={busi}&entType={ent}&marPrId=&marUniscId="
    )

    rec["steps"].append({"step": "portal_index_page", "data": PORTAL_INDEX_PAGE})
    ev(ws, f"location.href={json.dumps(PORTAL_INDEX_PAGE)}", timeout_ms=60000)
    sleep_human(6.0)
    active_establish = ev(ws, ACTIVE_FUC_ESTABLISH, timeout_ms=90000)
    rec["steps"].append({"step": "try_activefuc_establish", "data": active_establish})
    sleep_human(2.2)
    href_now = ev(ws, r"""(function(){return location.href;})()""", timeout_ms=15000)
    if not (isinstance(href_now, str) and ("enterprise-zone" in href_now or _in_name_register_spa(href_now))):
        fallback_establish = ev(ws, CLICK_ESTABLISH_DOM, timeout_ms=90000)
        rec["steps"].append({"step": "fallback_dom_click_establish", "data": fallback_establish})
        sleep_human(2.0)

    ws_zone, zone_cur = pick_ws_wait("enterprise-zone", timeout_sec=10.0, allow_fallback=False)
    if ws_zone and isinstance(zone_cur, str) and "enterprise-zone" in zone_cur:
        ws = ws_zone
        rec["steps"].append({"step": "enterprise_zone", "note": "portal_establish"})
        ez = ev(ws, enterprise_zone_establish_js(ent, [str(x) for x in dist_codes]), timeout_ms=90000)
        rec["steps"].append({"step": "enterprise_zone_establish_wizard", "data": ez})
        sleep_human(1.6)
        clicked = ev(ws, CLICK_FIRST_PRIMARY, timeout_ms=90000)
        rec["steps"].append({"step": "click_start_banli", "data": clicked})
        sleep_human(3.0)

    ws, ws_cur = pick_ws_wait("name-register.html", timeout_sec=15.0, allow_fallback=False)
    if not ws:
        ws_nav, _ = pick_ws_wait(timeout_sec=8.0)
        if ws_nav:
            ws = ws_nav
        # 有些场景不会自动弹出 name-register 页签，回退到显式导航后再重试。
        rec["steps"].append(
            {
                "step": "name_register_fallback_nav",
                "data": ev(ws, f"location.href={json.dumps(URL_DECL)}", timeout_ms=60000) if ws else {"ok": False, "msg": "no_cdp_page_for_fallback_nav"},
            }
        )
        sleep_human(6.0)
        ws, ws_cur = pick_ws_wait("name-register.html", timeout_sec=15.0, allow_fallback=False)
    ws = _need_ws_or_exit(rec, ws, ws_cur, error_code="name_register_tab_missing", step="name_register_pick")
    if not ws:
        return 2
    href_now = str(ws_cur or "")
    rec["steps"].append({"step": "name_register_entry", "data": {"href": href_now}})

    declaration_click_js = r"""(function(){
      function txt(e){ return (e && e.textContent || '').replace(/\s+/g,' ').trim(); }
      var btns=[...document.querySelectorAll('button,.el-button')].filter(function(b){
        return b && b.offsetParent!==null && !b.disabled;
      });
      // 1) 显式优先「我已阅读并同意」
      var agree=btns.find(function(b){ var t=txt(b); return t.indexOf('我已阅读并同意')>=0 || t.indexOf('同意并继续')>=0; });
      if(agree){ agree.click(); return {ok:true,mode:'agree',text:txt(agree)}; }
      // 2) 其次点「下一步/继续/确定」，显式排除「不同意」
      var next=btns.find(function(b){
        var t=txt(b);
        if(!t) return false;
        if(t.indexOf('不同意')>=0) return false;
        return t.indexOf('下一步')>=0 || t.indexOf('继续')>=0 || t==='确定';
      });
      if(next){ next.click(); return {ok:true,mode:'next_like',text:txt(next)}; }
      // 3) 最后兜底：若只有「不同意」可见，不自动点，交给人工。
      var reject=btns.find(function(b){ return txt(b).indexOf('不同意')>=0; });
      if(reject){ return {ok:false,mode:'reject_only_visible',text:txt(reject)}; }
      return {ok:false,mode:'no_target_button'};
    })()"""

    if "declaration-instructions" in href_now:
        rec["steps"].append({"step": "declaration_instructions", "note": "native_nav"})
        decl_click = ev(ws, declaration_click_js, timeout_ms=90000)
        rec["steps"].append({"step": "declaration_primary", "data": decl_click})
        sleep_human(2.6)
    elif "guide/base" not in href_now:
        rec["steps"].append(
            {
                "step": "declaration_fallback_nav",
                "data": ev(ws, f"location.href={json.dumps(URL_DECL)}", timeout_ms=60000),
            }
        )
        sleep_human(6.0)
        ws, ws_cur = pick_ws_wait("declaration-instructions", timeout_sec=12.0, allow_fallback=False)
        ws = _need_ws_or_exit(rec, ws, ws_cur, error_code="declaration_tab_missing", step="declaration_pick")
        if not ws:
            return 2
        rec["steps"].append({"step": "declaration_instructions", "note": "fallback_nav"})
        decl_click = ev(ws, declaration_click_js, timeout_ms=90000)
        rec["steps"].append({"step": "declaration_primary", "data": decl_click})
        sleep_human(2.6)

    guide_pick_ws, guide_pick_cur = pick_ws_wait("guide/base", timeout_sec=15.0, allow_fallback=False)
    if not guide_pick_ws:
        rec["steps"].append(
            {
                "step": "guide_fallback_nav",
                "data": ev(ws, f"location.href={json.dumps(URL_GUIDE)}", timeout_ms=60000),
            }
        )
        sleep_human(6.0)
        guide_pick_ws, guide_pick_cur = pick_ws_wait("guide/base", timeout_sec=15.0, allow_fallback=False)
    ws = _need_ws_or_exit(rec, guide_pick_ws, guide_pick_cur, error_code="guide_base_tab_missing", step="guide_base_pick")
    if not ws:
        return 2
    rec["steps"].append({"step": "guide_base", "note": "nav"})
    guide_seed = _build_phase1_guide_seed(case, dist_codes)
    guide_click = ev(
        ws,
        r"""(function(){
          var els=[...document.querySelectorAll('label,span,div,li,a')].filter(e=>e.offsetParent!==null);
          for(var e of els){
            var t=(e.textContent||'').replace(/\s+/g,' ').trim();
            if(t.indexOf('未办理企业名称预保留')>=0){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return 'picked_unreserved';}
          }
          var n=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&(x.textContent||'').indexOf('下一步')>=0&&!x.disabled);
          if(n){n.click();return 'next';}
          var ok=[...document.querySelectorAll('button,.el-button')].find(x=>x.offsetParent!==null&&((x.textContent||'').replace(/\s+/g,'').indexOf('确定')>=0)&&!x.disabled);
          if(ok){ok.click();return 'ok';}
          return 'no_click';
        })()""",
    )
    rec["steps"].append({"step": "guide_base_click", "data": guide_click})
    sleep_human(1.8)
    guide_advance = _advance_guide_base_phase1(ws, rec, guide_seed, rounds=4)
    rec["steps"].append({"step": "guide_base_advance_phase1", "data": guide_advance})
    sleep_human(2.2)

    ws, href_now = pick_ws_wait(timeout_sec=8.0)
    ws = _need_ws_or_exit(rec, ws, href_now, error_code="post_guide_tab_missing", step="after_guide_pick")
    if not ws:
        return 2
    snap = ev(
        ws,
        r"""(function(){return {href:location.href,hash:location.hash,text:(document.body.innerText||'').slice(0,400)};})()""",
    )
    rec["steps"].append({"step": "after_guide_snapshot", "data": snap})
    href_after_guide = str((snap or {}).get("href") or "")
    if "my-space" in href_after_guide or "space-index" in href_after_guide:
        ws2, href2 = _recover_from_my_space(ws, rec, target_ent_type=ent, target_busi_type=busi)
        if ws2:
            ws = ws2
        # 若已经进入 core 基础页，尝试直达名称核查页
        if isinstance(href2, str) and "core.html#/flow/base" in href2:
            to_namecheck = ev(
                ws,
                f"location.href={json.dumps(f'https://{HOST}/icpsp-web-pc/core.html#/flow/base/name-check-info')}",
                timeout_ms=60000,
            )
            rec["steps"].append({"step": "core_force_to_namecheck", "data": to_namecheck})
            sleep_human(3.0)
            ws3, href3 = pick_ws_wait(timeout_sec=10.0)
            if ws3:
                ws = ws3
            rec["steps"].append({"step": "core_force_to_namecheck_after", "data": {"href": href3}})

    # 名称查重页：注入字号（案例推导）+ 行业/组织占位 + 尝试查重（与 fill_namecheck_industry_org 同源思路）
    fill_js = build_namecheck_fill_js(case, name_mark, dist_codes)
    fill: dict | None = None
    for attempt in range(3):
        ws, href_now = pick_ws_wait(timeout_sec=8.0)
        if not ws:
            fill = {"ok": False, "msg": "no_cdp_page_after_guide", "href": href_now}
            step_name = "namecheck_fill_attempt" if attempt == 0 else f"namecheck_fill_attempt_{attempt}"
            rec["steps"].append({"step": step_name, "data": fill})
            break
        fill = ev(ws, fill_js, timeout_ms=120000)
        step_name = "namecheck_fill_attempt" if attempt == 0 else f"namecheck_fill_attempt_{attempt}"
        rec["steps"].append({"step": step_name, "data": fill})
        if isinstance(fill, dict) and fill.get("ok"):
            break
        if not (isinstance(fill, dict) and fill.get("msg") == "no_index_namecheck"):
            break
        guide_ws, _ = pick_ws_wait("guide/base", timeout_sec=10.0, allow_fallback=False)
        if not guide_ws:
            break
        guide_retry = _advance_guide_base_phase1(guide_ws, rec, guide_seed, rounds=2)
        rec["steps"].append({"step": f"guide_base_retry_after_fill_{attempt}", "data": guide_retry})
        sleep_human(1.8)

    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["note"] = (
        "已尽力：企业专区 establish、名称核查 nameCheckRepeat+flowSave（若 VM 可用）。"
        "行政区划下拉若需人工补选，请以页面为准；法定设立提交不在本脚本范围。"
    )
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT_JSON}")
    print("=== 完成（自动化已尽力推送；请在本机 Chrome 继续人工确认与提交）===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
