#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NameCheckInfo 门票页自动化框架（02_4 / entType=4540）

覆盖交互：
- 行政区划（下拉搜索/选择）
- 字号（输入 + 禁限用词弹窗处理）
- 行业/经营特点（关键词输入 → 选择带编号的候选项）
- 组织形式（下拉/网格选择）
- 勾选须知 → 保存并下一步

设计目标：
- 交互优先（模拟真实点击/选择），必要时 fallback 直接写 indexVm.formInfo
- 记录证据到 dashboard/data/records
"""

import json
import time
from pathlib import Path

import requests
import websocket

OUT = Path("G:/UFO/政务平台/dashboard/data/records/namecheck_ticket_runner.json")
URL_NAMECHECK = "https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/core.html#/flow/base/name-check-info"


def pick_ws():
    pages = requests.get("http://127.0.0.1:9225/json", timeout=5).json()
    for p in pages:
        if p.get("type") == "page" and "core.html#/flow/base/name-check-info" in (p.get("url") or ""):
            return p["webSocketDebuggerUrl"], p.get("url", "")
    for p in pages:
        u = p.get("url") or ""
        if p.get("type") == "page" and ":9087" in u and "icpsp-web-pc" in u:
            return p["webSocketDebuggerUrl"], u
    for p in pages:
        if p.get("type") == "page":
            return p["webSocketDebuggerUrl"], p.get("url", "")
    return None, None


def ev(ws, expr, msg_id=1, timeout=90000):
    ws.send(
        json.dumps(
            {
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "timeout": timeout},
            }
        )
    )
    end = time.time() + max(20, timeout / 1000 + 20)
    while True:
        if time.time() > end:
            return {"error": "cdp_eval_timeout"}
        try:
            raw = ws.recv()
        except Exception:
            continue
        try:
            m = json.loads(raw)
        except Exception:
            continue
        if m.get("id") == msg_id:
            return m.get("result", {}).get("result", {}).get("value")


def main():
    ws_url, cur = pick_ws()
    rec = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    rec["steps"].append({"step": "S0_pick", "data": {"url": cur}})
    if not ws_url:
        rec["error"] = "no_page"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {OUT}")
        return

    # 避免单 websocket 长时间挂住：每次 evaluate 新建连接（更稳）
    def e(js, timeout=90000):
        w = websocket.create_connection(ws_url, timeout=25)
        w.settimeout(2.0)
        try:
            return ev(w, js, msg_id=1, timeout=timeout)
        finally:
            try:
                w.close()
            except Exception:
                pass

    # 0) 确保在 name-check-info
    rec["steps"].append({"step": "S1_nav", "data": e(f"location.href={json.dumps(URL_NAMECHECK, ensure_ascii=False)}", timeout=60000)})
    time.sleep(5)

    # 1) 以“交互优先 + fallback set formInfo”的方式填充
    params = {
        # 行政区划下拉：优先选这个文本（支持模糊匹配）
        "district_text": "玉林市容县",
        # 字号候选（遇到禁限用词弹窗会轮换）
        "name_marks": ["智信五金", "智信百货", "智信商贸", "智信贸易"],
        # 行业关键词（输入后选择候选项）
        "industry_keyword": "批发",
        # 期望行业候选：优先匹配这个 code（如 F51747）或名称片段
        "industry_code_hint": "F51747",
        "industry_name_hint": "五金批发",
        # 组织形式：优先选择包含该文本的选项
        "organize_text": "所（个人独资）",
        # 企业名称后缀（个人独资常见）
        "name_suffix": "（个人独资）",
    }

    # 拆分为更短的 CDP eval，避免长 JS 导致 websocket 挂住
    js_cfg = json.dumps(params, ensure_ascii=False)

    rec["steps"].append(
        {
            "step": "S2a_set_cfg",
            "data": e(
                r"""(function(){
                  window.__nc_cfg = %s;
                  return {ok:true,keys:Object.keys(window.__nc_cfg||{})};
                })()"""
                % js_cfg,
                timeout=30000,
            ),
        }
    )

    rec["steps"].append(
        {
            "step": "S2b_fill",
            "data": e(
                r"""(async function(){
                  try{
                  const cfg = window.__nc_cfg || {};
                  function sleep(ms){return new Promise(r=>setTimeout(r,ms));}
                  function clean(s){return (s||'').replace(/\s+/g,' ').trim();}
                  function vis(el){return !!(el && el.offsetParent!==null);}
                  function qsa(sel){return Array.from(document.querySelectorAll(sel));}
                  function click(el){ if(!el) return false; ['mousedown','mouseup','click'].forEach(tp=>el.dispatchEvent(new MouseEvent(tp,{bubbles:true,cancelable:true,view:window}))); return true; }
                  function setInput(inp,val){
                    if(!inp) return false;
                    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;
                    if(setter) setter.call(inp, val);
                    else inp.value = val;
                    inp.dispatchEvent(new Event('input',{bubbles:true}));
                    inp.dispatchEvent(new Event('change',{bubbles:true}));
                    return true;
                  }
                  function modalText(){
                    const box = qsa('.el-message-box__wrapper,.el-dialog__wrapper').find(w=>vis(w));
                    if(!box) return '';
                    return clean(box.textContent||'');
                  }
                  function closeModalByText(t){
                    const btns = qsa('button,.el-button').filter(b=>vis(b) && !b.disabled);
                    const b = btns.find(x=>clean(x.textContent||'').includes(t));
                    if(b){ click(b); return true; }
                    return false;
                  }

                  function findIndexVm(){
                    function walk(vm,d){
                      if(!vm||d>25) return null;
                      const n = (vm.$options&&vm.$options.name)||'';
                      if(n==='index' && vm.$parent && vm.$parent.$options && vm.$parent.$options.name==='name-check-info') return vm;
                      const ch = vm.$children||[];
                      for(let i=0;i<ch.length;i++){ const r=walk(ch[i],d+1); if(r) return r; }
                      return null;
                    }
                    const app=document.getElementById('app');
                    return app&&app.__vue__?walk(app.__vue__,0):null;
                  }
                  function findVmByName(name){
                    function walk(vm,d){
                      if(!vm||d>25) return null;
                      const n=(vm.$options&&vm.$options.name)||'';
                      if(n===name) return vm;
                      const ch=vm.$children||[];
                      for(let i=0;i<ch.length;i++){ const r=walk(ch[i],d+1); if(r) return r; }
                      return null;
                    }
                    const app=document.getElementById('app');
                    return app&&app.__vue__?walk(app.__vue__,0):null;
                  }

                  const idx = findIndexVm();
                  const indVm = findVmByName('tni-industry-select');
                  const orgVm = findVmByName('organization-select');
                  if(!idx) return {ok:false,err:'no_index_vm',href:location.href,hash:location.hash};
                  idx.formInfo = idx.formInfo || {};
                  const trace=[];

                  // ===== A) 行政区划（交互：点 el-select，输入关键词，点下拉）=====
                  (function(){
                    const items=qsa('.el-form-item');
                    let it=null;
                    for(const x of items){
                      const lb=x.querySelector('.el-form-item__label');
                      if(lb && clean(lb.textContent).includes('行政区划')){ it=x; break; }
                    }
                    if(!it){ trace.push('dist:no_item'); return; }
                    const sel = it.querySelector('.el-select');
                    const inp = sel ? sel.querySelector('input.el-input__inner') : null;
                    if(inp){
                      click(inp);
                      // el-select 过滤通常需要输入
                      setInput(inp, cfg.district_text);
                      trace.push('dist:typed');
                    }else trace.push('dist:no_input');
                  })();
                  await sleep(600);
                  (function(){
                    const opts = qsa('.el-select-dropdown__item').filter(li=>vis(li));
                    let picked=null;
                    for(const o of opts){
                      const t=clean(o.textContent);
                      if(!t) continue;
                      if(t===cfg.district_text || t.includes(cfg.district_text) || cfg.district_text.includes(t)){
                        picked=o; break;
                      }
                    }
                    if(!picked && opts.length) picked=opts[opts.length-1];
                    if(picked){ click(picked); trace.push('dist:picked:'+clean(picked.textContent)); }
                    else trace.push('dist:no_option');
                  })();
                  await sleep(300);

                  // ===== B) 字号（输入 + 禁限用词弹窗处理）=====
                  function setNameMark(mark){
                    const items=qsa('.el-form-item');
                    let it=null;
                    for(const x of items){
                      const lb=x.querySelector('.el-form-item__label');
                      if(lb && clean(lb.textContent).includes('字号')){ it=x; break; }
                    }
                    const inp = it ? it.querySelector('input.el-input__inner') : null;
                    if(inp){
                      setInput(inp, mark);
                      trace.push('nameMark:set:'+mark);
                    }else{
                      // fallback to vm
                      try{ idx.$set(idx.formInfo,'nameMark',mark); }catch(e){}
                      trace.push('nameMark:set_vm:'+mark);
                    }
                  }

                  let finalNameMark = null;
                  for(const mark of (cfg.name_marks||[])){
                    setNameMark(mark);
                    await sleep(350);
                    const mt = modalText();
                    if(mt && (mt.includes('禁限用') || mt.includes('禁用') || mt.includes('限用'))){
                      closeModalByText('我已知晓') || closeModalByText('确定');
                      trace.push('nameMark:modal:'+mt.slice(0,40));
                      continue;
                    }
                    finalNameMark = mark;
                    break;
                  }
                  if(!finalNameMark){
                    finalNameMark = (cfg.name_marks||[])[0] || '智信商贸';
                    trace.push('nameMark:fallback:'+finalNameMark);
                  }

                  // 同步 name 字段（有些校验依赖 name）
                  try{
                    const distName = idx.formInfo.namePre || idx.formInfo.distName || '';
                    const industryName = idx.formInfo.industryName || '';
                    const orgName = idx.formInfo.organizeName || '';
                    const name = (finalNameMark || '') + (cfg.name_suffix||'');
                    idx.$set(idx.formInfo,'name', name);
                  }catch(e){}

                  // ===== C) 行业（交互：输入关键词 → 从下拉候选中选中包含编号项）=====
                  let industryInputEl = null;
                  (function(){
                    const items=qsa('.el-form-item');
                    let it=null;
                    for(const x of items){
                      const lb=x.querySelector('.el-form-item__label');
                      if(lb && (clean(lb.textContent).includes('行业') || clean(lb.textContent).includes('经营特点'))){ it=x; break; }
                    }
                    const inp = it ? it.querySelector('input.el-input__inner') : null;
                    if(inp){
                      industryInputEl = inp;
                      click(inp);
                      setInput(inp, cfg.industry_keyword);
                      trace.push('industry:typed:'+cfg.industry_keyword);
                    } else trace.push('industry:no_input');
                  })();
                  await sleep(600);
                  async function pickIndustryFromSuggest(){
                    // ElementUI autocomplete suggestion: must CLICK one option (not just type)
                    const wrap = qsa('.el-autocomplete-suggestion__wrap').find(vis) || null;
                    const ul = qsa('.el-autocomplete-suggestion__list').find(vis) || null;
                    if(!wrap || !ul) return '';

                    function getAllLi(){ return qsa('.el-autocomplete-suggestion li'); }
                    function bestPick(lis){
                      let picked=null;
                      if(cfg.industry_code_hint){
                        picked = lis.find(li=>clean(li.textContent).includes(cfg.industry_code_hint)) || null;
                      }
                      if(!picked && cfg.industry_name_hint){
                        picked = lis.find(li=>clean(li.textContent).includes(cfg.industry_name_hint)) || null;
                      }
                      if(!picked){
                        // heuristics: prefer entries containing "五金" or "批发"
                        picked = lis.find(li=>/五金/.test(clean(li.textContent))) || null;
                      }
                      if(!picked && lis.length) picked = lis[0];
                      return picked;
                    }

                    // scrollable; options may be outside viewport
                    const maxScroll = Math.max(0, wrap.scrollHeight - wrap.clientHeight);
                    const steps = 10;
                    for(let i=0;i<=steps;i++){
                      wrap.scrollTop = Math.floor(maxScroll * (i/steps));
                      await sleep(120);
                      const lis = getAllLi();
                      const picked = bestPick(lis);
                      if(picked){
                        picked.scrollIntoView({block:'center'});
                        await sleep(60);
                        click(picked);
                        return clean(picked.textContent);
                      }
                    }
                    return '';
                  }
                  const pickedIndustryText = await pickIndustryFromSuggest();
                  if(pickedIndustryText) {
                    trace.push('industry:picked:'+pickedIndustryText.slice(0,40));
                  } else {
                    // Fallback: keyboard select first suggestion (ArrowDown + Enter)
                    try{
                      if(industryInputEl){
                        industryInputEl.focus();
                        industryInputEl.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'ArrowDown',code:'ArrowDown',keyCode:40,which:40}));
                        await sleep(120);
                        industryInputEl.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));
                        trace.push('industry:key_select');
                      } else {
                        trace.push('industry:key_select:no_input');
                      }
                    }catch(e){
                      trace.push('industry:key_select_err:'+String(e).slice(0,80));
                    }
                  }
                  await sleep(500);

                  // 从 pickedIndustryText 解析 code（形如：五金批发(行业类型：[F51747]五金批发)）
                  let parsedCode = null;
                  let parsedName = null;
                  if(pickedIndustryText){
                    const m = pickedIndustryText.match(/\[([A-Z0-9]+)\]/);
                    if(m) parsedCode = m[1];
                    parsedName = pickedIndustryText.replace(/\s+/g,' ').trim().slice(0,60);
                  }

                  // 用组件/VM兜底同步字段（避免 UI 选中没写入 formInfo）
                  try{
                    if(indVm){
                      if(typeof indVm.renderList==='function') await indVm.renderList();
                    }
                  }catch(e){}
                  try{
                    // Force-set if still not written by component
                    if(parsedCode && (!idx.formInfo.industry || String(idx.formInfo.industry).length===0)){
                      idx.$set(idx.formInfo,'industry',parsedCode);
                      idx.$set(idx.formInfo,'industryName', cfg.industry_name_hint || parsedName || '');
                      idx.$set(idx.formInfo,'industrySpecial', cfg.industry_keyword || '');
                      idx.$set(idx.formInfo,'allIndKeyWord', cfg.industry_keyword || '');
                      idx.$set(idx.formInfo,'showKeyWord', cfg.industry_keyword || '');
                      trace.push('industry:set_vm:'+parsedCode);
                    }
                  }catch(e){}

                  // ===== D) 组织形式（交互：打开下拉/网格，点包含“所（个人独资）”的项）=====
                  (function(){
                    const items=qsa('.el-form-item');
                    let it=null;
                    for(const x of items){
                      const lb=x.querySelector('.el-form-item__label');
                      if(lb && clean(lb.textContent).includes('组织形式')){ it=x; break; }
                    }
                    const inp = it ? it.querySelector('.el-select input.el-input__inner') : null;
                    if(inp){ click(inp); trace.push('org:open'); }
                    else trace.push('org:no_input');
                  })();
                  await sleep(400);
                  (function(){
                    // 优先在下拉或网格里找匹配文本
                    const nodes = qsa('.el-select-dropdown__item, .el-dialog__wrapper .el-dialog, .el-popover, .el-scrollbar__view *')
                      .filter(n=>vis(n))
                      .filter(n=>['LI','SPAN','DIV','LABEL','A'].includes(n.tagName));
                    let hit=null;
                    for(const n of nodes){
                      const t=clean(n.textContent);
                      if(!t) continue;
                      if(cfg.organize_text && t.includes(cfg.organize_text)){ hit=n; break; }
                      if(!hit && (t.includes('个人独资') && (t.includes('所')||t.includes('中心')||t.includes('厂')||t.includes('店')))) hit=n;
                    }
                    if(hit){ click(hit); trace.push('org:picked:'+clean(hit.textContent).slice(0,20)); }
                    else trace.push('org:no_hit');
                  })();
                  await sleep(300);
                  // VM fallback：若 organization-select 有 groupList 则择一写入 organize
                  try{
                    if((!idx.formInfo.organize || String(idx.formInfo.organize).length===0) && orgVm && Array.isArray(orgVm.groupList) && orgVm.groupList.length){
                      let it=null;
                      for(const x of orgVm.groupList){
                        const t = (x.label||x.name||x.text||'')+'';
                        if(cfg.organize_text && t.includes(cfg.organize_text)){ it=x; break; }
                        if(t.includes('个人独资')){ it=x; break; }
                      }
                      if(!it) it = orgVm.groupList[0];
                      const val = (it.value||it.code||it.id||it.dictCode||it.organizeCode||'')+'';
                      if(val){ idx.$set(idx.formInfo,'organize',val); trace.push('org:set_vm:'+val); }
                    }
                  }catch(e){}

                  // ===== E) 勾选须知 & 点击 保存并下一步 =====
                  (function(){
                    const agree = qsa('label,span,div').find(x=>vis(x) && clean(x.textContent).includes('我已阅读并同意'));
                    if(agree){ click(agree); trace.push('agree:clicked'); }
                  })();
                  await sleep(200);
                  // 关掉“请选择是否需要名称”等弹窗
                  closeModalByText('确定');
                  closeModalByText('我已知晓');
                  await sleep(200);
                  (function(){
                    const save = qsa('button,.el-button').find(x=>vis(x) && !x.disabled && clean(x.textContent).replace(/\s+/g,'').includes('保存并下一步'));
                    if(save){ click(save); trace.push('saveNext:clicked'); }
                    else trace.push('saveNext:not_found');
                  })();

                  function flat(o){
                    const r={};
                    Object.keys(o||{}).forEach(k=>{
                      const v=o[k];
                      if(v===null || v===undefined || ['string','number','boolean'].includes(typeof v)) r[k]=v;
                    });
                    return r;
                  }
                  const errs = qsa('.el-form-item__error,.el-message').map(x=>clean(x.textContent)).filter(Boolean);
                  return {
                    ok:true,
                    href:location.href,
                    hash:location.hash,
                    trace:trace,
                    modal:modalText().slice(0,120),
                    errors:errs.slice(0,12),
                    formInfo:flat(idx.formInfo)
                  };
                  }catch(e){
                    return {ok:false,err:String(e),stack:(e&&e.stack)?String(e.stack):'',href:location.href,hash:location.hash};
                  }
                })()"""  # noqa: E501
                ,
                timeout=90000,
            ),
        }
    )

    time.sleep(6)
    rec["steps"].append(
        {
            "step": "S3_after",
            "data": e(
                r"""(function(){
                  var errs=[...document.querySelectorAll('.el-form-item__error,.el-message')].map(e=>(e.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
                  var txt=(document.body.innerText||'');
                  return {href:location.href,hash:location.hash,errors:errs.slice(0,12),hasYunbangban:txt.indexOf('云帮办流程模式选择')>=0,hasNameCheck:location.href.indexOf('name-check-info')>=0};
                })()""",
                timeout=30000,
            ),
        }
    )

    # ws already closed per call
    rec["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()

